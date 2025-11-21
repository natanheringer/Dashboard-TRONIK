/*
JavaScript da Página de Configurações - Dashboard-TRONIK
========================================================
Gerencia formulários de lixeiras e coletas.
*/

// Carregar lista de lixeiras ao carregar a página
document.addEventListener('DOMContentLoaded', async function() {
    // Permitir scroll na página de configurações
    const mainContainer = document.querySelector('.main-container');
    if (mainContainer) {
        mainContainer.style.overflowY = 'auto';
        mainContainer.style.overflowX = 'hidden';
    }
    
    // Carregar dropdowns de tipos e parceiros
    await carregarDropdowns();
    await carregarDropdownsColeta();
    await carregarDropdownsSensor();
    
    carregarListaLixeiras();
    carregarListaSensores();
    
    // Event listener para o formulário de lixeira
    const formLixeira = document.getElementById('form-nova-lixeira');
    if (formLixeira) {
        formLixeira.addEventListener('submit', async function(e) {
            e.preventDefault();
            await criarNovaLixeira();
        });
    }
    
    // Event listener para o formulário de coleta
    const formColeta = document.getElementById('form-nova-coleta');
    if (formColeta) {
        formColeta.addEventListener('submit', async function(e) {
            e.preventDefault();
            await criarNovaColeta();
        });
    }
    
    // Event listener para o formulário de sensor
    const formSensor = document.getElementById('form-novo-sensor');
    if (formSensor) {
        formSensor.addEventListener('submit', async function(e) {
            e.preventDefault();
            await criarNovoSensor();
        });
    }
    
    // Definir data/hora padrão como agora
    const dataHoraInput = document.getElementById('coleta-data-hora');
    if (dataHoraInput) {
        const agora = new Date();
        agora.setMinutes(agora.getMinutes() - agora.getTimezoneOffset());
        dataHoraInput.value = agora.toISOString().slice(0, 16);
    }
});

