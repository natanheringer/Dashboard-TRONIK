/*
Módulo Router Principal - Dashboard-TRONIK
==========================================
Orquestra todos os módulos de roteamento para calcular rotas robustas
*/

/**
 * Calcula rota robusta usando múltiplas estratégias
 * @param {Array} ponto1 - [lat, lon] ponto inicial
 * @param {Array} ponto2 - [lat, lon] ponto final
 * @param {Object} opcoes - Opções de cálculo
 * @returns {Promise<Array>} Rota calculada [lat, lon][]
 */
async function calcularRotaRobusta(ponto1, ponto2, opcoes = {}) {
    // Validar entrada
    if (!ponto1 || !ponto2) {
        throw new Error('Pontos não fornecidos');
    }
    
    // Validar formato de ponto (pode ser array [lat, lon] ou objeto {lat, lon})
    let lat1, lon1, lat2, lon2;
    
    if (Array.isArray(ponto1)) {
        lat1 = parseFloat(ponto1[0]);
        lon1 = parseFloat(ponto1[1]);
    } else if (ponto1.lat !== undefined && ponto1.lon !== undefined) {
        lat1 = parseFloat(ponto1.lat);
        lon1 = parseFloat(ponto1.lon);
    } else {
        throw new Error('Formato inválido para ponto1');
    }
    
    if (Array.isArray(ponto2)) {
        lat2 = parseFloat(ponto2[0]);
        lon2 = parseFloat(ponto2[1]);
    } else if (ponto2.lat !== undefined && ponto2.lon !== undefined) {
        lat2 = parseFloat(ponto2.lat);
        lon2 = parseFloat(ponto2.lon);
    } else {
        throw new Error('Formato inválido para ponto2');
    }
    
    // Validar coordenadas
    const validarCoordenadas = window.Formatacao && window.Formatacao.validarCoordenadas 
        ? window.Formatacao.validarCoordenadas 
        : (lat, lon) => {
            if (typeof lat !== 'number' || typeof lon !== 'number') return false;
            if (isNaN(lat) || isNaN(lon)) return false;
            if (!isFinite(lat) || !isFinite(lon)) return false;
            if (lat < -90 || lat > 90) return false;
            if (lon < -180 || lon > 180) return false;
            return true;
        };
    
    if (!validarCoordenadas(lat1, lon1)) {
        throw new Error(`Coordenadas inválidas para ponto1: lat=${lat1}, lon=${lon1}`);
    }
    if (!validarCoordenadas(lat2, lon2)) {
        throw new Error(`Coordenadas inválidas para ponto2: lat=${lat2}, lon=${lon2}`);
    }
    
    // Normalizar pontos para formato [lat, lon]
    const p1 = [lat1, lon1];
    const p2 = [lat2, lon2];
    const {
        usarOSM = true,
        usarCache = true,
        algoritmo = null, // null = escolher automaticamente
        suavizar = true
    } = opcoes;
    
    // Calcular distância para otimizações
    const distancia = calcularDistancia(
        p1[0], p1[1],
        p2[0], p2[1]
    );
    
    // Validar distância
    if (isNaN(distancia) || !isFinite(distancia) || distancia < 0) {
        throw new Error('Erro ao calcular distância entre pontos');
    }
    
    // Escolher algoritmo otimizado se não especificado
    if (!algoritmo && typeof escolherAlgoritmoOtimizado === 'function') {
        opcoes.algoritmo = escolherAlgoritmoOtimizado(distancia);
    } else {
        opcoes.algoritmo = algoritmo || 'aStar';
    }
    
    // Para rotas muito longas, usar processamento em segmentos
    if (distancia > 30 && typeof calcularRotaLonga === 'function') {
        return await calcularRotaLonga(p1, p2, (p1Seg, p2Seg) => 
            calcularRotaRobusta(p1Seg, p2Seg, { ...opcoes, usarOSM: false }) // Desabilitar OSM em segmentos
        );
    }
    
    // 1. Verificar cache primeiro
    if (usarCache && typeof obterRotaCache === 'function') {
        try {
            const rotaCache = await obterRotaCache(p1, p2);
            if (rotaCache && Array.isArray(rotaCache) && rotaCache.length >= 2) {
                console.log('Rota obtida do cache');
                return rotaCache;
            }
        } catch (e) {
            console.warn('Erro ao obter rota do cache:', e);
        }
    }
    
    let rota = null;
    
    // 2. Tentar usar dados OSM
    if (usarOSM && typeof buscarEstradasOSM === 'function') {
        try {
            const estradas = await buscarEstradasOSM(ponto1, ponto2);
            
            if (estradas && estradas.length > 0) {
                const { grafo, nodeMap } = construirGrafoOSM(estradas);
                
                // Encontrar nós mais próximos aos pontos
                const nosInicio = encontrarNosProximos(ponto1, nodeMap, 0.5);
                const nosFim = encontrarNosProximos(ponto2, nodeMap, 0.5);
                
                if (nosInicio.length > 0 && nosFim.length > 0) {
                    const noInicio = nosInicio[0].nodeId;
                    const noFim = nosFim[0].nodeId;
                    
                    // Calcular rota usando algoritmo escolhido
                    let caminho = null;
                    if (algoritmo === 'aStar' && typeof aStar === 'function') {
                        caminho = aStar(grafo, noInicio, noFim);
                    } else if (algoritmo === 'bidirectional' && typeof bidirectionalDijkstra === 'function') {
                        caminho = bidirectionalDijkstra(grafo, noInicio, noFim);
                    } else if (typeof dijkstra === 'function') {
                        caminho = dijkstra(grafo, noInicio, noFim);
                    }
                    
                    if (caminho) {
                        // Converter nós para coordenadas
                        rota = caminho.map(nodeId => nodeMap.get(nodeId)).filter(Boolean);
                        
                        // Adicionar pontos originais no início e fim
                        rota.unshift(ponto1);
                        rota.push(ponto2);
                        
                        // Marcar que veio do OSM
                        rota.vemOSM = true;
                        
                        console.log('Rota calculada usando dados OSM');
                    }
                }
            }
        } catch (error) {
            console.warn('Erro ao usar OSM, usando heurísticas:', error);
        }
    }
    
    // 3. Fallback: Heurísticas geográficas
    if (!rota) {
        rota = calcularRotaComHeuristicas(ponto1, ponto2, algoritmo);
        console.log('Rota calculada usando heurísticas geográficas');
    }
    
    // 4. Suavizar rota
    if (suavizar && rota && typeof suavizarRotaCompleta === 'function') {
        rota = suavizarRotaCompleta(rota, opcoes.suavizacao || {});
    }
    
    // 5. Salvar no cache
    if (usarCache && rota && typeof salvarRotaCache === 'function') {
        await salvarRotaCache(ponto1, ponto2, rota);
    }
    
    // 6. Salvar rota prevista para aprendizado (se não veio do OSM)
    if (rota && typeof salvarRotaPrevista === 'function' && !rota.vemOSM) {
        salvarRotaPrevista(rota, ponto1, ponto2);
    }
    
    // Garantir que sempre retornamos uma rota válida com múltiplos pontos
    if (!rota || rota.length < 3) {
        console.warn('Rota não calculada, gerando rota intermediária');
        // Gerar pontos intermediários para evitar linha reta
        rota = gerarRotaIntermediaria(ponto1, ponto2, 12);
    }
    
    // Garantir que temos pelo menos 3 pontos
    if (rota.length < 3) {
        console.warn('Rota ainda tem poucos pontos, forçando geração de pontos intermediários');
        rota = gerarRotaIntermediaria(ponto1, ponto2, 12);
    }
    
    return rota;
}

