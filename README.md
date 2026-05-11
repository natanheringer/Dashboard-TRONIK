# Dashboard-TRONIK

## Sobre o Projeto

O Dashboard-TRONIK é um sistema web de monitoramento e gestão de coletores inteligentes de resíduos eletrônicos, desenvolvido para a empresa Tronik Recicla. Permite visualizar em tempo real o nível de preenchimento e status de cada coletor equipada com sensores ultrassônicos e conecta esses dados a módulos comerciais (dashboard comercial, CRM e gestão de contratos).

## Objetivo

Desenvolver uma solução web completa para monitoramento e gestão de coletores de resíduos eletrônicos, permitindo que a equipe aprenda desenvolvimento web moderno através de um projeto real e prático, ao mesmo tempo em que gera valor direto para a operação da Tronik Recicla.

## Stack Tecnológico

- **Frontend:** HTML5 + CSS3 + JavaScript (ES6+, vanilla) + Leaflet.js + Chart.js
- **Backend:** Python 3.11+ + Flask 2.3.3 + SQLAlchemy 2.0+
- **Banco de Dados:** SQLite (desenvolvimento) / PostgreSQL/MySQL (produção)
- **Comunicação:** REST API + WebSocket (Flask-SocketIO)
- **Mapas:** Leaflet.js + Leaflet Routing Machine + OpenStreetMap + algoritmos A* e Dijkstra(fallback) 
- **Notificações:** Flask-Mail + APScheduler
- **Testes:** Pytest (120+ testes automatizados)

## Estrutura do Projeto

```
dashboard-tronik/
├── app.py                    # Aplicação Flask principal
├── requirements.txt          # Dependências Python
├── banco_dados/             # Configuração e modelos do banco
│   ├── modelos.py           # Modelos de dados (Coletor, Sensor, Pipeline, etc.)
│   ├── inicializar.py       # Setup inicial do banco de dados
│   ├── services/            # Camada de serviços (lógica de negócio)
│   │   ├── coletor_service.py
│   │   ├── coleta_service.py
│   │   ├── comercial_service.py
│   │   ├── crm_service.py
│   │   ├── contrato_service.py
│   │   └── relatorio_service.py
│   ├── utils/              # Utilitários
│   │   ├── datetime_utils.py
│   │   ├── logger.py
│   │   ├── erros.py
│   │   └── cache.py
│   ├── serializers.py      # Serialização de modelos
│   ├── geocodificacao.py   # Geocodificação de endereços
│   └── notificacoes.py     # Sistema de notificações
├── estatico/                # Arquivos estáticos (CSS, JS, imagens)
│   ├── css/
│   │   └── estilo.css       # Estilos do dashboard
│   ├── js/
│   │   ├── dashboard.js     # Lógica principal do dashboard
│   │   ├── api.js           # Comunicação com backend
│   │   ├── comercial.js     # Lógica do dashboard comercial
│   │   ├── crm.js           # Lógica do CRM
│   │   ├── mapa.js          # Módulo de mapas
│   │   ├── mapa-page.js     # Lógica da página de mapa
│   │   ├── relatorios.js    # Lógica de relatórios
│   │   ├── configuracoes.js # Lógica de configurações
│   │   ├── notificacoes.js  # Lógica de notificações
│   │   ├── routing/         # Sistema de roteamento modular
│   │   └── utils/           # Utilitários frontend
│   └── imagens/             # Imagens e ícones
├── templates/               # Templates HTML
│   ├── base.html            # Template base
│   ├── index.html           # Dashboard principal
│   ├── comercial.html       # Dashboard comercial
│   ├── crm.html             # Página CRM
│   ├── contratos.html       # Página de contratos
│   ├── mapa.html            # Página de mapa
│   ├── relatorios.html      # Página de relatórios
│   ├── configuracoes.html   # Página de configurações
│   ├── notificacoes.html    # Página de notificações
│   ├── login.html           # Página de login
│   ├── registro.html        # Página de registro
│   └── sobre.html           # Página sobre
├── rotas/                   # Definição de rotas (Blueprints)
│   ├── api/                 # API REST modularizada
│   │   ├── coletores.py     # Endpoints de coletores
│   │   ├── coletas.py       # Endpoints de coletas
│   │   ├── sensores.py      # Endpoints de sensores
│   │   ├── notificacoes.py  # Endpoints de notificações
│   │   ├── relatorios.py    # Endpoints de relatórios
│   │   ├── comercial.py     # Endpoints comerciais
│   │   ├── crm.py           # Endpoints de CRM
│   │   ├── contratos.py     # Endpoints de contratos
│   │   └── auxiliares.py    # Endpoints auxiliares
│   ├── auth.py              # Rotas de autenticação
│   ├── paginas.py           # Rotas das páginas web
│   └── websocket.py         # WebSocket para tempo real
├── tests/                   # Testes automatizados (120+ testes)
│   ├── conftest.py          # Configuração e fixtures
│   ├── test_api_*.py        # Testes de API
│   ├── test_auth.py         # Testes de autenticação
│   └── test_*.py            # Outros testes
├── scripts/                 # Scripts auxiliares
│   └── processar_alertas.py # Processar alertas manualmente
└── deploy/                  # Configurações de deploy
    ├── dashboard-tronik.service
    └── nginx/               # Configuração Nginx
```

