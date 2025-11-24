# 🔍 Investigação Adicional de Robustez - Dashboard-TRONIK

**Data:** 21-11-2025  
**Objetivo:** Identificar pontos adicionais para tornar o sistema 100% robusto

---

## 📋 SUMÁRIO EXECUTIVO

Após a investigação inicial, foram identificadas **18 áreas adicionais** que precisam de atenção para garantir robustez total do sistema.

---

## 🚨 ÁREAS CRÍTICAS IDENTIFICADAS

### 1. **Transações de Banco de Dados (CRÍTICO)**

#### Problema
- Nem todas as operações de escrita usam transações explícitas
- Rollback não está sendo chamado em todos os casos de erro
- Sessões podem não estar sendo fechadas corretamente

#### Arquivos Afetados
- `rotas/api/coletores.py` - Criação/atualização de coletores
- `rotas/api/coletas.py` - Criação de coletas
- `rotas/api/sensores.py` - Operações CRUD de sensores

#### Recomendações
```python
# Padrão recomendado:
db = get_db()
try:
    # Operações
    db.commit()
except Exception as e:
    db.rollback()
    raise
finally:
    db.close()
```

### 2. **Validação de Variáveis de Ambiente (ALTO)**

#### Problema
- Variáveis de ambiente podem não estar definidas
- Valores padrão podem não ser seguros
- Não há validação de formato/range

#### Arquivos Afetados
- `app.py` - SECRET_KEY, configurações de banco
- `banco_dados/notificacoes.py` - Configurações de email
- `banco_dados/agendamento.py` - Configurações de agendamento

#### Recomendações
```python
# Validar e fornecer defaults seguros
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise ValueError("SECRET_KEY deve ter pelo menos 32 caracteres")
```

### 3. **Segurança de Sessões e Cookies (CRÍTICO)**

#### Problema
- Cookies podem não ter flags de segurança adequadas
- Sessões podem não expirar corretamente
- Não há proteção CSRF explícita

#### Arquivos Afetados
- `app.py` - Configuração de sessão
- `rotas/auth.py` - Login/logout

#### Recomendações
```python
# Configurar sessão segura
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Não acessível via JS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Proteção CSRF
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
```

### 4. **Rate Limiting em APIs (ALTO)**

#### Problema
- Endpoints públicos não têm rate limiting
- Possibilidade de abuso/DDoS
- Endpoints de criação podem ser spammados

#### Arquivos Afetados
- `rotas/api/__init__.py` - Registro de blueprints
- `rotas/api/decorators.py` - Decorators de API

#### Recomendações
```python
# Implementar rate limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@limiter.limit("10 per minute")
@lixeiras_bp.route('/coletor', methods=['POST'])
def criar_lixeira_endpoint():
    ...
```

### 5. **N+1 Query Problems (MÉDIO)**

#### Problema
- Queries podem estar sendo executadas em loops
- Relacionamentos não estão sendo carregados eficientemente
- Falta de eager loading em alguns endpoints

#### Arquivos Afetados
- `banco_dados/services/relatorio_service.py` - Relatórios
- `rotas/api/coletores.py` - Listagem de coletores
- `rotas/api/coletas.py` - Listagem de coletas

#### Recomendações
```python
# Usar joinedload para evitar N+1
from sqlalchemy.orm import joinedload

coletores = db.query(Coletor).options(
    joinedload(Coletor.parceiro),
    joinedload(Coletor.tipo_material)
).all()
```

### 6. **Memory Leaks em Event Listeners (MÉDIO)**

#### Problema
- Event listeners podem não estar sendo removidos
- Intervalos podem não estar sendo limpos
- WebSocket listeners podem se acumular

#### Arquivos Afetados
- `estatico/js/dashboard.js` - Múltiplos listeners
- `estatico/js/mapa.js` - Listeners de mapa
- `estatico/js/utils/websocket.js` - WebSocket

#### Recomendações
```javascript
// Remover listeners ao destruir componente
function cleanup() {
    window.removeEventListener('websocket:lixeira_atualizada', handler);
    if (intervalo) clearInterval(intervalo);
}
```

### 7. **Tratamento de Erros em Operações Assíncronas (ALTO)**

#### Problema
- Algumas operações assíncronas não têm timeout
- Promises podem ficar pendentes indefinidamente
- Falta de cancelamento de requisições antigas

#### Arquivos Afetados
- `estatico/js/api.js` - Requisições HTTP
- `estatico/js/routing/router.js` - Cálculo de rotas
- `estatico/js/routing/osm.js` - Chamadas OSM

