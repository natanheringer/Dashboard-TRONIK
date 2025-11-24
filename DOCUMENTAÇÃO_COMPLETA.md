# 📚 Documentação Completa do Sistema Dashboard-TRONIK

**Versão:** 2.1  
**Data:** 24 de Novembro de 2025  
**Última Atualização:** 24 de Novembro de 2025

---

## 📋 Índice

1. [Visão Geral do Sistema](#1-visão-geral-do-sistema)
2. [Arquitetura do Sistema](#2-arquitetura-do-sistema)
3. [Backend - Flask Application](#3-backend---flask-application)
4. [Banco de Dados](#4-banco-de-dados)
5. [Sistema de Autenticação](#5-sistema-de-autenticação)
6. [API REST](#6-api-rest)
7. [Frontend](#7-frontend)
8. [Sistema de Roteamento](#8-sistema-de-roteamento)
9. [Sistema de Notificações](#9-sistema-de-notificações)
10. [Geocodificação](#10-geocodificação)
11. [Testes Automatizados](#11-testes-automatizados)
12. [Docker e Deploy](#12-docker-e-deploy)
13. [Segurança](#13-segurança)
14. [Módulos e Utilitários](#14-módulos-e-utilitários)
15. [Scripts e Ferramentas](#15-scripts-e-ferramentas)

---

## 1. Visão Geral do Sistema

### 1.1 Descrição

O **Dashboard-TRONIK** é um sistema web completo de monitoramento e gestão de coletores inteligentes para a empresa Tronik Recicla. O sistema permite visualizar em tempo real o status de coletores equipadas com sensores, gerenciar coletas, gerar relatórios financeiros e operacionais, calcular rotas otimizadas para equipes de coleta, e enviar notificações automáticas por email.

### 1.2 Objetivos

- **Monitoramento em Tempo Real**: Visualização do nível de preenchimento e status de cada coletor
- **Gestão de Coletas**: Registro e histórico completo de coletas realizadas
- **Análise Financeira**: Cálculo de custos, lucros e métricas operacionais
- **Otimização de Rotas**: Sistema avançado de cálculo de rotas com múltiplos algoritmos
- **Notificações Automáticas**: Alertas por email quando coletores estão cheias ou sensores com bateria baixa
- **Geocodificação Automática**: Conversão automática de endereços em coordenadas geográficas

### 1.3 Stack Tecnológico

#### Backend
- **Python 3.11+**: Linguagem principal
- **Flask 2.3.3**: Framework web
- **SQLAlchemy 2.0.23+**: ORM para banco de dados
- **Flask-Login 0.6.3**: Gerenciamento de sessões
- **Flask-Limiter 3.5.0**: Rate limiting
- **Flask-Talisman 1.1.0**: Headers de segurança HTTP
- **Flask-Mail 0.9.1**: Envio de emails
- **APScheduler 3.10.4**: Agendamento de tarefas
- **ReportLab 4.0.7**: Geração de PDFs

#### Frontend
- **HTML5**: Estrutura das páginas
- **CSS3**: Estilização (método BEM)
- **JavaScript (ES6+)**: Lógica do cliente (vanilla, sem frameworks)
- **Leaflet.js 1.9.4**: Mapas interativos
- **Leaflet.markercluster 1.5.3**: Agrupamento de marcadores
- **Leaflet Routing Machine 3.2.12**: Cálculo e exibição de rotas
- **Chart.js**: Gráficos e visualizações (via CDN)

#### Banco de Dados
- **SQLite**: Banco de dados relacional (desenvolvimento)
- **Suporte a PostgreSQL/MySQL**: Via SQLAlchemy (produção)

#### DevOps
- **Docker**: Containerização
- **Docker Compose**: Orquestração
- **Gunicorn**: Servidor WSGI (produção)

### 1.4 Estrutura de Diretórios

```
dashboard-Tronik/
├── app.py                          # Aplicação Flask principal
├── requirements.txt                # Dependências Python
├── Dockerfile                      # Imagem Docker
├── docker-compose.yml              # Orquestração Docker
├── .env                            # Variáveis de ambiente (não versionado)
├── pytest.ini                      # Configuração do Pytest
│
├── banco_dados/                    # Módulo de banco de dados
│   ├── __init__.py
│   ├── modelos.py                  # Modelos SQLAlchemy
│   ├── inicializar.py              # Inicialização do banco
│   ├── seed_tipos.py               # População de tipos
│   ├── seguranca.py                # Validações e sanitização
│   ├── utils.py                    # Utilitários (datetime)
│   ├── geocodificacao.py           # Geocodificação Nominatim
│   ├── geocodificar_coletores.py    # Script CLI de geocodificação
│   ├── importar_csv.py             # Importação de dados CSV
│   ├── migrar_dados.py             # Migração de dados
│   ├── migrar_notificacoes.py      # Migração de notificações
│   ├── notificacoes.py             # Sistema de notificações
│   ├── agendamento.py              # Agendamento APScheduler
│   └── dados/                      # Dados mock
│       └── sensores_mock.json
│
├── rotas/                          # Rotas Flask (Blueprints)
│   ├── api.py                      # API REST (30+ endpoints)
│   ├── auth.py                     # Autenticação (login, logout, registro)
│   └── paginas.py                  # Páginas web (7 rotas)
│
├── templates/                      # Templates Jinja2
│   ├── base.html                   # Template base
│   ├── index.html                  # Dashboard principal
│   ├── login.html                  # Página de login
│   ├── registro.html               # Página de registro
│   ├── mapa.html                   # Página de mapa
│   ├── relatorios.html             # Página de relatórios
│   ├── configuracoes.html          # Página de configurações
│   ├── notificacoes.html           # Página de notificações
│   └── sobre.html                  # Página sobre
│
├── estatico/                       # Arquivos estáticos
│   ├── css/                        # Folhas de estilo
│   │   ├── estilo.css              # Estilos principais
│   │   ├── auth.css                # Estilos de autenticação
│   │   ├── mapa.css                # Estilos do mapa
│   │   ├── relatorios.css          # Estilos de relatórios
│   │   ├── configuracoes.css       # Estilos de configurações
│   │   ├── notificacoes.css        # Estilos de notificações
│   │   ├── sobre.css               # Estilos da página sobre
│   │   └── menu-mobile.css         # Estilos do menu mobile
│   │
│   └── js/                         # Scripts JavaScript
│       ├── api.js                  # Cliente API (funções HTTP)
│       ├── dashboard.js            # Lógica do dashboard
│       ├── mapa.js                 # Módulo de mapa (Leaflet)
│       ├── mapa-page.js            # Lógica da página de mapa
│       ├── relatorios.js           # Lógica de relatórios
│       ├── configuracoes.js        # Lógica de configurações
│       ├── notificacoes.js         # Lógica de notificações
│       ├── menu.js                 # Menu hambúrguer
│       ├── routing-pt.js           # Localização PT para rotas
│       └── routing/                # Sistema de roteamento
│           ├── algoritmos.js       # A*, Dijkstra, Bidirectional
│           ├── heuristicas.js      # Heurísticas geográficas
│           ├── cache.js             # Cache IndexedDB
│           ├── osm.js               # Integração OpenStreetMap
│           ├── suavizacao.js       # Suavização de rotas
│           ├── aprendizado.js       # Aprendizado adaptativo
│           ├── otimizacao.js       # Otimizações de performance
│           └── router.js            # Router principal
│
├── tests/                          # Testes automatizados
│   ├── conftest.py                 # Configuração e fixtures
│   ├── test_api_coletores.py        # Testes de API de coletores
│   ├── test_api_coletas.py         # Testes de API de coletas
│   ├── test_api_sensores.py        # Testes de API de sensores
│   ├── test_api_atualizacao_exclusao.py  # Testes de atualização/exclusão
│   ├── test_api_endpoints_restantes.py    # Testes de outros endpoints
│   ├── test_auth.py                # Testes de autenticação
│   ├── test_validacoes.py          # Testes de validações
│   ├── test_geocodificacao.py      # Testes de geocodificação
│   └── test_estatisticas_relatorios.py    # Testes de relatórios
│
├── scripts/                        # Scripts auxiliares
│   └── processar_alertas.py        # CLI para processar alertas
│
├── deploy/                         # Configurações de deploy
│   ├── env.example                 # Exemplo de variáveis de ambiente
│   ├── dashboard-tronik.service    # Systemd service
│   └── nginx/                      # Configuração Nginx
│       └── tronik.conf
│
└── docs/                           # Documentação
    ├── Especificacao_Tecnica.md
    ├── MVP.md
    └── Planejamento.md
```

---

## 2. Arquitetura do Sistema

### 2.1 Arquitetura Geral

O sistema segue uma arquitetura **MVC (Model-View-Controller)** adaptada para Flask:

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENTE (Browser)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   HTML/CSS   │  │  JavaScript  │  │   Leaflet    │      │
│  │  (Templates) │  │  (Frontend)  │  │   (Mapas)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP/REST API
┌─────────────────────────────────────────────────────────────┐
│                    SERVIDOR FLASK (Backend)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Blueprints │  │   Business   │  │  Validações  │      │
│  │   (Rotas)    │  │    Logic     │  │  & Segurança │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   SQLAlchemy │  │  Notificações│  │ Agendamento  │      │
│  │    (ORM)     │  │   (Email)    │  │ (APScheduler)│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↕ SQL
┌─────────────────────────────────────────────────────────────┐
│                    BANCO DE DADOS (SQLite)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Lixeiras   │  │   Coletas    │  │  Sensores    │      │
│  │   Usuários   │  │ Notificações │  │  Parceiros   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Padrões de Design

#### 2.2.1 Blueprint Pattern (Flask)
O sistema utiliza **Blueprints** do Flask para organizar rotas em módulos:

- **`api_bp`**: Todas as rotas da API REST (`/api/*`)
- **`auth_bp`**: Rotas de autenticação (`/auth/*`)
- **`paginas_bp`**: Rotas de páginas web (`/`, `/mapa`, `/relatorios`, etc.)

#### 2.2.2 Repository Pattern (SQLAlchemy)
Os modelos SQLAlchemy atuam como repositórios, encapsulando acesso aos dados:

```python
# Exemplo: banco_dados/modelos.py
class Coletor(Base):
    __tablename__ = "coletores"
    # ... campos ...
    # Relacionamentos automáticos via SQLAlchemy
```

#### 2.2.3 Service Layer Pattern
Lógica de negócio separada em módulos:

- **`banco_dados/notificacoes.py`**: Lógica de notificações
- **`banco_dados/geocodificacao.py`**: Lógica de geocodificação
- **`banco_dados/agendamento.py`**: Lógica de agendamento

#### 2.2.4 Module Pattern (JavaScript)
Frontend organizado em módulos ES6:

```javascript
// estatico/js/mapa.js
const MapaTronik = (function() {
    // Código privado
    let mapa = null;
    
    // API pública
    return {
        inicializar: function() { /* ... */ },
        adicionarMarcador: function() { /* ... */ }
    };
})();
```

### 2.3 Fluxo de Dados

#### 2.3.1 Fluxo de Requisição HTTP

```
1. Cliente (Browser)
   ↓ HTTP Request
2. Flask App (app.py)
   ↓ Roteamento
3. Blueprint (rotas/api.py, rotas/auth.py, etc.)
   ↓ Validação & Autenticação
4. Business Logic (banco_dados/*.py)
   ↓ SQLAlchemy ORM
5. Banco de Dados (SQLite)
   ↓ Query Results
6. Serialização (JSON)
   ↓ HTTP Response
7. Cliente (Browser)
```

#### 2.3.2 Fluxo de Autenticação

```
1. Usuário acessa /auth/login
   ↓
2. Flask-Login verifica sessão
   ↓ (não autenticado)
3. Renderiza login.html
   ↓ (usuário submete credenciais)
4. auth.py valida credenciais
   ↓ (válidas)
5. Flask-Login cria sessão
   ↓
6. Redireciona para / (dashboard)
```

#### 2.3.3 Fluxo de Notificações

```
1. APScheduler (agendamento.py)
   ↓ (a cada 60 minutos)
2. processar_alertas_job()
   ↓
3. notificacoes.py::processar_alertas()
   ↓
4. verificar_alertas_lixeiras() / verificar_alertas_sensores()
   ↓ (alertas encontrados)
5. criar_notificacao() → Banco de Dados
   ↓
6. enviar_email_notificacao() → Flask-Mail
   ↓
7. Email enviado para administradores
```

---

## 3. Backend - Flask Application

### 3.1 Aplicação Principal (app.py)

O arquivo `app.py` é o ponto de entrada da aplicação Flask. Ele configura todos os componentes do sistema.

#### 3.1.1 Configurações de Segurança

```python
# SECRET_KEY - CRÍTICO para sessões
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Headers de segurança HTTP
talisman = Talisman(
    app,
    force_https=FLASK_ENV == 'production',
    strict_transport_security=True,
    content_security_policy={
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        'style-src': "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        'connect-src': "'self' https://cdn.jsdelivr.net https://router.project-osrm.org",
        # ...
    }
)

# Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
```

#### 3.1.2 Flask-Login

```python
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.session_protection = 'strong'

@login_manager.user_loader
def load_user(user_id):
    """Carrega usuário para sessão"""
    # ...
```

#### 3.1.3 Flask-Mail (Notificações)

```python
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', '')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
# ...

if app.config['MAIL_SERVER']:
    inicializar_mail(app)
```

#### 3.1.4 APScheduler (Agendamento)

```python
from banco_dados.agendamento import inicializar_agendamento
inicializar_agendamento(app)
```

#### 3.1.5 Banco de Dados

```python
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///tronik.db')
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = scoped_session(sessionmaker(bind=engine))
app.config['DATABASE_SESSION'] = SessionLocal

# Criar tabelas
Base.metadata.create_all(engine)

# Popular tipos
popular_tipos(engine)

# Criar usuário admin
criar_usuario_admin(engine)
```

#### 3.1.6 Blueprints

```python
app.register_blueprint(auth_bp)    # Autenticação primeiro
app.register_blueprint(api_bp)     # API REST
app.register_blueprint(paginas_bp) # Páginas web
```

#### 3.1.7 Tratamento de Erros

```python
@app.errorhandler(404)
def not_found(error):
    # ...

@app.errorhandler(403)
def forbidden(error):
    # ...

@app.errorhandler(429)
def ratelimit_handler(e):
    # ...

@app.errorhandler(500)
def internal_error(error):
    # ...
```

### 3.2 Blueprints

#### 3.2.1 API Blueprints (Modularizados)

**55+ endpoints REST** organizados em blueprints especializados:

**Coletores (`rotas/api/coletores.py`):**
- `GET /api/coletores` - Listar todas
- `GET /api/coletor/<id>` - Detalhes
- `POST /api/coletor` - Criar (autenticado)
- `PUT /api/coletor/<id>` - Atualizar (autenticado)
- `DELETE /api/coletor/<id>` - Deletar (admin)
- `POST /api/coletor/<id>/geocodificar` - Geocodificar manualmente

**Nota:** Sistema migrado de "lixeira" para "coletor" em toda a aplicação (novembro 2025).

**Coletas:**
- `GET /api/coletas` - Listar com filtros
- `GET /api/historico` - Histórico com filtro de data
- `POST /api/coleta` - Criar nova coleta

**Sensores:**
- `GET /api/sensores` - Listar com filtros
- `GET /api/sensor/<id>` - Detalhes
- `POST /api/sensor` - Criar (autenticado)
- `PUT /api/sensor/<id>` - Atualizar (autenticado)
- `DELETE /api/sensor/<id>` - Deletar (admin)

**Notificações:**
- `GET /api/notificacoes` - Listar com filtros
- `POST /api/notificacoes/processar-alertas` - Processar alertas (admin)
- `PUT /api/notificacoes/<id>/marcar-lida` - Marcar como lida
- `GET /api/notificacoes/pendentes-count` - Contagem de pendentes
- `GET /api/notificacoes/status-agendamento` - Status do agendamento

**Relatórios:**
- `GET /api/relatorios` - Dados para relatórios
- `GET /api/relatorios/exportar-pdf` - Exportar PDF

**Auxiliares (`rotas/api/auxiliares.py`):**
- `GET /api/estatisticas` - Estatísticas gerais
- `GET /api/configuracoes` - Configurações do sistema
- `GET /api/parceiros` - Listar parceiros
- `GET /api/tipos/material` - Tipos de material
- `GET /api/tipos/sensor` - Tipos de sensor
- `GET /api/tipos/coletor` - Tipos de coletor
- `POST /api/coletores/simular-niveis` - Simular níveis

**Comercial (`rotas/api/comercial.py`):**
- `GET /api/comercial/dashboard` - Dados do dashboard comercial
- `GET /api/comercial/meta` - Meta mensal atual
- `PUT /api/comercial/meta` - Atualizar meta
- `GET /api/comercial/meta/historico` - Histórico de metas
- `GET /api/comercial/metricas` - Métricas financeiras detalhadas
- `GET /api/comercial/parceiros` - Análise por parceiro
- `GET /api/comercial/comparar` - Comparação com mês anterior
- `POST /api/comercial/layout` - Salvar layout personalizado
- `GET /api/comercial/layout` - Obter layout salvo

**CRM (`rotas/api/crm.py`):**
- `GET /api/crm/pipeline` - Listar pipeline de vendas
- `POST /api/crm/pipeline` - Criar novo lead/pipeline
- `GET /api/crm/pipeline/<id>` - Detalhes do pipeline
- `PUT /api/crm/pipeline/<id>/status` - Atualizar status
- `POST /api/crm/pipeline/<id>/interacoes` - Registrar interação
- `GET /api/crm/funil` - Dados do funil de vendas (Kanban)
- `GET /api/crm/estatisticas` - Estatísticas do CRM
- `GET /api/crm/tarefas` - Listar tarefas pendentes
- `POST /api/crm/tarefas` - Criar nova tarefa
- `POST /api/crm/tarefas/<id>/concluir` - Concluir tarefa

**Contratos (`rotas/api/contratos.py`):**
- `GET /api/contratos` - Listar contratos recorrentes
- `POST /api/contratos` - Criar novo contrato
- `GET /api/contratos/<id>` - Detalhes do contrato
- `PUT /api/contratos/<id>` - Atualizar contrato
- `POST /api/contratos/<id>/cancelar` - Cancelar contrato
- `GET /api/contratos/receita-mensal` - Calcular receita mensal
- `GET /api/contratos/vencendo` - Contratos vencendo

**Características:**
- Rate limiting por endpoint
- Validação de dados com `banco_dados/seguranca.py`
- Autenticação via `@login_required`
- Permissões admin via `@admin_required`
- Eager loading com `joinedload()` para performance
- Tratamento de erros com logging
- **Todos os endpoints verificados e corrigidos (novembro 2025)**
- **Migração completa: lixeira → coletor**

#### 3.2.2 Auth Blueprint (`rotas/auth.py`)

**Rotas de Autenticação:**

- `GET/POST /auth/login` - Login de usuário
- `GET/POST /auth/logout` - Logout
- `GET/POST /auth/registro` - Registro de novo usuário
- `GET /auth/usuario/atual` - Informações do usuário atual

**Funcionalidades:**
- Validação de credenciais
- Sanitização de inputs
- Sessões seguras via Flask-Login
- Suporte a JSON e formulários HTML
- Logging de tentativas de login

#### 3.2.3 Páginas Blueprint (`rotas/paginas.py`)

**Rotas de Páginas Web:**

- `GET /` - Dashboard principal (`index.html`)
- `GET /relatorios` - Página de relatórios
- `GET /configuracoes` - Página de configurações
- `GET /mapa` - Página de mapa
- `GET /notificacoes` - Página de notificações
- `GET /sobre` - Página sobre (pública)

**Proteção:**
- Todas as rotas (exceto `/sobre`) requerem `@login_required`

---

## 4. Banco de Dados

### 4.1 Modelos de Dados

O sistema utiliza **SQLAlchemy ORM** com padrão **Declarative Base**. Todos os modelos estão em `banco_dados/modelos.py`.

#### 4.1.1 Modelo: Usuario

```python
class Usuario(Base, UserMixin):
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    nome_completo = Column(String(150))
    ativo = Column(Boolean, default=True)
    admin = Column(Boolean, default=False)
    criado_em = Column(DateTime, default=utc_now_naive)
    ultimo_login = Column(DateTime)
    
    # Métodos
    def set_senha(self, senha)
    def verificar_senha(self, senha)
```

**Campos:**
- `id`: Chave primária auto-incrementada
- `username`: Nome de usuário único (3-30 caracteres)
- `email`: Email único
- `senha_hash`: Hash bcrypt da senha (via Werkzeug)
- `nome_completo`: Nome completo opcional
- `ativo`: Status de ativação
- `admin`: Permissões administrativas
- `criado_em`: Data de criação
- `ultimo_login`: Último login

**Segurança:**
- Senhas nunca armazenadas em texto plano
- Hash bcrypt com salt automático
- Validação de força de senha (mínimo 8 caracteres, maiúscula, minúscula, número)

#### 4.1.2 Modelo: Parceiro

```python
class Parceiro(Base):
    __tablename__ = "parceiros"
    
    id = Column(Integer, primary_key=True)
    nome = Column(String(150), unique=True, nullable=False, index=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=utc_now_naive)
    
    # Relacionamentos
    coletores = relationship("Coletor", back_populates="parceiro")
    coletas = relationship("Coleta", back_populates="parceiro")
```

**Uso:** Representa clientes/parceiros da Tronik que possuem coletores.

#### 4.1.3 Modelo: TipoMaterial

```python
class TipoMaterial(Base):
    __tablename__ = "tipo_material"
    
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False, index=True)
    
    # Relacionamentos
    coletores = relationship("Coletor", back_populates="tipo_material")
```

**Valores comuns:** "Plástico", "Papel", "Metal", "Vidro", "Orgânico", etc.

#### 4.1.4 Modelo: TipoSensor

```python
class TipoSensor(Base):
    __tablename__ = "tipo_sensor"
    
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False, index=True)
    
    # Relacionamentos
    sensores = relationship("Sensor", back_populates="tipo_sensor")
```

**Valores comuns:** "Ultrassônico", "Infravermelho", "Peso", etc.

#### 4.1.5 Modelo: TipoColetor

```python
class TipoColetor(Base):
    __tablename__ = "tipo_coletor"
    
    id = Column(Integer, primary_key=True)
    nome = Column(String(100), unique=True, nullable=False, index=True)
    
    # Relacionamentos
    coletas = relationship("Coleta", back_populates="tipo_coletor")
```

**Valores comuns:** "Caminhão", "Carreta", "Van", etc.

#### 4.1.6 Modelo: Coletor

**Nota:** Este modelo foi renomeado de `Lixeira` para `Coletor` em novembro de 2025 para refletir a terminologia usada pela empresa.

```python
class Coletor(Base):
    __tablename__ = "coletores"
    
    id = Column(Integer, primary_key=True)
    localizacao = Column(String(150), nullable=False)
    nivel_preenchimento = Column(Float, default=0.0)  # 0-100%
    status = Column(String(20), default="OK")  # OK, CHEIA, QUEBRADA
    ultima_coleta = Column(DateTime, default=utc_now_naive)
    
    # Coordenadas geográficas
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Relacionamentos
    parceiro_id = Column(Integer, ForeignKey("parceiros.id"), nullable=True, index=True)
    tipo_material_id = Column(Integer, ForeignKey("tipo_material.id"), nullable=True, index=True)
    
    # Relacionamentos ORM
    parceiro = relationship("Parceiro", back_populates="coletores")
    tipo_material = relationship("TipoMaterial", back_populates="coletores")
    sensores = relationship("Sensor", back_populates="coletor", cascade="all, delete-orphan")
    coletas = relationship("Coleta", back_populates="coletor", cascade="all, delete-orphan")
```

**Campos:**
- `localizacao`: Endereço/nome da localização
- `nivel_preenchimento`: Percentual de preenchimento (0-100)
- `status`: Status operacional
- `ultima_coleta`: Data/hora da última coleta
- `latitude`/`longitude`: Coordenadas geográficas (para mapas)

**Cascata:**
- Ao deletar coletor, sensores e coletas são deletados automaticamente

#### 4.1.7 Modelo: Sensor

```python
class Sensor(Base):
    __tablename__ = "sensores"
    
    id = Column(Integer, primary_key=True)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=False, index=True)
    tipo_sensor_id = Column(Integer, ForeignKey("tipo_sensor.id"), nullable=True, index=True)
    bateria = Column(Float, default=100.0)  # 0-100%
    ultimo_ping = Column(DateTime, default=utc_now_naive)
    
    # Relacionamentos
    coletor = relationship("Coletor", back_populates="sensores")
    tipo_sensor = relationship("TipoSensor", back_populates="sensores")
```

**Campos:**
- `coletor_id`: Coletor à qual o sensor pertence (obrigatório)
- `tipo_sensor_id`: Tipo do sensor (opcional)
- `bateria`: Nível de bateria (0-100%)
- `ultimo_ping`: Última comunicação do sensor

#### 4.1.8 Modelo: Coleta

```python
class Coleta(Base):
    __tablename__ = "coletas"
    
    id = Column(Integer, primary_key=True)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=False, index=True)
    data_hora = Column(DateTime, default=utc_now_naive, index=True)
    volume_estimado = Column(Float)  # kg
    
    # Campos financeiros/operacionais
    tipo_operacao = Column(String(50))  # "Avulsa" ou "Campanha"
    km_percorrido = Column(Float)  # km
    preco_combustivel = Column(Float)  # R$/litro
    lucro_por_kg = Column(Float)  # R$/kg
    emissao_mtr = Column(Boolean, default=False)  # MTR emitido?
    
    # Relacionamentos
    tipo_coletor_id = Column(Integer, ForeignKey("tipo_coletor.id"), nullable=True, index=True)
    parceiro_id = Column(Integer, ForeignKey("parceiros.id"), nullable=True, index=True)
    
    # Relacionamentos ORM
    coletor = relationship("Coletor", back_populates="coletas")
    tipo_coletor = relationship("TipoColetor", back_populates="coletas")
    parceiro = relationship("Parceiro", back_populates="coletas")
```

**Campos Financeiros:**
- `volume_estimado`: Quantidade coletada em kg
- `km_percorrido`: Distância percorrida
- `preco_combustivel`: Preço do combustível no momento
- `lucro_por_kg`: Lucro por quilograma (do CSV)
- `tipo_operacao`: Tipo de operação (Avulsa/Campanha)

**Cálculos:**
- Custo de combustível: `(km_percorrido / 4) * preco_combustivel` (4 km/L padrão)
- Lucro total: `volume_estimado * lucro_por_kg`
- Lucro líquido: `lucro_total - custo_combustivel`

#### 4.1.9 Modelo: Notificacao

```python
class Notificacao(Base):
    __tablename__ = "notificacoes"
    
    id = Column(Integer, primary_key=True)
    tipo = Column(String(50), nullable=False)  # 'lixeira_cheia', 'bateria_baixa'
    titulo = Column(String(200), nullable=False)
    mensagem = Column(String(500), nullable=False)
    
    # Relacionamentos
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=True, index=True)
    sensor_id = Column(Integer, ForeignKey("sensores.id"), nullable=True, index=True)
    
    # Status
    enviada = Column(Boolean, default=False)
    enviada_em = Column(DateTime, nullable=True)
    lida = Column(Boolean, default=False)
    lida_em = Column(DateTime, nullable=True)
    criada_em = Column(DateTime, default=utc_now_naive)
    
    # Relacionamentos ORM
    coletor = relationship("Coletor", backref="notificacoes")
    sensor = relationship("Sensor", backref="notificacoes")
```

**Tipos de Notificação:**
- `lixeira_cheia`: Coletor com nível > 80%
- `bateria_baixa`: Sensor com bateria < 20%

**Status:**
- `enviada`: Se o email foi enviado
- `lida`: Se foi visualizada no frontend
- `criada_em`: Data de criação

#### 4.1.10 Modelo: MetaComercial

```python
class MetaComercial(Base):
    __tablename__ = "metas_comerciais"
    
    id = Column(Integer, primary_key=True)
    mes = Column(Integer, nullable=False)  # 1-12
    ano = Column(Integer, nullable=False)
    valor_meta = Column(Float, nullable=False)
    valor_realizado = Column(Float, default=0.0)
    percentual_atingido = Column(Float, default=0.0)
    status = Column(String(20), default='em_andamento')  # em_andamento, atingida, nao_atingida
    observacoes = Column(String(500))
    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
```

**Uso:** Metas mensais de faturamento para acompanhamento comercial.

#### 4.1.11 Modelo: Pipeline

```python
class Pipeline(Base):
    __tablename__ = "pipeline"
    
    id = Column(Integer, primary_key=True)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=True)  # Nullable para leads sem coletor
    status = Column(String(50), nullable=False, default='lead')  # lead, contato_inicial, proposta_enviada, negociacao, fechado, perdido
    valor_estimado = Column(Float, default=0.0)
    probabilidade = Column(Integer, default=10)  # 0-100%
    proxima_acao = Column(String(200))
    data_proxima_acao = Column(DateTime)
    responsavel_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    origem = Column(String(100))  # indicacao, site, rede_social, evento
    tipo_servico = Column(String(100))  # coleta, palestra, oficina, contrato
    observacoes = Column(String(1000))
    motivo_perda = Column(String(200))  # Se status='perdido'
    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
    fechado_em = Column(DateTime)
    
    # Relacionamentos
    coletor = relationship("Coletor", backref="pipeline_items")
    responsavel = relationship("Usuario", backref="pipeline_responsavel")
    interacoes = relationship("Interacao", back_populates="pipeline", cascade="all, delete-orphan", lazy="dynamic")
    tarefas = relationship("Tarefa", back_populates="pipeline", cascade="all, delete-orphan")
```

**Uso:** Pipeline de vendas/CRM para gerenciar leads e oportunidades.

#### 4.1.12 Modelo: Interacao

```python
class Interacao(Base):
    __tablename__ = "interacoes"
    
    id = Column(Integer, primary_key=True)
    pipeline_id = Column(Integer, ForeignKey("pipeline.id"), nullable=False)
    tipo = Column(String(50), nullable=False)  # ligacao, email, whatsapp, reuniao, visita, proposta, outro
    descricao = Column(String(1000), nullable=False)
    resultado = Column(String(100))  # positivo, neutro, negativo
    data = Column(DateTime, default=utc_now_naive)
    duracao_minutos = Column(Integer)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    anexos = Column(String(500))  # JSON string com lista de URLs
    criado_em = Column(DateTime, default=utc_now_naive)
    
    # Relacionamentos
    pipeline = relationship("Pipeline", back_populates="interacoes")
    usuario = relationship("Usuario", backref="interacoes")
```

**Uso:** Registro de interações com clientes no pipeline de vendas.

#### 4.1.13 Modelo: Tarefa

```python
class Tarefa(Base):
    __tablename__ = "tarefas"
    
    id = Column(Integer, primary_key=True)
    pipeline_id = Column(Integer, ForeignKey("pipeline.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    titulo = Column(String(200), nullable=False)
    descricao = Column(String(1000))
    status = Column(String(20), default='pendente')  # pendente, concluida
    prioridade = Column(String(20), default='media')  # baixa, media, alta
    data_vencimento = Column(DateTime)
    concluida_em = Column(DateTime)
    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
    
    # Relacionamentos
    pipeline = relationship("Pipeline", back_populates="tarefas")
    usuario = relationship("Usuario", backref="tarefas")
```

**Uso:** Tarefas do CRM associadas a pipelines ou independentes.

#### 4.1.14 Modelo: ContratoRecorrente

```python
class ContratoRecorrente(Base):
    __tablename__ = "contratos_recorrentes"
    
    id = Column(Integer, primary_key=True)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=False)
    parceiro_id = Column(Integer, ForeignKey("parceiros.id"), nullable=True)
    titulo = Column(String(200), nullable=False)
    descricao = Column(String(1000))
    valor_mensal = Column(Float, nullable=False)
    frequencia_coleta = Column(String(20), default='mensal')  # semanal, quinzenal, mensal, bimestral
    dia_coleta = Column(Integer)  # Dia do mês (1-31)
    data_inicio = Column(DateTime, nullable=False)
    data_vencimento = Column(DateTime)
    status = Column(String(20), default='ativo')  # ativo, pausado, cancelado, vencido
    observacoes = Column(String(1000))
    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
    
    # Relacionamentos
    coletor = relationship("Coletor", backref="contratos")
    parceiro = relationship("Parceiro", backref="contratos")
```

**Uso:** Contratos recorrentes de coleta com clientes.

#### 4.1.15 Modelo: PreferenciaLayout

```python
class PreferenciaLayout(Base):
    __tablename__ = "preferencias_layout"
    
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), unique=True, nullable=False)
    ordem_containers = Column(String(2000))  # JSON string com ordem dos containers
    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
    
    # Relacionamentos
    usuario = relationship("Usuario", backref="preferencia_layout")
```

**Uso:** Preferências de layout do dashboard comercial por usuário.

### 4.2 Relacionamentos

#### 4.2.1 Diagrama de Relacionamentos

```
Usuario (1) ────┐
                │
Parceiro (1) ───┼─── (N) Coletor (1) ──── (N) Sensor
                │                          │
                │                          │
TipoMaterial (1)┘                          │
                                           │
TipoSensor (1) ───────────────────────────┘

Coletor (1) ──── (N) Coleta (N) ──── (1) Parceiro
                │
                │
TipoColetor (1)┘

Coletor (1) ──── (N) Notificacao
Sensor (1) ──── (N) Notificacao
```

#### 4.2.2 Eager Loading

Para otimizar performance, o sistema usa **eager loading** com `joinedload()`:

```python
# Exemplo: Carregar coletor com parceiro e tipo_material
query = db.query(Coletor).options(
    joinedload(Coletor.parceiro),
    joinedload(Coletor.tipo_material)
)
```

### 4.3 Inicialização do Banco

#### 4.3.1 Criação de Tabelas

```python
# app.py
Base.metadata.create_all(engine)
```

SQLAlchemy cria automaticamente todas as tabelas que não existem.

#### 4.3.2 População de Tipos

```python
# banco_dados/seed_tipos.py
def popular_tipos(engine):
    """Popula tabelas de tipos (material, sensor, coletor)"""
    # Insere tipos padrão se não existirem
```

**Tipos padrão:**
- **Material**: Plástico, Papel, Metal, Vidro, Orgânico
- **Sensor**: Ultrassônico, Infravermelho, Peso
- **Coletor**: Caminhão, Carreta, Van

#### 4.3.3 Usuário Admin

```python
# banco_dados/inicializar.py
def criar_usuario_admin(engine):
    """Cria usuário admin a partir de variáveis de ambiente"""
    # ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD
```

### 4.4 Migrações

O sistema possui scripts de migração para adicionar colunas:

#### 4.4.1 Migração de Notificações

```python
# banco_dados/migrar_notificacoes.py
def migrar_notificacoes():
    """Adiciona colunas lida e lida_em à tabela notificacoes"""
    # ALTER TABLE notificacoes ADD COLUMN lida BOOLEAN DEFAULT 0
    # ALTER TABLE notificacoes ADD COLUMN lida_em DATETIME
```

**Uso:**
```bash
python banco_dados/migrar_notificacoes.py
```

### 4.5 Utilitários de Data/Hora

#### 4.5.1 banco_dados/utils.py

```python
def utc_now():
    """Retorna datetime UTC com timezone (Python 3.12+)"""
    return datetime.now(timezone.utc)

def utc_now_naive():
    """Retorna datetime UTC sem timezone (compatibilidade)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

**Motivo:** `datetime.utcnow()` está deprecado no Python 3.12+. O sistema usa funções compatíveis.

---

## 5. Sistema de Autenticação

### 5.1 Flask-Login

O sistema utiliza **Flask-Login** para gerenciamento de sessões.

#### 5.1.1 Configuração

```python
# app.py
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.session_protection = 'strong'  # Proteção contra session fixation

@login_manager.user_loader
def load_user(user_id):
    """Carrega usuário da sessão"""
    db = app.config.get('DATABASE_SESSION')
    session = db()
    try:
        return session.query(Usuario).get(int(user_id))
    finally:
        session.close()
```

#### 5.1.2 Decorators

**`@login_required`**: Exige autenticação
```python
@paginas_bp.route('/')
@login_required
def index():
    # ...
```

**`@admin_required`**: Exige permissões de admin
```python
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.admin:
            return jsonify({"erro": "Acesso negado"}), 403
        return f(*args, **kwargs)
    return decorated_function
```

### 5.2 Rotas de Autenticação

#### 5.2.1 Login (`/auth/login`)

**GET:** Renderiza página de login  
**POST:** Processa credenciais

**Validações:**
- Username/email não vazio
- Senha não vazia
- Usuário existe
- Senha correta
- Usuário ativo

**Fluxo:**
1. Validar credenciais
2. Atualizar `ultimo_login`
3. Criar sessão via `login_user()`
4. Redirecionar para dashboard ou `next_page`

#### 5.2.2 Logout (`/auth/logout`)

**GET/POST:** Encerra sessão

**Fluxo:**
1. `logout_user()` (Flask-Login)
2. Redirecionar para login

#### 5.2.3 Registro (`/auth/registro`)

**GET:** Renderiza página de registro  
**POST:** Cria novo usuário

**Validações:**
- Username válido (3-30 caracteres, alfanumérico)
- Email válido (regex)
- Senha forte (mínimo 8 caracteres, maiúscula, minúscula, número)
- Username/email únicos

**Segurança:**
- Senha nunca armazenada em texto plano
- Hash bcrypt com salt automático

### 5.3 Segurança de Senhas

#### 5.3.1 Hash de Senhas

```python
# banco_dados/modelos.py
from werkzeug.security import generate_password_hash, check_password_hash

def set_senha(self, senha):
    """Gera hash bcrypt da senha"""
    self.senha_hash = generate_password_hash(senha)

def verificar_senha(self, senha):
    """Verifica senha contra hash"""
    return check_password_hash(self.senha_hash, senha)
```

**Algoritmo:** bcrypt (via Werkzeug)  
**Salt:** Automático e único por senha

#### 5.3.2 Validação de Força

```python
# banco_dados/seguranca.py
def validar_senha(senha: str) -> Tuple[bool, Optional[str]]:
    """
    Requisitos:
    - Mínimo 8 caracteres
    - Pelo menos uma letra maiúscula
    - Pelo menos uma letra minúscula
    - Pelo menos um número
    """
```

### 5.4 Sessões

#### 5.4.1 Configuração de Cookies

```python
# app.py
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Previne XSS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Previne CSRF
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hora

if FLASK_ENV == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True  # Apenas HTTPS
```

#### 5.4.2 Proteção contra Session Fixation

```python
login_manager.session_protection = 'strong'
```

Flask-Login regenera o ID da sessão após login para prevenir session fixation attacks.

---

## 6. API REST

### 6.1 Estrutura da API

A API REST está organizada em `rotas/api.py` usando o blueprint `api_bp` com prefixo `/api`.

#### 6.1.1 Convenções

- **Métodos HTTP:**
  - `GET`: Leitura
  - `POST`: Criação
  - `PUT`: Atualização completa
  - `DELETE`: Exclusão

- **Respostas:**
  - `200 OK`: Sucesso
  - `201 Created`: Recurso criado
  - `400 Bad Request`: Dados inválidos
  - `401 Unauthorized`: Não autenticado
  - `403 Forbidden`: Sem permissão
  - `404 Not Found`: Recurso não encontrado
  - `429 Too Many Requests`: Rate limit excedido
  - `500 Internal Server Error`: Erro do servidor

- **Formato JSON:**
```json
{
  "id": 1,
  "localizacao": "Asa Norte - Bloco A",
  "nivel_preenchimento": 75.5,
  "status": "OK",
  "parceiro": {
    "id": 1,
    "nome": "Parceiro Exemplo"
  }
}
```

### 6.2 Endpoints de Lixeiras

#### 6.2.1 GET /api/coletores

**Descrição:** Lista todas as coletores

**Autenticação:** Não requerida

**Query Parameters:**
- `status` (opcional): Filtrar por status
- `parceiro_id` (opcional): Filtrar por parceiro

**Resposta:**
```json
[
  {
    "id": 1,
    "localizacao": "Asa Norte - Bloco A",
    "nivel_preenchimento": 75.5,
    "status": "OK",
    "latitude": -15.7942,
    "longitude": -47.8822,
    "parceiro": {...},
    "tipo_material": {...}
  }
]
```

**Características:**
- Eager loading de `parceiro` e `tipo_material`
- Ordenação por `id` (padrão)

#### 6.2.2 GET /api/coletor/<id>

**Descrição:** Detalhes de uma coletor específica

**Autenticação:** Não requerida

**Resposta:**
```json
{
  "id": 1,
  "localizacao": "Asa Norte - Bloco A",
  "nivel_preenchimento": 75.5,
  "status": "OK",
  "ultima_coleta": "2025-11-20T10:30:00",
  "latitude": -15.7942,
  "longitude": -47.8822,
  "parceiro": {...},
  "tipo_material": {...}
}
```

**Erros:**
- `404`: Coletor não encontrada

#### 6.2.3 POST /api/coletor

**Descrição:** Cria nova coletor

**Autenticação:** `@login_required`

**Body:**
```json
{
  "localizacao": "Nova Localização",
  "nivel_preenchimento": 0.0,
  "status": "OK",
  "latitude": -15.7942,
  "longitude": -47.8822,
  "parceiro_id": 1,
  "tipo_material_id": 1
}
```

**Validações:**
- `localizacao`: Não vazio
- `nivel_preenchimento`: 0-100
- `latitude`: -90 a 90
- `longitude`: -180 a 180
- `parceiro_id`: Deve existir (se fornecido)
- `tipo_material_id`: Deve existir (se fornecido)

**Resposta:**
```json
{
  "id": 1,
  "localizacao": "Nova Localização",
  ...
}
```

**Erros:**
- `400`: Dados inválidos
- `401`: Não autenticado

#### 6.2.4 PUT /api/coletor/<id>

**Descrição:** Atualiza coletor existente

**Autenticação:** `@login_required`

**Body:** Mesmo formato do POST (campos opcionais)

**Validações:** Mesmas do POST

**Erros:**
- `400`: Dados inválidos
- `401`: Não autenticado
- `404`: Coletor não encontrada

#### 6.2.5 DELETE /api/coletor/<id>

**Descrição:** Deleta coletor

**Autenticação:** `@admin_required`

**Cascata:**
- Sensores associados são deletados
- Coletas associadas são deletadas

**Resposta:**
```json
{
  "mensagem": "Coletor deletada com sucesso"
}
```

**Erros:**
- `403`: Apenas admins
- `404`: Coletor não encontrada

#### 6.2.6 POST /api/coletor/<id>/geocodificar

**Descrição:** Geocodifica coletor manualmente

**Autenticação:** `@login_required`

**Resposta:**
```json
{
  "mensagem": "Coordenadas atualizadas: (-15.7942, -47.8822)"
}
```

### 6.3 Endpoints de Coletas

#### 6.3.1 GET /api/coletas

**Descrição:** Lista coletas com filtros

**Autenticação:** Não requerida

**Query Parameters:**
- `coletor_id` (opcional)
- `parceiro_id` (opcional)
- `tipo_operacao` (opcional): "Avulsa" ou "Campanha"
- `data_inicio` (opcional): YYYY-MM-DD
- `data_fim` (opcional): YYYY-MM-DD

**Resposta:**
```json
[
  {
    "id": 1,
    "coletor_id": 1,
    "data_hora": "2025-11-20T10:30:00",
    "volume_estimado": 50.5,
    "tipo_operacao": "Avulsa",
    "km_percorrido": 15.2,
    "preco_combustivel": 5.50,
    "lucro_por_kg": 2.00,
    "coletor": {...},
    "parceiro": {...},
    "tipo_coletor": {...}
  }
]
```

#### 6.3.2 GET /api/historico

**Descrição:** Histórico de coletas com filtro de data

**Autenticação:** Não requerida

**Query Parameters:**
- `data` (opcional): YYYY-MM-DD

**Resposta:** Mesmo formato de `/api/coletas`

#### 6.3.3 POST /api/coleta

**Descrição:** Cria nova coleta

**Autenticação:** `@login_required`

**Body:**
```json
{
  "coletor_id": 1,
  "data_hora": "2025-11-20T10:30:00",
  "volume_estimado": 50.5,
  "tipo_operacao": "Avulsa",
  "km_percorrido": 15.2,
  "preco_combustivel": 5.50,
  "lucro_por_kg": 2.00,
  "tipo_coletor_id": 1,
  "parceiro_id": 1
}
```

**Validações:**
- `coletor_id`: Deve existir
- `data_hora`: Formato ISO válido
- `volume_estimado`: > 0
- `km_percorrido`: >= 0
- `preco_combustivel`: >= 0
- `tipo_operacao`: "Avulsa" ou "Campanha" (opcional)

### 6.4 Endpoints de Sensores

#### 6.4.1 GET /api/sensores

**Descrição:** Lista sensores com filtros

**Autenticação:** Não requerida

**Query Parameters:**
- `coletor_id` (opcional)
- `tipo_sensor_id` (opcional)
- `bateria_min` (opcional): Bateria mínima
- `bateria_max` (opcional): Bateria máxima

**Resposta:**
```json
[
  {
    "id": 1,
    "coletor_id": 1,
    "tipo_sensor_id": 1,
    "bateria": 85.5,
    "ultimo_ping": "2025-11-20T10:30:00",
    "coletor": {...},
    "tipo_sensor": {...}
  }
]
```

#### 6.4.2 GET /api/sensor/<id>

**Descrição:** Detalhes de um sensor

**Autenticação:** Não requerida

#### 6.4.3 POST /api/sensor

**Descrição:** Cria novo sensor

**Autenticação:** `@login_required`

**Body:**
```json
{
  "coletor_id": 1,
  "tipo_sensor_id": 1,
  "bateria": 100.0
}
```

**Validações:**
- `coletor_id`: Deve existir
- `tipo_sensor_id`: Deve existir (se fornecido)
- `bateria`: 0-100

#### 6.4.4 PUT /api/sensor/<id>

**Descrição:** Atualiza sensor

**Autenticação:** `@login_required`

#### 6.4.5 DELETE /api/sensor/<id>

**Descrição:** Deleta sensor

**Autenticação:** `@admin_required`

### 6.5 Endpoints de Notificações

#### 6.5.1 GET /api/notificacoes

**Descrição:** Lista notificações com filtros

**Autenticação:** `@login_required`

**Query Parameters:**
- `tipo` (opcional): "lixeira_cheia" ou "bateria_baixa"
- `enviada` (opcional): true/false
- `lida` (opcional): true/false
- `coletor_id` (opcional)
- `limite` (opcional): Número máximo (padrão: 50)

**Resposta:**
```json
[
  {
    "id": 1,
    "tipo": "lixeira_cheia",
    "titulo": "Coletor #1 - Nível Alto",
    "mensagem": "A coletor em Asa Norte está com 85% de preenchimento.",
    "enviada": true,
    "enviada_em": "2025-11-20T10:30:00",
    "lida": false,
    "lida_em": null,
    "criada_em": "2025-11-20T10:25:00",
    "coletor": {...},
    "sensor": null
  }
]
```

#### 6.5.2 POST /api/notificacoes/processar-alertas

**Descrição:** Processa alertas e envia notificações

**Autenticação:** `@admin_required`

**Rate Limit:** 5 por minuto

**Resposta:**
```json
{
  "mensagem": "Alertas processados com sucesso",
  "estatisticas": {
    "lixeiras_alertadas": 5,
    "sensores_alertados": 2,
    "emails_enviados": 7,
    "erros": 0
  }
}
```

#### 6.5.3 PUT /api/notificacoes/<id>/marcar-lida

**Descrição:** Marca notificação como lida

**Autenticação:** `@login_required`

**Resposta:**
```json
{
  "mensagem": "Notificação marcada como lida",
  "notificacao": {
    "id": 1,
    "lida": true,
    "lida_em": "2025-11-20T10:35:00"
  }
}
```

#### 6.5.4 GET /api/notificacoes/pendentes-count

**Descrição:** Contagem de notificações não lidas

**Autenticação:** `@login_required`

**Resposta:**
```json
{
  "count": 5
}
```

#### 6.5.5 GET /api/notificacoes/status-agendamento

**Descrição:** Status do agendamento automático

**Autenticação:** `@login_required`

**Resposta:**
```json
{
  "ativo": true,
  "proxima_execucao": "2025-11-20T11:00:00",
  "intervalo_minutos": 60
}
```

### 6.6 Endpoints de Relatórios

#### 6.6.1 GET /api/relatorios

**Descrição:** Dados para relatórios financeiros e operacionais

**Autenticação:** Não requerida

**Query Parameters:**
- `data_inicio` (opcional): YYYY-MM-DD
- `data_fim` (opcional): YYYY-MM-DD
- `parceiro_id` (opcional)
- `tipo_operacao` (opcional)

**Resposta:**
```json
{
  "periodo": {
    "data_inicio": "2025-11-01",
    "data_fim": "2025-11-20"
  },
  "resumo": {
    "total_coletas": 64,
    "volume_total": 3200.5,
    "km_total": 450.2,
    "custo_combustivel_total": 618.78,
    "lucro_total": 6401.0,
    "lucro_medio_por_coleta": 100.02,
    "coletas_por_lixeira": [...],
    "coletas_por_parceiro": [...]
  },
  "detalhes": [...]
}
```

**Cálculos:**
- Custo combustível: `(km_percorrido / 4) * preco_combustivel` (4 km/L padrão)
- Lucro total: `sum(volume_estimado * lucro_por_kg)`
- Lucro médio: `lucro_total / total_coletas`

#### 6.6.2 GET /api/relatorios/exportar-pdf

**Descrição:** Exporta relatório em PDF

**Autenticação:** `@login_required`

**Query Parameters:** Mesmos de `/api/relatorios`

**Resposta:** Arquivo PDF (Content-Type: application/pdf)

**Características:**
- Geração via ReportLab
- Inclui resumo e detalhamento (até 50 coletas)
- Filtros aplicados
- Nome do arquivo: `relatorio_tronik_YYYYMMDD_HHMMSS.pdf`

### 6.7 Endpoints Auxiliares

#### 6.7.1 GET /api/estatisticas

**Descrição:** Estatísticas gerais do sistema

**Autenticação:** Não requerida

**Resposta:**
```json
{
  "total_lixeiras": 40,
  "lixeiras_alerta": 5,
  "nivel_medio": 45.2,
  "coletas_hoje": 3,
  "sensores_ativos": 35,
  "sensores_bateria_baixa": 2
}
```

#### 6.7.2 GET /api/configuracoes

**Descrição:** Configurações do sistema

**Autenticação:** Não requerida

**Resposta:**
```json
{
  "niveis_alerta": {
    "lixeira_cheia": 80.0,
    "bateria_baixa": 20.0
  },
  "consumo_km_por_litro": 4.0
}
```

#### 6.7.3 GET /api/parceiros

**Descrição:** Lista todos os parceiros

**Autenticação:** Não requerida

#### 6.7.4 GET /api/tipos/material

**Descrição:** Lista tipos de material

**Autenticação:** Não requerida

#### 6.7.5 GET /api/tipos/sensor

**Descrição:** Lista tipos de sensor

**Autenticação:** Não requerida

#### 6.7.6 GET /api/tipos/coletor

**Descrição:** Lista tipos de coletor

**Autenticação:** Não requerida

#### 6.7.7 POST /api/coletores/simular-niveis

**Descrição:** Simula mudança de níveis de coletores

**Autenticação:** `@login_required`

**Rate Limit:** 10 por minuto

**Body:**
```json
{
  "coletores": [
    {"id": 1, "nivel": 75.5},
    {"id": 2, "nivel": 90.0}
  ]
}
```

**Uso:** Para testes e demonstrações

### 6.8 Rate Limiting

A API utiliza **Flask-Limiter** para proteger contra abuso:

```python
# Limites globais
limiter = Limiter(
    default_limits=["200 per day", "50 per hour"]
)

# Limites por endpoint
@api_bp.route('/notificacoes/processar-alertas', methods=['POST'])
@limiter.limit("5 per minute")
def processar_alertas_endpoint():
    # ...
```

**Limites:**
- Global: 200 requisições/dia, 50/hora
- Processar alertas: 5/minuto
- Simular níveis: 10/minuto

---

## 7. Frontend

### 7.1 Estrutura de Templates

O sistema utiliza **Jinja2** como engine de templates. Todos os templates herdam de `base.html`.

#### 7.1.1 Template Base (`templates/base.html`)

**Características:**
- Estrutura HTML5 semântica
- Meta tags para responsividade
- CDNs para bibliotecas externas (Leaflet, Chart.js)
- Header com menu principal e hambúrguer
- Footer (se necessário)
- Blocos para conteúdo específico: `{% block content %}`, `{% block extra_css %}`, `{% block extra_js %}`

**CDNs Carregados:**
- Leaflet.js 1.9.4 (mapas)
- Leaflet.markercluster 1.5.3 (clusters)
- Leaflet Routing Machine 3.2.12 (rotas)
- Chart.js (gráficos, via CDN em páginas específicas)

**Scripts Locais:**
- `js/api.js` - Cliente API
- `js/menu.js` - Menu hambúrguer
- `js/dashboard.js` - Lógica do dashboard
- `js/routing/*.js` - Sistema de roteamento

#### 7.1.2 Páginas

**Dashboard (`index.html`):**
- Grid de cards de coletores
- Filtros por status e parceiro
- Tabela de histórico de coletas
- Estatísticas gerais
- Botões de ação (atualizar, simular, exportar)

**Mapa (`mapa.html`):**
- Mapa Leaflet interativo
- Marcadores de coletores
- Marcador da sede Tronik
- Filtros (status, parceiro, distância, busca)
- Legenda interativa
- Controles de zoom

**Dashboard Comercial (`comercial.html`):**
- KPIs financeiros (faturamento, meta, percentual)
- Resumo financeiro detalhado
- Comparação com mês anterior
- Análise por parceiro (gráficos Chart.js)
- Próximas coletas agendadas
- Clientes inativos
- Sugestões de ações
- Layout personalizável (drag-and-drop)
- Filtro de período (mês, trimestre, semestre, ano, todos)

**CRM (`crm.html`):**
- Funil de vendas (Kanban board)
- Estatísticas do CRM
- Lista de pipelines
- Tarefas pendentes
- Modal de detalhes do pipeline
- Criação de novos leads
- Registro de interações
- Gestão de tarefas

**Contratos (`contratos.html`):**
- Lista de contratos recorrentes
- Criação de novos contratos
- Visualização de receita mensal
- Contratos vencendo
- Status de contratos

**Relatórios (`relatorios.html`):**
- Filtros de período e parceiro
- KPIs financeiros
- Gráficos (Chart.js)
- Tabela de detalhamento
- Botões de exportação (CSV, PDF)

**Configurações (`configuracoes.html`):**
- Formulário de criação de coletores
- Formulário de criação de coletas
- Lista de coletores cadastradas (com distância da sede)
- Gerenciamento de sensores (CRUD completo)
- Visualização de bateria de sensores

**Notificações (`notificacoes.html`):**
- Lista de notificações com filtros
- Estatísticas (total, enviadas, pendentes, hoje)
- Marcação de notificações como lidas
- Botão para processar alertas manualmente

**Sobre (`sobre.html`):**
- Informações sobre o projeto
- Página pública (não requer login)

**Login/Registro (`login.html`, `registro.html`):**
- Formulários de autenticação
- Validação client-side
- Mensagens de erro/sucesso

### 7.2 JavaScript - Módulos Frontend

#### 7.2.1 Cliente API (`estatico/js/api.js`)

**Funções Principais:**

```javascript
// Lixeiras
obterTodasLixeiras()
obterLixeira(id)
criarLixeira(dados)
atualizarLixeira(id, dados)
deletarLixeira(id)

// Coletas
obterColetas(filtros)
obterHistorico(dataFiltro)
criarColeta(dados)

// Sensores
obterTodosSensores(filtros)
obterSensor(id)
criarSensor(dados)
atualizarSensor(id, dados)
deletarSensor(id)

// Notificações
obterNotificacoes(filtros)
processarAlertas()
marcarNotificacaoLida(id)
obterNotificacoesPendentesCount()
obterStatusAgendamento()

// Relatórios
obterRelatorios(filtros)

// Estatísticas
obterEstatisticas()
```

**Características:**
- Função auxiliar `fazerRequisicao()` para todas as requisições
- Tratamento de erros centralizado
- Suporte a filtros via query parameters
- Headers JSON automáticos

#### 7.2.2 Dashboard (`estatico/js/dashboard.js`)

**Funcionalidades:**
- Carregamento de coletores e exibição em cards
- Filtros por status e parceiro
- Ordenação de tabela de histórico
- Atualização automática periódica
- Simulação de níveis
- Exportação CSV
- Cálculo e exibição de distância da sede

**Funções Principais:**
```javascript
carregarLixeiras()
criarCardLixeira(coletor)
aplicarFiltros()
ordenarTabela(coluna)
atualizarHistorico()
simularNiveis()
exportarCSV()
```

#### 7.2.3 Mapa (`estatico/js/mapa.js`)

**Módulo Principal de Mapas:**

```javascript
const MapaTronik = (function() {
    // Variáveis privadas
    let mapa = null;
    let marcadores = {};
    let markerClusterGroup = null;
    let routingControl = null;
    
    // API pública
    return {
        inicializar: function(containerId, coordenadas),
        adicionarMarcador: function(coletor),
        adicionarMarcadorSede: function(),
        limparMarcadores: function(),
        criarPopupLixeira: function(coletor),
        calcularRotaSede: function(lixeiraId),
        calcularDistanciaSede: function(coletor),
        formatarDistancia: function(distanciaKm),
        filtrarPorDistancia: function(coletores, filtro),
        ordenarLixeirasPorDistancia: function(coletores, ordem),
        ajustarZoomMarcadores: function(),
        getMapa: function()
    };
})();
```

**Funcionalidades:**
- Inicialização de mapa Leaflet
- Marcadores coloridos por status (verde=OK, amarelo=ALERTA, vermelho=CHEIA)
- Clusters de marcadores (Leaflet.markercluster)
- Popup informativo em cada coletor
- Marcador especial da sede Tronik (não agrupa)
- Cálculo de rotas (OSRM + sistema robusto)
- Cálculo de distância da sede (Haversine)
- Filtros e ordenação

**Integração com Sistema de Roteamento:**
- Usa `calcularRotaRobusta()` quando OSRM falha
- Fallback inteligente para evitar linhas retas
- Suporte a múltiplos pontos intermediários

#### 7.2.4 Mapa Page (`estatico/js/mapa-page.js`)

**Lógica Específica da Página de Mapa:**

- Carregamento de coletores
- Aplicação de filtros (status, parceiro, distância, busca)
- Ordenação por distância
- Event listeners para controles do mapa
- Sincronização com `MapaTronik`

#### 7.2.5 Relatórios (`estatico/js/relatorios.js`)

**Funcionalidades:**
- Carregamento de dados de relatórios
- Filtros por período, parceiro, tipo de operação
- Gráficos Chart.js:
  - Evolução de coletas
  - Distribuição por coletor
  - Distribuição por horário
  - Análise financeira
- Exportação CSV
- Exportação PDF
- KPIs financeiros

**Gráficos:**
- **Evolução**: Linha temporal de coletas
- **Distribuição por Coletor**: Barras horizontais/verticais
- **Distribuição por Horário**: Barras de horários
- **Financeiro**: Pizza de custos vs lucros

#### 7.2.6 Configurações (`estatico/js/configuracoes.js`)

**Funcionalidades:**
- Formulário de criação de coletores
- Formulário de criação de coletas
- Lista de coletores com ações (editar, deletar)
- Gerenciamento de sensores (CRUD)
- Carregamento de dropdowns (parceiros, tipos)
- Validação client-side
- Confirmações antes de deletar
- Loading states
- Cálculo de distância da sede

#### 7.2.7 Notificações (`estatico/js/notificacoes.js`)

**Funcionalidades:**
- Carregamento de notificações
- Filtros (tipo, status envio, status leitura, coletor)
- Estatísticas (total, enviadas, pendentes, hoje)
- Marcação como lida
- Atualização de badge no header
- Processamento manual de alertas

**Funções:**
```javascript
carregarNotificacoes()
exibirNotificacoes(notifs)
aplicarFiltros()
marcarComoLida(id)
atualizarBadgeNotificacoes()
atualizarEstatisticas(notifs)
```

#### 7.2.8 Menu (`estatico/js/menu.js`)

**Menu Hambúrguer Mobile:**

- Abertura/fechamento do menu
- Overlay para fechar ao clicar fora
- Sincronização de badge de notificações
- Responsividade

### 7.3 CSS - Estilização

#### 7.3.1 Esquema de Cores (Tronik Verde)

**Cores Principais:**
- **Verde Primário**: `#27ae60`
- **Verde Escuro**: `#229954`
- **Verde Claro**: `#2ecc71`
- **Texto**: `#1a1a1a` (preto para contraste)
- **Fundo**: `#f8f9fa` (cinza claro)
- **Bordas**: `#e0e0e0`

**Aplicação:**
- Botões primários: verde
- Links ativos: verde
- Bordas de cards: verde
- Gradientes: verde
- Badges: verde

#### 7.3.2 Arquivos CSS

**`estilo.css`**: Estilos principais
- Layout geral
- Header e navegação
- Cards e grid
- Botões e formulários
- Responsividade

**`auth.css`**: Páginas de autenticação
- Formulários de login/registro
- Gradientes verdes
- Animações

**`mapa.css`**: Página de mapa
- Container do mapa
- Controles Leaflet
- Popups customizados
- Legenda
- Filtros

**`relatorios.css`**: Página de relatórios
- Layout 3 colunas
- KPIs financeiros
- Gráficos
- Tabelas

**`configuracoes.css`**: Página de configurações
- Formulários
- Listas de coletores/sensores
- Indicadores de bateria
- Ações

**`notificacoes.css`**: Página de notificações
- Lista de notificações
- Badges de status
- Filtros
- Estatísticas

**`menu-mobile.css`**: Menu hambúrguer
- Menu lateral
- Overlay
- Animações
- Z-index e pointer-events

**`sobre.css`**: Página sobre
- Layout informativo
- Seções
- Feature list

#### 7.3.3 Responsividade

**Breakpoints:**
- Mobile: `< 768px`
- Tablet: `768px - 1024px`
- Desktop: `> 1024px`

**Adaptações:**
- Menu hambúrguer em mobile
- Grid responsivo (1-2-3 colunas)
- Tabelas com scroll horizontal
- Formulários empilhados
- Botões compactos

#### 7.3.4 Acessibilidade (ARIA)

**Atributos ARIA Implementados:**
- `aria-label`: Descrições de elementos
- `aria-label` em botões e links
- `role`: Navigation, menu, article
- `aria-label` em estatísticas
- Labels associados a inputs

**Exemplos:**
```html
<button aria-label="Marcar notificação como lida">✓ Marcar como lida</button>
<nav role="navigation" aria-label="Menu principal">
<div role="article" aria-label="Notificação não lida: ...">
```

---

## 8. Sistema de Roteamento

### 8.1 Visão Geral

O sistema de roteamento é um módulo JavaScript modular e robusto que calcula rotas otimizadas entre pontos geográficos. Utiliza múltiplas estratégias em cascata para garantir que sempre retorne uma rota válida.

### 8.2 Arquitetura Modular

O sistema é composto por **8 módulos especializados**:

```
routing/
├── router.js          # Orquestrador principal
├── algoritmos.js      # A*, Dijkstra, Bidirectional
├── heuristicas.js     # Heurísticas geográficas
├── cache.js           # Cache IndexedDB
├── osm.js             # Integração OpenStreetMap
├── suavizacao.js      # Suavização de rotas
├── aprendizado.js     # Aprendizado adaptativo
└── otimizacao.js      # Otimizações de performance
```

### 8.3 Estratégia Híbrida

O sistema utiliza uma **estratégia em cascata**:

```
1. Cache (IndexedDB)
   ↓ (não encontrado)
2. OSRM (servidor demo)
   ↓ (falha)
3. OpenStreetMap (Overpass API)
   ↓ (falha ou timeout)
4. Heurísticas Geográficas + A*
   ↓ (sempre disponível)
5. Rota Intermediária (múltiplos pontos)
```

### 8.4 Módulos Detalhados

#### 8.4.1 Router Principal (`router.js`)

**Função Principal:**
```javascript
async function calcularRotaRobusta(ponto1, ponto2, opcoes = {})
```

**Parâmetros:**
- `ponto1`: `[lat, lon]` - Ponto inicial
- `ponto2`: `[lat, lon]` - Ponto final
- `opcoes`:
  - `usarOSM`: boolean (padrão: true)
  - `usarCache`: boolean (padrão: true)
  - `algoritmo`: 'aStar' | 'dijkstra' | 'bidirectional' | null (auto)
  - `suavizar`: boolean (padrão: true)

**Fluxo:**
1. Verifica cache IndexedDB
2. Tenta OSRM (se disponível)
3. Tenta OSM com Overpass API
4. Usa heurísticas geográficas + A*
5. Suaviza rota (Catmull-Rom Spline)
6. Salva no cache
7. Retorna rota com múltiplos pontos (mínimo 3)

**Garantias:**
- Sempre retorna rota com pelo menos 3 pontos
- Nunca retorna linha reta (2 pontos)
- Fallback para rota intermediária se necessário

#### 8.4.2 Algoritmos (`algoritmos.js`)

**A* (A-estrela):**
```javascript
function aStar(grafo, inicio, fim, pontos, heuristica)
```

**Características:**
- Heurística customizável (padrão: Haversine)
- Mais eficiente que Dijkstra para rotas longas
- Explora menos nós que Dijkstra puro

**Dijkstra:**
```javascript
function dijkstra(grafo, inicio, fim)
```

**Características:**
- Algoritmo clássico de menor caminho
- Garante solução ótima
- Mais lento que A* para rotas longas

**Bidirectional Dijkstra:**
```javascript
function bidirectionalDijkstra(grafo, inicio, fim)
```

**Características:**
- Busca dos dois lados simultaneamente
- Mais rápido que Dijkstra unidirecional
- Útil para rotas muito longas

#### 8.4.3 Heurísticas (`heuristicas.js`)

**Áreas a Evitar:**

O sistema mapeia **13 áreas** em Brasília/DF que devem ser evitadas:

```javascript
const AREAS_EVITAR = [
    // Parques (6)
    {lat: -15.8, lon: -47.9, raio: 0.015, tipo: 'parque', nome: 'Parque da Cidade', penalidade: 10},
    // ... mais 5 parques
    
    // Lago Paranoá (3)
    {lat: -15.85, lon: -47.95, raio: 0.020, tipo: 'lago', nome: 'Lago Paranoá (Norte)', penalidade: 15},
    // ... mais 2 áreas do lago
    
    // Reservas e áreas rurais (4)
    // ...
];
```

**Funções de Heurística:**

```javascript
// Penalidade por área sem estradas
calcularPenalidadeArea(lat, lon)

// Peso baseado em densidade urbana
calcularPesoDensidade(lat, lon)
// - Dentro de 10km do centro: 0.8 (mais fácil)
// - 10-20km: 1.0 (normal)
// - Mais de 20km: 1.3 (mais difícil)

// Peso por direção (preferência cardinais)
calcularPesoDirecao(ponto1, ponto2, ponto3)
// - Prefere N/S/E/O
// - Penaliza mudanças bruscas de direção

// Cria heurística completa
criarHeuristicaCompleta(pontos)
```

**Integração com Aprendizado:**
- Pesos ajustáveis via `obterAjustes()`
- Multiplicadores de aprendizado aplicados

#### 8.4.4 Cache (`cache.js`)

**IndexedDB para Cache Local:**

```javascript
// Inicializar banco
async function initDB()

// Obter rota do cache
async function obterRotaCache(ponto1, ponto2)
// TTL: 1 hora

// Salvar rota no cache
async function salvarRotaCache(rota, ponto1, ponto2)

// Obter dados OSM do cache
async function obterOSMCache(bounds)
// TTL: 24 horas

// Salvar dados OSM no cache
async function salvarOSMCache(bounds, dados)

// Limpar cache expirado
async function limparCacheExpirado()
```

**Estrutura do Cache:**
- **Rota**: `{ponto1, ponto2, rota, timestamp}`
- **OSM**: `{bounds, dados, timestamp}`
- Limpeza automática de itens expirados

#### 8.4.5 OpenStreetMap (`osm.js`)

**Integração com Overpass API:**

```javascript
// Buscar estradas OSM
async function buscarEstradasOSM(ponto1, ponto2)

// Construir grafo a partir de estradas OSM
function construirGrafoOSM(estradas)
// - Pesos baseados em tipo de via
// - Rodovia < Avenida < Rua

// Encontrar nós próximos
function encontrarNosProximos(ponto, nodeMap, raio)
```

**Tipos de Via (pesos):**
- `highway=motorway`: peso 1.0 (mais rápido)
- `highway=primary`: peso 1.2
- `highway=secondary`: peso 1.5
- `highway=tertiary`: peso 2.0
- `highway=residential`: peso 3.0 (mais lento)

#### 8.4.6 Suavização (`suavizacao.js`)

**Catmull-Rom Spline:**

```javascript
// Suavizar rota completa
function suavizarRotaCompleta(rota, opcoes)

// Aplicar Catmull-Rom Spline
function aplicarCatmullRom(pontos, tensao)

// Simplificar rota (remover pontos muito próximos)
function simplificarRota(rota, tolerancia)

// Suavizar curvas (remover ângulos agudos)
function suavizarCurvas(rota, anguloMinimo)
```

**Resultado:** Rotas mais naturais e suaves visualmente.

#### 8.4.7 Aprendizado Adaptativo (`aprendizado.js`)

**Sistema de Aprendizado:**

```javascript
// Salvar rota real (do OSRM)
salvarRotaReal(rota, ponto1, ponto2)

// Salvar rota prevista (do nosso algoritmo)
salvarRotaPrevista(rota, ponto1, ponto2)

// Processar aprendizado (comparar rotas)
processarAprendizado()
// - Compara rotas previstas com reais
// - Ajusta pesos de heurísticas
// - Persiste no localStorage

// Obter ajustes de pesos
obterAjustes()
// Retorna: {penalidadeArea, pesoDensidade, pesoDirecao}
```

**Métricas de Similaridade:**
- Distância total
- Trajetória (pontos em comum)
- Desvio médio

**Persistência:**
- LocalStorage (pesos ajustados)
- Processamento em lote (a cada 5 minutos)

#### 8.4.8 Otimização (`otimizacao.js`)

**Otimizações para Rotas Longas:**

```javascript
// Dividir rota longa em segmentos
function calcularRotaLonga(ponto1, ponto2, calcularSegmento)
// - Rotas > 30km são divididas
// - Processamento paralelo de segmentos
// - Junção de segmentos

// Selecionar algoritmo otimizado
function escolherAlgoritmoOtimizado(distancia)
// - < 5km: A*
// - 5-15km: Bidirectional Dijkstra
// - > 15km: A* com menos pontos

// Calcular número ótimo de pontos
function calcularNumPontosOtimizado(distancia)
// - Baseado na distância
// - Balanceia precisão vs performance
```

**Estratégias:**
- Segmentação para rotas > 30km
- Seleção automática de algoritmo
- Número otimizado de pontos intermediários
- Simplificação de rotas muito longas

### 8.5 Localização Português (`routing-pt.js`)

**Tradução de Instruções:**

```javascript
// Traduz instruções do OSRM
function traduzirInstrucao(instrucao)

// Configurar formatter padrão
L.Routing.Formatter.prototype.formatDistance = function(distance) {
    // Formatação em português (km, m)
}

// Instruções traduzidas
instructions.pt = {
    'Head': 'Siga',
    'Turn left': 'Vire à esquerda',
    'Turn right': 'Vire à direita',
    // ... mais traduções
}
```

**Configuração Automática:**
- `language: 'pt'` (quando suportado)
- `units: 'metric'` (km, m)
- Formatação de distâncias em português

### 8.6 Uso no Mapa

**Integração com Leaflet:**

```javascript
// Calcular rota da sede até coletor
calcularRotaSede(lixeiraId)
// 1. Tenta OSRM (Leaflet Routing Machine)
// 2. Se falhar, usa calcularRotaRobusta()
// 3. Desenha rota no mapa
```

**Fallback Automático:**
- OSRM falha → Sistema robusto
- Sistema robusto sempre retorna rota válida
- Nunca mostra linha reta

---

## 9. Sistema de Notificações

### 9.1 Arquitetura

O sistema de notificações é composto por:

1. **Modelo de Dados** (`Notificacao` em `modelos.py`)
2. **Lógica de Negócio** (`banco_dados/notificacoes.py`)
3. **Agendamento** (`banco_dados/agendamento.py`)
4. **Frontend** (`templates/notificacoes.html`, `estatico/js/notificacoes.js`)

### 9.2 Tipos de Notificações

#### 9.2.1 Coletor Cheia

**Trigger:** `nivel_preenchimento > 80%`

**Processo:**
1. `verificar_alertas_lixeiras()` busca coletores com nível > 80%
2. Verifica se já existe notificação recente (últimas 24h)
3. Cria notificação no banco
4. Envia email para administradores
5. Marca como enviada

**Email:**
- Assunto: "Coletor #X - Nível Alto"
- Conteúdo: Localização, nível, status
- Destinatários: Todos os admins ativos

#### 9.2.2 Bateria Baixa

**Trigger:** `bateria < 20%`

**Processo:**
1. `verificar_alertas_sensores()` busca sensores com bateria < 20%
2. Verifica se já existe notificação recente (últimas 24h)
3. Cria notificação no banco
4. Envia email para administradores
5. Marca como enviada

**Email:**
- Assunto: "Sensor #X - Bateria Baixa"
- Conteúdo: Sensor ID, coletor, nível de bateria
- Destinatários: Todos os admins ativos

### 9.3 Processamento de Alertas

#### 9.3.1 Função Principal

```python
# banco_dados/notificacoes.py
def processar_alertas(db: Session) -> Dict[str, int]:
    """
    Processa todos os alertas e envia notificações.
    
    Returns:
        {
            'lixeiras_alertadas': int,
            'sensores_alertados': int,
            'emails_enviados': int,
            'erros': int
        }
    """
```

**Fluxo:**
1. Verifica alertas de coletores
2. Verifica alertas de sensores
3. Cria notificações
4. Envia emails
5. Retorna estatísticas

#### 9.3.2 Prevenção de Duplicatas

**Verificação de Notificações Recentes:**
```python
limite_tempo = utc_now_naive() - timedelta(hours=24)
notificacao_recente = db.query(Notificacao).filter(
    Notificacao.coletor_id == coletor.id,
    Notificacao.tipo == 'lixeira_cheia',
    Notificacao.criada_em >= limite_tempo
).first()
```

**Resultado:** Evita spam de emails (máximo 1 por 24h por coletor/sensor).

### 9.4 Agendamento Automático

#### 9.4.1 APScheduler

```python
# banco_dados/agendamento.py
def inicializar_agendamento(app):
    """
    Inicializa APScheduler para processar alertas automaticamente.
    """
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=processar_alertas_job,
        trigger=IntervalTrigger(minutes=intervalo_minutos),
        id='processar_alertas',
        replace_existing=True,
        max_instances=1  # Evita execuções simultâneas
    )
    scheduler.start()
```

**Configuração via `.env`:**
```env
AGENDAMENTO_ENABLED=true
AGENDAMENTO_INTERVALO_MINUTOS=60
```

**Características:**
- Processamento em background
- Não bloqueia aplicação principal
- Logs detalhados
- Tratamento de erros

#### 9.4.2 Job Agendado

```python
def processar_alertas_job():
    """
    Executado automaticamente pelo scheduler.
    """
    # Conecta ao banco
    # Processa alertas
    # Loga resultados
```

**Logs:**
```
🔄 Iniciando processamento automático de alertas...
============================================================
RESULTADO DO PROCESSAMENTO AUTOMÁTICO DE ALERTAS
============================================================
Lixeiras alertadas: 5
Sensores alertados: 2
Emails enviados: 7
Erros: 0
============================================================
✅ Processamento automático concluído com sucesso!
```

### 9.5 Flask-Mail

#### 9.5.1 Configuração

```python
# app.py
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', '')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@tronik.com')
```

#### 9.5.2 Envio de Email

```python
# banco_dados/notificacoes.py
def enviar_email_notificacao(destinatarios, assunto, corpo_html):
    """
    Envia email via Flask-Mail.
    """
    msg = Message(
        subject=assunto,
        recipients=destinatarios,
        html=corpo_html
    )
    mail.send(msg)
```

**Template HTML:**
- Estilizado com CSS inline
- Cores Tronik (verde)
- Informações formatadas
- Footer com identificação

### 9.6 Frontend de Notificações

#### 9.6.1 Página de Notificações

**Funcionalidades:**
- Lista de notificações com scroll
- Filtros (tipo, status envio, status leitura, coletor)
- Estatísticas (total, enviadas, pendentes, hoje)
- Marcação como lida
- Botão para processar alertas manualmente

**Filtros:**
- Tipo: Todos / Coletor Cheia / Bateria Baixa
- Status Envio: Todas / Enviadas / Não Enviadas
- Status Leitura: Todas / Lidas / Não Lidas
- Coletor: ID específico

#### 9.6.2 Badge no Header

**Atualização Automática:**
- Badge mostra contagem de notificações não lidas
- Atualiza a cada 5 minutos
- Atualiza após marcar como lida
- Atualiza após processar alertas

**Visualização:**
- Badge vermelho com número
- "99+" se mais de 99
- Oculto se não houver pendentes

### 9.7 Script CLI

#### 9.7.1 Processar Alertas Manualmente

```bash
# scripts/processar_alertas.py
python scripts/processar_alertas.py
```

**Uso:**
- Testes manuais
- Integração com cron
- Debugging

---

## 10. Geocodificação

### 10.1 Visão Geral

O sistema utiliza **Nominatim (OpenStreetMap)** para converter endereços em coordenadas geográficas (latitude/longitude).

### 10.2 Módulo de Geocodificação

#### 10.2.1 Função Principal

```python
# banco_dados/geocodificacao.py
def geocodificar_endereco(
    endereco: str,
    cidade: str = "Brasília",
    estado: str = "DF",
    pais: str = "Brasil"
) -> Optional[Dict[str, float]]
```

**Estratégias de Busca (em ordem):**
1. Endereço + Cidade + Estado + País
2. Endereço + Cidade + Estado
3. Endereço + Cidade
4. Apenas endereço
5. Variações com contexto de Brasília (se endereço genérico)

**Validação:**
- Prioriza resultados em Brasília/DF
- Valida coordenadas (lat: -16.5 a -15.0, lon: -48.5 a -47.0)
- Fallback para coordenadas aproximadas de Brasília

#### 10.2.2 Rate Limiting

**Configuração:**
```python
RATE_LIMIT_DELAY = 1.0  # 1 segundo entre requisições
```

**Respeito aos Limites:**
- Nominatim permite 1 requisição/segundo
- Sistema aguarda entre requisições
- Tratamento de erro 429 (rate limit)

### 10.3 Geocodificação de Lixeiras

#### 10.3.1 Função de Coletor

```python
def geocodificar_lixeira(
    session: Session,
    coletor_id: int,
    cidade: str = "Brasília",
    estado: str = "DF",
    forcar_atualizacao: bool = False
) -> Tuple[bool, Optional[str]]
```

**Comportamento:**
- Se `forcar_atualizacao=False` e já tem coordenadas: pula
- Geocodifica endereço da coletor
- Atualiza `latitude` e `longitude` no banco
- Retorna sucesso/mensagem

#### 10.3.2 Geocodificação em Lote

```python
def geocodificar_lixeiras_em_lote(
    session: Session,
    cidade: str = "Brasília",
    estado: str = "DF",
    apenas_sem_coordenadas: bool = True,
    limite: Optional[int] = None
) -> Dict[str, any]
```

**Estatísticas Retornadas:**
```python
{
    'total': 40,
    'processadas': 40,
    'sucesso': 12,
    'falha': 28,
    'puladas': 0,
    'erros': [...]
}
```

### 10.4 Script CLI

#### 10.4.1 Geocodificar Lixeiras

```bash
# banco_dados/geocodificar_coletores.py
python banco_dados/geocodificar_coletores.py
```

**Funcionalidades:**
- Processa todas as coletores sem coordenadas
- Respeita rate limiting
- Logs detalhados
- Relatório final

### 10.5 Integração Automática

#### 10.5.1 Criação de Coletor

Quando uma coletor é criada via API, o sistema pode geocodificar automaticamente:

```python
# rotas/api.py
@api_bp.route('/coletor', methods=['POST'])
def criar_lixeira():
    # ... criar coletor ...
    
    # Geocodificar se não tiver coordenadas
    if not coletor.latitude or not coletor.longitude:
        from banco_dados.geocodificacao import geocodificar_lixeira
        geocodificar_lixeira(db, coletor.id)
```

### 10.6 Endpoint Manual

#### 10.6.1 POST /api/coletor/<id>/geocodificar

**Descrição:** Geocodifica coletor manualmente

**Autenticação:** `@login_required`

**Resposta:**
```json
{
    "mensagem": "Coordenadas atualizadas: (-15.7942, -47.8822)"
}
```

**Uso:** Para corrigir coordenadas ou forçar atualização.

---

## 11. Testes Automatizados

### 11.1 Estrutura de Testes

O sistema possui **120 testes automatizados** organizados em arquivos especializados:

```
tests/
├── conftest.py                    # Fixtures e configuração
├── test_api_coletores.py          # Testes de API de coletores
├── test_api_coletas.py           # Testes de API de coletas
├── test_api_sensores.py           # Testes de API de sensores
├── test_api_atualizacao_exclusao.py  # Testes de atualização/exclusão
├── test_api_endpoints_restantes.py   # Testes de outros endpoints
├── test_auth.py                  # Testes de autenticação
├── test_validacoes.py            # Testes de validações
├── test_geocodificacao.py        # Testes de geocodificação
└── test_estatisticas_relatorios.py  # Testes de relatórios
```

### 11.2 Configuração (conftest.py)

#### 11.2.1 Fixtures

**`test_db` (session scope):**
```python
@pytest.fixture(scope='session')
def test_db():
    """Cria banco de dados temporário para testes"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    popular_tipos(engine)
    yield engine
    os.close(db_fd)
    os.unlink(db_path)
```

**`db_session` (function scope):**
```python
@pytest.fixture(scope='function')
def db_session(test_db):
    """Cria sessão limpa para cada teste"""
    # Limpa dados antes de cada teste
    # Mantém tipos (populados no seed)
```

**`client`:**
```python
@pytest.fixture
def client(test_db, db_session):
    """Cliente Flask para testes"""
    app.config['TESTING'] = True
    app.config['DATABASE_SESSION'] = lambda: db_session
    with app.test_client() as client:
        yield client
```

**`auth_headers`:**
```python
@pytest.fixture
def auth_headers(client, db_session):
    """Headers de autenticação para requisições"""
    # Cria usuário de teste
    # Faz login
    # Retorna headers
```

**`create_lixeira`:**
```python
@pytest.fixture
def create_lixeira(db_session):
    """Factory para criar coletores de teste"""
    def _create(**kwargs):
        # Cria coletor com dados padrão ou customizados
    return _create
```

**`create_sensor`:**
```python
@pytest.fixture
def create_sensor(db_session, create_lixeira):
    """Factory para criar sensores de teste"""
    def _create(**kwargs):
        # Cria sensor associado a coletor
    return _create
```

### 11.3 Cobertura de Testes

#### 11.3.1 Testes de API (69 testes)

**Lixeiras (test_api_coletores.py):**
- Listar coletores
- Obter coletor específica
- Criar coletor (sucesso e erros)
- Atualizar coletor
- Deletar coletor
- Filtros (status, parceiro)
- Validações (coordenadas, nível, etc.)

**Coletas (test_api_coletas.py):**
- Listar coletas
- Criar coleta (sucesso e erros)
- Filtros (coletor, parceiro, data)
- Validações (quantidade, tipo operação)

**Sensores (test_api_sensores.py - 18 testes):**
- Listar sensores
- Obter sensor específico
- Criar sensor (sucesso e erros)
- Atualizar sensor
- Deletar sensor
- Filtros (coletor, tipo, bateria)
- Validações (bateria, relacionamentos)

**Atualização/Exclusão (test_api_atualizacao_exclusao.py):**
- Atualizar coletor existente
- Deletar coletor (com cascade)
- Proteção de dados (não perde dados relacionados)
- Validações de permissão

**Outros Endpoints (test_api_endpoints_restantes.py):**
- Estatísticas
- Configurações
- Parceiros
- Tipos (material, sensor, coletor)
- Simulação de níveis
- Geocodificação manual

#### 11.3.2 Testes de Autenticação (11 testes)

**Login (test_auth.py):**
- Login bem-sucedido
- Credenciais inválidas
- Usuário inativo
- Campos obrigatórios
- Suporte a JSON e formulários

**Logout:**
- Logout bem-sucedido
- Redirecionamento

**Registro:**
- Registro bem-sucedido
- Username/email duplicado
- Validação de senha
- Validação de email

#### 11.3.3 Testes de Validações (28 testes)

**test_validacoes.py:**
- Validação de email
- Validação de coordenadas
- Validação de nível de preenchimento
- Validação de senha
- Validação de username
- Validação de latitude/longitude
- Validação de quantidade (kg)
- Validação de KM percorrido
- Validação de preço de combustível
- Validação de tipo de operação
- Validação de bateria

**Cada validação testa:**
- Casos válidos
- Casos inválidos
- Casos limite
- Mensagens de erro

#### 11.3.4 Testes de Geocodificação (9 testes)

**test_geocodificacao.py:**
- Geocodificação bem-sucedida
- Endereço não encontrado
- Rate limiting
- Fallback para coordenadas aproximadas
- Geocodificação de coletor
- Geocodificação em lote
- Validação de coordenadas

**Mocks:**
- Requisições HTTP mockadas
- Não faz requisições reais ao Nominatim

#### 11.3.5 Testes de Relatórios (7 testes)

**test_estatisticas_relatorios.py:**
- Estatísticas gerais
- Relatórios com filtros
- Cálculos financeiros
- Agregações (por coletor, por parceiro)
- Filtros de data
- Filtros de parceiro
- Filtros de tipo de operação

### 11.4 Execução de Testes

#### 11.4.1 Comando Básico

```bash
# Executar todos os testes
pytest

# Com cobertura
pytest --cov=. --cov-report=html

# Apenas um arquivo
pytest tests/test_api_coletores.py

# Apenas um teste
pytest tests/test_api_coletores.py::test_criar_lixeira_success

# Com verbose
pytest -v

# Com output detalhado
pytest -vv
```

#### 11.4.2 Configuração (pytest.ini)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

### 11.5 Mocks e Fixtures

#### 11.5.1 Mocks de APIs Externas

**Geocodificação:**
```python
@pytest.fixture
def mock_geocodificacao(monkeypatch):
    def mock_geocodificar(*args, **kwargs):
        return {'latitude': -15.7942, 'longitude': -47.8822}
    monkeypatch.setattr('banco_dados.geocodificacao.geocodificar_endereco', mock_geocodificar)
```

**Resultado:** Testes rápidos e não dependem de serviços externos.

#### 11.5.2 Isolamento de Banco

**Cada teste:**
- Usa banco temporário
- Limpa dados antes de executar
- Não afeta dados reais
- Rollback automático em caso de erro

### 11.6 Métricas

**Cobertura Atual:**
- **120 testes** passando
- **0 falhas**
- **0 warnings**
- Cobertura de:
  - Todos os endpoints da API
  - Todas as rotas de autenticação
  - Todas as funções de validação
  - Lógica de negócio principal

---

## 12. Docker e Deploy

### 12.1 Dockerfile

#### 12.1.1 Estrutura

```dockerfile
FROM python:3.11-slim

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=app.py

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Criar diretório de dados
RUN mkdir -p /app/data

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/configuracoes', timeout=5)" || exit 1

CMD ["python", "app.py"]
```

**Características:**
- Imagem base leve (python:3.11-slim)
- Cache de layers otimizado
- Health check configurado
- Diretório de dados persistente

### 12.2 Docker Compose

#### 12.2.1 Configuração

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: dashboard-tronik-app
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=${FLASK_ENV:-production}
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=sqlite:///data/tronik.db
      # ... mais variáveis
    volumes:
      - ./data:/app/data  # Persistência do banco
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:5000/api/configuracoes', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

#### 12.2.2 MailHog (Desenvolvimento)

```yaml
mailhog:
  image: mailhog/mailhog:latest
  container_name: dashboard-tronik-mailhog
  ports:
    - "1025:1025"  # SMTP
    - "8025:8025"  # Web UI
  restart: unless-stopped
```

**Uso:** Para testar emails localmente sem servidor SMTP real.

### 12.3 Deploy em Produção

#### 12.3.1 Systemd Service

```ini
# deploy/dashboard-tronik.service
[Unit]
Description=Dashboard-TRONIK Flask Application
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/dashboard-tronik
Environment="PATH=/opt/dashboard-tronik/venv/bin"
ExecStart=/opt/dashboard-tronik/venv/bin/gunicorn -c gunicorn.conf.py app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 12.3.2 Gunicorn

```python
# gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 4
worker_class = "sync"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
```

#### 12.3.3 Nginx (Reverse Proxy)

```nginx
# deploy/nginx/tronik.conf
server {
    listen 80;
    server_name tronik.example.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Arquivos estáticos
    location /static {
        alias /opt/dashboard-tronik/estatico;
        expires 30d;
    }
}
```

### 12.4 Variáveis de Ambiente

#### 12.4.1 Arquivo .env

```env
# Segurança
SECRET_KEY=chave-secreta-forte-gerada

# Ambiente
FLASK_ENV=production
DEBUG=false

# Banco de Dados
DATABASE_URL=sqlite:///tronik.db

# Email (Notificações)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=senha-app
MAIL_DEFAULT_SENDER=noreply@tronik.com

# Agendamento
AGENDAMENTO_ENABLED=true
AGENDAMENTO_INTERVALO_MINUTOS=60

# Admin
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@tronik.com
ADMIN_PASSWORD=SenhaForte123
```

#### 12.4.2 Exemplo (deploy/env.example)

O arquivo `deploy/env.example` contém todas as variáveis com descrições.

---

## 13. Segurança

### 13.1 Autenticação e Autorização

#### 13.1.1 Flask-Login

- Sessões seguras
- Proteção contra session fixation
- Cookies HTTPOnly
- Cookies SameSite
- Cookies Secure em produção

#### 13.1.2 Permissões

- **Usuário comum**: Leitura, criação, atualização
- **Admin**: Todas as operações + exclusão

#### 13.1.3 Validação de Dados

**Sanitização:**
```python
# banco_dados/seguranca.py
def sanitizar_string(texto: str, max_length: Optional[int] = None) -> str:
    # Remove caracteres de controle
    # Limita tamanho
    # Remove espaços extras
```

**Validações:**
- Todos os inputs validados
- Coordenadas dentro de limites
- Níveis 0-100
- Emails com regex
- Senhas com requisitos de força

### 13.2 Headers de Segurança

#### 13.2.1 Flask-Talisman

```python
talisman = Talisman(
    app,
    force_https=FLASK_ENV == 'production',
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,  # 1 ano
    content_security_policy={
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        'style-src': "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        'img-src': "'self' data: https:",
        'font-src': "'self' data: https://cdn.jsdelivr.net",
        'connect-src': "'self' https://cdn.jsdelivr.net https://router.project-osrm.org",
    }
)
```

**Headers Adicionados:**
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy: ...`

### 13.3 Rate Limiting

#### 13.3.1 Flask-Limiter

```python
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv('RATELIMIT_STORAGE_URL', 'memory://'),
    enabled=os.getenv('RATELIMIT_ENABLED', 'true').lower() == 'true'
)
```

**Limites:**
- Global: 200/dia, 50/hora
- Processar alertas: 5/minuto
- Simular níveis: 10/minuto

**Resposta 429:**
```json
{
    "erro": "Muitas requisições. Tente novamente mais tarde."
}
```

### 13.4 Proteção de Senhas

#### 13.4.1 Hash Bcrypt

- Algoritmo: bcrypt (via Werkzeug)
- Salt automático e único
- Nunca armazenado em texto plano
- Verificação segura

#### 13.4.2 Requisitos de Senha

- Mínimo 8 caracteres
- Pelo menos uma maiúscula
- Pelo menos uma minúscula
- Pelo menos um número

### 13.5 SQL Injection

**Prevenção:**
- SQLAlchemy ORM (parametrização automática)
- Nunca concatenação de strings em queries
- Validação de tipos

### 13.6 XSS (Cross-Site Scripting)

**Prevenção:**
- Sanitização de inputs
- Escape HTML no frontend (`escapeHtml()`)
- Content Security Policy
- Headers X-XSS-Protection

### 13.7 CSRF (Cross-Site Request Forgery)

**Prevenção:**
- Cookies SameSite=Lax
- Tokens CSRF (futuro)
- Verificação de origem

---

## 14. Módulos e Utilitários

### 14.1 Utilitários de Data/Hora

#### 14.1.1 banco_dados/utils.py

```python
def utc_now():
    """Retorna datetime UTC com timezone (Python 3.12+)"""
    return datetime.now(timezone.utc)

def utc_now_naive():
    """Retorna datetime UTC sem timezone (compatibilidade)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

**Motivo:** `datetime.utcnow()` está deprecado no Python 3.12+.

**Uso:** Substitui todas as chamadas a `datetime.utcnow()` no código.

### 14.2 Seed de Tipos

#### 14.2.1 banco_dados/seed_tipos.py

```python
def popular_tipos(engine):
    """Popula tabelas de tipos se não existirem"""
    # Tipos de Material
    # Tipos de Sensor
    # Tipos de Coletor
```

**Tipos Padrão:**
- **Material**: Plástico, Papel, Metal, Vidro, Orgânico
- **Sensor**: Ultrassônico, Infravermelho, Peso
- **Coletor**: Caminhão, Carreta, Van

**Características:**
- Idempotente (pode executar múltiplas vezes)
- Não duplica tipos existentes

### 14.3 Importação de Dados

#### 14.3.1 banco_dados/importar_csv.py

**Funcionalidade:** Importa dados de coletas de arquivo CSV

**Formato CSV Esperado:**
```csv
Data,Localização,Volume (kg),KM Percorrido,Preço Combustível,Lucro por kg,Tipo Operação,Parceiro
2025-10-17,Shopping Conjunto Nacional,60.0,15.2,5.50,2.00,Avulsa,Parceiro Exemplo
```

**Processo:**
1. Lê arquivo CSV
2. Valida dados
3. Busca/cria parceiros
4. Busca/cria coletores
5. Cria coletas
6. Relatório de importação

**Validações:**
- Datas válidas
- Volumes > 0
- KM >= 0
- Preços >= 0
- Tipos de operação válidos

### 14.4 Migrações

#### 14.4.1 banco_dados/migrar_notificacoes.py

**Funcionalidade:** Adiciona colunas `lida` e `lida_em` à tabela `notificacoes`

**Uso:**
```bash
python banco_dados/migrar_notificacoes.py
```

**Características:**
- Verifica se colunas já existem
- Adiciona apenas se necessário
- Logs detalhados
- Rollback em caso de erro

#### 14.4.2 banco_dados/migrar_dados.py

**Funcionalidade:** Migra dados de formato antigo para novo

**Processo:**
- Converte coordenadas string para float
- Converte tipos string para IDs
- Atualiza relacionamentos
- Backup automático

---

## 15. Scripts e Ferramentas

### 15.1 Scripts CLI

#### 15.1.1 processar_alertas.py

```bash
# scripts/processar_alertas.py
python scripts/processar_alertas.py
```

**Funcionalidade:** Processa alertas manualmente (sem agendamento)

**Uso:**
- Testes
- Debugging
- Integração com cron
- Execução sob demanda

#### 15.1.2 geocodificar_coletores.py

```bash
# banco_dados/geocodificar_coletores.py
python banco_dados/geocodificar_coletores.py
```

**Funcionalidade:** Geocodifica todas as coletores sem coordenadas

**Características:**
- Rate limiting automático
- Logs detalhados
- Relatório final
- Pode ser executado múltiplas vezes

#### 15.1.3 migrar_notificacoes.py

```bash
# banco_dados/migrar_notificacoes.py
python banco_dados/migrar_notificacoes.py
```

**Funcionalidade:** Adiciona colunas de leitura às notificações

### 15.2 Ferramentas de Desenvolvimento

#### 15.2.1 pytest.ini

Configuração do Pytest para execução de testes.

#### 15.2.2 .dockerignore

Arquivo que especifica quais arquivos e diretórios devem ser ignorados durante o build do Docker.

**Arquivos Ignorados:**
- `.git/` - Controle de versão
- `__pycache__/` - Cache Python
- `*.pyc`, `*.pyo` - Bytecode Python
- `.env` - Variáveis de ambiente (não versionadas)
- `venv/`, `env/` - Ambientes virtuais
- `tests/` - Testes (não necessários em produção)
- `*.db`, `*.sqlite` - Bancos de dados locais
- `.pytest_cache/` - Cache de testes
- `htmlcov/` - Relatórios de cobertura
- `*.md` - Documentação (opcional)

**Resultado:** Imagens Docker menores e builds mais rápidos.

#### 15.2.3 requirements.txt

Lista todas as dependências Python do projeto.

**Principais Dependências:**
- Flask 2.3.3
- SQLAlchemy 2.0.23+
- Flask-Login 0.6.3
- Flask-Limiter 3.5.0
- Flask-Talisman 1.1.0
- Flask-Mail 0.9.1
- APScheduler 3.10.4
- ReportLab 4.0.7
- Werkzeug 2.3.7

**Uso:**
```bash
pip install -r requirements.txt
```

### 15.3 Documentação Adicional

#### 15.3.1 ESTADO_ATUAL_PROJETO.md

Documento que descreve o estado atual do projeto, funcionalidades implementadas, pendências e próximos passos.

**Seções:**
- Funcionalidades Implementadas
- Pendências
- Melhorias Futuras
- Roadmap

#### 15.3.2 DOCKER.md

Documentação completa sobre Docker:
- Como construir a imagem
- Como executar com Docker Compose
- Configuração de variáveis de ambiente
- Troubleshooting

#### 15.3.3 README.md

Documentação principal do projeto:
- Visão geral
- Instalação
- Configuração
- Uso básico
- Contribuição

---

## 16. Conclusão

### 16.1 Resumo do Sistema

O **Dashboard-TRONIK** é um sistema completo e robusto de monitoramento e gestão de coletores inteligentes, desenvolvido com tecnologias modernas e boas práticas de engenharia de software.

**Principais Características:**
- ✅ **120 testes automatizados** com 0 falhas
- ✅ **30+ endpoints REST** documentados
- ✅ **Sistema de roteamento modular** com múltiplos algoritmos
- ✅ **Notificações automáticas** por email
- ✅ **Geocodificação automática** de endereços
- ✅ **Interface responsiva** com identidade visual Tronik
- ✅ **Segurança robusta** (CSP, rate limiting, validações)
- ✅ **Dockerização completa** para deploy fácil
- ✅ **Documentação extensa** e detalhada

### 16.2 Arquitetura e Design

O sistema segue princípios de:
- **Modularidade**: Código organizado em módulos especializados
- **Separação de Responsabilidades**: Backend, frontend e banco bem separados
- **Testabilidade**: Cobertura completa de testes
- **Manutenibilidade**: Código limpo e documentado
- **Escalabilidade**: Preparado para crescimento

### 16.3 Tecnologias Utilizadas

**Backend:**
- Python 3.11+ com Flask
- SQLAlchemy ORM
- Flask-Login para autenticação
- APScheduler para tarefas agendadas
- Flask-Mail para notificações
- ReportLab para PDFs

**Frontend:**
- JavaScript vanilla (ES6+)
- Leaflet.js para mapas
- Chart.js para gráficos
- CSS3 com metodologia BEM

**DevOps:**
- Docker e Docker Compose
- Gunicorn para produção
- Nginx como reverse proxy

### 16.4 Próximos Passos Sugeridos

**Melhorias Futuras:**
1. **Cálculo de Lucro por KG**: Implementar cálculo automático baseado em histórico
2. **Dashboard em Tempo Real**: WebSockets para atualizações em tempo real
3. **API de Integração**: Endpoints para integração com sistemas externos
4. **Relatórios Avançados**: Mais visualizações e análises
5. **Mobile App**: Aplicativo nativo ou PWA
6. **Machine Learning**: Previsão de níveis e otimização de rotas
7. **Multi-tenancy**: Suporte a múltiplas organizações
8. **Backup Automático**: Sistema de backup do banco de dados

### 16.5 Contribuição

O sistema está preparado para contribuições:
- Código bem documentado
- Testes automatizados
- Padrões de código consistentes
- Documentação completa

### 16.6 Suporte

Para dúvidas, problemas ou sugestões:
- Consulte a documentação
- Verifique os logs do sistema
- Execute os testes para validar funcionalidades
- Consulte `ESTADO_ATUAL_PROJETO.md` para status atual

---

## 📚 Referências e Recursos

### Documentação Externa

- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Leaflet.js Documentation](https://leafletjs.com/)
- [Chart.js Documentation](https://www.chartjs.org/)
- [Docker Documentation](https://docs.docker.com/)
- [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)

### Bibliotecas e Ferramentas

- **Flask**: Framework web Python
- **SQLAlchemy**: ORM para Python
- **Leaflet**: Biblioteca JavaScript para mapas interativos
- **Leaflet Routing Machine**: Plugin para cálculo de rotas
- **Chart.js**: Biblioteca para gráficos
- **Nominatim**: Serviço de geocodificação OpenStreetMap
- **OSRM**: Servidor de roteamento Open Source

---

## 📝 Histórico de Versões

### Versão 2.1 (24 de Novembro de 2025)
- ✅ **Migração completa: lixeira → coletor** em todo o sistema
- ✅ **Dashboard Comercial completo** com KPIs e análises
- ✅ **Sistema CRM completo** com funil de vendas e tarefas
- ✅ **Gestão de Contratos** recorrentes
- ✅ **Verificação e correção de todos os endpoints** (55+ endpoints)
- ✅ Correção de problemas com `lazy="dynamic"` em SQLAlchemy
- ✅ Correção do WebSocket (erro "write() before start_response")
- ✅ Substituição de emojis por ícones PNG profissionais
- ✅ Layout personalizável no dashboard comercial (drag-and-drop)
- ✅ Filtro de período expandido (todos os períodos)

### Versão 2.0 (20 de Novembro de 2025)
- ✅ Sistema de roteamento modular completo
- ✅ Notificações automáticas com APScheduler
- ✅ CRUD completo de sensores
- ✅ Exportação PDF de relatórios
- ✅ Melhorias de UX e acessibilidade
- ✅ Esquema de cores Tronik (verde)
- ✅ 120 testes automatizados
- ✅ Documentação completa

### Versão 1.0
- ✅ Funcionalidades básicas de monitoramento
- ✅ Dashboard principal
- ✅ API REST básica
- ✅ Sistema de autenticação
- ✅ Geocodificação de coletores

---

**Fim da Documentação**

---

*Documentação gerada em: 24 de Novembro de 2025*  
*Sistema: Dashboard-TRONIK v2.1*  
*Desenvolvido para: Tronik Recicla*