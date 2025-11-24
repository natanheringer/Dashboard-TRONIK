/**
 * Sistema de Logging - Dashboard-TRONIK (Frontend)
 * ================================================
 * Sistema centralizado de logging para o frontend.
 */

const Logger = (function() {
    'use strict';
    
    // Níveis de log
    const LEVELS = {
        DEBUG: 0,
        INFO: 1,
        WARNING: 2,
        ERROR: 3,
        NONE: 4
    };
    
    // Nível atual (padrão: INFO em produção, DEBUG em desenvolvimento)
    let nivelAtual = window.location.hostname === 'localhost' ? LEVELS.DEBUG : LEVELS.INFO;
    
    /**
     * Configura o nível de log
     */
    function configurar(nivel) {
        if (typeof nivel === 'string') {
            nivelAtual = LEVELS[nivel.toUpperCase()] || LEVELS.INFO;
        } else {
            nivelAtual = nivel;
        }
    }
    
    /**
     * Verifica se deve logar
     */
    function deveLogar(nivel) {
        return nivel >= nivelAtual;
    }
    
    /**
     * Formata mensagem de log
     */
    function formatarMensagem(nivel, mensagem, dados) {
        const timestamp = new Date().toISOString();
        const prefixo = `[${timestamp}] [${nivel}]`;
        
        if (dados && Object.keys(dados).length > 0) {
            return `${prefixo} ${mensagem}`, dados;
        }
        return `${prefixo} ${mensagem}`;
    }
    
    return {
        debug: function(mensagem, dados) {
            if (deveLogar(LEVELS.DEBUG)) {
                const msg = formatarMensagem('DEBUG', mensagem, dados);
                if (dados) {
                    console.debug(msg, dados);
                } else {
                    console.debug(msg);
                }
            }
        },
        
        info: function(mensagem, dados) {
            if (deveLogar(LEVELS.INFO)) {
                const msg = formatarMensagem('INFO', mensagem, dados);
                if (dados) {
                    console.info(msg, dados);
                } else {
                    console.info(msg);
                }
            }
        },
        
        warn: function(mensagem, dados) {
            if (deveLogar(LEVELS.WARNING)) {
                const msg = formatarMensagem('WARNING', mensagem, dados);
                if (dados) {
                    console.warn(msg, dados);
                } else {
                    console.warn(msg);
                }
            }
        },
        
        error: function(mensagem, erro) {
            if (deveLogar(LEVELS.ERROR)) {
                const msg = formatarMensagem('ERROR', mensagem);
                if (erro) {
                    console.error(msg, erro);
                } else {
                    console.error(msg);
                }
            }
        },
        
        configurar: configurar,
        
        LEVELS: LEVELS
    };
})();

// Exportar globalmente
window.Logger = Logger;

