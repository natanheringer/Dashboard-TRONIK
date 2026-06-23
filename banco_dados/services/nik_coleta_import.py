"""
Importação de coletas via CSV no chat Nik — fluxo Preview → Confirma → Executa.

O parsing acontece no upload (rota), gerando um "pending_import" no cache.
A confirmação ("CONFIRMAR") dispara os INSERTs via coleta_service.criar_coleta(),
com dedup, escopo de parceiro e resumo por linha.
"""

from __future__ import annotations

import contextlib
import logging
import os
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import Coleta, Coletor
from banco_dados.services import coleta_service, nik_coleta_chat as coleta_chat
from banco_dados.services.relatorio_service import lucro_liquido_total_coleta
from banco_dados.utils.cache import obter_cache

logger = logging.getLogger(__name__)

_PENDING_TTL = 1800
NIK_IMPORT_MAX_ROWS = int(os.getenv("NIK_IMPORT_MAX_ROWS", "500"))
_PRECO_PADRAO = float(os.getenv("NIK_COLETA_PRECO_COMBUSTIVEL_PADRAO", "5.5"))


def _chave_pending_import(usuario_id: int | None, thread_id: str) -> str:
    uid = usuario_id if usuario_id is not None else 0
    return f"nik:pending_import:{uid}:{thread_id}"


def limpar_pending_import(usuario_id: int | None, thread_id: str) -> None:
    obter_cache().invalidar(_chave_pending_import(usuario_id, thread_id))


def obter_pending_import(usuario_id: int | None, thread_id: str) -> dict[str, Any] | None:
    payload = obter_cache().obter(_chave_pending_import(usuario_id, thread_id), _PENDING_TTL)
    return payload if isinstance(payload, dict) else None


def _armazenar_pending_import(usuario_id: int | None, thread_id: str, dados: dict[str, Any]) -> None:
    obter_cache().definir(_chave_pending_import(usuario_id, thread_id), dados)


def _to_float(valor: Any) -> float | None:
    if valor in (None, ""):
        return None
    with contextlib.suppress(TypeError, ValueError):
        return float(str(valor).replace(",", "."))
    return None


def _to_int(valor: Any) -> int | None:
    if valor in (None, ""):
        return None
    with contextlib.suppress(TypeError, ValueError):
        return int(float(str(valor).replace(",", ".")))
    return None


def _normalizar_data(valor: str) -> str | None:
    raw = (valor or "").strip()
    if not raw:
        return None
    # ISO direto
    with contextlib.suppress(ValueError):
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).isoformat()
    # DD/MM/YYYY
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        with contextlib.suppress(ValueError):
            return datetime.strptime(raw, fmt).isoformat()
    return None


def _detectar_duplicata(db: Session, coletor_id: int, data_hora: str, volume: float | None) -> bool:
    with contextlib.suppress(ValueError, TypeError):
        dt = datetime.fromisoformat(data_hora.replace("Z", "+00:00"))
        q = db.query(Coleta).filter(
            Coleta.coletor_id == coletor_id,
            Coleta.data_hora == dt,
        )
        if volume is not None:
            q = q.filter(Coleta.volume_estimado == volume)
        return db.query(q.exists()).scalar() is True
    return False


