"""
Rotas Auxiliares - Dashboard-TRONIK
====================================
Endpoints auxiliares (estatísticas, tipos, parceiros, configurações).
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from rotas.api.decorators import get_db
from banco_dados.modelos import Coletor, Coleta, Parceiro, TipoMaterial, TipoSensor, TipoColetor, Sensor
from banco_dados.utils.cache import obter_cache
from banco_dados.utils.erros import tratar_erro_api
from banco_dados.utils.logger import obter_logger
from datetime import datetime
import random

logger = obter_logger(__name__)

# Criar blueprint
auxiliares_bp = Blueprint('auxiliares', __name__)


@auxiliares_bp.route('/estatisticas', methods=['GET'])
def obter_estatisticas():
    """Endpoint para obter estatísticas gerais"""
    db = get_db()
    try:
        # Usar cache para estatísticas (TTL: 5 minutos)
        cache = obter_cache()
        
        def calcular_estatisticas():
            coletores = db.query(Coletor).all()
            coletas = db.query(Coleta).all()
            sensores = db.query(Sensor).all()
            
            total_lixeiras = len(coletores)
            lixeiras_alerta = len([l for l in coletores if l.nivel_preenchimento > 80])
            
            if total_lixeiras > 0:
                nivel_medio = sum(l.nivel_preenchimento for l in coletores) / total_lixeiras
            else:
                nivel_medio = 0.0
            
            hoje = datetime.now().date()
            coletas_hoje = len([c for c in coletas if c.data_hora and c.data_hora.date() == hoje])
            
            sensores_ativos = len([s for s in sensores if s.bateria > 0])
            sensores_bateria_baixa = len([s for s in sensores if s.bateria < 20])
            
            return {
                "total_lixeiras": total_lixeiras,
                "lixeiras_alerta": lixeiras_alerta,
                "nivel_medio": round(nivel_medio, 1),
                "coletas_hoje": coletas_hoje,
                "sensores_ativos": sensores_ativos,
                "sensores_bateria_baixa": sensores_bateria_baixa
            }
        
        # Obter do cache ou calcular
        estatisticas = cache.obter_ou_calcular('estatisticas', calcular_estatisticas, ttl_segundos=300)
        
        return jsonify(estatisticas)
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@auxiliares_bp.route('/configuracoes', methods=['GET'])
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
def listar_parceiros():
    """Endpoint para listar todos os parceiros (com cache)"""
    db = get_db()
    try:
        # Usar cache para parceiros (TTL: 1 hora)
        cache = obter_cache()
        
        def buscar_parceiros():
            parceiros = db.query(Parceiro).filter(Parceiro.ativo == True).all()
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
@login_required
def simular_niveis():
    """Endpoint para simular mudança de níveis de coletores"""
    db = get_db()
    try:
        dados = request.get_json()
        if not dados or 'coletores' not in dados:
            return jsonify({"erro": "Dados inválidos. Esperado: {'coletores': [...]}"}), 400
        
        lixeiras_atualizadas = []
        
        for item in dados['coletores']:
            coletor_id = item.get('id')
            novo_nivel = item.get('nivel')
            
            if not coletor_id or novo_nivel is None:
                continue
            
            coletor = db.query(Coletor).filter(Coletor.id == coletor_id).first()
            if coletor:
                # Atualizar nível
                coletor.nivel_preenchimento = float(novo_nivel)
                
                # Atualizar status baseado no nível
                if coletor.nivel_preenchimento >= 95:
                    coletor.status = "CHEIA"
                elif coletor.nivel_preenchimento > 80:
                    coletor.status = "ALERTA"
                else:
                    coletor.status = "OK"
                
                lixeiras_atualizadas.append({
                    "id": coletor.id,
                    "nivel_preenchimento": coletor.nivel_preenchimento,
                    "status": coletor.status
                })
        
        db.commit()
        
        # Invalidar cache de estatísticas
        cache = obter_cache()
        cache.invalidar('estatisticas')
        
        return jsonify({
            "mensagem": f"{len(lixeiras_atualizadas)} coletor(s) atualizada(s)",
            "coletores": lixeiras_atualizadas
        })
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()

