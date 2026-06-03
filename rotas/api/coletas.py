"""
Rotas de Coletas - Dashboard-TRONIK
====================================
Endpoints para operações com coletas.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required

from banco_dados.serializers import coleta_para_dict
from banco_dados.services.coleta_service import (
    criar_coleta,
    obter_coletas_com_filtros,
    validar_dados_coleta,
)
from banco_dados.utils.erros import (
    ErroValidacao,
    tratar_erro_api,
)
from banco_dados.utils.logger import obter_logger
from banco_dados.utils.validacao import validar_paginacao
from rotas.api import decorators
from rotas.api.decorators import escopo_parceiro_id, get_db

logger = obter_logger(__name__)

# Criar blueprint
coletas_bp = Blueprint('coletas', __name__)


@coletas_bp.route('/coletas', methods=['GET'])
@login_required
def listar_coletas():
    """Endpoint para obter coletas com filtros opcionais e paginação"""
    db = get_db()
    try:
        # Parâmetros de paginação
        pagina, por_pagina = validar_paginacao(
            request.args.get('pagina', type=int),
            request.args.get('por_pagina', type=int)
        )

        # Filtros
        coletor_id = request.args.get('coletor_id', type=int)
        parceiro_id = escopo_parceiro_id(request.args.get('parceiro_id', type=int))
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
@login_required
def obter_historico():
    """Endpoint para obter histórico de coletas com filtro de data"""
    db = get_db()
    try:
        data_filtro = request.args.get('data')

        # Parâmetros de paginação com validação
        pagina, por_pagina = validar_paginacao(
            request.args.get('pagina', type=int),
            request.args.get('por_pagina', type=int)
        )

        # Se data fornecida, usar como data_inicio e data_fim
        data_inicio = data_filtro
        data_fim = data_filtro

        parceiro_id = escopo_parceiro_id()

        coletas, total_count = obter_coletas_com_filtros(
            db,
            data_inicio=data_inicio,
            data_fim=data_fim,
            parceiro_id=parceiro_id,
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
        from banco_dados.utils.validacao import sanitizar_dados_entrada, validar_dados_requisicao

        dados = request.get_json()
        dados = validar_dados_requisicao(dados)

        # Sanitizar dados de entrada
        campos_string = ['tipo_operacao', 'observacoes']
        dados = sanitizar_dados_entrada(dados, campos_string)

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

