// Verificar se Chart.js carregou
if (typeof Chart === 'undefined') {
    console.error('Chart.js não foi carregado corretamente!');
}

// Variáveis globais para gráficos
let chartEvolucao = null;
let chartDistribuicao = null;
let chartHorarios = null;
let chartFinanceiro = null;

// Estado do gráfico de distribuição (orientação e ordenação)
let distribOrientacao = 'horizontal'; // 'vertical' ou 'horizontal' - padrão horizontal conforme foto
let distribOrdem = 'desc';          // 'asc' ou 'desc'

// Guarda os últimos dados usados para poder redesenhar o gráfico
let ultimoRelatorioDistribuicao = {
    coletasPorLixeira: [],
    lixeiras: []
};

// Variável global para armazenar dados do relatório atual
let dadosRelatorioAtual = null;

function processarDadosDistribuicao(coletasPorLixeira, lixeiras, ordem = 'desc') {
    // Agrupar por região (usando parte do nome da localização)
    const regioes = {};
    
    coletasPorLixeira.forEach(item => {
        const lixeira = lixeiras.find(l => l.id === item.lixeira_id);
        if (lixeira) {
            // Extrair região do nome (ex: "Asa Norte" de "Asa Norte - Bloco A")
            const regiao = lixeira.localizacao.split(' - ')[0] || 'Outros';
            if (!regioes[regiao]) {
                regioes[regiao] = 0;
            }
            regioes[regiao] += item.total_coletas;
        }
    });

    // Transforma em lista de { label, valor }
    let pares = Object.keys(regioes).map(regiao => ({
        label: regiao,
        valor: regioes[regiao]
    }));

    // Ordena crescente ou decrescente
    pares.sort((a, b) => {
        if (ordem === 'asc') {
            return a.valor - b.valor; // menor → maior
        }
        return b.valor - a.valor;     // maior → menor (padrão)
    });

    return {
        labels: pares.map(p => p.label),
        valores: pares.map(p => p.valor)
    };
}

