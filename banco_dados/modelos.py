"""
Modelos de Dados - Dashboard-TRONIK
==================================

Define os modelos de dados para o banco SQLite.
Contém as classes que representam as tabelas.

Modelos implementados:
- Lixeira: Representa uma lixeira inteligente com sensores
- Sensor: Representa sensores associados a lixeiras
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
# TABELA: Lixeiras
# ----------------------------------------------------------
class Lixeira(Base):
    __tablename__ = "lixeiras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    localizacao = Column(String(150), nullable=False)
    nivel_preenchimento = Column(Float, default=0.0)
    status = Column(String(20), default="OK")  # OK, alerta, manutencao etc.
    ultima_coleta = Column(DateTime, default=datetime.utcnow)
    tipo = Column(String(50))
    coordenadas = Column(String(100))

    # Relacionamentos
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
    lixeira_id = Column(Integer, ForeignKey("lixeiras.id"))
    tipo = Column(String(50))  # ultrassonico, temperatura, etc.
    bateria = Column(Float, default=100.0)
    ultimo_ping = Column(DateTime, default=datetime.utcnow)

    # Relacionamento reverso
    lixeira = relationship("Lixeira", back_populates="sensores")

    def __repr__(self):
        return f"<Sensor(id={self.id}, tipo={self.tipo}, bateria={self.bateria}%)>"


# ----------------------------------------------------------
# TABELA: Coletas
# ----------------------------------------------------------
class Coleta(Base):
    __tablename__ = "coletas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lixeira_id = Column(Integer, ForeignKey("lixeiras.id"))
    data_hora = Column(DateTime, default=datetime.utcnow)
    volume_estimado = Column(Float)  # diferença entre nível antes/depois da coleta

    lixeira = relationship("Lixeira", back_populates="coletas")

    def __repr__(self):
        return f"<Coleta(id={self.id}, lixeira_id={self.lixeira_id}, volume={self.volume_estimado})>"



