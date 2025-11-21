/*
Página de Notificações - Dashboard-TRONIK
=========================================
Gerencia a visualização e interação com notificações.
*/

// Estado da página
let notificacoes = [];
let filtrosAtivos = {};

// Inicialização quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    carregarNotificacoes();
    configurarEventListeners();
    atualizarBadgeNotificacoes();
    
    // Atualizar badge periodicamente (a cada 5 minutos)
    setInterval(atualizarBadgeNotificacoes, 5 * 60 * 1000);
});

/**
 * Configura os event listeners
 */
function configurarEventListeners() {
    // Botão de atualizar
    const btnAtualizar = document.getElementById('btn-atualizar');
    if (btnAtualizar) {
        btnAtualizar.addEventListener('click', carregarNotificacoes);
    }
    
    // Botão de processar alertas
    const btnProcessar = document.getElementById('btn-processar-alertas');
    if (btnProcessar) {
        btnProcessar.addEventListener('click', processarAlertasHandler);
    }
    
    // Filtros
    const filterTipo = document.getElementById('filter-tipo');
    const filterEnviada = document.getElementById('filter-enviada');
    const filterLixeira = document.getElementById('filter-lixeira');
    const btnLimparFiltros = document.getElementById('btn-limpar-filtros');
    
    if (filterTipo) {
        filterTipo.addEventListener('change', aplicarFiltros);
    }
    if (filterEnviada) {
        filterEnviada.addEventListener('change', aplicarFiltros);
    }
    if (filterLixeira) {
        filterLixeira.addEventListener('input', debounce(aplicarFiltros, 500));
    }
    
    // Filtro de lidas
    const filterLida = document.getElementById('filter-lida');
    if (filterLida) {
        filterLida.addEventListener('change', aplicarFiltros);
    }
    
    if (btnLimparFiltros) {
        btnLimparFiltros.addEventListener('click', limparFiltros);
    }
}

/**
 * Carrega notificações do servidor
 */
async function carregarNotificacoes() {
    const loading = document.getElementById('notificacoes-loading');
    const list = document.getElementById('notificacoes-list');
    const empty = document.getElementById('notificacoes-empty');
    
    try {
        if (loading) loading.style.display = 'block';
        if (list) list.style.display = 'none';
        if (empty) empty.style.display = 'none';
        
        // Aplicar filtros
        const filtros = { ...filtrosAtivos, limite: 100 };
        notificacoes = await obterNotificacoes(filtros);
        
        if (loading) loading.style.display = 'none';
        
        if (notificacoes.length === 0) {
            if (empty) empty.style.display = 'block';
            if (list) list.style.display = 'none';
        } else {
            if (list) list.style.display = 'block';
            if (empty) empty.style.display = 'none';
            exibirNotificacoes(notificacoes);
            atualizarEstatisticas(notificacoes);
        }
    } catch (error) {
        console.error('Erro ao carregar notificações:', error);
        if (loading) loading.style.display = 'none';
        alert('Erro ao carregar notificações: ' + (error.message || 'Erro desconhecido'));
    }
}

/**
 * Exibe notificações na lista
 */
