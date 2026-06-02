# Pesquisa: Enriquecimento de CNPJ — Endereço + CNAE para MEIs do DF

**Data:** Maio 2026  
**Objetivo:** Resolver data leakage no pipeline de prospecção REEE onde ~95% dos ~534k CNPJs do DF carecem de CNAE principal, endereço e geocoding.

---

## 1. Análise do Problema

### Situação Atual
- **534k empresas do DF** (provenientes da Receita Federal via casadosdados)
- **~510k CNPJs** com `cnae_principal = null` (MEIs/PF com CNPJ)
- **Falta de features críticas:**
  - `cnae_principal` — necessário para segmentação
  - `latitude/longitude` — necessário para features geográficas
  - `endereco` (CEP, logradouro, número, bairro) — necessário para geocoding

### Impacto
O modelo XGBRanker não consegue rankear porque não há features discriminativas que separarem MEIs ativos de inativos.

---

## 2. Opções de Enriquecimento Avaliadas

### OPÇÃO 1: Receita Federal — Dump Local (RECOMENDADO)

**Descrição:**  
Baixar o dump completo dos estabelecimentos da Receita Federal em formato CSV/SQLite e fazer JOIN local com os CNPJs existentes.

**Fontes de Dados:**
- URL oficial: https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj
- Frequência: Atualizado mensalmente pela RFB
- Layout 2026: https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf

**Estrutura do Arquivo de Estabelecimentos:**

O arquivo contém as seguintes colunas (layout 2026):
- `cnpj` — CNPJ do estabelecimento
- `cnae_principal` — Código CNAE principal (7 dígitos, ex: "4721300")
- `cnae_secundaria` — CNAEs secundários (separados por virgula)
- `razao_social` — Nome da pessoa jurídica
- `nome_fantasia` — Nome comercial
- `situacao_cadastral` — Status (Ativa, Cancelada, Suspensa, etc)
- `tipo_logradouro` — Tipo (Rua, Avenida, Praça, etc)
- `logradouro` — Nome da rua/av
- `numero` — Número do imóvel
- `complemento` — Complemento (apto, sala, etc)
- `bairro` — Bairro
- `cep` — CEP (8 dígitos)
- `municipio` — Município (pode usar para filtrar DF=5300108)
- `uf` — Estado (DF)
- `email` — Email registrado
- `telefone` — Telefone

**Ferramentas Python Disponíveis:**

1. **`cnpj-sqlite`** (simples)
   - GitHub: https://github.com/rictom/cnpj-sqlite
   - Baixa o dump e converte para SQLite
   - Vantagem: Simples, pronto para uso
   - Tempo: ~2-4 horas para processar tudo
   - Disco necessário: ~60GB (30GB SQLite + 25GB arquivos RFB)

2. **`CNPJ-full`** (flexível)
   - GitHub: https://github.com/fabioserpa/CNPJ-full
   - Output: CSV, SQLite ou banco PostgreSQL
   - Vantagem: Suporta múltiplos formatos, filtros customizáveis
   - Recomendado se precisar exportar para pipelines downstream

3. **`rfb-cnpj-etl`** (robusto)
   - GitHub: https://github.com/msantosjader/rfb-cnpj-etl
   - Output: SQLite ou PostgreSQL com schema bem definido
   - Vantagem: Trata erros, versionamento de dados
   - Melhor para produção

4. **`qsacnpj`** (R language)
   - GitHub: https://github.com/georgevbsantiago/qsacnpj
   - Se sua stack usa R

**Como Usar (exemplo com cnpj-sqlite):**
```bash
git clone https://github.com/rictom/cnpj-sqlite.git
cd cnpj-sqlite
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py  # Baixa e processa tudo automaticamente
```

Resultado: Banco SQLite com tabelas `empresas`, `estabelecimentos`, `socios`, `simples`

**Viabilidade para 300k CNPJs do DF:**
- ✅ **Altíssima** — JOIN local (segundos)
- ✅ Sem rate limits
- ✅ Uma única execução mensal
- ✅ Garante CNAE principal + endereço completo
- ✅ Dados oficiais e auditáveis

