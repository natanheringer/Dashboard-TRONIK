"""
Cadastro de coletas via chat Nik — fluxo Extrai → Confirma → Executa.

A LLM/heurística só extrai campos; o INSERT usa coleta_service.criar_coleta().
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import Coletor, Parceiro, Usuario
from banco_dados.services import coleta_service, nik_provider as provider, nik_validacao as val
from banco_dados.services.relatorio_service import lucro_liquido_total_coleta
from banco_dados.utils.cache import obter_cache

logger = logging.getLogger(__name__)

_PENDING_TTL = 1800
_PRECO_COMBUSTIVEL_PADRAO = float(os.getenv("NIK_COLETA_PRECO_COMBUSTIVEL_PADRAO", "5.5"))

_SYSTEM_EXTRAIR_COLETA = """\
Extraia dados para cadastrar uma coleta operacional Tronik.
Responda SOMENTE JSON:
{"parceiro_nome":"...","coletor_ref":"L037 ou null","volume_kg":0,"km_percorrido_km":0,"data_coleta":"YYYY-MM-DD ou hoje","tipo_operacao":"Avulsa ou Campanha ou null","preco_combustivel":null}
Regras: volume_kg é peso em kg (NUNCA confunda com km). km_percorrido_km é distância. Use null se não souber.\
"""


def _chave_pending(usuario_id: int | None, thread_id: str) -> str:
    uid = usuario_id if usuario_id is not None else 0
    return f"nik:pending_coleta:{uid}:{thread_id}"


def _limpar_pending(usuario_id: int | None, thread_id: str) -> None:
    obter_cache().invalidar(_chave_pending(usuario_id, thread_id))


def _obter_pending(usuario_id: int | None, thread_id: str) -> dict[str, Any] | None:
    payload = obter_cache().obter(_chave_pending(usuario_id, thread_id), _PENDING_TTL)
    return payload if isinstance(payload, dict) else None


def _armazenar_pending(usuario_id: int | None, thread_id: str, dados: dict[str, Any]) -> None:
    obter_cache().definir(_chave_pending(usuario_id, thread_id), dados)


def mensagem_e_confirmacao_coleta(mensagem: str) -> bool:
    msg = (mensagem or "").strip().lower()
    return msg in {
        "confirmar",
        "confirma",
        "confirmo",
        "sim",
        "ok",
        "pode salvar",
        "salvar",
        "salva",
        "prosseguir",
    }


def mensagem_e_cancelamento_coleta(mensagem: str) -> bool:
    msg = (mensagem or "").strip().lower()
    return msg in {"cancelar", "cancela", "cancelo", "nao", "não", "abortar", "desistir"}


def mensagem_pede_cadastrar_coleta(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    verbos = [
        "cadastra",
        "cadastrar",
        "cadastro",
        "adiciona",
        "adicionar",
        "registra",
        "registrar",
        "insere",
        "inserir",
        "nova coleta",
        "novo registro de coleta",
        "lança coleta",
        "lancar coleta",
        "lançar coleta",
        "inclui coleta",
        "incluir coleta",
        "cria coleta",
        "criar coleta",
        "registrar coleta",
    ]
    if any(v in msg for v in verbos):
        return True
    return bool("coleta" in msg and any(v in msg for v in ["cadastra", "adiciona", "registra", "insere", "lança", "lancar", "lançar"]))


def _extrair_volume_kg(texto: str) -> float | None:
    msg = texto or ""
    for pattern in (
        r"(\d+(?:[.,]\d+)?)\s*kg\b",
        r"\bvolume[:\s]+(\d+(?:[.,]\d+)?)",
        r"\bpeso[:\s]+(\d+(?:[.,]\d+)?)",
    ):
        m = re.search(pattern, msg, flags=re.I)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except ValueError:
                continue
    return None


def _extrair_km(texto: str) -> float | None:
    msg = texto or ""
    for pattern in (
        r"(\d+(?:[.,]\d+)?)\s*km\b",
        r"\brodou\s+(\d+(?:[.,]\d+)?)",
        r"\bquilometragem[:\s]+(\d+(?:[.,]\d+)?)",
        r"\bdist[aâ]ncia[:\s]+(\d+(?:[.,]\d+)?)",
    ):
        m = re.search(pattern, msg, flags=re.I)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except ValueError:
                continue
    return None


def _extrair_coletor_ref(texto: str) -> int | None:
    for pattern in (
        r"#L0*(\d{1,4})\b",
        r"\b[lL]\s*0*(\d{1,4})\b",
        r"\bcoletor\s*#?\s*0*(\d{1,4})\b",
    ):
        m = re.search(pattern, texto or "", flags=re.I)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def _extrair_parceiro_nome(db: Session, mensagem: str) -> str | None:
    msg = (mensagem or "").lower()
    rows = db.query(Parceiro.nome).filter(Parceiro.ativo.is_(True)).all()
    for (nome,) in sorted(rows, key=lambda r: len(r[0] or ""), reverse=True):
        nome_l = (nome or "").strip().lower()
        if nome_l and nome_l in msg:
            return nome.strip()
    m = re.search(r"\b(?:parceiro|cliente|instituto|empresa)\s+([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9\s.&-]{2,60})", mensagem or "", flags=re.I)
    if m:
        return m.group(1).strip(" .,;:")
    return None


def _extrair_data_coleta(texto: str) -> date:
    msg = (texto or "").lower()
    if "ontem" in msg:
        return date.today() - timedelta(days=1)
    if "hoje" in msg or "agora" in msg:
        return date.today()
    for a, b, c in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", texto or ""):
        try:
            return date(int(a), int(b), int(c))
        except ValueError:
            continue
    for d, m, y in re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b", texto or ""):
        try:
            return date(int(y), int(m), int(d))
        except ValueError:
            continue
    return date.today()


def _escopo_parceiro_usuario(db: Session, usuario_id: int | None) -> int | None:
    if usuario_id is None:
        return None
    user = db.get(Usuario, usuario_id)
    if not user or getattr(user, "admin", False):
        return None
    pid = getattr(user, "parceiro_id", None)
    return int(pid) if pid is not None else None


def _resolver_parceiro_id(
    db: Session,
    nome: str | None,
    *,
    forcar_parceiro_id: int | None = None,
) -> tuple[int | None, str | None]:
    if forcar_parceiro_id is not None:
        row = db.query(Parceiro).filter(Parceiro.id == forcar_parceiro_id, Parceiro.ativo.is_(True)).first()
        if row:
            return row.id, row.nome
        return None, None
    if not nome:
        return None, None
    nome_l = nome.strip().lower()
    for p in db.query(Parceiro).filter(Parceiro.ativo.is_(True)).all():
        pn = (p.nome or "").strip().lower()
        if pn == nome_l or nome_l in pn or pn in nome_l:
            return p.id, p.nome
    return None, None


def _resolver_coletor_id(
    db: Session,
    *,
    coletor_ref: int | None,
    parceiro_id: int | None,
) -> tuple[int | None, str | None]:
    if coletor_ref is not None:
        c = db.query(Coletor).filter(Coletor.id == coletor_ref).first()
        if c:
            return c.id, c.localizacao
        return None, None
    if parceiro_id is not None:
        c = (
            db.query(Coletor)
            .filter(Coletor.parceiro_id == parceiro_id)
            .order_by(Coletor.id.asc())
            .first()
        )
        if c:
            return c.id, c.localizacao
    return None, None


def _extrair_coleta_heuristica(
    db: Session,
    mensagem: str,
    usuario_id: int | None,
) -> dict[str, Any]:
    escopo_pid = _escopo_parceiro_usuario(db, usuario_id)
    volume = _extrair_volume_kg(mensagem)
    km = _extrair_km(mensagem)
    coletor_ref = _extrair_coletor_ref(mensagem)
    parceiro_nome = _extrair_parceiro_nome(db, mensagem)
    parceiro_id, parceiro_resolvido = _resolver_parceiro_id(
        db, parceiro_nome, forcar_parceiro_id=escopo_pid
    )
    coletor_id, coletor_nome = _resolver_coletor_id(db, coletor_ref=coletor_ref, parceiro_id=parceiro_id)
    data_coleta = _extrair_data_coleta(mensagem)
    return {
        "parceiro_id": parceiro_id,
        "parceiro_nome": parceiro_resolvido or parceiro_nome,
        "coletor_id": coletor_id,
        "coletor_nome": coletor_nome,
        "volume_kg": volume,
        "km_percorrido_km": km,
        "data_coleta": data_coleta.isoformat(),
        "preco_combustivel": _PRECO_COMBUSTIVEL_PADRAO,
        "tipo_operacao": "Avulsa",
        "fonte_extracao": "heuristica",
    }


def _extrair_coleta_llm(mensagem: str) -> dict[str, Any] | None:
    if os.getenv("NIK_ENABLED", "true").strip().lower() in {"0", "false", "no"}:
        return None
    resposta = provider.chamar_modelo(
        _SYSTEM_EXTRAIR_COLETA,
        f"Mensagem do operador:\n{mensagem.strip()}",
        modelo=os.getenv("NIK_MODELO_OPS", "llama-3.1-8b-instant"),
        max_tokens=256,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    if not resposta.sucesso:
        return None
    parsed = val.extrair_json_do_output(resposta.texto)
    return parsed if isinstance(parsed, dict) else None


def _mesclar_extracao(
    db: Session,
    heuristica: dict[str, Any],
    llm: dict[str, Any] | None,
    usuario_id: int | None,
) -> dict[str, Any]:
    out = dict(heuristica)
    if not llm:
        return out
    if llm.get("parceiro_nome") and not out.get("parceiro_id"):
        pid, pnome = _resolver_parceiro_id(
            db,
            str(llm.get("parceiro_nome")),
            forcar_parceiro_id=_escopo_parceiro_usuario(db, usuario_id),
        )
        if pid:
            out["parceiro_id"] = pid
            out["parceiro_nome"] = pnome
    if out.get("volume_kg") is None and llm.get("volume_kg") is not None:
        with contextlib.suppress(TypeError, ValueError):
            out["volume_kg"] = float(llm["volume_kg"])
    if out.get("km_percorrido_km") is None and llm.get("km_percorrido_km") is not None:
        with contextlib.suppress(TypeError, ValueError):
            out["km_percorrido_km"] = float(llm["km_percorrido_km"])
    ref = llm.get("coletor_ref")
    if out.get("coletor_id") is None and ref:
        m = re.search(r"(\d+)", str(ref))
        if m:
            cid, cnome = _resolver_coletor_id(db, coletor_ref=int(m.group(1)), parceiro_id=out.get("parceiro_id"))
            if cid:
                out["coletor_id"] = cid
                out["coletor_nome"] = cnome
    if llm.get("data_coleta"):
        raw = str(llm["data_coleta"]).strip().lower()
        if raw == "hoje":
            out["data_coleta"] = date.today().isoformat()
        else:
            with contextlib.suppress(ValueError):
                out["data_coleta"] = date.fromisoformat(raw[:10]).isoformat()
    if llm.get("tipo_operacao"):
        out["tipo_operacao"] = str(llm["tipo_operacao"])[:50]
    if llm.get("preco_combustivel") is not None:
        with contextlib.suppress(TypeError, ValueError):
            out["preco_combustivel"] = float(llm["preco_combustivel"])
    out["fonte_extracao"] = "heuristica+llm" if llm else out.get("fonte_extracao")
    if out.get("coletor_id") is None and out.get("parceiro_id"):
        cid, cnome = _resolver_coletor_id(db, coletor_ref=None, parceiro_id=out["parceiro_id"])
        if cid:
            out["coletor_id"] = cid
            out["coletor_nome"] = cnome
    return out


def _validar_extracao(dados: dict[str, Any]) -> list[str]:
    erros: list[str] = []
    if not dados.get("parceiro_id"):
        erros.append("Informe o parceiro (nome reconhecido no sistema).")
    vol = dados.get("volume_kg")
    if vol is None or float(vol) <= 0:
        erros.append("Informe o volume em kg (ex.: 450 kg).")
    km = dados.get("km_percorrido_km")
    if km is None or float(km) < 0:
        erros.append("Informe a quilometragem em km (ex.: 28 km).")
    if not dados.get("coletor_id"):
        erros.append("Não encontrei coletor para esse parceiro — informe o coletor (ex.: L037).")
    return erros


def formatar_confirmacao_coleta(dados: dict[str, Any]) -> str:
    vol = dados.get("volume_kg")
    km = dados.get("km_percorrido_km")
    lucro = lucro_liquido_total_coleta(vol, km, dados.get("preco_combustivel"))
    return (
        "CONFIRMAR NOVA COLETA\n"
        f"Parceiro: {dados.get('parceiro_nome', '—')}\n"
        f"Coletor: {dados.get('coletor_nome', '—')} (#{dados.get('coletor_id')})\n"
        f"Data: {dados.get('data_coleta')}\n"
        f"Volume: {vol} kg\n"
        f"Quilometragem: {km} km\n"
        f"Combustível: R$ {float(dados.get('preco_combustivel', 0)):.2f}/L\n"
        f"Lucro líquido estimado: R$ {lucro:.2f}\n"
        "Digite CONFIRMAR para salvar ou CANCELAR para descartar."
    )


def preparar_cadastro_coleta(
    db: Session,
    mensagem: str,
    usuario_id: int | None,
    thread_id: str,
) -> dict[str, Any]:
    heur = _extrair_coleta_heuristica(db, mensagem, usuario_id)
    llm = None
    if heur.get("volume_kg") is None or heur.get("km_percorrido_km") is None or not heur.get("parceiro_id"):
        llm = _extrair_coleta_llm(mensagem)
    dados = _mesclar_extracao(db, heur, llm, usuario_id)
    erros = _validar_extracao(dados)
    if erros:
        return {
            "status": "erro_extracao",
            "texto": "Não consegui montar a coleta. " + " ".join(erros),
            "pendente": False,
        }
    _armazenar_pending(usuario_id, thread_id, dados)
    return {
        "status": "aguardando_confirmacao",
        "texto": formatar_confirmacao_coleta(dados),
        "pendente": True,
        "dados": dados,
    }


def executar_cadastro_coleta(
    db: Session,
    usuario_id: int | None,
    thread_id: str,
) -> dict[str, Any]:
    pending = _obter_pending(usuario_id, thread_id)
    if not pending:
        return {
            "status": "sem_pendencia",
            "texto": "Não há coleta pendente de confirmação nesta conversa.",
            "pendente": False,
        }

    escopo = _escopo_parceiro_usuario(db, usuario_id)
    if escopo is not None and pending.get("parceiro_id") != escopo:
        _limpar_pending(usuario_id, thread_id)
        return {
            "status": "escopo_negado",
            "texto": "Você só pode cadastrar coletas do seu parceiro vinculado.",
            "pendente": False,
        }

    vol = float(pending["volume_kg"])
    km = float(pending["km_percorrido_km"])
    preco = float(pending.get("preco_combustivel") or _PRECO_COMBUSTIVEL_PADRAO)
    data_iso = pending.get("data_coleta") or date.today().isoformat()
    data_hora = f"{data_iso}T12:00:00"

    payload = {
        "coletor_id": int(pending["coletor_id"]),
        "parceiro_id": pending.get("parceiro_id"),
        "data_hora": data_hora,
        "volume_estimado": vol,
        "km_percorrido": km,
        "preco_combustivel": preco,
        "tipo_operacao": pending.get("tipo_operacao") or "Avulsa",
        "lucro_por_kg": lucro_liquido_total_coleta(vol, km, preco) / vol if vol > 0 else 0,
    }

    erros = coleta_service.validar_dados_coleta(payload, criar=True, db=db)
    if erros:
        return {
            "status": "validacao_falhou",
            "texto": "Validação falhou: " + "; ".join(erros),
            "pendente": True,
        }

    try:
        nova = coleta_service.criar_coleta(db, payload)
    except Exception as exc:
        logger.exception("Falha ao criar coleta via chat Nik")
        return {
            "status": "erro_execucao",
            "texto": f"Não foi possível salvar a coleta: {exc}",
            "pendente": True,
        }

    _limpar_pending(usuario_id, thread_id)
    lucro = lucro_liquido_total_coleta(vol, km, preco)
    return {
        "status": "ok",
        "texto": (
            f"Coleta cadastrada com sucesso (ID #{nova.id}). "
            f"{pending.get('parceiro_nome', 'Parceiro')}: {vol} kg, {km} km. "
            f"Lucro líquido estimado: R$ {lucro:.2f}."
        ),
        "pendente": False,
        "coleta_id": nova.id,
    }


def processar_mensagem_coleta(
    db: Session,
    mensagem: str,
    usuario_id: int | None,
    thread_id: str,
) -> dict[str, Any] | None:
    """
    Intercepta fluxo transacional de coleta.
    Retorna payload de resposta ou None para seguir chat normal.
    """
    pending = _obter_pending(usuario_id, thread_id)

    if pending and mensagem_e_confirmacao_coleta(mensagem):
        return executar_cadastro_coleta(db, usuario_id, thread_id)

    if pending and mensagem_e_cancelamento_coleta(mensagem):
        _limpar_pending(usuario_id, thread_id)
        return {
            "status": "cancelado",
            "texto": "Cadastro de coleta cancelado.",
            "pendente": False,
        }

    if pending:
        return {
            "status": "aguardando_confirmacao",
            "texto": (
                "Há uma coleta aguardando confirmação. "
                "Digite CONFIRMAR para salvar ou CANCELAR para descartar.\n\n"
                + formatar_confirmacao_coleta(pending)
            ),
            "pendente": True,
        }

    if not mensagem_pede_cadastrar_coleta(mensagem):
        return None

    return preparar_cadastro_coleta(db, mensagem, usuario_id, thread_id)
