"""
Ferramentas de dados da Nik para conversa integrada.

Esta camada desacopla o "chat livre" das consultas de dados. A Nik pode
usar essas ferramentas para responder com base real do sistema e explicitar
quais fontes foram usadas.
"""

from __future__ import annotations

import csv
import io
import json
import os
import random
import secrets
import time
from datetime import date, datetime, timedelta
from ipaddress import ip_address
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from banco_dados.modelos import (
    Coleta,
    Coletor,
    ContratoRecorrente,
    EmpresaCandidata,
    Interacao,
    MetaComercial,
    Notificacao,
    Parceiro,
    Pipeline,
    ScoreProspeccao,
    Sensor,
    SolicitacaoColetor,
    Tarefa,
    TronikScore,
)
from banco_dados.serializers import notificacao_para_dict, sensor_para_dict
from banco_dados.services import (
    coleta_service,
    nik_contexto as ctx,
    preview_service as pv,
    prospeccao_crm_bridge as crm_bridge,
    prospeccao_xgb_service as prospeccao_svc,
)
from banco_dados.services.crm_service import CRMService
from banco_dados.services.ml_predicao import predizer_enchimento_coletor
from banco_dados.services.ml_score import obter_ranking
from banco_dados.services.relatorio_service import lucro_liquido_total_coleta
from banco_dados.utils import utc_now_naive
from banco_dados.utils.cache import obter_cache
from jobs.prospeccao.publish_scores import resolve_model

_WEB_CHAMADAS_TS: list[float] = []


def _web_request_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(k in msg for k in ("timed out", "timeout", "temporarily unavailable", "502", "503", "504")):
        return True
    if isinstance(exc, HTTPError) and exc.code in (502, 503, 504):
        return True
    return bool(isinstance(exc, URLError))


def _web_network_retries() -> int:
    try:
        return max(0, min(4, int(os.getenv("NIK_WEB_NETWORK_RETRIES", "2") or "2")))
    except ValueError:
        return 2