// Função para carregar dropdowns
async function carregarDropdowns() {
    try {
        const [tiposMaterial, parceiros] = await Promise.all([
            obterTiposMaterial().catch(() => []),
            obterParceiros().catch(() => [])
        ]);
        
        // Popular dropdown de tipos de material
        const selectTipo = document.getElementById('tipo_material_id');
        if (selectTipo) {
            tiposMaterial.forEach(tipo => {
                const option = document.createElement('option');
                option.value = tipo.id;
                option.textContent = tipo.nome;
                selectTipo.appendChild(option);
            });
        }
        
        // Popular dropdown de parceiros
        const selectParceiro = document.getElementById('parceiro_id');
        if (selectParceiro) {
            parceiros.forEach(parceiro => {
                const option = document.createElement('option');
                option.value = parceiro.id;
                option.textContent = parceiro.nome;
                selectParceiro.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Erro ao carregar dropdowns:', error);
    }
}

// Função para carregar dropdowns do formulário de coleta
async function carregarDropdownsColeta() {
    try {
        const [lixeiras, tiposColetor, parceiros] = await Promise.all([
            obterTodasLixeiras().catch(() => []),
            obterTiposColetor().catch(() => []),
            obterParceiros().catch(() => [])
        ]);
        
        // Popular dropdown de lixeiras
        const selectLixeira = document.getElementById('coleta-lixeira-id');
        if (selectLixeira) {
            lixeiras.forEach(lixeira => {
                const option = document.createElement('option');
                option.value = lixeira.id;
                option.textContent = `#L${String(lixeira.id).padStart(3, '0')} - ${lixeira.localizacao || 'Sem localização'}`;
                selectLixeira.appendChild(option);
            });
        }
        
        // Popular dropdown de tipos de coletor
        const selectTipoColetor = document.getElementById('coleta-tipo-coletor');
        if (selectTipoColetor) {
            tiposColetor.forEach(tipo => {
                const option = document.createElement('option');
                option.value = tipo.id;
                option.textContent = tipo.nome;
                selectTipoColetor.appendChild(option);
            });
        }
        
        // Popular dropdown de parceiros
        const selectParceiro = document.getElementById('coleta-parceiro');
        if (selectParceiro) {
            parceiros.forEach(parceiro => {
                const option = document.createElement('option');
                option.value = parceiro.id;
                option.textContent = parceiro.nome;
                selectParceiro.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Erro ao carregar dropdowns de coleta:', error);
    }
}

// Função para criar nova coleta
async function criarNovaColeta() {
    const form = document.getElementById('form-nova-coleta');
    const mensagem = document.getElementById('coleta-form-mensagem');
    if (!form || !mensagem) return;
    
    const btnSubmit = form.querySelector('button[type="submit"]');
    
    try {
        btnSubmit.disabled = true;
        btnSubmit.textContent = 'Adicionando...';
        mensagem.style.display = 'none';
        
        const formData = new FormData(form);
        const dados = {
            lixeira_id: parseInt(formData.get('lixeira_id')),
            data_hora: formData.get('data_hora') + ':00',
            volume_estimado: formData.get('volume_estimado') ? parseFloat(formData.get('volume_estimado')) : null,
            tipo_operacao: formData.get('tipo_operacao') || null,
            km_percorrido: formData.get('km_percorrido') ? parseFloat(formData.get('km_percorrido')) : null,
            preco_combustivel: formData.get('preco_combustivel') ? parseFloat(formData.get('preco_combustivel')) : null,
            lucro_por_kg: formData.get('lucro_por_kg') ? parseFloat(formData.get('lucro_por_kg')) : null,
            tipo_coletor_id: formData.get('tipo_coletor_id') ? parseInt(formData.get('tipo_coletor_id')) : null,
            parceiro_id: formData.get('parceiro_id') ? parseInt(formData.get('parceiro_id')) : null,
            emissao_mtr: formData.get('emissao_mtr') === 'true'
        };
        
        const coleta = await criarColeta(dados);
        
        mensagem.textContent = 'Coleta adicionada com sucesso!';
        mensagem.className = 'form-mensagem success';
        mensagem.style.display = 'block';
        
        form.reset();
        
        // Atualizar data/hora para agora
        const dataHoraInput = document.getElementById('coleta-data-hora');
        if (dataHoraInput) {
            const agora = new Date();
            agora.setMinutes(agora.getMinutes() - agora.getTimezoneOffset());
            dataHoraInput.value = agora.toISOString().slice(0, 16);
        }
        
        setTimeout(() => {
            mensagem.style.display = 'none';
        }, 3000);
        
    } catch (error) {
        console.error('Erro ao criar coleta:', error);
        mensagem.textContent = 'Erro ao adicionar coleta: ' + (error.message || 'Erro desconhecido');
        mensagem.className = 'form-mensagem error';
        mensagem.style.display = 'block';
    } finally {
        btnSubmit.disabled = false;
        btnSubmit.textContent = 'Adicionar Coleta';
    }
}

// Função para carregar lista de lixeiras
async function carregarListaLixeiras() {
    try {
        const lixeiras = await obterTodasLixeiras();
        exibirListaLixeiras(lixeiras);
    } catch (error) {
        console.error('Erro ao carregar lixeiras:', error);
        const container = document.getElementById('lista-lixeiras');
        if (container) {
            container.innerHTML = '<div class="loading-message">Erro ao carregar lixeiras</div>';
        }
    }
}

// Função para calcular distância da sede (Haversine)
function calcularDistanciaSede(lixeira) {
    if (!lixeira || !lixeira.latitude || !lixeira.longitude) {
        return null;
    }
    
    const SEDE_TRONIK = {
        lat: -15.908661672774747,
        lon: -48.076158282355806
    };
    
    const lat = parseFloat(lixeira.latitude);
    const lon = parseFloat(lixeira.longitude);
    
    if (isNaN(lat) || isNaN(lon)) {
        return null;
    }
    
    const R = 6371; // Raio da Terra em km
    const dLat = (lat - SEDE_TRONIK.lat) * Math.PI / 180;
    const dLon = (lon - SEDE_TRONIK.lon) * Math.PI / 180;
    const a = 
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(SEDE_TRONIK.lat * Math.PI / 180) * Math.cos(lat * Math.PI / 180) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

// Função para formatar distância
function formatarDistancia(distancia) {
    if (distancia === null || distancia === undefined) {
        return 'N/A';
    }
    
    if (distancia < 1) {
        return `${Math.round(distancia * 1000)}m`;
    }
    
    return `${distancia.toFixed(1)}km`;
}

// Função para exibir lista de lixeiras
function exibirListaLixeiras(lixeiras) {
    const container = document.getElementById('lista-lixeiras');
    if (!container) return;
    
    if (lixeiras.length === 0) {
        container.innerHTML = '<div class="loading-message">Nenhuma lixeira cadastrada</div>';
        return;
    }
    
    container.innerHTML = lixeiras.map(lixeira => {
        const tipoMaterial = lixeira.tipo_material ? lixeira.tipo_material.nome : 'Não especificado';
        const parceiro = lixeira.parceiro ? lixeira.parceiro.nome : 'N/A';
        const distanciaSede = calcularDistanciaSede(lixeira);
        const distanciaFormatada = formatarDistancia(distanciaSede);
        return `
        <div class="lixeira-item">
            <div class="lixeira-info">
                <div class="lixeira-id">#L${String(lixeira.id).padStart(3, '0')}</div>
                <div class="lixeira-local">${lixeira.localizacao || 'Sem localização'}</div>
                <div style="font-size: 12px; color: #7f8c8d; margin-top: 4px;">
                    ${tipoMaterial}${parceiro !== 'N/A' ? ` | ${parceiro}` : ''}${distanciaSede !== null ? ` | 📍 ${distanciaFormatada} da sede` : ''}
                </div>
            </div>
            <div class="lixeira-acoes">
                <button class="btn-delete" data-lixeira-id="${lixeira.id}">Excluir</button>
            </div>
        </div>
    `;
    }).join('');
    
    // Adicionar event listeners aos botões de deletar
    container.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', function() {
            const lixeiraId = parseInt(this.getAttribute('data-lixeira-id'));
            deletarLixeiraConfig(lixeiraId);
        });
    });
}

// Função para criar nova lixeira
async function criarNovaLixeira() {
    const form = document.getElementById('form-nova-lixeira');
    const mensagem = document.getElementById('form-mensagem');
    if (!form || !mensagem) return;
    
    const btnSubmit = form.querySelector('button[type="submit"]');
    
    // Coletar dados do formulário
    const dados = {
        localizacao: document.getElementById('localizacao').value.trim(),
        nivel_preenchimento: parseFloat(document.getElementById('nivel_preenchimento').value) || 0,
        status: document.getElementById('status').value
    };
    
    // Adicionar tipo_material_id se selecionado
    const tipoMaterialId = document.getElementById('tipo_material_id').value;
    if (tipoMaterialId) {
        dados.tipo_material_id = parseInt(tipoMaterialId);
    }
    
    // Adicionar parceiro_id se selecionado
    const parceiroId = document.getElementById('parceiro_id').value;
    if (parceiroId) {
        dados.parceiro_id = parseInt(parceiroId);
    }
    
    // Adicionar coordenadas se fornecidas
    const lat = document.getElementById('latitude').value;
    const lon = document.getElementById('longitude').value;
    if (lat && lon) {
        dados.latitude = parseFloat(lat);
        dados.longitude = parseFloat(lon);
    }
    
    // Validar
    if (!dados.localizacao) {
        mostrarMensagem('Por favor, preencha a localização', 'error');
        return;
    }
    if (isNaN(dados.nivel_preenchimento) || dados.nivel_preenchimento < 0 || dados.nivel_preenchimento > 100) {
        mostrarMensagem('Nível de preenchimento deve estar entre 0 e 100', 'error');
        return;
    }
    if ((lat && !lon) || (!lat && lon)) {
        mostrarMensagem('Informe latitude e longitude juntos', 'error');
        return;
    }
    
    try {
        mensagem.style.display = 'none';
        // Feedback visual
        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.textContent = 'Adicionando...';
        }
        
        const novaLixeira = await criarLixeira(dados);
        
        mostrarMensagem(`Lixeira #L${String(novaLixeira.id).padStart(3, '0')} criada com sucesso!`, 'success');
        form.reset();
        
        // Recarregar lista
        await carregarListaLixeiras();
        
        // Atualizar dropdown de lixeiras no formulário de coleta
        await carregarDropdownsColeta();
        
    } catch (error) {
        console.error('Erro ao criar lixeira:', error);
        mostrarMensagem('Erro ao criar lixeira: ' + (error.message || 'Erro desconhecido'), 'error');
    }
    finally {
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.textContent = 'Adicionar Lixeira';
        }
    }
}

// Função para mostrar mensagem
function mostrarMensagem(texto, tipo) {
    const mensagem = document.getElementById('form-mensagem');
    if (!mensagem) return;
    
    mensagem.textContent = texto;
    mensagem.className = `form-mensagem ${tipo}`;
    mensagem.style.display = 'block';
    
    // Esconder após 5 segundos se for sucesso
    if (tipo === 'success') {
        setTimeout(() => {
            mensagem.style.display = 'none';
        }, 5000);
    }
}

// Função para deletar lixeira (com confirmação melhorada)
async function deletarLixeiraConfig(id) {
    if (!confirm(`⚠️ Tem certeza que deseja excluir a lixeira #L${String(id).padStart(3, '0')}?\n\nEsta ação não pode ser desfeita e também excluirá todos os sensores e coletas associados.`)) {
        return;
    }
    
    try {
        mostrarLoading('Deletando lixeira...');
        await deletarLixeira(id);
        mostrarMensagem('Lixeira deletada com sucesso!', 'success');
        await carregarListaLixeiras();
        await carregarListaSensores();
        
        // Atualizar dropdowns
        await carregarDropdownsColeta();
        await carregarDropdownsSensor();
    } catch (error) {
        console.error('Erro ao deletar lixeira:', error);
        mostrarMensagem('Erro ao deletar lixeira: ' + (error.message || 'Erro desconhecido'), 'error');
    } finally {
        esconderLoading();
    }
}

// ============================================================
// FUNÇÕES PARA SENSORES
// ============================================================

// Função para carregar dropdowns do formulário de sensor
async function carregarDropdownsSensor() {
    try {
        const [lixeiras, tiposSensor] = await Promise.all([
            obterTodasLixeiras().catch(() => []),
            obterTiposSensor().catch(() => [])
        ]);
        
        // Popular dropdown de lixeiras
        const selectLixeira = document.getElementById('sensor-lixeira-id');
        if (selectLixeira) {
            // Limpar opções existentes (exceto a primeira)
            while (selectLixeira.children.length > 1) {
                selectLixeira.removeChild(selectLixeira.lastChild);
            }
            
            lixeiras.forEach(lixeira => {
                const option = document.createElement('option');
                option.value = lixeira.id;
                option.textContent = `#L${String(lixeira.id).padStart(3, '0')} - ${lixeira.localizacao || 'Sem localização'}`;
                selectLixeira.appendChild(option);
            });
        }
        
        // Popular dropdown de tipos de sensor
        const selectTipoSensor = document.getElementById('sensor-tipo-sensor-id');
        if (selectTipoSensor) {
            tiposSensor.forEach(tipo => {
                const option = document.createElement('option');
                option.value = tipo.id;
                option.textContent = tipo.nome;
                selectTipoSensor.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Erro ao carregar dropdowns de sensor:', error);
    }
}

// Função para criar novo sensor
async function criarNovoSensor() {
    const form = document.getElementById('form-novo-sensor');
    const mensagem = document.getElementById('sensor-form-mensagem');
    if (!form || !mensagem) return;
    
    const btnSubmit = form.querySelector('button[type="submit"]');
    
    try {
        btnSubmit.disabled = true;
        btnSubmit.textContent = 'Adicionando...';
        mensagem.style.display = 'none';
        
        const formData = new FormData(form);
        const dados = {
            lixeira_id: parseInt(formData.get('lixeira_id')),
            bateria: formData.get('bateria') ? parseFloat(formData.get('bateria')) : 100.0
        };
        
        const tipoSensorId = formData.get('tipo_sensor_id');
        if (tipoSensorId) {
            dados.tipo_sensor_id = parseInt(tipoSensorId);
        }
        
        const sensor = await criarSensor(dados);
        
        mensagem.textContent = 'Sensor adicionado com sucesso!';
        mensagem.className = 'form-mensagem success';
        mensagem.style.display = 'block';
        
        form.reset();
        
        // Recarregar lista de sensores
        await carregarListaSensores();
        
        setTimeout(() => {
            mensagem.style.display = 'none';
        }, 3000);
        
    } catch (error) {
        console.error('Erro ao criar sensor:', error);
        mensagem.textContent = 'Erro ao adicionar sensor: ' + (error.message || 'Erro desconhecido');
        mensagem.className = 'form-mensagem error';
        mensagem.style.display = 'block';
    } finally {
        btnSubmit.disabled = false;
        btnSubmit.textContent = 'Adicionar Sensor';
    }
}

// Função para carregar lista de sensores
async function carregarListaSensores() {
    const container = document.getElementById('lista-sensores');
    if (!container) return;
    
    try {
        container.innerHTML = '<div class="loading-message">Carregando sensores...</div>';
        const sensores = await obterTodosSensores();
        exibirListaSensores(sensores);
    } catch (error) {
        console.error('Erro ao carregar sensores:', error);
        container.innerHTML = '<div class="loading-message error">Erro ao carregar sensores</div>';
    }
}

// Função para exibir lista de sensores
function exibirListaSensores(sensores) {
    const container = document.getElementById('lista-sensores');
    if (!container) return;
    
    if (sensores.length === 0) {
        container.innerHTML = '<div class="loading-message">Nenhum sensor cadastrado</div>';
        return;
    }
    
    container.innerHTML = sensores.map(sensor => {
        const tipoSensor = sensor.tipo_sensor ? sensor.tipo_sensor.nome : 'Não especificado';
        const lixeira = sensor.lixeira ? sensor.lixeira.localizacao : 'N/A';
        const bateriaClass = sensor.bateria < 20 ? 'bateria-baixa' : sensor.bateria < 50 ? 'bateria-media' : 'bateria-ok';
        const ultimoPing = sensor.ultimo_ping ? new Date(sensor.ultimo_ping).toLocaleString('pt-BR') : 'N/A';
        
        return `
        <div class="lixeira-item">
            <div class="lixeira-info">
                <div class="lixeira-id">Sensor #${String(sensor.id).padStart(3, '0')}</div>
                <div class="lixeira-local">Lixeira: ${lixeira}</div>
                <div style="font-size: 12px; color: #7f8c8d; margin-top: 4px;">
                    ${tipoSensor} | Bateria: <span class="${bateriaClass}">${sensor.bateria.toFixed(1)}%</span> | Último ping: ${ultimoPing}
                </div>
            </div>
            <div class="lixeira-acoes">
                <button class="btn-delete" data-sensor-id="${sensor.id}">Excluir</button>
            </div>
        </div>
    `;
    }).join('');
    
    // Adicionar event listeners aos botões de deletar
    container.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', function() {
            const sensorId = parseInt(this.getAttribute('data-sensor-id'));
            deletarSensorConfig(sensorId);
        });
    });
}

