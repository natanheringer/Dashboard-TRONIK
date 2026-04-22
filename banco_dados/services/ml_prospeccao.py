"""Módulo 4 — Prospecção Geográfica Inteligente.

Identifica potenciais clientes e locais ideais para novos coletores
cruzando dados públicos (CNPJ, OSM, IBGE) com dados internos da TRONIK.

Scoring: Fase 1 heurística → Fase 2 MLP (MLPClassifier do scikit-learn).
Visualização: heatmap + marcadores no mapa Leaflet existente.
"""

from __future__ import annotations

import json
import logging
import os
from math import radians, sin, cos, sqrt, atan2
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from banco_dados.modelos import Coletor, LocalProspeccao, Parceiro
from banco_dados.utils import utc_now_naive

logger = logging.getLogger(__name__)

# Coordenadas da sede TRONIK
SEDE_LAT = float(os.getenv('TRONIK_SEDE_LAT', '-15.7942'))
SEDE_LNG = float(os.getenv('TRONIK_SEDE_LNG', '-47.8822'))

# Scores base por tipo de CNAE (quanto maior, mais relevante para e-waste)
CNAE_SCORES = {
    '4713-0': 10.0,   # Shopping centers / lojas departamento
    '6822-6': 8.0,    # Gestão de condomínios e shoppings
    '8532-5': 7.0,    # Universidades
    '8411-6': 7.0,    # Administração pública (órgãos com TI)
    '6201-5': 9.0,    # Empresas de TI / software
    '6202-3': 9.0,    # Consultoria em TI
    '4751-2': 8.0,    # Comércio de computadores e periféricos
    '4752-1': 7.0,    # Comércio de eletrônicos
    '5611-2': 3.0,    # Restaurantes (proxy de fluxo)
    '8531-7': 6.0,    # Educação profissional
    '8550-3': 5.0,    # Atividades de apoio à educação
    '6462-0': 4.0,    # Holdings
    '7020-4': 5.0,    # Atividades de consultoria empresarial
    '8610-1': 5.0,    # Hospitais
}

# Score por categoria OSM
CATEGORIA_SCORES = {
    'shopping': 10.0,
    'condominio': 8.0,
    'universidade': 7.0,
    'hospital': 5.0,
    'escritorio': 6.0,
    'governo': 7.0,
    'escola': 4.0,
    'comercio_eletronico': 9.0,
}

# Mínimo de parceiros existentes para treinar MLP
MIN_PARCEIROS_MLP = 10


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula distância em km entre dois pontos."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _calcular_features(
    local: LocalProspeccao,
    coletores: List[Coletor],
) -> Dict[str, float]:
    """Calcula features geográficas para um local candidato."""
    features: Dict[str, float] = {}

    lat, lng = local.latitude, local.longitude

    # Distância da sede
    features['distancia_sede_km'] = haversine(SEDE_LAT, SEDE_LNG, lat, lng)

    # Distância ao coletor mais próximo e contagem no raio
    distancias = []
    for c in coletores:
        if c.latitude and c.longitude:
            d = haversine(lat, lng, float(c.latitude), float(c.longitude))
            distancias.append(d)

    features['distancia_coletor_proximo_km'] = min(distancias) if distancias else 999.0
    features['n_coletores_raio_5km'] = sum(1 for d in distancias if d <= 5.0)

    # Score do tipo de estabelecimento
    cnae_prefix = (local.cnae_principal or '')[:6]
    features['tipo_score'] = CNAE_SCORES.get(cnae_prefix, 3.0)

    # Fallback para categoria OSM
    if not cnae_prefix and local.categoria:
        features['tipo_score'] = CATEGORIA_SCORES.get(
            local.categoria.lower(), 3.0
        )

    return features


