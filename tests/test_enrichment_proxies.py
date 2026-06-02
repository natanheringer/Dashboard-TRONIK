"""Tests for OSM/INEP/CNES enrichment proxy lookups."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from jobs.prospeccao.enrichment_proxies import (
    PROXY_KEYS,
    clear_proxy_caches,
    lookup_proxies,
    probe_enrichment_files,
)


@pytest.fixture(autouse=True)
def _reset_proxy_cache(monkeypatch):
    clear_proxy_caches()
    for name in (
        "TRONIK_OSM_POI_PARQUET",
        "TRONIK_INEP_CENSO_PARQUET",
        "TRONIK_CNES_PARQUET",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    clear_proxy_caches()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class TestLookupProxiesDefaults:
    def test_missing_files_return_zeros(self):
        result = lookup_proxies(-15.81, -47.89, "Plano Piloto", "Brasilia")
        assert set(result.keys()) == set(PROXY_KEYS)
        assert all(result[k] == 0.0 for k in PROXY_KEYS)


class TestOsmPoiDensity:
    def test_counts_nearby_pois(self, tmp_path, monkeypatch):
        osm = tmp_path / "osm_pois.csv"
        _write_csv(
            osm,
            ["latitude", "longitude"],
            [
                {"latitude": "-15.8105", "longitude": "-47.8894"},
                {"latitude": "-15.8106", "longitude": "-47.8895"},
                {"latitude": "-16.5", "longitude": "-48.5"},
            ],
        )
        monkeypatch.setenv("TRONIK_OSM_POI_PARQUET", str(osm))

        near = lookup_proxies(-15.8105, -47.8894, None, None)
        far = lookup_proxies(-16.0, -48.5, None, None)

        assert near["osm_poi_ree_density"] > 0.0
        assert near["osm_poi_ree_density"] >= far["osm_poi_ree_density"]


class TestInepCnesAggregates:
    def test_ra_level_proxy(self, tmp_path, monkeypatch):
        inep = tmp_path / "inep_ra.csv"
        _write_csv(
            inep,
            ["ra", "count"],
            [{"ra": "Taguatinga", "count": "12"}],
        )
        monkeypatch.setenv("TRONIK_INEP_CENSO_PARQUET", str(inep))

        hit = lookup_proxies(None, None, "Taguatinga", None)
        miss = lookup_proxies(None, None, "Ceilandia", None)

        assert 0.0 < hit["inep_institution_proxy"] <= 1.0
        assert miss["inep_institution_proxy"] == 0.0

    def test_municipio_level_cnes(self, tmp_path, monkeypatch):
        cnes = tmp_path / "cnes_mun.csv"
        _write_csv(
            cnes,
            ["municipio", "unidades"],
            [{"municipio": "Brasilia", "unidades": "8"}],
        )
        monkeypatch.setenv("TRONIK_CNES_PARQUET", str(cnes))

        result = lookup_proxies(None, None, None, "Brasilia")
        assert 0.0 < result["cnes_health_proxy"] <= 1.0


class TestProbeEnrichmentFiles:
    def test_probe_reports_missing(self):
        status = probe_enrichment_files()
        assert status["radius_km"] > 0
        for key in ("osm", "inep", "cnes"):
            assert status["sources"][key]["exists"] is False

    def test_probe_reports_existing(self, tmp_path, monkeypatch):
        osm = tmp_path / "osm.csv"
        _write_csv(osm, ["lat", "lon"], [{"lat": "-15.81", "lon": "-47.88"}])
        monkeypatch.setenv("TRONIK_OSM_POI_PARQUET", str(osm))

        status = probe_enrichment_files()
        assert status["sources"]["osm"]["exists"] is True
        assert status["sources"]["osm"]["loaded"] is True
