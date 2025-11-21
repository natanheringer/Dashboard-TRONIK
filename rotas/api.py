"""
Rotas da API - Dashboard-TRONIK
==============================

Endpoints da API REST para comunicação com o frontend.
Gerencia todas as operações CRUD das lixeiras.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.orm import scoped_session, joinedload
from banco_dados.modelos import (
    Lixeira, Sensor, Coleta, Parceiro, TipoMaterial, TipoSensor, TipoColetor, Notificacao
)
from banco_dados.seguranca import (
    validar_coordenadas, validar_nivel_preenchimento, sanitizar_string,
    validar_latitude, validar_longitude, validar_quantidade_kg,
    validar_km_percorrido, validar_preco_combustivel, validar_tipo_operacao,
    validar_bateria
)
from datetime import datetime
from banco_dados.utils import utc_now_naive
import random
import logging
from flask import Response
from io import BytesIO

# Configurar logging
logger = logging.getLogger(__name__)

# Criar blueprint da API
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Rate limiter específico para API
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per hour"]
)

def admin_required(f):
    """Decorator para exigir que o usuário seja admin"""
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.admin:
            return jsonify({"erro": "Acesso negado. Apenas administradores."}), 403
        return f(*args, **kwargs)
    return decorated_function

# Função auxiliar para obter sessão do banco
def get_db():
    """Retorna uma sessão do banco de dados"""
    from flask import current_app
    SessionLocal = current_app.config.get('DATABASE_SESSION')
    if SessionLocal:
        return SessionLocal()
    else:
        # Fallback: criar sessão diretamente
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine('sqlite:///tronik.db')
        Session = sessionmaker(bind=engine)
        return Session()

# Função para converter Lixeira para dict
def lixeira_para_dict(lixeira):
    """Converte um objeto Lixeira para dicionário com novos campos"""
    return {
        "id": lixeira.id,
        "localizacao": lixeira.localizacao,
        "nivel_preenchimento": lixeira.nivel_preenchimento,
        "status": lixeira.status,
        "ultima_coleta": lixeira.ultima_coleta.isoformat() if lixeira.ultima_coleta else None,
        "latitude": lixeira.latitude,
        "longitude": lixeira.longitude,
        "parceiro": {
            "id": lixeira.parceiro.id,
            "nome": lixeira.parceiro.nome
        } if lixeira.parceiro else None,
        "tipo_material": {
            "id": lixeira.tipo_material.id,
            "nome": lixeira.tipo_material.nome
        } if lixeira.tipo_material else None
    }

# Função para converter Coleta para dict
def coleta_para_dict(coleta):
    """Converte um objeto Coleta para dicionário com todos os campos do CSV"""
    return {
        "id": coleta.id,
        "lixeira_id": coleta.lixeira_id,
        "data_hora": coleta.data_hora.isoformat() if coleta.data_hora else None,
        "volume_estimado": coleta.volume_estimado,
        "tipo_operacao": coleta.tipo_operacao,
        "km_percorrido": coleta.km_percorrido,
        "preco_combustivel": coleta.preco_combustivel,
        "lucro_por_kg": coleta.lucro_por_kg,
        "emissao_mtr": coleta.emissao_mtr,
        "tipo_coletor": {
            "id": coleta.tipo_coletor.id,
            "nome": coleta.tipo_coletor.nome
        } if coleta.tipo_coletor else None,
        "parceiro": {
            "id": coleta.parceiro.id,
            "nome": coleta.parceiro.nome
        } if coleta.parceiro else None,
        "lixeira": {
            "id": coleta.lixeira.id,
            "localizacao": coleta.lixeira.localizacao
        } if coleta.lixeira else None
    }

# Função para converter Sensor para dict
def sensor_para_dict(sensor):
    """Converte um objeto Sensor para dicionário"""
    return {
        "id": sensor.id,
        "lixeira_id": sensor.lixeira_id,
        "bateria": sensor.bateria,
        "ultimo_ping": sensor.ultimo_ping.isoformat() if sensor.ultimo_ping else None,
        "tipo_sensor": {
            "id": sensor.tipo_sensor.id,
            "nome": sensor.tipo_sensor.nome
        } if sensor.tipo_sensor else None,
        "lixeira": {
            "id": sensor.lixeira.id,
            "localizacao": sensor.lixeira.localizacao
        } if sensor.lixeira else None
    }

# Função de validação de dados da lixeira
def validar_lixeira(dados, criar=True, db=None):
    """Valida dados da lixeira com novos campos"""
    erros = []
    
    if criar:
        if 'localizacao' not in dados or not dados['localizacao']:
            erros.append("Campo 'localizacao' é obrigatório")
    else:
        if 'localizacao' in dados and not dados['localizacao']:
            erros.append("Campo 'localizacao' não pode ser vazio")
    
    if 'nivel_preenchimento' in dados:
        valido, erro = validar_nivel_preenchimento(dados['nivel_preenchimento'])
        if not valido:
            erros.append(erro)
    
    # Validar latitude
    if 'latitude' in dados and dados['latitude'] is not None:
        valido, erro = validar_latitude(dados['latitude'])
        if not valido:
            erros.append(erro)
    
    # Validar longitude
    if 'longitude' in dados and dados['longitude'] is not None:
        valido, erro = validar_longitude(dados['longitude'])
        if not valido:
            erros.append(erro)
    
    # Validar parceiro_id (se fornecido)
    if 'parceiro_id' in dados and dados['parceiro_id'] is not None and db:
        parceiro = db.query(Parceiro).filter(Parceiro.id == dados['parceiro_id']).first()
        if not parceiro:
            erros.append("Parceiro não encontrado")
    
    # Validar tipo_material_id (se fornecido)
    if 'tipo_material_id' in dados and dados['tipo_material_id'] is not None and db:
        tipo_material = db.query(TipoMaterial).filter(TipoMaterial.id == dados['tipo_material_id']).first()
        if not tipo_material:
            erros.append("Tipo de material não encontrado")
    
    return erros


# Função de validação de dados da coleta
def validar_coleta(dados, criar=True, db=None):
    """Valida dados da coleta com todos os campos do CSV"""
    erros = []
    
    if criar:
        if 'lixeira_id' not in dados or not dados['lixeira_id']:
            erros.append("Campo 'lixeira_id' é obrigatório")
        else:
            # Validar que lixeira existe
            if db:
                lixeira = db.query(Lixeira).filter(Lixeira.id == dados['lixeira_id']).first()
                if not lixeira:
                    erros.append("Lixeira não encontrada")
        
        if 'data_hora' not in dados or not dados['data_hora']:
            erros.append("Campo 'data_hora' é obrigatório")
    
    # Validar quantidade/volume
    if 'volume_estimado' in dados and dados['volume_estimado'] is not None:
        valido, erro = validar_quantidade_kg(dados['volume_estimado'])
        if not valido:
            erros.append(erro)
    
    # Validar KM percorrido
    if 'km_percorrido' in dados and dados['km_percorrido'] is not None:
        valido, erro = validar_km_percorrido(dados['km_percorrido'])
        if not valido:
            erros.append(erro)
    
    # Validar preço combustível
    if 'preco_combustivel' in dados and dados['preco_combustivel'] is not None:
        valido, erro = validar_preco_combustivel(dados['preco_combustivel'])
        if not valido:
            erros.append(erro)
    
    # Validar tipo de operação
    if 'tipo_operacao' in dados and dados['tipo_operacao']:
        valido, erro = validar_tipo_operacao(dados['tipo_operacao'])
        if not valido:
            erros.append(erro)
    
    # Validar tipo_coletor_id (se fornecido)
    if 'tipo_coletor_id' in dados and dados['tipo_coletor_id'] is not None and db:
        tipo_coletor = db.query(TipoColetor).filter(TipoColetor.id == dados['tipo_coletor_id']).first()
        if not tipo_coletor:
            erros.append("Tipo de coletor não encontrado")
    
    # Validar parceiro_id (se fornecido)
    if 'parceiro_id' in dados and dados['parceiro_id'] is not None and db:
        parceiro = db.query(Parceiro).filter(Parceiro.id == dados['parceiro_id']).first()
        if not parceiro:
            erros.append("Parceiro não encontrado")
    
    return erros

# Função de validação de dados do sensor
def validar_sensor(dados, criar=True, db=None):
    """Valida dados do sensor"""
    erros = []
    
    if criar:
        if 'lixeira_id' not in dados or dados['lixeira_id'] is None:
            erros.append("Campo 'lixeira_id' é obrigatório")
    
    # Validar lixeira_id existe
    if 'lixeira_id' in dados and dados['lixeira_id'] is not None and db:
        lixeira = db.query(Lixeira).filter(Lixeira.id == dados['lixeira_id']).first()
        if not lixeira:
            erros.append("Lixeira não encontrada")
    
    # Validar tipo_sensor_id (se fornecido)
    if 'tipo_sensor_id' in dados and dados['tipo_sensor_id'] is not None and db:
        tipo_sensor = db.query(TipoSensor).filter(TipoSensor.id == dados['tipo_sensor_id']).first()
        if not tipo_sensor:
            erros.append("Tipo de sensor não encontrado")
    
    # Validar bateria
    if 'bateria' in dados and dados['bateria'] is not None:
        valido, erro = validar_bateria(dados['bateria'])
        if not valido:
            erros.append(erro)
    
    return erros

# ============================================================
# ENDPOINTS GET
# ============================================================

@api_bp.route('/lixeiras', methods=['GET'])
def listar_lixeiras():
    """Endpoint para obter todas as lixeiras com filtros opcionais"""
    db = get_db()
    try:
        # Carregar relacionamentos (eager loading)
        query = db.query(Lixeira).options(
            joinedload(Lixeira.parceiro),
            joinedload(Lixeira.tipo_material)
        )
        
        # Filtros opcionais
        parceiro_id = request.args.get('parceiro_id', type=int)
        tipo_material_id = request.args.get('tipo_material_id', type=int)
        status = request.args.get('status')
        
        if parceiro_id:
            query = query.filter(Lixeira.parceiro_id == parceiro_id)
        if tipo_material_id:
            query = query.filter(Lixeira.tipo_material_id == tipo_material_id)
        if status:
            query = query.filter(Lixeira.status == status)
        
        lixeiras = query.all()
        resultado = [lixeira_para_dict(l) for l in lixeiras]
        return jsonify(resultado)
    except Exception as e:
        logger.error(f"Erro ao listar lixeiras: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/lixeira/<int:lixeira_id>', methods=['GET'])
def obter_lixeira(lixeira_id):
    """Endpoint para obter uma lixeira específica"""
    db = get_db()
    try:
        # Carregar relacionamentos (eager loading)
        lixeira = db.query(Lixeira).options(
            joinedload(Lixeira.parceiro),
            joinedload(Lixeira.tipo_material)
        ).filter(Lixeira.id == lixeira_id).first()
        
        if lixeira:
            return jsonify(lixeira_para_dict(lixeira))
        else:
            return jsonify({"erro": "Lixeira não encontrada"}), 404
    except Exception as e:
        logger.error(f"Erro ao obter lixeira {lixeira_id}: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/configuracoes', methods=['GET'])
def obter_configuracoes():
    """Endpoint para obter as configurações do sistema"""
    configuracoes = {
        "nivel_alerta": 80,
        "nivel_critico": 95,
        "intervalo_atualizacao": 30,
        "timezone": "America/Sao_Paulo"
    }
    return jsonify(configuracoes)

@api_bp.route('/coletas', methods=['GET'])
def listar_coletas():
    """Endpoint para obter coletas com filtros opcionais"""
    db = get_db()
    try:
        # Carregar relacionamentos (eager loading)
        query = db.query(Coleta).options(
            joinedload(Coleta.lixeira),
            joinedload(Coleta.parceiro),
            joinedload(Coleta.tipo_coletor)
        )
        
        # Filtros opcionais
        lixeira_id = request.args.get('lixeira_id', type=int)
        parceiro_id = request.args.get('parceiro_id', type=int)
        tipo_operacao = request.args.get('tipo_operacao')
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        if lixeira_id:
            query = query.filter(Coleta.lixeira_id == lixeira_id)
        if parceiro_id:
            query = query.filter(Coleta.parceiro_id == parceiro_id)
        if tipo_operacao:
            query = query.filter(Coleta.tipo_operacao == tipo_operacao)
        if data_inicio:
            try:
                if len(data_inicio) == 10:
                    data_inicio_obj = datetime.fromisoformat(data_inicio + 'T00:00:00')
                else:
                    data_inicio_obj = datetime.fromisoformat(data_inicio.replace('Z', '+00:00'))
                query = query.filter(Coleta.data_hora >= data_inicio_obj)
            except:
                pass
        if data_fim:
            try:
                if len(data_fim) == 10:
                    data_fim_obj = datetime.fromisoformat(data_fim + 'T23:59:59')
                else:
                    data_fim_obj = datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
                query = query.filter(Coleta.data_hora <= data_fim_obj)
            except:
                pass
        
        coletas = query.order_by(Coleta.data_hora.desc()).all()
        resultado = [coleta_para_dict(c) for c in coletas]
        return jsonify(resultado)
    except Exception as e:
        logger.error(f"Erro ao listar coletas: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/historico', methods=['GET'])
def obter_historico():
    """Endpoint para obter histórico de coletas com filtro de data opcional"""
    db = get_db()
    try:
        # Obter parâmetro de filtro de data
        data_filtro = request.args.get('data')
        
        query = db.query(Coleta).options(
            joinedload(Coleta.lixeira),
            joinedload(Coleta.parceiro),
            joinedload(Coleta.tipo_coletor)
        )
        
        # Aplicar filtro de data se fornecido
        if data_filtro:
            try:
                if len(data_filtro) == 10:
                    # Formato YYYY-MM-DD
                    data_inicio = datetime.fromisoformat(data_filtro + 'T00:00:00')
                    data_fim = datetime.fromisoformat(data_filtro + 'T23:59:59')
                    query = query.filter(Coleta.data_hora >= data_inicio, Coleta.data_hora <= data_fim)
                else:
                    data_obj = datetime.fromisoformat(data_filtro.replace('Z', '+00:00'))
                    query = query.filter(Coleta.data_hora >= data_obj)
            except Exception as e:
                logger.warning(f"Erro ao processar filtro de data: {e}")
                pass
        
        coletas = query.order_by(Coleta.data_hora.desc()).limit(50).all()
        resultado = [coleta_para_dict(c) for c in coletas]
        return jsonify(resultado)
    except Exception as e:
        logger.error(f"Erro ao obter histórico: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/estatisticas', methods=['GET'])
def obter_estatisticas():
    """Endpoint para obter estatísticas gerais"""
    db = get_db()
    try:
        lixeiras = db.query(Lixeira).all()
        coletas = db.query(Coleta).all()
        
        total_lixeiras = len(lixeiras)
        lixeiras_alerta = len([l for l in lixeiras if l.nivel_preenchimento > 80])
        
        if total_lixeiras > 0:
            nivel_medio = sum(l.nivel_preenchimento for l in lixeiras) / total_lixeiras
        else:
            nivel_medio = 0.0
        
        hoje = datetime.now().date()  # Data atual local
        coletas_hoje = len([c for c in coletas if c.data_hora and c.data_hora.date() == hoje])
        
        estatisticas = {
            "total_lixeiras": total_lixeiras,
            "lixeiras_alerta": lixeiras_alerta,
            "nivel_medio": round(nivel_medio, 1),
            "coletas_hoje": coletas_hoje
        }
        
        return jsonify(estatisticas)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

# ============================================================
# ENDPOINTS POST, PUT, DELETE
# ============================================================

@api_bp.route('/lixeira', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def criar_lixeira():
    """Endpoint para criar uma nova lixeira"""
    db = get_db()
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({"erro": "Dados JSON não fornecidos"}), 400
        
        # Validar dados
        erros = validar_lixeira(dados, criar=True, db=db)
        if erros:
            return jsonify({"erro": "Erros de validação", "detalhes": erros}), 400
        
        # Sanitizar localização
        dados['localizacao'] = sanitizar_string(dados.get('localizacao', ''), max_length=150)
        if not dados['localizacao']:
            return jsonify({"erro": "Localização é obrigatória"}), 400
        
        # Processar coordenadas (latitude e longitude separadas)
        latitude = dados.get('latitude')
        longitude = dados.get('longitude')
        if latitude is not None and longitude is not None:
            if not validar_coordenadas(latitude, longitude):
                return jsonify({"erro": "Coordenadas inválidas"}), 400
        
        # Processar última coleta
        ultima_coleta = None
        if 'ultima_coleta' in dados and dados['ultima_coleta']:
            try:
                ultima_coleta = datetime.fromisoformat(dados['ultima_coleta'].replace('Z', '+00:00'))
            except:
                ultima_coleta = utc_now_naive()
        else:
            ultima_coleta = utc_now_naive()
        
        # Validar nível de preenchimento
        nivel = dados.get('nivel_preenchimento', 0.0)
        valido, erro = validar_nivel_preenchimento(nivel)
        if not valido:
            return jsonify({"erro": erro}), 400
        
        # Criar nova lixeira
        nova_lixeira = Lixeira(
            localizacao=dados['localizacao'],
            nivel_preenchimento=float(nivel),
            status=dados.get('status', 'OK'),
            ultima_coleta=ultima_coleta,
            latitude=latitude,
            longitude=longitude,
            parceiro_id=dados.get('parceiro_id'),
            tipo_material_id=dados.get('tipo_material_id')
        )
        
        db.add(nova_lixeira)
        db.commit()
        db.refresh(nova_lixeira)
        
        # Geocodificação automática se não tiver coordenadas
        if not latitude or not longitude:
            try:
                from banco_dados.geocodificacao import geocodificar_endereco
                resultado = geocodificar_endereco(
                    nova_lixeira.localizacao,
                    cidade="Brasília",
                    estado="DF"
                )
                if resultado:
                    nova_lixeira.latitude = resultado['latitude']
                    nova_lixeira.longitude = resultado['longitude']
                    db.commit()
                    db.refresh(nova_lixeira)
                    logger.info(f"Coordenadas geocodificadas automaticamente para lixeira {nova_lixeira.id}")
            except Exception as e:
                # Não falhar a criação se geocodificação falhar
                logger.warning(f"Geocodificação automática falhou para lixeira {nova_lixeira.id}: {e}")
        
        return jsonify(lixeira_para_dict(nova_lixeira)), 201
        
    except Exception as e:
        db.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/lixeira/<int:lixeira_id>', methods=['PUT'])
@login_required
@limiter.limit("20 per minute")
def atualizar_lixeira(lixeira_id):
    """Endpoint para atualizar uma lixeira"""
    db = get_db()
    try:
        lixeira = db.query(Lixeira).filter(Lixeira.id == lixeira_id).first()
        
        if not lixeira:
            return jsonify({"erro": "Lixeira não encontrada"}), 404
        
        dados = request.get_json()
        
        if not dados:
            return jsonify({"erro": "Dados JSON não fornecidos"}), 400
        
        # Validar dados
        erros = validar_lixeira(dados, criar=False, db=db)
        if erros:
            return jsonify({"erro": "Erros de validação", "detalhes": erros}), 400
        
        # Verificar se localização mudou (para geocodificação automática)
        localizacao_mudou = False
        localizacao_anterior = lixeira.localizacao
        
        # Atualizar campos
        if 'localizacao' in dados:
            nova_localizacao = sanitizar_string(dados['localizacao'], max_length=150)
            if nova_localizacao != lixeira.localizacao:
                localizacao_mudou = True
            lixeira.localizacao = nova_localizacao
        
        if 'nivel_preenchimento' in dados:
            lixeira.nivel_preenchimento = float(dados['nivel_preenchimento'])
        
        if 'status' in dados:
            lixeira.status = dados['status']
        
        if 'ultima_coleta' in dados and dados['ultima_coleta']:
            try:
                lixeira.ultima_coleta = datetime.fromisoformat(dados['ultima_coleta'].replace('Z', '+00:00'))
            except:
                pass
        
        # Se coordenadas foram fornecidas explicitamente, usar elas
        coordenadas_fornecidas = False
        if 'latitude' in dados:
            lixeira.latitude = dados['latitude'] if dados['latitude'] is not None else None
            coordenadas_fornecidas = True
        
        if 'longitude' in dados:
            lixeira.longitude = dados['longitude'] if dados['longitude'] is not None else None
            coordenadas_fornecidas = True
        
        if 'parceiro_id' in dados:
            lixeira.parceiro_id = dados['parceiro_id'] if dados['parceiro_id'] is not None else None
        
        if 'tipo_material_id' in dados:
            lixeira.tipo_material_id = dados['tipo_material_id'] if dados['tipo_material_id'] is not None else None
        
        db.commit()
        
        # Geocodificação automática se:
        # 1. Localização mudou E não tem coordenadas E coordenadas não foram fornecidas explicitamente
        # 2. Não tem coordenadas E coordenadas não foram fornecidas explicitamente
        if not coordenadas_fornecidas:
            precisa_geocodificar = (
                (localizacao_mudou and (not lixeira.latitude or not lixeira.longitude)) or
                (not lixeira.latitude or not lixeira.longitude)
            )
            
            if precisa_geocodificar:
                try:
                    from banco_dados.geocodificacao import geocodificar_endereco
                    resultado = geocodificar_endereco(
                        lixeira.localizacao,
                        cidade="Brasília",
                        estado="DF"
                    )
                    if resultado:
                        lixeira.latitude = resultado['latitude']
                        lixeira.longitude = resultado['longitude']
                        db.commit()
                        logger.info(f"Coordenadas geocodificadas automaticamente para lixeira {lixeira.id}")
                except Exception as e:
                    # Não falhar a atualização se geocodificação falhar
                    logger.warning(f"Geocodificação automática falhou para lixeira {lixeira.id}: {e}")
        
        db.refresh(lixeira)
        
        return jsonify(lixeira_para_dict(lixeira))
        
    except Exception as e:
        db.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/lixeira/<int:lixeira_id>', methods=['DELETE'])
@admin_required
@limiter.limit("5 per minute")
def deletar_lixeira(lixeira_id):
    """Endpoint para deletar uma lixeira"""
    db = get_db()
    try:
        lixeira = db.query(Lixeira).filter(Lixeira.id == lixeira_id).first()
        
        if not lixeira:
            return jsonify({"erro": "Lixeira não encontrada"}), 404
        
        db.delete(lixeira)
        db.commit()
        
        return jsonify({"mensagem": "Lixeira deletada com sucesso"}), 200
        
    except Exception as e:
        db.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/relatorios', methods=['GET'])
def obter_relatorios():
    """Endpoint para obter dados para relatórios com dados financeiros"""
    db = get_db()
    try:
        # Obter parâmetros de filtro
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        parceiro_id = request.args.get('parceiro_id', type=int)
        tipo_operacao = request.args.get('tipo_operacao')
        
        # Query base com eager loading
        query = db.query(Coleta).options(
            joinedload(Coleta.lixeira),
            joinedload(Coleta.parceiro),
            joinedload(Coleta.tipo_coletor)
        )
        
        # Aplicar filtros de data se fornecidos
        if data_inicio:
            try:
                if len(data_inicio) == 10:
                    data_inicio_obj = datetime.fromisoformat(data_inicio + 'T00:00:00')
                else:
                    data_inicio_obj = datetime.fromisoformat(data_inicio.replace('Z', '+00:00'))
                query = query.filter(Coleta.data_hora >= data_inicio_obj)
            except Exception as e:
                logger.warning(f"Erro ao processar data_inicio: {e}")
                pass
        
        if data_fim:
            try:
                if len(data_fim) == 10:
                    data_fim_obj = datetime.fromisoformat(data_fim + 'T23:59:59')
                else:
                    data_fim_obj = datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
                query = query.filter(Coleta.data_hora <= data_fim_obj)
            except Exception as e:
                logger.warning(f"Erro ao processar data_fim: {e}")
                pass
        
        # Filtros adicionais
        if parceiro_id:
            query = query.filter(Coleta.parceiro_id == parceiro_id)
        if tipo_operacao:
            query = query.filter(Coleta.tipo_operacao == tipo_operacao)
        
        coletas = query.order_by(Coleta.data_hora.desc()).all()
        
        # Agregar dados
        total_coletas = len(coletas)
        volume_total = sum(c.volume_estimado for c in coletas if c.volume_estimado) or 0.0
        km_total = sum(c.km_percorrido for c in coletas if c.km_percorrido) or 0.0
        
        # Cálculo correto do custo de combustível: (KM / consumo_km_por_litro) * preco_combustivel
        # Consumo padrão: 4 km/L (ajustável no futuro via configuração)
        CONSUMO_KM_POR_LITRO = 4.0
        custo_combustivel_total = sum(
            ((c.km_percorrido or 0) / CONSUMO_KM_POR_LITRO) * (c.preco_combustivel or 0) for c in coletas
        ) or 0.0
        lucro_total = sum(
            (c.volume_estimado or 0) * (c.lucro_por_kg or 0) for c in coletas
        ) or 0.0
        
        # Agrupar por lixeira
        coletas_por_lixeira = {}
        for coleta in coletas:
            lixeira_id = coleta.lixeira_id
            if lixeira_id not in coletas_por_lixeira:
                coletas_por_lixeira[lixeira_id] = {
                    "lixeira_id": lixeira_id,
                    "total_coletas": 0,
                    "volume_total": 0.0,
                    "km_total": 0.0,
                    "lucro_total": 0.0
                }
            coletas_por_lixeira[lixeira_id]["total_coletas"] += 1
            if coleta.volume_estimado:
                coletas_por_lixeira[lixeira_id]["volume_total"] += coleta.volume_estimado
            if coleta.km_percorrido:
                coletas_por_lixeira[lixeira_id]["km_total"] += coleta.km_percorrido
            if coleta.volume_estimado and coleta.lucro_por_kg:
                coletas_por_lixeira[lixeira_id]["lucro_total"] += coleta.volume_estimado * coleta.lucro_por_kg
        
        # Agrupar por parceiro
        coletas_por_parceiro = {}
        for coleta in coletas:
            parceiro_id = coleta.parceiro_id
            parceiro_nome = coleta.parceiro.nome if coleta.parceiro else 'Sem Parceiro'
            if parceiro_id not in coletas_por_parceiro:
                coletas_por_parceiro[parceiro_id] = {
                    "parceiro_id": parceiro_id,
                    "parceiro_nome": parceiro_nome,
                    "total_coletas": 0,
                    "volume_total": 0.0,
                    "lucro_total": 0.0
                }
            coletas_por_parceiro[parceiro_id]["total_coletas"] += 1
            if coleta.volume_estimado:
                coletas_por_parceiro[parceiro_id]["volume_total"] += coleta.volume_estimado
            if coleta.volume_estimado and coleta.lucro_por_kg:
                coletas_por_parceiro[parceiro_id]["lucro_total"] += coleta.volume_estimado * coleta.lucro_por_kg
        
        relatorio = {
            "periodo": {
                "data_inicio": data_inicio,
                "data_fim": data_fim
            },
            "resumo": {
                "total_coletas": total_coletas,
                "volume_total": round(volume_total, 2),
                "km_total": round(km_total, 2),
                "custo_combustivel_total": round(custo_combustivel_total, 2),
                "lucro_total": round(lucro_total, 2),
                "lucro_medio_por_coleta": round(lucro_total / total_coletas, 2) if total_coletas > 0 else 0.0,
                "coletas_por_lixeira": list(coletas_por_lixeira.values()),
                "coletas_por_parceiro": list(coletas_por_parceiro.values())
            },
            "detalhes": [coleta_para_dict(c) for c in coletas]
        }
        
        return jsonify(relatorio)
        
    except Exception as e:
        logger.error(f"Erro ao obter relatórios: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/relatorios/exportar-pdf', methods=['GET'])
@login_required
def exportar_relatorio_pdf():
    """Endpoint para exportar relatório em PDF"""
    db = get_db()
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        # Obter parâmetros de filtro
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        parceiro_id = request.args.get('parceiro_id', type=int)
        tipo_operacao = request.args.get('tipo_operacao')
        
        # Query base (mesma lógica do endpoint de relatórios)
        query = db.query(Coleta).options(
            joinedload(Coleta.lixeira),
            joinedload(Coleta.parceiro),
            joinedload(Coleta.tipo_coletor)
        )
        
        if data_inicio:
            try:
                if len(data_inicio) == 10:
                    data_inicio_obj = datetime.fromisoformat(data_inicio + 'T00:00:00')
                else:
                    data_inicio_obj = datetime.fromisoformat(data_inicio.replace('Z', '+00:00'))
                query = query.filter(Coleta.data_hora >= data_inicio_obj)
            except Exception:
                pass
        
        if data_fim:
            try:
                if len(data_fim) == 10:
                    data_fim_obj = datetime.fromisoformat(data_fim + 'T23:59:59')
                else:
                    data_fim_obj = datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
                query = query.filter(Coleta.data_hora <= data_fim_obj)
            except Exception:
                pass
        
        if parceiro_id:
            query = query.filter(Coleta.parceiro_id == parceiro_id)
        if tipo_operacao:
            query = query.filter(Coleta.tipo_operacao == tipo_operacao)
        
        coletas = query.order_by(Coleta.data_hora.desc()).all()
        
        # Calcular totais
        total_coletas = len(coletas)
        volume_total = sum(c.volume_estimado for c in coletas if c.volume_estimado) or 0.0
        km_total = sum(c.km_percorrido for c in coletas if c.km_percorrido) or 0.0
        CONSUMO_KM_POR_LITRO = 4.0
        custo_combustivel_total = sum(
            ((c.km_percorrido or 0) / CONSUMO_KM_POR_LITRO) * (c.preco_combustivel or 0) for c in coletas
        ) or 0.0
        lucro_total = sum(
            (c.volume_estimado or 0) * (c.lucro_por_kg or 0) for c in coletas
        ) or 0.0
        
        # Criar PDF em memória
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#27ae60'),
            spaceAfter=12,
            alignment=1  # Center
        )
        
        # Conteúdo do PDF
        story = []
        
        # Título
        story.append(Paragraph("Relatório de Coletas - TRONIK Recicla", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Período
        periodo_text = f"Período: {data_inicio or 'Início'} a {data_fim or 'Fim'}"
        story.append(Paragraph(periodo_text, styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        
        # Resumo
        resumo_data = [
            ['Métrica', 'Valor'],
            ['Total de Coletas', str(total_coletas)],
            ['Volume Total (kg)', f'{volume_total:.2f}'],
            ['KM Total', f'{km_total:.2f}'],
            ['Custo Combustível', f'R$ {custo_combustivel_total:.2f}'],
            ['Lucro Total', f'R$ {lucro_total:.2f}'],
        ]
        
        resumo_table = Table(resumo_data, colWidths=[3*inch, 2*inch])
        resumo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        story.append(Paragraph("<b>Resumo</b>", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))
        story.append(resumo_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Detalhamento (limitado a 50 coletas para não sobrecarregar o PDF)
        if coletas:
            story.append(Paragraph("<b>Detalhamento de Coletas</b>", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            # Cabeçalho da tabela
            detalhes_data = [['Data', 'Lixeira', 'Volume (kg)', 'KM', 'Lucro (R$)']]
            
            # Adicionar até 50 coletas
            for coleta in coletas[:50]:
                data_str = coleta.data_hora.strftime('%d/%m/%Y %H:%M') if coleta.data_hora else 'N/A'
                lixeira_nome = coleta.lixeira.localizacao if coleta.lixeira else 'N/A'
                volume = f'{coleta.volume_estimado:.2f}' if coleta.volume_estimado else '0.00'
                km = f'{coleta.km_percorrido:.2f}' if coleta.km_percorrido else '0.00'
                lucro = f'{(coleta.volume_estimado or 0) * (coleta.lucro_por_kg or 0):.2f}'
                
                detalhes_data.append([data_str, lixeira_nome[:30], volume, km, lucro])
            
            if len(coletas) > 50:
                detalhes_data.append(['...', f'({len(coletas) - 50} coletas adicionais)', '', '', ''])
            
            detalhes_table = Table(detalhes_data, colWidths=[1.2*inch, 2*inch, 1*inch, 0.8*inch, 1*inch])
            detalhes_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]))
            
            story.append(detalhes_table)
        
        # Gerar PDF
        doc.build(story)
        
        # Retornar PDF
        buffer.seek(0)
        filename = f'relatorio_tronik_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

# ============================================================
# NOVOS ENDPOINTS: TIPOS E PARCEIROS
# ============================================================

@api_bp.route('/parceiros', methods=['GET'])
def listar_parceiros():
    """Endpoint para listar todos os parceiros"""
    db = get_db()
    try:
        parceiros = db.query(Parceiro).filter(Parceiro.ativo == True).all()
        resultado = [
            {
                "id": p.id,
                "nome": p.nome,
                "ativo": p.ativo,
                "criado_em": p.criado_em.isoformat() if p.criado_em else None
            }
            for p in parceiros
        ]
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/lixeira/<int:lixeira_id>/geocodificar', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def geocodificar_lixeira_endpoint(lixeira_id):
    """Endpoint para geocodificar uma lixeira manualmente"""
    db = get_db()
    try:
        from banco_dados.geocodificacao import geocodificar_lixeira
        
        lixeira = db.query(Lixeira).filter(Lixeira.id == lixeira_id).first()
        
        if not lixeira:
            return jsonify({"erro": "Lixeira não encontrada"}), 404
        
        # Obter parâmetros opcionais
        dados = request.get_json() or {}
        cidade = dados.get('cidade', 'Brasília')
        estado = dados.get('estado', 'DF')
        forcar = dados.get('forcar', False)
        
        # Geocodificar
        sucesso, mensagem = geocodificar_lixeira(
            db,
            lixeira_id,
            cidade=cidade,
            estado=estado,
            forcar_atualizacao=forcar
        )
        
        if sucesso:
            db.refresh(lixeira)
            return jsonify({
                "mensagem": mensagem,
                "lixeira": lixeira_para_dict(lixeira)
            }), 200
        else:
            return jsonify({"erro": mensagem}), 400
            
    except Exception as e:
        logger.error(f"Erro ao geocodificar lixeira {lixeira_id}: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/tipos/material', methods=['GET'])
def listar_tipos_material():
    """Endpoint para listar todos os tipos de material"""
    db = get_db()
    try:
        tipos = db.query(TipoMaterial).all()
        resultado = [
            {
                "id": t.id,
                "nome": t.nome
            }
            for t in tipos
        ]
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/tipos/sensor', methods=['GET'])
def listar_tipos_sensor():
    """Endpoint para listar todos os tipos de sensor"""
    db = get_db()
    try:
        tipos = db.query(TipoSensor).all()
        resultado = [
            {
                "id": t.id,
                "nome": t.nome
            }
            for t in tipos
        ]
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/tipos/coletor', methods=['GET'])
def listar_tipos_coletor():
    """Endpoint para listar todos os tipos de coletor"""
    db = get_db()
    try:
        tipos = db.query(TipoColetor).all()
        resultado = [
            {
                "id": t.id,
                "nome": t.nome
            }
            for t in tipos
        ]
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

# ============================================================
# ENDPOINTS: SENSORES (CRUD)
# ============================================================

@api_bp.route('/sensores', methods=['GET'])
def listar_sensores():
    """Endpoint para listar todos os sensores com filtros opcionais"""
    db = get_db()
    try:
        # Carregar relacionamentos (eager loading)
        query = db.query(Sensor).options(
            joinedload(Sensor.lixeira),
            joinedload(Sensor.tipo_sensor)
        )
        
        # Filtros opcionais
        lixeira_id = request.args.get('lixeira_id', type=int)
        tipo_sensor_id = request.args.get('tipo_sensor_id', type=int)
        bateria_min = request.args.get('bateria_min', type=float)
        bateria_max = request.args.get('bateria_max', type=float)
        
        if lixeira_id:
            query = query.filter(Sensor.lixeira_id == lixeira_id)
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
        logger.error(f"Erro ao listar sensores: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/sensor/<int:sensor_id>', methods=['GET'])
def obter_sensor(sensor_id):
    """Endpoint para obter um sensor específico"""
    db = get_db()
    try:
        sensor = db.query(Sensor).options(
            joinedload(Sensor.lixeira),
            joinedload(Sensor.tipo_sensor)
        ).filter(Sensor.id == sensor_id).first()
        
        if not sensor:
            return jsonify({"erro": "Sensor não encontrado"}), 404
        
        return jsonify(sensor_para_dict(sensor))
    except Exception as e:
        logger.error(f"Erro ao obter sensor: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/sensor', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def criar_sensor():
    """Endpoint para criar um novo sensor"""
    db = get_db()
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({"erro": "Dados JSON não fornecidos"}), 400
        
        # Validar dados
        erros = validar_sensor(dados, criar=True, db=db)
        if erros:
            return jsonify({"erro": "Erros de validação", "detalhes": erros}), 400
        
        # Criar novo sensor
        novo_sensor = Sensor(
            lixeira_id=dados['lixeira_id'],
            tipo_sensor_id=dados.get('tipo_sensor_id'),
            bateria=dados.get('bateria', 100.0),
            ultimo_ping=utc_now_naive()
        )
        
        db.add(novo_sensor)
        db.commit()
        db.refresh(novo_sensor)
        
        # Carregar relacionamentos
        db.refresh(novo_sensor)
        novo_sensor = db.query(Sensor).options(
            joinedload(Sensor.lixeira),
            joinedload(Sensor.tipo_sensor)
        ).filter(Sensor.id == novo_sensor.id).first()
        
        return jsonify(sensor_para_dict(novo_sensor)), 201
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao criar sensor: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/sensor/<int:sensor_id>', methods=['PUT'])
@login_required
@limiter.limit("10 per minute")
def atualizar_sensor(sensor_id):
    """Endpoint para atualizar um sensor"""
    db = get_db()
    try:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        
        if not sensor:
            return jsonify({"erro": "Sensor não encontrado"}), 404
        
        dados = request.get_json()
        if not dados:
            return jsonify({"erro": "Dados JSON não fornecidos"}), 400
        
        # Validar dados
        erros = validar_sensor(dados, criar=False, db=db)
        if erros:
            return jsonify({"erro": "Erros de validação", "detalhes": erros}), 400
        
        # Atualizar campos
        if 'lixeira_id' in dados:
            sensor.lixeira_id = dados['lixeira_id']
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
            joinedload(Sensor.lixeira),
            joinedload(Sensor.tipo_sensor)
        ).filter(Sensor.id == sensor_id).first()
        
        return jsonify(sensor_para_dict(sensor))
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao atualizar sensor: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/sensor/<int:sensor_id>', methods=['DELETE'])
@admin_required
@limiter.limit("10 per minute")
def deletar_sensor(sensor_id):
    """Endpoint para deletar um sensor (apenas admin)"""
    db = get_db()
    try:
        sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
        
        if not sensor:
            return jsonify({"erro": "Sensor não encontrado"}), 404
        
        db.delete(sensor)
        db.commit()
        
        return jsonify({"mensagem": "Sensor deletado com sucesso"}), 200
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao deletar sensor: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

# ============================================================
# ENDPOINT: CRIAR COLETA
# ============================================================

@api_bp.route('/coleta', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def criar_coleta():
    """Endpoint para criar uma nova coleta"""
    db = get_db()
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({"erro": "Dados JSON não fornecidos"}), 400
        
        # Validar dados
        erros = validar_coleta(dados, criar=True, db=db)
        if erros:
            return jsonify({"erro": "Erros de validação", "detalhes": erros}), 400
        
        # Processar data_hora
        data_hora = None
        if 'data_hora' in dados and dados['data_hora']:
            try:
                data_hora = datetime.fromisoformat(dados['data_hora'].replace('Z', '+00:00'))
            except:
                data_hora = utc_now_naive()
        else:
            data_hora = utc_now_naive()
        
        # Criar nova coleta
        nova_coleta = Coleta(
            lixeira_id=dados['lixeira_id'],
            data_hora=data_hora,
            volume_estimado=dados.get('volume_estimado'),
            tipo_operacao=dados.get('tipo_operacao'),
            km_percorrido=dados.get('km_percorrido'),
            preco_combustivel=dados.get('preco_combustivel'),
            lucro_por_kg=dados.get('lucro_por_kg'),
            emissao_mtr=dados.get('emissao_mtr', False),
            tipo_coletor_id=dados.get('tipo_coletor_id'),
            parceiro_id=dados.get('parceiro_id')
        )
        
        db.add(nova_coleta)
        db.commit()
        db.refresh(nova_coleta)
        
        return jsonify(coleta_para_dict(nova_coleta)), 201
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao criar coleta: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

# ============================================================
# ENDPOINTS DE SIMULAÇÃO
# ============================================================

@api_bp.route('/lixeiras/simular-niveis', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def simular_niveis():
    """Endpoint para simular alterações nos níveis das lixeiras.
    Ajusta aleatoriamente o nível de preenchimento de todas as lixeiras,
    dentro de um intervalo seguro, mantendo valores entre 0 e 100.
    """
    db = get_db()
    try:
        params = request.get_json() or {}
        # Intensidade controla o delta máximo de alteração por passo
        delta_max = float(params.get('delta_max', 10))  # padrão: até +10/-5
        reduzir_max = float(params.get('reduzir_max', 5))

        lixeiras = db.query(Lixeira).all()
        atualizadas = []
        agora = utc_now_naive()
        for l in lixeiras:
            # Delta positivo maior que negativo para simular enchimento gradual
            delta = random.uniform(-reduzir_max, delta_max)
            novo_nivel = max(0.0, min(100.0, (l.nivel_preenchimento or 0.0) + delta))
            l.nivel_preenchimento = round(novo_nivel, 1)
            # Atualiza última coleta como "última atualização" para fins de exibição
            l.ultima_coleta = agora
            atualizadas.append(l)

        db.commit()
        return jsonify({
            "mensagem": "Níveis simulados com sucesso",
            "total_atualizadas": len(atualizadas),
            "lixeiras": [lixeira_para_dict(l) for l in atualizadas]
        })
    except Exception as e:
        db.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

# ============================================================
# ENDPOINTS: NOTIFICAÇÕES
# ============================================================

@api_bp.route('/notificacoes', methods=['GET'])
@login_required
def listar_notificacoes():
    """Endpoint para listar notificações com filtros opcionais"""
    db = get_db()
    try:
        query = db.query(Notificacao).options(
            joinedload(Notificacao.lixeira),
            joinedload(Notificacao.sensor)
        )
        
        # Filtros opcionais
        tipo = request.args.get('tipo')
        enviada = request.args.get('enviada')
        lida = request.args.get('lida')
        lixeira_id = request.args.get('lixeira_id', type=int)
        
        if tipo:
            query = query.filter(Notificacao.tipo == tipo)
        if enviada is not None:
            enviada_bool = enviada.lower() == 'true'
            query = query.filter(Notificacao.enviada == enviada_bool)
        if lida is not None:
            lida_bool = lida.lower() == 'true'
            query = query.filter(Notificacao.lida == lida_bool)
        if lixeira_id:
            query = query.filter(Notificacao.lixeira_id == lixeira_id)
        
        # Ordenar por data (mais recentes primeiro)
        query = query.order_by(Notificacao.criada_em.desc())
        
        # Limitar resultados (opcional)
        limite = request.args.get('limite', type=int, default=50)
        notificacoes = query.limit(limite).all()
        
        resultado = [{
            "id": n.id,
            "tipo": n.tipo,
            "titulo": n.titulo,
            "mensagem": n.mensagem,
            "enviada": n.enviada,
            "enviada_em": n.enviada_em.isoformat() if n.enviada_em else None,
            "lida": n.lida if hasattr(n, 'lida') else False,
            "lida_em": n.lida_em.isoformat() if hasattr(n, 'lida_em') and n.lida_em else None,
            "criada_em": n.criada_em.isoformat() if n.criada_em else None,
            "lixeira": {
                "id": n.lixeira.id,
                "localizacao": n.lixeira.localizacao
            } if n.lixeira else None,
            "sensor": {
                "id": n.sensor.id,
                "bateria": n.sensor.bateria
            } if n.sensor else None
        } for n in notificacoes]
        
        return jsonify(resultado)
    except Exception as e:
        logger.error(f"Erro ao listar notificações: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/notificacoes/processar-alertas', methods=['POST'])
@admin_required
@limiter.limit("5 per minute")
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
        logger.error(f"Erro ao processar alertas: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/notificacoes/<int:notificacao_id>/marcar-lida', methods=['PUT'])
@login_required
def marcar_notificacao_lida(notificacao_id):
    """Endpoint para marcar uma notificação como lida"""
    db = get_db()
    try:
        notificacao = db.query(Notificacao).filter(Notificacao.id == notificacao_id).first()
        
        if not notificacao:
            return jsonify({"erro": "Notificação não encontrada"}), 404
        
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
        logger.error(f"Erro ao marcar notificação como lida: {e}")
        db.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/notificacoes/pendentes-count', methods=['GET'])
@login_required
def contar_notificacoes_pendentes():
    """Endpoint para obter contagem de notificações pendentes (não lidas)"""
    db = get_db()
    try:
        count = db.query(Notificacao).filter(Notificacao.lida == False).count()
        return jsonify({"count": count})
    except Exception as e:
        logger.error(f"Erro ao contar notificações pendentes: {e}")
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/notificacoes/status-agendamento', methods=['GET'])
@login_required
def status_agendamento():
    """Endpoint para obter status do agendamento automático"""
    try:
        from banco_dados.agendamento import obter_status_agendamento
        
        status = obter_status_agendamento()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Erro ao obter status do agendamento: {e}")
        return jsonify({"erro": str(e)}), 500
