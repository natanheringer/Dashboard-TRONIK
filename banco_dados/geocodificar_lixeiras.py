#!/usr/bin/env python3
"""
Script de Geocodificação em Lote - Dashboard-TRONIK
===================================================
Script para geocodificar todas as coletores que não possuem coordenadas.

Uso:
    python banco_dados/geocodificar_coletores.py
    python banco_dados/geocodificar_coletores.py --limite 10
    python banco_dados/geocodificar_coletores.py --forcar
"""

import argparse
import logging
import os
import sys

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from banco_dados.geocodificacao import geocodificar_lixeiras_em_lote
from banco_dados.modelos import Coletor

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Geocodifica coletores sem coordenadas usando Nominatim'
    )
    parser.add_argument(
        '--limite',
        type=int,
        default=None,
        help='Número máximo de coletores a processar (padrão: todas)'
    )
    parser.add_argument(
        '--forcar',
        action='store_true',
        help='Forçar atualização mesmo se já tiver coordenadas'
    )
    parser.add_argument(
        '--cidade',
        type=str,
        default='Brasília',
        help='Cidade para geocodificação (padrão: Brasília)'
    )
    parser.add_argument(
        '--estado',
        type=str,
        default='DF',
        help='Estado para geocodificação (padrão: DF)'
    )
    parser.add_argument(
        '--database',
        type=str,
        default='sqlite:///tronik.db',
        help='URL do banco de dados (padrão: sqlite:///tronik.db)'
    )

    args = parser.parse_args()

    # Criar engine e sessão
    engine = create_engine(args.database, echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Contar coletores sem coordenadas
        total_sem_coords = session.query(Coletor).filter(
            (Coletor.latitude.is_(None)) | (Coletor.longitude.is_(None))
        ).count()

        total_com_coords = session.query(Coletor).filter(
            Coletor.latitude.isnot(None),
            Coletor.longitude.isnot(None)
        ).count()

        total_geral = session.query(Coletor).count()

        print("=" * 60)
        print("GEOCODIFICAÇÃO DE LIXEIRAS")
        print("=" * 60)
        print(f"Total de coletores: {total_geral}")
        print(f"Com coordenadas: {total_com_coords}")
        print(f"Sem coordenadas: {total_sem_coords}")
        print("=" * 60)

        if total_sem_coords == 0 and not args.forcar:
            print("✅ Todas as coletores já possuem coordenadas!")
            return

        if args.limite:
            print(f"⚠️  Processando apenas {args.limite} coletores (limite definido)")

        # Confirmar execução
        if not args.forcar:
            resposta = input(f"\nDeseja geocodificar {total_sem_coords if not args.limite else args.limite} coletor(s)? (s/N): ")
            if resposta.lower() != 's':
                print("Operação cancelada.")
                return

        print("\nIniciando geocodificação...")
        print("⚠️  Respeitando rate limit de 1 requisição/segundo\n")

        # Executar geocodificação
        stats = geocodificar_lixeiras_em_lote(
            session,
            cidade=args.cidade,
            estado=args.estado,
            apenas_sem_coordenadas=not args.forcar,
            limite=args.limite
        )

        # Exibir resultados
        print("\n" + "=" * 60)
        print("RESULTADO DA GEOCODIFICAÇÃO")
        print("=" * 60)
        print(f"Total processadas: {stats['processadas']}")
        print(f"✅ Sucesso: {stats['sucesso']}")
        print(f"❌ Falha: {stats['falha']}")
        print(f"⏭️  Puladas: {stats['puladas']}")

        if stats['erros']:
            print(f"\n⚠️  Erros encontrados: {len(stats['erros'])}")
            print("\nPrimeiros 5 erros:")
            for erro in stats['erros'][:5]:
                if 'coletor_id' in erro:
                    print(f"  - Coletor {erro['coletor_id']} ({erro['localizacao']}): {erro['erro']}")
                else:
                    print(f"  - {erro.get('erro_geral', erro)}")

        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\n⚠️  Operação interrompida pelo usuário.")
        session.rollback()
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()



