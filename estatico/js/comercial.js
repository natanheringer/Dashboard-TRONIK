/**
 * Dashboard Comercial - Dashboard-TRONIK
 * ======================================
 * Lógica frontend para o dashboard comercial.
 */

// Variáveis globais (removidas duplicatas - definidas mais abaixo)

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    carregarDashboard();
    inicializarDragAndDrop();
    
    // Atualizar a cada 5 minutos
    setInterval(carregarDashboard, 5 * 60 * 1000);
});

// Inicializar drag and drop
function inicializarDragAndDrop() {
    // Verificar se Sortable está disponível
    if (typeof Sortable === 'undefined') {
        console.warn('SortableJS não carregado');
        return;
    }
    
    // Configuração comum para todos os Sortables
    const sortableConfig = {
        animation: 150,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        dragClass: 'sortable-drag',
        group: {
            name: 'comercial-containers',
            pull: true,  // Permite mover elementos para fora
            put: true    // Permite receber elementos de outros grupos
        },
        onEnd: function(evt) {
            salvarOrdemContainers();
        }
    };
    
    // Criar Sortable para KPIs Grid
    const kpisGrid = document.getElementById('kpis-grid');
    if (kpisGrid) {
        new Sortable(kpisGrid, sortableConfig);
    }
    
    // Criar Sortable para Grid Principal (coluna esquerda)
    const gridEsquerda = document.querySelector('.comercial-grid > div:first-child');
    if (gridEsquerda) {
        new Sortable(gridEsquerda, sortableConfig);
    }
    
    // Criar Sortable para Grid Principal (coluna direita)
    const gridDireita = document.querySelector('.comercial-grid > div:last-child');
    if (gridDireita) {
        new Sortable(gridDireita, sortableConfig);
    }
    
    // Criar área sortable para resumo e comparação
    // Eles estão diretamente no comercial-container, então precisamos criar um wrapper
    const resumoFinanceiro = document.querySelector('[data-container-id="resumo-financeiro"]');
    const comparacaoMes = document.querySelector('[data-container-id="comparacao-mes"]');
    const comercialContainer = document.querySelector('.comercial-container');
    
    if (resumoFinanceiro && comercialContainer) {
        // Verificar se já existe wrapper
        let wrapperResumo = resumoFinanceiro.parentElement;
        
        // Se resumo não está em um wrapper dedicado, criar um
        if (!wrapperResumo.classList.contains('drag-area-resumo')) {
            // Criar wrapper para área de resumo/comparação
            wrapperResumo = document.createElement('div');
            wrapperResumo.className = 'drag-area-resumo';
            wrapperResumo.style.width = '100%';
            wrapperResumo.style.marginBottom = '1.5rem';
            
            // Inserir antes do grid principal
            const comercialGrid = document.getElementById('comercial-grid');
            if (comercialGrid) {
                comercialContainer.insertBefore(wrapperResumo, comercialGrid);
            } else {
                comercialContainer.appendChild(wrapperResumo);
            }
            
            // Mover resumo para wrapper
            if (resumoFinanceiro.parentElement) {
                resumoFinanceiro.parentElement.removeChild(resumoFinanceiro);
            }
            wrapperResumo.appendChild(resumoFinanceiro);
            
            // Mover comparação se existir e estiver no mesmo nível
            if (comparacaoMes && comparacaoMes.parentElement === comercialContainer) {
                comercialContainer.removeChild(comparacaoMes);
                wrapperResumo.appendChild(comparacaoMes);
            }
        }
        
        // Criar Sortable no wrapper
        new Sortable(wrapperResumo, {
            ...sortableConfig,
            direction: 'horizontal'
        });
    }
    
    // Adicionar cursor move e indicador visual a todos os containers
    document.querySelectorAll('[data-container-id]').forEach(container => {
        container.style.cursor = 'move';
        container.classList.add('draggable-container');
    });
}

