/*
JavaScript do Dashboard - Dashboard-TRONIK
=========================================
Lógica principal do dashboard.
Gerencia a interação com a interface e comunicação com a API.
*/

// Variáveis globais
let todasLixeiras = [];
let estatisticas = {};
let intervaloAtualizacao = null;
let intervaloSimulacao = null;
let simulacaoAtiva = false;
let filtros = {
    status: '',
    busca: ''
};
// Ordenação padrão: nível decrescente
let ordenacao = 'nivel_desc';
// Filtro de data para histórico
let dataFiltroHistorico = null;
// Ordenação da tabela de histórico
let ordenacaoHistorico = {
    coluna: null,
    direcao: 'desc' // 'asc' ou 'desc'
};
let dadosHistoricoAtual = [];
// Array para armazenar event listeners para cleanup
let eventListeners = [];
// Flag para controlar se os listeners WebSocket já foram configurados
let websocketListenersConfigurados = false;

// Função para determinar status da coletor
function determinarStatus(coletor) {
    const nivel = coletor.nivel_preenchimento || 0;
    const statusLixeira = coletor.status || 'ativo';
    
    if (nivel >= 95) return { tipo: 'alert', texto: 'Crítico' };
    if (nivel >= 80) return { tipo: 'warning', texto: 'Atenção' };
    if (statusLixeira === 'manutencao') return { tipo: 'warning', texto: 'Manutenção' };
    return { tipo: 'ok', texto: 'Normal' };
}

// Função para formatar data
function formatarData(dataISO) {
    if (!dataISO) return 'N/A';
    const data = new Date(dataISO);
    const agora = new Date();
    const diffMs = agora - data;
    const diffMin = Math.floor(diffMs / 60000);
    
    if (diffMin < 1) return 'Agora';
    if (diffMin < 60) return `Há ${diffMin} min`;
    const diffHora = Math.floor(diffMin / 60);
    if (diffHora < 24) return `Há ${diffHora}h`;
    const diffDias = Math.floor(diffHora / 24);
    return `Há ${diffDias} dias`;
}

