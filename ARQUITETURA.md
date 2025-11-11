# Arquitetura do Dashboard-TRONIK

## Diagrama de Arquitetura Completa

```mermaid
graph TB
    subgraph "Cliente - Navegador"
        Browser[Browser]
        subgraph "Frontend - Templates HTML"
            Index[index.html<br/>Dashboard Principal]
            Relatorios[relatorios.html<br/>Relatórios e Gráficos]
            Config[configuracoes.html<br/>CRUD Lixeiras]
            Sobre[sobre.html<br/>Informações do Projeto]
            Base[base.html<br/>Template Base]
        end
        
        subgraph "Frontend - JavaScript"
            DashboardJS[dashboard.js<br/>Lógica Principal<br/>- Carregar dados<br/>- Renderizar grid<br/>- Filtros<br/>- Exportar CSV<br/>- Polling automático]
            APIJS[api.js<br/>Comunicação API<br/>- GET/POST/PUT/DELETE<br/>- Requisições HTTP<br/>- Tratamento de erros]
        end
        
        subgraph "Frontend - CSS"
            EstiloCSS[estilo.css<br/>Estilos Globais]
            RelatoriosCSS[relatorios.css<br/>Estilos Relatórios]
            ConfigCSS[configuracoes.css<br/>Estilos Configurações]
            SobreCSS[sobre.css<br/>Estilos Sobre]
        end
    end
    
    subgraph "Backend - Flask Application"
        App[app.py<br/>Aplicação Principal<br/>- Inicialização Flask<br/>- Configuração CORS<br/>- Setup Banco de Dados<br/>- Registro de Blueprints]
        
        subgraph "Blueprints"
            APIBP[api.py<br/>Blueprint API<br/>Endpoints REST]
            PaginasBP[paginas.py<br/>Blueprint Páginas<br/>Rotas HTML]
        end
        
        subgraph "Endpoints API"
            GET1[GET /api/lixeiras<br/>Listar todas]
            GET2[GET /api/lixeira/id<br/>Obter uma]
            GET3[GET /api/estatisticas<br/>Estatísticas gerais]
            GET4[GET /api/historico<br/>Histórico coletas]
            GET5[GET /api/configuracoes<br/>Configurações sistema]
            GET6[GET /api/relatorios<br/>Dados para relatórios]
            POST1[POST /api/lixeira<br/>Criar nova]
            PUT1[PUT /api/lixeira/id<br/>Atualizar]
            DELETE1[DELETE /api/lixeira/id<br/>Deletar]
        end
        
        subgraph "Rotas Páginas"
            R1[GET /<br/>Dashboard]
            R2[GET /relatorios<br/>Relatórios]
            R3[GET /configuracoes<br/>Configurações]
            R4[GET /sobre<br/>Sobre]
        end
    end
    
    subgraph "Banco de Dados"
        subgraph "Modelos SQLAlchemy"
            ModelLixeira[Lixeira<br/>- id<br/>- localizacao<br/>- nivel_preenchimento<br/>- status<br/>- ultima_coleta<br/>- tipo<br/>- coordenadas]
            ModelSensor[Sensor<br/>- id<br/>- lixeira_id<br/>- tipo<br/>- bateria<br/>- ultimo_ping]
            ModelColeta[Coleta<br/>- id<br/>- lixeira_id<br/>- data_hora<br/>- volume_estimado]
        end
        
        SQLite[(SQLite<br/>tronik.db)]
        
        subgraph "Inicialização"
            Inicializar[inicializar.py<br/>- criar_banco<br/>- inserir_dados_iniciais<br/>- resetar_banco]
            MockData[sensores_mock.json<br/>Dados Mock<br/>- Lixeiras<br/>- Histórico Coletas]
        end
    end
    
    subgraph "Deploy e Configuração"
        Gunicorn[gunicorn.conf.py<br/>Configuração WSGI]
        Nginx[nginx/tronik.conf<br/>Configuração Nginx]
        Service[dashboard-tronik.service<br/>Systemd Service]
    end
    
    Browser --> Index
    Browser --> Relatorios
    Browser --> Config
    Browser --> Sobre
    Browser --> Base
    
    Index --> DashboardJS
    Relatorios --> DashboardJS
    Config --> DashboardJS
    Sobre --> DashboardJS
    
    Index --> EstiloCSS
    Relatorios --> RelatoriosCSS
    Config --> ConfigCSS
    Sobre --> SobreCSS
    Base --> EstiloCSS
    
    DashboardJS --> APIJS
    APIJS --> APIBP
    
    App --> APIBP
    App --> PaginasBP
    
    APIBP --> GET1
    APIBP --> GET2
    APIBP --> GET3
    APIBP --> GET4
    APIBP --> GET5
    APIBP --> GET6
    APIBP --> POST1
    APIBP --> PUT1
    APIBP --> DELETE1
    
    PaginasBP --> R1
    PaginasBP --> R2
    PaginasBP --> R3
    PaginasBP --> R4
    
    GET1 --> ModelLixeira
    GET2 --> ModelLixeira
    GET3 --> ModelLixeira
    GET3 --> ModelColeta
    GET4 --> ModelColeta
    GET6 --> ModelColeta
    POST1 --> ModelLixeira
    PUT1 --> ModelLixeira
    DELETE1 --> ModelLixeira
    
    ModelLixeira --> SQLite
    ModelSensor --> SQLite
    ModelColeta --> SQLite
    
    ModelLixeira -.->|1:N| ModelSensor
    ModelLixeira -.->|1:N| ModelColeta
    
    Inicializar --> SQLite
    MockData --> Inicializar
    
    App --> Inicializar
    
    Gunicorn --> App
    Nginx --> Gunicorn
    Service --> Gunicorn
    
    style App fill:#4a90e2,stroke:#2c5aa0,stroke-width:3px,color:#fff
    style SQLite fill:#3d9970,stroke:#2d6e4e,stroke-width:3px,color:#fff
    style Browser fill:#f39c12,stroke:#d68910,stroke-width:2px,color:#fff
    style DashboardJS fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
    style APIJS fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff
```