function exibirNotificacoes(notifs) {
    const list = document.getElementById('notificacoes-list');
    if (!list) return;
    
    list.innerHTML = notifs.map(notif => {
        const tipoIcon = notif.tipo === 'lixeira_cheia' ? '🗑️' : '🔋';
        const tipoLabel = notif.tipo === 'lixeira_cheia' ? 'Lixeira Cheia' : 'Bateria Baixa';
        const enviadaClass = notif.enviada ? 'enviada' : 'pendente';
        const lidaClass = notif.lida ? 'lida' : 'nao-lida';
        const enviadaBadge = notif.enviada 
            ? '<span class="badge-enviada">✓ Enviada</span>' 
            : '<span class="badge-pendente">⏳ Pendente</span>';
        const lidaBadge = notif.lida 
            ? '<span class="badge-lida">✓ Lida</span>' 
            : '<span class="badge-nao-lida">👁️ Não lida</span>';
        
        const dataFormatada = formatarData(notif.criada_em);
        const horaFormatada = formatarHora(notif.criada_em);
        
        return `
            <div class="notificacao-item ${enviadaClass} ${lidaClass}" data-id="${notif.id}" role="article" aria-label="Notificação ${notif.lida ? 'lida' : 'não lida'}: ${escapeHtml(notif.titulo)}">
                <div class="notificacao-icon" aria-hidden="true">${tipoIcon}</div>
                <div class="notificacao-content">
                    <div class="notificacao-header">
                        <h3 class="notificacao-titulo">${escapeHtml(notif.titulo)}</h3>
                        <div class="notificacao-badges">
                            ${enviadaBadge}
                            ${lidaBadge}
                        </div>
                    </div>
                    <p class="notificacao-mensagem">${escapeHtml(notif.mensagem)}</p>
                    <div class="notificacao-detalhes">
                        ${notif.lixeira ? `<span class="detalhe-item">📍 Lixeira #${notif.lixeira.id}: ${escapeHtml(notif.lixeira.localizacao)}</span>` : ''}
                        ${notif.sensor ? `<span class="detalhe-item">🔋 Sensor #${notif.sensor.id}: ${notif.sensor.bateria}%</span>` : ''}
                        <span class="detalhe-item">📅 ${dataFormatada} às ${horaFormatada}</span>
                        ${notif.enviada_em ? `<span class="detalhe-item">✉️ Enviada em ${formatarData(notif.enviada_em)} às ${formatarHora(notif.enviada_em)}</span>` : ''}
                        ${notif.lida_em ? `<span class="detalhe-item">👁️ Lida em ${formatarData(notif.lida_em)} às ${formatarHora(notif.lida_em)}</span>` : ''}
                    </div>
                    ${!notif.lida ? `<button class="btn-marcar-lida" onclick="marcarComoLida(${notif.id})" aria-label="Marcar notificação como lida">✓ Marcar como lida</button>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Atualiza estatísticas
 */
function atualizarEstatisticas(notifs) {
    const total = notifs.length;
    const enviadas = notifs.filter(n => n.enviada).length;
    const pendentes = total - enviadas;
    const lidas = notifs.filter(n => n.lida).length;
    const naoLidas = total - lidas;
    
    // Notificações de hoje
    const hoje = new Date().toISOString().split('T')[0];
    const hojeCount = notifs.filter(n => {
        if (!n.criada_em) return false;
        return n.criada_em.split('T')[0] === hoje;
    }).length;
    
    const statTotal = document.getElementById('stat-total');
    const statEnviadas = document.getElementById('stat-enviadas');
    const statPendentes = document.getElementById('stat-pendentes');
    const statHoje = document.getElementById('stat-hoje');
    
    if (statTotal) {
        statTotal.textContent = total;
        statTotal.setAttribute('aria-label', `${total} notificação${total !== 1 ? 'ões' : ''} no total`);
    }
    if (statEnviadas) {
        statEnviadas.textContent = enviadas;
        statEnviadas.setAttribute('aria-label', `${enviadas} notificação${enviadas !== 1 ? 'ões' : ''} enviada${enviadas !== 1 ? 's' : ''}`);
    }
    if (statPendentes) {
        statPendentes.textContent = pendentes;
        statPendentes.setAttribute('aria-label', `${pendentes} notificação${pendentes !== 1 ? 'ões' : ''} pendente${pendentes !== 1 ? 's' : ''}`);
    }
    if (statHoje) {
        statHoje.textContent = hojeCount;
        statHoje.setAttribute('aria-label', `${hojeCount} notificação${hojeCount !== 1 ? 'ões' : ''} de hoje`);
    }
}

/**
 * Aplica filtros
 */
function aplicarFiltros() {
    const filterTipo = document.getElementById('filter-tipo');
    const filterEnviada = document.getElementById('filter-enviada');
    const filterLida = document.getElementById('filter-lida');
    const filterLixeira = document.getElementById('filter-lixeira');
    
    filtrosAtivos = {};
    
    if (filterTipo && filterTipo.value) {
        filtrosAtivos.tipo = filterTipo.value;
    }
    if (filterEnviada && filterEnviada.value) {
        filtrosAtivos.enviada = filterEnviada.value;
    }
    if (filterLida && filterLida.value) {
        filtrosAtivos.lida = filterLida.value;
    }
    if (filterLixeira && filterLixeira.value) {
        filtrosAtivos.lixeira_id = parseInt(filterLixeira.value);
    }
    
    carregarNotificacoes();
}

/**
 * Limpa filtros
 */
function limparFiltros() {
    const filterTipo = document.getElementById('filter-tipo');
    const filterEnviada = document.getElementById('filter-enviada');
    const filterLida = document.getElementById('filter-lida');
    const filterLixeira = document.getElementById('filter-lixeira');
    
    if (filterTipo) filterTipo.value = '';
    if (filterEnviada) filterEnviada.value = '';
    if (filterLida) filterLida.value = '';
    if (filterLixeira) filterLixeira.value = '';
    
    filtrosAtivos = {};
    carregarNotificacoes();
}

/**
 * Processa alertas
 */
async function processarAlertasHandler() {
    const btn = document.getElementById('btn-processar-alertas');
    if (!btn) return;
    
    if (!confirm('Deseja processar alertas e enviar notificações por email?')) {
        return;
    }
    
    try {
        btn.disabled = true;
        btn.textContent = 'Processando...';
        
        const resultado = await processarAlertas();
        
        alert(`Alertas processados com sucesso!\n\n` +
              `Lixeiras alertadas: ${resultado.estatisticas.lixeiras_alertadas}\n` +
              `Sensores alertados: ${resultado.estatisticas.sensores_alertados}\n` +
              `Emails enviados: ${resultado.estatisticas.emails_enviados}`);
        
        // Recarregar notificações
        await carregarNotificacoes();
        await atualizarBadgeNotificacoes();
    } catch (error) {
        console.error('Erro ao processar alertas:', error);
        alert('Erro ao processar alertas: ' + (error.message || 'Erro desconhecido'));
    } finally {
        btn.disabled = false;
        btn.textContent = '🔔 Processar Alertas';
    }
}

/**
 * Marca uma notificação como lida
 */
async function marcarComoLida(notificacaoId) {
    try {
        await marcarNotificacaoLida(notificacaoId);
        
        // Atualizar visualmente
        const item = document.querySelector(`.notificacao-item[data-id="${notificacaoId}"]`);
        if (item) {
            item.classList.remove('nao-lida');
            item.classList.add('lida');
            
            // Remover botão e adicionar badge
            const content = item.querySelector('.notificacao-content');
            const btn = item.querySelector('.btn-marcar-lida');
            if (btn) btn.remove();
            
            const badges = item.querySelector('.notificacao-badges');
            if (badges && !badges.querySelector('.badge-lida')) {
                badges.innerHTML += '<span class="badge-lida">✓ Lida</span>';
            }
        }
        
        // Atualizar estatísticas e badge
        await carregarNotificacoes();
        await atualizarBadgeNotificacoes();
    } catch (error) {
        console.error('Erro ao marcar notificação como lida:', error);
        alert('Erro ao marcar notificação como lida: ' + (error.message || 'Erro desconhecido'));
    }
}

/**
 * Atualiza badge de notificações no header
 */
async function atualizarBadgeNotificacoes() {
    try {
        const response = await obterNotificacoesPendentesCount();
        const pendentes = response.count || 0;
        
        const badge = document.getElementById('notification-badge');
        if (badge) {
            if (pendentes > 0) {
                badge.textContent = pendentes > 99 ? '99+' : pendentes;
                badge.style.display = 'inline-block';
                badge.setAttribute('aria-label', `${pendentes} notificação${pendentes > 1 ? 'ões' : ''} não lida${pendentes > 1 ? 's' : ''}`);
            } else {
                badge.style.display = 'none';
                badge.removeAttribute('aria-label');
            }
        }
    } catch (error) {
        console.error('Erro ao atualizar badge:', error);
    }
}

/**
 * Formata data
 */
function formatarData(dataISO) {
    if (!dataISO) return 'N/A';
    try {
        const data = new Date(dataISO);
        return data.toLocaleDateString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    } catch (e) {
        return dataISO;
    }
}

/**
 * Formata hora
 */
function formatarHora(dataISO) {
    if (!dataISO) return 'N/A';
    try {
        const data = new Date(dataISO);
        return data.toLocaleTimeString('pt-BR', {
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return dataISO;
    }
}

/**
 * Escapa HTML para prevenir XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Debounce para limitar chamadas de função
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

