"""
Script de Migração: SQLite → PostgreSQL
========================================
Migra todos os dados do banco SQLite para PostgreSQL.

Uso:
    python banco_dados/migrar_sqlite_para_postgres.py

Requisitos:
    - psycopg2-binary instalado
    - PostgreSQL rodando e acessível
    - Arquivo tronik.db existente
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verificar_tabelas_existentes(engine, tabelas):
    """Verifica quais tabelas já existem no banco de destino"""
    inspector = inspect(engine)
    tabelas_existentes = inspector.get_table_names()
    return [t for t in tabelas if t in tabelas_existentes]

def migrar_tabela(origem_engine, destino_engine, tabela, session_origem, session_destino):
    """Migra uma tabela específica do SQLite para PostgreSQL"""
    try:
        # Verificar se a tabela existe no destino
        inspector = inspect(destino_engine)
        tabelas_destino = inspector.get_table_names()
        
        if tabela not in tabelas_destino:
            logger.warning(f"Tabela {tabela} não existe no destino. Pulando...")
            return 0
        
        # Contar registros existentes
        count_query = text(f"SELECT COUNT(*) FROM {tabela}")
        count_existente = session_destino.execute(count_query).scalar()
        
        if count_existente > 0:
            logger.info(f"⚠️  Tabela {tabela} já possui {count_existente} registros. Pulando...")
            return 0
        
        # Ler todos os dados do SQLite
        query = text(f"SELECT * FROM {tabela}")
        resultado = session_origem.execute(query)
        colunas = resultado.keys()
        dados = resultado.fetchall()
        
        if not dados:
            logger.info(f"Tabela {tabela} está vazia. Pulando...")
            return 0
        
        # Preparar INSERT
        colunas_str = ", ".join(colunas)
        placeholders = ", ".join([f":{col}" for col in colunas])
        insert_query = text(f"INSERT INTO {tabela} ({colunas_str}) VALUES ({placeholders})")
        
        # Inserir dados em lotes
        lote = 100
        total_inseridos = 0
        
        for i in range(0, len(dados), lote):
            lote_dados = dados[i:i+lote]
            registros = [dict(zip(colunas, linha)) for linha in lote_dados]
            
            session_destino.execute(insert_query, registros)
            total_inseridos += len(registros)
        
        session_destino.commit()
        logger.info(f"✅ {total_inseridos} registros migrados de {tabela}")
        return total_inseridos
        
    except Exception as e:
        session_destino.rollback()
        logger.error(f"❌ Erro ao migrar tabela {tabela}: {str(e)}")
        return 0

def migrar_dados(sqlite_url, postgres_url):
    """Migra todos os dados do SQLite para PostgreSQL"""
    
    logger.info("=" * 60)
    logger.info("MIGRAÇÃO SQLITE → POSTGRESQL")
    logger.info("=" * 60)
    
    # Verificar se o arquivo SQLite existe
    if sqlite_url.startswith('sqlite:///'):
        arquivo_db = sqlite_url.replace('sqlite:///', '')
        if not os.path.exists(arquivo_db):
            logger.error(f"❌ Arquivo de banco SQLite não encontrado: {arquivo_db}")
            return False
    
    try:
        # Conectar aos bancos
        logger.info("Conectando ao SQLite...")
        sqlite_engine = create_engine(sqlite_url, echo=False)
        session_origem = sessionmaker(bind=sqlite_engine)()
        
        logger.info("Conectando ao PostgreSQL...")
        postgres_engine = create_engine(postgres_url, echo=False)
        session_destino = sessionmaker(bind=postgres_engine)()
        
        # Testar conexão PostgreSQL
        session_destino.execute(text("SELECT 1"))
        logger.info("✅ Conexões estabelecidas com sucesso")
        
        # Listar todas as tabelas do SQLite
        inspector_origem = inspect(sqlite_engine)
        tabelas = inspector_origem.get_table_names()
        
        # Filtrar tabelas do sistema
        tabelas_sistema = ['sqlite_sequence', 'sqlite_stat1', 'sqlite_stat4']
        tabelas = [t for t in tabelas if t not in tabelas_sistema]
        
        logger.info(f"📋 Encontradas {len(tabelas)} tabelas para migrar:")
        for t in tabelas:
            logger.info(f"   - {t}")
        
        # Migrar cada tabela
        total_migrado = 0
        tabelas_migradas = []
        
        for tabela in tabelas:
            logger.info(f"\n🔄 Migrando tabela: {tabela}")
            registros = migrar_tabela(
                sqlite_engine, 
                postgres_engine, 
                tabela, 
                session_origem, 
                session_destino
            )
            if registros > 0:
                total_migrado += registros
                tabelas_migradas.append(tabela)
        
        # Fechar conexões
        session_origem.close()
        session_destino.close()
        
        # Resumo
        logger.info("\n" + "=" * 60)
        logger.info("✅ MIGRAÇÃO CONCLUÍDA!")
        logger.info("=" * 60)
        logger.info(f"📊 Tabelas migradas: {len(tabelas_migradas)}")
        logger.info(f"📊 Total de registros: {total_migrado}")
        logger.info(f"\nTabelas migradas:")
        for t in tabelas_migradas:
            logger.info(f"   ✅ {t}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro durante migração: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migra dados do SQLite para PostgreSQL')
    parser.add_argument('--sqlite', default='sqlite:///tronik.db', 
                       help='URL do banco SQLite (padrão: sqlite:///tronik.db)')
    parser.add_argument('--postgres', required=True,
                       help='URL do banco PostgreSQL (ex: postgresql://user:pass@host:port/db)')
    parser.add_argument('--backup', action='store_true',
                       help='Fazer backup do SQLite antes de migrar')
    
    args = parser.parse_args()
    
    # Fazer backup se solicitado
    if args.backup and args.sqlite.startswith('sqlite:///'):
        arquivo_db = args.sqlite.replace('sqlite:///', '')
        if os.path.exists(arquivo_db):
            import shutil
            from datetime import datetime
            backup_name = f"{arquivo_db}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(arquivo_db, backup_name)
            logger.info(f"✅ Backup criado: {backup_name}")
    
    # Executar migração
    sucesso = migrar_dados(args.sqlite, args.postgres)
    
    if sucesso:
        logger.info("\n🎉 Migração concluída com sucesso!")
        logger.info("💡 Agora você pode atualizar DATABASE_URL para usar PostgreSQL")
        sys.exit(0)
    else:
        logger.error("\n❌ Migração falhou. Verifique os erros acima.")
        sys.exit(1)

if __name__ == '__main__':
    main()

