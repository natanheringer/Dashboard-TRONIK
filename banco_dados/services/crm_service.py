"""
Serviço CRM - Dashboard-TRONIK
===============================
Lógica de negócio para CRM e pipeline de vendas.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from banco_dados.modelos import Coletor, Interacao, Pipeline, Tarefa
from banco_dados.services import prospeccao_xgb_service
from banco_dados.services.win_workflow import is_pipeline_won, process_pipeline_win
from banco_dados.utils import utc_now_naive
from banco_dados.utils.db_session import get_db_session

logger = logging.getLogger(__name__)


class CRMService:
    """Serviço para lógica de CRM"""

    # Mapeamento de status para probabilidade padrão
    STATUS_PROBABILIDADE = {
        'lead': 10,
        'contato_inicial': 25,
        'proposta_enviada': 50,
        'negociacao': 75,
        'ganho': 100,
        'fechado': 100,
        'perdido': 0
    }

    @staticmethod
    def criar_pipeline(dados, usuario_id=None):
        """Cria novo item no pipeline"""
        db = get_db_session()
        try:
            pipeline = Pipeline(
                coletor_id=dados.get('coletor_id'),  # Pode ser None para leads sem coletor
                status=dados.get('status', 'lead'),
                valor_estimado=dados.get('valor_estimado', 0.0),
                probabilidade=dados.get('probabilidade', CRMService.STATUS_PROBABILIDADE.get(dados.get('status', 'lead'), 10)),
                proxima_acao=dados.get('proxima_acao'),
                data_proxima_acao=dados.get('data_proxima_acao'),
                responsavel_id=usuario_id,
                origem=dados.get('origem'),
                tipo_servico=dados.get('tipo_servico'),
                observacoes=dados.get('observacoes')
            )

            db.add(pipeline)
            db.commit()
            db.refresh(pipeline)

            # Eager load relacionamentos antes de expurgar
            from sqlalchemy.orm import joinedload
            pipeline = db.query(Pipeline).options(
                joinedload(Pipeline.coletor),
                joinedload(Pipeline.responsavel)
            ).filter_by(id=pipeline.id).first()

            # Registrar interação inicial
            if dados.get('descricao_inicial'):
                CRMService.registrar_interacao(
                    pipeline.id,
                    tipo='outro',
                    descricao=dados['descricao_inicial'],
                    usuario_id=usuario_id
                )

            logger.info(f"Pipeline criado: ID {pipeline.id}, Status: {pipeline.status}")
            db.expunge(pipeline)
            return pipeline
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def atualizar_status(pipeline_id, novo_status, motivo_perda=None):
        """Atualiza status do pipeline"""
        db = get_db_session()
        try:
            from sqlalchemy.orm import joinedload
            pipeline = db.query(Pipeline).options(
                joinedload(Pipeline.coletor),
                joinedload(Pipeline.responsavel)
            ).filter_by(id=pipeline_id).first()

            if not pipeline:
                raise ValueError(f"Pipeline {pipeline_id} não encontrado")

            pipeline.status = novo_status
            pipeline.probabilidade = CRMService.STATUS_PROBABILIDADE.get(novo_status, pipeline.probabilidade)

            if novo_status == 'perdido':
                pipeline.motivo_perda = motivo_perda
                pipeline.fechado_em = utc_now_naive()
            elif is_pipeline_won(novo_status):
                pipeline.fechado_em = utc_now_naive()

            if is_pipeline_won(novo_status):
                process_pipeline_win(db, pipeline)

            db.commit()
            db.refresh(pipeline)
            logger.info(f"Pipeline {pipeline_id} atualizado para status: {novo_status}")
            db.expunge(pipeline)
            return pipeline
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def registrar_interacao(pipeline_id, tipo, descricao, resultado=None, usuario_id=None, duracao_minutos=None):
        """Registra interação com cliente"""
        db = get_db_session()
        try:
            interacao = Interacao(
                pipeline_id=pipeline_id,
                tipo=tipo,
                descricao=descricao,
                resultado=resultado,
                duracao_minutos=duracao_minutos,
                usuario_id=usuario_id
            )

            db.add(interacao)

            # Atualizar data da última interação no pipeline
            pipeline = db.query(Pipeline).filter_by(id=pipeline_id).first()
            if pipeline:
                pipeline.atualizado_em = utc_now_naive()

            db.commit()
            logger.info(f"Interação registrada: Pipeline {pipeline_id}, Tipo: {tipo}")
            db.expunge(interacao)
            return interacao
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get_funil_vendas():
        """Retorna dados do funil de vendas"""
        db = get_db_session()
        try:
            funil = db.query(
                Pipeline.status,
                func.count(Pipeline.id).label('quantidade'),
                func.sum(Pipeline.valor_estimado).label('valor_total'),
                func.avg(Pipeline.probabilidade).label('probabilidade_media')
            ).filter(
                Pipeline.status.in_(['lead', 'contato_inicial', 'proposta_enviada', 'negociacao'])
            ).group_by(Pipeline.status).all()

            return [
                {
                    'status': item.status,
                    'quantidade': item.quantidade,
                    'valor_total': float(item.valor_total or 0),
                    'probabilidade_media': float(item.probabilidade_media or 0)
                }
                for item in funil
            ]
        finally:
            db.close()

    @staticmethod
    def get_proximas_acoes(dias=7):
        """Retorna ações agendadas para os próximos N dias"""
        db = get_db_session()
        try:
            hoje = datetime.now()
            fim = hoje + timedelta(days=dias)

            pipelines = db.query(Pipeline).filter(
                Pipeline.data_proxima_acao.between(hoje, fim),
                ~Pipeline.status.in_(['fechado', 'perdido'])
            ).order_by(Pipeline.data_proxima_acao).all()

            return pipelines
        finally:
            db.close()

    @staticmethod
    def get_clientes_sem_contato(dias=30):
        """Identifica clientes sem interação há N dias"""
        db = get_db_session()
        try:
            limite = datetime.now() - timedelta(days=dias)

            # Subquery: pipelines com interação recente
            from sqlalchemy import select
            pipelines_ativos_ids = db.query(Interacao.pipeline_id).filter(
                Interacao.data >= limite
            ).distinct().subquery()

            # Pipelines sem interação recente (excluindo fechados/perdidos)
            # SQLAlchemy 2.0: select() não precisa de lista
            pipelines_sem_contato = db.query(Pipeline).filter(
                ~Pipeline.id.in_(select(pipelines_ativos_ids.c.pipeline_id)),
                ~Pipeline.status.in_(['fechado', 'perdido'])
            ).all()

            return pipelines_sem_contato
        finally:
            db.close()

    @staticmethod
    def get_estatisticas_periodo(data_inicio, data_fim):
        """Retorna estatísticas do período"""
        db = get_db_session()
        try:
            pipelines_criados = db.query(Pipeline).filter(
                Pipeline.criado_em.between(data_inicio, data_fim)
            ).count()

            pipelines_fechados = db.query(Pipeline).filter(
                Pipeline.fechado_em.between(data_inicio, data_fim),
                Pipeline.status == 'fechado'
            ).count()

            pipelines_perdidos = db.query(Pipeline).filter(
                Pipeline.fechado_em.between(data_inicio, data_fim),
                Pipeline.status == 'perdido'
            ).count()

            valor_fechado = db.query(func.sum(Pipeline.valor_estimado)).filter(
                Pipeline.fechado_em.between(data_inicio, data_fim),
                Pipeline.status == 'fechado'
            ).scalar() or 0

            taxa_conversao = (pipelines_fechados / pipelines_criados * 100) if pipelines_criados > 0 else 0

            return {
                'pipelines_criados': pipelines_criados,
                'pipelines_fechados': pipelines_fechados,
                'pipelines_perdidos': pipelines_perdidos,
                'valor_fechado': float(valor_fechado),
                'taxa_conversao': taxa_conversao
            }
        finally:
            db.close()

    @staticmethod
    def get_estatisticas_gerais():
        """Retorna estatísticas gerais do CRM"""
        db = get_db_session()
        try:
            hoje = datetime.now()
            inicio_mes = datetime(hoje.year, hoje.month, 1)

            # Total de pipelines
            total_pipelines = db.query(Pipeline).count()

            # Pipelines ativos (não fechados/perdidos)
            pipelines_ativos = db.query(Pipeline).filter(
                ~Pipeline.status.in_(['fechado', 'perdido'])
            ).count()

            # Valor total em pipeline
            valor_total_pipeline = db.query(func.sum(Pipeline.valor_estimado)).filter(
                ~Pipeline.status.in_(['fechado', 'perdido'])
            ).scalar() or 0

            # Pipelines do mês
            pipelines_mes = db.query(Pipeline).filter(
                Pipeline.criado_em >= inicio_mes
            ).count()

            # Valor fechado no mês
            valor_fechado_mes = db.query(func.sum(Pipeline.valor_estimado)).filter(
                Pipeline.fechado_em >= inicio_mes,
                Pipeline.status == 'fechado'
            ).scalar() or 0

            # Tarefas pendentes
            tarefas_pendentes = db.query(Tarefa).filter(
                Tarefa.status == 'pendente'
            ).count()

            # Tarefas atrasadas
            tarefas_atrasadas = db.query(Tarefa).filter(
                Tarefa.status == 'pendente',
                Tarefa.data_vencimento < hoje
            ).count()

            # Próximas ações (próximos 7 dias)
            fim_semana = hoje + timedelta(days=7)
            proximas_acoes = db.query(Pipeline).filter(
                Pipeline.data_proxima_acao.between(hoje, fim_semana),
                ~Pipeline.status.in_(['fechado', 'perdido'])
            ).count()

            return {
                'total_pipelines': total_pipelines,
                'pipelines_ativos': pipelines_ativos,
                'valor_total_pipeline': float(valor_total_pipeline),
                'pipelines_mes': pipelines_mes,
                'valor_fechado_mes': float(valor_fechado_mes),
                'tarefas_pendentes': tarefas_pendentes,
                'tarefas_atrasadas': tarefas_atrasadas,
                'proximas_acoes': proximas_acoes
            }
        finally:
            db.close()

    @staticmethod
    def criar_tarefa(dados, usuario_id):
        """Cria nova tarefa"""
        db = get_db_session()
        try:
            tarefa = Tarefa(
                titulo=dados['titulo'],
                descricao=dados.get('descricao'),
                pipeline_id=dados.get('pipeline_id'),
                usuario_id=usuario_id,
                prioridade=dados.get('prioridade', 'media'),
                data_vencimento=dados.get('data_vencimento')
            )

            db.add(tarefa)
            db.commit()
            db.refresh(tarefa)

            # Eager load relacionamentos antes de expurgar
            from sqlalchemy.orm import joinedload
            tarefa = db.query(Tarefa).options(
                joinedload(Tarefa.pipeline).joinedload(Pipeline.coletor),
                joinedload(Tarefa.usuario)
            ).filter_by(id=tarefa.id).first()

            logger.info(f"Tarefa criada: ID {tarefa.id}, Título: {tarefa.titulo}")
            db.expunge(tarefa)
            return tarefa
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def concluir_tarefa(tarefa_id):
        """Marca tarefa como concluída"""
        db = get_db_session()
        try:
            from sqlalchemy.orm import joinedload
            tarefa = db.query(Tarefa).options(
                joinedload(Tarefa.pipeline).joinedload(Pipeline.coletor),
                joinedload(Tarefa.usuario)
            ).filter_by(id=tarefa_id).first()

            if not tarefa:
                raise ValueError(f"Tarefa {tarefa_id} não encontrada")

            tarefa.status = 'concluida'
            tarefa.concluida_em = utc_now_naive()
            db.commit()
            db.refresh(tarefa)
            logger.info(f"Tarefa {tarefa_id} concluída")
            db.expunge(tarefa)
            return tarefa
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get_tarefas_pendentes(usuario_id=None):
        """Retorna tarefas pendentes"""
        db = get_db_session()
        try:
            from sqlalchemy.orm import joinedload
            query = db.query(Tarefa).options(
                joinedload(Tarefa.pipeline).joinedload(Pipeline.coletor),
                joinedload(Tarefa.usuario)
            ).filter_by(status='pendente')

            if usuario_id:
                query = query.filter_by(usuario_id=usuario_id)

            resultado = query.order_by(Tarefa.data_vencimento.asc()).all()
            # Expurgar objetos
            for t in resultado:
                db.expunge(t)
            return resultado
        finally:
            db.close()

    @staticmethod
    def get_tarefas_atrasadas(usuario_id=None):
        """Retorna tarefas atrasadas"""
        db = get_db_session()
        try:
            from sqlalchemy.orm import joinedload
            hoje = datetime.now()
            query = db.query(Tarefa).options(
                joinedload(Tarefa.pipeline).joinedload(Pipeline.coletor),
                joinedload(Tarefa.usuario)
            ).filter(
                Tarefa.status == 'pendente',
                Tarefa.data_vencimento < hoje
            )

            if usuario_id:
                query = query.filter_by(usuario_id=usuario_id)

            resultado = query.order_by(Tarefa.data_vencimento.asc()).all()
            # Expurgar objetos
            for t in resultado:
                db.expunge(t)
            return resultado
        finally:
            db.close()

    @staticmethod
    def _tokens_busca(*textos: str | None) -> set[str]:
        tokens: set[str] = set()
        for texto in textos:
            if not texto:
                continue
            norm = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
            for parte in re.findall(r"[a-z0-9]{3,}", norm.lower()):
                tokens.add(parte)
        return tokens

    @staticmethod
    def _relevancia_candidato(candidato: dict[str, Any], needles: set[str]) -> float:
        empresa = candidato.get("empresa") or {}
        local = candidato.get("local") or {}
        haystack = " ".join(
            str(v or "")
            for v in (
                empresa.get("razao_social"),
                empresa.get("nome_fantasia"),
                empresa.get("bairro"),
                local.get("bairro"),
                local.get("endereco"),
                candidato.get("qid"),
            )
        ).lower()
        if not needles:
            return float(candidato.get("score") or 0)
        hits = sum(1 for token in needles if token in haystack)
        if hits == 0:
            return 0.0
        return float(hits * 100) + float(candidato.get("score") or 0)

    @staticmethod
    def _resumo_candidato(candidato: dict[str, Any]) -> dict[str, Any]:
        empresa = candidato.get("empresa") or {}
        nome = (
            empresa.get("razao_social")
            or empresa.get("nome_fantasia")
            or "Candidato REE"
        )
        return {
            "score_id": candidato.get("id"),
            "score": candidato.get("score"),
            "score_percentil": candidato.get("score_percentil"),
            "prioridade": candidato.get("prioridade"),
            "qid": candidato.get("qid"),
            "ranking_contexto": candidato.get("ranking_contexto"),
            "empresa_nome": nome,
            "empresa_cnpj": empresa.get("cnpj"),
            "bairro": empresa.get("bairro") or (candidato.get("local") or {}).get("bairro"),
        }

    @staticmethod
    def prospeccao_para_pipeline(pipeline_id: int) -> dict[str, Any]:
        """Melhor candidato REE alinhado ao lead/coletor do pipeline."""
        db = get_db_session()
        try:
            pipeline = (
                db.query(Pipeline)
                .options(joinedload(Pipeline.coletor).joinedload(Coletor.parceiro))
                .filter_by(id=pipeline_id)
                .first()
            )
            if not pipeline:
                raise ValueError("Pipeline não encontrado")

            coletor = pipeline.coletor
            parceiro_nome = coletor.parceiro.nome if coletor and coletor.parceiro else None
            localizacao = coletor.localizacao if coletor else None

            needles = CRMService._tokens_busca(
                localizacao,
                parceiro_nome,
                pipeline.observacoes,
                pipeline.proxima_acao,
            )

            qid_hint = None
            if localizacao:
                slug = re.sub(r"[^a-z0-9]+", "", localizacao.lower())
                if len(slug) >= 4:
                    qid_hint = slug

            candidatos = prospeccao_xgb_service.buscar_candidatos_prospeccao(
                db,
                limite=120,
                qid=None,
                prioridade=None,
            )

            if qid_hint:
                por_qid = [c for c in candidatos if qid_hint in (c.get("qid") or "").lower()]
                if por_qid:
                    candidatos = por_qid

            if not candidatos:
                return {
                    "pipeline_id": pipeline_id,
                    "candidato": None,
                    "qid_hint": qid_hint,
                }

            melhor = max(candidatos, key=lambda c: CRMService._relevancia_candidato(c, needles))
            relevancia = CRMService._relevancia_candidato(melhor, needles)
            if needles and relevancia <= 0:
                melhor = max(candidatos, key=lambda c: float(c.get("score") or 0))
                relevancia = float(melhor.get("score") or 0)

            return {
                "pipeline_id": pipeline_id,
                "candidato": CRMService._resumo_candidato(melhor),
                "relevancia": relevancia,
                "qid_hint": qid_hint,
            }
        finally:
            db.close()

