/**
 * Utilitários de Formatação - Dashboard-TRONIK (Frontend)
 * =======================================================
 * Funções centralizadas para formatação de dados.
 */

/**
 * Escapa HTML para prevenir XSS
 */
function escapeHtml(text) {
    if (text === null || text === undefined) {
        return '';
    }
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

/**
 * Valida coordenadas (latitude e longitude)
 */
function validarCoordenadas(lat, lon) {
    if (typeof lat !== 'number' || typeof lon !== 'number') {
        return false;
    }
    if (isNaN(lat) || isNaN(lon)) {
        return false;
    }
    if (!isFinite(lat) || !isFinite(lon)) {
        return false;
    }
    if (lat < -90 || lat > 90) {
        return false;
    }
    if (lon < -180 || lon > 180) {
        return false;
    }
    return true;
}

/**
 * Valida número (não NaN, não Infinity)
 */
function validarNumero(valor) {
    if (typeof valor !== 'number') {
        return false;
    }
    if (isNaN(valor)) {
        return false;
    }
    if (!isFinite(valor)) {
        return false;
    }
    return true;
}

/**
 * Valida data (formato válido e range razoável)
 */
function validarData(dataStr) {
    if (!dataStr) {
        return false;
    }
    const data = new Date(dataStr);
    if (isNaN(data.getTime())) {
        return false;
    }
    // Validar range razoável (não antes de 2000, não depois de 2100)
    const min = new Date('2000-01-01');
    const max = new Date('2100-12-31');
    return data >= min && data <= max;
}

/**
 * Formata data para exibição
 */
function formatarData(dataISO, incluirHora = false) {
    if (!dataISO) return 'N/A';
    
    try {
        const data = new Date(dataISO);
        const opcoes = {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        };
        
        if (incluirHora) {
            opcoes.hour = '2-digit';
            opcoes.minute = '2-digit';
        }
        
        return data.toLocaleDateString('pt-BR', opcoes);
    } catch (e) {
        return dataISO;
    }
}

/**
 * Formata hora para exibição
 */
function formatarHora(dataISO) {
    if (!dataISO) return 'N/A';
    
    try {
        const data = new Date(dataISO);
        return data.toLocaleTimeString('pt-BR', {
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return dataISO;
    }
}

/**
 * Formata número com separadores
 */
function formatarNumero(numero, casasDecimais = 2) {
    if (numero === null || numero === undefined) {
        return '0';
    }
    
    return Number(numero).toLocaleString('pt-BR', {
        minimumFractionDigits: casasDecimais,
        maximumFractionDigits: casasDecimais
    });
}

/**
 * Formata moeda (R$)
 */
function formatarMoeda(valor) {
    if (valor === null || valor === undefined) {
        return 'R$ 0,00';
    }
    
    return Number(valor).toLocaleString('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    });
}

/**
 * Formata distância
 */
function formatarDistancia(distanciaKm) {
    if (distanciaKm === null || distanciaKm === undefined) {
        return 'N/A';
    }
    
    if (distanciaKm < 1) {
        return `${Math.round(distanciaKm * 1000)} m`;
    }
    
    return `${distanciaKm.toFixed(2)} km`;
}

/**
 * Formata percentual
 */
function formatarPercentual(valor, casasDecimais = 1) {
    if (valor === null || valor === undefined) {
        return '0%';
    }
    
    return `${Number(valor).toFixed(casasDecimais)}%`;
}

/**
 * Debounce para limitar chamadas de função
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Exportar globalmente
window.Formatacao = {
    escapeHtml,
    formatarData,
    formatarHora,
    formatarNumero,
    formatarMoeda,
    formatarDistancia,
    formatarPercentual,
    debounce,
    validarCoordenadas,
    validarNumero,
    validarData
};