## Diagrama de Fluxo de Dados

```mermaid
sequenceDiagram
    participant U as Usuário
    participant B as Browser
    participant JS as dashboard.js
    participant API as api.js
    participant F as Flask API
    participant DB as SQLite
    
    U->>B: Acessa Dashboard (/)
    B->>F: GET / (render_template)
    F-->>B: index.html
    B->>JS: DOMContentLoaded
    JS->>API: obterTodasLixeiras()
    API->>F: GET /api/lixeiras
    F->>DB: SELECT * FROM lixeiras
    DB-->>F: Lista de lixeiras
    F-->>API: JSON Response
    API-->>JS: Array de lixeiras
    JS->>JS: renderizarGridLixeiras()
    JS->>B: Atualiza DOM
    
    JS->>API: obterEstatisticas()
    API->>F: GET /api/estatisticas
    F->>DB: Queries agregadas
    DB-->>F: Estatísticas
    F-->>API: JSON Response
    API-->>JS: Estatísticas
    JS->>B: Atualiza estatísticas
    
    loop Polling (30s)
        JS->>API: obterTodasLixeiras()
        API->>F: GET /api/lixeiras
        F->>DB: SELECT * FROM lixeiras
        DB-->>F: Dados atualizados
        F-->>API: JSON Response
        API-->>JS: Dados atualizados
        JS->>B: Atualiza interface
    end
    
    U->>B: Cria nova lixeira
    B->>JS: criarNovaLixeira()
    JS->>API: criarLixeira(dados)
    API->>F: POST /api/lixeira
    F->>F: validar_lixeira()
    F->>DB: INSERT INTO lixeiras
    DB-->>F: Lixeira criada
    F-->>API: JSON Response (201)
    API-->>JS: Sucesso
    JS->>B: Atualiza interface
    B-->>U: Confirmação visual
```

