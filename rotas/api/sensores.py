"""
Rotas de Sensores - Dashboard-TRONIK
====================================
Endpoints para operações CRUD de sensores.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from rotas.api.decorators import admin_required, get_db
from rotas.api import decorators
from banco_dados.modelos import Sensor
from banco_dados.serializers import sensor_para_dict
from banco_dados.seguranca import validar_sensor
from banco_dados.utils import utc_now_naive
from banco_dados.utils.erros import tratar_erro_api, ErroNaoEncontrado, ErroValidacao, validar_requisicao_json
from banco_dados.utils.logger import obter_logger
from sqlalchemy.orm import joinedload
from datetime import datetime

logger = obter_logger(__name__)

# Criar blueprint
sensores_bp = Blueprint('sensores', __name__)


@sensores_bp.route('/sensores', methods=['GET'])
@decorators.rate_limit("30 per minute")
def listar_sensores():
    """Endpoint para listar todos os sensores com filtros opcionais"""
    db = get_db()
    try:
        query = db.query(Sensor).options(
            joinedload(Sensor.coletor),
            joinedload(Sensor.tipo_sensor)
        )
        
        # Filtros opcionais
        coletor_id = request.args.get('coletor_id', type=int)
        tipo_sensor_id = request.args.get('tipo_sensor_id', type=int)
        bateria_min = request.args.get('bateria_min', type=float)
        bateria_max = request.args.get('bateria_max', type=float)
        
        if coletor_id:
            query = query.filter(Sensor.coletor_id == coletor_id)
        if tipo_sensor_id:
            query = query.filter(Sensor.tipo_sensor_id == tipo_sensor_id)
        if bateria_min is not None:
            query = query.filter(Sensor.bateria >= bateria_min)
        if bateria_max is not None:
            query = query.filter(Sensor.bateria <= bateria_max)
        
        sensores = query.all()
        resultado = [sensor_para_dict(s) for s in sensores]
        return jsonify(resultado)
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@sensores_bp.route('/sensor/<int:sensor_id>', methods=['GET'])
def obter_sensor(sensor_id):
    """Endpoint para obter um sensor específico"""
    db = get_db()
    try:
        sensor = db.query(Sensor).options(
            joinedload(Sensor.coletor),
            joinedload(Sensor.tipo_sensor)
        ).filter(Sensor.id == sensor_id).first()
        
        if not sensor:
            raise ErroNaoEncontrado("Sensor", sensor_id)
        
        return jsonify(sensor_para_dict(sensor))
    except Exception as e:
        return tratar_erro_api(e)
    finally:
        db.close()


@sensores_bp.route('/sensor', methods=['POST'])
@login_required
@decorators.rate_limit("10 per minute")
def criar_sensor():
    """Endpoint para criar um novo sensor"""
    db = get_db()
    try:
        from banco_dados.utils.validacao import (
            validar_dados_requisicao, sanitizar_dados_entrada
        )
        
        dados = request.get_json()
        dados = validar_dados_requisicao(dados)
        
        # Sanitizar dados de entrada (sensores geralmente não têm strings, mas por segurança)
        dados = sanitizar_dados_entrada(dados, [])
        
        # Validar dados
        erros = validar_sensor(dados, criar=True, db=db)
        if erros:
            raise ErroValidacao("Erros de validação", {"detalhes": erros})
        
        # Criar novo sensor
        novo_sensor = Sensor(
            coletor_id=dados['coletor_id'],
            tipo_sensor_id=dados.get('tipo_sensor_id'),
            bateria=dados.get('bateria', 100.0),
            ultimo_ping=utc_now_naive()
        )
        
        db.add(novo_sensor)
        db.commit()
        db.refresh(novo_sensor)
        
        # Carregar relacionamentos
        novo_sensor = db.query(Sensor).options(
            joinedload(Sensor.coletor),
            joinedload(Sensor.tipo_sensor)
        ).filter(Sensor.id == novo_sensor.id).first()
        
        return jsonify(sensor_para_dict(novo_sensor)), 201
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()


@sensores_bp.route('/sensor/<int:sensor_id>', methods=['PUT'])
@login_required
@decorators.rate_limit("20 per minute")
def atualizar_sensor(sensor_id):
    """Endpoint para atualizar um sensor"""
    db = get_db()
    try:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise ErroNaoEncontrado("Sensor", sensor_id)
        
        from banco_dados.utils.validacao import (
            validar_dados_requisicao, sanitizar_dados_entrada
        )
        
        dados = request.get_json()
        dados = validar_dados_requisicao(dados)
        
        # Sanitizar dados de entrada
        dados = sanitizar_dados_entrada(dados, [])
        
        # Validar dados
        erros = validar_sensor(dados, criar=False, db=db)
        if erros:
            raise ErroValidacao("Erros de validação", {"detalhes": erros})
        
        # Atualizar campos
        if 'coletor_id' in dados:
            sensor.coletor_id = dados['coletor_id']
        if 'tipo_sensor_id' in dados:
            sensor.tipo_sensor_id = dados['tipo_sensor_id']
        if 'bateria' in dados:
            sensor.bateria = dados['bateria']
        if 'ultimo_ping' in dados and dados['ultimo_ping']:
            try:
                sensor.ultimo_ping = datetime.fromisoformat(dados['ultimo_ping'].replace('Z', '+00:00'))
            except:
                sensor.ultimo_ping = utc_now_naive()
        
        db.commit()
        db.refresh(sensor)
        
        # Carregar relacionamentos
        sensor = db.query(Sensor).options(
            joinedload(Sensor.coletor),
            joinedload(Sensor.tipo_sensor)
        ).filter(Sensor.id == sensor_id).first()
        
        return jsonify(sensor_para_dict(sensor))
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()


@sensores_bp.route('/sensor/<int:sensor_id>', methods=['DELETE'])
@admin_required
def deletar_sensor(sensor_id):
    """Endpoint para deletar um sensor (apenas admin)"""
    db = get_db()
    try:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise ErroNaoEncontrado("Sensor", sensor_id)
        
        db.delete(sensor)
        db.commit()
        
        return jsonify({"mensagem": "Sensor deletado com sucesso"}), 200
    except Exception as e:
        db.rollback()
        return tratar_erro_api(e)
    finally:
        db.close()

@sensores_bp.route('/sensor/telemetria', methods=['POST'])
@decorators.rate_limit("100 per minute")
def receber_telemetria():
    """Endpoint para receber dados de telemetria dos sensores hardware"""
    db = get_db()
    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Payload JSON vazio"}), 400
            
        sensor_id = dados.get('sensor_id')
        coletor_id = dados.get('coletor_id')
        nivel = dados.get('nivel_preenchimento')
        bateria = dados.get('bateria')
        
        if sensor_id is None or coletor_id is None or nivel is None or bateria is None:
            return jsonify({"erro": "Campos obrigatórios ausentes"}), 400
            
        from banco_dados.modelos import Coletor, Notificacao
        from datetime import timedelta
        
        coletor = db.query(Coletor).filter(Coletor.id == coletor_id).first()
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        
        if not coletor or not sensor:
            return jsonify({"erro": "Coletor ou sensor não encontrado"}), 404
            
        # Atualizar Coletor
        coletor.nivel_preenchimento = float(nivel)
        
        if coletor.nivel_preenchimento > 80.0:
            if coletor.status != 'QUEBRADA':
                coletor.status = 'CHEIA'
                
            limite_tempo = utc_now_naive() - timedelta(hours=24)
            notificacao_recente = db.query(Notificacao).filter(
                Notificacao.coletor_id == coletor.id,
                Notificacao.tipo == 'lixeira_cheia',
                Notificacao.criada_em >= limite_tempo
            ).first()
            
            if not notificacao_recente:
                from banco_dados.notificacoes import criar_notificacao
                criar_notificacao(
                    db=db,
                    tipo='lixeira_cheia',
                    titulo=f"Coletor #{coletor.id} - Nível Alto",
                    mensagem=f"O coletor em {coletor.localizacao} está com {coletor.nivel_preenchimento:.1f}% de preenchimento.",
                    coletor_id=coletor.id
                )
        elif coletor.nivel_preenchimento <= 80.0 and coletor.status == 'CHEIA':
            coletor.status = 'OK'
            
        # Atualizar Sensor
        sensor.bateria = float(bateria)
        sensor.ultimo_ping = utc_now_naive()
        
        if sensor.bateria < 20.0:
            limite_tempo = utc_now_naive() - timedelta(hours=24)
            notificacao_bateria = db.query(Notificacao).filter(
                Notificacao.sensor_id == sensor.id,
                Notificacao.tipo == 'bateria_baixa',
                Notificacao.criada_em >= limite_tempo
            ).first()
            
            if not notificacao_bateria:
                from banco_dados.notificacoes import criar_notificacao
                criar_notificacao(
                    db=db,
                    tipo='bateria_baixa',
                    titulo=f"Sensor #{sensor.id} - Bateria Baixa",
                    mensagem=f"O sensor do coletor em {coletor.localizacao} está com {sensor.bateria:.1f}% de bateria.",
                    sensor_id=sensor.id,
                    coletor_id=coletor.id
                )
                
        db.commit()
        return jsonify({"mensagem": "Telemetria registrada com sucesso", "status": "ok"}), 200
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro em telemetria: {e}")
        return tratar_erro_api(e)
    finally:
        db.close()
