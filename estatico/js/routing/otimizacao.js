/*
Módulo de Otimização de Performance - Dashboard-TRONIK
=======================================================
Otimizações para rotas muito longas
*/

/**
 * Divide rota longa em segmentos menores para processamento
 * @param {Array} ponto1 - [lat, lon] ponto inicial
 * @param {Array} ponto2 - [lat, lon] ponto final
 * @param {number} maxDistancia - Distância máxima por segmento (km)
 * @returns {Array} Array de segmentos [[ponto1, ponto2], ...]
 */
function dividirRotaEmSegmentos(ponto1, ponto2, maxDistancia = 20) {
    const distanciaTotal = calcularDistancia(
        ponto1[0], ponto1[1],
        ponto2[0], ponto2[1]
    );
    
    // Se rota é curta, não precisa dividir
    if (distanciaTotal <= maxDistancia) {
        return [[ponto1, ponto2]];
    }
    
    // Calcular número de segmentos
    const numSegmentos = Math.ceil(distanciaTotal / maxDistancia);
    const segmentos = [];
    
    for (let i = 0; i < numSegmentos; i++) {
        const t1 = i / numSegmentos;
        const t2 = (i + 1) / numSegmentos;
        
        const p1 = [
            ponto1[0] + (ponto2[0] - ponto1[0]) * t1,
            ponto1[1] + (ponto2[1] - ponto1[1]) * t1
        ];
        
        const p2 = i === numSegmentos - 1 ? ponto2 : [
            ponto1[0] + (ponto2[0] - ponto1[0]) * t2,
            ponto1[1] + (ponto2[1] - ponto1[1]) * t2
        ];
        
        segmentos.push([p1, p2]);
    }
    
    return segmentos;
}

/**
 * Calcula rota longa usando processamento em paralelo de segmentos
 * @param {Array} ponto1 - [lat, lon] ponto inicial
 * @param {Array} ponto2 - [lat, lon] ponto final
 * @param {Function} calcularSegmento - Função para calcular cada segmento
 * @returns {Promise<Array>} Rota completa
 */
async function calcularRotaLonga(ponto1, ponto2, calcularSegmento) {
    const distanciaTotal = calcularDistancia(
        ponto1[0], ponto1[1],
        ponto2[0], ponto2[1]
    );
    
    // Se rota é curta (< 30km), calcular normalmente
    if (distanciaTotal < 30) {
        return await calcularSegmento(ponto1, ponto2);
    }
    
    // Dividir em segmentos
    const segmentos = dividirRotaEmSegmentos(ponto1, ponto2, 20);
    
    // Calcular cada segmento
    const rotasSegmentos = await Promise.all(
        segmentos.map(segmento => calcularSegmento(segmento[0], segmento[1]))
    );
    
    // Combinar rotas (remover pontos duplicados nas junções)
    const rotaCompleta = [rotasSegmentos[0][0]]; // Primeiro ponto
    
    for (let i = 0; i < rotasSegmentos.length; i++) {
        const segmento = rotasSegmentos[i];
        
        // Adicionar pontos do segmento (pular primeiro se não for o primeiro segmento)
        const inicio = i === 0 ? 0 : 1;
        for (let j = inicio; j < segmento.length; j++) {
            rotaCompleta.push(segmento[j]);
        }
    }
    
    return rotaCompleta;
}

/**
 * Simplifica rota removendo pontos muito próximos (reduz complexidade)
 * @param {Array} rota - Rota original
 * @param {number} distanciaMinima - Distância mínima entre pontos (km)
 * @returns {Array} Rota simplificada
 */
function simplificarRotaLonga(rota, distanciaMinima = 0.1) {
    if (rota.length <= 2) return rota;
    
    const simplificada = [rota[0]];
    
    for (let i = 1; i < rota.length - 1; i++) {
        const dist = calcularDistancia(
            simplificada[simplificada.length - 1][0],
            simplificada[simplificada.length - 1][1],
            rota[i][0],
            rota[i][1]
        );
        
        if (dist >= distanciaMinima) {
            simplificada.push(rota[i]);
        }
    }
    
    // Sempre incluir último ponto
    simplificada.push(rota[rota.length - 1]);
    
    return simplificada;
}

/**
 * Usa algoritmo mais eficiente baseado no tamanho da rota
 * @param {number} distancia - Distância em km
 * @returns {string} Nome do algoritmo recomendado
 */
function escolherAlgoritmoOtimizado(distancia) {
    if (distancia < 10) {
        return 'aStar'; // Rotas curtas: A* é ideal
    } else if (distancia < 30) {
        return 'bidirectional'; // Rotas médias: Bidirectional é mais eficiente
    } else {
        return 'dijkstra'; // Rotas longas: Dijkstra simples é mais rápido
    }
}

/**
 * Limita número de pontos intermediários baseado na distância
 * @param {number} distancia - Distância em km
 * @returns {number} Número recomendado de pontos
 */
function calcularNumPontosOtimizado(distancia) {
    // Base: 8 pontos para 10km
    // Escala: +2 pontos a cada 10km adicionais
    const base = 8;
    const adicional = Math.floor(distancia / 10) * 2;
    const max = 20; // Limite máximo
    
    return Math.min(base + adicional, max);
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
        dividirRotaEmSegmentos,
        calcularRotaLonga,
        simplificarRotaLonga,
        escolherAlgoritmoOtimizado,
        calcularNumPontosOtimizado
    };
}


