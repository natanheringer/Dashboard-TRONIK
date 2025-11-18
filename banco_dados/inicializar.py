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
from banco_dados.modelos import Base, Lixeira, Sensor, Coleta, Usuario
import json
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

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
        print("Inserindo lixeiras...")
        for item in dados["lixeiras"]:
            lixeira = Lixeira(
                localizacao=item["localizacao"],
                nivel_preenchimento=item["nivel_preenchimento"],
                status=item["status"],
                ultima_coleta=datetime.fromisoformat(item["ultima_coleta"]),
                tipo=item["tipo"],
                coordenadas=f"{item['coordenadas']['latitude']}, {item['coordenadas']['longitude']}"
            )
            session.add(lixeira)
        session.commit()
        print("Lixeiras inseridas com sucesso!")

        # --- INSERIR COLETAS ---
        print("Inserindo histórico de coletas...")
        for coleta in dados["historico_coletas"]:
            nova_coleta = Coleta(
                lixeira_id=coleta["id_lixeira"],
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
    
    IMPORTANTE: Requer variáveis de ambiente configuradas:
    - ADMIN_USERNAME (obrigatório)
    - ADMIN_EMAIL (obrigatório)
    - ADMIN_PASSWORD (obrigatório)
    
    Se as variáveis não estiverem configuradas, o usuário admin não será criado.
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Verificar se já existe admin
        admin_existente = session.query(Usuario).filter(Usuario.admin == True).first()
        if admin_existente:
            logger.info(f"Usuário admin já existe: {admin_existente.username}")
            return
        
        # Obter credenciais do ambiente (OBRIGATÓRIAS)
        admin_username = os.getenv('ADMIN_USERNAME')
        admin_email = os.getenv('ADMIN_EMAIL')
        admin_password = os.getenv('ADMIN_PASSWORD')
        
        # Validar que todas as credenciais foram fornecidas
        if not admin_username or not admin_email or not admin_password:
            logger.warning(
                "⚠️  Usuário admin não criado: variáveis de ambiente não configuradas.\n"
                "   Configure no arquivo .env:\n"
                "   - ADMIN_USERNAME=seu-usuario\n"
                "   - ADMIN_EMAIL=seu-email@dominio.com\n"
                "   - ADMIN_PASSWORD=sua-senha-forte\n"
                "   Ou crie manualmente via página de registro."
            )
            return
        
        # Validar força básica da senha (mais flexível para admin inicial)
        if len(admin_password) < 8:
            logger.error("❌ Senha do admin muito curta. Mínimo 8 caracteres.")
            return
        
        # Aviso se a senha não for muito forte, mas permite
        if len(admin_password) < 12:
            logger.warning("⚠️  Senha do admin é curta. Recomendado: pelo menos 12 caracteres.")
        
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

# ----------------------------------------------------------
# Execução direta do script
# ----------------------------------------------------------
if __name__ == "__main__":
    engine = criar_banco()
    inserir_dados_iniciais(engine)
    criar_usuario_admin(engine)


