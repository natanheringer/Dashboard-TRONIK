# Especificação Técnica

**Versão:** 2.1  
**Data de Atualização:** 24 de Novembro de 2025  
**Status:** Sistema Completo e Pronto para Deploy

## 1. Visão Geral

O **Dashboard-TRONIK** é um sistema web completo desenvolvido para a **Tronik Recicla**, empresa especializada na coleta e reciclagem de resíduos eletrônicos. O sistema monitora coletores inteligentes equipados com sensores ultrassônicos, fornecendo visibilidade em tempo real sobre níveis de preenchimento, status operacional e permitindo otimização de rotas e controle eficiente da logística de coleta.

## 2. Stack de Desenvolvimento

### 2.1 Backend
- **Python 3.11+**: Linguagem principal
- **Flask 2.3.3**: Framework web
- **SQLAlchemy 2.0.23+**: ORM para banco de dados
- **Flask-Login 0.6.3**: Gerenciamento de sessões
- **Flask-Limiter 3.5.0**: Rate limiting
- **Flask-Talisman 1.1.0**: Headers de segurança HTTP
- **Flask-Mail 0.9.1**: Envio de emails
- **Flask-SocketIO 5.3.6**: WebSocket para tempo real
- **APScheduler 3.10.4**: Agendamento de tarefas
- **ReportLab 4.0.7**: Geração de PDFs
- **Werkzeug 3.0.1**: Hash seguro de senhas

### 2.2 Frontend
- **HTML5**: Estrutura semântica das páginas
- **CSS3**: Estilização com metodologia BEM e design responsivo
- **JavaScript ES6+**: Lógica do cliente (vanilla, sem frameworks pesados)
- **Leaflet.js 1.9.4**: Mapas interativos
- **Leaflet.markercluster 1.5.3**: Agrupamento de marcadores
- **Leaflet Routing Machine 3.2.12**: Cálculo e exibição de rotas
- **Chart.js**: Gráficos e visualizações
- **SortableJS**: Drag-and-drop para personalização

### 2.3 Banco de Dados
- **SQLite**: Banco de dados relacional (desenvolvimento)
- **PostgreSQL/MySQL**: Suporte via SQLAlchemy (produção)
- **IndexedDB**: Cache local no navegador para rotas e dados OSM

### 2.4 DevOps
- **Docker**: Containerização
- **Docker Compose**: Orquestração
- **Gunicorn**: Servidor WSGI (produção)
- **Nginx**: Reverse proxy

### 2.5 APIs e Serviços Externos
- **Nominatim (OpenStreetMap)**: Geocodificação de endereços
- **OSRM (Open Source Routing Machine)**: Cálculo de rotas otimizadas
- **Overpass API**: Busca de dados de estradas do OpenStreetMap

### 2.6 Testes
- **Pytest 7.4.2**: Framework de testes
- **pytest-flask 1.2.0**: Extensão para Flask
- **pytest-cov 4.1.0**: Cobertura de código

## 3. Interface do Usuário (Implementada)

### 3.1 Páginas Principais
- **Dashboard Principal** (`/`): Grid de coletores, filtros, estatísticas, histórico
- **Dashboard Comercial** (`/comercial`): KPIs financeiros, metas, análise por parceiro, gráficos
- **CRM** (`/crm`): Funil de vendas (Kanban), pipeline, interações, tarefas
- **Contratos** (`/contratos`): Gestão de contratos recorrentes, receita mensal
- **Mapa** (`/mapa`): Visualização geográfica, rotas otimizadas, filtros
- **Relatórios** (`/relatorios`): Relatórios financeiros e operacionais, exportação PDF/CSV
- **Configurações** (`/configuracoes`): CRUD de coletores e sensores
- **Notificações** (`/notificacoes`): Lista de notificações, filtros, estatísticas

## 4. Arquitetura e Integrações

### 4.1 Visão Geral
O sistema segue arquitetura **MVC (Model-View-Controller)** adaptada para Flask. O backend (`app.py`) expõe rotas de páginas e API REST. O frontend (templates + estáticos) consome a API via `estatico/js/api.js` e renderiza via módulos JavaScript especializados. Dados são persistidos em banco de dados SQLite/PostgreSQL via SQLAlchemy ORM.

### 4.2 Módulos Principais

**Backend:**
- `app.py`: Inicializa Flask, registra blueprints, configura segurança, WebSocket, banco de dados
- `rotas/api/`: API REST modularizada (55+ endpoints em blueprints especializados)
  - `coletores.py`: CRUD de coletores
  - `coletas.py`: Gestão de coletas
  - `sensores.py`: CRUD de sensores
  - `notificacoes.py`: Sistema de notificações
  - `relatorios.py`: Relatórios financeiros e operacionais
  - `comercial.py`: Dashboard comercial
  - `crm.py`: Sistema CRM
  - `contratos.py`: Gestão de contratos
  - `auxiliares.py`: Endpoints auxiliares
- `rotas/auth.py`: Autenticação (login, logout, registro)
- `rotas/paginas.py`: Rotas das páginas web
- `rotas/websocket.py`: WebSocket para atualizações em tempo real
- `banco_dados/modelos.py`: 15 modelos SQLAlchemy
- `banco_dados/services/`: Camada de serviços (lógica de negócio)
- `banco_dados/utils/`: Utilitários (datetime, logger, erros, cache)

