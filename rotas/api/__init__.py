"""
API Blueprints - Dashboard-TRONIK
==================================
Registra todos os blueprints da API.
"""

from flask import Blueprint
from rotas.api import coletores, coletas, sensores, notificacoes, relatorios, auxiliares
from rotas.api import comercial, crm, contratos
from rotas.api import telemetria


# Criar blueprint principal da API
api_bp = Blueprint('api', __name__, url_prefix='/api')


# Registrar sub-blueprints operacionais
api_bp.register_blueprint(coletores.coletores_bp)
api_bp.register_blueprint(coletas.coletas_bp)
api_bp.register_blueprint(sensores.sensores_bp)
api_bp.register_blueprint(notificacoes.notificacoes_bp)
api_bp.register_blueprint(relatorios.relatorios_bp)
api_bp.register_blueprint(auxiliares.auxiliares_bp)
api_bp.register_blueprint(telemetria.telemetria_bp)

# Registrar sub-blueprints comerciais
api_bp.register_blueprint(comercial.comercial_bp)
api_bp.register_blueprint(crm.crm_bp)
api_bp.register_blueprint(contratos.contratos_bp)

