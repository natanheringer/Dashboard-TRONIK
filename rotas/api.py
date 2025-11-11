"""
Rotas da API - Dashboard-TRONIK
==============================

Endpoints da API REST para comunicação com o frontend.
Gerencia todas as operações CRUD das lixeiras.
"""

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import scoped_session
from banco_dados.modelos import Lixeira, Sensor, Coleta
from datetime import datetime

# Criar blueprint da API
api_bp = Blueprint('api', __name__, url_prefix='/api')

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
    """Converte um objeto Lixeira para dicionário"""
    coords = {}
    if lixeira.coordenadas:
        try:
            lat, lon = lixeira.coordenadas.split(', ')
            coords = {"latitude": float(lat), "longitude": float(lon)}
        except:
            coords = {"latitude": 0.0, "longitude": 0.0}
    else:
        coords = {"latitude": 0.0, "longitude": 0.0}
    
    return {
        "id": lixeira.id,
        "localizacao": lixeira.localizacao,
        "nivel_preenchimento": lixeira.nivel_preenchimento,
        "status": lixeira.status,
        "ultima_coleta": lixeira.ultima_coleta.isoformat() if lixeira.ultima_coleta else None,
        "tipo": lixeira.tipo,
        "coordenadas": coords
    }

# Função para converter Coleta para dict
def coleta_para_dict(coleta):
    """Converte um objeto Coleta para dicionário"""
    return {
        "id": coleta.id,
        "id_lixeira": coleta.lixeira_id,
        "data_coleta": coleta.data_hora.isoformat() if coleta.data_hora else None,
        "volume_estimado": coleta.volume_estimado
    }

# Função de validação de dados da lixeira
def validar_lixeira(dados, criar=True):
    """Valida dados da lixeira"""
    erros = []
    
    if criar:
        if 'localizacao' not in dados or not dados['localizacao']:
            erros.append("Campo 'localizacao' é obrigatório")
    else:
        if 'localizacao' in dados and not dados['localizacao']:
            erros.append("Campo 'localizacao' não pode ser vazio")
    
    if 'nivel_preenchimento' in dados:
        try:
            nivel = float(dados['nivel_preenchimento'])
            if nivel < 0 or nivel > 100:
                erros.append("Nível de preenchimento deve estar entre 0 e 100")
        except (ValueError, TypeError):
            erros.append("Nível de preenchimento deve ser um número")
    
    if 'coordenadas' in dados:
        if isinstance(dados['coordenadas'], dict):
            if 'latitude' not in dados['coordenadas'] or 'longitude' not in dados['coordenadas']:
                erros.append("Coordenadas devem ter 'latitude' e 'longitude'")
    
    return erros

# ============================================================
# ENDPOINTS GET
# ============================================================

@api_bp.route('/lixeiras', methods=['GET'])
def listar_lixeiras():
    """Endpoint para obter todas as lixeiras"""
    db = get_db()
    try:
        lixeiras = db.query(Lixeira).all()
        resultado = [lixeira_para_dict(l) for l in lixeiras]
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/lixeira/<int:lixeira_id>', methods=['GET'])
def obter_lixeira(lixeira_id):
    """Endpoint para obter uma lixeira específica"""
    db = get_db()
    try:
        lixeira = db.query(Lixeira).filter(Lixeira.id == lixeira_id).first()
        if lixeira:
            return jsonify(lixeira_para_dict(lixeira))
        else:
            return jsonify({"erro": "Lixeira não encontrada"}), 404
    except Exception as e:
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

