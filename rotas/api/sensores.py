"""
Rotas de Sensores - Dashboard-TRONIK
====================================
Endpoints para operações CRUD de sensores.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from rotas.api.decorators import admin_required, get_db
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
def criar_sensor():
    """Endpoint para criar um novo sensor"""
    db = get_db()
    try:
        dados = request.get_json()
        validar_requisicao_json(dados)
        
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
def atualizar_sensor(sensor_id):
    """Endpoint para atualizar um sensor"""
    db = get_db()
    try:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        if not sensor:
            raise ErroNaoEncontrado("Sensor", sensor_id)
        
        dados = request.get_json()
        validar_requisicao_json(dados)
        
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

