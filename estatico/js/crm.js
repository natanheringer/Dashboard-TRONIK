/**
 * CRM - Dashboard-TRONIK
 * ======================
 * Lógica frontend para o CRM e pipeline de vendas.
 */

let pipelineData = [];
let tarefasData = [];
let funilData = {};
let estatisticasData = {};

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    carregarEstatisticas();
    carregarPipeline();
    carregarTarefas();
    carregarFunil();
    
    // Atualizar a cada 5 minutos
    setInterval(() => {
        carregarEstatisticas();
        carregarPipeline();
        carregarTarefas();
        carregarFunil();
    }, 5 * 60 * 1000);
});

// Carregar estatísticas
async function carregarEstatisticas() {
    try {
        const response = await fetch('/api/crm/estatisticas');
        if (!response.ok) {
            console.error('Erro HTTP ao carregar estatísticas:', response.status, response.statusText);
            throw new Error('Erro ao carregar estatísticas');
        }
        
        estatisticasData = await response.json();
        console.log('Estatísticas carregadas:', estatisticasData);
        renderizarEstatisticas();
    } catch (erro) {
        console.error('Erro ao carregar estatísticas:', erro);
        // Mostrar valores padrão mesmo em caso de erro
        renderizarEstatisticas();
    }
}

// Renderizar estatísticas (KPIs)
function renderizarEstatisticas() {
    const kpiAtivos = document.getElementById('kpi-ativos');
    const kpiValor = document.getElementById('kpi-valor-pipeline');
    const kpiFechados = document.getElementById('kpi-fechados-mes');
    const kpiTarefas = document.getElementById('kpi-tarefas');
    const kpiAtrasadas = document.getElementById('kpi-atrasadas');
    const kpiProximas = document.getElementById('kpi-proximas');
    
    if (kpiAtivos) kpiAtivos.textContent = estatisticasData.pipelines_ativos || 0;
    if (kpiValor) kpiValor.textContent = formatarMoeda(estatisticasData.valor_total_pipeline || 0);
    if (kpiFechados) kpiFechados.textContent = formatarMoeda(estatisticasData.valor_fechado_mes || 0);
    if (kpiTarefas) kpiTarefas.textContent = estatisticasData.tarefas_pendentes || 0;
    if (kpiAtrasadas) kpiAtrasadas.textContent = estatisticasData.tarefas_atrasadas || 0;
    if (kpiProximas) kpiProximas.textContent = estatisticasData.proximas_acoes || 0;
}

// Carregar pipeline
async function carregarPipeline() {
    try {
        const response = await fetch('/api/crm/pipeline');
        if (!response.ok) {
            console.error('Erro HTTP ao carregar pipeline:', response.status, response.statusText);
            throw new Error('Erro ao carregar pipeline');
        }
        
        pipelineData = await response.json();
        console.log('Pipeline carregado:', pipelineData);
        renderizarPipeline();
        renderizarFunil();
    } catch (erro) {
        console.error('Erro ao carregar pipeline:', erro);
        mostrarErro('Erro ao carregar pipeline');
        // Limpar containers em caso de erro
        const container = document.getElementById('pipeline-container');
        if (container) {
            container.innerHTML = '<p style="text-align: center; color: #ef4444; padding: 2rem;">Erro ao carregar pipeline. Tente atualizar a página.</p>';
        }
    }
}

// Carregar tarefas
async function carregarTarefas() {
    try {
        const response = await fetch('/api/crm/tarefas');
        if (!response.ok) {
            console.error('Erro HTTP ao carregar tarefas:', response.status, response.statusText);
            throw new Error('Erro ao carregar tarefas');
        }
        
        tarefasData = await response.json();
        console.log('Tarefas carregadas:', tarefasData);
        renderizarTarefas();
    } catch (erro) {
        console.error('Erro ao carregar tarefas:', erro);
        const container = document.getElementById('tarefas-container');
        if (container) {
            container.innerHTML = '<p style="text-align: center; color: #ef4444; padding: 2rem;">Erro ao carregar tarefas. Tente atualizar a página.</p>';
        }
    }
}

