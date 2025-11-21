"""
Sistema de Agendamento - Dashboard-TRONIK
=========================================
Gerencia tarefas agendadas usando APScheduler.
Processa alertas automaticamente em intervalos configuráveis.
"""

import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from banco_dados.notificacoes import processar_alertas

logger = logging.getLogger(__name__)

# Instância global do scheduler
scheduler = None


def inicializar_agendamento(app):
    """
    Inicializa o sistema de agendamento.
    
    Args:
        app: Instância da aplicação Flask
    """
    global scheduler
    
    # Verificar se agendamento está habilitado
    agendamento_enabled = os.getenv('AGENDAMENTO_ENABLED', 'false').lower() == 'true'
    
    if not agendamento_enabled:
        logger.info("Sistema de agendamento desativado (AGENDAMENTO_ENABLED=false)")
        return
    
    # Obter intervalo de processamento (em minutos)
    intervalo_minutos = int(os.getenv('AGENDAMENTO_INTERVALO_MINUTOS', '60'))
    
    if intervalo_minutos < 1:
        logger.warning(f"Intervalo inválido ({intervalo_minutos} minutos). Usando padrão de 60 minutos.")
        intervalo_minutos = 60
    
    # Criar scheduler
    scheduler = BackgroundScheduler(daemon=True)
    
    # Adicionar job para processar alertas
    scheduler.add_job(
        func=processar_alertas_job,
        trigger=IntervalTrigger(minutes=intervalo_minutos),
        id='processar_alertas',
        name='Processar Alertas',
        replace_existing=True,
        max_instances=1  # Evitar execuções simultâneas
    )
    
    # Iniciar scheduler
    scheduler.start()
    
    logger.info(f"✅ Sistema de agendamento ativado")
    logger.info(f"   Intervalo: {intervalo_minutos} minutos")
    logger.info(f"   Próxima execução: {scheduler.get_job('processar_alertas').next_run_time}")


def processar_alertas_job():
    """
    Job agendado para processar alertas.
    Esta função é executada automaticamente pelo scheduler.
    """
    try:
        logger.info("🔄 Iniciando processamento automático de alertas...")
        
        # Conectar ao banco de dados
        database_url = os.getenv('DATABASE_URL', 'sqlite:///tronik.db')
        engine = create_engine(database_url, echo=False)
        SessionLocal = sessionmaker(bind=engine)
        
        # Criar sessão
        db = SessionLocal()
        
        try:
            # Processar alertas
            stats = processar_alertas(db)
            
            logger.info("=" * 60)
            logger.info("RESULTADO DO PROCESSAMENTO AUTOMÁTICO DE ALERTAS")
            logger.info("=" * 60)
            logger.info(f"Lixeiras alertadas: {stats['lixeiras_alertadas']}")
            logger.info(f"Sensores alertados: {stats['sensores_alertados']}")
            logger.info(f"Emails enviados: {stats['emails_enviados']}")
            logger.info(f"Erros: {stats['erros']}")
            logger.info("=" * 60)
            
            if stats['erros'] > 0:
                logger.warning(f"⚠️  {stats['erros']} erro(s) encontrado(s) durante o processamento")
            else:
                logger.info("✅ Processamento automático concluído com sucesso!")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Erro ao processar alertas automaticamente: {e}", exc_info=True)


def parar_agendamento():
    """
    Para o sistema de agendamento.
    """
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Sistema de agendamento parado")


def obter_status_agendamento():
    """
    Retorna o status do sistema de agendamento.
    
    Returns:
        dict: Status do agendamento
    """
    global scheduler
    
    if not scheduler or not scheduler.running:
        return {
            'ativo': False,
            'mensagem': 'Sistema de agendamento não está ativo'
        }
    
    job = scheduler.get_job('processar_alertas')
    
    if not job:
        return {
            'ativo': False,
            'mensagem': 'Job de processamento não encontrado'
        }
    
    return {
        'ativo': True,
        'proxima_execucao': job.next_run_time.isoformat() if job.next_run_time else None,
        'ultima_execucao': None,  # APScheduler não armazena isso por padrão
        'intervalo_minutos': int(os.getenv('AGENDAMENTO_INTERVALO_MINUTOS', '60'))
    }


