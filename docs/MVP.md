# MVP - Dashboard-TRONIK

**Versão:** 2.1  
**Data de Atualização:** 24 de Novembro de 2025  
**Cliente:** Tronik Recicla

## 1. Descrição do MVP

### 1.1 Problema (≤ 250 caracteres)
A Tronik Recicla enfrenta desafios no controle da logística de coleta de resíduos eletrônicos nos seus coletores, causando coletas ineficientes, desperdício de recursos e custos operacionais elevados.

### 1.2 Solução (≤ 250 caracteres)
Dashboard web completo que monitora coletores inteligentes de resíduos eletrônicos via sensores ultrassônicos, exibindo níveis, alertas (>80%) e status em tempo real, permitindo otimização de rotas e controle eficiente da logística de coleta.

### 1.3 Personas
- **Gestor Comercial**: acompanha KPIs financeiros, metas mensais e análises de parceiros.
- **Supervisor Operacional**: planeja rotas diárias, prioriza coletas urgentes e otimiza operações.
- **Equipe de Coleta**: executa as rotas otimizadas e reporta ocorrências em campo.
- **Analista de Dados**: avalia históricos, identifica padrões e sugere otimizações.

### 1.4 Jornadas do usuário
- **Gestor Comercial**: acessa dashboard comercial → verifica KPIs e metas → analisa por parceiro → exporta relatórios.
- **Supervisor**: abre o mapa/grid → identifica coletores >80% → calcula rota otimizada → reorganiza rota do dia.
- **Equipe de Coleta**: consulta lista priorizada → segue rota otimizada → realiza coleta → registra no sistema.
- **Analista**: consulta histórico agregado → identifica padrões → propõe ajustes de frequência e otimizações.

## 2. Escopo do MVP (versão inicial - IMPLEMENTADO ✅)

### Funcionalidades Core (Implementadas)
- ✅ Grid de coletores com nível e status
- ✅ API REST completa para CRUD de coletores e sensores
- ✅ Alerta visual e por email para nível >80% e bateria <20%
- ✅ Relatórios financeiros e operacionais completos
- ✅ Mapa interativo com rotas otimizadas
- ✅ Geocodificação automática de endereços
- ✅ Sistema de autenticação e autorização
- ✅ Notificações automáticas por email
- ✅ WebSocket para atualizações em tempo real

### Funcionalidades Comerciais (Implementadas)
- ✅ Dashboard Comercial com KPIs financeiros
- ✅ Sistema CRM completo com funil de vendas
- ✅ Gestão de Contratos recorrentes
- ✅ Análise por parceiro com gráficos

### Itens Implementados Além do MVP
- ✅ Sistema de roteamento modular robusto (7 módulos)
- ✅ Testes automatizados (120+ testes)
- ✅ Docker e containerização
- ✅ Sistema de notificações automáticas
- ✅ Exportação PDF de relatórios

## 3. Critérios de sucesso (ATENDIDOS ✅)

- ✅ Usuário visualiza coletores com nível e estado em tempo real
- ✅ Alertas são exibidos e enviados por email quando nível >80% ou bateria <20%
- ✅ Dados são atualizados via WebSocket em tempo real
- ✅ Página responde adequadamente em desktop, tablet e mobile
- ✅ Sistema completo de autenticação e autorização
- ✅ Rotas otimizadas calculadas automaticamente
- ✅ Relatórios financeiros e operacionais completos

## 4. Métricas (Atuais)

- ✅ **120+ testes automatizados** passando (0 falhas, 0 warnings)
- ✅ **55+ endpoints REST** documentados e funcionais
- ✅ **Score geral: 94/100** (pronto para deploy)
- ✅ **Cobertura de funcionalidades**: 98% das funcionalidades core implementadas
- ✅ **Performance**: Queries otimizadas com eager loading (46+ queries)

## 5. Alinhamento com repositório

- **Frontend**: `templates/` (12 templates), `estatico/js/` (módulos JavaScript), `estatico/css/` (estilos)
- **Backend**: Flask em `app.py`, `rotas/api/` (API REST modularizada com 55+ endpoints), `rotas/auth.py`, `rotas/paginas.py`
- **Banco de Dados**: `banco_dados/modelos.py` (15 modelos), `banco_dados/services/` (camada de serviços)
- **Testes**: `tests/` (120+ testes automatizados)
- **Deploy**: `Dockerfile`, `docker-compose.yml`, `deploy/` (configurações)

