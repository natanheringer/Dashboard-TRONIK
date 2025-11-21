/*
Módulo de Aprendizado Adaptativo - Dashboard-TRONIK
====================================================
Aprende com rotas reais para melhorar heurísticas
*/

const DADOS_APRENDIZADO = {
    rotasReais: [], // Rotas calculadas pelo OSRM
    rotasPrevistas: [], // Rotas previstas pelo nosso sistema
    ajustes: {
        penalidadeArea: 1.0,
        pesoDensidade: 1.0,
        pesoDirecao: 1.0
    }
};

/**
 * Salva uma rota real (do OSRM) para aprendizado
 * @param {Array} rotaReal - Rota calculada pelo OSRM
 * @param {Array} ponto1 - Ponto inicial
 * @param {Array} ponto2 - Ponto final
 */
function salvarRotaReal(rotaReal, ponto1, ponto2) {
    if (!rotaReal || rotaReal.length < 2) return;
    
    DADOS_APRENDIZADO.rotasReais.push({
        rota: rotaReal,
        ponto1,
        ponto2,
        timestamp: Date.now(),
        distancia: calcularDistanciaTotal(rotaReal)
    });
    
    // Manter apenas últimas 100 rotas
    if (DADOS_APRENDIZADO.rotasReais.length > 100) {
        DADOS_APRENDIZADO.rotasReais.shift();
    }
}

/**
 * Salva uma rota prevista (do nosso sistema) para comparação
 * @param {Array} rotaPrevista - Rota calculada pelo nosso sistema
 * @param {Array} ponto1 - Ponto inicial
 * @param {Array} ponto2 - Ponto final
 */
function salvarRotaPrevista(rotaPrevista, ponto1, ponto2) {
    if (!rotaPrevista || rotaPrevista.length < 2) return;
    
    DADOS_APRENDIZADO.rotasPrevistas.push({
        rota: rotaPrevista,
        ponto1,
        ponto2,
        timestamp: Date.now(),
        distancia: calcularDistanciaTotal(rotaPrevista)
    });
    
    // Manter apenas últimas 100 rotas
    if (DADOS_APRENDIZADO.rotasPrevistas.length > 100) {
        DADOS_APRENDIZADO.rotasPrevistas.shift();
    }
}

/**
 * Compara rota prevista com rota real e ajusta heurísticas
 * @param {Array} rotaPrevista - Rota prevista
 * @param {Array} rotaReal - Rota real (OSRM)
 */
function compararEAjustar(rotaPrevista, rotaReal) {
    if (!rotaPrevista || !rotaReal || rotaPrevista.length < 2 || rotaReal.length < 2) {
        return;
    }
    
    // Calcular métricas de comparação
    const distanciaPrevista = calcularDistanciaTotal(rotaPrevista);
    const distanciaReal = calcularDistanciaTotal(rotaReal);
    const diferencaPercentual = Math.abs(distanciaPrevista - distanciaReal) / distanciaReal;
    
    // Calcular similaridade de trajetória
    const similaridade = calcularSimilaridadeTrajetoria(rotaPrevista, rotaReal);
    
    // Se diferença for grande (>20%), ajustar heurísticas
    if (diferencaPercentual > 0.2) {
        ajustarHeuristicas(distanciaPrevista, distanciaReal, similaridade);
    }
    
    console.log(`Aprendizado: Diferença ${(diferencaPercentual * 100).toFixed(1)}%, Similaridade ${(similaridade * 100).toFixed(1)}%`);
}

/**
 * Calcula similaridade entre duas trajetórias
 */
function calcularSimilaridadeTrajetoria(rota1, rota2) {
    // Usar distância de Hausdorff simplificada
    let maxDist = 0;
    
    for (const ponto1 of rota1) {
        let minDist = Infinity;
        for (const ponto2 of rota2) {
            const dist = calcularDistancia(
                ponto1[0], ponto1[1],
                ponto2[0], ponto2[1]
            );
            minDist = Math.min(minDist, dist);
        }
        maxDist = Math.max(maxDist, minDist);
    }
    
    // Normalizar (assumindo que rotas são < 50km)
    const similaridade = Math.max(0, 1 - (maxDist / 5)); // 5km = 0% similaridade
    return similaridade;
}

/**
 * Ajusta pesos das heurísticas baseado em erros
 */
