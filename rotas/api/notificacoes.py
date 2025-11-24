"""
Rotas de Notificações - Dashboard-TRONIK
=========================================
Endpoints para operações com notificações.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from rotas.api.decorators import admin_required, get_db
from banco_dados.modelos import Notificacao
from banco_dados.serializers import notificacao_para_dict
from banco_dados.utils import utc_now_naive
from banco_dados.utils.erros import tratar_erro_api, ErroNaoEncontrado, validar_requisicao_json
from banco_dados.utils.logger import obter_logger
from sqlalchemy.orm import joinedload

logger = obter_logger(__name__)

# Criar blueprint
notificacoes_bp = Blueprint('notificacoes', __name__)


@notificacoes_bp.route('/notificacoes', methods=['GET'])
@login_required
def listar_notificacoes():
    """Endpoint para listar notificações com filtros opcionais e paginação"""
    db = get_db()
    try:
        query = db.query(Notificacao).options(
            joinedload(Notificacao.coletor),
            joinedload(Notificacao.sensor)
        )
        
        # Filtros opcionais
        tipo = request.args.get('tipo')
        enviada = request.args.get('enviada')
        lida = request.args.get('lida')
        coletor_id = request.args.get('coletor_id', type=int)
        
        if tipo:
            query = query.filter(Notificacao.tipo == tipo)
        if enviada is not None:
            enviada_bool = enviada.lower() == 'true'
            query = query.filter(Notificacao.enviada == enviada_bool)
        if lida is not None:
            lida_bool = lida.lower() == 'true'
            query = query.filter(Notificacao.lida == lida_bool)
        if coletor_id:
            query = query.filter(Notificacao.coletor_id == coletor_id)
        
        # Ordenar por data (mais recentes primeiro)
        query = query.order_by(Notificacao.criada_em.desc())
        
        # Paginação
        # Parâmetros de paginação com validação
        pagina = request.args.get('pagina', type=int, default=1)
        if pagina < 1:
            pagina = 1
        if pagina > 1000:  # Limite máximo de páginas
            pagina = 1000
        
        por_pagina = request.args.get('por_pagina', type=int, default=50)
        limite = request.args.get('limite', type=int)  # Compatibilidade com código antigo
        
        if limite:
            por_pagina = limite
        
        # Validar por_pagina após possível ajuste por limite
        if por_pagina < 1:
            por_pagina = 1
        if por_pagina > 500:  # Limite máximo de itens por página
            por_pagina = 500
        
        total_count = query.count()
        offset = (pagina - 1) * por_pagina
        notificacoes = query.offset(offset).limit(por_pagina).all()
        
        resultado = [notificacao_para_dict(n) for n in notificacoes]
        
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


@notificacoes_bp.route('/notificacoes/processar-alertas', methods=['POST'])
@admin_required
def processar_alertas_endpoint():
    """Endpoint para processar alertas e enviar notificações (apenas admin)"""
    db = get_db()
    try:
        from banco_dados.notificacoes import processar_alertas
        
        stats = processar_alertas(db)
        
        return jsonify({
            "mensagem": "Alertas processados com sucesso",
            "estatisticas": stats
        })
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@notificacoes_bp.route('/notificacoes/<int:notificacao_id>/marcar-lida', methods=['PUT'])
@login_required
def marcar_notificacao_lida(notificacao_id):
    """Endpoint para marcar uma notificação como lida"""
    db = get_db()
    try:
        notificacao = db.query(Notificacao).filter(Notificacao.id == notificacao_id).first()
        if not notificacao:
            raise ErroNaoEncontrado("Notificação", notificacao_id)
        
        notificacao.lida = True
        notificacao.lida_em = utc_now_naive()
        db.commit()
        
        return jsonify({
            "mensagem": "Notificação marcada como lida",
            "notificacao": {
                "id": notificacao.id,
                "lida": notificacao.lida,
                "lida_em": notificacao.lida_em.isoformat() if notificacao.lida_em else None
            }
        })
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()


@notificacoes_bp.route('/notificacoes/pendentes-count', methods=['GET'])
@login_required
def contar_notificacoes_pendentes():
    """Endpoint para obter contagem de notificações pendentes (não lidas)"""
    db = get_db()
    try:
        count = db.query(Notificacao).filter(Notificacao.lida == False).count()
        return jsonify({"count": count})
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@notificacoes_bp.route('/notificacoes/status-agendamento', methods=['GET'])
@login_required
def status_agendamento():
    """Endpoint para obter status do agendamento automático"""
    try:
        from banco_dados.agendamento import obter_status_agendamento
        
        status = obter_status_agendamento()
        return jsonify(status)
    except Exception as e:
        return tratar_erro_api(e)

