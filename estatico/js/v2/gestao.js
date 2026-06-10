/**
 * Gestão v2 — cadastro de coletores, sensores, coletas e solicitações da landing.
 */

let _coletoresGestaoCache = null;

async function obterColetoresGestao() {
    if (_coletoresGestaoCache) return _coletoresGestaoCache;
    if (!window.obterTodosColetores) return [];
    _coletoresGestaoCache = await window.obterTodosColetores();
    return _coletoresGestaoCache;
}

function invalidarColetoresGestao() {
    _coletoresGestaoCache = null;
    if (window.invalidarCacheColetores) window.invalidarCacheColetores();
}

document.addEventListener('DOMContentLoaded', async function () {
    setupTabs();

    const dtInput = document.getElementById('coleta-data-hora');
    if (dtInput) {
        dtInput.value = dataHoraLocalIso();
    }

    try {
        const coletores = await obterColetoresGestao();
        await carregarDropdowns(coletores);
        await carregarListaColetores(coletores);
    } catch (err) {
        console.error('Erro ao carregar selects:', err);
        const msg = formatGestaoError(err);
        ['lista-coletores', 'lista-sensores', 'lista-solicitacoes'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) {
                el.innerHTML = `<p class="home-subtitle" style="color:var(--signal-critical)">${msg}</p>`;
            }
        });
    }

    await Promise.all([carregarListaSensores(), carregarSolicitacoes()]);

    setupFormHandlers();
});

function dataHoraLocalIso() {
    const agora = new Date();
    agora.setMinutes(agora.getMinutes() - agora.getTimezoneOffset());
    return agora.toISOString().slice(0, 16);
}

function setupTabs() {
    const tabBtns = document.querySelectorAll('.gestao-tab');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;

            tabBtns.forEach((b) => b.classList.remove('active'));
            tabContents.forEach((c) => c.classList.remove('active'));

            btn.classList.add('active');
            const panel = document.getElementById(`tab-${target}`);
            if (panel) panel.classList.add('active');

            if (target === 'solicitacoes') {
                carregarSolicitacoes();
            }
        });
    });
}

function resetSelect(selectEl, placeholder) {
    if (!selectEl) return;
    selectEl.innerHTML = '';
    selectEl.appendChild(new Option(placeholder || 'Selecione...', ''));
}

function formatGestaoError(err) {
    if (err && err.status === 401) {
        return 'Sessão expirada. Faça login novamente e recarregue a página.';
    }
    if (err && err.status === 403) {
        return 'Acesso negado. Gestão exige usuário administrador.';
    }
    return `Erro: ${(err && err.message) || 'falha ao carregar dados'}`;
}

function showStatus(el, text, type, durationMs) {
    if (!el) return;
    el.textContent = text;
    el.className = `form-status ${type}`;
    el.style.display = 'block';
    const ms = durationMs || (text.length > 120 ? 12000 : 6000);
    setTimeout(() => {
        el.style.display = 'none';
    }, ms);
}

async function carregarDropdowns(coletoresPrecarregados) {
    const [tiposMaterial, parceiros, tiposSensor, coletores] = await Promise.all([
        window.obterTiposMaterial ? window.obterTiposMaterial() : [],
        window.obterParceiros ? window.obterParceiros() : [],
        window.obterTiposSensor ? window.obterTiposSensor() : [],
        coletoresPrecarregados != null
            ? coletoresPrecarregados
            : obterColetoresGestao(),
    ]);

    const selMat = document.getElementById('tipo_material_id');
    resetSelect(selMat, 'Selecione...');
    tiposMaterial.forEach((t) => selMat && selMat.appendChild(new Option(t.nome, t.id)));

    const selParc = document.getElementById('parceiro_id');
    resetSelect(selParc, 'Selecione...');
    parceiros.forEach((p) => selParc && selParc.appendChild(new Option(p.nome, p.id)));

    const selTipoSen = document.getElementById('sensor-tipo-id');
    resetSelect(selTipoSen, 'Selecione...');
    tiposSensor.forEach((t) => selTipoSen && selTipoSen.appendChild(new Option(t.nome, t.id)));

    const selColSen = document.getElementById('sensor-coletor-id');
    const selColCol = document.getElementById('coleta-coletor-id');
    resetSelect(selColSen, 'Selecione um coletor...');
    resetSelect(selColCol, 'Selecione um coletor...');

    coletores.forEach((c) => {
        const label = `#L${String(c.id).padStart(3, '0')} — ${c.localizacao || 'Sem nome'}`;
        if (selColSen) selColSen.appendChild(new Option(label, c.id));
        if (selColCol) selColCol.appendChild(new Option(label, c.id));
    });
}