// Carregar funil
async function carregarFunil() {
    try {
        const response = await fetch('/api/crm/funil');
        if (!response.ok) {
            console.error('Erro HTTP ao carregar funil:', response.status, response.statusText);
            throw new Error('Erro ao carregar funil');
        }
        
        funilData = await response.json();
        console.log('Funil carregado:', funilData);
        // O funil é renderizado junto com o pipeline
        // renderizarFunil() é chamado em carregarPipeline()
    } catch (erro) {
        console.error('Erro ao carregar funil:', erro);
        // O funil será renderizado vazio se não houver dados
    }
}

// Renderizar pipeline (função unificada)

// Renderizar tarefas
function renderizarTarefas() {
    const container = document.getElementById('tarefas-container');
    if (!container) {
        console.error('Container tarefas-container não encontrado');
        return;
    }
    
    if (!tarefasData || tarefasData.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #64748b; padding: 2rem;">Nenhuma tarefa pendente</p>';
        return;
    }
    
    container.innerHTML = tarefasData.map(tarefa => `
        <div class="tarefa-item ${tarefa.atrasada ? 'atrasada' : ''}">
            <div class="tarefa-info">
                <strong>${tarefa.titulo}</strong>
                <span class="tarefa-prioridade prioridade-${tarefa.prioridade}">${tarefa.prioridade}</span>
            </div>
            <div class="tarefa-detalhes">
                ${tarefa.data_vencimento ? `<span>Vence: ${formatarData(tarefa.data_vencimento)}</span>` : ''}
                ${tarefa.cliente ? `<span>Cliente: ${tarefa.cliente}</span>` : ''}
            </div>
            <div class="tarefa-acoes">
                <button class="btn btn-xs btn-primario" onclick="concluirTarefa(${tarefa.id})">Concluir</button>
            </div>
        </div>
    `).join('');
}

// Renderizar funil
function renderizarFunil() {
    const statusMap = {
        'lead': { container: 'funil-lead', count: 'count-lead', valor: 'valor-lead' },
        'contato_inicial': { container: 'funil-contato', count: 'count-contato', valor: 'valor-contato' },
        'proposta_enviada': { container: 'funil-proposta', count: 'count-proposta', valor: 'valor-proposta' },
        'negociacao': { container: 'funil-negociacao', count: 'count-negociacao', valor: 'valor-negociacao' },
        'fechado': { container: 'funil-fechado', count: 'count-fechado', valor: 'valor-fechado' }
    };
    
    // Limpar funil
    Object.values(statusMap).forEach(({ container }) => {
        const el = document.getElementById(container);
        if (el) el.innerHTML = '';
    });
    
    // Agrupar por status
    const pipelinePorStatus = {};
    (pipelineData || []).forEach(item => {
        if (!pipelinePorStatus[item.status]) {
            pipelinePorStatus[item.status] = [];
        }
        pipelinePorStatus[item.status].push(item);
    });
    
    // Renderizar cada coluna
    Object.entries(statusMap).forEach(([status, { container, count, valor }]) => {
        const containerEl = document.getElementById(container);
        const countEl = document.getElementById(count);
        const valorEl = document.getElementById(valor);
        
        if (!containerEl) return;
        
        const items = pipelinePorStatus[status] || [];
        const totalValor = items.reduce((sum, item) => sum + (item.valor_estimado || 0), 0);
        
        // Atualizar contador
        if (countEl) {
            countEl.textContent = items.length;
        }
        
        // Atualizar valor total
        if (valorEl) {
            valorEl.textContent = formatarMoeda(totalValor);
        }
        
        // Renderizar items
        if (items.length === 0) {
            containerEl.innerHTML = '<div class="funil-vazio">Nenhum item</div>';
            return;
        }
        
        containerEl.innerHTML = items.map(item => `
            <div class="funil-item" onclick="verDetalhesPipeline(${item.id})">
                <div class="funil-item-titulo">${item.coletor?.localizacao || 'Lead #' + item.id}</div>
                <div class="funil-item-valor">${formatarMoeda(item.valor_estimado)}</div>
                <div class="funil-item-prob">Probabilidade: ${item.probabilidade}%</div>
            </div>
        `).join('');
    });
}

