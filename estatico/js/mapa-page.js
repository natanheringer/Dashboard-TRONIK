/*
JavaScript da Página de Mapa - Dashboard-TRONIK
===============================================
Gerencia a página dedicada de mapa.
Carrega lixeiras e atualiza o mapa.
*/

let todasLixeirasMapa = [];
let mapaInicializado = false;

/**
 * Carrega todas as lixeiras e atualiza o mapa
 */
async function carregarLixeirasNoMapa() {
    try {
        // Verificar se a função obterTodasLixeiras está disponível
        if (typeof obterTodasLixeiras !== 'function') {
            console.error('Função obterTodasLixeiras não encontrada. Verifique se api.js está carregado.');
            return;
        }

        const lixeiras = await obterTodasLixeiras();
        todasLixeirasMapa = lixeiras;
        
        // Aplicar filtros
        const lixeirasFiltradas = aplicarFiltrosMapa(lixeiras);
        
        // Atualizar mapa
        if (typeof window.MapaTronik !== 'undefined' && window.MapaTronik.atualizarMarcadores) {
            window.MapaTronik.atualizarMarcadores(lixeirasFiltradas);
        } else {
            console.warn('MapaTronik.atualizarMarcadores não disponível');
        }
    } catch (error) {
        console.error('Erro ao carregar lixeiras:', error);
    }
}

/**
 * Aplica filtros às lixeiras
 */
function aplicarFiltrosMapa(lixeiras) {
    const statusFiltro = document.getElementById('filter-status-mapa')?.value || '';
    const parceiroFiltro = document.getElementById('filter-parceiro-mapa')?.value || '';
    const buscaFiltro = document.getElementById('filter-busca-mapa')?.value.toLowerCase() || '';
    const distanciaFiltro = document.getElementById('filter-distancia-mapa')?.value || 'todas';
    const ordenarDistancia = document.getElementById('ordenar-distancia-mapa')?.value || '';

    let lixeirasFiltradas = lixeiras.filter(lixeira => {
        // Filtro de status
        if (statusFiltro) {
            const nivel = lixeira.nivel_preenchimento || 0;
            const status = lixeira.status || 'OK';
            
            if (statusFiltro === 'normal' && (nivel >= 80 || status !== 'OK')) return false;
            if (statusFiltro === 'atencao' && (nivel < 80 || nivel >= 95)) return false;
            if (statusFiltro === 'critico' && nivel < 95) return false;
            if (statusFiltro === 'manutencao' && status !== 'MANUTENCAO') return false;
        }

        // Filtro de parceiro
        if (parceiroFiltro) {
            const parceiroId = lixeira.parceiro?.id || null;
            if (parceiroId !== parseInt(parceiroFiltro)) return false;
        }

        // Filtro de busca
        if (buscaFiltro) {
            const localizacao = (lixeira.localizacao || '').toLowerCase();
            const id = `#L${String(lixeira.id).padStart(3, '0')}`.toLowerCase();
            if (!localizacao.includes(buscaFiltro) && !id.includes(buscaFiltro)) {
                return false;
            }
        }

        return true;
    });

    // Aplicar filtro de distância (usando função do mapa.js)
    if (typeof filtrarPorDistancia === 'function') {
        lixeirasFiltradas = filtrarPorDistancia(lixeirasFiltradas, distanciaFiltro);
    }

    // Aplicar ordenação por distância
    if (ordenarDistancia && typeof ordenarPorDistancia === 'function') {
        const ordem = ordenarDistancia === 'proxima' ? 'asc' : 'desc';
        lixeirasFiltradas = ordenarPorDistancia(lixeirasFiltradas, ordem);
    }

    return lixeirasFiltradas;
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
    const mapaContainer = document.getElementById('mapa-lixeiras');
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

            window.MapaTronik.inicializar('mapa-lixeiras', {
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

    // Carregar lixeiras
    await carregarLixeirasNoMapa();

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
            carregarLixeirasNoMapa();
        });
    }

    // Filtros
    const filterStatus = document.getElementById('filter-status-mapa');
    if (filterStatus) {
        filterStatus.addEventListener('change', () => {
            carregarLixeirasNoMapa();
        });
    }

    const filterParceiro = document.getElementById('filter-parceiro-mapa');
    if (filterParceiro) {
        filterParceiro.addEventListener('change', () => {
            carregarLixeirasNoMapa();
        });
    }

    const filterBusca = document.getElementById('filter-busca-mapa');
    if (filterBusca) {
        filterBusca.addEventListener('input', () => {
            carregarLixeirasNoMapa();
        });
    }

    const filterDistancia = document.getElementById('filter-distancia-mapa');
    if (filterDistancia) {
        filterDistancia.addEventListener('change', () => {
            carregarLixeirasNoMapa();
        });
    }

    const ordenarDistancia = document.getElementById('ordenar-distancia-mapa');
    if (ordenarDistancia) {
        ordenarDistancia.addEventListener('change', () => {
            carregarLixeirasNoMapa();
        });
    }
}


// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', inicializarPaginaMapa);

