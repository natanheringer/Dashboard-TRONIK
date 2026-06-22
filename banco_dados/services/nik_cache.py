"""
Invalidação de cache da Nik e dados operacionais após mudanças em coletas.
"""

from __future__ import annotations

from datetime import datetime

from banco_dados.utils.cache import obter_cache


def invalidar_cache_apos_coleta(
    data_hora: datetime | None = None,
    *,
    parceiro_id: int | None = None,
) -> None:
    """Limpa caches que podem ficar desatualizados quando uma coleta entra ou muda."""
    cache = obter_cache()
    cache.invalidar_por_prefixo("nik:")
    if data_hora is not None:
        cache.invalidar_por_substring(data_hora.date().isoformat())
    cache.invalidar("preview:estatisticas_resumo")
    cache.invalidar("preview:coletores_geojson")
    cache.invalidar("estatisticas")
    if parceiro_id is not None:
        cache.invalidar(f"estatisticas:{parceiro_id}")