// Filtrar pipeline
function filtrarPipeline() {
    const filtroStatus = document.getElementById('filtro-status')?.value || '';
    const busca = document.getElementById('busca-pipeline')?.value.toLowerCase() || '';
    
    let pipelineFiltrado = pipelineData;
    
    // Filtrar por status
    if (filtroStatus) {
        pipelineFiltrado = pipelineFiltrado.filter(p => p.status === filtroStatus);
    }
    
    // Filtrar por busca
    if (busca) {
        pipelineFiltrado = pipelineFiltrado.filter(p => {
            const localizacao = (p.coletor?.localizacao || '').toLowerCase();
            const observacoes = (p.observacoes || '').toLowerCase();
            return localizacao.includes(busca) || observacoes.includes(busca) || 
                   p.id.toString().includes(busca);
        });
    }
    
    renderizarPipeline(pipelineFiltrado);
    renderizarFunilFiltrado(pipelineFiltrado);
}

// Renderizar pipeline com dados filtrados
function renderizarPipeline(dados = null) {
    const container = document.getElementById('pipeline-container');
    if (!container) {
        console.error('Container pipeline-container não encontrado');
        return;
    }
    
    const filtroStatus = document.getElementById('filtro-status')?.value || '';
    const busca = document.getElementById('busca-pipeline')?.value.toLowerCase() || '';
    
    let pipelineFiltrado = dados || pipelineData || [];
    
    if (!dados) {
        if (filtroStatus) {
            pipelineFiltrado = pipelineFiltrado.filter(p => p.status === filtroStatus);
        }
        if (busca) {
            pipelineFiltrado = pipelineFiltrado.filter(p => {
                const localizacao = (p.coletor?.localizacao || '').toLowerCase();
                const observacoes = (p.observacoes || '').toLowerCase();
                return localizacao.includes(busca) || observacoes.includes(busca) || 
                       p.id.toString().includes(busca);
            });
        }
    }
    
    if (pipelineFiltrado.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #64748b; padding: 2rem;">Nenhum item encontrado</p>';
        return;
    }
    
    container.innerHTML = pipelineFiltrado.map(item => `
        <div class="pipeline-item">
            <div class="pipeline-info">
                <strong>${item.coletor?.localizacao || 'Lead #' + item.id}</strong>
                <span class="pipeline-status status-${item.status}">${(item.status || '').replace('_', ' ')}</span>
            </div>
            <div class="pipeline-detalhes">
                <span><img src="/static/icons/dinheiro_icon.png" alt="Valor" class="inline-icon"> ${formatarMoeda(item.valor_estimado)}</span>
                <span><img src="/static/icons/grafico_icon.png" alt="Probabilidade" class="inline-icon"> ${item.probabilidade}%</span>
            </div>
            <div class="pipeline-acoes">
                <button class="btn btn-xs btn-primario" onclick="verDetalhesPipeline(${item.id})">Ver</button>
                <button class="btn btn-xs btn-secundario" onclick="atualizarStatusPipeline(${item.id})">Atualizar</button>
            </div>
        </div>
    `).join('');
}

