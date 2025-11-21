"""
Utilitários - Dashboard-TRONIK
==============================
Funções auxiliares compartilhadas.
"""

from datetime import datetime, timezone


def utc_now():
    """
    Retorna a data/hora atual em UTC (timezone-aware).
    Substitui datetime.utcnow() que está deprecado no Python 3.12+.
    
    Returns:
        datetime: Data/hora atual em UTC com timezone
    """
    return datetime.now(timezone.utc)


def utc_now_naive():
    """
    Retorna a data/hora atual em UTC sem timezone (naive).
    Para compatibilidade com código legado que espera datetime sem timezone.
    
    Returns:
        datetime: Data/hora atual em UTC sem timezone
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


