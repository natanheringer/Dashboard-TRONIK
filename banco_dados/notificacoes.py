"""
Sistema de Notificações - Dashboard-TRONIK
==========================================
Gerencia envio de notificações por email e alertas do sistema.
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime
from flask import current_app
from flask_mail import Mail, Message
from sqlalchemy.orm import Session
from banco_dados.modelos import Lixeira, Sensor, Notificacao, Usuario
from banco_dados.utils import utc_now_naive

logger = logging.getLogger(__name__)

# Instância global do Mail (será inicializada no app.py)
mail = Mail()

# Configurações de alertas
NIVEL_ALERTA_LIXEIRA = 80.0  # Lixeira > 80% = alerta
NIVEL_ALERTA_BATERIA = 20.0  # Bateria < 20% = alerta


def inicializar_mail(app):
    """Inicializa Flask-Mail com as configurações do app"""
    mail.init_app(app)
    logger.info("Flask-Mail inicializado")


def verificar_alertas_lixeiras(db: Session) -> List[Dict]:
    """
    Verifica lixeiras que precisam de alerta (nível > 80%).
    
    Returns:
        Lista de dicionários com informações das lixeiras que precisam de alerta
    """
    alertas = []
    
    try:
        lixeiras = db.query(Lixeira).filter(
            Lixeira.nivel_preenchimento > NIVEL_ALERTA_LIXEIRA,
            Lixeira.status != "QUEBRADA"
        ).all()
        
        for lixeira in lixeiras:
            # Verificar se já existe notificação recente (últimas 24h)
            from datetime import timedelta
            limite_tempo = utc_now_naive() - timedelta(hours=24)
            
            notificacao_recente = db.query(Notificacao).filter(
                Notificacao.lixeira_id == lixeira.id,
                Notificacao.tipo == 'lixeira_cheia',
                Notificacao.criada_em >= limite_tempo
            ).first()
            
            if not notificacao_recente:
                alertas.append({
                    'lixeira_id': lixeira.id,
                    'localizacao': lixeira.localizacao,
                    'nivel': lixeira.nivel_preenchimento,
                    'status': lixeira.status
                })
        
        return alertas
    except Exception as e:
        logger.error(f"Erro ao verificar alertas de lixeiras: {e}")
        return []


def verificar_alertas_sensores(db: Session) -> List[Dict]:
    """
    Verifica sensores com bateria baixa (< 20%).
    
    Returns:
        Lista de dicionários com informações dos sensores que precisam de alerta
    """
    alertas = []
    
    try:
        sensores = db.query(Sensor).filter(
            Sensor.bateria < NIVEL_ALERTA_BATERIA
        ).all()
        
        for sensor in sensores:
            # Verificar se já existe notificação recente (últimas 24h)
            from datetime import timedelta
            limite_tempo = utc_now_naive() - timedelta(hours=24)
            
            notificacao_recente = db.query(Notificacao).filter(
                Notificacao.sensor_id == sensor.id,
                Notificacao.tipo == 'bateria_baixa',
                Notificacao.criada_em >= limite_tempo
            ).first()
            
            if not notificacao_recente:
                lixeira = db.query(Lixeira).filter(Lixeira.id == sensor.lixeira_id).first()
                alertas.append({
                    'sensor_id': sensor.id,
                    'lixeira_id': sensor.lixeira_id,
                    'localizacao': lixeira.localizacao if lixeira else 'N/A',
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
    lixeira_id: Optional[int] = None,
    sensor_id: Optional[int] = None
) -> Notificacao:
    """
    Cria uma nova notificação no banco de dados.
    
    Args:
        db: Sessão do banco de dados
        tipo: Tipo da notificação ('lixeira_cheia', 'bateria_baixa', etc.)
        titulo: Título da notificação
        mensagem: Mensagem da notificação
        lixeira_id: ID da lixeira relacionada (opcional)
        sensor_id: ID do sensor relacionado (opcional)
    
    Returns:
        Objeto Notificacao criado
    """
    notificacao = Notificacao(
        tipo=tipo,
        titulo=titulo,
        mensagem=mensagem,
        lixeira_id=lixeira_id,
        sensor_id=sensor_id,
        enviada=False
    )
    
    db.add(notificacao)
    db.commit()
    db.refresh(notificacao)
    
    logger.info(f"Notificação criada: {tipo} - {titulo}")
    return notificacao


def enviar_email_notificacao(
    destinatarios: List[str],
    assunto: str,
    corpo_html: str,
    corpo_texto: Optional[str] = None
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


def processar_alertas(db: Session) -> Dict[str, int]:
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
        # Verificar alertas de lixeiras
        alertas_lixeiras = verificar_alertas_lixeiras(db)
        for alerta in alertas_lixeiras:
            try:
                # Criar notificação
                notificacao = criar_notificacao(
                    db=db,
                    tipo='lixeira_cheia',
                    titulo=f"Lixeira #{alerta['lixeira_id']} - Nível Alto",
                    mensagem=f"A lixeira em {alerta['localizacao']} está com {alerta['nivel']:.1f}% de preenchimento.",
                    lixeira_id=alerta['lixeira_id']
                )
                
                # Obter emails de admins
                admins = db.query(Usuario).filter(
                    Usuario.admin == True,
                    Usuario.ativo == True
                ).all()
                
                if admins:
                    emails = [admin.email for admin in admins if admin.email]
                    
                    if emails:
                        corpo_html = f"""
                        <html>
                        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                            <h2 style="color: #27ae60;">⚠️ Alerta: Lixeira com Nível Alto</h2>
                            <p><strong>Lixeira:</strong> #{alerta['lixeira_id']} - {alerta['localizacao']}</p>
                            <p><strong>Nível de Preenchimento:</strong> {alerta['nivel']:.1f}%</p>
                            <p><strong>Status:</strong> {alerta['status']}</p>
                            <p style="margin-top: 20px; color: #666; font-size: 12px;">
                                Dashboard-TRONIK - Sistema de Monitoramento
                            </p>
                        </body>
                        </html>
                        """
                        
                        if enviar_email_notificacao(emails, notificacao.titulo, corpo_html):
                            notificacao.enviada = True
                            notificacao.enviada_em = utc_now_naive()
                            db.commit()
                            stats['emails_enviados'] += len(emails)
                
                stats['lixeiras_alertadas'] += 1
            except Exception as e:
                logger.error(f"Erro ao processar alerta de lixeira {alerta['lixeira_id']}: {e}")
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
                    mensagem=f"O sensor da lixeira em {alerta['localizacao']} está com {alerta['bateria']:.1f}% de bateria.",
                    sensor_id=alerta['sensor_id'],
                    lixeira_id=alerta['lixeira_id']
                )
                
                # Obter emails de admins
                admins = db.query(Usuario).filter(
                    Usuario.admin == True,
                    Usuario.ativo == True
                ).all()
                
                if admins:
                    emails = [admin.email for admin in admins if admin.email]
                    
                    if emails:
                        corpo_html = f"""
                        <html>
                        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                            <h2 style="color: #f39c12;">🔋 Alerta: Bateria Baixa</h2>
                            <p><strong>Sensor:</strong> #{alerta['sensor_id']}</p>
                            <p><strong>Lixeira:</strong> #{alerta['lixeira_id']} - {alerta['localizacao']}</p>
                            <p><strong>Nível de Bateria:</strong> {alerta['bateria']:.1f}%</p>
                            <p style="margin-top: 20px; color: #666; font-size: 12px;">
                                Dashboard-TRONIK - Sistema de Monitoramento
                            </p>
                        </body>
                        </html>
                        """
                        
                        if enviar_email_notificacao(emails, notificacao.titulo, corpo_html):
                            notificacao.enviada = True
                            notificacao.enviada_em = utc_now_naive()
                            db.commit()
                            stats['emails_enviados'] += len(emails)
                
                stats['sensores_alertados'] += 1
            except Exception as e:
                logger.error(f"Erro ao processar alerta de sensor {alerta['sensor_id']}: {e}")
                stats['erros'] += 1
        
        return stats
    except Exception as e:
        logger.error(f"Erro ao processar alertas: {e}")
        stats['erros'] += 1
        return stats


