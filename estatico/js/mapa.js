/*
Módulo de Mapa - Dashboard-TRONIK
==================================
Gerencia a visualização de lixeiras em mapa usando Leaflet.
Módulo independente e desacoplado do dashboard principal.
*/

// Coordenadas padrão (Brasília - DF)
const COORDENADAS_PADRAO = {
    lat: -15.7942,
    lon: -47.8822,
    zoom: 11
};

// Coordenadas da Sede Tronik Recicla
const SEDE_TRONIK = {
    lat: -15.908661672774747,
    lon: -48.076158282355806,
    nome: 'Sede Tronik Recicla'
};

// Instância do mapa (global para acesso externo)
let mapa = null;
let marcadores = {};
let grupoMarcadores = null;
let markerClusterGroup = null; // Grupo de clusters
let routingControl = null; // Controle de rotas
let lixeiras = []; // Armazenar lixeiras para acesso em funções como calcularRotaSede

/**
 * Inicializa o mapa Leaflet
 * @param {string} containerId - ID do elemento HTML que conterá o mapa
 * @param {Object} options - Opções de configuração do mapa
 */
function inicializarMapa(containerId, options = {}) {
    // Verificar se o container existe
    const container = document.getElementById(containerId);
    if (!container) {
        console.warn(`Container #${containerId} não encontrado para o mapa`);
        return null;
    }

    // Verificar se Leaflet está disponível
    if (typeof L === 'undefined') {
        console.error('Leaflet não está carregado. Verifique se o CDN está incluído.');
        container.innerHTML = '<div class="mapa-erro">Erro: Biblioteca Leaflet não encontrada</div>';
        return null;
    }

    // Opções padrão
    const config = {
        center: [options.lat || COORDENADAS_PADRAO.lat, options.lon || COORDENADAS_PADRAO.lon],
        zoom: options.zoom || COORDENADAS_PADRAO.zoom,
        ...options
    };

    // Criar mapa
    mapa = L.map(containerId, {
        center: config.center,
        zoom: config.zoom,
        zoomControl: true
    });

    // Adicionar tile layer (OpenStreetMap)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(mapa);

    // Criar grupo de marcadores para controle conjunto
    grupoMarcadores = L.layerGroup().addTo(mapa);
    
    // Criar grupo de clusters (MarkerClusterGroup)
    if (typeof L.markerClusterGroup !== 'undefined') {
        markerClusterGroup = L.markerClusterGroup({
            chunkedLoading: true,
            maxClusterRadius: 50,
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: true
        }).addTo(mapa);
    } else {
        // Fallback se MarkerCluster não estiver disponível
        markerClusterGroup = grupoMarcadores;
    }

    // Adicionar marcador da sede da Tronik
    adicionarMarcadorSede();

    return mapa;
}

/**
 * Obtém cor do marcador baseado no status da lixeira
 * @param {Object} lixeira - Objeto lixeira
 * @returns {string} Cor em hexadecimal
 */
function obterCorMarcador(lixeira) {
    const nivel = lixeira.nivel_preenchimento || 0;
    const status = lixeira.status || 'OK';

    if (nivel >= 95 || status === 'CRITICO') return '#dc3545'; // Vermelho
    if (nivel >= 80 || status === 'ALERTA') return '#ffc107';   // Amarelo
    if (status === 'MANUTENCAO') return '#6c757d';              // Cinza
    return '#28a745'; // Verde
}

/**
 * Cria ícone customizado para o marcador
 * @param {string} cor - Cor do marcador
 * @returns {L.Icon} Ícone do Leaflet
 */