**Limitações:**
- ⚠️ Requer ~60GB disco temporário
- ⚠️ Processamento leva horas (uma vez)
- ⚠️ Delay de 1-2 meses no ciclo oficial da RFB

---

### OPÇÃO 2: BrasilAPI CNPJ — Consulta por API

**Descrição:**  
API pública que expõe dados da Receita Federal em tempo real (mais atualizados que dump).

**Endpoint:**  
```
GET https://brasilapi.com.br/api/cnpj/v1/{CNPJ}
```

**Response Example:**
```json
{
  "cnpj": "11222333000181",
  "razao_social": "Empresa LTDA",
  "nome_fantasia": "Nome Comercial",
  "descricao_situacao_cadastral": "Ativa",
  "data_situacao_cadastral": "2021-11-05",
  "tipo_inscricao": 1,
  "endereco": {
    "logradouro": "Rua das Flores",
    "numero": "123",
    "complemento": "Apto 45",
    "bairro": "Bom Abrigo",
    "municipio": "Brasília",
    "uf": "DF",
    "cep": "70040000"
  },
  "cnae_fiscal": "4721300",
  "cnae_fiscal_descricao": "Consultoria em Sistemas de Tecnologia da Informação",
  "natureza_juridica": "Sociedade Limitada",
  "socios": [...]
}
```

