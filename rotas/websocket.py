"""
WebSocket Routes - Dashboard-TRONIK
====================================
Rotas WebSocket para atualizações em tempo real.
"""

import os

from flask import Blueprint
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import current_user
from banco_dados.utils.logger import obter_logger
import re

logger = obter_logger(__name__)

# Criar blueprint (será registrado no app.py)
websocket_bp = Blueprint('websocket', __name__)

# Instância do SocketIO será criada no app.py
socketio = None


def _origens_socket_io():
    """Alinha CORS do Engine.IO a ``CORS_ORIGINS`` (mesma lista da API)."""
    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5000,http://127.0.0.1:5000",
    )
    partes = [p.strip() for p in raw.split(",") if p.strip()]
    if not partes:
        return ["http://localhost:5000"]
    return partes


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
            cors_allowed_origins=_origens_socket_io(),
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
        """
        Manipula conexão WebSocket com autenticação obrigatória.
        
        Args:
            auth: Dicionário opcional com token de autenticação (para futuro)
        """
        try:
            # Verificar autenticação de forma segura
            from flask_login import current_user
            from flask import request
            
            # Tentar obter usuário autenticado
            is_authenticated = False
            username = 'unknown'
            
            try:
                # Verificar se há sessão Flask-Login ativa
                if hasattr(current_user, 'is_authenticated'):
                    is_authenticated = current_user.is_authenticated
                    if is_authenticated:
                        username = getattr(current_user, 'username', 'unknown')
            except Exception as auth_error:
                logger.debug(f"Erro ao verificar autenticação: {auth_error}")
                is_authenticated = False
            
            # Se não autenticado, verificar token na query string (fallback)
            if not is_authenticated and auth and isinstance(auth, dict):
                # Futuro: validar token JWT aqui
                logger.debug("Autenticação via token não implementada ainda")
            
            # Exigir autenticação para conexão
            if not is_authenticated:
                logger.warning(f"Tentativa de conexão WebSocket não autenticada de {request.remote_addr}")
                # Rejeitar conexão não autenticada
                emit('error', {'message': 'Autenticação necessária'})
                return False
            
            # Conexão autenticada - permitir
            logger.info(f"Cliente WebSocket conectado: {username} ({request.remote_addr})")
            try:
                emit('connected', {
                    'message': 'Conectado ao servidor WebSocket',
                    'username': username
                })
            except Exception as emit_error:
                logger.error(f"Erro ao emitir mensagem de conexão: {emit_error}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao processar conexão WebSocket: {e}", exc_info=True)
            # Em caso de erro, rejeitar conexão por segurança
            try:
                emit('error', {'message': 'Erro ao conectar'})
            except:
                pass
            return False
    
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
        """
        Permite que cliente entre em uma sala (room) com validação de segurança.
        
        Args:
            data: Dicionário com 'room' (nome da sala)
        """
        try:
            # Verificar autenticação
            if not hasattr(current_user, 'is_authenticated') or not current_user.is_authenticated:
                logger.warning("Tentativa de join_room sem autenticação")
                emit('error', {'message': 'Autenticação necessária'})
                return False
            
            # Validar e sanitizar nome da sala
            if not data or not isinstance(data, dict):
                emit('error', {'message': 'Dados inválidos'})
                return False
            
            room = data.get('room', 'default')
            if not room or not isinstance(room, str):
                emit('error', {'message': 'Nome de sala inválido'})
                return False
            
            # Sanitizar nome da sala (apenas alfanuméricos, underscore, hífen)
            from banco_dados.seguranca import sanitizar_string
            room = sanitizar_string(room, max_length=50)
            if not re.match(r'^[a-zA-Z0-9_-]+$', room):
                logger.warning(f"Nome de sala inválido tentado: {room}")
                emit('error', {'message': 'Nome de sala inválido'})
                return False
            
            # Permitir apenas salas conhecidas (whitelist)
            salas_permitidas = ['coletores', 'sensores', 'notificacoes', 'coletas', 'estatisticas', 'default']
            if room not in salas_permitidas:
                logger.warning(f"Tentativa de entrar em sala não permitida: {room}")
                emit('error', {'message': 'Sala não permitida'})
                return False
            
            join_room(room)
            logger.info(f"Usuário {current_user.username} entrou na sala: {room}")
            emit('joined_room', {'room': room})
            return True
            
        except Exception as e:
            logger.error(f"Erro ao processar join_room: {e}", exc_info=True)
            emit('error', {'message': 'Erro ao entrar na sala'})
            return False
    
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