// Salvar ordem dos containers
async function salvarOrdemContainers() {
    try {
        // Coletar ordem de todas as áreas
        const ordem = [];
        
        // Ordem dos KPIs
        const kpisGrid = document.getElementById('kpis-grid');
        if (kpisGrid) {
            Array.from(kpisGrid.querySelectorAll('[data-container-id]')).forEach(el => {
                ordem.push(el.getAttribute('data-container-id'));
            });
        }
        
        // Ordem de resumo e comparação
        const resumo = document.querySelector('[data-container-id="resumo-financeiro"]');
        const comparacao = document.querySelector('[data-container-id="comparacao-mes"]');
        if (resumo && resumo.parentElement) {
            const parent = resumo.parentElement;
            const siblings = Array.from(parent.children).filter(c => 
                c.hasAttribute('data-container-id') && 
                (c.getAttribute('data-container-id') === 'resumo-financeiro' || 
                 c.getAttribute('data-container-id') === 'comparacao-mes')
            );
            siblings.forEach(el => {
                if (!ordem.includes(el.getAttribute('data-container-id'))) {
                    ordem.push(el.getAttribute('data-container-id'));
                }
            });
        }
        
        // Ordem do grid principal (esquerda)
        const gridEsquerda = document.querySelector('.comercial-grid > div:first-child');
        if (gridEsquerda) {
            Array.from(gridEsquerda.querySelectorAll('[data-container-id]')).forEach(el => {
                const id = el.getAttribute('data-container-id');
                if (!ordem.includes(id)) {
                    ordem.push(id);
                }
            });
        }
        
        // Ordem do grid principal (direita)
        const gridDireita = document.querySelector('.comercial-grid > div:last-child');
        if (gridDireita) {
            Array.from(gridDireita.querySelectorAll('[data-container-id]')).forEach(el => {
                const id = el.getAttribute('data-container-id');
                if (!ordem.includes(id)) {
                    ordem.push(id);
                }
            });
        }
        
        const response = await fetch('/api/comercial/layout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ordem_containers: ordem })
        });
        
        if (!response.ok) {
            console.error('Erro ao salvar layout');
            return;
        }
        
        // Feedback visual discreto
        const btn = document.getElementById('btn-reset-layout');
        if (btn) {
            const textoOriginal = btn.textContent;
            btn.textContent = '✓ Salvo';
            btn.style.background = '#22c55e';
            btn.style.color = 'white';
            setTimeout(() => {
                btn.textContent = textoOriginal;
                btn.style.background = '';
                btn.style.color = '';
            }, 2000);
        }
    } catch (erro) {
        console.error('Erro ao salvar ordem:', erro);
    }
}

// Resetar layout para ordem padrão
function resetarLayout() {
    if (!confirm('Deseja resetar o layout para a ordem padrão?')) {
        return;
    }
    
    // Ordem padrão por área
    const ordemPadraoKPIs = [
        'kpi-meta', 'kpi-faturamento', 'kpi-falta', 'kpi-agendado', 'kpi-projecao',
        'kpi-lucro-medio', 'kpi-rentabilidade', 'kpi-ticket-medio'
    ];
    
    const ordemPadraoResumo = ['resumo-financeiro', 'comparacao-mes'];
    const ordemPadraoEsquerda = ['proximas-coletas', 'clientes-inativos', 'sugestoes'];
    const ordemPadraoDireita = ['alertas', 'grafico-evolucao', 'grafico-parceiros', 'tabela-parceiros'];
    
    // Coletar containers
    const containers = {};
    [...ordemPadraoKPIs, ...ordemPadraoResumo, ...ordemPadraoEsquerda, ...ordemPadraoDireita].forEach(id => {
        const el = document.querySelector(`[data-container-id="${id}"]`);
        if (el) {
            containers[id] = el;
        }
    });
    
    // Reorganizar KPIs
    const kpisGrid = document.getElementById('kpis-grid');
    if (kpisGrid) {
        ordemPadraoKPIs.forEach(id => {
            if (containers[id]) {
                kpisGrid.appendChild(containers[id]);
            }
        });
    }
    
    // Reorganizar resumo e comparação (antes do grid)
    const comercialGrid = document.getElementById('comercial-grid');
    const comercialContainer = document.querySelector('.comercial-container');
    
    if (comercialContainer && comercialGrid) {
        ordemPadraoResumo.forEach(id => {
            if (containers[id]) {
                // Remover de onde está
                if (containers[id].parentElement) {
                    containers[id].parentElement.removeChild(containers[id]);
                }
                // Inserir antes do grid
                comercialContainer.insertBefore(containers[id], comercialGrid);
            }
        });
    }
    
    // Reorganizar grid principal (coluna esquerda)
    const gridEsquerda = document.querySelector('.comercial-grid > div:first-child');
    if (gridEsquerda) {
        ordemPadraoEsquerda.forEach(id => {
            if (containers[id]) {
                // Remover de onde está
                if (containers[id].parentElement && containers[id].parentElement !== gridEsquerda) {
                    containers[id].parentElement.removeChild(containers[id]);
                }
                gridEsquerda.appendChild(containers[id]);
            }
        });
    }
    
    // Reorganizar grid principal (coluna direita)
    const gridDireita = document.querySelector('.comercial-grid > div:last-child');
    if (gridDireita) {
        ordemPadraoDireita.forEach(id => {
            if (containers[id]) {
                // Remover de onde está
                if (containers[id].parentElement && containers[id].parentElement !== gridDireita) {
                    containers[id].parentElement.removeChild(containers[id]);
                }
                gridDireita.appendChild(containers[id]);
            }
        });
    }
    
    // Salvar ordem resetada
    salvarOrdemContainers();
    
    mostrarSucesso('Layout resetado para ordem padrão!');
}