async function carregarListaColetores(coletoresPrecarregados) {
    const listEl = document.getElementById('lista-coletores');
    if (!listEl) return;

    try {
        const coletores =
            coletoresPrecarregados != null
                ? coletoresPrecarregados
                : await obterColetoresGestao();
        if (!coletores || coletores.length === 0) {
            listEl.innerHTML = '<p class="home-subtitle">Nenhum coletor cadastrado. Use o formulário ao lado.</p>';
            return;
        }

        listEl.innerHTML = coletores.map((c) => {
            const info = [
                c.tipo_material ? c.tipo_material.nome : 'Material não def.',
                c.parceiro ? c.parceiro.nome : 'Sem parceiro',
            ].join(' · ');

            return `
                <div class="gestao-item">
                    <div class="gestao-item-info">
                        <strong>#L${String(c.id).padStart(3, '0')} · ${escapeHtml(c.localizacao)}</strong>
                        <span>${escapeHtml(info)} · ${escapeHtml(c.status || 'OK')} · telemetria: ${c.nivel_preenchimento ?? 0}%</span>
                    </div>
                    <button type="button" class="btn-delete-v2" data-delete-coletor="${c.id}">Excluir</button>
                </div>
            `;
        }).join('');

        listEl.querySelectorAll('[data-delete-coletor]').forEach((btn) => {
            btn.addEventListener('click', () => handleDeleteColetor(parseInt(btn.dataset.deleteColetor, 10)));
        });
    } catch (err) {
        listEl.innerHTML = `<p class="home-subtitle" style="color:var(--signal-critical)">${formatGestaoError(err)}</p>`;
    }
}

async function carregarListaSensores() {
    const listEl = document.getElementById('lista-sensores');
    if (!listEl) return;

    try {
        const sensores = await window.obterTodosSensores();
        if (!sensores || sensores.length === 0) {
            listEl.innerHTML = '<p class="home-subtitle">Nenhum sensor cadastrado. Crie um sensor no coletor antes do ESP32.</p>';
            return;
        }

        listEl.innerHTML = sensores.map((s) => {
            const colName = s.coletor ? s.coletor.localizacao : 'Desconhecido';
            const colId = s.coletor_id || (s.coletor && s.coletor.id) || '?';
            const batClasse = s.bateria < 20 ? 'color:var(--signal-critical)' : '';

            return `
                <div class="gestao-item">
                    <div class="gestao-item-info">
                        <strong>Sensor #${String(s.id).padStart(3, '0')}</strong>
                        <span>coletor_id=${colId} · ${escapeHtml(colName)} · bateria: <strong style="${batClasse}">${s.bateria}%</strong></span>
                    </div>
                    <button type="button" class="btn-delete-v2" data-delete-sensor="${s.id}">Excluir</button>
                </div>
            `;
        }).join('');

        listEl.querySelectorAll('[data-delete-sensor]').forEach((btn) => {
            btn.addEventListener('click', () => handleDeleteSensor(parseInt(btn.dataset.deleteSensor, 10)));
        });
    } catch (err) {
        listEl.innerHTML = `<p class="home-subtitle" style="color:var(--signal-critical)">${formatGestaoError(err)}</p>`;
    }
}

