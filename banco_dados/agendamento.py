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


def _criar_sessao_padrao():
    """Cria sessão de banco para jobs isolados do app context."""
    database_url = os.getenv('DATABASE_URL', 'sqlite:///tronik.db')
    if database_url.startswith('postgresql://') and '+psycopg' not in database_url:
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://')
    if database_url.startswith('postgres://') and '+psycopg' not in database_url:
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://')

    # Apply SQLite WAL configuration if using SQLite
    if database_url.startswith('sqlite'):
        engine = create_engine(
            database_url,
            echo=False,
            connect_args={
                "timeout": 60,
                "check_same_thread": False,
            },
        )
        with engine.begin() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
    else:
        engine = create_engine(database_url, echo=False)

    return sessionmaker(bind=engine)()


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

    # ========================================
    # JOBS DE MACHINE LEARNING
    # ========================================

    # Módulo 1: Predição de enchimento (2x/dia — a cada 12h)
    ml_predicao_enabled = os.getenv('ML_PREDICAO_ENABLED', 'true').lower() == 'true'
    if ml_predicao_enabled:
        scheduler.add_job(
            func=_job_ml_predicao,
            trigger=IntervalTrigger(hours=12),
            id='ml_predicao',
            name='ML - Predição de Enchimento',
            replace_existing=True,
            max_instances=1,
        )

    # Módulo 2: TRONIK Score (1x/dia — a cada 24h)
    ml_score_enabled = os.getenv('ML_SCORE_ENABLED', 'true').lower() == 'true'
    if ml_score_enabled:
        scheduler.add_job(
            func=_job_ml_score,
            trigger=IntervalTrigger(hours=24),
            id='ml_score',
            name='ML - TRONIK Score',
            replace_existing=True,
            max_instances=1,
        )

    prospeccao_pipeline_enabled = os.getenv('PROSPECCAO_PIPELINE_ENABLED', 'false').lower() == 'true'
    if prospeccao_pipeline_enabled:
        prospeccao_intervalo_horas = int(os.getenv('PROSPECCAO_PIPELINE_INTERVAL_HOURS', '168'))
        if prospeccao_intervalo_horas < 1:
            logger.warning(
                "PROSPECCAO_PIPELINE_INTERVAL_HOURS inválido (%s); usando 168h (semanal).",
                prospeccao_intervalo_horas,
            )
            prospeccao_intervalo_horas = 168
        scheduler.add_job(
            func=executar_pipeline_prospeccao_job,
            trigger=IntervalTrigger(hours=prospeccao_intervalo_horas),
            id='prospeccao_pipeline',
            name='Prospecção - Pipeline ML',
            replace_existing=True,
            max_instances=1,
        )

    nik_enabled = os.getenv('NIK_PRE_GERACAO_ENABLED', 'false').lower() == 'true'
    if nik_enabled:
        nik_intervalo = int(os.getenv('NIK_PRE_GERACAO_INTERVALO_MIN', '60'))
        scheduler.add_job(
            func=pre_gerar_nik_job,
            trigger=IntervalTrigger(minutes=nik_intervalo),
            id='pre_gerar_nik',
            name='Pré-gerar conteúdo Nik',
            replace_existing=True,
            max_instances=1,
        )

    # Iniciar scheduler
    scheduler.start()

    logger.info("✅ Sistema de agendamento ativado")
    logger.info(f"   Intervalo alertas: {intervalo_minutos} minutos")
    if ml_predicao_enabled:
        logger.info("   ML Predição: a cada 12h")
    if ml_score_enabled:
        logger.info("   ML Score: a cada 24h")
    if prospeccao_pipeline_enabled:
        logger.info(f"   Prospecção pipeline: a cada {prospeccao_intervalo_horas}h")
    if nik_enabled:
        logger.info(f"   Nik pré-geração: a cada {nik_intervalo} minutos")
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

        # Apply SQLite WAL configuration if using SQLite
        if database_url.startswith('sqlite'):
            engine = create_engine(
                database_url,
                echo=False,
                connect_args={
                    "timeout": 60,
                    "check_same_thread": False,
                },
            )
            with engine.begin() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
        else:
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