// Função para carregar parceiros no dropdown
async function carregarParceirosFiltro() {
    try {
        const parceiros = await obterParceiros();
        const selectParceiro = document.getElementById('filtro-parceiro');
        if (selectParceiro && parceiros) {
            parceiros.forEach(parceiro => {
                const option = document.createElement('option');
                option.value = parceiro.id;
                option.textContent = parceiro.nome;
                selectParceiro.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Erro ao carregar parceiros para filtro:', error);
    }
}

// Função para inicializar a página
function inicializarPagina() {
    // Verificar se Chart.js está disponível
    if (typeof Chart === 'undefined') {
        console.error('Chart.js não foi carregado! Verifique a conexão com o CDN.');
        // Tentar novamente após 500ms
        setTimeout(inicializarPagina, 500);
        return;
    }
    
    // Carregar parceiros no filtro (não bloqueia o carregamento do relatório)
    carregarParceirosFiltro().catch(err => {
        console.warn('Erro ao carregar parceiros para filtro:', err);
    });
    
    // Configurar datas padrão para incluir os dados reais (março a novembro 2025)
    // Os dados reais estão entre 2025-03-06 e 2025-11-01
    const dataInicioEl = document.getElementById('data-inicio');
    const dataFimEl = document.getElementById('data-fim');
    
    if (dataInicioEl && dataFimEl) {
        // Se não houver valor, usar período dos dados reais (últimos 30 dias ou período completo)
        if (!dataInicioEl.value || !dataFimEl.value) {
            const hoje = new Date(); // Data atual
            const dataFimDados = new Date('2025-11-01'); // Última coleta real
            const dataInicioDados = new Date('2025-03-06'); // Primeira coleta real
            
            // Usar a data mais recente entre hoje e a última coleta
            const dataFim = hoje > dataFimDados ? hoje : dataFimDados;
            
            // Calcular início: 30 dias antes ou desde o início dos dados
            const inicio = new Date(dataFim);
            inicio.setDate(inicio.getDate() - 29); // 30 dias
            
            // Se o início calculado for antes da primeira coleta, usar a primeira coleta
            if (inicio < dataInicioDados) {
                dataInicioEl.value = dataInicioDados.toISOString().split('T')[0];
            } else {
                dataInicioEl.value = inicio.toISOString().split('T')[0];
            }
            
            dataFimEl.value = dataFim.toISOString().split('T')[0];
        }
    }
    
    // Botão aplicar filtro
    const btnAplicar = document.getElementById('btn-aplicar-filtro');
    if (btnAplicar) {
        btnAplicar.addEventListener('click', carregarRelatorio);
    }
    
    // Botão exportar coletas CSV
    const btnExportar = document.getElementById('btn-exportar-coletas');
    if (btnExportar) {
        btnExportar.addEventListener('click', exportarColetasCSV);
    }
    
    // Botão exportar PDF
    const btnExportarPDF = document.getElementById('btn-exportar-pdf');
    if (btnExportarPDF) {
        btnExportarPDF.addEventListener('click', exportarRelatorioPDF);
    }
    
    // Tabs de período
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            // Obter período selecionado
            const periodoStr = this.dataset.periodo;
            const periodo = periodoStr === 'todos' ? 'todos' : parseInt(periodoStr);
            
            // Atualizar campos de data
            const dataInicioEl = document.getElementById('data-inicio');
            const dataFimEl = document.getElementById('data-fim');
            
            if (dataInicioEl && dataFimEl) {
                const dataFimDados = new Date('2025-11-01'); // Última coleta real
                const dataInicioDados = new Date('2025-03-06'); // Primeira coleta real
                const hoje = new Date();
                
                // Determinar data fim: usar a mais recente entre hoje e última coleta
                const dataFimAtual = hoje > dataFimDados ? hoje : dataFimDados;
                
                // Lógica diferenciada para cada período:
                // - todos: TODOS os dados disponíveis (período completo desde o início)
                // - 7 dias: últimos 7 dias a partir da data fim
                // - 30 dias: últimos 30 dias a partir da data fim
                // - 90 dias: últimos 90 dias a partir da data fim
                if (periodo === 'todos') {
                    // Todos: mostrar TODOS os dados disponíveis (período completo desde o início)
                    dataInicioEl.value = dataInicioDados.toISOString().split('T')[0];
                    dataFimEl.value = dataFimAtual.toISOString().split('T')[0];
                } else {
                    // Calcular nova data início retrocedendo o período a partir da data fim
                    const novaDataInicio = new Date(dataFimAtual);
                    novaDataInicio.setDate(novaDataInicio.getDate() - periodo + 1); // +1 para incluir o dia atual
                    
                    if (periodo >= 90) {
                        // 90+ dias: se o período calculado vai antes do início, mostrar todos os dados
                        if (novaDataInicio < dataInicioDados) {
                            dataInicioEl.value = dataInicioDados.toISOString().split('T')[0];
                            dataFimEl.value = dataFimAtual.toISOString().split('T')[0];
                        } else {
                            dataInicioEl.value = novaDataInicio.toISOString().split('T')[0];
                            dataFimEl.value = dataFimAtual.toISOString().split('T')[0];
                        }
                    } else if (periodo === 30) {
                        // 30 dias: mostrar exatamente 30 dias a partir da data fim
                        // Se o período calculado vai antes do início dos dados, limitar ao início
                        if (novaDataInicio < dataInicioDados) {
                            // Período maior que dados disponíveis: mostrar todos os dados disponíveis
                            dataInicioEl.value = dataInicioDados.toISOString().split('T')[0];
                            dataFimEl.value = dataFimAtual.toISOString().split('T')[0];
                        } else {
                            // Período normal de 30 dias dentro dos dados disponíveis
                            dataInicioEl.value = novaDataInicio.toISOString().split('T')[0];
                            dataFimEl.value = dataFimAtual.toISOString().split('T')[0];
                        }
                    } else {
                        // 7 dias ou outros períodos menores: calcular normalmente
                        if (novaDataInicio < dataInicioDados) {
                            dataInicioEl.value = dataInicioDados.toISOString().split('T')[0];
                        } else {
                            dataInicioEl.value = novaDataInicio.toISOString().split('T')[0];
                        }
                        dataFimEl.value = dataFimAtual.toISOString().split('T')[0];
                    }
                }
                
                console.log(`Período ${periodo === 'todos' ? 'Todos' : periodo + ' dias'}: ${dataInicioEl.value} até ${dataFimEl.value}`);
                
                // Recarregar relatório com novas datas
                carregarRelatorio();
            }
        });
    });
    
    // Carregar relatório inicial após um pequeno delay para garantir que as datas foram configuradas
    setTimeout(() => {
        carregarRelatorio();
    }, 100);
}

