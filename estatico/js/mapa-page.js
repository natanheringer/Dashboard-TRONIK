/*
JavaScript da Página de Mapa - Dashboard-TRONIK
===============================================
Gerencia a página dedicada de mapa.
Carrega coletores e atualiza o mapa.
*/

let todosColetoresMapa = [];
let mapaInicializado = false;

/**
 * Carrega todas as coletores e atualiza o mapa
 */
async function carregarColetoresNoMapa() {
    try {
        // Verificar se a função obterTodosColetores está disponível
        if (typeof obterTodosColetores !== 'function') {
            console.error('Função obterTodosColetores não encontrada. Verifique se api.js está carregado.');
            return;
        }

        const coletores = await obterTodosColetores();
        // Garantir que seja um array
        const coletoresArray = Array.isArray(coletores) ? coletores : [];
        todosColetoresMapa = coletoresArray;
        
        // Aplicar filtros
        const coletoresFiltrados = aplicarFiltrosMapa(coletoresArray);
        
        // Atualizar mapa
        if (typeof window.MapaTronik !== 'undefined' && window.MapaTronik.atualizarMarcadores) {
            window.MapaTronik.atualizarMarcadores(coletoresFiltrados);
        } else {
            console.warn('MapaTronik.atualizarMarcadores não disponível');
        }
    } catch (error) {
        console.error('Erro ao carregar coletores:', error);
    }
}

/**
 * Aplica filtros às coletores
 */
function aplicarFiltrosMapa(coletores) {
    const statusFiltro = document.getElementById('filter-status-mapa')?.value || '';
    const parceiroFiltro = document.getElementById('filter-parceiro-mapa')?.value || '';
    const buscaFiltro = document.getElementById('filter-busca-mapa')?.value.toLowerCase() || '';
    const distanciaFiltro = document.getElementById('filter-distancia-mapa')?.value || 'todas';
    const ordenarDistancia = document.getElementById('ordenar-distancia-mapa')?.value || '';

    let coletoresFiltrados = coletores.filter(coletor => {
        // Filtro de status
        if (statusFiltro) {
            const nivel = coletor.nivel_preenchimento || 0;
            const status = coletor.status || 'OK';
            
            if (statusFiltro === 'normal' && (nivel >= 80 || status !== 'OK')) return false;
            if (statusFiltro === 'atencao' && (nivel < 80 || nivel >= 95)) return false;
            if (statusFiltro === 'critico' && nivel < 95) return false;
            if (statusFiltro === 'manutencao' && status !== 'MANUTENCAO') return false;
        }

        // Filtro de parceiro
        if (parceiroFiltro) {
            const parceiroId = coletor.parceiro?.id || null;
            if (parceiroId !== parseInt(parceiroFiltro)) return false;
        }

        // Filtro de busca
        if (buscaFiltro) {
            const localizacao = (coletor.localizacao || '').toLowerCase();
            const id = `#L${String(coletor.id).padStart(3, '0')}`.toLowerCase();
            if (!localizacao.includes(buscaFiltro) && !id.includes(buscaFiltro)) {
                return false;
            }
        }

        return true;
    });

    // Aplicar filtro de distância (usando função do mapa.js)
    if (typeof filtrarPorDistancia === 'function') {
        coletoresFiltrados = filtrarPorDistancia(coletoresFiltrados, distanciaFiltro);
    }

    // Aplicar ordenação por distância
    if (ordenarDistancia && typeof ordenarPorDistancia === 'function') {
        const ordem = ordenarDistancia === 'proxima' ? 'asc' : 'desc';
        coletoresFiltrados = ordenarPorDistancia(coletoresFiltrados, ordem);
    }

    return coletoresFiltrados;
}

/**
 * Carrega parceiros no filtro
 */
