"""Bridge between CRM pipeline leads and REE prospection scores."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from banco_dados.modelos import Coletor, EmpresaCandidata, LocalCandidato, Pipeline, ScoreProspeccao
from banco_dados.services import prospeccao_xgb_service
from banco_dados.services.crm_service import CRMService
from banco_dados.utils import utc_now_naive
from jobs.prospeccao.labels_internal import (
    extract_cnpjs_from_text,
    normalize_cnpj,
    normalize_org_name,
)
from jobs.prospeccao.publish_scores import (
    percentile_map_for_qid,
    resolve_model,
    serialize_published_score_row,
)


def _observacoes_pipeline_prospeccao(
    empresa: EmpresaCandidata,
    observacoes_extra: str | None = None,
) -> str:
    """Monta observações do lead CRM com razão social e CNPJ da candidata."""
    nome = (empresa.razao_social or empresa.nome_fantasia or "Empresa").strip()
    partes = [nome]
    if empresa.cnpj:
        partes.append(f"CNPJ: {empresa.cnpj}")
    if observacoes_extra and str(observacoes_extra).strip():
        partes.append(str(observacoes_extra).strip())
    return "\n".join(partes)[:1000]


def criar_pipeline_de_candidato(
    db: Session,
    empresa_id: int,
    usuario_id: int | None = None,
    *,
    observacoes: str | None = None,
    valor_estimado: float | None = None,
    status: str | None = None,
) -> dict[str, Any] | None:
    """Cria lead CRM a partir de ``EmpresaCandidata`` e vincula ``pipeline_id``."""
    empresa = db.query(EmpresaCandidata).filter_by(id=empresa_id).first()
    if not empresa:
        return None

    if empresa.pipeline_id:
        pipeline = db.query(Pipeline).filter_by(id=empresa.pipeline_id).first()
        if pipeline:
            return {
                "pipeline_id": pipeline.id,
                "empresa_id": empresa.id,
                "status": pipeline.status,
                "valor_estimado": float(pipeline.valor_estimado or 0),
                "origem": pipeline.origem,
                "ja_vinculado": True,
            }
        empresa.pipeline_id = None
        empresa.atualizado_em = utc_now_naive()
        db.flush()

    status_final = (status or "lead").strip().lower()
    if status_final not in CRMService.STATUS_PROBABILIDADE:
        raise ValueError(f"Status inválido: {status_final}")

    valor = float(valor_estimado) if valor_estimado is not None else 0.0
    pipeline = Pipeline(
        status=status_final,
        valor_estimado=valor,
        probabilidade=CRMService.STATUS_PROBABILIDADE.get(status_final, 10),
        responsavel_id=usuario_id,
        origem="prospeccao_ree",
        observacoes=_observacoes_pipeline_prospeccao(empresa, observacoes),
        atualizado_em=utc_now_naive(),
    )
    db.add(pipeline)
    db.flush()

    empresa.pipeline_id = pipeline.id
    empresa.atualizado_em = utc_now_naive()
    db.commit()
    db.refresh(pipeline)

    return {
        "pipeline_id": pipeline.id,
        "empresa_id": empresa.id,
        "status": pipeline.status,
        "valor_estimado": float(pipeline.valor_estimado or 0),
        "origem": pipeline.origem,
        "observacoes": pipeline.observacoes,
        "ja_vinculado": False,
    }


def _match_empresa_por_nome(
    busca_norm: str,
    empresa: EmpresaCandidata | None,
    *,
    cnpjs_busca: set[str],
) -> str | None:
    """Return match source label or None."""
    if not empresa:
        return None

    cnpj = normalize_cnpj(empresa.cnpj)
    if cnpj and cnpj in cnpjs_busca:
        return "cnpj"

    if not busca_norm:
        return None

    for field, source in (("razao_social", "razao_social"), ("nome_fantasia", "nome_fantasia")):
        valor = getattr(empresa, field, None)
        if not valor:
            continue
        emp_norm = normalize_org_name(valor)
        if not emp_norm:
            continue
        if emp_norm == busca_norm:
            return source
        if busca_norm in emp_norm or emp_norm in busca_norm:
            return f"{source}_parcial"
    return None


def _attach_score_percentis(db: Session, model_id: int, rows: list[dict[str, Any]]) -> None:
    cache: dict[str, dict[int, float]] = {}
    for row in rows:
        qid = row.get("qid")
        sid = row.get("id")
        if not qid or sid is None:
            row["score_percentil"] = 0.0
            continue
        if qid not in cache:
            cache[qid] = percentile_map_for_qid(db, model_id, str(qid))
        row["score_percentil"] = cache[qid].get(int(sid), 0.0)


def buscar_candidatos_por_nome_empresa(
    db: Session,
    nome: str,
    limite: int = 5,
    model_version: str | None = None,
) -> list[dict[str, Any]]:
    """Match published prospection scores by normalized company name."""
    busca_norm = normalize_org_name(nome)
    cnpjs_busca = extract_cnpjs_from_text(nome)
    if not busca_norm and not cnpjs_busca:
        return []

    model = resolve_model(db, model_version)
    if not model:
        return []

    rows = (
        db.query(ScoreProspeccao, EmpresaCandidata, LocalCandidato)
        .outerjoin(EmpresaCandidata, ScoreProspeccao.empresa_id == EmpresaCandidata.id)
        .outerjoin(LocalCandidato, ScoreProspeccao.local_id == LocalCandidato.id)
        .filter(ScoreProspeccao.modelo_id == model.id)
        .all()
    )

    matches: list[tuple[float, dict[str, Any]]] = []
    for score, empresa, local in rows:
        source = _match_empresa_por_nome(busca_norm, empresa, cnpjs_busca=cnpjs_busca)
        if not source:
            continue
        matches.append((
            score.score,
            serialize_published_score_row(score, empresa, local, match_source=source),
        ))

    matches.sort(key=lambda item: item[0], reverse=True)
    out = [row for _, row in matches[:limite]]
    _attach_score_percentis(db, model.id, out)
    return out


def _termos_busca_pipeline(pipeline: Pipeline, coletor: Coletor | None) -> list[str]:
    termos: list[str] = []
    if coletor and coletor.localizacao:
        termos.append(coletor.localizacao.strip())
    if pipeline.observacoes:
        termos.append(str(pipeline.observacoes).strip())
    return [t for t in termos if t]


def buscar_scores_para_pipeline(
    db: Session,
    pipeline_id: int,
    *,
    model_version: str | None = None,
) -> dict[str, Any] | None:
    """Resolve CRM pipeline to prospection scores and explain hints."""
    pipeline = (
        db.query(Pipeline)
        .options(joinedload(Pipeline.coletor))
        .filter_by(id=pipeline_id)
        .first()
    )
    if not pipeline:
        return None

    coletor = pipeline.coletor
    termos = _termos_busca_pipeline(pipeline, coletor)
    vistos: set[int] = set()
    scores: list[dict[str, Any]] = []

    for termo in termos:
        for item in buscar_candidatos_por_nome_empresa(db, termo, limite=5, model_version=model_version):
            score_id = item.get("id")
            if score_id is None or score_id in vistos:
                continue
            vistos.add(score_id)
            scores.append(item)

    hints: list[dict[str, Any]] = []
    for item in scores[:5]:
        score_id = item.get("id")
        if score_id is None:
            continue
        explain = prospeccao_xgb_service.explicar_candidato(db, score_id, model_version)
        hints.append({
            "score_id": score_id,
            "match_source": item.get("match_source"),
            "prioridade": item.get("prioridade"),
            "explicacao": (explain or {}).get("explicacao", item.get("motivos", [])),
        })

    return {
        "pipeline_id": pipeline.id,
        "pipeline_status": pipeline.status,
        "coletor_id": pipeline.coletor_id,
        "coletor_localizacao": coletor.localizacao if coletor else None,
        "termos_busca": termos,
        "scores": scores,
        "hints": hints,
    }


def _resumir_pipeline(pipeline: Pipeline, coletor: Coletor | None) -> dict[str, Any]:
    return {
        "id": pipeline.id,
        "status": pipeline.status,
        "valor_estimado": float(pipeline.valor_estimado or 0),
        "probabilidade": int(pipeline.probabilidade or 0),
        "origem": pipeline.origem,
        "tipo_servico": pipeline.tipo_servico,
        "coletor_id": pipeline.coletor_id,
        "coletor": coletor.localizacao if coletor else None,
        "observacoes": (pipeline.observacoes or "")[:400] or None,
        "proxima_acao": pipeline.proxima_acao,
    }


def _pipelines_por_nome_empresa(db: Session, nome: str, *, limite: int = 3) -> list[dict[str, Any]]:
    busca = normalize_org_name(nome)
    if len(busca) < 3:
        return []
    like = f"%{busca}%"
    rows = (
        db.query(Pipeline, Coletor)
        .outerjoin(Coletor, Pipeline.coletor_id == Coletor.id)
        .filter(
            (func.lower(func.coalesce(Pipeline.observacoes, "")).like(like))
            | (func.lower(func.coalesce(Pipeline.origem, "")).like(like))
            | (func.lower(func.coalesce(Coletor.localizacao, "")).like(like))
        )
        .order_by(Pipeline.atualizado_em.desc())
        .limit(max(1, min(limite, 10)))
        .all()
    )
    return [_resumir_pipeline(pipe, coletor) for pipe, coletor in rows]


def cruzar_crm_prospeccao(
    db: Session,
    *,
    pipeline_id: int | None = None,
    empresa: str | None = None,
    limite_scores: int = 5,
    model_version: str | None = None,
) -> dict[str, Any]:
    """Cruza pipeline CRM com scores do ranker REE (por pipeline_id ou nome da empresa)."""
    empresa_txt = (empresa or "").strip() or None
    if pipeline_id is None and not empresa_txt:
        return {
            "encontrado": False,
            "resumo": "Informe pipeline_id ou nome da empresa para cruzar CRM e prospecção.",
        }

    limite = max(1, min(int(limite_scores or 5), 20))
    pipeline_resumo: dict[str, Any] | None = None
    pipelines_relacionados: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    hints: list[dict[str, Any]] = []
    termos_busca: list[str] = []

    if pipeline_id is not None:
        cruzado = buscar_scores_para_pipeline(db, int(pipeline_id), model_version=model_version)
        if not cruzado:
            return {
                "encontrado": False,
                "pipeline_id": int(pipeline_id),
                "resumo": f"Pipeline CRM #{pipeline_id} não encontrado.",
            }
        row = (
            db.query(Pipeline, Coletor)
            .outerjoin(Coletor, Pipeline.coletor_id == Coletor.id)
            .filter(Pipeline.id == int(pipeline_id))
            .first()
        )
        pipe, coletor = row if row else (None, None)
        pipeline_resumo = _resumir_pipeline(pipe, coletor) if pipe else None
        scores = cruzado.get("scores") or []
        hints = cruzado.get("hints") or []
        termos_busca = cruzado.get("termos_busca") or []
        if empresa_txt:
            extra = buscar_candidatos_por_nome_empresa(
                db, empresa_txt, limite=limite, model_version=model_version
            )
            vistos = {s.get("id") for s in scores}
            for item in extra:
                if item.get("id") not in vistos:
                    scores.append(item)
                    vistos.add(item.get("id"))
    elif empresa_txt:
        scores = buscar_candidatos_por_nome_empresa(db, empresa_txt, limite=limite, model_version=model_version)
        pipelines_relacionados = _pipelines_por_nome_empresa(db, empresa_txt, limite=3)
        if pipelines_relacionados:
            pipeline_resumo = pipelines_relacionados[0]

    empresa_info = None
    if scores:
        emp = (scores[0].get("empresa") or {}) if isinstance(scores[0].get("empresa"), dict) else {}
        if emp:
            empresa_info = {
                "id": emp.get("id"),
                "cnpj": emp.get("cnpj"),
                "razao_social": emp.get("razao_social"),
                "nome_fantasia": emp.get("nome_fantasia"),
            }

    encontrado = bool(pipeline_resumo or scores or pipelines_relacionados)
    melhor = scores[0] if scores else None
    partes: list[str] = []
    if pipeline_resumo:
        partes.append(
            f"CRM pipeline #{pipeline_resumo['id']} ({pipeline_resumo.get('status')}, "
            f"prob. {pipeline_resumo.get('probabilidade')}%)"
        )
    if empresa_info and empresa_info.get("razao_social"):
        partes.append(f"empresa {empresa_info['razao_social']}")
    elif empresa_txt:
        partes.append(f"busca '{empresa_txt}'")
    if scores:
        rank = melhor.get("ranking_contexto") if melhor else None
        rank_txt = f" (melhor rank {rank})" if rank is not None else ""
        partes.append(f"{len(scores)} score(s) REE{rank_txt}")
    elif empresa_txt and not pipeline_id:
        return {
            "encontrado": False,
            "empresa_consulta": empresa_txt,
            "pipelines_relacionados": pipelines_relacionados,
            "resumo": f"Empresa '{empresa_txt}' não encontrada na base de prospecção.",
        }

    return {
        "encontrado": encontrado,
        "pipeline_id": pipeline_resumo.get("id") if pipeline_resumo else pipeline_id,
        "empresa_consulta": empresa_txt,
        "pipeline": pipeline_resumo,
        "pipelines_relacionados": pipelines_relacionados,
        "empresa": empresa_info,
        "scores_prospeccao": scores,
        "hints_explicacao": hints,
        "termos_busca": termos_busca,
        "total_scores": len(scores),
        "resumo": (
            "Cruzamento CRM ↔ prospecção: " + "; ".join(partes) + "."
            if partes
            else "Nenhum vínculo encontrado entre CRM e ranker REE."
        ),
    }