def _normalizar_linha(
    db: Session,
    row: dict[str, str],
    *,
    escopo_parceiro_id: int | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    erros: list[str] = []
    coletor_id = _to_int(row.get("coletor_id"))
    parceiro_id = _to_int(row.get("parceiro_id"))
    volume = _to_float(row.get("volume_kg"))
    km = _to_float(row.get("km_percorrido_km"))
    preco = _to_float(row.get("preco_combustivel")) or _PRECO_PADRAO
    data_iso = _normalizar_data(row.get("data_hora", ""))
    tipo = (row.get("tipo_operacao") or "Avulsa").strip() or "Avulsa"

    if coletor_id is None:
        erros.append("coletor_id ausente/ inválido")
    if data_iso is None:
        erros.append("data_hora ausente/ inválida")

    coletor = db.query(Coletor).filter(Coletor.id == coletor_id).first() if coletor_id else None
    if coletor_id is not None and coletor is None:
        erros.append(f"coletor #{coletor_id} não encontrado")

    # Escopo de parceiro: usuário não-admin só importa do próprio parceiro
    if escopo_parceiro_id is not None:
        if parceiro_id is not None and parceiro_id != escopo_parceiro_id:
            erros.append("parceiro fora do seu escopo")
        parceiro_id = escopo_parceiro_id
        if coletor is not None and coletor.parceiro_id not in (None, escopo_parceiro_id):
            erros.append("coletor não pertence ao seu parceiro")

    if erros:
        return None, erros

    payload = {
        "coletor_id": coletor_id,
        "parceiro_id": parceiro_id,
        "data_hora": data_iso,
        "volume_estimado": volume,
        "km_percorrido": km,
        "preco_combustivel": preco,
        "tipo_operacao": tipo,
        "lucro_por_kg": (
            lucro_liquido_total_coleta(volume, km, preco) / volume
            if volume and volume > 0
            else 0
        ),
    }
    val_erros = coleta_service.validar_dados_coleta(payload, criar=True, db=db)
    if val_erros:
        return None, val_erros
    return payload, []


def preparar_import_coletas(
    db: Session,
    linhas: list[dict[str, str]],
    *,
    usuario_id: int | None,
    thread_id: str,
    filename: str,
) -> dict[str, Any]:
    """Valida as linhas do CSV e guarda um pending_import no cache."""
    if coleta_chat._obter_pending(usuario_id, thread_id):
        return {
            "status": "conflito",
            "texto": (
                "Há uma coleta aguardando confirmação. "
                "Digite CONFIRMAR ou CANCELAR antes de importar um arquivo."
            ),
            "pendente": False,
        }

    if len(linhas) > NIK_IMPORT_MAX_ROWS:
        return {
            "status": "limite",
            "texto": f"O arquivo tem {len(linhas)} linhas; o limite é {NIK_IMPORT_MAX_ROWS}.",
            "pendente": False,
        }

    escopo = coleta_chat._escopo_parceiro_usuario(db, usuario_id)
    rows: list[dict[str, Any]] = []
    validas = invalidas = duplicadas = 0
    preview: list[dict[str, Any]] = []

    for idx, row in enumerate(linhas, start=2):  # linha 1 = cabeçalho
        payload, erros = _normalizar_linha(db, row, escopo_parceiro_id=escopo)
        if payload is None:
            invalidas += 1
            rows.append({"linha": idx, "status": "erro", "erros": erros})
            if len(preview) < 5:
                preview.append({"linha": idx, "status": "erro", "erros": erros})
            continue
        dup = _detectar_duplicata(
            db, payload["coletor_id"], payload["data_hora"], payload.get("volume_estimado")
        )
        if dup:
            duplicadas += 1
            rows.append({"linha": idx, "status": "duplicada", "payload": payload})
            if len(preview) < 5:
                preview.append({"linha": idx, "status": "duplicada", "coletor_id": payload["coletor_id"]})
            continue
        validas += 1
        rows.append({"linha": idx, "status": "ok", "payload": payload})
        if len(preview) < 5:
            preview.append(
                {
                    "linha": idx,
                    "status": "ok",
                    "coletor_id": payload["coletor_id"],
                    "volume_kg": payload.get("volume_estimado"),
                    "data_hora": payload["data_hora"],
                }
            )

    pending = {
        "filename": filename,
        "modo": "import_coletas",
        "total_linhas": len(linhas),
        "validas": validas,
        "invalidas": invalidas,
        "duplicadas": duplicadas,
        "preview_rows": preview,
        "rows": rows,
        "escopo_parceiro_id": escopo,
        "usuario_id": usuario_id,
    }

    if validas == 0:
        limpar_pending_import(usuario_id, thread_id)
        return {
            "status": "sem_validas",
            "texto": (
                f"Nenhuma das {len(linhas)} linha(s) está pronta para importar "
                f"({invalidas} inválida(s), {duplicadas} duplicada(s)). "
                "Verifique as colunas: data_hora, coletor_id, volume_kg, km_percorrido_km."
            ),
            "pendente": False,
            "stats": {"validas": validas, "invalidas": invalidas, "duplicadas": duplicadas},
            "preview": preview,
        }

    _armazenar_pending_import(usuario_id, thread_id, pending)
    return {
        "status": "aguardando_confirmacao",
        "texto": formatar_preview_import(pending),
        "pendente": True,
        "stats": {
            "total": len(linhas),
            "validas": validas,
            "invalidas": invalidas,
            "duplicadas": duplicadas,
        },
        "preview": preview,
    }


def formatar_preview_import(pending: dict[str, Any]) -> str:
    linhas = [
        f"IMPORTAR {pending['validas']} COLETA(S) — {pending.get('filename', 'arquivo.csv')}",
        f"Válidas: {pending['validas']} | Inválidas: {pending['invalidas']} | Duplicadas: {pending['duplicadas']}",
    ]
    for p in pending.get("preview_rows", [])[:5]:
        if p.get("status") == "ok":
            linhas.append(
                f"  • Linha {p['linha']}: coletor #{p['coletor_id']}, "
                f"{p.get('volume_kg', '—')} kg, {str(p.get('data_hora', ''))[:10]}"
            )
        elif p.get("status") == "duplicada":
            linhas.append(f"  • Linha {p['linha']}: duplicada (coletor #{p.get('coletor_id')})")
        else:
            linhas.append(f"  • Linha {p['linha']}: erro — {'; '.join(p.get('erros', []))}")
    linhas.append("Digite CONFIRMAR para importar ou CANCELAR para descartar.")
    return "\n".join(linhas)


def executar_import_coletas(
    db: Session,
    usuario_id: int | None,
    thread_id: str,
) -> dict[str, Any]:
    pending = obter_pending_import(usuario_id, thread_id)
    if not pending:
        return {
            "status": "sem_pendencia",
            "texto": "Não há importação pendente nesta conversa.",
            "pendente": False,
        }

    escopo = coleta_chat._escopo_parceiro_usuario(db, usuario_id)
    if pending.get("escopo_parceiro_id") not in (None, escopo) and escopo is not None:
        limpar_pending_import(usuario_id, thread_id)
        return {
            "status": "escopo_negado",
            "texto": "Você só pode importar coletas do seu parceiro vinculado.",
            "pendente": False,
        }

    criadas = 0
    falhas = 0
    coleta_ids: list[int] = []
    erros_linha: list[dict[str, Any]] = []

    for item in pending.get("rows", []):
        if item.get("status") != "ok":
            continue
        payload = item.get("payload")
        try:
            nova = coleta_service.criar_coleta(db, payload)
            criadas += 1
            coleta_ids.append(nova.id)
        except Exception as exc:  # noqa: BLE001
            falhas += 1
            erros_linha.append({"linha": item.get("linha"), "erro": str(exc)})
            logger.exception("Falha ao importar coleta da linha %s", item.get("linha"))

    limpar_pending_import(usuario_id, thread_id)
    resumo = (
        f"Importação concluída: {criadas} coleta(s) criada(s), "
        f"{pending.get('duplicadas', 0)} duplicada(s) ignorada(s), {falhas} falha(s)."
    )
    return {
        "status": "ok",
        "texto": resumo,
        "pendente": False,
        "criadas": criadas,
        "duplicadas": pending.get("duplicadas", 0),
        "falhas": falhas,
        "coleta_ids": coleta_ids,
        "erros_linha": erros_linha,
    }


def processar_mensagem_import(
    db: Session,
    mensagem: str,
    usuario_id: int | None,
    thread_id: str,
) -> dict[str, Any] | None:
    """Intercepta confirmação/cancelamento de uma importação pendente."""
    pending = obter_pending_import(usuario_id, thread_id)
    if not pending:
        return None

    if coleta_chat.mensagem_e_confirmacao_coleta(mensagem):
        return executar_import_coletas(db, usuario_id, thread_id)

    if coleta_chat.mensagem_e_cancelamento_coleta(mensagem):
        limpar_pending_import(usuario_id, thread_id)
        return {
            "status": "cancelado",
            "texto": "Importação de coletas cancelada.",
            "pendente": False,
        }

    return {
        "status": "aguardando_confirmacao",
        "texto": (
            "Há uma importação aguardando confirmação.\n\n" + formatar_preview_import(pending)
        ),
        "pendente": True,
    }
