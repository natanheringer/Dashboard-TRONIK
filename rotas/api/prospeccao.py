"""Blueprint de endpoints de prospecção REE (ranking XGBoost)."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user

from banco_dados.services import prospeccao_crm_bridge, prospeccao_xgb_service
from rotas.api.decorators import admin_required, get_db

logger = logging.getLogger(__name__)

prospeccao_bp = Blueprint("prospeccao", __name__, url_prefix="/prospeccao")

_ERRO_INTERNO = "Erro interno ao processar solicitação de prospecção."


@prospeccao_bp.route("/candidatos", methods=["GET"])
@admin_required
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
        limite = min(1000, max(1, request.args.get("limite", 50, type=int)))
        qid = request.args.get("qid") or None
        prioridade = request.args.get("prioridade") or None
        model_version = request.args.get("model_version") or None

        logger.debug("Buscando candidatos: limite=%d, qid=%s, prioridade=%s, model_version=%s",
                     limite, qid, prioridade, model_version)

        candidatos = prospeccao_xgb_service.buscar_candidatos_prospeccao(
            db,
            limite=limite,
            qid=qid,
            prioridade=prioridade,
            model_version=model_version,
        )

        logger.debug("Retornando %d candidatos", len(candidatos) if candidatos else 0)
        return jsonify({"ok": True, "dados": candidatos, "erros": []})
    except Exception as e:
        logger.error("Erro ao listar candidatos de prospecção: %s", e, exc_info=True)
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "ERRO_PROSPECCAO", "mensagem": _ERRO_INTERNO}],
        }), 500
    finally:
        db.close()


@prospeccao_bp.route("/candidatos/<int:empresa_id>/pipeline", methods=["POST"])
@admin_required
def criar_pipeline_candidato(empresa_id: int):
    """Cria lead CRM a partir de empresa candidata à prospecção REE.

    POST /api/prospeccao/candidatos/<empresa_id>/pipeline
    Body (opcional): { "observacoes", "valor_estimado", "status" }
    """
    db = get_db()
    try:
        body = request.get_json(silent=True) or {}
        usuario_id = current_user.id if current_user.is_authenticated else None
        resultado = prospeccao_crm_bridge.criar_pipeline_de_candidato(
            db,
            empresa_id,
            usuario_id,
            observacoes=body.get("observacoes"),
            valor_estimado=body.get("valor_estimado"),
            status=body.get("status"),
        )
        if resultado is None:
            return jsonify({
                "ok": False,
                "dados": None,
                "erros": [{
                    "codigo": "EMPRESA_NAO_ENCONTRADA",
                    "mensagem": f"Empresa candidata #{empresa_id} não encontrada.",
                }],
            }), 404

        status_code = 200 if resultado.get("ja_vinculado") else 201
        return jsonify({"ok": True, "dados": resultado, "erros": []}), status_code
    except ValueError as e:
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "VALIDACAO", "mensagem": str(e)}],
        }), 400
    except Exception as e:
        logger.error("Erro ao criar pipeline de candidato %s: %s", empresa_id, e)
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "ERRO_PROSPECCAO", "mensagem": _ERRO_INTERNO}],
        }), 500
    finally:
        db.close()


@prospeccao_bp.route("/saude", methods=["GET"])
@admin_required
def saude():
    """Saúde do ranker de prospecção: modelo ativo, métricas NDCG, scores publicados.

    GET /api/prospeccao/saude
    Query params:
      - model_version: str — versão específica; omitido usa o ativo
    """
    db = get_db()
    try:
        dados = prospeccao_xgb_service.saude_prospeccao(
            db,
            model_version=request.args.get("model_version") or None,
        )
        return jsonify({"ok": True, "dados": dados, "erros": []})
    except Exception as e:
        logger.error("Erro ao consultar saúde de prospecção: %s", e)
        return jsonify({
            "ok": False,
            "dados": None,
            "erros": [{"codigo": "ERRO_PROSPECCAO", "mensagem": _ERRO_INTERNO}],
        }), 500
    finally:
        db.close()


@prospeccao_bp.route("/modelo-ativo", methods=["GET"])
@admin_required
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
            "erros": [{"codigo": "ERRO_PROSPECCAO", "mensagem": _ERRO_INTERNO}],
        }), 500
    finally:
        db.close()
