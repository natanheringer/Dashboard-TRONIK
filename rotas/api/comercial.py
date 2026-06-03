"""
API Comercial - Dashboard-TRONIK
=================================
Endpoints para dashboard comercial e metas.
"""

from flask import Blueprint, jsonify, request
from flask_login import current_user

from banco_dados.modelos import MetaComercial, PreferenciaLayout
from banco_dados.seguranca import validar_meta_comercial
from banco_dados.services.comercial_service import ComercialService
from banco_dados.utils.db_session import get_db_session
from banco_dados.utils.logger import obter_logger
from rotas.api import decorators
from rotas.api.decorators import admin_required

logger = obter_logger(__name__)

comercial_bp = Blueprint('comercial_api', __name__, url_prefix='/comercial')


@comercial_bp.route('/dashboard', methods=['GET'])
@admin_required
@decorators.rate_limit("30 per minute")
def get_dashboard():
    """
    GET /api/comercial/dashboard?mes=11&ano=2025

    Retorna dados completos do dashboard comercial

    Query params:
    - mes: Mês (1-12), padrão: mês atual
    - ano: Ano, padrão: ano atual
    - meses: Número de meses para agregar (ex: 3 para últimos 3 meses, 6 para últimos 6 meses)
    - todos: Se 'true', retorna dados de todos os períodos (ignora mes/ano/meses)

    Response 200:
    {
        "meta": {...},
        "faturamento_atual": 2749.0,
        "percentual_meta": 22.9,
        "falta_para_meta": 9251.0,
        "proximas_coletas": [...],
        "valor_agendado_semana": 1600.0,
        "clientes_inativos": {...},
        "sugestoes": [...],
        "projecao_fim_mes": 8247.0,
        "metricas_financeiras": {...},
        "analise_parceiros": [...],
        "lucro_por_parceiro": [...]
    }
    """
    try:
        mes = request.args.get('mes', type=int)
        ano = request.args.get('ano', type=int)
        meses = request.args.get('meses', type=int)  # Para agregar múltiplos meses
        todos = request.args.get('todos', type=str, default='false').lower() == 'true'
        data = ComercialService.get_dashboard_data(mes=mes, ano=ano, meses_retroceder=meses, todos_periodos=todos)
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Erro ao obter dashboard comercial: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao carregar dados do dashboard'}), 500


