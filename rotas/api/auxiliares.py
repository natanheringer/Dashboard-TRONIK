"""
Rotas Auxiliares - Dashboard-TRONIK
====================================
Endpoints auxiliares (estatísticas, tipos, parceiros, configurações).
"""

from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required

from banco_dados.modelos import (
    Coleta,
    Coletor,
    Parceiro,
    Sensor,
    TipoColetor,
    TipoMaterial,
    TipoSensor,
)
from banco_dados.utils.cache import obter_cache
from banco_dados.utils.erros import tratar_erro_api
from banco_dados.utils.logger import obter_logger
from rotas.api import decorators
from rotas.api.decorators import escopo_parceiro_id, get_db

logger = obter_logger(__name__)

# Criar blueprint
auxiliares_bp = Blueprint('auxiliares', __name__)


@auxiliares_bp.route('/health', methods=['GET'])
def health_check():
    """Endpoint simples para health check (sem autenticação)"""
    return jsonify({"status": "ok", "service": "dashboard-tronik"}), 200


@auxiliares_bp.route('/estatisticas', methods=['GET'])
@login_required
@decorators.rate_limit("30 per minute")
def obter_estatisticas():
    """Endpoint para obter estatísticas gerais"""
    db = get_db()
    try:
        parceiro_id = escopo_parceiro_id()
        cache = obter_cache()
        cache_key = f"estatisticas:{parceiro_id}" if parceiro_id is not None else "estatisticas"

        def calcular_estatisticas():
            q_coletores = db.query(Coletor)
            if parceiro_id is not None:
                q_coletores = q_coletores.filter(Coletor.parceiro_id == parceiro_id)
            coletores = q_coletores.all()

            if parceiro_id is not None:
                coletor_ids = [c.id for c in coletores]
                coletas = (
                    db.query(Coleta).filter(Coleta.coletor_id.in_(coletor_ids)).all()
                    if coletor_ids
                    else []
                )
                sensores = (
                    db.query(Sensor).filter(Sensor.coletor_id.in_(coletor_ids)).all()
                    if coletor_ids
                    else []
                )
            else:
                coletas = db.query(Coleta).all()
                sensores = db.query(Sensor).all()

            total_coletores = len(coletores)
            coletores_alerta = len([c for c in coletores if c.nivel_preenchimento > 80])

            if total_coletores > 0:
                nivel_medio = sum(c.nivel_preenchimento for c in coletores) / total_coletores
            else:
                nivel_medio = 0.0

            hoje = datetime.now().date()
            coletas_hoje = len([c for c in coletas if c.data_hora and c.data_hora.date() == hoje])

            sensores_ativos = len([s for s in sensores if s.bateria > 0])
            sensores_bateria_baixa = len([s for s in sensores if s.bateria < 20])

            return {
                "total_coletores": total_coletores,
                "coletores_alerta": coletores_alerta,
                "nivel_medio": round(nivel_medio, 1),
                "coletas_hoje": coletas_hoje,
                "sensores_ativos": sensores_ativos,
                "sensores_bateria_baixa": sensores_bateria_baixa,
            }

        estatisticas = cache.obter_ou_calcular(cache_key, calcular_estatisticas, ttl_segundos=300)

        return jsonify(estatisticas)
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@auxiliares_bp.route('/configuracoes', methods=['GET'])
@login_required
def obter_configuracoes():
    """Endpoint para obter as configurações do sistema"""
    configuracoes = {
        "nivel_alerta": 80,
        "nivel_critico": 95,
        "intervalo_atualizacao": 30,
        "timezone": "America/Sao_Paulo",
        "niveis_alerta": {
            "lixeira_cheia": 80.0,
            "bateria_baixa": 20.0
        },
        "consumo_km_por_litro": 4.0
    }
    return jsonify(configuracoes)


