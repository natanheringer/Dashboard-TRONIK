#!/usr/bin/env python3
"""
Script para alterar senhas de usuários existentes
=================================================

Uso:
    python scripts/alterar_senha_usuarios.py --usuario admin --nova-senha MinhaNovaSenha123
    python scripts/alterar_senha_usuarios.py --usuario admin1 --nova-senha MinhaNovaSenha123
    python scripts/alterar_senha_usuarios.py --listar  # Lista todos os usuários
"""

import os
import sys
import argparse
from getpass import getpass

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from banco_dados.modelos import Usuario, Base
from banco_dados.seguranca import validar_senha
from banco_dados.utils.logger import obter_logger

logger = obter_logger(__name__)


def obter_engine():
    """Obtém engine do banco de dados"""
    database_url = os.getenv('DATABASE_URL', 'sqlite:///tronik.db')
    
    # Converter URL do PostgreSQL se necessário
    if database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    
    # Converter caminho simples para SQLite URL
    if not database_url.startswith(('sqlite:///', 'postgresql')):
        database_url = f'sqlite:///{database_url}'
    
    return create_engine(database_url, echo=False)


def listar_usuarios(session):
    """Lista todos os usuários"""
    usuarios = session.query(Usuario).all()
    
    if not usuarios:
        print("❌ Nenhum usuário encontrado no banco de dados.")
        return
    
    print("\n📋 Usuários cadastrados:")
    print("=" * 80)
    print(f"{'ID':<5} {'Username':<20} {'Email':<30} {'Admin':<8} {'Ativo':<8}")
    print("-" * 80)
    
    for usuario in usuarios:
        admin_str = "✅ Sim" if usuario.admin else "❌ Não"
        ativo_str = "✅ Sim" if usuario.ativo else "❌ Não"
        print(f"{usuario.id:<5} {usuario.username:<20} {usuario.email:<30} {admin_str:<8} {ativo_str:<8}")
    
    print("=" * 80)
    print(f"\nTotal: {len(usuarios)} usuário(s)\n")


def alterar_senha(session, username, nova_senha):
    """Altera a senha de um usuário"""
    usuario = session.query(Usuario).filter(Usuario.username == username).first()
    
    if not usuario:
        print(f"❌ Usuário '{username}' não encontrado.")
        return False
    
    # Validar senha
    valido, erro = validar_senha(nova_senha)
    if not valido:
        print(f"❌ Senha inválida: {erro}")
        return False
    
    # Alterar senha
    usuario.set_senha(nova_senha)
    session.commit()
    
    print(f"✅ Senha alterada com sucesso para o usuário '{username}'")
    print(f"   Email: {usuario.email}")
    print(f"   Admin: {'Sim' if usuario.admin else 'Não'}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Script para alterar senhas de usuários',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Listar todos os usuários
  python scripts/alterar_senha_usuarios.py --listar
  
  # Alterar senha de um usuário específico
  python scripts/alterar_senha_usuarios.py --usuario admin --nova-senha MinhaNovaSenha123
  
  # Alterar senha com prompt interativo (mais seguro)
  python scripts/alterar_senha_usuarios.py --usuario admin
        """
    )
    
    parser.add_argument(
        '--usuario', '-u',
        type=str,
        help='Username do usuário para alterar a senha'
    )
    
    parser.add_argument(
        '--nova-senha', '-s',
        type=str,
        help='Nova senha (se não fornecido, será solicitado de forma segura)'
    )
    
    parser.add_argument(
        '--listar', '-l',
        action='store_true',
        help='Lista todos os usuários cadastrados'
    )
    
    args = parser.parse_args()
    
    # Conectar ao banco
    engine = obter_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Listar usuários
        if args.listar:
            listar_usuarios(session)
            return
        
        # Alterar senha
        if not args.usuario:
            print("❌ Erro: --usuario é obrigatório para alterar senha")
            print("   Use --listar para ver os usuários disponíveis")
            return
        
        # Obter senha
        if args.nova_senha:
            nova_senha = args.nova_senha
        else:
            nova_senha = getpass("Digite a nova senha: ")
            confirmar_senha = getpass("Confirme a nova senha: ")
            
            if nova_senha != confirmar_senha:
                print("❌ Erro: As senhas não coincidem.")
                return
        
        # Alterar senha
        alterar_senha(session, args.usuario, nova_senha)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operação cancelada pelo usuário.")
    except Exception as e:
        logger.error(f"Erro ao alterar senha: {e}")
        print(f"❌ Erro: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == '__main__':
    main()