// Variáveis globais
let dashboardData = {};
let periodoAtual = { mes: null, ano: null };
let parceiroSelecionadoGrafico = '';
let parceiroSelecionadoTabela = '';
let graficoEvolucao = null;
let graficoParceiros = null;

// Carregar dados do dashboard
async function carregarDashboard(mes = null, ano = null, meses = null, todos = false) {
    try {
        mostrarLoading(true);
        
        let url = '/api/comercial/dashboard';
        const params = [];
        if (todos) {
            params.push('todos=true');
        } else {
            if (mes && ano) {
                params.push(`mes=${mes}`);
                params.push(`ano=${ano}`);
            }
            if (meses) {
                params.push(`meses=${meses}`);
            }
        }
        if (params.length > 0) {
            url += '?' + params.join('&');
        }
        
        const response = await fetch(url);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Erro HTTP:', response.status, errorText);
            throw new Error(`Erro ${response.status}: ${errorText}`);
        }
        
        dashboardData = await response.json();
        periodoAtual = dashboardData.periodo || { mes: null, ano: null };
        
        // Carregar lista de parceiros para filtros
        await carregarListaParceiros();
        
        renderizarKPIs();
        renderizarResumoFinanceiro();
        renderizarProximasColetas();
        renderizarClientesInativos();
        renderizarSugestoes();
        renderizarAlertas();
        await renderizarGraficoEvolucao(mes, ano);
        renderizarGraficoParceiros();
        renderizarTabelaParceiros();
        
        // Carregar comparação se for mês atual
        if (!mes && !ano) {
            await carregarComparacao();
        }
        
        mostrarLoading(false);
    } catch (erro) {
        console.error('Erro ao carregar dashboard:', erro);
        mostrarErro(`Erro ao carregar dados do dashboard: ${erro.message}`);
        mostrarLoading(false);
    }
}

// Carregar lista de parceiros para filtros
async function carregarListaParceiros() {
    try {
        const response = await fetch('/api/parceiros');
        if (!response.ok) return;
        
        const parceiros = await response.json();
        
        // Preencher filtro do gráfico
        const selectGrafico = document.getElementById('filtro-parceiro-grafico');
        if (selectGrafico) {
            selectGrafico.innerHTML = '<option value="">Todos os Parceiros</option>';
            parceiros.forEach(p => {
                const option = document.createElement('option');
                option.value = p.id;
                option.textContent = p.nome;
                if (p.id == parceiroSelecionadoGrafico) {
                    option.selected = true;
                }
                selectGrafico.appendChild(option);
            });
        }
        
        // Preencher filtro da tabela
        const selectTabela = document.getElementById('filtro-parceiro-tabela');
        if (selectTabela) {
            selectTabela.innerHTML = '<option value="">Todos os Parceiros</option>';
            parceiros.forEach(p => {
                const option = document.createElement('option');
                option.value = p.id;
                option.textContent = p.nome;
                if (p.id == parceiroSelecionadoTabela) {
                    option.selected = true;
                }
                selectTabela.appendChild(option);
            });
        }
    } catch (erro) {
        console.error('Erro ao carregar parceiros:', erro);
    }
}

// Filtrar gráfico por parceiro
function filtrarParceiroGrafico() {
    const select = document.getElementById('filtro-parceiro-grafico');
    parceiroSelecionadoGrafico = select ? select.value : '';
    renderizarGraficoParceiros();
}

// Filtrar tabela por parceiro
function filtrarParceiroTabela() {
    const select = document.getElementById('filtro-parceiro-tabela');
    parceiroSelecionadoTabela = select ? select.value : '';
    renderizarTabelaParceiros();
}

