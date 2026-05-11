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
HTTP_MAX_RETRIES = int(os.environ.get("TRONIK_HTTP_MAX_RETRIES", "5"))
HTTP_BACKOFF_FACTOR = float(os.environ.get("TRONIK_HTTP_BACKOFF_FACTOR", "0.6"))

# --- Geofabrik OSM ---
GEOFABRIK_DEFAULT_PBF = os.environ.get(
    "TRONIK_GEOFABRIK_PBF_URL",
    "https://download.geofabrik.de/south-america/brazil/centro-oeste-latest.osm.pbf",
)

# --- Receita CNPJ (URLs completas OU base para descoberta) ---
RECEITA_CNPJ_ZIP_URLS = os.environ.get("TRONIK_RECEITA_CNPJ_ZIP_URLS", "")
# Bases oficiais candidatas (ordem: tentar HEAD até achar ZIPs)
RECEITA_CNPJ_BASE_URLS = os.environ.get(
    "TRONIK_RECEITA_CNPJ_BASE_URLS",
    "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/,"
    "https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/",
)

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
IBGE_MUNICIPIO_DF_IBGE = "5300108"  # Brasília

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
