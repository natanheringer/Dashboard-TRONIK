"""Train or bootstrap the REE prospection ranker.

v3+: geo-first listwise qids + quantile labels live in snapshots; training shards
oversized groups and guarantees enough multi-document qids for validation.

v2: group-aware validation, hyperparameter search, monotonic XGBRanker, quality gate.
"""

from __future__ import annotations

import json
import logging
import random
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import FeatureSnapshotProspeccao, ModeloProspeccao
from jobs.prospeccao import config
from jobs.prospeccao.ranker_contract import (
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    MONOTONIC_CONSTRAINTS,
)

logger = logging.getLogger(__name__)

MODEL_DIR = config.REPO_ROOT / "data" / "ml" / "prospeccao"

MIN_ACTIVATION_NDCG = 0.30


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_training_rows(
    db: Session,
    pipeline_version: str,
) -> list[FeatureSnapshotProspeccao]:
    return (
        db.query(FeatureSnapshotProspeccao)
        .filter(FeatureSnapshotProspeccao.pipeline_version == pipeline_version)
        .order_by(FeatureSnapshotProspeccao.qid.asc(), FeatureSnapshotProspeccao.id.asc())
        .all()
    )


def _group_rows(rows: list[FeatureSnapshotProspeccao]) -> dict[str, list[FeatureSnapshotProspeccao]]:
    grouped: dict[str, list[FeatureSnapshotProspeccao]] = defaultdict(list)
    for row in rows:
        grouped[row.qid].append(row)
    return grouped


def _matrix(grouped: dict[str, list[FeatureSnapshotProspeccao]]) -> tuple[list[list[float]], list[int], list[int]]:
    x: list[list[float]] = []
    y: list[int] = []
    group_sizes: list[int] = []
    for qid in sorted(grouped):
        items = grouped[qid]
        group_sizes.append(len(items))
        for item in items:
            features = json.loads(item.features_json)
            x.append([float(features.get(name, 0.0)) for name in FEATURE_NAMES])
            y.append(int(item.label_ordinal or 0))
    return x, y, group_sizes


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _mean_ndcg_by_group(y_true: list[int], y_score: list[float], group_sizes: list[int]) -> float | None:
    try:
        from sklearn.metrics import ndcg_score
    except Exception:
        return None

    scores = []
    cursor = 0
    for size in group_sizes:
        if size < 2:
            cursor += size
            continue
        yt = [y_true[cursor : cursor + size]]
        ys = [y_score[cursor : cursor + size]]
        scores.append(float(ndcg_score(yt, ys, k=min(20, size))))
        cursor += size
    if not scores:
        return None
    return round(sum(scores) / len(scores), 4)


# ---------------------------------------------------------------------------
# Validation split
# ---------------------------------------------------------------------------

def _shard_oversized_groups(
    grouped: dict[str, list[FeatureSnapshotProspeccao]],
    *,
    max_share: float = 0.025,
    shards: int = 128,
) -> dict[str, list[FeatureSnapshotProspeccao]]:
    """Break dominant qids so LTR has many listwise groups and validation can hold out."""
    total = sum(len(items) for items in grouped.values())
    if total == 0:
        return grouped
    out: dict[str, list[FeatureSnapshotProspeccao]] = {}
    for qid, items in grouped.items():
        share = len(items) / total
        if share > max_share and len(items) >= shards * 4:
            for row in items:
                h = (row.empresa_id ^ (row.local_id or 0) ^ 0x9E3779B9) % shards
                nq = f"{qid}~s{h}"
                out.setdefault(nq, []).append(row)
        else:
            out[qid] = list(items)
    return out


def _ensure_multi_item_qids(
    grouped: dict[str, list[FeatureSnapshotProspeccao]],
    *,
    min_qids_with_pair: int = 12,
    shards: int = 96,
) -> dict[str, list[FeatureSnapshotProspeccao]]:
    """If almost all groups are singletons, hash-bucket globally for trainable LTR."""
    multi = [qid for qid, items in grouped.items() if len(items) >= 2]
    if len(multi) >= min_qids_with_pair:
        return grouped
    flat: list[FeatureSnapshotProspeccao] = []
    for items in grouped.values():
        flat.extend(items)
    out: dict[str, list[FeatureSnapshotProspeccao]] = defaultdict(list)
    for row in flat:
        h = (row.empresa_id ^ (row.local_id or 0) ^ 0x85EBCA6B) % shards
        out[f"ltr~{h}"].append(row)
    return dict(out)


