"""Tests for IBAMA CTF/APP CSV parsing helpers (no network)."""

import pytest

from jobs.prospeccao.ibama_ctf_ingest import (
    _ATIVIDADE_FIELDS,
    _CNPJ_FIELDS,
    _find_field,
    _parse_csv_bytes,
)


class TestFindField:
    def test_exact_match(self):
        header = ["cnpj", "razao_social", "atividade"]
        assert _find_field(header, ("cnpj",)) == 0
        assert _find_field(header, ("atividade",)) == 2

    def test_case_insensitive_and_stripped(self):
        header = [" CNPJ ", "Ds_Atividade"]
        assert _find_field(header, _CNPJ_FIELDS) == 0
        assert _find_field(header, _ATIVIDADE_FIELDS) == 1

    def test_returns_none_when_missing(self):
        header = ["nome", "uf"]
        assert _find_field(header, _CNPJ_FIELDS) is None

    def test_first_candidate_wins(self):
        header = ["nr_cnpj", "cnpj"]
        assert _find_field(header, ("cnpj", "nr_cnpj")) == 1


class TestParseCsvBytes:
    def test_semicolon_delimited_utf8(self):
        raw = (
            "cnpj;razao_social;atividade\n"
            "12345678000199;Eco Eletronica;Industria de material eletrico\n"
            "98765432000111;Loja X;Comercio varejista\n"
        ).encode("utf-8")
        rows = _parse_csv_bytes(raw)
        assert len(rows) == 2
        assert rows[0]["cnpj"] == "12345678000199"
        assert "eletrico" in rows[0]["atividade"]

    def test_comma_delimited_latin1(self):
        raw = (
            "CNPJ,Razao,Atividade\n"
            "11111111000191,Parceiro SA,Destinação de resíduos\n"
        ).encode("latin-1")
        rows = _parse_csv_bytes(raw)
        assert len(rows) == 1
        assert rows[0]["CNPJ"] == "11111111000191"

    def test_utf8_bom(self):
        raw = (
            "cnpj;nome;atividade\n"
            "00000000000191;Recicla;reciclagem de residuos\n"
        ).encode("utf-8-sig")
        rows = _parse_csv_bytes(raw)
        assert len(rows) == 1
        assert rows[0]["cnpj"] == "00000000000191"

    def test_empty_or_unparseable_returns_empty_list(self):
        assert _parse_csv_bytes(b"") == []
        assert _parse_csv_bytes(b"only,one\n") == []
