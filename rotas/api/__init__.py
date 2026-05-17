"""
API Blueprints - Dashboard-TRONIK
==================================
Registra todos os blueprints da API.

Convencoes:
- Cada sub-blueprint expoe um objeto *_bp e registra suas proprias rotas.
- O endpoint POST /api/sensor/telemetria vive em `sensores.py` e e o unico
  handler de telemetria real (recebe ESP32 em producao).
- Nao adicionar handlers duplicados para a mesma rota em outro blueprint.
"""

from flask import Blueprint

from rotas.api import (
    auxiliares,
    coletas,
    coletores,
    comercial,
    contratos,
    crm,
    ml,
    nik,
    notificacoes,
    prospeccao,
    relatorios,
    sensores,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Operacional
api_bp.register_blueprint(coletores.coletores_bp)
api_bp.register_blueprint(coletas.coletas_bp)
api_bp.register_blueprint(sensores.sensores_bp)
api_bp.register_blueprint(notificacoes.notificacoes_bp)
api_bp.register_blueprint(relatorios.relatorios_bp)
api_bp.register_blueprint(auxiliares.auxiliares_bp)
api_bp.register_blueprint(nik.nik_bp)

# Comercial
api_bp.register_blueprint(comercial.comercial_bp)
api_bp.register_blueprint(crm.crm_bp)
api_bp.register_blueprint(contratos.contratos_bp)

# Machine Learning
api_bp.register_blueprint(ml.ml_bp)
api_bp.register_blueprint(prospeccao.prospeccao_bp)