def _serper_post_json(payload: bytes, api_key: str, timeout_s: float) -> str:
    req = Request(
        url="https://google.serper.dev/search",
        data=payload,
        headers={"Content-Type": "application/json", "X-API-KEY": api_key},
        method="POST",
    )
    retries = _web_network_retries()
    last: BaseException | None = None
    for attempt in range(retries + 1):
        if attempt > 0:
            delay = min(3.0, 0.2 * (1.6 ** (attempt - 1))) * random.uniform(0.85, 1.15)
            time.sleep(delay)
        try:
            with urlopen(req, timeout=timeout_s) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except (URLError, HTTPError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < retries and _web_request_transient(exc):
                continue
            raise exc
    raise last or RuntimeError("serper: falha sem exceção")

_CATALOGO_FONTES_WEB: dict[str, list[str]] = {
    "regulatorio": [
        "gov.br",
        "mma.gov.br",
        "ibama.gov.br",
        "camara.leg.br",
        "senado.leg.br",
    ],
    "dados_publicos": [
        "ibge.gov.br",
        "ipea.gov.br",
        "dados.gov.br",
    ],
    "setorial": [
        "abree.org.br",
        "cempre.org.br",
        "sebrae.com.br",
    ],
    "mercado": [
        "valor.globo.com",
        "exame.com",
        "agenciabrasil.ebc.com.br",
    ],
}


def _normalizar_texto(texto: str) -> str:
    base = (texto or "").strip().lower()
    trocas = {
        "á": "a", "à": "a", "â": "a", "ã": "a",
        "é": "e", "ê": "e",
        "í": "i",
        "ó": "o", "ô": "o", "õ": "o",
        "ú": "u", "ç": "c",
    }
    for antigo, novo in trocas.items():
        base = base.replace(antigo, novo)
    return " ".join(base.split())


def _tokens_busca(consulta: str) -> list[str]:
    texto = _normalizar_texto(consulta)
    tokens = [t for t in texto.split(" ") if len(t) >= 2]
    # Remove duplicados preservando ordem
    vistos: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t in vistos:
            continue
        vistos.add(t)
        out.append(t)
    return out[:8]


def catalogo_fontes_web() -> dict[str, list[str]]:
    return {k: list(v) for k, v in _CATALOGO_FONTES_WEB.items()}


def _intencao_web(consulta: str) -> str:
    q = _normalizar_texto(consulta)
    if any(k in q for k in ["lei", "decreto", "norma", "conama", "mtr", "licenca", "licenciamento"]):
        return "regulatorio"
    if any(k in q for k in ["ibge", "ipea", "serie historica", "indicador", "estatistica", "dados"]):
        return "dados_publicos"
    if any(k in q for k in ["logistica reversa", "reciclagem", "residuo", "eletroeletronico", "abree", "cempre"]):
        return "setorial"
    return "mercado"


def _dominios_ativos_web(consulta: str) -> list[str]:
    intencao = _intencao_web(consulta)
    base = _CATALOGO_FONTES_WEB.get(intencao, [])
    extras = [d.strip().lower() for d in (os.getenv("NIK_WEB_ALLOWED_DOMAINS", "") or "").split(",") if d.strip()]
    dominios = base + [d for d in extras if d not in base]
    return dominios[:20]


def _montar_queries_web(consulta: str) -> list[str]:
    q = (consulta or "").strip()
    dominios = _dominios_ativos_web(q)
    if not q:
        return []
    queries = [q]
    for d in dominios[:4]:
        queries.append(f"{q} site:{d}")
    # determinístico: dedupe preservando ordem
    vistos: set[str] = set()
    saida: list[str] = []
    for item in queries:
        chave = _normalizar_texto(item)
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(item)
    return saida


def _score_resultado_web(item: dict[str, Any], consulta: str, dominios_trust: list[str]) -> int:
    titulo = _normalizar_texto(str(item.get("titulo") or ""))
    snippet = _normalizar_texto(str(item.get("snippet") or ""))
    fonte = _normalizar_texto(str(item.get("fonte") or ""))
    url = _normalizar_texto(str(item.get("url") or ""))
    tokens = _tokens_busca(consulta)
    score = 0
    score += sum(4 for t in tokens if t in titulo)
    score += sum(2 for t in tokens if t in snippet)
    score += sum(1 for t in tokens if t in url)
    if any(fonte == d or fonte.endswith(f".{d}") for d in dominios_trust):
        score += 10
    if ".gov.br" in fonte:
        score += 4
    return score


def _periodo_do_ano(ano: int) -> pv.PeriodoRelatorio:
    return pv.PeriodoRelatorio(date(ano, 1, 1), date(ano, 12, 31))


def _limites_historico(db: Session) -> tuple[date | None, date | None]:
    row = db.query(func.min(Coleta.data_hora), func.max(Coleta.data_hora)).first()
    if not row:
        return None, None
    minimo, maximo = row
    return (minimo.date() if minimo else None, maximo.date() if maximo else None)


def ferramenta_limites_historico(db: Session) -> dict[str, str | None]:
    inicio, fim = _limites_historico(db)
    return {
        "inicio": inicio.isoformat() if inicio else None,
        "fim": fim.isoformat() if fim else None,
    }


def ferramenta_snapshot_operacional(db: Session) -> dict[str, Any]:
    return ctx.contexto_conversa_ops(db)


def ferramenta_resumo_periodo(
    db: Session,
    inicio: str | None = None,
    fim: str | None = None,
    parceiro_id: int | None = None,
) -> dict[str, Any]:
    periodo = pv.resolver_periodo(inicio, fim)
    resumo = pv.resumo_relatorios(db, periodo, parceiro_id=parceiro_id)
    return {
        "periodo": {"inicio": periodo.inicio.isoformat(), "fim": periodo.fim.isoformat()},
        "parceiro_id": parceiro_id,
        "resumo": resumo,
    }


def ferramenta_timeline_anual(
    db: Session,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
    parceiro_id: int | None = None,
) -> dict[str, Any]:
    data_min, data_max = _limites_historico(db)
    if not data_min or not data_max:
        return {
            "faixa": {"inicio": None, "fim": None},
            "anos": [],
            "mensagem": "Sem histórico de coletas na base.",
        }

    inicio_real = ano_inicio or data_min.year
    fim_real = ano_fim or data_max.year
    if inicio_real > fim_real:
        inicio_real, fim_real = fim_real, inicio_real

    inicio_real = max(inicio_real, data_min.year)
    fim_real = min(fim_real, data_max.year)

    anos: list[dict[str, Any]] = []
    for ano in range(inicio_real, fim_real + 1):
        resumo = pv.resumo_relatorios(db, _periodo_do_ano(ano), parceiro_id=parceiro_id)
        anos.append(
            {
                "ano": ano,
                "total_coletas": resumo.get("total_coletas", 0),
                "volume_kg": resumo.get("volume_kg", 0),
                "km_total": resumo.get("km_total", 0),
                "media_kg_coleta": resumo.get("media_kg_coleta", 0),
                "media_km_coleta": resumo.get("media_km_coleta", 0),
            }
        )

    return {
        "faixa": {"inicio": inicio_real, "fim": fim_real},
        "anos": anos,
        "parceiro_id": parceiro_id,
    }


def ferramenta_impacto_geral(
    db: Session,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
    parceiro_id: int | None = None,
) -> dict[str, Any]:
    timeline = ferramenta_timeline_anual(db, ano_inicio=ano_inicio, ano_fim=ano_fim, parceiro_id=parceiro_id)
    anos = timeline.get("anos", [])
    total_coletas = int(sum(a.get("total_coletas", 0) for a in anos))
    volume_kg = float(sum(a.get("volume_kg", 0) for a in anos))
    km_total = float(sum(a.get("km_total", 0) for a in anos))
    eficiencia = round(volume_kg / km_total, 3) if km_total > 0 else 0.0
    return {
        "faixa": timeline.get("faixa"),
        "total_coletas": total_coletas,
        "volume_kg": round(volume_kg, 1),
        "km_total": round(km_total, 1),
        "eficiencia_kg_km": eficiencia,
        "parceiro_id": parceiro_id,
    }


def ferramenta_listar_candidatos_prospeccao(
    db: Session,
    *,
    limite: int = 20,
    qid: str | None = None,
    prioridade: str | None = None,
    model_version: str | None = None,
) -> dict[str, Any]:
    """Fila ranqueada de candidatos REE (mesmo read-model do dashboard e /api/prospeccao/candidatos)."""
    limite_efetivo = max(1, min(int(limite or 20), 50))
    prioridade_norm = (prioridade or "").strip().lower() or None
    if prioridade_norm and prioridade_norm not in {"alta", "media", "baixa"}:
        prioridade_norm = None

    candidatos = prospeccao_svc.buscar_candidatos_prospeccao(
        db,
        limite=limite_efetivo,
        qid=(qid or "").strip() or None,
        prioridade=prioridade_norm,
        model_version=(model_version or "").strip() or None,
    )
    return {
        "limite": limite_efetivo,
        "qid": qid,
        "prioridade": prioridade_norm,
        "model_version": model_version,
        "total": len(candidatos),
        "candidatos": candidatos,
        "resumo": (
            f"Fila de prospecção com {len(candidatos)} candidato(s) ranqueado(s)"
            + (f" (prioridade {prioridade_norm})" if prioridade_norm else "")
            + (f" no contexto {qid}" if qid else "")
            + ".",
        ),
    }


def ferramenta_explicar_candidato_prospeccao(
    db: Session,
    *,
    score_id: int | None = None,
    model_version: str | None = None,
) -> dict[str, Any]:
    """Evidências e motivos do score para um candidato da fila REE."""
    if score_id is None:
        return {
            "encontrado": False,
            "resumo": "Informe score_id do candidato (ex.: score_id=42 ou candidato 42).",
        }
    score_id_int = int(score_id)
    resultado = prospeccao_svc.explicar_candidato(
        db,
        score_id_int,
        model_version=(model_version or "").strip() or None,
    )
    if not resultado:
        return {
            "score_id": score_id_int,
            "encontrado": False,
            "resumo": f"Candidato score_id={score_id_int} não encontrado no modelo ativo.",
        }

    score = resultado.get("score") or {}
    explicacao = resultado.get("explicacao") or []
    empresa = (score.get("empresa") or {}) if isinstance(score.get("empresa"), dict) else {}
    razao = empresa.get("razao_social") or empresa.get("nome_fantasia") or "empresa"
    return {
        "score_id": score_id_int,
        "encontrado": True,
        "score": score,
        "explicacao": explicacao,
        "resumo": (
            f"Explicação do candidato {razao} (score_id={score_id_int}): "
            f"{len(explicacao)} motivo(s) registrado(s)."
        ),
    }


def ferramenta_cruzar_crm_prospeccao(
    db: Session,
    *,
    pipeline_id: int | None = None,
    empresa: str | None = None,
    limite_scores: int = 5,
    model_version: str | None = None,
    modo_global: bool = False,
) -> dict[str, Any]:
    """Cruza pipeline CRM com scores REE; modo_global lista todos os pipelines."""
    if db is None:
        return {"encontrado": False, "resumo": "Informe pipeline_id ou nome da empresa para cruzar CRM e prospecção."}
    if modo_global or (pipeline_id is None and not (empresa or "").strip()):
        return crm_bridge.listar_cruzamento_crm_ree_global(
            db,
            limite_pipelines=40,
            limite_ree_sem_crm=15,
            model_version=model_version,
        )
    return crm_bridge.cruzar_crm_prospeccao(
        db,
        pipeline_id=pipeline_id,
        empresa=empresa,
        limite_scores=max(1, min(int(limite_scores or 5), 20)),
        model_version=model_version,
    )


def ferramenta_info_coletor(
    db: Session,
    coletor_id: int,
    *,
    dias: int = 90,
) -> dict[str, Any]:
    """Detalhe do coletor + totais de coletas recentes com unidades explícitas."""
    detalhe = ctx.contexto_coletor(db, coletor_id)
    if not detalhe:
        return {"encontrado": False, "coletor_id": coletor_id, "resumo": f"Coletor #{coletor_id} não encontrado."}
    fim = date.today()
    inicio = fim - timedelta(days=max(1, min(int(dias or 90), 365)) - 1)
    t0 = datetime.combine(inicio, datetime.min.time())
    total = db.query(Coleta).filter(Coleta.coletor_id == coletor_id, Coleta.data_hora >= t0).count()
    vol = float(
        db.query(func.coalesce(func.sum(Coleta.volume_estimado), 0.0))
        .filter(Coleta.coletor_id == coletor_id, Coleta.data_hora >= t0)
        .scalar()
        or 0
    )
    km = float(
        db.query(func.coalesce(func.sum(Coleta.km_percorrido), 0.0))
        .filter(Coleta.coletor_id == coletor_id, Coleta.data_hora >= t0)
        .scalar()
        or 0
    )
    coletor = detalhe.get("coletor") or {}
    return {
        "encontrado": True,
        "coletor_id": coletor_id,
        "id_fmt": coletor.get("id_fmt") or f"#L{coletor_id:03d}",
        "nome": coletor.get("nome") or coletor.get("localizacao"),
        "parceiro": coletor.get("parceiro"),
        "nivel_preenchimento_pct": coletor.get("nivel"),
        "bateria_pct": coletor.get("bateria"),
        "periodo": {"inicio": inicio.isoformat(), "fim": fim.isoformat()},
        "total_coletas": total,
        "volume_kg_periodo": round(vol, 2),
        "km_percorrido_km_periodo": round(km, 2),
        "resumo": (
            f"Coletor {coletor.get('id_fmt', coletor_id)} ({coletor.get('nome', '—')}): "
            f"{total} coleta(s), {round(vol, 2)} kg e {round(km, 2)} km no período."
        ),
    }


def _resolver_parceiro_ids(
    db: Session,
    parceiro_ids: list[int] | None = None,
    parceiro_nomes: list[str] | None = None,
) -> list[int]:
    ids: set[int] = set()
    for pid in parceiro_ids or []:
        if pid:
            ids.add(int(pid))
    nomes = [n.strip().lower() for n in (parceiro_nomes or []) if n and str(n).strip()]
    if nomes:
        for p in db.query(Parceiro.id, Parceiro.nome).filter(Parceiro.ativo.is_(True)).all():
            nome_l = (p.nome or "").strip().lower()
            if any(n in nome_l or nome_l in n for n in nomes):
                ids.add(int(p.id))
    return sorted(ids)


def ferramenta_exportar_coletas_csv(
    db: Session,
    *,
    inicio: str | None = None,
    fim: str | None = None,
    parceiro_ids: list[int] | None = None,
    parceiro_nomes: list[str] | None = None,
    usuario_id: int | None = None,
) -> dict[str, Any]:
    """Exporta coletas filtradas para CSV (sem limite de linhas) e retorna link de download."""
    periodo = pv.resolver_periodo(inicio, fim)
    ids_parceiro = _resolver_parceiro_ids(db, parceiro_ids, parceiro_nomes)

    t0 = datetime.combine(periodo.inicio, datetime.min.time())
    t1 = datetime.combine(periodo.fim, datetime.max.time())
    q = (
        db.query(Coleta)
        .options(
            joinedload(Coleta.coletor),
            joinedload(Coleta.parceiro),
            joinedload(Coleta.tipo_coletor),
        )
        .filter(Coleta.data_hora >= t0, Coleta.data_hora <= t1)
    )
    if ids_parceiro:
        q = q.filter(Coleta.parceiro_id.in_(ids_parceiro))
    coletas = q.order_by(Coleta.data_hora.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "data_hora",
            "coletor_id",
            "coletor_localizacao",
            "parceiro_id",
            "parceiro_nome",
            "volume_kg",
            "km_percorrido_km",
            "preco_combustivel",
            "lucro_liquido_estimado",
            "tipo_operacao",
        ]
    )
    for c in coletas:
        vol = c.volume_estimado or 0
        km = c.km_percorrido or 0
        preco = c.preco_combustivel or 0
        writer.writerow(
            [
                c.data_hora.isoformat() if c.data_hora else "",
                c.coletor_id,
                c.coletor.localizacao if c.coletor else "",
                c.parceiro_id,
                c.parceiro.nome if c.parceiro else "",
                vol,
                km,
                preco,
                lucro_liquido_total_coleta(vol, km, preco),
                c.tipo_operacao,
            ]
        )

    token = secrets.token_urlsafe(24)
    nome_arquivo = f"coletas_{periodo.inicio.isoformat()}_{periodo.fim.isoformat()}.csv"
    obter_cache().definir(
        f"nik:export:{token}",
        {
            "csv": buf.getvalue(),
            "filename": nome_arquivo,
            "usuario_id": usuario_id,
            "total_linhas": len(coletas),
            "periodo": {"inicio": periodo.inicio.isoformat(), "fim": periodo.fim.isoformat()},
            "parceiro_ids": ids_parceiro,
        },
    )
    return {
        "status": "ok",
        "total_linhas": len(coletas),
        "periodo": {"inicio": periodo.inicio.isoformat(), "fim": periodo.fim.isoformat()},
        "parceiro_ids": ids_parceiro,
        "download_url": f"/api/nik/ops/export/{token}",
        "filename": nome_arquivo,
        "resumo": (
            f"Exportação pronta: {len(coletas)} coleta(s) de "
            f"{periodo.inicio.isoformat()} a {periodo.fim.isoformat()}."
        ),
    }


