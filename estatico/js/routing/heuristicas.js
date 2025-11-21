/*
Módulo de Heurísticas Geográficas - Dashboard-TRONIK
====================================================
Implementa heurísticas para melhorar cálculo de rotas:
- Evitar áreas sem estradas (parques, rios)
- Preferir direções cardinais (N/S/E/O)
- Considerar densidade urbana
- Penalidades por elevação (futuro)
*/

// Áreas conhecidas de Brasília sem estradas (parques, lagos, etc.)
// Baseado em dados reais de Brasília/DF
const AREAS_EVITAR = [
    // Parques
    {lat: -15.8, lon: -47.9, raio: 0.015, tipo: 'parque', nome: 'Parque da Cidade', penalidade: 10},
    {lat: -15.78, lon: -47.88, raio: 0.008, tipo: 'parque', nome: 'Parque Olhos d\'Água', penalidade: 8},
    {lat: -15.82, lon: -47.92, raio: 0.010, tipo: 'parque', nome: 'Parque Nacional de Brasília', penalidade: 12},
    {lat: -15.79, lon: -47.87, raio: 0.006, tipo: 'parque', nome: 'Parque do Bosque', penalidade: 6},
    {lat: -15.83, lon: -47.91, raio: 0.007, tipo: 'parque', nome: 'Parque Águas Claras', penalidade: 7},
    {lat: -15.76, lon: -47.89, raio: 0.005, tipo: 'parque', nome: 'Parque Ecológico do Guará', penalidade: 5},
    
    // Lago Paranoá (área extensa)
    {lat: -15.85, lon: -47.95, raio: 0.020, tipo: 'lago', nome: 'Lago Paranoá (Norte)', penalidade: 15},
    {lat: -15.87, lon: -47.93, raio: 0.018, tipo: 'lago', nome: 'Lago Paranoá (Sul)', penalidade: 15},
    {lat: -15.84, lon: -47.97, raio: 0.012, tipo: 'lago', nome: 'Lago Paranoá (Oeste)', penalidade: 15},
    
    // Áreas verdes e reservas
    {lat: -15.88, lon: -47.90, raio: 0.010, tipo: 'reserva', nome: 'Reserva Ecológica', penalidade: 12},
    {lat: -15.75, lon: -47.85, raio: 0.008, tipo: 'parque', nome: 'Parque Ecológico Águas Claras', penalidade: 8},
    
    // Áreas rurais sem estradas principais
    {lat: -15.70, lon: -47.80, raio: 0.015, tipo: 'rural', nome: 'Área Rural (Noroeste)', penalidade: 5},
    {lat: -15.90, lon: -48.00, raio: 0.012, tipo: 'rural', nome: 'Área Rural (Sudoeste)', penalidade: 5},
];

// Centro de Brasília (referência para densidade)
const CENTRO_BRASILIA = {
    lat: -15.7942,
    lon: -47.8822
};

/**
 * Calcula penalidade por estar em área sem estradas
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @returns {number} Penalidade (0 = sem penalidade, maior = mais penalidade)
 */
function calcularPenalidadeArea(lat, lon) {
    let penalidade = 0;
    
    // Obter ajustes de aprendizado se disponível
    let multiplicador = 1.0;
    if (typeof obterAjustes === 'function') {
        const ajustes = obterAjustes();
        multiplicador = ajustes.penalidadeArea || 1.0;
    }
    
    for (const area of AREAS_EVITAR) {
        const dist = calcularDistancia(lat, lon, area.lat, area.lon);
        if (dist < area.raio) {
            // Penalidade cresce exponencialmente conforme se aproxima
            const fator = 1 - (dist / area.raio);
            const penalidadeBase = area.penalidade || 10;
            // Penalidade quadrática com base customizável e ajuste de aprendizado
            penalidade += fator * fator * penalidadeBase * multiplicador;
        }
    }
    
    return penalidade;
}

/**
 * Calcula peso baseado na densidade urbana
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @returns {number} Multiplicador de peso (0.8 = mais fácil, 1.3 = mais difícil)
 */
