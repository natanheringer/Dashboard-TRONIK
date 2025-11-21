/*
Módulo de Suavização de Rotas - Dashboard-TRONIK
================================================
Aplica algoritmos de suavização para tornar rotas mais naturais
*/

/**
 * Aplica suavização Catmull-Rom Spline à rota
 * @param {Array} pontos - Array de pontos [lat, lon]
 * @param {number} numPontos - Número de pontos intermediários por segmento
 * @returns {Array} Rota suavizada
 */
function suavizarCatmullRom(pontos, numPontos = 3) {
    if (pontos.length < 2) return pontos;
    if (pontos.length === 2) return pontos;
    
    const suavizada = [pontos[0]]; // Primeiro ponto
    
    for (let i = 0; i < pontos.length - 1; i++) {
        const p0 = pontos[Math.max(0, i - 1)];
        const p1 = pontos[i];
        const p2 = pontos[i + 1];
        const p3 = pontos[Math.min(pontos.length - 1, i + 2)];
        
        // Gerar pontos intermediários
        for (let j = 1; j <= numPontos; j++) {
            const t = j / (numPontos + 1);
            const ponto = catmullRom(p0, p1, p2, p3, t);
            suavizada.push(ponto);
        }
    }
    
    suavizada.push(pontos[pontos.length - 1]); // Último ponto
    
    return suavizada;
}

/**
 * Calcula ponto na curva Catmull-Rom
 */
function catmullRom(p0, p1, p2, p3, t) {
    const t2 = t * t;
    const t3 = t2 * t;
    
    const lat = 0.5 * (
        (2 * p1[0]) +
        (-p0[0] + p2[0]) * t +
        (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
        (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
    );
    
    const lon = 0.5 * (
        (2 * p1[1]) +
        (-p0[1] + p2[1]) * t +
        (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
        (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
    );
    
    return [lat, lon];
}

/**
 * Remove pontos muito próximos (simplificação)
 * @param {Array} pontos - Array de pontos [lat, lon]
 * @param {number} distanciaMinima - Distância mínima entre pontos (km)
 * @returns {Array} Rota simplificada
 */
function simplificarRota(pontos, distanciaMinima = 0.05) {
    if (pontos.length <= 2) return pontos;
    
    const simplificada = [pontos[0]];
    
    for (let i = 1; i < pontos.length - 1; i++) {
        const dist = calcularDistancia(
            simplificada[simplificada.length - 1][0],
            simplificada[simplificada.length - 1][1],
            pontos[i][0],
            pontos[i][1]
        );
        
        if (dist >= distanciaMinima) {
            simplificada.push(pontos[i]);
        }
    }
    
    // Sempre incluir último ponto
    simplificada.push(pontos[pontos.length - 1]);
    
    return simplificada;
}

/**
 * Remove ângulos muito agudos (suavização de curvas)
 * @param {Array} pontos - Array de pontos [lat, lon]
 * @param {number} anguloMaximo - Ângulo máximo permitido (graus)
 * @returns {Array} Rota com curvas suavizadas
 */
function suavizarCurvas(pontos, anguloMaximo = 30) {
    if (pontos.length < 3) return pontos;
    
    const suavizada = [pontos[0]];
    
    for (let i = 1; i < pontos.length - 1; i++) {
        const p0 = pontos[i - 1];
        const p1 = pontos[i];
        const p2 = pontos[i + 1];
        
        const angulo = calcularAnguloEntrePontos(p0, p1, p2);
        
        if (Math.abs(angulo) > anguloMaximo) {
            // Criar ponto intermediário para suavizar curva
            const pontoIntermediario = [
                (p1[0] + p2[0]) / 2,
                (p1[1] + p2[1]) / 2
            ];
            suavizada.push(pontoIntermediario);
        }
        
        suavizada.push(p1);
    }
    
    suavizada.push(pontos[pontos.length - 1]);
    
    return suavizada;
}

/**
 * Calcula ângulo entre três pontos
 */
function calcularAnguloEntrePontos(p0, p1, p2) {
    const angulo1 = Math.atan2(p1[1] - p0[1], p1[0] - p0[0]) * 180 / Math.PI;
    const angulo2 = Math.atan2(p2[1] - p1[1], p2[0] - p1[0]) * 180 / Math.PI;
    
    let angulo = angulo2 - angulo1;
    
    // Normalizar para -180 a 180
    if (angulo > 180) angulo -= 360;
    if (angulo < -180) angulo += 360;
    
    return angulo;
}

/**
 * Aplica todas as técnicas de suavização
 * @param {Array} pontos - Array de pontos [lat, lon]
 * @param {Object} opcoes - Opções de suavização
 * @returns {Array} Rota suavizada
 */
function suavizarRotaCompleta(pontos, opcoes = {}) {
    if (!pontos || pontos.length < 2) return pontos;
    
    let rota = [...pontos];
    
    // Simplificar primeiro (remover pontos muito próximos)
    if (opcoes.simplificar !== false) {
        rota = simplificarRota(rota, opcoes.distanciaMinima || 0.05);
    }
    
    // Suavizar curvas
    if (opcoes.suavizarCurvas !== false) {
        rota = suavizarCurvas(rota, opcoes.anguloMaximo || 30);
    }
    
    // Aplicar spline
    if (opcoes.aplicarSpline !== false) {
        rota = suavizarCatmullRom(rota, opcoes.numPontosSpline || 2);
    }
    
    return rota;
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
        suavizarCatmullRom,
        simplificarRota,
        suavizarCurvas,
        suavizarRotaCompleta
    };
}


