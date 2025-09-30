# Planejamento do Desenvolvimento

## 1. Backlog do Produto (Priorizado com cliente)

1. Visualizar grid de lixeiras com nível e status
2. Exibir alertas quando nível >80%
3. API REST para listar lixeiras (mock)
4. Relatório básico de coletas/níveis por período
5. Atualização periódica dos dados (polling)
6. CRUD básico de lixeiras (criar/editar/remover)
7. Interface responsiva (desktop e mobile básico)
8. Histórico de níveis (visual simples)
9. Exportar CSV dos dados listados
10. Autenticação simples (post-MVP)

## 2. Roadmap (sprints sugeridas)
- Sprint 1 (MVP funcional): itens 1–5
- Sprint 2 (robustez): itens 6–9
- Sprint 3 (segurança/escala): item 10 e melhorias

## 3. Histórias de Usuário e Critérios de Aceitação

### US-01: Visualizar grid de lixeiras
Como Supervisor, quero ver um grid com lixeiras e seus níveis para priorizar coletas.
- Critérios de Aceitação:
  - Exibir nome/ID da lixeira, nível (%), status (OK/Alerta).
  - Ordenar por nível decrescente.
  - Exibir pelo menos 10 itens com dados mock.

### US-02: Exibir alertas >80%
Como Supervisor, quero ver destaque visual para lixeiras acima de 80% para agir rapidamente.
- Critérios de Aceitação:
  - Cards >80% com cor/ícone de alerta.
  - Filtro para mostrar apenas em alerta.

### US-03: Listar lixeiras via API
Como Frontend, quero consumir um endpoint para obter as lixeiras para manter o dashboard atualizado.
- Critérios de Aceitação:
  - Endpoint GET `/api/lixeiras` retorna lista mock com nível e status.
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

### US-06: CRUD de lixeiras
Como Administrador, quero criar/editar/remover lixeiras para manter o cadastro atualizado.
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
  - Filtro por lixeira.

### US-09: Exportar CSV
Como Gestor, quero exportar os dados exibidos para análise externa.
- Critérios de Aceitação:
  - Botão Exportar que gera CSV do dataset atual.

### US-10: Autenticação (post-MVP)
Como Administrador, quero login básico para restringir ações de CRUD.
- Critérios de Aceitação:
  - Tela de login simples.
  - Sessão mínima.

## 4. Dependências e Riscos
- Dependência: disponibilidade de dados reais (usa-se mock inicialmente).
- Risco: prazos curtos — priorizar itens 1–5 para o MVP.
- Mitigação: arquitetura simples e iterativa; validações mínimas.

