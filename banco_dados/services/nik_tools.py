"""
Ferramentas de dados da Nik para conversa integrada.

Esta camada desacopla o "chat livre" das consultas de dados. A Nik pode
usar essas ferramentas para responder com base real do sistema e explicitar
quais fontes foram usadas.
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import date, datetime
from ipaddress import ip_address
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from banco_dados.modelos import Coleta, Coletor, ContratoRecorrente, Parceiro, Pipeline
from banco_dados.services import nik_contexto as ctx
from banco_dados.services import preview_service as pv
from banco_dados.services import prospeccao_xgb_service as prospeccao_svc
from banco_dados.utils.cache import obter_cache

_WEB_CHAMADAS_TS: list[float] = []


def _web_request_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    if any(k in msg for k in ("timed out", "timeout", "temporarily unavailable", "502", "503", "504")):
        return True
    if isinstance(exc, HTTPError) and exc.code in (502, 503, 504):
        return True
    if isinstance(exc, URLError):
        return True
    return False


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
    last: Optional[BaseException] = None
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


def _limites_historico(db: Session) -> tuple[Optional[date], Optional[date]]:
    row = db.query(func.min(Coleta.data_hora), func.max(Coleta.data_hora)).first()
    if not row:
        return None, None
    minimo, maximo = row
    return (minimo.date() if minimo else None, maximo.date() if maximo else None)


def ferramenta_limites_historico(db: Session) -> dict[str, Optional[str]]:
    inicio, fim = _limites_historico(db)
    return {
        "inicio": inicio.isoformat() if inicio else None,
        "fim": fim.isoformat() if fim else None,
    }


def ferramenta_snapshot_operacional(db: Session) -> dict[str, Any]:
    return ctx.contexto_conversa_ops(db)


def ferramenta_resumo_periodo(
    db: Session,
    inicio: Optional[str] = None,
    fim: Optional[str] = None,
    parceiro_id: Optional[int] = None,
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
    ano_inicio: Optional[int] = None,
    ano_fim: Optional[int] = None,
    parceiro_id: Optional[int] = None,
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
    ano_inicio: Optional[int] = None,
    ano_fim: Optional[int] = None,
    parceiro_id: Optional[int] = None,
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
    score_id: Optional[int] = None,
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
    parceiro_id: Optional[int] = None,
) -> dict[str, Any]:
    termo = _normalizar_texto(consulta or "")
    if not termo:
        return {"consulta": "", "itens": [], "resumo": "Consulta vazia."}

    tokens = _tokens_busca(consulta or "")
    like = f"%{termo}%"
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
        (func.lower(Coletor.localizacao).like(like))
        | (func.lower(func.coalesce(Parceiro.nome, "")).like(like))
        | (func.lower(func.coalesce(Coleta.tipo_operacao, "")).like(like))
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
            (func.lower(func.coalesce(Pipeline.status, "")).like(like))
            | (func.lower(func.coalesce(Pipeline.tipo_servico, "")).like(like))
            | (func.lower(func.coalesce(Pipeline.origem, "")).like(like))
            | (func.lower(func.coalesce(Pipeline.observacoes, "")).like(like))
            | (func.lower(func.coalesce(Coletor.localizacao, "")).like(like))
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
            (func.lower(func.coalesce(ContratoRecorrente.titulo, "")).like(like))
            | (func.lower(func.coalesce(ContratoRecorrente.descricao, "")).like(like))
            | (func.lower(func.coalesce(ContratoRecorrente.status, "")).like(like))
            | (func.lower(func.coalesce(Parceiro.nome, "")).like(like))
            | (func.lower(func.coalesce(Coletor.localizacao, "")).like(like))
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
    if allowlist and not any(host == d or host.endswith(f".{d}") for d in allowlist):
        return False
    return True


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
        {"nome": "busca_web", "descricao": "Busca na internet com guardrails e fontes externas auditáveis."},
        {"nome": "catalogo_fontes_web", "descricao": "Catálogo curado de domínios de alta confiança para busca web."},
    ]

