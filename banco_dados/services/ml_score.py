"""Módulo 2 — TRONIK Score (Classificação de Prioridade).

Score 0-100 por coletor: urgência × viabilidade × valor.
Fase 1 (MVP): heurística ponderada com domain expertise.
Fase 2: XGBoost automático quando count(coletas) >= 200.

Executado via APScheduler 1x/dia.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from math import atan2, cos, radians, sin, sqrt
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from banco_dados.modelos import (
    Coleta,
    Coletor,
    PredicaoEnchimento,
    TronikScore,
)
from banco_dados.utils import utc_now_naive

logger = logging.getLogger(__name__)

# Pesos da heurística (configuráveis via env)
PESOS_DEFAULT = {
    'nivel': 0.25,
    'velocidade': 0.20,
    'proximidade_sede': 0.20,
    'dias_sem_coleta': 0.15,
    'lucro_medio': 0.10,
    'cluster_bonus': 0.10,
}

# Coordenadas da sede TRONIK (env var ou fallback Brasília)
SEDE_LAT = float(os.getenv('TRONIK_SEDE_LAT', '-15.7942'))
SEDE_LNG = float(os.getenv('TRONIK_SEDE_LNG', '-47.8822'))

# Limiar mínimo de coletas para usar XGBoost
MIN_COLETAS_XGBOOST = 200

# Ordem explícita de features para XGBoost (schema verificável)
_XGBOOST_FEATURE_NAMES = [
    "nivel",
    "velocidade",
    "km_sede",
    "dias_sem_coleta",
    "lucro_medio",
    "coletores_proximos",
]


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula distância em km entre dois pontos (haversine)."""
    R = 6371.0  # raio da Terra em km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _normalizar_0_100(valor: float, minimo: float, maximo: float) -> float:
    """Normaliza valor para escala 0-100."""
    if maximo <= minimo:
        return 50.0
    return max(0.0, min(100.0, (valor - minimo) / (maximo - minimo) * 100))


def _extrair_features(
    db: Session,
    coletor: Coletor,
    todos_coletores: list[Coletor],
) -> dict[str, float]:
    """Extrai features para scoring de um coletor.

    Features:
    1. nivel_preenchimento (0-100)
    2. velocidade_enchimento (%/hora, do Módulo 1)
    3. km_da_sede (distância haversine)
    4. dias_sem_coleta (diff entre agora e última coleta)
    5. lucro_medio_por_kg (média histórica do parceiro)
    6. coletores_proximos_acima_60 (cluster bonus)
    """
    agora = utc_now_naive()
    features: dict[str, float] = {}

    # 1. Nível de preenchimento
    features['nivel'] = float(coletor.nivel_preenchimento or 0)

    # 2. Velocidade de enchimento (do Módulo 1)
    pred = db.query(PredicaoEnchimento).filter(
        PredicaoEnchimento.coletor_id == coletor.id
    ).first()
    features['velocidade'] = float(pred.velocidade_enchimento or 0) if pred else 0.0

    # 3. Distância da sede (km)
    if coletor.latitude and coletor.longitude:
        features['km_sede'] = haversine(
            SEDE_LAT, SEDE_LNG,
            float(coletor.latitude), float(coletor.longitude)
        )
    else:
        features['km_sede'] = 50.0  # fallback conservador

    # 4. Dias sem coleta
    if coletor.ultima_coleta:
        features['dias_sem_coleta'] = (agora - coletor.ultima_coleta).total_seconds() / 86400
    else:
        features['dias_sem_coleta'] = 30.0  # assume muito tempo

    # 5. Lucro médio por kg (do parceiro)
    lucro_medio = (
        db.query(func.avg(Coleta.lucro_por_kg))
        .filter(
            Coleta.coletor_id == coletor.id,
            Coleta.lucro_por_kg.isnot(None),
        )
        .scalar()
    )
    features['lucro_medio'] = float(lucro_medio) if lucro_medio else 2.0  # fallback R$2/kg

    # 6. Cluster bonus: coletores próximos acima de 60%
    count_proximos = 0
    if coletor.latitude and coletor.longitude:
        for outro in todos_coletores:
            if outro.id == coletor.id:
                continue
            if outro.latitude and outro.longitude:
                dist = haversine(
                    float(coletor.latitude), float(coletor.longitude),
                    float(outro.latitude), float(outro.longitude),
                )
                if dist <= 5.0 and float(outro.nivel_preenchimento or 0) >= 60:
                    count_proximos += 1
    features['coletores_proximos'] = count_proximos

    return features


