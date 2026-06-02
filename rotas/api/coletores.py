"""
Rotas de Coletores - Dashboard-TRONIK
=====================================
Endpoints para operações CRUD de coletores.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy.orm import joinedload

from banco_dados.modelos import Coletor
from banco_dados.serializers import coletor_para_dict
from banco_dados.services.coletor_service import (
    atualizar_coletor,
    criar_coletor,
    obter_coletores_com_filtros,
    resumo_operacional,
    validar_dados_coletor,
)
from banco_dados.utils.erros import ErroNaoEncontrado, ErroValidacao, tratar_erro_api
from banco_dados.utils.logger import obter_logger
from banco_dados.utils.validacao import validar_paginacao
from rotas.api import decorators
from rotas.api.decorators import admin_required, escopo_parceiro_id, get_db

logger = obter_logger(__name__)

# Criar blueprint
coletores_bp = Blueprint('coletores', __name__)


@coletores_bp.route('/coletores/resumo', methods=['GET'])
@login_required
def resumo_coletores():
    """Resumo operacional agregado dos coletores."""
    db = get_db()
    try:
        parceiro_id = escopo_parceiro_id()
        return jsonify(resumo_operacional(db, parceiro_id=parceiro_id))
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@coletores_bp.route('/coletores', methods=['GET'])
@login_required
def listar_coletores():
    """Endpoint para obter todas as coletores com filtros opcionais e paginação"""
    db = get_db()
    try:
        # Parâmetros de paginação com validação
        pagina, por_pagina = validar_paginacao(
            request.args.get('pagina', type=int),
            request.args.get('por_pagina', type=int)
        )

        # Filtros
        status = request.args.get('status')
        parceiro_id = escopo_parceiro_id(request.args.get('parceiro_id', type=int))

        # Obter coletores com filtros e paginação
        coletores, total_count = obter_coletores_com_filtros(
            db, status=status, parceiro_id=parceiro_id,
            pagina=pagina, por_pagina=por_pagina
        )

        resultado = [coletor_para_dict(c) for c in coletores]

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


@coletores_bp.route('/coletor/<int:coletor_id>', methods=['GET'])
@login_required
def obter_lixeira(coletor_id):
    """Endpoint para obter uma coletor específica"""
    db = get_db()
    try:
        coletor = db.query(Coletor).options(
            joinedload(Coletor.parceiro),
            joinedload(Coletor.tipo_material)
        ).filter(Coletor.id == coletor_id).first()

        if not coletor:
            raise ErroNaoEncontrado("Coletor", coletor_id)

        # [SEGURANÇA] Verificar se o usuário tem acesso ao coletor deste parceiro
        parceiro_id = escopo_parceiro_id()
        if parceiro_id is not None and coletor.parceiro_id != parceiro_id:
            return jsonify({"erro": "Acesso negado"}), 403

        return jsonify(coletor_para_dict(coletor))
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@coletores_bp.route('/coletor', methods=['POST'])
@login_required
@decorators.rate_limit("10 per minute")
def criar_coletor_endpoint():
    """Endpoint para criar uma nova coletor"""
    db = get_db()
    try:
        from banco_dados.utils.validacao import sanitizar_dados_entrada, validar_dados_requisicao

        dados = request.get_json()
        dados = validar_dados_requisicao(dados)

        # Sanitizar dados de entrada
        campos_string = ['localizacao', 'status', 'observacoes']
        dados = sanitizar_dados_entrada(dados, campos_string)

        # Validar dados
        erros = validar_dados_coletor(dados, criar=True, db=db)
        if erros:
            raise ErroValidacao("Erros de validação", {"detalhes": erros})

        # Criar coletor
        novo_coletor = criar_coletor(db, dados)

        # Emitir atualização via WebSocket
        try:
            from rotas.websocket import emitir_atualizacao_coletor
            emitir_atualizacao_coletor(coletor_para_dict(novo_coletor), 'coletor_criado')
        except Exception as e:
            logger.warning(f"Erro ao emitir atualização WebSocket: {e}")

        # Commit inicial do registro antes da geocodificação
        db.commit()

        # Geocodificação automática se não tiver coordenadas (APÓS commit)
        if not novo_coletor.latitude or not novo_coletor.longitude:
            try:
                from banco_dados.geocodificacao import geocodificar_endereco
                resultado = geocodificar_endereco(
                    novo_coletor.localizacao,
                    cidade="Brasília",
                    estado="DF"
                )
                if resultado:
                    novo_coletor.latitude = resultado['latitude']
                    novo_coletor.longitude = resultado['longitude']
                    db.commit()
                    db.refresh(novo_coletor)
                    logger.info(f"Coordenadas geocodificadas automaticamente para coletor {novo_coletor.id}")
            except Exception as e:
                logger.warning(f"Geocodificação automática falhou para coletor {novo_coletor.id}: {e}")

        return jsonify(coletor_para_dict(novo_coletor)), 201
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()


@coletores_bp.route('/coletor/<int:coletor_id>', methods=['PUT'])
@login_required
@decorators.rate_limit("20 per minute")
def atualizar_coletor_endpoint(coletor_id):
    """Endpoint para atualizar uma coletor"""
    db = get_db()
    try:
        coletor = db.query(Coletor).filter(Coletor.id == coletor_id).first()
        if not coletor:
            raise ErroNaoEncontrado("Coletor", coletor_id)

        # [SEGURANÇA] Verificar se o usuário tem acesso ao coletor deste parceiro
        parceiro_id = escopo_parceiro_id()
        if parceiro_id is not None and coletor.parceiro_id != parceiro_id:
            return jsonify({"erro": "Acesso negado"}), 403

        from banco_dados.utils.validacao import sanitizar_dados_entrada, validar_dados_requisicao

        dados = request.get_json()
        dados = validar_dados_requisicao(dados)

        # Sanitizar dados de entrada
        campos_string = ['localizacao', 'status', 'observacoes']
        dados = sanitizar_dados_entrada(dados, campos_string)

        # Validar dados
        erros = validar_dados_coletor(dados, criar=False, db=db)
        if erros:
            raise ErroValidacao("Erros de validação", {"detalhes": erros})

        # Verificar se localização mudou (para geocodificação)
        localizacao_mudou = 'localizacao' in dados and dados['localizacao'] != coletor.localizacao
        coordenadas_fornecidas = 'latitude' in dados or 'longitude' in dados

        # Atualizar coletor
        coletor = atualizar_coletor(db, coletor, dados)

        # Emitir atualização via WebSocket
        try:
            from rotas.websocket import emitir_atualizacao_coletor
            emitir_atualizacao_coletor(coletor_para_dict(coletor))
        except Exception as e:
            logger.warning(f"Erro ao emitir atualização WebSocket: {e}")

        # Commit inicial do registro antes da geocodificação
        db.commit()

        # Geocodificação automática se necessário (APÓS commit)
        if not coordenadas_fornecidas and (localizacao_mudou or not coletor.latitude or not coletor.longitude):
            try:
                from banco_dados.geocodificacao import geocodificar_endereco
                resultado = geocodificar_endereco(
                    coletor.localizacao,
                    cidade="Brasília",
                    estado="DF"
                )
                if resultado:
                    coletor.latitude = resultado['latitude']
                    coletor.longitude = resultado['longitude']
                    db.commit()
                    logger.info(f"Coordenadas geocodificadas automaticamente para coletor {coletor.id}")
            except Exception as e:
                logger.warning(f"Geocodificação automática falhou para coletor {coletor.id}: {e}")

        return jsonify(coletor_para_dict(coletor))
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()


@coletores_bp.route('/coletor/<int:coletor_id>', methods=['DELETE'])
@admin_required
@decorators.rate_limit("5 per minute")
def deletar_lixeira(coletor_id):
    """Endpoint para deletar uma coletor (apenas admin)"""
    db = get_db()
    try:
        coletor = db.query(Coletor).filter(Coletor.id == coletor_id).first()
        if not coletor:
            raise ErroNaoEncontrado("Coletor", coletor_id)

        db.delete(coletor)
        db.commit()

        return jsonify({"mensagem": "Coletor deletada com sucesso"}), 200
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()


@coletores_bp.route('/coletor/<int:coletor_id>/geocodificar', methods=['POST'])
@login_required
def geocodificar_lixeira(coletor_id):
    """Endpoint para geocodificar coletor manualmente"""
    db = get_db()
    try:
        coletor = db.query(Coletor).filter(Coletor.id == coletor_id).first()
        if not coletor:
            raise ErroNaoEncontrado("Coletor", coletor_id)

        # [SEGURANÇA] Verificar se o usuário tem acesso ao coletor deste parceiro
        parceiro_id = escopo_parceiro_id()
        if parceiro_id is not None and coletor.parceiro_id != parceiro_id:
            return jsonify({"erro": "Acesso negado"}), 403

        from banco_dados.geocodificacao import geocodificar_coletor
        sucesso, mensagem = geocodificar_coletor(db, coletor_id)

        if sucesso:
            db.refresh(coletor)
            return jsonify({
                "mensagem": f"Coordenadas atualizadas: ({coletor.latitude}, {coletor.longitude})"
            })
        else:
            raise ErroValidacao(mensagem)
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()

