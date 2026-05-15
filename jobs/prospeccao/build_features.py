"""Build versioned feature snapshots for the REE prospection ranker."""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime
from statistics import median
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


def _compute_feature_statistics(
    bucket: list[tuple],
    FEATURE_NAMES: list[str],
) -> dict[str, dict[str, float]]:
    """Compute mean, nonzero_pct, and max for each feature from sample."""
    sample_size = min(10_000, len(bucket))
    sample_idxs = list(range(0, len(bucket), max(1, len(bucket) // sample_size)))[:sample_size]

    feature_stats = {}
    for feat_name in FEATURE_NAMES:
        vals = []
        for idx in sample_idxs:
            _, _, _, features, _, _ = bucket[idx]
            vals.append(features.get(feat_name, 0.0))

        nonzero_count = sum(1 for v in vals if v != 0)
        feature_stats[feat_name] = {
            "mean": round(sum(vals) / len(vals) if vals else 0, 4),
            "nonzero_pct": round(nonzero_count / len(vals) * 100 if vals else 0, 1),
            "max": round(max(vals) if vals else 0, 4),
        }

    return feature_stats


def _check_feature_quality_alerts(
    feature_stats: dict[str, dict[str, float]],
    unique_qids: int,
) -> list[str]:
    """Return list of quality warnings."""
    warnings = []

    # Check for empty or sparse features
    for feat_name, stats in feature_stats.items():
        if stats["nonzero_pct"] < 5.0:
            warnings.append(
                f"Feature '{feat_name}' is sparse (nonzero_pct={stats['nonzero_pct']}%) "
                "— probably empty/useless"
            )
        if stats["mean"] == 0.0:
            warnings.append(
                f"Feature '{feat_name}' is constant (mean=0.0) "
                "— no discriminative power"
            )

    # Check QID coverage for LTR viability
    if unique_qids < 10:
        warnings.append(
            f"Only {unique_qids} unique QIDs detected — LTR training will be compromised"
        )

    return warnings


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

    # Calculate QID coverage report BEFORE label computation
    qid_sizes = Counter(qid for _, _, qid, _, _, _ in bucket)
    if qid_sizes:
        qid_sizes_list = list(qid_sizes.values())
        singleton_count = sum(1 for s in qid_sizes_list if s == 1)
        stats["qid_distribution"] = {
            "unique_qids": len(qid_sizes),
            "median_group_size": median(qid_sizes_list),
            "min_group_size": min(qid_sizes_list),
            "max_group_size": max(qid_sizes_list),
            "singleton_qids_pct": round(singleton_count / len(qid_sizes) * 100, 1),
        }
        logger.info(
            "QID distribution: %d unique QIDs, median=%d, min=%d, max=%d, singletons=%.1f%%",
            len(qid_sizes),
            stats["qid_distribution"]["median_group_size"],
            stats["qid_distribution"]["min_group_size"],
            stats["qid_distribution"]["max_group_size"],
            stats["qid_distribution"]["singleton_qids_pct"],
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

    # Compute feature statistics on sample (up to 10k rows for memory efficiency)
    logger.info("build-features: calculando estatísticas por feature na amostra…")
    FEATURE_NAMES = list(feature_schema().keys())
    feature_stats = _compute_feature_statistics(bucket, FEATURE_NAMES)
    stats["feature_stats"] = feature_stats

    # Check for quality alerts
    quality_warnings = _check_feature_quality_alerts(feature_stats, stats["unique_qids"])
    if quality_warnings:
        logger.warning(
            "build-features: %d quality alerts detected:\n%s",
            len(quality_warnings),
            "\n".join(f"  - {w}" for w in quality_warnings),
        )
        stats["quality_warnings"] = quality_warnings
    else:
        logger.info("build-features: sem alertas de qualidade detectados")

    # Update snapshots with features and commit in batches to avoid long-running transactions
    BATCH_SIZE = 5000
    logger.info(
        "build-features: atualizando %s snapshots em batches de %s (libera locks intermediários)…",
        len(bucket),
        BATCH_SIZE,
    )

    for batch_start in range(0, len(bucket), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(bucket))
        for idx in range(batch_start, batch_end):
            empresa, _local, qid, features, raw, local_id = bucket[idx]
            key = (empresa.id, local_id)
            snapshot = snapshot_by_key[key]
            snapshot.qid = qid
            snapshot.label_ordinal = ordinals[idx]
            snapshot.features_json = _json(features)
            snapshot.feature_schema_json = schema_json
            snapshot.criado_em = datetime.utcnow()

        # Flush and commit each batch to release locks and prevent transaction lock-ups
        db.flush()
        db.commit()
        logger.info(
            "build-features: batch %s/%s snapshots commitado (liberado locks para outras transações)",
            min(batch_end, len(bucket)),
            len(bucket),
        )

    logger.info("Feature snapshots concluído: %s", stats)
    return stats
