# Planejamento do Desenvolvimento

**Versão:** 2.1  
**Data de Atualização:** 24 de Novembro de 2025  
**Status:** MVP Completo + Funcionalidades Comerciais Implementadas

## 1. Backlog do Produto (Status de Implementação)

### Sprint 1 - MVP Funcional (✅ CONCLUÍDO)
1. ✅ Visualizar grid de coletores com nível e status
2. ✅ Exibir alertas quando nível >80% (visual e por email)
3. ✅ API REST completa para CRUD de coletores e sensores
4. ✅ Relatórios financeiros e operacionais completos
5. ✅ Atualização em tempo real via WebSocket
6. ✅ CRUD completo de coletores e sensores
7. ✅ Interface responsiva (desktop, tablet e mobile)
8. ✅ Histórico de coletas com filtros e ordenação
9. ✅ Exportar CSV e PDF dos dados
10. ✅ Sistema de autenticação e autorização completo

### Sprint 2 - Robustez e Segurança (✅ CONCLUÍDO)
11. ✅ Sistema de notificações automáticas por email
12. ✅ Mapa interativo com rotas otimizadas
13. ✅ Geocodificação automática de endereços
14. ✅ Sistema de roteamento modular robusto
15. ✅ Testes automatizados (120+ testes)
16. ✅ Docker e containerização
17. ✅ Segurança robusta (rate limiting, headers, validação)

### Sprint 3 - Funcionalidades Comerciais (✅ CONCLUÍDO)
18. ✅ Dashboard Comercial com KPIs financeiros
19. ✅ Sistema CRM completo com funil de vendas
20. ✅ Gestão de Contratos recorrentes
21. ✅ Análise por parceiro com gráficos
22. ✅ Layout personalizável (drag-and-drop)

### Sprint 4 - Melhorias e Otimizações (✅ CONCLUÍDO)
23. ✅ Otimização de queries (eager loading)
24. ✅ Sistema de cache para rotas
25. ✅ Aprendizado adaptativo de rotas
26. ✅ Migração completa: lixeira → coletor
27. ✅ WebSocket para atualizações em tempo real

## 2. Roadmap (Status Atual)

### ✅ Sprint 1 - MVP Funcional (CONCLUÍDO)
- Grid de coletores, API REST, Alertas, Relatórios básicos, Polling

### ✅ Sprint 2 - Robustez e Segurança (CONCLUÍDO)
- CRUD completo, Autenticação, Notificações, Mapa, Geocodificação, Testes

### ✅ Sprint 3 - Funcionalidades Comerciais (CONCLUÍDO)
- Dashboard Comercial, CRM, Contratos, Análises financeiras

### ✅ Sprint 4 - Otimizações (CONCLUÍDO)
- Sistema de roteamento modular, Otimizações de performance, WebSocket

### 🚀 Próximas Sprints (Planejadas)
- **Sprint 5**: Modo Apresentação, Otimizador de Rotas Semanal, Calculadora de Precificação
- **Sprint 6**: Integração WhatsApp, Templates de Propostas, App Mobile/PWA
- **Sprint 7**: Landing Page Pública, Relatório de Impacto, Machine Learning

## 3. Histórias de Usuário e Critérios de Aceitação

### US-01: Visualizar grid de coletores
Como Supervisor, quero ver um grid com coletores e seus níveis para priorizar coletas.
- Critérios de Aceitação:
  - Exibir nome/ID da coletor, nível (%), status (OK/Alerta).
  - Ordenar por nível decrescente.
  - Exibir pelo menos 10 itens com dados mock.

### US-02: Exibir alertas >80%
Como Supervisor, quero ver destaque visual para coletores acima de 80% para agir rapidamente.
- Critérios de Aceitação:
  - Cards >80% com cor/ícone de alerta.
  - Filtro para mostrar apenas em alerta.

### US-03: Listar coletores via API
Como Frontend, quero consumir um endpoint para obter as coletores para manter o dashboard atualizado.
- Critérios de Aceitação:
  - Endpoint GET `/api/coletores` retorna lista mock com nível e status.
  - Resposta JSON válida, HTTP 200.

### US-04: Relatório básico por período
Como Gestor, quero listar níveis/ocorrências por período para análise semanal.
- Critérios de Aceitação:
  - Página/rota de relatórios com filtros simples (data início/fim).
  - Tabela com exportação CSV.

### US-05: Atualização periódica (polling)
Como Supervisor, quero que o dashboard atualize automaticamente a cada X segundos para refletir mudanças.
- Critérios de Aceitação:
  - Atualização sem recarregar a página.
  - Intervalo configurável (ex.: 10–30s).

### US-06: CRUD de coletores
Como Administrador, quero criar/editar/remover coletores para manter o cadastro atualizado.
- Critérios de Aceitação:
  - Endpoints POST/PUT/DELETE com validação mínima.
  - Feedback de sucesso/erro no frontend.

### US-07: Responsividade
Como Usuário, quero usar o dashboard no celular com layout adaptado para leitura.
- Critérios de Aceitação:
  - Breakpoints para grid.
  - Navegação e botões clicáveis em telas pequenas.

### US-08: Histórico simples
Como Analista, quero visualizar histórico de níveis para identificar tendências.
- Critérios de Aceitação:
  - Tabela/linha do tempo simples.
  - Filtro por coletor.

### US-09: Exportar CSV
Como Gestor, quero exportar os dados exibidos para análise externa.
- Critérios de Aceitação:
  - Botão Exportar que gera CSV do dataset atual.

### US-10: Autenticação ✅ IMPLEMENTADO
Como Administrador, quero login completo para restringir ações de CRUD.
- Critérios de Aceitação:
  - ✅ Tela de login e registro funcionais
  - ✅ Sessões seguras com Flask-Login
  - ✅ Permissões de admin e usuário
  - ✅ Proteção de rotas com decorators

### US-11: Mapa Interativo ✅ IMPLEMENTADO
Como Supervisor, quero visualizar coletores em mapa geográfico com rotas otimizadas.
- Critérios de Aceitação:
  - ✅ Mapa interativo com Leaflet.js
  - ✅ Marcadores coloridos por status
  - ✅ Cálculo de rotas otimizadas
  - ✅ Filtros por distância, status e parceiro

### US-12: Dashboard Comercial ✅ IMPLEMENTADO
Como Gestor Comercial, quero acompanhar KPIs financeiros e metas mensais.
- Critérios de Aceitação:
  - ✅ KPIs financeiros (faturamento, meta, percentual)
  - ✅ Análise por parceiro com gráficos
  - ✅ Comparação com mês anterior
  - ✅ Layout personalizável

### US-13: Sistema CRM ✅ IMPLEMENTADO
Como Vendedor, quero gerenciar pipeline de vendas e interações com clientes.
- Critérios de Aceitação:
  - ✅ Funil de vendas (Kanban board)
  - ✅ Registro de interações
  - ✅ Gestão de tarefas
  - ✅ Estatísticas do CRM

## 4. Dependências e Riscos
- Dependência: disponibilidade de dados reais (usa-se mock inicialmente).
- Risco: prazos curtos — priorizar itens 1–5 para o MVP.
- Mitigação: arquitetura simples e iterativa; validações mínimas.

