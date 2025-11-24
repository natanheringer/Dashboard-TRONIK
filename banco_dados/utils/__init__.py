"""
Utilitários - Dashboard-TRONIK
===============================
Módulo de utilitários compartilhados.
"""

# Importar funções de datetime (compatibilidade com código legado)
from banco_dados.utils.datetime_utils import utc_now, utc_now_naive

# Importar logger
from banco_dados.utils.logger import obter_logger, configurar_logging

# Importar tratamento de erros
from banco_dados.utils.erros import (
    tratar_erro_api, ErroAPI, ErroValidacao, ErroNaoEncontrado, ErroAcessoNegado,
    validar_requisicao_json, validar_recurso_existe
)

# Importar cache
from banco_dados.utils.cache import obter_cache, CacheMemoria

__all__ = [
    # Datetime (compatibilidade)
    'utc_now',
    'utc_now_naive',
    # Logger
    'obter_logger',
    'configurar_logging',
    # Erros
    'tratar_erro_api',
    'ErroAPI',
    'ErroValidacao',
    'ErroNaoEncontrado',
    'ErroAcessoNegado',
    'validar_requisicao_json',
    'validar_recurso_existe',
    # Cache
    'obter_cache',
    'CacheMemoria'
]