function criarIconeMarcador(cor) {
    return L.divIcon({
        className: 'marcador-lixeira',
        html: `<div style="background-color: ${cor}; border: 2px solid white; border-radius: 50%; width: 20px; height: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
}

/**
 * Adiciona marcador de lixeira no mapa
 * @param {Object} lixeira - Objeto lixeira com latitude e longitude
 */
function adicionarMarcadorLixeira(lixeira) {
    if (!mapa) {
        console.warn('Mapa não inicializado');
        return;
    }

    // Verificar se tem coordenadas
    if (!lixeira.latitude || !lixeira.longitude) {
        return; // Pula lixeiras sem coordenadas
    }

    const cor = obterCorMarcador(lixeira);
    const icone = criarIconeMarcador(cor);

    // Criar popup com informações
    const popupContent = criarPopupLixeira(lixeira);

    // Criar marcador
    const marcador = L.marker(
        [lixeira.latitude, lixeira.longitude],
        { icon: icone }
    )
    .bindPopup(popupContent, {
        maxWidth: 300,
        className: 'popup-lixeira'
    });

    // Adicionar ao grupo de clusters (se disponível) ou grupo normal
    if (markerClusterGroup && markerClusterGroup !== grupoMarcadores) {
        markerClusterGroup.addLayer(marcador);
    } else {
        marcador.addTo(grupoMarcadores);
    }

    // Armazenar referência
    marcadores[lixeira.id] = marcador;

    return marcador;
}

/**
 * Cria conteúdo do popup do marcador
 * @param {Object} lixeira - Objeto lixeira
 * @returns {string} HTML do popup
 */
function criarPopupLixeira(lixeira) {
    const nivel = lixeira.nivel_preenchimento || 0;
    const statusTexto = determinarStatusTexto(lixeira);
    const parceiro = lixeira.parceiro ? lixeira.parceiro.nome : 'N/A';
    const tipoMaterial = lixeira.tipo_material ? lixeira.tipo_material.nome : 'N/A';
    const distanciaSede = calcularDistanciaSede(lixeira);
    const distanciaFormatada = formatarDistancia(distanciaSede);

    return `
        <div class="popup-lixeira-content">
            <h3>#L${String(lixeira.id).padStart(3, '0')} - ${lixeira.localizacao || 'Sem localização'}</h3>
            <div class="popup-info">
                <div class="popup-item">
                    <strong>Nível:</strong> ${nivel.toFixed(1)}%
                </div>
                <div class="popup-item">
                    <strong>Status:</strong> <span class="status-${statusTexto.toLowerCase()}">${statusTexto}</span>
                </div>
                <div class="popup-item">
                    <strong>Parceiro:</strong> ${parceiro}
                </div>
                <div class="popup-item">
                    <strong>Tipo:</strong> ${tipoMaterial}
                </div>
                ${distanciaSede !== null ? `
                <div class="popup-item">
                    <strong>Distância da Sede:</strong> <span class="distancia-sede">${distanciaFormatada}</span>
                </div>
                ` : ''}
                ${lixeira.ultima_coleta ? `
                <div class="popup-item">
                    <strong>Última Coleta:</strong> ${formatarData(lixeira.ultima_coleta)}
                </div>
                ` : ''}
            </div>
            <div class="popup-buttons">
                <button class="btn-popup-detalhes" onclick="verDetalhes(${lixeira.id})">
                    Ver Detalhes
                </button>
                ${distanciaSede !== null ? `
                <button class="btn-popup-rota" onclick="calcularRotaSede(${lixeira.id})" title="Calcular rota a partir da sede">
                    🗺️ Rota da Sede
                </button>
                ` : ''}
            </div>
        </div>
    `;
}

/**
 * Determina texto do status
 * @param {Object} lixeira - Objeto lixeira
 * @returns {string} Texto do status
 */
function determinarStatusTexto(lixeira) {
    const nivel = lixeira.nivel_preenchimento || 0;
    if (nivel >= 95) return 'CRÍTICO';
    if (nivel >= 80) return 'ATENÇÃO';
    if (lixeira.status === 'MANUTENCAO') return 'MANUTENÇÃO';
    return 'NORMAL';
}

/**
 * Formata data para exibição
 * @param {string} dataISO - Data em formato ISO
 * @returns {string} Data formatada
 */
function formatarData(dataISO) {
    if (!dataISO) return 'N/A';
    try {
        const data = new Date(dataISO);
        return data.toLocaleDateString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return dataISO;
    }
}

/**
 * Atualiza todos os marcadores no mapa
 * @param {Array} lixeirasArray - Array de lixeiras
 */
function atualizarMarcadores(lixeirasArray) {
    if (!mapa) return;

    // Armazenar lixeiras globalmente
    lixeiras = lixeirasArray || [];

    // Limpar marcadores existentes
    limparMarcadores();

    // Filtrar lixeiras com coordenadas
    const lixeirasComCoordenadas = lixeiras.filter(l => 
        l.latitude && l.longitude
    );

    if (lixeirasComCoordenadas.length === 0) {
        mostrarMensagemSemCoordenadas();
        return;
    }

    // Adicionar novos marcadores
    lixeirasComCoordenadas.forEach(lixeira => {
        adicionarMarcadorLixeira(lixeira);
    });

    // Ajustar zoom para mostrar todos os marcadores
    if (lixeirasComCoordenadas.length > 0) {
        setTimeout(() => ajustarZoomMarcadores(), 100);
    } else {
        mostrarMensagemSemCoordenadas();
    }
}

/**
 * Limpa todos os marcadores do mapa
 */
function limparMarcadores() {
    // Preservar marcador da sede
    const marcadorSede = marcadores['sede'];
    
    if (markerClusterGroup && markerClusterGroup !== grupoMarcadores) {
        markerClusterGroup.clearLayers();
    }
    if (grupoMarcadores) {
        grupoMarcadores.clearLayers();
    }
    
    // Limpar referências, mas preservar sede
    marcadores = {};
    if (marcadorSede) {
        marcadores['sede'] = marcadorSede;
    }
}

/**
 * Ajusta o zoom do mapa para mostrar todos os marcadores
 */
function ajustarZoomMarcadores() {
    if (!mapa) return;

    let bounds = null;
    
    // Tentar obter bounds do MarkerClusterGroup primeiro
    if (markerClusterGroup && markerClusterGroup !== grupoMarcadores) {
        try {
            // MarkerClusterGroup tem getBounds() mas pode falhar se não houver marcadores
            bounds = markerClusterGroup.getBounds();
        } catch (e) {
            console.warn('Erro ao obter bounds do MarkerClusterGroup:', e);
        }
    }
    
    // Se não conseguiu do cluster, tentar do grupo normal
    if (!bounds && grupoMarcadores) {
        try {
            // Verificar se grupoMarcadores tem getBounds (L.LayerGroup)
            if (typeof grupoMarcadores.getBounds === 'function') {
                bounds = grupoMarcadores.getBounds();
            }
        } catch (e) {
            console.warn('Erro ao obter bounds do grupoMarcadores:', e);
        }
    }
    
    // Se ainda não conseguiu, calcular bounds manualmente a partir dos marcadores
    if (!bounds || !bounds.isValid()) {
        const marcadoresValidos = Object.values(marcadores).filter(m => 
            m && m.getLatLng && !m._icon?.classList?.contains('marcador-sede')
        );
        
        if (marcadoresValidos.length > 0) {
            const coordenadas = marcadoresValidos.map(m => m.getLatLng());
            bounds = L.latLngBounds(coordenadas);
        }
    }
    
    // Ajustar zoom se tiver bounds válidos
    if (bounds && bounds.isValid()) {
        // Incluir marcador da sede se existir
        const marcadorSede = marcadores['sede'];
        if (marcadorSede && marcadorSede.getLatLng) {
            bounds.extend(marcadorSede.getLatLng());
        }
        mapa.fitBounds(bounds, { padding: [50, 50] });
    } else {
        // Se não há marcadores, voltar para zoom padrão
        mapa.setView([COORDENADAS_PADRAO.lat, COORDENADAS_PADRAO.lon], COORDENADAS_PADRAO.zoom);
    }
}

/**
 * Mostra mensagem quando não há coordenadas
 */
function mostrarMensagemSemCoordenadas() {
    if (!mapa) return;

    // Remover overlay anterior se existir
    const overlayExistente = document.querySelector('.mapa-sem-coordenadas-overlay');
    if (overlayExistente) {
        overlayExistente.remove();
    }

    // Criar overlay com mensagem
    const overlay = L.control({ position: 'topright' });
    overlay.onAdd = function() {
        const div = L.DomUtil.create('div', 'mapa-sem-coordenadas mapa-sem-coordenadas-overlay');
        div.innerHTML = `
            <div class="alerta-sem-coordenadas">
                <strong>⚠️ Aviso</strong><br>
                Nenhuma lixeira possui coordenadas cadastradas.
                Adicione coordenadas nas configurações para visualizar no mapa.
            </div>
        `;
        return div;
    };
    overlay.addTo(mapa);
}

/**
 * Destaca uma lixeira específica no mapa
 * @param {number} lixeiraId - ID da lixeira
 */
function destacarLixeira(lixeiraId) {
    if (!marcadores[lixeiraId]) return;

    const marcador = marcadores[lixeiraId];
    mapa.setView(marcador.getLatLng(), 15);
    marcador.openPopup();
}

/**
 * Atualiza cor do marcador baseado em mudanças na lixeira
 * @param {Object} lixeira - Objeto lixeira atualizado
 */
function atualizarMarcadorLixeira(lixeira) {
    if (!marcadores[lixeira.id]) return;

    const marcador = marcadores[lixeira.id];
    const cor = obterCorMarcador(lixeira);
    const novoIcone = criarIconeMarcador(cor);

    marcador.setIcon(novoIcone);
    
    // Atualizar popup
    const novoPopup = criarPopupLixeira(lixeira);
    marcador.setPopupContent(novoPopup);
}

/**
 * Exporta mapa como imagem (funcionalidade futura)
 */
function exportarMapa() {
    // TODO: Implementar exportação de mapa
    console.log('Exportação de mapa não implementada ainda');
}

/**
 * Calcula rota otimizada entre múltiplas lixeiras
 * @param {Array} lixeiras - Array de lixeiras para visitar
 * @param {Object} pontoInicial - Coordenadas do ponto inicial {lat, lon}
 * @returns {Array} Array de coordenadas ordenadas para rota otimizada
 */
function calcularRotaOtimizada(lixeiras, pontoInicial = null) {
    if (!lixeiras || lixeiras.length === 0) return [];
    
    // Filtrar lixeiras com coordenadas válidas
    const lixeirasValidas = lixeiras.filter(l => 
        l.latitude && l.longitude && 
        !isNaN(parseFloat(l.latitude)) && 
        !isNaN(parseFloat(l.longitude))
    );
    
    if (lixeirasValidas.length === 0) return [];
    
    // Se há apenas uma lixeira, retornar direto
    if (lixeirasValidas.length === 1) {
        return [[parseFloat(lixeirasValidas[0].latitude), parseFloat(lixeirasValidas[0].longitude)]];
    }
    
    // Converter para array de coordenadas
    const pontos = lixeirasValidas.map(l => ({
        id: l.id,
        lat: parseFloat(l.latitude),
        lon: parseFloat(l.longitude),
        nivel: l.nivel_preenchimento || 0
    }));
    
    // Se há ponto inicial, adicionar no início
    if (pontoInicial && pontoInicial.lat && pontoInicial.lon) {
        pontos.unshift({
            id: 'inicio',
            lat: parseFloat(pontoInicial.lat),
            lon: parseFloat(pontoInicial.lon),
            nivel: 0
        });
    }
    
    // Algoritmo simples: Nearest Neighbor (vizinho mais próximo)
    const rota = [];
    const visitados = new Set();
    let atual = pontos[0];
    rota.push([atual.lat, atual.lon]);
    visitados.add(atual.id);
    
    while (visitados.size < pontos.length) {
        let maisProximo = null;
        let menorDistancia = Infinity;
        
        for (const ponto of pontos) {
            if (!visitados.has(ponto.id)) {
                const distancia = calcularDistancia(
                    atual.lat, atual.lon,
                    ponto.lat, ponto.lon
                );
                if (distancia < menorDistancia) {
                    menorDistancia = distancia;
                    maisProximo = ponto;
                }
            }
        }
        
        if (maisProximo) {
            rota.push([maisProximo.lat, maisProximo.lon]);
            visitados.add(maisProximo.id);
            atual = maisProximo;
        } else {
            break;
        }
    }
    
    return rota;
}

/**
 * Calcula distância entre dois pontos (Haversine)
 * @param {number} lat1 - Latitude do ponto 1
 * @param {number} lon1 - Longitude do ponto 1
 * @param {number} lat2 - Latitude do ponto 2
 * @param {number} lon2 - Longitude do ponto 2
 * @returns {number} Distância em quilômetros
 */
function calcularDistancia(lat1, lon1, lat2, lon2) {
    const R = 6371; // Raio da Terra em km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = 
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

/**
 * Calcula distância de uma lixeira até a sede
 * @param {Object} lixeira - Objeto lixeira com latitude e longitude
 * @returns {number|null} Distância em quilômetros ou null se não tiver coordenadas
 */
function calcularDistanciaSede(lixeira) {
    if (!lixeira || !lixeira.latitude || !lixeira.longitude) {
        return null;
    }
    
    const lat = parseFloat(lixeira.latitude);
    const lon = parseFloat(lixeira.longitude);
    
    if (isNaN(lat) || isNaN(lon)) {
        return null;
    }
    
    return calcularDistancia(
        lat, lon,
        SEDE_TRONIK.lat, SEDE_TRONIK.lon
    );
}

/**
 * Formata distância para exibição
 * @param {number} distancia - Distância em km
 * @returns {string} Distância formatada
 */
function formatarDistancia(distancia) {
    if (distancia === null || distancia === undefined) {
        return 'N/A';
    }
    
    if (distancia < 1) {
        return `${Math.round(distancia * 1000)}m`;
    }
    
    return `${distancia.toFixed(1)}km`;
}

/**
 * Adiciona rota ao mapa usando Leaflet Routing Machine
 */
function adicionarRota(waypoints, options = {}) {
    if (!mapa || typeof L.Routing === 'undefined') {
        console.warn('Leaflet Routing Machine não está disponível');
        alert('Serviço de rotas não disponível. Verifique se a biblioteca está carregada.');
        return null;
    }
    
    // Remover rota anterior se existir
    if (routingControl) {
        mapa.removeControl(routingControl);
        routingControl = null;
    }
    
    if (!waypoints || waypoints.length < 2) {
        console.warn('É necessário pelo menos 2 waypoints para criar uma rota');
        return null;
    }
    
    // Converter waypoints para formato L.Routing
    const routingWaypoints = waypoints.map(wp => 
        L.latLng(wp[0], wp[1])
    );
    
    // Configurar router OSRM (servidor demo não suporta pt, usar en)
    const router = L.Routing.osrmv1({
        serviceUrl: 'https://router.project-osrm.org/route/v1',
        timeout: 10000, // 10 segundos
        profile: 'driving',
        language: 'en' // Servidor demo não suporta pt, usar en
    });
    
    // Armazenar waypoints originais para fallback
    const waypointsOriginais = waypoints;
    
    // Criar controle de rota com tratamento de erros
    routingControl = L.Routing.control({
        router: router,
        waypoints: routingWaypoints,
        routeWhileDragging: false,
        showAlternatives: false,
        addWaypoints: false,
        draggableWaypoints: false,
        show: true,
        fitSelectedRoutes: true,
        language: 'en', // Servidor demo não suporta pt
        units: 'metric', // Unidades métricas (km, m)
        lineOptions: {
            styles: [
                {color: '#27ae60', opacity: 0.8, weight: 5}
            ]
        },
        ...options
    }).addTo(mapa);
    
    // Tratamento de erros
    routingControl.on('routingerror', function(e) {
        console.error('Erro ao calcular rota:', e);
        
        // Remover controle de rota que falhou
        if (routingControl && mapa) {
            mapa.removeControl(routingControl);
            routingControl = null;
        }
        
        // Usar sistema robusto como fallback (sempre usar, não mostrar alerta)
        if (waypointsOriginais && waypointsOriginais.length >= 2) {
            console.log('OSRM falhou, usando sistema robusto de roteamento');
            desenharRotaRobusta(waypointsOriginais[0], waypointsOriginais[1]);
        } else {
            console.error('Erro ao calcular rota:', e.error?.message || 'Erro desconhecido');
        }
    });
    
    // Sucesso
    routingControl.on('routesfound', function(e) {
        console.log('Rota calculada com sucesso:', e.routes);
        if (e.routes && e.routes.length > 0) {
            const route = e.routes[0];
            const distancia = (route.summary?.totalDistance / 1000).toFixed(1);
            const tempo = Math.round(route.summary?.totalTime / 60);
            console.log(`Distância: ${distancia}km | Tempo estimado: ${tempo}min`);
            
            // Salvar rota real para aprendizado
            if (typeof salvarRotaReal === 'function' && waypointsOriginais && waypointsOriginais.length >= 2) {
                // Converter waypoints da rota OSRM para array de coordenadas
                const rotaReal = route.coordinates || route.waypoints?.map(wp => [wp.lat, wp.lng]) || [];
                if (rotaReal.length > 0) {
                    salvarRotaReal(rotaReal, waypointsOriginais[0], waypointsOriginais[1]);
                }
            }
        }
    });
    
    return routingControl;
}

// Variável para armazenar linha de rota alternativa
let rotaLinha = null;

// Cache de dados OSM
let osmCache = {
    estradas: new Map(),
    ultimaAtualizacao: null,
    tempoCache: 3600000 // 1 hora
};

/**
 * Remove rota do mapa
 */
function removerRota() {
    if (routingControl && mapa) {
        mapa.removeControl(routingControl);
        routingControl = null;
    }
    
    // Remover linha de rota alternativa se existir
    if (rotaLinha && mapa) {
        mapa.removeLayer(rotaLinha);
        rotaLinha = null;
    }
}

/**
 * Implementação do algoritmo de Dijkstra para encontrar caminho mais curto
 * @param {Object} grafo - Grafo representado como {node: {vizinho: peso}}
 * @param {string} inicio - Nó inicial
 * @param {string} fim - Nó final
 * @returns {Array} Caminho do início ao fim
 */
function dijkstra(grafo, inicio, fim) {
    const distancias = {};
    const anteriores = {};
    const naoVisitados = new Set();
    
    // Inicializar distâncias
    for (const node in grafo) {
        distancias[node] = Infinity;
        anteriores[node] = null;
        naoVisitados.add(node);
    }
    distancias[inicio] = 0;
    
    while (naoVisitados.size > 0) {
        // Encontrar nó com menor distância
        let noAtual = null;
        let menorDistancia = Infinity;
        
        for (const node of naoVisitados) {
            if (distancias[node] < menorDistancia) {
                menorDistancia = distancias[node];
                noAtual = node;
            }
        }
        
        if (noAtual === null || noAtual === fim) {
            break;
        }
        
        naoVisitados.delete(noAtual);
        
        // Atualizar distâncias dos vizinhos
        if (grafo[noAtual]) {
            for (const vizinho in grafo[noAtual]) {
                const distancia = distancias[noAtual] + grafo[noAtual][vizinho];
                if (distancia < distancias[vizinho]) {
                    distancias[vizinho] = distancia;
                    anteriores[vizinho] = noAtual;
                }
            }
        }
    }
    
    // Reconstruir caminho
    const caminho = [];
    let atual = fim;
    while (atual !== null) {
        caminho.unshift(atual);
        atual = anteriores[atual];
    }
    
    return caminho.length > 1 ? caminho : null;
}

/**
 * Cria uma grade de pontos intermediários entre dois pontos
 * @param {Array} ponto1 - [lat, lon]
 * @param {Array} ponto2 - [lat, lon]
 * @param {number} numPontos - Número de pontos intermediários
 * @returns {Array} Array de pontos [lat, lon]
 */
function criarGradePontos(ponto1, ponto2, numPontos = 5) {
    const pontos = [ponto1];
    
    for (let i = 1; i < numPontos; i++) {
        const t = i / numPontos;
        const lat = ponto1[0] + (ponto2[0] - ponto1[0]) * t;
        const lon = ponto1[1] + (ponto2[1] - ponto1[1]) * t;
        
        // Adicionar pequena variação aleatória para simular desvios de rota
        const variacao = 0.002; // ~200m
        const latVariada = lat + (Math.random() - 0.5) * variacao;
        const lonVariada = lon + (Math.random() - 0.5) * variacao;
        
        pontos.push([latVariada, lonVariada]);
    }
    
    pontos.push(ponto2);
    return pontos;
}

/**
 * Cria grafo a partir de pontos para o algoritmo de Dijkstra
 * @param {Array} pontos - Array de pontos [lat, lon]
 * @returns {Object} Grafo {nodeIndex: {vizinhoIndex: distancia}}
 */
function criarGrafo(pontos) {
    const grafo = {};
    
    for (let i = 0; i < pontos.length; i++) {
        grafo[i] = {};
        
        // Conectar com pontos próximos (até 3 pontos à frente)
        for (let j = i + 1; j < Math.min(i + 4, pontos.length); j++) {
            const distancia = calcularDistancia(
                pontos[i][0], pontos[i][1],
                pontos[j][0], pontos[j][1]
            );
            grafo[i][j] = distancia;
            
            // Grafo bidirecional
            if (!grafo[j]) grafo[j] = {};
            grafo[j][i] = distancia;
        }
    }
    
    return grafo;
}

/**
 * Calcula rota usando algoritmo de Dijkstra (fallback quando OSRM não está disponível)
 * @param {Array} ponto1 - [lat, lon] ponto inicial
 * @param {Array} ponto2 - [lat, lon] ponto final
 * @returns {Array} Array de pontos que formam a rota
 */
function calcularRotaDijkstra(ponto1, ponto2) {
    // Criar grade de pontos intermediários
    const numPontos = 8; // Mais pontos = rota mais suave
    const pontosGrade = criarGradePontos(ponto1, ponto2, numPontos);
    
    // Criar grafo
    const grafo = criarGrafo(pontosGrade);
    
    // Calcular caminho usando Dijkstra
    const caminho = dijkstra(grafo, 0, pontosGrade.length - 1);
    
    if (!caminho) {
        // Se Dijkstra falhar, retornar linha reta
        return [ponto1, ponto2];
    }
    
    // Converter índices para coordenadas
    const rota = caminho.map(idx => pontosGrade[idx]);
    
    return rota;
}

/**
 * Desenha rota calculada usando sistema robusto de roteamento
 * @param {Array} ponto1 - [lat, lon] ponto inicial
 * @param {Array} ponto2 - [lat, lon] ponto final
 */
async function desenharRotaRobusta(ponto1, ponto2) {
    // Remover linha anterior se existir
    if (rotaLinha && mapa) {
        mapa.removeLayer(rotaLinha);
        rotaLinha = null;
    }
    
    // Calcular rota usando sistema robusto
    let pontosRota = null;
    let tipoRota = 'Aproximada';
    
    if (typeof calcularRotaRobusta === 'function') {
        try {
            pontosRota = await calcularRotaRobusta(ponto1, ponto2, {
                usarOSM: true,
                usarCache: true,
                algoritmo: 'aStar',
                suavizar: true
            });
            tipoRota = 'Calculada';
        } catch (error) {
            console.warn('Erro ao calcular rota robusta:', error);
        }
    }
    
    // Garantir que sempre temos uma rota válida com múltiplos pontos
    if (!pontosRota || pontosRota.length < 3) {
        console.warn('Rota calculada tem poucos pontos, gerando rota intermediária');
        // Gerar pontos intermediários para evitar linha reta
        if (typeof gerarRotaIntermediaria === 'function') {
            pontosRota = gerarRotaIntermediaria(ponto1, ponto2, 8);
        } else {
            // Fallback: criar pontos intermediários manualmente
            pontosRota = [ponto1];
            for (let i = 1; i < 7; i++) {
                const t = i / 8;
                pontosRota.push([
                    ponto1[0] + (ponto2[0] - ponto1[0]) * t,
                    ponto1[1] + (ponto2[1] - ponto1[1]) * t
                ]);
            }
            pontosRota.push(ponto2);
        }
        tipoRota = 'Aproximada';
    }
    
    // Calcular distância total
    let distanciaTotal = 0;
    for (let i = 0; i < pontosRota.length - 1; i++) {
        distanciaTotal += calcularDistancia(
            pontosRota[i][0], pontosRota[i][1],
            pontosRota[i + 1][0], pontosRota[i + 1][1]
        );
    }
    const distanciaFormatada = formatarDistancia(distanciaTotal);
    
    // Criar linha da rota
    rotaLinha = L.polyline(pontosRota, {
        color: '#27ae60',
        weight: 4,
        opacity: 0.7,
        dashArray: tipoRota === 'Calculada' ? '0' : '8, 4' // Sólida se calculada, tracejada se aproximada
    }).addTo(mapa);
    
    // Adicionar popup na linha
    rotaLinha.bindPopup(`<strong>Rota ${tipoRota}</strong><br>Distância: ${distanciaFormatada}<br><small>${tipoRota === 'Calculada' ? 'Rota otimizada com dados reais' : 'Rota aproximada - serviço otimizado não disponível'}</small>`);
    
    return rotaLinha;
}

/**
 * Gera rota intermediária com múltiplos pontos (evita linha reta)
 * @param {Array} ponto1 - [lat, lon] ponto inicial
 * @param {Array} ponto2 - [lat, lon] ponto final
 * @param {number} numPontos - Número de pontos intermediários
 * @returns {Array} Array de coordenadas [lat, lon][]
 */
function gerarRotaIntermediaria(ponto1, ponto2, numPontos = 10) {
    const pontos = [ponto1];
    
    for (let i = 1; i < numPontos - 1; i++) {
        const t = i / numPontos;
        const lat = ponto1[0] + (ponto2[0] - ponto1[0]) * t;
        const lon = ponto1[1] + (ponto2[1] - ponto1[1]) * t;
        
        // Adicionar pequena variação para evitar linha perfeitamente reta
        const variacao = 0.001; // ~100m
        const variacaoLat = (Math.random() - 0.5) * variacao;
        const variacaoLon = (Math.random() - 0.5) * variacao;
        
        pontos.push([lat + variacaoLat, lon + variacaoLon]);
    }
    
    pontos.push(ponto2);
    return pontos;
}

/**
 * Calcula rota da sede até uma lixeira específica
 * @param {number} lixeiraId - ID da lixeira de destino
 */
function calcularRotaSede(lixeiraId) {
    if (!lixeiras || !lixeiras.length) {
        console.warn('Nenhuma lixeira disponível');
        alert('Nenhuma lixeira disponível no mapa');
        return;
    }
    
    const lixeira = lixeiras.find(l => l.id === lixeiraId);
    if (!lixeira || !lixeira.latitude || !lixeira.longitude) {
        alert('Lixeira não encontrada ou sem coordenadas');
        return;
    }
    
    const lat = parseFloat(lixeira.latitude);
    const lon = parseFloat(lixeira.longitude);
    
    if (isNaN(lat) || isNaN(lon)) {
        alert('Coordenadas inválidas para esta lixeira');
        return;
    }
    
    // Criar rota: Sede -> Lixeira
    const waypoints = [
        [SEDE_TRONIK.lat, SEDE_TRONIK.lon],
        [lat, lon]
    ];
    
    // Tentar usar Leaflet Routing Machine
    if (typeof L.Routing !== 'undefined') {
        try {
            const resultado = adicionarRota(waypoints, {
                createMarker: function(i, wp) {
                    if (i === 0) {
                        // Marcador especial para a sede
                        return L.marker(wp.latLng, {
                            icon: L.icon({
                                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
                                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
                                iconSize: [25, 41],
                                iconAnchor: [12, 41],
                                popupAnchor: [1, -34],
                                shadowSize: [41, 41]
                            })
                        }).bindPopup(`<strong>${SEDE_TRONIK.nome}</strong><br>Ponto de partida`);
                    } else {
                        // Marcador padrão para a lixeira
                        return L.marker(wp.latLng);
                    }
                }
            });
            
            // Se falhou imediatamente, usar sistema robusto como fallback
            if (!resultado) {
                console.warn('Falha ao criar rota otimizada, usando sistema robusto');
                desenharRotaRobusta(waypoints[0], waypoints[1]);
            }
        } catch (error) {
            console.error('Erro ao tentar criar rota:', error);
            // Usar sistema robusto como fallback
            desenharRotaRobusta(waypoints[0], waypoints[1]);
        }
    } else {
        // Se Leaflet Routing Machine não estiver disponível, usar sistema robusto
        console.warn('Leaflet Routing Machine não disponível, usando sistema robusto');
        desenharRotaRobusta(waypoints[0], waypoints[1]);
    }
    
    // Centralizar mapa na rota
    const bounds = L.latLngBounds(waypoints);
    mapa.fitBounds(bounds, { padding: [50, 50] });
    
    console.log(`Rota calculada: ${SEDE_TRONIK.nome} -> Lixeira #${lixeiraId}`);
}

/**
 * Filtra lixeiras por distância da sede
 * @param {Array} lixeirasList - Lista de lixeiras
 * @param {string} filtroDistancia - Filtro de distância ('todas', 'ate-10', '10-20', '20-50', 'mais-50')
 * @returns {Array} Lista filtrada
 */
function filtrarPorDistancia(lixeirasList, filtroDistancia = 'todas') {
    if (filtroDistancia === 'todas') {
        return lixeirasList;
    }
    
    return lixeirasList.filter(lixeira => {
        const distancia = calcularDistanciaSede(lixeira);
        if (distancia === null) {
            return false; // Excluir lixeiras sem coordenadas
        }
        
        switch (filtroDistancia) {
            case 'ate-10':
                return distancia <= 10;
            case '10-20':
                return distancia > 10 && distancia <= 20;
            case '20-50':
                return distancia > 20 && distancia <= 50;
            case 'mais-50':
                return distancia > 50;
            default:
                return true;
        }
    });
}

/**
 * Ordena lixeiras por distância da sede
 * @param {Array} lixeirasList - Lista de lixeiras
 * @param {string} ordem - 'asc' (mais próxima primeiro) ou 'desc' (mais distante primeiro)
 * @returns {Array} Lista ordenada
 */
function ordenarPorDistancia(lixeirasList, ordem = 'asc') {
    const lixeirasComDistancia = lixeirasList.map(lixeira => ({
        lixeira,
        distancia: calcularDistanciaSede(lixeira)
    }));
    
    // Separar lixeiras com e sem coordenadas
    const comCoordenadas = lixeirasComDistancia.filter(item => item.distancia !== null);
    const semCoordenadas = lixeirasComDistancia.filter(item => item.distancia === null);
    
    // Ordenar por distância
    comCoordenadas.sort((a, b) => {
        if (ordem === 'asc') {
            return a.distancia - b.distancia;
        } else {
            return b.distancia - a.distancia;
        }
    });
    
    // Retornar: ordenadas + sem coordenadas
    return comCoordenadas.map(item => item.lixeira).concat(semCoordenadas.map(item => item.lixeira));
}

/**
 * Adiciona marcador da sede da Tronik Recicla
 */
function adicionarMarcadorSede() {
    if (!mapa) return;
    
    // Coordenadas da sede
    const sedeLat = -15.908661672774747;
    const sedeLon = -48.076158282355806;
    
    // Criar ícone especial para a sede (maior e diferente)
    const iconeSede = L.divIcon({
        className: 'marcador-sede',
        html: `
            <div style="
                background: linear-gradient(135deg, #27ae60 0%, #229954 100%);
                border: 3px solid white;
                border-radius: 50%;
                width: 32px;
                height: 32px;
                box-shadow: 0 3px 8px rgba(0,0,0,0.4);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
                color: white;
                font-weight: bold;
            ">🏢</div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -16]
    });
    
    // Criar marcador da sede
    const marcadorSede = L.marker([sedeLat, sedeLon], {
        icon: iconeSede,
        zIndexOffset: 1000 // Sempre acima dos outros marcadores
    });
    
    // Criar popup da sede
    const popupSede = `
        <div style="text-align: center; padding: 5px;">
            <h3 style="margin: 0 0 10px 0; color: #27ae60; font-size: 18px;">
                🏢 Sede Tronik Recicla
            </h3>
            <p style="margin: 5px 0; color: #555;">
                <strong>Endereço:</strong><br>
                Coordenadas: ${sedeLat.toFixed(6)}, ${sedeLon.toFixed(6)}
            </p>
            <p style="margin: 5px 0; color: #555; font-size: 12px;">
                Centro administrativo e operacional
            </p>
        </div>
    `;
    
    marcadorSede.bindPopup(popupSede, {
        maxWidth: 250,
        className: 'popup-sede'
    });
    
    // Adicionar ao mapa (não ao cluster, para sempre estar visível)
    marcadorSede.addTo(mapa);
    
    // Armazenar referência
    marcadores['sede'] = marcadorSede;
    
    return marcadorSede;
}

// Exportar funções principais para uso externo
if (typeof window !== 'undefined') {
    // Tornar calcularRotaSede acessível globalmente para uso em popups
    window.calcularRotaSede = calcularRotaSede;

    window.MapaTronik = {
        inicializar: inicializarMapa,
        atualizarMarcadores: atualizarMarcadores,
        calcularRotaOtimizada: calcularRotaOtimizada,
        adicionarRota: adicionarRota,
        removerRota: removerRota,
        adicionarMarcadorSede: adicionarMarcadorSede,
        destacarLixeira: destacarLixeira,
        atualizarMarcador: atualizarMarcadorLixeira,
        limpar: limparMarcadores,
        ajustarZoomMarcadores: ajustarZoomMarcadores,
        exportar: exportarMapa,
        get mapa() { return mapa; } // Expor instância do mapa para redimensionamento
    };
    
    // Também expor globalmente para compatibilidade
    window.mapa = mapa;
}