**Rate Limits:**
- ❌ NÃO publicado na documentação oficial
- ⚠️ GitHub discussions (#235) indicam que há throttling
- ⚠️ BrasilAPI avisa contra "automated crawling" ou "full scanning"
- Upstream (ReceitaWS) tem limite de **3 queries/minuto**
- ⚠️ Para 300k CNPJs com este limite: ~100 dias de requisições

**Viabilidade para 300k CNPJs:**
- ⚠️ **Baixa** — rate limiting agressivo (não documentado)
- ⚠️ Tempo estimado: 100+ dias se respeitando limites
- ❌ Não viável para enriquecimento em batch
- ✅ Útil para validar dados individuais pós-enriquecimento

**Recomendação:**
Usar como fallback para CNPJs novos ou validação em tempo real, não para batch inicial.

---

### OPÇÃO 3: ReceitaWS API

**Descrição:**  
Serviço de consulta CNPJ gratuito mantido pela comunidade. Webservice que agregava dados da Receita Federal.

**Endpoint:**
```
GET https://www.receitaws.com.br/v1/cnpj/{CNPJ}
```

**Response Example:**
```json
{
  "cnpj": "11222333000181",
  "nome": "Empresa LTDA",
  "atividade_principal": [
    {
      "text": "Consultoria em Sistemas de Tecnologia da Informação",
      "code": "4721300"
    }
  ],
  "atividades_secundarias": [...],
  "endereco": "Rua das Flores",
  "numero": "123",
  "complemento": "Apto 45",
  "bairro": "Bom Abrigo",
  "municipio": "Brasília",
  "cep": "70040900",
  "uf": "DF",
  "status": "Ativa"
}
```

**Rate Limits:**
- ❌ Limite conhecimento: **3 queries/minuto** (conforme documentação FAQ)
- ❌ Para 300k CNPJs: ~100 dias em batch sequencial
- ⚠️ CNPJs muito recentes podem retornar dados incompletos
- ⚠️ Depende de servidor externo (menos confiável que dump local)

**Viabilidade para 300k CNPJs:**
- ❌ **Muito Baixa** — rate limiting severo
- ⚠️ Requer mecanismo de retry e backoff
- ❌ Não recomendado para batch inicial
- ✅ Útil para: validação unitária, dados em tempo real, CNPJs novos

**Problema adicional:**  
ReceitaWS é mantenido por comunidade; dados podem estar desatualizados em relação ao RFB.

---

### OPÇÃO 4: Portal Gov.br — API Oficial do Governo

**Descrição:**  
API oficial do governo federal para consulta CNPJ, integração com Receita Federal.

**Endpoint:**  
```
https://www.gov.br/conecta/catalogo/apis/consulta-cnpj
```

**Tipos de Consulta:**
1. **Consulta Básica** — Status cadastral, endereço, atividade econômica, telefone
2. **Consulta QSA** — Basic + sócios/quadro societário
3. **Consulta Empresa** — All + CPF/CNPJ dos sócios

**Rate Limits:**
- ⚠️ NÃO encontrado documentação clara de rate limits
- Presume-se similar a ReceitaWS (upstream) — ~3/min
- Requer integração via portal gov.br
- Acesso pode exigir credenciais

**Viabilidade para 300k CNPJs:**
- ❌ **Provavelmente Baixa** — sem documentação de throughput
- ⚠️ Requer acesso oficial via gov.br
- ❌ Sem garantias de SLA para batch processing
- ✅ Útil para: validação oficial, casos específicos

---

### OPÇÃO 5: Base dos Dados — CNPJ via BigQuery

**Descrição:**  
Plataforma open-source que disponibiliza datasets públicos brasileiros em BigQuery, incluindo tabelas CNPJ estruturadas.

**URL:**  
https://basedosdados.org/dataset/33b49786-fb5f-496f-bb7c-9811c985af8e?table=b71e9a46-f98e-476b-a2d6-4444213a8ddc

**Tables Disponíveis:**
- `br_receita_federal.cnpj_empresas` — Empresa principal
- `br_receita_federal.cnpj_estabelecimentos` — Estabelecimentos (endereço + CNAE)
- `br_receita_federal.cnpj_socios` — Sócios
- `br_receita_federal.cnpj_cnae` — Descritivo CNAE

**Query Example (BigQuery SQL):**
```sql
SELECT
  est.cnpj,
  est.cnae_principal,
  est.razao_social,
  est.logradouro,
  est.numero,
  est.bairro,
  est.cep,
  est.municipio
FROM `basedosdados.br_receita_federal.cnpj_estabelecimentos` est
WHERE est.uf = 'DF'
  AND est.cnpj IN (SELECT cnpj FROM seu_dataset.cnpjs_prospeccao);
```

**Rate Limits:**
- ✅ BigQuery: ilimitado (pago por volume)
- ✅ Consultas rápidas (segundos para 300k)
- ✅ Dados estruturados, auditados

**Viabilidade para 300k CNPJs:**
- ✅ **Alta** — se tiver crédito BigQuery ou acesso free
- ✅ Query em segundos
- ✅ Dados oficiais RFB sincronizados
- ⚠️ Requer conta Google Cloud / BigQuery
- ⚠️ Custo: ~USD 5-10 para 300k registros (excesso de free tier)

**Recomendação:**
Excelente alternativa se ja tem Cloud setup; caso contrário, preferir Receita Federal dump local.

---

## 3. Comparativo de Viabilidade

| Critério | Receita Federal Dump | BrasilAPI | ReceitaWS | Gov.br API | Base dos Dados |
|----------|---------------------|-----------|-----------|-----------|-----------------|
| **Tempo p/ 300k** | 1-2h (load) | 100+ dias | 100+ dias | ~100 dias | ~30s (BigQuery) |
| **Rate Limit** | ∞ (local) | ❌ Não doc | 3/min | ❌ Não doc | ✅ BigQuery |
| **CNAE + Endereço** | ✅ Completo | ✅ Sim | ✅ Sim | ✅ Sim | ✅ Completo |
| **Custo** | Disco (1x) | Grátis | Grátis | Grátis | USD 5-10 |
| **Facilidade** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **Atualização** | Mensal (RFB) | Tempo real | Desatualizado | Tempo real | Mensal (RFB) |
| **Viabilidade** | 🟢 Altíssima | 🔴 Baixa | 🔴 Baixa | 🟡 Média | 🟢 Alta |

---

## 4. Recomendação de Implementação (Ordem de Prioridade)

### FASE 1 (Recomendado) — Receita Federal Dump Local
**Viabilidade:** 🟢 Altíssima  
**Timeline:** 1-2 horas (uma vez por mês)

1. **Tooling:**
   - Usar `rfb-cnpj-etl` (mais robusto para produção)
   - GitHub: https://github.com/msantosjader/rfb-cnpj-etl

2. **Setup:**
   ```bash
   git clone https://github.com/msantosjader/rfb-cnpj-etl.git
   cd rfb-cnpj-etl
   pip install -r requirements.txt
   
   # Configurar para apenas DF + apenas estabelecimentos
   python main.py --state=DF --tables=estabelecimentos --format=sqlite --output=cnpj_df.db
   ```

3. **Operação:**
   - Executar mensalmente (1ª semana após RFB liberar dump)
   - Exportar para PostgreSQL/SQLite na infraestrutura Tronik
   - Fazer JOIN com CNPJs existentes:
   ```sql
   UPDATE prospeccao.candidatos pc
   SET cnae_principal = est.cnae_principal,
       endereco = CONCAT(est.logradouro, ', ', est.numero),
       bairro = est.bairro,
       cep = est.cep
   FROM (SELECT * FROM cnpj_df.estabelecimentos WHERE uf='DF') est
   WHERE pc.cnpj = est.cnpj
     AND pc.cnae_principal IS NULL;
   ```

4. **Resultado Esperado:**
   - ✅ Cobertura de ~300k CNPJs do DF
   - ✅ CNAE principal recuperado
   - ✅ Endereço + CEP + bairro para geocoding
   - ✅ Sem rate limits
   - ✅ Dados auditáveis

5. **Esforço de Implementação:**
   - Setup: 2-3h (download + parsing + teste)
   - Operacional: 30min/mês (cron job)

---

### FASE 2 (Backup/Validação) — BrasilAPI para CNPJs Novos
**Viabilidade:** 🟡 Média (validação, não batch)  
**Timeline:** On-demand

**Caso de Uso:**
- Quando novo CNPJ for adicionado ao pipeline APÓS enriquecimento Fase 1
- Validação de dados em tempo real
- Features adicionais (sócios, capital, etc)

**Implementação:**
```python
import httpx
import asyncio

async def enrich_new_cnpj(cnpj: str):
    async with httpx.AsyncClient() as client:
        # Rate limit: 1 req/sec
        resp = await client.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}")
        return resp.json()

# Usar em background job, não em batch
```

---

### FASE 3 (Opcional) — Base dos Dados para Validação em BigQuery
**Viabilidade:** 🟢 Alta (se houver Cloud setup)  
**Timeline:** Ad-hoc

**Caso de Uso:**
- Validação de dados RFB via BigQuery
- Enriquecimento adicional com tabelas complementares
- Análise de qualidade de dados

**Query:**
```sql
SELECT est.cnpj, est.cnae_principal, est.logradouro
FROM `basedosdados.br_receita_federal.cnpj_estabelecimentos` est
WHERE est.uf = 'DF'
LIMIT 300000;
```

---

## 5. Problema MEI — CNAE em PF com CNPJ

### Situação:
Pessoas físicas registradas como MEI (ex: "66.600.157 MARCUS VINICIUS") aparecem no dump CNPJ com:
- `cnae_principal = null` (aparentemente)
- `cnae_secundaria` = preenchido

### Solução no Dump RFB:
No arquivo de estabelecimentos da Receita Federal:
- MEIs estão na tabela `estabelecimentos`
- Campo `cnae_principal` contém o CNAE principal do MEI
- Pode haver múltiplos CNAEs no campo `cnae_secundaria`

**Filtrar MEIs do DF:**
```sql
SELECT cnpj, cnae_principal, razao_social, logradouro, numero, bairro, cep
FROM estabelecimentos
WHERE uf = 'DF'
  AND situacao_cadastral = 'Ativa'
  AND (tipo_pessoa = 'Pessoa Física' OR cnae_principal IS NOT NULL)
LIMIT 300000;
```

### Validação:
- Se após JOIN ainda houver `cnae_principal = null`, significa CNPJ nunca foi registrado na RFB
- Neste caso: usar BrasilAPI como fallback (Fase 2)

---

## 6. Estrutura Final Recomendada

```
tronik/dashboard-tronik/
├── docs/
│   └── research_cnpj_enrichment.md  (este arquivo)
├── jobs/prospeccao/
│   ├── enrich_cnpj_receita_federal.py  (NOVA — Fase 1)
│   ├── enrich_cnpj_brasilapi.py        (NOVA — Fase 2)
│   └── ...
├── data/
│   └── cnpj/
│       └── cnpj_df_estabelecimentos.db  (Receita Federal dump)
└── ...
```

**Script Principal (pseudo-código):**
```python
#!/usr/bin/env python3
# enrich_cnpj_receita_federal.py

import sqlite3
import subprocess
from datetime import datetime

def main():
    # FASE 1: Download + Parse Receita Federal
    print(f"[{datetime.now()}] Iniciando enriquecimento CNPJ (Receita Federal)")
    
    # Download RFB dump (usando rfb-cnpj-etl ou cnpj-sqlite)
    subprocess.run([
        "python", "-m", "rfb_cnpj_etl.main",
        "--state=DF",
        "--format=sqlite",
        "--output=/data/cnpj/cnpj_df.db"
    ])
    
    # Load no banco Tronik
    conn = sqlite3.connect("/data/cnpj/cnpj_df.db")
    cursor = conn.cursor()
    
    # JOIN com prospeccao.candidatos
    cursor.execute("""
        UPDATE prospeccao.candidatos pc
        SET cnae_principal = est.cnae_principal,
            endereco = est.logradouro || ', ' || est.numero,
            bairro = est.bairro,
            cep = est.cep,
            atualizado_em = NOW()
        FROM cnpj_df.estabelecimentos est
        WHERE pc.cnpj = est.cnpj
          AND pc.cnae_principal IS NULL
    """)
    
    # FASE 2: Enriquecer CNPJs novos via BrasilAPI (background)
    # TODO: implementar on-demand
    
    print(f"[{datetime.now()}] Enriquecimento concluído!")

if __name__ == "__main__":
    main()
```

---

## 7. Links de Referência

**Receita Federal — Dados Abertos:**
- Portal: https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj
- Metadados Layout 2026: https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf

**Ferramentas Recomendadas:**
- rfb-cnpj-etl: https://github.com/msantosjader/rfb-cnpj-etl
- cnpj-sqlite: https://github.com/rictom/cnpj-sqlite
- CNPJ-full: https://github.com/fabioserpa/CNPJ-full

**APIs Complementares:**
- BrasilAPI CNPJ: https://brasilapi.com.br/docs
- ReceitaWS: https://receitaws.com.br/api
- Gov.br API: https://www.gov.br/conecta/catalogo/apis/consulta-cnpj
- Base dos Dados: https://basedosdados.org/dataset/33b49786-fb5f-496f-bb7c-9811c985af8e

**Referências Técnicas:**
- CONCLA CNAE Search: https://concla.ibge.gov.br/busca-online-cnae.html
- MEI Atividades Permitidas: https://www.gov.br/empresas-e-negocios/pt-br/empreendedor/quero-ser-mei/atividades-permitidas

---

## 8. Próximos Passos

1. ✅ Validar espaço em disco (60GB) para download RFB
2. ⬜ Testar `rfb-cnpj-etl` localmente com subset DF
3. ⬜ Implementar script de cron job (mensal)
4. ⬜ Executar JOIN inicial com 300k CNPJs
5. ⬜ Avaliar cobertura de `cnae_principal` pós-enriquecimento
6. ⬜ Reescrever features ML do XGBRanker com novos campos
7. ⬜ Re-treinar modelo com features discriminativas
8. ⬜ Implementar Fase 2 (BrasilAPI on-demand) se necessário

---

**Conclusão:** A solução recomendada (Receita Federal Dump Local + rfb-cnpj-etl) resolve 95%+ do problema de data leakage com viabilidade altíssima, custo mínimo e sem rate limits. APIs (BrasilAPI, ReceitaWS) são úteis apenas como complemento para validação e novos registros.
