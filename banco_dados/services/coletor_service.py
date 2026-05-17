"""
Serviço de Coletores - Dashboard-TRONIK
=======================================
Lógica de negócio para operações com coletores.
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from banco_dados.modelos import Coletor, Parceiro, TipoMaterial
from banco_dados.utils import utc_now_naive
from banco_dados.seguranca import (
    validar_nivel_preenchimento, validar_latitude, validar_longitude,
    sanitizar_string
)
import logging

logger = logging.getLogger(__name__)

# Alinhado a preview_service.NIVEL_ATENCAO e notificacoes.NIVEL_ALERTA_LIXEIRA
NIVEL_ALERTA_ALTO = 80.0
_STATUS_INATIVO = frozenset({"QUEBRADA", "MANUTENCAO", "MANUTENÇÃO"})


def _status_ativo_expr():
    st = func.upper(func.coalesce(Coletor.status, "OK"))
    return ~st.in_(tuple(_STATUS_INATIVO))


def resumo_operacional(db: Session) -> Dict[str, Any]:
    """
    Resumo operacional agregado dos coletores.

    Returns:
        total_coletores, ativos, alerta_nivel_alto e sem_geocode (se lat/lng existirem).
    """
    total_coletores = db.query(func.count(Coletor.id)).scalar() or 0
    ativos = db.query(func.count(Coletor.id)).filter(_status_ativo_expr()).scalar() or 0
    alerta_nivel_alto = (
        db.query(func.count(Coletor.id))
        .filter(
            Coletor.nivel_preenchimento >= NIVEL_ALERTA_ALTO,
            _status_ativo_expr(),
        )
        .scalar()
        or 0
    )

    resumo: Dict[str, Any] = {
        "total_coletores": total_coletores,
        "ativos": ativos,
        "alerta_nivel_alto": alerta_nivel_alto,
    }
    if hasattr(Coletor, "latitude") and hasattr(Coletor, "longitude"):
        resumo["sem_geocode"] = (
            db.query(func.count(Coletor.id))
            .filter(or_(Coletor.latitude.is_(None), Coletor.longitude.is_(None)))
            .scalar()
            or 0
        )
    return resumo


def validar_dados_coletor(dados: Dict, criar: bool = True, db: Optional[Session] = None) -> List[str]:
    """
    Valida dados de uma coletor.
    
    Returns:
        Lista de erros (vazia se válido)
    """
    erros = []
    
    if criar:
        if 'localizacao' not in dados or not dados['localizacao']:
            erros.append("Campo 'localizacao' é obrigatório")
    else:
        if 'localizacao' in dados and not dados['localizacao']:
            erros.append("Campo 'localizacao' não pode ser vazio")
    
    if 'nivel_preenchimento' in dados:
        valido, erro = validar_nivel_preenchimento(dados['nivel_preenchimento'])
        if not valido:
            erros.append(erro)
    
    # Validar latitude
    if 'latitude' in dados and dados['latitude'] is not None:
        valido, erro = validar_latitude(dados['latitude'])
        if not valido:
            erros.append(erro)
    
    # Validar longitude
    if 'longitude' in dados and dados['longitude'] is not None:
        valido, erro = validar_longitude(dados['longitude'])
        if not valido:
            erros.append(erro)
    
    # Validar parceiro_id (se fornecido)
    if 'parceiro_id' in dados and dados['parceiro_id'] is not None and db:
        parceiro = db.query(Parceiro).filter(Parceiro.id == dados['parceiro_id']).first()
        if not parceiro:
            erros.append("Parceiro não encontrado")
    
    # Validar tipo_material_id (se fornecido)
    if 'tipo_material_id' in dados and dados['tipo_material_id'] is not None and db:
        tipo_material = db.query(TipoMaterial).filter(TipoMaterial.id == dados['tipo_material_id']).first()
        if not tipo_material:
            erros.append("Tipo de material não encontrado")
    
    return erros


def processar_ultima_coleta(ultima_coleta_str: Optional[str]) -> datetime:
    """
    Processa string de última coleta e retorna datetime.
    Se inválido ou None, retorna datetime atual.
    """
    if not ultima_coleta_str:
        return utc_now_naive()
    
    try:
        return datetime.fromisoformat(ultima_coleta_str.replace('Z', '+00:00'))
    except Exception:
        logger.warning(f"Erro ao processar ultima_coleta: {ultima_coleta_str}. Usando data atual.")
        return utc_now_naive()


def criar_coletor(db: Session, dados: Dict) -> Coletor:
    """
    Cria uma nova coletor no banco de dados.
    
    Returns:
        Objeto Coletor criado
    """
    # Sanitizar localização
    localizacao = sanitizar_string(dados.get('localizacao', ''), max_length=150)
    if not localizacao:
        raise ValueError("Localização é obrigatória")
    
    # Processar última coleta
    ultima_coleta = processar_ultima_coleta(dados.get('ultima_coleta'))
    
    # Criar coletor
    nova_lixeira = Coletor(
        localizacao=localizacao,
        nivel_preenchimento=float(dados.get('nivel_preenchimento', 0.0)),
        status=dados.get('status', 'OK'),
        ultima_coleta=ultima_coleta,
        latitude=dados.get('latitude'),
        longitude=dados.get('longitude'),
        parceiro_id=dados.get('parceiro_id'),
        tipo_material_id=dados.get('tipo_material_id')
    )
    
    db.add(nova_lixeira)
    db.commit()
    db.refresh(nova_lixeira)
    
    logger.info(f"Coletor criada: ID {nova_lixeira.id} - {localizacao}")
    return nova_lixeira


def atualizar_coletor(db: Session, coletor: Coletor, dados: Dict) -> Coletor:
    """
    Atualiza uma coletor existente.
    
    Returns:
        Objeto Coletor atualizado
    """
    # Atualizar localização
    if 'localizacao' in dados:
        nova_localizacao = sanitizar_string(dados['localizacao'], max_length=150)
        coletor.localizacao = nova_localizacao
    
    # Atualizar nível de preenchimento
    if 'nivel_preenchimento' in dados:
        coletor.nivel_preenchimento = float(dados['nivel_preenchimento'])
    
    # Atualizar status
    if 'status' in dados:
        coletor.status = dados['status']
    
    # Atualizar última coleta
    if 'ultima_coleta' in dados and dados['ultima_coleta']:
        coletor.ultima_coleta = processar_ultima_coleta(dados['ultima_coleta'])
    
    # Atualizar coordenadas
    if 'latitude' in dados:
        coletor.latitude = dados['latitude'] if dados['latitude'] is not None else None
    if 'longitude' in dados:
        coletor.longitude = dados['longitude'] if dados['longitude'] is not None else None
    
    # Atualizar relacionamentos
    if 'parceiro_id' in dados:
        coletor.parceiro_id = dados['parceiro_id'] if dados['parceiro_id'] is not None else None
    if 'tipo_material_id' in dados:
        coletor.tipo_material_id = dados['tipo_material_id'] if dados['tipo_material_id'] is not None else None
    
    db.commit()
    db.refresh(coletor)
    
    logger.info(f"Coletor atualizada: ID {coletor.id}")
    return coletor


def obter_coletores_com_filtros(
    db: Session,
    status: Optional[str] = None,
    parceiro_id: Optional[int] = None,
    pagina: int = 1,
    por_pagina: int = 100
) -> Tuple[List[Coletor], int]:
    """
    Obtém coletores com filtros aplicados e paginação.
    
    Returns:
        Tuple[List[Coletor], total_count]
    """
    query = db.query(Coletor).options(
        joinedload(Coletor.parceiro),
        joinedload(Coletor.tipo_material)
    )
    
    # Aplicar filtros
    if status:
        query = query.filter(Coletor.status == status)
    if parceiro_id:
        query = query.filter(Coletor.parceiro_id == parceiro_id)
    
    # Contar total
    total_count = query.count()
    
    # Aplicar paginação
    offset = (pagina - 1) * por_pagina
    coletores = query.order_by(Coletor.id).offset(offset).limit(por_pagina).all()
    
    return coletores, total_count


# Compat: testes e código legado ainda importam estes nomes.
obter_lixeiras_com_filtros = obter_coletores_com_filtros
validar_dados_lixeira = validar_dados_coletor

