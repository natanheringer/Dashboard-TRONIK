/**
 * Gestão v2 - Operações críticas de configuração
 * @author Antigravity
 */

document.addEventListener('DOMContentLoaded', async function() {
    // 1. Alternância de abas
    setupTabs();

    // 2. Data/Hora padrão para coletas
    const dtInput = document.getElementById('coleta-data-hora');
    if (dtInput) {
        const agora = new Date();
        agora.setMinutes(agora.getMinutes() - agora.getTimezoneOffset());
        dtInput.value = agora.toISOString().slice(0, 16);
    }

    // 3. Carga inicial de dados (Dropdowns)
    await carregarDropdowns();

    // 4. Carregar Listas
    await Promise.all([
        carregarListaColetores(),
        carregarListaSensores()
    ]);

    // 5. Setup de Forms
    setupFormHandlers();
});

/**
 * Lógica simples de tabs
 */
function setupTabs() {
    const tabBtns = document.querySelectorAll('.gestao-tab');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            
            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(`tab-${target}`).classList.add('active');
        });
    });
}

/**
 * Busca dados da API para popular selects
 */
async function carregarDropdowns() {
    try {
        // Tipos de Material and Parceiros (for Coletor form)
        const [tiposMaterial, parceiros, tiposSensor, coletores] = await Promise.all([
            window.obterTiposMaterial ? window.obterTiposMaterial() : [],
            window.obterParceiros ? window.obterParceiros() : [],
            window.obterTiposSensor ? window.obterTiposSensor() : [],
            window.obterTodosColetores ? window.obterTodosColetores() : []
        ]);

        // Popular Material
        const selMat = document.getElementById('tipo_material_id');
        if (selMat) {
            tiposMaterial.forEach(t => selMat.appendChild(new Option(t.nome, t.id)));
        }

        // Popular Parceiros
        const selParc = document.getElementById('parceiro_id');
        if (selParc) {
            parceiros.forEach(p => selParc.appendChild(new Option(p.nome, p.id)));
        }

        // Popular Tipos de Sensor
        const selTipoSen = document.getElementById('sensor-tipo-id');
        if (selTipoSen) {
            tiposSensor.forEach(t => selTipoSen.appendChild(new Option(t.nome, t.id)));
        }

        // Popular Coletores (for Sensor and Coleta forms)
        const selColSen = document.getElementById('sensor-coletor-id');
        const selColCol = document.getElementById('coleta-coletor-id');
        
        coletores.forEach(c => {
            const label = `#L${String(c.id).padStart(3, '0')} - ${c.localizacao || 'Sem nome'}`;
            if (selColSen) selColSen.appendChild(new Option(label, c.id));
            if (selColCol) selColCol.appendChild(new Option(label, c.id));
        });

    } catch (err) {
        console.error('Erro ao carregar selects:', err);
    }
}

/**
 * Listagem de Coletores
 */
async function carregarListaColetores() {
    const listEl = document.getElementById('lista-coletores');
    if (!listEl) return;

    try {
        const coletores = await window.obterTodosColetores();
        if (!coletores || coletores.length === 0) {
            listEl.innerHTML = '<p class="home-subtitle">Nenhum coletor cadastrado.</p>';
            return;
        }

        listEl.innerHTML = coletores.map(c => {
            const info = [
                c.tipo_material ? c.tipo_material.nome : 'Material não def.',
                c.parceiro ? c.parceiro.nome : 'Sem parceiro'
            ].join(' · ');

            return `
                <div class="gestao-item">
                    <div class="gestao-item-info">
                        <strong>#L${String(c.id).padStart(3, '0')} · ${c.localizacao}</strong>
                        <span>${info} · ${c.status || 'OK'} · ${c.nivel_preenchimento || 0}%</span>
                    </div>
                    <button class="btn-delete-v2" onclick="handleDeleteColetor(${c.id})">Excluir</button>
                </div>
            `;
        }).join('');

    } catch (err) {
        listEl.innerHTML = '<p class="home-subtitle" style="color:var(--signal-critical)">Erro ao carregar coletores.</p>';
    }
}

/**
 * Listagem de Sensores
 */
async function carregarListaSensores() {
    const listEl = document.getElementById('lista-sensores');
    if (!listEl) return;

    try {
        const sensores = await window.obterTodosSensores();
        if (!sensores || sensores.length === 0) {
            listEl.innerHTML = '<p class="home-subtitle">Nenhum sensor cadastrado.</p>';
            return;
        }

        listEl.innerHTML = sensores.map(s => {
            const colName = s.coletor ? s.coletor.localizacao : 'Desconhecido';
            const batClasse = s.bateria < 20 ? 'color:var(--signal-critical)' : '';

            return `
                <div class="gestao-item">
                    <div class="gestao-item-info">
                        <strong>Sensor #${String(s.id).padStart(3, '0')}</strong>
                        <span>Coletor: ${colName} · Bateria: <strong style="${batClasse}">${s.bateria}%</strong></span>
                    </div>
                    <button class="btn-delete-v2" onclick="handleDeleteSensor(${s.id})">Excluir</button>
                </div>
            `;
        }).join('');

    } catch (err) {
        listEl.innerHTML = '<p class="home-subtitle" style="color:var(--signal-critical)">Erro ao carregar sensores.</p>';
    }
}