// Função para deletar sensor (com confirmação)
async function deletarSensorConfig(id) {
    if (!confirm(`⚠️ Tem certeza que deseja excluir o sensor #${String(id).padStart(3, '0')}?\n\nEsta ação não pode ser desfeita.`)) {
        return;
    }
    
    try {
        mostrarLoading('Deletando sensor...');
        await deletarSensor(id);
        mostrarMensagem('Sensor deletado com sucesso!', 'success');
        await carregarListaSensores();
    } catch (error) {
        console.error('Erro ao deletar sensor:', error);
        mostrarMensagem('Erro ao deletar sensor: ' + (error.message || 'Erro desconhecido'), 'error');
    } finally {
        esconderLoading();
    }
}

// ============================================================
// MELHORIAS DE UX (Loading States, etc.)
// ============================================================

// Função para mostrar loading
function mostrarLoading(mensagem = 'Carregando...') {
    // Criar ou atualizar elemento de loading
    let loadingEl = document.getElementById('global-loading');
    if (!loadingEl) {
        loadingEl = document.createElement('div');
        loadingEl.id = 'global-loading';
        loadingEl.className = 'global-loading';
        loadingEl.innerHTML = `
            <div class="loading-spinner"></div>
            <div class="loading-text">${mensagem}</div>
        `;
        document.body.appendChild(loadingEl);
    } else {
        loadingEl.querySelector('.loading-text').textContent = mensagem;
        loadingEl.style.display = 'flex';
    }
}

// Função para esconder loading
function esconderLoading() {
    const loadingEl = document.getElementById('global-loading');
    if (loadingEl) {
        loadingEl.style.display = 'none';
    }
}

