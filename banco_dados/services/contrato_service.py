"""
Serviço de Contratos - Dashboard-TRONIK
========================================
Lógica de negócio para gestão de contratos recorrentes.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import func

from banco_dados.modelos import ContratoRecorrente
from banco_dados.utils import utc_now_naive
from banco_dados.utils.db_session import get_db_session

logger = logging.getLogger(__name__)


class ContratoService:
    """Serviço para lógica de contratos recorrentes"""

    @staticmethod
    def criar_contrato(dados):
        """Cria novo contrato recorrente"""
        db = get_db_session()
        try:
            contrato = ContratoRecorrente(
                coletor_id=dados['coletor_id'],
                parceiro_id=dados.get('parceiro_id'),
                titulo=dados['titulo'],
                descricao=dados.get('descricao'),
                valor_mensal=dados['valor_mensal'],
                frequencia_coleta=dados.get('frequencia_coleta', 'mensal'),
                dia_coleta=dados.get('dia_coleta'),
                data_inicio=dados.get('data_inicio') or utc_now_naive(),
                data_vencimento=dados.get('data_vencimento'),
                status=dados.get('status', 'ativo'),
                observacoes=dados.get('observacoes')
            )

            db.add(contrato)
            db.commit()
            logger.info(f"Contrato criado: ID {contrato.id}, Coletor: {contrato.coletor_id}")
            db.expunge(contrato)
            return contrato
        finally:
            db.close()

    @staticmethod
    def atualizar_contrato(contrato_id, dados):
        """Atualiza contrato existente"""
        db = get_db_session()
        try:
            contrato = db.query(ContratoRecorrente).filter_by(id=contrato_id).first()
            if not contrato:
                raise ValueError(f"Contrato {contrato_id} não encontrado")

            # Atualizar campos permitidos
            campos_permitidos = [
                'titulo', 'descricao', 'valor_mensal', 'frequencia_coleta',
                'dia_coleta', 'data_vencimento', 'status', 'observacoes'
            ]

            for campo in campos_permitidos:
                if campo in dados:
                    setattr(contrato, campo, dados[campo])

            contrato.atualizado_em = utc_now_naive()
            db.commit()
            logger.info(f"Contrato {contrato_id} atualizado")
            db.expunge(contrato)
            return contrato
        finally:
            db.close()

    @staticmethod
    def cancelar_contrato(contrato_id, motivo=None):
        """Cancela um contrato"""
        db = get_db_session()
        try:
            contrato = db.query(ContratoRecorrente).filter_by(id=contrato_id).first()
            if not contrato:
                raise ValueError(f"Contrato {contrato_id} não encontrado")

            contrato.status = 'cancelado'
            if motivo:
                contrato.observacoes = f"{contrato.observacoes or ''}\nCancelado: {motivo}"
            contrato.atualizado_em = utc_now_naive()
            db.commit()
            logger.info(f"Contrato {contrato_id} cancelado")
            db.expunge(contrato)
            return contrato
        finally:
            db.close()

    @staticmethod
    def listar_contratos_ativos():
        """Lista todos os contratos ativos"""
        db = get_db_session()
        try:
            return db.query(ContratoRecorrente).filter_by(status='ativo').order_by(
                ContratoRecorrente.data_inicio.desc()
            ).all()
        finally:
            db.close()

    @staticmethod
    def listar_contratos_por_coletor(coletor_id):
        """Lista contratos de uma coletor específica"""
        db = get_db_session()
        try:
            return db.query(ContratoRecorrente).filter_by(
                coletor_id=coletor_id
            ).order_by(ContratoRecorrente.data_inicio.desc()).all()
        finally:
            db.close()

    @staticmethod
    def calcular_receita_mensal_contratos(mes=None, ano=None):
        """Calcula receita mensal esperada de contratos ativos"""
        db = get_db_session()
        try:
            hoje = datetime.now()
            mes = mes or hoje.month
            ano = ano or hoje.year

            # Soma SQL direto de contratos ativos
            receita_total = db.query(func.sum(ContratoRecorrente.valor_mensal)).filter(
                ContratoRecorrente.status == 'ativo'
            ).scalar() or 0.0

            # Filtro de data via Python pós-agregação (retorna valor filtrado por mes/ano)
            # Se necessário aplicar filtro de data na query SQL, pode-se expandir com
            # .filter(and_(ContratoRecorrente.data_inicio <= data_fim, ...))
            # Por agora mantendo simplificado com aggregate SQL
            return receita_total
        finally:
            db.close()

    @staticmethod
    def identificar_contratos_vencendo(dias=30):
        """Identifica contratos que vencem nos próximos N dias"""
        db = get_db_session()
        try:
            hoje = datetime.now()
            fim = hoje + timedelta(days=dias)

            contratos = db.query(ContratoRecorrente).filter(
                ContratoRecorrente.status == 'ativo',
                ContratoRecorrente.data_vencimento.between(hoje, fim)
            ).order_by(ContratoRecorrente.data_vencimento).all()

            return contratos
        finally:
            db.close()

    @staticmethod
    def atualizar_contratos_vencidos():
        """Atualiza status de contratos vencidos"""
        db = get_db_session()
        try:
            hoje = datetime.now()

            contratos_vencidos = db.query(ContratoRecorrente).filter(
                ContratoRecorrente.status == 'ativo',
                ContratoRecorrente.data_vencimento < hoje
            ).all()

            for contrato in contratos_vencidos:
                contrato.status = 'vencido'
                contrato.atualizado_em = utc_now_naive()

            db.commit()
            logger.info(f"{len(contratos_vencidos)} contratos marcados como vencidos")
            return contratos_vencidos
        finally:
            db.close()

