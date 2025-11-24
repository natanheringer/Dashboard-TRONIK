/**
 * Contratos - Dashboard-TRONIK
 * ============================
 * Lógica frontend para gestão de contratos recorrentes.
 */

let contratosData = [];

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    carregarColetores();
    carregarContratos();
    carregarKPIs();
    
    // Atualizar a cada 5 minutos
    setInterval(() => {
        carregarContratos();
        carregarKPIs();
    }, 5 * 60 * 1000);
});

// Carregar coletores para o dropdown
async function carregarColetores() {
    try {
        const response = await fetch('/api/coletores');
        if (!response.ok) {
            console.error('Erro HTTP ao carregar coletores:', response.status, response.statusText);
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        
        const dados = await response.json();
        console.log('Dados recebidos da API:', dados);
        
        // A API retorna formato paginado: {dados: [...], paginacao: {...}}
        // Ou pode retornar array direto (compatibilidade)
        let coletores = [];
        if (Array.isArray(dados)) {
            coletores = dados;
        } else if (dados.dados && Array.isArray(dados.dados)) {
            coletores = dados.dados;
        } else if (dados.data && Array.isArray(dados.data)) {
            coletores = dados.data;
        } else if (dados.coletores && Array.isArray(dados.coletores)) {
            coletores = dados.coletores;
        }
        
        if (!Array.isArray(coletores)) {
            console.error('Resposta não é um array:', dados);
            throw new Error('Formato de resposta inválido');
        }
        
        const select = document.getElementById('coletor-id-contrato');
        if (!select) {
            console.error('Elemento select não encontrado');
            return;
        }
        
        // Limpar opções existentes (exceto a primeira)
        select.innerHTML = '<option value="">Selecione um coletor...</option>';
        
        if (coletores.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Nenhum coletor disponível';
            option.disabled = true;
            select.appendChild(option);
            console.warn('Nenhum coletor encontrado');
            return;
        }
        
        // Adicionar coletores
        coletores.forEach(coletor => {
            if (!coletor || !coletor.id) {
                console.warn('Coletor inválido ignorado:', coletor);
                return;
            }
            
            const option = document.createElement('option');
            option.value = coletor.id;
            const localizacao = coletor.localizacao || 'Sem localização';
            // Verificar se parceiro é objeto ou null
            const parceiroNome = (coletor.parceiro && typeof coletor.parceiro === 'object' && coletor.parceiro.nome) 
                ? coletor.parceiro.nome 
                : (coletor.parceiro_nome || '');
            option.textContent = parceiroNome ? `${localizacao} - ${parceiroNome}` : localizacao;
            select.appendChild(option);
        });
        
        console.log(`${coletores.length} coletores carregados no dropdown`);
    } catch (erro) {
        console.error('Erro ao carregar coletores:', erro);
        const select = document.getElementById('coletor-id-contrato');
        if (select) {
            select.innerHTML = '<option value="">Erro ao carregar coletores</option>';
        }
        mostrarErro('Erro ao carregar lista de coletores. Tente novamente.');
    }
}

// Carregar contratos
async function carregarContratos() {
    try {
        const response = await fetch('/api/contratos/');
        if (!response.ok) throw new Error('Erro ao carregar contratos');
        
        contratosData = await response.json();
        renderizarContratos();
    } catch (erro) {
        console.error('Erro ao carregar contratos:', erro);
        mostrarErro('Erro ao carregar contratos');
    }
}

// Carregar KPIs
async function carregarKPIs() {
    try {
        // Receita mensal
        const receitaResponse = await fetch('/api/contratos/receita-mensal');
        if (receitaResponse.ok) {
            const receitaData = await receitaResponse.json();
            document.getElementById('kpi-receita-mensal').textContent = formatarMoeda(receitaData.receita_mensal);
        }
        
        // Total de contratos
        const totalAtivos = contratosData.filter(c => c.status === 'ativo').length;
        document.getElementById('kpi-total-contratos').textContent = contratosData.length;
        document.getElementById('kpi-total-desc').textContent = `${totalAtivos} ativos`;
        
        // Contratos vencendo
        const vencendoResponse = await fetch('/api/contratos/vencendo?dias=30');
        if (vencendoResponse.ok) {
            const vencendoData = await vencendoResponse.json();
            document.getElementById('kpi-vencendo').textContent = vencendoData.length;
        }
    } catch (erro) {
        console.error('Erro ao carregar KPIs:', erro);
    }
}

// Renderizar contratos
function renderizarContratos() {
    const container = document.getElementById('contratos-container');
    if (!container) return;
    
    const filtroStatus = document.getElementById('filtro-status-contrato')?.value || '';
    const filtroColetor = document.getElementById('filtro-coletor-contrato')?.value || '';
    
    let contratosFiltrados = contratosData;
    
    if (filtroStatus) {
        contratosFiltrados = contratosFiltrados.filter(c => c.status === filtroStatus);
    }
    
    if (filtroColetor) {
        contratosFiltrados = contratosFiltrados.filter(c => c.coletor_id === parseInt(filtroColetor));
    }
    
    // Limpar container de forma segura
    container.textContent = '';
    
    if (contratosFiltrados.length === 0) {
        const emptyMsg = document.createElement('p');
        emptyMsg.style.textAlign = 'center';
        emptyMsg.style.color = '#64748b';
        emptyMsg.style.padding = '2rem';
        emptyMsg.textContent = 'Nenhum contrato encontrado';
        container.appendChild(emptyMsg);
        return;
    }
    
    // Criar elementos de forma segura
    contratosFiltrados.forEach(contrato => {
        const item = document.createElement('div');
        item.className = 'contrato-item';
        
        // Info
        const info = document.createElement('div');
        info.className = 'contrato-info';
        
        const strong = document.createElement('strong');
        strong.textContent = contrato.titulo || 'Sem título';
        
        const statusSpan = document.createElement('span');
        statusSpan.className = `contrato-status status-${contrato.status || 'ativo'}`;
        statusSpan.textContent = contrato.status || 'ativo';
        
        info.appendChild(strong);
        info.appendChild(statusSpan);
        
        // Detalhes
        const detalhes = document.createElement('div');
        detalhes.className = 'contrato-detalhes';
        
        const clienteSpan = document.createElement('span');
        clienteSpan.textContent = `Cliente: ${contrato.coletor?.localizacao || 'N/A'}`;
        
        const valorSpan = document.createElement('span');
        valorSpan.textContent = `Valor: ${formatarMoeda(contrato.valor_mensal || 0)}/mês`;
        
        const freqSpan = document.createElement('span');
        freqSpan.textContent = `Frequência: ${contrato.frequencia_coleta || 'N/A'}`;
        
        detalhes.appendChild(clienteSpan);
        detalhes.appendChild(valorSpan);
        detalhes.appendChild(freqSpan);
        
        // Datas
        const datas = document.createElement('div');
        datas.className = 'contrato-datas';
        
        const inicioSpan = document.createElement('span');
        inicioSpan.textContent = `Início: ${formatarData(contrato.data_inicio)}`;
        
        datas.appendChild(inicioSpan);
        
        if (contrato.data_vencimento) {
            const vencSpan = document.createElement('span');
            vencSpan.textContent = `Vencimento: ${formatarData(contrato.data_vencimento)}`;
            datas.appendChild(vencSpan);
        } else {
            const semVenc = document.createElement('span');
            semVenc.textContent = 'Sem vencimento';
            datas.appendChild(semVenc);
        }
        
        // Ações
        const acoes = document.createElement('div');
        acoes.className = 'contrato-acoes';
        
        const btnVer = document.createElement('button');
        btnVer.className = 'btn btn-xs';
        btnVer.textContent = 'Ver';
        btnVer.onclick = () => verDetalhesContrato(contrato.id);
        
        const btnEditar = document.createElement('button');
        btnEditar.className = 'btn btn-xs';
        btnEditar.textContent = 'Editar';
        btnEditar.onclick = () => editarContrato(contrato.id);
        
        acoes.appendChild(btnVer);
        acoes.appendChild(btnEditar);
        
        if (contrato.status === 'ativo') {
            const btnCancelar = document.createElement('button');
            btnCancelar.className = 'btn btn-xs btn-danger';
            btnCancelar.textContent = 'Cancelar';
            btnCancelar.onclick = () => cancelarContrato(contrato.id);
            acoes.appendChild(btnCancelar);
        }
        
        item.appendChild(info);
        item.appendChild(detalhes);
        item.appendChild(datas);
        item.appendChild(acoes);
        container.appendChild(item);
    });
}

// Filtrar contratos
function filtrarContratos() {
    renderizarContratos();
}

// Criar contrato - Expor no escopo global
window.criarContrato = async function(event) {
    event.preventDefault();
    
    try {
        const formData = new FormData(event.target);
        const coletorId = formData.get('coletor_id');
        
        if (!coletorId) {
            mostrarErro('Por favor, selecione um coletor');
            return;
        }
        
        const dados = {
            coletor_id: parseInt(coletorId),
            titulo: formData.get('titulo'),
            descricao: formData.get('observacoes') || '',
            valor_mensal: parseFloat(formData.get('valor_mensal')),
            frequencia_coleta: formData.get('frequencia_coleta') || 'mensal',
            dia_coleta: formData.get('dia_coleta') ? parseInt(formData.get('dia_coleta')) : null,
            data_inicio: new Date(formData.get('data_inicio')).toISOString(),
            data_vencimento: formData.get('data_vencimento') ? new Date(formData.get('data_vencimento')).toISOString() : null,
            observacoes: formData.get('observacoes') || ''
        };
        
        const response = await fetch('/api/contratos/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        });
        
        if (!response.ok) {
            const erroData = await response.json().catch(() => ({}));
            throw new Error(erroData.erro || 'Erro ao criar contrato');
        }
        
        mostrarSucesso('Contrato criado com sucesso!');
        window.fecharModalNovoContrato();
        carregarContratos();
        carregarKPIs();
    } catch (erro) {
        console.error('Erro:', erro);
        mostrarErro(erro.message || 'Erro ao criar contrato');
    }
};


// Modais - Expor no escopo global
window.abrirModalNovoContrato = function() {
    const modal = document.getElementById('modal-novo-contrato');
    if (modal) {
        // Garantir que coletores estão carregados
        carregarColetores();
        
        modal.classList.add('active');
        // Definir data de início como hoje
        const hoje = new Date().toISOString().split('T')[0];
        const dataInicioInput = document.getElementById('data-inicio-contrato');
        if (dataInicioInput) {
            dataInicioInput.value = hoje;
        }
        // Prevenir scroll do body quando modal está aberto
        document.body.style.overflow = 'hidden';
    }
};

window.fecharModalNovoContrato = function() {
    const modal = document.getElementById('modal-novo-contrato');
    if (modal) {
        modal.classList.remove('active');
        const form = document.getElementById('form-novo-contrato');
        if (form) {
            form.reset();
        }
        // Restaurar scroll do body
        document.body.style.overflow = '';
    }
};

// Fechar modal ao clicar fora
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('modal-novo-contrato');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                window.fecharModalNovoContrato();
            }
        });
        
        // Fechar com ESC
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                window.fecharModalNovoContrato();
            }
        });
    }
});

