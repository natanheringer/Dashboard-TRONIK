"""
Sistema de Notificações - Dashboard-TRONIK
==========================================
Gerencia envio de notificações por email e alertas do sistema.
"""

import logging

from flask import current_app
from flask_mail import Mail, Message
from sqlalchemy.orm import Session

from banco_dados.modelos import Coletor, Notificacao, Sensor, Usuario
from banco_dados.utils import utc_now_naive

logger = logging.getLogger(__name__)

# Instância global do Mail (será inicializada no app.py)
mail = Mail()

# Configurações de alertas
NIVEL_ALERTA_LIXEIRA = 80.0  # Coletor > 80% = alerta
NIVEL_ALERTA_BATERIA = 20.0  # Bateria < 20% = alerta


def inicializar_mail(app):
    """Inicializa Flask-Mail com as configurações do app"""
    mail.init_app(app)
    logger.info("Flask-Mail inicializado")


def verificar_alertas_lixeiras(db: Session) -> list[dict]:
    """
    Verifica coletores que precisam de alerta (nível > 80%).

    Returns:
        Lista de dicionários com informações das coletores que precisam de alerta
    """
    alertas = []

    try:
        from datetime import timedelta
        limite_tempo = utc_now_naive() - timedelta(hours=24)

        coletores = db.query(Coletor).filter(
            Coletor.nivel_preenchimento > NIVEL_ALERTA_LIXEIRA,
            Coletor.status != "QUEBRADA"
        ).all()

        # Pré-carregar todas as notificações recentes para os coletores (evita N+1)
        coletor_ids = [c.id for c in coletores]
        notificacoes_recentes = db.query(Notificacao).filter(
            Notificacao.coletor_id.in_(coletor_ids),
            Notificacao.tipo == 'lixeira_cheia',
            Notificacao.criada_em >= limite_tempo
        ).all()

        # Criar dicionário {coletor_id: [notificacoes]} para lookup O(1)
        notificacoes_por_coletor = {}
        for notif in notificacoes_recentes:
            if notif.coletor_id not in notificacoes_por_coletor:
                notificacoes_por_coletor[notif.coletor_id] = []
            notificacoes_por_coletor[notif.coletor_id].append(notif)

        for coletor in coletores:
            # Verificar se já existe notificação recente (últimas 24h)
            if coletor.id not in notificacoes_por_coletor:
                alertas.append({
                    'coletor_id': coletor.id,
                    'localizacao': coletor.localizacao,
                    'nivel': coletor.nivel_preenchimento,
                    'status': coletor.status
                })

        return alertas
    except Exception as e:
        logger.error(f"Erro ao verificar alertas de coletores: {e}")
        return []


def verificar_alertas_sensores(db: Session) -> list[dict]:
    """
    Verifica sensores com bateria baixa (< 20%).

    Returns:
        Lista de dicionários com informações dos sensores que precisam de alerta
    """
    alertas = []

    try:
        from datetime import timedelta
        limite_tempo = utc_now_naive() - timedelta(hours=24)

        sensores = db.query(Sensor).filter(
            Sensor.bateria < NIVEL_ALERTA_BATERIA
        ).all()

        # Pré-carregar todas as notificações recentes para os sensores (evita N+1)
        sensor_ids = [s.id for s in sensores]
        notificacoes_recentes = db.query(Notificacao).filter(
            Notificacao.sensor_id.in_(sensor_ids),
            Notificacao.tipo == 'bateria_baixa',
            Notificacao.criada_em >= limite_tempo
        ).all()

        # Criar dicionário {sensor_id: [notificacoes]} para lookup O(1)
        notificacoes_por_sensor = {}
        for notif in notificacoes_recentes:
            if notif.sensor_id not in notificacoes_por_sensor:
                notificacoes_por_sensor[notif.sensor_id] = []
            notificacoes_por_sensor[notif.sensor_id].append(notif)

        # Pré-carregar todos os coletores relevantes (evita N+1)
        coletor_ids = list({s.coletor_id for s in sensores})
        coletores = db.query(Coletor).filter(Coletor.id.in_(coletor_ids)).all()

        # Criar dicionário {coletor_id: coletor} para lookup O(1)
        coletores_por_id = {c.id: c for c in coletores}

        for sensor in sensores:
            # Verificar se já existe notificação recente (últimas 24h)
            if sensor.id not in notificacoes_por_sensor:
                coletor = coletores_por_id.get(sensor.coletor_id)
                alertas.append({
                    'sensor_id': sensor.id,
                    'coletor_id': sensor.coletor_id,
                    'localizacao': coletor.localizacao if coletor else 'N/A',
                    'bateria': sensor.bateria
                })

        return alertas
    except Exception as e:
        logger.error(f"Erro ao verificar alertas de sensores: {e}")
        return []