// Renderizar KPIs
function renderizarKPIs() {
    const { meta, faturamento_atual, percentual_meta, falta_para_meta, valor_agendado_semana, projecao_fim_mes } = dashboardData;
    
    // Meta circular
    const percentual = Math.min(100, Math.max(0, percentual_meta));
    const circunferencia = 2 * Math.PI * 54; // raio = 54
    const offset = circunferencia - (percentual / 100) * circunferencia;
    
    document.getElementById('circle-progress').setAttribute('stroke-dashoffset', offset);
    document.getElementById('percentual-text').textContent = `${percentual.toFixed(1)}%`;
    document.getElementById('meta-valor').textContent = formatarMoeda(faturamento_atual);
    document.getElementById('meta-total').textContent = `de ${formatarMoeda(meta.valor_meta)}`;
    
    // Status badge
    const statusBadge = document.getElementById('status-badge');
    const statusIcon = meta.status === 'atingida' ? '<img src="/static/icons/check_icon.png" alt="Atingida" class="status-icon">' : 
                       meta.status === 'nao_atingida' ? '<img src="/static/icons/alert_icon.png" alt="Não Atingida" class="status-icon">' : 
                       '<img src="/static/icons/refresh_icon.png" alt="Em Andamento" class="status-icon">';
    statusBadge.innerHTML = meta.status === 'atingida' ? statusIcon + ' Atingida' : 
                              meta.status === 'nao_atingida' ? statusIcon + ' Não Atingida' : 
                              statusIcon + ' Em Andamento';
    statusBadge.className = `status-badge ${meta.status === 'atingida' ? 'sucesso' : 
                                                      meta.status === 'nao_atingida' ? 'erro' : 
                                                      'atencao'}`;
    
    // Outros KPIs
    document.getElementById('kpi-faturamento').textContent = formatarMoeda(faturamento_atual);
    document.getElementById('kpi-faturamento-desc').textContent = `Este mês (${percentual.toFixed(1)}% da meta)`;
    
    document.getElementById('kpi-falta').textContent = formatarMoeda(falta_para_meta);
    document.getElementById('kpi-falta-desc').textContent = falta_para_meta > 0 ? 'Restante' : 'Meta atingida!';
    
    document.getElementById('kpi-agendado').textContent = formatarMoeda(valor_agendado_semana);
    
    document.getElementById('kpi-projecao').textContent = formatarMoeda(projecao_fim_mes);
    const projecaoPercentual = (projecao_fim_mes / meta.valor_meta * 100).toFixed(1);
    document.getElementById('kpi-projecao-desc').textContent = `${projecaoPercentual}% da meta`;
    
    // Novos KPIs
    const metricas = dashboardData.metricas_financeiras || {};
    document.getElementById('kpi-lucro-medio').textContent = formatarMoeda(metricas.lucro_medio_coleta || 0);
    document.getElementById('kpi-rentabilidade').textContent = `${(metricas.rentabilidade || 0).toFixed(1)}%`;
    document.getElementById('kpi-rentabilidade-desc').textContent = `Margem de ${(metricas.margem_lucro || 0).toFixed(1)}%`;
    document.getElementById('kpi-ticket-medio').textContent = formatarMoeda(metricas.ticket_medio || 0);
}

// Renderizar resumo financeiro
function renderizarResumoFinanceiro() {
    const metricas = dashboardData.metricas_financeiras || {};
    
    document.getElementById('resumo-receita').textContent = formatarMoeda(metricas.receita_total || 0);
    document.getElementById('resumo-custo').textContent = formatarMoeda(metricas.custo_total || 0);
    document.getElementById('resumo-lucro').textContent = formatarMoeda(metricas.lucro_total || 0);
    document.getElementById('resumo-margem').textContent = `${(metricas.margem_lucro || 0).toFixed(1)}%`;
    
    // Adicionar classes de cor baseado em valores
    const lucroEl = document.getElementById('resumo-lucro');
    const margemEl = document.getElementById('resumo-margem');
    
    if (metricas.lucro_total > 0) {
        lucroEl.classList.add('positivo');
        lucroEl.classList.remove('negativo');
    } else {
        lucroEl.classList.add('negativo');
        lucroEl.classList.remove('positivo');
    }
    
    if (metricas.margem_lucro > 20) {
        margemEl.classList.add('positivo');
    } else if (metricas.margem_lucro > 10) {
        margemEl.classList.add('atencao');
    } else {
        margemEl.classList.add('negativo');
    }
}

