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
let filtros = {
    status: '',
    busca: ''
};

// Função para determinar status da lixeira
function determinarStatus(lixeira) {
    const nivel = lixeira.nivel_preenchimento || 0;
    const statusLixeira = lixeira.status || 'ativo';
    
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

// Função para criar card de lixeira
function criarCardLixeira(lixeira) {
    const status = determinarStatus(lixeira);
    const nivel = Math.round(lixeira.nivel_preenchimento || 0);
    
    const card = document.createElement('div');
    card.className = `bin-card ${status.tipo === 'alert' ? 'alert' : status.tipo === 'warning' ? 'warning' : ''}`;
    card.dataset.id = lixeira.id;
    
    card.innerHTML = `
        <div class="bin-header">
            <div class="bin-info">
                <div class="bin-id">#L${String(lixeira.id).padStart(3, '0')}</div>
                <div class="bin-name">${lixeira.localizacao || 'Sem localização'}</div>
                <div class="bin-location">${lixeira.tipo || 'Resíduos Eletrônicos'}</div>
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
            <span class="bin-update">${formatarData(lixeira.ultima_coleta)}</span>
            <button class="bin-action" onclick="verDetalhes(${lixeira.id})">Detalhes</button>
        </div>
    `;
    
    return card;
}

// Função para renderizar grid de lixeiras
function renderizarGridLixeiras(lixeirasFiltradas) {
    const grid = document.getElementById('bins-grid');
    grid.innerHTML = '';
    
    if (lixeirasFiltradas.length === 0) {
        grid.innerHTML = '<div class="loading-message">Nenhuma lixeira encontrada</div>';
        return;
    }
    
    lixeirasFiltradas.forEach(lixeira => {
        const card = criarCardLixeira(lixeira);
        grid.appendChild(card);
    });
}

// Função para atualizar estatísticas
function atualizarEstatisticas(dados) {
    estatisticas = dados;
    
    document.getElementById('stat-total').textContent = dados.total_lixeiras || 0;
    document.getElementById('stat-nivel-medio').textContent = `${dados.nivel_medio || 0}%`;
    document.getElementById('stat-alertas').textContent = dados.lixeiras_alerta || 0;
    document.getElementById('stat-coletas-hoje').textContent = dados.coletas_hoje || 0;
}

// Função para atualizar alertas
function atualizarAlertas() {
    const alertasBar = document.getElementById('alerts-bar');
    const alertTitle = document.getElementById('alert-title');
    const alertMessage = document.getElementById('alert-message');
    
    const lixeirasAlerta = todasLixeiras.filter(l => l.nivel_preenchimento >= 80);
    
    if (lixeirasAlerta.length > 0) {
        alertTitle.textContent = `${lixeirasAlerta.length} lixeira(s) precisam de atenção urgente`;
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
    
    renderizarGridLixeiras(lixeirasFiltradas);
}

// Função para carregar dados
async function carregarDados() {
    try {
        // Atualizar status de conexão
        const statusIndicator = document.getElementById('status-indicator');
        statusIndicator.querySelector('span').textContent = 'Carregando...';
        
        // Carregar lixeiras e estatísticas em paralelo
        const [lixeiras, stats] = await Promise.all([
            obterTodasLixeiras(),
            obterEstatisticas()
        ]);
        
        todasLixeiras = lixeiras;
        atualizarEstatisticas(stats);
        atualizarAlertas();
        aplicarFiltros();
        
        // Carregar histórico
        carregarHistorico();
        
        // Atualizar status
        statusIndicator.querySelector('span').textContent = 'Conectado';
        
    } catch (error) {
        console.error('Erro ao carregar dados:', error);
        const statusIndicator = document.getElementById('status-indicator');
        statusIndicator.querySelector('span').textContent = 'Erro';
        statusIndicator.style.background = '#f8d7da';
        
        document.getElementById('bins-grid').innerHTML = 
            '<div class="loading-message">Erro ao carregar dados. Tente novamente.</div>';
    }
}

// Função para carregar histórico
async function carregarHistorico() {
    try {
        const historico = await obterHistorico();
        const tbody = document.getElementById('history-tbody');
        
        if (historico.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center;">Nenhuma coleta registrada</td></tr>';
            return;
        }
        
        tbody.innerHTML = historico.slice(0, 10).map(coleta => {
            const lixeira = todasLixeiras.find(l => l.id === coleta.id_lixeira);
            const data = new Date(coleta.data_coleta);
            const hora = data.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
            const dataFormatada = data.toLocaleDateString('pt-BR');
            
            return `
                <tr>
                    <td>#L${String(coleta.id_lixeira).padStart(3, '0')}</td>
                    <td>${lixeira ? lixeira.localizacao : 'N/A'}</td>
                    <td>${dataFormatada} ${hora}</td>
                    <td>${coleta.volume_estimado ? Math.round(coleta.volume_estimado) + 'L' : 'N/A'}</td>
                    <td>${coleta.volume_estimado ? Math.round(coleta.volume_estimado) : 'N/A'}</td>
                    <td><span class="bin-status-badge status-ok">OK</span></td>
                </tr>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Erro ao carregar histórico:', error);
    }
}

// Função para ver detalhes
async function verDetalhes(id) {
    try {
        const lixeira = await obterLixeira(id);
        const historico = await obterHistorico();
        const historicoLixeira = historico.filter(c => c.id_lixeira === id).slice(0, 5);
        
        const status = determinarStatus(lixeira);
        const nivel = Math.round(lixeira.nivel_preenchimento || 0);
        
        // Preencher modal
        document.getElementById('modal-title').textContent = 
            `Lixeira #L${String(lixeira.id).padStart(3, '0')} - ${lixeira.localizacao || 'Sem localização'}`;
        
        const modalBody = document.getElementById('modal-body');
        modalBody.innerHTML = `
            <div class="modal-detail-card">
                <div class="modal-detail-header">
                    <div>
                        <div class="modal-detail-title">${lixeira.localizacao || 'Sem localização'}</div>
                        <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">
                            ${lixeira.tipo || 'Resíduos Eletrônicos'} | Atualizado ${formatarData(lixeira.ultima_coleta)}
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
                        <span class="modal-info-value">${lixeira.status || 'ativo'}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Tipo</span>
                        <span class="modal-info-value">${lixeira.tipo || 'Resíduos Eletrônicos'}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Última Coleta</span>
                        <span class="modal-info-value">${formatarData(lixeira.ultima_coleta)}</span>
                    </div>
                    <div class="modal-info-item">
                        <span class="modal-info-label">Coordenadas</span>
                        <span class="modal-info-value">
                            ${lixeira.coordenadas ? 
                                `${lixeira.coordenadas.latitude.toFixed(4)}, ${lixeira.coordenadas.longitude.toFixed(4)}` : 
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
                            <th style="padding: 8px; text-align: left;">Volume</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${historicoLixeira.map(coleta => {
                            const data = new Date(coleta.data_coleta);
                            return `
                                <tr>
                                    <td style="padding: 8px;">${data.toLocaleString('pt-BR')}</td>
                                    <td style="padding: 8px;">${coleta.volume_estimado ? Math.round(coleta.volume_estimado) + 'L' : 'N/A'}</td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
            ` : ''}
        `;
        
        // Mostrar modal
        document.getElementById('modal-overlay').style.display = 'flex';
        
    } catch (error) {
        console.error('Erro ao carregar detalhes:', error);
        alert('Erro ao carregar detalhes da lixeira.');
    }
}

// Função para fechar modal
function fecharModal() {
    document.getElementById('modal-overlay').style.display = 'none';
}

// Função para exportar CSV
function exportarCSV() {
    try {
        // Preparar dados
        const lixeiras = todasLixeiras.map(l => {
            const status = determinarStatus(l);
            return {
                'ID': `L${String(l.id).padStart(3, '0')}`,
                'Localização': l.localizacao || '',
                'Nível (%)': l.nivel_preenchimento || 0,
                'Status': status.texto,
                'Tipo': l.tipo || '',
                'Última Coleta': l.ultima_coleta ? new Date(l.ultima_coleta).toLocaleString('pt-BR') : 'N/A',
                'Coordenadas': l.coordenadas ? `${l.coordenadas.latitude}, ${l.coordenadas.longitude}` : ''
            };
        });
        
        // Criar CSV
        const headers = Object.keys(lixeiras[0] || {});
        const csvRows = [];
        
        // Adicionar cabeçalhos
        csvRows.push(headers.join(','));
        
        // Adicionar dados
        lixeiras.forEach(lixeira => {
            const values = headers.map(header => {
                const value = lixeira[header];
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
document.addEventListener('DOMContentLoaded', function() {
    // Botão atualizar
    document.getElementById('btn-atualizar').addEventListener('click', carregarDados);
    
    // Filtros
    document.getElementById('filter-status').addEventListener('change', function(e) {
        filtros.status = e.target.value;
        aplicarFiltros();
    });
    
    document.getElementById('filter-busca').addEventListener('input', function(e) {
        filtros.busca = e.target.value;
        aplicarFiltros();
    });
    
    // Botão exportar
    document.getElementById('btn-exportar').addEventListener('click', exportarCSV);
    
    // Fechar modal
    document.getElementById('modal-close').addEventListener('click', fecharModal);
    document.getElementById('modal-overlay').addEventListener('click', function(e) {
        if (e.target.id === 'modal-overlay') {
            fecharModal();
        }
    });
    
    // Carregar dados iniciais
    carregarDados();
    
    // Configurar atualização automática (a cada 30 segundos)
    obterConfiguracoes().then(configuracoes => {
        const intervalo = (configuracoes.intervalo_atualizacao || 30) * 1000;
        intervaloAtualizacao = setInterval(carregarDados, intervalo);
    });
});

// Limpar intervalo ao sair da página
window.addEventListener('beforeunload', function() {
    if (intervaloAtualizacao) {
        clearInterval(intervaloAtualizacao);
    }
});
