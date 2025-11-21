/*
Módulo de Cache - Dashboard-TRONIK
===================================
Gerencia cache de rotas e dados OSM usando IndexedDB
*/

const CACHE_DB_NAME = 'tronik_routing_cache';
const CACHE_VERSION = 1;
const CACHE_TTL = 3600000; // 1 hora em ms

let db = null;

/**
 * Inicializa o banco de dados IndexedDB
 * @returns {Promise<IDBDatabase>}
 */
async function inicializarCache() {
    if (db) return db;
    
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(CACHE_DB_NAME, CACHE_VERSION);
        
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
            db = request.result;
            resolve(db);
        };
        
        request.onupgradeneeded = (event) => {
            const database = event.target.result;
            
            // Object store para rotas
            if (!database.objectStoreNames.contains('rotas')) {
                const rotaStore = database.createObjectStore('rotas', { keyPath: 'id' });
                rotaStore.createIndex('timestamp', 'timestamp', { unique: false });
            }
            
            // Object store para dados OSM
            if (!database.objectStoreNames.contains('osm')) {
                const osmStore = database.createObjectStore('osm', { keyPath: 'id' });
                osmStore.createIndex('timestamp', 'timestamp', { unique: false });
            }
        };
    });
}

/**
 * Gera chave de cache para uma rota
 */
function gerarChaveRota(ponto1, ponto2) {
    const lat1 = ponto1[0].toFixed(6);
    const lon1 = ponto1[1].toFixed(6);
    const lat2 = ponto2[0].toFixed(6);
    const lon2 = ponto2[1].toFixed(6);
    return `rota_${lat1}_${lon1}_${lat2}_${lon2}`;
}

/**
 * Gera chave de cache para dados OSM
 */
function gerarChaveOSM(bbox) {
    return `osm_${bbox.south}_${bbox.west}_${bbox.north}_${bbox.east}`;
}

/**
 * Obtém rota do cache
 * @param {Array} ponto1 - [lat, lon]
 * @param {Array} ponto2 - [lat, lon]
 * @returns {Promise<Array|null>} Rota em cache ou null
 */
async function obterRotaCache(ponto1, ponto2) {
    try {
        await inicializarCache();
        const chave = gerarChaveRota(ponto1, ponto2);
        const transacao = db.transaction(['rotas'], 'readonly');
        const store = transacao.objectStore('rotas');
        
        return new Promise((resolve, reject) => {
            const request = store.get(chave);
            request.onsuccess = () => {
                const resultado = request.result;
                if (!resultado) {
                    resolve(null);
                    return;
                }
                
                // Verificar se expirou
                const agora = Date.now();
                if (agora - resultado.timestamp > CACHE_TTL) {
                    // Remover do cache
                    removerRotaCache(ponto1, ponto2);
                    resolve(null);
                    return;
                }
                
                resolve(resultado.rota);
            };
            request.onerror = () => reject(request.error);
        });
    } catch (error) {
        console.warn('Erro ao acessar cache:', error);
        return null;
    }
}

/**
 * Salva rota no cache
 * @param {Array} ponto1 - [lat, lon]
 * @param {Array} ponto2 - [lat, lon]
 * @param {Array} rota - Rota calculada
 */
async function salvarRotaCache(ponto1, ponto2, rota) {
    try {
        await inicializarCache();
        const chave = gerarChaveRota(ponto1, ponto2);
        const transacao = db.transaction(['rotas'], 'readwrite');
        const store = transacao.objectStore('rotas');
        
        await new Promise((resolve, reject) => {
            const request = store.put({
                id: chave,
                rota: rota,
                timestamp: Date.now()
            });
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    } catch (error) {
        console.warn('Erro ao salvar no cache:', error);
    }
}

/**
 * Remove rota do cache
 */
async function removerRotaCache(ponto1, ponto2) {
    try {
        await inicializarCache();
        const chave = gerarChaveRota(ponto1, ponto2);
        const transacao = db.transaction(['rotas'], 'readwrite');
        const store = transacao.objectStore('rotas');
        store.delete(chave);
    } catch (error) {
        console.warn('Erro ao remover do cache:', error);
    }
}

/**
 * Obtém dados OSM do cache
 */
async function obterOSMCache(bbox) {
    try {
        await inicializarCache();
        const chave = gerarChaveOSM(bbox);
        const transacao = db.transaction(['osm'], 'readonly');
        const store = transacao.objectStore('osm');
        
        return new Promise((resolve, reject) => {
            const request = store.get(chave);
            request.onsuccess = () => {
                const resultado = request.result;
                if (!resultado) {
                    resolve(null);
                    return;
                }
                
                // Verificar se expirou (dados OSM podem ficar mais tempo)
                const agora = Date.now();
                if (agora - resultado.timestamp > CACHE_TTL * 24) { // 24 horas
                    removerOSMCache(bbox);
                    resolve(null);
                    return;
                }
                
                resolve(resultado.dados);
            };
            request.onerror = () => reject(request.error);
        });
    } catch (error) {
        console.warn('Erro ao acessar cache OSM:', error);
        return null;
    }
}

/**
 * Salva dados OSM no cache
 */
async function salvarOSMCache(bbox, dados) {
    try {
        await inicializarCache();
        const chave = gerarChaveOSM(bbox);
        const transacao = db.transaction(['osm'], 'readwrite');
        const store = transacao.objectStore('osm');
        
        await new Promise((resolve, reject) => {
            const request = store.put({
                id: chave,
                dados: dados,
                timestamp: Date.now()
            });
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    } catch (error) {
        console.warn('Erro ao salvar OSM no cache:', error);
    }
}

/**
 * Remove dados OSM do cache
 */
async function removerOSMCache(bbox) {
    try {
        await inicializarCache();
        const chave = gerarChaveOSM(bbox);
        const transacao = db.transaction(['osm'], 'readwrite');
        const store = transacao.objectStore('osm');
        store.delete(chave);
    } catch (error) {
        console.warn('Erro ao remover OSM do cache:', error);
    }
}

/**
 * Limpa cache expirado
 */
async function limparCacheExpirado() {
    try {
        await inicializarCache();
        const agora = Date.now();
        
        // Limpar rotas expiradas
        const transacaoRotas = db.transaction(['rotas'], 'readwrite');
        const storeRotas = transacaoRotas.objectStore('rotas');
        const indexRotas = storeRotas.index('timestamp');
        const range = IDBKeyRange.upperBound(agora - CACHE_TTL);
        
        indexRotas.openCursor(range).onsuccess = (event) => {
            const cursor = event.target.result;
            if (cursor) {
                cursor.delete();
                cursor.continue();
            }
        };
        
        // Limpar OSM expirado
        const transacaoOSM = db.transaction(['osm'], 'readwrite');
        const storeOSM = transacaoOSM.objectStore('osm');
        const indexOSM = storeOSM.index('timestamp');
        const rangeOSM = IDBKeyRange.upperBound(agora - CACHE_TTL * 24);
        
        indexOSM.openCursor(rangeOSM).onsuccess = (event) => {
            const cursor = event.target.result;
            if (cursor) {
                cursor.delete();
                cursor.continue();
            }
        };
    } catch (error) {
        console.warn('Erro ao limpar cache:', error);
    }
}

// Exportar funções
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        obterRotaCache,
        salvarRotaCache,
        removerRotaCache,
        obterOSMCache,
        salvarOSMCache,
        removerOSMCache,
        limparCacheExpirado
    };
}



