"""
API Contratos - Dashboard-TRONIK
=================================
Endpoints para gestão de contratos recorrentes.
"""

from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required

from banco_dados.modelos import Coletor, ContratoRecorrente
from banco_dados.services.contrato_service import ContratoService
from banco_dados.utils.db_session import get_db_session
from banco_dados.utils.logger import obter_logger
from rotas.api import decorators
from rotas.api.decorators import escopo_parceiro_id

logger = obter_logger(__name__)

contratos_bp = Blueprint('contratos_api', __name__, url_prefix='/contratos')


def _filtrar_contratos_parceiro(db, contratos, parceiro_id: int | None):
    """Restringe contratos ao parceiro do usuário quando aplicável."""
    if parceiro_id is None:
        return contratos
    coletor_ids = {c.coletor_id for c in contratos}
    if not coletor_ids:
        return []
    permitidos = {
        row[0]
        for row in db.query(Coletor.id).filter(
            Coletor.id.in_(coletor_ids),
            Coletor.parceiro_id == parceiro_id,
        ).all()
    }
    return [c for c in contratos if c.coletor_id in permitidos]


def _coletor_acessivel(db, coletor_id: int, parceiro_id: int | None) -> bool:
    if parceiro_id is None:
        return True
    coletor = db.query(Coletor).filter_by(id=coletor_id).first()
    return coletor is not None and coletor.parceiro_id == parceiro_id


