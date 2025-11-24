/**
 * Icon Helper - Dashboard-TRONIK
 * ===============================
 * Função helper para renderizar ícones ao invés de emojis
 */

/**
 * Renderiza um ícone baseado no nome
 * @param {string} iconName - Nome do ícone (sem extensão)
 * @param {string} size - Tamanho ('small', 'medium', 'large', ou CSS válido)
 * @param {string} alt - Texto alternativo
 * @returns {string} HTML do ícone
 */
function renderIcon(iconName, size = 'medium', alt = '') {
    const sizeMap = {
        'small': '16px',
        'medium': '24px',
        'large': '32px',
        'xlarge': '48px'
    };
    
    const iconSize = sizeMap[size] || size || '24px';
    
    return `<img src="/static/icons/${iconName}.png" alt="${alt || iconName}" class="icon" style="width: ${iconSize}; height: ${iconSize}; vertical-align: middle; object-fit: contain;">`;
}

/**
 * Mapeamento de emojis para ícones
 */
const emojiToIcon = {
    '📊': 'grafico_icon',
    '💰': 'dinheiro_icon',
    '✅': 'check_icon',
    '👥': 'people_icon',
    '📋': 'prancheta_icon',
    '📞': 'telephone_icon',
    '📅': 'calendar',
    '🎯': 'alvo_icon',
    '⚠️': 'alert_icon',
    '🔄': 'refresh_icon',
    '↻': 'refresh_icon',
    '⚙️': 'prancheta_icon', // Usando prancheta como fallback para configurações
    '📈': 'grafico_icon',
    '📉': 'grafico_icon',
    '➕': 'check_icon', // Usando check como fallback para adicionar
    '⏳': 'calendar', // Usando calendar como fallback para pendente
    '📍': 'alvo_icon', // Usando alvo como fallback para localização
    '🔋': 'alert_icon', // Usando alert como fallback para bateria
    '✉️': 'prancheta_icon', // Usando prancheta como fallback para email
    '👁️': 'people_icon', // Usando people como fallback para visualizar
    '✓': 'check_icon'
};

/**
 * Substitui emojis por ícones em uma string HTML
 * @param {string} html - String HTML com emojis
 * @param {string} size - Tamanho dos ícones
 * @returns {string} HTML com ícones
 */
function replaceEmojisWithIcons(html, size = 'medium') {
    let result = html;
    for (const [emoji, iconName] of Object.entries(emojiToIcon)) {
        const iconHtml = renderIcon(iconName, size);
        result = result.replace(new RegExp(emoji.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), iconHtml);
    }
    return result;
}