// Renderizar próximas coletas
function renderizarProximasColetas() {
    const { proximas_coletas } = dashboardData;
    const container = document.getElementById('proximas-coletas');
    
    if (!proximas_coletas || proximas_coletas.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #64748b; padding: 2rem;">Nenhuma coleta agendada</p>';
        return;
    }
    
    container.innerHTML = proximas_coletas.map(coleta => `
        <div class="coleta-item">
            <div class="coleta-info">
                <strong>${coleta.coletor?.localizacao || 'Coletor #' + coleta.coletor_id}</strong>
                <span class="coleta-data">${formatarDataCurta(coleta.data_hora)}</span>
            </div>
            <div class="coleta-valor">
                ${coleta.volume_estimado ? `~${coleta.volume_estimado.toFixed(1)}kg` : 'N/A'}
            </div>
        </div>
    `).join('');
}

// Renderizar clientes inativos
function renderizarClientesInativos() {
    const { clientes_inativos } = dashboardData;
    const container = document.getElementById('clientes-inativos');
    const badge = document.getElementById('badge-inativos');
    
    badge.textContent = clientes_inativos.quantidade;
    
    if (clientes_inativos.quantidade === 0) {
        container.innerHTML = '<p style="text-align: center; color: #64748b; padding: 2rem;">Nenhum cliente inativo</p>';
        return;
    }
    
    container.innerHTML = clientes_inativos.lista.map(cliente => `
        <div class="cliente-item">
            <div class="cliente-info">
                <strong>${cliente.localizacao || 'Cliente'}</strong>
                <span class="cliente-distancia">${cliente.distancia_sede?.toFixed(1) || '?'} km</span>
            </div>
            <button onclick="contatarCliente(${cliente.id})" class="btn btn-xs btn-primario">
                <img src="/static/icons/telephone_icon.png" alt="Contatar" class="btn-icon-small"> Contatar
            </button>
        </div>
    `).join('');
}

// Renderizar sugestões
function renderizarSugestoes() {
    const { sugestoes } = dashboardData;
    const container = document.getElementById('sugestoes-container');
    
    if (!sugestoes || sugestoes.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #64748b; padding: 2rem;">Nenhuma sugestão disponível</p>';
        return;
    }
    
    container.innerHTML = sugestoes.map(sugestao => `
        <div class="sugestao-item">
            <div class="sugestao-tipo">${sugestao.tipo === 'coletas' ? '<img src="/static/icons/refresh_icon.png" alt="Coletas" class="sugestao-icon">' : sugestao.tipo === 'palestras' ? '<img src="/static/icons/people_icon.png" alt="Palestras" class="sugestao-icon">' : '<img src="/static/icons/sugestao_icon.png" alt="Outros" class="sugestao-icon">'}</div>
            <div class="sugestao-descricao">
                <strong>${sugestao.quantidade}x ${sugestao.tipo}</strong>
                <p>${sugestao.descricao}</p>
            </div>
        </div>
    `).join('');
}

// Renderizar alertas
function renderizarAlertas() {
    const { 
        percentual_meta, 
        clientes_inativos,
        dias_uteis_restantes,
        projecao_fim_mes,
        meta,
        metricas_financeiras
    } = dashboardData;
    
    const container = document.getElementById('alertas-container');
    const alertas = [];
    
    // Alerta: Meta muito longe
    if (percentual_meta < 30 && dias_uteis_restantes < 10) {
        alertas.push({
            tipo: 'erro',
            mensagem: `<img src="/static/icons/alert_icon.png" alt="Alerta" class="alert-icon-inline"> Apenas ${dias_uteis_restantes} dias úteis restantes e meta em ${percentual_meta.toFixed(0)}%!`,
            acao: 'Agendar urgente'
        });
    }
    
    // Alerta: Clientes inativos
    if (clientes_inativos.quantidade > 5) {
        alertas.push({
            tipo: 'atencao',
            mensagem: `${clientes_inativos.quantidade} clientes inativos há mais de 30 dias`,
            acao: 'Reativar clientes'
        });
    }
    
    // Alerta: Projeção baixa
    if (projecao_fim_mes < meta.valor_meta * 0.8) {
        alertas.push({
            tipo: 'atencao',
            mensagem: 'Projeção indica que não atingirá 80% da meta',
            acao: 'Acelerar vendas'
        });
    }
    
    // Alerta: Margem de lucro baixa
    if (metricas_financeiras && metricas_financeiras.margem_lucro < 10) {
        alertas.push({
            tipo: 'atencao',
            mensagem: `Margem de lucro baixa: ${metricas_financeiras.margem_lucro.toFixed(1)}%`,
            acao: 'Revisar custos'
        });
    }
    
    // Alerta: Custo por km alto
    if (metricas_financeiras && metricas_financeiras.custo_medio_km > 2.0) {
        alertas.push({
            tipo: 'atencao',
            mensagem: `Custo médio por KM alto: R$ ${metricas_financeiras.custo_medio_km.toFixed(2)}/km`,
            acao: 'Otimizar rotas'
        });
    }
    
    // Alerta: Eficiência baixa (pouco kg por km)
    if (metricas_financeiras && metricas_financeiras.eficiencia_kg_km < 1.0) {
        alertas.push({
            tipo: 'atencao',
            mensagem: `Eficiência de rotas baixa: ${metricas_financeiras.eficiencia_kg_km.toFixed(2)} kg/km`,
            acao: 'Otimizar coletas'
        });
    }
    
    // Alerta: Tudo OK
    if (alertas.length === 0 && percentual_meta > 70) {
        alertas.push({
            tipo: 'sucesso',
            mensagem: '<img src="/static/icons/check_icon.png" alt="Sucesso" class="alert-icon-inline"> Ótimo ritmo! Continue assim!',
            acao: null
        });
    }
    
    if (alertas.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #64748b; padding: 2rem;">Nenhum alerta</p>';
        return;
    }
    
    container.innerHTML = alertas.map(alerta => `
        <div class="alerta alerta-${alerta.tipo}">
            <p>${alerta.mensagem}</p>
            ${alerta.acao ? `<button class="btn btn-xs">${alerta.acao}</button>` : ''}
        </div>
    `).join('');
}