def _criar_sessao_ml():
    """Cria sessão de banco para jobs ML (isolada do app context)."""
    return _criar_sessao_padrao()


def pre_gerar_nik_job():
    """Pré-popula cache da Nik para landing e blocos ops mais acessados."""
    try:
        logger.info("[Nik] Iniciando pré-geração de conteúdo...")
        from banco_dados.services import nik_service as nik

        tipos_landing = [
            "fala_nik",
            "fato_reciclagem",
            "impacto_tronik",
            "pergunta_guiada",
            "nik_explica",
        ]
        for tipo in tipos_landing:
            resultado = nik.gerar_bloco_landing(tipo)
            logger.info("[Nik] Landing %s: %s", tipo, resultado.get("fonte"))

        db = _criar_sessao_padrao()
        try:
            logger.info("[Nik] Ops resumo: %s", nik.resumo_operacional(db).get("fonte"))
            logger.info("[Nik] Ops alerta: %s", nik.analise_alerta(db).get("fonte"))
        finally:
            db.close()
        logger.info("[Nik] Pré-geração concluída")
    except Exception as exc:
        logger.error("[Nik] Erro na pré-geração: %s", exc, exc_info=True)


def _job_ml_predicao():
    """Job: Módulo 1 — Recalcula predições de enchimento para todos os coletores."""
    try:
        logger.info("🔄 [ML] Iniciando predição de enchimento...")
        from banco_dados.services.ml_predicao import recalcular_predicoes_todos
        db = _criar_sessao_ml()
        try:
            stats = recalcular_predicoes_todos(db)
            logger.info(f"✅ [ML] Predição concluída: {stats}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ [ML] Erro na predição: {e}", exc_info=True)


def _job_ml_score():
    """Job: Módulo 2 — Recalcula TRONIK Score para todos os coletores."""
    try:
        logger.info("🔄 [ML] Iniciando cálculo de TRONIK Score...")
        from banco_dados.services.ml_score import recalcular_scores_todos
        db = _criar_sessao_ml()
        try:
            stats = recalcular_scores_todos(db)
            logger.info(f"✅ [ML] Score concluído: {stats}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ [ML] Erro no score: {e}", exc_info=True)


def executar_pipeline_prospeccao_job():
    """Job: pipeline ML de prospecção REE (ingest→normalize→link-crm→train→score)."""
    try:
        logger.info("🔄 [Prospecção] Iniciando pipeline ML agendado...")
        from jobs.prospeccao.pipeline_ops import run_scheduled_pipeline

        result = run_scheduled_pipeline()
        if result.get("ok"):
            logger.info("✅ [Prospecção] Pipeline concluído: %s", result)
        else:
            logger.error("❌ [Prospecção] Pipeline terminou com falhas: %s", result)
    except Exception as e:
        logger.error("❌ [Prospecção] Erro no pipeline agendado: %s", e, exc_info=True)


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

    # Incluir status dos jobs ML
    ml_jobs = {}
    for job_id in ['ml_predicao', 'ml_score', 'prospeccao_pipeline']:
        ml_job = scheduler.get_job(job_id)
        if ml_job:
            ml_jobs[job_id] = {
                'ativo': True,
                'proxima_execucao': ml_job.next_run_time.isoformat() if ml_job.next_run_time else None,
            }

    return {
        'ativo': True,
        'proxima_execucao': job.next_run_time.isoformat() if job.next_run_time else None,
        'ultima_execucao': None,  # APScheduler não armazena isso por padrão
        'intervalo_minutos': int(os.getenv('AGENDAMENTO_INTERVALO_MINUTOS', '60')),
        'jobs_ml': ml_jobs,
    }
