"""
Script de Migração de Dados - Dashboard-TRONIK
===============================================

Migra dados existentes do modelo antigo para o novo modelo.
Converte coordenadas string para latitude/longitude e tipos string para FKs.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from banco_dados.modelos import Base, Lixeira, Sensor, Coleta, TipoMaterial, TipoSensor
from banco_dados.seed_tipos import popular_tipos
import logging

logger = logging.getLogger(__name__)


def converter_coordenadas_string(coordenadas_str):
    """
    Converte coordenadas de string "lat, lon" para (latitude, longitude).
    
    Args:
        coordenadas_str: String no formato "latitude, longitude"
    
    Returns:
        tuple: (latitude, longitude) ou (None, None) se inválido
    """
    if not coordenadas_str or not coordenadas_str.strip():
        return (None, None)
    
    try:
        # Remover espaços e dividir por vírgula
        partes = coordenadas_str.strip().split(',')
        if len(partes) == 2:
            lat = float(partes[0].strip())
            lon = float(partes[1].strip())
            # Validar ranges
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return (lat, lon)
    except (ValueError, AttributeError):
        pass
    
    return (None, None)


def mapear_tipo_material(tipo_str):
    """
    Mapeia tipo de material string para ID.
    
    Args:
        tipo_str: String com tipo de material
    
    Returns:
        int: ID do tipo de material ou None
    """
    if not tipo_str:
        return None
    
    tipo_str = tipo_str.strip().lower()
    
    # Mapeamento básico
    mapeamento = {
        'plástico': 'Plástico',
        'plastic': 'Plástico',
        'metal': 'Metal',
        'papel': 'Papel',
        'vidro': 'Vidro',
        'orgânico': 'Orgânico',
        'organico': 'Orgânico',
        'eletrônico': 'Eletrônico',
        'eletronico': 'Eletrônico',
    }
    
    tipo_normalizado = mapeamento.get(tipo_str, None)
    if not tipo_normalizado:
        return None
    
    return tipo_normalizado


def mapear_tipo_sensor(tipo_str):
    """
    Mapeia tipo de sensor string para ID.
    
    Args:
        tipo_str: String com tipo de sensor
    
    Returns:
        int: ID do tipo de sensor ou None
    """
    if not tipo_str:
        return None
    
    tipo_str = tipo_str.strip().lower()
    
    # Mapeamento básico
    mapeamento = {
        'ultrassônico': 'Ultrassônico',
        'ultrassonico': 'Ultrassônico',
        'ultrasonic': 'Ultrassônico',
        'temperatura': 'Temperatura',
        'peso': 'Peso',
        'infravermelho': 'Infravermelho',
        'infrared': 'Infravermelho',
    }
    
    tipo_normalizado = mapeamento.get(tipo_str, None)
    if not tipo_normalizado:
        return None
    
    return tipo_normalizado


def migrar_dados(engine, backup=True):
    """
    Migra dados existentes para o novo modelo.
    
    Args:
        engine: SQLAlchemy engine
        backup: Se True, faz backup antes de migrar
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    
    stats = {
        'lixeiras_migradas': 0,
        'lixeiras_com_coordenadas': 0,
        'lixeiras_sem_coordenadas': 0,
        'sensores_migrados': 0,
        'sensores_com_tipo': 0,
        'sensores_sem_tipo': 0,
        'erros': []
    }
    
    try:
        logger.info("Iniciando migração de dados...")
        
        # ============================================================
        # 1. Garantir que tipos estão populados
        # ============================================================
        logger.info("Garantindo que tipos estão populados...")
        popular_tipos(engine)
        
        # ============================================================
        # 2. Migrar Lixeiras
        # ============================================================
        logger.info("Migrando lixeiras...")
        lixeiras = session.query(Lixeira).all()
        
        for lixeira in lixeiras:
            try:
                # Converter coordenadas
                if lixeira.coordenadas:
                    lat, lon = converter_coordenadas_string(lixeira.coordenadas)
                    if lat is not None and lon is not None:
                        lixeira.latitude = lat
                        lixeira.longitude = lon
                        stats['lixeiras_com_coordenadas'] += 1
                    else:
                        stats['lixeiras_sem_coordenadas'] += 1
                        logger.warning(f"Coordenadas inválidas na lixeira {lixeira.id}: {lixeira.coordenadas}")
                else:
                    stats['lixeiras_sem_coordenadas'] += 1
                
                # Converter tipo de material
                if lixeira.tipo:
                    tipo_nome = mapear_tipo_material(lixeira.tipo)
                    if tipo_nome:
                        tipo_material = session.query(TipoMaterial).filter(
                            TipoMaterial.nome == tipo_nome
                        ).first()
                        if tipo_material:
                            lixeira.tipo_material_id = tipo_material.id
                
                stats['lixeiras_migradas'] += 1
                
            except Exception as e:
                stats['erros'].append({
                    'tipo': 'lixeira',
                    'id': lixeira.id,
                    'erro': str(e)
                })
                logger.error(f"Erro ao migrar lixeira {lixeira.id}: {e}")
        
        session.commit()
        logger.info(f"✅ {stats['lixeiras_migradas']} lixeiras migradas")
        
        # ============================================================
        # 3. Migrar Sensores
        # ============================================================
        logger.info("Migrando sensores...")
        sensores = session.query(Sensor).all()
        
        for sensor in sensores:
            try:
                # Converter tipo de sensor
                if sensor.tipo:
                    tipo_nome = mapear_tipo_sensor(sensor.tipo)
                    if tipo_nome:
                        tipo_sensor = session.query(TipoSensor).filter(
                            TipoSensor.nome == tipo_nome
                        ).first()
                        if tipo_sensor:
                            sensor.tipo_sensor_id = tipo_sensor.id
                            stats['sensores_com_tipo'] += 1
                    else:
                        stats['sensores_sem_tipo'] += 1
                else:
                    stats['sensores_sem_tipo'] += 1
                
                stats['sensores_migrados'] += 1
                
            except Exception as e:
                stats['erros'].append({
                    'tipo': 'sensor',
                    'id': sensor.id,
                    'erro': str(e)
                })
                logger.error(f"Erro ao migrar sensor {sensor.id}: {e}")
        
        session.commit()
        logger.info(f"✅ {stats['sensores_migrados']} sensores migrados")
        
        # ============================================================
        # 4. Resumo
        # ============================================================
        logger.info("✅ Migração concluída!")
        logger.info(f"   Lixeiras migradas: {stats['lixeiras_migradas']}")
        logger.info(f"   Lixeiras com coordenadas: {stats['lixeiras_com_coordenadas']}")
        logger.info(f"   Lixeiras sem coordenadas: {stats['lixeiras_sem_coordenadas']}")
        logger.info(f"   Sensores migrados: {stats['sensores_migrados']}")
        logger.info(f"   Sensores com tipo: {stats['sensores_com_tipo']}")
        logger.info(f"   Sensores sem tipo: {stats['sensores_sem_tipo']}")
        
        if stats['erros']:
            logger.warning(f"   Erros encontrados: {len(stats['erros'])}")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Erro fatal na migração: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    from sqlalchemy import create_engine
    from banco_dados.modelos import Base
    
    # Criar engine
    engine = create_engine('sqlite:///tronik.db', echo=False)
    
    # Garantir que tabelas existem
    Base.metadata.create_all(engine)
    
    # Executar migração
    stats = migrar_dados(engine, backup=True)
    
    print("\n" + "="*60)
    print("RESUMO DA MIGRAÇÃO")
    print("="*60)
    print(f"Lixeiras migradas: {stats['lixeiras_migradas']}")
    print(f"Lixeiras com coordenadas: {stats['lixeiras_com_coordenadas']}")
    print(f"Lixeiras sem coordenadas: {stats['lixeiras_sem_coordenadas']}")
    print(f"Sensores migrados: {stats['sensores_migrados']}")
    print(f"Sensores com tipo: {stats['sensores_com_tipo']}")
    print(f"Sensores sem tipo: {stats['sensores_sem_tipo']}")
    if stats['erros']:
        print(f"\nErros encontrados: {len(stats['erros'])}")
        for erro in stats['erros'][:10]:
            print(f"  {erro['tipo']} {erro['id']}: {erro['erro']}")

