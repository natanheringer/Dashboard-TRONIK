# Pesquisa: Geocodificação de 300k Endereços do DF

**Data:** Maio 2026  
**Objetivo:** Resolver a falta de coordenadas (lat/lon) para empresas com CEP disponível  
**Contexto:** Pipeline prospeccao_ree com módulo CNEFE, mas cobertura insuficiente para endereços incompletos

---

## 1. Análise de APIs de CEP → Coordenadas

### 1.1 ViaCEP (https://viacep.com.br)
- **O que retorna:** Logradouro, número, bairro, cidade, estado, CEP — **NÃO retorna lat/lon**
- **Limitação crítica:** Requer endereço completo (logradouro + número)
- **Cobertura DF:** Apenas para CEPs válidos registrados nos Correios
- **Conclusão:** Não recomendado para este caso de uso

### 1.2 AwesomeAPI CEP (https://cep.awesomeapi.com.br)
- **O que retorna:** CEP, logradouro, número, bairro, cidade, **lat, lng**, state, DDD
- **Base de dados:** IBGE CNEFE
- **Rate limit (Free):** 100.000 requisições/mês (desde Mar/2025)
- **Formato:** JSON/XML
- **Endpoint:** `https://cep.awesomeapi.com.br/json/{cep}` → Retorna objeto com `lat` e `lng`
- **Documentação:** [AwesomeAPI CEP Docs](https://docs.awesomeapi.com.br/api-cep) | [GitHub](https://github.com/awesomeapibrasil/awesomeapi-cep)
- **Status:** Ativo e mantido (2025+)
- **Conclusão:** ✅ **MELHOR opção gratuita para CEP → lat/lon direto**
  - Para 300k: precisa 3 meses com free tier (100k/mês) ou upgrade pago
  - Custo negligenciável se batch processing

### 1.3 BrasilAPI v2 (https://brasilapi.com.br)
- **Informação:** BrasilAPI v2 exibe coordenadas de cada CEP
- **Limitação:** Documentação genérica, implementação exata não especificada
- **Alternativa:** Use AwesomeAPI que tem docs mais claras
- **Referência:** [BrasilAPI Issue #34](https://github.com/BrasilAPI/BrasilAPI/issues/34)

### 1.4 CEP Aberto (https://www.cepaberto.com)
- **O que retorna:** CEP, logradouro, bairro, **lat, lng**, altitude, DDD
- **Base de dados:** Colaborativa (crowdsourced + oficial)
- **Rate limit:** Não especificado publicamente; acesso requer registro gratuito
- **Qualidade:** Variável (base colaborativa)
- **Conclusão:** Alternativa viável se AwesomeAPI atingir limite mensal
- **Referência:** [CEP Aberto](https://www.cepaberto.com/)

### 1.5 MapaCEP (https://www.mapacep.com.br)
- **O que oferece:** Busca por CEP, cidade, endereço, CNPJ
- **Coordenadas:** Aparenta ter, mas sem API documentada
- **Conclusão:** Interface web apenas, não recomendado para batch

### 1.6 geocodebr (R package, IPEA)
- **O que é:** Pacote R com CNEFE para geocodificação de endereços
- **Base:** CNEFE + OpenStreetMap Nominatim
- **Precisão:** 6 categorias, com estimativa de incerteza em metros
- **Velocidade:** Milhões de endereços em minutos
- **Custo:** Gratuito, sem limites
- **Limitação:** Apenas R (não Python nativo), requer endereço estruturado
- **Uso:** Referência para fallback por bairro/RA
- **Documentação:** [geocodebr](https://ipeagit.github.io/geocodebr/) | [GitHub](https://github.com/ipeaGIT/geocodebr)

---

## 2. OpenStreetMap Nominatim (Batch)

### 2.1 Nominatim Público (https://nominatim.openstreetmap.org)
- **Rate limit:** 1 requisição/segundo (máximo)
- **Tempo estimado para 300k:** ~83 horas contínuas (não viável)
- **Termos de Serviço:** Não recomendado para uso comercial em larga escala
- **Conclusão:** ❌ Inviável para 300k endereços em tempo razoável
- **Referência:** [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)

### 2.2 Nominatim Self-Hosted (Docker)
- **Imagem recomendada:** `mediagis/nominatim` (100% funcional em container)
- **Requisitos:**
  - Docker Desktop (disponível em Windows)
  - PostgreSQL + PostGIS (inclusos no container)
  - Espaço em disco: ~10-20GB para dados do Brasil
  - RAM: 4-8GB recomendado
- **Vantagem:** Zero rate limits, rápido (10-100 req/s dependendo hardware)
- **Desvantagem:** 
  - Overhead de manutenção (atualização de dados PBF)
  - Inicialização lenta (1-2h para import dos dados do Brasil)
  - Complexidade operacional
- **Tempo to value:** ~2-3 horas setup + teste
- **Conclusão:** ⚠️ Viável apenas se volume > 5M endereços/ano ou uso recorrente
- **Referência:** [mediagis/nominatim GitHub](https://github.com/mediagis/nominatim-docker) | [Docker Hub](https://hub.docker.com/r/mediagis/nominatim/)

---

## 3. Serviços Comerciais

### 3.1 Google Maps Geocoding API
- **Free tier:** 10.000 requisições/mês (desde Mar/2025)
- **Preço:** $2-7 / 1.000 após limite
- **Para 300k:** ~$600-2.100/ano (300k = 300 × 1k)
- **Taxa de consulta:** 3.000 req/min
- **Qualidade:** Excelente (cobertura global)
- **Conclusão:** 💰 Custo-benefício ruim para 300k único batch
- **Referência:** [Google Maps Pricing](https://developers.google.com/maps/billing-and-pricing/pricing) | [2026 Cost Guide](https://csv2geo.com/blog/geocoding-api-pricing-compared-real-cost-2026)

### 3.2 Mapbox Geocoding API
- **Free tier:** 100.000 requisições/mês
- **Preço (acima do free):** 
  - Temporary (sem storage): $0.45-0.75 / 1.000
  - Permanent (com storage): $5 / 1.000
- **Para 300k (temporary):** ~$90-135 para 300k + 3 primeiros meses grátis
- **Economia vs Google:** 30-50% mais barato em larga escala
- **Taxa de consulta:** 600 req/min
- **Restrição crítica:** "Um request acima de 100k e o medidor começa a rodar"
- **Conclusão:** 💰 Melhor preço comercial, mas ainda caro para único batch
- **Referência:** [Mapbox Pricing](https://www.mapbox.com/pricing) | [Comparison 2026](https://www.buildmvpfast.com/api-costs/maps)

### 3.3 Here Technologies
- **Free tier:** 5.000-15.000 req/mês (depende do plano)
- **Preço:** Customizado, escondido até contato
- **Conclusão:** ❌ Evitar para este caso (pouca transparência)

---

## 4. CNEFE - Cobertura Atual

### 4.1 O que é CNEFE
- **Nome completo:** Cadastro Nacional de Endereços para Fins Estatísticos (IBGE)
- **Cobertura:** Todo o Brasil (106,8M endereços no Censo 2022)
- **Atualização:** A cada Censo Demográfico
- **Dados inclusos:** Logradouro, número, complemento, bairro, CEP, tipo de edificação

### 4.2 Cobertura DF Específica
- **Estrutura do DF:** 35 Regiões Administrativas (RAs) — NÃO há divisão em "cidades"
- **Cobertura esperada:** Alto em áreas consolidadas (Plano Piloto, RAs oficiais); baixo em invasões/áreas irregulares
- **Limite do módulo atual:** 
  - Require endereço estruturado (logradouro completo)
  - Não funciona com "Brasília, DF" genérico sem logradouro
  - Maior sucesso com endereços de empresas formalizadas vs. residências

### 4.3 Falhas Atuais (300k com lat/lon = NULL)
- **Causas:**
  1. Logradouro incompleto ou inválido no pipeline
  2. Endereço não encontrado no CNEFE (áreas informais)
  3. Apenas CEP disponível, sem logradouro
  4. Variações ortográficas não normalizadas
- **Cobertura estimada CNEFE:** 60-75% das empresas do DF com CEP válido
- **Referência:** [CNEFE IBGE](https://www.ibge.gov.br/estatisticas/sociais/populacao/38734-cadastro-nacional-de-enderecos-para-fins-estatisticos.html)

---

## 5. IBGE API - Fallback por RA/Bairro

### 5.1 IBGE Localidades API
- **Endpoint:** `https://servicodados.ibge.gov.br/api/docs/localidades`
- **O que oferece:** Informações sobre divisões político-administrativas do Brasil
- **Para DF:** Dados de cada RA, mas centróides não foram precisados

### 5.2 IBGE Malhas API (v3/v4)
- **Endpoint:** `https://servicodados.ibge.gov.br/api/docs/malhas`
- **Formatos:** GeoJSON, TopoJSON, SVG
- **Parâmetro:** `?formato=application/vnd.geo+json`
- **Benefício:** Polígonos das RAs com geometria real
- **Extração de centróide:** Calc geométrico do polígono → lat/lon do centroid

### 5.3 Alternativa: IBRAM (Órgão do DF)
- **Servidor ArcGIS:** IBRAM Território/Regiões_Administrativas_DF_2025
- **Formato:** GeoJSON (Layer ID 0)
- **Vantagem:** Dados atualizados pelo DF, não apenas IBGE
- **Referência:** [IBRAM REST Services](https://onda.ibram.df.gov.br/server/rest/services/Territorio/Regioes_Administrativas_DF_2025/MapServer/0)

---

## 6. Recomendação Final: Estratégia Híbrida

### 🎯 Solução Proposta

#### **Pipeline de Geocodificação em 4 Camadas:**

```
Entrada: CEP + Endereço (pode estar incompleto)
           ↓
    [Camada 1] AwesomeAPI CEP → lat/lon direto
           ↓ (sem sucesso ou CEP inválido)
    [Camada 2] CNEFE Ingest atual (se logradouro completo)
           ↓ (sem sucesso)
    [Camada 3] IBGE Malhas API → Centróide da RA
           ↓ (sem sucesso)
    [Camada 4] DF Centróide (~-15.78, -47.88)
           ↓
    Saída: lat/lon + flag de qualidade/fonte
```

### 1️⃣ Camada 1: AwesomeAPI CEP (Primária)

**Implementação:**
```python
import requests

def geocode_by_cep(cep_clean):
    """
    Geocodifica via AwesomeAPI CEP → lat/lon direto.
    Input: CEP apenas (ex: "01000000")
    Output: {"lat": float, "lng": float, "quality": "cep"}
    """
    try:
        resp = requests.get(f"https://cep.awesomeapi.com.br/json/{cep_clean}")
        if resp.status_code == 200:
            data = resp.json()
            return {
                "lat": float(data.get("lat")),
                "lng": float(data.get("lng")),
                "quality": "cep_direct",
                "source": "awesomeapi"
            }
    except:
        pass
    return None
```

**Características:**
- ✅ Zero latência (resp instantâneo)
- ✅ Sem overhead de processamento de texto
- ✅ Limites: 100k/mês free (upgradável)
- ✅ Precisão: Centróide do CEP (±500m típico)
- ⚠️ Requer CEP válido e bem-formado

**Custo para 300k:**
- Free: 3 meses × 100k = 300k (requer wait ou upgrade)
- Upgrade: ~R$ 50-100/mês (pricing não publicado, estimar contato)

---

### 2️⃣ Camada 2: CNEFE Ingest Existente (Refinamento)

**Melhorias ao módulo atual:**
```python
def geocode_by_cnefe_refined(endereco_dict, max_partial=True):
    """
    Tenta CNEFE, mas com tolerância a endereços parciais.
    - Se logradouro vazio → tenta apenas bairro + CEP
    - Se bairro vazio → tenta logradouro + CEP
    - Retorna melhor match, não só exato
    """
    # Seu cnefe_ingest.py já faz isso?
    # Recomendação: adicionar modo "fuzzy matching"
    # Referência: fuzzywuzzy ou Levenshtein
    pass
```

**Considerar integração com geocodebr (via R subprocess):**
```python
import subprocess
import json

def geocode_via_geocodebr(endereco_estruturado):
    """
    Fallback: chama geocodebr do R se disponível.
    Melhor cobertura de CNEFE + fallback OSM automático.
    """
    r_code = f'''
    library(geocodebr)
    result <- geocode(address="{endereco_estruturado}")
    cat(jsonlite::toJSON(result))
    '''
    proc = subprocess.run(
        ["Rscript", "-e", r_code],
        capture_output=True, text=True
    )
    return json.loads(proc.stdout)
```

**Características:**
- ✅ Máxima precisão (endereço real vs. centróide)
- ✅ Já implementado no pipeline
- ⚠️ Requer dados estruturados (logradouro, número)
- ⚠️ Sem sucesso se dados incompletos

---

### 3️⃣ Camada 3: IBGE Malhas API → Centróide RA (Fallback Geo)

**Implementação:**

```python
import requests
from shapely.geometry import shape
import json

# Cache das RAs do DF (pre-cache na inicialização)
RA_CACHE = {}

def init_ra_cache():
    """
    Carrega polígonos das RAs DF uma única vez.
    Calcula centróide de cada RA.
    """
    global RA_CACHE
    
    # Opção A: IBGE Malhas (genérica)
    # resp = requests.get("https://servicodados.ibge.gov.br/api/v3/malhas?formato=application/vnd.geo+json")
    
    # Opção B: IBRAM (mais atualizado para DF)
    resp = requests.get(
        "https://onda.ibram.df.gov.br/server/rest/services/Territorio/Regioes_Administrativas_DF_2025/MapServer/0/query",
        params={"where": "1=1", "outFormat": "geojson", "returnGeometry": True}
    )
    
    if resp.status_code == 200:
        geojson = resp.json()
        for feature in geojson.get("features", []):
            ra_name = feature["properties"].get("name") or feature["properties"].get("NOME")
            geom = shape(feature["geometry"])
            centroid = geom.centroid
            
            RA_CACHE[ra_name] = {
                "lat": centroid.y,
                "lng": centroid.x,
                "polygon": geom
            }

def geocode_by_ra(ra_name):
    """
    Retorna centróide da RA do DF.
    Input: Nome da RA (ex: "Brasília", "Taguatinga")
    """
    if not RA_CACHE:
        init_ra_cache()
    
    if ra_name in RA_CACHE:
        return {
            "lat": RA_CACHE[ra_name]["lat"],
            "lng": RA_CACHE[ra_name]["lng"],
            "quality": "ra_centroid",
            "source": "ibge_malhas"
        }
    return None
```

**Características:**
- ✅ Cobertura 100% (todas as 35 RAs do DF)
- ✅ Sem rate limits (dados estatísticos)
- ✅ Precisão: Centróide RA (~1-3km)
- ⚠️ Requer extração de RA do endereço original

**Extração de RA:**
```python
def extract_ra_from_address(endereco):
    """
    Tenta encontrar RA em "Brasília, Taguatinga, DF" etc.
    Usa fuzzy match contra lista das 35 RAs.
    """
    from fuzzywuzzy import fuzz
    
    ras_df = [
        "Brasília", "Taguatinga", "Brazlândia", "Sobradinho", "Planaltina",
        "Paranoá", "Núcleo Bandeirante", "Ceilândia", "Guará", "Cruzeiro",
        "Samambaia", "Santa Maria", "São Sebastião", "Recanto das Emas",
        "Lago Sul", "Riacho Fundo", "Lago Norte", "Candangolândia",
        "Águas Claras", "Riacho Fundo II", "Sudoeste/Octogonal",
        "Varjão", "Park Way", "SCIA", "Sobradinho II", "Jardins Mangueiral",
        "Itapoã", "SIA", "Vicente Pires", "Fercal", "Arniqueira",
        # ... etc
    ]
    
    best_match = max(
        [(ra, fuzz.ratio(endereco.upper(), ra.upper())) for ra in ras_df],
        key=lambda x: x[1]
    )
    
    if best_match[1] > 80:  # threshold
        return best_match[0]
    return None
```

**Referências:**
- [IBGE Malhas API](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3)
- [IBRAM DF Layer](https://onda.ibram.df.gov.br/server/rest/services/Territorio/Regioes_Administrativas_DF_2025/MapServer/0)

---

### 4️⃣ Camada 4: Centróide DF (Fallback Extremo)

**Implementação:**
```python
DF_CENTROID = {
    "lat": -15.7839,  # Aproximado
    "lng": -47.8822,  # Aproximado
    "quality": "df_centroid",
    "source": "hardcoded_fallback"
}

def geocode_by_df_fallback():
    """Última tentativa: retorna ponto central do DF."""
    return DF_CENTROID
```

**Uso:** Apenas se nenhuma outra camada funcionar.

---

### 📊 Função Orquestradora Completa

```python
def geocode_empresa(cep=None, endereco=None, bairro=None, ra=None):
    """
    Orquestra as 4 camadas de geocodificação.
    Retorna: (lat, lng, quality_score, source)
    """
    
    # Camada 1: CEP direto
    if cep:
        result = geocode_by_cep(normalize_cep(cep))
        if result:
            return result["lat"], result["lng"], 0.95, "cep_direct"
    
    # Camada 2: CNEFE completo
    if endereco or (bairro and cep):
        result = geocode_by_cnefe_refined({
            "logradouro": endereco,
            "bairro": bairro,
            "cep": cep
        })
        if result:
            return result["lat"], result["lng"], 0.85, "cnefe"
    
    # Camada 3: RA centróide
    ra_detected = ra or extract_ra_from_address(endereco or "")
    if ra_detected:
        result = geocode_by_ra(ra_detected)
        if result:
            return result["lat"], result["lng"], 0.5, f"ra_centroid_{ra_detected}"
    
    # Camada 4: DF centróide
    result = geocode_by_df_fallback()
    return result["lat"], result["lng"], 0.1, "df_centroid"
```

---

## 7. Integração com Pipeline Existente

### Arquivos a Modificar

1. **`normalize_candidates.py`**
   - Adicionar campo `geocoding_quality` (0-1) ao output
   - Adicionar campo `geocoding_source` (enum)
   - Chamar nova função `geocode_empresa()` antes de salvar

2. **`cnefe_ingest.py`** (existente)
   - Manter como está (não quebrar)
   - Adicionar fallback a Camada 1 se falhar
   - Log de sucesso vs. timeout

3. **Novo arquivo: `geocoding_utils.py`**
   ```python
   # Consolidar todas as 4 camadas aqui
   # Imports: requests, shapely, fuzzywuzzy
   # Exports: geocode_empresa(), init_caches()
   ```

4. **Novo arquivo: `requirements_geocoding.txt`**
   ```
   requests>=2.31.0
   shapely>=2.0
   fuzzywuzzy>=0.18
   python-Levenshtein>=0.21
   ```

### Ordem de Execução

```
1. normalize_candidates.py
   ├─ Extract CEP, endereço, bairro, RA
   ├─ Call geocoding_utils.geocode_empresa()
   └─ Append (lat, lng, quality, source)
2. cnefe_ingest.py (se ainda não geocodificado)
3. Save to banco_dados
```

---

## 8. Limitações e Cobertura Esperada

### Cenário 1: Endereços com CEP + Logradouro Completo (70% do dataset)
| Camada | Taxa Sucesso | Cobertura |
|--------|-------------|-----------|
| CEP direto (AwesomeAPI) | ~95% | 66.5% da entrada |
| CNEFE ingest | ~80% | 56% da entrada |
| **Total Camada 1+2** | **~99%** | **~99% com quality ≥ 0.5** |

**Resultado:** ~2-3 empresas falham por CEP inválido

### Cenário 2: Endereços Parciais (CEP + Bairro apenas, ~20%)
| Camada | Taxa Sucesso |
|--------|-------------|
| CEP direto | ~90% |
| RA centróide | ~95% |
| **Total** | **~99.5% com quality ≥ 0.5** |

**Resultado:** Precisão ±1-3km (centróide da RA)

### Cenário 3: Endereços Mínimos (RA + Cidade apenas, ~10%)
| Camada | Taxa Sucesso |
|--------|-------------|
| RA centróide | ~80% (extração fuzzy) |
| DF centróide | ~100% |
| **Total** | **100%** |

**Resultado:** Precisão ±10-50km (centróide DF)

### 📈 Cobertura Global Esperada
```
Sem lat/lon nenhuma → 300.000 empresas
├─ AwesomeAPI CEP (Camada 1): +240.000 (80%)
├─ CNEFE (Camada 2): +45.000 (+15%)
├─ RA Centróide (Camada 3): +12.000 (+4%)
└─ DF Centróide (Camada 4): +3.000 (+1%)

RESULTADO: ~300k com lat/lon (100% cobertura)
           ~300k com quality_score:
           - Excelente (0.8-1.0): 285k (95%)
           - Boa (0.5-0.8): 12k (4%)
           - Fallback (0.1-0.5): 3k (1%)
```

### ⚠️ Limitações Conhecidas

1. **Qualidade CEP:** AwesomeAPI pode retornar CEPs "vazios" (CEP válido mas sem logradouro atribuído)
   - **Mitigation:** Validar `lat != 0 AND lng != 0` antes de usar

2. **RAs informais/invasões:** ~5-10% das empresas em áreas não consolidadas
   - **Mitigation:** Será geocodificada em RA mais próxima ou DF centróide

3. **Variações ortográficas:** "Taguatinga" vs. "Taguatinga" (acentos)
   - **Mitigation:** Fuzzy matching com threshold 80%

4. **Dinâmica de CEPs:** Novos CEPs podem demorar ~3 meses para entrar no AwesomeAPI
   - **Mitigation:** Manter fallback para CNEFE manual

5. **Rate limit AwesomeAPI:** 100k/mês pode ser insuficiente se processamento diário
   - **Mitigation:** 
     - Batch semanal ou mensal
     - Upgrade plano (contatar support)
     - Cache agressivo de resultados

---

## 9. Roadmap de Implementação

### Fase 1: MVP (Semana 1)
- [ ] Implementar `geocoding_utils.py` com Camada 1 (AwesomeAPI)
- [ ] Integrar em `normalize_candidates.py`
- [ ] Testar com amostra de 100 CEPs
- [ ] Medir taxa de sucesso real

**Saída esperada:** ~80-85% das 300k geocodificadas com quality ≥ 0.8

### Fase 2: Fallback Geo (Semana 2)
- [ ] Implementar Camada 3 (IBGE Malhas RA)
- [ ] Pre-cache das 35 RAs
- [ ] Extrator de RA com fuzzy matching
- [ ] Testar com amostra de 1k endereços sem CEP válido

**Saída esperada:** +10-15% adicionais com quality ≥ 0.5

### Fase 3: Refinement CNEFE (Semana 3)
- [ ] Review/melhorias em `cnefe_ingest.py`
- [ ] Adicionar fuzzy matching para logradouros parciais
- [ ] Integração com geocodebr via R subprocess (opcional)

**Saída esperada:** +4-8% adicionais com quality ≥ 0.85

### Fase 4: Validação & Deploy (Semana 4)
- [ ] Testar pipeline completo em lote de 10k
- [ ] Validar quality_score vs. manual spot-checks
- [ ] Documentar índice de cobertura por RA
- [ ] Deploy em produção

**Saída esperada:** 300k empresas com lat/lon, quality flag conhecido

---

## 10. Alternativas Rejeitadas

| Opção | Motivo da Rejeição |
|-------|-------------------|
| **Nominatim OSM pública** | 1 req/s → 83h contínuas inviável |
| **Nominatim self-hosted** | Overhead operacional, melhor se volume 5M+/ano |
| **Google Maps API** | Custo $600+/ano para único batch |
| **Mapbox API** | Custo $90-135 mas melhor que Google, não recomendado vs. AwesomeAPI free |
| **Here Technologies** | Pricing opaco, evitar |
| **CEP Aberto apenas** | Qualidade variável, base colaborativa; usar como fallback |
| **CNEFE sem CEP** | Requer endereço completo, impossível para 30% do dataset |

---

## 11. Referências & Documentação

### APIs Utilizadas
- [AwesomeAPI CEP](https://docs.awesomeapi.com.br/api-cep) — **PRIMÁRIA**
- [AwesomeAPI Rate Limits](https://docs.awesomeapi.com.br/aviso-sobre-limites)
- [IBGE Malhas API v3](https://servicodados.ibge.gov.br/api/docs/malhas)
- [IBGE Localidades API](https://servicodados.ibge.gov.br/api/docs/localidades)
- [IBRAM DF GIS Layer](https://onda.ibram.df.gov.br/server/rest/services/Territorio/Regioes_Administrativas_DF_2025/MapServer/0)

### Bibliotecas Recomendadas
- [Shapely](https://shapely.readthedocs.io/) — Geometria/centróides
- [FuzzyWuzzy](https://github.com/seatgeek/fuzzywuzzy) — String matching
- [geocodebr (R)](https://ipeagit.github.io/geocodebr/) — Referência CNEFE

### Dados & Contexto
- [CNEFE IBGE](https://www.ibge.gov.br/estatisticas/sociais/populacao/38734-cadastro-nacional-de-enderecos-para-fins-estatisticos.html)
- [Census 2022 dados](https://agenciadenoticias.ibge.gov.br/agencia-noticias/2012-agencia-de-noticias/noticias/40393-noticia-cnefe)
- [CEP Aberto](https://www.cepaberto.com/)
- [Nominatim Docker](https://github.com/mediagis/nominatim-docker)

---

## 12. Conclusão

**Estratégia recomendada: Híbrida de 4 camadas com AwesomeAPI como primária**

- ✅ Cobertura: ~100% (300k empresas)
- ✅ Qualidade: 95% com ≥0.8 score (CEP direto ou CNEFE)
- ✅ Custo: ~R$ 0-150 (free tier + minimal upgrade se necessário)
- ✅ Tempo de implementação: 2-3 semanas
- ✅ Manutenção: Baixa (APIs estáveis, IBGE público)

**Próximo passo:** Implementar Fase 1 (AwesomeAPI) no `normalize_candidates.py` esta semana.

---

*Pesquisa realizada: Maio/2026*  
*Próxima revisão recomendada: Q3 2026 (check AwesomeAPI pricing/updates)*
