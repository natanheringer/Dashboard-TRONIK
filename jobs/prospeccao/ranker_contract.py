"""Shared feature contract for the REE prospection ranker.

v3.1: listwise qid fallbacks (CEP5, CNAE4, municipio) + equal-frequency rank labels
in build-features (see jobs/prospeccao/build_features.py).

v3: same 17-feature vector as v2; geo-first qid + quantile labels (superseded by v3.1).

v2: continuous signals, secondary CNAE scoring, neighborhood density,
exponential distance decay, monotonic constraint map for XGBRanker.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from typing import Any

FEATURE_NAMES = [
    "cnae_ree_fit",
    "cnae_secondary_max_fit",
    "cnae_secondary_hit_count",
    "porte_ordinal",
    "active_status",
    "contact_richness",
    "data_completeness",
    "address_quality",
    "logistics_proximity_exp",
    "age_years_log",
    "public_proxy_fit",
    "is_df_proper",
    "is_entorno_inner",
    "neighborhood_candidate_density",
    "neighborhood_ree_ratio",
    "has_geocode",
]

FEATURE_SCHEMA_VERSION = "prospeccao-ree-v3.1"

# Monotonic constraints for XGBRanker (index-aligned with FEATURE_NAMES).
# 1 = increasing is always better; 0 = let the tree decide.
MONOTONIC_CONSTRAINTS = (
    1,   # cnae_ree_fit
    1,   # cnae_secondary_max_fit
    1,   # cnae_secondary_hit_count
    1,   # porte_ordinal
    1,   # active_status
    1,   # contact_richness
    1,   # data_completeness
    1,   # address_quality
    1,   # logistics_proximity_exp
    0,   # age_years_log — young startups in tech may outperform established companies
    0,   # public_proxy_fit — context-dependent
    0,   # is_df_proper — tree decides DF vs Entorno tradeoff
    0,   # is_entorno_inner — tree decides inner ring value
    0,   # neighborhood_candidate_density — saturation effects
    0,   # neighborhood_ree_ratio — not always monotonic
    1,   # has_geocode — better to have confirmed coordinates
)

SEDE_LAT = float(os.getenv("TRONIK_SEDE_LAT", "-15.7942"))
SEDE_LNG = float(os.getenv("TRONIK_SEDE_LNG", "-47.8822"))

REE_CNAE_PREFIX_WEIGHTS: dict[str, float] = {
    "4651": 1.00,  # atacado de computadores/perifericos
    "4652": 1.00,  # atacado de componentes eletronicos
    "4751": 0.95,  # varejo de computadores/perifericos
    "4752": 0.90,  # varejo de eletrodomesticos
    "4742": 0.75,  # material eletrico
    "4744": 0.72,  # varejo ferramentas / material elétrico (CNAE 4744-00/02)
    "4530": 0.58,  # comércio atacadista de equipamentos de informática
    "620": 0.70,  # desenvolvimento/consultoria TI
    "631": 0.65,  # tratamento de dados/hosting
    "9511": 1.00,  # reparacao de computadores
    "9512": 0.95,  # reparacao de comunicacao
    "9521": 0.82,  # reparacao e manutencao de eletrodomesticos
    "859": 0.35,  # educacao profissional / laboratorios
    "861": 0.30,  # hospitais — proxy territorial
}

_GENERIC_EMAIL_DOMAINS = frozenset({
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.com.br",
    "bol.com.br", "uol.com.br", "terra.com.br", "ig.com.br", "live.com",
})

_FEATURE_LABELS: dict[str, str] = {
    "cnae_ree_fit": "Primary CNAE compatible with electronics/e-waste",
    "cnae_secondary_max_fit": "Secondary CNAE matches REE activity",
    "cnae_secondary_hit_count": "Multiple secondary CNAEs in REE sector",
    "porte_ordinal": "Business size suggests operational volume",
    "active_status": "Company registration is active",
    "contact_richness": "Contact channels available (email/phone quality)",
    "data_completeness": "Rich data profile available for assessment",
    "address_quality": "Address data is usable and well-resolved",
    "logistics_proximity_exp": "Close to Tronik logistics base",
    "age_years_log": "Established operating history",
    "public_proxy_fit": "Public/context proxy supports REE fit",
    "is_df_proper": "Located inside Distrito Federal (not Entorno)",
    "is_entorno_inner": "Located in inner-ring Entorno (Valparaíso, Novo Gama, etc.)",
    "neighborhood_candidate_density": "Located in area with many candidate businesses",
    "neighborhood_ree_ratio": "Area has high concentration of REE-compatible businesses",
    "has_geocode": "Geocoding coordinates are available",
}

_AGE_LOG_CAP = math.log1p(40)  # ~3.71 — normalizes age_years_log to 0-1


def feature_schema() -> list[dict[str, str]]:
    return [
        {"name": name, "type": "float", "version": FEATURE_SCHEMA_VERSION}
        for name in FEATURE_NAMES
    ]


# ---------------------------------------------------------------------------
# Individual feature functions
# ---------------------------------------------------------------------------

def sanitize_cnae(cnae: str | None) -> str:
    return "".join(ch for ch in (cnae or "") if ch.isalnum())


def cnae_ree_fit(cnae: str | None) -> float:
    value = sanitize_cnae(cnae)
    for prefix, weight in REE_CNAE_PREFIX_WEIGHTS.items():
        if value.startswith(prefix):
            return weight
    return 0.0


def cnae_secondary_scores(cnae_secundarios_json: str | None) -> tuple[float, float]:
    """Return (max_fit, normalized_hit_count) across secondary CNAEs."""
    if not cnae_secundarios_json:
        return 0.0, 0.0
    try:
        cnaes = json.loads(cnae_secundarios_json)
    except (json.JSONDecodeError, TypeError):
        return 0.0, 0.0
    if not isinstance(cnaes, list) or not cnaes:
        return 0.0, 0.0
    max_fit = 0.0
    hits = 0
    for raw in cnaes:
        score = cnae_ree_fit(str(raw))
        if score > 0:
            hits += 1
            max_fit = max(max_fit, score)
    normalized = math.log1p(hits) / math.log1p(20) if hits else 0.0
    return max_fit, min(normalized, 1.0)


def porte_ordinal(porte: str | None) -> float:
    """Continuous 0-1 scale letting XGBoost find optimal split points."""
    value = (porte or "").strip().lower()
    if value == "mei" or "microempreendedor" in value:
        return 0.15
    if "micro" in value or value == "me":
        return 0.35
    if "pequeno" in value or "epp" in value:
        return 0.55
    if any(tok in value for tok in ("medio", "médio")):
        return 0.75
    if any(tok in value for tok in ("grande", "demais")):
        return 1.0
    return 0.40


def active_status(situacao: str | None) -> float:
    value = (situacao or "").strip().lower()
    return 1.0 if "ativa" in value or "ativo" in value else 0.0


def contact_richness(email: str | None, telefone: str | None) -> float:
    """Granular contactability — rewards business-domain emails over generic webmail."""
    has_email = bool(email and "@" in email)
    has_phone = bool(telefone and len(telefone.strip()) >= 8)
    if not has_email and not has_phone:
        return 0.0
    if has_phone and not has_email:
        return 0.30
    domain = (email.rsplit("@", 1)[-1].strip().lower()) if email else ""
    is_business = domain and domain not in _GENERIC_EMAIL_DOMAINS
    if has_email and not has_phone:
        return 0.60 if is_business else 0.45
    return 1.0 if is_business else 0.85


def data_completeness(empresa: Any, local: Any | None) -> float:
    """Fraction of important fields that are non-null / non-empty."""
    checks = [
        bool(getattr(empresa, "cnae_principal", None)),
        bool(getattr(empresa, "porte", None)),
        bool(getattr(empresa, "email", None)),
        bool(getattr(empresa, "telefone", None)),
        bool(getattr(empresa, "bairro", None)),
        bool(getattr(empresa, "cep", None)),
        bool(getattr(empresa, "endereco_normalizado", None)),
        bool(getattr(empresa, "situacao_cadastral", None)),
        bool(getattr(empresa, "natureza_juridica", None)),
    ]
    if local:
        checks.extend([
            getattr(local, "latitude", None) is not None,
            getattr(local, "longitude", None) is not None,
            bool(getattr(local, "ra", None)),
            bool(getattr(local, "cep", None)),
        ])
    return sum(checks) / len(checks) if checks else 0.0


def address_quality(local: Any | None, empresa: Any | None = None) -> float:
    """Composite address quality: geocode confidence + structural fields present."""
    score = 0.0
    total = 4.0
    if local:
        score += float(getattr(local, "geocode_quality", None) or 0.0)
        score += 1.0 if getattr(local, "cep", None) else 0.0
        score += 1.0 if getattr(local, "ra", None) else 0.0
        score += 1.0 if getattr(local, "endereco", None) else 0.0
    elif empresa:
        score += 1.0 if getattr(empresa, "cep", None) else 0.0
        score += 1.0 if getattr(empresa, "bairro", None) else 0.0
        score += 1.0 if getattr(empresa, "endereco_normalizado", None) else 0.0
    return score / total


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def logistics_proximity(latitude: float | None, longitude: float | None) -> float:
    """Linear decay — 0 at 60 km."""
    if latitude is None or longitude is None:
        return 0.35
    km = haversine_km(SEDE_LAT, SEDE_LNG, float(latitude), float(longitude))
    return max(0.0, min(1.0, 1 - (km / 60.0)))


def logistics_proximity_exp(latitude: float | None, longitude: float | None) -> float:
    """Exponential decay — more realistic distance penalty than linear."""
    if latitude is None or longitude is None:
        return 0.25
    km = haversine_km(SEDE_LAT, SEDE_LNG, float(latitude), float(longitude))
    return math.exp(-km / 25.0)


def age_years_log(data_abertura: datetime | None) -> float:
    """log(1 + years) — continuous signal for tree-based models."""
    if not data_abertura:
        return 0.0
    years = max(0.0, (datetime.utcnow() - data_abertura).days / 365.25)
    return round(math.log1p(years), 4)


def public_proxy_fit(categoria_operacional: str | None, ra: str | None) -> float:
    category = (categoria_operacional or "").strip().lower()
    if any(tok in category for tok in ("ti", "eletron", "eletro", "assistencia", "shopping")):
        return 0.85
    if any(tok in category for tok in ("escola", "saude", "saúde", "orgao", "órgão")):
        return 0.45
    return 0.30 if ra else 0.15


def geography_flags(uf: str | None, municipio_ibge: int | None = None) -> tuple[float, float]:
    """Return (is_df_proper, is_entorno_inner).

    Lets XGBoost learn the DF-vs-Entorno tradeoff without hardcoding a penalty.
    """
    from jobs.prospeccao import config

    is_df = 1.0 if (uf or "").strip().upper() == "DF" else 0.0
    is_inner = 0.0
    if municipio_ibge and municipio_ibge in config.ENTORNO_INNER_RING:
        is_inner = 1.0
    elif municipio_ibge and municipio_ibge in config.RIDE_ENTORNO_MUNICIPIOS:
        is_inner = 0.5
    return is_df, is_inner


def neighborhood_features(qid_total: int, qid_ree_compatible: int) -> tuple[float, float]:
    """Return (density_log_normalized, ree_ratio).

    density: log(1+n)/log(1+500) caps at ~500 candidates per group.
    ree_ratio: fraction of REE-compatible businesses in the group.
    """
    density = math.log1p(qid_total) / math.log1p(500) if qid_total > 0 else 0.0
    ree_ratio = qid_ree_compatible / qid_total if qid_total > 0 else 0.0
    return min(density, 1.0), ree_ratio


# ---------------------------------------------------------------------------
# Vector assembly
# ---------------------------------------------------------------------------

NeighborhoodContext = dict[str, int]


def build_feature_vector(
    empresa: Any,
    local: Any | None,
    neighborhood: NeighborhoodContext | None = None,
) -> dict[str, float]:
    neighborhood = neighborhood or {}
    sec_max, sec_hits = cnae_secondary_scores(
        getattr(empresa, "cnae_secundarios_json", None),
    )
    neigh_density, neigh_ree = neighborhood_features(
        neighborhood.get("qid_total", 0),
        neighborhood.get("qid_ree_compatible", 0),
    )
    uf = getattr(empresa, "uf", None)
    municipio_ibge = getattr(empresa, "municipio_ibge", None) or getattr(local, "municipio_ibge", None)
    is_df, is_inner = geography_flags(uf, municipio_ibge)
    has_coords = (
        getattr(local, "latitude", None) is not None
        and getattr(local, "longitude", None) is not None
    )
    return {
        "cnae_ree_fit": cnae_ree_fit(getattr(empresa, "cnae_principal", None)),
        "cnae_secondary_max_fit": sec_max,
        "cnae_secondary_hit_count": sec_hits,
        "porte_ordinal": porte_ordinal(getattr(empresa, "porte", None)),
        "active_status": active_status(getattr(empresa, "situacao_cadastral", None)),
        "contact_richness": contact_richness(
            getattr(empresa, "email", None),
            getattr(empresa, "telefone", None),
        ),
        "data_completeness": data_completeness(empresa, local),
        "address_quality": address_quality(local, empresa),
        "logistics_proximity_exp": logistics_proximity_exp(
            getattr(local, "latitude", None),
            getattr(local, "longitude", None),
        ),
        "age_years_log": age_years_log(getattr(empresa, "data_abertura", None)),
        "public_proxy_fit": public_proxy_fit(
            getattr(local, "categoria_operacional", None),
            getattr(local, "ra", None),
        ),
        "is_df_proper": is_df,
        "is_entorno_inner": is_inner,
        "neighborhood_candidate_density": neigh_density,
        "neighborhood_ree_ratio": neigh_ree,
        "has_geocode": 1.0 if has_coords else 0.0,
    }


# ---------------------------------------------------------------------------
# Listwise query id (LTR groups) — geography-first to avoid monolithic "df"
# ---------------------------------------------------------------------------


def _cep5_digits(empresa: Any, local: Any | None) -> str:
    raw = ""
    if local is not None:
        raw = getattr(local, "cep", None) or ""
    if not raw:
        raw = getattr(empresa, "cep", None) or ""
    digits = "".join(c for c in str(raw) if c.isdigit())
    return digits[:5] if len(digits) >= 5 else ""


def _bairro_key(empresa: Any, local: Any | None) -> str | None:
    b = getattr(empresa, "bairro", None) or (getattr(local, "bairro", None) if local else None)
    if not b:
        return None
    return str(b).strip().lower()[:100]


def _municipio_key(empresa: Any) -> str | None:
    m = getattr(empresa, "municipio", None)
    if not m:
        return None
    s = str(m).strip().lower()
    return s[:100] if s else None


def listwise_training_qid(empresa: Any, local: Any | None) -> str:
    """Stable LTR group: geo → RA → normalize qid → UF rules → bairro → CEP → CNAE.

    Avoids putting almost the entire base in a single `df` bucket when coords/RA are missing.
    """
    lat = lon = None
    if local is not None:
        lat = getattr(local, "latitude", None)
        lon = getattr(local, "longitude", None)
    if lat is not None and lon is not None:
        try:
            return f"geo:{round(float(lat), 2)}:{round(float(lon), 2)}"
        except (TypeError, ValueError):
            pass
    if local is not None and getattr(local, "ra", None):
        return f"ra:{str(local.ra).strip().lower()}"
    if local is not None and getattr(local, "qid", None):
        q = str(local.qid).strip()
        if q and q.lower() not in ("df", "entorno"):
            return q
    uf = (getattr(empresa, "uf", None) or "").strip().upper()
    if uf == "GO":
        municipio = getattr(empresa, "municipio", None) or (
            getattr(local, "bairro", None) if local else None
        )
        if municipio:
            return f"entorno:{str(municipio).strip().lower()}"
        return "entorno"
    mun = _municipio_key(empresa) or "sem_municipio"
    bk = _bairro_key(empresa, local)
    if bk:
        return f"bairro:{mun}:{bk}"
    cep5 = _cep5_digits(empresa, local)
    if cep5:
        return f"cep5:{mun}:{cep5}"
    cnae = sanitize_cnae(getattr(empresa, "cnae_principal", None))[:4]
    if len(cnae) >= 4:
        return f"cnae4:{mun}:{cnae}"
    return f"df:{mun}"


# ---------------------------------------------------------------------------
# Heuristic helpers (bootstrap labels / fallback scorer)
# ---------------------------------------------------------------------------


def heuristic_relevance_continuous(features: dict[str, float]) -> float:
    """Unbounded-ish domain expert score; use quantile binning for LTR labels."""
    age_norm = min(features.get("age_years_log", 0.0) / _AGE_LOG_CAP, 1.0)
    geo_bonus = features.get("is_df_proper", 0) * 0.03 + features.get("is_entorno_inner", 0) * 0.02
    return (
        features.get("cnae_ree_fit", 0) * 0.20
        + features.get("cnae_secondary_max_fit", 0) * 0.08
        + features.get("cnae_secondary_hit_count", 0) * 0.03
        + features.get("porte_ordinal", 0) * 0.09
        + features.get("active_status", 0) * 0.04
        + features.get("contact_richness", 0) * 0.09
        + features.get("data_completeness", 0) * 0.05
        + features.get("address_quality", 0) * 0.05
        + features.get("logistics_proximity_exp", 0) * 0.08
        + age_norm * 0.04
        + features.get("public_proxy_fit", 0) * 0.11
        + features.get("neighborhood_ree_ratio", 0) * 0.03
        + features.get("neighborhood_candidate_density", 0) * 0.02
        + features.get("has_geocode", 0) * 0.02
        + geo_bonus
    )


def heuristic_relevance_label(features: dict[str, float]) -> int:
    """Coarse 0–3 ordinal (legacy thresholds); prefer quantile labels in build-features."""
    score = heuristic_relevance_continuous(features)
    if score >= 0.75:
        return 3
    if score >= 0.52:
        return 2
    if score >= 0.32:
        return 1
    return 0


def heuristic_score(features: dict[str, float]) -> float:
    label = heuristic_relevance_label(features)
    age_norm = min(features.get("age_years_log", 0.0) / _AGE_LOG_CAP, 1.0)
    vals = [features.get(n, 0.0) for n in FEATURE_NAMES if n != "age_years_log"]
    vals.append(age_norm)
    avg = sum(vals) / len(vals) if vals else 0.0
    return round((avg * 70) + (label * 10), 4)


def top_reasons(
    features: dict[str, float],
    shap_values: dict[str, float] | None = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Feature-importance explanations. Uses SHAP values when available."""
    if shap_values:
        ranked = sorted(shap_values.items(), key=lambda item: abs(item[1]), reverse=True)
        return [
            {
                "feature": name,
                "reason": _FEATURE_LABELS.get(name, name),
                "value": round(float(features.get(name, 0)), 4),
                "shap": round(float(val), 4),
            }
            for name, val in ranked[:limit]
        ]
    ranked = sorted(features.items(), key=lambda item: item[1], reverse=True)
    return [
        {"feature": name, "reason": _FEATURE_LABELS.get(name, name), "value": round(float(value), 4)}
        for name, value in ranked[:limit]
    ]
