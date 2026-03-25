# 📋 Especificação Técnica Completa - Novas Features Dashboard-TRONIK

**Projeto:** Sistema de Gestão Integrada para Tronik Recicla    
**Cliente:** Maiara (Fundadora Tronik Recicla)  
**Data:** 27 de Novembro de 2025  
**Versão:** 2.0 - Módulos Comerciais e Operacionais

---

## 📚 ÍNDICE

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura e Integrações](#2-arquitetura-e-integrações)
3. [TIER 1: Features Prioritárias](#3-tier-1-features-prioritárias)
   - 3.1 [Dashboard Comercial](#31-dashboard-comercial)
   - 3.2 [CRM Comercial Simplificado](#32-crm-comercial-simplificado)
   - 3.3 [Contratos Recorrentes](#33-contratos-recorrentes)
   - 3.4 [Modo Apresentação](#34-modo-apresentação)
4. [TIER 2: Quick Wins](#4-tier-2-quick-wins)
   - 4.1 [Otimizador de Rotas Semanal](#41-otimizador-de-rotas-semanal)
   - 4.2 [Calculadora de Precificação](#42-calculadora-de-precificação)
   - 4.3 [WhatsApp Integration](#43-whatsapp-integration)
   - 4.4 [Templates de Propostas](#44-templates-de-propostas)
5. [TIER 3: Marketing & Escala](#5-tier-3-marketing--escala)
   - 5.1 [Landing Page Pública](#51-landing-page-pública)
   - 5.2 [Relatório de Impacto](#52-relatório-de-impacto)
6. [Banco de Dados](#6-banco-de-dados)
7. [Testes](#7-testes)
8. [Deployment](#8-deployment)
9. [Roadmap de Implementação](#9-roadmap-de-implementação)

---

## 1. VISÃO GERAL

### 1.1 Contexto do Projeto

**Situação Atual:**
- Sistema de monitoramento de coletores IoT ✅ (95% completo)
- 103 testes automatizados passando ✅
- Arquitetura Flask robusta ✅
- Frontend modular ✅

**Objetivo das Novas Features:**
1. **Aumentar vendas** 
2. **Reduzir custos operacionais** 
3. **Profissionalizar operação** (ferramenta de vendas)
4. **Criar receita recorrente** 

### 1.2 Escopo das Features

| Tier | Features | Impacto | Complexidade | Tempo |
|------|----------|---------|--------------|-------|
| **1** | Dashboard Comercial, CRM, Contratos, Modo Apresentação | Alto | Média | 2,5 semanas |
| **2** | Otimizador Rotas, Calculadora, WhatsApp, Templates | Médio | Baixa | 2 semanas |
| **3** | Landing Page, Relatório Impacto | Médio | Média | 1,5 semanas |


### 1.3 Tecnologias Utilizadas

**Backend:**
```python
Flask 2.3.3
SQLAlchemy 2.0.23
Flask-Login 0.6.3
APScheduler 3.10.4
ReportLab 4.0.7 (PDFs)
Twilio 8.x (WhatsApp - opcional)
```

**Frontend:**
```javascript
Vanilla JavaScript (ES6+)
Leaflet.js 1.9.4 (já integrado)
Chart.js 4.x (novo - para gráficos comerciais)
CSS3 (metodologia BEM)
```

**Banco de Dados:**
```
SQLite (desenvolvimento)
PostgreSQL (produção) (a decidir)
```

---

## 2. ARQUITETURA E INTEGRAÇÕES

### 2.1 Estrutura de Diretórios (Expansão)

```
dashboard-Tronik/
├── app.py
├── banco_dados/
│   ├── modelos.py               # Adicionar novos modelos
│   ├── services/                # Novos serviços
│   │   ├── crm_service.py       # NOVO
│   │   ├── comercial_service.py # NOVO
│   │   └── contrato_service.py  # NOVO
│   └── utils/
│       └── precificacao.py      # NOVO
│
├── rotas/
│   ├── api/
│   │   ├── comercial.py         # NOVO - Endpoints comerciais
│   │   ├── crm.py               # NOVO - Endpoints CRM
│   │   ├── contratos.py         # NOVO - Endpoints contratos
│   │   └── propostas.py         # NOVO - Geração propostas
│   └── apresentacao.py          # NOVO - Rotas públicas
│
├── templates/
│   ├── comercial/
│   │   ├── dashboard.html       # NOVO
│   │   ├── crm.html             # NOVO
│   │   └── contratos.html       # NOVO
│   ├── apresentacao/
│   │   ├── base.html            # NOVO
│   │   ├── operacao.html        # NOVO
│   │   ├── impacto.html         # NOVO
│   │   └── tecnologia.html      # NOVO
│   └── publico/
│       └── landing.html         # NOVO
│
├── estatico/
│   ├── css/
│   │   ├── comercial.css        # NOVO
│   │   ├── crm.css              # NOVO
│   │   ├── apresentacao.css     # NOVO
│   │   └── landing.css          # NOVO
│   └── js/
│       ├── comercial/
│       │   ├── dashboard.js     # NOVO
│       │   ├── crm.js           # NOVO
│       │   └── contratos.js     # NOVO
│       ├── utils/
│       │   ├── charts.js        # NOVO - Wrapper Chart.js
│       │   └── whatsapp.js      # NOVO - Helper WhatsApp
│       └── apresentacao/
│           └── demo.js          # NOVO
│
└── tests/
    ├── test_comercial.py        # NOVO
    ├── test_crm.py              # NOVO
    └── test_contratos.py        # NOVO
```

### 2.2 Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────┐
│                    CAMADA DE APRESENTAÇÃO                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Dashboard  │  │     CRM      │  │  Contratos   │      │
│  │   Comercial  │  │              │  │  Recorrentes │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP/REST
┌─────────────────────────────────────────────────────────────┐
│                      CAMADA DE NEGÓCIO                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Comercial  │  │     CRM      │  │  Contratos   │      │
│  │   Service    │  │   Service    │  │   Service    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Precificação │  │  WhatsApp    │  │   Proposta   │      │
│  │   Util       │  │   Helper     │  │  Generator   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↕ SQL
┌─────────────────────────────────────────────────────────────┐
│                    CAMADA DE PERSISTÊNCIA                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Pipeline   │  │   Contrato   │  │     Meta     │      │
│  │              │  │  Recorrente  │  │   Comercial  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Interacao  │  │   Proposta   │  │   Tarefa     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Integrações Externas

**WhatsApp (Twilio):**
```python
# Opcional - usar apenas se cliente aprovar custo
TWILIO_ACCOUNT_SID = env.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = env.get('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = env.get('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
```

**Alternativa (Gratuita):**
```python
# Usar wa.me links (sem custo, mas sem automação)
def gerar_link_whatsapp(telefone, mensagem):
    telefone_limpo = re.sub(r'\D', '', telefone)
    mensagem_encoded = urllib.parse.quote(mensagem)
    return f"https://wa.me/55{telefone_limpo}?text={mensagem_encoded}"
```

---

## 3. TIER 1: FEATURES PRIORITÁRIAS

### 3.1 DASHBOARD COMERCIAL

#### 3.1.1 Objetivo

Fornecer visão clara de metas, progresso e ações necessárias para atingir objetivos comerciais.

#### 3.1.2 Requisitos Funcionais

**RF-DC-001:** Sistema deve permitir configurar meta mensal de faturamento  
**RF-DC-002:** Sistema deve calcular progresso em tempo real (faturamento atual vs meta)  
**RF-DC-003:** Sistema deve sugerir ações para atingir meta  
**RF-DC-004:** Sistema deve mostrar projeção de fim de mês baseada em ritmo atual  
**RF-DC-005:** Sistema deve listar próximas coletas/palestras agendadas  
**RF-DC-006:** Sistema deve alertar sobre clientes inativos (>30 dias sem coleta)  
**RF-DC-007:** Sistema deve calcular dias úteis restantes no mês  

#### 3.1.3 Modelo de Dados

```python
# banco_dados/modelos.py

class MetaComercial(db.Model):
    """Meta de faturamento mensal"""
    __tablename__ = 'metas_comerciais'
    
    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.Integer, nullable=False)  # 1-12
    ano = db.Column(db.Integer, nullable=False)
    valor_meta = db.Column(db.Float, nullable=False, default=12000.00)
    valor_realizado = db.Column(db.Float, default=0.0)
    percentual_atingido = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='em_andamento')  # 'em_andamento', 'atingida', 'nao_atingida'
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Índice único para mes+ano
    __table_args__ = (
        db.UniqueConstraint('mes', 'ano', name='uq_meta_mes_ano'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'mes': self.mes,
            'ano': self.ano,
            'valor_meta': self.valor_meta,
            'valor_realizado': self.valor_realizado,
            'percentual_atingido': self.percentual_atingido,
            'status': self.status,
            'observacoes': self.observacoes,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None
        }
```

#### 3.1.4 Service Layer

```python
# banco_dados/services/comercial_service.py

from datetime import datetime, timedelta, date
from calendar import monthrange
import math
from sqlalchemy import extract, func
from banco_dados.modelos import db, Coleta, MetaComercial, Coletor
from banco_dados.utils.datetime_utils import get_dias_uteis_mes

class ComercialService:
    """Serviço para lógica de negócio comercial"""
    
    @staticmethod
    def get_ou_criar_meta_atual():
        """Retorna meta do mês atual ou cria uma nova"""
        hoje = datetime.now()
        mes = hoje.month
        ano = hoje.year
        
        meta = MetaComercial.query.filter_by(mes=mes, ano=ano).first()
        
        if not meta:
            meta = MetaComercial(
                mes=mes,
                ano=ano,
                valor_meta=12000.00,  # Valor padrão baseado na análise
                valor_realizado=0.0,
                percentual_atingido=0.0,
                status='em_andamento'
            )
            db.session.add(meta)
            db.session.commit()
        
        return meta
    
    @staticmethod
    def calcular_faturamento_mes(mes=None, ano=None):
        """Calcula faturamento total do mês"""
        hoje = datetime.now()
        mes = mes or hoje.month
        ano = ano or hoje.year
        
        faturamento = db.session.query(func.sum(Coleta.valor)).filter(
            extract('month', Coleta.data_coleta) == mes,
            extract('year', Coleta.data_coleta) == ano
        ).scalar() or 0.0
        
        return float(faturamento)
    
    @staticmethod
    def calcular_proximas_coletas(dias=7):
        """Retorna coletas agendadas nos próximos N dias"""
        hoje = datetime.now()
        fim = hoje + timedelta(days=dias)
        
        coletas = Coleta.query.filter(
            Coleta.data_coleta >= hoje,
            Coleta.data_coleta <= fim
        ).order_by(Coleta.data_coleta).all()
        
        return coletas
    
    @staticmethod
    def calcular_valor_agendado(coletas):
        """Calcula valor total de coletas agendadas"""
        return sum(c.valor for c in coletas if c.valor)
    
    @staticmethod
    def identificar_clientes_inativos(dias=30):
        """Identifica clientes sem coleta há N dias"""
        limite = datetime.now() - timedelta(days=dias)
        
        # Subquery: clientes com coletas recentes
        clientes_ativos_ids = db.session.query(Coletor.id).join(
            Coleta, Coleta.coletor_id == Coletor.id
        ).filter(
            Coleta.data_coleta >= limite
        ).distinct().subquery()
        
        # Clientes sem coletas recentes
        clientes_inativos = Coletor.query.filter(
            ~Coletor.id.in_(clientes_ativos_ids)
        ).all()
        
        return clientes_inativos
    
    @staticmethod
    def gerar_sugestoes_meta(falta, precos_servicos=None):
        """Gera sugestões de ações para atingir meta"""
        if precos_servicos is None:
            precos_servicos = {
                'coleta_0_40km': 800,
                'coleta_40_60km': 850,
                'palestra': 1000,
                'oficina': 800
            }
        
        if falta <= 0:
            return []
        
        sugestoes = []
        
        # Opção 1: Só coletas
        coletas_necessarias = math.ceil(falta / precos_servicos['coleta_0_40km'])
        sugestoes.append({
            'tipo': 'coletas',
            'quantidade': coletas_necessarias,
            'descricao': f"{coletas_necessarias} coletas (0-40km) de R$ {precos_servicos['coleta_0_40km']}"
        })
        
        # Opção 2: Só palestras
        palestras_necessarias = math.ceil(falta / precos_servicos['palestra'])
        sugestoes.append({
            'tipo': 'palestras',
            'quantidade': palestras_necessarias,
            'descricao': f"{palestras_necessarias} palestras de R$ {precos_servicos['palestra']}"
        })
        
        # Opção 3: Mix equilibrado
        coletas_mix = math.ceil(coletas_necessarias / 2)
        palestras_mix = math.ceil(palestras_necessarias / 2)
        valor_mix = (coletas_mix * precos_servicos['coleta_0_40km']) + (palestras_mix * precos_servicos['palestra'])
        
        sugestoes.append({
            'tipo': 'mix',
            'quantidade': coletas_mix + palestras_mix,
            'descricao': f"{coletas_mix} coletas + {palestras_mix} palestras (R$ {valor_mix:,.2f})"
        })
        
        return sugestoes
    
    @staticmethod
    def calcular_projecao_mes(faturamento_atual, dia_atual, dias_no_mes):
        """Projeta faturamento de fim de mês baseado no ritmo atual"""
        if dia_atual == 0:
            return faturamento_atual
        
        media_diaria = faturamento_atual / dia_atual
        projecao = media_diaria * dias_no_mes
        
        return projecao
    
    @staticmethod
    def atualizar_meta_atual():
        """Atualiza valores da meta do mês atual"""
        meta = ComercialService.get_ou_criar_meta_atual()
        faturamento = ComercialService.calcular_faturamento_mes()
        
        meta.valor_realizado = faturamento
        meta.percentual_atingido = (faturamento / meta.valor_meta * 100) if meta.valor_meta > 0 else 0
        
        # Atualizar status se mês acabou
        hoje = datetime.now()
        ultimo_dia = monthrange(hoje.year, hoje.month)[1]
        
        if hoje.day == ultimo_dia:
            meta.status = 'atingida' if meta.percentual_atingido >= 100 else 'nao_atingida'
        
        db.session.commit()
        return meta
    
    @staticmethod
    def get_dashboard_data():
        """Retorna todos os dados para o dashboard comercial"""
        hoje = datetime.now()
        mes_atual = hoje.month
        ano_atual = hoje.year
        dias_no_mes = monthrange(ano_atual, mes_atual)[1]
        dia_atual = hoje.day
        
        # Meta
        meta = ComercialService.get_ou_criar_meta_atual()
        
        # Faturamento
        faturamento_atual = ComercialService.calcular_faturamento_mes()
        percentual_meta = (faturamento_atual / meta.valor_meta * 100) if meta.valor_meta > 0 else 0
        falta_para_meta = max(0, meta.valor_meta - faturamento_atual)
        
        # Próximas coletas
        proximas = ComercialService.calcular_proximas_coletas(dias=7)
        valor_agendado = ComercialService.calcular_valor_agendado(proximas)
        
        # Clientes inativos
        clientes_inativos = ComercialService.identificar_clientes_inativos(dias=30)
        
        # Sugestões
        sugestoes = ComercialService.gerar_sugestoes_meta(falta_para_meta)
        
        # Projeção
        projecao_fim_mes = ComercialService.calcular_projecao_mes(
            faturamento_atual, 
            dia_atual, 
            dias_no_mes
        )
        
        # Dias úteis restantes
        dias_uteis_restantes = get_dias_uteis_mes(ano_atual, mes_atual) - dia_atual
        
        return {
            'meta': meta.to_dict(),
            'faturamento_atual': faturamento_atual,
            'percentual_meta': percentual_meta,
            'falta_para_meta': falta_para_meta,
            'proximas_coletas': [c.to_dict() for c in proximas],
            'valor_agendado_semana': valor_agendado,
            'clientes_inativos': {
                'quantidade': len(clientes_inativos),
                'lista': [c.to_dict() for c in clientes_inativos[:5]]  # Primeiros 5
            },
            'sugestoes': sugestoes,
            'projecao_fim_mes': projecao_fim_mes,
            'dias_restantes_mes': dias_no_mes - dia_atual,
            'dias_uteis_restantes': dias_uteis_restantes,
            'dia_atual': dia_atual,
            'dias_no_mes': dias_no_mes
        }
```

#### 3.1.5 API Endpoints

```python
# rotas/api/comercial.py

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from banco_dados.services.comercial_service import ComercialService
from banco_dados.modelos import db, MetaComercial
from banco_dados.seguranca import validar_meta_comercial

comercial_bp = Blueprint('comercial_api', __name__, url_prefix='/api/comercial')

@comercial_bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    """
    GET /api/comercial/dashboard
    
    Retorna dados completos do dashboard comercial
    
    Response 200:
    {
        "meta": {...},
        "faturamento_atual": 2749.0,
        "percentual_meta": 22.9,
        "falta_para_meta": 9251.0,
        "proximas_coletas": [...],
        "valor_agendado_semana": 1600.0,
        "clientes_inativos": {...},
        "sugestoes": [...],
        "projecao_fim_mes": 8247.0,
        "dias_restantes_mes": 8,
        "dias_uteis_restantes": 6
    }
    """
    try:
        data = ComercialService.get_dashboard_data()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@comercial_bp.route('/meta', methods=['GET'])
@login_required
def get_meta_atual():
    """
    GET /api/comercial/meta
    
    Retorna meta do mês atual
    """
    try:
        meta = ComercialService.get_ou_criar_meta_atual()
        return jsonify(meta.to_dict()), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@comercial_bp.route('/meta', methods=['PUT'])
@login_required
def atualizar_meta():
    """
    PUT /api/comercial/meta
    
    Atualiza valor da meta mensal
    
    Body:
    {
        "valor_meta": 15000.0,
        "observacoes": "Meta aumentada devido a novo contrato"
    }
    """
    try:
        dados = request.get_json()
        
        # Validação
        erros = validar_meta_comercial(dados)
        if erros:
            return jsonify({'erros': erros}), 400
        
        meta = ComercialService.get_ou_criar_meta_atual()
        meta.valor_meta = dados.get('valor_meta', meta.valor_meta)
        meta.observacoes = dados.get('observacoes', meta.observacoes)
        
        db.session.commit()
        
        return jsonify(meta.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'erro': str(e)}), 500


@comercial_bp.route('/meta/historico', methods=['GET'])
@login_required
def get_historico_metas():
    """
    GET /api/comercial/meta/historico?limite=12
    
    Retorna histórico de metas
    """
    try:
        limite = request.args.get('limite', 12, type=int)
        
        metas = MetaComercial.query.order_by(
            MetaComercial.ano.desc(),
            MetaComercial.mes.desc()
        ).limit(limite).all()
        
        return jsonify([m.to_dict() for m in metas]), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@comercial_bp.route('/atualizar', methods=['POST'])
@login_required
def forcar_atualizacao():
    """
    POST /api/comercial/atualizar
    
    Força atualização da meta com valores atuais
    """
    try:
        meta = ComercialService.atualizar_meta_atual()
        return jsonify(meta.to_dict()), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
```

#### 3.1.6 Frontend - HTML

```html
<!-- templates/comercial/dashboard.html -->

{% extends "base.html" %}

{% block titulo %}Dashboard Comercial - Tronik{% endblock %}

{% block head_extra %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/comercial.css') }}">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
{% endblock %}

{% block conteudo %}
<div class="comercial-container">
    
    <!-- Header -->
    <div class="comercial-header">
        <h1>📊 Dashboard Comercial</h1>
        <div class="header-actions">
            <button onclick="atualizarDados()" class="btn btn-secundario">
                🔄 Atualizar
            </button>
            <button onclick="configurarMeta()" class="btn btn-primario">
                ⚙️ Configurar Meta
            </button>
        </div>
    </div>

    <!-- Indicadores Principais -->
    <div class="kpis-grid">
        
        <!-- Meta Circular -->
        <div class="kpi-card kpi-meta">
            <h3>Meta Mensal</h3>
            <div id="meta-circular" class="circular-chart">
                <!-- Gerado via JS -->
            </div>
            <div class="meta-detalhes">
                <p class="meta-valor">R$ <span id="faturamento-atual">0</span></p>
                <p class="meta-total">de R$ <span id="meta-total">12.000</span></p>
            </div>
        </div>

        <!-- Falta para Meta -->
        <div class="kpi-card kpi-falta">
            <h3>Falta para Atingir</h3>
            <p class="kpi-valor grande">R$ <span id="falta-meta">0</span></p>
            <p class="kpi-descricao">
                <span id="dias-restantes">0</span> dias úteis restantes
            </p>
        </div>

        <!-- Projeção -->
        <div class="kpi-card kpi-projecao">
            <h3>Projeção Fim do Mês</h3>
            <p class="kpi-valor" id="projecao-valor">R$ 0</p>
            <p class="kpi-descricao">
                Baseado no ritmo atual
            </p>
            <div id="projecao-status" class="status-badge"></div>
        </div>

        <!-- Próxima Semana -->
        <div class="kpi-card kpi-agendado">
            <h3>Agendado (7 dias)</h3>
            <p class="kpi-valor">R$ <span id="valor-agendado">0</span></p>
            <p class="kpi-descricao">
                <span id="coletas-agendadas">0</span> coletas
            </p>
        </div>

    </div>

    <!-- Grid Principal -->
    <div class="comercial-grid">
        
        <!-- Coluna Esquerda -->
        <div class="col-esquerda">
            
            <!-- Sugestões -->
            <div class="card">
                <div class="card-header">
                    <h3>💡 Para Atingir a Meta</h3>
                </div>
                <div class="card-body">
                    <ul id="sugestoes-lista" class="sugestoes-lista">
                        <!-- Gerado via JS -->
                    </ul>
                </div>
            </div>

            <!-- Gráfico de Evolução -->
            <div class="card">
                <div class="card-header">
                    <h3>📈 Evolução Mensal</h3>
                </div>
                <div class="card-body">
                    <canvas id="grafico-evolucao"></canvas>
                </div>
            </div>

        </div>

        <!-- Coluna Direita -->
        <div class="col-direita">
            
            <!-- Alertas -->
            <div id="alertas-container">
                <!-- Gerado via JS -->
            </div>

            <!-- Próximas Coletas -->
            <div class="card">
                <div class="card-header">
                    <h3>📅 Próximas Coletas</h3>
                </div>
                <div class="card-body">
                    <div id="proximas-coletas-lista">
                        <!-- Gerado via JS -->
                    </div>
                </div>
            </div>

            <!-- Clientes Inativos -->
            <div class="card">
                <div class="card-header">
                    <h3>⚠️ Clientes Inativos</h3>
                    <span class="badge" id="badge-inativos">0</span>
                </div>
                <div class="card-body">
                    <p class="descricao">Sem coleta há mais de 30 dias</p>
                    <div id="clientes-inativos-lista">
                        <!-- Gerado via JS -->
                    </div>
                    <button onclick="verTodosInativos()" class="btn btn-texto">
                        Ver todos →
                    </button>
                </div>
            </div>

        </div>

    </div>

</div>

<!-- Modal Configurar Meta -->
<div id="modal-meta" class="modal" style="display: none;">
    <div class="modal-content">
        <div class="modal-header">
            <h2>⚙️ Configurar Meta Mensal</h2>
            <button onclick="fecharModalMeta()" class="btn-fechar">&times;</button>
        </div>
        <div class="modal-body">
            <form id="form-meta" onsubmit="salvarMeta(event)">
                <div class="form-group">
                    <label for="valor-meta-input">Valor da Meta (R$)</label>
                    <input 
                        type="number" 
                        id="valor-meta-input" 
                        name="valor_meta"
                        step="0.01"
                        min="0"
                        required
                        placeholder="12000.00"
                    >
                </div>
                <div class="form-group">
                    <label for="observacoes-input">Observações</label>
                    <textarea 
                        id="observacoes-input" 
                        name="observacoes"
                        rows="3"
                        placeholder="Motivo da alteração, contexto..."
                    ></textarea>
                </div>
                <div class="modal-footer">
                    <button type="button" onclick="fecharModalMeta()" class="btn btn-secundario">
                        Cancelar
                    </button>
                    <button type="submit" class="btn btn-primario">
                        Salvar Meta
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>

{% endblock %}

{% block scripts %}
<script src="{{ url_for('static', filename='js/utils/charts.js') }}"></script>
<script src="{{ url_for('static', filename='js/comercial/dashboard.js') }}"></script>
{% endblock %}
```

#### 3.1.7 Frontend - JavaScript

```javascript
// estatico/js/comercial/dashboard.js

let dashboardData = null;
let graficoEvolucao = null;

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    carregarDashboard();
    
    // Atualizar a cada 5 minutos
    setInterval(carregarDashboard, 5 * 60 * 1000);
});

// Carregar todos os dados
async function carregarDashboard() {
    try {
        mostrarLoading(true);
        
        const response = await fetch('/api/comercial/dashboard');
        if (!response.ok) throw new Error('Erro ao carregar dashboard');
        
        dashboardData = await response.json();
        
        renderizarKPIs();
        renderizarSugestoes();
        renderizarProximasColetas();
        renderizarClientesInativos();
        renderizarGraficoEvolucao();
        renderizarAlertas();
        
        mostrarLoading(false);
    } catch (erro) {
        console.error('Erro:', erro);
        mostrarErro('Erro ao carregar dados do dashboard');
        mostrarLoading(false);
    }
}

// Renderizar KPIs principais
function renderizarKPIs() {
    const { 
        meta, 
        faturamento_atual, 
        percentual_meta, 
        falta_para_meta,
        valor_agendado_semana,
        proximas_coletas,
        projecao_fim_mes,
        dias_uteis_restantes
    } = dashboardData;
    
    // Meta circular
    renderizarMetaCircular(percentual_meta);
    
    // Valores
    document.getElementById('faturamento-atual').textContent = 
        formatarMoeda(faturamento_atual);
    document.getElementById('meta-total').textContent = 
        formatarMoeda(meta.valor_meta);
    document.getElementById('falta-meta').textContent = 
        formatarMoeda(falta_para_meta);
    document.getElementById('dias-restantes').textContent = 
        dias_uteis_restantes;
    
    // Projeção
    document.getElementById('projecao-valor').textContent = 
        formatarMoeda(projecao_fim_mes);
    
    const statusProjecao = document.getElementById('projecao-status');
    if (projecao_fim_mes >= meta.valor_meta) {
        statusProjecao.textContent = '✅ No caminho!';
        statusProjecao.className = 'status-badge sucesso';
    } else {
        statusProjecao.textContent = '⚠️ Precisa acelerar';
        statusProjecao.className = 'status-badge atencao';
    }
    
    // Agendado
    document.getElementById('valor-agendado').textContent = 
        formatarMoeda(valor_agendado_semana);
    document.getElementById('coletas-agendadas').textContent = 
        proximas_coletas.length;
}

// Renderizar meta circular (progresso)
function renderizarMetaCircular(percentual) {
    const container = document.getElementById('meta-circular');
    const percentualSeguro = Math.min(percentual, 100);
    
    container.innerHTML = `
        <svg viewBox="0 0 200 200" class="circular-svg">
            <!-- Círculo de fundo -->
            <circle
                cx="100"
                cy="100"
                r="80"
                fill="none"
                stroke="#e0e0e0"
                stroke-width="20"
            />
            <!-- Círculo de progresso -->
            <circle
                cx="100"
                cy="100"
                r="80"
                fill="none"
                stroke="${getCorProgresso(percentual)}"
                stroke-width="20"
                stroke-dasharray="${(percentualSeguro / 100) * 502.65} 502.65"
                stroke-linecap="round"
                transform="rotate(-90 100 100)"
            />
            <!-- Texto central -->
            <text x="100" y="100" text-anchor="middle" dy="0.3em" class="percentual-texto">
                ${percentualSeguro.toFixed(0)}%
            </text>
        </svg>
    `;
}

function getCorProgresso(percentual) {
    if (percentual >= 100) return '#22c55e'; // Verde
    if (percentual >= 70) return '#3b82f6';  // Azul
    if (percentual >= 40) return '#f59e0b';  // Amarelo
    return '#ef4444'; // Vermelho
}

// Renderizar sugestões
function renderizarSugestoes() {
    const { sugestoes } = dashboardData;
    const lista = document.getElementById('sugestoes-lista');
    
    if (!sugestoes || sugestoes.length === 0) {
        lista.innerHTML = '<li class="sugestao-vazio">✅ Meta já atingida!</li>';
        return;
    }
    
    lista.innerHTML = sugestoes.map((s, index) => `
        <li class="sugestao-item">
            <span class="sugestao-numero">${index + 1}</span>
            <span class="sugestao-texto">${s.descricao}</span>
        </li>
    `).join('');
}

// Renderizar próximas coletas
function renderizarProximasColetas() {
    const { proximas_coletas } = dashboardData;
    const container = document.getElementById('proximas-coletas-lista');
    
    if (!proximas_coletas || proximas_coletas.length === 0) {
        container.innerHTML = `
            <p class="vazio">Nenhuma coleta agendada para os próximos 7 dias</p>
            <button onclick="agendarColeta()" class="btn btn-primario btn-block">
                + Agendar Coleta
            </button>
        `;
        return;
    }
    
    container.innerHTML = proximas_coletas.map(coleta => `
        <div class="coleta-item">
            <div class="coleta-data">
                ${formatarDataCurta(coleta.data_coleta)}
            </div>
            <div class="coleta-info">
                <strong>${coleta.coletor?.endereco || 'Cliente'}</strong>
                <span class="coleta-valor">R$ ${coleta.valor?.toFixed(2) || '0.00'}</span>
            </div>
        </div>
    `).join('');
}

// Renderizar clientes inativos
function renderizarClientesInativos() {
    const { clientes_inativos } = dashboardData;
    const badge = document.getElementById('badge-inativos');
    const lista = document.getElementById('clientes-inativos-lista');
    
    badge.textContent = clientes_inativos.quantidade;
    
    if (clientes_inativos.quantidade === 0) {
        lista.innerHTML = '<p class="vazio">✅ Todos os clientes estão ativos!</p>';
        return;
    }
    
    lista.innerHTML = clientes_inativos.lista.map(cliente => `
        <div class="cliente-inativo-item">
            <div class="cliente-info">
                <strong>${cliente.endereco || 'Cliente'}</strong>
                <span class="cliente-distancia">${cliente.distancia_sede?.toFixed(1) || '?'} km</span>
            </div>
            <button onclick="contatarCliente(${cliente.id})" class="btn btn-xs btn-primario">
                📞 Contatar
            </button>
        </div>
    `).join('');
}

// Renderizar alertas
function renderizarAlertas() {
    const { 
        percentual_meta, 
        clientes_inativos,
        dias_uteis_restantes,
        projecao_fim_mes,
        meta
    } = dashboardData;
    
    const container = document.getElementById('alertas-container');
    const alertas = [];
    
    // Alerta: Meta muito longe
    if (percentual_meta < 30 && dias_uteis_restantes < 10) {
        alertas.push({
            tipo: 'erro',
            mensagem: `⚠️ Apenas ${dias_uteis_restantes} dias úteis restantes e meta em ${percentual_meta.toFixed(0)}%!`,
            acao: 'Agendar urgente'
        });
    }
    
    // Alerta: Clientes inativos
    if (clientes_inativos.quantidade > 5) {
        alertas.push({
            tipo: 'atencao',
            mensagem: `${clientes_inativos.quantidade} clientes inativos há mais de 30 dias`,
            acao: 'Reativar clientes'
        });
    }
    
    // Alerta: Projeção baixa
    if (projecao_fim_mes < meta.valor_meta * 0.8) {
        alertas.push({
            tipo: 'atencao',
            mensagem: 'Projeção indica que não atingirá 80% da meta',
            acao: 'Acelerar vendas'
        });
    }
    
    // Alerta: Tudo OK
    if (alertas.length === 0 && percentual_meta > 70) {
        alertas.push({
            tipo: 'sucesso',
            mensagem: '✅ Ótimo ritmo! Continue assim!',
            acao: null
        });
    }
    
    container.innerHTML = alertas.map(alerta => `
        <div class="alerta alerta-${alerta.tipo}">
            <p>${alerta.mensagem}</p>
            ${alerta.acao ? `<button class="btn btn-xs">${alerta.acao}</button>` : ''}
        </div>
    `).join('');
}

// Renderizar gráfico de evolução
async function renderizarGraficoEvolucao() {
    try {
        // Buscar histórico
        const response = await fetch('/api/comercial/meta/historico?limite=6');
        const historico = await response.json();
        
        const ctx = document.getElementById('grafico-evolucao');
        
        // Destruir gráfico anterior se existir
        if (graficoEvolucao) {
            graficoEvolucao.destroy();
        }
        
        const labels = historico.reverse().map(m => `${getNomeMes(m.mes)}/${m.ano}`);
        const metas = historico.map(m => m.valor_meta);
        const realizados = historico.map(m => m.valor_realizado);
        
        graficoEvolucao = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Meta',
                        data: metas,
                        borderColor: '#94a3b8',
                        backgroundColor: 'rgba(148, 163, 184, 0.1)',
                        borderDash: [5, 5]
                    },
                    {
                        label: 'Realizado',
                        data: realizados,
                        borderColor: '#22c55e',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (value) => `R$ ${(value/1000).toFixed(0)}k`
                        }
                    }
                }
            }
        });
    } catch (erro) {
        console.error('Erro ao renderizar gráfico:', erro);
    }
}

// Modal de configuração
function configurarMeta() {
    const { meta } = dashboardData;
    
    document.getElementById('valor-meta-input').value = meta.valor_meta;
    document.getElementById('observacoes-input').value = meta.observacoes || '';
    document.getElementById('modal-meta').style.display = 'flex';
}

function fecharModalMeta() {
    document.getElementById('modal-meta').style.display = 'none';
}

async function salvarMeta(event) {
    event.preventDefault();
    
    try {
        const formData = new FormData(event.target);
        const dados = {
            valor_meta: parseFloat(formData.get('valor_meta')),
            observacoes: formData.get('observacoes')
        };
        
        const response = await fetch('/api/comercial/meta', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        });
        
        if (!response.ok) throw new Error('Erro ao salvar meta');
        
        mostrarSucesso('Meta atualizada com sucesso!');
        fecharModalMeta();
        carregarDashboard();
    } catch (erro) {
        console.error('Erro:', erro);
        mostrarErro('Erro ao salvar meta');
    }
}

// Ações
function agendarColeta() {
    window.location.href = '/configuracoes#nova-coleta';
}

function contatarCliente(clienteId) {
    window.location.href = `/crm?cliente=${clienteId}`;
}

function verTodosInativos() {
    window.location.href = '/crm?filtro=inativos';
}

async function atualizarDados() {
    mostrarLoading(true);
    
    try {
        await fetch('/api/comercial/atualizar', { method: 'POST' });
        await carregarDashboard();
        mostrarSucesso('Dados atualizados!');
    } catch (erro) {
        console.error('Erro:', erro);
        mostrarErro('Erro ao atualizar dados');
    }
    
    mostrarLoading(false);
}

// Utilitários
function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(valor || 0);
}

function formatarDataCurta(dataStr) {
    const data = new Date(dataStr);
    const dia = data.getDate().toString().padStart(2, '0');
    const mes = (data.getMonth() + 1).toString().padStart(2, '0');
    return `${dia}/${mes}`;
}

function getNomeMes(numero) {
    const meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 
                   'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
    return meses[numero - 1];
}

function mostrarLoading(mostrar) {
    // Implementar indicador de loading
}

function mostrarSucesso(mensagem) {
    // Implementar notificação de sucesso
    alert(mensagem);
}

function mostrarErro(mensagem) {
    // Implementar notificação de erro
    alert(mensagem);
}
```

#### 3.1.8 Frontend - CSS

```css
/* estatico/css/comercial.css */

/* Container Principal */
.comercial-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem;
}

.comercial-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
}

.comercial-header h1 {
    font-size: 2rem;
    color: var(--cor-texto-principal);
    margin: 0;
}

.header-actions {
    display: flex;
    gap: 1rem;
}

/* KPIs Grid */
.kpis-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.kpi-card {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s, box-shadow 0.2s;
}

.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.kpi-card h3 {
    font-size: 0.875rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 1rem 0;
}

.kpi-valor {
    font-size: 2rem;
    font-weight: 700;
    color: var(--cor-primaria);
    margin: 0;
}

.kpi-valor.grande {
    font-size: 2.5rem;
}

.kpi-descricao {
    font-size: 0.875rem;
    color: #64748b;
    margin: 0.5rem 0 0 0;
}

/* Meta Circular */
.kpi-meta {
    grid-column: span 1;
}

.circular-chart {
    width: 120px;
    height: 120px;
    margin: 0 auto 1rem;
}

.circular-svg {
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
}

.percentual-texto {
    font-size: 32px;
    font-weight: 700;
    fill: var(--cor-primaria);
    transform: rotate(90deg);
    transform-origin: center;
}

.meta-detalhes {
    text-align: center;
}

.meta-valor {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--cor-primaria);
    margin: 0;
}

.meta-total {
    font-size: 0.875rem;
    color: #64748b;
    margin: 0.25rem 0 0 0;
}

/* Status Badge */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-top: 0.5rem;
}

.status-badge.sucesso {
    background: #dcfce7;
    color: #166534;
}

.status-badge.atencao {
    background: #fef3c7;
    color: #92400e;
}

/* Grid Principal */
.comercial-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 1.5rem;
}

@media (max-width: 1024px) {
    .comercial-grid {
        grid-template-columns: 1fr;
    }
}

/* Cards */
.card {
    background: white;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    margin-bottom: 1.5rem;
}

.card-header {
    padding: 1.5rem;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.card-header h3 {
    font-size: 1.125rem;
    color: var(--cor-texto-principal);
    margin: 0;
}

.card-body {
    padding: 1.5rem;
}

/* Sugestões */
.sugestoes-lista {
    list-style: none;
    padding: 0;
    margin: 0;
}

.sugestao-item {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem 0;
    border-bottom: 1px solid #e2e8f0;
}

.sugestao-item:last-child {
    border-bottom: none;
}

.sugestao-numero {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: var(--cor-primaria);
    color: white;
    border-radius: 50%;
    font-weight: 600;
    font-size: 0.875rem;
    flex-shrink: 0;
}

.sugestao-texto {
    flex: 1;
    color: var(--cor-texto-principal);
}

.sugestao-vazio {
    text-align: center;
    padding: 2rem;
    color: #64748b;
}

/* Gráfico */
#grafico-evolucao {
    height: 300px;
}

/* Alertas */
#alertas-container {
    margin-bottom: 1.5rem;
}

.alerta {
    padding: 1rem;
    border-radius: 8px;
    margin-bottom: 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.alerta p {
    margin: 0;
    flex: 1;
}

.alerta-erro {
    background: #fee2e2;
    border-left: 4px solid #dc2626;
    color: #991b1b;
}

.alerta-atencao {
    background: #fef3c7;
    border-left: 4px solid #f59e0b;
    color: #92400e;
}

.alerta-sucesso {
    background: #dcfce7;
    border-left: 4px solid #22c55e;
    color: #166534;
}

/* Próximas Coletas */
.coleta-item {
    display: flex;
    gap: 1rem;
    padding: 0.75rem 0;
    border-bottom: 1px solid #e2e8f0;
}

.coleta-item:last-child {
    border-bottom: none;
}

.coleta-data {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: var(--cor-primaria-light);
    color: var(--cor-primaria);
    padding: 0.5rem;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.875rem;
    min-width: 60px;
}

.coleta-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.coleta-valor {
    color: var(--cor-primaria);
    font-weight: 600;
}

/* Clientes Inativos */
.badge {
    background: #ef4444;
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
}

.cliente-inativo-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 0;
    border-bottom: 1px solid #e2e8f0;
}

.cliente-inativo-item:last-child {
    border-bottom: none;
}

.cliente-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.cliente-distancia {
    font-size: 0.875rem;
    color: #64748b;
}

.vazio {
    text-align: center;
    padding: 2rem;
    color: #64748b;
}

/* Modal */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 1000;
    align-items: center;
    justify-content: center;
}

.modal-content {
    background: white;
    border-radius: 12px;
    max-width: 500px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
}

.modal-header {
    padding: 1.5rem;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-header h2 {
    margin: 0;
    font-size: 1.5rem;
}

.btn-fechar {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: #64748b;
}

.modal-body {
    padding: 1.5rem;
}

.modal-footer {
    display: flex;
    gap: 1rem;
    justify-content: flex-end;
    margin-top: 1.5rem;
}

.form-group {
    margin-bottom: 1.5rem;
}

.form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: var(--cor-texto-principal);
}

.form-group input,
.form-group textarea {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    font-size: 1rem;
}

.form-group input:focus,
.form-group textarea:focus {
    outline: none;
    border-color: var(--cor-primaria);
}

/* Botões */
.btn {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-primario {
    background: var(--cor-primaria);
    color: white;
}

.btn-primario:hover {
    background: var(--cor-primaria-hover);
}

.btn-secundario {
    background: white;
    color: var(--cor-primaria);
    border: 1px solid var(--cor-primaria);
}

.btn-secundario:hover {
    background: var(--cor-primaria-light);
}

.btn-texto {
    background: none;
    color: var(--cor-primaria);
    padding: 0.5rem;
}

.btn-xs {
    padding: 0.25rem 0.75rem;
    font-size: 0.75rem;
}

.btn-block {
    width: 100%;
    margin-top: 1rem;
}
```

---

### 3.2 CRM COMERCIAL SIMPLIFICADO

#### 3.2.1 Objetivo

Gerenciar relacionamento com clientes, rastrear interações e organizar pipeline de vendas.

#### 3.2.2 Requisitos Funcionais

**RF-CRM-001:** Sistema deve permitir criar/editar leads e oportunidades  
**RF-CRM-002:** Sistema deve rastrear status do pipeline (lead → contato → proposta → negociação → fechado/perdido)  
**RF-CRM-003:** Sistema deve registrar histórico de interações com cliente  
**RF-CRM-004:** Sistema deve alertar sobre próximas ações agendadas  
**RF-CRM-005:** Sistema deve calcular probabilidade de fechamento  
**RF-CRM-006:** Sistema deve mostrar funil visual de vendas  
**RF-CRM-007:** Sistema deve identificar clientes sem contato recente  
**RF-CRM-008:** Sistema deve permitir adicionar tarefas e lembretes  

#### 3.2.3 Modelo de Dados

```python
# banco_dados/modelos.py

class Pipeline(db.Model):
    """Pipeline de vendas/CRM"""
    __tablename__ = 'pipeline'
    
    id = db.Column(db.Integer, primary_key=True)
    coletor_id = db.Column(db.Integer, db.ForeignKey('coletores.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='lead')
    # Status: 'lead', 'contato_inicial', 'proposta_enviada', 'negociacao', 'fechado', 'perdido'
    
    valor_estimado = db.Column(db.Float, default=0.0)
    probabilidade = db.Column(db.Integer, default=10)  # 0-100%
    
    proxima_acao = db.Column(db.String(200))
    data_proxima_acao = db.Column(db.DateTime)
    responsavel_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    
    origem = db.Column(db.String(100))  # 'indicacao', 'site', 'rede_social', 'evento', etc
    tipo_servico = db.Column(db.String(100))  # 'coleta', 'palestra', 'oficina', 'contrato'
    
    observacoes = db.Column(db.Text)
    motivo_perda = db.Column(db.String(200))  # Preenchido se status='perdido'
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fechado_em = db.Column(db.DateTime)
    
    # Relacionamentos
    coletor = db.relationship('Coletor', backref='pipeline_items')
    responsavel = db.relationship('Usuario', backref='pipeline_responsavel')
    interacoes = db.relationship('Interacao', backref='pipeline', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'coletor': self.coletor.to_dict() if self.coletor else None,
            'status': self.status,
            'valor_estimado': self.valor_estimado,
            'probabilidade': self.probabilidade,
            'proxima_acao': self.proxima_acao,
            'data_proxima_acao': self.data_proxima_acao.isoformat() if self.data_proxima_acao else None,
            'responsavel': self.responsavel.nome if self.responsavel else None,
            'origem': self.origem,
            'tipo_servico': self.tipo_servico,
            'observacoes': self.observacoes,
            'motivo_perda': self.motivo_perda,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None,
            'fechado_em': self.fechado_em.isoformat() if self.fechado_em else None,
            'dias_no_pipeline': (datetime.utcnow() - self.criado_em).days if self.criado_em else 0,
            'ultima_interacao': self.interacoes.order_by(Interacao.data.desc()).first().to_dict() if self.interacoes.first() else None
        }


class Interacao(db.Model):
    """Registro de interações com cliente"""
    __tablename__ = 'interacoes'
    
    id = db.Column(db.Integer, primary_key=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipeline.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    # Tipo: 'ligacao', 'email', 'whatsapp', 'reuniao', 'visita', 'proposta', 'outro'
    
    descricao = db.Column(db.Text, nullable=False)
    resultado = db.Column(db.String(100))  # 'positivo', 'neutro', 'negativo'
    
    data = db.Column(db.DateTime, default=datetime.utcnow)
    duracao_minutos = db.Column(db.Integer)
    
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    usuario = db.relationship('Usuario', backref='interacoes')
    
    anexos = db.Column(db.JSON)  # Lista de URLs de arquivos anexados
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'pipeline_id': self.pipeline_id,
            'tipo': self.tipo,
            'descricao': self.descricao,
            'resultado': self.resultado,
            'data': self.data.isoformat() if self.data else None,
            'duracao_minutos': self.duracao_minutos,
            'usuario': self.usuario.nome if self.usuario else None,
            'anexos': self.anexos,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None
        }


class Tarefa(db.Model):
    """Tarefas e lembretes"""
    __tablename__ = 'tarefas'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    
    pipeline_id = db.Column(db.Integer, db.ForeignKey('pipeline.id'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    status = db.Column(db.String(20), default='pendente')  # 'pendente', 'concluida', 'cancelada'
    prioridade = db.Column(db.String(20), default='media')  # 'baixa', 'media', 'alta', 'urgente'
    
    data_vencimento = db.Column(db.DateTime)
    concluida_em = db.Column(db.DateTime)
    
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    pipeline = db.relationship('Pipeline', backref='tarefas')
    usuario = db.relationship('Usuario', backref='tarefas')
    
    def to_dict(self):
        return {
            'id': self.id,
            'titulo': self.titulo,
            'descricao': self.descricao,
            'pipeline_id': self.pipeline_id,
            'cliente': self.pipeline.coletor.endereco if self.pipeline and self.pipeline.coletor else None,
            'usuario': self.usuario.nome if self.usuario else None,
            'status': self.status,
            'prioridade': self.prioridade,
            'data_vencimento': self.data_vencimento.isoformat() if self.data_vencimento else None,
            'concluida_em': self.concluida_em.isoformat() if self.concluida_em else None,
            'atrasada': self.data_vencimento < datetime.utcnow() if self.data_vencimento and self.status == 'pendente' else False,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None
        }
```

#### 3.2.4 Service Layer

```python
# banco_dados/services/crm_service.py

from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func
from banco_dados.modelos import db, Pipeline, Interacao, Tarefa, Coletor

class CRMService:
    """Serviço para lógica de CRM"""
    
    # Mapeamento de status para probabilidade padrão
    STATUS_PROBABILIDADE = {
        'lead': 10,
        'contato_inicial': 25,
        'proposta_enviada': 50,
        'negociacao': 75,
        'fechado': 100,
        'perdido': 0
    }
    
    @staticmethod
    def criar_pipeline(dados, usuario_id=None):
        """Cria novo item no pipeline"""
        pipeline = Pipeline(
            coletor_id=dados['coletor_id'],
            status=dados.get('status', 'lead'),
            valor_estimado=dados.get('valor_estimado', 0.0),
            probabilidade=dados.get('probabilidade', CRMService.STATUS_PROBABILIDADE.get(dados.get('status', 'lead'), 10)),
            proxima_acao=dados.get('proxima_acao'),
            data_proxima_acao=dados.get('data_proxima_acao'),
            responsavel_id=usuario_id,
            origem=dados.get('origem'),
            tipo_servico=dados.get('tipo_servico'),
            observacoes=dados.get('observacoes')
        )
        
        db.session.add(pipeline)
        db.session.commit()
        
        # Registrar interação inicial
        if dados.get('descricao_inicial'):
            CRMService.registrar_interacao(
                pipeline.id,
                tipo='outro',
                descricao=dados['descricao_inicial'],
                usuario_id=usuario_id
            )
        
        return pipeline
    
    @staticmethod
    def atualizar_status(pipeline_id, novo_status, motivo_perda=None):
        """Atualiza status do pipeline"""
        pipeline = Pipeline.query.get_or_404(pipeline_id)
        pipeline.status = novo_status
        pipeline.probabilidade = CRMService.STATUS_PROBABILIDADE.get(novo_status, pipeline.probabilidade)
        
        if novo_status == 'perdido':
            pipeline.motivo_perda = motivo_perda
            pipeline.fechado_em = datetime.utcnow()
        elif novo_status == 'fechado':
            pipeline.fechado_em = datetime.utcnow()
        
        db.session.commit()
        return pipeline
    
    @staticmethod
    def registrar_interacao(pipeline_id, tipo, descricao, resultado=None, usuario_id=None, duracao_minutos=None):
        """Registra interação com cliente"""
        interacao = Interacao(
            pipeline_id=pipeline_id,
            tipo=tipo,
            descricao=descricao,
            resultado=resultado,
            duracao_minutos=duracao_minutos,
            usuario_id=usuario_id
        )
        
        db.session.add(interacao)
        
        # Atualizar data da última interação no pipeline
        pipeline = Pipeline.query.get(pipeline_id)
        if pipeline:
            pipeline.atualizado_em = datetime.utcnow()
        
        db.session.commit()
        return interacao
    
    @staticmethod
    def get_funil_vendas():
        """Retorna dados do funil de vendas"""
        funil = db.session.query(
            Pipeline.status,
            func.count(Pipeline.id).label('quantidade'),
            func.sum(Pipeline.valor_estimado).label('valor_total'),
            func.avg(Pipeline.probabilidade).label('probabilidade_media')
        ).filter(
            Pipeline.status.in_(['lead', 'contato_inicial', 'proposta_enviada', 'negociacao'])
        ).group_by(Pipeline.status).all()
        
        return [
            {
                'status': item.status,
                'quantidade': item.quantidade,
                'valor_total': float(item.valor_total or 0),
                'probabilidade_media': float(item.probabilidade_media or 0)
            }
            for item in funil
        ]
    
    @staticmethod
    def get_proximas_acoes(dias=7):
        """Retorna ações agendadas para os próximos N dias"""
        hoje = datetime.now()
        fim = hoje + timedelta(days=dias)
        
        pipelines = Pipeline.query.filter(
            Pipeline.data_proxima_acao.between(hoje, fim),
            Pipeline.status.notin_(['fechado', 'perdido'])
        ).order_by(Pipeline.data_proxima_acao).all()
        
        return pipelines
    
    @staticmethod
    def get_clientes_sem_contato(dias=30):
        """Identifica clientes sem interação há N dias"""
        limite = datetime.now() - timedelta(days=dias)
        
        # Subquery: pipelines com interação recente
        pipelines_ativos_ids = db.session.query(Interacao.pipeline_id).filter(
            Interacao.data >= limite
        ).distinct().subquery()
        
        # Pipelines sem interação recente (excluindo fechados/perdidos)
        pipelines_sem_contato = Pipeline.query.filter(
            ~Pipeline.id.in_(pipelines_ativos_ids),
            Pipeline.status.notin_(['fechado', 'perdido'])
        ).all()
        
        return pipelines_sem_contato
    
    @staticmethod
    def get_estatisticas_periodo(data_inicio, data_fim):
        """Retorna estatísticas do período"""
        pipelines_criados = Pipeline.query.filter(
            Pipeline.criado_em.between(data_inicio, data_fim)
        ).count()
        
        pipelines_fechados = Pipeline.query.filter(
            Pipeline.fechado_em.between(data_inicio, data_fim),
            Pipeline.status == 'fechado'
        ).count()
        
        pipelines_perdidos = Pipeline.query.filter(
            Pipeline.fechado_em.between(data_inicio, data_fim),
            Pipeline.status == 'perdido'
        ).count()
        
        valor_fechado = db.session.query(func.sum(Pipeline.valor_estimado)).filter(
            Pipeline.fechado_em.between(data_inicio, data_fim),
            Pipeline.status == 'fechado'
        ).scalar() or 0
        
        taxa_conversao = (pipelines_fechados / pipelines_criados * 100) if pipelines_criados > 0 else 0
        
        return {
            'pipelines_criados': pipelines_criados,
            'pipelines_fechados': pipelines_fechados,
            'pipelines_perdidos': pipelines_perdidos,
            'valor_fechado': float(valor_fechado),
            'taxa_conversao': taxa_conversao
        }
    
    @staticmethod
    def criar_tarefa(dados, usuario_id):
        """Cria nova tarefa"""
        tarefa = Tarefa(
            titulo=dados['titulo'],
            descricao=dados.get('descricao'),
            pipeline_id=dados.get('pipeline_id'),
            usuario_id=usuario_id,
            prioridade=dados.get('prioridade', 'media'),
            data_vencimento=dados.get('data_vencimento')
        )
        
        db.session.add(tarefa)
        db.session.commit()
        return tarefa
    
    @staticmethod
    def concluir_tarefa(tarefa_id):
        """Marca tarefa como concluída"""
        tarefa = Tarefa.query.get_or_404(tarefa_id)
        tarefa.status = 'concluida'
        tarefa.concluida_em = datetime.utcnow()
        db.session.commit()
        return tarefa
    
    @staticmethod
    def get_tarefas_pendentes(usuario_id=None):
        """Retorna tarefas pendentes"""
        query = Tarefa.query.filter_by(status='pendente')
        
        if usuario_id:
            query = query.filter_by(usuario_id=usuario_id)
        
        return query.order_by(Tarefa.data_vencimento.asc()).all()
    
    @staticmethod
    def get_tarefas_atrasadas(usuario_id=None):
        """Retorna tarefas atrasadas"""
        hoje = datetime.now()
        query = Tarefa.query.filter(
            Tarefa.status == 'pendente',
            Tarefa.data_vencimento < hoje
        )
        
        if usuario_id:
            query = query.filter_by(usuario_id=usuario_id)
        
        return query.order_by(Tarefa.data_vencimento.asc()).all()
```

[Continuação no próximo arquivo devido ao limite de caracteres...]
