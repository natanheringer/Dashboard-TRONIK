# MVP - Dashboard-TRONIK

## 1. Descrição do MVP

### 1.1 Problema (≤ 250 caracteres)
Municípios e equipes de limpeza carecem de visibilidade sobre o nível de preenchimento de lixeiras públicas, causando coletas ineficientes, transbordo e custos operacionais elevados.

### 1.2 Solução (≤ 250 caracteres)
Dashboard web que monitora lixeiras inteligentes via sensores ultrassônicos, exibindo níveis, alertas (>80%) e status em tempo quase real, permitindo priorização de rotas e coletas mais eficientes.

### 1.3 Personas
- Gestor de Limpeza Urbana: define políticas, acompanha indicadores e custos.
- Supervisor Operacional: planeja rotas diárias e prioriza coletas urgentes.
- Agente de Coleta: executa as rotas e reporta ocorrências em campo.
- Analista de Dados: avalia históricos e sugere otimizações.

### 1.4 Jornadas do usuário
- Gestor: acessa o dashboard → filtra por região → verifica alertas → exporta relatório semanal.
- Supervisor: abre o mapa/grid → identifica lixeiras >80% → reorganiza rota do dia.
- Agente: consulta lista priorizada → realiza coleta → marca lixeira como vazia (futuro).
- Analista: consulta histórico agregado → identifica padrões → propõe ajustes de frequência.

## 2. Escopo do MVP (versão inicial)
- Grid de lixeiras com nível e status.
- API REST para leitura de dados (mock/simulada).
- Alerta visual para nível >80%.
- Relatório básico (listagem) por período.

Itens fora do escopo inicial (próximas iterações): autenticação, mapas em tempo real, otimização automática de rotas, app mobile.

## 3. Critérios de sucesso
- Usuário visualiza ao menos 10 lixeiras com nível e estado.
- Alertas são exibidos quando nível >80%.
- Dados podem ser atualizados via mock a cada X segundos.
- Página responde adequadamente em desktop e mobile básico.

## 4. Métricas (iniciais)
- % de lixeiras com coleta preventiva (antes do transbordo).
- Tempo médio entre alertas e coleta efetiva (simulado).
- Redução de ocorrências de transbordo (simulado).

## 5. Alinhamento com repositório
- Frontend: `templates/`, `estatico/` com `dashboard.js`.
- Backend: Flask em `app.py` e `rotas/api.py` (endpoints CRUD/mocks).
- Dados mock: `dados/sensores_mock.json`.

