/*
Módulo de Integração OSM - Dashboard-TRONIK
===========================================
Integração com OpenStreetMap via Overpass API
*/

const OVERPASS_API = 'https://overpass-api.de/api/interpreter';
const OVERPASS_TIMEOUT = 25; // segundos

/**
 * Calcula bounding box ampliada entre dois pontos
 * @param {Array} ponto1 - [lat, lon]
 * @param {Array} ponto2 - [lat, lon]
 * @param {number} margem - Margem em graus (~0.01 = 1km)
 * @returns {Object} {north, south, east, west}
 */
function calcularBoundingBox(ponto1, ponto2, margem = 0.05) {
    const lats = [ponto1[0], ponto2[0]];
    const lons = [ponto1[1], ponto2[1]];
    
    return {
        north: Math.max(...lats) + margem,
        south: Math.min(...lats) - margem,
        east: Math.max(...lons) + margem,
        west: Math.min(...lons) - margem
    };
}

/**
 * Busca estradas no OSM usando Overpass API
 * @param {Array} ponto1 - [lat, lon] ponto inicial
 * @param {Array} ponto2 - [lat, lon] ponto final
 * @returns {Promise<Array>} Array de estradas (ways) do OSM
 */
async function buscarEstradasOSM(ponto1, ponto2) {
    const bbox = calcularBoundingBox(ponto1, ponto2, 0.05);
    
    // Verificar cache primeiro
    if (typeof obterOSMCache === 'function') {
        const cache = await obterOSMCache(bbox);
        if (cache) {
            console.log('Dados OSM obtidos do cache');
            return cache;
        }
    }
    
    // Query Overpass para buscar estradas
    const query = `
        [out:json][timeout:${OVERPASS_TIMEOUT}];
        (
          way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|unclassified|service)$"]
            (${bbox.south},${bbox.west},${bbox.north},${bbox.east});
        );
        out geom;
    `;
    
    try {
        const response = await fetch(OVERPASS_API, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `data=${encodeURIComponent(query)}`
        });
        
        if (!response.ok) {
            throw new Error(`Overpass API error: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Processar e filtrar resultados
        const estradas = data.elements
            .filter(el => el.type === 'way' && el.geometry)
            .map(el => ({
                id: el.id,
                nodes: el.nodes,
                geometry: el.geometry,
                tags: el.tags || {},
                tipo: el.tags?.highway || 'unknown'
            }));
        
        // Salvar no cache
        if (typeof salvarOSMCache === 'function') {
            await salvarOSMCache(bbox, estradas);
        }
        
        console.log(`Encontradas ${estradas.length} estradas no OSM`);
        return estradas;
        
    } catch (error) {
        console.warn('Erro ao buscar estradas OSM:', error);
        return [];
    }
}

/**
 * Constrói grafo a partir de dados OSM
 * @param {Array} estradas - Array de estradas do OSM
 * @returns {Object} Grafo {nodeId: {vizinhoId: peso}}
 */
function construirGrafoOSM(estradas) {
    const grafo = {};
    const nodeMap = new Map(); // nodeId -> coordenadas
    
    // Primeiro, mapear todos os nós
    for (const estrada of estradas) {
        for (const node of estrada.geometry) {
            if (!nodeMap.has(node.id)) {
                nodeMap.set(node.id, [node.lat, node.lon]);
            }
        }
    }
    
    // Criar conexões entre nós
    for (const estrada of estradas) {
        const geometry = estrada.geometry;
        const tipo = estrada.tags?.highway || 'unknown';
        
        // Peso baseado no tipo de via
        const pesoBase = obterPesoTipoVia(tipo);
        
        for (let i = 0; i < geometry.length - 1; i++) {
            const node1 = geometry[i].id;
            const node2 = geometry[i + 1].id;
            
            // Calcular distância real
            const coord1 = nodeMap.get(node1);
            const coord2 = nodeMap.get(node2);
            if (!coord1 || !coord2) continue;
            
            const distancia = calcularDistancia(
                coord1[0], coord1[1],
                coord2[0], coord2[1]
            );
            
            const peso = distancia * pesoBase;
            
            // Adicionar conexão bidirecional
            if (!grafo[node1]) grafo[node1] = {};
            if (!grafo[node2]) grafo[node2] = {};
            
            grafo[node1][node2] = peso;
            grafo[node2][node1] = peso;
        }
    }
    
    return { grafo, nodeMap };
}

/**
 * Obtém peso baseado no tipo de via
 */
function obterPesoTipoVia(tipo) {
    const pesos = {
        'motorway': 0.5,      // Rodovias = mais rápido
        'trunk': 0.6,
        'primary': 0.7,
        'secondary': 0.8,
        'tertiary': 0.9,
        'residential': 1.0,   // Ruas = normal
        'unclassified': 1.1,
        'service': 1.5        // Vias de serviço = mais lento
    };
    
    return pesos[tipo] || 1.0;
}

/**
 * Encontra nós OSM mais próximos aos pontos dados
 */
function encontrarNosProximos(ponto, nodeMap, maxDistancia = 0.5) {
    const nosProximos = [];
    
    for (const [nodeId, coords] of nodeMap.entries()) {
        const dist = calcularDistancia(
            ponto[0], ponto[1],
            coords[0], coords[1]
        );
        
        if (dist <= maxDistancia) {
            nosProximos.push({ nodeId, coords, dist });
        }
    }
    
    // Ordenar por distância
    nosProximos.sort((a, b) => a.dist - b.dist);
    
    return nosProximos;
}

/**
 * Calcula distância Haversine
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

// Exportar funções
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        buscarEstradasOSM,
        construirGrafoOSM,
        encontrarNosProximos,
        calcularBoundingBox
    };
}