def _score_heuristica(features: Dict[str, float]) -> float:
    """Score de prospecção via heurística ponderada.

    Quanto maior, mais promissor o local para prospecção.
    """
    score = 0.0

    # GAP DE COBERTURA (30%) — mais longe de coletores existentes = mais oportunidade
    dist_coletor = features.get('distancia_coletor_proximo_km', 0)
    if dist_coletor >= 10:
        gap_score = 100.0
    elif dist_coletor >= 5:
        gap_score = 70.0
    elif dist_coletor >= 2:
        gap_score = 40.0
    else:
        gap_score = 10.0  # já tem coletor perto, menos urgente
    score += gap_score * 0.30

    # TIPO DE ESTABELECIMENTO (25%)
    tipo = features.get('tipo_score', 3.0)
    score += (tipo / 10.0) * 100 * 0.25

    # PROXIMIDADE DA SEDE (20%) — mais perto = mais viável
    dist_sede = features.get('distancia_sede_km', 50)
    prox_score = max(0, 100 - (dist_sede / 60) * 100)
    score += prox_score * 0.20

    # DENSIDADE LOCAL (15%) — mais coletores no raio = zona com demanda comprovada
    n_coletores = features.get('n_coletores_raio_5km', 0)
    density_score = min(100, n_coletores * 25)  # 4+ coletores = 100
    score += density_score * 0.15

    # POPULAÇÃO/RENDA (10%)
    pop = features.get('populacao_setor', 0)
    renda = features.get('renda_media_setor', 0)
    pop_score = min(100, (pop / 5000) * 50 + (renda / 5000) * 50) if pop or renda else 50
    score += pop_score * 0.10

    return round(max(0, min(100, score)), 1)


def _score_mlp(
    features: Dict[str, float],
    model_path: str = 'banco_dados/ml_models/prospeccao_mlp.pkl',
) -> Optional[float]:
    """Score via MLP (Fase 2). Retorna None se modelo não existir."""
    try:
        import joblib
        import numpy as np

        scaler, model = joblib.load(model_path)
        X = np.array([[
            features.get('distancia_sede_km', 50),
            features.get('distancia_coletor_proximo_km', 50),
            features.get('n_coletores_raio_5km', 0),
            features.get('tipo_score', 3),
            features.get('populacao_setor', 0),
            features.get('renda_media_setor', 0),
            features.get('n_empresas_proximas', 0),
        ]])
        X_scaled = scaler.transform(X)
        prob = float(model.predict_proba(X_scaled)[:, 1][0])
        return round(prob * 100, 1)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning(f"Erro no MLP de prospecção: {e}")
        return None


def recalcular_scores_prospeccao(db: Session) -> Dict[str, Any]:
    """Recalcula scores de prospecção para todos os locais.

    Chamado via APScheduler ou sob demanda.
    """
    stats = {'processados': 0, 'sucesso': 0, 'falha': 0}

    coletores = db.query(Coletor).filter(
        Coletor.latitude.isnot(None),
        Coletor.longitude.isnot(None),
    ).all()

    locais = db.query(LocalProspeccao).all()
    logger.info(f"🔄 Recalculando scores para {len(locais)} locais de prospecção...")

    for local in locais:
        stats['processados'] += 1
        try:
            features = _calcular_features(local, coletores)

            # Tentar MLP, fallback para heurística
            score = _score_mlp(features)
            modelo = 'mlp'
            if score is None:
                score = _score_heuristica(features)
                modelo = 'heuristica'

            # Atualizar registro
            local.distancia_sede_km = features.get('distancia_sede_km')
            local.distancia_coletor_proximo_km = features.get('distancia_coletor_proximo_km')
            local.n_coletores_raio_5km = features.get('n_coletores_raio_5km')
            local.tipo_score = features.get('tipo_score')
            local.score_prospeccao = score
            local.modelo_usado = modelo
            local.calculado_em = utc_now_naive()

            stats['sucesso'] += 1

        except Exception as e:
            logger.error(f"Erro ao processar local {local.id}: {e}")
            stats['falha'] += 1

    db.commit()
    logger.info(f"✅ Prospecção: {stats['sucesso']} ok, {stats['falha']} falhas")
    return stats


def obter_ranking_prospeccao(
    db: Session,
    limite: int = 100,
    score_minimo: float = 0,
    categoria: Optional[str] = None,
    excluir_contatados: bool = False,
) -> List[Dict[str, Any]]:
    """Retorna locais de prospecção ranqueados por score."""
    query = db.query(LocalProspeccao).filter(
        LocalProspeccao.score_prospeccao >= score_minimo
    )

    if categoria:
        query = query.filter(LocalProspeccao.categoria == categoria)
    if excluir_contatados:
        query = query.filter(LocalProspeccao.ja_contatado.is_(False))

    locais = (
        query
        .order_by(LocalProspeccao.score_prospeccao.desc())
        .limit(limite)
        .all()
    )

    return [l.to_dict() for l in locais]


