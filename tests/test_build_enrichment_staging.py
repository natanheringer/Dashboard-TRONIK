"""Tests for OSM/INEP/CNES enrichment staging parquet builders."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pytest

from jobs.prospeccao.build_enrichment_staging import (
    build_all_enrichment,
    build_cnes_mun_parquet,
    build_inep_ra_parquet,
    build_osm_poi_parquet,
)
from jobs.prospeccao.enrichment_proxies import clear_proxy_caches, lookup_proxies

pytest.importorskip("pandas")


@pytest.fixture(autouse=True)
def _reset_caches(monkeypatch):
    clear_proxy_caches()
    for name in (
        "TRONIK_OSM_POI_PARQUET",
        "TRONIK_INEP_CENSO_PARQUET",
        "TRONIK_CNES_PARQUET",
        "TRONIK_OSM_SOURCE_DIR",
        "TRONIK_INEP_SOURCE_DIR",
        "TRONIK_CNES_SOURCE_DIR",
        "TRONIK_INEP_CENSO_ESCOLAR_CSV_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    yield
    clear_proxy_caches()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class TestBuildOsmParquet:
    def test_csv_to_parquet_lookup_returns_positive(self, tmp_path, monkeypatch):
        osm_dir = tmp_path / "osm"
        _write_csv(
            osm_dir / "pois.csv",
            ["latitude", "longitude", "category"],
            [
                {"latitude": "-15.8105", "longitude": "-47.8894", "category": "shop=electronics"},
                {"latitude": "-15.8106", "longitude": "-47.8895", "category": "shop=computer"},
                {"latitude": "-16.5", "longitude": "-48.5", "category": "shop=electronics"},
            ],
        )
        out = tmp_path / "staging" / "osm_poi_ree.parquet"
        monkeypatch.setenv("TRONIK_OSM_SOURCE_DIR", str(osm_dir))

        result = build_osm_poi_parquet(output_path=out)

        assert result["skipped"] is False
        assert result["ok"] is True
        assert out.is_file()
        assert result["rows"] == 3

        monkeypatch.setenv("TRONIK_OSM_POI_PARQUET", str(out))
        clear_proxy_caches()

        near = lookup_proxies(-15.8105, -47.8894, None, None)
        far = lookup_proxies(-16.0, -48.5, None, None)

        assert near["osm_poi_ree_density"] > 0.0
        assert near["osm_poi_ree_density"] >= far["osm_poi_ree_density"]


class TestBuildInepParquet:
    def test_aggregate_by_ra(self, tmp_path, monkeypatch):
        inep_dir = tmp_path / "inep"
        _write_csv(
            inep_dir / "censo_escolar_externo.csv",
            ["co_uf", "no_regiao"],
            [
                {"co_uf": "53", "no_regiao": "Taguatinga"},
                {"co_uf": "53", "no_regiao": "Taguatinga"},
                {"co_uf": "53", "no_regiao": "Ceilandia"},
            ],
        )
        out = tmp_path / "staging" / "inep_censo_ra.parquet"
        monkeypatch.setenv("TRONIK_INEP_SOURCE_DIR", str(inep_dir))
        monkeypatch.setenv("TRONIK_INEP_CENSO_ESCOLAR_CSV_URL", "https://example.invalid/censo.csv")

        result = build_inep_ra_parquet(output_path=out)

        assert result["skipped"] is False
        assert result["ok"] is True
        assert result["rows"] == 2

        monkeypatch.setenv("TRONIK_INEP_CENSO_PARQUET", str(out))
        clear_proxy_caches()

        hit = lookup_proxies(None, None, "Taguatinga", None)
        assert hit["inep_institution_proxy"] > 0.0


class TestBuildCnesParquet:
    def test_zip_to_municipio_parquet(self, tmp_path, monkeypatch):
        cnes_dir = tmp_path / "cnes"
        cnes_dir.mkdir()
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["no_municipio", "co_cnes"], delimiter=";")
        writer.writeheader()
        writer.writerow({"no_municipio": "Brasilia", "co_cnes": "1"})
        writer.writerow({"no_municipio": "Brasilia", "co_cnes": "2"})
        writer.writerow({"no_municipio": "Taguatinga", "co_cnes": "3"})
        zip_path = cnes_dir / "cnes_base.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("tbEstabelecimento.csv", buf.getvalue())

        out = tmp_path / "staging" / "cnes_mun.parquet"
        monkeypatch.setenv("TRONIK_CNES_SOURCE_DIR", str(cnes_dir))

        result = build_cnes_mun_parquet(output_path=out)

        assert result["skipped"] is False
        assert result["ok"] is True
        assert result["rows"] == 2

        monkeypatch.setenv("TRONIK_CNES_PARQUET", str(out))
        clear_proxy_caches()

        hit = lookup_proxies(None, None, None, "Brasilia")
        assert hit["cnes_health_proxy"] > 0.0


class TestBuildAllEnrichment:
    def test_graceful_skip_when_sources_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TRONIK_OSM_SOURCE_DIR", str(tmp_path / "empty_osm"))
        monkeypatch.setenv("TRONIK_INEP_SOURCE_DIR", str(tmp_path / "empty_inep"))
        monkeypatch.setenv("TRONIK_CNES_SOURCE_DIR", str(tmp_path / "empty_cnes"))

        result = build_all_enrichment()

        assert result["osm"]["skipped"] is True
        assert result["inep"]["skipped"] is True
        assert result["cnes"]["skipped"] is True
