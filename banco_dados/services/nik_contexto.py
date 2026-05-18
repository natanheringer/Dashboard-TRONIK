"""
Montagem de contextos para os prompts da Nik.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from banco_dados.modelos import Coletor
from banco_dados.services import nik_mock, preview_service as pv


def _usar_mock(db: Session) -> bool:
    try:
        return db.query(Coletor).count() == 0
    except Exception:
        return True


def contexto_resumo_operacional(db: Session) -> dict[str, Any]:
    if _usar_mock(db):
        return {
            "data": pv.data_longa_pt(),
            "estatisticas": nik_mock.mock_stats(),
            "coletores_atencao": [c["nome"] for c in nik_mock.mock_coletores() if c["classe"] in {"warn", "crit"}][:4],
            "alerta_destaque": nik_mock.mock_alerta(),
            "ultimas_coletas": nik_mock.mock_recentes(5),
            "modo": "mock",
        }
    stats = pv.estatisticas_resumo(db)
    coletores = pv.coletores_monitoramento(db)
    alerta = pv.primeiro_alerta_critico(coletores)
    recentes = pv.coletas_recentes(db, 5)
    return {
        "data": pv.data_longa_pt(),
        "estatisticas": stats,
        "coletores_atencao": pv.nomes_coletores_atencao(coletores, limite=4),
        "alerta_destaque": alerta,
        "ultimas_coletas": recentes,
    }


def contexto_coletor(db: Session, coletor_id: int) -> dict[str, Any] | None:
    if _usar_mock(db):
        detalhe = nik_mock.mock_detalhe_coletor(coletor_id)
        if not detalhe:
            return None
        return {
            "data": pv.data_longa_pt(),
            "media_geral": nik_mock.mock_stats().get("nivel_medio", 0),
            "coletor": detalhe,
            "modo": "mock",
        }
    detalhe = pv.detalhe_coletor_mapa(db, coletor_id)
    if not detalhe:
        return None
    return {
        "data": pv.data_longa_pt(),
        "media_geral": pv.estatisticas_resumo(db).get("nivel_medio", 0),
        "coletor": detalhe,
    }


def contexto_alerta(db: Session) -> dict[str, Any] | None:
    if _usar_mock(db):
        alerta = nik_mock.mock_alerta()
        if not alerta:
            return None
        return {
            "data": pv.data_longa_pt(),
            "alerta": alerta,
            "coletas_recentes": nik_mock.mock_recentes(8),
            "modo": "mock",
        }
    coletores = pv.coletores_monitoramento(db)
    alerta = pv.primeiro_alerta_critico(coletores)
    if not alerta:
        return None
    return {
        "data": pv.data_longa_pt(),
        "alerta": alerta,
        "coletas_recentes": pv.coletas_recentes(db, 8),
    }


def contexto_relatorio(
    db: Session,
    inicio_raw: str | None,
    fim_raw: str | None,
    parceiro_id: int | None,
) -> dict[str, Any]:
    if _usar_mock(db):
        resumo_mock = nik_mock.mock_relatorio()
        return {
            "periodo": {
                "inicio": (date.today() - timedelta(days=29)).isoformat(),
                "fim": date.today().isoformat(),
            },
            "parceiro_id": parceiro_id,
            "parceiro_nome": "Mock parceiro local" if parceiro_id else None,
            "resumo": resumo_mock,
            "top_coletor": resumo_mock.get("top_coletores", [None])[0],
            "top_parceiro": resumo_mock.get("volume_por_parceiro", [None])[0],
            "insights_base": {
                "eficiencia_kg_km": round(resumo_mock.get("volume_kg", 0) / max(resumo_mock.get("km_total", 1), 1), 2),
                "ha_dados": resumo_mock.get("total_coletas", 0) > 0,
            },
            "modo": "mock",
        }
    periodo = pv.resolver_periodo(inicio_raw, fim_raw)
    resumo = pv.resumo_relatorios(db, periodo, parceiro_id=parceiro_id)
    parceiros = {p["id"]: p["nome"] for p in pv.listar_parceiros_select(db)}
    top_coletor = resumo.get("top_coletores", [None])[0] if resumo.get("top_coletores") else None
    top_parceiro = resumo.get("volume_por_parceiro", [None])[0] if resumo.get("volume_por_parceiro") else None
    eficiencia = round(resumo.get("volume_kg", 0) / max(resumo.get("km_total", 1), 1), 2) if resumo.get("km_total", 0) else 0.0
    return {
        "periodo": {
            "inicio": periodo.inicio.isoformat(),
            "fim": periodo.fim.isoformat(),
        },
        "parceiro_id": parceiro_id,
        "parceiro_nome": parceiros.get(parceiro_id) if parceiro_id else None,
        "resumo": resumo,
        "top_coletor": top_coletor,
        "top_parceiro": top_parceiro,
        "insights_base": {
            "eficiencia_kg_km": eficiencia,
            "ha_dados": resumo.get("total_coletas", 0) > 0,
        },
    }


def contexto_landing() -> dict[str, Any]:
    return {
        "empresa": "Tronik Recicla",
        "origem": "startup de impacto socioambiental",
        "atuacao": "coleta e reciclagem de residuos eletroeletronicos",
        "modelo_operacao": "B2B2C com foco em economia circular e logistica reversa",
        "cidade_base": "Brasilia/DF",
        "fatos_setor": [
            "O Brasil gera milhoes de toneladas de lixo eletronico por ano.",
            "A maior parte desse material ainda nao recebe tratamento adequado.",
            "A reciclarem correta reduz extracao mineral e amplia reaproveitamento de componentes.",
        ],
    }


def contexto_conversa_ops(db: Session) -> dict[str, Any]:
    if _usar_mock(db):
        return nik_mock.mock_contexto_conversa()
    return {
        "modo": "real",
        "data": pv.data_longa_pt(),
        "estatisticas": pv.estatisticas_resumo(db),
        "alerta_destaque": pv.primeiro_alerta_critico(pv.coletores_monitoramento(db)),
        "coletas_recentes": pv.coletas_recentes(db, 5),
    }
