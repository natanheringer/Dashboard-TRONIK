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
- Lixeira: Lixeiras inteligentes com sensores
- Sensor: Sensores associados a lixeiras
- Coleta: Histórico de coletas realizadas
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

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
    criado_em = Column(DateTime, default=datetime.utcnow)
    ultimo_login = Column(DateTime)

    def set_senha(self, senha):
        """Define a senha do usuário usando hash seguro"""
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        """Verifica se a senha fornecida está correta"""
        return check_password_hash(self.senha_hash, senha)

    def __repr__(self):
        return f"<Usuario(id={self.id}, username='{self.username}', admin={self.admin})>"


# ----------------------------------------------------------
# TABELA: Parceiros
# ----------------------------------------------------------
class Parceiro(Base):
    __tablename__ = "parceiros"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(150), unique=True, nullable=False, index=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    lixeiras = relationship("Lixeira", back_populates="parceiro")
    coletas = relationship("Coleta", back_populates="parceiro")

    def __repr__(self):
        return f"<Parceiro(id={self.id}, nome='{self.nome}', ativo={self.ativo})>"


# ----------------------------------------------------------
# TABELA: Tipo de Material
# ----------------------------------------------------------
class TipoMaterial(Base):
    __tablename__ = "tipo_material"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), unique=True, nullable=False, index=True)

    # Relacionamentos
    lixeiras = relationship("Lixeira", back_populates="tipo_material")

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
# TABELA: Lixeiras
# ----------------------------------------------------------
class Lixeira(Base):
    __tablename__ = "lixeiras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    localizacao = Column(String(150), nullable=False)
    nivel_preenchimento = Column(Float, default=0.0)
    status = Column(String(20), default="OK")  # OK, CHEIA, QUEBRADA, etc.
    ultima_coleta = Column(DateTime, default=datetime.utcnow)
    
    # NOVOS CAMPOS (substituem coordenadas string e tipo string)
    latitude = Column(Float)  # Coordenada latitude
    longitude = Column(Float)  # Coordenada longitude
    parceiro_id = Column(Integer, ForeignKey("parceiros.id"), nullable=True, index=True)
    tipo_material_id = Column(Integer, ForeignKey("tipo_material.id"), nullable=True, index=True)

    # Relacionamentos
    parceiro = relationship("Parceiro", back_populates="lixeiras")
    tipo_material = relationship("TipoMaterial", back_populates="lixeiras")
    sensores = relationship("Sensor", back_populates="lixeira", cascade="all, delete-orphan")
    coletas = relationship("Coleta", back_populates="lixeira", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lixeira(id={self.id}, local='{self.localizacao}', nivel={self.nivel_preenchimento}%)>"


# ----------------------------------------------------------
# TABELA: Sensores
# ----------------------------------------------------------
class Sensor(Base):
    __tablename__ = "sensores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lixeira_id = Column(Integer, ForeignKey("lixeiras.id"), nullable=False, index=True)
    tipo_sensor_id = Column(Integer, ForeignKey("tipo_sensor.id"), nullable=True, index=True)
    bateria = Column(Float, default=100.0)
    ultimo_ping = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    lixeira = relationship("Lixeira", back_populates="sensores")
    tipo_sensor = relationship("TipoSensor", back_populates="sensores")

    def __repr__(self):
        tipo_nome = self.tipo_sensor.nome if self.tipo_sensor else "N/A"
        return f"<Sensor(id={self.id}, tipo='{tipo_nome}', bateria={self.bateria}%)>"


# ----------------------------------------------------------
# TABELA: Coletas
# ----------------------------------------------------------
class Coleta(Base):
    __tablename__ = "coletas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lixeira_id = Column(Integer, ForeignKey("lixeiras.id"), nullable=False, index=True)
    data_hora = Column(DateTime, default=datetime.utcnow, index=True)
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
    lixeira = relationship("Lixeira", back_populates="coletas")
    tipo_coletor = relationship("TipoColetor", back_populates="coletas")
    parceiro = relationship("Parceiro", back_populates="coletas")

    def __repr__(self):
        parceiro_nome = self.parceiro.nome if self.parceiro else "N/A"
        return f"<Coleta(id={self.id}, lixeira_id={self.lixeira_id}, data={self.data_hora}, parceiro='{parceiro_nome}')>"