// Renderizar gráfico de lucro por parceiro
function renderizarGraficoParceiros() {
    try {
        let lucroParceiros = dashboardData.lucro_por_parceiro || [];
        
        // Aplicar filtro de parceiro se selecionado
        if (parceiroSelecionadoGrafico) {
            const parceiroId = parseInt(parceiroSelecionadoGrafico);
            lucroParceiros = lucroParceiros.filter(p => {
                const pId = parseInt(p.parceiro_id);
                return pId === parceiroId;
            });
        }
        
        if (lucroParceiros.length === 0) {
            const ctx = document.getElementById('grafico-parceiros');
            if (ctx && graficoParceiros) {
                graficoParceiros.destroy();
                graficoParceiros = null;
            }
            return;
        }
        
        const ctx = document.getElementById('grafico-parceiros');
        if (!ctx) return;
        
        // Destruir gráfico anterior se existir
        if (graficoParceiros) {
            graficoParceiros.destroy();
        }
        
        const labels = lucroParceiros.map(p => p.parceiro || p.parceiro_nome || 'Sem nome');
        const lucros = lucroParceiros.map(p => p.lucro || p.lucro_total || 0);
        const receitas = lucroParceiros.map(p => p.receita || p.receita_total || 0);
        const custos = lucroParceiros.map(p => p.custo || p.custo_total || 0);
        
        graficoParceiros = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Receita',
                        data: receitas,
                        backgroundColor: 'rgba(34, 197, 94, 0.6)',
                        borderColor: '#22c55e',
                        borderWidth: 1
                    },
                    {
                        label: 'Custo',
                        data: custos,
                        backgroundColor: 'rgba(239, 68, 68, 0.6)',
                        borderColor: '#ef4444',
                        borderWidth: 1
                    },
                    {
                        label: 'Lucro',
                        data: lucros,
                        backgroundColor: 'rgba(59, 130, 246, 0.6)',
                        borderColor: '#3b82f6',
                        borderWidth: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.dataset.label}: ${formatarMoeda(context.parsed.y)}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => `R$ ${(value/1000).toFixed(0)}k`
                        }
                    }
                }
            }
        });
    } catch (erro) {
        console.error('Erro ao renderizar gráfico de parceiros:', erro);
    }
}

// Renderizar tabela de parceiros
function renderizarTabelaParceiros() {
    let analise = dashboardData.analise_parceiros || [];
    
    // Aplicar filtro de parceiro se selecionado
    if (parceiroSelecionadoTabela) {
        const parceiroId = parseInt(parceiroSelecionadoTabela);
        analise = analise.filter(item => {
            const itemId = parseInt(item.parceiro_id);
            return itemId === parceiroId;
        });
    }
    
    const tbody = document.getElementById('tbody-parceiros');
    
    if (!tbody) return;
    
    if (analise.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #64748b; padding: 2rem;">Nenhum dado disponível para o período selecionado</td></tr>';
        return;
    }
    
    tbody.innerHTML = analise.map(item => `
        <tr>
            <td><strong>${item.parceiro_nome}</strong></td>
            <td>${item.num_coletas}</td>
            <td>${item.volume_total.toFixed(1)} kg</td>
            <td>${formatarMoeda(item.receita_total)}</td>
            <td>${formatarMoeda(item.custo_total)}</td>
            <td class="${item.lucro_total >= 0 ? 'positivo' : 'negativo'}">
                <strong>${formatarMoeda(item.lucro_total)}</strong>
            </td>
            <td>${item.margem_lucro.toFixed(1)}%</td>
        </tr>
    `).join('');
}