/**
 * Handlers de Formulários
 */
function setupFormHandlers() {
    // 1. Novo Coletor
    const fColetor = document.getElementById('form-novo-coletor');
    if (fColetor) {
        fColetor.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msgEl = document.getElementById('msg-coletor');
            const btn = fColetor.querySelector('button[type="submit"]');

            try {
                btn.disabled = true;
                btn.textContent = 'Salvando...';
                
                const formData = new FormData(fColetor);
                const payload = {
                    localizacao: formData.get('localizacao'),
                    status: formData.get('status'),
                    nivel_preenchimento: parseFloat(formData.get('nivel_preenchimento')) || 0
                };

                if (formData.get('tipo_material_id')) payload.tipo_material_id = parseInt(formData.get('tipo_material_id'));
                if (formData.get('parceiro_id')) payload.parceiro_id = parseInt(formData.get('parceiro_id'));
                if (formData.get('latitude')) payload.latitude = parseFloat(formData.get('latitude'));
                if (formData.get('longitude')) payload.longitude = parseFloat(formData.get('longitude'));

                await window.criarColetor(payload);
                
                showStatus(msgEl, 'Coletor criado com sucesso!', 'success');
                fColetor.reset();
                await carregarListaColetores();
                // Refresh list for other forms
                await carregarDropdowns();
            } catch (err) {
                showStatus(msgEl, `Erro: ${err.message}`, 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Salvar Coletor';
            }
        });
    }

    // 2. Novo Sensor
    const fSensor = document.getElementById('form-novo-sensor');
    if (fSensor) {
        fSensor.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msgEl = document.getElementById('msg-sensor');
            const btn = fSensor.querySelector('button[type="submit"]');

            try {
                btn.disabled = true;
                const formData = new FormData(fSensor);
                const payload = {
                    coletor_id: parseInt(formData.get('coletor_id')),
                    bateria: parseFloat(formData.get('bateria')) || 100
                };
                if (formData.get('tipo_sensor_id')) payload.tipo_sensor_id = parseInt(formData.get('tipo_sensor_id'));

                await window.criarSensor(payload);
                showStatus(msgEl, 'Sensor adicionado!', 'success');
                fSensor.reset();
                await carregarListaSensores();
            } catch (err) {
                showStatus(msgEl, `Erro: ${err.message}`, 'error');
            } finally {
                btn.disabled = false;
            }
        });
    }

    // 3. Nova Coleta
    const fColeta = document.getElementById('form-nova-coleta');
    if (fColeta) {
        fColeta.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msgEl = document.getElementById('msg-coleta');
            const btn = fColeta.querySelector('button[type="submit"]');

            try {
                btn.disabled = true;
                const formData = new FormData(fColeta);
                const payload = {
                    coletor_id: parseInt(formData.get('coletor_id')),
                    data_hora: formData.get('data_hora').replace('T', ' ') + ':00',
                    volume_estimado: parseFloat(formData.get('volume_estimado')),
                    tipo_operacao: formData.get('tipo_operacao'),
                    emissao_mtr: formData.get('emissao_mtr') === 'true'
                };

                if (formData.get('km_percorrido')) payload.km_percorrido = parseFloat(formData.get('km_percorrido'));
                if (formData.get('preco_combustivel')) payload.preco_combustivel = parseFloat(formData.get('preco_combustivel'));
                if (formData.get('lucro_por_kg')) payload.lucro_por_kg = parseFloat(formData.get('lucro_por_kg'));

                await window.criarColeta(payload);
                showStatus(msgEl, 'Coleta registrada!', 'success');
                fColeta.reset();
                // Reset date to now
                const dtInput = document.getElementById('coleta-data-hora');
                const agora = new Date();
                agora.setMinutes(agora.getMinutes() - agora.getTimezoneOffset());
                dtInput.value = agora.toISOString().slice(0, 16);
                
                // Refresh list to show updated levels if needed
                await carregarListaColetores();
            } catch (err) {
                showStatus(msgEl, `Erro: ${err.message}`, 'error');
            } finally {
                btn.disabled = false;
            }
        });
    }
}

/**
 * Helpers Global (exposed to HTML via window or directly)
 */
window.handleDeleteColetor = async (id) => {
    if (!confirm('Excluir este coletor e todos os dados relacionados?')) return;
    try {
        await window.deletarColetor(id);
        await carregarListaColetores();
        await carregarDropdowns();
    } catch (err) {
        alert('Erro ao excluir: ' + err.message);
    }
};

window.handleDeleteSensor = async (id) => {
    if (!confirm('Remover este sensor?')) return;
    try {
        await window.deletarSensor(id);
        await carregarListaSensores();
    } catch (err) {
        alert('Erro ao excluir: ' + err.message);
    }
};

function showStatus(el, text, type) {
    el.textContent = text;
    el.className = `form-status ${type}`;
    setTimeout(() => { el.style.display = 'none'; }, 5000);
}
