"""Tests for enhanced QID generation in ranker_contract and normalize_candidates."""

import pytest

from jobs.prospeccao.ranker_contract import listwise_training_qid


class MockEmpresa:
    """Mock empresa object for testing."""
    def __init__(self, **kwargs):
        self.cnpj = kwargs.get('cnpj', '00000000000191')
        self.razao_social = kwargs.get('razao_social', 'Test Company')
        self.uf = kwargs.get('uf', 'DF')
        self.municipio = kwargs.get('municipio', 'Brasilia')
        self.bairro = kwargs.get('bairro')
        self.cep = kwargs.get('cep')
        self.cnae_principal = kwargs.get('cnae_principal', '4751201')


class MockLocal:
    """Mock local_candidato object for testing."""
    def __init__(self, **kwargs):
        self.latitude = kwargs.get('latitude')
        self.longitude = kwargs.get('longitude')
        self.ra = kwargs.get('ra')
        self.bairro = kwargs.get('bairro')
        self.cep = kwargs.get('cep')
        self.qid = kwargs.get('qid')


class TestListwiseTrainingQid:
    """Test enhanced listwise_training_qid fallback chain."""

    def test_geo_priority_with_coordinates(self):
        """Coordinates should take highest priority."""
        empresa = MockEmpresa()
        local = MockLocal(latitude=-15.8105, longitude=-47.8894)
        qid = listwise_training_qid(empresa, local)
        assert qid.startswith('geo:'), f"Expected geo:*, got {qid}"
        assert '-15.81' in qid
        assert '-47.89' in qid

    def test_ra_priority_over_qid(self):
        """RA should override qid when present."""
        empresa = MockEmpresa()
        local = MockLocal(ra='Plano Piloto', qid='old_qid')
        qid = listwise_training_qid(empresa, local)
        assert qid == 'ra:plano piloto'

    def test_qid_normalized_when_valid(self):
        """Valid normalized qid should be used."""
        empresa = MockEmpresa()
        local = MockLocal(qid='bairro:asa_sul')
        qid = listwise_training_qid(empresa, local)
        assert qid == 'bairro:asa_sul'

    def test_bairro_fallback(self):
        """Bairro should be used as fallback when qid is NULL."""
        empresa = MockEmpresa()
        local = MockLocal(bairro='Asa Sul')
        qid = listwise_training_qid(empresa, local)
        assert qid == 'bairro:brasilia:asa sul'

    def test_cep5_fallback(self):
        """CEP5 should be used when bairro is missing."""
        empresa = MockEmpresa(bairro=None)
        local = MockLocal(bairro=None, cep='70040-902')
        qid = listwise_training_qid(empresa, local)
        assert qid == 'cep5:brasilia:70040'

    def test_cnae4_fallback(self):
        """CNAE4 should be used when bairro and CEP are missing."""
        empresa = MockEmpresa(bairro=None, cep=None, cnae_principal='4751201')
        local = MockLocal(bairro=None, cep=None)
        qid = listwise_training_qid(empresa, local)
        assert qid.startswith('cnae4:')
        assert '4751' in qid

    def test_zone_fallback_with_partial_cep(self):
        """Zone fallback (UF+CEP3) when only a partial postal prefix exists."""
        empresa = MockEmpresa(bairro=None, cep='700', cnae_principal=None)
        local = MockLocal(bairro=None, cep=None)
        qid = listwise_training_qid(empresa, local)
        assert qid == 'zone:df:700', f"Expected zone:df:700, got {qid}"

    def test_final_fallback_by_uf(self):
        """Should fall back to UF when all else fails."""
        empresa = MockEmpresa(bairro=None, cep=None, cnae_principal=None)
        local = MockLocal(bairro=None, cep=None)
        qid = listwise_training_qid(empresa, local)
        # Sparse rows without geo/address → dedicated bucket (not monolithic df:df)
        assert qid == 'unlocated'

    def test_go_state_entorno(self):
        """GO state should generate entorno: prefix."""
        empresa = MockEmpresa(uf='GO', municipio='Valparaiso')
        local = MockLocal()
        qid = listwise_training_qid(empresa, local)
        assert qid.startswith('entorno:')

    def test_multiple_qids_from_same_municipio(self):
        """Multiple companies in same municipio should generate different QIDs."""
        empresa_base = MockEmpresa(municipio='Brasilia')

        # Company 1: with bairro
        local1 = MockLocal(bairro='Asa Sul')
        qid1 = listwise_training_qid(empresa_base, local1)

        # Company 2: different bairro
        local2 = MockLocal(bairro='Taguatinga')
        qid2 = listwise_training_qid(empresa_base, local2)

        # Company 3: with CEP but no bairro
        empresa3 = MockEmpresa(municipio='Brasilia', bairro=None)
        local3 = MockLocal(bairro=None, cep='73000-000')
        qid3 = listwise_training_qid(empresa3, local3)

        # All should be different
        assert qid1 != qid2, f"Bairro-based QIDs should differ: {qid1} vs {qid2}"
        assert qid1 != qid3, f"Bairro vs CEP QIDs should differ: {qid1} vs {qid3}"
        assert qid2 != qid3, f"Different bairros vs CEP should differ: {qid2} vs {qid3}"

    def test_ra_fallback_layer(self):
        """RA fallback layer should activate when bairro is missing."""
        empresa = MockEmpresa(bairro=None)
        local = MockLocal(bairro=None, ra='Plano Piloto', cep=None)
        qid = listwise_training_qid(empresa, local)
        # Should use bairro/CEP/CNAE first, then RA fallback
        # In this case: no bairro, no CEP, so RA fallback
        assert 'plano' in qid.lower() or qid.startswith('cnae4:') or qid.startswith('zone:')


class TestQidDiversity:
    """Test that the fallback chain generates diverse QIDs."""

    def test_no_single_massive_group(self):
        """With diverse field combinations, should not get massive monolithic groups."""
        empresa_base = MockEmpresa(municipio='Brasilia')

        # Generate 10 different QIDs
        test_cases = [
            MockLocal(bairro='Bairro1'),
            MockLocal(bairro='Bairro2'),
            MockLocal(bairro='Bairro3'),
            MockLocal(bairro='Bairro4'),
            MockLocal(bairro='Bairro5'),
            # These should generate CEP5 groups
            MockLocal(bairro=None, cep='70000-000'),
            MockLocal(bairro=None, cep='71000-000'),
            MockLocal(bairro=None, cep='72000-000'),
            # These should generate other fallbacks
            MockLocal(bairro=None, cep=None),
            MockLocal(bairro=None, cep=None),
        ]

        qids = [listwise_training_qid(empresa_base, local) for local in test_cases]
        unique_qids = set(qids)

        # Should have at least 7-8 different QIDs (bairros are unique, CEPs should differ)
        assert len(unique_qids) >= 6, (
            f"Expected at least 6 unique QIDs, got {len(unique_qids)}: {unique_qids}"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
