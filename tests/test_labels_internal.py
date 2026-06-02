"""Tests for internal ops label index (normalize, score bounds, lookup)."""

from datetime import datetime, timedelta

import pytest

from jobs.prospeccao.labels_internal import (
    InternalLabelIndex,
    InternalSiteSignals,
    extract_cnpjs_from_text,
    internal_relevance_continuous,
    lookup_internal_score,
    lookup_internal_signals,
    normalize_cnpj,
    normalize_org_name,
)


class MockEmpresa:
    def __init__(self, **kwargs):
        self.cnpj = kwargs.get("cnpj", "00000000000191")
        self.razao_social = kwargs.get("razao_social")
        self.nome_fantasia = kwargs.get("nome_fantasia")
        self.pipeline_id = kwargs.get("pipeline_id")


class MockLocal:
    def __init__(self, **kwargs):
        self.endereco = kwargs.get("endereco")


class TestNormalizeOrgName:
    def test_empty_and_none(self):
        assert normalize_org_name(None) == ""
        assert normalize_org_name("") == ""

    def test_strips_accents_and_lowercases(self):
        assert normalize_org_name("Reciclagem São Paulo") == "reciclagem sao paulo"

    def test_removes_legal_suffix_stopwords(self):
        assert normalize_org_name("EcoTech Ltda. ME") == "ecotech"
        assert normalize_org_name("Indústria Ltda") == "industria"

    def test_strips_punctuation(self):
        assert normalize_org_name("A&B - Comércio") == "a b comercio"


class TestInternalRelevanceContinuous:
    def test_zero_for_empty_signals(self):
        assert internal_relevance_continuous(InternalSiteSignals()) == 0.0

    def test_non_negative(self):
        signals = InternalSiteSignals(
            parceiro_ativo=True,
            has_active_contract=True,
            contract_valor_mensal=50_000.0,
            coleta_count=100,
            volume_total_kg=10_000.0,
            last_coleta_at=datetime.utcnow(),
        )
        assert internal_relevance_continuous(signals) >= 0.0

    def test_bounded_max_score(self):
        """Worst-case stack of all components stays within theoretical max."""
        signals = InternalSiteSignals(
            parceiro_ativo=True,
            has_active_contract=True,
            contract_valor_mensal=1_000_000.0,
            coleta_count=10_000,
            volume_total_kg=1_000_000.0,
            last_coleta_at=datetime.utcnow(),
        )
        score = internal_relevance_continuous(signals)
        # 5 + (40+30) + 45 + 25 + 20 = 165
        assert score <= 165.0

    def test_contract_cap(self):
        """Valor bonus caps at +30 once monthly value exceeds 15k."""
        below_cap = InternalSiteSignals(has_active_contract=True, contract_valor_mensal=10_000.0)
        at_cap = InternalSiteSignals(has_active_contract=True, contract_valor_mensal=500_000.0)
        assert internal_relevance_continuous(below_cap) < internal_relevance_continuous(at_cap)
        assert internal_relevance_continuous(at_cap) == 70.0

    def test_recency_tiers(self):
        now = datetime.utcnow()
        recent = InternalSiteSignals(last_coleta_at=now - timedelta(days=10))
        mid = InternalSiteSignals(last_coleta_at=now - timedelta(days=60))
        old = InternalSiteSignals(last_coleta_at=now - timedelta(days=200))
        stale = InternalSiteSignals(last_coleta_at=now - timedelta(days=400))
        assert internal_relevance_continuous(recent) > internal_relevance_continuous(mid)
        assert internal_relevance_continuous(mid) > internal_relevance_continuous(old)
        assert internal_relevance_continuous(old) > internal_relevance_continuous(stale)


class TestCnpjHelpers:
    def test_normalize_cnpj_digits(self):
        assert normalize_cnpj("12.345.678/0001-95") == "12345678000195"

    def test_extract_from_notes(self):
        text = "Cliente futuro CNPJ 12.345.678/0001-95 aguardando contrato"
        assert "12345678000195" in extract_cnpjs_from_text(text)


