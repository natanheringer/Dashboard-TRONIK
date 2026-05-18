"""Tests for jobs.prospeccao.publish_scores (global top-N vs listwise)."""

from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from banco_dados.modelos import (
    Base,
    FeatureSnapshotProspeccao,
    ModeloProspeccao,
    ScoreProspeccao,
)
from jobs.prospeccao.publish_scores import list_published_scores


def _empty_snapshots(db, model: ModeloProspeccao, qids: list[str]) -> list[FeatureSnapshotProspeccao]:
    snaps: list[FeatureSnapshotProspeccao] = []
    for q in qids:
        s = FeatureSnapshotProspeccao(
            empresa_id=None,
            local_id=None,
            pipeline_version=model.pipeline_version,
            qid=q,
            features_json="{}",
            feature_schema_json="[]",
        )
        db.add(s)
        snaps.append(s)
    db.flush()
    return snaps


def test_global_queue_orders_priority_before_score():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    model = ModeloProspeccao(
        versao="publish-test-a",
        algoritmo="xgboost_ranker",
        pipeline_version="pv-publish",
        feature_schema_json=json.dumps([]),
        ativo=True,
    )
    db.add(model)
    db.flush()

    snaps = _empty_snapshots(db, model, ["q:media", "q:alta"])
    db.add_all([
        ScoreProspeccao(
            snapshot_id=snaps[0].id,
            modelo_id=model.id,
            qid="q:media",
            score=0.99,
            ranking_contexto=1,
            prioridade="media",
            motivos_json="[]",
        ),
        ScoreProspeccao(
            snapshot_id=snaps[1].id,
            modelo_id=model.id,
            qid="q:alta",
            score=0.2,
            ranking_contexto=3,
            prioridade="alta",
            motivos_json="[]",
        ),
    ])
    db.commit()

    rows = list_published_scores(db, limite=1)
    assert len(rows) == 1
    assert rows[0]["prioridade"] == "alta"
    assert rows[0]["score"] == 0.2
    db.close()


def test_listwise_qid_orders_by_ranking_contexto():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    model = ModeloProspeccao(
        versao="publish-test-b",
        algoritmo="xgboost_ranker",
        pipeline_version="pv-publish",
        feature_schema_json=json.dumps([]),
        ativo=True,
    )
    db.add(model)
    db.flush()

    snaps = _empty_snapshots(db, model, ["ctx:x", "ctx:x"])
    db.add_all([
        ScoreProspeccao(
            snapshot_id=snaps[0].id,
            modelo_id=model.id,
            qid="ctx:x",
            score=0.95,
            ranking_contexto=2,
            prioridade="alta",
            motivos_json="[]",
        ),
        ScoreProspeccao(
            snapshot_id=snaps[1].id,
            modelo_id=model.id,
            qid="ctx:x",
            score=0.5,
            ranking_contexto=1,
            prioridade="alta",
            motivos_json="[]",
        ),
    ])
    db.commit()

    rows = list_published_scores(db, limite=10, qid="ctx:x")
    assert [r["ranking_contexto"] for r in rows] == [1, 2]
    db.close()
