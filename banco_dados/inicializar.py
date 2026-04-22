"""
Inicialização do Banco - Dashboard-TRONIK
========================================

Script para configurar e inicializar o banco de dados.
Cria as tabelas e insere dados iniciais.

Funções implementadas:
- criar_banco(): Cria o banco de dados SQLite e todas as tabelas
- inserir_dados_iniciais(): Carrega dados mock do arquivo JSON
- resetar_banco(): Remove e recria todas as tabelas
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from banco_dados.modelos import (
    Base, Coletor, Sensor, Coleta, Usuario,
    Parceiro, TipoMaterial, TipoSensor, TipoColetor
)
from banco_dados.seed_tipos import popular_tipos
import json
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)


def _ambiente_desenvolvimento() -> bool:
    """Alinhado a app.py: sem FLASK_ENV no ambiente, assume development."""
    flask_env = os.getenv("FLASK_ENV", "development").strip().lower()
    return flask_env in ("development", "dev")


def _credenciais_dev_desabilitadas() -> bool:
    return os.getenv("DISABLE_DEV_CREDENTIALS", "").strip().lower() in ("1", "true", "yes")


# ----------------------------------------------------------
# Função: cria o banco de dados SQLite e as tabelas
# ----------------------------------------------------------
def criar_banco(caminho_db="sqlite:///tronik.db"):
    print("Criando banco de dados...")
    engine = create_engine(caminho_db, echo=False)
    Base.metadata.create_all(engine)
    print("Banco criado com sucesso!")
    return engine

# ----------------------------------------------------------
# Função: insere dados iniciais a partir do JSON completo
# ----------------------------------------------------------
def inserir_dados_iniciais(engine, caminho_json="banco_dados/dados/sensores_mock.json"):
    print("Lendo arquivo JSON...")

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        with open(caminho_json, encoding="utf-8") as f:
            dados = json.load(f)

        # --- INSERIR LIXEIRAS ---
        print("Inserindo coletores...")
        for item in dados["lixeiras"]:
            coletor = Coletor(
                localizacao=item["localizacao"],
                nivel_preenchimento=item["nivel_preenchimento"],
                status=item["status"],
                ultima_coleta=datetime.fromisoformat(item["ultima_coleta"]),
                tipo=item["tipo"],
                coordenadas=f"{item['coordenadas']['latitude']}, {item['coordenadas']['longitude']}"
            )
            session.add(coletor)
        session.commit()
        print("Lixeiras inseridas com sucesso!")

        # --- INSERIR COLETAS ---
        print("Inserindo histórico de coletas...")
        for coleta in dados["historico_coletas"]:
            nova_coleta = Coleta(
                coletor_id=coleta["id_lixeira"],
                data_hora=datetime.fromisoformat(coleta["data_coleta"]),
                volume_estimado=float(coleta["nivel_antes"]) - float(coleta["nivel_depois"])
            )
            session.add(nova_coleta)
        session.commit()
        print("Histórico de coletas inserido com sucesso!")

        print("Todos os dados iniciais foram carregados com sucesso!")

    except Exception as e:
        print("ERRO ao inserir dados:", e)
        session.rollback()

    finally:
        session.close()

# ----------------------------------------------------------
# Função: resetar banco (apaga e recria)
# ----------------------------------------------------------
def resetar_banco(engine):
    print("Resetando banco de dados...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("Banco resetado com sucesso!")

# ----------------------------------------------------------
# Função: criar usuário admin padrão
# ----------------------------------------------------------
def criar_usuario_admin(engine):
    """
    Cria um usuário administrador se não existir.

    Credenciais:
    - Preferência: ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD (todos obrigatórios juntos).
    - Em FLASK_ENV=development, se os três ADMIN_* estiverem ausentes e
      DISABLE_DEV_CREDENTIALS não for true, usa DEV_USERNAME / DEV_EMAIL / DEV_PASSWORD
      (padrão: dev / dev@localhost.internal / DevTronik!local).
    - Se definir só parte de ADMIN_*, nada é criado (evita estado inconsistente).
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Verificar se já existe admin
        admin_existente = session.query(Usuario).filter(Usuario.admin == True).first()
        if admin_existente:
            logger.info(f"Usuário admin já existe: {admin_existente.username}")
            return
        
        admin_username = os.getenv("ADMIN_USERNAME")
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")
        tem_admin_completo = bool(admin_username and admin_email and admin_password)
        tem_algum_admin = bool(admin_username or admin_email or admin_password)

        if not tem_admin_completo:
            if tem_algum_admin:
                logger.warning(
                    "⚠️  ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD incompletos. "
                    "Defina os três ou remova todos para usar credenciais de desenvolvimento."
                )
                return
            if _ambiente_desenvolvimento() and not _credenciais_dev_desabilitadas():
                admin_username = os.getenv("DEV_USERNAME", "dev")
                admin_email = os.getenv("DEV_EMAIL", "dev@localhost.internal")
                admin_password = os.getenv("DEV_PASSWORD", "DevTronik!local")
                logger.warning(
                    "⚠️  Ambiente development: primeiro admin será criado com "
                    "DEV_USERNAME/DEV_EMAIL/DEV_PASSWORD (ou valores padrão). "
                    "Desative com DISABLE_DEV_CREDENTIALS=true."
                )
            else:
                logger.warning(
                    "⚠️  Usuário admin não criado: configure ADMIN_* no .env ou "
                    "use FLASK_ENV=development para credenciais DEV_* automáticas."
                )
                return
        
        # Validar força básica da senha (mais flexível para admin inicial)
        if len(admin_password) < 8:
            logger.error("❌ Senha do admin muito curta. Mínimo 8 caracteres.")
            # Não logar a senha em si
            return
        
        # Aviso se a senha não for muito forte, mas permite
        if len(admin_password) < 12:
            logger.warning("⚠️  Senha do admin é curta. Recomendado: pelo menos 12 caracteres.")
            # Não logar a senha em si
        
        # Criar admin
        admin = Usuario(
            username=admin_username,
            email=admin_email,
            nome_completo='Administrador',
            ativo=True,
            admin=True
        )
        admin.set_senha(admin_password)
        
        session.add(admin)
        session.commit()
        logger.info(f"✅ Usuário admin criado: {admin_username}")
        logger.info(f"   Email: {admin_email}")
        
    except Exception as e:
        logger.error(f"ERRO ao criar usuário admin: {e}")
        session.rollback()
        # Não levantar exceção para não quebrar a aplicação
        # O admin pode ser criado manualmente depois
    finally:
        session.close()


