"""
Script de Seed - Popular Tabelas de Tipos
==========================================

Popula as tabelas de tipos com dados iniciais.
Deve ser executado após criar as tabelas e antes de inserir dados reais.
"""

from sqlalchemy.orm import sessionmaker
from banco_dados.modelos import Parceiro, TipoMaterial, TipoSensor, TipoColetor
import logging

logger = logging.getLogger(__name__)


def popular_tipos(engine):
    """
    Popula tabelas de tipos com dados iniciais.
    
    Args:
        engine: SQLAlchemy engine
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # ============================================================
        # TIPO_MATERIAL
        # ============================================================
        logger.info("Populando TIPO_MATERIAL...")
        tipos_material = [
            "Plástico",
            "Metal",
            "Papel",
            "Vidro",
            "Orgânico",
            "Eletrônico",
            "Outros"
        ]
        
        for nome in tipos_material:
            tipo_existente = session.query(TipoMaterial).filter(TipoMaterial.nome == nome).first()
            if not tipo_existente:
                tipo = TipoMaterial(nome=nome)
                session.add(tipo)
        
        session.commit()
        logger.info(f"✅ {len(tipos_material)} tipos de material criados")
        
        # ============================================================
        # TIPO_SENSOR
        # ============================================================
        logger.info("Populando TIPO_SENSOR...")
        tipos_sensor = [
            "Ultrassônico",
            "Temperatura",
            "Peso",
            "Infravermelho",
            "Outros"
        ]
        
        for nome in tipos_sensor:
            tipo_existente = session.query(TipoSensor).filter(TipoSensor.nome == nome).first()
            if not tipo_existente:
                tipo = TipoSensor(nome=nome)
                session.add(tipo)
        
        session.commit()
        logger.info(f"✅ {len(tipos_sensor)} tipos de sensor criados")
        
        # ============================================================
        # TIPO_COLETOR (valores do CSV)
        # ============================================================
        logger.info("Populando TIPO_COLETOR...")
        tipos_coletor = [
            "TUBO DE PASTA DENTE",
            "COLETOR DO CLIENTE",
            "SEM COLETOR"
        ]
        
        for nome in tipos_coletor:
            tipo_existente = session.query(TipoColetor).filter(TipoColetor.nome == nome).first()
            if not tipo_existente:
                tipo = TipoColetor(nome=nome)
                session.add(tipo)
        
        session.commit()
        logger.info(f"✅ {len(tipos_coletor)} tipos de coletor criados")
        
        # ============================================================
        # PARCEIROS (valores do CSV)
        # ============================================================
        logger.info("Populando PARCEIROS...")
        parceiros = [
            "INSTITUTO ARAPOTI",
            "ECOGRANA",
            "NEOENERGIA",
            "ESG SUMMIT",
            "COLEGIO RENOVAÇÃO",
            "COLETA SEM PARCEIRO"  # Especial - para coletas sem parceiro
        ]
        
        for nome in parceiros:
            parceiro_existente = session.query(Parceiro).filter(Parceiro.nome == nome).first()
            if not parceiro_existente:
                parceiro = Parceiro(nome=nome, ativo=True)
                session.add(parceiro)
        
        session.commit()
        logger.info(f"✅ {len(parceiros)} parceiros criados")
        
        logger.info("✅ Todas as tabelas de tipos foram populadas com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro ao popular tipos: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def obter_tipo_coletor_por_nome(session, nome):
    """
    Busca ou cria um tipo de coletor pelo nome.
    
    Args:
        session: SQLAlchemy session
        nome: Nome do tipo de coletor
    
    Returns:
        TipoColetor object
    """
    tipo = session.query(TipoColetor).filter(TipoColetor.nome == nome).first()
    if not tipo:
        # Criar se não existir (para dados dinâmicos)
        tipo = TipoColetor(nome=nome)
        session.add(tipo)
        session.commit()
        session.refresh(tipo)
    return tipo


def obter_parceiro_por_nome(session, nome):
    """
    Busca ou cria um parceiro pelo nome.
    
    Args:
        session: SQLAlchemy session
        nome: Nome do parceiro
    
    Returns:
        Parceiro object ou None se for "COLETA SEM PARCEIRO"
    """
    if not nome or nome.strip() == "" or nome == "COLETA SEM PARCEIRO":
        # Buscar o parceiro especial "COLETA SEM PARCEIRO"
        parceiro = session.query(Parceiro).filter(Parceiro.nome == "COLETA SEM PARCEIRO").first()
        if not parceiro:
            parceiro = Parceiro(nome="COLETA SEM PARCEIRO", ativo=True)
            session.add(parceiro)
            session.commit()
            session.refresh(parceiro)
        return parceiro
    
    parceiro = session.query(Parceiro).filter(Parceiro.nome == nome).first()
    if not parceiro:
        # Criar se não existir
        parceiro = Parceiro(nome=nome, ativo=True)
        session.add(parceiro)
        session.commit()
        session.refresh(parceiro)
    return parceiro