/**
 * Calcula rota usando heurísticas geográficas
 */
function calcularRotaComHeuristicas(ponto1, ponto2, algoritmo = 'aStar') {
    // Calcular distância para otimização
    const distancia = calcularDistancia(
        ponto1[0], ponto1[1],
        ponto2[0], ponto2[1]
    );
    
    // Escolher número de pontos otimizado
    let numPontos = 12; // Padrão
    if (typeof calcularNumPontosOtimizado === 'function') {
        numPontos = calcularNumPontosOtimizado(distancia);
    }
    
    // Criar grade de pontos inteligente
    const pontosGrade = criarGradePontosInteligente(ponto1, ponto2, numPontos);
    
    // Criar grafo com heurísticas
    const grafo = criarGrafoComHeuristicas(pontosGrade);
    
    // Criar heurística completa
    const heuristica = typeof criarHeuristicaCompleta === 'function' 
        ? criarHeuristicaCompleta(pontosGrade)
        : null;
    
    // Calcular caminho
    let caminho = null;
    if (algoritmo === 'aStar' && typeof aStar === 'function') {
        caminho = aStar(grafo, 0, pontosGrade.length - 1, pontosGrade, heuristica);
    } else if (algoritmo === 'bidirectional' && typeof bidirectionalDijkstra === 'function') {
        caminho = bidirectionalDijkstra(grafo, 0, pontosGrade.length - 1);
    } else if (typeof dijkstra === 'function') {
        caminho = dijkstra(grafo, 0, pontosGrade.length - 1);
    }
    
    if (!caminho || caminho.length < 2) {
        // Se não encontrou caminho, retornar grade completa (melhor que linha reta)
        console.warn('Caminho não encontrado, usando grade completa');
        return pontosGrade;
    }
    
    // Converter índices para coordenadas
    const rota = caminho.map(idx => pontosGrade[idx]);
    
    // Garantir que temos pelo menos 3 pontos
    if (rota.length < 3) {
        return pontosGrade; // Retornar grade completa
    }
    
    return rota;
}

