"""
Serviço de Relatórios - Dashboard-TRONIK
=========================================
Lógica de negócio para geração de relatórios financeiros e operacionais.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from banco_dados.modelos import Coleta
from banco_dados.serializers import coleta_para_dict
import logging
import math

logger = logging.getLogger(__name__)

# Constantes (importadas de utils.constantes para centralização)
from banco_dados.utils.constantes import CONSUMO_KM_POR_LITRO, LUCRO_BRUTO_POR_KG


def calcular_lucro_liquido_por_kg(
    volume_estimado: float,
    km_percorrido: float,
    preco_combustivel: float
) -> float:
    """
    Calcula o lucro líquido por kg subtraindo os custos de combustível.
    
    Fórmula:
    - Lucro bruto por kg = R$ 1,00 (fixo)
    - Custo de combustível = (km_percorrido / CONSUMO_KM_POR_LITRO) * preco_combustivel
    - Custo por kg = custo_combustivel / volume_estimado
    - Lucro líquido por kg = lucro_bruto_por_kg - custo_por_kg
    
    Args:
        volume_estimado: Volume coletado em kg
        km_percorrido: Distância percorrida em km
        preco_combustivel: Preço do combustível por litro
        
    Returns:
        Lucro líquido por kg (pode ser negativo se custos excederem receita)
    """
    if not volume_estimado or volume_estimado <= 0:
        return 0.0
    
    try:
        volume = float(volume_estimado)
        km = float(km_percorrido) if km_percorrido else 0.0
        preco = float(preco_combustivel) if preco_combustivel else 0.0
        
        if math.isnan(volume) or not math.isfinite(volume) or volume <= 0:
            return 0.0
        
        # Calcular custo de combustível total
        if km > 0 and preco > 0:
            custo_combustivel_total = (km / CONSUMO_KM_POR_LITRO) * preco
            custo_por_kg = custo_combustivel_total / volume
        else:
            custo_por_kg = 0.0
        
        # Lucro líquido = bruto - custos
        lucro_liquido_por_kg = LUCRO_BRUTO_POR_KG - custo_por_kg
        
        return round(lucro_liquido_por_kg, 4)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0


def calcular_lucro_liquido_total(
    volume_estimado: float,
    km_percorrido: float,
    preco_combustivel: float
) -> float:
    """
    Calcula o lucro líquido total (não por kg) de uma coleta.
    
    Args:
        volume_estimado: Volume coletado em kg
        km_percorrido: Distância percorrida em km
        preco_combustivel: Preço do combustível por litro
        
    Returns:
        Lucro líquido total em reais
    """
    lucro_por_kg = calcular_lucro_liquido_por_kg(volume_estimado, km_percorrido, preco_combustivel)
    return round(lucro_por_kg * volume_estimado, 2) if volume_estimado > 0 else 0.0


def processar_filtros_data(
    query,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None
) -> Tuple[any, Optional[datetime], Optional[datetime]]:
    """
    Processa filtros de data e aplica à query.
    
    Returns:
        Tuple[query, data_inicio_obj, data_fim_obj]
    """
    data_inicio_obj = None
    data_fim_obj = None
    
    if data_inicio:
        try:
            if len(data_inicio) == 10:
                data_inicio_obj = datetime.fromisoformat(data_inicio + 'T00:00:00')
            else:
                data_inicio_obj = datetime.fromisoformat(data_inicio.replace('Z', '+00:00'))
            query = query.filter(Coleta.data_hora >= data_inicio_obj)
        except Exception as e:
            logger.warning(f"Erro ao processar data_inicio: {e}")
    
    if data_fim:
        try:
            if len(data_fim) == 10:
                data_fim_obj = datetime.fromisoformat(data_fim + 'T23:59:59')
            else:
                data_fim_obj = datetime.fromisoformat(data_fim.replace('Z', '+00:00'))
            query = query.filter(Coleta.data_hora <= data_fim_obj)
        except Exception as e:
            logger.warning(f"Erro ao processar data_fim: {e}")
    
    return query, data_inicio_obj, data_fim_obj


def calcular_metricas_financeiras(coletas: List[Coleta]) -> Dict:
    """
    Calcula métricas financeiras a partir de uma lista de coletas.
    
    Returns:
        Dict com total_coletas, volume_total, km_total, custo_combustivel_total,
        lucro_total, lucro_medio_por_coleta
    """
    if not coletas or not isinstance(coletas, list):
        coletas = []
    
    total_coletas = len(coletas)
    
    # Validar e somar volumes
    volume_total = 0.0
    for c in coletas:
        if c and hasattr(c, 'volume_estimado') and c.volume_estimado is not None:
            try:
                vol = float(c.volume_estimado)
                if not math.isnan(vol) and math.isfinite(vol) and vol >= 0:
                    volume_total += vol
            except (ValueError, TypeError):
                pass
    
    # Validar e somar km
    km_total = 0.0
    for c in coletas:
        if c and hasattr(c, 'km_percorrido') and c.km_percorrido is not None:
            try:
                km = float(c.km_percorrido)
                if not math.isnan(km) and math.isfinite(km) and km >= 0:
                    km_total += km
            except (ValueError, TypeError):
                pass
    
    # Calcular custo de combustível
    custo_combustivel_total = 0.0
    for c in coletas:
        if c:
            try:
                km = float(c.km_percorrido) if c.km_percorrido is not None else 0.0
                preco = float(c.preco_combustivel) if c.preco_combustivel is not None else 0.0
                if not math.isnan(km) and not math.isnan(preco) and math.isfinite(km) and math.isfinite(preco) and km >= 0 and preco >= 0:
                    custo = (km / CONSUMO_KM_POR_LITRO) * preco
                    if not math.isnan(custo) and math.isfinite(custo):
                        custo_combustivel_total += custo
            except (ValueError, TypeError):
                pass
    
    # Calcular lucro líquido total (usando cálculo baseado em custos de combustível)
    lucro_total = 0.0
    for c in coletas:
        if c:
            try:
                volume = float(c.volume_estimado) if c.volume_estimado is not None else 0.0
                km = float(c.km_percorrido) if c.km_percorrido is not None else 0.0
                preco = float(c.preco_combustivel) if c.preco_combustivel is not None else 0.0
                
                if not math.isnan(volume) and math.isfinite(volume) and volume > 0:
                    # Usar cálculo de lucro líquido (bruto - custos)
                    lucro = calcular_lucro_liquido_total(volume, km, preco)
                    if not math.isnan(lucro) and math.isfinite(lucro):
                        lucro_total += lucro
            except (ValueError, TypeError):
                pass
    
    return {
        "total_coletas": total_coletas,
        "volume_total": round(volume_total, 2),
        "km_total": round(km_total, 2),
        "custo_combustivel_total": round(custo_combustivel_total, 2),
        "lucro_total": round(lucro_total, 2),
        "lucro_medio_por_coleta": round(lucro_total / total_coletas, 2) if total_coletas > 0 else 0.0
    }


def agrupar_coletas_por_lixeira(coletas: List[Coleta]) -> List[Dict]:
    """Agrupa coletas por coletor e calcula totais"""
    coletas_por_lixeira = {}
    
    if not coletas or not isinstance(coletas, list):
        return []
    
    for coleta in coletas:
        if not coleta or not hasattr(coleta, 'coletor_id'):
            continue
        coletor_id = coleta.coletor_id
        if coletor_id not in coletas_por_lixeira:
            coletas_por_lixeira[coletor_id] = {
                "coletor_id": coletor_id,
                "total_coletas": 0,
                "volume_total": 0.0,
                "km_total": 0.0,
                "lucro_total": 0.0
            }
        
        coletas_por_lixeira[coletor_id]["total_coletas"] += 1
        if coleta.volume_estimado is not None:
            try:
                volume = float(coleta.volume_estimado)
                if not math.isnan(volume) and math.isfinite(volume) and volume >= 0:
                    coletas_por_lixeira[coletor_id]["volume_total"] += volume
            except (ValueError, TypeError):
                pass
        if coleta.km_percorrido is not None:
            try:
                km = float(coleta.km_percorrido)
                if not math.isnan(km) and math.isfinite(km) and km >= 0:
                    coletas_por_lixeira[coletor_id]["km_total"] += km
            except (ValueError, TypeError):
                pass
        # Calcular lucro líquido usando novo cálculo (bruto - custos)
        if coleta.volume_estimado is not None:
            try:
                volume = float(coleta.volume_estimado) if coleta.volume_estimado is not None else 0.0
                km = float(coleta.km_percorrido) if coleta.km_percorrido is not None else 0.0
                preco = float(coleta.preco_combustivel) if coleta.preco_combustivel is not None else 0.0
                if not math.isnan(volume) and math.isfinite(volume) and volume > 0:
                    lucro = calcular_lucro_liquido_total(volume, km, preco)
                    if not math.isnan(lucro) and math.isfinite(lucro):
                        coletas_por_lixeira[coletor_id]["lucro_total"] += lucro
            except (ValueError, TypeError):
                pass
    
    return list(coletas_por_lixeira.values())


def agrupar_coletas_por_parceiro(coletas: List[Coleta]) -> List[Dict]:
    """Agrupa coletas por parceiro e calcula totais"""
    coletas_por_parceiro = {}
    
    if not coletas or not isinstance(coletas, list):
        return []
    
    for coleta in coletas:
        if not coleta:
            continue
        parceiro_id = coleta.parceiro_id
        parceiro_nome = coleta.parceiro.nome if (coleta.parceiro and hasattr(coleta.parceiro, 'nome')) else 'Sem Parceiro'
        
        if parceiro_id not in coletas_por_parceiro:
            coletas_por_parceiro[parceiro_id] = {
                "parceiro_id": parceiro_id,
                "parceiro_nome": parceiro_nome,
                "total_coletas": 0,
                "volume_total": 0.0,
                "lucro_total": 0.0
            }
        
        coletas_por_parceiro[parceiro_id]["total_coletas"] += 1
        if coleta.volume_estimado is not None:
            try:
                volume = float(coleta.volume_estimado)
                if not math.isnan(volume) and math.isfinite(volume) and volume >= 0:
                    coletas_por_parceiro[parceiro_id]["volume_total"] += volume
            except (ValueError, TypeError):
                pass
        # Calcular lucro líquido usando novo cálculo (bruto - custos)
        if coleta.volume_estimado is not None:
            try:
                volume = float(coleta.volume_estimado) if coleta.volume_estimado is not None else 0.0
                km = float(coleta.km_percorrido) if coleta.km_percorrido is not None else 0.0
                preco = float(coleta.preco_combustivel) if coleta.preco_combustivel is not None else 0.0
                if not math.isnan(volume) and math.isfinite(volume) and volume > 0:
                    lucro = calcular_lucro_liquido_total(volume, km, preco)
                    if not math.isnan(lucro) and math.isfinite(lucro):
                        coletas_por_parceiro[parceiro_id]["lucro_total"] += lucro
            except (ValueError, TypeError):
                pass
    
    return list(coletas_por_parceiro.values())


def obter_coletas_com_filtros(
    db: Session,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    parceiro_id: Optional[int] = None,
    tipo_operacao: Optional[str] = None,
    pagina: int = 1,
    por_pagina: int = 50
) -> Tuple[List[Coleta], int]:
    """
    Obtém coletas com filtros aplicados e paginação.
    
    Returns:
        Tuple[List[Coleta], total_count]
    """
    # Query base com eager loading
    query = db.query(Coleta).options(
        joinedload(Coleta.coletor),
        joinedload(Coleta.parceiro),
        joinedload(Coleta.tipo_coletor)
    )
    
    # Aplicar filtros de data
    query, _, _ = processar_filtros_data(query, data_inicio, data_fim)
    
    # Filtros adicionais
    if parceiro_id:
        query = query.filter(Coleta.parceiro_id == parceiro_id)
    if tipo_operacao:
        query = query.filter(Coleta.tipo_operacao == tipo_operacao)
    
    # Contar total (antes da paginação)
    total_count = query.count()
    
    # Aplicar paginação
    offset = (pagina - 1) * por_pagina
    coletas = query.order_by(Coleta.data_hora.desc()).offset(offset).limit(por_pagina).all()
    
    return coletas, total_count


def gerar_relatorio(
    db: Session,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    parceiro_id: Optional[int] = None,
    tipo_operacao: Optional[str] = None,
    pagina: int = 1,
    por_pagina: int = 50
) -> Dict:
    """
    Gera relatório completo com dados financeiros e operacionais.
    
    Returns:
        Dict com periodo, resumo, detalhes, paginacao
    """
    # Obter coletas com filtros
    coletas, total_count = obter_coletas_com_filtros(
        db, data_inicio, data_fim, parceiro_id, tipo_operacao, pagina, por_pagina
    )
    
    # Calcular métricas
    metricas = calcular_metricas_financeiras(coletas)
    
    # Agrupar dados
    coletas_por_lixeira = agrupar_coletas_por_lixeira(coletas)
    coletas_por_parceiro = agrupar_coletas_por_parceiro(coletas)
    
    # Serializar detalhes
    detalhes = [coleta_para_dict(c) for c in coletas]
    
    return {
        "periodo": {
            "data_inicio": data_inicio,
            "data_fim": data_fim
        },
        "resumo": {
            **metricas,
            "coletas_por_lixeira": coletas_por_lixeira,
            "coletas_por_parceiro": coletas_por_parceiro
        },
        "detalhes": detalhes,
        "paginacao": {
            "pagina": pagina,
            "por_pagina": por_pagina,
            "total": total_count,
            "total_paginas": (total_count + por_pagina - 1) // por_pagina if total_count > 0 else 0
        }
    }

