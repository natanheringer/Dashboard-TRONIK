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
async function obterHistorico() {
    return await fazerRequisicao('/historico');
}

// Função para obter configurações
async function obterConfiguracoes() {
    return await fazerRequisicao('/configuracoes');
}

// Função para obter relatórios
async function obterRelatorios(dataInicio = null, dataFim = null) {
    let url = '/relatorios';
    const params = new URLSearchParams();
    
    if (dataInicio) params.append('data_inicio', dataInicio);
    if (dataFim) params.append('data_fim', dataFim);
    
    if (params.toString()) {
        url += '?' + params.toString();
    }
    
    return await fazerRequisicao(url);
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
        obterConfiguracoes,
        obterRelatorios
    };
}