// Renderizar funil filtrado
function renderizarFunilFiltrado(dadosFiltrados) {
    const statusMap = {
        'lead': { container: 'funil-lead', count: 'count-lead', valor: 'valor-lead' },
        'contato_inicial': { container: 'funil-contato', count: 'count-contato', valor: 'valor-contato' },
        'proposta_enviada': { container: 'funil-proposta', count: 'count-proposta', valor: 'valor-proposta' },
        'negociacao': { container: 'funil-negociacao', count: 'count-negociacao', valor: 'valor-negociacao' },
        'fechado': { container: 'funil-fechado', count: 'count-fechado', valor: 'valor-fechado' }
    };
    
    // Agrupar por status
    const pipelinePorStatus = {};
    dadosFiltrados.forEach(item => {
        if (!pipelinePorStatus[item.status]) {
            pipelinePorStatus[item.status] = [];
        }
        pipelinePorStatus[item.status].push(item);
    });
    
    // Renderizar cada coluna
    Object.entries(statusMap).forEach(([status, { container, count, valor }]) => {
        const containerEl = document.getElementById(container);
        const countEl = document.getElementById(count);
        const valorEl = document.getElementById(valor);
        
        if (!containerEl) return;
        
        const items = pipelinePorStatus[status] || [];
        const totalValor = items.reduce((sum, item) => sum + (item.valor_estimado || 0), 0);
        
        // Atualizar contador
        if (countEl) {
            countEl.textContent = items.length;
        }
        
        // Atualizar valor total
        if (valorEl) {
            valorEl.textContent = formatarMoeda(totalValor);
        }
        
        // Renderizar items
        if (items.length === 0) {
            containerEl.innerHTML = '<div class="funil-vazio">Nenhum item</div>';
            return;
        }
        
        containerEl.innerHTML = items.map(item => `
            <div class="funil-item" onclick="verDetalhesPipeline(${item.id})">
                <div class="funil-item-titulo">${item.coletor?.localizacao || 'Lead #' + item.id}</div>
                <div class="funil-item-valor">${formatarMoeda(item.valor_estimado)}</div>
                <div class="funil-item-prob">Probabilidade: ${item.probabilidade}%</div>
            </div>
        `).join('');
    });
}

// Criar pipeline
async function criarPipeline(event) {
    event.preventDefault();
    
    try {
        const formData = new FormData(event.target);
        const dados = {
            coletor_id: formData.get('coletor_id') ? parseInt(formData.get('coletor_id')) : null,
            status: formData.get('status') || 'lead',
            valor_estimado: parseFloat(formData.get('valor_estimado')) || 0,
            proxima_acao: formData.get('proxima_acao') || '',
            data_proxima_acao: formData.get('data_proxima_acao') ? new Date(formData.get('data_proxima_acao')).toISOString() : null,
            observacoes: formData.get('observacoes') || '',
            origem: formData.get('origem') || 'outro',
            tipo_servico: formData.get('tipo_servico') || 'coleta'
        };
        
        const response = await fetch('/api/crm/pipeline', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        });
        
        if (!response.ok) {
            const erroData = await response.json().catch(() => ({}));
            throw new Error(erroData.erro || `Erro ${response.status}: ${response.statusText}`);
        }
        
        mostrarSucesso('Pipeline criado com sucesso!');
        fecharModalNovoPipeline();
        await Promise.all([
            carregarEstatisticas(),
            carregarPipeline(),
            carregarFunil()
        ]);
    } catch (erro) {
        console.error('Erro ao criar pipeline:', erro);
        mostrarErro(erro.message || 'Erro ao criar pipeline');
    }
}