## Diagrama de Estrutura de Diretórios

```mermaid
graph TD
    Root[Dashboard-TRONIK/]
    
    Root --> App[app.py]
    Root --> Req[requirements.txt]
    Root --> DB[tronik.db]
    
    Root --> Banco[banco_dados/]
    Banco --> Modelos[modelos.py<br/>Lixeira, Sensor, Coleta]
    Banco --> Init[inicializar.py<br/>Setup DB]
    Banco --> Dados[dados/]
    Dados --> Mock[sensores_mock.json]
    
    Root --> Rotas[rotas/]
    Rotas --> API[api.py<br/>Endpoints REST]
    Rotas --> Paginas[paginas.py<br/>Rotas HTML]
    
    Root --> Templates[templates/]
    Templates --> Base[base.html]
    Templates --> Index[index.html]
    Templates --> Rel[relatorios.html]
    Templates --> Config[configuracoes.html]
    Templates --> Sobre[sobre.html]
    
    Root --> Estatico[estatico/]
    Estatico --> CSS[css/]
    CSS --> Estilo[estilo.css]
    CSS --> RelCSS[relatorios.css]
    CSS --> ConfigCSS[configuracoes.css]
    CSS --> SobreCSS[sobre.css]
    
    Estatico --> JS[js/]
    JS --> DashboardJS[dashboard.js]
    JS --> APIJS[api.js]
    
    Estatico --> Imagens[imagens/]
    
    Root --> Docs[docs/]
    Docs --> MVP[MVP.md]
    Docs --> Planejamento[Planejamento.md]
    Docs --> Espec[Especificacao_Tecnica.md]
    
    Root --> Deploy[deploy/]
    Deploy --> Gunicorn[gunicorn.conf.py]
    Deploy --> Nginx[nginx/]
    Deploy --> Service[dashboard-tronik.service]
    
    Root --> Teste[teste/]
    Teste --> Mockups[Mockups HTML]
```

## Diagrama de Modelo de Dados

```mermaid
erDiagram
    LIXEIRA ||--o{ SENSOR : "tem"
    LIXEIRA ||--o{ COLETA : "tem"
    
    LIXEIRA {
        int id PK
        string localizacao
        float nivel_preenchimento
        string status
        datetime ultima_coleta
        string tipo
        string coordenadas
    }
    
    SENSOR {
        int id PK
        int lixeira_id FK
        string tipo
        float bateria
        datetime ultimo_ping
    }
    
    COLETA {
        int id PK
        int lixeira_id FK
        datetime data_hora
        float volume_estimado
    }
```

## Diagrama de Componentes Frontend

```mermaid
graph LR
    subgraph "Página: Dashboard (index.html)"
        D1[Header<br/>Navegação]
        D2[Filtros<br/>Status e Busca]
        D3[Estatísticas<br/>KPIs]
        D4[Grid Lixeiras<br/>Cards Dinâmicos]
        D5[Histórico<br/>Tabela]
        D6[Botões<br/>Atualizar, Exportar]
    end
    
    subgraph "Página: Relatórios (relatorios.html)"
        R1[Filtros Data<br/>7/30/90 dias]
        R2[KPIs<br/>Total, Volume]
        R3[Gráfico Evolução<br/>Chart.js]
        R4[Gráfico Distribuição<br/>Chart.js]
        R5[Gráfico Horários<br/>Chart.js]
        R6[Tabela Detalhes<br/>Coletas]
    end
    
    subgraph "Página: Configurações (configuracoes.html)"
        C1[Formulário<br/>Criar Lixeira]
        C2[Lista Lixeiras<br/>Existentes]
        C3[Botões<br/>Criar, Deletar]
    end
    
    subgraph "Página: Sobre (sobre.html)"
        S1[Informações<br/>Projeto]
        S2[Informações<br/>TRONIK]
        S3[Contribuidores]
        S4[Contato]
    end
    
    subgraph "JavaScript: dashboard.js"
        JS1[carregarDados<br/>Carrega lixeiras e stats]
        JS2[renderizarGridLixeiras<br/>Cria cards]
        JS3[aplicarFiltros<br/>Filtra por status/busca]
        JS4[atualizarEstatisticas<br/>Atualiza KPIs]
        JS5[exportarCSV<br/>Exporta dados]
        JS6[Polling<br/>Atualização automática]
    end
    
    subgraph "JavaScript: api.js"
        API1[obterTodasLixeiras<br/>GET /api/lixeiras]
        API2[obterEstatisticas<br/>GET /api/estatisticas]
        API3[obterRelatorios<br/>GET /api/relatorios]
        API4[criarLixeira<br/>POST /api/lixeira]
        API5[deletarLixeira<br/>DELETE /api/lixeira]
    end
    
    D4 --> JS2
    D3 --> JS4
    D6 --> JS5
    JS1 --> API1
    JS1 --> API2
    JS4 --> API2
    JS2 --> API1
    
    R3 --> API3
    R4 --> API3
    R5 --> API3
    
    C1 --> API4
    C2 --> API1
    C3 --> API5
```

