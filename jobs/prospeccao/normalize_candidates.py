"""Post-parse normalization: dedup, geocode, RA assignment, qid generation.

Run after receita_parse has populated empresa_candidata + local_candidato.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from banco_dados.modelos import EmpresaCandidata, LocalCandidato
from jobs.prospeccao import config
from jobs.prospeccao import paths as pathutil

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CNEFE geocoding
# ---------------------------------------------------------------------------

def _normalize_logradouro(raw: str) -> str:
    s = raw.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s)
    return s


def geocode_candidates(db: Session, cnefe_dir: Path | None = None) -> dict[str, int]:
    """Geocode local_candidato rows that lack lat/lon using CNEFE lookup."""
    from jobs.prospeccao.cnefe_ingest import build_cnefe_lookup, geocode_address

    lookup = build_cnefe_lookup(cnefe_dir)
    if not lookup:
        logger.warning("CNEFE lookup is empty — skipping geocoding")
        return {"geocoded": 0, "already_had_coords": 0, "no_match": 0}

    stats = {"geocoded": 0, "already_had_coords": 0, "no_match": 0}
    locais = db.query(LocalCandidato).filter(
        LocalCandidato.latitude.is_(None) | LocalCandidato.longitude.is_(None),
    ).all()

    for local in locais:
        empresa = local.empresa
        cep = local.cep or (empresa.cep if empresa else None)
        logradouro = local.endereco or (empresa.endereco_normalizado if empresa else None)
        numero = _extract_numero(logradouro)

        result = geocode_address(lookup, cep, logradouro, numero)
        if result:
            local.latitude, local.longitude, local.geocode_quality = result
            stats["geocoded"] += 1
        else:
            stats["no_match"] += 1

    already = db.query(func.count(LocalCandidato.id)).filter(
        LocalCandidato.latitude.isnot(None),
        LocalCandidato.longitude.isnot(None),
    ).scalar() or 0
    stats["already_had_coords"] = already

    db.flush()
    logger.info("Geocoding: %s", stats)
    return stats


def _extract_numero(endereco: str | None) -> str | None:
    """Try to extract the street number from an address string."""
    if not endereco:
        return None
    m = re.search(r"(?:,\s*|\s)(\d{1,6})(?:\s|,|$)", endereco)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# RA point-in-polygon assignment
# ---------------------------------------------------------------------------

def _load_ra_polygons(geojson_path: Path) -> list[tuple[str, Any]]:
    """Load RA polygons from the geoportal GeoJSON.

    Returns list of (ra_name, shapely_geometry).
    """
    try:
        from shapely.geometry import shape
    except ImportError:
        logger.warning("shapely not installed — RA assignment will be skipped")
        return []

    if not geojson_path.exists():
        logger.warning("RA GeoJSON not found: %s", geojson_path)
        return []

    with open(geojson_path, encoding="utf-8") as f:
        fc = json.load(f)

    polygons: list[tuple[str, Any]] = []
    for feat in fc.get("features", []):
        props = feat.get("properties", {})
        ra_name = (
            props.get("ra")
            or props.get("RA")
            or props.get("nome")
            or props.get("NOME")
            or props.get("NM_RA")
            or props.get("nm_ra")
            or ""
        )
        if not ra_name:
            continue
        try:
            geom = shape(feat["geometry"])
            polygons.append((ra_name.strip(), geom))
        except Exception:
            logger.debug("Could not parse geometry for RA %s", ra_name)

    logger.info("Loaded %d RA polygons", len(polygons))
    return polygons


def _point_in_ra(lat: float, lon: float, polygons: list[tuple[str, Any]]) -> str | None:
    """Return the RA name that contains the point, or None."""
    from shapely.geometry import Point

    pt = Point(lon, lat)
    for ra_name, geom in polygons:
        if geom.contains(pt):
            return ra_name
    return None


def assign_ra(db: Session, geojson_path: Path | None = None) -> dict[str, int]:
    """Assign RA to local_candidato rows with coordinates but no RA."""
    dirs = pathutil.ensure_raw_layout()
    if geojson_path is None:
        geojson_path = dirs["geoportal"] / "regioes_administrativas.geojson"

    polygons = _load_ra_polygons(geojson_path)
    if not polygons:
        return {"assigned": 0, "no_coords": 0, "outside_df": 0}

    stats = {"assigned": 0, "no_coords": 0, "outside_df": 0}
    locais = db.query(LocalCandidato).filter(
        LocalCandidato.ra.is_(None),
        LocalCandidato.latitude.isnot(None),
        LocalCandidato.longitude.isnot(None),
    ).all()

    for local in locais:
        ra = _point_in_ra(local.latitude, local.longitude, polygons)
        if ra:
            local.ra = ra
            stats["assigned"] += 1
        else:
            stats["outside_df"] += 1

    db.flush()
    logger.info("RA assignment: %s", stats)
    return stats


# ---------------------------------------------------------------------------
# QID generation
# ---------------------------------------------------------------------------

_RIDE_NAMES_LOWER: set[str] = {
    name.lower() for name in config.RIDE_ENTORNO_MUNICIPIOS.values()
}


def assign_qid(db: Session) -> dict[str, int]:
    """Assign qid to local_candidato rows that lack one.

    Rules:
      - DF candidates with RA: qid = "ra:<ra_lower>"
      - GO Entorno candidates: qid = "entorno:<municipio_lower>"
      - DF candidates without RA: qid = "bairro:<bairro_lower>" or "df"
    """
    stats = {"assigned": 0, "already_had": 0}
    locais = db.query(LocalCandidato).filter(LocalCandidato.qid.is_(None)).all()

    for local in locais:
        empresa = local.empresa
        uf = (empresa.uf if empresa else "").strip().upper()
        qid = None

        if local.ra:
            qid = f"ra:{local.ra.lower()}"
        elif uf == "GO":
            municipio = empresa.municipio if empresa else None
            if municipio:
                qid = f"entorno:{municipio.strip().lower()}"
            else:
                qid = "entorno"
        elif local.bairro:
            qid = f"bairro:{local.bairro.lower()}"
        else:
            qid = "df"

        local.qid = qid
        stats["assigned"] += 1

    db.flush()
    logger.info("QID assignment: %s", stats)
    return stats


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate_empresas(db: Session) -> dict[str, int]:
    """Remove duplicate empresa_candidata rows with the same CNPJ.

    Keeps the row with the lowest id (earliest insert). Reassigns
    local_candidato foreign keys before deleting duplicates.
    """
    stats = {"duplicates_removed": 0, "locais_reassigned": 0}

    dupes = (
        db.query(EmpresaCandidata.cnpj, func.count(EmpresaCandidata.id).label("cnt"))
        .group_by(EmpresaCandidata.cnpj)
        .having(func.count(EmpresaCandidata.id) > 1)
        .all()
    )

    for cnpj, cnt in dupes:
        rows = (
            db.query(EmpresaCandidata)
            .filter_by(cnpj=cnpj)
            .order_by(EmpresaCandidata.id.asc())
            .all()
        )
        keeper = rows[0]
        for dup in rows[1:]:
            reassigned = (
                db.query(LocalCandidato)
                .filter_by(empresa_id=dup.id)
                .update({"empresa_id": keeper.id})
            )
            stats["locais_reassigned"] += reassigned
            db.delete(dup)
            stats["duplicates_removed"] += 1

    db.flush()
    logger.info("Deduplication: %s", stats)
    return stats


# ---------------------------------------------------------------------------
# Full normalization pipeline
# ---------------------------------------------------------------------------

def normalize_all(
    db: Session,
    *,
    cnefe_dir: Path | None = None,
    geojson_path: Path | None = None,
    skip_geocode: bool = False,
    skip_ra: bool = False,
) -> dict[str, Any]:
    """Run the full normalization pipeline: dedup -> geocode -> RA -> qid."""
    results: dict[str, Any] = {}

    logger.info("Step 1/4: Deduplication")
    results["dedup"] = deduplicate_empresas(db)

    if not skip_geocode:
        logger.info("Step 2/4: CNEFE geocoding")
        results["geocode"] = geocode_candidates(db, cnefe_dir)
    else:
        logger.info("Step 2/4: Geocoding skipped")
        results["geocode"] = "skipped"

    if not skip_ra:
        logger.info("Step 3/4: RA assignment")
        results["ra_assign"] = assign_ra(db, geojson_path)
    else:
        logger.info("Step 3/4: RA assignment skipped")
        results["ra_assign"] = "skipped"

    logger.info("Step 4/4: QID generation")
    results["qid_assign"] = assign_qid(db)

    db.commit()
    logger.info("Normalization complete: %s", results)
    return results
