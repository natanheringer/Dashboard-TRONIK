"""
Script de Migration - Tabelas Comerciais
=========================================
Cria as novas tabelas comerciais no banco de dados existente.
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect
from banco_dados.modelos import (
    Base, MetaComercial, Pipeline, Interacao, Tarefa, ContratoRecorrente
)
from banco_dados.utils.logger import configurar_logging
import logging

# Configurar logging
configurar_logging()
logger = logging.getLogger(__name__)

def verificar_tabela_existe(engine, nome_tabela):
    """Verifica se uma tabela já existe no banco"""
    inspector = inspect(engine)
    return nome_tabela in inspector.get_table_names()

def criar_tabelas_comerciais(database_url=None):
    """
    Cria as novas tabelas comerciais no banco de dados.
    
    Args:
        database_url: URL do banco de dados (opcional, usa padrão se None)
    """
    if database_url is None:
        database_url = os.getenv('DATABASE_URL', 'sqlite:///banco_dados/tronik.db')
    
    logger.info(f"Conectando ao banco: {database_url}")
    engine = create_engine(database_url, echo=False)
    
    # Lista de tabelas a criar
    tabelas = [
        ('metas_comerciais', MetaComercial),
        ('pipeline', Pipeline),
        ('interacoes', Interacao),
        ('tarefas', Tarefa),
        ('contratos_recorrentes', ContratoRecorrente),
    ]
    
    logger.info("Verificando tabelas existentes...")
    tabelas_criadas = []
    tabelas_existentes = []
    
    for nome_tabela, modelo in tabelas:
        if verificar_tabela_existe(engine, nome_tabela):
            logger.info(f"  ✓ Tabela '{nome_tabela}' já existe")
            tabelas_existentes.append(nome_tabela)
        else:
            logger.info(f"  → Criando tabela '{nome_tabela}'...")
            tabelas_criadas.append(nome_tabela)
    
    if tabelas_criadas:
        logger.info(f"\nCriando {len(tabelas_criadas)} nova(s) tabela(s)...")
        # Criar apenas as tabelas que não existem
        # SQLAlchemy só cria tabelas que não existem automaticamente
        Base.metadata.create_all(engine, tables=[
            modelo.__table__ for nome, modelo in tabelas 
            if nome in tabelas_criadas
        ])
        logger.info("✅ Tabelas criadas com sucesso!")
    else:
        logger.info("\n✅ Todas as tabelas já existem. Nada a fazer.")
    
    logger.info(f"\nResumo:")
    logger.info(f"  - Tabelas existentes: {len(tabelas_existentes)}")
    logger.info(f"  - Tabelas criadas: {len(tabelas_criadas)}")
    
    if tabelas_criadas:
        logger.info(f"\nTabelas criadas:")
        for nome in tabelas_criadas:
            logger.info(f"  ✓ {nome}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Cria tabelas comerciais no banco de dados')
    parser.add_argument(
        '--database-url',
        type=str,
        default=None,
        help='URL do banco de dados (padrão: sqlite:///banco_dados/tronik.db)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Apenas verifica, não cria tabelas'
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("🔍 Modo DRY-RUN: apenas verificando...")
        # TODO: Implementar verificação sem criar
        logger.info("Modo dry-run ainda não implementado completamente")
    else:
        criar_tabelas_comerciais(args.database_url)
        logger.info("\n✅ Migration concluída!")

