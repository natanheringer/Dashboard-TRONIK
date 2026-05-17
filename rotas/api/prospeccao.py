"""Blueprint de endpoints de prospecção REE (ranking XGBoost)."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from banco_dados.services import prospeccao_xgb_service
from rotas.api.decorators import get_db

logger = logging.getLogger(__name__)

prospeccao_bp = Blueprint("prospeccao", __name__, url_prefix="/prospeccao")


@prospeccao_bp.route("/candidatos", methods=["GET"])
@login_required
def listar_candidatos():
    """Retorna fila ranqueada de candidatos à prospecção.

    GET /api/prospeccao/candidatos
    Query params:
      - limite: int (default 50)
      - qid: str — filtro por contexto listwise (ex. bairro:brasilia:centro)
      - prioridade: str — alta | media | baixa
      - model_version: str — versão do modelo; omitido usa o ativo mais recente
    """
    db = get_db()
    try:
        candidatos = prospeccao_xgb_service.buscar_candidatos_prospeccao(
            db,
            limite=request.args.get("limite", 50, type=int),
            qid=request.args.get("qid") or None,
            prioridade=request.args.get("prioridade") or None,
            model_version=request.args.get("model_version") or None,
        )
        return jsonify({"ok": True, "dados": candidatos, "erros": []})
    except Exception as e:
        logger.error("Erro ao listar candidatos de prospecção: %s", e)
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "ERRO_PROSPECCAO", "mensagem": str(e)}],
        }), 500
    finally:
        db.close()


@prospeccao_bp.route("/modelo-ativo", methods=["GET"])
@login_required
def modelo_ativo():
    """Retorna resumo do modelo de prospecção ativo.

    GET /api/prospeccao/modelo-ativo
    """
    db = get_db()
    try:
        modelo = prospeccao_xgb_service.buscar_modelo_ativo(db)
        return jsonify({"ok": True, "dados": modelo, "erros": []})
    except Exception as e:
        logger.error("Erro ao buscar modelo ativo de prospecção: %s", e)
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "ERRO_PROSPECCAO", "mensagem": str(e)}],
        }), 500
    finally:
        db.close()
