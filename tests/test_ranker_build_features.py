"""Tests for ranker 19-feature vector and equal-frequency label binning."""

from collections import Counter
from datetime import datetime

from jobs.prospeccao.build_features import _equal_frequency_ordinal_labels
from jobs.prospeccao.ranker_contract import (
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    MONOTONIC_CONSTRAINTS,
    build_feature_vector,
    feature_schema,
    validate_feature_contract,
)


class MockEmpresa:
    def __init__(self, **kwargs):
        self.cnpj = kwargs.get("cnpj", "00000000000191")
        self.cnae_principal = kwargs.get("cnae_principal", "4751201")
        self.cnae_secundarios_json = kwargs.get("cnae_secundarios_json")
        self.porte = kwargs.get("porte", "Empresa de Pequeno Porte")
        self.situacao_cadastral = kwargs.get("situacao_cadastral", "ATIVA")
        self.email = kwargs.get("email", "contato@empresa.example")
        self.telefone = kwargs.get("telefone", "(61) 3333-0000")
        self.bairro = kwargs.get("bairro", "Asa Sul")
        self.cep = kwargs.get("cep", "70040-902")
        self.endereco_normalizado = kwargs.get("endereco_normalizado", "SQN 100")
        self.natureza_juridica = kwargs.get("natureza_juridica", "2062")
        self.uf = kwargs.get("uf", "DF")
        self.municipio_ibge = kwargs.get("municipio_ibge")
        self.data_abertura = kwargs.get("data_abertura", datetime(2015, 1, 1))


class MockLocal:
    def __init__(self, **kwargs):
        self.latitude = kwargs.get("latitude", -15.8105)
        self.longitude = kwargs.get("longitude", -47.8894)
        self.ra = kwargs.get("ra", "Plano Piloto")
        self.cep = kwargs.get("cep", "70040-902")
        self.endereco = kwargs.get("endereco", "SQN 100")
        self.geocode_quality = kwargs.get("geocode_quality", 0.9)
        self.categoria_operacional = kwargs.get("categoria_operacional", "varejo de informatica")


class TestEqualFrequencyOrdinalLabels:
    def test_empty_scores(self):
        assert _equal_frequency_ordinal_labels([]) == []

    def test_fewer_than_bins_returns_zeros(self):
        scores = [0.1, 0.5, 0.9]
        assert _equal_frequency_ordinal_labels(scores, n_bins=8) == [0, 0, 0]

    def test_spreads_labels_across_bins(self):
        scores = list(range(16))
        labels = _equal_frequency_ordinal_labels(scores, n_bins=8)
        assert len(labels) == 16
        assert min(labels) == 0
        assert max(labels) == 7
        counts = Counter(labels)
        assert len(counts) == 8
        assert all(count == 2 for count in counts.values())

    def test_handles_ties(self):
        scores = [0.5] * 8 + list(range(8))
        labels = _equal_frequency_ordinal_labels(scores, n_bins=8)
        assert len(labels) == 16
        assert min(labels) >= 0
        assert max(labels) <= 7


class TestFeatureVectorContract:
    def test_feature_names_length(self):
        assert len(FEATURE_NAMES) == 19

    def test_schema_version_and_entries(self):
        schema = feature_schema()
        assert len(schema) == 19
        assert all(entry["name"] in FEATURE_NAMES for entry in schema)
        assert all(entry["version"] == FEATURE_SCHEMA_VERSION for entry in schema)
        assert FEATURE_SCHEMA_VERSION == "prospeccao-ree-v3.3"

    def test_monotonic_constraints_aligned(self):
        assert len(MONOTONIC_CONSTRAINTS) == len(FEATURE_NAMES)

    def test_build_feature_vector_has_nineteen_keys(self):
        empresa = MockEmpresa()
        local = MockLocal()
        vec = build_feature_vector(
            empresa,
            local,
            neighborhood={"qid_total": 10, "qid_ree_compatible": 4},
        )
        assert set(vec.keys()) == set(FEATURE_NAMES)
        assert len(vec) == 19
        validate_feature_contract(vec)

    def test_enrichment_proxies_merged_when_provided(self):
        vec = build_feature_vector(
            MockEmpresa(),
            MockLocal(),
            enrichment_proxies={
                "osm_poi_ree_density": 0.42,
                "inep_institution_proxy": 0.33,
                "cnes_health_proxy": 0.21,
            },
        )
        assert vec["osm_poi_ree_density"] == 0.42
        assert vec["inep_institution_proxy"] == 0.33
        assert vec["cnes_health_proxy"] == 0.21

    def test_has_geocode_reflects_coordinates(self):
        empresa = MockEmpresa()
        with_coords = build_feature_vector(empresa, MockLocal())
        without_coords = build_feature_vector(
            empresa,
            MockLocal(latitude=None, longitude=None),
        )
        assert with_coords["has_geocode"] == 1.0
        assert without_coords["has_geocode"] == 0.0

    def test_all_values_are_numeric(self):
        vec = build_feature_vector(MockEmpresa(), MockLocal())
        for name in FEATURE_NAMES:
            assert isinstance(vec[name], (int, float)), name