function calcularPesoDensidade(lat, lon) {
    const distCentro = calcularDistancia(
        lat, lon,
        CENTRO_BRASILIA.lat, CENTRO_BRASILIA.lon
    );
    
    let pesoBase = 1.0;
    
    // Dentro de 10km do centro = área urbana densa (mais estradas)
    if (distCentro < 10) {
        pesoBase = 0.8; // -20% peso (mais fácil navegar)
    }
    // Entre 10-20km = área suburbana
    else if (distCentro < 20) {
        pesoBase = 1.0; // peso normal
    }
    // Mais de 20km = área rural (menos estradas)
    else {
        pesoBase = 1.3; // +30% peso (mais difícil)
    }
    
    // Aplicar ajuste de aprendizado se disponível
    if (typeof obterAjustes === 'function') {
        const ajustes = obterAjustes();
        pesoBase *= (ajustes.pesoDensidade || 1.0);
    }
    
    return pesoBase;
}

/**
 * Calcula peso baseado na direção da rota
 * @param {Array} ponto1 - [lat, lon] ponto anterior
 * @param {Array} ponto2 - [lat, lon] ponto atual
 * @param {Array} ponto3 - [lat, lon] ponto próximo
 * @returns {number} Multiplicador de peso
 */
function calcularPesoDirecao(ponto1, ponto2, ponto3) {
    if (!ponto1 || !ponto2 || !ponto3) return 1.0;
    
    // Calcular ângulos
    const angulo1 = calcularAngulo(ponto1, ponto2);
    const angulo2 = calcularAngulo(ponto2, ponto3);
    const mudancaAngulo = Math.abs(angulo1 - angulo2);
    
    // Normalizar mudança de ângulo (0-180)
    const mudancaNormalizada = Math.min(mudancaAngulo, 360 - mudancaAngulo);
    
    let pesoBase = 1.0;
    
    // Penalizar mudanças bruscas de direção (> 45 graus)
    if (mudancaNormalizada > 45) {
        pesoBase = 1.0 + (mudancaNormalizada - 45) / 45 * 0.5; // Até +50% de peso
    }
    // Bonificar direções cardinais (N/S/E/O)
    else {
        const direcoesCardinais = [0, 90, 180, 270]; // graus
        const maisProximo = direcoesCardinais.reduce((min, dir) => {
            const dist1 = Math.abs(angulo2 - dir);
            const dist2 = Math.abs(angulo2 - min);
            return dist1 < dist2 ? dir : min;
        });
        
        const distCardinal = Math.min(
            Math.abs(angulo2 - maisProximo),
            360 - Math.abs(angulo2 - maisProximo)
        );
        
        if (distCardinal < 10) {
            pesoBase = 0.9; // -10% de peso (bonus por direção cardinal)
        }
    }
    
    // Aplicar ajuste de aprendizado se disponível
    if (typeof obterAjustes === 'function') {
        const ajustes = obterAjustes();
        pesoBase *= (ajustes.pesoDirecao || 1.0);
    }
    
    return pesoBase;
}

/**
 * Calcula ângulo de direção entre dois pontos
 * @param {Array} ponto1 - [lat, lon]
 * @param {Array} ponto2 - [lat, lon]
 * @returns {number} Ângulo em graus (0 = Norte, 90 = Leste, 180 = Sul, 270 = Oeste)
 */
function calcularAngulo(ponto1, ponto2) {
    const dLat = ponto2[0] - ponto1[0];
    const dLon = ponto2[1] - ponto1[1];
    
    // Converter para graus
    let angulo = Math.atan2(dLon, dLat) * 180 / Math.PI;
    
    // Normalizar para 0-360
    if (angulo < 0) angulo += 360;
    
    return angulo;
}

/**
 * Calcula distância entre dois pontos (Haversine)
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
 * Cria heurística completa para A*
 * @param {Array} pontos - Array de coordenadas [lat, lon]
 * @returns {Function} Função heurística (node1, node2) => número
 */
function criarHeuristicaCompleta(pontos) {
    return function(node1, node2) {
        if (!pontos || !pontos[node1] || !pontos[node2]) {
            return 0;
        }
        
        const p1 = pontos[node1];
        const p2 = pontos[node2];
        
        // Distância base (Haversine)
        let distancia = calcularDistancia(p1[0], p1[1], p2[0], p2[1]);
        
        // Aplicar multiplicador de densidade
        distancia *= calcularPesoDensidade(p1[0], p1[1]);
        
        // Adicionar penalidade de área
        distancia += calcularPenalidadeArea(p1[0], p1[1]);
        
        return distancia;
    };
}

// Exportar funções
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        calcularPenalidadeArea,
        calcularPesoDensidade,
        calcularPesoDirecao,
        calcularAngulo,
        criarHeuristicaCompleta,
        AREAS_EVITAR,
        CENTRO_BRASILIA
    };
}

