"""
Script para atualizar tipos de coletores no banco de dados
==========================================================
Atualiza todos os tipos para "residuos eletronicos"
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from banco_dados.modelos import Coletor

def atualizar_tipos_lixeiras():
    """Atualiza todos os tipos de coletores para 'residuos eletronicos'"""
    # Caminho do banco (na raiz do projeto)
    projeto_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_db = os.path.join(projeto_root, 'tronik.db')
    
    if not os.path.exists(caminho_db):
        print(f"Banco de dados não encontrado em: {caminho_db}")
        print("O banco será criado na próxima execução do app.py")
        return
    
    # Usar caminho absoluto para SQLAlchemy
    caminho_absoluto = os.path.abspath(caminho_db)
    engine = create_engine(f'sqlite:///{caminho_absoluto}')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Buscar todas as coletores
        coletores = session.query(Coletor).all()
        
        print(f"Encontradas {len(coletores)} coletores")
        
        # Atualizar tipos
        atualizadas = 0
        for coletor in coletores:
            if coletor.tipo and coletor.tipo != "residuos eletronicos":
                coletor.tipo = "residuos eletronicos"
                atualizadas += 1
                print(f"Atualizada coletor ID {coletor.id}: {coletor.localizacao}")
            elif not coletor.tipo:
                coletor.tipo = "residuos eletronicos"
                atualizadas += 1
                print(f"Atualizada coletor ID {coletor.id}: {coletor.localizacao} (sem tipo)")
        
        session.commit()
        print(f"\nTotal de coletores atualizadas: {atualizadas}")
        print("Atualização concluída com sucesso!")
        
    except Exception as e:
        print(f"Erro ao atualizar: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    atualizar_tipos_lixeiras()