## Como Começar

### Para Iniciantes
Se você nunca trabalhou com desenvolvimento web, Git, ou em equipe, comece aqui:
**[GUIA_DESENVOLVIMENTO.md](GUIA_DESENVOLVIMENTO.md)** - Setup completo e fluxo de trabalho

### Para Quem Já Tem Experiência
Se você já sabe usar terminal e Git:

```bash
# Clone o repositório
git clone [URL_DO_REPOSITORIO]
cd Dashboard-TRONIK

# Instale as dependências Python
pip install -r requirements.txt

# Execute a aplicação
python app.py
```

### Acesse o Dashboard
Abra seu navegador e acesse: `http://localhost:5000`

## Organização da Equipe

A equipe deve se auto-organizar baseada nos interesses e habilidades de cada membro. O projeto permite diferentes abordagens:

### Áreas de Desenvolvimento
- **Frontend:** Interface web (HTML, CSS, JavaScript)
- **Backend:** APIs e lógica (Python, Flask, SQLite)
- **Dados:** Mock data, testes e validação
- **Documentação:** README, comentários e guias

### Como Começar
1. Leia o [GUIA_DESENVOLVIMENTO.md](GUIA_DESENVOLVIMENTO.md)
2. Explore a estrutura do projeto
3. Escolha uma área baseada no seu interesse
4. Comece com tarefas simples
5. Colabore com outros membros conforme necessário

## Funcionalidades Implementadas

- [x] ✅ Dashboard visual com grid de coletores
- [x] ✅ API REST completa para CRUD de coletores e sensores
- [x] ✅ Simulação de mudança de nível em tempo real
- [x] ✅ Sistema de alertas (nível > 80%, bateria < 20%)
- [x] ✅ Relatórios financeiros e operacionais completos
- [x] ✅ Interface responsiva para mobile, tablet e desktop
- [x] ✅ **Dashboard Comercial** com KPIs e análises
- [x] ✅ **Sistema CRM** completo com funil de vendas
- [x] ✅ **Gestão de Contratos** recorrentes
- [x] ✅ Mapa interativo com rotas otimizadas
- [x] ✅ Geocodificação automática de endereços
- [x] ✅ Notificações automáticas por email
- [x] ✅ WebSocket para atualizações em tempo real
- [x] ✅ Testes automatizados (120+ testes)

## Documentação Principal

- `docs/ARQUITETURA.md` — Diagramas Mermaid alinhados ao código atual (preview v2, API, telemetria, ML, jobs de ingestão)
- `DOCUMENTAÇÃO_COMPLETA.md` — Visão geral completa, arquitetura, backend, frontend, banco de dados, segurança, testes e deploy
- `ESTADO_ATUAL_PROJETO.md` — Resumo executivo do estado atual (funcionalidades, métricas, próximos passos)
- `docs/MVP.md` — Definição do MVP original e sua evolução até a versão atual
- `docs/Planejamento.md` — Backlog, roadmap e histórias de usuário atualizados
- `docs/Especificacao_Tecnica.md` — Stack técnica, arquitetura e integrações atualizadas
- `ESPECIFICACAO_TECNICA_NOVAS_FEATURES.md` — Especificação das features comerciais (dashboard comercial, CRM, contratos)