async function carregarSolicitacoes() {
    const listEl = document.getElementById('lista-solicitacoes');
    if (!listEl || !window.obterSolicitacoes) return;

    try {
        const itens = await window.obterSolicitacoes();
        if (!itens || itens.length === 0) {
            listEl.innerHTML = '<p class="home-subtitle">Nenhuma solicitação recebida.</p>';
            return;
        }

        listEl.innerHTML = itens.map((s) => {
            const pendente = s.status === 'pendente';
            const acoes = pendente
                ? `
                    <button type="button" class="btn btn-primary" style="padding:4px 10px;font-size:12px;"
                      data-sol-aprovar="${s.id}">Aprovar</button>
                    <button type="button" class="btn-delete-v2" style="margin-left:6px;"
                      data-sol-recusar="${s.id}">Recusar</button>
                    <button type="button" class="btn" style="margin-left:6px;padding:4px 10px;font-size:12px;"
                      data-sol-cadastrar="${s.id}"
                      data-sol-local="${encodeURIComponent(s.localizacao || '')}"
                      data-sol-email="${encodeURIComponent(s.email || '')}">Cadastrar coletor</button>
                  `
                : `<span class="home-subtitle">${escapeHtml(s.status)}</span>`;

            return `
                <div class="gestao-item">
                    <div class="gestao-item-info">
                        <strong>${escapeHtml(s.nome)} · ${escapeHtml(s.localizacao)}</strong>
                        <span>${escapeHtml(s.email)}${s.empresa ? ' · ' + escapeHtml(s.empresa) : ''} · ${escapeHtml(s.status)}</span>
                        ${s.mensagem ? `<span style="display:block;margin-top:4px;">${escapeHtml(s.mensagem)}</span>` : ''}
                    </div>
                    <div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center;">${acoes}</div>
                </div>
            `;
        }).join('');

        listEl.querySelectorAll('[data-sol-aprovar]').forEach((btn) => {
            btn.addEventListener('click', () => atualizarSolicitacao(parseInt(btn.dataset.solAprovar, 10), 'aprovado'));
        });
        listEl.querySelectorAll('[data-sol-recusar]').forEach((btn) => {
            btn.addEventListener('click', () => atualizarSolicitacao(parseInt(btn.dataset.solRecusar, 10), 'recusado'));
        });
        listEl.querySelectorAll('[data-sol-cadastrar]').forEach((btn) => {
            btn.addEventListener('click', () => {
                preencherColetorDaSolicitacao(
                    decodeURIComponent(btn.dataset.solLocal || ''),
                    decodeURIComponent(btn.dataset.solEmail || ''),
                    parseInt(btn.dataset.solCadastrar, 10)
                );
            });
        });
    } catch (err) {
        listEl.innerHTML = `<p class="home-subtitle" style="color:var(--signal-critical)">${formatGestaoError(err)}</p>`;
    }
}

async function atualizarSolicitacao(id, status) {
    if (!window.atualizarStatusSolicitacao) return;
    try {
        await window.atualizarStatusSolicitacao(id, status);
        await carregarSolicitacoes();
    } catch (err) {
        alert(formatGestaoError(err));
    }
}

