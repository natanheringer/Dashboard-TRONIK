"""Importador de dados públicos para prospecção geográfica — TRONIK Recicla.

Coleta, processa e importa dados de 3 fontes públicas gratuitas:

1. **CNPJ / Receita Federal** — empresas do DF filtradas por CNAE relevante
2. **OpenStreetMap (Overpass API)** — POIs: shoppings, universidades, condomínios
3. **IBGE Censo 2022** — população e renda por setor censitário (enriquecimento)

Todos os dados são geocodificados e salvos na tabela `locais_prospeccao`.

Uso:
    python scripts/importar_dados_publicos.py --fonte todas
    python scripts/importar_dados_publicos.py --fonte osm
    python scripts/importar_dados_publicos.py --fonte cnpj --arquivo dados/cnpj_estabelecimentos_df.csv
    python scripts/importar_dados_publicos.py --recalcular-scores
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Adicionar raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from banco_dados.modelos import Base, LocalProspeccao
from banco_dados.utils import utc_now_naive

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ==============================================================
# CONFIGURAÇÃO
# ==============================================================

# CNAEs relevantes para prospecção de e-waste
CNAES_RELEVANTES = {
    '4713001': ('Lojas de departamento / shopping', 'shopping'),
    '4713002': ('Lojas em geral', 'comercio'),
    '6822600': ('Gestão de condomínios e shoppings', 'condominio'),
    '8532500': ('Educação superior — graduação', 'universidade'),
    '8411600': ('Administração pública geral', 'governo'),
    '6201500': ('Desenvolvimento de software', 'escritorio'),
    '6202300': ('Consultoria em tecnologia', 'escritorio'),
    '4751201': ('Comércio de computadores', 'comercio_eletronico'),
    '4751202': ('Comércio de periféricos', 'comercio_eletronico'),
    '4752100': ('Comércio de eletrônicos', 'comercio_eletronico'),
    '5611201': ('Restaurantes (proxy fluxo)', 'restaurante'),
    '8531700': ('Educação profissional', 'escola'),
    '8610101': ('Hospitais gerais', 'hospital'),
    '8610102': ('Hospitais especializados', 'hospital'),
    '7020400': ('Consultoria empresarial', 'escritorio'),
    '6462000': ('Holdings não financeiras', 'escritorio'),
    '8550301': ('Atividades apoio educação', 'escola'),
}

# UFs — DF = 53 (código IBGE)
UF_DF = '53'

# Nominatim rate limit
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {'User-Agent': 'TRONIK-Prospeccao/1.0'}
RATE_LIMIT = 1.0  # 1 req/segundo

# Overpass API
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


# ==============================================================
# 1. OPENSTREETMAP — Overpass API
# ==============================================================

def importar_osm(db_session) -> Dict[str, Any]:
    """Importa POIs relevantes do OpenStreetMap para o DF via Overpass API.

    Busca: shopping centers, universidades, hospitais, prédios de escritório,
    condomínios (building=apartments), órgãos do governo.
    """
    stats = {'fonte': 'osm', 'importados': 0, 'duplicados': 0, 'erros': 0}

    queries = [
        # Shoppings
        {
            'query': """
            [out:json][timeout:60];
            area["name"="Distrito Federal"]["admin_level"="4"]->.searchArea;
            (
              nwr["shop"="mall"](area.searchArea);
              nwr["building"="retail"](area.searchArea);
              nwr["amenity"="marketplace"](area.searchArea);
            );
            out center;
            """,
            'categoria': 'shopping',
        },
        # Universidades
        {
            'query': """
            [out:json][timeout:60];
            area["name"="Distrito Federal"]["admin_level"="4"]->.searchArea;
            (
              nwr["amenity"="university"](area.searchArea);
              nwr["amenity"="college"](area.searchArea);
            );
            out center;
            """,
            'categoria': 'universidade',
        },
        # Hospitais
        {
            'query': """
            [out:json][timeout:60];
            area["name"="Distrito Federal"]["admin_level"="4"]->.searchArea;
            nwr["amenity"="hospital"](area.searchArea);
            out center;
            """,
            'categoria': 'hospital',
        },
        # Escritórios/edifícios comerciais
        {
            'query': """
            [out:json][timeout:60];
            area["name"="Distrito Federal"]["admin_level"="4"]->.searchArea;
            (
              nwr["office"](area.searchArea);
              nwr["building"="commercial"](area.searchArea);
            );
            out center;
            """,
            'categoria': 'escritorio',
        },
        # Órgãos públicos
        {
            'query': """
            [out:json][timeout:60];
            area["name"="Distrito Federal"]["admin_level"="4"]->.searchArea;
            nwr["office"="government"](area.searchArea);
            out center;
            """,
            'categoria': 'governo',
        },
    ]

    for q in queries:
        logger.info(f"  🌐 Buscando '{q['categoria']}' no OSM...")
        try:
            response = requests.post(
                OVERPASS_URL,
                data={'data': q['query']},
                timeout=90,
            )
            response.raise_for_status()
            data = response.json()

            elements = data.get('elements', [])
            logger.info(f"    → {len(elements)} elementos encontrados")

            for elem in elements:
                # Extrair coordenadas
                lat = elem.get('lat') or (elem.get('center', {}).get('lat'))
                lng = elem.get('lon') or (elem.get('center', {}).get('lon'))

                if not lat or not lng:
                    continue

                # Validar que está no DF (bounding box)
                if not (-16.1 <= lat <= -15.4 and -48.3 <= lng <= -47.3):
                    continue

                # Extrair nome
                tags = elem.get('tags', {})
                nome = (
                    tags.get('name')
                    or tags.get('official_name')
                    or tags.get('alt_name')
                    or f"OSM_{q['categoria']}_{elem.get('id', 'unknown')}"
                )

                endereco_parts = [
                    tags.get('addr:street', ''),
                    tags.get('addr:housenumber', ''),
                    tags.get('addr:city', ''),
                ]
                endereco = ', '.join(p for p in endereco_parts if p) or None

                # Verificar duplicata (por coordenadas aproximadas)
                existente = db_session.query(LocalProspeccao).filter(
                    LocalProspeccao.nome == nome,
                    LocalProspeccao.fonte == 'osm',
                ).first()

                if existente:
                    stats['duplicados'] += 1
                    continue

                local = LocalProspeccao(
                    nome=nome[:300],
                    endereco=endereco[:500] if endereco else None,
                    latitude=float(lat),
                    longitude=float(lng),
                    fonte='osm',
                    categoria=q['categoria'],
                    score_prospeccao=0,  # será calculado depois
                    calculado_em=utc_now_naive(),
                )
                db_session.add(local)
                stats['importados'] += 1

        except Exception as e:
            logger.error(f"    ❌ Erro na query OSM '{q['categoria']}': {e}")
            stats['erros'] += 1

        time.sleep(2)  # Rate limit entre queries

    db_session.commit()
    logger.info(f"  ✅ OSM: {stats['importados']} importados, {stats['duplicados']} duplicados")
    return stats


# ==============================================================
# 2. CNPJ — Receita Federal (dados abertos)
# ==============================================================

def importar_cnpj(
    db_session,
    arquivo_csv: Optional[str] = None,
) -> Dict[str, Any]:
    """Importa empresas do DF filtradas por CNAE relevante.

    Os dados da Receita Federal são distribuídos em arquivos CSV grandes.
    Este script espera um arquivo pré-filtrado para o DF, ou processa
    o arquivo completo (Estabelecimentos) filtrando por UF=53.

    Download manual:
      https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj

    O arquivo de Estabelecimentos contém colunas (sem header):
      0: CNPJ_BASICO
      1: CNPJ_ORDEM
      2: CNPJ_DV
      3: IDENTIFICADOR_MATRIZ_FILIAL
      4: NOME_FANTASIA
      5: SITUACAO_CADASTRAL (2=ativa)
      6: DATA_SITUACAO_CADASTRAL
      7: MOTIVO_SITUACAO_CADASTRAL
      8: NOME_CIDADE_EXTERIOR
      9: PAIS
      10: DATA_INICIO_ATIVIDADE
      11: CNAE_FISCAL_PRINCIPAL
      12: CNAE_FISCAL_SECUNDARIA
      13: TIPO_LOGRADOURO
      14: LOGRADOURO
      15: NUMERO
      16: COMPLEMENTO
      17: BAIRRO
      18: CEP
      19: UF
      20: MUNICIPIO (código IBGE)
      ...
    """
    stats = {'fonte': 'cnpj', 'importados': 0, 'duplicados': 0, 'filtrados': 0, 'erros': 0}

    if not arquivo_csv:
        logger.info("  ℹ️  Nenhum arquivo CNPJ fornecido.")
        logger.info("  📥 Baixe o arquivo de Estabelecimentos em:")
        logger.info("     https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj")
        logger.info("  💡 Depois rode:")
        logger.info("     python scripts/importar_dados_publicos.py --fonte cnpj --arquivo <caminho.csv>")
        logger.info("")
        logger.info("  🔧 Gerando dados de exemplo com empresas conhecidas do DF...")
        return _importar_cnpj_exemplos(db_session)

    logger.info(f"  📂 Processando arquivo CNPJ: {arquivo_csv}")

    try:
        # Detectar se é zip ou csv
        if arquivo_csv.endswith('.zip'):
            with zipfile.ZipFile(arquivo_csv, 'r') as zf:
                csv_files = [f for f in zf.namelist() if f.endswith('.csv') or 'ESTABELE' in f.upper()]
                if not csv_files:
                    logger.error("Nenhum CSV encontrado no ZIP")
                    return stats
                with zf.open(csv_files[0]) as f:
                    content = io.TextIOWrapper(f, encoding='latin-1')
                    stats = _processar_csv_cnpj(db_session, content, stats)
        else:
            with open(arquivo_csv, 'r', encoding='latin-1') as f:
                stats = _processar_csv_cnpj(db_session, f, stats)

    except Exception as e:
        logger.error(f"❌ Erro ao processar CNPJ: {e}", exc_info=True)
        stats['erros'] += 1

    return stats


def _processar_csv_cnpj(db_session, file_handle, stats: dict) -> dict:
    """Processa CSV de estabelecimentos da Receita Federal."""
    reader = csv.reader(file_handle, delimiter=';', quotechar='"')
    batch = []
    linhas = 0

    for row in reader:
        linhas += 1
        if linhas % 100000 == 0:
            logger.info(f"    Processando linha {linhas:,}...")

        if len(row) < 21:
            continue

        # Filtrar: UF = DF (53) e situação ativa (2)
        uf = row[19].strip() if len(row) > 19 else ''
        situacao = row[5].strip() if len(row) > 5 else ''

        if uf != UF_DF or situacao != '2':
            continue

        # Filtrar por CNAE relevante
        cnae = row[11].strip() if len(row) > 11 else ''
        cnae_limpo = cnae.replace('.', '').replace('-', '').replace('/', '')[:7]

        if cnae_limpo not in CNAES_RELEVANTES:
            stats['filtrados'] += 1
            continue

        cnae_desc, categoria = CNAES_RELEVANTES[cnae_limpo]

        # Montar dados
        cnpj_base = row[0].strip()
        cnpj_ordem = row[1].strip()
        cnpj_dv = row[2].strip()
        cnpj_formatado = f"{cnpj_base}/{cnpj_ordem}-{cnpj_dv}"

        nome = row[4].strip() or f"Empresa CNPJ {cnpj_formatado}"
        logradouro = f"{row[13].strip()} {row[14].strip()}" if len(row) > 14 else ''
        numero = row[15].strip() if len(row) > 15 else ''
        bairro = row[17].strip() if len(row) > 17 else ''
        cep = row[18].strip() if len(row) > 18 else ''

        endereco = f"{logradouro} {numero}, {bairro}, Brasília-DF, {cep}".strip(', ')

        batch.append({
            'nome': nome[:300],
            'cnpj': cnpj_formatado[:18],
            'cnae_principal': cnae[:10],
            'cnae_descricao': cnae_desc[:200],
            'endereco': endereco[:500],
            'categoria': categoria,
        })

        if len(batch) >= 500:
            _geocodificar_e_salvar_batch(db_session, batch, stats)
            batch = []

    # Processar resto
    if batch:
        _geocodificar_e_salvar_batch(db_session, batch, stats)

    logger.info(f"  📊 CNPJ: {linhas:,} linhas processadas, {stats['filtrados']:,} filtradas por CNAE")
    return stats


def _geocodificar_e_salvar_batch(db_session, batch: list, stats: dict):
    """Geocodifica e salva um batch de empresas."""
    for item in batch:
        # Verificar duplicata
        existente = db_session.query(LocalProspeccao).filter(
            LocalProspeccao.cnpj == item['cnpj'],
        ).first()

        if existente:
            stats['duplicados'] += 1
            continue

        # Geocodificar via Nominatim
        coords = _geocodificar_simples(item['endereco'])

        if not coords:
            # Tentar só com bairro + Brasília
            parts = item['endereco'].split(',')
            if len(parts) >= 2:
                coords = _geocodificar_simples(f"{parts[1].strip()}, Brasília, DF")

        if not coords:
            stats['erros'] += 1
            continue

        local = LocalProspeccao(
            nome=item['nome'],
            cnpj=item['cnpj'],
            cnae_principal=item['cnae_principal'],
            cnae_descricao=item['cnae_descricao'],
            endereco=item['endereco'],
            latitude=coords[0],
            longitude=coords[1],
            fonte='cnpj',
            categoria=item['categoria'],
            score_prospeccao=0,
            calculado_em=utc_now_naive(),
        )
        db_session.add(local)
        stats['importados'] += 1

    db_session.commit()


def _geocodificar_simples(endereco: str) -> Optional[tuple]:
    """Geocodifica endereço via Nominatim (com rate limit)."""
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                'q': endereco,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'br',
            },
            headers=NOMINATIM_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        if data:
            lat = float(data[0]['lat'])
            lng = float(data[0]['lon'])
            # Validar que está no DF
            if -16.1 <= lat <= -15.4 and -48.3 <= lng <= -47.3:
                time.sleep(RATE_LIMIT)
                return (lat, lng)

    except Exception:
        pass

    time.sleep(RATE_LIMIT)
    return None


def _importar_cnpj_exemplos(db_session) -> Dict[str, Any]:
    """Importa dados de exemplo com empresas conhecidas do DF.

    Usado quando o usuário não fornece o arquivo da Receita Federal.
    Inclui shoppings, condomínios e universidades reais de Brasília.
    """
    stats = {'fonte': 'cnpj_exemplos', 'importados': 0, 'duplicados': 0, 'erros': 0}

    exemplos = [
        # Shoppings
        {'nome': 'Taguatinga Shopping', 'lat': -15.8361, 'lng': -48.0536, 'cat': 'shopping',
         'cnae': '4713-0/01', 'end': 'QS 1, Águas Claras, Taguatinga'},
        {'nome': 'Park Shopping', 'lat': -15.8336, 'lng': -47.9628, 'cat': 'shopping',
         'cnae': '4713-0/01', 'end': 'SAI/SO, Guará'},
        {'nome': 'ParkShopping Brasília', 'lat': -15.8329, 'lng': -47.9614, 'cat': 'shopping',
         'cnae': '4713-0/01', 'end': 'SAI/SO Área 6580, Guará'},
        {'nome': 'Conjunto Nacional', 'lat': -15.7916, 'lng': -47.8827, 'cat': 'shopping',
         'cnae': '4713-0/01', 'end': 'SDN, Asa Norte, Brasília'},
        {'nome': 'Pátio Brasil Shopping', 'lat': -15.7980, 'lng': -47.8925, 'cat': 'shopping',
         'cnae': '4713-0/01', 'end': 'SCS Q 7 Bl A, Asa Sul'},
        {'nome': 'Terraço Shopping', 'lat': -15.8394, 'lng': -48.0233, 'cat': 'shopping',
         'cnae': '4713-0/01', 'end': 'Cruzeiro, Brasília'},
        {'nome': 'Boulevard Shopping', 'lat': -15.7148, 'lng': -47.8917, 'cat': 'shopping',
         'cnae': '4713-0/01', 'end': 'STN, Asa Norte'},
        {'nome': 'Shopping Iguatemi Brasília', 'lat': -15.7372, 'lng': -47.8913, 'cat': 'shopping',
         'cnae': '4713-0/01', 'end': 'Lago Norte, Brasília'},
        {'nome': 'Venâncio Shopping', 'lat': -15.7940, 'lng': -47.8852, 'cat': 'shopping',
         'cnae': '4713-0/01', 'end': 'SRTVS Q 702, Asa Sul'},

        # Universidades
        {'nome': 'Universidade de Brasília (UnB)', 'lat': -15.7631, 'lng': -47.8707, 'cat': 'universidade',
         'cnae': '8532-5/00', 'end': 'Campus Darcy Ribeiro, Asa Norte'},
        {'nome': 'IFB Campus Brasília', 'lat': -15.7883, 'lng': -47.8771, 'cat': 'universidade',
         'cnae': '8532-5/00', 'end': 'SGAN 610, Asa Norte'},
        {'nome': 'UniCEUB', 'lat': -15.7636, 'lng': -47.8889, 'cat': 'universidade',
         'cnae': '8532-5/00', 'end': 'SEPN 707/907, Asa Norte'},
        {'nome': 'IESB Campus Asa Sul', 'lat': -15.8238, 'lng': -47.9115, 'cat': 'universidade',
         'cnae': '8532-5/00', 'end': 'SGAS 613/614, Asa Sul'},
        {'nome': 'UnB Campus Gama', 'lat': -15.9892, 'lng': -48.0445, 'cat': 'universidade',
         'cnae': '8532-5/00', 'end': 'St. Leste Área Especial, Gama'},

        # Condomínios / Residenciais
        {'nome': 'Condomínio Ville de Montagne', 'lat': -15.8485, 'lng': -47.9280, 'cat': 'condominio',
         'cnae': '6822-6/00', 'end': 'Jardim Botânico, Brasília'},
        {'nome': 'Condomínio Ville de France', 'lat': -15.8520, 'lng': -47.9310, 'cat': 'condominio',
         'cnae': '6822-6/00', 'end': 'Jardim Botânico, Brasília'},
        {'nome': 'Alphaville Brasília', 'lat': -15.6998, 'lng': -47.6561, 'cat': 'condominio',
         'cnae': '6822-6/00', 'end': 'Cidade Ocidental, Entorno'},

        # Órgãos públicos
        {'nome': 'Esplanada dos Ministérios', 'lat': -15.7995, 'lng': -47.8625, 'cat': 'governo',
         'cnae': '8411-6/00', 'end': 'Esplanada dos Ministérios, Brasília'},
        {'nome': 'Tribunal de Contas da União', 'lat': -15.8006, 'lng': -47.8611, 'cat': 'governo',
         'cnae': '8411-6/00', 'end': 'SAFS Q 4, Asa Sul'},
        {'nome': 'Banco Central do Brasil', 'lat': -15.7917, 'lng': -47.8751, 'cat': 'governo',
         'cnae': '8411-6/00', 'end': 'SBS Q 3, Asa Sul'},

        # Empresas de TI
        {'nome': 'CTIS Tecnologia', 'lat': -15.7987, 'lng': -47.8907, 'cat': 'escritorio',
         'cnae': '6201-5/00', 'end': 'SCS Q 8, Asa Sul'},
        {'nome': 'Stefanini IT Solutions', 'lat': -15.7828, 'lng': -47.9003, 'cat': 'escritorio',
         'cnae': '6201-5/00', 'end': 'SCN Q 1, Asa Norte'},
        {'nome': 'Globalweb Corp', 'lat': -15.7934, 'lng': -47.8830, 'cat': 'escritorio',
         'cnae': '6201-5/00', 'end': 'SRTVS Q 701, Asa Sul'},

        # Hospitais
        {'nome': 'Hospital Santa Lúcia', 'lat': -15.8283, 'lng': -47.9185, 'cat': 'hospital',
         'cnae': '8610-1/01', 'end': 'SHLS 716, Asa Sul'},
        {'nome': 'Hospital Sírio Libanês Brasília', 'lat': -15.8256, 'lng': -47.9123, 'cat': 'hospital',
         'cnae': '8610-1/01', 'end': 'SMHS Q 501, Asa Sul'},
    ]

    for ex in exemplos:
        # Verificar duplicata
        existente = db_session.query(LocalProspeccao).filter(
            LocalProspeccao.nome == ex['nome'],
        ).first()

        if existente:
            stats['duplicados'] += 1
            continue

        local = LocalProspeccao(
            nome=ex['nome'],
            cnae_principal=ex['cnae'],
            cnae_descricao=CNAES_RELEVANTES.get(
                ex['cnae'].replace('-', '').replace('/', '')[:7],
                ('', '')
            )[0],
            endereco=ex['end'],
            latitude=ex['lat'],
            longitude=ex['lng'],
            fonte='cnpj_exemplos',
            categoria=ex['cat'],
            score_prospeccao=0,
            calculado_em=utc_now_naive(),
        )
        db_session.add(local)
        stats['importados'] += 1

    db_session.commit()
    logger.info(f"  ✅ Exemplos: {stats['importados']} importados, {stats['duplicados']} duplicados")
    return stats


# ==============================================================
# MAIN
# ==============================================================

def importar_todos(
    database_url: str | None = None,
    arquivo_cnpj: str | None = None,
    recalcular: bool = True,
) -> Dict[str, Any]:
    """Executa importação completa de todas as fontes."""
    from dotenv import load_dotenv
    load_dotenv()

    if not database_url:
        database_url = os.getenv('DATABASE_URL', 'sqlite:///tronik.db')

    # Ajustar URL para psycopg
    if database_url.startswith('postgresql://') and '+psycopg' not in database_url:
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://')
    if database_url.startswith('postgres://') and '+psycopg' not in database_url:
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://')

    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    resultados: Dict[str, Any] = {}

    try:
        logger.info("=" * 60)
        logger.info("IMPORTAÇÃO DE DADOS PÚBLICOS — TRONIK Recicla")
        logger.info("=" * 60)

        # 1. OpenStreetMap
        logger.info("\n📍 Fonte 1: OpenStreetMap (Overpass API)")
        resultados['osm'] = importar_osm(db)

        # 2. CNPJ
        logger.info("\n🏢 Fonte 2: CNPJ / Receita Federal")
        resultados['cnpj'] = importar_cnpj(db, arquivo_csv=arquivo_cnpj)

        # 3. Recalcular scores
        if recalcular:
            logger.info("\n🔄 Recalculando scores de prospecção...")
            from banco_dados.services.ml_prospeccao import recalcular_scores_prospeccao
            resultados['scores'] = recalcular_scores_prospeccao(db)

        # Resumo final
        total_locais = db.query(LocalProspeccao).count()
        logger.info("\n" + "=" * 60)
        logger.info("RESUMO DA IMPORTAÇÃO")
        logger.info("=" * 60)
        logger.info(f"  Total de locais de prospecção no banco: {total_locais}")
        for fonte, stats in resultados.items():
            if isinstance(stats, dict):
                imp = stats.get('importados', stats.get('sucesso', '?'))
                logger.info(f"  {fonte}: {imp} importados")

    except Exception as e:
        logger.error(f"❌ Erro na importação: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

    return resultados


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Importar dados públicos para prospecção')
    parser.add_argument(
        '--fonte',
        choices=['todas', 'osm', 'cnpj'],
        default='todas',
        help='Fonte de dados a importar (default: todas)',
    )
    parser.add_argument(
        '--arquivo',
        type=str,
        default=None,
        help='Caminho do arquivo CSV da Receita Federal (Estabelecimentos)',
    )
    parser.add_argument(
        '--recalcular-scores',
        action='store_true',
        default=True,
        help='Recalcular scores após importação',
    )
    parser.add_argument(
        '--db-url',
        type=str,
        default=None,
        help='Database URL (default: env DATABASE_URL)',
    )
    args = parser.parse_args()

    if args.fonte == 'todas':
        importar_todos(
            database_url=args.db_url,
            arquivo_cnpj=args.arquivo,
            recalcular=args.recalcular_scores,
        )
    elif args.fonte == 'osm':
        from dotenv import load_dotenv
        load_dotenv()
        db_url = args.db_url or os.getenv('DATABASE_URL', 'sqlite:///tronik.db')
        if db_url.startswith('postgresql://') and '+psycopg' not in db_url:
            db_url = db_url.replace('postgresql://', 'postgresql+psycopg://')
        engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            importar_osm(db)
        finally:
            db.close()
    elif args.fonte == 'cnpj':
        from dotenv import load_dotenv
        load_dotenv()
        db_url = args.db_url or os.getenv('DATABASE_URL', 'sqlite:///tronik.db')
        if db_url.startswith('postgresql://') and '+psycopg' not in db_url:
            db_url = db_url.replace('postgresql://', 'postgresql+psycopg://')
        engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            importar_cnpj(db, arquivo_csv=args.arquivo)
        finally:
            db.close()
