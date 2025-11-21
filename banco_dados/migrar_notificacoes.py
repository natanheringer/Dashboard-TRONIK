"""
Migração: Adicionar colunas lida e lida_em à tabela notificacoes
================================================================

Este script adiciona as colunas 'lida' e 'lida_em' à tabela 'notificacoes'
se elas não existirem.

Execute: python banco_dados/migrar_notificacoes.py
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verificar_coluna_existe(engine, tabela, coluna):
    """Verifica se uma coluna existe em uma tabela"""
    inspector = inspect(engine)
    colunas = [col['name'] for col in inspector.get_columns(tabela)]
    return coluna in colunas


def migrar_notificacoes():
    """Adiciona colunas lida e lida_em à tabela notificacoes"""
    
    # Caminho do banco de dados
    db_path = os.getenv('DATABASE_URL', 'sqlite:///tronik.db')
    
    # Se for SQLite, verificar se o arquivo existe
    if db_path.startswith('sqlite:///'):
        arquivo_db = db_path.replace('sqlite:///', '')
        if not os.path.exists(arquivo_db):
            logger.error(f"Banco de dados não encontrado: {arquivo_db}")
            logger.info("Execute o app.py primeiro para criar o banco de dados.")
            return False
    
    # Criar engine
    engine = create_engine(db_path, echo=False)
    
    # Verificar se a tabela notificacoes existe
    inspector = inspect(engine)
    if 'notificacoes' not in inspector.get_table_names():
        logger.warning("Tabela 'notificacoes' não existe. Ela será criada automaticamente pelo SQLAlchemy.")
        logger.info("Execute o app.py para criar a tabela com as novas colunas.")
        return False
    
    # Verificar se as colunas já existem
    lida_existe = verificar_coluna_existe(engine, 'notificacoes', 'lida')
    lida_em_existe = verificar_coluna_existe(engine, 'notificacoes', 'lida_em')
    
    if lida_existe and lida_em_existe:
        logger.info("✅ Colunas 'lida' e 'lida_em' já existem na tabela 'notificacoes'.")
        return True
    
    # Criar sessão
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("Iniciando migração da tabela 'notificacoes'...")
        
        # Adicionar coluna 'lida' se não existir
        if not lida_existe:
            logger.info("Adicionando coluna 'lida'...")
            session.execute(text("""
                ALTER TABLE notificacoes 
                ADD COLUMN lida BOOLEAN DEFAULT 0
            """))
            logger.info("✅ Coluna 'lida' adicionada com sucesso.")
        else:
            logger.info("Coluna 'lida' já existe, pulando...")
        
        # Adicionar coluna 'lida_em' se não existir
        if not lida_em_existe:
            logger.info("Adicionando coluna 'lida_em'...")
            session.execute(text("""
                ALTER TABLE notificacoes 
                ADD COLUMN lida_em DATETIME
            """))
            logger.info("✅ Coluna 'lida_em' adicionada com sucesso.")
        else:
            logger.info("Coluna 'lida_em' já existe, pulando...")
        
        # Commit das alterações
        session.commit()
        
        logger.info("=" * 60)
        logger.info("✅ Migração concluída com sucesso!")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro durante a migração: {e}")
        session.rollback()
        return False
        
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 60)
    print("MIGRAÇÃO: Adicionar colunas lida e lida_em")
    print("=" * 60)
    print()
    
    sucesso = migrar_notificacoes()
    
    if sucesso:
        print("\n✅ Migração concluída!")
        sys.exit(0)
    else:
        print("\n❌ Migração falhou ou não foi necessária.")
        sys.exit(1)