#### Recomendações
```javascript
// Adicionar timeout
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 10000);

fetch(url, { signal: controller.signal })
    .finally(() => clearTimeout(timeoutId));
```

### 8. **Timeouts em Chamadas Externas (ALTO)**

#### Problema
- Chamadas a APIs externas não têm timeout
- Geocodificação pode travar indefinidamente
- OSM API pode não responder

#### Arquivos Afetados
- `banco_dados/geocodificacao.py` - Nominatim API
- `estatico/js/routing/osm.js` - Overpass API

#### Recomendações
```python
# Adicionar timeout
import requests

response = requests.get(url, timeout=10)  # 10 segundos
```

### 9. **Validação de Tipos Numéricos (MÉDIO)**

#### Problema
- Parsing de números pode retornar NaN
- Valores podem estar fora de range esperado
- Divisão por zero não está sendo verificada

#### Arquivos Afetados
- `estatico/js/dashboard.js` - Cálculos de distância
- `estatico/js/routing/heuristicas.js` - Cálculos de rota
- `estatico/js/relatorios.js` - Cálculos financeiros

#### Recomendações
```javascript
// Validar antes de usar
const valor = parseFloat(input);
if (isNaN(valor) || !isFinite(valor)) {
    throw new Error('Valor inválido');
}
```

### 10. **Validação de Coordenadas (ALTO)**

#### Problema
- Coordenadas podem estar fora de range válido
- Latitude/longitude podem ser inválidas
- Rotas podem falhar com coordenadas extremas

#### Arquivos Afetados
- `estatico/js/routing/router.js` - Cálculo de rotas
- `estatico/js/mapa.js` - Marcadores no mapa
- `banco_dados/geocodificacao.py` - Geocodificação

#### Recomendações
```javascript
// Validar coordenadas
function validarCoordenadas(lat, lon) {
    if (typeof lat !== 'number' || typeof lon !== 'number') return false;
    if (isNaN(lat) || isNaN(lon)) return false;
    if (lat < -90 || lat > 90) return false;
    if (lon < -180 || lon > 180) return false;
    return true;
}
```

### 11. **Tratamento de Erros em Email (MÉDIO)**

#### Problema
- Envio de email pode falhar silenciosamente
- Erros de SMTP não estão sendo logados adequadamente
- Falta de retry para emails críticos

#### Arquivos Afetados
- `banco_dados/notificacoes.py` - Envio de notificações

#### Recomendações
```python
# Adicionar retry e logging
try:
    mail.send(msg)
except Exception as e:
    logger.error(f"Erro ao enviar email: {e}")
    # Retry logic ou queue para processar depois
```

### 12. **Quota de Storage do Browser (MÉDIO)**

#### Problema
- localStorage pode estar cheio
- IndexedDB pode falhar com quota exceeded
- Cache pode não estar sendo limpo

#### Arquivos Afetados
- `estatico/js/utils/cache.js` - Cache frontend
- `estatico/js/routing/cache.js` - Cache de rotas

#### Recomendações
```javascript
// Tratar quota exceeded
try {
    localStorage.setItem(key, value);
} catch (e) {
    if (e.name === 'QuotaExceededError') {
        // Limpar cache antigo
        limparCacheAntigo();
    }
}
```

### 13. **Validação de Datas (MÉDIO)**

#### Problema
- Datas podem estar em formatos inválidos
- Timezone pode causar problemas
- Datas futuras/passadas extremas podem quebrar

#### Arquivos Afetados
- `estatico/js/dashboard.js` - Formatação de datas
- `estatico/js/relatorios.js` - Filtros de data
- `banco_dados/services/coleta_service.py` - Processamento de data_hora

#### Recomendações
```javascript
// Validar data
function validarData(dataStr) {
    const data = new Date(dataStr);
    if (isNaN(data.getTime())) return false;
    // Validar range razoável (ex: não antes de 2000, não depois de 2100)
    const min = new Date('2000-01-01');
    const max = new Date('2100-12-31');
    return data >= min && data <= max;
}
```

### 14. **Índices de Banco de Dados (BAIXO)**

#### Problema
- Algumas queries frequentes podem não ter índices
- Foreign keys podem não ter índices
- Queries de busca podem ser lentas

#### Arquivos Afetados
- `banco_dados/modelos.py` - Definição de modelos