def garantir_usuario_dev(engine):
    """Em development, garante utilizador DEV_USERNAME (default dev) com senha conhecida.

    Corre mesmo quando já existe outro admin (ex.: base copiada). Assim há sempre um login
    fixo para testar. Defina DEV_SYNC_PASSWORD=true para repor a senha se já existir.
    Ignorado em produção ou com DISABLE_DEV_CREDENTIALS=true.
    """
    if not _ambiente_desenvolvimento() or _credenciais_dev_desabilitadas():
        return

    username = (os.getenv("DEV_USERNAME") or "dev").strip()
    email = (os.getenv("DEV_EMAIL") or "dev@localhost.internal").strip()
    password = os.getenv("DEV_PASSWORD") or "DevTronik!local"
    sync = os.getenv("DEV_SYNC_PASSWORD", "").strip().lower() in ("1", "true", "yes")

    if len(password) < 8:
        logger.warning("DEV_PASSWORD tem menos de 8 caracteres; garantir_usuario_dev ignorado.")
        return

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        existente = session.query(Usuario).filter(Usuario.username == username).first()
        if existente is None:
            email_ocupado = session.query(Usuario).filter(Usuario.email == email).first()
            if email_ocupado is not None:
                logger.warning(
                    "Não foi criado utilizador dev: email %s já está em uso por outro utilizador.",
                    email,
                )
                return
            u = Usuario(
                username=username,
                email=email,
                nome_completo="Desenvolvimento",
                ativo=True,
                admin=True,
            )
            u.set_senha(password)
            session.add(u)
            session.commit()
            logger.info("Utilizador de desenvolvimento criado: %s (use esta conta para testes locais)", username)
            return

        if sync:
            existente.set_senha(password)
            session.commit()
            logger.info("Senha do utilizador dev '%s' atualizada (DEV_SYNC_PASSWORD).", username)
    except Exception as e:
        logger.error("Erro em garantir_usuario_dev: %s", e)
        session.rollback()
    finally:
        session.close()


# ----------------------------------------------------------
# Execução direta do script
# ----------------------------------------------------------
if __name__ == "__main__":
    engine = criar_banco()
    # Popular tipos antes de inserir dados iniciais
    popular_tipos(engine)
    inserir_dados_iniciais(engine)
    criar_usuario_admin(engine)
    garantir_usuario_dev(engine)


