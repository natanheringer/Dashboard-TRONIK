"""
Testes de Performance - Dashboard-TRONIK
========================================
Testa performance de queries e carga do sistema.
"""

import time

import pytest

from banco_dados.modelos import Coletor, Parceiro
from banco_dados.services.coleta_service import obter_coletas_com_filtros
from banco_dados.services.coletor_service import obter_lixeiras_com_filtros
from banco_dados.services.relatorio_service import gerar_relatorio


class TestPerformanceQueries:
    """Testes de performance de queries"""

    def test_query_lixeiras_performance(self, db_session):
        """Testa performance da query de coletores"""
        inicio = time.time()

        coletores, total = obter_lixeiras_com_filtros(
            db_session,
            pagina=1,
            por_pagina=100
        )

        tempo = time.time() - inicio

        # Query deve completar em menos de 1 segundo
        assert tempo < 1.0, f"Query de coletores muito lenta: {tempo:.3f}s"
        assert len(coletores) <= 100, "Paginação não funcionou corretamente"

    def test_query_coletas_performance(self, db_session):
        """Testa performance da query de coletas"""
        inicio = time.time()

        coletas, total = obter_coletas_com_filtros(
            db_session,
            pagina=1,
            por_pagina=50
        )

        tempo = time.time() - inicio

        # Query deve completar em menos de 1 segundo
        assert tempo < 1.0, f"Query de coletas muito lenta: {tempo:.3f}s"
        assert len(coletas) <= 50, "Paginação não funcionou corretamente"

    def test_query_coletas_com_filtros_performance(self, db_session):
        """Testa performance da query de coletas com filtros"""
        inicio = time.time()

        coletas, total = obter_coletas_com_filtros(
            db_session,
            data_inicio='2025-01-01',
            data_fim='2025-12-31',
            pagina=1,
            por_pagina=50
        )

        tempo = time.time() - inicio

        # Query com filtros deve completar em menos de 2 segundos
        assert tempo < 2.0, f"Query de coletas com filtros muito lenta: {tempo:.3f}s"

    def test_relatorio_performance(self, db_session):
        """Testa performance da geração de relatório"""
        inicio = time.time()

        relatorio = gerar_relatorio(
            db_session,
            data_inicio='2025-01-01',
            data_fim='2025-12-31',
            pagina=1,
            por_pagina=50
        )

        tempo = time.time() - inicio

        # Relatório deve ser gerado em menos de 3 segundos
        assert tempo < 3.0, f"Geração de relatório muito lenta: {tempo:.3f}s"
        assert 'resumo' in relatorio, "Relatório deve conter resumo"
        assert 'detalhes' in relatorio, "Relatório deve conter detalhes"

    def test_query_lixeiras_com_join_performance(self, db_session):
        """Testa performance de query com joins (eager loading)"""
        from sqlalchemy.orm import joinedload

        inicio = time.time()

        query = db_session.query(Coletor).options(
            joinedload(Coletor.parceiro),
            joinedload(Coletor.tipo_material)
        )
        coletores = query.all()

        tempo = time.time() - inicio

        # Query com joins deve completar em menos de 1.5 segundos
        assert tempo < 1.5, f"Query com joins muito lenta: {tempo:.3f}s"

        # Verificar que relacionamentos foram carregados (N+1 problem evitado)
        if coletores:
            # Acessar relacionamentos não deve causar queries adicionais
            inicio2 = time.time()
            for coletor in coletores[:10]:  # Testar apenas 10 primeiras
                _ = coletor.parceiro
                _ = coletor.tipo_material
            tempo2 = time.time() - inicio2

            # Acesso aos relacionamentos deve ser instantâneo (já carregados)
            assert tempo2 < 0.1, "Problema N+1 detectado - relacionamentos não foram eager loaded"


class TestPerformanceCarga:
    """Testes de carga do sistema"""

    def test_multiplas_queries_concorrentes(self, db_session):
        """Testa performance com múltiplas queries sequenciais (SQLite não suporta threading bem)"""
        # SQLite tem limitações com threading, então testamos sequencialmente
        # mas verificamos que múltiplas queries são rápidas

        def executar_query():
            # Criar nova sessão para cada query (simula concorrência)
            from sqlalchemy.orm import sessionmaker
            Session = sessionmaker(bind=db_session.bind)
            session = Session()
            try:
                return obter_lixeiras_com_filtros(session, pagina=1, por_pagina=10)
            finally:
                session.close()

        inicio = time.time()

        # Executar 10 queries sequenciais (simulando carga)
        resultados = []
        for _ in range(10):
            resultados.append(executar_query())

        tempo = time.time() - inicio

        # 10 queries sequenciais devem completar em menos de 2 segundos
        assert tempo < 2.0, f"Queries sequenciais muito lentas: {tempo:.3f}s"
        assert len(resultados) == 10, "Nem todas as queries foram executadas"

    def test_paginacao_grandes_volumes(self, db_session):
        """Testa performance de paginação com grandes volumes"""
        # Testar diferentes tamanhos de página
        tamanhos = [10, 50, 100, 200]

        for tamanho in tamanhos:
            inicio = time.time()

            coletores, total = obter_lixeiras_com_filtros(
                db_session,
                pagina=1,
                por_pagina=tamanho
            )

            tempo = time.time() - inicio

            # Cada página deve carregar em menos de 1 segundo
            assert tempo < 1.0, f"Paginação com {tamanho} itens muito lenta: {tempo:.3f}s"
            assert len(coletores) <= tamanho, f"Paginação retornou mais itens que o esperado: {len(coletores)} > {tamanho}"


class TestPerformanceIndices:
    """Testa se índices estão sendo utilizados corretamente"""

    def test_query_por_status_performance(self, db_session):
        """Testa se query por status usa índice"""
        inicio = time.time()

        coletores, total = obter_lixeiras_com_filtros(
            db_session,
            status='OK',
            pagina=1,
            por_pagina=100
        )

        tempo = time.time() - inicio

        # Query com filtro de status deve ser rápida (índice)
        assert tempo < 1.0, f"Query por status muito lenta: {tempo:.3f}s"

    def test_query_por_parceiro_performance(self, db_session):
        """Testa se query por parceiro usa índice"""
        # Obter primeiro parceiro_id disponível
        parceiro = db_session.query(Parceiro).first()

        if parceiro:
            inicio = time.time()

            coletores, total = obter_lixeiras_com_filtros(
                db_session,
                parceiro_id=parceiro.id,
                pagina=1,
                por_pagina=100
            )

            tempo = time.time() - inicio

            # Query com filtro de parceiro deve ser rápida (índice)
            assert tempo < 1.0, f"Query por parceiro muito lenta: {tempo:.3f}s"


@pytest.mark.parametrize("pagina,por_pagina", [
    (1, 10),
    (1, 50),
    (1, 100),
    (2, 50),
    (3, 50),
])
def test_paginacao_variada_performance(db_session, pagina, por_pagina):
    """Testa performance de paginação com diferentes parâmetros"""
    inicio = time.time()

    coletores, total = obter_lixeiras_com_filtros(
        db_session,
        pagina=pagina,
        por_pagina=por_pagina
    )

    tempo = time.time() - inicio

    # Todas as páginas devem carregar rapidamente
    assert tempo < 1.0, f"Paginação ({pagina}, {por_pagina}) muito lenta: {tempo:.3f}s"
    assert len(coletores) <= por_pagina, "Página retornou mais itens que o esperado"

