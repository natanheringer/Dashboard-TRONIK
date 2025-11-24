"""
WebSocket Routes - Dashboard-TRONIK
====================================
Rotas WebSocket para atualizações em tempo real.
"""

from flask import Blueprint
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import current_user
from banco_dados.utils.logger import obter_logger

logger = obter_logger(__name__)

# Criar blueprint (será registrado no app.py)
websocket_bp = Blueprint('websocket', __name__)

# Instância do SocketIO será criada no app.py
socketio = None


def inicializar_websocket(app):
    """
    Inicializa o SocketIO com a aplicação Flask.
    Deve ser chamado no app.py após criar a app.
    """
    global socketio
    from flask_socketio import SocketIO
    
    try:
        socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode='threading',
            logger=False,  # Desabilitar logger para evitar problemas
            engineio_logger=False,  # Desabilitar engineio logger
            ping_timeout=60,
            ping_interval=25
        )
        
        # Registrar handlers após inicializar socketio
        registrar_handlers()
        
        logger.info("WebSocket inicializado com sucesso")
        return socketio
    except Exception as e:
        logger.error(f"Erro ao inicializar WebSocket: {e}", exc_info=True)
        # Retornar None se falhar, mas não quebrar a aplicação
        return None


def registrar_handlers():
    """Registra todos os handlers WebSocket"""
    if not socketio:
        return
    
    @socketio.on('connect')
    def handle_connect(auth=None):
        """Manipula conexão WebSocket"""
        try:
            # Verificar autenticação de forma segura
            from flask_login import current_user
            try:
                is_authenticated = current_user.is_authenticated if hasattr(current_user, 'is_authenticated') else False
            except:
                is_authenticated = False
            
            if is_authenticated:
                username = getattr(current_user, 'username', 'unknown')
                logger.info(f"Cliente WebSocket conectado: {username}")
                try:
                    emit('connected', {'message': 'Conectado ao servidor WebSocket'})
                except Exception as emit_error:
                    logger.error(f"Erro ao emitir mensagem de conexão: {emit_error}")
                return True
            else:
                logger.warning("Tentativa de conexão WebSocket não autenticada - permitindo conexão")
                # Permitir conexão mesmo sem autenticação para evitar erro 500
                # A autenticação será verificada em cada evento específico
                return True
        except Exception as e:
            logger.error(f"Erro ao processar conexão WebSocket: {e}", exc_info=True)
            # Retornar True para evitar erro 500, mas logar o erro
            return True
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Manipula desconexão WebSocket"""
        try:
            from flask_login import current_user
            if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                username = getattr(current_user, 'username', 'unknown')
                logger.info(f"Cliente WebSocket desconectado: {username}")
        except Exception as e:
            logger.debug(f"Erro ao processar desconexão: {e}")
    
    @socketio.on('join_room')
    def handle_join_room(data):
        """Permite que cliente entre em uma sala (room)"""
        if not current_user.is_authenticated:
            return False
        
        room = data.get('room', 'default')
        join_room(room)
        logger.info(f"Usuário {current_user.username} entrou na sala: {room}")
        emit('joined_room', {'room': room})
    
    @socketio.on('leave_room')
    def handle_leave_room(data):
        """Permite que cliente saia de uma sala"""
        if not current_user.is_authenticated:
            return False
        
        room = data.get('room', 'default')
        leave_room(room)
        logger.info(f"Usuário {current_user.username} saiu da sala: {room}")
        emit('left_room', {'room': room})
    
    @socketio.on('subscribe_lixeiras')
    def handle_subscribe_lixeiras():
        """Cliente se inscreve para atualizações de coletores"""
        if not current_user.is_authenticated:
            return False
        
        join_room('coletores')
        logger.info(f"Usuário {current_user.username} inscrito em atualizações de coletores")
        emit('subscribed', {'topic': 'coletores'})
    
    @socketio.on('subscribe_sensores')
    def handle_subscribe_sensores():
        """Cliente se inscreve para atualizações de sensores"""
        if not current_user.is_authenticated:
            return False
        
        join_room('sensores')
        logger.info(f"Usuário {current_user.username} inscrito em atualizações de sensores")
        emit('subscribed', {'topic': 'sensores'})
    
    @socketio.on('subscribe_notificacoes')
    def handle_subscribe_notificacoes():
        """Cliente se inscreve para atualizações de notificações"""
        if not current_user.is_authenticated:
            return False
        
        join_room('notificacoes')
        logger.info(f"Usuário {current_user.username} inscrito em atualizações de notificações")
        emit('subscribed', {'topic': 'notificacoes'})


# Funções para emitir atualizações (chamadas de outros módulos)
def emitir_atualizacao_coletor(coletor_data, evento='coletor_atualizado'):
    """
    Emite atualização de coletor para todos os clientes inscritos.
    
    Args:
        coletor_data: Dicionário com dados da coletor
        evento: Nome do evento (padrão: 'lixeira_atualizada')
    """
    if socketio:
        socketio.emit(evento, coletor_data, room='coletores')
        logger.debug(f"Atualização de coletor emitida: {coletor_data.get('id')}")


def emitir_atualizacao_sensor(sensor_data, evento='sensor_atualizado'):
    """
    Emite atualização de sensor para todos os clientes inscritos.
    
    Args:
        sensor_data: Dicionário com dados do sensor
        evento: Nome do evento (padrão: 'sensor_atualizado')
    """
    if socketio:
        socketio.emit(evento, sensor_data, room='sensores')
        logger.debug(f"Atualização de sensor emitida: {sensor_data.get('id')}")


def emitir_nova_notificacao(notificacao_data):
    """
    Emite nova notificação para todos os clientes inscritos.
    
    Args:
        notificacao_data: Dicionário com dados da notificação
    """
    if socketio:
        socketio.emit('nova_notificacao', notificacao_data, room='notificacoes')
        logger.debug(f"Nova notificação emitida: {notificacao_data.get('id')}")


def emitir_atualizacao_estatisticas(estatisticas_data):
    """
    Emite atualização de estatísticas para todos os clientes.
    
    Args:
        estatisticas_data: Dicionário com estatísticas
    """
    if socketio:
        socketio.emit('estatisticas_atualizadas', estatisticas_data, room='estatisticas')
        logger.debug("Estatísticas atualizadas emitidas")


def emitir_atualizacao_coleta(coleta_data):
    """
    Emite atualização de coleta para todos os clientes.
    
    Args:
        coleta_data: Dicionário com dados da coleta
    """
    if socketio:
        socketio.emit('coleta_criada', coleta_data, room='coletas')
        logger.debug(f"Atualização de coleta emitida: {coleta_data.get('id')}")
