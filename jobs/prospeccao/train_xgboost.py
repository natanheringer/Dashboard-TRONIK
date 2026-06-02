"""Train or bootstrap the REE prospection ranker.

v3+: geo-first listwise qids + quantile labels live in snapshots; training shards
oversized groups and guarantees enough multi-document qids for validation.

v2: group-aware validation, hyperparameter search, monotonic XGBRanker, quality gate.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import defaultdict
from datetime import UTC, datetime
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
EARLY_STOPPING_ROUNDS = 35


def _artifact_stem(model_version: str) -> str:
    """Filesystem-safe stem for joblib paths (no dirs / odd unicode)."""
    stem = "".join(
        c if (c.isalnum() or c in "._-") else "_"
        for c in (model_version or "").strip()
    ).strip("._-")
    return stem[:180] or "model"


def _xgb_major_version() -> tuple[int, int, int]:
    try:
        import xgboost as xgb

        parts: list[int] = []
        for token in xgb.__version__.split(".")[:3]:
            digits = "".join(ch for ch in token if ch.isdigit())
            parts.append(int(digits or "0"))
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)


def _create_xgb_ranker(
    candidate: dict[str, Any],
    *,
    early_stopping_rounds: int | None = None,
) -> tuple[Any, str | None]:
    """Return (ranker, early_stop_mode) where mode is ctor | fit_callback | fit_kwarg | None."""
    from xgboost import XGBRanker

    ctor = dict(candidate)
    if early_stopping_rounds is None:
        return XGBRanker(**ctor), None
    try:
        return XGBRanker(**ctor, early_stopping_rounds=early_stopping_rounds), "ctor"
    except TypeError:
        if _xgb_major_version() >= (2, 0, 0):
            return XGBRanker(**ctor), "fit_callback"
        return XGBRanker(**ctor), "fit_kwarg"


def _fit_xgb_ranker(
    ranker: Any,
    x: Any,
    y: Any,
    group: list[int],
    *,
    eval_set: list[tuple[Any, Any]] | None = None,
    eval_group: list[list[int]] | None = None,
    early_stopping_rounds: int | None = None,
    early_stop_mode: str | None = None,
) -> None:
    fit_kwargs: dict[str, Any] = {"group": group, "verbose": False}
    if eval_set:
        fit_kwargs["eval_set"] = eval_set
        fit_kwargs["eval_group"] = eval_group
    if early_stopping_rounds and eval_set and early_stop_mode != "ctor":
        if early_stop_mode == "fit_callback" or (
            early_stop_mode is None and _xgb_major_version() >= (2, 0, 0)
        ):
            from xgboost.callback import EarlyStopping

            fit_kwargs["callbacks"] = [
                EarlyStopping(rounds=early_stopping_rounds, save_best=True)
            ]
        else:
            fit_kwargs["early_stopping_rounds"] = early_stopping_rounds
    ranker.fit(x, y, **fit_kwargs)


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
        .filter(FeatureSnapshotProspeccao.qid != "unlocated")
        .filter(FeatureSnapshotProspeccao.qid != "df")
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


def _ndcg_at_k(y_true: list[int], y_score: list[float], group_sizes: list[int], k: int) -> float | None:
    """Compute mean NDCG@K across groups; skip groups with size < 2."""
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
        scores.append(float(ndcg_score(yt, ys, k=min(k, size))))
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
    """Hold out entire qid groups so validation measures cross-group generalization.

    Uses temporal split based on snapshot ID (proxy for creation time):
    - Sort qids by max snapshot ID in each group (most recent)
    - Hold out last ~20% (chronologically most recent) for validation
    - Use earlier 80% for training
    This prevents data leakage when snapshots are ordered chronologically.
    """
    qids = [qid for qid, items in grouped.items() if len(items) >= 2]
    if len(qids) < 2:
        return grouped, {}

    # Sort qids by max ID in each group (proxy for temporal order)
    qids_sorted = sorted(qids, key=lambda qid: max(item.id for item in grouped[qid]))

    holdout_count = max(1, int(round(len(qids_sorted) * validation_ratio)))
    holdout = set(qids_sorted[-holdout_count:])  # Hold out most recent qids

    # ASSERTION: warn if validation set is suspiciously small (< 5 qids)
    if len(holdout) < 5:
        logger.warning(
            "_stratified_qid_split: validation set has only %d qids (< 5) — "
            "may not represent cross-group generalization well",
            len(holdout)
        )

    train_grouped: dict[str, list[FeatureSnapshotProspeccao]] = {}
    val_grouped: dict[str, list[FeatureSnapshotProspeccao]] = {}
    for qid, items in grouped.items():
        if qid in holdout:
            val_grouped[qid] = items
        else:
            train_grouped[qid] = items
    if not val_grouped:
        return grouped, {}

    logger.info("Temporal split: %d train qids, %d val qids", len(train_grouped), len(val_grouped))
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
        {**base, "n_estimators": 200, "max_depth": 4, "learning_rate": 0.10,
         "subsample": 0.80, "colsample_bytree": 0.70, "min_child_weight": 5,
         "reg_lambda": 1.0, "reg_alpha": 0.0},
        {**base, "n_estimators": 240, "max_depth": 4, "learning_rate": 0.05,
         "subsample": 0.85, "colsample_bytree": 0.80, "min_child_weight": 10,
         "reg_lambda": 1.5, "reg_alpha": 0.1},
        {**base, "n_estimators": 280, "max_depth": 6, "learning_rate": 0.10,
         "subsample": 0.80, "colsample_bytree": 0.70, "min_child_weight": 5,
         "reg_lambda": 1.0, "reg_alpha": 0.0},
        {**base, "n_estimators": 320, "max_depth": 6, "learning_rate": 0.05,
         "subsample": 0.85, "colsample_bytree": 0.80, "min_child_weight": 10,
         "reg_lambda": 2.0, "reg_alpha": 0.2},
        {**base, "n_estimators": 360, "max_depth": 8, "learning_rate": 0.20,
         "subsample": 1.00, "colsample_bytree": 1.00, "min_child_weight": 5,
         "reg_lambda": 1.0, "reg_alpha": 0.0},
        {**base, "n_estimators": 400, "max_depth": 8, "learning_rate": 0.05,
         "subsample": 0.80, "colsample_bytree": 0.70, "min_child_weight": 20,
         "reg_lambda": 2.0, "reg_alpha": 0.1},
        {**base, "tree_method": "hist", "n_estimators": 480, "max_depth": 6, "learning_rate": 0.08,
         "subsample": 0.88, "colsample_bytree": 0.82, "min_child_weight": 10,
         "reg_lambda": 1.5, "reg_alpha": 0.05},
        {**base, "tree_method": "hist", "n_estimators": 520, "max_depth": 8, "learning_rate": 0.05,
         "subsample": 0.80, "colsample_bytree": 0.70, "min_child_weight": 15,
         "reg_lambda": 2.5, "reg_alpha": 0.15},
    ]


def _feature_importance(ranker: Any) -> dict[str, dict[str, float]]:
    """Extract feature importance (gain, weight, cover) for all features with names."""
    try:
        result: dict[str, dict[str, float]] = {}
        for importance_type in ["gain", "weight", "cover"]:
            try:
                importance = ranker.get_booster().get_score(importance_type=importance_type)
                type_scores: dict[str, float] = {}
                for key, val in importance.items():
                    idx = int(key.replace("f", ""))
                    if idx < len(FEATURE_NAMES):
                        type_scores[FEATURE_NAMES[idx]] = round(float(val), 4)
                result[importance_type] = type_scores
            except Exception:
                result[importance_type] = {}
        return result
    except Exception:
        return {"gain": {}, "weight": {}, "cover": {}}


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
    model_version = model_version or f"{pipeline_version}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    schema_json = rows[0].feature_schema_json if rows else _json(
        [{"name": name, "type": "float", "version": pipeline_version} for name in FEATURE_NAMES]
    )

    metrics: dict[str, Any] = {}
    grouped = _group_rows(rows)
    metrics["groups_raw_snapshot_qid"] = len(grouped)
    grouped = _shard_oversized_groups(grouped)
    grouped = _ensure_multi_item_qids(grouped)
    metrics["groups_after_ltr_preprocess"] = len(grouped)

    # --- Pre-training quality gate: check QID diversity and label monolith ---
    multi_qids = [q for q, items in grouped.items() if len(items) >= 2]
    total_snaps = sum(len(v) for v in grouped.values())
    largest_frac = max(len(v) for v in grouped.values()) / max(total_snaps, 1) if grouped else 0.0

    if len(multi_qids) < 8:
        raise ValueError(
            f"Pre-training abort: only {len(multi_qids)} QIDs with size >= 2 "
            f"(min 8 required for listwise ranking). Insufficient QID diversity."
        )

    if largest_frac > 0.50:
        raise ValueError(
            f"Pre-training abort: largest QID is {largest_frac:.1%} of training set "
            f"(max 50% allowed). Risk of label collapse."
        )

    logger.info(
        "pre-train quality gate OK: %d multi-qids, largest QID %.1f%% of training set",
        len(multi_qids), largest_frac * 100,
    )

    x, y, group_sizes = _matrix(grouped)
    metrics.update(
        {
            "rows": len(rows),
            "groups": len(group_sizes),
            "label_distribution": {str(label): y.count(label) for label in sorted(set(y))},
        }
    )

    # --- Pre-training diagnostic log ---
    logger.info(
        "Training data: %d snapshots, %d qids (%d multi-item), "
        "excluded: unlocated+df",
        len(rows), len(grouped), len(multi_qids),
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

            # --- qid-aware train / validation split ---
            train_grouped, val_grouped = _stratified_qid_split(grouped)
            x_train, y_train, train_group_sizes = _matrix(train_grouped)
            x_val, y_val, val_group_sizes = _matrix(val_grouped)

            # --- Filter singleton groups from training (listwise ranking requires size >= 2) ---
            valid_mask = np.array(
                [size >= 2 for size in train_group_sizes for _ in range(size)]
            )
            x_train_filtered = [x_train[i] for i in range(len(x_train)) if valid_mask[i]]
            y_train_filtered = [y_train[i] for i in range(len(y_train)) if valid_mask[i]]
            train_group_sizes_filtered = [s for s in train_group_sizes if s >= 2]

            x_train_np = np.asarray(x_train_filtered, dtype=float)
            y_train_np = np.asarray(y_train_filtered, dtype=float)
            x_val_np = np.asarray(x_val, dtype=float) if x_val else None

            # --- Hyperparameter search ---
            best_ranker = None
            best_params: dict[str, Any] | None = None
            best_val_ndcg = float("-inf")
            search_results: list[dict[str, Any]] = []

            for candidate in _ranker_param_candidates():
                has_eval = x_val_np is not None and val_group_sizes
                es_rounds = EARLY_STOPPING_ROUNDS if has_eval else None
                ranker, es_mode = _create_xgb_ranker(
                    candidate, early_stopping_rounds=es_rounds
                )
                eval_set = None
                eval_group = None
                if has_eval:
                    eval_set = [
                        (x_train_np, y_train_np),
                        (x_val_np, np.asarray(y_val, dtype=float)),
                    ]
                    eval_group = [train_group_sizes_filtered, val_group_sizes]
                _fit_xgb_ranker(
                    ranker,
                    x_train_np,
                    y_train_np,
                    train_group_sizes_filtered,
                    eval_set=eval_set,
                    eval_group=eval_group,
                    early_stopping_rounds=es_rounds,
                    early_stop_mode=es_mode,
                )

                train_pred = [float(v) for v in ranker.predict(x_train_np)]
                train_ndcg = _mean_ndcg_by_group(y_train_filtered, train_pred, train_group_sizes_filtered)
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

            # --- Retrain winner on ALL data: tree count from CV winner only (no eval on val). ---
            final_params = dict(best_params)
            bi = getattr(best_ranker, "best_iteration", None)
            if bi is not None:
                final_params["n_estimators"] = int(bi) + 1
            final_ranker, _final_es_mode = _create_xgb_ranker(
                final_params, early_stopping_rounds=None
            )
            _fit_xgb_ranker(
                final_ranker,
                np.asarray(x, dtype=float),
                np.asarray(y, dtype=float),
                group_sizes,
                eval_set=None,
                eval_group=None,
                early_stopping_rounds=None,
                early_stop_mode=None,
            )

            full_pred = [float(v) for v in final_ranker.predict(np.asarray(x, dtype=float))]
            full_ndcg = _mean_ndcg_by_group(y, full_pred, group_sizes)

            params = {k: v for k, v in best_params.items() if k != "monotone_constraints"}
            params["monotone_constraints"] = "enabled"
            metrics["train_ndcg_mean"] = full_ndcg

            # --- NDCG@K for multiple K values ---
            for k_val in [1, 5, 10, 20]:
                ndcg_k = _ndcg_at_k(y, full_pred, group_sizes, k_val)
                metrics[f"train_ndcg@{k_val}"] = ndcg_k

            has_val = len(y_val) > 0
            metrics["validation_has_holdout"] = has_val
            metrics["validation_groups"] = len(val_group_sizes)
            metrics["validation_rows"] = len(y_val)
            metrics["validation_ndcg_mean"] = (
                round(val_ndcg_selected, 4) if val_ndcg_selected is not None else None
            )
            if has_val and x_val_np is not None:
                val_pred_for_k = [float(v) for v in final_ranker.predict(x_val_np)]
                for k_val in [1, 5, 10, 20]:
                    val_ndcg_k = _ndcg_at_k(y_val, val_pred_for_k, val_group_sizes, k_val)
                    metrics[f"validation_ndcg@{k_val}"] = val_ndcg_k

            if metrics["validation_ndcg_mean"] is None and best_val_ndcg > float("-inf"):
                metrics["hyperparam_selection_train_ndcg"] = round(best_val_ndcg, 4)
            metrics["search_results"] = search_results
            metrics["feature_importance"] = _feature_importance(final_ranker)
            metrics["retrained_on_full_data"] = True
            metrics["final_fit_val_eval"] = False

            # --- Extract learning curve from evals_result_ if available ---
            try:
                if hasattr(final_ranker, "evals_result_") and final_ranker.evals_result_:
                    learning_curve: dict[str, list[float]] = {}
                    for eval_name, eval_results in final_ranker.evals_result_.items():
                        learning_curve[eval_name] = [round(v, 6) for v in eval_results]
                    metrics["learning_curve"] = learning_curve
            except Exception:
                pass

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

            # --- Persist artifact with feature importance ---
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            artifact = MODEL_DIR / f"{_artifact_stem(model_version)}.joblib"
            feature_importance_data = _feature_importance(final_ranker)
            artifact_data = {
                "model": final_ranker,
                "features": FEATURE_NAMES,
                "feature_importance": feature_importance_data,
            }
            joblib.dump(artifact_data, artifact)
            artifact_path = str(artifact.relative_to(config.REPO_ROOT))
            algoritmo = "xgboost_ranker"

        except Exception as exc:
            metrics["ranker_error"] = f"{exc!s} (interpreter: {sys.executable})"
            logger.exception("XGBRanker training failed")
            if not allow_baseline:
                raise
            logger.warning("Falling back to heuristic baseline after ranker failure")
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
        treinado_em=datetime.now(UTC),
    )
    db.add(model)
    db.flush()
    if should_activate:
        _activate_model(db, model)

    result = model.to_dict()
    result["metrics"] = metrics
    return result