// Ações - Expor no escopo global
window.atualizarContratos = function() {
    carregarContratos();
    carregarKPIs();
};

window.verDetalhesContrato = function(id) {
    alert(`Ver detalhes do contrato #${id}`);
};

window.editarContrato = function(id) {
    alert(`Editar contrato #${id}`);
};

window.cancelarContrato = function(contratoId) {
    if (!confirm('Tem certeza que deseja cancelar este contrato?')) return;
    
    fetch(`/api/contratos/${contratoId}/cancelar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ motivo: 'Cancelado pelo usuário' })
    })
    .then(response => {
        if (!response.ok) throw new Error('Erro ao cancelar contrato');
        mostrarSucesso('Contrato cancelado!');
        carregarContratos();
        carregarKPIs();
    })
    .catch(erro => {
        console.error('Erro:', erro);
        mostrarErro('Erro ao cancelar contrato');
    });
};

// Utilitários
function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(valor || 0);
}

function formatarData(dataStr) {
    if (!dataStr) return 'N/A';
    const data = new Date(dataStr);
    return data.toLocaleDateString('pt-BR');
}

function mostrarSucesso(mensagem) {
    // Criar notificação visual
    const notificacao = document.createElement('div');
    notificacao.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #27ae60;
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    notificacao.textContent = mensagem;
    document.body.appendChild(notificacao);
    
    setTimeout(() => {
        notificacao.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notificacao.remove(), 300);
    }, 3000);
}

function mostrarErro(mensagem) {
    // Criar notificação visual
    const notificacao = document.createElement('div');
    notificacao.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #e74c3c;
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    notificacao.textContent = mensagem;
    document.body.appendChild(notificacao);
    
    setTimeout(() => {
        notificacao.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notificacao.remove(), 300);
    }, 3000);
}

// Adicionar animações CSS
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

