"""URLs, pastas e parâmetros de robustez (env)."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw" / "prospeccao"
RAW_DIR = Path(os.environ.get("TRONIK_PROSPECCAO_RAW_DIR", str(DEFAULT_RAW_DIR))).resolve()

# --- CKAN DF ---
CKAN_BASE_URL = os.environ.get("TRONIK_CKAN_DF_URL", "https://dados.df.gov.br").rstrip("/")
CKAN_ROWS_PER_PAGE = int(os.environ.get("TRONIK_CKAN_ROWS", "100"))
CKAN_PAGE_SLEEP_S = float(os.environ.get("TRONIK_CKAN_PAGE_SLEEP_S", "0.35"))

# --- HTTP ---
HTTP_USER_AGENT = os.environ.get(
    "TRONIK_HTTP_USER_AGENT",
    "Dashboard-TRONIK-prospeccao/0.2 (+https://github.com/natanheringer/Dashboard-TRONIK)",
)
HTTP_TIMEOUT_S = int(os.environ.get("TRONIK_HTTP_TIMEOUT", "180"))
HTTP_CONNECT_TIMEOUT_S = float(os.environ.get("TRONIK_HTTP_CONNECT_TIMEOUT", "10"))
HTTP_READ_TIMEOUT_S = float(os.environ.get("TRONIK_HTTP_READ_TIMEOUT", str(HTTP_TIMEOUT_S)))
HTTP_MAX_RETRIES = int(os.environ.get("TRONIK_HTTP_MAX_RETRIES", "5"))
HTTP_BACKOFF_FACTOR = float(os.environ.get("TRONIK_HTTP_BACKOFF_FACTOR", "0.6"))
LINK_CHECK_TIMEOUT_S = int(os.environ.get("TRONIK_LINK_CHECK_TIMEOUT", "25"))
DOWNLOAD_PROGRESS_EVERY_MB = int(os.environ.get("TRONIK_DOWNLOAD_PROGRESS_EVERY_MB", "25"))
DOWNLOAD_MAX_SECONDS = int(os.environ.get("TRONIK_DOWNLOAD_MAX_SECONDS", "0"))

# --- Geofabrik OSM ---
GEOFABRIK_DEFAULT_PBF = os.environ.get(
    "TRONIK_GEOFABRIK_PBF_URL",
    "https://download.geofabrik.de/south-america/brazil/centro-oeste-latest.osm.pbf",
)

# --- Receita CNPJ (URLs completas OU base para descoberta) ---
RECEITA_CNPJ_ZIP_URLS = os.environ.get("TRONIK_RECEITA_CNPJ_ZIP_URLS", "")
# Bases oficiais + CDN mirror (ordem: tentar HEAD até achar ZIPs)
RECEITA_CNPJ_BASE_URLS = os.environ.get(
    "TRONIK_RECEITA_CNPJ_BASE_URLS",
    "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/,"
    "https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/,"
    "https://dados-abertos-rf-cnpj.casadosdados.com.br/arquivos/",
)
RECEITA_CSV_ENCODING = "latin-1"
RECEITA_CSV_SEPARATOR = ";"

# Receita situacao_cadastral code -> description
RECEITA_SITUACAO_MAP: dict[str, str] = {
    "01": "NULA", "02": "ATIVA", "03": "SUSPENSA", "04": "INAPTA", "08": "BAIXADA",
}
# Receita porte code -> description
RECEITA_PORTE_MAP: dict[str, str] = {
    "00": "Nao informado", "01": "Microempresa", "03": "Empresa de Pequeno Porte", "05": "Demais",
}

# --- CNEFE 2022 (IBGE geocoding reference — full address + coordinates) ---
# Arquivos_CNEFE has CEP, logradouro, numero, lat, lon per address.
CNEFE_BASE = os.environ.get(
    "TRONIK_CNEFE_BASE",
    "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/"
    "Censo_Demografico_2022/Arquivos_CNEFE/CSV/UF/",
)
CNEFE_FILES: dict[str, str] = {
    "DF": "53_DF.zip",   # 19 MB
    "GO": "52_GO.zip",   # 115 MB
}

# --- INEP Censo Escolar ---
INEP_CENSO_ESCOLAR_CSV_URL = os.environ.get("TRONIK_INEP_CENSO_ESCOLAR_CSV_URL", "")
INEP_CENSO_ESCOLAR_YEAR = os.environ.get("TRONIK_INEP_CENSO_ESCOLAR_YEAR", "2024")
INEP_MICRODADOS_BASE = os.environ.get(
    "TRONIK_INEP_MICRODADOS_BASE",
    "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{year}.zip",
)

# --- CNES ---
CNES_BASE_ZIP_URL = os.environ.get("TRONIK_CNES_BASE_ZIP_URL", "")

# --- PNCP: gestão (Swagger pncp/v1) vs consultas públicas ---
PNCP_API_BASE = os.environ.get("TRONIK_PNCP_API_BASE", "https://pncp.gov.br/api/pncp/v1").rstrip("/")
PNCP_CONSULTA_BASE = os.environ.get(
    "TRONIK_PNCP_CONSULTA_BASE",
    "https://pncp.gov.br/api/consulta/v1",
).rstrip("/")

# --- IBGE ---
IBGE_API_BASE = os.environ.get("TRONIK_IBGE_API_BASE", "https://servicodados.ibge.gov.br/api/v1").rstrip("/")
IBGE_UF_DF = "53"
IBGE_UF_GO = "52"
IBGE_MUNICIPIO_DF_IBGE = "5300108"  # Brasília

# RIDE — Região Integrada de Desenvolvimento do DF e Entorno (LC 94/1998).
# 29 municípios de Goiás + Brasília/DF.  IBGE codes fetched 2026-05.
RIDE_ENTORNO_MUNICIPIOS: dict[int, str] = {
    5200100: "Abadiânia",
    5200175: "Água Fria de Goiás",
    5200258: "Águas Lindas de Goiás",
    5200308: "Alexânia",
    5200605: "Alto Paraíso de Goiás",
    5200803: "Alvorada do Norte",
    5203203: "Barro Alto",
    5204003: "Cabeceiras",
    5205307: "Cavalcante",
    5205497: "Cidade Ocidental",
    5205513: "Cocalzinho de Goiás",
    5205802: "Corumbá de Goiás",
    5206206: "Cristalina",
    5207907: "Flores de Goiás",
    5208004: "Formosa",
    5208608: "Goianésia",
    5212501: "Luziânia",
    5213053: "Mimoso de Goiás",
    5214606: "Niquelândia",
    5215231: "Novo Gama",
    5215603: "Padre Bernardo",
    5217302: "Pirenópolis",
    5217609: "Planaltina",
    5219753: "Santo Antônio do Descoberto",
    5220009: "São João d'Aliança",
    5220686: "Simolândia",
    5221858: "Valparaíso de Goiás",
    5222203: "Vila Boa",
    5222302: "Vila Propício",
}

# Subset most likely within logistics reach (inner ring, <60 km from Plano Piloto)
ENTORNO_INNER_RING: set[int] = {
    5221858,  # Valparaíso de Goiás
    5215231,  # Novo Gama
    5205497,  # Cidade Ocidental
    5219753,  # Santo Antônio do Descoberto
    5200258,  # Águas Lindas de Goiás
    5217609,  # Planaltina (GO)
    5208004,  # Formosa
    5212501,  # Luziânia
    5215603,  # Padre Bernardo
    5205513,  # Cocalzinho de Goiás
    5200308,  # Alexânia
}

# --- ANEEL (consumidores livres — proxy de porte operacional) ---
ANEEL_CONSUMIDORES_URL = os.environ.get("TRONIK_ANEEL_CONSUMIDORES_URL", "")

# --- IBRAM/SEMA-DF (cadastro de geradores de resíduos perigosos) ---
IBRAM_GERADORES_URL = os.environ.get("TRONIK_IBRAM_GERADORES_URL", "")

# --- IBAMA CTF/APP (pessoas jurídicas inscritas no CTF/APP — CSV por UF) ---
# TRONIK_IBAMA_CTF_UFS — UFs separadas por vírgula para `ibama-ctf` e harvest step `ibama_ctf`
#   (default DF,GO; fonte: http://dadosabertos.ibama.gov.br/dados/CTF/APP/{UF}/pessoasJuridicas.csv)
IBAMA_CTF_DEFAULT_UFS = os.environ.get("TRONIK_IBAMA_CTF_UFS", "DF,GO")

# --- Brasil API (free CNPJ enrichment, no auth required) ---
BRASILAPI_BASE = os.environ.get(
    "TRONIK_BRASILAPI_BASE",
    "https://brasilapi.com.br/api/cnpj/v1",
)
BRASILAPI_SLEEP_S = float(os.environ.get("TRONIK_BRASILAPI_SLEEP_S", "0.4"))
BRASILAPI_BATCH_SIZE = int(os.environ.get("TRONIK_BRASILAPI_BATCH", "500"))

# --- Casa dos Dados API v5 (targeted CNPJ search, requires API key) ---
# Get your key at https://portal.casadosdados.com.br/plataforma/api/chave
CASADOSDADOS_API_BASE = os.environ.get(
    "TRONIK_CASADOSDADOS_API_BASE",
    "https://api.casadosdados.com.br/v5/cnpj/pesquisa",
)
CASADOSDADOS_API_KEY = os.environ.get("TRONIK_CASADOSDADOS_API_KEY", "")
CASADOSDADOS_PAGE_SLEEP_S = float(os.environ.get("TRONIK_CASADOSDADOS_PAGE_SLEEP_S", "1.2"))
CASADOSDADOS_LIMIT_PER_PAGE = int(os.environ.get("TRONIK_CASADOSDADOS_LIMIT", "1000"))
CASADOSDADOS_MAX_PAGES_PER_QUERY = int(os.environ.get("TRONIK_CASADOSDADOS_MAX_PAGES", "50"))

# Proximity tiers from Recanto das Emas (sede TRONIK)
# Tier 1: Recanto + adjacent RAs (< 10 km)
SEDE_TIER_1: list[str] = [
    "RECANTO DAS EMAS", "SAMAMBAIA", "RIACHO FUNDO II", "RIACHO FUNDO",
]
# Tier 2: Near RAs (10-20 km)
SEDE_TIER_2: list[str] = [
    "TAGUATINGA", "CEILANDIA", "GAMA", "SANTA MARIA",
    "AGUAS CLARAS", "VICENTE PIRES", "ARNIQUEIRA",
]
# Tier 3: Rest of DF (20+ km)
SEDE_TIER_3: list[str] = [
    "PLANO PILOTO", "ASA SUL", "ASA NORTE", "LAGO SUL", "LAGO NORTE",
    "GUARA", "CRUZEIRO", "SUDOESTE", "OCTOGONAL", "NOROESTE",
    "NUCLEO BANDEIRANTE", "CANDANGOLANDIA", "PARK WAY",
    "SAO SEBASTIAO", "JARDIM BOTANICO", "ITAPOA",
    "PARANOA", "PLANALTINA", "SOBRADINHO", "SOBRADINHO II",
    "BRAZLANDIA", "FERCAL", "SIA", "SCIA", "ESTRUTURAL",
    "SOL NASCENTE", "POR DO SOL", "VARJAO",
]

# --- Geoportal / ArcGIS (RA DF — serviços públicos comuns) ---
# Pode sobrescrever por camada oficial preferida do IDE-DF / SISDIA / IBRAM
GEOPORTAL_RA_FEATURE_URL = os.environ.get(
    "TRONIK_GEOPORTAL_RA_FEATURE_URL",
    "https://onda.ibram.df.gov.br/server/rest/services/Territorio/Regioes_Administrativas_DF_2025/FeatureServer/0",
)

# Timeout mais curto para camadas ArcGIS (evita bloqueio longo em retry)
GEOPORTAL_TIMEOUT_S = int(os.environ.get("TRONIK_GEOPORTAL_TIMEOUT_S", "90"))

# Organizações CKAN do DF frequentemente úteis (slug pode mudar; ajustável)
DEFAULT_CKAN_ORGS = os.environ.get(
    "TRONIK_CKAN_DEFAULT_ORGS",
    "slu,secretaria-de-saude,seduc,detran-der,jucis-df",
).split(",")
