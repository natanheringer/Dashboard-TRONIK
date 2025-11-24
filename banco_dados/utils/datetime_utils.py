"""
Utilitários de Data/Hora - Dashboard-TRONIK
===========================================
Funções auxiliares para manipulação de datetime.
"""

from datetime import datetime, timezone, date
from calendar import monthrange


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


def get_dias_uteis_mes(ano: int, mes: int) -> int:
    """
    Calcula o número de dias úteis em um mês (excluindo sábados e domingos).
    
    Args:
        ano: Ano (ex: 2025)
        mes: Mês (1-12)
        
    Returns:
        int: Número de dias úteis no mês
    """
    _, ultimo_dia = monthrange(ano, mes)
    dias_uteis = 0
    
    for dia in range(1, ultimo_dia + 1):
        data = date(ano, mes, dia)
        # weekday() retorna 0=segunda, 6=domingo
        if data.weekday() < 5:  # Segunda a sexta (0-4)
            dias_uteis += 1
    
    return dias_uteis


def get_dias_uteis_ate_hoje(ano: int, mes: int, dia_atual: int = None) -> int:
    """
    Calcula o número de dias úteis até o dia atual do mês.
    
    Args:
        ano: Ano (ex: 2025)
        mes: Mês (1-12)
        dia_atual: Dia atual (se None, usa dia de hoje)
        
    Returns:
        int: Número de dias úteis até hoje
    """
    if dia_atual is None:
        hoje = datetime.now()
        if hoje.year == ano and hoje.month == mes:
            dia_atual = hoje.day
        else:
            return 0
    
    dias_uteis = 0
    for dia in range(1, dia_atual + 1):
        try:
            data = date(ano, mes, dia)
            if data.weekday() < 5:  # Segunda a sexta
                dias_uteis += 1
        except ValueError:
            # Dia inválido (ex: 31 de fevereiro)
            continue
    
    return dias_uteis