@contratos_bp.route('/', methods=['GET'])
@login_required
@decorators.rate_limit("30 per minute")
def listar_contratos():
    """
    GET /api/contratos

    Lista contratos recorrentes

    Query Parameters:
    - status: Filtrar por status (ativo, pausado, cancelado, vencido)
    - coletor_id: Filtrar por coletor/cliente
    - apenas_ativos: true/false - Apenas contratos ativos
    """
    db = get_db_session()
    try:
        status = request.args.get('status')
        coletor_id = request.args.get('coletor_id', type=int)
        apenas_ativos = request.args.get('apenas_ativos', 'false').lower() == 'true'
        parceiro_escopo = escopo_parceiro_id()

        if coletor_id and not _coletor_acessivel(db, coletor_id, parceiro_escopo):
            return jsonify([]), 200

        if apenas_ativos:
            contratos = ContratoService.listar_contratos_ativos()
        elif coletor_id:
            contratos = ContratoService.listar_contratos_por_coletor(coletor_id)
        else:
            query = db.query(ContratoRecorrente)
            if status:
                query = query.filter_by(status=status)
            contratos = query.order_by(ContratoRecorrente.data_inicio.desc()).all()
            for c in contratos:
                db.expunge(c)

        contratos = _filtrar_contratos_parceiro(db, contratos, parceiro_escopo)

        return jsonify([c.to_dict() for c in contratos]), 200
    except Exception as e:
        logger.error(f"Erro ao listar contratos: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao listar contratos'}), 500
    finally:
        db.close()


@contratos_bp.route('/', methods=['POST'])
@login_required
@decorators.rate_limit("10 per minute")
def criar_contrato():
    """
    POST /api/contratos

    Cria novo contrato recorrente

    Body:
    {
        "coletor_id": 1,
        "parceiro_id": 1,  # Opcional
        "titulo": "Contrato Mensal - Cliente X",
        "descricao": "...",
        "valor_mensal": 800.0,
        "frequencia_coleta": "mensal",  # semanal, quinzenal, mensal, bimestral
        "dia_coleta": 15,  # Dia do mês (1-31)
        "data_inicio": "2025-12-01T00:00:00",
        "data_vencimento": "2026-12-01T00:00:00",  # Opcional
        "observacoes": "..."
    }
    """
    try:
        from banco_dados.utils.validacao import (
            sanitizar_dados_entrada,
            validar_dados_requisicao,
            validar_id_positivo,
            validar_range,
            validar_tamanho_string,
            validar_tipo_campo,
        )

        dados = request.get_json()
        dados = validar_dados_requisicao(dados, ['coletor_id', 'titulo', 'valor_mensal'])

        # Sanitizar dados de entrada
        campos_string = ['titulo', 'descricao', 'observacoes', 'frequencia_coleta']
        dados = sanitizar_dados_entrada(dados, campos_string)

        # Validações específicas
        validar_id_positivo(dados.get('coletor_id'), 'coletor_id')
        validar_tipo_campo(dados.get('titulo'), str, 'titulo')
        validar_tamanho_string(dados.get('titulo'), min_len=1, max_len=200, nome_campo='titulo')
        validar_tipo_campo(dados.get('valor_mensal'), (int, float), 'valor_mensal')
        validar_range(dados.get('valor_mensal'), min_val=0, max_val=1000000, nome_campo='valor_mensal')

        # Validar que coletor existe
        db = get_db_session()
        try:
            coletor = db.query(Coletor).filter_by(id=dados['coletor_id']).first()
            if not coletor:
                return jsonify({'erro': 'Coletor não encontrada'}), 404
        finally:
            db.close()

        # Converter datas se fornecidas
        if 'data_inicio' in dados and dados['data_inicio']:
            try:
                dados['data_inicio'] = datetime.fromisoformat(
                    dados['data_inicio'].replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                return jsonify({'erro': 'Formato de data_inicio inválido (use ISO 8601)'}), 400

        if 'data_vencimento' in dados and dados['data_vencimento']:
            try:
                dados['data_vencimento'] = datetime.fromisoformat(
                    dados['data_vencimento'].replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                return jsonify({'erro': 'Formato de data_vencimento inválido (use ISO 8601)'}), 400

        contrato = ContratoService.criar_contrato(dados)
        return jsonify(contrato.to_dict()), 201
    except ValueError as e:
        logger.warning(f"Erro ao criar contrato: {str(e)}")
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao criar contrato: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao criar contrato'}), 500


@contratos_bp.route('/<int:contrato_id>', methods=['GET'])
@login_required
def obter_contrato(contrato_id):
    """GET /api/contratos/<id> - Obtém detalhes de um contrato"""
    db = get_db_session()
    try:
        contrato = db.query(ContratoRecorrente).filter_by(id=contrato_id).first()
        if not contrato:
            return jsonify({'erro': 'Contrato não encontrado'}), 404

        parceiro_escopo = escopo_parceiro_id()
        if not _coletor_acessivel(db, contrato.coletor_id, parceiro_escopo):
            return jsonify({'erro': 'Contrato não encontrado'}), 404

        db.expunge(contrato)
        return jsonify(contrato.to_dict()), 200
    except Exception as e:
        logger.error(f"Erro ao obter contrato: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao obter contrato'}), 500
    finally:
        db.close()


@contratos_bp.route('/<int:contrato_id>', methods=['PUT'])
@login_required
@decorators.rate_limit("20 per minute")
def atualizar_contrato(contrato_id):
    """
    PUT /api/contratos/<id>

    Atualiza contrato existente

    Body: Mesmos campos do POST (todos opcionais)
    """
    try:
        from banco_dados.utils.validacao import (
            sanitizar_dados_entrada,
            validar_dados_requisicao,
            validar_data_iso,
        )

        dados = request.get_json()
        dados = validar_dados_requisicao(dados)

        # Sanitizar dados de entrada
        campos_string = ['titulo', 'descricao', 'frequencia_coleta', 'observacoes']
        dados = sanitizar_dados_entrada(dados, campos_string)

        # Converter data_vencimento se fornecida (usando validação padronizada)
        if 'data_vencimento' in dados and dados['data_vencimento']:
            try:
                dados['data_vencimento'] = validar_data_iso(dados['data_vencimento'], 'data_vencimento')
            except Exception as e:
                return jsonify({'erro': str(e)}), 400

        contrato = ContratoService.atualizar_contrato(contrato_id, dados)
        return jsonify(contrato.to_dict()), 200
    except ValueError as e:
        logger.warning(f"Erro ao atualizar contrato: {str(e)}")
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao atualizar contrato: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao atualizar contrato'}), 500


@contratos_bp.route('/<int:contrato_id>/cancelar', methods=['POST'])
@login_required
def cancelar_contrato(contrato_id):
    """
    POST /api/contratos/<id>/cancelar

    Cancela um contrato

    Body (opcional):
    {
        "motivo": "Cliente solicitou cancelamento"
    }
    """
    try:
        dados = request.get_json() or {}
        motivo = dados.get('motivo')

        contrato = ContratoService.cancelar_contrato(contrato_id, motivo)
        return jsonify(contrato.to_dict()), 200
    except ValueError as e:
        logger.warning(f"Erro ao cancelar contrato: {str(e)}")
        return jsonify({'erro': str(e)}), 404
    except Exception as e:
        logger.error(f"Erro ao cancelar contrato: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao cancelar contrato'}), 500


@contratos_bp.route('/receita-mensal', methods=['GET'])
@login_required
def calcular_receita_mensal():
    """
    GET /api/contratos/receita-mensal

    Calcula receita mensal esperada de contratos ativos

    Query Parameters:
    - mes: Mês (1-12, padrão: mês atual)
    - ano: Ano (padrão: ano atual)
    """
    try:
        mes = request.args.get('mes', type=int)
        ano = request.args.get('ano', type=int)

        receita = ContratoService.calcular_receita_mensal_contratos(mes, ano)
        return jsonify({'receita_mensal': receita}), 200
    except Exception as e:
        logger.error(f"Erro ao calcular receita mensal: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao calcular receita mensal'}), 500


@contratos_bp.route('/vencendo', methods=['GET'])
@login_required
def listar_contratos_vencendo():
    """
    GET /api/contratos/vencendo

    Lista contratos que vencem nos próximos N dias

    Query Parameters:
    - dias: Número de dias (padrão: 30)
    """
    try:
        dias = request.args.get('dias', 30, type=int)
        if dias < 1 or dias > 365:
            dias = 30

        contratos = ContratoService.identificar_contratos_vencendo(dias)
        return jsonify([c.to_dict() for c in contratos]), 200
    except Exception as e:
        logger.error(f"Erro ao listar contratos vencendo: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao listar contratos vencendo'}), 500

