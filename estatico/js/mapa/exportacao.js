/**
 * Exportação de Mapa - Dashboard-TRONIK
 * ======================================
 * Funcionalidades para exportar mapa como imagem (PNG/PDF).
 */

const MapaExportacao = (function() {
    'use strict';
    
    /**
     * Exporta mapa como PNG
     * @param {L.Map} mapa - Instância do mapa Leaflet
     * @param {string} nomeArquivo - Nome do arquivo (opcional)
     * @returns {Promise<Blob>} Blob da imagem PNG
     */
    async function exportarComoPNG(mapa, nomeArquivo = 'mapa_tronik.png') {
        if (!mapa) {
            throw new Error('Mapa não inicializado');
        }
        
        return new Promise((resolve, reject) => {
            try {
                // Usar html2canvas se disponível
                if (typeof html2canvas !== 'undefined') {
                    const container = mapa.getContainer();
                    html2canvas(container, {
                        useCORS: true,
                        logging: false,
                        backgroundColor: '#ffffff'
                    }).then(canvas => {
                        canvas.toBlob((blob) => {
                            if (blob) {
                                resolve(blob);
                            } else {
                                reject(new Error('Erro ao criar blob da imagem'));
                            }
                        }, 'image/png');
                    }).catch(reject);
                } else {
                    // Fallback: usar leaflet-image
                    if (typeof L.imageUtil !== 'undefined') {
                        L.imageUtil.print(mapa, (dataURL) => {
                            // Converter dataURL para Blob
                            fetch(dataURL)
                                .then(res => res.blob())
                                .then(resolve)
                                .catch(reject);
                        });
                    } else {
                        reject(new Error('Biblioteca de exportação não disponível. Adicione html2canvas ou leaflet-image.'));
                    }
                }
            } catch (error) {
                reject(error);
            }
        });
    }
    
    /**
     * Faz download de um blob como arquivo
     */
    function downloadBlob(blob, nomeArquivo) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = nomeArquivo;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }
    
    /**
     * Exporta mapa e faz download
     */
    async function exportarMapa(mapa, formato = 'png', nomeArquivo = null) {
        try {
            if (window.Logger) {
                window.Logger.info('Iniciando exportação do mapa...');
            }
            
            if (!nomeArquivo) {
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
                nomeArquivo = `mapa_tronik_${timestamp}.${formato}`;
            }
            
            let blob;
            if (formato === 'png') {
                blob = await exportarComoPNG(mapa, nomeArquivo);
            } else {
                throw new Error(`Formato ${formato} não suportado`);
            }
            
            downloadBlob(blob, nomeArquivo);
            
            if (window.Logger) {
                window.Logger.info(`Mapa exportado com sucesso: ${nomeArquivo}`);
            }
            
            return blob;
        } catch (error) {
            if (window.Logger) {
                window.Logger.error('Erro ao exportar mapa:', error);
            } else {
                console.error('Erro ao exportar mapa:', error);
            }
            throw error;
        }
    }
    
    return {
        exportarMapa,
        exportarComoPNG
    };
})();

// Exportar globalmente
window.MapaExportacao = MapaExportacao;