def criar_notificacao(
    db: Session,
    tipo: str,
    titulo: str,
    mensagem: str,
    coletor_id: int | None = None,
    sensor_id: int | None = None
) -> Notificacao:
    """
    Cria uma nova notificação no banco de dados.

    Args:
        db: Sessão do banco de dados
        tipo: Tipo da notificação ('lixeira_cheia', 'bateria_baixa', etc.)
        titulo: Título da notificação
        mensagem: Mensagem da notificação
        coletor_id: ID da coletor relacionada (opcional)
        sensor_id: ID do sensor relacionado (opcional)

    Returns:
        Objeto Notificacao criado
    """
    notificacao = Notificacao(
        tipo=tipo,
        titulo=titulo,
        mensagem=mensagem,
        coletor_id=coletor_id,
        sensor_id=sensor_id,
        enviada=False
    )

    db.add(notificacao)
    db.commit()
    db.refresh(notificacao)

    logger.info(f"Notificação criada: {tipo} - {titulo}")

    # Emitir atualização via WebSocket
    try:
        from banco_dados.serializers import notificacao_para_dict
        from rotas.websocket import emitir_nova_notificacao
        emitir_nova_notificacao(notificacao_para_dict(notificacao))
    except Exception as e:
        logger.warning(f"Erro ao emitir notificação via WebSocket: {e}")

    return notificacao


def enviar_email_notificacao(
    destinatarios: list[str],
    assunto: str,
    corpo_html: str,
    corpo_texto: str | None = None
) -> bool:
    """
    Envia email de notificação.

    Args:
        destinatarios: Lista de emails destinatários
        assunto: Assunto do email
        corpo_html: Corpo do email em HTML
        corpo_texto: Corpo do email em texto (opcional)

    Returns:
        True se enviado com sucesso, False caso contrário
    """
    try:
        if not current_app.config.get('MAIL_SERVER'):
            logger.warning("Servidor de email não configurado. Notificação não enviada.")
            return False

        msg = Message(
            subject=assunto,
            recipients=destinatarios,
            html=corpo_html,
            body=corpo_texto or corpo_html
        )

        mail.send(msg)
        logger.info(f"Email enviado para {len(destinatarios)} destinatário(s): {assunto}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar email: {e}")
        return False


def enviar_email_com_retry(destinatarios: list[str], assunto: str, corpo_html: str, corpo_texto: str | None = None, max_tentativas: int = 3) -> bool:
    """
    Envia um email com retry automático em caso de falha.
    Usado para emails críticos (notificações de alertas).

    Args:
        destinatarios: Lista de endereços de email
        assunto: Assunto do email
        corpo_html: Corpo do email em HTML
        corpo_texto: Corpo do email em texto plano (opcional)
        max_tentativas: Número máximo de tentativas (padrão: 3)

    Returns:
        True se enviado com sucesso, False caso contrário
    """
    import time

    for tentativa in range(max_tentativas):
        try:
            if enviar_email_notificacao(destinatarios, assunto, corpo_html, corpo_texto):
                return True
        except Exception as e:
            logger.warning(f"Tentativa {tentativa + 1}/{max_tentativas} de envio de email falhou: {e}")
            if tentativa < max_tentativas - 1:
                # Backoff exponencial: 2s, 4s, 8s...
                delay = 2 ** tentativa
                time.sleep(delay)
            else:
                logger.error(f"Falha ao enviar email após {max_tentativas} tentativas: {assunto}")

    return False


