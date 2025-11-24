/**
 * Utilitários de Segurança - Dashboard-TRONIK
 * ===========================================
 * Funções para prevenir XSS e outras vulnerabilidades no frontend.
 */

/**
 * Escapa HTML para prevenir XSS
 * @param {string} str - String a escapar
 * @returns {string} String escapada
 */
function escapeHtml(str) {
    if (typeof str !== 'string') {
        return String(str);
    }
    
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '/': '&#x2F;'
    };
    
    return str.replace(/[&<>"'/]/g, (char) => map[char]);
}

/**
 * Cria um elemento de forma segura
 * @param {string} tag - Tag do elemento
 * @param {Object} attributes - Atributos do elemento
 * @param {string|Node} content - Conteúdo (será escapado se string)
 * @returns {HTMLElement} Elemento criado
 */
function createSafeElement(tag, attributes = {}, content = '') {
    const element = document.createElement(tag);
    
    // Adicionar atributos de forma segura
    for (const [key, value] of Object.entries(attributes)) {
        if (key === 'innerHTML' || key === 'textContent') {
            continue; // Será tratado separadamente
        }
        
        // Para atributos que podem conter código, validar
        if (key.startsWith('on')) {
            console.warn(`Atributo de evento ignorado por segurança: ${key}`);
            continue;
        }
        
        // Escapar valores de atributos
        if (typeof value === 'string') {
            element.setAttribute(key, escapeHtml(value));
        } else {
            element.setAttribute(key, value);
        }
    }
    
    // Adicionar conteúdo de forma segura
    if (content) {
        if (typeof content === 'string') {
            element.textContent = content; // textContent escapa automaticamente
        } else if (content instanceof Node) {
            element.appendChild(content);
        } else if (Array.isArray(content)) {
            content.forEach(item => {
                if (typeof item === 'string') {
                    element.appendChild(document.createTextNode(item));
                } else if (item instanceof Node) {
                    element.appendChild(item);
                }
            });
        }
    }
    
    return element;
}

/**
 * Renderiza HTML de forma segura (apenas para conteúdo confiável)
 * @param {HTMLElement} container - Container onde renderizar
 * @param {string} html - HTML a renderizar (deve ser de fonte confiável)
 * @param {boolean} sanitize - Se true, sanitiza o HTML (padrão: false)
 */
function safeInnerHTML(container, html, sanitize = false) {
    if (!container) return;
    
    if (sanitize) {
        // Sanitização básica: remover scripts e eventos
        const temp = document.createElement('div');
        temp.textContent = html; // Isso escapa tudo
        container.textContent = html; // Usar textContent em vez de innerHTML
        return;
    }
    
    // Apenas para conteúdo confiável (ex: templates do próprio sistema)
    container.innerHTML = html;
}

/**
 * Cria um elemento option de forma segura
 * @param {string} value - Valor da opção
 * @param {string} text - Texto da opção
 * @param {boolean} selected - Se deve estar selecionado
 * @returns {HTMLOptionElement} Elemento option
 */
function createSafeOption(value, text, selected = false) {
    const option = document.createElement('option');
    option.value = escapeHtml(String(value));
    option.textContent = escapeHtml(String(text));
    if (selected) {
        option.selected = true;
    }
    return option;
}

/**
 * Valida e sanitiza entrada do usuário
 * @param {string} input - Entrada a validar
 * @param {number} maxLength - Tamanho máximo
 * @returns {string} Entrada sanitizada
 */
function sanitizeInput(input, maxLength = 1000) {
    if (typeof input !== 'string') {
        return '';
    }
    
    // Remover caracteres de controle
    let sanitized = input.replace(/[\x00-\x1f\x7f-\x9f]/g, '');
    
    // Limitar tamanho
    if (maxLength && sanitized.length > maxLength) {
        sanitized = sanitized.substring(0, maxLength);
    }
    
    return sanitized.trim();
}

/**
 * Valida se uma string é um ID numérico válido
 * @param {*} value - Valor a validar
 * @returns {boolean} True se válido
 */
function isValidId(value) {
    const num = Number(value);
    return !isNaN(num) && num > 0 && Number.isInteger(num);
}

/**
 * Valida se uma string é um email válido
 * @param {string} email - Email a validar
 * @returns {boolean} True se válido
 */
function isValidEmail(email) {
    if (typeof email !== 'string') return false;
    const pattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return pattern.test(email);
}

// Exportar para uso global
if (typeof window !== 'undefined') {
    window.SecurityUtils = {
        escapeHtml,
        createSafeElement,
        safeInnerHTML,
        createSafeOption,
        sanitizeInput,
        isValidId,
        isValidEmail
    };
}