def _stratified_qid_split(
    grouped: dict[str, list[FeatureSnapshotProspeccao]],
    validation_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[dict[str, list[FeatureSnapshotProspeccao]], dict[str, list[FeatureSnapshotProspeccao]]]:
    """Hold out entire qid groups so validation measures cross-group generalization."""
    qids = [qid for qid, items in grouped.items() if len(items) >= 2]
    if len(qids) < 2:
        return grouped, {}

    rng = random.Random(seed)
    shuffled = qids[:]
    rng.shuffle(shuffled)
    holdout_count = max(1, int(round(len(shuffled) * validation_ratio)))
    holdout = set(shuffled[:holdout_count])

    train_grouped: dict[str, list[FeatureSnapshotProspeccao]] = {}
    val_grouped: dict[str, list[FeatureSnapshotProspeccao]] = {}
    for qid, items in grouped.items():
        if qid in holdout:
            val_grouped[qid] = items
        else:
            train_grouped[qid] = items
    if not val_grouped:
        return grouped, {}
    return train_grouped, val_grouped


# ---------------------------------------------------------------------------
# Hyperparameter search space
# ---------------------------------------------------------------------------

def _ranker_param_candidates() -> list[dict[str, Any]]:
    base = {
        "objective": "rank:ndcg",
        "eval_metric": "ndcg@20",
        "monotone_constraints": MONOTONIC_CONSTRAINTS,
        "random_state": 42,
        "n_jobs": -1,
    }
    return [
        {**base, "n_estimators": 200, "max_depth": 3, "learning_rate": 0.07,
         "subsample": 0.90, "colsample_bytree": 0.90, "min_child_weight": 2,
         "reg_lambda": 1.0, "reg_alpha": 0.0},
        {**base, "n_estimators": 260, "max_depth": 4, "learning_rate": 0.05,
         "subsample": 0.85, "colsample_bytree": 0.85, "min_child_weight": 3,
         "reg_lambda": 1.5, "reg_alpha": 0.1},
        {**base, "n_estimators": 320, "max_depth": 5, "learning_rate": 0.04,
         "subsample": 0.80, "colsample_bytree": 0.80, "min_child_weight": 4,
         "reg_lambda": 2.0, "reg_alpha": 0.2},
        {**base, "n_estimators": 400, "max_depth": 6, "learning_rate": 0.03,
         "subsample": 0.75, "colsample_bytree": 0.75, "min_child_weight": 5,
         "reg_lambda": 3.0, "reg_alpha": 0.3},
        {**base, "tree_method": "hist", "n_estimators": 480, "max_depth": 5, "learning_rate": 0.025,
         "subsample": 0.88, "colsample_bytree": 0.82, "min_child_weight": 4,
         "reg_lambda": 2.2, "reg_alpha": 0.12},
        {**base, "tree_method": "hist", "n_estimators": 600, "max_depth": 7, "learning_rate": 0.018,
         "subsample": 0.82, "colsample_bytree": 0.78, "min_child_weight": 5,
         "reg_lambda": 3.5, "reg_alpha": 0.22},
    ]


def _feature_importance(ranker: Any) -> dict[str, float]:
    try:
        importance = ranker.get_booster().get_score(importance_type="gain")
        result: dict[str, float] = {}
        for key, val in importance.items():
            idx = int(key.replace("f", ""))
            if idx < len(FEATURE_NAMES):
                result[FEATURE_NAMES[idx]] = round(float(val), 4)
        return result
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Model activation
# ---------------------------------------------------------------------------

def _activate_model(db: Session, model: ModeloProspeccao) -> None:
    db.query(ModeloProspeccao).filter(
        ModeloProspeccao.ativo.is_(True),
        ModeloProspeccao.id != model.id,
    ).update({"ativo": False})
    model.ativo = True


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def train_ranker(
    db: Session,
    *,
    pipeline_version: str = FEATURE_SCHEMA_VERSION,
    model_version: str | None = None,
    allow_baseline: bool = True,
) -> dict[str, Any]:
    rows = _load_training_rows(db, pipeline_version)
    model_version = model_version or f"{pipeline_version}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    schema_json = rows[0].feature_schema_json if rows else _json(
        [{"name": name, "type": "float", "version": pipeline_version} for name in FEATURE_NAMES]
    )

    metrics: dict[str, Any] = {}
    grouped = _group_rows(rows)
    metrics["groups_raw_snapshot_qid"] = len(grouped)
    grouped = _shard_oversized_groups(grouped)
    grouped = _ensure_multi_item_qids(grouped)
    metrics["groups_after_ltr_preprocess"] = len(grouped)

    x, y, group_sizes = _matrix(grouped)
    metrics.update(
        {
            "rows": len(rows),
            "groups": len(group_sizes),
            "label_distribution": {str(label): y.count(label) for label in sorted(set(y))},
        }
    )

    enough_for_ranker = (
        len(rows) >= 8
        and len(group_sizes) >= 2
        and any(size >= 2 for size in group_sizes)
        and len(set(y)) >= 2
    )

    artifact_path: str | None = None
    algoritmo = "heuristic_bootstrap"
    objetivo = "rank:ndcg"
    params: dict[str, Any] = {"reason": "insufficient_labeled_groups"}
    should_activate = True

    if enough_for_ranker:
        try:
            import joblib
            import numpy as np
            from xgboost import XGBRanker

            # --- qid-aware train / validation split ---
            train_grouped, val_grouped = _stratified_qid_split(grouped)
            x_train, y_train, train_group_sizes = _matrix(train_grouped)
            x_val, y_val, val_group_sizes = _matrix(val_grouped)

            x_train_np = np.asarray(x_train, dtype=float)
            y_train_np = np.asarray(y_train, dtype=float)
            x_val_np = np.asarray(x_val, dtype=float) if x_val else None

            # --- Hyperparameter search ---
            best_ranker = None
            best_params: dict[str, Any] | None = None
            best_val_ndcg = float("-inf")
            search_results: list[dict[str, Any]] = []

            for candidate in _ranker_param_candidates():
                has_eval = x_val_np is not None and val_group_sizes
                # XGBoost >= 2.x: early_stopping_rounds moved to constructor
                ctor_kwargs = dict(candidate)
                if has_eval:
                    ctor_kwargs["early_stopping_rounds"] = 35
                ranker = XGBRanker(**ctor_kwargs)
                fit_kwargs: dict[str, Any] = {
                    "group": train_group_sizes,
                    "verbose": False,
                }
                if has_eval:
                    fit_kwargs["eval_set"] = [
                        (x_train_np, y_train_np),
                        (x_val_np, np.asarray(y_val, dtype=float)),
                    ]
                    fit_kwargs["eval_group"] = [train_group_sizes, val_group_sizes]

                ranker.fit(x_train_np, y_train_np, **fit_kwargs)

                train_pred = [float(v) for v in ranker.predict(x_train_np)]
                train_ndcg = _mean_ndcg_by_group(y_train, train_pred, train_group_sizes)
                val_ndcg = None
                if x_val_np is not None and val_group_sizes:
                    val_pred = [float(v) for v in ranker.predict(x_val_np)]
                    val_ndcg = _mean_ndcg_by_group(y_val, val_pred, val_group_sizes)

                result_entry = {
                    "params": {k: v for k, v in candidate.items() if k != "monotone_constraints"},
                    "train_ndcg_mean": train_ndcg,
                    "val_ndcg_mean": val_ndcg,
                }
                search_results.append(result_entry)

                metric = val_ndcg if val_ndcg is not None else (train_ndcg or float("-inf"))
                if metric > best_val_ndcg:
                    best_val_ndcg = metric
                    best_ranker = ranker
                    best_params = candidate

            if best_ranker is None or best_params is None:
                raise RuntimeError("Hyperparameter search produced no viable ranker")

            val_ndcg_selected: float | None = None
            if x_val_np is not None and val_group_sizes:
                try:
                    val_pred_sel = [float(v) for v in best_ranker.predict(x_val_np)]
                    val_ndcg_selected = _mean_ndcg_by_group(y_val, val_pred_sel, val_group_sizes)
                except Exception:
                    val_ndcg_selected = None

            # --- Retrain winner on ALL data ---
            final_ranker = XGBRanker(**best_params)
            final_ranker.fit(
                np.asarray(x, dtype=float),
                np.asarray(y, dtype=float),
                group=group_sizes,
                verbose=False,
            )

            full_pred = [float(v) for v in final_ranker.predict(np.asarray(x, dtype=float))]
            full_ndcg = _mean_ndcg_by_group(y, full_pred, group_sizes)

            params = {k: v for k, v in best_params.items() if k != "monotone_constraints"}
            params["monotone_constraints"] = "enabled"
            metrics["train_ndcg_mean"] = full_ndcg
            has_val = len(y_val) > 0
            metrics["validation_has_holdout"] = has_val
            metrics["validation_groups"] = len(val_group_sizes)
            metrics["validation_rows"] = len(y_val)
            metrics["validation_ndcg_mean"] = (
                round(val_ndcg_selected, 4) if val_ndcg_selected is not None else None
            )
            if metrics["validation_ndcg_mean"] is None and best_val_ndcg > float("-inf"):
                metrics["hyperparam_selection_train_ndcg"] = round(best_val_ndcg, 4)
            metrics["search_results"] = search_results
            metrics["feature_importance_gain"] = _feature_importance(final_ranker)
            metrics["retrained_on_full_data"] = True

            # --- Quality gate ---
            gate_passed = True
            current_active = (
                db.query(ModeloProspeccao)
                .filter(ModeloProspeccao.ativo.is_(True))
                .order_by(ModeloProspeccao.treinado_em.desc())
                .first()
            )
            if current_active and current_active.metricas_json:
                try:
                    cur_metrics = json.loads(current_active.metricas_json)
                    cur_ndcg = cur_metrics.get("validation_ndcg_mean")
                    if (
                        cur_ndcg is not None
                        and metrics["validation_ndcg_mean"] is not None
                        and metrics["validation_ndcg_mean"] < cur_ndcg
                    ):
                        gate_passed = False
                        metrics["quality_gate"] = "blocked"
                        metrics["quality_gate_reason"] = (
                            f"val_ndcg {metrics['validation_ndcg_mean']:.4f} "
                            f"< active model {cur_ndcg:.4f}"
                        )
                        logger.warning(
                            "Quality gate blocked: new val NDCG %.4f < active %.4f",
                            metrics["validation_ndcg_mean"],
                            cur_ndcg,
                        )
                except (json.JSONDecodeError, TypeError):
                    pass

            if (
                gate_passed
                and metrics.get("validation_ndcg_mean") is not None
                and metrics["validation_ndcg_mean"] < MIN_ACTIVATION_NDCG
            ):
                gate_passed = False
                metrics["quality_gate"] = "blocked"
                metrics["quality_gate_reason"] = (
                    f"val_ndcg {metrics['validation_ndcg_mean']:.4f} below floor {MIN_ACTIVATION_NDCG}"
                )
                logger.warning("Quality gate: val NDCG %.4f below absolute floor", metrics["validation_ndcg_mean"])

            if gate_passed:
                metrics["quality_gate"] = "passed"

            should_activate = gate_passed

            # --- Persist artifact ---
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            artifact = MODEL_DIR / f"{model_version}.joblib"
            joblib.dump({"model": final_ranker, "features": FEATURE_NAMES}, artifact)
            artifact_path = str(artifact.relative_to(config.REPO_ROOT))
            algoritmo = "xgboost_ranker"

        except Exception as exc:
            if not allow_baseline:
                raise
            metrics["ranker_error"] = f"{exc!s} (interpreter: {sys.executable})"
            logger.exception("XGBRanker training failed; falling back to heuristic baseline")
    elif not allow_baseline:
        raise ValueError("Not enough labeled feature snapshots to train XGBRanker")

    model = ModeloProspeccao(
        versao=model_version,
        algoritmo=algoritmo,
        objetivo=objetivo,
        pipeline_version=pipeline_version,
        feature_schema_json=schema_json,
        hiperparametros_json=_json(params),
        metricas_json=_json(metrics),
        artefato_path=artifact_path,
        ativo=should_activate,
        treinado_em=datetime.utcnow(),
    )
    db.add(model)
    db.flush()
    if should_activate:
        _activate_model(db, model)

    result = model.to_dict()
    result["metrics"] = metrics
    return result
