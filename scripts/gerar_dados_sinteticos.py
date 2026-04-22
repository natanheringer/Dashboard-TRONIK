"""Gerador de dados sintéticos de telemetria — TRONIK Recicla.

Gera séries temporais realistas para cada coletor:
- Curva linear ascendente com ruído gaussiano
- Resets de coleta (nível volta a 0-10%)
- Padrões diferentes por tipo de parceiro:
  - Shopping: picos em dias úteis, sexta-feira forte
  - Condomínio: fluxo constante, leve pico no fim de semana
  - Escritório: só dias úteis
  - Universidade: semestre letivo vs férias

Uso:
    python scripts/gerar_dados_sinteticos.py [--dias 30] [--intervalo-min 15]
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from datetime import datetime, timedelta
from typing import List, Tuple

# Adicionar raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from banco_dados.modelos import Base, Coletor, LeituraSensor, Sensor
from banco_dados.utils import utc_now_naive

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# Perfis de enchimento por tipo de parceiro/local
PERFIS = {
    'shopping': {
        'taxa_base_hora': 0.8,     # %/hora base
        'ruido': 0.15,             # desvio padrão do ruído
        'pico_dia_util': 1.3,      # multiplicador dia útil
        'pico_fds': 0.7,           # multiplicador fim de semana
        'horario_pico': (10, 20),  # horário de maior fluxo
        'mult_pico': 1.5,
        'coleta_threshold': 85,    # nível que dispara coleta
    },
    'condominio': {
        'taxa_base_hora': 0.4,
        'ruido': 0.08,
        'pico_dia_util': 1.0,
        'pico_fds': 1.2,
        'horario_pico': (18, 22),
        'mult_pico': 1.3,
        'coleta_threshold': 90,
    },
    'escritorio': {
        'taxa_base_hora': 0.6,
        'ruido': 0.12,
        'pico_dia_util': 1.4,
        'pico_fds': 0.1,          # quase nada no fds
        'horario_pico': (9, 17),
        'mult_pico': 1.4,
        'coleta_threshold': 80,
    },
    'universidade': {
        'taxa_base_hora': 0.5,
        'ruido': 0.20,
        'pico_dia_util': 1.2,
        'pico_fds': 0.3,
        'horario_pico': (8, 18),
        'mult_pico': 1.2,
        'coleta_threshold': 85,
    },
    'geral': {
        'taxa_base_hora': 0.5,
        'ruido': 0.15,
        'pico_dia_util': 1.1,
        'pico_fds': 0.9,
        'horario_pico': (8, 20),
        'mult_pico': 1.2,
        'coleta_threshold': 85,
    },
}


def _classificar_coletor(localizacao: str) -> str:
    """Classifica coletor numa categoria por nome."""
    loc = localizacao.lower()
    if any(p in loc for p in ['shopping', 'mall', 'park', 'boulevard']):
        return 'shopping'
    if any(p in loc for p in ['condomínio', 'condominio', 'residencial', 'village']):
        return 'condominio'
    if any(p in loc for p in ['escritório', 'escritorio', 'office', 'sala', 'edifício']):
        return 'escritorio'
    if any(p in loc for p in ['universidade', 'faculdade', 'unb', 'ifb', 'campus']):
        return 'universidade'
    return 'geral'


def _gerar_serie_coletor(
    coletor_id: int,
    sensor_id: int,
    perfil: dict,
    inicio: datetime,
    fim: datetime,
    intervalo_min: int = 15,
) -> List[dict]:
    """Gera série temporal sintética para um coletor."""
    leituras = []
    nivel = random.uniform(0, 30)  # nível inicial aleatório
    bateria = random.uniform(80, 100)
    temperatura = random.uniform(22, 35)

    t = inicio
    while t <= fim:
        # Calcular taxa de enchimento para este momento
        hora = t.hour
        dia_semana = t.weekday()  # 0=segunda, 6=domingo
        eh_dia_util = dia_semana < 5

        taxa = perfil['taxa_base_hora']

        # Multiplicador dia útil vs fds
        if eh_dia_util:
            taxa *= perfil['pico_dia_util']
        else:
            taxa *= perfil['pico_fds']

        # Multiplicador horário de pico
        h_inicio, h_fim = perfil['horario_pico']
        if h_inicio <= hora <= h_fim:
            taxa *= perfil['mult_pico']
        else:
            taxa *= 0.3  # fora do pico

        # Converter para incremento por intervalo (intervalo em horas)
        incremento = taxa * (intervalo_min / 60)

        # Adicionar ruído
        incremento += random.gauss(0, perfil['ruido'])
        incremento = max(0, incremento)  # não pode ser negativo

        nivel += incremento

        # Simular coleta (reset)
        if nivel >= perfil['coleta_threshold']:
            if random.random() > 0.3:  # 70% chance de coletar
                nivel = random.uniform(2, 12)
                logger.debug(f"  Coleta simulada no coletor {coletor_id} em {t}")

        nivel = max(0, min(100, nivel))

        # Bateria decresce lentamente
        bateria = max(5, bateria - random.uniform(0.001, 0.01))

        # Temperatura varia com hora do dia
        if 10 <= hora <= 16:
            temperatura = random.gauss(32, 2)
        else:
            temperatura = random.gauss(24, 2)

        leituras.append({
            'sensor_id': sensor_id,
            'coletor_id': coletor_id,
            'nivel': round(nivel, 2),
            'bateria': round(bateria, 1),
            'temperatura': round(temperatura, 1),
            'timestamp': t,
        })

        t += timedelta(minutes=intervalo_min)

    return leituras


def gerar_dados_sinteticos(
    dias: int = 30,
    intervalo_min: int = 15,
    database_url: str | None = None,
) -> dict:
    """Gera e insere dados sintéticos de telemetria no banco.

    Args:
        dias: quantos dias de histórico gerar
        intervalo_min: intervalo entre leituras em minutos
        database_url: URL do banco (default: env DATABASE_URL ou sqlite)

    Returns:
        dict com estatísticas
    """
    from dotenv import load_dotenv
    load_dotenv()

    if not database_url:
        database_url = os.getenv('DATABASE_URL', 'sqlite:///tronik.db')

    # Ajustar URL para psycopg se PostgreSQL
    if database_url.startswith('postgresql://') and '+psycopg' not in database_url:
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://')
    if database_url.startswith('postgres://') and '+psycopg' not in database_url:
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://')

    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    stats = {
        'coletores': 0,
        'leituras_geradas': 0,
        'dias': dias,
        'intervalo_min': intervalo_min,
    }

    try:
        coletores = db.query(Coletor).all()
        if not coletores:
            logger.warning("⚠️  Nenhum coletor encontrado no banco. Nada a gerar.")
            return stats

        stats['coletores'] = len(coletores)
        agora = utc_now_naive()
        inicio = agora - timedelta(days=dias)

        logger.info(f"📊 Gerando {dias} dias de telemetria para {len(coletores)} coletores...")
        logger.info(f"   Período: {inicio.strftime('%d/%m/%Y')} → {agora.strftime('%d/%m/%Y')}")
        logger.info(f"   Intervalo: {intervalo_min} min (~{24 * 60 // intervalo_min} leituras/dia)")

        # Limpar leituras anteriores (opcional — evita duplicatas)
        deleted = db.query(LeituraSensor).filter(
            LeituraSensor.timestamp >= inicio
        ).delete(synchronize_session=False)
        if deleted:
            logger.info(f"   Removidas {deleted} leituras anteriores no período")

        for coletor in coletores:
            # Encontrar sensor associado (ou criar dummy)
            sensor = db.query(Sensor).filter(
                Sensor.coletor_id == coletor.id
            ).first()
            sensor_id = sensor.id if sensor else 1

            # Classificar perfil
            categoria = _classificar_coletor(coletor.localizacao or '')
            perfil = PERFIS.get(categoria, PERFIS['geral'])

            logger.info(f"  🔧 Coletor #{coletor.id} ({coletor.localizacao[:40]}) → perfil '{categoria}'")

            # Gerar série
            leituras = _gerar_serie_coletor(
                coletor.id, sensor_id, perfil,
                inicio, agora, intervalo_min,
            )

            # Inserir em batch
            batch = [LeituraSensor(**l) for l in leituras]
            db.bulk_save_objects(batch)
            stats['leituras_geradas'] += len(batch)

            logger.info(f"    → {len(batch)} leituras geradas")

        db.commit()

        leituras_por_coletor = stats['leituras_geradas'] // max(stats['coletores'], 1)
        logger.info(f"\n✅ Dados sintéticos gerados com sucesso!")
        logger.info(f"   Total: {stats['leituras_geradas']} leituras")
        logger.info(f"   Média: {leituras_por_coletor} leituras/coletor")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro ao gerar dados: {e}", exc_info=True)
        raise
    finally:
        db.close()

    return stats


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gerar dados sintéticos de telemetria')
    parser.add_argument('--dias', type=int, default=30, help='Dias de histórico (default: 30)')
    parser.add_argument('--intervalo-min', type=int, default=15, help='Intervalo em minutos (default: 15)')
    parser.add_argument('--db-url', type=str, default=None, help='Database URL (default: env DATABASE_URL)')
    args = parser.parse_args()

    stats = gerar_dados_sinteticos(
        dias=args.dias,
        intervalo_min=args.intervalo_min,
        database_url=args.db_url,
    )
    print(f"\n📊 Resumo: {stats}")
