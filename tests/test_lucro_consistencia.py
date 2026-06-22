"""Testes de consistência financeira e cache operacional."""

from datetime import datetime

from banco_dados.modelos import Coleta, Coletor, Parceiro, TipoColetor, TipoMaterial
from banco_dados.services import preview_service as pv
from banco_dados.services.nik_cache import invalidar_cache_apos_coleta
from banco_dados.services.nik_tools import ferramenta_exportar_coletas_csv
from banco_dados.services.relatorio_service import (
    calcular_lucro_liquido_total,
    lucro_liquido_total_coleta,
)
from banco_dados.utils import utc_now_naive
from banco_dados.utils.cache import obter_cache


def test_lucro_resumo_igual_soma_csv(db_session):
    tipo_material = db_session.query(TipoMaterial).first()
    tipo_coletor = db_session.query(TipoColetor).first()
    parceiro = Parceiro(nome="Instituto Teste Lucro", ativo=True)
    db_session.add(parceiro)
    db_session.flush()
    coletor = Coletor(
        localizacao="Teste Lucro",
        parceiro_id=parceiro.id,
        tipo_material_id=tipo_material.id if tipo_material else None,
    )
    db_session.add(coletor)
    db_session.flush()

    hoje = utc_now_naive()
    coletas_dados = [
        (100.0, 40.0, 5.5),
        (50.0, 20.0, 5.0),
    ]
    for vol, km, preco in coletas_dados:
        db_session.add(
            Coleta(
                coletor_id=coletor.id,
                parceiro_id=parceiro.id,
                data_hora=hoje,
                volume_estimado=vol,
                km_percorrido=km,
                preco_combustivel=preco,
                lucro_por_kg=99.0,
                tipo_coletor_id=tipo_coletor.id if tipo_coletor else None,
            )
        )
    db_session.commit()

    dia = hoje.date().isoformat()
    periodo = pv.PeriodoRelatorio(hoje.date(), hoje.date())
    resumo = pv.resumo_relatorios(db_session, periodo, parceiro_id=parceiro.id)
    export = ferramenta_exportar_coletas_csv(
        db_session,
        inicio=dia,
        fim=dia,
        parceiro_ids=[parceiro.id],
    )

    soma_csv = sum(
        lucro_liquido_total_coleta(vol, km, preco) for vol, km, preco in coletas_dados
    )
    assert round(resumo["lucro_liquido_estimado"], 2) == round(soma_csv, 2)
    assert export["total_linhas"] == 2


def test_invalidar_cache_apos_coleta(db_session):
    cache = obter_cache()
    cache.definir("nik:ops:resumo", {"texto": "velho"})
    cache.definir("nik:ops:relatorio:2026-06-22:2026-06-22:all", {"texto": "velho"})
    cache.definir("estatisticas", {"n": 1})

    invalidar_cache_apos_coleta(datetime(2026, 6, 22, 15, 30), parceiro_id=3)

    assert cache.obter("nik:ops:resumo", 3600) is None
    assert cache.obter("nik:ops:relatorio:2026-06-22:2026-06-22:all", 3600) is None
    assert cache.obter("estatisticas", 3600) is None
    assert cache.obter("estatisticas:3", 3600) is None


def test_lucro_liquido_total_coleta_alias():
    assert lucro_liquido_total_coleta(100, 40, 5.5) == calcular_lucro_liquido_total(100, 40, 5.5)