class TestLookupInternalSignals:
    @pytest.fixture
    def index(self):
        key = normalize_org_name("Eco Recicla Ltda")
        signals = InternalSiteSignals(
            coletor_id=42,
            parceiro_id=7,
            coleta_count=5,
            has_active_contract=True,
        )
        return InternalLabelIndex(by_norm_name={key: signals}, stats={})

    def test_match_by_razao_social(self, index):
        empresa = MockEmpresa(razao_social="Eco Recicla Ltda")
        signals, source = lookup_internal_signals(empresa, None, index)
        assert signals is not None
        assert signals.coletor_id == 42
        assert source == "razao_social"

    def test_match_by_nome_fantasia(self, index):
        empresa = MockEmpresa(nome_fantasia="Eco Recicla Ltda")
        signals, source = lookup_internal_signals(empresa, None, index)
        assert signals is not None
        assert source == "nome_fantasia"

    def test_match_by_local_endereco(self, index):
        empresa = MockEmpresa()
        local = MockLocal(endereco="Eco Recicla Ltda")
        signals, source = lookup_internal_signals(empresa, local, index)
        assert signals is not None
        assert source == "local_endereco"

    def test_no_match_returns_none(self, index):
        empresa = MockEmpresa(razao_social="Empresa Desconhecida SA")
        signals, source = lookup_internal_signals(empresa, None, index)
        assert signals is None
        assert source is None

    def test_match_by_cnpj_index(self):
        cnpj = "12345678000195"
        signals = InternalSiteSignals(coletor_id=99, coleta_count=1)
        index = InternalLabelIndex(by_cnpj={cnpj: signals}, stats={})
        empresa = MockEmpresa(cnpj="12.345.678/0001-95")
        matched, source = lookup_internal_signals(empresa, None, index)
        assert matched is not None
        assert matched.coletor_id == 99
        assert source == "cnpj"

    def test_match_by_localizacao_index(self):
        key = normalize_org_name("Shopping Norte Recicla")
        signals = InternalSiteSignals(coletor_id=11)
        index = InternalLabelIndex(by_norm_localizacao={key: signals}, stats={})
        empresa = MockEmpresa(razao_social="Shopping Norte Recicla")
        matched, source = lookup_internal_signals(empresa, None, index)
        assert matched is not None
        assert source == "razao_social_localizacao"

    def test_match_pipeline_won(self):
        key = normalize_org_name("Cliente Fechado Ltda")
        signals = InternalSiteSignals(pipeline_won=True, coletor_id=3)
        index = InternalLabelIndex(by_pipeline_won={key: signals}, stats={})
        empresa = MockEmpresa(razao_social="Cliente Fechado Ltda")
        matched, source = lookup_internal_signals(empresa, None, index)
        assert matched is not None
        assert source == "razao_social_pipeline_won"


class TestLookupInternalScore:
    def test_matched_returns_score_and_metadata(self):
        key = normalize_org_name("Parceiro Ativo")
        signals = InternalSiteSignals(parceiro_ativo=True, coleta_count=2)
        index = InternalLabelIndex(by_norm_name={key: signals}, stats={})
        empresa = MockEmpresa(razao_social="Parceiro Ativo")
        score, meta = lookup_internal_score(empresa, None, index)
        assert score is not None
        assert score > 0
        assert meta["matched"] is True
        assert meta["match_source"] == "razao_social"
        assert meta["coleta_count"] == 2

    def test_unmatched_returns_none(self):
        index = InternalLabelIndex(by_norm_name={}, stats={})
        empresa = MockEmpresa(razao_social="Sem Cadastro")
        score, meta = lookup_internal_score(empresa, None, index)
        assert score is None
        assert meta == {"matched": False}

    def test_pipeline_won_excluded_from_training_score(self):
        """pipeline_won is outcome data — must not leak into label continuous score."""
        plain = InternalSiteSignals(coleta_count=1)
        won = InternalSiteSignals(coleta_count=1, pipeline_won=True)
        assert internal_relevance_continuous(won) == internal_relevance_continuous(plain)

    def test_crm_persisted_link_boosts_score_when_enabled(self):
        key = normalize_org_name("Parceiro CRM")
        signals = InternalSiteSignals(coleta_count=1)
        index = InternalLabelIndex(
            by_norm_name={key: signals},
            fechado_pipeline_ids=frozenset({99}),
            stats={},
        )
        empresa = MockEmpresa(razao_social="Parceiro CRM", pipeline_id=99)
        score, meta = lookup_internal_score(
            empresa, None, index, apply_crm_persisted_boost=True
        )
        assert score is not None
        assert meta.get("crm_persisted_link") is True
        empresa_no_link = MockEmpresa(razao_social="Parceiro CRM", pipeline_id=None)
        score_plain, _ = lookup_internal_score(
            empresa_no_link, None, index, apply_crm_persisted_boost=True
        )
        assert score > score_plain

    def test_crm_persisted_link_boost_disabled_by_default(self):
        key = normalize_org_name("Parceiro CRM")
        signals = InternalSiteSignals(coleta_count=1)
        index = InternalLabelIndex(
            by_norm_name={key: signals},
            fechado_pipeline_ids=frozenset({99}),
            stats={},
        )
        empresa_linked = MockEmpresa(razao_social="Parceiro CRM", pipeline_id=99)
        empresa_plain = MockEmpresa(razao_social="Parceiro CRM", pipeline_id=None)
        s_link, m_link = lookup_internal_score(empresa_linked, None, index)
        s_plain, m_plain = lookup_internal_score(empresa_plain, None, index)
        assert s_link == s_plain
        assert m_link.get("crm_persisted_link") is not True
        assert m_plain.get("crm_persisted_link") is not True

    def test_crm_persisted_link_ignored_when_pipeline_not_fechado(self):
        key = normalize_org_name("Parceiro CRM")
        signals = InternalSiteSignals(coleta_count=1)
        index = InternalLabelIndex(
            by_norm_name={key: signals},
            fechado_pipeline_ids=frozenset(),
            stats={},
        )
        empresa = MockEmpresa(razao_social="Parceiro CRM", pipeline_id=99)
        score, meta = lookup_internal_score(empresa, None, index)
        assert meta.get("crm_persisted_link") is not True
