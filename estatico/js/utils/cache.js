/**
 * Sistema de Cache - Dashboard-TRONIK (Frontend)
 * ================================================
 * Cache simples em memória para requisições GET.
 */

const CacheFrontend = (function() {
    'use strict';
    
    const cache = new Map();
    const pending = new Map();
    const TTL_PADRAO = 5 * 60 * 1000; // 5 minutos
    
    /**
     * Obtém valor do cache
     */
    function obter(chave) {
        const entrada = cache.get(chave);
        if (!entrada) {
            return null;
        }
        
        // Verificar se expirou
        if (Date.now() > entrada.expiracao) {
            cache.delete(chave);
            return null;
        }
        
        return entrada.valor;
    }
    
    /**
     * Define valor no cache
     * Trata quota exceeded do localStorage
     */
    function definir(chave, valor, ttl = TTL_PADRAO) {
        try {
            cache.set(chave, {
                valor: valor,
                expiracao: Date.now() + ttl
            });
        } catch (e) {
            if (e.name === 'QuotaExceededError') {
                // Limpar cache antigo (remover 50% das entradas mais antigas)
                limparCacheAntigo();
                // Tentar novamente
                try {
                    cache.set(chave, {
                        valor: valor,
                        expiracao: Date.now() + ttl
                    });
                } catch (e2) {
                    console.warn('Cache não pôde ser salvo após limpeza:', e2);
                }
            } else {
                throw e;
            }
        }
    }
    
    /**
     * Limpa cache antigo (50% das entradas mais antigas)
     */
    function limparCacheAntigo() {
        const entradas = Array.from(cache.entries());
        if (entradas.length === 0) return;
        
        // Ordenar por expiração (mais antigas primeiro)
        entradas.sort((a, b) => a[1].expiracao - b[1].expiracao);
        
        // Remover 50% das mais antigas
        const quantidadeRemover = Math.floor(entradas.length / 2);
        for (let i = 0; i < quantidadeRemover; i++) {
            cache.delete(entradas[i][0]);
        }
    }
    
    /**
     * Remove entrada do cache
     */
    function invalidar(chave) {
        cache.delete(chave);
    }
    
    /**
     * Limpa todo o cache
     */
    function limpar() {
        cache.clear();
    }
    
    /**
     * Obtém ou calcula valor (padrão de cache)
     */
    async function obterOuCalcular(chave, calcularFn, ttl = TTL_PADRAO) {
        const valor = obter(chave);
        if (valor !== null) {
            return valor;
        }
        if (pending.has(chave)) {
            return pending.get(chave);
        }
        const promessa = (async function () {
            try {
                const novoValor = await calcularFn();
                definir(chave, novoValor, ttl);
                return novoValor;
            } finally {
                pending.delete(chave);
            }
        })();
        pending.set(chave, promessa);
        return promessa;
    }
    
    return {
        obter,
        definir,
        invalidar,
        limpar,
        obterOuCalcular
    };
})();

// Exportar globalmente
window.CacheFrontend = CacheFrontend;

