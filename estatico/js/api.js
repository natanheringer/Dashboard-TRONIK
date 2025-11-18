/*
API JavaScript - Dashboard-TRONIK
================================
Funções para comunicação com o backend.
Gerencia todas as requisições HTTP para a API.
*/

// Configuração base da API
const API_BASE_URL = '/api';

// Função auxiliar para fazer requisições
async function fazerRequisicao(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            const erro = await response.json().catch(() => ({ erro: 'Erro desconhecido' }));
            throw new Error(erro.erro || `Erro HTTP: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Erro na requisição:', error);
        throw error;
    }
}

// Função para obter todas as lixeiras
async function obterTodasLixeiras() {
    return await fazerRequisicao('/lixeiras');
}

// Função para obter lixeira específica
async function obterLixeira(id) {
    return await fazerRequisicao(`/lixeira/${id}`);
}

// Função para criar nova lixeira
async function criarLixeira(dados) {
    return await fazerRequisicao('/lixeira', {
        method: 'POST',
        body: JSON.stringify(dados)
    });
}

// Função para atualizar lixeira
async function atualizarLixeira(id, dados) {
    return await fazerRequisicao(`/lixeira/${id}`, {
        method: 'PUT',
        body: JSON.stringify(dados)
    });
}

// Função para deletar lixeira
async function deletarLixeira(id) {
    return await fazerRequisicao(`/lixeira/${id}`, {
        method: 'DELETE'
    });
}

// Função para obter estatísticas
async function obterEstatisticas() {
    return await fazerRequisicao('/estatisticas');
}

// Função para obter histórico de coletas
async function obterHistorico(dataFiltro = null) {
    let url = '/historico';
    if (dataFiltro) {
        url += '?data=' + encodeURIComponent(dataFiltro);
    }
    return await fazerRequisicao(url);
}

// Função para obter coletas (novo endpoint com filtros)
async function obterColetas(filtros = {}) {
    let url = '/coletas';
    const params = new URLSearchParams();
    
    if (filtros.lixeira_id) params.append('lixeira_id', filtros.lixeira_id);
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

// Função para simular níveis das lixeiras
async function simularNiveis({ delta_max = 10, reduzir_max = 5 } = {}) {
    return await fazerRequisicao('/lixeiras/simular-niveis', {
        method: 'POST',
        body: JSON.stringify({ delta_max, reduzir_max })
    });
}

// Exportar funções (para uso em outros scripts)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        obterTodasLixeiras,
        obterLixeira,
        criarLixeira,
        atualizarLixeira,
        deletarLixeira,
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
        simularNiveis
    };
}
