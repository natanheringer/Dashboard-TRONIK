"""
Utilitários - Dashboard-TRONIK
===============================
Módulo de utilitários compartilhados.
"""

# Importar funções de datetime (compatibilidade com código legado)
# Importar cache
from banco_dados.utils.cache import CacheMemoria, obter_cache
from banco_dados.utils.datetime_utils import utc_now, utc_now_naive

# Importar tratamento de erros
from banco_dados.utils.erros import (
    ErroAcessoNegado,
    ErroAPI,
    ErroNaoEncontrado,
    ErroValidacao,
    tratar_erro_api,
    validar_recurso_existe,
    validar_requisicao_json,
)

# Importar logger
from banco_dados.utils.logger import configurar_logging, obter_logger

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