async function carregarParceirosFiltro() {
    try {
        // Usar função da API se disponível, senão fazer requisição direta
        let parceiros;
        if (typeof obterParceiros === 'function') {
            parceiros = await obterParceiros();
        } else {
            const response = await fetch('/api/parceiros');
            if (!response.ok) throw new Error('Erro ao buscar parceiros');
            parceiros = await response.json();
        }

        const select = document.getElementById('filter-parceiro-mapa');
        
        if (!select) return;

        // Limpar opções existentes (exceto "Todos")
        select.innerHTML = '<option value="">Todos</option>';

        // Adicionar parceiros
        parceiros.forEach(parceiro => {
            const option = document.createElement('option');
            option.value = parceiro.id;
            option.textContent = parceiro.nome;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Erro ao carregar parceiros:', error);
    }
}

/**
 * Inicializa a página de mapa
 */
async function inicializarPaginaMapa() {
    // Verificar se estamos na página de mapa
    const mapaContainer = document.getElementById('mapa-coletores');
    if (!mapaContainer) return;

    // Aguardar o carregamento do módulo MapaTronik
    let tentativas = 0;
    const maxTentativas = 10;
    
    while (typeof window.MapaTronik === 'undefined' && tentativas < maxTentativas) {
        await new Promise(resolve => setTimeout(resolve, 100));
        tentativas++;
    }

    // Verificar se Leaflet está disponível
    if (typeof L === 'undefined') {
        console.error('Leaflet não está carregado. Verifique se o CDN está incluído.');
        mapaContainer.innerHTML = '<div class="mapa-erro">Erro: Biblioteca Leaflet não encontrada. Verifique sua conexão com a internet.</div>';
        return;
    }

    // Inicializar mapa
    if (typeof window.MapaTronik !== 'undefined' && window.MapaTronik.inicializar) {
        try {
            // Remover indicador de carregamento
            const carregando = mapaContainer.querySelector('.mapa-carregando');
            if (carregando) {
                carregando.remove();
            }

            window.MapaTronik.inicializar('mapa-coletores', {
                lat: -15.7942,  // Brasília
                lon: -47.8822,
                zoom: 11
            });
            mapaInicializado = true;
        } catch (error) {
            console.error('Erro ao inicializar mapa:', error);
            mapaContainer.innerHTML = '<div class="mapa-erro">Erro ao carregar o mapa: ' + error.message + '<br>Recarregue a página.</div>';
            return;
        }
    } else {
        console.error('Módulo MapaTronik não encontrado. Verifique se mapa.js está carregado.');
        mapaContainer.innerHTML = '<div class="mapa-erro">Erro: Biblioteca de mapa não encontrada. Verifique se mapa.js está carregado corretamente.</div>';
        return;
    }

    // Aguardar um pouco para garantir que o mapa está renderizado
    await new Promise(resolve => setTimeout(resolve, 300));

    // Forçar redimensionamento do mapa após renderização
    if (mapaInicializado && window.MapaTronik && typeof L !== 'undefined') {
        setTimeout(() => {
            const mapaInstancia = window.MapaTronik.mapa || (window.mapa || null);
            if (mapaInstancia && typeof mapaInstancia.invalidateSize === 'function') {
                mapaInstancia.invalidateSize();
            }
        }, 100);
    }
    
    // Redimensionar mapa quando a janela for redimensionada
    window.addEventListener('resize', () => {
        if (mapaInicializado && window.MapaTronik) {
            const mapaInstancia = window.MapaTronik.mapa || (window.mapa || null);
            if (mapaInstancia && typeof mapaInstancia.invalidateSize === 'function') {
                setTimeout(() => mapaInstancia.invalidateSize(), 100);
            }
        }
    });

    // Carregar parceiros
    await carregarParceirosFiltro();

    // Carregar coletores
    await carregarColetoresNoMapa();

    // Event listeners
    const btnAjustarZoom = document.getElementById('btn-ajustar-zoom');
    if (btnAjustarZoom) {
        btnAjustarZoom.addEventListener('click', () => {
            if (typeof window.MapaTronik !== 'undefined' && window.MapaTronik.ajustarZoomMarcadores) {
                window.MapaTronik.ajustarZoomMarcadores();
            }
        });
    }

    const btnAtualizar = document.getElementById('btn-atualizar-mapa');
    if (btnAtualizar) {
        btnAtualizar.addEventListener('click', () => {
            carregarColetoresNoMapa();
        });
    }

    // Filtros
    const filterStatus = document.getElementById('filter-status-mapa');
    if (filterStatus) {
        filterStatus.addEventListener('change', () => {
            carregarColetoresNoMapa();
        });
    }

    const filterParceiro = document.getElementById('filter-parceiro-mapa');
    if (filterParceiro) {
        filterParceiro.addEventListener('change', () => {
            carregarColetoresNoMapa();
        });
    }

    const filterBusca = document.getElementById('filter-busca-mapa');
    if (filterBusca) {
        filterBusca.addEventListener('input', () => {
            carregarColetoresNoMapa();
        });
    }

    const filterDistancia = document.getElementById('filter-distancia-mapa');
    if (filterDistancia) {
        filterDistancia.addEventListener('change', () => {
            carregarColetoresNoMapa();
        });
    }

    const ordenarDistancia = document.getElementById('ordenar-distancia-mapa');
    if (ordenarDistancia) {
        ordenarDistancia.addEventListener('change', () => {
            carregarColetoresNoMapa();
        });
    }
}


// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', function() {
    inicializarPaginaMapa();
    
    // Garantir que verDetalhes está disponível globalmente
    // Se dashboard.js não estiver carregado, criar uma versão básica
    if (typeof window.verDetalhes !== 'function') {
        console.warn('verDetalhes não encontrado, aguardando dashboard.js...');
        // Aguardar um pouco para ver se dashboard.js carrega
        setTimeout(() => {
            if (typeof window.verDetalhes !== 'function') {
                console.error('verDetalhes ainda não está disponível após aguardar');
            }
        }, 1000);
    }
});

