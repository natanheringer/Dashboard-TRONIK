/**
 * Mapa Core - Dashboard-TRONIK
 * ==============================
 * Inicialização e configuração básica do mapa.
 */

const MapaCore = (function() {
    'use strict';
    
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
    
    // Instância do mapa
    let mapa = null;
    
    /**
     * Inicializa o mapa Leaflet
     */
    function inicializar(containerId, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) {
            if (window.Logger) {
                window.Logger.warn(`Container #${containerId} não encontrado para o mapa`);
            } else {
                console.warn(`Container #${containerId} não encontrado para o mapa`);
            }
            return null;
        }
        
        if (typeof L === 'undefined') {
            const errorMsg = 'Leaflet não está carregado. Verifique se o CDN está incluído.';
            if (window.Logger) {
                window.Logger.error(errorMsg);
            } else {
                console.error(errorMsg);
            }
            container.innerHTML = '<div class="mapa-erro">Erro: Biblioteca Leaflet não encontrada</div>';
            return null;
        }
        
        const config = {
            center: [options.lat || COORDENADAS_PADRAO.lat, options.lon || COORDENADAS_PADRAO.lon],
            zoom: options.zoom || COORDENADAS_PADRAO.zoom,
            ...options
        };
        
        mapa = L.map(containerId, {
            center: config.center,
            zoom: config.zoom,
            zoomControl: true
        });
        
        // Adicionar tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        }).addTo(mapa);
        
        return mapa;
    }
    
    /**
     * Obtém instância do mapa
     */
    function getMapa() {
        return mapa;
    }
    
    /**
     * Obtém coordenadas da sede
     */
    function getSedeTronik() {
        return SEDE_TRONIK;
    }
    
    return {
        inicializar,
        getMapa,
        getSedeTronik
    };
})();

// Exportar globalmente
window.MapaCore = MapaCore;