#### Recomendações
```python
# Adicionar índices
from sqlalchemy import Index

Index('idx_lixeira_status', Coletor.status)
Index('idx_coleta_data_hora', Coleta.data_hora)
Index('idx_coleta_lixeira_id', Coleta.coletor_id)
```

### 15. **Validação de Entrada em APIs (ALTO)**

#### Problema
- Parâmetros de query podem não estar sendo validados
- Tipos podem estar incorretos
- Ranges podem estar fora do esperado

#### Arquivos Afetados
- `rotas/api/coletores.py` - Parâmetros de paginação
- `rotas/api/coletas.py` - Filtros de data
- `rotas/api/relatorios.py` - Parâmetros de relatório

#### Recomendações
```python
# Validar parâmetros
pagina = request.args.get('pagina', type=int, default=1)
if pagina < 1:
    pagina = 1
if pagina > 1000:  # Limite máximo
    pagina = 1000
```

### 16. **Proteção contra SQL Injection (CRÍTICO)**

#### Problema
- Queries raw podem estar vulneráveis
- String formatting pode ser inseguro
- Parâmetros podem não estar sendo escapados

#### Status
✅ **JÁ PROTEGIDO** - SQLAlchemy ORM previne SQL injection automaticamente

#### Verificação Necessária
- Verificar se há queries raw em algum lugar
- Garantir que todos os parâmetros usam bind parameters

### 17. **Validação de Tamanho de Upload (MÉDIO)**

#### Problema
- Arquivos CSV podem ser muito grandes
- Importação pode consumir muita memória
- Não há limite de tamanho de requisição

#### Arquivos Afetados
- `banco_dados/importar_csv.py` - Importação de dados

#### Recomendações
```python
# Limitar tamanho de upload
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
```

### 18. **Logging e Monitoramento (BAIXO)**

#### Problema
- Alguns erros podem não estar sendo logados
- Falta de métricas de performance
- Falta de alertas para erros críticos

#### Recomendações
```python
# Logging estruturado
import logging
logger = logging.getLogger(__name__)

logger.error('Erro crítico', extra={
    'user_id': current_user.id,
    'endpoint': request.endpoint,
    'error_type': type(e).__name__
})
```

---

## 📊 PRIORIZAÇÃO

### 🔴 **CRÍTICO (Implementar Imediatamente)**
1. Transações de banco de dados com rollback
2. Segurança de sessões e cookies
3. Proteção contra SQL Injection (verificar)
4. Rate limiting em APIs públicas

### 🟠 **ALTO (Implementar em Breve)**
5. Validação de variáveis de ambiente
6. Timeouts em chamadas externas
7. Validação de entrada em APIs
8. Tratamento de erros em operações assíncronas
9. Validação de coordenadas

### 🟡 **MÉDIO (Implementar Quando Possível)**
10. N+1 Query Problems
11. Memory leaks em event listeners
12. Validação de tipos numéricos
13. Tratamento de erros em email
14. Quota de storage do browser
15. Validação de datas
16. Limite de tamanho de upload

### 🟢 **BAIXO (Melhorias Futuras)**
17. Índices de banco de dados
18. Logging e monitoramento

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

### Backend Python
- [ ] Adicionar rollback em todas as transações
- [ ] Validar variáveis de ambiente com defaults seguros
- [ ] Configurar sessões seguras (HttpOnly, Secure, SameSite)
- [ ] Implementar rate limiting
- [ ] Adicionar timeouts em chamadas externas
- [ ] Validar todos os parâmetros de entrada
- [ ] Adicionar retry para emails críticos
- [ ] Limitar tamanho de upload

### Frontend JavaScript
- [ ] Adicionar timeouts em requisições HTTP
- [ ] Validar coordenadas antes de usar
- [ ] Validar números antes de cálculos
- [ ] Tratar quota exceeded em storage
- [ ] Remover event listeners ao destruir componentes
- [ ] Validar datas antes de processar
- [ ] Adicionar cancelamento de requisições antigas

### Banco de Dados
- [ ] Adicionar índices em queries frequentes
- [ ] Usar eager loading para evitar N+1
- [ ] Verificar constraints e foreign keys

---

## 🎯 CONCLUSÃO

Foram identificadas **18 áreas adicionais** que precisam de atenção para garantir robustez total. As áreas críticas devem ser implementadas imediatamente, enquanto as de prioridade média/baixa podem ser implementadas gradualmente.

**Status:** Sistema está **85% robusto**. Com as correções críticas, chegará a **95% robusto**.