// Criar tarefa
async function criarTarefa(event) {
    event.preventDefault();
    
    try {
        const formData = new FormData(event.target);
        const dados = {
            titulo: formData.get('titulo'),
            descricao: formData.get('descricao'),
            prioridade: formData.get('prioridade'),
            data_vencimento: formData.get('data_vencimento') ? new Date(formData.get('data_vencimento')).toISOString() : null
        };
        
        const response = await fetch('/api/crm/tarefas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        });
        
        if (!response.ok) throw new Error('Erro ao criar tarefa');
        
        mostrarSucesso('Tarefa criada com sucesso!');
        fecharModalNovaTarefa();
        carregarTarefas();
    } catch (erro) {
        console.error('Erro:', erro);
        mostrarErro('Erro ao criar tarefa');
    }
}

// Concluir tarefa
// Função global para concluir tarefa
window.concluirTarefa = async function(tarefaId) {
    try {
        const response = await fetch(`/api/crm/tarefas/${tarefaId}/concluir`, {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error('Erro ao concluir tarefa');
        
        mostrarSucesso('Tarefa concluída!');
        carregarTarefas();
    } catch (erro) {
        console.error('Erro:', erro);
        mostrarErro('Erro ao concluir tarefa');
    }
};

// Modais - Funções globais para acesso via onclick
window.abrirModalNovoPipeline = function() {
    document.getElementById('modal-novo-pipeline').style.display = 'flex';
};

window.fecharModalNovoPipeline = function() {
    document.getElementById('modal-novo-pipeline').style.display = 'none';
    document.getElementById('form-novo-pipeline').reset();
};

window.abrirModalNovaTarefa = function() {
    document.getElementById('modal-nova-tarefa').style.display = 'flex';
};

window.fecharModalNovaTarefa = function() {
    document.getElementById('modal-nova-tarefa').style.display = 'none';
    document.getElementById('form-nova-tarefa').reset();
};

// Ações
// Função global para atualizar pipeline
window.atualizarPipeline = async function() {
    await Promise.all([
        carregarEstatisticas(),
        carregarPipeline(),
        carregarTarefas(),
        carregarFunil()
    ]);
    mostrarSucesso('Dados atualizados!');
};

// Ver detalhes do pipeline
// Função global para ver detalhes do pipeline
window.verDetalhesPipeline = async function(id) {
    try {
        // Criar função mostrarLoading se não existir
        if (typeof mostrarLoading === 'undefined') {
            window.mostrarLoading = function(mostrar) {
                // Implementação simples
                if (mostrar) {
                    document.body.style.cursor = 'wait';
                } else {
                    document.body.style.cursor = 'default';
                }
            };
        }
        mostrarLoading(true);
        
        // Buscar dados completos do pipeline
        const response = await fetch(`/api/crm/pipeline/${id}`);
        if (!response.ok) {
            throw new Error('Erro ao carregar detalhes do pipeline');
        }
        
        const pipeline = await response.json();
        
        // Buscar interações do pipeline
        let interacoes = pipeline.interacoes || [];
        if (!Array.isArray(interacoes)) {
            interacoes = [];
        }
        
        // Buscar tarefas relacionadas
        let tarefasRelacionadas = pipeline.tarefas || [];
        if (!Array.isArray(tarefasRelacionadas)) {
            tarefasRelacionadas = [];
        }
        
        // Se não vieram no pipeline, buscar das tarefas carregadas
        if (tarefasRelacionadas.length === 0 && tarefasData && Array.isArray(tarefasData)) {
            tarefasRelacionadas = tarefasData.filter(t => t.pipeline_id === id);
        }
        
        // Exibir modal com detalhes
        mostrarModalDetalhesPipeline(pipeline, interacoes, tarefasRelacionadas);
        
        mostrarLoading(false);
    } catch (erro) {
        console.error('Erro ao carregar detalhes:', erro);
        mostrarErro('Erro ao carregar detalhes do pipeline');
        mostrarLoading(false);
    }
}

// Mostrar modal com detalhes do pipeline
function mostrarModalDetalhesPipeline(pipeline, interacoes, tarefas) {
    const modal = document.getElementById('modal-detalhes-pipeline');
    if (!modal) {
        // Criar modal se não existir
        criarModalDetalhesPipeline();
    }
    
    const modalEl = document.getElementById('modal-detalhes-pipeline');
    const modalContent = document.getElementById('modal-detalhes-pipeline-content');
    
    if (!modalEl || !modalContent) return;
    
    // Preencher conteúdo
    const statusLabels = {
        'lead': 'Lead',
        'qualificado': 'Qualificado',
        'proposta_enviada': 'Proposta Enviada',
        'negociacao': 'Negociação',
        'fechado': 'Fechado',
        'perdido': 'Perdido'
    };
    
    const statusColors = {
        'lead': '#64748b',
        'qualificado': '#3b82f6',
        'proposta_enviada': '#8b5cf6',
        'negociacao': '#f59e0b',
        'fechado': '#22c55e',
        'perdido': '#ef4444'
    };
    
    modalContent.innerHTML = `
        <div class="modal-detalhes-header">
            <h2><img src="/static/icons/prancheta_icon.png" alt="Pipeline" class="modal-icon"> Pipeline #${pipeline.id}</h2>
            <button class="modal-close" onclick="fecharModalDetalhesPipeline()">×</button>
        </div>
        
        <div class="modal-detalhes-body">
            <!-- Informações Principais -->
            <div class="detalhes-section">
                <h3>Informações Principais</h3>
                <div class="detalhes-grid">
                    <div class="detalhes-item">
                        <label>Status:</label>
                        <span class="status-badge" style="background-color: ${statusColors[pipeline.status] || '#64748b'}">
                            ${statusLabels[pipeline.status] || pipeline.status}
                        </span>
                    </div>
                    <div class="detalhes-item">
                        <label>Valor Estimado:</label>
                        <span class="valor-destaque">${formatarMoeda(pipeline.valor_estimado || 0)}</span>
                    </div>
                    <div class="detalhes-item">
                        <label>Probabilidade:</label>
                        <span>${pipeline.probabilidade || 0}%</span>
                    </div>
                    <div class="detalhes-item">
                        <label>Responsável:</label>
                        <span>${pipeline.responsavel || pipeline.responsavel_id || 'Não atribuído'}</span>
                    </div>
                </div>
            </div>
            
            <!-- Cliente/Coletor -->
            ${pipeline.coletor ? `
            <div class="detalhes-section">
                <h3>Cliente</h3>
                <div class="detalhes-grid">
                    <div class="detalhes-item">
                        <label>Localização:</label>
                        <span>${pipeline.coletor.localizacao || 'N/A'}</span>
                    </div>
                    ${pipeline.coletor.parceiro ? `
                    <div class="detalhes-item">
                        <label>Parceiro:</label>
                        <span>${pipeline.coletor.parceiro.nome || 'N/A'}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
            ` : '<div class="detalhes-section"><p>Lead sem coletor associada</p></div>'}
            
            <!-- Detalhes do Serviço -->
            <div class="detalhes-section">
                <h3>Detalhes do Serviço</h3>
                <div class="detalhes-grid">
                    ${pipeline.tipo_servico ? `
                    <div class="detalhes-item">
                        <label>Tipo de Serviço:</label>
                        <span>${pipeline.tipo_servico}</span>
                    </div>
                    ` : ''}
                    ${pipeline.origem ? `
                    <div class="detalhes-item">
                        <label>Origem:</label>
                        <span>${pipeline.origem}</span>
                    </div>
                    ` : ''}
                    ${pipeline.proxima_acao ? `
                    <div class="detalhes-item">
                        <label>Próxima Ação:</label>
                        <span>${pipeline.proxima_acao}</span>
                    </div>
                    ` : ''}
                    ${pipeline.data_proxima_acao ? `
                    <div class="detalhes-item">
                        <label>Data Próxima Ação:</label>
                        <span>${formatarData(pipeline.data_proxima_acao)}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
            
            <!-- Observações -->
            ${pipeline.observacoes ? `
            <div class="detalhes-section">
                <h3>Observações</h3>
                <p class="detalhes-texto">${pipeline.observacoes}</p>
            </div>
            ` : ''}
            
            ${pipeline.descricao_inicial ? `
            <div class="detalhes-section">
                <h3>Descrição Inicial</h3>
                <p class="detalhes-texto">${pipeline.descricao_inicial}</p>
            </div>
            ` : ''}
            
            <!-- Interações -->
            <div class="detalhes-section">
                <h3>Interações (${interacoes.length})</h3>
                ${interacoes.length > 0 ? `
                <div class="interacoes-list">
                    ${interacoes.map(interacao => `
                        <div class="interacao-item">
                            <div class="interacao-header">
                                <span class="interacao-tipo">${interacao.tipo}</span>
                                <span class="interacao-data">${formatarData(interacao.data_interacao)}</span>
                            </div>
                            ${interacao.descricao ? `<p class="interacao-descricao">${interacao.descricao}</p>` : ''}
                        </div>
                    `).join('')}
                </div>
                ` : '<p class="texto-vazio">Nenhuma interação registrada</p>'}
            </div>
            
            <!-- Tarefas Relacionadas -->
            ${tarefas.length > 0 ? `
            <div class="detalhes-section">
                <h3>Tarefas Relacionadas (${tarefas.length})</h3>
                <div class="tarefas-list">
                    ${tarefas.map(tarefa => `
                        <div class="tarefa-item ${tarefa.concluida ? 'concluida' : ''}">
                            <div class="tarefa-header">
                                <span class="tarefa-titulo">${tarefa.titulo}</span>
                                <span class="tarefa-status">${tarefa.concluida ? '<img src="/static/icons/check_icon.png" alt="Concluída" class="status-icon-small"> Concluída' : '<img src="/static/icons/calendar.png" alt="Pendente" class="status-icon-small"> Pendente'}</span>
                            </div>
                            ${tarefa.descricao ? `<p class="tarefa-descricao">${tarefa.descricao}</p>` : ''}
                            ${tarefa.data_vencimento ? `
                                <span class="tarefa-vencimento">Vencimento: ${formatarData(tarefa.data_vencimento)}</span>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
            ` : ''}
            
            <!-- Datas -->
            <div class="detalhes-section">
                <h3>Histórico</h3>
                <div class="detalhes-grid">
                    <div class="detalhes-item">
                        <label>Criado em:</label>
                        <span>${formatarData(pipeline.criado_em)}</span>
                    </div>
                    ${pipeline.atualizado_em ? `
                    <div class="detalhes-item">
                        <label>Atualizado em:</label>
                        <span>${formatarData(pipeline.atualizado_em)}</span>
                    </div>
                    ` : ''}
                    ${pipeline.fechado_em ? `
                    <div class="detalhes-item">
                        <label>Fechado em:</label>
                        <span>${formatarData(pipeline.fechado_em)}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        </div>
        
        <div class="modal-detalhes-footer">
            <button class="btn btn-secundario" onclick="fecharModalDetalhesPipeline()">Fechar</button>
            <button class="btn btn-primario" onclick="atualizarStatusPipeline(${pipeline.id})">Atualizar Status</button>
        </div>
    `;
    
    modalEl.style.display = 'flex';
}

// Criar modal de detalhes se não existir
function criarModalDetalhesPipeline() {
    const modal = document.createElement('div');
    modal.id = 'modal-detalhes-pipeline';
    modal.className = 'modal';
    modal.style.display = 'none';
    modal.innerHTML = `
        <div class="modal-content modal-detalhes" id="modal-detalhes-pipeline-content">
            <!-- Conteúdo será preenchido dinamicamente -->
        </div>
    `;
    document.body.appendChild(modal);
    
    // Fechar ao clicar fora
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            fecharModalDetalhesPipeline();
        }
    });
}

// Fechar modal de detalhes
function fecharModalDetalhesPipeline() {
    const modal = document.getElementById('modal-detalhes-pipeline');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Função global para atualizar status do pipeline
window.atualizarStatusPipeline = function(id) {
    // Implementar atualização de status
    alert(`Atualizar status do pipeline #${id}`);
};

// Utilitários
function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(valor || 0);
}

function formatarData(dataStr) {
    if (!dataStr) return 'N/A';
    const data = new Date(dataStr);
    return data.toLocaleDateString('pt-BR');
}

function mostrarSucesso(mensagem) {
    // Criar notificação de sucesso
    const notificacao = document.createElement('div');
    notificacao.className = 'notificacao notificacao-sucesso';
    notificacao.textContent = mensagem;
    notificacao.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #22c55e;
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;
    document.body.appendChild(notificacao);
    
    setTimeout(() => {
        notificacao.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notificacao.remove(), 300);
    }, 3000);
}

function mostrarErro(mensagem) {
    // Criar notificação de erro
    const notificacao = document.createElement('div');
    notificacao.className = 'notificacao notificacao-erro';
    notificacao.textContent = mensagem;
    notificacao.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ef4444;
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
        max-width: 400px;
    `;
    document.body.appendChild(notificacao);
    
    setTimeout(() => {
        notificacao.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notificacao.remove(), 300);
    }, 5000);
}

// Adicionar animações CSS se não existirem
if (!document.getElementById('crm-notificacoes-style')) {
    const style = document.createElement('style');
    style.id = 'crm-notificacoes-style';
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
}

