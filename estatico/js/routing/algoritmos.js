/*
Módulo de Algoritmos de Roteamento - Dashboard-TRONIK
=====================================================
Implementa algoritmos avançados de busca de caminho:
- A* (A-estrela)
- Dijkstra
- Bidirectional Dijkstra
*/

/**
 * Implementação do algoritmo A* (A-estrela)
 * @param {Object} grafo - Grafo {node: {vizinho: peso}}
 * @param {number|string} inicio - Nó inicial
 * @param {number|string} fim - Nó final
 * @param {Array} pontos - Array de coordenadas [lat, lon] para heurística
 * @param {Function} heuristica - Função heurística (ponto1, ponto2) => número
 * @returns {Array|null} Caminho do início ao fim ou null
 */
function aStar(grafo, inicio, fim, pontos = null, heuristica = null) {
    const gScore = {}; // Custo real do início até aqui
    const fScore = {}; // gScore + heurística
    const anteriores = {};
    const abertos = new Set([inicio]);
    const fechados = new Set();
    
    // Heurística padrão (distância Haversine)
    const h = heuristica || ((p1, p2) => {
        if (!pontos) return 0;
        const lat1 = pontos[p1]?.[0] || 0;
        const lon1 = pontos[p1]?.[1] || 0;
        const lat2 = pontos[p2]?.[0] || 0;
        const lon2 = pontos[p2]?.[1] || 0;
        return calcularDistanciaHaversine(lat1, lon1, lat2, lon2);
    });
    
    // Inicializar
    for (const node in grafo) {
        gScore[node] = Infinity;
        fScore[node] = Infinity;
    }
    gScore[inicio] = 0;
    fScore[inicio] = pontos ? h(inicio, fim) : 0;
    
    while (abertos.size > 0) {
        // Escolher nó com menor fScore
        let atual = null;
        let menorF = Infinity;
        
        for (const node of abertos) {
            if (fScore[node] < menorF) {
                menorF = fScore[node];
                atual = node;
            }
        }
        
        if (atual === null) break;
        
        if (atual === fim) {
            return reconstruirCaminho(anteriores, inicio, fim);
        }
        
        abertos.delete(atual);
        fechados.add(atual);
        
        // Explorar vizinhos
        if (grafo[atual]) {
            for (const vizinho in grafo[atual]) {
                if (fechados.has(vizinho)) continue;
                
                const tentativaG = gScore[atual] + grafo[atual][vizinho];
                
                if (!abertos.has(vizinho)) {
                    abertos.add(vizinho);
                } else if (tentativaG >= gScore[vizinho]) {
                    continue; // Caminho pior
                }
                
                anteriores[vizinho] = atual;
                gScore[vizinho] = tentativaG;
                fScore[vizinho] = gScore[vizinho] + (pontos ? h(vizinho, fim) : 0);
            }
        }
    }
    
    return null; // Sem caminho
}

/**
 * Implementação do algoritmo de Dijkstra
 * @param {Object} grafo - Grafo {node: {vizinho: peso}}
 * @param {number|string} inicio - Nó inicial
 * @param {number|string} fim - Nó final
 * @returns {Array|null} Caminho do início ao fim ou null
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
    
    return reconstruirCaminho(anteriores, inicio, fim);
}

/**
 * Implementação do algoritmo Bidirectional Dijkstra
 * @param {Object} grafo - Grafo {node: {vizinho: peso}}
 * @param {number|string} inicio - Nó inicial
 * @param {number|string} fim - Nó final
 * @returns {Array|null} Caminho do início ao fim ou null
 */
