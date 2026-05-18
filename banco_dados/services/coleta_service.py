"""
Serviço de Coletas - Dashboard-TRONIK
======================================
Lógica de negócio para operações com coletas.
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from banco_dados.modelos import Coleta, Coletor
from banco_dados.seguranca import (
    validar_km_percorrido,
    validar_preco_combustivel,
    validar_quantidade_kg,
    validar_tipo_operacao,
)
from banco_dados.utils import utc_now_naive

logger = logging.getLogger(__name__)


def validar_dados_coleta(dados: dict, criar: bool = True, db: Session | None = None) -> list[str]:
    """
    Valida dados de uma coleta.

    Returns:
        Lista de erros (vazia se válido)
    """
    erros = []

    if criar:
        if 'coletor_id' not in dados or not dados['coletor_id']:
            erros.append("Campo 'coletor_id' é obrigatório")
        else:
            if db:
                coletor = db.query(Coletor).filter(Coletor.id == dados['coletor_id']).first()
                if not coletor:
                    erros.append("Coletor não encontrada")

        if 'data_hora' not in dados or not dados['data_hora']:
            erros.append("Campo 'data_hora' é obrigatório")

    # Validar quantidade/volume
    if 'volume_estimado' in dados and dados['volume_estimado'] is not None:
        valido, erro = validar_quantidade_kg(dados['volume_estimado'])
        if not valido:
            erros.append(erro)

    # Validar KM percorrido
    if 'km_percorrido' in dados and dados['km_percorrido'] is not None:
        valido, erro = validar_km_percorrido(dados['km_percorrido'])
        if not valido:
            erros.append(erro)

    # Validar preço de combustível
    if 'preco_combustivel' in dados and dados['preco_combustivel'] is not None:
        valido, erro = validar_preco_combustivel(dados['preco_combustivel'])
        if not valido:
            erros.append(erro)

    # Validar tipo de operação
    if 'tipo_operacao' in dados and dados['tipo_operacao']:
        valido, erro = validar_tipo_operacao(dados['tipo_operacao'])
        if not valido:
            erros.append(erro)

    return erros


def processar_data_hora(data_hora_str: str | None) -> datetime:
    """
    Processa string de data/hora e retorna datetime.
    Se inválido ou None, retorna datetime atual.
    Valida range razoável (2000-2100).
    """
    if not data_hora_str:
        return utc_now_naive()

    try:
        data_obj = datetime.fromisoformat(data_hora_str.replace('Z', '+00:00'))

        # Validar range razoável (não antes de 2000, não depois de 2100)
        min_data = datetime(2000, 1, 1)
        max_data = datetime(2100, 12, 31, 23, 59, 59)

        if data_obj < min_data or data_obj > max_data:
            logger.warning(f"Data fora do range válido (2000-2100): {data_hora_str}. Usando data atual.")
            return utc_now_naive()

        return data_obj
    except Exception as e:
        logger.warning(f"Erro ao processar data_hora: {data_hora_str}. Erro: {e}. Usando data atual.")
        return utc_now_naive()


def criar_coleta(db: Session, dados: dict) -> Coleta:
    """
    Cria uma nova coleta no banco de dados.

    Returns:
        Objeto Coleta criado
    """
    # Processar data_hora
    data_hora = processar_data_hora(dados.get('data_hora'))

    # Criar coleta
    nova_coleta = Coleta(
        coletor_id=dados['coletor_id'],
        data_hora=data_hora,
        volume_estimado=dados.get('volume_estimado'),
        tipo_operacao=dados.get('tipo_operacao'),
        km_percorrido=dados.get('km_percorrido'),
        preco_combustivel=dados.get('preco_combustivel'),
        lucro_por_kg=dados.get('lucro_por_kg'),
        emissao_mtr=dados.get('emissao_mtr', False),
        tipo_coletor_id=dados.get('tipo_coletor_id'),
        parceiro_id=dados.get('parceiro_id')
    )

    db.add(nova_coleta)
    db.commit()
    db.refresh(nova_coleta)

    # Atualizar última coleta da coletor
    coletor = db.query(Coletor).filter(Coletor.id == dados['coletor_id']).first()
    if coletor:
        coletor.ultima_coleta = data_hora
        db.commit()

    logger.info(f"Coleta criada: ID {nova_coleta.id} para coletor {dados['coletor_id']}")
    return nova_coleta


def obter_coletas_com_filtros(
    db: Session,
    coletor_id: int | None = None,
    parceiro_id: int | None = None,
    tipo_operacao: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    pagina: int = 1,
    por_pagina: int = 50
) -> tuple[list[Coleta], int]:
    """
    Obtém coletas com filtros aplicados e paginação.

    Returns:
        Tuple[List[Coleta], total_count]
    """
    query = db.query(Coleta).options(
        joinedload(Coleta.coletor),
        joinedload(Coleta.parceiro),
        joinedload(Coleta.tipo_coletor)
    )

    # Aplicar filtros
    if coletor_id:
        query = query.filter(Coleta.coletor_id == coletor_id)
    if parceiro_id:
        query = query.filter(Coleta.parceiro_id == parceiro_id)
    if tipo_operacao:
        query = query.filter(Coleta.tipo_operacao == tipo_operacao)

    # Filtros de data
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

    # Contar total
    total_count = query.count()

    # Aplicar paginação
    offset = (pagina - 1) * por_pagina
    coletas = query.order_by(Coleta.data_hora.desc()).offset(offset).limit(por_pagina).all()

    return coletas, total_count