// Carregar comparação com mês anterior
async function carregarComparacao() {
    try {
        const response = await fetch('/api/comercial/comparar');
        if (!response.ok) return;
        
        const comparacao = await response.json();
        renderizarComparacao(comparacao);
    } catch (erro) {
        console.error('Erro ao carregar comparação:', erro);
    }
}

// Renderizar comparação
function renderizarComparacao(comparacao) {
    const container = document.getElementById('comparacao-container');
    const card = document.getElementById('card-comparacao');
    
    if (!container || !card) return;
    
    const { mes_atual, mes_anterior, variacoes } = comparacao;
    
    if (!mes_anterior.metricas.total_coletas) {
        card.style.display = 'none';
        return;
    }
    
    card.style.display = 'block';
    
    const formatarVariacao = (valor) => {
        const sinal = valor >= 0 ? '+' : '';
        const classe = valor >= 0 ? 'positivo' : 'negativo';
        return `<span class="${classe}">${sinal}${valor.toFixed(1)}%</span>`;
    };
    
    container.innerHTML = `
        <div class="comparacao-grid">
            <div class="comparacao-item">
                <span class="comparacao-label">Faturamento</span>
                <div class="comparacao-valores">
                    <span class="valor-atual">${formatarMoeda(mes_atual.faturamento)}</span>
                    <span class="variacao">${formatarVariacao(variacoes.faturamento)}</span>
                </div>
            </div>
            <div class="comparacao-item">
                <span class="comparacao-label">Lucro Total</span>
                <div class="comparacao-valores">
                    <span class="valor-atual">${formatarMoeda(mes_atual.metricas.lucro_total)}</span>
                    <span class="variacao">${formatarVariacao(variacoes.lucro_total)}</span>
                </div>
            </div>
            <div class="comparacao-item">
                <span class="comparacao-label">Número de Coletas</span>
                <div class="comparacao-valores">
                    <span class="valor-atual">${mes_atual.metricas.total_coletas}</span>
                    <span class="variacao">${formatarVariacao(variacoes.num_coletas)}</span>
                </div>
            </div>
            <div class="comparacao-item">
                <span class="comparacao-label">Volume Total</span>
                <div class="comparacao-valores">
                    <span class="valor-atual">${mes_atual.metricas.total_volume.toFixed(1)} kg</span>
                    <span class="variacao">${formatarVariacao(variacoes.volume_total)}</span>
                </div>
            </div>
        </div>
    `;
}

// Alterar período
function alterarPeriodo() {
    const seletor = document.getElementById('seletor-periodo');
    const valor = seletor.value;
    
    const hoje = new Date();
    let mes = null;
    let ano = null;
    let meses = null;
    
    switch(valor) {
        case 'atual':
            mes = hoje.getMonth() + 1;
            ano = hoje.getFullYear();
            break;
        case 'anterior':
            if (hoje.getMonth() === 0) {
                mes = 12;
                ano = hoje.getFullYear() - 1;
            } else {
                mes = hoje.getMonth();
                ano = hoje.getFullYear();
            }
            break;
        case 'ultimos3':
            // Agregar últimos 3 meses
            mes = hoje.getMonth() + 1;
            ano = hoje.getFullYear();
            meses = 3;
            break;
        case 'ultimos6':
            // Agregar últimos 6 meses
            mes = hoje.getMonth() + 1;
            ano = hoje.getFullYear();
            meses = 6;
            break;
        case 'todos':
            // Todos os períodos - passar flag todos=true
            mes = null;
            ano = null;
            meses = null;
            carregarDashboard(mes, ano, meses, true);
            return;  // Retornar aqui para não executar o carregarDashboard abaixo
    }
    
    // Limpar filtros de parceiro ao mudar período
    parceiroSelecionadoGrafico = '';
    parceiroSelecionadoTabela = '';
    
    carregarDashboard(mes, ano, meses, false);
}