@comercial_bp.route('/meta', methods=['GET'])
@admin_required
def get_meta_atual():
    """
    GET /api/comercial/meta

    Retorna meta do mês atual
    """
    try:
        meta = ComercialService.get_ou_criar_meta_atual()
        return jsonify(meta.to_dict()), 200
    except Exception as e:
        logger.error(f"Erro ao obter meta atual: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao obter meta'}), 500


@comercial_bp.route('/meta', methods=['PUT'])
@admin_required
@decorators.rate_limit("10 per minute")
def atualizar_meta():
    """
    PUT /api/comercial/meta

    Atualiza valor da meta mensal

    Body:
    {
        "valor_meta": 15000.0,
        "observacoes": "Meta aumentada devido a novo contrato"
    }
    """
    db = get_db_session()
    try:
        from banco_dados.utils.validacao import (
            sanitizar_dados_entrada,
            validar_dados_requisicao,
            validar_range,
            validar_tamanho_string,
            validar_tipo_campo,
        )

        dados = request.get_json()
        dados = validar_dados_requisicao(dados)

        # Sanitizar dados de entrada
        campos_string = ['observacoes']
        dados = sanitizar_dados_entrada(dados, campos_string)

        # Validação usando função existente + validação padronizada
        erros = validar_meta_comercial(dados)
        if erros:
            return jsonify({'erros': erros}), 400

        # Validações adicionais padronizadas
        if 'valor_meta' in dados:
            validar_tipo_campo(dados.get('valor_meta'), (int, float), 'valor_meta')
            validar_range(dados.get('valor_meta'), min_val=0, max_val=1000000, nome_campo='valor_meta')
        if 'observacoes' in dados and dados['observacoes']:
            validar_tamanho_string(dados.get('observacoes'), max_len=500, nome_campo='observacoes')

        # Obter meta atual
        from datetime import datetime
        hoje = datetime.now()
        meta = db.query(MetaComercial).filter_by(
            mes=hoje.month, ano=hoje.year
        ).first()

        if not meta:
            # Criar se não existir
            meta = MetaComercial(
                mes=hoje.month,
                ano=hoje.year,
                valor_meta=12000.00,
                valor_realizado=0.0,
                percentual_atingido=0.0,
                status='em_andamento'
            )
            db.add(meta)

        # Atualizar campos permitidos
        if 'valor_meta' in dados:
            meta.valor_meta = float(dados['valor_meta'])
        if 'observacoes' in dados:
            meta.observacoes = dados['observacoes']

        db.commit()
        db.expunge(meta)
        return jsonify(meta.to_dict()), 200

    except ValueError as e:
        logger.warning(f"Erro de validação ao atualizar meta: {str(e)}")
        db.rollback()
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao atualizar meta: {str(e)}", exc_info=True)
        db.rollback()
        return jsonify({'erro': 'Erro ao atualizar meta'}), 500
    finally:
        db.close()


@comercial_bp.route('/meta/historico', methods=['GET'])
@admin_required
def get_historico_metas():
    """
    GET /api/comercial/meta/historico?limite=12&mes=11&ano=2025

    Retorna histórico de metas
    Query params:
    - limite: Número de meses a retornar (padrão: 12)
    - mes: Mês limite (opcional)
    - ano: Ano limite (opcional)
    """
    db = get_db_session()
    try:
        limite = request.args.get('limite', 12, type=int)
        if limite < 1 or limite > 100:
            limite = 12

        mes = request.args.get('mes', type=int)
        ano = request.args.get('ano', type=int)

        query = db.query(MetaComercial)

        # Se mes e ano fornecidos, filtrar até aquele mês
        if mes and ano:
            # Retornar histórico até o mês/ano especificado
            query = query.filter(
                (MetaComercial.ano < ano) |
                ((MetaComercial.ano == ano) & (MetaComercial.mes <= mes))
            )

        metas = query.order_by(
            MetaComercial.ano.desc(),
            MetaComercial.mes.desc()
        ).limit(limite).all()

        # Expurgar objetos da sessão
        for meta in metas:
            db.expunge(meta)

        return jsonify([m.to_dict() for m in metas]), 200
    except Exception as e:
        logger.error(f"Erro ao obter histórico de metas: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao obter histórico'}), 500
    finally:
        db.close()


@comercial_bp.route('/atualizar', methods=['POST'])
@admin_required
def forcar_atualizacao():
    """
    POST /api/comercial/atualizar

    Força atualização da meta com valores atuais
    """
    try:
        meta = ComercialService.atualizar_meta_atual()
        return jsonify(meta.to_dict()), 200
    except Exception as e:
        logger.error(f"Erro ao forçar atualização: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao atualizar meta'}), 500


@comercial_bp.route('/metricas', methods=['GET'])
@admin_required
def get_metricas():
    """
    GET /api/comercial/metricas?mes=11&ano=2025

    Retorna métricas financeiras detalhadas
    """
    try:
        mes = request.args.get('mes', type=int)
        ano = request.args.get('ano', type=int)
        metricas = ComercialService.calcular_metricas_financeiras_detalhadas(mes=mes, ano=ano)
        return jsonify(metricas), 200
    except Exception as e:
        logger.error(f"Erro ao obter métricas: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao obter métricas'}), 500


@comercial_bp.route('/parceiros', methods=['GET'])
@admin_required
def get_analise_parceiros():
    """
    GET /api/comercial/parceiros?mes=11&ano=2025

    Retorna análise detalhada por parceiro
    """
    try:
        mes = request.args.get('mes', type=int)
        ano = request.args.get('ano', type=int)
        analise = ComercialService.analisar_por_parceiro(mes=mes, ano=ano)
        return jsonify(analise), 200
    except Exception as e:
        logger.error(f"Erro ao obter análise de parceiros: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao obter análise de parceiros'}), 500


@comercial_bp.route('/comparar', methods=['GET'])
@admin_required
def comparar_meses():
    """
    GET /api/comercial/comparar

    Compara mês atual com mês anterior
    """
    try:
        comparacao = ComercialService.comparar_com_mes_anterior()
        return jsonify(comparacao), 200
    except Exception as e:
        logger.error(f"Erro ao comparar meses: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao comparar meses'}), 500


@comercial_bp.route('/layout', methods=['POST'])
@admin_required
def salvar_layout():
    """
    POST /api/comercial/layout

    Salva ordem dos containers do dashboard comercial

    Body:
    {
        "ordem_containers": ["kpi-meta", "resumo-financeiro", "kpi-faturamento", ...]
    }
    """
    db = get_db_session()
    try:
        dados = request.get_json()
        if not dados or 'ordem_containers' not in dados:
            return jsonify({'erro': 'Dados não fornecidos'}), 400

        import json
        ordem_json = json.dumps(dados['ordem_containers'])

        # Buscar ou criar preferência
        preferencia = db.query(PreferenciaLayout).filter_by(
            usuario_id=current_user.id
        ).first()

        if not preferencia:
            preferencia = PreferenciaLayout(
                usuario_id=current_user.id,
                ordem_containers=ordem_json
            )
            db.add(preferencia)
        else:
            preferencia.ordem_containers = ordem_json

        db.commit()
        db.expunge(preferencia)

        return jsonify({'sucesso': True, 'mensagem': 'Layout salvo com sucesso'}), 200

    except Exception as e:
        logger.error(f"Erro ao salvar layout: {str(e)}", exc_info=True)
        db.rollback()
        return jsonify({'erro': 'Erro ao salvar layout'}), 500
    finally:
        db.close()


@comercial_bp.route('/layout', methods=['GET'])
@admin_required
def obter_layout():
    """
    GET /api/comercial/layout

    Retorna ordem salva dos containers (se houver)
    """
    db = get_db_session()
    try:
        preferencia = db.query(PreferenciaLayout).filter_by(
            usuario_id=current_user.id
        ).first()

        if preferencia:
            db.expunge(preferencia)
            return jsonify(preferencia.to_dict()), 200
        else:
            return jsonify({'ordem_containers': []}), 200

    except Exception as e:
        logger.error(f"Erro ao obter layout: {str(e)}", exc_info=True)
        return jsonify({'erro': 'Erro ao obter layout'}), 500
    finally:
        db.close()