function bidirectionalDijkstra(grafo, inicio, fim) {
    // Busca do início
    const distInicio = {};
    const antInicio = {};
    const abertosInicio = new Set([inicio]);
    
    // Busca do fim
    const distFim = {};
    const antFim = {};
    const abertosFim = new Set([fim]);
    
    distInicio[inicio] = 0;
    distFim[fim] = 0;
    
    let melhorDistancia = Infinity;
    let pontoEncontro = null;
    
    while (abertosInicio.size > 0 && abertosFim.size > 0) {
        // Expandir do início
        const atualInicio = extrairMinimo(abertosInicio, distInicio);
        if (atualInicio !== null) {
            if (distFim[atualInicio] !== undefined && distFim[atualInicio] < Infinity) {
                const distTotal = distInicio[atualInicio] + distFim[atualInicio];
                if (distTotal < melhorDistancia) {
                    melhorDistancia = distTotal;
                    pontoEncontro = atualInicio;
                }
            }
            
            // Explorar vizinhos
            if (grafo[atualInicio]) {
                for (const vizinho in grafo[atualInicio]) {
                    const novaDist = distInicio[atualInicio] + grafo[atualInicio][vizinho];
                    if (distInicio[vizinho] === undefined || novaDist < distInicio[vizinho]) {
                        distInicio[vizinho] = novaDist;
                        antInicio[vizinho] = atualInicio;
                        abertosInicio.add(vizinho);
                    }
                }
            }
        }
        
        // Expandir do fim
        const atualFim = extrairMinimo(abertosFim, distFim);
        if (atualFim !== null) {
            if (distInicio[atualFim] !== undefined && distInicio[atualFim] < Infinity) {
                const distTotal = distInicio[atualFim] + distFim[atualFim];
                if (distTotal < melhorDistancia) {
                    melhorDistancia = distTotal;
                    pontoEncontro = atualFim;
                }
            }
            
            // Explorar vizinhos
            if (grafo[atualFim]) {
                for (const vizinho in grafo[atualFim]) {
                    const novaDist = distFim[atualFim] + grafo[atualFim][vizinho];
                    if (distFim[vizinho] === undefined || novaDist < distFim[vizinho]) {
                        distFim[vizinho] = novaDist;
                        antFim[vizinho] = atualFim;
                        abertosFim.add(vizinho);
                    }
                }
            }
        }
        
        // Se encontramos um caminho, parar
        if (pontoEncontro && melhorDistancia < Infinity) {
            return reconstruirBidirecional(antInicio, antFim, pontoEncontro, inicio, fim);
        }
        
        // Evitar loop infinito
        if (abertosInicio.size === 0 && abertosFim.size === 0) break;
    }
    
    return null;
}

/**
 * Reconstrói caminho a partir de mapa de anteriores
 */
function reconstruirCaminho(anteriores, inicio, fim) {
    const caminho = [];
    let atual = fim;
    
    while (atual !== null && atual !== undefined) {
        caminho.unshift(atual);
        atual = anteriores[atual];
        if (atual === inicio) {
            caminho.unshift(inicio);
            break;
        }
    }
    
    return caminho.length > 1 ? caminho : null;
}

/**
 * Reconstrói caminho bidirecional
 */
function reconstruirBidirecional(antInicio, antFim, pontoEncontro, inicio, fim) {
    const caminhoInicio = [];
    let atual = pontoEncontro;
    
    while (atual !== null && atual !== undefined && atual !== inicio) {
        caminhoInicio.unshift(atual);
        atual = antInicio[atual];
    }
    caminhoInicio.unshift(inicio);
    
    const caminhoFim = [];
    atual = antFim[pontoEncontro];
    while (atual !== null && atual !== undefined && atual !== fim) {
        caminhoFim.push(atual);
        atual = antFim[atual];
    }
    caminhoFim.push(fim);
    
    return caminhoInicio.concat(caminhoFim);
}

/**
 * Extrai nó com menor distância do conjunto
 */
function extrairMinimo(conjunto, distancias) {
    let minimo = null;
    let menorDist = Infinity;
    
    for (const node of conjunto) {
        if (distancias[node] !== undefined && distancias[node] < menorDist) {
            menorDist = distancias[node];
            minimo = node;
        }
    }
    
    if (minimo !== null) {
        conjunto.delete(minimo);
    }
    
    return minimo;
}

/**
 * Calcula distância Haversine entre dois pontos
 */
function calcularDistanciaHaversine(lat1, lon1, lat2, lon2) {
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
        aStar,
        dijkstra,
        bidirectionalDijkstra,
        calcularDistanciaHaversine
    };
}



