"""
Inicialização do Banco - Dashboard-TRONIK
========================================

Script para configurar e inicializar o banco de dados.
Cria as tabelas e insere dados iniciais.

TODO para a equipe Backend:
- Configurar conexão com SQLite
- Criar todas as tabelas
- Inserir dados mock iniciais
- Implementar funções de reset/backup
"""

# TODO: Importar dependências necessárias

# TODO: Função para criar banco de dados

# TODO: Função para criar tabelas

# TODO: Função para inserir dados iniciais

# TODO: Função para resetar banco

# TODO: Executar inicialização se chamado diretamente 

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from banco_dados.modelos import Base, Lixeira, Sensor, Coleta
import json
from datetime import datetime

# ----------------------------------------------------------
# Função: cria o banco de dados SQLite e as tabelas
# ----------------------------------------------------------
def criar_banco(caminho_db="sqlite:///tronik.db"):
    print("🚀 Criando banco de dados...")
    engine = create_engine(caminho_db, echo=False)
    Base.metadata.create_all(engine)
    print("✅ Banco criado com sucesso!")
    return engine

# ----------------------------------------------------------
# Função: insere dados iniciais a partir do JSON completo
# ----------------------------------------------------------
def inserir_dados_iniciais(engine, caminho_json="banco_dados/dados/sensores_mock.json"):
    print("📥 Lendo arquivo JSON...")

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        with open(caminho_json, encoding="utf-8") as f:
            dados = json.load(f)

        # --- INSERIR LIXEIRAS ---
        print("🗑️ Inserindo lixeiras...")
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
        print("✅ Lixeiras inseridas com sucesso!")

        # --- INSERIR COLETAS ---
        print("🚛 Inserindo histórico de coletas...")
        for coleta in dados["historico_coletas"]:
            nova_coleta = Coleta(
                lixeira_id=coleta["id_lixeira"],
                data_hora=datetime.fromisoformat(coleta["data_coleta"]),
                volume_estimado=float(coleta["nivel_antes"]) - float(coleta["nivel_depois"])
            )
            session.add(nova_coleta)
        session.commit()
        print("✅ Histórico de coletas inserido com sucesso!")

        print("🎉 Todos os dados iniciais foram carregados com sucesso!")

    except Exception as e:
        print("❌ Erro ao inserir dados:", e)
        session.rollback()

    finally:
        session.close()

# ----------------------------------------------------------
# Função: resetar banco (apaga e recria)
# ----------------------------------------------------------
def resetar_banco(engine):
    print("🧹 Resetando banco de dados...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("✅ Banco resetado com sucesso!")

# ----------------------------------------------------------
# Execução direta do script
# ----------------------------------------------------------
if __name__ == "__main__":
    engine = criar_banco()
    inserir_dados_iniciais(engine)


