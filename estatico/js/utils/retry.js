/**
 * Sistema de Retry - Dashboard-TRONIK (Frontend)
 * ===============================================
 * Implementa retry automático para requisições HTTP.
 */

/**
 * Executa uma função com retry automático
 * 
 * @param {Function} fn - Função assíncrona a executar
 * @param {Object} opcoes - Opções de retry
 * @param {number} opcoes.maxTentativas - Número máximo de tentativas (padrão: 3)
 * @param {number} opcoes.delayInicial - Delay inicial em ms (padrão: 1000)
 * @param {number} opcoes.fatorBackoff - Fator de backoff exponencial (padrão: 2)
 * @param {Function} opcoes.deveTentar - Função que determina se deve tentar novamente (padrão: sempre true)
 * @returns {Promise} Resultado da função
 */
async function executarComRetry(fn, opcoes = {}) {
    const {
        maxTentativas = 3,
        delayInicial = 1000,
        fatorBackoff = 2,
        deveTentar = () => true
    } = opcoes;
    
    let ultimoErro;
    let delay = delayInicial;
    
    for (let tentativa = 1; tentativa <= maxTentativas; tentativa++) {
        try {
            return await fn();
        } catch (erro) {
            ultimoErro = erro;
            
            // Verificar se deve tentar novamente
            if (!deveTentar(erro, tentativa)) {
                throw erro;
            }
            
            // Se não for a última tentativa, aguardar antes de tentar novamente
            if (tentativa < maxTentativas) {
                await aguardar(delay);
                delay *= fatorBackoff; // Backoff exponencial
            }
        }
    }
    
    // Todas as tentativas falharam
    throw ultimoErro;
}

/**
 * Aguarda um período de tempo
 */
function aguardar(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Determina se um erro de rede deve ser retentado
 */
function deveRetentarErroRede(erro) {
    // Retentar erros de rede (sem resposta do servidor)
    if (erro instanceof TypeError && erro.message.includes('fetch')) {
        return true;
    }
    
    // Retentar erros 5xx (erros do servidor)
    if (erro.status >= 500 && erro.status < 600) {
        return true;
    }
    
    // Retentar erros 429 (rate limit) - mas com mais cuidado
    if (erro.status === 429) {
        return true;
    }
    
    // Não retentar outros erros (4xx, etc)
    return false;
}

// Exportar
window.Retry = {
    executarComRetry,
    deveRetentarErroRede
};