@auxiliares_bp.route('/parceiros', methods=['GET'])
@login_required
def listar_parceiros():
    """Endpoint para listar todos os parceiros (com cache)"""
    db = get_db()
    try:
        # Usar cache para parceiros (TTL: 1 hora)
        cache = obter_cache()

        def buscar_parceiros():
            parceiros = db.query(Parceiro).filter(Parceiro.ativo).all()
            return [
                {
                    "id": p.id,
                    "nome": p.nome,
                    "ativo": p.ativo,
                    "criado_em": p.criado_em.isoformat() if p.criado_em else None
                }
                for p in parceiros
            ]

        resultado = cache.obter_ou_calcular('parceiros', buscar_parceiros, ttl_segundos=3600)
        return jsonify(resultado)
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@auxiliares_bp.route('/tipos/material', methods=['GET'])
@login_required
def listar_tipos_material():
    """Endpoint para listar todos os tipos de material (com cache)"""
    db = get_db()
    try:
        cache = obter_cache()

        def buscar_tipos():
            tipos = db.query(TipoMaterial).all()
            return [{"id": t.id, "nome": t.nome} for t in tipos]

        resultado = cache.obter_ou_calcular('tipos_material', buscar_tipos, ttl_segundos=3600)
        return jsonify(resultado)
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@auxiliares_bp.route('/tipos/sensor', methods=['GET'])
@login_required
def listar_tipos_sensor():
    """Endpoint para listar todos os tipos de sensor (com cache)"""
    db = get_db()
    try:
        cache = obter_cache()

        def buscar_tipos():
            tipos = db.query(TipoSensor).all()
            return [{"id": t.id, "nome": t.nome} for t in tipos]

        resultado = cache.obter_ou_calcular('tipos_sensor', buscar_tipos, ttl_segundos=3600)
        return jsonify(resultado)
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@auxiliares_bp.route('/tipos/coletor', methods=['GET'])
@login_required
def listar_tipos_coletor():
    """Endpoint para listar todos os tipos de coletor (com cache)"""
    db = get_db()
    try:
        cache = obter_cache()

        def buscar_tipos():
            tipos = db.query(TipoColetor).all()
            return [{"id": t.id, "nome": t.nome} for t in tipos]

        resultado = cache.obter_ou_calcular('tipos_coletor', buscar_tipos, ttl_segundos=3600)
        return jsonify(resultado)
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@auxiliares_bp.route('/coletores/simular-niveis', methods=['POST'])
@decorators.admin_required
@decorators.rate_limit("10 per minute")
def simular_niveis():
    """Endpoint para simular mudança de níveis de coletores"""
    db = get_db()
    try:
        from banco_dados.utils.validacao import (
            validar_dados_requisicao,
            validar_tipo_campo,
        )

        dados = request.get_json()
        dados = validar_dados_requisicao(dados, ['coletores'])

        # Validar estrutura
        validar_tipo_campo(dados.get('coletores'), list, 'coletores')

        if not dados.get('coletores'):
            return jsonify({"erro": "Lista de coletores não pode estar vazia"}), 400

        coletores_atualizados = []

        for item in dados['coletores']:
            # Validar estrutura do item
            if not isinstance(item, dict):
                continue

            coletor_id = item.get('id')
            novo_nivel = item.get('nivel')

            if not coletor_id or novo_nivel is None:
                continue

            # Validar tipos
            try:
                coletor_id = int(coletor_id)
                novo_nivel = float(novo_nivel)
            except (ValueError, TypeError):
                continue

            # Validar range do nível
            if novo_nivel < 0 or novo_nivel > 100:
                continue

            coletor = db.query(Coletor).filter(Coletor.id == coletor_id).first()
            if coletor:
                # Atualizar nível
                coletor.nivel_preenchimento = novo_nivel

                # Atualizar status baseado no nível
                if coletor.nivel_preenchimento >= 95:
                    coletor.status = "CHEIA"
                elif coletor.nivel_preenchimento > 80:
                    coletor.status = "ALERTA"
                else:
                    coletor.status = "OK"

                coletores_atualizados.append({
                    "id": coletor.id,
                    "nivel_preenchimento": coletor.nivel_preenchimento,
                    "status": coletor.status
                })

        db.commit()

        # Invalidar cache de estatísticas
        cache = obter_cache()
        cache.invalidar('estatisticas')

        return jsonify({
            "mensagem": f"{len(coletores_atualizados)} coletor(s) atualizada(s)",
            "coletores": coletores_atualizados
        })
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()


@auxiliares_bp.route('/solicitacoes', methods=['GET'])
@login_required
def listar_solicitacoes():
    """Lista solicitações pendentes de coletores"""
    db = get_db()
    try:
        from banco_dados.modelos import SolicitacaoColetor
        solicitacoes = db.query(SolicitacaoColetor).order_by(SolicitacaoColetor.criado_em.desc()).all()
        return jsonify([s.to_dict() for s in solicitacoes])
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@auxiliares_bp.route('/solicitacoes/<int:id>/status', methods=['POST'])
@decorators.admin_required
def atualizar_status_solicitacao(id):
    """Aprova ou recusa uma solicitação"""
    db = get_db()
    try:
        from banco_dados.modelos import SolicitacaoColetor
        dados = request.get_json()
        novo_status = dados.get('status')

        if novo_status not in ['aprovado', 'recusado', 'pendente']:
            return jsonify({"erro": "Status inválido"}), 400

        solicitacao = db.query(SolicitacaoColetor).filter_by(id=id).first()
        if not solicitacao:
            return jsonify({"erro": "Solicitação não encontrada"}), 404

        solicitacao.status = novo_status
        db.commit()
        return jsonify({"mensagem": f"Solicitação {novo_status}", "solicitacao": solicitacao.to_dict()})
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()