## Diagrama de Endpoints da API

```mermaid
graph TB
    subgraph "API REST - /api"
        subgraph "GET Endpoints"
            G1[GET /lixeiras<br/>Lista todas as lixeiras]
            G2[GET /lixeira/id<br/>Obtém lixeira específica]
            G3[GET /estatisticas<br/>Estatísticas agregadas]
            G4[GET /historico<br/>Histórico de coletas]
            G5[GET /configuracoes<br/>Configurações sistema]
            G6[GET /relatorios<br/>Dados para relatórios<br/>?data_inicio&data_fim]
        end
        
        subgraph "POST Endpoints"
            P1[POST /lixeira<br/>Cria nova lixeira<br/>Body: JSON]
        end
        
        subgraph "PUT Endpoints"
            U1[PUT /lixeira/id<br/>Atualiza lixeira<br/>Body: JSON]
        end
        
        subgraph "DELETE Endpoints"
            D1[DELETE /lixeira/id<br/>Deleta lixeira]
        end
    end
    
    subgraph "Rotas de Páginas"
        R1[GET /<br/>Dashboard]
        R2[GET /relatorios<br/>Relatórios]
        R3[GET /configuracoes<br/>Configurações]
        R4[GET /sobre<br/>Sobre]
    end
    
    G1 --> ModelLixeira[Modelo: Lixeira]
    G2 --> ModelLixeira
    G3 --> ModelLixeira
    G3 --> ModelColeta[Modelo: Coleta]
    G4 --> ModelColeta
    G6 --> ModelColeta
    P1 --> ModelLixeira
    U1 --> ModelLixeira
    D1 --> ModelLixeira
```

## Stack Tecnológico

```mermaid
graph TB
    subgraph "Frontend"
        F1[HTML5<br/>Templates Jinja2]
        F2[CSS3<br/>Responsive Design]
        F3[JavaScript ES6+<br/>Vanilla JS]
        F4[Chart.js<br/>Gráficos]
    end
    
    subgraph "Backend"
        B1[Python 3.x]
        B2[Flask<br/>Web Framework]
        B3[Flask-CORS<br/>Cross-Origin]
        B4[SQLAlchemy<br/>ORM]
    end
    
    subgraph "Banco de Dados"
        DB1[SQLite<br/>tronik.db]
    end
    
    subgraph "Deploy"
        D1[Gunicorn<br/>WSGI Server]
        D2[Nginx<br/>Reverse Proxy]
        D3[Systemd<br/>Service]
    end
    
    F1 --> B2
    F2 --> B2
    F3 --> B2
    F4 --> F3
    B2 --> B4
    B4 --> DB1
    B2 --> D1
    D1 --> D2
    D2 --> D3
```