// Renderizar gráfico de evolução
async function renderizarGraficoEvolucao(mes = null, ano = null) {
    try {
        // Se período específico, buscar histórico até aquele mês
        let url = '/api/comercial/meta/historico?limite=12';
        if (mes && ano) {
            // Buscar histórico até o mês selecionado
            url += `&mes=${mes}&ano=${ano}`;
        }
        
        const response = await fetch(url);
        if (!response.ok) return;
        
        const historico = await response.json();
        
        const ctx = document.getElementById('grafico-evolucao');
        
        // Destruir gráfico anterior se existir
        if (graficoEvolucao) {
            graficoEvolucao.destroy();
        }
        
        const labels = historico.reverse().map(m => `${getNomeMes(m.mes)}/${m.ano}`);
        const metas = historico.map(m => m.valor_meta);
        const realizados = historico.map(m => m.valor_realizado);
        
        graficoEvolucao = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Meta',
                        data: metas,
                        borderColor: '#94a3b8',
                        backgroundColor: 'rgba(148, 163, 184, 0.1)',
                        borderDash: [5, 5]
                    },
                    {
                        label: 'Realizado',
                        data: realizados,
                        borderColor: '#22c55e',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => `R$ ${(value/1000).toFixed(0)}k`
                        }
                    }
                }
            }
        });
    } catch (erro) {
        console.error('Erro ao renderizar gráfico:', erro);
    }
}

// Modal de configuração
function configurarMeta() {
    const { meta } = dashboardData;
    
    document.getElementById('valor-meta-input').value = meta.valor_meta;
    document.getElementById('observacoes-input').value = meta.observacoes || '';
    document.getElementById('modal-meta').style.display = 'flex';
}

function fecharModalMeta() {
    document.getElementById('modal-meta').style.display = 'none';
}

async function salvarMeta(event) {
    event.preventDefault();
    
    try {
        const formData = new FormData(event.target);
        const dados = {
            valor_meta: parseFloat(formData.get('valor_meta')),
            observacoes: formData.get('observacoes')
        };
        
        const response = await fetch('/api/comercial/meta', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        });
        
        if (!response.ok) throw new Error('Erro ao salvar meta');
        
        mostrarSucesso('Meta atualizada com sucesso!');
        fecharModalMeta();
        carregarDashboard();
    } catch (erro) {
        console.error('Erro:', erro);
        mostrarErro('Erro ao salvar meta');
    }
}

// Ações
function agendarColeta() {
    window.location.href = '/configuracoes#nova-coleta';
}

function contatarCliente(clienteId) {
    window.location.href = `/crm?cliente=${clienteId}`;
}

function verTodosInativos() {
    window.location.href = '/crm?filtro=inativos';
}

async function atualizarDados() {
    mostrarLoading(true);
    
    try {
        await fetch('/api/comercial/atualizar', { method: 'POST' });
        const seletor = document.getElementById('seletor-periodo');
        if (seletor && seletor.value === 'atual') {
            await carregarDashboard();
        } else {
            await carregarDashboard(periodoAtual.mes, periodoAtual.ano);
        }
        mostrarSucesso('Dados atualizados!');
    } catch (erro) {
        console.error('Erro:', erro);
        mostrarErro('Erro ao atualizar dados');
    }
    
    mostrarLoading(false);
}

// Utilitários
function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(valor || 0);
}

function formatarDataCurta(dataStr) {
    const data = new Date(dataStr);
    const dia = data.getDate().toString().padStart(2, '0');
    const mes = (data.getMonth() + 1).toString().padStart(2, '0');
    return `${dia}/${mes}`;
}

function getNomeMes(numero) {
    const meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 
                   'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
    return meses[numero - 1];
}

function mostrarLoading(mostrar) {
    const btn = document.getElementById('btn-atualizar-comercial');
    if (btn) {
        btn.disabled = mostrar;
        if (mostrar) {
            btn.innerHTML = '<img src="/static/icons/refresh_icon.png" alt="Carregando" class="btn-icon-small"> Carregando...';
        } else {
            btn.innerHTML = '<img src="/static/icons/refresh_icon.png" alt="Atualizar" class="btn-icon-small"> Atualizar';
        }
    }
}

function mostrarSucesso(mensagem) {
    // Implementar notificação de sucesso (pode usar toast ou alert)
    alert(mensagem);
}

function mostrarErro(mensagem) {
    // Implementar notificação de erro
    alert(mensagem);
}