def obter_heatmap_data(
    db: Session,
    score_minimo: float = 20,
) -> List[Dict[str, Any]]:
    """Retorna dados para heatmap Leaflet (lat, lng, intensidade)."""
    locais = (
        db.query(LocalProspeccao)
        .filter(LocalProspeccao.score_prospeccao >= score_minimo)
        .all()
    )

    return [
        {
            'lat': l.latitude,
            'lng': l.longitude,
            'intensidade': l.score_prospeccao / 100.0,  # 0-1 para heatmap
            'nome': l.nome,
            'score': l.score_prospeccao,
            'categoria': l.categoria,
        }
        for l in locais
    ]


def treinar_mlp_prospeccao(db: Session) -> Dict[str, Any]:
    """Treina MLP de prospecção usando parceiros existentes como positive labels.

    Chamado manualmente ou quando há dados suficientes.
    """
    try:
        import joblib
        import numpy as np
        from sklearn.neural_network import MLPClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_score
    except ImportError:
        return {'erro': 'scikit-learn não instalado'}

    # Parceiros existentes com coordenadas = positive samples
    parceiros_com_coords = (
        db.query(Parceiro)
        .join(Coletor, Coletor.parceiro_id == Parceiro.id)
        .filter(
            Coletor.latitude.isnot(None),
            Parceiro.ativo.is_(True),
        )
        .all()
    )

    if len(parceiros_com_coords) < MIN_PARCEIROS_MLP:
        return {
            'erro': f'Dados insuficientes: {len(parceiros_com_coords)} parceiros '
                    f'(mínimo {MIN_PARCEIROS_MLP})',
        }

    coletores = db.query(Coletor).filter(
        Coletor.latitude.isnot(None)
    ).all()

    # Montar dataset
    X_list, y_list = [], []

    # Positive: locais de parceiros existentes
    for parceiro in parceiros_com_coords:
        for coletor in coletores:
            if coletor.parceiro_id == parceiro.id and coletor.latitude:
                dummy = LocalProspeccao(
                    latitude=coletor.latitude,
                    longitude=coletor.longitude,
                    cnae_principal='',
                    categoria='parceiro',
                )
                features = _calcular_features(dummy, coletores)
                X_list.append([
                    features.get('distancia_sede_km', 50),
                    features.get('distancia_coletor_proximo_km', 50),
                    features.get('n_coletores_raio_5km', 0),
                    features.get('tipo_score', 3),
                    features.get('populacao_setor', 0),
                    features.get('renda_media_setor', 0),
                    features.get('n_empresas_proximas', 0),
                ])
                y_list.append(1)

    # Negative: locais de prospecção não convertidos
    nao_convertidos = (
        db.query(LocalProspeccao)
        .filter(LocalProspeccao.convertido.is_(False))
        .limit(len(y_list) * 3)  # oversample negatives
        .all()
    )

    for local in nao_convertidos:
        features = _calcular_features(local, coletores)
        X_list.append([
            features.get('distancia_sede_km', 50),
            features.get('distancia_coletor_proximo_km', 50),
            features.get('n_coletores_raio_5km', 0),
            features.get('tipo_score', 3),
            features.get('populacao_setor', 0),
            features.get('renda_media_setor', 0),
            features.get('n_empresas_proximas', 0),
        ])
        y_list.append(0)

    if len(set(y_list)) < 2:
        return {'erro': 'Dataset precisa de classes positivas e negativas'}

    X = np.array(X_list)
    y = np.array(y_list)

    # Treinar
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = MLPClassifier(
        hidden_layer_sizes=(64, 32),
        activation='relu',
        solver='adam',
        max_iter=500,
        random_state=42,
    )

    # Cross-validation
    scores = cross_val_score(model, X_scaled, y, cv=min(5, len(y) // 2), scoring='accuracy')
    accuracy = float(scores.mean())

    # Treinar modelo final
    model.fit(X_scaled, y)

    # Salvar
    os.makedirs('banco_dados/ml_models', exist_ok=True)
    model_path = 'banco_dados/ml_models/prospeccao_mlp.pkl'
    joblib.dump((scaler, model), model_path)

    logger.info(f"✅ MLP de prospecção treinado: accuracy={accuracy:.3f}")

    return {
        'sucesso': True,
        'accuracy': round(accuracy, 3),
        'n_positivos': sum(y),
        'n_negativos': len(y) - sum(y),
        'modelo_salvo': model_path,
    }