// Aguardar DOM estar pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarPagina);
} else {
    // DOM já está pronto
    inicializarPagina();
}

// Função para processar dados para gráfico de evolução
function processarDadosEvolucao(coletas) {
    // Agrupar coletas por data
    const coletasPorData = {};
    
    coletas.forEach(coleta => {
        const data = coleta.data_hora ? new Date(coleta.data_hora) : null;
        if (!data) return;
        const dataStr = data.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
        
        if (!coletasPorData[dataStr]) {
            coletasPorData[dataStr] = 0;
        }
        coletasPorData[dataStr]++;
    });
    
    // Ordenar por data
    const datas = Object.keys(coletasPorData).sort((a, b) => {
        const [diaA, mesA] = a.split('/');
        const [diaB, mesB] = b.split('/');
        return new Date(2024, mesA - 1, diaA) - new Date(2024, mesB - 1, diaB);
    });
    
    return {
        labels: datas,
        valores: datas.map(d => coletasPorData[d])
    };
}

// Função para processar dados de distribuição por região
function processarDadosDistribuicaoRegiao(coletasPorLixeira, lixeiras) {
    // Agrupar por região (usando parte do nome da localização)
    const regioes = {};
    
    coletasPorLixeira.forEach(item => {
        const lixeira = lixeiras.find(l => l.id === item.lixeira_id);
        if (lixeira) {
            // Extrair região do nome (ex: "Asa Norte" de "Asa Norte - Bloco A")
            const regiao = lixeira.localizacao.split(' - ')[0] || 'Outros';
            if (!regioes[regiao]) {
                regioes[regiao] = 0;
            }
            regioes[regiao] += item.total_coletas;
        }
    });
    
    return {
        labels: Object.keys(regioes),
        valores: Object.values(regioes)
    };
}

// Função para processar dados de horários de pico
function processarDadosHorarios(coletas) {
    const horarios = Array(24).fill(0);
    
    coletas.forEach(coleta => {
        const data = coleta.data_hora ? new Date(coleta.data_hora) : null;
        if (!data) return;
        const hora = data.getHours();
        horarios[hora]++;
    });
    
    return {
        labels: Array.from({length: 24}, (_, i) => `${i.toString().padStart(2, '0')}h`),
        valores: horarios
    };
}