def _resumo_candidato_comparacao(payload: dict[str, Any]) -> dict[str, Any]:
    empresa = payload.get("empresa") if isinstance(payload.get("empresa"), dict) else {}
    local = payload.get("local") if isinstance(payload.get("local"), dict) else {}
    motivos = payload.get("motivos") or []
    if not isinstance(motivos, list):
        motivos = []
    return {
        "score_id": payload.get("id"),
        "empresa_id": payload.get("empresa_id") or empresa.get("id"),
        "razao_social": empresa.get("razao_social") or empresa.get("nome_fantasia"),
        "nome_fantasia": empresa.get("nome_fantasia"),
        "prioridade": payload.get("prioridade"),
        "score": payload.get("score"),
        "score_percentil": payload.get("score_percentil"),
        "ranking_contexto": payload.get("ranking_contexto"),
        "qid": payload.get("qid"),
        "cnae_principal": empresa.get("cnae_principal"),
        "porte": empresa.get("porte"),
        "local": {
            "bairro": local.get("bairro") or empresa.get("bairro"),
            "ra": local.get("ra"),
            "endereco": local.get("endereco") or empresa.get("endereco_normalizado"),
            "cep": empresa.get("cep"),
        },
        "contato": {
            "telefone": empresa.get("telefone"),
            "email": empresa.get("email"),
        },
        "motivos": motivos[:6],
    }


def _carregar_score_por_empresa_id(db: Session, empresa_id: int) -> dict[str, Any] | None:
    model = resolve_model(db)
    if not model:
        return None
    row = (
        db.query(ScoreProspeccao)
        .filter(ScoreProspeccao.modelo_id == model.id, ScoreProspeccao.empresa_id == int(empresa_id))
        .order_by(ScoreProspeccao.ranking_contexto.asc())
        .first()
    )
    if not row:
        return None
    explicado = prospeccao_svc.explicar_candidato(db, int(row.id))
    return (explicado or {}).get("score")


def _resolver_payload_candidato(
    db: Session,
    *,
    score_id: int | None = None,
    empresa_id: int | None = None,
    pipeline_id: int | None = None,
) -> dict[str, Any] | None:
    if score_id is not None:
        explicado = prospeccao_svc.explicar_candidato(db, int(score_id))
        return (explicado or {}).get("score")
    if empresa_id is not None:
        return _carregar_score_por_empresa_id(db, int(empresa_id))
    if pipeline_id is not None:
        cruzado = crm_bridge.buscar_scores_para_pipeline(db, int(pipeline_id))
        if not cruzado:
            return None
        scores = cruzado.get("scores") or []
        if scores and isinstance(scores[0], dict):
            return scores[0]
    return None