## Deploy em Produção

O projeto está configurado para deploy em plataformas cloud:

### Railway.app (Recomendado) 🚂

- **Guia Completo:** [`GUIA_DEPLOY_RAILWAY.md`](GUIA_DEPLOY_RAILWAY.md)
- **Análise de Migração:** [`ANALISE_MIGRACAO_RENDER_RAILWAY.md`](ANALISE_MIGRACAO_RENDER_RAILWAY.md)
- **Configuração:** `railway.json` ou `Procfile`
- **Modelo:** Pay-as-you-go (mais flexível)
- **Vantagens:** Escalabilidade automática, sem hibernação, interface moderna

### Render.com (Atual) 🎨

- **Guia Completo:** [`GUIA_DEPLOY_RENDER.md`](GUIA_DEPLOY_RENDER.md)
- **Configuração:** `render.yaml`
- **Modelo:** Plano fixo mensal
- **Status:** Sistema atual em produção

### Docker 🐳

- **Guia:** [`DOCKER.md`](DOCKER.md)
- **Configuração:** `Dockerfile` e `docker-compose.yml`
- **Uso:** Desenvolvimento local ou deploy em servidor próprio

## Documentação Legada / Histórica

A pasta `documentacao_legado/` contém análises detalhadas, relatórios de investigação, changelogs e decisões históricas que foram importantes durante o desenvolvimento, mas não são necessárias para o uso diário do sistema ou onboarding de novos contribuidores:

- `documentacao_legado/ANALISE_CONFLITOS_DADOS.md`
- `documentacao_legado/ANALISE_ERROS_SISTEMA.md`
- `documentacao_legado/ANALISE_IMPORTACAO_PRECIFICACAO.md`
- `documentacao_legado/ANALISE_INTEGRACAO_NOVAS_FEATURES.md`
- `documentacao_legado/INVESTIGACAO_PROFUNDA_SISTEMA.md`
- `documentacao_legado/INVESTIGACAO_ADICIONAL_ROBUSTEZ.md`
- `documentacao_legado/DOCUMENTACAO_ROBUSTEZ.md`
- `documentacao_legado/PONTOS_CRITICOS_IMPLEMENTAR.md`
- `documentacao_legado/IMPLEMENTACOES_2025.md`
- `documentacao_legado/MUDANÇAS_SESSAO_2025.md`
- `documentacao_legado/RELATORIO_MUDANCAS.md`
- `documentacao_legado/PROGRESSO_IMPLEMENTACAO.md`
- `documentacao_legado/CHANGELOG_IMPLEMENTACOES.md`
- `documentacao_legado/CHANGELOG_PRECIFICACAO.md`
- `documentacao_legado/MELHORIAS_IMPLEMENTADAS.md`
- `documentacao_legado/MELHORIAS_PAGINA_COMERCIAL.md`
- `documentacao_legado/RESUMO_IMPORTACAO_PRECIFICACAO.md`
- `documentacao_legado/COORDENADAS_COMPLETAS.md`

Esses arquivos são úteis como registro técnico e histórico de decisões, mas a documentação principal para entender e evoluir o sistema está nas seções anteriores.


## Desenvolvimento

### Padrões de Código
- **Python:** PEP 8
- **JavaScript:** ES6+
- **CSS:** BEM methodology
- **Commits:** Conventional Commits

### Fluxo de Trabalho
1. Criar branch para feature
2. Desenvolver com testes
3. Code review
4. Merge para main

## Licença

Este projeto está sob a licença GPL-2.0. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## Contribuindo

1. Faça fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Contribuidores

Veja a lista completa de contribuidores em [CONTRIBUTORS.md](CONTRIBUTORS.md).

## Contato

Para dúvidas sobre o projeto, entre em contato com a equipe de desenvolvimento.

---

**Nota:** Este é um projeto acadêmico focado no aprendizado de desenvolvimento web.