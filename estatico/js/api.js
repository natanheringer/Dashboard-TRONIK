/*
API JavaScript - Dashboard-TRONIK
================================
Funções para comunicação com o backend.
Gerencia todas as requisições HTTP para a API.
Usa sistema de retry automático e cache.
*/

// Configuração base da API
const API_BASE_URL = '/api';

// Função auxiliar para fazer requisições com retry automático
async function fazerRequisicao(endpoint, options = {}) {
    // Timeout de 30 segundos
    const TIMEOUT_MS = 30000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);
    
    // Usar retry automático se disponível
    if (window.Retry && window.Retry.executarComRetry) {
        try {
            return await window.Retry.executarComRetry(
                async () => {
                    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                        headers: {
                            'Content-Type': 'application/json',
                            ...options.headers
                        },
                        signal: controller.signal,
                        ...options
                    });
                    
                    clearTimeout(timeoutId);
                    
                    if (!response.ok) {
                        const erro = await response.json().catch(() => ({ erro: 'Erro desconhecido' }));
                        const errorObj = new Error(erro.erro || `Erro HTTP: ${response.status}`);
                        errorObj.status = response.status;
                        throw errorObj;
                    }
                    
                    return await response.json();
                },
                {
                    maxTentativas: 3,
                    delayInicial: 1000,
                    deveTentar: (erro) => window.Retry.deveRetentarErroRede(erro)
                }
            );
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                const timeoutError = new Error('Requisição expirou (timeout de 30s)');
                timeoutError.name = 'TimeoutError';
                throw timeoutError;
            }
            throw error;
        }
    } else {
        // Fallback sem retry
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                signal: controller.signal,
                ...options
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                const erro = await response.json().catch(() => ({ erro: 'Erro desconhecido' }));
                throw new Error(erro.erro || `Erro HTTP: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                const timeoutError = new Error('Requisição expirou (timeout de 30s)');
                timeoutError.name = 'TimeoutError';
                if (window.Logger) {
                    window.Logger.error('Timeout na requisição:', timeoutError);
                } else {
                    console.error('Timeout na requisição:', timeoutError);
                }
                throw timeoutError;
            }
            if (window.Logger) {
                window.Logger.error('Erro na requisição:', error);
            } else {
                console.error('Erro na requisição:', error);
            }
            throw error;
        }
    }
}

// Função auxiliar para requisições GET com cache
async function fazerRequisicaoComCache(endpoint, ttl = 5 * 60 * 1000) {
    if (window.CacheFrontend) {
        return await window.CacheFrontend.obterOuCalcular(
            `api:${endpoint}`,
            () => fazerRequisicao(endpoint),
            ttl
        );
    } else {
        return await fazerRequisicao(endpoint);
    }
}

// Função para obter todos os coletores (com cache)
async function obterTodosColetores() {
    try {
        const resultado = await fazerRequisicaoComCache('/coletores', 2 * 60 * 1000); // Cache de 2 minutos
        // Ajustar para formato paginado (se aplicável)
        if (resultado && resultado.dados) {
            return Array.isArray(resultado.dados) ? resultado.dados : [];
        }
        // Se não for formato paginado, retornar direto (compatibilidade)
        return Array.isArray(resultado) ? resultado : [];
    } catch (error) {
        console.error('Erro ao obter coletores:', error);
        return [];  // Retornar array vazio em caso de erro
    }
}

// Função para obter coletor específico
async function obterColetor(id) {
    return await fazerRequisicao(`/coletor/${id}`);
}

// Função para criar novo coletor
async function criarColetor(dados) {
    return await fazerRequisicao('/coletor', {
        method: 'POST',
        body: JSON.stringify(dados)
    });
}

// Função para atualizar coletor
async function atualizarColetor(id, dados) {
    return await fazerRequisicao(`/coletor/${id}`, {
        method: 'PUT',
        body: JSON.stringify(dados)
    });
}

// Função para deletar coletor
async function deletarColetor(id) {
    return await fazerRequisicao(`/coletor/${id}`, {
        method: 'DELETE'
    });
}

// Função para obter estatísticas (com cache)
async function obterEstatisticas() {
    return await fazerRequisicaoComCache('/estatisticas', 5 * 60 * 1000); // Cache de 5 minutos
}

// Função para obter histórico de coletas
async function obterHistorico(dataFiltro = null) {
    let url = '/historico';
    if (dataFiltro) {
        url += '?data=' + encodeURIComponent(dataFiltro);
    }
    const resposta = await fazerRequisicao(url);
    // Se a resposta for paginada, extrair o array de dados
    if (resposta && typeof resposta === 'object' && 'dados' in resposta) {
        return resposta.dados;
    }
    // Se for array direto (compatibilidade com versão antiga)
    return Array.isArray(resposta) ? resposta : [];
}

// Função para obter coletas (novo endpoint com filtros)
async function obterColetas(filtros = {}) {
    let url = '/coletas';
    const params = new URLSearchParams();
    
    if (filtros.coletor_id) params.append('coletor_id', filtros.coletor_id);
    if (filtros.parceiro_id) params.append('parceiro_id', filtros.parceiro_id);
    if (filtros.tipo_operacao) params.append('tipo_operacao', filtros.tipo_operacao);
    if (filtros.data_inicio) params.append('data_inicio', filtros.data_inicio);
    if (filtros.data_fim) params.append('data_fim', filtros.data_fim);
    
    if (params.toString()) {
        url += '?' + params.toString();
    }
    
    return await fazerRequisicao(url);
}

// Função para criar coleta
async function criarColeta(dados) {
    return await fazerRequisicao('/coleta', {
        method: 'POST',
        body: JSON.stringify(dados)
    });
}

// Função para obter parceiros
async function obterParceiros() {
    return await fazerRequisicao('/parceiros');
}

// Função para obter tipos de material
async function obterTiposMaterial() {
    return await fazerRequisicao('/tipos/material');
}

// Função para obter tipos de sensor
async function obterTiposSensor() {
    return await fazerRequisicao('/tipos/sensor');
}

// Função para obter tipos de coletor
async function obterTiposColetor() {
    return await fazerRequisicao('/tipos/coletor');
}

// Função para obter configurações
async function obterConfiguracoes() {
    return await fazerRequisicao('/configuracoes');
}

// Função para obter relatórios
async function obterRelatorios(dataInicio = null, dataFim = null, parceiroId = null, tipoOperacao = null) {
    let url = '/relatorios';
    const params = new URLSearchParams();
    
    if (dataInicio) params.append('data_inicio', dataInicio);
    if (dataFim) params.append('data_fim', dataFim);
    if (parceiroId) params.append('parceiro_id', parceiroId);
    if (tipoOperacao) params.append('tipo_operacao', tipoOperacao);
    
    if (params.toString()) {
        url += '?' + params.toString();
    }
    
    return await fazerRequisicao(url);
}

// Função para simular níveis das coletores
async function simularNiveis({ delta_max = 10, reduzir_max = 5 } = {}) {
    return await fazerRequisicao('/coletores/simular-niveis', {
        method: 'POST',
        body: JSON.stringify({ delta_max, reduzir_max })
    });
}

// ============================================================
// FUNÇÕES DE API PARA SENSORES
// ============================================================

// Função para obter todos os sensores
async function obterTodosSensores(filtros = {}) {
    let url = '/sensores';
    const params = new URLSearchParams();
    
    if (filtros.coletor_id) params.append('coletor_id', filtros.coletor_id);
    if (filtros.tipo_sensor_id) params.append('tipo_sensor_id', filtros.tipo_sensor_id);
    if (filtros.bateria_min) params.append('bateria_min', filtros.bateria_min);
    if (filtros.bateria_max) params.append('bateria_max', filtros.bateria_max);
    
    if (params.toString()) {
        url += '?' + params.toString();
    }
    
    return await fazerRequisicao(url);
}

// Função para obter sensor específico
async function obterSensor(id) {
    return await fazerRequisicao(`/sensor/${id}`);
}

// Função para criar novo sensor
async function criarSensor(dados) {
    return await fazerRequisicao('/sensor', {
        method: 'POST',
        body: JSON.stringify(dados)
    });
}

// Função para atualizar sensor
async function atualizarSensor(id, dados) {
    return await fazerRequisicao(`/sensor/${id}`, {
        method: 'PUT',
        body: JSON.stringify(dados)
    });
}

// Função para deletar sensor
async function deletarSensor(id) {
    return await fazerRequisicao(`/sensor/${id}`, {
        method: 'DELETE'
    });
}

// Funções para Notificações
async function obterNotificacoes(filtros = {}) {
    let url = '/notificacoes';
    const params = new URLSearchParams();
    
    if (filtros.tipo) params.append('tipo', filtros.tipo);
    if (filtros.enviada !== undefined) params.append('enviada', filtros.enviada);
    if (filtros.coletor_id) params.append('coletor_id', filtros.coletor_id);
    if (filtros.limite) params.append('limite', filtros.limite);
    
    if (params.toString()) {
        url += '?' + params.toString();
    }
    
    return await fazerRequisicao(url);
}

async function processarAlertas() {
    return await fazerRequisicao('/notificacoes/processar-alertas', {
        method: 'POST'
    });
}

async function marcarNotificacaoLida(notificacaoId) {
    return await fazerRequisicao(`/notificacoes/${notificacaoId}/marcar-lida`, {
        method: 'PUT'
    });
}

async function obterNotificacoesPendentesCount() {
    return await fazerRequisicao('/notificacoes/pendentes-count');
}

async function obterStatusAgendamento() {
    return await fazerRequisicao('/notificacoes/status-agendamento');
}

// Exportar funções (para uso em outros scripts)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        obterTodosColetores,
        obterColetor,
        criarColetor,
        atualizarColetor,
        deletarColetor,
        // Compatibilidade: manter funções antigas por enquanto
        obterTodasLixeiras: obterTodosColetores,
        obterLixeira: obterColetor,
        criarLixeira: criarColetor,
        atualizarLixeira: atualizarColetor,
        deletarLixeira: deletarColetor,
        obterEstatisticas,
        obterHistorico,
        obterColetas,
        criarColeta,
        obterParceiros,
        obterTiposMaterial,
        obterTiposSensor,
        obterTiposColetor,
        obterConfiguracoes,
        obterRelatorios,
        simularNiveis,
        obterTodosSensores,
        obterSensor,
        criarSensor,
        atualizarSensor,
        deletarSensor,
        obterNotificacoes,
        processarAlertas,
        marcarNotificacaoLida,
        obterNotificacoesPendentesCount,
        obterStatusAgendamento
    };
}
