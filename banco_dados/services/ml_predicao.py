"""Módulo 1 — Predição de Enchimento (Séries Temporais).

Prevê quando cada coletor atingirá nível crítico (90%).
Algoritmo SOTA: statsforecast AutoETS (leve, sem compilação C++).
Fallback: regressão linear na janela dos últimos 3 dias.

Executado via APScheduler 2x/dia.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from banco_dados.modelos import Coletor, LeituraSensor, PredicaoEnchimento
from banco_dados.utils import utc_now_naive

logger = logging.getLogger(__name__)

# Constantes
NIVEL_ALVO = 90.0          # prever quando atinge 90%
MIN_LEITURAS = 48          # mínimo ~12h de dados (a cada 15min)
MIN_DIAS_AUTOETS = 3       # mínimo para AutoETS
HORIZONTE_HORAS = 168      # prever até 7 dias à frente


def _regressao_linear(timestamps: np.ndarray, niveis: np.ndarray) -> Tuple[float, float]:
    """Regressão linear simples: nível = a*t + b.

    Args:
        timestamps: array de timestamps em horas (float) relativo ao primeiro
        niveis: array de níveis (0-100)

    Returns:
        (slope, intercept) — slope em %/hora
    """
    if len(timestamps) < 2:
        return 0.0, niveis[-1] if len(niveis) > 0 else 0.0

    # Polyfit grau 1
    coefs = np.polyfit(timestamps, niveis, deg=1)
    return float(coefs[0]), float(coefs[1])


def _predizer_linear(
    leituras: List[LeituraSensor],
    nivel_atual: float,
) -> Dict[str, Any]:
    """Predição via regressão linear (MVP, zero dependências extras)."""
    if len(leituras) < 2:
        return {'dados_suficientes': False}

    # Converter timestamps para horas relativas
    t0 = leituras[0].timestamp
    horas = np.array([(l.timestamp - t0).total_seconds() / 3600 for l in leituras])
    niveis = np.array([l.nivel for l in leituras])

    slope, intercept = _regressao_linear(horas, niveis)

    if slope <= 0:
        # Nível está caindo ou estável — não vai encher
        return {
            'dados_suficientes': True,
            'predicted_full_at': None,
            'horas_restantes': None,
            'velocidade_enchimento': float(slope),
            'modelo_usado': 'linear',
        }

    # Calcular quando atinge NIVEL_ALVO
    hora_atual = horas[-1]
    nivel_predito_agora = slope * hora_atual + intercept
    horas_para_alvo = (NIVEL_ALVO - nivel_predito_agora) / slope

    if horas_para_alvo < 0:
        horas_para_alvo = 0  # já passou do alvo

    agora = leituras[-1].timestamp
    predicted_full_at = agora + timedelta(hours=horas_para_alvo)

    # Intervalo de confiança simples (±20% do tempo)
    margem = max(horas_para_alvo * 0.2, 1.0)  # mínimo 1h de margem
    confianca_lower = agora + timedelta(hours=max(0, horas_para_alvo - margem))
    confianca_upper = agora + timedelta(hours=horas_para_alvo + margem)

    # Erro médio (MAE das últimas 12 leituras back-tested)
    if len(leituras) > 12:
        treino_h = horas[:-12]
        treino_n = niveis[:-12]
        teste_h = horas[-12:]
        teste_n = niveis[-12:]
        s, i = _regressao_linear(treino_h, treino_n)
        pred = s * teste_h + i
        mae = float(np.mean(np.abs(pred - teste_n)))
    else:
        mae = None

    return {
        'dados_suficientes': True,
        'predicted_full_at': predicted_full_at,
        'horas_restantes': round(horas_para_alvo, 1),
        'confianca_lower': confianca_lower,
        'confianca_upper': confianca_upper,
        'velocidade_enchimento': round(slope, 4),
        'modelo_usado': 'linear',
        'erro_medio': round(mae, 2) if mae is not None else None,
    }


def _predizer_autoets(
    leituras: List[LeituraSensor],
    nivel_atual: float,
) -> Dict[str, Any]:
    """Predição SOTA via statsforecast AutoETS."""
    try:
        import pandas as pd
        from statsforecast import StatsForecast
        from statsforecast.models import AutoETS
    except ImportError:
        logger.warning("statsforecast não instalado, usando fallback linear")
        return _predizer_linear(leituras, nivel_atual)

    if len(leituras) < MIN_LEITURAS:
        return _predizer_linear(leituras, nivel_atual)

    # Montar DataFrame no formato do statsforecast
    df = pd.DataFrame({
        'unique_id': ['coletor'] * len(leituras),
        'ds': [l.timestamp for l in leituras],
        'y': [l.nivel for l in leituras],
    })
    df = df.sort_values('ds').reset_index(drop=True)

    # Frequência: ~15min → 4 leituras/hora
    # Horizonte: prever até 7 dias (168h × 4 = 672 pontos)
    horizon = min(672, len(leituras))

    try:
        sf = StatsForecast(
            models=[AutoETS(season_length=96)],  # 96 = 24h × 4 leituras/hora
            freq='15min',
            n_jobs=1,
        )
        sf.fit(df)
        forecast = sf.predict(h=horizon)

        # Encontrar quando atinge NIVEL_ALVO
        forecast_vals = forecast['AutoETS'].values
        ultimo_ts = df['ds'].max()

        predicted_full_at = None
        horas_restantes = None

        for i, val in enumerate(forecast_vals):
            if val >= NIVEL_ALVO:
                delta_minutos = (i + 1) * 15
                predicted_full_at = ultimo_ts + timedelta(minutes=delta_minutos)
                horas_restantes = delta_minutos / 60
                break

        # Velocidade de enchimento (slope dos últimos 24h de forecast)
        if len(forecast_vals) >= 4:
            slope_15min = float(np.mean(np.diff(forecast_vals[:96])))
            velocidade = slope_15min * 4  # converter para %/hora
        else:
            velocidade = 0.0

        # Cross-validation para erro
        try:
            cv_results = sf.cross_validation(df, h=48, step_size=48, n_windows=2)
            mae = float(np.mean(np.abs(cv_results['AutoETS'] - cv_results['y'])))
        except Exception:
            mae = None

        # Confiança
        if horas_restantes is not None:
            margem = max(horas_restantes * 0.15, 0.5)
            confianca_lower = ultimo_ts + timedelta(hours=max(0, horas_restantes - margem))
            confianca_upper = ultimo_ts + timedelta(hours=horas_restantes + margem)
        else:
            confianca_lower = None
            confianca_upper = None

        return {
            'dados_suficientes': True,
            'predicted_full_at': predicted_full_at,
            'horas_restantes': round(horas_restantes, 1) if horas_restantes else None,
            'confianca_lower': confianca_lower,
            'confianca_upper': confianca_upper,
            'velocidade_enchimento': round(velocidade, 4),
            'modelo_usado': 'autoets',
            'erro_medio': round(mae, 2) if mae is not None else None,
        }

    except Exception as e:
        logger.warning(f"AutoETS falhou, usando fallback linear: {e}")
        return _predizer_linear(leituras, nivel_atual)


def predizer_enchimento_coletor(
    db: Session,
    coletor_id: int,
    usar_autoets: bool = True,
) -> Dict[str, Any]:
    """Prediz enchimento de um coletor específico.

    Args:
        db: sessão do SQLAlchemy
        coletor_id: ID do coletor
        usar_autoets: se True, tenta AutoETS primeiro

    Returns:
        dict com previsão (predicted_full_at, horas_restantes, etc.)
    """
    coletor = db.query(Coletor).filter(Coletor.id == coletor_id).first()
    if not coletor:
        return {'erro': f'Coletor {coletor_id} não encontrado'}

    # Buscar leituras dos últimos 14 dias (ordenadas por timestamp)
    data_limite = utc_now_naive() - timedelta(days=14)
    leituras = (
        db.query(LeituraSensor)
        .filter(
            LeituraSensor.coletor_id == coletor_id,
            LeituraSensor.timestamp >= data_limite,
        )
        .order_by(LeituraSensor.timestamp.asc())
        .all()
    )

    if len(leituras) < 2:
        return {
            'coletor_id': coletor_id,
            'dados_suficientes': False,
            'mensagem': f'Dados insuficientes: {len(leituras)} leituras (mínimo 2)',
            'minimo_dias': 1,
        }

    nivel_atual = float(coletor.nivel_preenchimento or 0)

    if usar_autoets and len(leituras) >= MIN_LEITURAS:
        resultado = _predizer_autoets(leituras, nivel_atual)
    else:
        resultado = _predizer_linear(leituras, nivel_atual)

    resultado['coletor_id'] = coletor_id
    resultado['nivel_atual'] = nivel_atual
    resultado['total_leituras'] = len(leituras)
    return resultado


def recalcular_predicoes_todos(db: Session) -> Dict[str, Any]:
    """Recalcula predições para todos os coletores ativos.

    Chamado pelo APScheduler 2x/dia.

    Returns:
        dict com estatísticas do processamento
    """
    stats = {'processados': 0, 'sucesso': 0, 'falha': 0, 'insuficientes': 0}

    coletores = db.query(Coletor).all()
    logger.info(f"🔄 Recalculando predições para {len(coletores)} coletores...")

    for coletor in coletores:
        stats['processados'] += 1

        try:
            resultado = predizer_enchimento_coletor(db, coletor.id)

            if not resultado.get('dados_suficientes', False):
                stats['insuficientes'] += 1
                # Salvar estado "insuficiente"
                pred = db.query(PredicaoEnchimento).filter(
                    PredicaoEnchimento.coletor_id == coletor.id
                ).first()
                if not pred:
                    pred = PredicaoEnchimento(coletor_id=coletor.id)
                    db.add(pred)
                pred.dados_suficientes = False
                pred.calculado_em = utc_now_naive()
                continue

            # Upsert predição
            pred = db.query(PredicaoEnchimento).filter(
                PredicaoEnchimento.coletor_id == coletor.id
            ).first()
            if not pred:
                pred = PredicaoEnchimento(coletor_id=coletor.id)
                db.add(pred)

            pred.predicted_full_at = resultado.get('predicted_full_at')
            pred.horas_restantes = resultado.get('horas_restantes')
            pred.confianca_lower = resultado.get('confianca_lower')
            pred.confianca_upper = resultado.get('confianca_upper')
            pred.velocidade_enchimento = resultado.get('velocidade_enchimento')
            pred.modelo_usado = resultado.get('modelo_usado')
            pred.erro_medio = resultado.get('erro_medio')
            pred.dados_suficientes = True
            pred.calculado_em = utc_now_naive()

            stats['sucesso'] += 1

        except Exception as e:
            logger.error(f"Erro ao predizer coletor {coletor.id}: {e}")
            stats['falha'] += 1

    db.commit()
    logger.info(
        f"✅ Predições concluídas: {stats['sucesso']} ok, "
        f"{stats['insuficientes']} insuficientes, {stats['falha']} falhas"
    )
    return stats


def obter_serie_historica(
    db: Session, coletor_id: int, dias: int = 7
) -> List[Dict[str, Any]]:
    """Retorna série histórica de leituras para visualização.

    Args:
        db: sessão SQLAlchemy
        coletor_id: ID do coletor
        dias: quantos dias de histórico

    Returns:
        lista de dicts com {timestamp, nivel, bateria}
    """
    data_limite = utc_now_naive() - timedelta(days=dias)
    leituras = (
        db.query(LeituraSensor)
        .filter(
            LeituraSensor.coletor_id == coletor_id,
            LeituraSensor.timestamp >= data_limite,
        )
        .order_by(LeituraSensor.timestamp.asc())
        .all()
    )
    return [l.to_dict() for l in leituras]
