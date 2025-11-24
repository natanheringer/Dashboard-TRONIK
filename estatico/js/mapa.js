/*
Módulo de Mapa - Dashboard-TRONIK
==================================
Gerencia a visualização de coletores em mapa usando Leaflet.
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
let coletores = []; // Armazenar coletores para acesso em funções como calcularRotaSede

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
 * Obtém cor do marcador baseado no status da coletor
 * @param {Object} coletor - Objeto coletor
 * @returns {string} Cor em hexadecimal
 */
function obterCorMarcador(coletor) {
    const nivel = coletor.nivel_preenchimento || 0;
    const status = coletor.status || 'OK';

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
        className: 'marcador-coletor',
        html: `<div style="background-color: ${cor}; border: 2px solid white; border-radius: 50%; width: 20px; height: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
}

/**
 * Adiciona marcador de coletor no mapa
 * @param {Object} coletor - Objeto coletor com latitude e longitude
 */
function adicionarMarcadorColetor(coletor) {
    if (!mapa) {
        console.warn('Mapa não inicializado');
        return;
    }

    // Verificar se tem coordenadas
    if (!coletor.latitude || !coletor.longitude) {
        return; // Pula coletores sem coordenadas
    }

    const cor = obterCorMarcador(coletor);
    const icone = criarIconeMarcador(cor);

    // Criar popup com informações
    const popupContent = criarPopupColetor(coletor);

    // Criar marcador
    const marcador = L.marker(
        [coletor.latitude, coletor.longitude],
        { icon: icone }
    )
    .bindPopup(popupContent, {
        maxWidth: 300,
        className: 'popup-coletor'
    });

    // Adicionar ao grupo de clusters (se disponível) ou grupo normal
    if (markerClusterGroup && markerClusterGroup !== grupoMarcadores) {
        markerClusterGroup.addLayer(marcador);
    } else {
        marcador.addTo(grupoMarcadores);
    }

    // Armazenar referência
    marcadores[coletor.id] = marcador;

    return marcador;
}

/**
 * Cria conteúdo do popup do marcador
 * @param {Object} coletor - Objeto coletor
 * @returns {string} HTML do popup
 */
function criarPopupColetor(coletor) {
    const nivel = coletor.nivel_preenchimento || 0;
    const statusTexto = determinarStatusTexto(coletor);
    const parceiro = coletor.parceiro ? coletor.parceiro.nome : 'N/A';
    const tipoMaterial = coletor.tipo_material ? coletor.tipo_material.nome : 'N/A';
    const distanciaSede = calcularDistanciaSede(coletor);
    const distanciaFormatada = formatarDistancia(distanciaSede);

    return `
        <div class="popup-coletor-content">
            <h3>#L${String(coletor.id).padStart(3, '0')} - ${coletor.localizacao || 'Sem localização'}</h3>
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
                ${coletor.ultima_coleta ? `
                <div class="popup-item">
                    <strong>Última Coleta:</strong> ${formatarData(coletor.ultima_coleta)}
                </div>
                ` : ''}
            </div>
            <div class="popup-buttons">
                <button class="btn-popup-detalhes" onclick="if(typeof verDetalhes === 'function') { verDetalhes(${coletor.id}); } else { console.error('verDetalhes não está disponível'); }">
                    Ver Detalhes
                </button>
                ${distanciaSede !== null ? `
                <button class="btn-popup-rota" onclick="calcularRotaSede(${coletor.id})" title="Calcular rota a partir da sede">
                    🗺️ Rota da Sede
                </button>
                ` : ''}
            </div>
        </div>
    `;
}

/**
 * Determina texto do status
 * @param {Object} coletor - Objeto coletor
 * @returns {string} Texto do status
 */
function determinarStatusTexto(coletor) {
    const nivel = coletor.nivel_preenchimento || 0;
    if (nivel >= 95) return 'CRÍTICO';
    if (nivel >= 80) return 'ATENÇÃO';
    if (coletor.status === 'MANUTENCAO') return 'MANUTENÇÃO';
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
 * @param {Array} coletoresArray - Array de coletores
 */
function atualizarMarcadores(coletoresArray) {
    if (!mapa) return;

    // Armazenar coletores globalmente
    coletores = Array.isArray(coletoresArray) ? coletoresArray : [];

    // Limpar marcadores existentes
    limparMarcadores();

    // Filtrar coletores com coordenadas válidas
    const coletoresComCoordenadas = coletores.filter(c => {
        if (!l) return false;
        const lat = parseFloat(l.latitude);
        const lon = parseFloat(l.longitude);
        return !isNaN(lat) && !isNaN(lon) && 
               isFinite(lat) && isFinite(lon) &&
               lat >= -90 && lat <= 90 &&
               lon >= -180 && lon <= 180;
    });

    if (coletoresComCoordenadas.length === 0) {
        mostrarMensagemSemCoordenadas();
        return;
    }

    // Adicionar novos marcadores
    coletoresComCoordenadas.forEach(coletor => {
        adicionarMarcadorColetor(coletor);
    });

    // Ajustar zoom para mostrar todos os marcadores
    if (coletoresComCoordenadas.length > 0) {
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
                <strong><img src="/static/icons/alert_icon.png" alt="Aviso" class="inline-icon"> Aviso</strong><br>
                Nenhuma coletor possui coordenadas cadastradas.
                Adicione coordenadas nas configurações para visualizar no mapa.
            </div>
        `;
        return div;
    };
    overlay.addTo(mapa);
}

/**
 * Destaca uma coletor específica no mapa
 * @param {number} coletorId - ID do coletor
 */
function destacarColetor(coletorId) {
    if (!mapa || !marcadores || !marcadores[coletorId]) return;

    const marcador = marcadores[coletorId];
    if (!marcador || typeof marcador.getLatLng !== 'function') return;
    
    try {
        const latLng = marcador.getLatLng();
        if (latLng && typeof latLng.lat === 'number' && typeof latLng.lng === 'number') {
            mapa.setView(latLng, 15);
            if (typeof marcador.openPopup === 'function') {
                marcador.openPopup();
            }
        }
    } catch (e) {
        console.warn('Erro ao destacar coletor:', e);
    }
}

/**
 * Atualiza cor do marcador baseado em mudanças na coletor
 * @param {Object} coletor - Objeto coletor atualizado
 */