def processar_alertas(db: Session) -> dict[str, int]:
    """
    Processa todos os alertas e envia notificações.

    Returns:
        Dicionário com estatísticas de alertas processados
    """
    stats = {
        'lixeiras_alertadas': 0,
        'sensores_alertados': 0,
        'emails_enviados': 0,
        'erros': 0
    }

    try:
        # Pré-carregar todos os admins uma vez (evita N+1)
        admins = db.query(Usuario).filter(
            Usuario.admin,
            Usuario.ativo
        ).all()
        emails_admins = [admin.email for admin in admins if admin.email]

        # Verificar alertas de coletores
        alertas_lixeiras = verificar_alertas_lixeiras(db)
        for alerta in alertas_lixeiras:
            try:
                # Criar notificação
                notificacao = criar_notificacao(
                    db=db,
                    tipo='lixeira_cheia',
                    titulo=f"Coletor #{alerta['coletor_id']} - Nível Alto",
                    mensagem=f"A coletor em {alerta['localizacao']} está com {alerta['nivel']:.1f}% de preenchimento.",
                    coletor_id=alerta['coletor_id']
                )

                if emails_admins:
                    corpo_html = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <h2 style="color: #27ae60;">⚠️ Alerta: Coletor com Nível Alto</h2>
                        <p><strong>Coletor:</strong> #{alerta['coletor_id']} - {alerta['localizacao']}</p>
                        <p><strong>Nível de Preenchimento:</strong> {alerta['nivel']:.1f}%</p>
                        <p><strong>Status:</strong> {alerta['status']}</p>
                        <p style="margin-top: 20px; color: #666; font-size: 12px;">
                            Dashboard-TRONIK - Sistema de Monitoramento
                        </p>
                    </body>
                    </html>
                    """

                    if enviar_email_com_retry(emails_admins, notificacao.titulo, corpo_html):
                        notificacao.enviada = True
                        notificacao.enviada_em = utc_now_naive()
                        db.commit()
                        stats['emails_enviados'] += len(emails_admins)

                stats['lixeiras_alertadas'] += 1
            except Exception as e:
                logger.error(f"Erro ao processar alerta de coletor {alerta['coletor_id']}: {e}")
                stats['erros'] += 1

        # Verificar alertas de sensores
        alertas_sensores = verificar_alertas_sensores(db)
        for alerta in alertas_sensores:
            try:
                # Criar notificação
                notificacao = criar_notificacao(
                    db=db,
                    tipo='bateria_baixa',
                    titulo=f"Sensor #{alerta['sensor_id']} - Bateria Baixa",
                    mensagem=f"O sensor da coletor em {alerta['localizacao']} está com {alerta['bateria']:.1f}% de bateria.",
                    sensor_id=alerta['sensor_id'],
                    coletor_id=alerta['coletor_id']
                )

                if emails_admins:
                    corpo_html = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <h2 style="color: #f39c12;">🔋 Alerta: Bateria Baixa</h2>
                        <p><strong>Sensor:</strong> #{alerta['sensor_id']}</p>
                        <p><strong>Coletor:</strong> #{alerta['coletor_id']} - {alerta['localizacao']}</p>
                        <p><strong>Nível de Bateria:</strong> {alerta['bateria']:.1f}%</p>
                        <p style="margin-top: 20px; color: #666; font-size: 12px;">
                            Dashboard-TRONIK - Sistema de Monitoramento
                        </p>
                    </body>
                    </html>
                    """

                    if enviar_email_com_retry(emails_admins, notificacao.titulo, corpo_html):
                        notificacao.enviada = True
                        notificacao.enviada_em = utc_now_naive()
                        db.commit()
                        stats['emails_enviados'] += len(emails_admins)

                stats['sensores_alertados'] += 1
            except Exception as e:
                logger.error(f"Erro ao processar alerta de sensor {alerta['sensor_id']}: {e}")
                stats['erros'] += 1

        return stats
    except Exception as e:
        logger.error(f"Erro ao processar alertas: {e}")
        stats['erros'] += 1
        return stats



