"""Build versioned feature snapshots for the REE prospection ranker."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata, FeatureSnapshotProspeccao, LocalCandidato
from jobs.prospeccao.ranker_contract import (
    FEATURE_SCHEMA_VERSION,
    build_feature_vector,
    cnae_ree_fit,
    feature_schema,
    heuristic_relevance_label,
)

logger = logging.getLogger(__name__)


DEMO_CANDIDATES = [
    {
        "cnpj": "00000000000191",
        "razao_social": "Demo Informatica Asa Sul LTDA",
        "nome_fantasia": "Demo TI Asa Sul",
        "cnae_principal": "4751201",
        "porte": "Empresa de Pequeno Porte",
        "situacao_cadastral": "ATIVA",
        "email": "contato@demo-ti.example",
        "telefone": "(61) 3333-0001",
        "bairro": "Asa Sul",
        "ra": "Plano Piloto",
        "latitude": -15.8105,
        "longitude": -47.8894,
        "categoria_operacional": "varejo de informatica",
    },
    {
        "cnpj": "00000000000272",
        "razao_social": "Demo Assistencia Eletronica Taguatinga",
        "nome_fantasia": "Conserta Eletronicos Demo",
        "cnae_principal": "9511800",
        "porte": "Microempresa",
        "situacao_cadastral": "ATIVA",
        "telefone": "(61) 3333-0002",
        "bairro": "Taguatinga Centro",
        "ra": "Taguatinga",
        "latitude": -15.8317,
        "longitude": -48.0568,
        "categoria_operacional": "assistencia eletronica",
    },
    {
        "cnpj": "00000000000353",
        "razao_social": "Demo Escola Tecnica Ceilandia",
        "nome_fantasia": "ET Demo",
        "cnae_principal": "8599604",
        "porte": "Demais",
        "situacao_cadastral": "ATIVA",
        "email": "secretaria@etdemo.example",
        "bairro": "Ceilandia",
        "ra": "Ceilandia",
        "latitude": -15.8191,
        "longitude": -48.1086,
        "categoria_operacional": "escola tecnica",
    },
]


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def seed_demo_candidates(db: Session) -> int:
    created = 0
    for row in DEMO_CANDIDATES:
        empresa = db.query(EmpresaCandidata).filter_by(cnpj=row["cnpj"]).first()
        if not empresa:
            empresa = EmpresaCandidata(
                cnpj=row["cnpj"],
                razao_social=row["razao_social"],
                nome_fantasia=row["nome_fantasia"],
                cnae_principal=row["cnae_principal"],
                porte=row["porte"],
                situacao_cadastral=row["situacao_cadastral"],
                email=row.get("email"),
                telefone=row.get("telefone"),
                bairro=row["bairro"],
                uf="DF",
                municipio="Brasilia",
                origem="demo",
            )
            db.add(empresa)
            db.flush()
            created += 1

        if not empresa.locais:
            db.add(
                LocalCandidato(
                    empresa_id=empresa.id,
                    endereco=f"{row['bairro']}, DF",
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    ra=row["ra"],
                    bairro=row["bairro"],
                    geocode_quality=0.90,
                    categoria_operacional=row["categoria_operacional"],
                    qid=f"ra:{row['ra'].lower()}",
                    origem="demo",
                )
            )
    db.flush()
    return created


def _qid_for(empresa: EmpresaCandidata, local: LocalCandidato | None) -> str:
    """Generate ranking group id.

    DF candidates group by RA (satellite city granularity).
    Entorno/GO candidates group by municipio name.
    """
    if local and local.qid:
        return local.qid
    if local and local.ra:
        return f"ra:{local.ra.lower()}"
    uf = (getattr(empresa, "uf", None) or "").strip().upper()
    if uf == "GO":
        municipio = getattr(empresa, "municipio", None) or getattr(local, "bairro", None) if local else None
        if municipio:
            return f"entorno:{municipio.strip().lower()}"
        return "entorno"
    if empresa.bairro:
        return f"bairro:{empresa.bairro.lower()}"
    return "df"


def build_feature_snapshots(
    db: Session,
    *,
    pipeline_version: str = FEATURE_SCHEMA_VERSION,
    seed_demo: bool = False,
) -> dict[str, Any]:
    if seed_demo:
        seed_demo_candidates(db)

    empresas = db.query(EmpresaCandidata).order_by(EmpresaCandidata.id.asc()).all()
    schema_json = _json(feature_schema())
    stats = {
        "pipeline_version": pipeline_version,
        "empresas": len(empresas),
        "snapshots_criados": 0,
        "seed_demo": seed_demo,
    }

    # Pre-compute neighborhood context per qid for spatial density features
    qid_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"qid_total": 0, "qid_ree_compatible": 0},
    )
    for empresa in empresas:
        for local in (empresa.locais or [None]):
            qid = _qid_for(empresa, local)
            qid_stats[qid]["qid_total"] += 1
            if cnae_ree_fit(getattr(empresa, "cnae_principal", None)) > 0:
                qid_stats[qid]["qid_ree_compatible"] += 1

    for empresa in empresas:
        locais = empresa.locais or [None]
        for local in locais:
            qid = _qid_for(empresa, local)
            features = build_feature_vector(empresa, local, neighborhood=qid_stats[qid])
            local_id = local.id if local else None
            snapshot = (
                db.query(FeatureSnapshotProspeccao)
                .filter(
                    FeatureSnapshotProspeccao.empresa_id == empresa.id,
                    FeatureSnapshotProspeccao.local_id == local_id,
                    FeatureSnapshotProspeccao.pipeline_version == pipeline_version,
                )
                .first()
            )
            if not snapshot:
                snapshot = FeatureSnapshotProspeccao(
                    empresa_id=empresa.id,
                    local_id=local_id,
                    pipeline_version=pipeline_version,
                )
                db.add(snapshot)
                stats["snapshots_criados"] += 1

            snapshot.qid = qid
            snapshot.label_ordinal = heuristic_relevance_label(features)
            snapshot.features_json = _json(features)
            snapshot.feature_schema_json = schema_json
            snapshot.criado_em = datetime.utcnow()

    logger.info("Feature snapshots criados: %s", stats)
    return stats
