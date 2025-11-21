#!/usr/bin/env python3
"""
Script para Processar Alertas - Dashboard-TRONIK
=================================================
Script CLI para processar alertas e enviar notificações por email.
Pode ser executado manualmente ou agendado via cron.

Uso:
    python scripts/processar_alertas.py
"""

import sys
import os
import logging

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from banco_dados.modelos import Base
from banco_dados.notificacoes import processar_alertas
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """Função principal"""
    try:
        # Conectar ao banco de dados
        database_url = os.getenv('DATABASE_URL', 'sqlite:///tronik.db')
        engine = create_engine(database_url, echo=False)
        SessionLocal = sessionmaker(bind=engine)
        
        # Criar sessão
        db = SessionLocal()
        
        try:
            logger.info("Iniciando processamento de alertas...")
            
            # Processar alertas
            stats = processar_alertas(db)
            
            # Exibir resultados
            logger.info("=" * 60)
            logger.info("RESULTADO DO PROCESSAMENTO DE ALERTAS")
            logger.info("=" * 60)
            logger.info(f"Lixeiras alertadas: {stats['lixeiras_alertadas']}")
            logger.info(f"Sensores alertados: {stats['sensores_alertados']}")
            logger.info(f"Emails enviados: {stats['emails_enviados']}")
            logger.info(f"Erros: {stats['erros']}")
            logger.info("=" * 60)
            
            if stats['erros'] > 0:
                logger.warning(f"⚠️  {stats['erros']} erro(s) encontrado(s) durante o processamento")
                sys.exit(1)
            else:
                logger.info("✅ Processamento concluído com sucesso!")
                sys.exit(0)
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Erro ao processar alertas: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()