// Função para calcular distância da sede (Haversine)
function calcularDistanciaSede(coletor) {
    if (!coletor || !coletor.latitude || !coletor.longitude) {
        return null;
    }
    
    const SEDE_TRONIK = {
        lat: -15.908661672774747,
        lon: -48.076158282355806
    };
    
    const lat = parseFloat(coletor.latitude);
    const lon = parseFloat(coletor.longitude);
    
    if (isNaN(lat) || isNaN(lon)) {
        return null;
    }
    
    const R = 6371; // Raio da Terra em km
    const dLat = (lat - SEDE_TRONIK.lat) * Math.PI / 180;
    const dLon = (lon - SEDE_TRONIK.lon) * Math.PI / 180;
    const a = 
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(SEDE_TRONIK.lat * Math.PI / 180) * Math.cos(lat * Math.PI / 180) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

// Função para formatar distância
function formatarDistancia(distancia) {
    if (distancia === null || distancia === undefined) {
        return 'N/A';
    }
    
    if (distancia < 1) {
        return `${Math.round(distancia * 1000)}m`;
    }
    
    return `${distancia.toFixed(1)}km`;
}

// Função para criar card de coletor
function criarCardLixeira(coletor) {
    const status = determinarStatus(coletor);
    const nivel = Math.round(coletor.nivel_preenchimento || 0);
    
    // Sanitizar dados
    const escapeHtml = window.Formatacao && window.Formatacao.escapeHtml ? window.Formatacao.escapeHtml : (text) => {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };
    
    const tipoMaterial = escapeHtml(coletor.tipo_material ? coletor.tipo_material.nome : 'Não especificado');
    const parceiro = coletor.parceiro ? escapeHtml(coletor.parceiro.nome) : null;
    const localizacao = escapeHtml(coletor.localizacao || 'Sem localização');
    const distanciaSede = calcularDistanciaSede(coletor);
    const distanciaFormatada = formatarDistancia(distanciaSede);
    
    const card = document.createElement('div');
    card.className = `bin-card ${status.tipo === 'alert' ? 'alert' : status.tipo === 'warning' ? 'warning' : ''}`;
    card.dataset.id = coletor.id;
    
    card.innerHTML = `
        <div class="bin-header">
            <div class="bin-info">
                <div class="bin-id">#L${String(coletor.id).padStart(3, '0')}</div>
                <div class="bin-name">${localizacao}</div>
                <div class="bin-location">${tipoMaterial}${parceiro ? ` | ${parceiro}` : ''}${distanciaSede !== null ? ` | 📍 ${distanciaFormatada} da sede` : ''}</div>
            </div>
            <span class="bin-status-badge status-${status.tipo}">${status.texto}</span>
        </div>
        <div class="bin-level">
            <div class="level-label">
                <span>Nível</span>
                <span class="level-percentage">${nivel}%</span>
            </div>
            <div class="level-bar">
                <div class="level-fill ${nivel >= 80 ? nivel >= 95 ? 'alert' : 'warning' : ''}" 
                     style="width: ${nivel}%"></div>
            </div>
        </div>
        <div class="bin-footer">
            <span class="bin-update">${formatarData(coletor.ultima_coleta)}</span>
            <button class="bin-action" data-coletor-id="${coletor.id}">Detalhes</button>
        </div>
    `;
    
    return card;
}

// Função para renderizar grid de coletores
function renderizarGridLixeiras(lixeirasFiltradas) {
    const grid = document.getElementById('bins-grid');
    if (!grid) {
        console.warn('Elemento bins-grid não encontrado');
        return;
    }
    
    grid.innerHTML = '';
    
    if (!Array.isArray(lixeirasFiltradas) || lixeirasFiltradas.length === 0) {
        grid.innerHTML = '<div class="loading-message">Nenhuma coletor encontrada</div>';
        return;
    }
    
    lixeirasFiltradas.forEach(coletor => {
        const card = criarCardLixeira(coletor);
        // Adicionar event listener ao botão de detalhes
        const btnDetalhes = card.querySelector('.bin-action');
        if (btnDetalhes) {
            btnDetalhes.addEventListener('click', () => verDetalhes(coletor.id));
        }
        grid.appendChild(card);
    });
}

// Função para atualizar estatísticas
function atualizarEstatisticas(dados) {
    estatisticas = dados;
    
    const statTotal = document.getElementById('stat-total');
    const statNivelMedio = document.getElementById('stat-nivel-medio');
    const statAlertas = document.getElementById('stat-alertas');
    const statColetasHoje = document.getElementById('stat-coletas-hoje');
    
    if (statTotal) statTotal.textContent = dados.total_lixeiras || 0;
    if (statNivelMedio) statNivelMedio.textContent = `${dados.nivel_medio || 0}%`;
    if (statAlertas) statAlertas.textContent = dados.lixeiras_alerta || 0;
    if (statColetasHoje) statColetasHoje.textContent = dados.coletas_hoje || 0;
}

// Função para atualizar alertas
function atualizarAlertas() {
    const alertasBar = document.getElementById('alerts-bar');
    const alertTitle = document.getElementById('alert-title');
    const alertMessage = document.getElementById('alert-message');
    
    const lixeirasAlerta = todasLixeiras.filter(l => l.nivel_preenchimento >= 80);
    
    if (lixeirasAlerta.length > 0) {
        alertTitle.textContent = `${lixeirasAlerta.length} coletor(s) precisam de atenção urgente`;
        const ids = lixeirasAlerta.map(l => `#L${String(l.id).padStart(3, '0')}`).join(', ');
        alertMessage.textContent = `Lixeiras ${ids} estão acima de 80% de capacidade`;
        alertasBar.style.display = 'flex';
    } else {
        alertasBar.style.display = 'none';
    }
}

// Função para aplicar filtros
function aplicarFiltros() {
    let lixeirasFiltradas = [...todasLixeiras];
    
    // Filtro por status
    if (filtros.status) {
        lixeirasFiltradas = lixeirasFiltradas.filter(l => {
            const status = determinarStatus(l);
            if (filtros.status === 'ativo') return status.tipo === 'ok';
            if (filtros.status === 'alerta') return status.tipo === 'warning' || status.tipo === 'alert';
            if (filtros.status === 'manutencao') return l.status === 'manutencao';
            return true;
        });
    }
    
    // Filtro por busca
    if (filtros.busca) {
        const busca = filtros.busca.toLowerCase();
        lixeirasFiltradas = lixeirasFiltradas.filter(l => {
            const id = `L${String(l.id).padStart(3, '0')}`.toLowerCase();
            const localizacao = (l.localizacao || '').toLowerCase();
            return id.includes(busca) || localizacao.includes(busca);
        });
    }

    // Ordenação
    lixeirasFiltradas.sort((a, b) => {
        const nivelA = a.nivel_preenchimento || 0;
        const nivelB = b.nivel_preenchimento || 0;
        const nomeA = (a.localizacao || '').toLowerCase();
        const nomeB = (b.localizacao || '').toLowerCase();
        const dataA = a.ultima_coleta ? new Date(a.ultima_coleta).getTime() : 0;
        const dataB = b.ultima_coleta ? new Date(b.ultima_coleta).getTime() : 0;
        
        switch (ordenacao) {
            case 'nivel_desc':
                return nivelB - nivelA;
            case 'nivel_asc':
                return nivelA - nivelB;
            case 'nome_asc':
                return nomeA.localeCompare(nomeB);
            case 'nome_desc':
                return nomeB.localeCompare(nomeA);
            case 'data_desc':
                return dataB - dataA;
            case 'data_asc':
                return dataA - dataB;
            default:
                return nivelB - nivelA;
        }
    });
    
    renderizarGridLixeiras(lixeirasFiltradas);
}

// Função para carregar dados
async function carregarDados() {
    try {
        // Verificar se estamos na página do dashboard
        const binsGrid = document.getElementById('bins-grid');
        if (!binsGrid) {
            // Não é a página do dashboard, não executar
            return;
        }
        
        // Atualizar status de conexão
        const statusIndicator = document.getElementById('status-indicator');
        if (statusIndicator) {
            const statusSpan = statusIndicator.querySelector('span');
            if (statusSpan) {
                statusSpan.textContent = simulacaoAtiva ? 'Simulando...' : 'Carregando...';
            }
        }
        
        // Carregar coletores e estatísticas em paralelo (usar allSettled para não falhar tudo se uma falhar)
        const results = await Promise.allSettled([
            obterTodasLixeiras(),
            obterEstatisticas()
        ]);
        
        const coletores = results[0].status === 'fulfilled' ? (Array.isArray(results[0].value) ? results[0].value : []) : [];
        const stats = results[1].status === 'fulfilled' ? (results[1].value || {}) : {};
        
        if (results[0].status === 'rejected') {
            console.error('Erro ao carregar coletores:', results[0].reason);
        }
        if (results[1].status === 'rejected') {
            console.error('Erro ao carregar estatísticas:', results[1].reason);
        }
        
        todasLixeiras = coletores;
        atualizarEstatisticas(stats);
        atualizarAlertas();
        aplicarFiltros();
        
        // Configurar listeners WebSocket para atualizações em tempo real
        configurarWebSocketListeners();
        
        // Carregar histórico (só se o elemento existir)
        const historyTbody = document.getElementById('history-tbody');
        if (historyTbody) {
            carregarHistorico();
        }
        
        // Atualizar status
        if (statusIndicator) {
            const statusSpan = statusIndicator.querySelector('span');
            if (statusSpan) {
                statusSpan.textContent = simulacaoAtiva ? 'Simulando' : 'Conectado';
            }
        }
        
    } catch (error) {
        console.error('Erro ao carregar dados:', error);
        const statusIndicator = document.getElementById('status-indicator');
        if (statusIndicator) {
            const statusSpan = statusIndicator.querySelector('span');
            if (statusSpan) {
                statusSpan.textContent = 'Erro';
            }
            statusIndicator.style.background = '#f8d7da';
        }
        
        const binsGrid = document.getElementById('bins-grid');
        if (binsGrid) {
            binsGrid.innerHTML = '<div class="loading-message">Erro ao carregar dados. Tente novamente.</div>';
        }
    }
}

// Atualização manual com feedback de botão
async function atualizarComFeedback() {
    console.log('[Dashboard] atualizarComFeedback chamado');
    const btn = document.getElementById('btn-atualizar');
    if (!btn) {
        console.warn('[Dashboard] Botão atualizar não encontrado, chamando carregarDados diretamente');
        return carregarDados();
    }
    const original = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Atualizando...';
    console.log('[Dashboard] Iniciando atualização de dados...');
    try {
        await carregarDados();
        console.log('[Dashboard] Dados atualizados com sucesso');
    } catch (error) {
        console.error('[Dashboard] Erro ao atualizar dados:', error);
    } finally {
        btn.disabled = false;
        btn.textContent = original;
    }
}

// Alternar simulação de níveis
function alternarSimulacao() {
    const btn = document.getElementById('btn-simular');
    if (!btn) return;
    simulacaoAtiva = !simulacaoAtiva;
    if (simulacaoAtiva) {
        btn.textContent = '⏸ Pausar Simulação';
        btn.classList.add('ativo');
        // Dispara imediatamente e depois a cada 5s
        simularNiveis().then(carregarDados).catch(console.error);
        intervaloSimulacao = setInterval(async () => {
            try {
                await simularNiveis();
                await carregarDados();
            } catch (e) {
                console.error('Erro na simulação:', e);
            }
        }, 5000);
    } else {
        btn.textContent = '▶ Simular Níveis';
        btn.classList.remove('ativo');
        if (intervaloSimulacao) {
            clearInterval(intervaloSimulacao);
            intervaloSimulacao = null;
        }
        carregarDados();
    }
}

// Função para carregar histórico
async function carregarHistorico() {
    try {
        const tbody = document.getElementById('history-tbody');
        if (!tbody) {
            // Elemento não existe, não executar
            return;
        }
        
        let historico = await obterHistorico(dataFiltroHistorico);
        
        // Garantir que historico é um array
        if (!Array.isArray(historico)) {
            console.warn('Histórico não é um array, convertendo...', historico);
            historico = historico && historico.dados ? historico.dados : [];
        }
        
        // Armazenar dados para ordenação
        dadosHistoricoAtual = historico;
        
        if (historico.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">Nenhuma coleta registrada</td></tr>';
            return;
        }
        
        // Aplicar ordenação se houver
        let historicoOrdenado = [...historico];
        if (ordenacaoHistorico.coluna) {
            historicoOrdenado = ordenarHistorico(historicoOrdenado, ordenacaoHistorico.coluna, ordenacaoHistorico.direcao);
        }
        
        // Mostrar todas as coletas (ou limitar a 50 se houver muitas)
        const coletasLimitadas = historicoOrdenado.length > 50 ? historicoOrdenado.slice(0, 50) : historicoOrdenado;
        tbody.innerHTML = coletasLimitadas.map(coleta => {
            const coletor = todasLixeiras.find(l => l.id === coleta.coletor_id) || coleta.coletor;
            const data = coleta.data_hora ? new Date(coleta.data_hora) : null;
            const hora = data ? data.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : 'N/A';
            const dataFormatada = data ? data.toLocaleDateString('pt-BR') : 'N/A';
            const volume = coleta.volume_estimado ? Math.round(coleta.volume_estimado) : 0;
            const km = coleta.km_percorrido ? Math.round(coleta.km_percorrido * 10) / 10 : 'N/A';
            const parceiro = coleta.parceiro ? coleta.parceiro.nome : 'N/A';
            const tipoOperacao = coleta.tipo_operacao || 'N/A';
            
            return `
                <tr>
                    <td>#L${String(coleta.coletor_id || 'N/A').padStart(3, '0')}</td>
                    <td>${coletor ? (coletor.localizacao || 'N/A') : 'N/A'}</td>
                    <td>${dataFormatada} ${hora}</td>
                    <td>${volume}KG</td>
                    <td>${km}${typeof km === 'number' ? 'km' : ''}</td>
                    <td>${parceiro}</td>
                    <td>${tipoOperacao}</td>
                    <td><span class="bin-status-badge status-ok">OK</span></td>
                </tr>
            `;
        }).join('');
        
        // Atualizar indicadores de ordenação após renderizar
        atualizarIndicadoresOrdenacao();
        
    } catch (error) {
        console.error('Erro ao carregar histórico:', error);
    }
}

// Função para ordenar histórico
function ordenarHistorico(coletas, coluna, direcao) {
    const copia = [...coletas];
    
    copia.sort((a, b) => {
        let valorA, valorB;
        
        switch(coluna) {
            case 'id':
                valorA = a.coletor_id || 0;
                valorB = b.coletor_id || 0;
                break;
            case 'local':
                const lixeiraA = todasLixeiras.find(l => l.id === a.coletor_id) || a.coletor;
                const lixeiraB = todasLixeiras.find(l => l.id === b.coletor_id) || b.coletor;
                valorA = (lixeiraA ? (lixeiraA.localizacao || '') : '').toLowerCase();
                valorB = (lixeiraB ? (lixeiraB.localizacao || '') : '').toLowerCase();
                break;
            case 'hora':
                valorA = a.data_hora ? new Date(a.data_hora).getTime() : 0;
                valorB = b.data_hora ? new Date(b.data_hora).getTime() : 0;
                break;
            case 'volume':
                valorA = a.volume_estimado || 0;
                valorB = b.volume_estimado || 0;
                break;
            case 'km':
                valorA = a.km_percorrido || 0;
                valorB = b.km_percorrido || 0;
                break;
            case 'parceiro':
                valorA = (a.parceiro ? a.parceiro.nome : 'N/A').toLowerCase();
                valorB = (b.parceiro ? b.parceiro.nome : 'N/A').toLowerCase();
                break;
            case 'tipo':
                valorA = (a.tipo_operacao || 'N/A').toLowerCase();
                valorB = (b.tipo_operacao || 'N/A').toLowerCase();
                break;
            default:
                return 0;
        }
        
        if (typeof valorA === 'string' && typeof valorB === 'string') {
            if (direcao === 'asc') {
                return valorA.localeCompare(valorB, 'pt-BR');
            } else {
                return valorB.localeCompare(valorA, 'pt-BR');
            }
        } else {
            if (direcao === 'asc') {
                return valorA - valorB;
            } else {
                return valorB - valorA;
            }
        }
    });
    
    return copia;
}

// Função para alternar ordenação ao clicar no cabeçalho
function alternarOrdenacaoHistorico(coluna) {
    if (ordenacaoHistorico.coluna === coluna) {
        // Se já está ordenando por esta coluna, inverte a direção
        ordenacaoHistorico.direcao = ordenacaoHistorico.direcao === 'asc' ? 'desc' : 'asc';
    } else {
        // Nova coluna, começa com desc
        ordenacaoHistorico.coluna = coluna;
        ordenacaoHistorico.direcao = 'desc';
    }
    
    // Atualizar indicadores visuais
    atualizarIndicadoresOrdenacao();
    
    // Re-renderizar tabela
    renderizarHistoricoOrdenado();
}

// Função para atualizar indicadores visuais de ordenação
function atualizarIndicadoresOrdenacao() {
    const headers = document.querySelectorAll('#history-table thead th');
    headers.forEach((th, index) => {
        // Remover todas as classes de ordenação
        th.classList.remove('sort-asc', 'sort-desc');
        
        // Mapear índice para nome da coluna
        const colunas = ['id', 'local', 'hora', 'volume', 'km', 'parceiro', 'tipo', 'status'];
        const coluna = colunas[index];
        
        if (coluna && ordenacaoHistorico.coluna === coluna) {
            th.classList.add('sort-' + ordenacaoHistorico.direcao);
        }
    });
}

// Função para renderizar histórico ordenado
function renderizarHistoricoOrdenado() {
    const tbody = document.getElementById('history-tbody');
    if (!tbody) {
        console.warn('Elemento history-tbody não encontrado');
        return;
    }
    
    // Garantir que dadosHistoricoAtual é um array
    if (!Array.isArray(dadosHistoricoAtual)) {
        dadosHistoricoAtual = [];
    }
    
    if (dadosHistoricoAtual.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">Nenhuma coleta registrada</td></tr>';
        return;
    }
    
    // Aplicar ordenação
    const historicoOrdenado = ordenarHistorico(dadosHistoricoAtual, ordenacaoHistorico.coluna, ordenacaoHistorico.direcao);
    const coletasLimitadas = historicoOrdenado.length > 50 ? historicoOrdenado.slice(0, 50) : historicoOrdenado;
    
    // Sanitizar função
    const escapeHtml = window.Formatacao && window.Formatacao.escapeHtml ? window.Formatacao.escapeHtml : (text) => {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };
    
    tbody.innerHTML = coletasLimitadas.map(coleta => {
        const coletor = Array.isArray(todasLixeiras) ? todasLixeiras.find(l => l && l.id === coleta.coletor_id) : null;
        const lixeiraObj = coletor || coleta.coletor;
        const data = coleta.data_hora ? new Date(coleta.data_hora) : null;
        const hora = data ? data.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : 'N/A';
        const dataFormatada = data ? data.toLocaleDateString('pt-BR') : 'N/A';
        const volume = coleta.volume_estimado ? Math.round(coleta.volume_estimado) : 0;
        const km = coleta.km_percorrido ? Math.round(coleta.km_percorrido * 10) / 10 : 'N/A';
        const parceiroNome = coleta.parceiro ? escapeHtml(coleta.parceiro.nome) : 'N/A';
        const tipoOperacao = escapeHtml(coleta.tipo_operacao || 'N/A');
        const localizacao = lixeiraObj ? escapeHtml(lixeiraObj.localizacao || 'N/A') : 'N/A';
        
        return `
            <tr>
                <td>#L${String(coleta.coletor_id || 'N/A').padStart(3, '0')}</td>
                <td>${localizacao}</td>
                <td>${dataFormatada} ${hora}</td>
                <td>${volume}KG</td>
                <td>${km}${typeof km === 'number' ? 'km' : ''}</td>
                <td>${parceiroNome}</td>
                <td>${tipoOperacao}</td>
                <td><span class="bin-status-badge status-ok">OK</span></td>
            </tr>
        `;
    }).join('');
}

// Função para ver detalhes
async function verDetalhes(id) {
    try {
        const coletor = await obterLixeira(id);
        let historico = await obterHistorico();
        
        // Garantir que historico é um array
        if (!Array.isArray(historico)) {
            historico = historico && historico.dados ? historico.dados : [];
        }
        
        const historicoLixeira = historico.filter(c => c.coletor_id === id).slice(0, 5);
        
        const status = determinarStatus(coletor);
        const nivel = Math.round(coletor.nivel_preenchimento || 0);
        
        // Mostrar modal ANTES de preencher conteúdo
        let modalOverlay = document.getElementById('modal-overlay');
        if (!modalOverlay) {
            console.error('Elemento modal-overlay não encontrado');
            // Tentar criar o modal se não existir
            const body = document.body;
            if (body) {
                modalOverlay = document.createElement('div');
                modalOverlay.id = 'modal-overlay';
                modalOverlay.className = 'modal-overlay';
                modalOverlay.style.display = 'none';
                modalOverlay.textContent = '\n                    <div class="modal-container">\n                        <div class="modal-header">\n                            <h2 id="modal-title">Detalhes da Coletor</h2>\n                            <button class="modal-close" id="modal-close">&times;</button>\n                        </div>\n                        <div class="modal-body" id="modal-body">\n                            <!-- Conteúdo será preenchido via JavaScript -->\n                        </div>\n                    </div>\n                ';
                body.appendChild(modalOverlay);
                
                // Adicionar event listeners para fechar modal
                const modalClose = modalOverlay.querySelector('#modal-close');
                if (modalClose) {
                    modalClose.addEventListener('click', () => {
                        modalOverlay.style.display = 'none';
                    });
                }
                modalOverlay.addEventListener('click', (e) => {
                    if (e.target.id === 'modal-overlay') {
                        modalOverlay.style.display = 'none';
                    }
                });
            } else {
                console.error('Body não encontrado, não é possível criar modal');
                return;
            }
        }
        
        // Preencher modal - validar elementos
        const modalTitle = modalOverlay.querySelector('#modal-title');
        if (!modalTitle) {
            console.error('Elemento modal-title não encontrado no modal');
            return;
        }
        
        const modalBody = modalOverlay.querySelector('#modal-body');
        if (!modalBody) {
            console.error('Elemento modal-body não encontrado no modal');
            return;
        }
        
        modalTitle.textContent = 
            `Coletor #L${String(coletor.id).padStart(3, '0')} - ${coletor.localizacao || 'Sem localização'}`;
        
        // Mostrar modal
        modalOverlay.style.display = 'flex';
        
        // Carregar tipos e parceiros para dropdowns
        const [tiposMaterial, parceiros] = await Promise.all([
            obterTiposMaterial().catch(() => []),
            obterParceiros().catch(() => [])
        ]);
        
        // Garantir que são arrays
        const tiposMaterialArray = Array.isArray(tiposMaterial) ? tiposMaterial : [];
        const parceirosArray = Array.isArray(parceiros) ? parceiros : [];
        
        const tipoMaterialAtual = coletor.tipo_material ? coletor.tipo_material.id : null;
        const parceiroAtual = coletor.parceiro ? coletor.parceiro.id : null;
        
        // Sanitizar dados antes de inserir no HTML
        const escapeHtml = window.Formatacao && window.Formatacao.escapeHtml ? window.Formatacao.escapeHtml : (text) => {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        };
        
        const localizacao = escapeHtml(coletor.localizacao || 'Sem localização');
        const tipoMaterialNome = escapeHtml(coletor.tipo_material ? coletor.tipo_material.nome : 'Não especificado');
        const parceiroNome = escapeHtml(coletor.parceiro ? coletor.parceiro.nome : 'N/A');
        
        modalBody.innerHTML = `
            <div class="modal-detail-card">
                <div class="modal-detail-header">
                    <div>
                        <div class="modal-detail-title">${localizacao}</div>
                        <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">
                            ${tipoMaterialNome}${coletor.parceiro ? ` | ${parceiroNome}` : ''} | Atualizado ${formatarData(coletor.ultima_coleta)}
                        </div>
                    </div>
                    <span class="bin-status-badge status-${status.tipo}">${status.texto}</span>
                </div>
                
                <div class="modal-detail-level">
                    <div class="modal-level-visual">
                        <div class="modal-level-percentage" style="color: ${nivel >= 80 ? nivel >= 95 ? '#e74c3c' : '#f39c12' : '#2c3e50'}">
                            ${nivel}%
                        </div>
                        <div style="font-size: 12px; color: #7f8c8d; margin-bottom: 10px;">Nível de Preenchimento</div>
                        <div class="modal-level-bar">
                            <div class="modal-level-fill ${nivel >= 80 ? nivel >= 95 ? 'alert' : 'warning' : ''}" 
                                 style="width: ${nivel}%"></div>
                        </div>
                    </div>
                </div>
                
                <div class="modal-info-grid">
                    <div class="modal-info-item">
                        <span class="modal-info-label">Status</span>
                        <span class="modal-info-value">${coletor.status || 'OK'}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Tipo de Material</span>
                        <span class="modal-info-value">${tipoMaterialNome}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Parceiro</span>
                        <span class="modal-info-value">${parceiroNome}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Última Coleta</span>
                        <span class="modal-info-value">${formatarData(coletor.ultima_coleta)}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Coordenadas</span>
                        <span class="modal-info-value">
                            ${coletor.latitude && coletor.longitude ? 
                                `${parseFloat(coletor.latitude).toFixed(4)}, ${parseFloat(coletor.longitude).toFixed(4)}` : 
                                'N/A'}
                        </span>
                    </div>
                </div>
            </div>
            
            ${historicoLixeira.length > 0 ? `
            <div class="modal-detail-card">
                <h3 style="font-size: 14px; font-weight: 600; margin-bottom: 10px; color: #2c3e50;">Últimas Coletas</h3>
                <table style="width: 100%; font-size: 12px;">
                    <thead>
                        <tr style="background: #f8f9fa;">
                            <th style="padding: 8px; text-align: left;">Data/Hora</th>
                            <th style="padding: 8px; text-align: left;">Volume (KG)</th>
                            <th style="padding: 8px; text-align: left;">KM</th>
                            <th style="padding: 8px; text-align: left;">Tipo</th>
                            <th style="padding: 8px; text-align: left;">Parceiro</th>
                            <th style="padding: 8px; text-align: left;">Lucro/KG</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${historicoLixeira.map(coleta => {
                            const data = coleta.data_hora ? new Date(coleta.data_hora) : null;
                            const km = coleta.km_percorrido ? Math.round(coleta.km_percorrido * 10) / 10 : 'N/A';
                            const parceiro = coleta.parceiro ? coleta.parceiro.nome : 'N/A';
                            const lucro = coleta.lucro_por_kg ? `R$ ${coleta.lucro_por_kg.toFixed(2)}` : 'N/A';
                            return `
                                <tr>
                                    <td style="padding: 8px;">${data ? data.toLocaleString('pt-BR') : 'N/A'}</td>
                                    <td style="padding: 8px;">${coleta.volume_estimado ? Math.round(coleta.volume_estimado) + 'KG' : 'N/A'}</td>
                                    <td style="padding: 8px;">${km}${typeof km === 'number' ? 'km' : ''}</td>
                                    <td style="padding: 8px;">${coleta.tipo_operacao || 'N/A'}</td>
                                    <td style="padding: 8px;">${parceiro}</td>
                                    <td style="padding: 8px;">${lucro}</td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
            ` : ''}
            
            <div class="modal-detail-card" id="edit-section">
                <h3 style="font-size: 14px; font-weight: 600; margin-bottom: 10px; color: #2c3e50;">Editar Coletor</h3>
                <div id="edit-feedback" style="display:none; font-size:12px; margin-bottom:8px;"></div>
                <div class="form-grid" style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <div class="form-group">
                        <label style="font-size:12px; color:#7f8c8d;">Localização *</label>
                        <input type="text" id="edit-localizacao" value="${coletor.localizacao || ''}" />
                    </div>
                    <div class="form-group">
                        <label style="font-size:12px; color:#7f8c8d;">Tipo de Material</label>
                        <select id="edit-tipo-material">
                            <option value="">Selecione...</option>
                            ${tiposMaterialArray.map(tipo => {
                                if (!tipo || !tipo.id || !tipo.nome) return '';
                                const nomeEscapado = escapeHtml(tipo.nome);
                                return `<option value="${tipo.id}" ${tipo.id === tipoMaterialAtual ? 'selected' : ''}>${nomeEscapado}</option>`;
                            }).filter(opt => opt).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label style="font-size:12px; color:#7f8c8d;">Parceiro</label>
                        <select id="edit-parceiro">
                            <option value="">Selecione...</option>
                            ${parceirosArray.map(parceiro => {
                                if (!parceiro || !parceiro.id || !parceiro.nome) return '';
                                const nomeEscapado = escapeHtml(parceiro.nome);
                                return `<option value="${parceiro.id}" ${parceiro.id === parceiroAtual ? 'selected' : ''}>${nomeEscapado}</option>`;
                            }).filter(opt => opt).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label style="font-size:12px; color:#7f8c8d;">Nível (%)</label>
                        <input type="number" id="edit-nivel" min="0" max="100" step="0.1" value="${coletor.nivel_preenchimento || 0}" />
                    </div>
                    <div class="form-group">
                        <label style="font-size:12px; color:#7f8c8d;">Status</label>
                        <select id="edit-status">
                            <option value="OK" ${coletor.status === 'OK' ? 'selected' : ''}>OK</option>
                            <option value="CHEIA" ${coletor.status === 'CHEIA' ? 'selected' : ''}>CHEIA</option>
                            <option value="QUEBRADA" ${coletor.status === 'QUEBRADA' ? 'selected' : ''}>QUEBRADA</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label style="font-size:12px; color:#7f8c8d;">Latitude</label>
                        <input type="number" id="edit-lat" step="0.0001" value="${coletor.latitude || ''}" />
                    </div>
                    <div class="form-group">
                        <label style="font-size:12px; color:#7f8c8d;">Longitude</label>
                        <input type="number" id="edit-lon" step="0.0001" value="${coletor.longitude || ''}" />
                    </div>
                </div>
                <div class="form-actions" style="margin-top:10px; display:flex; gap:8px;">
                    <button class="btn-atualizar" id="btn-salvar-edicao">Salvar Alterações</button>
                    <button class="btn-exportar" id="btn-cancelar-edicao">Cancelar</button>
                </div>
            </div>
        `;
        
        // Mostrar modal (já foi validado acima)
        modalOverlay = document.getElementById('modal-overlay');
        if (modalOverlay) {
            modalOverlay.style.display = 'flex';
        }
        
        // Listeners de edição - validar elementos
        const btnCancelar = document.getElementById('btn-cancelar-edicao');
        const btnSalvar = document.getElementById('btn-salvar-edicao');
        
        if (btnCancelar) {
            btnCancelar.addEventListener('click', fecharModal);
        }
        
        if (btnSalvar) {
            btnSalvar.addEventListener('click', async function() {
            const feedback = document.getElementById('edit-feedback');
            if (!feedback) {
                console.error('Elemento edit-feedback não encontrado');
                return;
            }
            feedback.style.display = 'none';
            feedback.textContent = '';
            feedback.className = '';

            const localizacaoEl = document.getElementById('edit-localizacao');
            const tipoMaterialEl = document.getElementById('edit-tipo-material');
            const parceiroEl = document.getElementById('edit-parceiro');
            const nivelEl = document.getElementById('edit-nivel');
            const statusEl = document.getElementById('edit-status');
            const latEl = document.getElementById('edit-lat');
            const lonEl = document.getElementById('edit-lon');
            
            if (!localizacaoEl || !nivelEl || !statusEl) {
                feedback.textContent = 'Erro: Campos do formulário não encontrados.';
                feedback.style.display = 'block';
                feedback.style.color = '#e74c3c';
                return;
            }

            const localizacao = localizacaoEl.value.trim();
            const tipoMaterialId = tipoMaterialEl ? tipoMaterialEl.value : '';
            const parceiroId = parceiroEl ? parceiroEl.value : '';
            const nivelStr = nivelEl.value;
            const statusSel = statusEl.value;
            const latStr = latEl ? latEl.value : '';
            const lonStr = lonEl ? lonEl.value : '';

            // Validações
            if (!localizacao) {
                feedback.textContent = 'Localização é obrigatória.';
                feedback.style.display = 'block';
                feedback.style.color = '#e74c3c';
                return;
            }
            const nivel = parseFloat(nivelStr);
            if (isNaN(nivel) || nivel < 0 || nivel > 100) {
                feedback.textContent = 'Nível deve ser um número entre 0 e 100.';
                feedback.style.display = 'block';
                feedback.style.color = '#e74c3c';
                return;
            }

            const dadosAtualizacao = {
                localizacao,
                nivel_preenchimento: nivel,
                status: statusSel,
                tipo_material_id: tipoMaterialId ? parseInt(tipoMaterialId) : null,
                parceiro_id: parceiroId ? parseInt(parceiroId) : null
            };
            
            // Atualizar coordenadas independentemente (permitir atualizar apenas uma)
            // Converter vírgula para ponto (formato brasileiro -> internacional)
            if (latStr && latStr.trim() !== '') {
                const latStrNormalizado = latStr.trim().replace(',', '.');
                const lat = parseFloat(latStrNormalizado);
                if (!isNaN(lat)) {
                    dadosAtualizacao.latitude = lat;
                    console.log(`[Editar Coletor] Latitude será atualizada: ${lat}`);
                } else {
                    console.warn(`[Editar Coletor] Latitude inválida: "${latStr}"`);
                }
            }
            
            if (lonStr && lonStr.trim() !== '') {
                const lonStrNormalizado = lonStr.trim().replace(',', '.');
                const lon = parseFloat(lonStrNormalizado);
                if (!isNaN(lon)) {
                    dadosAtualizacao.longitude = lon;
                    console.log(`[Editar Coletor] Longitude será atualizada: ${lon}`);
                } else {
                    console.warn(`[Editar Coletor] Longitude inválida: "${lonStr}"`);
                }
            }

            console.log('[Editar Coletor] Dados que serão enviados:', dadosAtualizacao);

            // Feedback de loading
            const btnSalvar = document.getElementById('btn-salvar-edicao');
            btnSalvar.disabled = true;
            btnSalvar.textContent = 'Salvando...';
            try {
                await atualizarLixeira(id, dadosAtualizacao);
                feedback.textContent = 'Coletor atualizada com sucesso!';
                feedback.style.display = 'block';
                feedback.style.color = '#27ae60';
                // Atualizar grid e estatísticas
                await carregarDados();
                // Fechar modal após pequeno delay
                setTimeout(() => {
                    fecharModal();
                }, 800);
            } catch (err) {
                console.error('Erro ao atualizar coletor:', err);
                feedback.textContent = 'Erro ao atualizar coletor: ' + (err.message || 'Erro desconhecido');
                feedback.style.display = 'block';
                feedback.style.color = '#e74c3c';
            } finally {
                btnSalvar.disabled = false;
                btnSalvar.textContent = 'Salvar Alterações';
            }
            });
        }
        
    } catch (error) {
        console.error('Erro ao carregar detalhes:', error);
        alert('Erro ao carregar detalhes da coletor.');
    }
}

// Função para fechar modal
function fecharModal() {
    const modalOverlay = document.getElementById('modal-overlay');
    if (modalOverlay) {
        modalOverlay.style.display = 'none';
    }
}

// Função para exportar CSV
function exportarCSV() {
    try {
        // Preparar dados
        const coletores = todasLixeiras.map(l => {
            const status = determinarStatus(l);
            return {
                'ID': `L${String(l.id).padStart(3, '0')}`,
                'Localização': l.localizacao || '',
                'Nível (%)': l.nivel_preenchimento || 0,
                'Status': status.texto,
                'Tipo de Material': l.tipo_material ? l.tipo_material.nome : '',
                'Parceiro': l.parceiro ? l.parceiro.nome : '',
                'Última Coleta': l.ultima_coleta ? new Date(l.ultima_coleta).toLocaleString('pt-BR') : 'N/A',
                'Coordenadas': (l.latitude && l.longitude) ? `${l.latitude}, ${l.longitude}` : ''
            };
        });
        
        // Criar CSV
        const headers = Object.keys(coletores[0] || {});
        const csvRows = [];
        
        // Adicionar cabeçalhos
        csvRows.push(headers.join(','));
        
        // Adicionar dados
        coletores.forEach(coletor => {
            const values = headers.map(header => {
                const value = coletor[header];
                // Escapar valores que contêm vírgulas
                return typeof value === 'string' && value.includes(',') ? `"${value}"` : value;
            });
            csvRows.push(values.join(','));
        });
        
        // Criar arquivo
        const csvContent = csvRows.join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        link.setAttribute('href', url);
        link.setAttribute('download', `lixeiras_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
    } catch (error) {
        console.error('Erro ao exportar CSV:', error);
        alert('Erro ao exportar CSV. Tente novamente.');
    }
}

// Event listeners
/**
 * Atualiza a lista de coletores no grid
 * Reaplica filtros e renderiza novamente
 */
function atualizarListaLixeiras() {
    // Verificar se estamos na página do dashboard
    const binsGrid = document.getElementById('bins-grid');
    if (!binsGrid) {
        return; // Não é a página do dashboard
    }
    
    // Reaplicar filtros para atualizar a visualização
    aplicarFiltros();
}

/**
 * Configura listeners WebSocket para atualizações em tempo real
 */
function configurarWebSocketListeners() {
    // Evitar configurar múltiplas vezes
    if (websocketListenersConfigurados) {
        return;
    }
    
    if (!window.WebSocketClient || !window.WebSocketClient.estaConectado()) {
        return;
    }
    
    // Listener para atualização de coletor
    const handlerLixeira = function(event) {
        const coletor = event.detail;
        // Atualizar coletor na lista local
        const index = todasLixeiras.findIndex(l => l.id === coletor.id);
        if (index !== -1) {
            todasLixeiras[index] = coletor;
            atualizarListaLixeiras();
        } else {
            // Nova coletor - recarregar dados
            carregarDados();
        }
    };
    window.addEventListener('websocket:lixeira_atualizada', handlerLixeira);
    eventListeners.push({ type: 'websocket:lixeira_atualizada', handler: handlerLixeira });
    
    // Listener para nova coletor criada
    const handlerLixeiraCriada = function(event) {
        const coletor = event.detail;
        todasLixeiras.push(coletor);
        atualizarListaLixeiras();
        // Recarregar estatísticas
        obterEstatisticas()
            .then(atualizarEstatisticas)
            .catch(error => {
                console.error('Erro ao recarregar estatísticas:', error);
            });
    };
    window.addEventListener('websocket:lixeira_criada', handlerLixeiraCriada);
    eventListeners.push({ type: 'websocket:lixeira_criada', handler: handlerLixeiraCriada });
    
    // Listener para atualização de estatísticas
    const handlerEstatisticas = function(event) {
        atualizarEstatisticas(event.detail);
    };
    window.addEventListener('websocket:estatisticas_atualizadas', handlerEstatisticas);
    eventListeners.push({ type: 'websocket:estatisticas_atualizadas', handler: handlerEstatisticas });
    
    // Listener para nova notificação
    const handlerNotificacao = function(event) {
        // Atualizar badge de notificações
        if (typeof atualizarBadgeNotificacoes === 'function') {
            atualizarBadgeNotificacoes();
        }
    };
    window.addEventListener('websocket:nova_notificacao', handlerNotificacao);
    eventListeners.push({ type: 'websocket:nova_notificacao', handler: handlerNotificacao });
    
    // Marcar como configurado
    websocketListenersConfigurados = true;
}

/**
 * Remove todos os event listeners e limpa intervalos
 * Previne memory leaks
 */
function cleanupEventListeners() {
    // Verificar se eventListeners existe antes de usar
    if (eventListeners && Array.isArray(eventListeners)) {
        // Remover todos os event listeners registrados
        eventListeners.forEach(({ type, handler }) => {
            if (type && handler) {
                window.removeEventListener(type, handler);
            }
        });
        eventListeners.length = 0;
    }
    
    // Limpar intervalos
    if (intervaloAtualizacao) {
        clearInterval(intervaloAtualizacao);
        intervaloAtualizacao = null;
    }
    if (intervaloSimulacao) {
        clearInterval(intervaloSimulacao);
        intervaloSimulacao = null;
    }
    
    // Resetar flag para permitir reconfiguração
    websocketListenersConfigurados = false;
}

// Função para configurar listeners do botão atualizar
function configurarBotaoAtualizar() {
    const btnAtualizar = document.getElementById('btn-atualizar');
    if (btnAtualizar) {
        console.log('[Dashboard] Botão atualizar encontrado, configurando event listener');
        
        // Remover todos os listeners anteriores clonando o botão
        const novoBtn = btnAtualizar.cloneNode(true);
        if (btnAtualizar.parentNode) {
            btnAtualizar.parentNode.replaceChild(novoBtn, btnAtualizar);
        }
        
        // Adicionar novo listener
        novoBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('[Dashboard] Botão atualizar clicado!');
            atualizarComFeedback();
        });
        
        console.log('[Dashboard] Event listener do botão atualizar configurado');
        return true;
    } else {
        console.warn('[Dashboard] Botão atualizar (btn-atualizar) não encontrado no DOM');
        return false;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('[Dashboard] DOMContentLoaded disparado');
    
    // Verificar se estamos na página do dashboard (não na página de relatórios)
    // A página de relatórios tem o elemento 'relatorios-container'
    const isRelatoriosPage = document.querySelector('.relatorios-container') !== null;
    const isMapaPage = document.querySelector('.mapa-page-container') !== null;
    
    console.log('[Dashboard] isRelatoriosPage:', isRelatoriosPage, 'isMapaPage:', isMapaPage);
    
    if (isRelatoriosPage) {
        // É a página de relatórios, não executar listeners específicos do dashboard
        console.log('[Dashboard] Página de relatórios detectada, pulando configuração de listeners do dashboard');
        return;
    }
    
    // Configurar botão atualizar (disponível em todas as páginas exceto relatórios)
    configurarBotaoAtualizar();
    
    // Filtros
    const filterStatus = document.getElementById('filter-status');
    if (filterStatus) {
        filterStatus.addEventListener('change', function(e) {
            filtros.status = e.target.value;
            aplicarFiltros();
        });
    }
    
    const filterBusca = document.getElementById('filter-busca');
    if (filterBusca) {
        filterBusca.addEventListener('input', function(e) {
            filtros.busca = e.target.value;
            aplicarFiltros();
        });
    }

    // Ordenação
    const selectOrdenacao = document.getElementById('filter-ordenacao');
    if (selectOrdenacao) {
        selectOrdenacao.addEventListener('change', function(e) {
            ordenacao = e.target.value;
            aplicarFiltros();
        });
    }
    
    // Botão exportar
    const btnExportar = document.getElementById('btn-exportar');
    if (btnExportar) {
        btnExportar.addEventListener('click', exportarCSV);
    }

    // Botão simular
    const btnSimular = document.getElementById('btn-simular');
    if (btnSimular) {
        btnSimular.addEventListener('click', alternarSimulacao);
    }
    
    // Filtro de data no histórico
    const filterDate = document.getElementById('filter-date');
    if (filterDate) {
        filterDate.addEventListener('change', function(e) {
            dataFiltroHistorico = e.target.value || null;
            carregarHistorico();
        });
    }
    
    // Botão Relatório
    const btnRelatorio = document.getElementById('btn-relatorio');
    if (btnRelatorio) {
        btnRelatorio.addEventListener('click', function() {
            window.location.href = '/relatorios';
        });
    }
    
    // Ordenação ao clicar nos cabeçalhos da tabela de histórico
    const historyTable = document.getElementById('history-table');
    if (historyTable) {
        const headers = historyTable.querySelectorAll('thead th');
        const colunas = ['id', 'local', 'hora', 'volume', 'km', 'parceiro', 'tipo', 'status'];
        
        headers.forEach((th, index) => {
            if (colunas[index] && colunas[index] !== 'status') { // Status não é ordenável
                th.style.cursor = 'pointer';
                th.style.userSelect = 'none';
                th.title = 'Clique para ordenar';
                
                th.addEventListener('click', function() {
                    alternarOrdenacaoHistorico(colunas[index]);
                });
            }
        });
    }
    
    // Fechar modal
    const modalClose = document.getElementById('modal-close');
    if (modalClose) {
        modalClose.addEventListener('click', fecharModal);
    }
    
    const modalOverlay = document.getElementById('modal-overlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function(e) {
            if (e.target.id === 'modal-overlay') {
                fecharModal();
            }
        });
    }
    
    // Tornar verDetalhes global para acesso do mapa
    window.verDetalhes = verDetalhes;
    
    // Carregar dados iniciais
    carregarDados();
    
    // Configurar atualização automática (a cada 30 segundos)
    obterConfiguracoes().then(configuracoes => {
        const intervalo = (configuracoes.intervalo_atualizacao || 30) * 1000;
        intervaloAtualizacao = setInterval(carregarDados, intervalo);
    }).catch(err => {
        console.warn('Erro ao obter configurações:', err);
    });
});

// Limpar intervalo ao sair da página
window.addEventListener('beforeunload', function() {
    // Cleanup ao sair da página
    cleanupEventListeners();
});
