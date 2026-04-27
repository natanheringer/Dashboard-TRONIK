/**
 * Cliente WebSocket - Dashboard-TRONIK
 * ====================================
 * Gerencia conexão WebSocket e atualizações em tempo real.
 */

const WebSocketClient = (function() {
    'use strict';
    
    let socket = null;
    let conectado = false;
    let tentativasReconexao = 0;
    const MAX_TENTATIVAS = 5;
    const DELAY_RECONEXAO = 3000; // 3 segundos
    
    /**
     * Inicializa conexão WebSocket
     */
    function conectar() {
        if (typeof io === 'undefined') {
            if (window.Logger) {
                window.Logger.warn('Socket.IO não está disponível. WebSocket desabilitado.');
            } else {
                console.warn('Socket.IO não está disponível. WebSocket desabilitado.');
            }
            return;
        }
        
        try {
            socket = io({
                transports: ['polling'],
                upgrade: false,
                reconnection: true,
                reconnectionDelay: DELAY_RECONEXAO,
                reconnectionAttempts: MAX_TENTATIVAS
            });
            
            // Eventos de conexão
            socket.on('connect', function() {
                conectado = true;
                tentativasReconexao = 0;
                
                if (window.Logger) {
                    window.Logger.info('WebSocket conectado');
                } else {
                    console.log('WebSocket conectado');
                }
                
                // Inscrever em atualizações
                inscreverEmAtualizacoes();
                
                // Emitir evento customizado
                if (window.dispatchEvent) {
                    window.dispatchEvent(new CustomEvent('websocket:connected'));
                }
            });
            
            socket.on('disconnect', function() {
                conectado = false;
                
                if (window.Logger) {
                    window.Logger.warn('WebSocket desconectado');
                } else {
                    console.warn('WebSocket desconectado');
                }
                
                if (window.dispatchEvent) {
                    window.dispatchEvent(new CustomEvent('websocket:disconnected'));
                }
            });
            
            socket.on('connect_error', function(error) {
                tentativasReconexao++;
                
                if (window.Logger) {
                    window.Logger.error('Erro ao conectar WebSocket:', error);
                } else {
                    console.error('Erro ao conectar WebSocket:', error);
                }
                
                if (tentativasReconexao >= MAX_TENTATIVAS) {
                    if (window.Logger) {
                        window.Logger.error('Máximo de tentativas de reconexão atingido');
                    }
                }
            });
            
            // Eventos de atualização
            socket.on('coletor_atualizado', function(data) {
                if (window.Logger) {
                    window.Logger.debug('Coletor atualizada via WebSocket:', data);
                }
                
                if (window.dispatchEvent) {
                    window.dispatchEvent(new CustomEvent('websocket:coletor_atualizado', {
                        detail: data
                    }));
                }
            });
            
            socket.on('sensor_atualizado', function(data) {
                if (window.Logger) {
                    window.Logger.debug('Sensor atualizado via WebSocket:', data);
                }
                
                if (window.dispatchEvent) {
                    window.dispatchEvent(new CustomEvent('websocket:sensor_atualizado', {
                        detail: data
                    }));
                }
            });
            
            socket.on('nova_notificacao', function(data) {
                if (window.Logger) {
                    window.Logger.info('Nova notificação via WebSocket:', data);
                }
                
                if (window.dispatchEvent) {
                    window.dispatchEvent(new CustomEvent('websocket:nova_notificacao', {
                        detail: data
                    }));
                }
            });
            
            socket.on('estatisticas_atualizadas', function(data) {
                if (window.Logger) {
                    window.Logger.debug('Estatísticas atualizadas via WebSocket');
                }
                
                if (window.dispatchEvent) {
                    window.dispatchEvent(new CustomEvent('websocket:estatisticas_atualizadas', {
                        detail: data
                    }));
                }
            });
            
            socket.on('coleta_criada', function(data) {
                if (window.Logger) {
                    window.Logger.debug('Coleta criada via WebSocket:', data);
                }
                
                if (window.dispatchEvent) {
                    window.dispatchEvent(new CustomEvent('websocket:coleta_criada', {
                        detail: data
                    }));
                }
            });
            
        } catch (error) {
            if (window.Logger) {
                window.Logger.error('Erro ao inicializar WebSocket:', error);
            } else {
                console.error('Erro ao inicializar WebSocket:', error);
            }
        }
    }
    
    /**
     * Inscreve em atualizações
     */
    function inscreverEmAtualizacoes() {
        if (!socket || !conectado) return;
        
        socket.emit('subscribe_lixeiras');
        socket.emit('subscribe_sensores');
        socket.emit('subscribe_notificacoes');
        
        // Inscrever em estatísticas
        socket.emit('join_room', { room: 'estatisticas' });
        socket.emit('join_room', { room: 'coletas' });
    }
    
    /**
     * Desconecta WebSocket
     */
    function desconectar() {
        if (socket) {
            socket.disconnect();
            socket = null;
            conectado = false;
        }
    }
    
    /**
     * Verifica se está conectado
     */
    function estaConectado() {
        return conectado && socket && socket.connected;
    }
    
    return {
        conectar,
        desconectar,
        estaConectado,
        getSocket: () => socket
    };
})();

// Exportar globalmente
window.WebSocketClient = WebSocketClient;

