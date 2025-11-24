"""
API CRM - Dashboard-TRONIK
===========================
Endpoints para CRM e pipeline de vendas.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from banco_dados.services.crm_service import CRMService
from banco_dados.modelos import Pipeline, Interacao, Tarefa
from banco_dados.utils.db_session import get_db_session
from banco_dados.utils.logger import obter_logger
from rotas.api import decorators
from datetime import datetime

logger = obter_logger(__name__)

crm_bp = Blueprint('crm_api', __name__, url_prefix='/crm')


@crm_bp.route('/pipeline', methods=['GET'])
@login_required
@decorators.rate_limit("30 per minute")
def listar_pipeline():
    """
    GET /api/crm/pipeline
    
    Lista itens do pipeline com filtros opcionais
    
    Query Parameters:
    - status: Filtrar por status
    - responsavel_id: Filtrar por responsável
    - coletor_id: Filtrar por coletor/cliente
    """
    db = get_db_session()
    try:
        from sqlalchemy.orm import joinedload
        
        status = request.args.get('status')
        responsavel_id = request.args.get('responsavel_id', type=int)
        coletor_id = request.args.get('coletor_id', type=int)
        
        query = db.query(Pipeline).options(
            joinedload(Pipeline.coletor),
            joinedload(Pipeline.responsavel)
        )
        
        if status:
            query = query.filter_by(status=status)
        if responsavel_id:
            query = query.filter_by(responsavel_id=responsavel_id)
        if coletor_id:
            query = query.filter_by(coletor_id=coletor_id)
        
        pipelines = query.order_by(Pipeline.criado_em.desc()).all()
        
        # Expurgar objetos após serializar
        resultado = [p.to_dict() for p in pipelines]
        for p in pipelines:
            db.expunge(p)
        
        return jsonify(resultado), 200
    except Exception as e:
        logger.error(f"Erro ao listar pipeline: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao listar pipeline'}), 500
    finally:
        db.close()


@crm_bp.route('/pipeline', methods=['POST'])
@login_required
@decorators.rate_limit("10 per minute")
def criar_pipeline():
    """
    POST /api/crm/pipeline
    
    Cria novo item no pipeline
    
    Body:
    {
        "coletor_id": 1,  # Opcional (pode ser null para leads sem coletor)
        "status": "lead",
        "valor_estimado": 800.0,
        "proxima_acao": "Ligar para cliente",
        "data_proxima_acao": "2025-11-25T10:00:00",
        "origem": "indicacao",
        "tipo_servico": "coleta",
        "observacoes": "...",
        "descricao_inicial": "Lead recebido via indicação"
    }
    """
    try:
        from banco_dados.utils.validacao import (
            validar_dados_requisicao, validar_data_iso, sanitizar_dados_entrada
        )
        
        dados = request.get_json()
        dados = validar_dados_requisicao(dados)
        
        # Sanitizar dados de entrada
        campos_string = ['proxima_acao', 'origem', 'tipo_servico', 'observacoes', 'descricao_inicial', 'status']
        dados = sanitizar_dados_entrada(dados, campos_string)
        
        # Converter data_proxima_acao se fornecida (usando validação padronizada)
        if 'data_proxima_acao' in dados and dados['data_proxima_acao']:
            try:
                dados['data_proxima_acao'] = validar_data_iso(dados['data_proxima_acao'], 'data_proxima_acao')
            except Exception as e:
                return jsonify({'erro': str(e)}), 400
        
        usuario_id = current_user.id if current_user.is_authenticated else None
        pipeline = CRMService.criar_pipeline(dados, usuario_id)
        
        # Pipeline já foi expurgado pelo serviço, mas precisamos garantir que to_dict funcione
        # O serviço já faz eager load e expunge, então está seguro
        return jsonify(pipeline.to_dict()), 201
    except ValueError as e:
        logger.warning(f"Erro de validação ao criar pipeline: {str(e)}")
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao criar pipeline: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao criar pipeline'}), 500


@crm_bp.route('/pipeline/<int:pipeline_id>', methods=['GET'])
@login_required
@decorators.rate_limit("30 per minute")
def obter_pipeline(pipeline_id):
    """GET /api/crm/pipeline/<id> - Obtém detalhes de um pipeline"""
    db = get_db_session()
    try:
        from sqlalchemy.orm import joinedload
        # Não usar joinedload em interacoes porque é lazy="dynamic"
        pipeline = db.query(Pipeline).options(
            joinedload(Pipeline.coletor),
            joinedload(Pipeline.responsavel),
            joinedload(Pipeline.tarefas)
        ).filter_by(id=pipeline_id).first()
        
        if not pipeline:
            return jsonify({'erro': 'Pipeline não encontrado'}), 404
        
        resultado = pipeline.to_dict()
        # Carregar interações separadamente (lazy="dynamic" retorna query object)
        from banco_dados.modelos import Interacao
        interacoes = db.query(Interacao).filter_by(pipeline_id=pipeline_id).all()
        resultado['interacoes'] = [i.to_dict() for i in interacoes]
        resultado['tarefas'] = [t.to_dict() for t in pipeline.tarefas] if pipeline.tarefas else []
        
        db.expunge(pipeline)
        return jsonify(resultado), 200
    except Exception as e:
        logger.error(f"Erro ao obter pipeline: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao obter pipeline'}), 500
    finally:
        db.close()


@crm_bp.route('/pipeline/<int:pipeline_id>/status', methods=['PUT'])
@login_required
@decorators.rate_limit("20 per minute")
def atualizar_status_pipeline(pipeline_id):
    """
    PUT /api/crm/pipeline/<id>/status
    
    Atualiza status do pipeline
    
    Body:
    {
        "status": "proposta_enviada",
        "motivo_perda": "..."  # Obrigatório se status='perdido'
    }
    """
    try:
        from banco_dados.utils.validacao import (
            validar_dados_requisicao, validar_enum, sanitizar_dados_entrada
        )
        
        dados = request.get_json()
        dados = validar_dados_requisicao(dados, ['status'])
        
        # Sanitizar dados de entrada
        campos_string = ['status', 'motivo_perda']
        dados = sanitizar_dados_entrada(dados, campos_string)
        
        # Validar status
        status_permitidos = ['lead', 'contato_inicial', 'proposta_enviada', 'negociacao', 'fechado', 'perdido']
        validar_enum(dados.get('status'), status_permitidos, 'status')
        
        novo_status = dados.get('status')
        if not novo_status:
            return jsonify({'erro': 'Status não fornecido'}), 400
        
        motivo_perda = dados.get('motivo_perda') if novo_status == 'perdido' else None
        if novo_status == 'perdido' and not motivo_perda:
            return jsonify({'erro': 'Motivo da perda é obrigatório quando status é "perdido"'}), 400
        
        pipeline = CRMService.atualizar_status(pipeline_id, novo_status, motivo_perda)
        return jsonify(pipeline.to_dict()), 200
    except ValueError as e:
        logger.warning(f"Erro ao atualizar status: {str(e)}")
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao atualizar status do pipeline: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao atualizar status'}), 500


@crm_bp.route('/pipeline/<int:pipeline_id>/interacoes', methods=['POST'])
@login_required
@decorators.rate_limit("20 per minute")
def registrar_interacao(pipeline_id):
    """
    POST /api/crm/pipeline/<id>/interacoes
    
    Registra interação com cliente
    
    Body:
    {
        "tipo": "ligacao",
        "descricao": "Cliente demonstrou interesse",
        "resultado": "positivo",
        "duracao_minutos": 15
    }
    """
    try:
        from banco_dados.utils.validacao import (
            validar_dados_requisicao, validar_obrigatorio, validar_enum,
            validar_tamanho_string, sanitizar_dados_entrada
        )
        
        dados = request.get_json()
        dados = validar_dados_requisicao(dados, ['tipo', 'descricao'])
        
        # Sanitizar dados de entrada
        campos_string = ['tipo', 'descricao', 'resultado']
        dados = sanitizar_dados_entrada(dados, campos_string)
        
        # Validações específicas
        validar_tamanho_string(dados.get('descricao'), min_len=1, max_len=1000, nome_campo='descricao')
        
        # Validar tipo de interação
        tipos_permitidos = ['ligacao', 'email', 'reuniao', 'whatsapp', 'outro']
        validar_enum(dados.get('tipo'), tipos_permitidos, 'tipo')
        
        tipo = dados.get('tipo')
        descricao = dados.get('descricao')
        
        usuario_id = current_user.id if current_user.is_authenticated else None
        interacao = CRMService.registrar_interacao(
            pipeline_id,
            tipo,
            descricao,
            resultado=dados.get('resultado'),
            usuario_id=usuario_id,
            duracao_minutos=dados.get('duracao_minutos')
        )
        
        return jsonify(interacao.to_dict()), 201
    except ValueError as e:
        logger.warning(f"Erro ao registrar interação: {str(e)}")
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao registrar interação: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao registrar interação'}), 500


@crm_bp.route('/funil', methods=['GET'])
@login_required
@decorators.rate_limit("30 per minute")
def get_funil_vendas():
    """GET /api/crm/funil - Retorna dados do funil de vendas"""
    try:
        funil = CRMService.get_funil_vendas()
        return jsonify(funil), 200
    except Exception as e:
        logger.error(f"Erro ao obter funil: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao obter funil de vendas'}), 500


@crm_bp.route('/estatisticas', methods=['GET'])
@login_required
@decorators.rate_limit("30 per minute")
def get_estatisticas():
    """GET /api/crm/estatisticas - Retorna estatísticas gerais do CRM"""
    try:
        estatisticas = CRMService.get_estatisticas_gerais()
        return jsonify(estatisticas), 200
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao obter estatísticas'}), 500


@crm_bp.route('/tarefas', methods=['GET'])
@login_required
@decorators.rate_limit("30 per minute")
def listar_tarefas():
    """
    GET /api/crm/tarefas
    
    Lista tarefas pendentes
    
    Query Parameters:
    - usuario_id: Filtrar por usuário (padrão: usuário atual)
    - atrasadas: true/false - Filtrar apenas atrasadas
    """
    try:
        usuario_id = request.args.get('usuario_id', type=int)
        atrasadas = request.args.get('atrasadas', 'false').lower() == 'true'
        
        # Se não especificado, usar usuário atual
        if not usuario_id and current_user.is_authenticated:
            usuario_id = current_user.id
        
        if atrasadas:
            tarefas = CRMService.get_tarefas_atrasadas(usuario_id)
        else:
            tarefas = CRMService.get_tarefas_pendentes(usuario_id)
        
        return jsonify([t.to_dict() for t in tarefas]), 200
    except Exception as e:
        logger.error(f"Erro ao listar tarefas: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao listar tarefas'}), 500


@crm_bp.route('/tarefas', methods=['POST'])
@login_required
@decorators.rate_limit("10 per minute")
def criar_tarefa():
    """
    POST /api/crm/tarefas
    
    Cria nova tarefa
    
    Body:
    {
        "titulo": "Ligar para cliente X",
        "descricao": "...",
        "pipeline_id": 1,  # Opcional
        "prioridade": "alta",
        "data_vencimento": "2025-11-25T10:00:00"
    }
    """
    try:
        from banco_dados.utils.validacao import (
            validar_dados_requisicao, validar_tipo_campo,
            validar_tamanho_string, validar_data_iso, sanitizar_dados_entrada
        )
        
        dados = request.get_json()
        dados = validar_dados_requisicao(dados, ['titulo'])
        
        # Sanitizar dados de entrada
        campos_string = ['titulo', 'descricao', 'prioridade']
        dados = sanitizar_dados_entrada(dados, campos_string)
        
        # Validações específicas
        validar_tipo_campo(dados.get('titulo'), str, 'titulo')
        validar_tamanho_string(dados.get('titulo'), min_len=1, max_len=200, nome_campo='titulo')
        
        # Converter data_vencimento se fornecida (usando validação padronizada)
        if 'data_vencimento' in dados and dados['data_vencimento']:
            try:
                dados['data_vencimento'] = validar_data_iso(dados['data_vencimento'], 'data_vencimento')
            except Exception as e:
                return jsonify({'erro': str(e)}), 400
        
        usuario_id = current_user.id if current_user.is_authenticated else None
        tarefa = CRMService.criar_tarefa(dados, usuario_id)
        
        return jsonify(tarefa.to_dict()), 201
    except ValueError as e:
        logger.warning(f"Erro ao criar tarefa: {str(e)}")
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao criar tarefa: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao criar tarefa'}), 500


@crm_bp.route('/tarefas/<int:tarefa_id>/concluir', methods=['POST'])
@login_required
@decorators.rate_limit("20 per minute")
def concluir_tarefa(tarefa_id):
    """POST /api/crm/tarefas/<id>/concluir - Marca tarefa como concluída"""
    try:
        tarefa = CRMService.concluir_tarefa(tarefa_id)
        return jsonify(tarefa.to_dict()), 200
    except ValueError as e:
        logger.warning(f"Erro ao concluir tarefa: {str(e)}")
        return jsonify({'erro': str(e)}), 404
    except Exception as e:
        logger.error(f"Erro ao concluir tarefa: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao concluir tarefa'}), 500

