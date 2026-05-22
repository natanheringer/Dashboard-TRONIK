"""
Modelos de Dados - Dashboard-TRONIK
==================================

Define os modelos de dados para o banco SQLite.
Contém as classes que representam as tabelas.

Modelos implementados:
- Usuario: Usuários do sistema
- Parceiro: Parceiros/clientes da Tronik
- TipoMaterial: Tipos de material coletado
- TipoSensor: Tipos de sensores
- TipoColetor: Tipos de coletores
- Coletor: Coletores inteligentes com sensores
- Sensor: Sensores associados a coletores
- Coleta: Histórico de coletas realizadas
"""

import contextlib
from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from banco_dados.utils import utc_now_naive

# Base do SQLAlchemy (todas as tabelas herdam dela)
Base = declarative_base()

# ----------------------------------------------------------
# TABELA: Usuários
# ----------------------------------------------------------
class Usuario(Base, UserMixin):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    nome_completo = Column(String(150))
    ativo = Column(Boolean, default=True)
    admin = Column(Boolean, default=False)
    parceiro_id = Column(Integer, ForeignKey("parceiros.id"), nullable=True, index=True)
    criado_em = Column(DateTime, default=utc_now_naive)
    ultimo_login = Column(DateTime)

    # Relacionamento
    parceiro = relationship("Parceiro", backref="usuarios")

    def set_senha(self, senha):
        """Define a senha do usuário usando hash seguro"""
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        """Verifica se a senha fornecida está correta"""
        return check_password_hash(self.senha_hash, senha)

    def __repr__(self):
        return f"<Usuario(id={self.id}, username='{self.username}', admin={self.admin})>"


# ----------------------------------------------------------
# TABELA: Preferências de Layout do Usuário
# ----------------------------------------------------------
class PreferenciaLayout(Base):
    """Preferências de layout do dashboard comercial por usuário"""
    __tablename__ = "preferencias_layout"
    __table_args__ = (
        Index('idx_pref_usuario', 'usuario_id'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, unique=True, index=True)

    # Ordem dos containers (JSON string com array de IDs)
    ordem_containers = Column(String(2000))  # JSON: ["kpi-meta", "resumo-financeiro", ...]

    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    # Relacionamento
    usuario = relationship("Usuario", backref="preferencia_layout")

    def to_dict(self):
        import json
        try:
            ordem = json.loads(self.ordem_containers) if self.ordem_containers else []
        except (json.JSONDecodeError, TypeError):
            ordem = []
        return {
            'id': self.id,
            'usuario_id': self.usuario_id,
            'ordem_containers': ordem,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None
        }

    def __repr__(self):
        return f"<PreferenciaLayout(id={self.id}, usuario_id={self.usuario_id})>"


# ----------------------------------------------------------
# TABELA: Parceiros
# ----------------------------------------------------------
class Parceiro(Base):
    __tablename__ = "parceiros"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(150), unique=True, nullable=False, index=True)
    cnpj = Column(String(18), unique=True, nullable=True, index=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=utc_now_naive)

    # Relacionamentos
    coletores = relationship("Coletor", back_populates="parceiro")
    coletas = relationship("Coleta", back_populates="parceiro")

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'cnpj': self.cnpj,
            'ativo': self.ativo,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
        }

    def __repr__(self):
        return f"<Parceiro(id={self.id}, nome='{self.nome}', ativo={self.ativo})>"


# ----------------------------------------------------------
# TABELA: Conta comercial (Loló Account)
# ----------------------------------------------------------
class ContaComercial(Base):
    """Conta comercial unificada (CNPJ, prospecção, parceiro operacional)."""
    __tablename__ = "conta_comercial"
    __table_args__ = (
        Index('idx_conta_comercial_cnpj', 'cnpj'),
        Index('idx_conta_comercial_parceiro', 'parceiro_id'),
        Index('idx_conta_comercial_empresa', 'empresa_candidata_id'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    cnpj = Column(String(18), unique=True, nullable=True, index=True)
    razao_social = Column(String(255))
    nome_fantasia = Column(String(255))
    parceiro_id = Column(Integer, ForeignKey("parceiros.id"), nullable=True, index=True)
    empresa_candidata_id = Column(
        Integer, ForeignKey("empresa_candidata.id"), nullable=True, index=True
    )
    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    parceiro = relationship("Parceiro", backref="contas_comerciais")
    empresa_candidata = relationship("EmpresaCandidata", backref="conta_comercial")

    def to_dict(self):
        return {
            'id': self.id,
            'cnpj': self.cnpj,
            'razao_social': self.razao_social,
            'nome_fantasia': self.nome_fantasia,
            'parceiro_id': self.parceiro_id,
            'empresa_candidata_id': self.empresa_candidata_id,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None,
        }

    def __repr__(self):
        return f"<ContaComercial(id={self.id}, cnpj='{self.cnpj}')>"


# ----------------------------------------------------------
# TABELA: Solicitação de Coletor (Landing)
# ----------------------------------------------------------
class SolicitacaoColetor(Base):
    """Solicitações públicas de interesse em ter um coletor (vindas da landing page)."""
    __tablename__ = "solicitacoes_coletor"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(120), nullable=False)
    empresa = Column(String(120))
    localizacao = Column(String(200), nullable=False)
    mensagem = Column(String(1000))
    status = Column(String(20), default="pendente", index=True)  # pendente, aprovado, recusado
    criado_em = Column(DateTime, default=utc_now_naive)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'email': self.email,
            'empresa': self.empresa,
            'localizacao': self.localizacao,
            'mensagem': self.mensagem,
            'status': self.status,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None
        }

    def __repr__(self):
        return f"<Solicitacao(id={self.id}, nome='{self.nome}', status='{self.status}')>"


# ----------------------------------------------------------
# TABELA: Tipo de Material
# ----------------------------------------------------------
class TipoMaterial(Base):
    __tablename__ = "tipo_material"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), unique=True, nullable=False, index=True)

    # Relacionamentos
    coletores = relationship("Coletor", back_populates="tipo_material")

    def __repr__(self):
        return f"<TipoMaterial(id={self.id}, nome='{self.nome}')>"


