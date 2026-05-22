"""Blueprint de endpoints ML — Dashboard-TRONIK.

Endpoints para os módulos de Machine Learning:
- Módulo 1: Predição de enchimento (séries temporais)
- Módulo 2: TRONIK Score (classificação de prioridade)
- Módulo 3: Narrativa de impacto (NLP generativo)
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required

from rotas.api.decorators import get_db

logger = logging.getLogger(__name__)

ml_bp = Blueprint("ml", __name__, url_prefix="/ml")


# ==============================================================
# MÓDULO 1 — PREDIÇÃO DE ENCHIMENTO
# ==============================================================

@ml_bp.route("/predicao/<int:coletor_id>", methods=["GET"])
@login_required
def predicao_coletor(coletor_id: int):
    """Retorna previsão de enchimento + série histórica de um coletor.

    GET /api/ml/predicao/<coletor_id>
    Query params:
      - dias_historico: int (default 7) — dias de série para retornar
    """
    from banco_dados.services.ml_predicao import (
        obter_serie_historica,
        predizer_enchimento_coletor,
    )

    db = get_db()
    try:
        resultado = predizer_enchimento_coletor(db, coletor_id)

        dias = request.args.get("dias_historico", 7, type=int)
        serie = obter_serie_historica(db, coletor_id, dias=dias)

        return jsonify({
            "ok": True,
            "dados": {
                "predicao": resultado,
                "serie_historica": serie,
            },
            "erros": [],
        })
    except Exception as e:
        logger.error(f"Erro na predição do coletor {coletor_id}: {e}", exc_info=True)
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "ERRO_ML", "mensagem": "Erro interno do servidor"}],
        }), 500
    finally:
        db.close()


@ml_bp.route("/predicao/recalcular", methods=["POST"])
@login_required
def recalcular_predicoes():
    """Força recálculo de predições para todos os coletores.

    POST /api/ml/predicao/recalcular
    """
    from banco_dados.services.ml_predicao import recalcular_predicoes_todos

    db = get_db()
    try:
        stats = recalcular_predicoes_todos(db)
        return jsonify({"ok": True, "dados": stats, "erros": []})
    except Exception as e:
        logger.error(f"Erro ao recalcular predições: {e}", exc_info=True)
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "ERRO_ML", "mensagem": "Erro interno do servidor"}],
        }), 500
    finally:
        db.close()


# ==============================================================
# MÓDULO 2 — TRONIK SCORE
# ==============================================================

@ml_bp.route("/ranking", methods=["GET"])
@login_required
def ranking_coletores():
    """Retorna coletores ordenados por TRONIK Score.

    GET /api/ml/ranking
    Query params:
      - limite: int (default 50)
    """
    from banco_dados.services.ml_score import obter_ranking

    db = get_db()
    try:
        limite = request.args.get("limite", 50, type=int)
        ranking = obter_ranking(db, limite=limite)
        return jsonify({"ok": True, "dados": ranking, "erros": []})
    except Exception as e:
        logger.error(f"Erro ao obter ranking: {e}", exc_info=True)
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "ERRO_ML", "mensagem": "Erro interno do servidor"}],
        }), 500
    finally:
        db.close()


@ml_bp.route("/score/recalcular", methods=["POST"])
@login_required
def recalcular_scores():
    """Força recálculo de TRONIK Score para todos os coletores.

    POST /api/ml/score/recalcular
    """
    from banco_dados.services.ml_score import recalcular_scores_todos

    db = get_db()
    try:
        stats = recalcular_scores_todos(db)
        return jsonify({"ok": True, "dados": stats, "erros": []})
    except Exception as e:
        logger.error(f"Erro ao recalcular scores: {e}", exc_info=True)
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "ERRO_ML", "mensagem": "Erro interno do servidor"}],
        }), 500
    finally:
        db.close()


# ==============================================================
# MÓDULO 3 — NARRATIVA NLP
# ==============================================================

@ml_bp.route("/narrativa/<int:parceiro_id>", methods=["GET"])
@login_required
def narrativa_parceiro(parceiro_id: int):
    """Retorna narrativa de impacto do parceiro.

    GET /api/ml/narrativa/<parceiro_id>
    Query params:
      - inicio: str ISO date (default: 30 dias atrás)
      - fim: str ISO date (default: hoje)
      - forcar: bool (default false) — ignora cache
    """
    from banco_dados.services.ml_narrativa import gerar_narrativa_parceiro

    db = get_db()
    try:
        inicio_str = request.args.get("inicio")
        fim_str = request.args.get("fim")
        forcar = request.args.get("forcar", "false").lower() in ("1", "true", "yes")

        inicio = datetime.fromisoformat(inicio_str) if inicio_str else None
        fim = datetime.fromisoformat(fim_str) if fim_str else None

        resultado = gerar_narrativa_parceiro(
            db, parceiro_id,
            periodo_inicio=inicio,
            periodo_fim=fim,
            forcar_nova=forcar,
        )

        if resultado.get("erro"):
            return jsonify({
                "ok": False,
                "dados": None,
                "erros": [{"codigo": "SEM_DADOS", "mensagem": resultado["erro"]}],
            }), 404

        return jsonify({"ok": True, "dados": resultado, "erros": []})
    except Exception as e:
        logger.error(f"Erro na narrativa do parceiro {parceiro_id}: {e}", exc_info=True)
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "ERRO_ML", "mensagem": "Erro interno do servidor"}],
        }), 500
    finally:
        db.close()


# ==============================================================
# RETREINAR TODOS OS MODELOS
# ==============================================================

@ml_bp.route("/retreinar", methods=["POST"])
@login_required
def retreinar_modelos():
    """Força recálculo de todos os modelos ML.

    POST /api/ml/retreinar
    """
    from banco_dados.services.ml_predicao import recalcular_predicoes_todos
    from banco_dados.services.ml_score import recalcular_scores_todos

    db = get_db()
    try:
        resultados = {}

        logger.info("🔄 Retreinando todos os modelos ML...")

        resultados['predicao'] = recalcular_predicoes_todos(db)
        resultados['score'] = recalcular_scores_todos(db)

        logger.info("✅ Todos os modelos retreinados")
        return jsonify({"ok": True, "dados": resultados, "erros": []})
    except Exception as e:
        logger.error(f"Erro ao retreinar modelos: {e}", exc_info=True)
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "ERRO_ML", "mensagem": "Erro interno do servidor"}],
        }), 500
    finally:
        db.close()