@api_bp.route('/historico', methods=['GET'])
def obter_historico():
    """Endpoint para obter histórico de coletas"""
    db = get_db()
    try:
        coletas = db.query(Coleta).order_by(Coleta.data_hora.desc()).all()
        resultado = [coleta_para_dict(c) for c in coletas]
        return jsonify(resultado)
    except Exception as e:
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
        
        hoje = datetime.now().date()
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
def criar_lixeira():
    """Endpoint para criar uma nova lixeira"""
    db = get_db()
    try:
        dados = request.get_json()
        
        if not dados:
            return jsonify({"erro": "Dados JSON não fornecidos"}), 400
        
        # Validar dados
        erros = validar_lixeira(dados, criar=True)
        if erros:
            return jsonify({"erro": "Erros de validação", "detalhes": erros}), 400
        
        # Processar coordenadas
        coordenadas_str = None
        if 'coordenadas' in dados and isinstance(dados['coordenadas'], dict):
            lat = dados['coordenadas'].get('latitude', 0.0)
            lon = dados['coordenadas'].get('longitude', 0.0)
            coordenadas_str = f"{lat}, {lon}"
        
        # Processar última coleta
        ultima_coleta = None
        if 'ultima_coleta' in dados and dados['ultima_coleta']:
            try:
                ultima_coleta = datetime.fromisoformat(dados['ultima_coleta'].replace('Z', '+00:00'))
            except:
                ultima_coleta = datetime.utcnow()
        else:
            ultima_coleta = datetime.utcnow()
        
        # Criar nova lixeira
        nova_lixeira = Lixeira(
            localizacao=dados['localizacao'],
            nivel_preenchimento=dados.get('nivel_preenchimento', 0.0),
            status=dados.get('status', 'ativo'),
            ultima_coleta=ultima_coleta,
            tipo=dados.get('tipo'),
            coordenadas=coordenadas_str
        )
        
        db.add(nova_lixeira)
        db.commit()
        db.refresh(nova_lixeira)
        
        return jsonify(lixeira_para_dict(nova_lixeira)), 201
        
    except Exception as e:
        db.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/lixeira/<int:lixeira_id>', methods=['PUT'])
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
        erros = validar_lixeira(dados, criar=False)
        if erros:
            return jsonify({"erro": "Erros de validação", "detalhes": erros}), 400
        
        # Atualizar campos
        if 'localizacao' in dados:
            lixeira.localizacao = dados['localizacao']
        
        if 'nivel_preenchimento' in dados:
            lixeira.nivel_preenchimento = float(dados['nivel_preenchimento'])
        
        if 'status' in dados:
            lixeira.status = dados['status']
        
        if 'tipo' in dados:
            lixeira.tipo = dados['tipo']
        
        if 'ultima_coleta' in dados and dados['ultima_coleta']:
            try:
                lixeira.ultima_coleta = datetime.fromisoformat(dados['ultima_coleta'].replace('Z', '+00:00'))
            except:
                pass
        
        if 'coordenadas' in dados and isinstance(dados['coordenadas'], dict):
            lat = dados['coordenadas'].get('latitude', 0.0)
            lon = dados['coordenadas'].get('longitude', 0.0)
            lixeira.coordenadas = f"{lat}, {lon}"
        
        db.commit()
        db.refresh(lixeira)
        
        return jsonify(lixeira_para_dict(lixeira))
        
    except Exception as e:
        db.rollback()
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()

@api_bp.route('/lixeira/<int:lixeira_id>', methods=['DELETE'])
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
    """Endpoint para obter dados para relatórios"""
    db = get_db()
    try:
        # Obter parâmetros de filtro
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        
        # Query base
        query = db.query(Coleta)
        
        # Aplicar filtros de data se fornecidos
        if data_inicio:
            try:
                # Se for apenas data (YYYY-MM-DD), incluir desde o início do dia
                if len(data_inicio) == 10:
                    data_inicio_obj = datetime.fromisoformat(data_inicio + 'T00:00:00')
                else:
                    data_inicio_obj = datetime.fromisoformat(data_inicio.replace('Z', '+00:00'))
                query = query.filter(Coleta.data_hora >= data_inicio_obj)
            except Exception as e:
                print(f"Erro ao processar data_inicio: {e}")
                pass
        
        if data_fim:
            try:
                # Se for apenas data (YYYY-MM-DD), incluir até o final do dia
                if len(data_fim) == 10:
                    data_fim_obj = datetime.fromisoformat(data_fim + 'T23:59:59')
                else:
                    data_fim_obj = datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
                query = query.filter(Coleta.data_hora <= data_fim_obj)
            except Exception as e:
                print(f"Erro ao processar data_fim: {e}")
                pass
        
        coletas = query.order_by(Coleta.data_hora.desc()).all()
        
        # Agregar dados
        total_coletas = len(coletas)
        volume_total = sum(c.volume_estimado for c in coletas if c.volume_estimado)
        
        # Agrupar por lixeira
        coletas_por_lixeira = {}
        for coleta in coletas:
            lixeira_id = coleta.lixeira_id
            if lixeira_id not in coletas_por_lixeira:
                coletas_por_lixeira[lixeira_id] = {
                    "lixeira_id": lixeira_id,
                    "total_coletas": 0,
                    "volume_total": 0.0
                }
            coletas_por_lixeira[lixeira_id]["total_coletas"] += 1
            if coleta.volume_estimado:
                coletas_por_lixeira[lixeira_id]["volume_total"] += coleta.volume_estimado
        
        relatorio = {
            "periodo": {
                "data_inicio": data_inicio,
                "data_fim": data_fim
            },
            "resumo": {
                "total_coletas": total_coletas,
                "volume_total": round(volume_total, 2),
                "coletas_por_lixeira": list(coletas_por_lixeira.values())
            },
            "detalhes": [coleta_para_dict(c) for c in coletas]
        }
        
        return jsonify(relatorio)
        
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        db.close()
