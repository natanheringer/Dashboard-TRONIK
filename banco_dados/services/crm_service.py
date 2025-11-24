"""
Serviço CRM - Dashboard-TRONIK
===============================
Lógica de negócio para CRM e pipeline de vendas.
"""

from datetime import datetime, timedelta
from sqlalchemy import func
from banco_dados.modelos import Pipeline, Interacao, Tarefa, Coletor
from banco_dados.utils import utc_now_naive
from banco_dados.utils.db_session import get_db_session
import logging

logger = logging.getLogger(__name__)


class CRMService:
    """Serviço para lógica de CRM"""
    
    # Mapeamento de status para probabilidade padrão
    STATUS_PROBABILIDADE = {
        'lead': 10,
        'contato_inicial': 25,
        'proposta_enviada': 50,
        'negociacao': 75,
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
            elif novo_status == 'fechado':
                pipeline.fechado_em = utc_now_naive()
            
            db.commit()
            db.refresh(pipeline)
            logger.info(f"Pipeline {pipeline_id} atualizado para status: {novo_status}")
            db.expunge(pipeline)
            return pipeline
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

