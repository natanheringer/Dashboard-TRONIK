"""Unit tests for candidate ingest / normalization helpers (REE training inputs)."""

from __future__ import annotations

import json

from jobs.prospeccao.casadosdados_fetch import _cnae_secundarios_to_json
from jobs.prospeccao.ranker_contract import cnae_secondary_scores, normalize_cep8, sanitize_cnae
from jobs.prospeccao.receita_parse import _compose_cnpj, _parse_secondary_cnaes


def test_normalize_cep8_valid_and_invalid() -> None:
    assert normalize_cep8("70.040-902") == "70040902"
    assert normalize_cep8("70040902") == "70040902"
    assert normalize_cep8("70040") is None
    assert normalize_cep8(None) is None
    assert normalize_cep8("") is None


def test_sanitize_cnae_strips_noise() -> None:
    assert sanitize_cnae("4751-2/01") == "4751201"


def test_compose_cnpj_rejects_garbage() -> None:
    assert _compose_cnpj("12345678", "0001", "00") == "12345678000100"
    assert _compose_cnpj("123", "1", "2") is None


def test_parse_secondary_cnaes_dedupes_and_min_length() -> None:
    raw = "4751-2/01, 4751201, 123, foo"
    got = _parse_secondary_cnaes(raw)
    assert got == ["4751201"]


def test_cnae_secondary_scores_reads_json_from_db_shape() -> None:
    codes = ["4751201", "4751201", "9511800"]
    blob = json.dumps(codes)
    mx, hits = cnae_secondary_scores(blob)
    assert mx > 0
    assert hits > 0


def test_casadosdados_secondary_payloads_normalize_to_json() -> None:
    assert _cnae_secundarios_to_json(None) is None
    assert _cnae_secundarios_to_json("not json") is None
    j = _cnae_secundarios_to_json('[{"codigo": "4751-2/01"}, {"codigo": "9511800"}]')
    assert j is not None
    assert json.loads(j) == ["4751201", "9511800"]