// Função para criar/atualizar gráfico de evolução
function atualizarGraficoEvolucao(dados) {
    const ctx = document.getElementById('chart-evolucao');
    
    if (!ctx) {
        console.error('Canvas chart-evolucao não encontrado');
        return;
    }
    
    if (chartEvolucao) {
        chartEvolucao.destroy();
    }
    
    const processed = processarDadosEvolucao(dados.detalhes || []);
    
    // Se não houver dados, mostrar gráfico vazio
    if (processed.labels.length === 0) {
        processed.labels = ['Sem dados'];
        processed.valores = [0];
    }
    
    try {
        chartEvolucao = new Chart(ctx, {
            type: 'line',
            data: {
                labels: processed.labels,
                datasets: [{
                    label: 'Coletas',
                    data: processed.valores,
                    borderColor: '#5DB5A4',
                    backgroundColor: 'rgba(93, 181, 164, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: processed.labels.length > 1
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Erro ao criar gráfico de evolução:', error);
    }
}

// Função para criar/atualizar gráfico de distribuição
function atualizarGraficoDistribuicao(coletasPorLixeira, lixeiras) {
    const ctx = document.getElementById('chart-distribuicao');
    
    if (!ctx) {
        // Elemento não encontrado, mas não é erro crítico - pode não estar na página
        return;
    }
    
    if (chartDistribuicao) {
        chartDistribuicao.destroy();
    }

    // Guarda os dados pra reutilizar quando mudar orientação/ordem
    ultimoRelatorioDistribuicao = {
        coletasPorLixeira: coletasPorLixeira || [],
        lixeiras: lixeiras || []
    };
    
    const processed = processarDadosDistribuicao(
        ultimoRelatorioDistribuicao.coletasPorLixeira,
        ultimoRelatorioDistribuicao.lixeiras,
        distribOrdem // usa o estado global de ordenação
    );
    
    // Se não houver dados, mostra um gráfico "vazio"
    if (processed.labels.length === 0) {
        processed.labels = ['Sem dados'];
        processed.valores = [0];
    }
    
    try {
        chartDistribuicao = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: processed.labels,
                datasets: [{
                    label: 'Coletas por Região',
                    data: processed.valores,
                    backgroundColor: [
                        '#5DB5A4',
                        '#3498db',
                        '#f39c12',
                        '#e74c3c',
                        '#9b59b6',
                        '#1abc9c',
                        '#34495e'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: distribOrientacao === 'horizontal' ? 'y' : 'x',
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.formattedValue} coletas`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Erro ao criar gráfico de distribuição:', error);
    }
}

// Função para processar dados financeiros
function processarDadosFinanceiros(coletas) {
    const dadosPorData = {};
    
    coletas.forEach(coleta => {
        const data = coleta.data_hora ? new Date(coleta.data_hora) : null;
        if (!data) return;
        const dataStr = data.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
        
        if (!dadosPorData[dataStr]) {
            dadosPorData[dataStr] = {
                lucro: 0,
                custo: 0
            };
        }
        
        const volume = coleta.volume_estimado || 0;
        const lucroPorKg = coleta.lucro_por_kg || 0;
        const km = coleta.km_percorrido || 0;
        const precoCombustivel = coleta.preco_combustivel || 0;
        
        // Cálculo correto do custo: (KM / consumo_km_por_litro) * preco_combustivel
        // Consumo padrão: 4 km/L (deve corresponder ao backend)
        const CONSUMO_KM_POR_LITRO = 4.0;
        const custoCombustivel = (km / CONSUMO_KM_POR_LITRO) * precoCombustivel;
        
        dadosPorData[dataStr].lucro += volume * lucroPorKg;
        dadosPorData[dataStr].custo += custoCombustivel;
    });
    
    // Ordenar por data
    const datas = Object.keys(dadosPorData).sort((a, b) => {
        const [diaA, mesA] = a.split('/');
        const [diaB, mesB] = b.split('/');
        return new Date(2024, mesA - 1, diaA) - new Date(2024, mesB - 1, diaB);
    });
    
    return {
        labels: datas,
        lucro: datas.map(d => dadosPorData[d].lucro),
        custo: datas.map(d => dadosPorData[d].custo),
        lucroLiquido: datas.map(d => dadosPorData[d].lucro - dadosPorData[d].custo)
    };
}

// Função para criar/atualizar gráfico financeiro
function atualizarGraficoFinanceiro(coletas) {
    const ctx = document.getElementById('chart-financeiro');
    
    if (!ctx) {
        // Elemento não encontrado, mas não é erro crítico - pode não estar na página
        return;
    }
    
    if (chartFinanceiro) {
        chartFinanceiro.destroy();
    }
    
    const processed = processarDadosFinanceiros(coletas || []);
    
    // Se não houver dados, mostrar gráfico vazio
    if (processed.labels.length === 0) {
        processed.labels = ['Sem dados'];
        processed.lucro = [0];
        processed.custo = [0];
        processed.lucroLiquido = [0];
    }
    
    try {
        chartFinanceiro = new Chart(ctx, {
            type: 'line',
            data: {
                labels: processed.labels,
                datasets: [
                    {
                        label: 'Lucro Bruto',
                        data: processed.lucro,
                        borderColor: '#27ae60',
                        backgroundColor: 'rgba(39, 174, 96, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Custo Combustível',
                        data: processed.custo,
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Lucro Líquido',
                        data: processed.lucroLiquido,
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        tension: 0.4,
                        fill: true,
                        borderDash: [5, 5]
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.dataset.label}: R$ ${context.parsed.y.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return 'R$ ' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Erro ao criar gráfico financeiro:', error);
    }
}

// Função para criar/atualizar gráfico de horários
function atualizarGraficoHorarios(coletas) {
    const ctx = document.getElementById('chart-horarios');
    
    if (!ctx) {
        // Elemento não encontrado, mas não é erro crítico - pode não estar na página
        return;
    }
    
    if (chartHorarios) {
        chartHorarios.destroy();
    }
    
    const processed = processarDadosHorarios(coletas || []);
    
    try {
        chartHorarios = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: processed.labels,
                datasets: [{
                    label: 'Coletas',
                    data: processed.valores,
                    backgroundColor: '#5DB5A4',
                    borderColor: '#4A9B8E',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    },
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            font: {
                                size: 8
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Erro ao criar gráfico de horários:', error);
    }
}

async function carregarRelatorio() {
    try {
        const dataInicio = document.getElementById('data-inicio').value;
        const dataFim = document.getElementById('data-fim').value;
        const parceiroId = document.getElementById('filtro-parceiro').value || null;
        const tipoOperacao = document.getElementById('filtro-tipo-operacao').value || null;
        
        // Debug: verificar filtros sendo enviados
        console.log('Carregando relatório:', { dataInicio, dataFim, parceiroId, tipoOperacao });
        
        const relatorio = await obterRelatorios(dataInicio, dataFim, parceiroId, tipoOperacao);
        
        // Armazenar dados para exportação
        dadosRelatorioAtual = relatorio;
        
        // Debug: verificar quantas coletas foram retornadas
        console.log('Coletas retornadas:', relatorio.detalhes.length);
        
        // Carregar lixeiras para gráfico de distribuição
        const lixeiras = await obterTodasLixeiras();
        
        // Atualizar KPIs (usando os novos IDs)
        const kpiTotalColetas = document.getElementById('kpi-total-coletas');
        const kpiVolumeTotal = document.getElementById('kpi-volume-total');
        const kpiKmTotal = document.getElementById('kpi-km-total');
        const kpiLucroTotal = document.getElementById('kpi-lucro-total');
        const kpiLucroMedio = document.getElementById('kpi-lucro-medio');
        
        if (kpiTotalColetas) {
            kpiTotalColetas.textContent = relatorio.resumo.total_coletas || 0;
        }
        if (kpiVolumeTotal) {
            kpiVolumeTotal.textContent = relatorio.resumo.volume_total ? Math.round(relatorio.resumo.volume_total) + 'KG' : '0KG';
        }
        if (kpiKmTotal) {
            kpiKmTotal.textContent = relatorio.resumo.km_total ? Math.round(relatorio.resumo.km_total * 10) / 10 + 'km' : '0km';
        }
        if (kpiLucroTotal) {
            kpiLucroTotal.textContent = relatorio.resumo.lucro_total ? 'R$ ' + relatorio.resumo.lucro_total.toFixed(2) : 'R$ 0';
        }
        if (kpiLucroMedio) {
            kpiLucroMedio.textContent = relatorio.resumo.lucro_medio_por_coleta ? 'R$ ' + relatorio.resumo.lucro_medio_por_coleta.toFixed(2) : 'R$ 0';
        }
        
        // Sempre atualizar gráficos com os dados filtrados
        atualizarGraficoEvolucao(relatorio);
        atualizarGraficoHorarios(relatorio.detalhes || []);
        atualizarGraficoFinanceiro(relatorio.detalhes || []);
        
        // Gráfico de distribuição só se houver coletas por lixeira
        if (relatorio.resumo && relatorio.resumo.coletas_por_lixeira) {
            atualizarGraficoDistribuicao(relatorio.resumo.coletas_por_lixeira, lixeiras);
        } else {
            atualizarGraficoDistribuicao([], lixeiras);
        }
        
        // Atualizar tabela
        const tbody = document.getElementById('relatorio-tbody');
        if (relatorio.detalhes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">Nenhuma coleta no período</td></tr>';
        } else {
            tbody.innerHTML = relatorio.detalhes.map(coleta => {
                const data = coleta.data_hora ? new Date(coleta.data_hora) : null;
                const lixeiraNome = coleta.lixeira ? coleta.lixeira.localizacao : `Lixeira ${coleta.lixeira_id}`;
                const volume = coleta.volume_estimado ? Math.round(coleta.volume_estimado) : 0;
                const km = coleta.km_percorrido ? Math.round(coleta.km_percorrido * 10) / 10 : 'N/A';
                const parceiro = coleta.parceiro ? coleta.parceiro.nome : 'N/A';
                const tipoOperacao = coleta.tipo_operacao || 'N/A';
                const lucro = coleta.lucro_por_kg ? `R$ ${coleta.lucro_por_kg.toFixed(2)}` : 'N/A';
                
                return `
                    <tr>
                        <td>${data ? data.toLocaleString('pt-BR') : 'N/A'}</td>
                        <td>#L${String(coleta.lixeira_id).padStart(3, '0')}</td>
                        <td>${lixeiraNome}</td>
                        <td>${volume}KG</td>
                        <td>${km}${typeof km === 'number' ? 'km' : ''}</td>
                        <td>${parceiro}</td>
                        <td>${tipoOperacao}</td>
                        <td>${lucro}</td>
                    </tr>
                `;
            }).join('');
        }
        
        // Atualizar top lixeiras
        const topList = document.getElementById('top-lixeiras');
        if (topList) {
            if (relatorio.resumo.coletas_por_lixeira && relatorio.resumo.coletas_por_lixeira.length > 0) {
                const top = relatorio.resumo.coletas_por_lixeira
                    .sort((a, b) => b.total_coletas - a.total_coletas)
                    .slice(0, 5);
                
                topList.innerHTML = top.map(item => {
                    const lixeira = lixeiras.find(l => l.id === item.lixeira_id);
                    const nome = lixeira ? lixeira.localizacao : `Lixeira ${item.lixeira_id}`;
                    return `
                        <div class="top-item">
                            <span class="top-name">#L${String(item.lixeira_id).padStart(3, '0')} - ${nome}</span>
                            <span class="top-value">${item.total_coletas} coletas</span>
                        </div>
                    `;
                }).join('');
            } else {
                topList.innerHTML = '<p style="text-align: center; color: #7f8c8d; font-size: 12px;">Nenhum dado disponível</p>';
            }
        }
        
        // Atualizar resumo executivo
        const resumoDesempenho = document.getElementById('resumo-desempenho');
        const resumoAtencao = document.getElementById('resumo-atencao');
        const resumoRecomendacoes = document.getElementById('resumo-recomendacoes');
        
        if (resumoDesempenho) {
            const volumeTotal = Math.round(relatorio.resumo.volume_total || 0);
            const lucroTotal = relatorio.resumo.lucro_total || 0;
            const custoCombustivel = relatorio.resumo.custo_combustivel_total || 0;
            const lucroLiquido = lucroTotal - custoCombustivel;
            
            resumoDesempenho.textContent = 
                `${relatorio.resumo.total_coletas} coletas realizadas, totalizando ${volumeTotal}KG coletados. Lucro bruto de R$ ${lucroTotal.toFixed(2)} com custo de combustível de R$ ${custoCombustivel.toFixed(2)}, resultando em lucro líquido de R$ ${lucroLiquido.toFixed(2)} no período selecionado.`;
        }
        
        if (resumoAtencao) {
            // Pontos de atenção
            const lixeirasComProblemas = relatorio.resumo.coletas_por_lixeira 
                ? relatorio.resumo.coletas_por_lixeira.filter(l => l.total_coletas > 10).length 
                : 0;
            
            if (lixeirasComProblemas > 0) {
                resumoAtencao.textContent = 
                    `${lixeirasComProblemas} lixeira(s) com alto número de coletas no período. Verifique necessidade de otimização de rotas.`;
            } else {
                resumoAtencao.textContent = 
                    'Nenhum ponto de atenção crítico no período selecionado.';
            }
        }
        
        if (resumoRecomendacoes) {
            // Recomendações
            if (relatorio.resumo.total_coletas > 50) {
                resumoRecomendacoes.textContent = 
                    'Aumentar frequência nas lixeiras críticas. Implementar coletas preventivas nos horários de pico.';
            } else if (relatorio.resumo.total_coletas > 0) {
                resumoRecomendacoes.textContent = 
                    'Monitorar padrões de coleta para identificar horários de pico e otimizar rotas.';
            } else {
                resumoRecomendacoes.textContent = 
                    'Selecione um período com dados para gerar recomendações.';
            }
        }
        
    } catch (error) {
        console.error('Erro ao carregar relatório:', error);
        alert('Erro ao carregar relatório.');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const btnVert = document.getElementById('btn-orientacao-vertical');
    const btnHor  = document.getElementById('btn-orientacao-horizontal');
    const btnAsc  = document.getElementById('btn-ordem-asc');
    const btnDesc = document.getElementById('btn-ordem-desc');

    function atualizarBotoesOrientacao() {
        if (!btnVert || !btnHor) return;
        btnVert.classList.toggle('active', distribOrientacao === 'vertical');
        btnHor.classList.toggle('active', distribOrientacao === 'horizontal');
    }

    function atualizarBotoesOrdem() {
        if (!btnAsc || !btnDesc) return;
        btnAsc.classList.toggle('active', distribOrdem === 'asc');
        btnDesc.classList.toggle('active', distribOrdem === 'desc');
    }

    function redesenharGraficoDistribuicaoSePossivel() {
        if (ultimoRelatorioDistribuicao.lixeiras.length > 0 ||
            ultimoRelatorioDistribuicao.coletasPorLixeira.length > 0) {
            atualizarGraficoDistribuicao(
                ultimoRelatorioDistribuicao.coletasPorLixeira,
                ultimoRelatorioDistribuicao.lixeiras
            );
        }
    }

    if (btnVert && btnHor) {
        btnVert.addEventListener('click', function () {
            distribOrientacao = 'vertical';
            atualizarBotoesOrientacao();
            redesenharGraficoDistribuicaoSePossivel();
        });

        btnHor.addEventListener('click', function () {
            distribOrientacao = 'horizontal';
            atualizarBotoesOrientacao();
            redesenharGraficoDistribuicaoSePossivel();
        });
    }

    if (btnAsc && btnDesc) {
        btnAsc.addEventListener('click', function () {
            distribOrdem = 'asc';
            atualizarBotoesOrdem();
            redesenharGraficoDistribuicaoSePossivel();
        });

        btnDesc.addEventListener('click', function () {
            distribOrdem = 'desc';
            atualizarBotoesOrdem();
            redesenharGraficoDistribuicaoSePossivel();
        });
    }

    // Deixa os botões marcados de acordo com o estado inicial (horizontal por padrão)
    atualizarBotoesOrientacao();
    atualizarBotoesOrdem();
});

// Função para exportar coletas em CSV
function exportarColetasCSV() {
    if (!dadosRelatorioAtual || !dadosRelatorioAtual.detalhes || dadosRelatorioAtual.detalhes.length === 0) {
        alert('Nenhuma coleta disponível para exportar.');
        return;
    }
    
    try {
        const coletas = dadosRelatorioAtual.detalhes;
        
        // Preparar dados para CSV
        const csvRows = [];
        
        // Cabeçalhos
        const headers = [
            'ID',
            'Data/Hora',
            'Lixeira ID',
            'Localização',
            'Volume (KG)',
            'KM Percorrido',
            'Tipo de Operação',
            'Parceiro',
            'Tipo Coletor',
            'Preço Combustível (R$/L)',
            'Lucro por KG (R$)',
            'Lucro Total (R$)',
            'Custo Combustível (R$)',
            'Emissão MTR'
        ];
        csvRows.push(headers.join(','));
        
        // Dados
        coletas.forEach(coleta => {
            const data = coleta.data_hora ? new Date(coleta.data_hora) : null;
            const dataFormatada = data ? data.toLocaleString('pt-BR') : 'N/A';
            const lixeiraNome = coleta.lixeira ? coleta.lixeira.localizacao : 'N/A';
            const parceiroNome = coleta.parceiro ? coleta.parceiro.nome : 'N/A';
            const tipoColetorNome = coleta.tipo_coletor ? coleta.tipo_coletor.nome : 'N/A';
            const volume = coleta.volume_estimado || 0;
            const km = coleta.km_percorrido || 0;
            const precoCombustivel = coleta.preco_combustivel || 0;
            const lucroPorKg = coleta.lucro_por_kg || 0;
            const lucroTotal = volume * lucroPorKg;
            // Cálculo correto do custo: (KM / consumo_km_por_litro) * preco_combustivel
            const CONSUMO_KM_POR_LITRO = 4.0;
            const custoCombustivel = (km / CONSUMO_KM_POR_LITRO) * precoCombustivel;
            const emissaoMTR = coleta.emissao_mtr ? 'SIM' : 'NÃO';
            
            const row = [
                coleta.id || '',
                dataFormatada,
                coleta.lixeira_id || '',
                `"${lixeiraNome}"`,
                volume.toFixed(2),
                km.toFixed(1),
                coleta.tipo_operacao || '',
                `"${parceiroNome}"`,
                `"${tipoColetorNome}"`,
                precoCombustivel.toFixed(2),
                lucroPorKg.toFixed(2),
                lucroTotal.toFixed(2),
                custoCombustivel.toFixed(2),
                emissaoMTR
            ];
            
            csvRows.push(row.join(','));
        });
        
        // Criar arquivo CSV
        const csvContent = csvRows.join('\n');
        const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        // Nome do arquivo com data
        const dataAtual = new Date().toISOString().split('T')[0];
        link.setAttribute('href', url);
        link.setAttribute('download', `coletas_${dataAtual}.csv`);
        link.style.visibility = 'hidden';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
    } catch (error) {
        console.error('Erro ao exportar CSV:', error);
        alert('Erro ao exportar CSV. Tente novamente.');
    }
}

// Função para exportar relatório em PDF
function exportarRelatorioPDF() {
    try {
        // Obter filtros atuais
        const dataInicio = document.getElementById('data-inicio')?.value || '';
        const dataFim = document.getElementById('data-fim')?.value || '';
        const parceiroId = document.getElementById('filtro-parceiro')?.value || '';
        const tipoOperacao = document.getElementById('filtro-tipo-operacao')?.value || '';
        
        // Construir URL com parâmetros
        let url = '/api/relatorios/exportar-pdf?';
        const params = [];
        
        if (dataInicio) params.push(`data_inicio=${encodeURIComponent(dataInicio)}`);
        if (dataFim) params.push(`data_fim=${encodeURIComponent(dataFim)}`);
        if (parceiroId) params.push(`parceiro_id=${encodeURIComponent(parceiroId)}`);
        if (tipoOperacao) params.push(`tipo_operacao=${encodeURIComponent(tipoOperacao)}`);
        
        url += params.join('&');
        
        // Abrir em nova aba para download
        window.open(url, '_blank');
    } catch (error) {
        console.error('Erro ao exportar PDF:', error);
        alert('Erro ao exportar PDF. Tente novamente.');
    }
}
