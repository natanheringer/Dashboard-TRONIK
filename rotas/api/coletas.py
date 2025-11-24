"""
Rotas de Coletas - Dashboard-TRONIK
====================================
Endpoints para operações com coletas.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from rotas.api import decorators
from rotas.api.decorators import get_db
from banco_dados.serializers import coleta_para_dict
from banco_dados.services.coleta_service import (
    validar_dados_coleta, criar_coleta, obter_coletas_com_filtros
)
from banco_dados.utils.erros import (
    tratar_erro_api, ErroValidacao, validar_requisicao_json,
    validar_tipo, validar_range
)
from banco_dados.utils.logger import obter_logger

logger = obter_logger(__name__)

# Criar blueprint
coletas_bp = Blueprint('coletas', __name__)


@coletas_bp.route('/coletas', methods=['GET'])
def listar_coletas():
    """Endpoint para obter coletas com filtros opcionais e paginação"""
    db = get_db()
    try:
        # Parâmetros de paginação
        pagina = request.args.get('pagina', type=int, default=1)
        por_pagina = request.args.get('por_pagina', type=int, default=50)
        
        # Filtros
        coletor_id = request.args.get('coletor_id', type=int)
        parceiro_id = request.args.get('parceiro_id', type=int)
        tipo_operacao = request.args.get('tipo_operacao')
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        # Obter coletas com filtros e paginação
        coletas, total_count = obter_coletas_com_filtros(
            db,
            coletor_id=coletor_id,
            parceiro_id=parceiro_id,
            tipo_operacao=tipo_operacao,
            data_inicio=data_inicio,
            data_fim=data_fim,
            pagina=pagina,
            por_pagina=por_pagina
        )
        
        resultado = [coleta_para_dict(c) for c in coletas]
        
        return jsonify({
            "dados": resultado,
            "paginacao": {
                "pagina": pagina,
                "por_pagina": por_pagina,
                "total": total_count,
                "total_paginas": (total_count + por_pagina - 1) // por_pagina if total_count > 0 else 0
            }
        })
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@coletas_bp.route('/historico', methods=['GET'])
def obter_historico():
    """Endpoint para obter histórico de coletas com filtro de data"""
    db = get_db()
    try:
        data_filtro = request.args.get('data')
        
        # Parâmetros de paginação com validação
        pagina = request.args.get('pagina', type=int, default=1)
        if pagina < 1:
            pagina = 1
        if pagina > 1000:  # Limite máximo de páginas
            pagina = 1000
        
        por_pagina = request.args.get('por_pagina', type=int, default=50)
        if por_pagina < 1:
            por_pagina = 1
        if por_pagina > 500:  # Limite máximo de itens por página
            por_pagina = 500
        
        # Se data fornecida, usar como data_inicio e data_fim
        data_inicio = data_filtro
        data_fim = data_filtro
        
        coletas, total_count = obter_coletas_com_filtros(
            db,
            data_inicio=data_inicio,
            data_fim=data_fim,
            pagina=pagina,
            por_pagina=por_pagina
        )
        
        resultado = [coleta_para_dict(c) for c in coletas]
        
        return jsonify({
            "dados": resultado,
            "paginacao": {
                "pagina": pagina,
                "por_pagina": por_pagina,
                "total": total_count,
                "total_paginas": (total_count + por_pagina - 1) // por_pagina if total_count > 0 else 0
            }
        })
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@coletas_bp.route('/coleta', methods=['POST'])
@login_required
@decorators.rate_limit("30 per minute")
def criar_coleta_endpoint():
    """Endpoint para criar uma nova coleta"""
    db = get_db()
    try:
        dados = request.get_json()
        validar_requisicao_json(dados)
        
        # Validar dados
        erros = validar_dados_coleta(dados, criar=True, db=db)
        if erros:
            raise ErroValidacao("Erros de validação", {"detalhes": erros})
        
        # Criar coleta
        nova_coleta = criar_coleta(db, dados)
        
        # Emitir atualização via WebSocket
        try:
            from rotas.websocket import emitir_atualizacao_coleta
            emitir_atualizacao_coleta(coleta_para_dict(nova_coleta))
        except Exception as e:
            logger.warning(f"Erro ao emitir atualização WebSocket: {e}")
        
        return jsonify(coleta_para_dict(nova_coleta)), 201
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()

