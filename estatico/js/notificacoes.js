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
    const filterColetor = document.getElementById('filter-coletor');
    const btnLimparFiltros = document.getElementById('btn-limpar-filtros');
    
    if (filterTipo) {
        filterTipo.addEventListener('change', aplicarFiltros);
    }
    if (filterEnviada) {
        filterEnviada.addEventListener('change', aplicarFiltros);
    }
        if (filterColetor) {
            filterColetor.addEventListener('input', debounce(aplicarFiltros, 500));
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
        
        // Aplicar filtros - garantir que filtrosAtivos está definido
        if (typeof filtrosAtivos === 'undefined' || filtrosAtivos === null) {
            filtrosAtivos = {};
        }
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
        if (window.Logger) {
            window.Logger.error('Erro ao carregar notificações:', error);
        } else {
            console.error('Erro ao carregar notificações:', error);
        }
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
    
    // Garantir que notifs é um array
    if (!Array.isArray(notifs)) {
        notifs = [];
    }
    
    list.innerHTML = notifs.map(notif => {
        // Validar notificação
        if (!notif || !notif.id) {
            return '';
        }
        const tipoIcon = notif.tipo === 'coletor_cheio' 
            ? '<img src="/static/icons/alert_icon.png" alt="Coletor" class="notificacao-icon-img">' 
            : '<img src="/static/icons/alert_icon.png" alt="Bateria" class="notificacao-icon-img">';
        const tipoLabel = notif.tipo === 'coletor_cheio' ? 'Coletor Cheio' : 'Bateria Baixa';
        const enviadaClass = notif.enviada ? 'enviada' : 'pendente';
        const lidaClass = notif.lida ? 'lida' : 'nao-lida';
        const enviadaBadge = notif.enviada 
            ? '<span class="badge-enviada"><img src="/static/icons/check_icon.png" alt="Enviada" class="badge-icon"> Enviada</span>' 
            : '<span class="badge-pendente"><img src="/static/icons/calendar.png" alt="Pendente" class="badge-icon"> Pendente</span>';
        const lidaBadge = notif.lida 
            ? '<span class="badge-lida"><img src="/static/icons/check_icon.png" alt="Lida" class="badge-icon"> Lida</span>' 
            : '<span class="badge-nao-lida"><img src="/static/icons/people_icon.png" alt="Não lida" class="badge-icon"> Não lida</span>';
        
        // Usar utilitários de formatação se disponíveis
        const formatarDataFn = window.Formatacao ? window.Formatacao.formatarData : formatarData;
        const formatarHoraFn = window.Formatacao ? window.Formatacao.formatarHora : formatarHora;
        const escapeHtmlFn = window.Formatacao ? window.Formatacao.escapeHtml : escapeHtml;
        
        const dataFormatada = formatarDataFn(notif.criada_em);
        const horaFormatada = formatarHoraFn(notif.criada_em);
        
        return `
            <div class="notificacao-item ${enviadaClass} ${lidaClass}" data-id="${notif.id}" role="article" aria-label="Notificação ${notif.lida ? 'lida' : 'não lida'}: ${escapeHtml(notif.titulo)}">
                <div class="notificacao-icon" aria-hidden="true">${tipoIcon}</div>
                <div class="notificacao-content">
                    <div class="notificacao-header">
                        <h3 class="notificacao-titulo">${escapeHtmlFn(notif.titulo)}</h3>
                        <div class="notificacao-badges">
                            ${enviadaBadge}
                            ${lidaBadge}
                        </div>
                    </div>
                    <p class="notificacao-mensagem">${escapeHtmlFn(notif.mensagem)}</p>
                    <div class="notificacao-detalhes">
                        ${notif.coletor && notif.coletor.id && notif.coletor.localizacao ? `<span class="detalhe-item"><img src="/static/icons/alvo_icon.png" alt="Coletor" class="inline-icon"> Coletor #${notif.coletor.id}: ${escapeHtmlFn(String(notif.coletor.localizacao))}</span>` : ''}
                        ${notif.sensor && notif.sensor.id && typeof notif.sensor.bateria === 'number' ? `<span class="detalhe-item"><img src="/static/icons/alert_icon.png" alt="Sensor" class="inline-icon"> Sensor #${notif.sensor.id}: ${notif.sensor.bateria}%</span>` : ''}
                        <span class="detalhe-item"><img src="/static/icons/calendar.png" alt="Data" class="inline-icon"> ${dataFormatada} às ${horaFormatada}</span>
                        ${notif.enviada_em ? `<span class="detalhe-item"><img src="/static/icons/prancheta_icon.png" alt="Enviada" class="inline-icon"> Enviada em ${formatarDataFn(notif.enviada_em)} às ${formatarHoraFn(notif.enviada_em)}</span>` : ''}
                        ${notif.lida_em ? `<span class="detalhe-item"><img src="/static/icons/people_icon.png" alt="Lida" class="inline-icon"> Lida em ${formatarDataFn(notif.lida_em)} às ${formatarHoraFn(notif.lida_em)}</span>` : ''}
                    </div>
                    ${!notif.lida ? `<button class="btn-marcar-lida" onclick="marcarComoLida(${notif.id})" aria-label="Marcar notificação como lida"><img src="/static/icons/check_icon.png" alt="Marcar" class="btn-icon-small"> Marcar como lida</button>` : ''}
                </div>
            </div>
        `;
    }).filter(item => item).join('');
}

/**
 * Atualiza estatísticas
 */
function atualizarEstatisticas(notifs) {
    // Garantir que notifs é um array
    if (!Array.isArray(notifs)) {
        notifs = [];
    }
    
    const total = notifs.length;
    const enviadas = notifs.filter(n => n && n.enviada === true).length;
    const pendentes = total - enviadas;
    const lidas = notifs.filter(n => n && n.lida === true).length;
    const naoLidas = total - lidas;
    
    // Notificações de hoje
    const hoje = new Date().toISOString().split('T')[0];
    const hojeCount = notifs.filter(n => {
        if (!n || !n.criada_em) return false;
        try {
            const dataStr = String(n.criada_em);
            return dataStr.split('T')[0] === hoje;
        } catch (e) {
            return false;
        }
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
    const filterColetor = document.getElementById('filter-coletor');
    
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
        if (filterColetor && filterColetor.value) {
            filtrosAtivos.coletor_id = parseInt(filterColetor.value);
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
    const filterColetor = document.getElementById('filter-coletor');
    
    if (filterTipo) filterTipo.value = '';
    if (filterEnviada) filterEnviada.value = '';
    if (filterLida) filterLida.value = '';
        if (filterColetor) filterColetor.value = '';
    
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
              `Coletores alertados: ${resultado.estatisticas.coletores_alertados}\n` +
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
 * Formata data (usa utilitário se disponível)
 */
function formatarData(dataISO) {
    if (window.Formatacao) {
        return window.Formatacao.formatarData(dataISO);
    }
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
 * Formata hora (usa utilitário se disponível)
 */
function formatarHora(dataISO) {
    if (window.Formatacao) {
        return window.Formatacao.formatarHora(dataISO);
    }
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
 * Escapa HTML para prevenir XSS (usa utilitário se disponível)
 */
function escapeHtml(text) {
    if (window.Formatacao) {
        return window.Formatacao.escapeHtml(text);
    }
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Debounce para limitar chamadas de função (usa utilitário se disponível)
 */
function debounce(func, wait) {
    if (window.Formatacao && window.Formatacao.debounce) {
        return window.Formatacao.debounce(func, wait);
    }
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