# ----------------------------------------------------------
# TABELA: Tipo de Sensor
# ----------------------------------------------------------
class TipoSensor(Base):
    __tablename__ = "tipo_sensor"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), unique=True, nullable=False, index=True)

    # Relacionamentos
    sensores = relationship("Sensor", back_populates="tipo_sensor")

    def __repr__(self):
        return f"<TipoSensor(id={self.id}, nome='{self.nome}')>"


# ----------------------------------------------------------
# TABELA: Tipo de Coletor
# ----------------------------------------------------------
class TipoColetor(Base):
    __tablename__ = "tipo_coletor"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), unique=True, nullable=False, index=True)

    # Relacionamentos
    coletas = relationship("Coleta", back_populates="tipo_coletor")

    def __repr__(self):
        return f"<TipoColetor(id={self.id}, nome='{self.nome}')>"


# ----------------------------------------------------------
# TABELA: Coletores
# ----------------------------------------------------------
class Coletor(Base):
    __tablename__ = "coletores"
    __table_args__ = (
        Index('idx_coletor_status', 'status'),
        Index('idx_coletor_parceiro', 'parceiro_id'),
        Index('idx_coletor_tipo_material', 'tipo_material_id'),
        Index('idx_coletor_nivel', 'nivel_preenchimento'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    localizacao = Column(String(150), nullable=False)
    nivel_preenchimento = Column(Float, default=0.0)
    status = Column(String(20), default="OK")  # OK, CHEIA, QUEBRADA, etc.
    ultima_coleta = Column(DateTime, default=utc_now_naive)

    # NOVOS CAMPOS (substituem coordenadas string e tipo string)
    latitude = Column(Float)  # Coordenada latitude
    longitude = Column(Float)  # Coordenada longitude
    parceiro_id = Column(Integer, ForeignKey("parceiros.id"), nullable=True, index=True)
    tipo_material_id = Column(Integer, ForeignKey("tipo_material.id"), nullable=True, index=True)

    # Relacionamentos
    parceiro = relationship("Parceiro", back_populates="coletores")
    tipo_material = relationship("TipoMaterial", back_populates="coletores")
    sensores = relationship("Sensor", back_populates="coletor", cascade="all")
    coletas = relationship("Coleta", back_populates="coletor", cascade="all")

    def __repr__(self):
        return f"<Coletor(id={self.id}, local='{self.localizacao}', nivel={self.nivel_preenchimento}%)>"


# ----------------------------------------------------------
# TABELA: Sensores
# ----------------------------------------------------------
class Sensor(Base):
    __tablename__ = "sensores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=False, index=True)
    tipo_sensor_id = Column(Integer, ForeignKey("tipo_sensor.id"), nullable=True, index=True)
    bateria = Column(Float, default=100.0)
    ultimo_ping = Column(DateTime, default=utc_now_naive)
    # Token opaco para POST /api/sensor/telemetria (firmware); nunca expor em listagens.
    api_token = Column(String(128), nullable=True, index=True)

    # Relacionamentos
    coletor = relationship("Coletor", back_populates="sensores")
    tipo_sensor = relationship("TipoSensor", back_populates="sensores")

    def __repr__(self):
        tipo_nome = self.tipo_sensor.nome if self.tipo_sensor else "N/A"
        return f"<Sensor(id={self.id}, tipo='{tipo_nome}', bateria={self.bateria}%)>"


# ----------------------------------------------------------
# TABELA: Coletas
# ----------------------------------------------------------
class Coleta(Base):
    __tablename__ = "coletas"
    __table_args__ = (
        Index('idx_coleta_data_coletor_parceiro', 'data_hora', 'coletor_id', 'parceiro_id'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=False, index=True)
    data_hora = Column(DateTime, default=utc_now_naive, index=True)
    volume_estimado = Column(Float)  # Mantido para compatibilidade

    # NOVOS CAMPOS (do CSV)
    tipo_operacao = Column(String(50))  # "Avulsa" ou "Campanha"
    km_percorrido = Column(Float)  # Distância percorrida em km
    preco_combustivel = Column(Float)  # Preço do combustível por litro
    lucro_por_kg = Column(Float)  # Lucro em reais por quilograma
    emissao_mtr = Column(Boolean, default=False)  # Se houve emissão de MTR
    tipo_coletor_id = Column(Integer, ForeignKey("tipo_coletor.id"), nullable=True, index=True)
    parceiro_id = Column(Integer, ForeignKey("parceiros.id"), nullable=True, index=True)

    # Relacionamentos
    coletor = relationship("Coletor", back_populates="coletas")
    tipo_coletor = relationship("TipoColetor", back_populates="coletas")
    parceiro = relationship("Parceiro", back_populates="coletas")

    def __repr__(self):
        parceiro_nome = self.parceiro.nome if self.parceiro else "N/A"
        return f"<Coleta(id={self.id}, coletor_id={self.coletor_id}, data={self.data_hora}, parceiro='{parceiro_nome}')>"


# ----------------------------------------------------------
# TABELA: Notificações
# ----------------------------------------------------------
class Notificacao(Base):
    __tablename__ = "notificacoes"
    __table_args__ = (
        Index('idx_notificacao_tipo', 'tipo'),
        Index('idx_notificacao_coletor', 'coletor_id'),
        Index('idx_notificacao_enviada', 'enviada'),
        Index('idx_notificacao_lida', 'lida'),
        Index('idx_notificacao_criada_em', 'criada_em'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(String(50), nullable=False)  # 'lixeira_cheia', 'bateria_baixa', etc.
    titulo = Column(String(200), nullable=False)
    mensagem = Column(String(500), nullable=False)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=True, index=True)
    sensor_id = Column(Integer, ForeignKey("sensores.id"), nullable=True, index=True)
    enviada = Column(Boolean, default=False)
    enviada_em = Column(DateTime, nullable=True)
    lida = Column(Boolean, default=False)
    lida_em = Column(DateTime, nullable=True)
    criada_em = Column(DateTime, default=utc_now_naive)

    # Relacionamentos
    coletor = relationship("Coletor", backref="notificacoes")
    sensor = relationship("Sensor", backref="notificacoes")

    def __repr__(self):
        return f"<Notificacao(id={self.id}, tipo='{self.tipo}', enviada={self.enviada})>"


# ----------------------------------------------------------
# TABELA: Meta Comercial
# ----------------------------------------------------------
class MetaComercial(Base):
    """Meta de faturamento mensal"""
    __tablename__ = "metas_comerciais"
    __table_args__ = (
        Index('idx_meta_mes_ano', 'mes', 'ano'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    mes = Column(Integer, nullable=False)  # 1-12
    ano = Column(Integer, nullable=False)
    valor_meta = Column(Float, nullable=False, default=12000.00)
    valor_realizado = Column(Float, default=0.0)
    percentual_atingido = Column(Float, default=0.0)
    status = Column(String(20), default='em_andamento')  # 'em_andamento', 'atingida', 'nao_atingida'
    observacoes = Column(String(500))
    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    def to_dict(self):
        # Usar getattr com fallback para evitar erros quando objeto está desanexado
        try:
            return {
                'id': getattr(self, 'id', None),
                'mes': getattr(self, 'mes', None),
                'ano': getattr(self, 'ano', None),
                'valor_meta': getattr(self, 'valor_meta', 0.0),
                'valor_realizado': getattr(self, 'valor_realizado', 0.0),
                'percentual_atingido': getattr(self, 'percentual_atingido', 0.0),
                'status': getattr(self, 'status', 'em_andamento'),
                'observacoes': getattr(self, 'observacoes', None),
                'criado_em': self.criado_em.isoformat() if getattr(self, 'criado_em', None) else None,
                'atualizado_em': self.atualizado_em.isoformat() if getattr(self, 'atualizado_em', None) else None
            }
        except Exception:
            # Fallback: usar __dict__ se houver problema
            return {
                'id': self.__dict__.get('id'),
                'mes': self.__dict__.get('mes'),
                'ano': self.__dict__.get('ano'),
                'valor_meta': self.__dict__.get('valor_meta', 0.0),
                'valor_realizado': self.__dict__.get('valor_realizado', 0.0),
                'percentual_atingido': self.__dict__.get('percentual_atingido', 0.0),
                'status': self.__dict__.get('status', 'em_andamento'),
                'observacoes': self.__dict__.get('observacoes'),
                'criado_em': self.__dict__.get('criado_em').isoformat() if self.__dict__.get('criado_em') else None,
                'atualizado_em': self.__dict__.get('atualizado_em').isoformat() if self.__dict__.get('atualizado_em') else None
            }

    def __repr__(self):
        return f"<MetaComercial(id={self.id}, {self.mes}/{self.ano}, meta=R${self.valor_meta:.2f}, realizado={self.percentual_atingido:.1f}%)>"


# ----------------------------------------------------------
# TABELA: Pipeline (CRM)
# ----------------------------------------------------------
class Pipeline(Base):
    """Pipeline de vendas/CRM"""
    __tablename__ = "pipeline"
    __table_args__ = (
        Index('idx_pipeline_status', 'status'),
        Index('idx_pipeline_coletor', 'coletor_id'),
        Index('idx_pipeline_responsavel', 'responsavel_id'),
        Index('idx_pipeline_data_acao', 'data_proxima_acao'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=True, index=True)  # Nullable para leads sem coletor
    status = Column(String(50), nullable=False, default='lead', index=True)
    # Status: 'lead', 'contato_inicial', 'proposta_enviada', 'negociacao', 'fechado', 'perdido'

    valor_estimado = Column(Float, default=0.0)
    probabilidade = Column(Integer, default=10)  # 0-100%

    proxima_acao = Column(String(200))
    data_proxima_acao = Column(DateTime, index=True)
    responsavel_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    conta_comercial_id = Column(
        Integer, ForeignKey("conta_comercial.id"), nullable=True, index=True
    )

    origem = Column(String(100))  # 'indicacao', 'site', 'rede_social', 'evento', etc
    tipo_servico = Column(String(100))  # 'coleta', 'palestra', 'oficina', 'contrato'

    observacoes = Column(String(1000))
    motivo_perda = Column(String(200))  # Preenchido se status='perdido'

    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
    fechado_em = Column(DateTime)

    # Relacionamentos
    coletor = relationship("Coletor", backref="pipeline_items")
    responsavel = relationship("Usuario", backref="pipeline_responsavel")
    conta_comercial = relationship("ContaComercial", backref="pipelines")
    interacoes = relationship("Interacao", back_populates="pipeline", cascade="all, delete-orphan", lazy="dynamic")
    tarefas = relationship("Tarefa", back_populates="pipeline", cascade="all, delete-orphan")

    def to_dict(self):
        from banco_dados.serializers import coletor_para_dict

        # Tentar obter coletor serializado (com tratamento para objetos detached)
        coletor_dict = None
        if self.coletor_id:
            try:
                # Verificar se o objeto está anexado à sessão
                from sqlalchemy.orm import object_session
                session = object_session(self)

                if session and hasattr(self, 'coletor') and self.coletor is not None:
                    # Objeto está na sessão, pode serializar
                    try:
                        coletor_dict = coletor_para_dict(self.coletor)
                    except Exception:
                        # Fallback: dados básicos
                        coletor_dict = {
                            'id': self.coletor_id,
                            'localizacao': getattr(self.coletor, 'localizacao', None)
                        }
                else:
                    # Objeto não está na sessão ou não foi carregado, usar apenas ID
                    coletor_dict = {'id': self.coletor_id}
            except Exception:
                # Fallback final: apenas ID
                coletor_dict = {'id': self.coletor_id}

        # Tentar obter última interação
        ultima_interacao = None
        try:
            if self.interacoes and self.interacoes.first():
                ultima = self.interacoes.order_by(Interacao.data.desc()).first()
                if ultima:
                    ultima_interacao = ultima.to_dict()
        except Exception:
            pass  # Ignorar erro ao acessar interações

        return {
            'id': self.id,
            'coletor': coletor_dict,
            'coletor_id': self.coletor_id,
            'status': self.status,
            'valor_estimado': self.valor_estimado,
            'probabilidade': self.probabilidade,
            'proxima_acao': self.proxima_acao,
            'data_proxima_acao': self.data_proxima_acao.isoformat() if self.data_proxima_acao else None,
            'responsavel': self.responsavel.nome_completo if self.responsavel else None,
            'responsavel_id': self.responsavel_id,
            'conta_comercial_id': self.conta_comercial_id,
            'origem': self.origem,
            'tipo_servico': self.tipo_servico,
            'observacoes': self.observacoes,
            'motivo_perda': self.motivo_perda,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None,
            'fechado_em': self.fechado_em.isoformat() if self.fechado_em else None,
            'dias_no_pipeline': (datetime.now() - self.criado_em).days if self.criado_em else 0,
            'ultima_interacao': ultima_interacao
        }

    def __repr__(self):
        return f"<Pipeline(id={self.id}, status='{self.status}', valor=R${self.valor_estimado:.2f}, prob={self.probabilidade}%)>"


# ----------------------------------------------------------
# TABELA: Interações (CRM)
# ----------------------------------------------------------
class Interacao(Base):
    """Registro de interações com cliente"""
    __tablename__ = "interacoes"
    __table_args__ = (
        Index('idx_interacao_pipeline', 'pipeline_id'),
        Index('idx_interacao_data', 'data'),
        Index('idx_interacao_tipo', 'tipo'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_id = Column(Integer, ForeignKey("pipeline.id"), nullable=False, index=True)
    tipo = Column(String(50), nullable=False, index=True)
    # Tipo: 'ligacao', 'email', 'whatsapp', 'reuniao', 'visita', 'proposta', 'outro'

    descricao = Column(String(1000), nullable=False)
    resultado = Column(String(100))  # 'positivo', 'neutro', 'negativo'

    data = Column(DateTime, default=utc_now_naive, index=True)
    duracao_minutos = Column(Integer)

    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    usuario = relationship("Usuario", backref="interacoes")

    # Anexos podem ser armazenados como JSON (lista de URLs)
    anexos = Column(String(500))  # JSON string com lista de URLs

    criado_em = Column(DateTime, default=utc_now_naive)

    # Relacionamentos
    pipeline = relationship("Pipeline", back_populates="interacoes")

    def to_dict(self):
        return {
            'id': self.id,
            'pipeline_id': self.pipeline_id,
            'tipo': self.tipo,
            'descricao': self.descricao,
            'resultado': self.resultado,
            'data': self.data.isoformat() if self.data else None,
            'duracao_minutos': self.duracao_minutos,
            'usuario': self.usuario.nome_completo if self.usuario else None,
            'usuario_id': self.usuario_id,
            'anexos': self.anexos,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None
        }

    def __repr__(self):
        return f"<Interacao(id={self.id}, tipo='{self.tipo}', pipeline_id={self.pipeline_id})>"


# ----------------------------------------------------------
# TABELA: Tarefas
# ----------------------------------------------------------
class Tarefa(Base):
    """Tarefas e lembretes"""
    __tablename__ = "tarefas"
    __table_args__ = (
        Index('idx_tarefa_status', 'status'),
        Index('idx_tarefa_usuario', 'usuario_id'),
        Index('idx_tarefa_vencimento', 'data_vencimento'),
        Index('idx_tarefa_prioridade', 'prioridade'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    titulo = Column(String(200), nullable=False)
    descricao = Column(String(1000))

    pipeline_id = Column(Integer, ForeignKey("pipeline.id"), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    status = Column(String(20), default='pendente', index=True)  # 'pendente', 'concluida', 'cancelada'
    prioridade = Column(String(20), default='media', index=True)  # 'baixa', 'media', 'alta', 'urgente'

    data_vencimento = Column(DateTime, index=True)
    concluida_em = Column(DateTime)

    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    # Relacionamentos
    pipeline = relationship("Pipeline", back_populates="tarefas")
    usuario = relationship("Usuario", backref="tarefas")

    def to_dict(self):
        from sqlalchemy.orm import object_session
        hoje = datetime.now()

        # Obter cliente de forma segura (tratando objetos detached)
        cliente = None
        if self.pipeline_id:
            try:
                session = object_session(self)
                if session and hasattr(self, 'pipeline') and self.pipeline:
                    try:
                        if hasattr(self.pipeline, 'coletor') and self.pipeline.coletor:
                            cliente = self.pipeline.coletor.localizacao
                    except Exception:
                        # Objeto detached, usar apenas ID
                        pass
            except Exception:
                pass

        # Obter usuário de forma segura
        usuario_nome = None
        try:
            session = object_session(self)
            if session and hasattr(self, 'usuario') and self.usuario:
                with contextlib.suppress(Exception):
                    usuario_nome = self.usuario.nome_completo
        except Exception:
            pass

        return {
            'id': self.id,
            'titulo': self.titulo,
            'descricao': self.descricao,
            'pipeline_id': self.pipeline_id,
            'cliente': cliente,
            'usuario': usuario_nome,
            'usuario_id': self.usuario_id,
            'status': self.status,
            'prioridade': self.prioridade,
            'data_vencimento': self.data_vencimento.isoformat() if self.data_vencimento else None,
            'concluida_em': self.concluida_em.isoformat() if self.concluida_em else None,
            'atrasada': self.data_vencimento < hoje if self.data_vencimento and self.status == 'pendente' else False,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None
        }

    def __repr__(self):
        return f"<Tarefa(id={self.id}, titulo='{self.titulo}', status='{self.status}')>"


# ----------------------------------------------------------
# TABELA: Contratos Recorrentes
# ----------------------------------------------------------
class ContratoRecorrente(Base):
    """Contratos de coleta recorrente"""
    __tablename__ = "contratos_recorrentes"
    __table_args__ = (
        Index('idx_contrato_coletor', 'coletor_id'),
        Index('idx_contrato_status', 'status'),
        Index('idx_contrato_vencimento', 'data_vencimento'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=False, index=True)
    parceiro_id = Column(Integer, ForeignKey("parceiros.id"), nullable=True)

    titulo = Column(String(200), nullable=False)
    descricao = Column(String(1000))

    valor_mensal = Column(Float, nullable=False)
    frequencia_coleta = Column(String(50), default='mensal')  # 'semanal', 'quinzenal', 'mensal', 'bimestral'
    dia_coleta = Column(Integer)  # Dia do mês (1-31) ou dia da semana (1-7) dependendo da frequência

    data_inicio = Column(DateTime, nullable=False)
    data_vencimento = Column(DateTime)
    status = Column(String(20), default='ativo', index=True)  # 'ativo', 'pausado', 'cancelado', 'vencido'

    observacoes = Column(String(1000))
    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    # Relacionamentos
    coletor = relationship("Coletor", backref="contratos")
    parceiro = relationship("Parceiro", backref="contratos")

    def to_dict(self):
        from banco_dados.serializers import coletor_para_dict

        # Tentar obter coletor serializado
        coletor_dict = None
        if self.coletor:
            try:
                coletor_dict = coletor_para_dict(self.coletor)
            except Exception:
                # Fallback se não conseguir serializar
                coletor_dict = {
                    'id': self.coletor.id,
                    'localizacao': self.coletor.localizacao
                }

        return {
            'id': self.id,
            'coletor': coletor_dict,
            'coletor_id': self.coletor_id,
            'parceiro': self.parceiro.nome if self.parceiro else None,
            'parceiro_id': self.parceiro_id,
            'titulo': self.titulo,
            'descricao': self.descricao,
            'valor_mensal': self.valor_mensal,
            'frequencia_coleta': self.frequencia_coleta,
            'dia_coleta': self.dia_coleta,
            'data_inicio': self.data_inicio.isoformat() if self.data_inicio else None,
            'data_vencimento': self.data_vencimento.isoformat() if self.data_vencimento else None,
            'status': self.status,
            'observacoes': self.observacoes,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None
        }

    def __repr__(self):
        return f"<ContratoRecorrente(id={self.id}, coletor_id={self.coletor_id}, valor=R${self.valor_mensal:.2f}/mês, status='{self.status}')>"


# ==============================================================
# MODELOS DE MACHINE LEARNING
# ==============================================================


# ----------------------------------------------------------
# TABELA: Leituras do Sensor (série temporal para ML)
# ----------------------------------------------------------
class LeituraSensor(Base):
    """Série temporal de leituras dos sensores (alimentada pelo ESP32).

    Cada registro representa uma leitura a cada ~15 min.
    Usado pelo Módulo 1 (predição de enchimento) como input.
    """
    __tablename__ = "leituras_sensor"
    __table_args__ = (
        Index('idx_leitura_sensor_ts', 'sensor_id', 'timestamp'),
        Index('idx_leitura_coletor_ts', 'coletor_id', 'timestamp'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    sensor_id = Column(Integer, ForeignKey("sensores.id"), nullable=False, index=True)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=False, index=True)
    nivel = Column(Float, nullable=False)          # 0.0 a 100.0
    bateria = Column(Float)
    temperatura = Column(Float)                     # MPU6050 pode fornecer
    timestamp = Column(DateTime, default=utc_now_naive, index=True)

    # Relacionamentos
    sensor = relationship("Sensor", backref="leituras")
    coletor = relationship("Coletor", backref="leituras_sensor")

    def to_dict(self):
        return {
            'id': self.id,
            'sensor_id': self.sensor_id,
            'coletor_id': self.coletor_id,
            'nivel': self.nivel,
            'bateria': self.bateria,
            'temperatura': self.temperatura,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self):
        return f"<LeituraSensor(id={self.id}, coletor={self.coletor_id}, nivel={self.nivel}%, ts={self.timestamp})>"


# ----------------------------------------------------------
# TABELA: Predição de enchimento (output Módulo 1)
# ----------------------------------------------------------
class PredicaoEnchimento(Base):
    """Previsão de quando cada coletor atingirá nível crítico.

    Gerado pelo Módulo 1 (séries temporais) via APScheduler 2x/dia.
    Algoritmo: statsforecast AutoETS (leve, sem compilação C++).
    """
    __tablename__ = "predicoes_enchimento"
    __table_args__ = (
        Index('idx_predicao_coletor', 'coletor_id'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=False, index=True)
    predicted_full_at = Column(DateTime)             # quando atinge 90%
    horas_restantes = Column(Float)                  # horas até encher
    confianca_lower = Column(DateTime)               # intervalo inferior
    confianca_upper = Column(DateTime)               # intervalo superior
    velocidade_enchimento = Column(Float)             # %/hora (derivada)
    modelo_usado = Column(String(50))                # 'autoets', 'linear', 'arima'
    erro_medio = Column(Float)                       # MAPE do modelo
    dados_suficientes = Column(Boolean, default=True)
    calculado_em = Column(DateTime, default=utc_now_naive)

    # Relacionamento
    coletor = relationship("Coletor", backref="predicao_enchimento")

    def to_dict(self):
        return {
            'id': self.id,
            'coletor_id': self.coletor_id,
            'predicted_full_at': self.predicted_full_at.isoformat() if self.predicted_full_at else None,
            'horas_restantes': self.horas_restantes,
            'confianca_lower': self.confianca_lower.isoformat() if self.confianca_lower else None,
            'confianca_upper': self.confianca_upper.isoformat() if self.confianca_upper else None,
            'velocidade_enchimento': self.velocidade_enchimento,
            'modelo_usado': self.modelo_usado,
            'erro_medio': self.erro_medio,
            'dados_suficientes': self.dados_suficientes,
            'calculado_em': self.calculado_em.isoformat() if self.calculado_em else None,
        }

    def __repr__(self):
        return f"<PredicaoEnchimento(coletor={self.coletor_id}, full_at={self.predicted_full_at}, modelo={self.modelo_usado})>"


# ----------------------------------------------------------
# TABELA: TRONIK Score (output Módulo 2)
# ----------------------------------------------------------
class TronikScore(Base):
    """Score de prioridade 0-100 por coletor (urgência × viabilidade × valor).

    Fase 1: heurística ponderada (domain expertise).
    Fase 2: XGBoost quando count(coletas) >= 200.
    Gerado via APScheduler 1x/dia.
    """
    __tablename__ = "tronik_scores"
    __table_args__ = (
        Index('idx_score_coletor', 'coletor_id'),
        Index('idx_score_valor', 'score'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    coletor_id = Column(Integer, ForeignKey("coletores.id"), nullable=False, index=True)
    score = Column(Float, nullable=False)             # 0-100
    features_json = Column(String(2000))              # JSON com features usadas
    modelo_usado = Column(String(50))                 # 'heuristica', 'xgboost'
    calculado_em = Column(DateTime, default=utc_now_naive)

    # Relacionamento
    coletor = relationship("Coletor", backref="tronik_score")

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'coletor_id': self.coletor_id,
            'score': self.score,
            'features': json.loads(self.features_json) if self.features_json else {},
            'modelo_usado': self.modelo_usado,
            'calculado_em': self.calculado_em.isoformat() if self.calculado_em else None,
        }

    def __repr__(self):
        return f"<TronikScore(coletor={self.coletor_id}, score={self.score:.1f}, modelo={self.modelo_usado})>"


# ----------------------------------------------------------
# TABELA: Narrativa Gerada (output Módulo 3)
# ----------------------------------------------------------
class NarrativaGerada(Base):
    """Texto narrativo de impacto ESG gerado por IA.

    Chain de LLM: Groq (primário) → Ollama (fallback) → Gemini (fallback 2).
    Gerado via APScheduler 1x/mês ou sob demanda.
    """
    __tablename__ = "narrativas_geradas"
    __table_args__ = (
        Index('idx_narrativa_parceiro', 'parceiro_id'),
        Index('idx_narrativa_periodo', 'periodo_inicio', 'periodo_fim'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    parceiro_id = Column(Integer, ForeignKey("parceiros.id"), nullable=False, index=True)
    periodo_inicio = Column(DateTime, nullable=False)
    periodo_fim = Column(DateTime, nullable=False)
    texto = Column(String(5000), nullable=False)
    dados_input_json = Column(String(2000))           # dados usados para gerar
    modelo_usado = Column(String(100))                # 'groq/llama-3.1-70b', 'ollama/deepseek-r1:8b', etc.
    provider_usado = Column(String(50))               # 'groq', 'ollama', 'gemini'
    tempo_geracao_ms = Column(Integer)                 # latência
    validacao_ok = Column(Boolean, default=True)       # números batem com input?
    gerado_em = Column(DateTime, default=utc_now_naive)

    # Relacionamento
    parceiro = relationship("Parceiro", backref="narrativas")

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'parceiro_id': self.parceiro_id,
            'periodo_inicio': self.periodo_inicio.isoformat() if self.periodo_inicio else None,
            'periodo_fim': self.periodo_fim.isoformat() if self.periodo_fim else None,
            'texto': self.texto,
            'dados_input': json.loads(self.dados_input_json) if self.dados_input_json else {},
            'modelo_usado': self.modelo_usado,
            'provider_usado': self.provider_usado,
            'tempo_geracao_ms': self.tempo_geracao_ms,
            'validacao_ok': self.validacao_ok,
            'gerado_em': self.gerado_em.isoformat() if self.gerado_em else None,
        }

    def __repr__(self):
        preview = self.texto[:60] + '...' if self.texto and len(self.texto) > 60 else self.texto
        return f"<NarrativaGerada(parceiro={self.parceiro_id}, provider={self.provider_usado}, texto='{preview}')>"


# ----------------------------------------------------------
# TABELA: Conversas da Nik
# ----------------------------------------------------------
class NikConversa(Base):
    """Histórico persistido das interações da Nik por usuário."""
    __tablename__ = "nik_conversas"
    __table_args__ = (
        Index('idx_nik_conversa_usuario', 'usuario_id'),
        Index('idx_nik_conversa_thread', 'thread_id'),
        Index('idx_nik_conversa_criado_em', 'criado_em'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    thread_id = Column(String(80), default='main', index=True)
    pergunta = Column(String(4000), nullable=False)
    resposta = Column(String(8000), nullable=False)
    contexto_modo = Column(String(20), default='real')
    modelo_usado = Column(String(120))
    fonte = Column(String(20), default='modelo')
    resumo_thread = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=utc_now_naive, index=True)

    usuario = relationship("Usuario", backref="nik_conversas")

    def to_dict(self):
        return {
            'id': self.id,
            'usuario_id': self.usuario_id,
            'thread_id': self.thread_id,
            'pergunta': self.pergunta,
            'resposta': self.resposta,
            'contexto_modo': self.contexto_modo,
            'modelo_usado': self.modelo_usado,
            'fonte': self.fonte,
            'resumo_thread': self.resumo_thread,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
        }


# ----------------------------------------------------------
# TABELA: Relatórios executivos da Nik
# ----------------------------------------------------------
class NikRelatorioGerado(Base):
    """Relatórios executivos estruturados gerados pela Nik para uso interno."""
    __tablename__ = "nik_relatorios_gerados"
    __table_args__ = (
        Index('idx_nik_rel_usuario', 'usuario_id'),
        Index('idx_nik_rel_periodo', 'periodo_inicio', 'periodo_fim'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    parceiro_id = Column(Integer, ForeignKey("parceiros.id"), nullable=True, index=True)
    periodo_inicio = Column(DateTime, nullable=False)
    periodo_fim = Column(DateTime, nullable=False)
    formato = Column(String(20), default='json')
    titulo = Column(String(200), nullable=False)
    conteudo_json = Column(String(12000), nullable=False)
    conteudo_markdown = Column(String(12000))
    modelo_usado = Column(String(120))
    fonte = Column(String(20), default='modelo')
    criado_em = Column(DateTime, default=utc_now_naive, index=True)

    usuario = relationship("Usuario", backref="nik_relatorios")
    parceiro = relationship("Parceiro", backref="nik_relatorios")

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'usuario_id': self.usuario_id,
            'parceiro_id': self.parceiro_id,
            'periodo_inicio': self.periodo_inicio.isoformat() if self.periodo_inicio else None,
            'periodo_fim': self.periodo_fim.isoformat() if self.periodo_fim else None,
            'formato': self.formato,
            'titulo': self.titulo,
            'conteudo': json.loads(self.conteudo_json) if self.conteudo_json else {},
            'conteudo_markdown': self.conteudo_markdown,
            'modelo_usado': self.modelo_usado,
            'fonte': self.fonte,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
        }


# ----------------------------------------------------------
# TABELAS: Prospecção REE com Learning-to-Rank
# ----------------------------------------------------------
class EmpresaCandidata(Base):
    """Empresa elegível para prospecção de REE/e-waste.

    CNPJ fica como texto para compatibilidade com o formato alfanumérico previsto.
    """
    __tablename__ = "empresa_candidata"
    __table_args__ = (
        Index('idx_empresa_candidata_cnpj', 'cnpj'),
        Index('idx_empresa_candidata_cnae', 'cnae_principal'),
        Index('idx_empresa_candidata_situacao', 'situacao_cadastral'),
        Index('idx_empresa_candidata_origem', 'origem'),
        Index('idx_empresa_candidata_pipeline', 'pipeline_id'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    cnpj = Column(String(32), unique=True, nullable=False)
    razao_social = Column(String(255), nullable=False)
    nome_fantasia = Column(String(255))
    cnae_principal = Column(String(16), index=True)
    cnae_secundarios_json = Column(Text)
    porte = Column(String(80))
    natureza_juridica = Column(String(120))
    situacao_cadastral = Column(String(80), default='ATIVA', index=True)
    data_abertura = Column(DateTime)
    endereco_normalizado = Column(String(500))
    bairro = Column(String(120), index=True)
    cep = Column(String(20), index=True)
    municipio = Column(String(120), default='Brasília')
    uf = Column(String(2), default='DF', index=True)
    telefone = Column(String(80))
    email = Column(String(180))
    origem = Column(String(80), default='manual')
    pipeline_id = Column(Integer, ForeignKey("pipeline.id"), nullable=True, index=True)
    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    locais = relationship("LocalCandidato", back_populates="empresa")
    feature_snapshots = relationship("FeatureSnapshotProspeccao", back_populates="empresa")
    pipeline = relationship("Pipeline", backref="empresas_candidatas")

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'cnpj': self.cnpj,
            'razao_social': self.razao_social,
            'nome_fantasia': self.nome_fantasia,
            'cnae_principal': self.cnae_principal,
            'cnae_secundarios': json.loads(self.cnae_secundarios_json) if self.cnae_secundarios_json else [],
            'porte': self.porte,
            'natureza_juridica': self.natureza_juridica,
            'situacao_cadastral': self.situacao_cadastral,
            'endereco_normalizado': self.endereco_normalizado,
            'bairro': self.bairro,
            'cep': self.cep,
            'municipio': self.municipio,
            'uf': self.uf,
            'telefone': self.telefone,
            'email': self.email,
            'origem': self.origem,
            'pipeline_id': self.pipeline_id,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None,
        }


class LocalCandidato(Base):
    """Local físico associado a uma empresa candidata."""
    __tablename__ = "local_candidato"
    __table_args__ = (
        Index('idx_local_empresa', 'empresa_id'),
        Index('idx_local_ra', 'ra'),
        Index('idx_local_qid', 'qid'),
        Index('idx_local_lat_lon', 'latitude', 'longitude'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # CONSTRAINT: empresa_id obrigatório para evitar locais órfãos que causam crashes
    empresa_id = Column(Integer, ForeignKey("empresa_candidata.id", ondelete="CASCADE"), nullable=False, index=True)
    endereco = Column(String(500))
    latitude = Column(Float)
    longitude = Column(Float)
    ra = Column(String(120), index=True)
    bairro = Column(String(120), index=True)
    cep = Column(String(20), index=True)
    geocode_quality = Column(Float, default=0.0)
    categoria_operacional = Column(String(120))
    qid = Column(String(160), index=True)
    origem = Column(String(80), default='manual')
    criado_em = Column(DateTime, default=utc_now_naive)
    atualizado_em = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    empresa = relationship("EmpresaCandidata", back_populates="locais")
    feature_snapshots = relationship("FeatureSnapshotProspeccao", back_populates="local")

    def to_dict(self):
        return {
            'id': self.id,
            'empresa_id': self.empresa_id,
            'endereco': self.endereco,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'ra': self.ra,
            'bairro': self.bairro,
            'cep': self.cep,
            'geocode_quality': self.geocode_quality,
            'categoria_operacional': self.categoria_operacional,
            'qid': self.qid,
            'origem': self.origem,
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
            'atualizado_em': self.atualizado_em.isoformat() if self.atualizado_em else None,
        }


class FontePublicaRegistro(Base):
    """Registro bruto rastreável vindo de fonte pública."""
    __tablename__ = "fonte_publica_registro"
    __table_args__ = (
        Index('idx_fonte_publica_origem', 'origem'),
        Index('idx_fonte_publica_hash', 'registro_hash'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    origem = Column(String(80), nullable=False, index=True)
    origem_id = Column(String(200))
    registro_hash = Column(String(80), unique=True, nullable=False)
    payload_json = Column(Text, nullable=False)
    ingerido_em = Column(DateTime, default=utc_now_naive, index=True)

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'origem': self.origem,
            'origem_id': self.origem_id,
            'registro_hash': self.registro_hash,
            'payload': json.loads(self.payload_json) if self.payload_json else {},
            'ingerido_em': self.ingerido_em.isoformat() if self.ingerido_em else None,
        }


class FeatureSnapshotProspeccao(Base):
    """Features versionadas para treino e scoring do ranker de prospecção."""
    __tablename__ = "feature_snapshot_prospeccao"
    __table_args__ = (
        Index('idx_feature_snapshot_empresa', 'empresa_id'),
        Index('idx_feature_snapshot_local', 'local_id'),
        Index('idx_feature_snapshot_qid', 'qid'),
        Index('idx_feature_snapshot_pipeline', 'pipeline_version'),
        Index('idx_feature_snapshot_pipeline_qid_id', 'pipeline_version', 'qid', 'id'),
        UniqueConstraint('empresa_id', 'local_id', 'pipeline_version', name='uq_feature_snapshot_empresa_local_pipeline'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("empresa_candidata.id"), nullable=True, index=True)
    local_id = Column(Integer, ForeignKey("local_candidato.id"), nullable=True, index=True)
    pipeline_version = Column(String(80), nullable=False, index=True)
    qid = Column(String(160), nullable=False, index=True)
    label_ordinal = Column(Integer, default=0)
    features_json = Column(Text, nullable=False)
    feature_schema_json = Column(Text, nullable=False)
    criado_em = Column(DateTime, default=utc_now_naive, index=True)

    empresa = relationship("EmpresaCandidata", back_populates="feature_snapshots")
    local = relationship("LocalCandidato", back_populates="feature_snapshots")
    scores = relationship("ScoreProspeccao", back_populates="snapshot")

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'empresa_id': self.empresa_id,
            'local_id': self.local_id,
            'pipeline_version': self.pipeline_version,
            'qid': self.qid,
            'label_ordinal': self.label_ordinal,
            'features': json.loads(self.features_json) if self.features_json else {},
            'feature_schema': json.loads(self.feature_schema_json) if self.feature_schema_json else [],
            'criado_em': self.criado_em.isoformat() if self.criado_em else None,
        }


class ModeloProspeccao(Base):
    """Artefato versionado do ranker de prospecção."""
    __tablename__ = "modelo_prospeccao"
    __table_args__ = (
        Index('idx_modelo_prospeccao_versao', 'versao'),
        Index('idx_modelo_prospeccao_ativo', 'ativo'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    versao = Column(String(120), unique=True, nullable=False)
    algoritmo = Column(String(80), nullable=False)
    objetivo = Column(String(80), default='rank:ndcg')
    pipeline_version = Column(String(80), nullable=False)
    feature_schema_json = Column(Text, nullable=False)
    hiperparametros_json = Column(Text)
    metricas_json = Column(Text)
    artefato_path = Column(String(500))
    ativo = Column(Boolean, default=False, index=True)
    treinado_em = Column(DateTime, default=utc_now_naive, index=True)

    scores = relationship("ScoreProspeccao", back_populates="modelo")

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'versao': self.versao,
            'algoritmo': self.algoritmo,
            'objetivo': self.objetivo,
            'pipeline_version': self.pipeline_version,
            'feature_schema': json.loads(self.feature_schema_json) if self.feature_schema_json else [],
            'hiperparametros': json.loads(self.hiperparametros_json) if self.hiperparametros_json else {},
            'metricas': json.loads(self.metricas_json) if self.metricas_json else {},
            'artefato_path': self.artefato_path,
            'ativo': self.ativo,
            'treinado_em': self.treinado_em.isoformat() if self.treinado_em else None,
        }


class ScoreProspeccao(Base):
    """Score e ranking publicados para consumo da dashboard e da Nik."""
    __tablename__ = "score_prospeccao"
    __table_args__ = (
        Index('idx_score_prospeccao_modelo', 'modelo_id'),
        Index('idx_score_prospeccao_qid_rank', 'qid', 'ranking_contexto'),
        Index('idx_score_prospeccao_prioridade', 'prioridade'),
        Index('idx_score_prospeccao_modelo_pipeline', 'modelo_id', 'pipeline_version'),
        Index('idx_score_prospeccao_modelo_prio_score', 'modelo_id', 'prioridade', 'score'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("feature_snapshot_prospeccao.id"), nullable=False, index=True)
    modelo_id = Column(Integer, ForeignKey("modelo_prospeccao.id"), nullable=False, index=True)
    empresa_id = Column(Integer, ForeignKey("empresa_candidata.id", ondelete="CASCADE"), nullable=True, index=True)
    local_id = Column(Integer, ForeignKey("local_candidato.id", ondelete="CASCADE"), nullable=True, index=True)
    qid = Column(String(160), nullable=False, index=True)
    score = Column(Float, nullable=False)
    ranking_contexto = Column(Integer, nullable=False)
    prioridade = Column(String(20), default='media', index=True)
    # RASTREABILIDADE: versão do pipeline que gerou as features usadas neste score
    pipeline_version = Column(String(80), nullable=True, index=True)
    motivos_json = Column(Text)
    calculado_em = Column(DateTime, default=utc_now_naive, index=True)

    snapshot = relationship("FeatureSnapshotProspeccao", back_populates="scores")
    modelo = relationship("ModeloProspeccao", back_populates="scores")
    empresa = relationship("EmpresaCandidata")
    local = relationship("LocalCandidato")

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'snapshot_id': self.snapshot_id,
            'modelo_id': self.modelo_id,
            'empresa_id': self.empresa_id,
            'local_id': self.local_id,
            'qid': self.qid,
            'score': self.score,
            'ranking_contexto': self.ranking_contexto,
            'prioridade': self.prioridade,
            'pipeline_version': self.pipeline_version,
            'motivos': json.loads(self.motivos_json) if self.motivos_json else [],
            'calculado_em': self.calculado_em.isoformat() if self.calculado_em else None,
        }