**Frontend:**
- `templates/`: 12 templates HTML (Jinja2)
- `estatico/js/`: Módulos JavaScript especializados
  - `api.js`: Cliente API
  - `dashboard.js`: Lógica do dashboard principal
  - `comercial.js`: Dashboard comercial
  - `crm.js`: Sistema CRM
  - `mapa.js`: Módulo de mapas
  - `routing/`: Sistema de roteamento modular (7 módulos)
- `estatico/css/`: Folhas de estilo (metodologia BEM)

### 4.3 Endpoints Implementados (55+ endpoints)

**Coletores:**
- GET `/api/coletores` - Listar todas
- GET `/api/coletor/<id>` - Detalhes
- POST `/api/coletor` - Criar (autenticado)
- PUT `/api/coletor/<id>` - Atualizar (autenticado)
- DELETE `/api/coletor/<id>` - Deletar (admin)
- POST `/api/coletor/<id>/geocodificar` - Geocodificar manualmente

**Coletas:**
- GET `/api/coletas` - Listar com filtros
- GET `/api/historico` - Histórico com filtro de data
- POST `/api/coleta` - Criar nova coleta

**Sensores:**
- GET `/api/sensores` - Listar com filtros
- GET `/api/sensor/<id>` - Detalhes
- POST `/api/sensor` - Criar (autenticado)
- PUT `/api/sensor/<id>` - Atualizar (autenticado)
- DELETE `/api/sensor/<id>` - Deletar (admin)

**Notificações:**
- GET `/api/notificacoes` - Listar com filtros
- POST `/api/notificacoes/processar-alertas` - Processar alertas (admin)
- PUT `/api/notificacoes/<id>/marcar-lida` - Marcar como lida

**Comercial:**
- GET `/api/comercial/dashboard` - Dados do dashboard comercial
- GET `/api/comercial/meta` - Meta mensal atual
- PUT `/api/comercial/meta` - Atualizar meta
- GET `/api/comercial/metricas` - Métricas financeiras
- GET `/api/comercial/parceiros` - Análise por parceiro

**CRM:**
- GET `/api/crm/pipeline` - Listar pipeline de vendas
- POST `/api/crm/pipeline` - Criar novo lead
- GET `/api/crm/funil` - Dados do funil de vendas
- GET `/api/crm/estatisticas` - Estatísticas do CRM

**Contratos:**
- GET `/api/contratos` - Listar contratos
- POST `/api/contratos` - Criar novo contrato
- GET `/api/contratos/receita-mensal` - Calcular receita mensal

**Auxiliares:**
- GET `/api/estatisticas` - Estatísticas gerais
- GET `/api/configuracoes` - Configurações do sistema
- GET `/api/parceiros` - Listar parceiros
- GET `/api/tipos/*` - Listar tipos (material, sensor, coletor)

### 4.4 Modelo de Dados (Implementado)

**Modelos Principais (15 modelos):**
- **Usuario**: Autenticação e autorização
- **Coletor**: Coletores de resíduos eletrônicos
- **Sensor**: Sensores ultrassônicos dos coletores
- **Coleta**: Registro de coletas realizadas
- **Notificacao**: Alertas e notificações
- **Parceiro**: Parceiros da Tronik Recicla
- **TipoMaterial, TipoSensor, TipoColetor**: Tipos de classificação
- **MetaComercial**: Metas mensais de faturamento
- **Pipeline**: Pipeline de vendas/CRM
- **Interacao**: Registro de interações com clientes
- **Tarefa**: Tarefas do CRM
- **ContratoRecorrente**: Contratos recorrentes
- **PreferenciaLayout**: Preferências de layout do usuário

### 4.5 Decisões Técnicas Implementadas

- ✅ **Banco de Dados Real**: SQLAlchemy ORM com SQLite (dev) / PostgreSQL (prod)
- ✅ **Comunicação em Tempo Real**: WebSocket (Flask-SocketIO) para atualizações instantâneas
- ✅ **Autenticação Completa**: Flask-Login com sessões seguras e permissões
- ✅ **Segurança Robusta**: Rate limiting, headers de segurança, validação completa
- ✅ **Sistema de Roteamento**: Módulo robusto com múltiplas estratégias de fallback
- ✅ **Testes Automatizados**: 120+ testes com cobertura completa

### 4.6 Padrões e Qualidade

- **Python**: PEP 8, type hints onde aplicável
- **JavaScript**: ES6+, módulos, padrão Module
- **CSS**: Metodologia BEM, design responsivo
- **Commits**: Conventional Commits
- **Arquitetura**: Service Layer Pattern, Blueprint Pattern, Repository Pattern

### 4.7 Implantação

- ✅ **Docker**: Containerização completa com Dockerfile e docker-compose.yml
- ✅ **Gunicorn**: Servidor WSGI configurado para produção
- ✅ **Nginx**: Reverse proxy configurado
- ✅ **Variáveis de Ambiente**: Configuração via `.env`
- ✅ **Health Checks**: Configurados no Docker
- ✅ **Deploy**: Pronto para Render.com, Heroku, ou servidor próprio

