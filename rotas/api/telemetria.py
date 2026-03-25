from flask import Blueprint, request, jsonify

telemetria_bp = Blueprint('telemetria', __name__, url_prefix='/sensor')

@telemetria_bp.route('/telemetria', methods=['POST'])
def receber_telemetria():
    data = request.get_json()

    nivel = data.get("nivel_preenchimento")

    return jsonify({
        "status": "ok",
        "coletor_status": "OK",
        "nivel": nivel,
        "notificacoes_criadas": 0
    })