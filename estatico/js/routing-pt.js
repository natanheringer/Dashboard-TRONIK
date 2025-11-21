/*
Localização Português (pt-BR) para Leaflet Routing Machine
==========================================================
Traduções das instruções de navegação para português brasileiro
Intercepta e traduz as instruções do Leaflet Routing Machine
*/

(function() {
    'use strict';
    
    // Aguardar Leaflet Routing Machine carregar
    function inicializarTraducao() {
        if (typeof L === 'undefined' || typeof L.Routing === 'undefined') {
            setTimeout(inicializarTraducao, 100);
            return;
        }
        
        // Criar formatter customizado em português
        if (L.Routing && L.Routing.Formatter) {
            const FormatterPT = L.Routing.Formatter.extend({
                formatInstruction: function(instruction) {
                    if (!instruction || !instruction.text) {
                        return '';
                    }
                    
                    // Traduzir instrução
                    let texto = traduzirInstrucao(instruction.text);
                    
                    // Adicionar distância se disponível
                    if (instruction.distance !== undefined) {
                        const distancia = this.formatDistance(instruction.distance);
                        texto += ' (' + distancia + ')';
                    }
                    
                    return texto;
                },
                
                formatDistance: function(distance) {
                    if (distance < 1000) {
                        return Math.round(distance) + ' m';
                    } else {
                        return (distance / 1000).toFixed(1) + ' km';
                    }
                }
            });
            
            // Registrar formatter em português
            L.Routing.FormatterPT = FormatterPT;
        }
        
        // Interceptar criação de controle de rota
        const originalControl = L.Routing.control;
        
        L.Routing.control = function(options) {
            // Forçar idioma português
            if (!options.language) {
                options.language = 'pt';
            }
            
            // Forçar unidades métricas
            if (!options.units) {
                options.units = 'metric';
            }
            
            // Usar formatter em português se disponível
            if (!options.formatter && L.Routing.FormatterPT) {
                options.formatter = new L.Routing.FormatterPT();
            }
            
            // Criar controle
            const control = originalControl.call(this, options);
            
            // Interceptar eventos para traduzir instruções após renderização
            control.on('routeselected', function(e) {
                setTimeout(function() {
                    traduzirInstrucoesNoDOM();
                }, 100);
            });
            
            control.on('routesfound', function(e) {
                setTimeout(function() {
                    traduzirInstrucoesNoDOM();
                }, 100);
            });
            
            return control;
        };
        
        // Copiar propriedades originais
        Object.keys(originalControl).forEach(function(key) {
            L.Routing.control[key] = originalControl[key];
        });
        
        // Função para traduzir instruções já renderizadas no DOM
        function traduzirInstrucoesNoDOM() {
            // Procurar por elementos com instruções
            const elementos = document.querySelectorAll('.leaflet-routing-instruction-text, .leaflet-routing-alt');
            
            elementos.forEach(function(el) {
                if (el.textContent && typeof traduzirInstrucao === 'function') {
                    const textoOriginal = el.textContent.trim();
                    const textoTraduzido = traduzirInstrucao(textoOriginal);
                    if (textoTraduzido !== textoOriginal) {
                        el.textContent = textoTraduzido;
                    }
                }
            });
        }
    }
    
    // Função para traduzir instruções
    window.traduzirInstrucao = function(instrucao) {
        if (!instrucao || typeof instrucao !== 'string') return instrucao;
        
        const traducoes = {
            // Direções básicas
            'Head': 'Siga',
            'Head east': 'Siga para leste',
            'Head west': 'Siga para oeste',
            'Head north': 'Siga para norte',
            'Head south': 'Siga para sul',
            'Head northeast': 'Siga para nordeste',
            'Head northwest': 'Siga para noroeste',
            'Head southeast': 'Siga para sudeste',
            'Head southwest': 'Siga para sudoeste',
            
            // Curvas
            'Turn left': 'Vire à esquerda',
            'Turn right': 'Vire à direita',
            'Turn sharp left': 'Vire acentuadamente à esquerda',
            'Turn sharp right': 'Vire acentuadamente à direita',
            'Turn slight left': 'Vire levemente à esquerda',
            'Turn slight right': 'Vire levemente à direita',
            
            // Continuar
            'Continue': 'Continue',
            'Continue straight': 'Continue em frente',
            'Go straight': 'Siga em frente',
            'Go': 'Siga',
            
            // Rotatórias
            'Enter the traffic circle': 'Entre na rotatória',
            'Exit the traffic circle': 'Saia da rotatória',
            'Take the 1st exit': 'Pegue a 1ª saída',
            'Take the 2nd exit': 'Pegue a 2ª saída',
            'Take the 3rd exit': 'Pegue a 3ª saída',
            'Take the 4th exit': 'Pegue a 4ª saída',
            'Take the 5th exit': 'Pegue a 5ª saída',
            'Take the 6th exit': 'Pegue a 6ª saída',
            'Take the 7th exit': 'Pegue a 7ª saída',
            'Take the 8th exit': 'Pegue a 8ª saída',
            'Take the 9th exit': 'Pegue a 9ª saída',
            'Take the 10th exit': 'Pegue a 10ª saída',
            
            // Retornos
            'Make a U-turn': 'Faça um retorno',
            'Make a sharp U-turn': 'Faça um retorno acentuado',
            
            // Destino
            'Reached your destination': 'Você chegou ao destino',
            'You have arrived': 'Você chegou',
            'Arrive at': 'Chegue em',
            
            // Preposições
            'on': 'em',
            'onto': 'para',
            'via': 'via',
            'and': 'e',
            'then': 'depois',
            'at': 'em'
        };
        
        // Traduzir instrução completa (ordem importa - frases completas primeiro)
        let texto = instrucao;
        
        // Ordenar por tamanho (maior primeiro) para evitar substituições parciais
        const chavesOrdenadas = Object.keys(traducoes).sort((a, b) => b.length - a.length);
        
        for (const chave of chavesOrdenadas) {
            const regex = new RegExp('\\b' + chave.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'gi');
            texto = texto.replace(regex, traducoes[chave]);
        }
        
        // Traduzir padrões com números (rotatórias)
        texto = texto.replace(/Take the (\d+)(st|nd|rd|th) exit/gi, function(match, num) {
            const numero = parseInt(num);
            return `Pegue a ${numero}ª saída`;
        });
        
        // Traduzir "via" quando aparece no início
        texto = texto.replace(/^Via /i, 'Via ');
        
        return texto;
    };
    
    // Inicializar quando DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', inicializarTraducao);
    } else {
        inicializarTraducao();
    }
})();