function atualizarMarcadorColetor(coletor) {
    if (!coletor || !coletor.id || !marcadores || !marcadores[coletor.id]) return;

    const marcador = marcadores[coletor.id];
    if (!marcador || typeof marcador.setIcon !== 'function') return;
    
    try {
        const cor = obterCorMarcador(coletor);
        const novoIcone = criarIconeMarcador(cor);
        if (novoIcone) {
            marcador.setIcon(novoIcone);
        }
        
        // Atualizar popup
        const novoPopup = criarPopupColetor(coletor);
        if (novoPopup && typeof marcador.setPopupContent === 'function') {
            marcador.setPopupContent(novoPopup);
        }
    } catch (e) {
        console.warn('Erro ao atualizar marcador:', e);
    }
}

/**
 * Exporta mapa como imagem (PNG)
 */
function exportarMapa() {
    if (!mapa) {
        if (window.Logger) {
            window.Logger.warn('Mapa não inicializado. Não é possível exportar.');
        } else {
            console.warn('Mapa não inicializado. Não é possível exportar.');
        }
        return;
    }
    
    if (window.MapaExportacao) {
        window.MapaExportacao.exportarMapa(mapa, 'png')
            .then(() => {
                if (window.Logger) {
                    window.Logger.info('Mapa exportado com sucesso');
                }
            })
            .catch((error) => {
                if (window.Logger) {
                    window.Logger.error('Erro ao exportar mapa:', error);
                } else {
                    console.error('Erro ao exportar mapa:', error);
                }
                alert('Erro ao exportar mapa. Verifique se html2canvas está disponível.');
            });
    } else {
        alert('Funcionalidade de exportação não disponível. Recarregue a página.');
    }
}

/**
 * Calcula rota otimizada entre múltiplas coletores
 * @param {Array} coletores - Array de coletores para visitar
 * @param {Object} pontoInicial - Coordenadas do ponto inicial {lat, lon}
 * @returns {Array} Array de coordenadas ordenadas para rota otimizada
 */
