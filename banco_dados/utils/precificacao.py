"""
Utilitários de Precificação - Dashboard-TRONIK
===============================================
Funções auxiliares para cálculos de precificação de serviços.
"""

import logging

logger = logging.getLogger(__name__)

# Preços padrão dos serviços (em reais)
PRECOS_SERVICOS = {
    'coleta_0_40km': 800.0,
    'coleta_40_60km': 850.0,
    'coleta_60_plus': 900.0,
    'palestra': 1000.0,
    'oficina': 800.0,
    'consultoria': 1500.0,
    'instalacao_sensor': 500.0,
    'manutencao': 300.0
}

# Consumo de combustível (km por litro)
CONSUMO_KM_POR_LITRO = 4.0

# Lucro bruto por kg (valor fixo)
LUCRO_BRUTO_POR_KG = 1.0


def calcular_preco_coleta(distancia_km: float, preco_combustivel: float = 5.50) -> float:
    """
    Calcula preço de uma coleta baseado na distância.

    Args:
        distancia_km: Distância em quilômetros
        preco_combustivel: Preço do combustível por litro (padrão: R$ 5,50)

    Returns:
        Preço sugerido para a coleta
    """
    # Preço base por faixa de distância
    if distancia_km <= 40:
        preco_base = PRECOS_SERVICOS['coleta_0_40km']
    elif distancia_km <= 60:
        preco_base = PRECOS_SERVICOS['coleta_40_60km']
    else:
        preco_base = PRECOS_SERVICOS['coleta_60_plus']
        # Adicionar R$ 10 por km adicional acima de 60km
        km_extra = distancia_km - 60
        preco_base += km_extra * 10

    # Ajustar baseado no preço do combustível (se muito alto, aumentar preço)
    if preco_combustivel > 6.0:
        ajuste_combustivel = (preco_combustivel - 5.50) * 10  # R$ 10 por R$ 0,10 de aumento
        preco_base += ajuste_combustivel

    return round(preco_base, 2)


def calcular_lucro_estimado_coleta(
    volume_kg: float,
    distancia_km: float,
    preco_combustivel: float = 5.50
) -> dict[str, float]:
    """
    Calcula lucro estimado de uma coleta.

    Args:
        volume_kg: Volume coletado em kg
        distancia_km: Distância percorrida em km
        preco_combustivel: Preço do combustível por litro

    Returns:
        Dicionário com receita, custos e lucro
    """
    # Receita bruta
    receita_bruta = volume_kg * LUCRO_BRUTO_POR_KG

    # Custo de combustível
    litros_consumidos = distancia_km / CONSUMO_KM_POR_LITRO
    custo_combustivel = litros_consumidos * preco_combustivel

    # Outros custos (estimativa: 10% da receita)
    outros_custos = receita_bruta * 0.10

    # Lucro líquido
    lucro_liquido = receita_bruta - custo_combustivel - outros_custos

    return {
        'receita_bruta': round(receita_bruta, 2),
        'custo_combustivel': round(custo_combustivel, 2),
        'outros_custos': round(outros_custos, 2),
        'lucro_liquido': round(lucro_liquido, 2),
        'margem_percentual': round((lucro_liquido / receita_bruta * 100) if receita_bruta > 0 else 0, 2)
    }


def sugerir_preco_servico(
    tipo_servico: str,
    parametros: dict | None = None
) -> float:
    """
    Sugere preço para um tipo de serviço.

    Args:
        tipo_servico: Tipo do serviço ('coleta', 'palestra', 'oficina', etc.)
        parametros: Parâmetros adicionais (ex: {'distancia_km': 35})

    Returns:
        Preço sugerido
    """
    parametros = parametros or {}

    if tipo_servico == 'coleta':
        distancia = parametros.get('distancia_km', 0)
        preco_combustivel = parametros.get('preco_combustivel', 5.50)
        return calcular_preco_coleta(distancia, preco_combustivel)

    # Outros serviços usam preços fixos
    chave_preco = tipo_servico.lower()
    if chave_preco in PRECOS_SERVICOS:
        return PRECOS_SERVICOS[chave_preco]

    logger.warning(f"Tipo de serviço '{tipo_servico}' não encontrado. Usando preço padrão.")
    return PRECOS_SERVICOS.get('coleta_0_40km', 800.0)


def obter_precos_servicos() -> dict[str, float]:
    """Retorna dicionário com todos os preços de serviços"""
    return PRECOS_SERVICOS.copy()