function preencherColetorDaSolicitacao(localizacao, email, solicitacaoId) {
    document.querySelectorAll('.gestao-tab').forEach((b) => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach((c) => c.classList.remove('active'));
    const tabBtn = document.querySelector('.gestao-tab[data-tab="coletores"]');
    const tabPanel = document.getElementById('tab-coletores');
    if (tabBtn) tabBtn.classList.add('active');
    if (tabPanel) tabPanel.classList.add('active');

    const loc = document.getElementById('localizacao');
    if (loc && localizacao) loc.value = localizacao;

    const msgEl = document.getElementById('msg-coletor');
    if (msgEl) {
        showStatus(
            msgEl,
            `Solicitação #${solicitacaoId}: preencha material/parceiro e salve. Contato: ${email || '—'}`,
            'success',
            10000
        );
    }
    if (loc) loc.focus();
}

function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function setupFormHandlers() {
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
                    status: formData.get('status') || 'OK',
                };

                if (formData.get('tipo_material_id')) {
                    payload.tipo_material_id = parseInt(formData.get('tipo_material_id'), 10);
                }
                if (formData.get('parceiro_id')) {
                    payload.parceiro_id = parseInt(formData.get('parceiro_id'), 10);
                }
                if (formData.get('latitude')) payload.latitude = parseFloat(formData.get('latitude'));
                if (formData.get('longitude')) payload.longitude = parseFloat(formData.get('longitude'));

                await window.criarColetor(payload);

                showStatus(
                    msgEl,
                    'Coletor criado. Próximo passo: aba Sensores → vincular ESP32 (sensor_id + coletor_id).',
                    'success'
                );
                fColetor.reset();
                const statusEl = document.getElementById('status');
                if (statusEl) statusEl.value = 'OK';

                invalidarColetoresGestao();
                const coletores = await obterColetoresGestao();
                await carregarListaColetores(coletores);
                await carregarDropdowns(coletores);
            } catch (err) {
                showStatus(msgEl, formatGestaoError(err), 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Salvar Coletor';
            }
        });
    }

    const fSensor = document.getElementById('form-novo-sensor');
    if (fSensor) {
        fSensor.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msgEl = document.getElementById('msg-sensor');
            const btn = fSensor.querySelector('button[type="submit"]');

            try {
                btn.disabled = true;
                btn.textContent = 'Salvando...';

                const formData = new FormData(fSensor);
                const coletorId = parseInt(formData.get('coletor_id'), 10);
                if (!coletorId) {
                    throw new Error('Selecione um coletor');
                }

                const payload = {
                    coletor_id: coletorId,
                    bateria: parseFloat(formData.get('bateria')) || 100,
                };
                if (formData.get('tipo_sensor_id')) {
                    payload.tipo_sensor_id = parseInt(formData.get('tipo_sensor_id'), 10);
                }

                const created = await window.criarSensor(payload);
                const sid = created && created.id;
                let hint = sid
                    ? `Sensor #${sid} criado. Firmware: sensor_id=${sid}, coletor_id=${coletorId}.`
                    : 'Sensor adicionado!';
                if (created && created.api_token) {
                    hint += ` Token (se não usar TELEMETRY_SHARED_SECRET): ${created.api_token}`;
                }

                showStatus(msgEl, hint, 'success', 15000);
                fSensor.reset();
                document.getElementById('sensor-bateria').value = '100';
                await carregarListaSensores();
            } catch (err) {
                showStatus(msgEl, formatGestaoError(err), 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = 'Adicionar Sensor';
            }
        });
    }

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
                    coletor_id: parseInt(formData.get('coletor_id'), 10),
                    data_hora: formData.get('data_hora').replace('T', ' ') + ':00',
                    volume_estimado: parseFloat(formData.get('volume_estimado')),
                    tipo_operacao: formData.get('tipo_operacao'),
                    emissao_mtr: formData.get('emissao_mtr') === 'true',
                };

                if (formData.get('km_percorrido')) payload.km_percorrido = parseFloat(formData.get('km_percorrido'));
                if (formData.get('preco_combustivel')) {
                    payload.preco_combustivel = parseFloat(formData.get('preco_combustivel'));
                }
                if (formData.get('lucro_por_kg')) payload.lucro_por_kg = parseFloat(formData.get('lucro_por_kg'));

                await window.criarColeta(payload);
                showStatus(msgEl, 'Coleta (esvaziamento) registrada.', 'success');
                fColeta.reset();
                document.getElementById('coleta-data-hora').value = dataHoraLocalIso();
            } catch (err) {
                showStatus(msgEl, formatGestaoError(err), 'error');
            } finally {
                btn.disabled = false;
            }
        });
    }
}

async function handleDeleteColetor(id) {
    if (
        !confirm(
            'Excluir este coletor? Sensores, coletas e histórico vinculados serão removidos (cascade).'
        )
    ) {
        return;
    }
    try {
        await window.deletarColetor(id);
        invalidarColetoresGestao();
        const coletores = await obterColetoresGestao();
        await carregarListaColetores(coletores);
        await carregarDropdowns(coletores);
        await carregarListaSensores();
    } catch (err) {
        alert(formatGestaoError(err));
    }
}

async function handleDeleteSensor(id) {
    if (!confirm('Remover este sensor? O ESP32 deixará de atualizar telemetria para este ID.')) return;
    try {
        await window.deletarSensor(id);
        await carregarListaSensores();
    } catch (err) {
        alert(formatGestaoError(err));
    }
}