function calcularRotaOtimizada(coletores, pontoInicial = null) {
    if (!coletores || coletores.length === 0) return [];
    
    // Filtrar coletores com coordenadas válidas
    const coletoresValidos = coletores.filter(c => 
        l.latitude && l.longitude && 
        !isNaN(parseFloat(l.latitude)) && 
        !isNaN(parseFloat(l.longitude))
    );
    
    if (coletoresValidos.length === 0) return [];
    
    // Se há apenas uma coletor, retornar direto
    if (coletoresValidos.length === 1) {
        return [[parseFloat(coletoresValidos[0].latitude), parseFloat(coletoresValidos[0].longitude)]];
    }
    
    // Converter para array de coordenadas
    const pontos = coletoresValidos.map(c => ({
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
            if (!ponto || !ponto.id) continue;
            if (!visitados.has(ponto.id)) {
                const lat = parseFloat(ponto.lat);
                const lon = parseFloat(ponto.lon);
                if (isNaN(lat) || isNaN(lon) || !isFinite(lat) || !isFinite(lon)) continue;
                
                const distancia = calcularDistancia(
                    atual.lat, atual.lon,
                    lat, lon
                );
                if (!isNaN(distancia) && isFinite(distancia) && distancia < menorDistancia) {
                    menorDistancia = distancia;
                    maisProximo = ponto;
                }
            }
        }
        
        if (maisProximo) {
            const lat = parseFloat(maisProximo.lat);
            const lon = parseFloat(maisProximo.lon);
            if (!isNaN(lat) && !isNaN(lon) && isFinite(lat) && isFinite(lon)) {
                rota.push([lat, lon]);
                visitados.add(maisProximo.id);
                atual = maisProximo;
            } else {
                break;
            }
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
 * Calcula distância de uma coletor até a sede
 * @param {Object} coletor - Objeto coletor com latitude e longitude
 * @returns {number|null} Distância em quilômetros ou null se não tiver coordenadas
 */
function calcularDistanciaSede(coletor) {
    if (!coletor || !coletor.latitude || !coletor.longitude) {
        return null;
    }
    
    const lat = parseFloat(coletor.latitude);
    const lon = parseFloat(coletor.longitude);
    
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
    
    // Remover controle anterior se existir
    if (routingControl && mapa) {
        try {
            mapa.removeControl(routingControl);
        } catch (e) {
            console.warn('Erro ao remover controle de rota anterior:', e);
        }
        routingControl = null;
    }
    
    // Limpar observer anterior e flags de formatação
    if (window.routingObserver) {
        window.routingObserver.disconnect();
        window.routingObserver = null;
    }
    const instrucoesAntigas = document.querySelectorAll('.leaflet-routing-instruction-text');
    instrucoesAntigas.forEach(function(instrucao) {
        if (instrucao) {
            instrucao.removeAttribute('data-formatado');
        }
    });
    
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
    });
    
    // Adicionar ao mapa com tratamento de erro
    try {
        routingControl.addTo(mapa);
    } catch (e) {
        console.error('Erro ao adicionar controle de rota ao mapa:', e);
        // Usar fallback
        if (waypointsOriginais && waypointsOriginais.length >= 2) {
            desenharRotaRobusta(waypointsOriginais[0], waypointsOriginais[1]);
        }
        return null;
    }
    
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
    
    // Sucesso - Leaflet Routing Machine desenha automaticamente, mas vamos garantir
    routingControl.on('routesfound', function(e) {
        console.log('Rota calculada com sucesso:', e.routes);
        if (e.routes && e.routes.length > 0) {
            const route = e.routes[0];
            
            // Validar estrutura da rota
            if (!route.summary) {
                console.warn('Rota retornada sem summary, usando fallback');
                if (waypointsOriginais && waypointsOriginais.length >= 2) {
                    desenharRotaRobusta(waypointsOriginais[0], waypointsOriginais[1]);
                }
                return;
            }
            
            // Verificar se route.coordinates existe (pode estar em route.coordinates ou route.waypoints)
            const temCoordenadas = route.coordinates && Array.isArray(route.coordinates) && route.coordinates.length >= 2;
            const temWaypoints = route.waypoints && Array.isArray(route.waypoints) && route.waypoints.length >= 2;
            
            if (!temCoordenadas && !temWaypoints) {
                console.warn('Rota sem coordenadas válidas, usando fallback');
                if (waypointsOriginais && waypointsOriginais.length >= 2) {
                    desenharRotaRobusta(waypointsOriginais[0], waypointsOriginais[1]);
                }
                return;
            }
            
            const distancia = (route.summary.totalDistance / 1000).toFixed(1);
            const tempo = Math.round(route.summary.totalTime / 60);
            console.log(`Distância: ${distancia}km | Tempo estimado: ${tempo}min`);
            
            // Formatar instruções após renderização (múltiplas tentativas com delays maiores)
            // O Leaflet Routing Machine pode demorar para renderizar instruções longas
            // IMPORTANTE: Executar DEPOIS da tradução do routing-pt.js
            // Mas também tentar ANTES para pegar elementos assim que forem criados
            setTimeout(() => {
                console.log('[routesfound] Tentativa 1 de formatação (100ms)');
                formatarInstrucoesRota();
            }, 100);
            setTimeout(() => {
                console.log('[routesfound] Tentativa 2 de formatação (300ms)');
                formatarInstrucoesRota();
            }, 300);
            setTimeout(() => {
                console.log('[routesfound] Tentativa 3 de formatação (600ms)');
                formatarInstrucoesRota();
            }, 600);
            setTimeout(() => {
                console.log('[routesfound] Tentativa 4 de formatação (1000ms)');
                formatarInstrucoesRota();
            }, 1000);
            setTimeout(() => {
                console.log('[routesfound] Tentativa 5 de formatação (2000ms)');
                formatarInstrucoesRota();
            }, 2000);
            setTimeout(() => {
                console.log('[routesfound] Tentativa 6 de formatação (3500ms)');
                formatarInstrucoesRota();
            }, 3500);
            
            // Observar mudanças no DOM para formatar novas instruções
            // Usar observer mais agressivo que reformata imediatamente quando detecta mudanças
            if (typeof MutationObserver !== 'undefined') {
                // Remover observer anterior se existir
                if (window.routingObserver) {
                    window.routingObserver.disconnect();
                }
                
                // Função para formatar quando detectar mudanças
                const formatarQuandoMudar = function() {
                    // Formatar IMEDIATAMENTE
                    formatarInstrucoesRota();
                    // Também formatar após pequenos delays para pegar mudanças subsequentes
                    setTimeout(() => formatarInstrucoesRota(), 10);
                    setTimeout(() => formatarInstrucoesRota(), 50);
                    setTimeout(() => formatarInstrucoesRota(), 100);
                };
                
                const observer = new MutationObserver(function(mutations) {
                    let shouldFormat = false;
                    mutations.forEach(function(mutation) {
                        // Qualquer mudança no container de rotas
                        if (mutation.target && mutation.target.classList) {
                            if (mutation.target.classList.contains('leaflet-routing-container') ||
                                mutation.target.classList.contains('leaflet-routing-instruction') ||
                                mutation.target.classList.contains('leaflet-routing-instruction-text') ||
                                mutation.target.closest('.leaflet-routing-container')) {
                                shouldFormat = true;
                            }
                        }
                        
                        // Nós adicionados
                        if (mutation.addedNodes.length > 0) {
                            mutation.addedNodes.forEach(function(node) {
                                if (node.nodeType === 1) {
                                    if (node.classList?.contains('leaflet-routing-instruction') ||
                                        node.classList?.contains('leaflet-routing-instruction-text') ||
                                        node.querySelector?.('.leaflet-routing-instruction-text')) {
                                        shouldFormat = true;
                                    }
                                } else if (node.nodeType === 3 && node.textContent && node.textContent.trim().length > 20) {
                                    // Nó de texto adicionado diretamente
                                    shouldFormat = true;
                                }
                            });
                        }
                        
                        // Mudanças no texto
                        if (mutation.type === 'childList' || mutation.type === 'characterData') {
                            shouldFormat = true;
                        }
                    });
                    
                    if (shouldFormat) {
                        formatarQuandoMudar();
                    }
                });
                
                // Observar o container de rotas com configuração mais abrangente
                const routingContainer = document.querySelector('.leaflet-routing-container');
                if (routingContainer) {
                    observer.observe(routingContainer, {
                        childList: true,
                        subtree: true,
                        characterData: true,
                        attributes: false
                    });
                    window.routingObserver = observer;
                } else {
                    // Se o container ainda não existe, aguardar e observar o body
                    setTimeout(() => {
                        const container = document.querySelector('.leaflet-routing-container');
                        if (container) {
                            observer.observe(container, {
                                childList: true,
                                subtree: true,
                                characterData: true
                            });
                            window.routingObserver = observer;
                        }
                    }, 500);
                }
                
                // Observar mudanças diretamente nos elementos de instrução quando forem criados
                const observarInstrucoes = function() {
                    const instrucoes = document.querySelectorAll('.leaflet-routing-instruction-text');
                    instrucoes.forEach(function(instrucao) {
                        if (instrucao && !instrucao.dataset.observado) {
                            // Interceptar propriedades de texto
                            interceptarPropriedadesTexto(instrucao);
                            
                            // Observar este elemento específico
                            observer.observe(instrucao, {
                                childList: true,
                                characterData: true,
                                subtree: true
                            });
                            
                            // Formatar imediatamente
                            formatarInstrucoesRota();
                            
                            instrucao.dataset.observado = 'true';
                        }
                    });
                };
                
                // Observar instruções periodicamente até que todas sejam encontradas
                let tentativasObservacao = 0;
                const intervaloObservacao = setInterval(() => {
                    observarInstrucoes();
                    tentativasObservacao++;
                    if (tentativasObservacao >= 30) { // 30 * 200ms = 6 segundos
                        clearInterval(intervaloObservacao);
                    }
                }, 200);
                
                // Também observar quando novos elementos são adicionados
                if (routingContainer) {
                    const observerNovosElementos = new MutationObserver(function(mutations) {
                        mutations.forEach(function(mutation) {
                            mutation.addedNodes.forEach(function(node) {
                                if (node.nodeType === 1) {
                                    let instrucoesNovas = [];
                                    if (node.querySelectorAll) {
                                        instrucoesNovas = Array.from(node.querySelectorAll('.leaflet-routing-instruction-text'));
                                    }
                                    if (node.classList && node.classList.contains('leaflet-routing-instruction-text')) {
                                        instrucoesNovas.push(node);
                                    }
                                    instrucoesNovas.forEach(function(instrucao) {
                                        if (instrucao && !instrucao._formatacaoInterceptada) {
                                            interceptarPropriedadesTexto(instrucao);
                                            formatarInstrucoesRota();
                                        }
                                    });
                                }
                            });
                        });
                    });
                    
                    observerNovosElementos.observe(routingContainer, {
                        childList: true,
                        subtree: true
                    });
                    
                    if (!window.routingObservers) window.routingObservers = [];
                    window.routingObservers.push(observerNovosElementos);
                }
            }
            
            // Formatação contínua em intervalos para garantir que persista
            // Limpar intervalo anterior se existir
            if (window.formatarInstrucoesInterval) {
                clearInterval(window.formatarInstrucoesInterval);
            }
            // Formatar a cada 500ms por 10 segundos após a rota ser encontrada
            let tentativas = 0;
            window.formatarInstrucoesInterval = setInterval(() => {
                formatarInstrucoesRota();
                tentativas++;
                if (tentativas >= 20) { // 20 * 500ms = 10 segundos
                    clearInterval(window.formatarInstrucoesInterval);
                    window.formatarInstrucoesInterval = null;
                }
            }, 500);
            
            // Leaflet Routing Machine desenha automaticamente, mas vamos garantir que está visível
            // Forçar redesenho do mapa após um pequeno delay
            setTimeout(() => {
                if (mapa && routingControl) {
                    mapa.invalidateSize();
                    // Garantir que a rota está visível ajustando o zoom
                    try {
                        // Tentar obter bounds da rota do controle
                        const routeLayer = routingControl._route;
                        if (routeLayer && routeLayer.getBounds) {
                            const bounds = routeLayer.getBounds();
                            if (bounds && bounds.isValid()) {
                                mapa.fitBounds(bounds, { padding: [50, 50] });
                            }
                        } else if (route.coordinates && route.coordinates.length > 0) {
                            const bounds = L.latLngBounds(route.coordinates);
                            if (bounds && bounds.isValid()) {
                                mapa.fitBounds(bounds, { padding: [50, 50] });
                            }
                        }
                    } catch (err) {
                        console.warn('Erro ao ajustar zoom da rota:', err);
                        // Usar waypoints originais como fallback
                        if (waypointsOriginais && waypointsOriginais.length >= 2) {
                            const bounds = L.latLngBounds(waypointsOriginais);
                            if (bounds && bounds.isValid()) {
                                mapa.fitBounds(bounds, { padding: [50, 50] });
                            }
                        }
                    }
                }
            }, 200);
            
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
    
    // Limpar observer de formatação se existir
    if (window.routingObserver) {
        window.routingObserver.disconnect();
        window.routingObserver = null;
    }
    
    // Limpar intervalo de formatação contínua
    if (window.formatarInstrucoesInterval) {
        clearInterval(window.formatarInstrucoesInterval);
        window.formatarInstrucoesInterval = null;
    }
    
    // Limpar flags de formatação para permitir reformatação na próxima rota
    const instrucoes = document.querySelectorAll('.leaflet-routing-instruction-text');
    instrucoes.forEach(function(instrucao) {
        if (instrucao) {
            instrucao.removeAttribute('data-formatado');
            instrucao.removeAttribute('data-observado');
        }
    });
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
 * @returns {Promise<L.Polyline|null>} Promise que resolve com a linha da rota
 */
async function desenharRotaRobusta(ponto1, ponto2) {
    if (!mapa) {
        console.error('Mapa não inicializado, não é possível desenhar rota');
        return null;
    }
    
    // Validar pontos de entrada
    if (!Array.isArray(ponto1) || !Array.isArray(ponto2) || 
        ponto1.length < 2 || ponto2.length < 2) {
        console.error('Pontos inválidos para desenhar rota');
        return null;
    }
    
    // Remover linha anterior se existir
    if (rotaLinha && mapa) {
        try {
            mapa.removeLayer(rotaLinha);
        } catch (e) {
            console.warn('Erro ao remover rota anterior:', e);
        }
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
            if (pontosRota && pontosRota.length >= 3) {
                tipoRota = 'Calculada';
            }
        } catch (error) {
            console.warn('Erro ao calcular rota robusta:', error);
        }
    }
    
    // Garantir que sempre temos uma rota válida com múltiplos pontos
    if (!pontosRota || pontosRota.length < 3) {
        console.log('Gerando rota intermediária com múltiplos pontos');
        // Gerar pontos intermediários para evitar linha reta
        if (typeof gerarRotaIntermediaria === 'function') {
            pontosRota = gerarRotaIntermediaria(ponto1, ponto2, 10);
        } else {
            // Fallback: criar pontos intermediários manualmente
            pontosRota = [ponto1];
            const numPontos = 10;
            for (let i = 1; i < numPontos - 1; i++) {
                const t = i / numPontos;
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
        const ponto1 = pontosRota[i];
        const ponto2 = pontosRota[i + 1];
        if (!ponto1 || !ponto2 || !Array.isArray(ponto1) || !Array.isArray(ponto2)) continue;
        
        const lat1 = parseFloat(ponto1[0]);
        const lon1 = parseFloat(ponto1[1]);
        const lat2 = parseFloat(ponto2[0]);
        const lon2 = parseFloat(ponto2[1]);
        
        if (isNaN(lat1) || isNaN(lon1) || isNaN(lat2) || isNaN(lon2)) continue;
        if (!isFinite(lat1) || !isFinite(lon1) || !isFinite(lat2) || !isFinite(lon2)) continue;
        
        const distancia = calcularDistancia(lat1, lon1, lat2, lon2);
        if (!isNaN(distancia) && isFinite(distancia)) {
            distanciaTotal += distancia;
        }
    }
    const distanciaFormatada = formatarDistancia(distanciaTotal);
    
    // Validar e normalizar pontos da rota antes de criar a linha
    const pontosValidos = pontosRota.filter(ponto => {
        if (!Array.isArray(ponto) || ponto.length < 2) return false;
        const lat = parseFloat(ponto[0]);
        const lon = parseFloat(ponto[1]);
        return !isNaN(lat) && !isNaN(lon) && isFinite(lat) && isFinite(lon) &&
               lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
    });
    
    if (pontosValidos.length < 2) {
        console.error('Não há pontos válidos suficientes para desenhar a rota');
        return null;
    }
    
    // Criar linha da rota com pontos validados
    try {
        rotaLinha = L.polyline(pontosValidos, {
            color: '#27ae60',
            weight: 5,
            opacity: 0.8,
            dashArray: tipoRota === 'Calculada' ? null : '10, 5' // Sólida se calculada, tracejada se aproximada
        }).addTo(mapa);
        
        // Adicionar popup na linha
        rotaLinha.bindPopup(`<strong>Rota ${tipoRota}</strong><br>Distância: ${distanciaFormatada}<br><small>${tipoRota === 'Calculada' ? 'Rota otimizada com dados reais' : 'Rota aproximada - serviço otimizado não disponível'}</small>`);
        
        // Garantir que a rota está visível
        setTimeout(() => {
            if (mapa && rotaLinha) {
                try {
                    const bounds = rotaLinha.getBounds();
                    if (bounds && bounds.isValid()) {
                        mapa.fitBounds(bounds, { padding: [50, 50] });
                    }
                } catch (e) {
                    console.warn('Erro ao ajustar zoom da rota:', e);
                }
            }
        }, 100);
        
        console.log(`Rota desenhada: ${pontosValidos.length} pontos, distância: ${distanciaFormatada}`);
        return rotaLinha;
    } catch (error) {
        console.error('Erro ao criar linha da rota:', error);
        return null;
    }
}

/**
 * Gera rota intermediária com múltiplos pontos (evita linha reta)
 * @param {Array} ponto1 - [lat, lon] ponto inicial
 * @param {Array} ponto2 - [lat, lon] ponto final
 * @param {number} numPontos - Número de pontos intermediários
 * @returns {Array} Array de coordenadas [lat, lon][]
 */
function gerarRotaIntermediaria(ponto1, ponto2, numPontos = 10) {
    // Validar pontos
    if (!Array.isArray(ponto1) || !Array.isArray(ponto2)) {
        return [ponto1, ponto2];
    }
    
    const lat1 = parseFloat(ponto1[0]);
    const lon1 = parseFloat(ponto1[1]);
    const lat2 = parseFloat(ponto2[0]);
    const lon2 = parseFloat(ponto2[1]);
    
    if (isNaN(lat1) || isNaN(lon1) || isNaN(lat2) || isNaN(lon2)) {
        return [ponto1, ponto2];
    }
    if (!isFinite(lat1) || !isFinite(lon1) || !isFinite(lat2) || !isFinite(lon2)) {
        return [ponto1, ponto2];
    }
    
    // Validar numPontos
    numPontos = Math.max(2, Math.min(50, Math.floor(numPontos)));
    
    const pontos = [ponto1];
    
    for (let i = 1; i < numPontos - 1; i++) {
        const t = i / numPontos;
        const lat = lat1 + (lat2 - lat1) * t;
        const lon = lon1 + (lon2 - lon1) * t;
        
        // Adicionar pequena variação para evitar linha perfeitamente reta
        const variacao = 0.001; // ~100m
        const variacaoLat = (Math.random() - 0.5) * variacao;
        const variacaoLon = (Math.random() - 0.5) * variacao;
        
        const latFinal = lat + variacaoLat;
        const lonFinal = lon + variacaoLon;
        
        // Validar coordenadas finais
        if (!isNaN(latFinal) && !isNaN(lonFinal) && 
            isFinite(latFinal) && isFinite(lonFinal) &&
            latFinal >= -90 && latFinal <= 90 &&
            lonFinal >= -180 && lonFinal <= 180) {
            pontos.push([latFinal, lonFinal]);
        }
    }
    
    pontos.push(ponto2);
    return pontos;
}

/**
 * Intercepta e formata texto antes de ser inserido no DOM
 * Sobrescreve textContent e innerHTML para aplicar formatação automaticamente
 */
function interceptarPropriedadesTexto(elemento) {
    if (!elemento || elemento._formatacaoInterceptada) return;
    
    // Interceptar textContent
    const originalTextContentDesc = Object.getOwnPropertyDescriptor(Node.prototype, 'textContent') || 
                                     Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'textContent');
    
    if (originalTextContentDesc) {
        const originalTextContent = originalTextContentDesc.set;
        Object.defineProperty(elemento, 'textContent', {
            get: function() {
                return originalTextContentDesc.get.call(this);
            },
            set: function(value) {
                // Se o valor não tem HTML formatado e é longo, formatar antes de definir
                if (value && typeof value === 'string' && value.length > 20 && 
                    !value.includes('<br>') && !value.includes('<span class="instrucao-')) {
                    const textoFormatado = formatarTextoInstrucao(value);
                    if (textoFormatado !== value) {
                        // Usar innerHTML em vez de textContent para preservar formatação
                        console.log('Interceptando textContent e formatando:', value.substring(0, 50) + '...');
                        this.innerHTML = textoFormatado;
                        this.dataset.formatado = 'true';
                        return;
                    }
                }
                originalTextContent.call(this, value);
            },
            configurable: true
        });
    }
    
    // Interceptar innerHTML também
    const originalInnerHTMLDesc = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
    if (originalInnerHTMLDesc) {
        const originalInnerHTML = originalInnerHTMLDesc.set;
        Object.defineProperty(elemento, 'innerHTML', {
            get: function() {
                return originalInnerHTMLDesc.get.call(this);
            },
            set: function(value) {
                // Se o valor não tem HTML formatado e é longo, formatar antes de definir
                if (value && typeof value === 'string' && value.length > 20 && 
                    !value.includes('<br>') && !value.includes('<span class="instrucao-')) {
                    const textoFormatado = formatarTextoInstrucao(value);
                    if (textoFormatado !== value) {
                        console.log('Interceptando innerHTML e formatando:', value.substring(0, 50) + '...');
                        originalInnerHTML.call(this, textoFormatado);
                        this.dataset.formatado = 'true';
                        return;
                    }
                }
                originalInnerHTML.call(this, value);
            },
            configurable: true
        });
    }
    
    // Interceptar appendChild para formatar texto quando for adicionado
    const originalAppendChild = elemento.appendChild;
    elemento.appendChild = function(child) {
        if (child && child.nodeType === 3 && child.textContent) {
            // É um nó de texto
            const texto = child.textContent;
            if (texto && texto.length > 20 && !texto.includes('<br>')) {
                const textoFormatado = formatarTextoInstrucao(texto);
                if (textoFormatado !== texto) {
                    // Criar elemento com HTML formatado
                    const temp = document.createElement('span');
                    temp.innerHTML = textoFormatado;
                    while (temp.firstChild) {
                        originalAppendChild.call(this, temp.firstChild);
                    }
                    return temp.firstChild || child;
                }
            }
        }
        return originalAppendChild.call(this, child);
    };
    
    elemento._formatacaoInterceptada = true;
}

/**
 * Formata texto de instrução (versão que retorna HTML)
 */
function formatarTextoInstrucao(texto) {
    if (!texto || texto.length < 20) return texto;
    
    let textoFormatado = texto;
    
    // CRÍTICO: Primeiro, adicionar espaços onde faltam
    textoFormatado = textoFormatado.replace(/([a-záàâãéèêíïóôõöúçñA-Z])(\d+\.?\d*\s*(?:km|m|min))/g, '$1 $2');
    textoFormatado = textoFormatado.replace(/(\d+\.?\d*)([a-záàâãéèêíïóôõöúçñA-Z])/g, '$1 $2');
    
    // Remover distâncias duplicadas
    textoFormatado = textoFormatado.replace(/\((\d+\.?\d*\s*(?:km|m|min))\)\s*\1/g, '($1)');
    
    // Separar distâncias/tempos
    textoFormatado = textoFormatado.replace(/(\d+\.?\d*\s*(?:km|m|min)),\s*(\d+\.?\d*\s*(?:km|m|min))/g, '$1<br>$2');
    textoFormatado = textoFormatado.replace(/([a-záàâãéèêíïóôõöúçñA-Z])\s*\((\d+\.?\d*\s*(?:km|m|min))\)/g, '$1<br>($2)');
    textoFormatado = textoFormatado.replace(/([a-záàâãéèêíïóôõöúçñA-Z0-9])\s*(\d+\.?\d*\s*(?:km|m|min))\s*([A-Z])/g, '$1<br>$2<br>$3');
    
    // Separar instruções
    textoFormatado = textoFormatado.replace(/\s+(Siga|Vire|Continue|Entre|Saia|Pegue|Faça|Mantenha|Keep|Merge|Enter|Turn|Go|Head|Take|Exit)\s+/gi, '<br>$1 ');
    
    // Criar HTML formatado
    const linhas = textoFormatado.split('<br>').filter(l => l.trim());
    if (linhas.length > 1) {
        let html = '';
        linhas.forEach((linha, index) => {
            linha = linha.trim();
            if (!linha) return;
            
            if (/^\(?\d+\.?\d*\s*(?:km|m|min)\)?$/.test(linha)) {
                html += `<span class="instrucao-distancia">${linha}</span>`;
            } else if (/^\d+\.?\d*\s*(?:km|m|min)/.test(linha)) {
                html += `<span class="instrucao-distancia">${linha}</span>`;
            } else {
                html += `<span class="instrucao-texto">${linha}</span>`;
            }
            
            if (index < linhas.length - 1) {
                html += '<br>';
            }
        });
        return html;
    }
    
    return textoFormatado;
}

/**
 * Formata as instruções de rota para exibição adequada
 * Esta função é chamada repetidamente para garantir que a formatação persista
 */
function formatarInstrucoesRota() {
    // O Leaflet Routing Machine pode renderizar de duas formas:
    // 1. Com elementos .leaflet-routing-instruction-text (estrutura completa)
    // 2. Com texto diretamente em .leaflet-routing-alt (estrutura simplificada)
    
    // Primeiro, tentar encontrar elementos .leaflet-routing-instruction-text
    let instrucoes = document.querySelectorAll('.leaflet-routing-instruction-text');
    
    // Se não encontrou, o texto pode estar diretamente em .leaflet-routing-alt
    if (instrucoes.length === 0) {
        const altContainer = document.querySelector('.leaflet-routing-alt');
        if (altContainer && altContainer.textContent && altContainer.textContent.trim().length > 20) {
            // O texto está diretamente no container, vamos formatá-lo
            console.log(`[formatarInstrucoesRota] Texto encontrado diretamente em .leaflet-routing-alt`);
            
            let texto = altContainer.textContent || altContainer.innerText || '';
            const htmlAtual = altContainer.innerHTML;
            
            // Verificar se já está formatado
            const jaFormatado = htmlAtual.includes('<br>') || htmlAtual.includes('<span class="instrucao-');
            
            if (!jaFormatado && texto && texto.length > 20) {
                console.log(`[formatarInstrucoesRota] Formatando texto diretamente no container`);
                
                // Aplicar formatação
                texto = texto.replace(/([a-záàâãéèêíïóôõöúçñA-Z])(\d+\.?\d*\s*(?:km|m|min))/g, '$1 $2');
                texto = texto.replace(/(\d+\.?\d*)([a-záàâãéèêíïóôõöúçñA-Z])/g, '$1 $2');
                texto = texto.replace(/\((\d+\.?\d*\s*(?:km|m|min))\)\s*\1/g, '($1)');
                texto = texto.replace(/([a-záàâãéèêíïóôõöúçñA-Z])\s*\((\d+\.?\d*\s*(?:km|m|min))\)/g, '$1\n($2)');
                texto = texto.replace(/([a-záàâãéèêíïóôõöúçñA-Z0-9])\s*(\d+\.?\d*\s*(?:km|m|min))\s*([A-Z])/g, '$1\n$2\n$3');
                texto = texto.replace(/(\d+\.?\d*\s*(?:km|m|min)),\s*(\d+\.?\d*\s*(?:km|m|min))/g, '$1\n$2');
                texto = texto.replace(/\s+(Siga|Vire|Continue|Entre|Saia|Pegue|Faça|Mantenha|Keep|Merge|Enter|Turn|Go|Head|Take|Exit)\s+/gi, '\n$1 ');
                texto = texto.replace(/\n\n+/g, '\n').trim();
                
                // Criar HTML formatado
                const linhas = texto.split('\n').filter(l => l.trim());
                if (linhas.length > 1) {
                    let htmlFormatado = '';
                    linhas.forEach((linha, index) => {
                        linha = linha.trim();
                        if (!linha) return;
                        
                        if (/^\(?\d+\.?\d*\s*(?:km|m|min)\)?$/.test(linha)) {
                            htmlFormatado += `<span class="instrucao-distancia">${linha}</span>`;
                        } else if (/^\d+\.?\d*\s*(?:km|m|min)/.test(linha)) {
                            htmlFormatado += `<span class="instrucao-distancia">${linha}</span>`;
                        } else {
                            htmlFormatado += `<span class="instrucao-texto">${linha}</span>`;
                        }
                        
                        if (index < linhas.length - 1) {
                            htmlFormatado += '<br>';
                        }
                    });
                    
                    altContainer.innerHTML = htmlFormatado;
                    altContainer.dataset.formatado = 'true';
                    console.log(`[formatarInstrucoesRota] HTML formatado aplicado ao container`);
                    return; // Já formatamos, não precisa continuar
                }
            }
        }
    }
    
    console.log(`[formatarInstrucoesRota] Encontradas ${instrucoes.length} instruções individuais`);
    
    instrucoes.forEach(function(instrucao, index) {
        if (!instrucao) return;
        
        // Interceptar propriedades de texto para este elemento
        interceptarPropriedadesTexto(instrucao);
        
        // Obter texto atual (pode ter sido alterado pelo Leaflet Routing Machine)
        let texto = instrucao.textContent || instrucao.innerText || '';
        const textoOriginal = texto;
        const htmlAtual = instrucao.innerHTML;
        
        // Debug: log do primeiro elemento para ver o que está acontecendo
        if (index === 0 && texto.length > 50) {
            console.log(`[formatarInstrucoesRota] Primeira instrução - Texto: "${texto.substring(0, 100)}..."`);
            console.log(`[formatarInstrucoesRota] HTML atual: "${htmlAtual.substring(0, 100)}..."`);
        }
        
        // Verificar se o HTML já está bem formatado (tem quebras de linha ou spans)
        const jaFormatado = htmlAtual.includes('<br>') || 
                           htmlAtual.includes('<span class="instrucao-');
        
        // Se já está formatado corretamente, verificar se não foi sobrescrito
        if (jaFormatado) {
            // Verificar se o texto ainda está formatado (não foi sobrescrito)
            const textoFormatado = htmlAtual.replace(/<[^>]*>/g, '').trim();
            // Se o texto mudou, significa que foi sobrescrito, então reformatar
            if (textoFormatado === textoOriginal && textoOriginal.length > 50) {
                // Parece que está formatado e não foi alterado, mas vamos verificar se precisa melhorar
                return;
            }
        }
        
        // Se o texto foi sobrescrito (não tem HTML formatado mas tem texto), reformatar
        // Se o texto não tem quebras de linha adequadas, tentar formatar
        if (!jaFormatado && texto && texto.length > 20) {
            console.log(`[formatarInstrucoesRota] Formatando instrução ${index + 1} - Texto não formatado detectado`);
            // CRÍTICO: Primeiro, adicionar espaços onde faltam (caso específico do problema)
            // Padrão: letra seguida de número sem espaço: "Samambaia14.8" -> "Samambaia 14.8"
            texto = texto.replace(/([a-záàâãéèêíïóôõöúçñA-Z])(\d+\.?\d*\s*(?:km|m|min))/g, '$1 $2');
            
            // Padrão: número seguido de letra sem espaço: "14.8km" -> "14.8 km"
            texto = texto.replace(/(\d+\.?\d*)([a-záàâãéèêíïóôõöúçñA-Z])/g, '$1 $2');
            
            // Remover distâncias duplicadas: "(67 m)67 m" -> "(67 m)"
            texto = texto.replace(/\((\d+\.?\d*\s*(?:km|m|min))\)\s*\1/g, '($1)');
            
            // Separar distâncias entre parênteses: "(67 m)" -> linha separada ANTES da instrução
            texto = texto.replace(/([a-záàâãéèêíïóôõöúçñA-Z])\s*\((\d+\.?\d*\s*(?:km|m|min))\)/g, '$1\n($2)');
            
            // Separar distâncias/tempos que aparecem sozinhos (mas não dentro de parênteses já processados)
            texto = texto.replace(/([a-záàâãéèêíïóôõöúçñA-Z0-9])\s*(\d+\.?\d*\s*(?:km|m|min))\s*([A-Z])/g, '$1\n$2\n$3');
            
            // Separar quando há vírgula seguida de distância/tempo: "14.8 km, 19 min" -> linhas separadas
            texto = texto.replace(/(\d+\.?\d*\s*(?:km|m|min)),\s*(\d+\.?\d*\s*(?:km|m|min))/g, '$1\n$2');
            
            // Separar instruções principais (verbos de ação em português) - com espaço antes
            texto = texto.replace(/\s+(Siga|Vire|Continue|Entre|Saia|Pegue|Faça|Mantenha)\s+/g, '\n$1 ');
            
            // Separar instruções em inglês (caso o servidor retorne em inglês)
            texto = texto.replace(/\s+(Keep|Merge|Enter|Turn|Go|Head|Take|Exit)\s+/gi, '\n$1 ');
            
            // Separar quando há "para" ou "em" seguido de nome de rua
            texto = texto.replace(/(para|em|to|onto)\s+([A-Z][a-záàâãéèêíïóôõöúçñA-Z0-9\s,]+?)(\s*\(|\s*\d|$)/g, '$1 $2\n$3');
            
            // Separar nomes de ruas longos seguidos de instruções
            texto = texto.replace(/([A-Z][a-záàâãéèêíïóôõöúçñA-Z0-9\s,]{10,}?)\s+(Siga|Vire|Continue|Entre|Saia|Pegue|Faça|Mantenha|Keep|Merge|Enter|Turn|Go|Head|Take|Exit)/gi, '$1\n$2');
            
            // Limpar múltiplas quebras de linha
            texto = texto.replace(/\n\n+/g, '\n');
            texto = texto.trim();
            
            // Criar estrutura HTML formatada
            const linhas = texto.split('\n').filter(l => l.trim());
            if (linhas.length > 1) {
                let htmlFormatado = '';
                linhas.forEach((linha, index) => {
                    linha = linha.trim();
                    if (!linha) return;
                    
                    // Detectar se é uma distância/tempo (formato: número + unidade, com ou sem parênteses)
                    if (/^\(?\d+\.?\d*\s*(?:km|m|min)\)?$/.test(linha)) {
                        htmlFormatado += `<span class="instrucao-distancia">${linha}</span>`;
                    } else if (/^\d+\.?\d*\s*(?:km|m|min)/.test(linha)) {
                        htmlFormatado += `<span class="instrucao-distancia">${linha}</span>`;
                    } else {
                        // É uma instrução ou nome de rua
                        htmlFormatado += `<span class="instrucao-texto">${linha}</span>`;
                    }
                    
                    if (index < linhas.length - 1) {
                        htmlFormatado += '<br>';
                    }
                });
                
                console.log(`[formatarInstrucoesRota] Aplicando HTML formatado na instrução ${index + 1}`);
                instrucao.innerHTML = htmlFormatado;
                instrucao.dataset.formatado = 'true';
            } else if (texto && texto !== textoOriginal) {
                // Se não conseguiu quebrar mas houve alguma mudança, aplicar
                console.log(`[formatarInstrucoesRota] Aplicando texto formatado (sem HTML) na instrução ${index + 1}`);
                instrucao.textContent = texto;
                instrucao.dataset.formatado = 'true';
            } else if (textoOriginal) {
                // Se não conseguiu formatar, marcar como formatado para evitar loops
                console.log(`[formatarInstrucoesRota] Não foi possível formatar instrução ${index + 1}, texto muito curto ou já formatado`);
                instrucao.dataset.formatado = 'true';
            }
        } else {
            // Marcar como formatado mesmo que seja curto
            instrucao.dataset.formatado = 'true';
        }
    });
    
    // Também formatar o cabeçalho da rota (distância total e tempo)
    const rotas = document.querySelectorAll('.leaflet-routing-alt');
    rotas.forEach(function(rota) {
        if (!rota) return;
        
        // Procurar por texto não formatado no cabeçalho
        const primeiroItem = rota.querySelector('.leaflet-routing-instruction:first-child');
        if (primeiroItem) {
            const instrucaoTexto = primeiroItem.querySelector('.leaflet-routing-instruction-text');
            if (instrucaoTexto && instrucaoTexto.dataset.formatado !== 'true') {
                let textoItem = instrucaoTexto.textContent || '';
                // Se o texto contém distância e tempo juntos sem formatação
                if (textoItem.match(/\d+\.?\d*\s*km.*\d+\s*min/) && !textoItem.includes('<br>')) {
                    const textoFormatado = textoItem.replace(/(\d+\.?\d*\s*km)/, '<strong>$1</strong>')
                                                    .replace(/(\d+\s*min)/, '<span class="instrucao-distancia">$1</span>');
                    instrucaoTexto.innerHTML = textoFormatado;
                    instrucaoTexto.dataset.formatado = 'true';
                } else {
                    instrucaoTexto.dataset.formatado = 'true';
                }
            }
        }
    });
}

/**
 * Calcula rota da sede até uma coletor específica
 * @param {number} coletorId - ID do coletor de destino
 */
function calcularRotaSede(coletorId) {
    if (!coletores || !coletores.length) {
        console.warn('Nenhuma coletor disponível');
        alert('Nenhuma coletor disponível no mapa');
        return;
    }
    
    const coletor = coletores.find(c => c.id === coletorId);
    if (!coletor || !coletor.latitude || !coletor.longitude) {
        alert('Coletor não encontrada ou sem coordenadas');
        return;
    }
    
    const lat = parseFloat(coletor.latitude);
    const lon = parseFloat(coletor.longitude);
    
    if (isNaN(lat) || isNaN(lon)) {
        alert('Coordenadas inválidas para esta coletor');
        return;
    }
    
    // Criar rota: Sede -> Coletor
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
                        // Marcador padrão para a coletor
                        return L.marker(wp.latLng);
                    }
                }
            });
            
            // Se falhou imediatamente, usar sistema robusto como fallback
            if (!resultado) {
                console.warn('Falha ao criar rota otimizada, usando sistema robusto');
                desenharRotaRobusta(waypoints[0], waypoints[1]).then(() => {
                    // Centralizar mapa na rota após desenhar
                    const bounds = L.latLngBounds(waypoints);
                    if (bounds && bounds.isValid()) {
                        mapa.fitBounds(bounds, { padding: [50, 50] });
                    }
                });
            } else {
                // Se sucesso, aguardar um pouco antes de centralizar (rota pode ainda estar sendo calculada)
                setTimeout(() => {
                    const bounds = L.latLngBounds(waypoints);
                    if (bounds && bounds.isValid()) {
                        mapa.fitBounds(bounds, { padding: [50, 50] });
                    }
                }, 500);
            }
        } catch (error) {
            console.error('Erro ao tentar criar rota:', error);
            // Usar sistema robusto como fallback
            desenharRotaRobusta(waypoints[0], waypoints[1]).then(() => {
                // Centralizar mapa na rota após desenhar
                const bounds = L.latLngBounds(waypoints);
                if (bounds && bounds.isValid()) {
                    mapa.fitBounds(bounds, { padding: [50, 50] });
                }
            });
        }
    } else {
        // Se Leaflet Routing Machine não estiver disponível, usar sistema robusto
        console.warn('Leaflet Routing Machine não disponível, usando sistema robusto');
        desenharRotaRobusta(waypoints[0], waypoints[1]).then(() => {
            // Centralizar mapa na rota após desenhar
            const bounds = L.latLngBounds(waypoints);
            if (bounds && bounds.isValid()) {
                mapa.fitBounds(bounds, { padding: [50, 50] });
            }
        });
    }
    
    console.log(`Rota calculada: ${SEDE_TRONIK.nome} -> Coletor #${coletorId}`);
}

/**
 * Filtra coletores por distância da sede
 * @param {Array} coletoresList - Lista de coletores
 * @param {string} filtroDistancia - Filtro de distância ('todas', 'ate-10', '10-20', '20-50', 'mais-50')
 * @returns {Array} Lista filtrada
 */
function filtrarPorDistancia(coletoresList, filtroDistancia = 'todas') {
    if (filtroDistancia === 'todas') {
        return coletoresList;
    }
    
    return coletoresList.filter(coletor => {
        const distancia = calcularDistanciaSede(coletor);
        if (distancia === null) {
            return false; // Excluir coletores sem coordenadas
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
 * Ordena coletores por distância da sede
 * @param {Array} coletoresList - Lista de coletores
 * @param {string} ordem - 'asc' (mais próxima primeiro) ou 'desc' (mais distante primeiro)
 * @returns {Array} Lista ordenada
 */
function ordenarPorDistancia(coletoresList, ordem = 'asc') {
    const coletoresComDistancia = coletoresList.map(coletor => ({
        coletor,
        distancia: calcularDistanciaSede(coletor)
    }));
    
    // Separar coletores com e sem coordenadas
    const comCoordenadas = coletoresComDistancia.filter(item => item.distancia !== null);
    const semCoordenadas = coletoresComDistancia.filter(item => item.distancia === null);
    
    // Ordenar por distância
    comCoordenadas.sort((a, b) => {
        if (ordem === 'asc') {
            return a.distancia - b.distancia;
        } else {
            return b.distancia - a.distancia;
        }
    });
    
    // Retornar: ordenadas + sem coordenadas
    return comCoordenadas.map(item => item.coletor).concat(semCoordenadas.map(item => item.coletor));
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
        destacarColetor: destacarColetor,
        atualizarMarcador: atualizarMarcadorColetor,
        limpar: limparMarcadores,
        ajustarZoomMarcadores: ajustarZoomMarcadores,
        exportar: exportarMapa,
        get mapa() { return mapa; } // Expor instância do mapa para redimensionamento
    };
    
    // Também expor globalmente para compatibilidade
    window.mapa = mapa;
}