def _score_heuristica(features: dict[str, float]) -> float:
    """Calcula TRONIK Score via heurística ponderada.

    Score = soma ponderada de features normalizadas.
    Quanto maior, mais prioritário para coleta.
    """
    pesos = PESOS_DEFAULT.copy()

    # Ler pesos customizados (se existirem como env var)
    pesos_env = os.getenv('TRONIK_SCORE_PESOS')
    if pesos_env:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            pesos.update(json.loads(pesos_env))

    scores_parciais = {}

    # Nível: mais cheio = mais urgente
    scores_parciais['nivel'] = features['nivel']

    # Velocidade: enchendo mais rápido = mais urgente
    # Normalizar: 0-2 %/hora é o range esperado
    scores_parciais['velocidade'] = _normalizar_0_100(features['velocidade'], 0, 2.0)

    # Proximidade da sede: mais perto = mais viável (inverso do km)
    # Score = 100 se km=0, score = 0 se km >= 60
    scores_parciais['proximidade_sede'] = max(0, 100 - (features['km_sede'] / 60) * 100)

    # Dias sem coleta: mais dias = mais urgente
    # Normalizar: 0-30 dias
    scores_parciais['dias_sem_coleta'] = _normalizar_0_100(
        features['dias_sem_coleta'], 0, 30
    )

    # Lucro médio: mais lucrativo = mais valioso
    # Normalizar: R$0-10/kg
    scores_parciais['lucro_medio'] = _normalizar_0_100(features['lucro_medio'], 0, 10)

    # Cluster bonus: mais coletores próximos cheios = vale mais coletar na região
    # Normalizar: 0-5 coletores
    scores_parciais['cluster_bonus'] = _normalizar_0_100(
        features['coletores_proximos'], 0, 5
    )

    # Score final ponderado
    score = sum(
        scores_parciais.get(k, 0) * pesos.get(k, 0)
        for k in pesos
    )

    return round(max(0, min(100, score)), 1)


def _score_xgboost(
    features: dict[str, float],
    model_path: str = 'banco_dados/ml_models/score_model.pkl',
) -> float | None:
    """Calcula TRONIK Score via XGBoost (Fase 2).

    Retorna None se modelo não existir ou falhar.
    """
    try:
        import joblib
        import numpy as np

        model = joblib.load(model_path)
        # Build feature array using explicit schema (raises KeyError if feature missing)
        X = np.array([[features[f] for f in _XGBOOST_FEATURE_NAMES]])
        score = float(model.predict(X)[0])
        return round(max(0, min(100, score)), 1)

    except FileNotFoundError:
        logger.debug("Modelo XGBoost não encontrado, usando heurística")
        return None
    except Exception as e:
        logger.warning(f"Erro no XGBoost: {e}, usando heurística")
        return None


def calcular_score_coletor(
    db: Session,
    coletor: Coletor,
    todos_coletores: list[Coletor],
) -> dict[str, Any]:
    """Calcula TRONIK Score para um coletor."""
    features = _extrair_features(db, coletor, todos_coletores)

    # Tentar XGBoost se houver dados suficientes
    total_coletas = db.query(func.count(Coleta.id)).scalar() or 0
    modelo_usado = 'heuristica'
    score = None

    if total_coletas >= MIN_COLETAS_XGBOOST:
        score = _score_xgboost(features)
        if score is not None:
            modelo_usado = 'xgboost'

    if score is None:
        score = _score_heuristica(features)
        modelo_usado = 'heuristica'

    return {
        'coletor_id': coletor.id,
        'score': score,
        'features': features,
        'modelo_usado': modelo_usado,
    }


def recalcular_scores_todos(db: Session) -> dict[str, Any]:
    """Recalcula TRONIK Score para todos os coletores.

    Chamado pelo APScheduler 1x/dia.

    Returns:
        dict com estatísticas
    """
    stats = {'processados': 0, 'sucesso': 0, 'falha': 0}

    coletores = db.query(Coletor).all()
    logger.info(f"🔄 Recalculando TRONIK Score para {len(coletores)} coletores...")

    for coletor in coletores:
        stats['processados'] += 1
        try:
            resultado = calcular_score_coletor(db, coletor, coletores)

            # Upsert
            ts = db.query(TronikScore).filter(
                TronikScore.coletor_id == coletor.id
            ).first()
            if not ts:
                ts = TronikScore(coletor_id=coletor.id)
                db.add(ts)

            ts.score = resultado['score']
            ts.features_json = json.dumps(resultado['features'], default=str)
            ts.modelo_usado = resultado['modelo_usado']
            ts.calculado_em = utc_now_naive()

            stats['sucesso'] += 1

        except Exception as e:
            logger.error(f"Erro ao calcular score coletor {coletor.id}: {e}")
            stats['falha'] += 1

    db.commit()
    logger.info(
        f"✅ Scores concluídos: {stats['sucesso']} ok, {stats['falha']} falhas"
    )
    return stats


def obter_ranking(db: Session, limite: int = 50) -> list[dict[str, Any]]:
    """Retorna coletores ordenados por TRONIK Score (desc).

    Returns:
        lista de dicts com coletor + score + features
    """
    scores = (
        db.query(TronikScore)
        .options(joinedload(TronikScore.coletor).joinedload(Coletor.parceiro))
        .order_by(TronikScore.score.desc())
        .limit(limite)
        .all()
    )

    ranking = []
    for i, ts in enumerate(scores, 1):
        coletor = ts.coletor
        if not coletor:
            continue
        ranking.append({
            'rank': i,
            'coletor_id': ts.coletor_id,
            'nome': coletor.localizacao,
            'parceiro': coletor.parceiro.nome if coletor.parceiro else '—',
            'nivel': float(coletor.nivel_preenchimento or 0),
            'score': ts.score,
            'modelo_usado': ts.modelo_usado,
            'features': json.loads(ts.features_json) if ts.features_json else {},
            'calculado_em': ts.calculado_em.isoformat() if ts.calculado_em else None,
        })

    return ranking
