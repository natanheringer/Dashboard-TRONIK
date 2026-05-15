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
    heuristic_relevance_continuous,
    listwise_training_qid,
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


def _equal_frequency_ordinal_labels(scores: list[float], n_bins: int = 8) -> list[int]:
    """Global relevance ordinals 0..n_bins-1 with ~equal count per bin (handles ties)."""
    n = len(scores)
    if n == 0:
        return []
    if n < n_bins:
        return [0] * n
    order = sorted(range(n), key=lambda i: (scores[i], i))
    out = [0] * n
    for rank, idx in enumerate(order):
        out[idx] = min(n_bins - 1, int(rank * n_bins / n))
    return out


def build_feature_snapshots(
    db: Session,
    *,
    pipeline_version: str = FEATURE_SCHEMA_VERSION,
    seed_demo: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    if seed_demo:
        seed_demo_candidates(db)

    q = db.query(EmpresaCandidata).order_by(EmpresaCandidata.id.asc())
    if limit is not None and limit > 0:
        q = q.limit(limit)
    empresas = q.all()
    total = len(empresas)
    logger.info(
        "build-features: carregadas %s empresas (limit=%s); montando qid_stats…",
        total,
        limit,
    )
    schema_json = _json(feature_schema())
    stats = {
        "pipeline_version": pipeline_version,
        "empresas": total,
        "snapshots_criados": 0,
        "seed_demo": seed_demo,
        "limit": limit,
    }

    # Pre-compute neighborhood context per qid for spatial density features
    qid_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"qid_total": 0, "qid_ree_compatible": 0},
    )
    for i, empresa in enumerate(empresas, start=1):
        for local in (empresa.locais or [None]):
            qid = listwise_training_qid(empresa, local)
            qid_stats[qid]["qid_total"] += 1
            if cnae_ree_fit(getattr(empresa, "cnae_principal", None)) > 0:
                qid_stats[qid]["qid_ree_compatible"] += 1
        if i % 10_000 == 0 or i == total:
            logger.info("build-features: qid_stats %s/%s empresas", i, total)

    # Uma leitura em lote evita ~1 SELECT por candidato no loop principal (SQLite ficava horas).
    snapshot_by_key: dict[tuple[int, int | None], FeatureSnapshotProspeccao] = {}
    for snap in (
        db.query(FeatureSnapshotProspeccao)
        .filter(FeatureSnapshotProspeccao.pipeline_version == pipeline_version)
        .all()
    ):
        snapshot_by_key[(snap.empresa_id, snap.local_id)] = snap
    logger.info(
        "build-features: %s snapshots já existentes para %s; atualizando/inserindo…",
        len(snapshot_by_key),
        pipeline_version,
    )

    n_label_bins = 8
    bucket: list[
        tuple[EmpresaCandidata, LocalCandidato | None, str, dict[str, float], float, int | None]
    ] = []
    processed_rows = 0
    for i, empresa in enumerate(empresas, start=1):
        locais = empresa.locais or [None]
        for local in locais:
            qid = listwise_training_qid(empresa, local)
            features = build_feature_vector(empresa, local, neighborhood=qid_stats[qid])
            raw = heuristic_relevance_continuous(features)
            local_id = local.id if local else None
            key = (empresa.id, local_id)
            snapshot = snapshot_by_key.get(key)
            if not snapshot:
                snapshot = FeatureSnapshotProspeccao(
                    empresa_id=empresa.id,
                    local_id=local_id,
                    pipeline_version=pipeline_version,
                )
                db.add(snapshot)
                snapshot_by_key[key] = snapshot
                stats["snapshots_criados"] += 1
            bucket.append((empresa, local, qid, features, raw, local_id))
            processed_rows += 1

        if i % 10_000 == 0 or i == total:
            logger.info(
                "build-features: buffer %s/%s empresas (%s linhas)",
                i,
                total,
                processed_rows,
            )

    # Group bucket by qid for listwise label computation
    qid_bucket_idxs: dict[str, list[int]] = defaultdict(list)
    for idx, (_, _, qid, _, _, _) in enumerate(bucket):
        qid_bucket_idxs[qid].append(idx)

    ordinals = [0] * len(bucket)
    for qid_group_idxs in qid_bucket_idxs.values():
        group_scores = [bucket[i][4] for i in qid_group_idxs]
        group_labels = _equal_frequency_ordinal_labels(group_scores, n_bins=n_label_bins)
        for idx, label in zip(qid_group_idxs, group_labels):
            ordinals[idx] = label

    stats["label_binning"] = "equal_frequency_rank_per_qid"
    stats["label_bins"] = n_label_bins
    stats["unique_qids"] = len(qid_stats)

    for (empresa, _local, qid, features, raw, local_id), ord_label in zip(bucket, ordinals, strict=True):
        key = (empresa.id, local_id)
        snapshot = snapshot_by_key[key]
        snapshot.qid = qid
        snapshot.label_ordinal = ord_label
        snapshot.features_json = _json(features)
        snapshot.feature_schema_json = schema_json
        snapshot.criado_em = datetime.utcnow()

    logger.info("Feature snapshots concluído: %s", stats)
    return stats