/**
 * Gera rota intermediária com múltiplos pontos (evita linha reta)
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
 * Cria grade de pontos inteligente (com variação controlada)
 */
function criarGradePontosInteligente(ponto1, ponto2, numPontos = 10) {
    const pontos = [ponto1];
    
    for (let i = 1; i < numPontos; i++) {
        const t = i / numPontos;
        const lat = ponto1[0] + (ponto2[0] - ponto1[0]) * t;
        const lon = ponto1[1] + (ponto2[1] - ponto1[1]) * t;
        
        // Variação controlada (não totalmente aleatória)
        const variacao = 0.003; // ~300m
        const angulo = Math.atan2(ponto2[1] - ponto1[1], ponto2[0] - ponto1[0]);
        const perpendicular = angulo + Math.PI / 2;
        
        // Variação perpendicular à direção principal
        const variacaoLat = Math.cos(perpendicular) * variacao * (Math.random() - 0.5);
        const variacaoLon = Math.sin(perpendicular) * variacao * (Math.random() - 0.5);
        
        pontos.push([lat + variacaoLat, lon + variacaoLon]);
    }
    
    pontos.push(ponto2);
    return pontos;
}

/**
 * Cria grafo aplicando heurísticas geográficas
 */
function criarGrafoComHeuristicas(pontos) {
    const grafo = {};
    
    for (let i = 0; i < pontos.length; i++) {
        grafo[i] = {};
        
        // Conectar com pontos próximos (até 4 pontos à frente)
        for (let j = i + 1; j < Math.min(i + 5, pontos.length); j++) {
            // Distância base
            let peso = calcularDistancia(
                pontos[i][0], pontos[i][1],
                pontos[j][0], pontos[j][1]
            );
            
            // Aplicar heurísticas
            if (typeof calcularPesoDensidade === 'function') {
                peso *= calcularPesoDensidade(pontos[i][0], pontos[i][1]);
            }
            
            if (typeof calcularPenalidadeArea === 'function') {
                peso += calcularPenalidadeArea(pontos[i][0], pontos[i][1]);
            }
            
            // Penalidade por direção (se tiver ponto anterior)
            if (i > 0 && typeof calcularPesoDirecao === 'function') {
                peso *= calcularPesoDirecao(
                    pontos[i - 1],
                    pontos[i],
                    pontos[j]
                );
            }
            
            grafo[i][j] = peso;
            
            // Grafo bidirecional
            if (!grafo[j]) grafo[j] = {};
            grafo[j][i] = peso;
        }
    }
    
    return grafo;
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
        calcularRotaRobusta,
        gerarRotaIntermediaria
    };
}

// Tornar funções disponíveis globalmente
if (typeof window !== 'undefined') {
    window.calcularRotaRobusta = calcularRotaRobusta;
    window.gerarRotaIntermediaria = gerarRotaIntermediaria;
}

