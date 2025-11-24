# Especificação Técnica

## 3.1 Stack de desenvolvimento
- Backend: Python 3.x, Flask, Flask-CORS, SQLite (SQLAlchemy opcional)
- Frontend: HTML5, CSS3, JavaScript (vanilla)
- Comunicação: REST (JSON), polling simples
- Ferramentas: Git, VS Code/Cursor, Windows 10+, Python venv

## 3.2 Wireframe de baixa fidelidade (descrição)
- Página principal (Dashboard):
  - Cabeçalho com título e filtros (status, região, busca)
  - Grid de cards das coletores: nome/ID, nível (%), status (cor)
  - Barra lateral/rodapé com estatísticas agregadas (média, em alerta)
  - Botões: Atualizar, Exportar CSV (futuro)
- Relatórios:
  - Filtros de período (data início/fim)
  - Tabela de registros/histórico

Sugestão de ferramentas para mockup: Figma ou Lucidchart.

## 3.3 Arquitetura e integrações

### Visão Geral
`Flask (app.py)` expõe rotas de páginas e API. O frontend (templates + estáticos) consome a API via `estatico/js/api.js` e renderiza via `dashboard.js`. Dados vêm de `dados/sensores_mock.json` no MVP.

### Módulos
- `app.py`: inicializa Flask, registra blueprints (`rotas/paginas.py`, `rotas/api.py`), configura CORS.
- `rotas/api.py`: endpoints `/api/coletores` e CRUD (mock inicialmente).
- `rotas/paginas.py`: páginas `index`, `relatorios` etc.
- `banco_dados/`: modelos (futuro com SQLAlchemy) e inicialização.
- `templates/` e `estatico/`: UI, estilos e scripts.

### Endpoints (propostos)
- GET `/api/coletores`: lista coletores com nível e status
- GET `/api/coletor/<id>`: detalha uma coletor
- POST `/api/coletor`: cria
- PUT `/api/coletor/<id>`: atualiza
- DELETE `/api/coletor/<id>`: remove
- GET `/api/relatorios`: dados agregados (mock)

### Modelo de Dados (proposto)
- Coletor: id, nome, localizacao, nivel_percentual, status, atualizado_em
- Sensor: id, coletor_id, tipo (ultrassonico), bateria, ultimo_ping
- Coleta: id, coletor_id, data_hora, volume_estimado

### Decisões Técnicas
- MVP com mock JSON para reduzir dependências.
- Polling a cada 10–30s via `setInterval` no `dashboard.js`.
- Sem autenticação no MVP; adicionar em fase posterior.

### Padrões e Qualidade
- Python PEP8, JS ES6+, CSS BEM.
- Estrutura de pastas já definida no README.

### Implantação (futuro)
- Container Docker simples ou execução local com `python app.py`.
- Variáveis de ambiente para configurações.

