from flask import Blueprint, jsonify, request
from http import HTTPStatus
from banco_dados.modelos import db, Lixeira, Sensor

api_bp = Blueprint("api", __name__)

@api_bp.get("/lixeiras")
def listar_lixeiras():
    lista = Lixeira.query.all()
    return jsonify({"data": [{"id": x.id, "nome": x.nome, "nivel": x.nivel, "status": x.status} for x in lista]}), HTTPStatus.OK

@api_bp.patch("/lixeiras/<int:id>/nivel")
def atualizar_nivel(id):
    dados = request.get_json()
    lixeira = Lixeira.query.get(id)
    if not lixeira:
        return jsonify({"error": "Não encontrada"}), HTTPStatus.NOT_FOUND
    nivel = dados.get("nivel")
    if not isinstance(nivel, int) or not 0 <= nivel <= 100:
        return jsonify({"error": "Nível inválido"}), HTTPStatus.BAD_REQUEST
    lixeira.nivel = nivel
    lixeira.atualizar_status()
    db.session.commit()
    return jsonify({"data": {"nivel": lixeira.nivel, "status": lixeira.status}}), HTTPStatus.OK

@api_bp.get("/sensores")
def sensores():
    lista = Sensor.query.all()
    return jsonify({"data": [{"id": x.id, "identificador": x.identificador, "lixeira_id": x.lixeira_id} for x in lista]}), HTTPStatus.OK