def _parse_data_limite(data_limite: str | None) -> datetime | None:
    bruto = (data_limite or "").strip()
    if not bruto:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(bruto[:19] if "T" not in bruto and len(bruto) > 10 else bruto, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(bruto.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _montar_roteiro_contato(payload: dict[str, Any]) -> dict[str, Any]:
    empresa = payload.get("empresa") if isinstance(payload.get("empresa"), dict) else {}
    local = payload.get("local") if isinstance(payload.get("local"), dict) else {}
    razao = (empresa.get("razao_social") or empresa.get("nome_fantasia") or "sua empresa").strip()
    bairro = (local.get("bairro") or empresa.get("bairro") or "sua região").strip()
    cnae = (empresa.get("cnae_principal") or "setor compatível").strip()
    prioridade = (payload.get("prioridade") or "media").strip()
    motivos = payload.get("motivos") or []
    motivos_txt = ""
    if isinstance(motivos, list) and motivos:
        trechos = []
        for m in motivos[:3]:
            if isinstance(m, dict):
                feat = m.get("feature") or m.get("nome") or m.get("label")
                if feat:
                    trechos.append(str(feat).replace("_", " "))
            elif m:
                trechos.append(str(m))
        if trechos:
            motivos_txt = "; ".join(trechos)

    abertura = (
        f"Olá, falo da Tronik. Estamos mapeando parceiros para logística reversa de resíduos eletrônicos (REE) "
        f"no DF e identificamos {razao} em {bairro} como candidata prioritária ({prioridade}). "
        "Posso explicar em dois minutos como funciona a coleta recorrente?"
    )
    argumentos = [
        "A Tronik opera coleta de e-waste com rastreabilidade e conformidade ambiental no Distrito Federal.",
        f"O perfil CNAE {cnae} costuma gerar volume recorrente de equipamentos fora de uso.",
        "Modelo flexível: pontual ou contrato recorrente, com roteirização próxima à sua base.",
    ]
    if motivos_txt:
        argumentos.append(f"Sinais do nosso ranker REE: {motivos_txt}.")
    objecoes = [
        {
            "objecao": "Já temos fornecedor de descarte.",
            "resposta": "Podemos complementar picos de volume ou auditoria de destinação final, sem substituir contrato vigente.",
        },
        {
            "objecao": "Não temos volume agora.",
            "resposta": "Faz sentido começar com diagnóstico gratuito e piloto; muitos parceiros iniciam com uma coleta teste.",
        },
        {
            "objecao": "Preciso falar com outra área.",
            "resposta": "Posso enviar um resumo executivo e agendar retorno com facilities/compras no horário de vocês.",
        },
    ]
    proximo_passo = (
        "Registrar interação no CRM, enviar proposta de piloto de coleta REE e agendar visita técnica "
        "ou ligação de follow-up em até 3 dias úteis."
    )
    return {
        "abertura": abertura,
        "argumentos_ree": argumentos,
        "objecoes": objecoes,
        "proximo_passo": proximo_passo,
    }


def ferramenta_comparar_candidatos(
    db: Session,
    *,
    score_ids: list[int] | None = None,
    empresa_ids: list[int] | None = None,
    limite: int = 5,
) -> dict[str, Any]:
    """Compara candidatos REE lado a lado (scores, CNAE, local, motivos)."""
    limite_efetivo = max(1, min(int(limite or 5), 10))
    payloads: list[dict[str, Any]] = []
    vistos: set[int] = set()

    for sid in score_ids or []:
        try:
            sid_int = int(sid)
        except (TypeError, ValueError):
            continue
        if sid_int in vistos:
            continue
        explicado = prospeccao_svc.explicar_candidato(db, sid_int)
        score = (explicado or {}).get("score")
        if score:
            vistos.add(sid_int)
            payloads.append(score)
        if len(payloads) >= limite_efetivo:
            break

    if len(payloads) < limite_efetivo:
        for eid in empresa_ids or []:
            try:
                eid_int = int(eid)
            except (TypeError, ValueError):
                continue
            score = _carregar_score_por_empresa_id(db, eid_int)
            if not score:
                continue
            sid = score.get("id")
            if sid is not None and int(sid) in vistos:
                continue
            if sid is not None:
                vistos.add(int(sid))
            payloads.append(score)
            if len(payloads) >= limite_efetivo:
                break

    if not payloads:
        fila = prospeccao_svc.buscar_candidatos_prospeccao(db, limite=limite_efetivo)
        payloads = fila[:limite_efetivo]

    comparacao = [_resumo_candidato_comparacao(p) for p in payloads if isinstance(p, dict)]
    if not comparacao:
        return {
            "encontrado": False,
            "total": 0,
            "comparacao": [],
            "resumo": "Nenhum candidato encontrado para comparar. Informe score_ids ou empresa_ids.",
        }

    nomes = [c.get("razao_social") or "?" for c in comparacao]
    return {
        "encontrado": True,
        "total": len(comparacao),
        "comparacao": comparacao,
        "resumo": f"Comparação lado a lado de {len(comparacao)} candidato(s): {', '.join(nomes[:5])}.",
    }


def ferramenta_gerar_roteiro_contato(
    db: Session,
    *,
    score_id: int | None = None,
    empresa_id: int | None = None,
    pipeline_id: int | None = None,
) -> dict[str, Any]:
    """Roteiro estruturado de contato comercial (abertura, REE, objeções, próximo passo)."""
    if score_id is None and empresa_id is None and pipeline_id is None:
        return {
            "encontrado": False,
            "resumo": "Informe score_id, empresa_id ou pipeline_id para gerar o roteiro de contato.",
        }

    payload = _resolver_payload_candidato(
        db,
        score_id=score_id,
        empresa_id=empresa_id,
        pipeline_id=pipeline_id,
    )
    if not payload:
        ref = (
            f"score_id={score_id}"
            if score_id is not None
            else f"empresa_id={empresa_id}"
            if empresa_id is not None
            else f"pipeline_id={pipeline_id}"
        )
        return {
            "encontrado": False,
            "resumo": f"Candidato não encontrado para {ref}.",
        }

    empresa = payload.get("empresa") if isinstance(payload.get("empresa"), dict) else {}
    razao = empresa.get("razao_social") or empresa.get("nome_fantasia") or "empresa"
    roteiro = _montar_roteiro_contato(payload)
    return {
        "encontrado": True,
        "score_id": payload.get("id"),
        "empresa_id": payload.get("empresa_id") or empresa.get("id"),
        "pipeline_id": pipeline_id,
        "razao_social": razao,
        "roteiro": roteiro,
        "resumo": f"Roteiro de contato gerado para {razao} (score_id={payload.get('id')}).",
    }


def ferramenta_criar_tarefa_comercial(
    db: Session,
    titulo: str,
    *,
    pipeline_id: int | None = None,
    empresa_id: int | None = None,
    data_limite: str | None = None,
    descricao: str | None = None,
    usuario_id: int | None = None,
) -> dict[str, Any]:
    """Cria tarefa comercial no CRM (via CRMService)."""
    titulo_limpo = (titulo or "").strip()
    if not titulo_limpo:
        return {
            "criado": False,
            "resumo": "Informe o título da tarefa comercial.",
        }
    if usuario_id is None:
        return {
            "criado": False,
            "resumo": "Usuário não identificado: tarefa CRM exige sessão autenticada.",
        }

    pipeline_efetivo = pipeline_id
    if pipeline_efetivo is None and empresa_id is not None:
        empresa = db.query(EmpresaCandidata).filter_by(id=int(empresa_id)).first()
        if empresa and empresa.pipeline_id:
            pipeline_efetivo = int(empresa.pipeline_id)

    descricao_final = (descricao or "").strip() or None
    if empresa_id is not None and not descricao_final:
        empresa = db.query(EmpresaCandidata).filter_by(id=int(empresa_id)).first()
        if empresa:
            nome = (empresa.razao_social or empresa.nome_fantasia or "").strip()
            if nome:
                descricao_final = f"Tarefa vinculada à empresa candidata {nome} (empresa_id={empresa_id})."

    dados: dict[str, Any] = {
        "titulo": titulo_limpo[:200],
        "descricao": descricao_final,
        "pipeline_id": pipeline_efetivo,
        "prioridade": "media",
    }
    data_venc = _parse_data_limite(data_limite)
    if data_venc:
        dados["data_vencimento"] = data_venc

    tarefa = CRMService.criar_tarefa(dados, int(usuario_id))
    return {
        "criado": True,
        "tarefa_id": tarefa.id,
        "titulo": tarefa.titulo,
        "pipeline_id": tarefa.pipeline_id,
        "data_vencimento": tarefa.data_vencimento.isoformat() if tarefa.data_vencimento else None,
        "resumo": f"Tarefa CRM #{tarefa.id} criada: {tarefa.titulo}.",
    }


def ferramenta_status_modelo_prospeccao(
    db: Session,
    *,
    model_version: str | None = None,
) -> dict[str, Any]:
    """Versão ativa do ranker REE e métricas-chave de validação."""
    status = prospeccao_svc.status_modelo_prospeccao(
        db,
        model_version=(model_version or "").strip() or None,
    )
    if not status:
        return {
            "encontrado": False,
            "resumo": "Nenhum modelo de prospecção ativo encontrado na base.",
        }

    modelo = status.get("modelo") or {}
    metricas = status.get("metricas") or {}
    versao = modelo.get("versao") or "desconhecida"
    ndcg = metricas.get("validation_ndcg_mean") or metricas.get("train_ndcg_mean")
    ndcg_txt = f", NDCG validação {ndcg:.4f}" if isinstance(ndcg, (int, float)) else ""
    return {
        "encontrado": True,
        "modelo": modelo,
        "metricas": metricas,
        "total_scores": status.get("total_scores", 0),
        "prioridade": status.get("prioridade") or {},
        "resumo": (
            f"Modelo ativo {versao} ({status.get('total_scores', 0)} scores publicados{ndcg_txt})."
        ),
    }


def ferramenta_busca_unificada(
    db: Session,
    consulta: str,
    limite: int = 8,
    parceiro_id: int | None = None,
) -> dict[str, Any]:
    termo = _normalizar_texto(consulta or "")
    if not termo:
        return {"consulta": "", "itens": [], "resumo": "Consulta vazia."}

    tokens = _tokens_busca(consulta or "")
    # Escape special characters for LIKE pattern
    escaped = termo.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    like = f"%{escaped}%"
    max_itens = max(1, min(int(limite or 8), 30))
    candidatos: list[dict[str, Any]] = []

    # Coletas relevantes
    q_coletas = (
        db.query(Coleta, Coletor, Parceiro)
        .join(Coletor, Coleta.coletor_id == Coletor.id)
        .outerjoin(Parceiro, Coleta.parceiro_id == Parceiro.id)
    )
    if parceiro_id:
        q_coletas = q_coletas.filter(Coleta.parceiro_id == parceiro_id)
    q_coletas = q_coletas.filter(
        (func.lower(Coletor.localizacao).like(like, escape='\\'))
        | (func.lower(func.coalesce(Parceiro.nome, "")).like(like, escape='\\'))
        | (func.lower(func.coalesce(Coleta.tipo_operacao, "")).like(like, escape='\\'))
    )
    for coleta, coletor, parceiro in q_coletas.order_by(Coleta.data_hora.desc()).limit(max_itens * 3).all():
        texto_ref = _normalizar_texto(
            " ".join(
                [
                    str(coletor.localizacao if coletor else ""),
                    str(parceiro.nome if parceiro else ""),
                    str(coleta.tipo_operacao or ""),
                ]
            )
        )
        score = sum(2 if tok in texto_ref else 0 for tok in tokens)
        candidatos.append(
            {
                "tipo": "coleta",
                "id": coleta.id,
                "data": coleta.data_hora.isoformat() if coleta.data_hora else None,
                "coletor": coletor.localizacao if coletor else None,
                "parceiro": parceiro.nome if parceiro else None,
                "volume_kg": float(coleta.volume_estimado or 0),
                "km": float(coleta.km_percorrido or 0),
                "_score": score + 1,
            }
        )

    # Pipeline (CRM)
    q_pipeline = (
        db.query(Pipeline, Coletor)
        .outerjoin(Coletor, Pipeline.coletor_id == Coletor.id)
        .filter(
            (func.lower(func.coalesce(Pipeline.status, "")).like(like, escape='\\'))
            | (func.lower(func.coalesce(Pipeline.tipo_servico, "")).like(like, escape='\\'))
            | (func.lower(func.coalesce(Pipeline.origem, "")).like(like, escape='\\'))
            | (func.lower(func.coalesce(Pipeline.observacoes, "")).like(like, escape='\\'))
            | (func.lower(func.coalesce(Coletor.localizacao, "")).like(like, escape='\\'))
        )
        .order_by(Pipeline.atualizado_em.desc())
        .limit(max_itens)
    )
    for pipe, coletor in q_pipeline.limit(max_itens * 3).all():
        texto_ref = _normalizar_texto(
            " ".join(
                [
                    str(pipe.status or ""),
                    str(pipe.tipo_servico or ""),
                    str(pipe.origem or ""),
                    str(pipe.observacoes or ""),
                    str(coletor.localizacao if coletor else ""),
                ]
            )
        )
        score = sum(2 if tok in texto_ref else 0 for tok in tokens)
        candidatos.append(
            {
                "tipo": "pipeline",
                "id": pipe.id,
                "status": pipe.status,
                "valor_estimado": float(pipe.valor_estimado or 0),
                "probabilidade": int(pipe.probabilidade or 0),
                "coletor": coletor.localizacao if coletor else None,
                "tipo_servico": pipe.tipo_servico,
                "_score": score + 2,
            }
        )

    # Contratos
    q_contratos = (
        db.query(ContratoRecorrente, Coletor, Parceiro)
        .outerjoin(Coletor, ContratoRecorrente.coletor_id == Coletor.id)
        .outerjoin(Parceiro, ContratoRecorrente.parceiro_id == Parceiro.id)
        .filter(
            (func.lower(func.coalesce(ContratoRecorrente.titulo, "")).like(like, escape='\\'))
            | (func.lower(func.coalesce(ContratoRecorrente.descricao, "")).like(like, escape='\\'))
            | (func.lower(func.coalesce(ContratoRecorrente.status, "")).like(like, escape='\\'))
            | (func.lower(func.coalesce(Parceiro.nome, "")).like(like, escape='\\'))
            | (func.lower(func.coalesce(Coletor.localizacao, "")).like(like, escape='\\'))
        )
        .order_by(ContratoRecorrente.atualizado_em.desc())
        .limit(max_itens)
    )
    for contrato, coletor, parceiro in q_contratos.limit(max_itens * 3).all():
        texto_ref = _normalizar_texto(
            " ".join(
                [
                    str(contrato.titulo or ""),
                    str(contrato.descricao or ""),
                    str(contrato.status or ""),
                    str(parceiro.nome if parceiro else ""),
                    str(coletor.localizacao if coletor else ""),
                ]
            )
        )
        score = sum(2 if tok in texto_ref else 0 for tok in tokens)
        candidatos.append(
            {
                "tipo": "contrato",
                "id": contrato.id,
                "titulo": contrato.titulo,
                "status": contrato.status,
                "valor_mensal": float(contrato.valor_mensal or 0),
                "parceiro": parceiro.nome if parceiro else None,
                "coletor": coletor.localizacao if coletor else None,
                "_score": score + 3,
            }
        )

    # Dedupe + ranking por score e recência implícita
    vistos: set[tuple[str, int]] = set()
    itens_rank: list[dict[str, Any]] = []
    for item in sorted(candidatos, key=lambda x: float(x.get("_score", 0)), reverse=True):
        chave = (str(item.get("tipo", "")), int(item.get("id") or 0))
        if chave in vistos:
            continue
        vistos.add(chave)
        item.pop("_score", None)
        itens_rank.append(item)
        if len(itens_rank) >= max_itens * 3:
            break

    return {
        "consulta": consulta.strip(),
        "tokens": tokens,
        "total_encontrado": len(itens_rank),
        "itens": itens_rank,
        "cobertura": {
            "coletas": sum(1 for i in itens_rank if i.get("tipo") == "coleta"),
            "pipeline": sum(1 for i in itens_rank if i.get("tipo") == "pipeline"),
            "contratos": sum(1 for i in itens_rank if i.get("tipo") == "contrato"),
        },
        "resumo": f"Busca unificada com ranking executada para '{consulta.strip()}' em coletas, CRM e contratos.",
    }


def _bool_env(chave: str, padrao: bool = False) -> bool:
    return os.getenv(chave, str(padrao)).strip().lower() in {"1", "true", "yes", "on"}


def _host_permitido(hostname: str) -> bool:
    host = (hostname or "").strip().lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return False
    try:
        ip = ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False
    except ValueError:
        pass
    allowlist = [d.strip().lower() for d in (os.getenv("NIK_WEB_ALLOWED_DOMAINS", "") or "").split(",") if d.strip()]
    return not (allowlist and not any(host == d or host.endswith(f".{d}") for d in allowlist))


def _rate_limit_ok() -> bool:
    limite = max(1, int(os.getenv("NIK_WEB_RATE_LIMIT_PER_MIN", "20") or "20"))
    agora = time.time()
    while _WEB_CHAMADAS_TS and (agora - _WEB_CHAMADAS_TS[0]) > 60:
        _WEB_CHAMADAS_TS.pop(0)
    if len(_WEB_CHAMADAS_TS) >= limite:
        return False
    _WEB_CHAMADAS_TS.append(agora)
    return True


def ferramenta_busca_web(
    _db: Session,
    consulta: str,
    limite: int = 5,
) -> dict[str, Any]:
    if not _bool_env("NIK_WEB_ENABLED", False):
        return {
            "consulta": (consulta or "").strip(),
            "itens": [],
            "total_encontrado": 0,
            "resumo": "Busca web desabilitada por configuração.",
            "status": "disabled",
        }
    if not _rate_limit_ok():
        return {
            "consulta": (consulta or "").strip(),
            "itens": [],
            "total_encontrado": 0,
            "resumo": "Limite de chamadas web por minuto atingido.",
            "status": "rate_limited",
        }

    termo = (consulta or "").strip()
    if not termo:
        return {"consulta": "", "itens": [], "total_encontrado": 0, "resumo": "Consulta web vazia.", "status": "empty"}

    provider = (os.getenv("NIK_WEB_PROVIDER", "serper") or "serper").strip().lower()
    api_key = (os.getenv("NIK_WEB_API_KEY", "") or "").strip()
    max_itens = max(1, min(int(limite or 5), int(os.getenv("NIK_WEB_MAX_RESULTS", "5") or "5"), 10))
    timeout_s = max(2.0, float(os.getenv("NIK_WEB_TIMEOUT_MS", "8000") or "8000") / 1000.0)

    queries = _montar_queries_web(termo)
    dominios_trust = _dominios_ativos_web(termo)
    cache_key = f"nik:web:{provider}:{_normalizar_texto(termo)}:{max_itens}:{'|'.join(queries)}"
    cached = obter_cache().obter(cache_key, int(os.getenv("NIK_WEB_CACHE_TTL", "900") or "900"))
    if cached:
        return cached

    if provider != "serper":
        return {
            "consulta": termo,
            "itens": [],
            "total_encontrado": 0,
            "resumo": f"Provider web '{provider}' não suportado no momento.",
            "status": "unsupported_provider",
        }
    if not api_key:
        return {
            "consulta": termo,
            "itens": [],
            "total_encontrado": 0,
            "resumo": "NIK_WEB_API_KEY não configurada.",
            "status": "missing_key",
        }

    try:
        candidatos: list[dict[str, Any]] = []
        for query in queries:
            payload = json.dumps({"q": query, "num": max_itens}).encode("utf-8")
            body = _serper_post_json(payload, api_key, timeout_s)
            parsed = json.loads(body)
            organic = parsed.get("organic", []) if isinstance(parsed, dict) else []
            for row in organic:
                url = (row.get("link") or "").strip()
                host = urlparse(url).hostname or ""
                if not url or not _host_permitido(host):
                    continue
                candidatos.append(
                    {
                        "titulo": (row.get("title") or "").strip()[:180],
                        "url": url[:500],
                        "snippet": (row.get("snippet") or "").strip()[:400],
                        "fonte": host.lower(),
                        "_score": 0,
                    }
                )

        # Dedupe e ranking determinístico
        dedupe: dict[str, dict[str, Any]] = {}
        for item in candidatos:
            k = _normalizar_texto(item.get("url") or "")
            if not k:
                continue
            atual = dedupe.get(k)
            item["_score"] = _score_resultado_web(item, termo, dominios_trust)
            if atual is None or item["_score"] > int(atual.get("_score", 0)):
                dedupe[k] = item

        ordenados = sorted(
            dedupe.values(),
            key=lambda x: (
                -int(x.get("_score", 0)),
                _normalizar_texto(str(x.get("fonte") or "")),
                _normalizar_texto(str(x.get("titulo") or "")),
                _normalizar_texto(str(x.get("url") or "")),
            ),
        )
        itens = []
        for item in ordenados[:max_itens]:
            item.pop("_score", None)
            itens.append(item)
        resultado = {
            "consulta": termo,
            "queries_executadas": queries,
            "dominios_catalogo": dominios_trust,
            "itens": itens,
            "total_encontrado": len(itens),
            "resumo": f"Busca web executada com {len(itens)} fonte(s) externa(s).",
            "status": "ok",
        }
        obter_cache().definir(cache_key, resultado)
        return resultado
    except Exception as exc:
        return {
            "consulta": termo,
            "itens": [],
            "total_encontrado": 0,
            "resumo": f"Falha na busca web: {str(exc)[:180]}",
            "status": "error",
        }


def _dias_sem_coleta(ultima_coleta: datetime | None) -> int | None:
    if ultima_coleta is None:
        return None
    agora = utc_now_naive()
    return max(0, (agora - ultima_coleta).days)


def ferramenta_listar_coletores(
    db: Session,
    *,
    status: str | None = None,
    parceiro_id: int | None = None,
    sem_coleta_dias: int | None = None,
    limite: int = 50,
) -> dict[str, Any]:
    """Lista coletores operacionais (monitoramento) com filtros opcionais."""
    limite_efetivo = max(1, min(int(limite or 50), 50))
    status_norm = (status or "").strip().upper() or None
    coletores = pv.coletores_monitoramento(db)
    itens: list[dict[str, Any]] = []

    for c in coletores:
        if status_norm and (c.status or "OK").upper() != status_norm:
            continue
        if parceiro_id is not None and c.parceiro_id != parceiro_id:
            continue
        dias = _dias_sem_coleta(c.ultima_coleta)
        if (
            sem_coleta_dias is not None
            and c.ultima_coleta is not None
            and (dias is None or dias < sem_coleta_dias)
        ):
            continue
        itens.append(
            {
                "id": c.id,
                "id_fmt": f"#L{c.id:03d}",
                "localizacao": c.localizacao,
                "status": c.status or "OK",
                "nivel_preenchimento": round(float(c.nivel_preenchimento or 0), 1),
                "parceiro_nome": c.parceiro.nome if c.parceiro else None,
                "ultima_coleta": c.ultima_coleta.isoformat() if c.ultima_coleta else None,
                "dias_sem_coleta": dias,
            }
        )
        if len(itens) >= limite_efetivo:
            break

    filtro_txt = ""
    if sem_coleta_dias is not None:
        filtro_txt = f" sem coleta há ≥{sem_coleta_dias} dia(s)"
    elif status_norm:
        filtro_txt = f" status={status_norm}"
    elif parceiro_id is not None:
        filtro_txt = f" parceiro_id={parceiro_id}"

    return {
        "total": len(itens),
        "limite": limite_efetivo,
        "filtros": {
            "status": status_norm,
            "parceiro_id": parceiro_id,
            "sem_coleta_dias": sem_coleta_dias,
        },
        "coletores": itens,
        "resumo": f"{len(itens)} coletor(es) listado(s){filtro_txt}.",
    }


def ferramenta_status_sensores(
    db: Session,
    *,
    coletor_id: int | None = None,
    bateria_max: float | None = None,
    limite: int = 50,
) -> dict[str, Any]:
    """Lista sensores com bateria e último ping (sem expor api_token)."""
    limite_efetivo = max(1, min(int(limite or 50), 50))
    query = db.query(Sensor).options(
        joinedload(Sensor.coletor),
        joinedload(Sensor.tipo_sensor),
    )
    if coletor_id is not None:
        query = query.filter(Sensor.coletor_id == coletor_id)
    if bateria_max is not None:
        query = query.filter(Sensor.bateria <= float(bateria_max))
    sensores = query.order_by(Sensor.bateria.asc().nullslast(), Sensor.id).limit(limite_efetivo).all()
    itens = [sensor_para_dict(s) for s in sensores]

    filtro_txt = ""
    if coletor_id is not None:
        filtro_txt = f" do coletor #{coletor_id}"
    if bateria_max is not None:
        filtro_txt += f" com bateria ≤{bateria_max}%"

    return {
        "total": len(itens),
        "limite": limite_efetivo,
        "filtros": {"coletor_id": coletor_id, "bateria_max": bateria_max},
        "sensores": itens,
        "resumo": f"{len(itens)} sensor(es){filtro_txt}.",
    }


def ferramenta_historico_coletas(
    db: Session,
    *,
    coletor_id: int | None = None,
    parceiro_id: int | None = None,
    inicio: str | None = None,
    fim: str | None = None,
    tipo_operacao: str | None = None,
    pagina: int = 1,
    por_pagina: int = 20,
) -> dict[str, Any]:
    """Histórico row-level de coletas com paginação."""
    pagina_efetiva = max(1, int(pagina or 1))
    por_pagina_efetiva = max(1, min(int(por_pagina or 20), 50))
    coletas, total = coleta_service.obter_coletas_com_filtros(
        db,
        coletor_id=coletor_id,
        parceiro_id=parceiro_id,
        tipo_operacao=(tipo_operacao or "").strip() or None,
        data_inicio=inicio,
        data_fim=fim,
        pagina=pagina_efetiva,
        por_pagina=por_pagina_efetiva,
    )
    linhas = [
        {
            "data_hora": c.data_hora.isoformat() if c.data_hora else None,
            "coletor_localizacao": c.coletor.localizacao if c.coletor else None,
            "parceiro_nome": c.parceiro.nome if c.parceiro else None,
            "volume_kg": round(float(c.volume_estimado or 0), 2),
            "km": round(float(c.km_percorrido or 0), 2),
            "tipo_operacao": c.tipo_operacao,
        }
        for c in coletas
    ]
    total_paginas = (total + por_pagina_efetiva - 1) // por_pagina_efetiva if total else 0
    return {
        "total": total,
        "pagina": pagina_efetiva,
        "por_pagina": por_pagina_efetiva,
        "total_paginas": total_paginas,
        "coletas": linhas,
        "filtros": {
            "coletor_id": coletor_id,
            "parceiro_id": parceiro_id,
            "inicio": inicio,
            "fim": fim,
            "tipo_operacao": tipo_operacao,
        },
        "resumo": (
            f"Página {pagina_efetiva}/{max(1, total_paginas)}: "
            f"{len(linhas)} coleta(s) de {total} no total."
        ),
    }


def ferramenta_ml_coletor(db: Session, *, coletor_id: int) -> dict[str, Any]:
    """Predição de enchimento e TRONIK Score para um coletor."""
    coletor = db.query(Coletor).filter(Coletor.id == int(coletor_id)).first()
    if not coletor:
        return {
            "status": "nao_encontrado",
            "coletor_id": coletor_id,
            "resumo": f"Coletor #{coletor_id} não encontrado.",
        }

    predicao: dict[str, Any] | None = None
    try:
        predicao = predizer_enchimento_coletor(db, int(coletor_id))
    except Exception as exc:
        predicao = {"erro": str(exc)[:180]}

    ts = db.query(TronikScore).filter(TronikScore.coletor_id == int(coletor_id)).first()
    score: dict[str, Any] | None = None
    if ts:
        score = {
            "score": round(float(ts.score), 2),
            "modelo_usado": ts.modelo_usado,
            "calculado_em": ts.calculado_em.isoformat() if ts.calculado_em else None,
        }

    pred_ok = bool(
        predicao
        and not predicao.get("erro")
        and predicao.get("dados_suficientes", True)
    )
    score_ok = score is not None
    if not pred_ok and not score_ok:
        return {
            "status": "indisponivel",
            "coletor_id": coletor_id,
            "localizacao": coletor.localizacao,
            "predicao": predicao,
            "tronik_score": score,
            "resumo": (
                f"ML indisponível para coletor #{coletor_id} "
                f"({coletor.localizacao or '—'}): sem predição nem score calculados."
            ),
        }

    partes: list[str] = []
    if score_ok and score:
        partes.append(f"TRONIK Score {score['score']}")
    if pred_ok and predicao:
        horas = predicao.get("horas_restantes")
        if horas is not None:
            partes.append(f"enchimento em ~{round(float(horas), 1)}h")
        elif predicao.get("predicted_full_at"):
            partes.append("predição de enchimento disponível")

    return {
        "status": "ok",
        "coletor_id": coletor_id,
        "localizacao": coletor.localizacao,
        "nivel_atual": round(float(coletor.nivel_preenchimento or 0), 1),
        "predicao": predicao,
        "tronik_score": score,
        "resumo": (
            f"Coletor #{coletor_id} ({coletor.localizacao or '—'}): "
            + (", ".join(partes) if partes else "dados parciais de ML.")
            + "."
        ),
    }


def _resolver_mes_comercial(mes: str | None) -> tuple[int, int]:
    """Resolve mês/ano a partir de 'YYYY-MM' ou mês corrente."""
    bruto = (mes or "").strip()
    if bruto:
        partes = bruto.split("-", 1)
        if len(partes) == 2 and partes[0].isdigit() and partes[1].isdigit():
            ano = int(partes[0])
            mes_num = int(partes[1])
            if 1 <= mes_num <= 12:
                return mes_num, ano
    hoje = date.today()
    return hoje.month, hoje.year


def _pipeline_item_resumo(pipe: Pipeline) -> dict[str, Any]:
    empresa = None
    if pipe.coletor:
        empresa = pipe.coletor.localizacao
    elif pipe.observacoes:
        empresa = (pipe.observacoes or "")[:120]
    return {
        "id": pipe.id,
        "empresa": empresa,
        "status": pipe.status,
        "valor_estimado": round(float(pipe.valor_estimado or 0), 2),
        "probabilidade": int(pipe.probabilidade or 0),
        "proxima_acao": pipe.proxima_acao,
        "responsavel": pipe.responsavel.nome_completo if pipe.responsavel else None,
        "responsavel_id": pipe.responsavel_id,
    }


def ferramenta_listar_pipeline(
    db: Session,
    *,
    status: str | None = None,
    responsavel_id: int | None = None,
    limite: int = 20,
) -> dict[str, Any]:
    """Lista deals do pipeline CRM (mesmo read-model de GET /api/crm/pipeline)."""
    limite_efetivo = max(1, min(int(limite or 20), 50))
    status_norm = (status or "").strip().lower() or None
    query = db.query(Pipeline).options(
        joinedload(Pipeline.coletor),
        joinedload(Pipeline.responsavel),
    )
    if status_norm:
        query = query.filter(Pipeline.status == status_norm)
    if responsavel_id is not None:
        query = query.filter(Pipeline.responsavel_id == int(responsavel_id))
    pipelines = query.order_by(Pipeline.atualizado_em.desc()).limit(limite_efetivo).all()
    itens = [_pipeline_item_resumo(p) for p in pipelines]
    filtro_txt = ""
    if status_norm:
        filtro_txt = f" status={status_norm}"
    elif responsavel_id is not None:
        filtro_txt = f" responsavel_id={responsavel_id}"
    return {
        "total": len(itens),
        "limite": limite_efetivo,
        "filtros": {"status": status_norm, "responsavel_id": responsavel_id},
        "deals": itens,
        "resumo": f"{len(itens)} deal(s) no pipeline{filtro_txt}.",
    }


def ferramenta_listar_tarefas_comerciais(
    db: Session,
    *,
    status: str | None = None,
    limite: int = 20,
) -> dict[str, Any]:
    """Lista tarefas CRM (padrão: abertas/pendentes)."""
    limite_efetivo = max(1, min(int(limite or 20), 50))
    status_norm = (status or "").strip().lower() or None
    if status_norm in {None, "aberta", "abertas", "pendente", "pendentes", "aberto", "abertos"}:
        status_efetivo = "pendente"
    else:
        status_efetivo = status_norm

    tarefas = (
        db.query(Tarefa)
        .options(
            joinedload(Tarefa.pipeline).joinedload(Pipeline.coletor),
            joinedload(Tarefa.usuario),
        )
        .filter(Tarefa.status == status_efetivo)
        .order_by(Tarefa.data_vencimento.asc().nullslast(), Tarefa.id.asc())
        .limit(limite_efetivo)
        .all()
    )
    itens: list[dict[str, Any]] = []
    for tarefa in tarefas:
        bruto = tarefa.to_dict()
        itens.append(
            {
                "id": bruto.get("id"),
                "titulo": bruto.get("titulo"),
                "status": bruto.get("status"),
                "data_vencimento": bruto.get("data_vencimento"),
                "pipeline_id": bruto.get("pipeline_id"),
                "empresa": bruto.get("cliente"),
                "prioridade": bruto.get("prioridade"),
            }
        )
    return {
        "total": len(itens),
        "limite": limite_efetivo,
        "filtros": {"status": status_efetivo},
        "tarefas": itens,
        "resumo": f"{len(itens)} tarefa(s) comercial(is) ({status_efetivo}).",
    }


def ferramenta_interacoes_pipeline(
    db: Session,
    *,
    pipeline_id: int | None = None,
    limite: int = 20,
) -> dict[str, Any]:
    """Timeline de interações de um pipeline CRM."""
    if pipeline_id is None:
        return {
            "encontrado": False,
            "resumo": "Informe pipeline_id para listar interações do negócio.",
        }
    limite_efetivo = max(1, min(int(limite or 20), 50))
    pipe = db.query(Pipeline).filter_by(id=int(pipeline_id)).first()
    if not pipe:
        return {
            "encontrado": False,
            "pipeline_id": int(pipeline_id),
            "resumo": f"Pipeline #{pipeline_id} não encontrado.",
        }
    interacoes = (
        db.query(Interacao)
        .options(joinedload(Interacao.usuario))
        .filter_by(pipeline_id=int(pipeline_id))
        .order_by(Interacao.data.desc(), Interacao.id.desc())
        .limit(limite_efetivo)
        .all()
    )
    itens = [
        {
            "id": i.id,
            "tipo": i.tipo,
            "descricao": i.descricao,
            "data": i.data.isoformat() if i.data else None,
            "autor": i.usuario.nome_completo if i.usuario else None,
        }
        for i in interacoes
    ]
    return {
        "encontrado": True,
        "pipeline_id": int(pipeline_id),
        "total": len(itens),
        "limite": limite_efetivo,
        "interacoes": itens,
        "resumo": f"{len(itens)} interação(ões) no pipeline #{pipeline_id}.",
    }


def ferramenta_listar_notificacoes(
    db: Session,
    *,
    lida: bool | None = None,
    limite: int = 20,
) -> dict[str, Any]:
    """Lista notificações operacionais (mesmo serializer do dashboard)."""
    limite_efetivo = max(1, min(int(limite or 20), 50))
    query = db.query(Notificacao).options(
        joinedload(Notificacao.coletor),
        joinedload(Notificacao.sensor),
    )
    if lida is not None:
        query = query.filter(Notificacao.lida.is_(bool(lida)))
    rows = query.order_by(Notificacao.criada_em.desc()).limit(limite_efetivo).all()
    itens = [notificacao_para_dict(n) for n in rows]
    filtro_txt = ""
    if lida is False:
        filtro_txt = " não lidas"
    elif lida is True:
        filtro_txt = " lidas"
    return {
        "total": len(itens),
        "limite": limite_efetivo,
        "filtros": {"lida": lida},
        "notificacoes": itens,
        "resumo": f"{len(itens)} notificação(ões){filtro_txt}.",
    }


def ferramenta_listar_solicitacoes(
    db: Session,
    *,
    status: str | None = None,
    limite: int = 20,
) -> dict[str, Any]:
    """Lista solicitações de coletor da landing (GET /api/solicitacoes)."""
    limite_efetivo = max(1, min(int(limite or 20), 50))
    status_norm = (status or "").strip().lower() or None
    query = db.query(SolicitacaoColetor)
    if status_norm:
        query = query.filter(SolicitacaoColetor.status == status_norm)
    rows = query.order_by(SolicitacaoColetor.criado_em.desc()).limit(limite_efetivo).all()
    itens = [
        {
            "id": s.id,
            "nome": s.nome,
            "email": s.email,
            "status": s.status,
            "criado_em": s.criado_em.isoformat() if s.criado_em else None,
        }
        for s in rows
    ]
    filtro_txt = f" status={status_norm}" if status_norm else ""
    return {
        "total": len(itens),
        "limite": limite_efetivo,
        "filtros": {"status": status_norm},
        "solicitacoes": itens,
        "resumo": f"{len(itens)} solicitação(ões) de coletor{filtro_txt}.",
    }


def ferramenta_meta_comercial(
    db: Session,
    *,
    mes: str | None = None,
) -> dict[str, Any]:
    """Meta comercial do mês (valor_meta, realizado, % atingido)."""
    mes_num, ano = _resolver_mes_comercial(mes)
    mes_iso = f"{ano}-{mes_num:02d}"
    meta = db.query(MetaComercial).filter_by(mes=mes_num, ano=ano).first()
    if not meta:
        return {
            "status": "indisponivel",
            "mes": mes_iso,
            "resumo": f"Nenhuma meta comercial configurada para {mes_num:02d}/{ano}.",
        }
    valor_meta = float(meta.valor_meta or 0)
    valor_realizado = float(meta.valor_realizado or 0)
    pct = round(float(meta.percentual_atingido or 0), 1)
    falta = round(max(0.0, valor_meta - valor_realizado), 2)
    return {
        "status": "ok",
        "mes": mes_iso,
        "valor_meta": round(valor_meta, 2),
        "valor_realizado": round(valor_realizado, 2),
        "percentual_atingido": pct,
        "falta_para_meta": falta,
        "meta_status": meta.status,
        "resumo": (
            f"Meta {mes_num:02d}/{ano}: R${valor_realizado:.0f} de R${valor_meta:.0f} "
            f"({pct}% atingido, faltam R${falta:.0f})."
        ),
    }


def ferramenta_ranking_ml(db: Session, *, limite: int = 10) -> dict[str, Any]:
    """Top coletores por TRONIK Score / prioridade operacional."""
    limite_efetivo = max(1, min(int(limite or 10), 50))
    try:
        ranking = obter_ranking(db, limite=limite_efetivo)
    except Exception as exc:
        return {
            "status": "indisponivel",
            "total": 0,
            "ranking": [],
            "resumo": f"Ranking ML indisponível: {str(exc)[:120]}.",
        }

    if not ranking:
        return {
            "status": "indisponivel",
            "total": 0,
            "limite": limite_efetivo,
            "ranking": [],
            "resumo": "Nenhum TRONIK Score calculado na base.",
        }

    top = ranking[0]
    return {
        "status": "ok",
        "total": len(ranking),
        "limite": limite_efetivo,
        "ranking": ranking,
        "resumo": (
            f"Top {len(ranking)} coletor(es) por TRONIK Score; "
            f"líder: {top.get('nome', '—')} (score {top.get('score', '—')})."
        ),
    }


def catalogo_ferramentas() -> list[dict[str, Any]]:
    return [
        {"nome": "snapshot_operacional", "descricao": "Estado operacional atual (alertas e indicadores)."},
        {"nome": "resumo_periodo", "descricao": "Resumo de coletas em período específico."},
        {"nome": "timeline_anual", "descricao": "Linha do tempo anual de coletas/volume/km."},
        {"nome": "impacto_geral", "descricao": "Impacto agregado com eficiência logística no intervalo."},
        {"nome": "limites_historico", "descricao": "Datas mínima e máxima disponíveis na base de coletas."},
        {"nome": "busca_unificada", "descricao": "Pesquisa textual em coletas, CRM (pipeline) e contratos."},
        {
            "nome": "listar_candidatos_prospeccao",
            "descricao": "Fila ranqueada de empresas/locais candidatos à prospecção REE (modelo XGBoost).",
        },
        {
            "nome": "explicar_candidato_prospeccao",
            "descricao": "Motivos e evidências do score de um candidato (parâmetro score_id).",
        },
        {
            "nome": "status_modelo_prospeccao",
            "descricao": "Versão ativa do ranker REE e métricas-chave (NDCG, amostras, fila publicada).",
        },
        {
            "nome": "cruzar_crm_prospeccao",
            "descricao": "Cruza leads CRM com scores REE (global ou por pipeline/empresa).",
        },
        {
            "nome": "info_coletor",
            "descricao": "Detalhes e totais (volume_kg, km) de um coletor por ID.",
        },
        {
            "nome": "listar_coletores",
            "descricao": "Lista coletores com status, nível, parceiro, última coleta e dias sem coleta.",
        },
        {
            "nome": "status_sensores",
            "descricao": "Lista sensores com bateria, último ping e coletor (sem token de API).",
        },
        {
            "nome": "historico_coletas",
            "descricao": "Histórico detalhado de coletas (linha a linha) com paginação.",
        },
        {
            "nome": "ml_coletor",
            "descricao": "Predição de enchimento e TRONIK Score de um coletor específico.",
        },
        {
            "nome": "ranking_ml",
            "descricao": "Ranking de coletores por TRONIK Score / prioridade operacional.",
        },
        {
            "nome": "listar_pipeline",
            "descricao": "Lista deals do funil CRM (status, valor, probabilidade, responsável).",
        },
        {
            "nome": "listar_tarefas_comerciais",
            "descricao": "Tarefas comerciais abertas ou filtradas por status (título, prazo, pipeline).",
        },
        {
            "nome": "interacoes_pipeline",
            "descricao": "Histórico de interações de um pipeline CRM (parâmetro pipeline_id).",
        },
        {
            "nome": "listar_notificacoes",
            "descricao": "Notificações do sistema (tipo, título, lida, coletor).",
        },
        {
            "nome": "listar_solicitacoes",
            "descricao": "Solicitações de coletor vindas da landing page.",
        },
        {
            "nome": "meta_comercial",
            "descricao": "Meta de faturamento do mês (meta, realizado, % atingido).",
        },
        {
            "nome": "exportar_coletas_csv",
            "descricao": "Exporta coletas filtradas por período/parceiro para CSV (download).",
        },
        {
            "nome": "comparar_candidatos",
            "descricao": "Compara candidatos REE lado a lado (score, CNAE, local, motivos).",
        },
        {
            "nome": "gerar_roteiro_contato",
            "descricao": "Roteiro de ligação/contato (abertura, argumentos REE, objeções, próximo passo).",
        },
        {
            "nome": "criar_tarefa_comercial",
            "descricao": "Cria tarefa ou lembrete no CRM comercial (título, pipeline, prazo).",
        },
        {
            "nome": "cadastrar_coleta",
            "descricao": (
                "Inicia o cadastro de uma NOVA coleta operacional (pesagem/transporte) com confirmação. "
                "Use SOMENTE quando o usuário pedir explicitamente para cadastrar/registrar/lançar uma coleta "
                "com dados (parceiro, volume em kg, km). "
                "NUNCA use para relatórios, consultas, listagens ou buscas."
            ),
        },
        {"nome": "busca_web", "descricao": "Busca na internet com guardrails e fontes externas auditáveis."},
        {"nome": "catalogo_fontes_web", "descricao": "Catálogo curado de domínios de alta confiança para busca web."},
    ]


def _schema_vazio() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "additionalProperties": False}


def _schema_props(**fields: dict[str, Any]) -> dict[str, Any]:
    required = [k for k, v in fields.items() if v.get("required")]
    props = {k: {kk: vv for kk, vv in v.items() if kk != "required"} for k, v in fields.items()}
    out: dict[str, Any] = {"type": "object", "properties": props, "additionalProperties": False}
    if required:
        out["required"] = required
    return out


_PARAMETROS_OPENAI: dict[str, dict[str, Any]] = {
    "snapshot_operacional": _schema_vazio(),
    "limites_historico": _schema_vazio(),
    "catalogo_fontes_web": _schema_vazio(),
    "resumo_periodo": _schema_props(
        inicio={"type": "string", "description": "Data início ISO (YYYY-MM-DD)."},
        fim={"type": "string", "description": "Data fim ISO (YYYY-MM-DD)."},
        parceiro_id={"type": "integer", "description": "ID do parceiro comercial."},
    ),
    "timeline_anual": _schema_props(
        ano_inicio={"type": "integer", "description": "Ano inicial."},
        ano_fim={"type": "integer", "description": "Ano final."},
        parceiro_id={"type": "integer", "description": "ID do parceiro."},
    ),
    "impacto_geral": _schema_props(
        ano_inicio={"type": "integer", "description": "Ano inicial."},
        ano_fim={"type": "integer", "description": "Ano final."},
        parceiro_id={"type": "integer", "description": "ID do parceiro."},
    ),
    "busca_unificada": _schema_props(
        consulta={"type": "string", "description": "Termo de busca.", "required": True},
        limite={"type": "integer", "description": "Máximo de itens (1-30)."},
        parceiro_id={"type": "integer", "description": "Filtrar por parceiro."},
    ),
    "busca_web": _schema_props(
        consulta={"type": "string", "description": "Consulta para busca externa.", "required": True},
    ),
    "listar_candidatos_prospeccao": _schema_props(
        limite={"type": "integer", "description": "Quantidade de candidatos (1-50)."},
        qid={"type": "string", "description": "Contexto QID do ranking."},
        prioridade={"type": "string", "description": "alta, media ou baixa."},
        model_version={"type": "string", "description": "Versão do modelo REE."},
    ),
    "explicar_candidato_prospeccao": _schema_props(
        score_id={"type": "integer", "description": "ID do score do candidato.", "required": True},
        model_version={"type": "string", "description": "Versão do modelo REE."},
    ),
    "status_modelo_prospeccao": _schema_props(
        model_version={"type": "string", "description": "Versão do modelo REE."},
    ),
    "cruzar_crm_prospeccao": _schema_props(
        pipeline_id={"type": "integer", "description": "ID do pipeline CRM."},
        empresa={"type": "string", "description": "Nome da empresa para cruzar."},
        limite_scores={"type": "integer", "description": "Máximo de scores retornados."},
        model_version={"type": "string", "description": "Versão do modelo REE (opcional)."},
        modo_global={"type": "boolean", "description": "Cruzar todos os pipelines CRM com REE."},
    ),
    "info_coletor": _schema_props(
        coletor_id={"type": "integer", "description": "ID numérico do coletor.", "required": True},
        dias={"type": "integer", "description": "Janela de dias para totais (padrão 90)."},
    ),
    "listar_coletores": _schema_props(
        status={"type": "string", "description": "Filtrar por status (ex.: OK, QUEBRADA)."},
        parceiro_id={"type": "integer", "description": "Filtrar por parceiro comercial."},
        sem_coleta_dias={"type": "integer", "description": "Apenas coletores sem coleta há N dias ou mais."},
        limite={"type": "integer", "description": "Máximo de coletores (1-50)."},
    ),
    "status_sensores": _schema_props(
        coletor_id={"type": "integer", "description": "Filtrar sensores de um coletor."},
        bateria_max={"type": "number", "description": "Apenas sensores com bateria ≤ valor."},
        limite={"type": "integer", "description": "Máximo de sensores (1-50)."},
    ),
    "historico_coletas": _schema_props(
        coletor_id={"type": "integer", "description": "Filtrar por coletor."},
        parceiro_id={"type": "integer", "description": "Filtrar por parceiro."},
        inicio={"type": "string", "description": "Data início ISO (YYYY-MM-DD)."},
        fim={"type": "string", "description": "Data fim ISO (YYYY-MM-DD)."},
        tipo_operacao={"type": "string", "description": "Tipo de operação da coleta."},
        pagina={"type": "integer", "description": "Página (1-indexed)."},
        por_pagina={"type": "integer", "description": "Itens por página (1-50)."},
    ),
    "ml_coletor": _schema_props(
        coletor_id={"type": "integer", "description": "ID do coletor.", "required": True},
    ),
    "ranking_ml": _schema_props(
        limite={"type": "integer", "description": "Quantidade no ranking (1-50)."},
    ),
    "listar_pipeline": _schema_props(
        status={"type": "string", "description": "Filtrar por status do deal (ex.: negociacao)."},
        responsavel_id={"type": "integer", "description": "Filtrar por responsável comercial."},
        limite={"type": "integer", "description": "Máximo de deals (1-50)."},
    ),
    "listar_tarefas_comerciais": _schema_props(
        status={"type": "string", "description": "Status da tarefa (padrão: aberta/pendente)."},
        limite={"type": "integer", "description": "Máximo de tarefas (1-50)."},
    ),
    "interacoes_pipeline": _schema_props(
        pipeline_id={"type": "integer", "description": "ID do pipeline CRM.", "required": True},
        limite={"type": "integer", "description": "Máximo de interações (1-50)."},
    ),
    "listar_notificacoes": _schema_props(
        lida={"type": "boolean", "description": "True=só lidas; False=só não lidas."},
        limite={"type": "integer", "description": "Máximo de notificações (1-50)."},
    ),
    "listar_solicitacoes": _schema_props(
        status={"type": "string", "description": "Filtrar por status (pendente, aprovado, recusado)."},
        limite={"type": "integer", "description": "Máximo de solicitações (1-50)."},
    ),
    "meta_comercial": _schema_props(
        mes={"type": "string", "description": "Mês no formato YYYY-MM (padrão: mês atual)."},
    ),
    "exportar_coletas_csv": _schema_props(
        inicio={"type": "string", "description": "Data início ISO (YYYY-MM-DD)."},
        fim={"type": "string", "description": "Data fim ISO (YYYY-MM-DD)."},
        parceiro_ids={"type": "array", "items": {"type": "integer"}, "description": "IDs de parceiros."},
        parceiro_nomes={"type": "array", "items": {"type": "string"}, "description": "Nomes de parceiros."},
    ),
    "comparar_candidatos": _schema_props(
        score_ids={
            "type": "array",
            "items": {"type": "integer"},
            "description": "Lista de score_id para comparar.",
        },
        empresa_ids={
            "type": "array",
            "items": {"type": "integer"},
            "description": "Lista de empresa_id para comparar.",
        },
        limite={"type": "integer", "description": "Máximo de candidatos na comparação."},
    ),
    "gerar_roteiro_contato": _schema_props(
        score_id={"type": "integer", "description": "ID do score do candidato."},
        empresa_id={"type": "integer", "description": "ID da empresa candidata."},
        pipeline_id={"type": "integer", "description": "ID do pipeline CRM."},
    ),
    "criar_tarefa_comercial": _schema_props(
        titulo={"type": "string", "description": "Título da tarefa CRM.", "required": True},
        pipeline_id={"type": "integer", "description": "ID do pipeline CRM."},
        empresa_id={"type": "integer", "description": "ID da empresa candidata."},
        data_limite={"type": "string", "description": "Prazo ISO ou DD/MM/YYYY."},
        descricao={"type": "string", "description": "Descrição opcional."},
    ),
    "cadastrar_coleta": _schema_props(
        parceiro_nome={"type": "string", "description": "Nome do parceiro/cliente reconhecido no sistema."},
        volume_kg={"type": "number", "description": "Peso coletado em kg."},
        km_percorrido_km={"type": "number", "description": "Distância percorrida em km."},
        coletor_ref={"type": "string", "description": "Referência do coletor, ex.: L037."},
        data_coleta={"type": "string", "description": "Data: 'hoje', ISO YYYY-MM-DD ou DD/MM/YYYY."},
        tipo_operacao={"type": "string", "description": "Avulsa ou Campanha."},
        preco_combustivel={"type": "number", "description": "Preço do combustível por litro (opcional)."},
    ),
}


def ferramentas_openai_schema() -> list[dict[str, Any]]:
    """Converte o catálogo interno em definições OpenAI function-calling."""
    saida: list[dict[str, Any]] = []
    for item in catalogo_ferramentas():
        nome = str(item.get("nome") or "").strip()
        if not nome:
            continue
        params = _PARAMETROS_OPENAI.get(nome, _schema_vazio())
        saida.append(
            {
                "type": "function",
                "function": {
                    "name": nome,
                    "description": str(item.get("descricao") or nome),
                    "parameters": params,
                },
            }
        )
    return saida