function ajustarHeuristicas(distanciaPrevista, distanciaReal, similaridade) {
    const erro = distanciaPrevista - distanciaReal;
    const fatorErro = erro / distanciaReal;
    
    // Se previsto > real: heurísticas muito conservadoras (aumentar penalidades)
    // Se previsto < real: heurísticas muito otimistas (diminuir penalidades)
    
    if (fatorErro > 0.1) {
        // Rota prevista muito longa: diminuir penalidades
        DADOS_APRENDIZADO.ajustes.penalidadeArea *= 0.95;
        DADOS_APRENDIZADO.ajustes.pesoDensidade *= 0.98;
    } else if (fatorErro < -0.1) {
        // Rota prevista muito curta: aumentar penalidades
        DADOS_APRENDIZADO.ajustes.penalidadeArea *= 1.05;
        DADOS_APRENDIZADO.ajustes.pesoDensidade *= 1.02;
    }
    
    // Ajustar baseado em similaridade
    if (similaridade < 0.5) {
        // Trajetórias muito diferentes: ajustar peso de direção
        DADOS_APRENDIZADO.ajustes.pesoDirecao *= 1.05;
    }
    
    // Limitar ajustes (não deixar valores extremos)
    DADOS_APRENDIZADO.ajustes.penalidadeArea = Math.max(0.5, Math.min(2.0, DADOS_APRENDIZADO.ajustes.penalidadeArea));
    DADOS_APRENDIZADO.ajustes.pesoDensidade = Math.max(0.5, Math.min(2.0, DADOS_APRENDIZADO.ajustes.pesoDensidade));
    DADOS_APRENDIZADO.ajustes.pesoDirecao = Math.max(0.5, Math.min(2.0, DADOS_APRENDIZADO.ajustes.pesoDirecao));
}

/**
 * Obtém ajustes atuais para aplicar nas heurísticas
 */
function obterAjustes() {
    return { ...DADOS_APRENDIZADO.ajustes };
}

/**
 * Processa todas as rotas salvas para aprendizado em lote
 */
function processarAprendizadoEmLote() {
    if (DADOS_APRENDIZADO.rotasReais.length === 0 || DADOS_APRENDIZADO.rotasPrevistas.length === 0) {
        return;
    }
    
    // Comparar rotas com pontos similares
    for (const rotaReal of DADOS_APRENDIZADO.rotasReais) {
        for (const rotaPrevista of DADOS_APRENDIZADO.rotasPrevistas) {
            // Verificar se são rotas similares (mesmos pontos de origem/destino)
            const distancia1 = calcularDistancia(
                rotaReal.ponto1[0], rotaReal.ponto1[1],
                rotaPrevista.ponto1[0], rotaPrevista.ponto1[1]
            );
            const distancia2 = calcularDistancia(
                rotaReal.ponto2[0], rotaReal.ponto2[1],
                rotaPrevista.ponto2[0], rotaPrevista.ponto2[1]
            );
            
            // Se pontos são próximos (< 500m), comparar rotas
            if (distancia1 < 0.5 && distancia2 < 0.5) {
                compararEAjustar(rotaPrevista.rota, rotaReal.rota);
            }
        }
    }
}

/**
 * Calcula distância total de uma rota
 */
function calcularDistanciaTotal(rota) {
    let total = 0;
    for (let i = 0; i < rota.length - 1; i++) {
        total += calcularDistancia(
            rota[i][0], rota[i][1],
            rota[i + 1][0], rota[i + 1][1]
        );
    }
    return total;
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

/**
 * Salva dados de aprendizado no localStorage
 */
function salvarAprendizado() {
    try {
        localStorage.setItem('tronik_aprendizado', JSON.stringify(DADOS_APRENDIZADO.ajustes));
    } catch (error) {
        console.warn('Erro ao salvar aprendizado:', error);
    }
}

/**
 * Carrega dados de aprendizado do localStorage
 */
function carregarAprendizado() {
    try {
        const dados = localStorage.getItem('tronik_aprendizado');
        if (dados) {
            const ajustes = JSON.parse(dados);
            DADOS_APRENDIZADO.ajustes = { ...DADOS_APRENDIZADO.ajustes, ...ajustes };
        }
    } catch (error) {
        console.warn('Erro ao carregar aprendizado:', error);
    }
}

// Carregar aprendizado ao inicializar
if (typeof window !== 'undefined') {
    carregarAprendizado();
    
    // Processar aprendizado em lote a cada 5 minutos
    setInterval(() => {
        processarAprendizadoEmLote();
        salvarAprendizado();
    }, 300000); // 5 minutos
}

// Exportar funções
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        salvarRotaReal,
        salvarRotaPrevista,
        compararEAjustar,
        obterAjustes,
        processarAprendizadoEmLote
    };
}


