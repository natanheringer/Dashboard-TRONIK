"""
Script de Importação CSV - Dashboard-TRONIK
===========================================

Importa dados reais de coletas do arquivo CSV para o banco de dados.
"""

import csv
import os
import sys
from datetime import datetime
from banco_dados.utils import utc_now_naive
from sqlalchemy.orm import sessionmaker

# Adicionar diretório raiz ao path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from banco_dados.modelos import Lixeira, Coleta, Parceiro, TipoColetor
from banco_dados.seed_tipos import obter_parceiro_por_nome, obter_tipo_coletor_por_nome
import logging

logger = logging.getLogger(__name__)


def converter_data(data_str):
    """
    Converte data do formato DD/MM/YYYY para datetime.
    
    Args:
        data_str: String no formato DD/MM/YYYY
    
    Returns:
        datetime object ou None se inválido
    """
    if not data_str or not data_str.strip():
        return None
    
    try:
        # Remover espaços e tentar converter
        data_str = data_str.strip()
        return datetime.strptime(data_str, "%d/%m/%Y")
    except ValueError as e:
        logger.warning(f"Data inválida: '{data_str}' - {e}")
        return None


def validar_float(valor, nome_campo, min_valor=0):
    """
    Valida e converte string para float.
    
    Args:
        valor: Valor a converter
        nome_campo: Nome do campo (para mensagens de erro)
        min_valor: Valor mínimo permitido
    
    Returns:
        float ou None se inválido
    """
    if not valor or not str(valor).strip():
        return None
    
    try:
        valor_float = float(str(valor).strip().replace(',', '.'))
        if valor_float < min_valor:
            logger.warning(f"{nome_campo} negativo ou zero: {valor_float}")
            return None
        return valor_float
    except (ValueError, AttributeError):
        logger.warning(f"{nome_campo} inválido: '{valor}'")
        return None


def validar_boolean(valor):
    """
    Converte string para boolean.
    SIM -> True, NÃO -> False
    
    Args:
        valor: String "SIM" ou "NÃO"
    
    Returns:
        bool
    """
    if not valor:
        return False
    
    valor_str = str(valor).strip().upper()
    return valor_str == "SIM"


def criar_ou_buscar_lixeira(session, nome_empresa, parceiro_id=None, tipo_material_id=None):
    """
    Cria ou busca uma lixeira pelo nome da empresa.
    
    Args:
        session: SQLAlchemy session
        nome_empresa: Nome da empresa/localização
        parceiro_id: ID do parceiro (opcional)
        tipo_material_id: ID do tipo de material (opcional)
    
    Returns:
        Lixeira object
    """
    if not nome_empresa or not nome_empresa.strip():
        raise ValueError("Nome da empresa não pode ser vazio")
    
    nome_empresa = nome_empresa.strip()
    
    # Buscar lixeira existente pela localização
    lixeira = session.query(Lixeira).filter(Lixeira.localizacao == nome_empresa).first()
    
    if not lixeira:
        # Criar nova lixeira
        lixeira = Lixeira(
            localizacao=nome_empresa,
            nivel_preenchimento=0.0,
            status="OK",
            ultima_coleta=utc_now_naive(),
            parceiro_id=parceiro_id,
            tipo_material_id=tipo_material_id
        )
        session.add(lixeira)
        session.commit()
        session.refresh(lixeira)
        logger.debug(f"Nova lixeira criada: {nome_empresa}")
    else:
        # Atualizar parceiro se fornecido
        if parceiro_id and not lixeira.parceiro_id:
            lixeira.parceiro_id = parceiro_id
            session.commit()
    
    return lixeira


def validar_linha_csv(linha, num_linha):
    """
    Valida uma linha do CSV.
    
    Args:
        linha: Dict com dados da linha
        num_linha: Número da linha (para logs)
    
    Returns:
        tuple: (valido, erros)
    """
    erros = []
    
    # Validar empresa
    empresa = linha.get('EMPRESAS', '').strip() if 'EMPRESAS' in linha else ''
    if not empresa:
        erros.append("Empresa vazia")
    
    # Validar data
    data_str = linha.get('DATA DA COLETA', '').strip() if 'DATA DA COLETA' in linha else ''
    if not data_str:
        erros.append("Data da coleta vazia")
    else:
        data = converter_data(data_str)
        if not data:
            erros.append(f"Data inválida: {data_str}")
    
    # Validar quantidade
    quantidade_str = linha.get('QUANTIDADE(KG)', '').strip() if 'QUANTIDADE(KG)' in linha else ''
    quantidade = validar_float(quantidade_str, "QUANTIDADE(KG)", min_valor=0)
    if quantidade is None or quantidade <= 0:
        erros.append(f"Quantidade inválida: {quantidade_str}")
    
    return len(erros) == 0, erros


def importar_csv(caminho_csv, engine, atualizar_existentes=False):
    """
    Importa coletas do arquivo CSV para o banco de dados.
    
    Args:
        caminho_csv: Caminho para o arquivo CSV
        engine: SQLAlchemy engine
        atualizar_existentes: Se True, atualiza coletas existentes (mesma empresa + data + quantidade)
    
    Returns:
        dict: Estatísticas da importação
    """
    if not os.path.exists(caminho_csv):
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {caminho_csv}")
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    stats = {
        'total_linhas': 0,
        'linhas_validas': 0,
        'linhas_invalidas': 0,
        'coletas_criadas': 0,
        'coletas_atualizadas': 0,
        'coletas_duplicadas': 0,
        'erros': []
    }
    
    try:
        logger.info(f"Iniciando importação do CSV: {caminho_csv}")
        
        # Ler CSV com encoding UTF-8-sig (remove BOM)
        with open(caminho_csv, 'r', encoding='utf-8-sig', newline='') as f:
            # Ler primeira linha para detectar delimitador
            primeira_linha = f.readline()
            f.seek(0)
            
            # Detectar delimitador
            delimiter = ',' if ',' in primeira_linha else ';'
            
            reader = csv.DictReader(f, delimiter=delimiter)
            
            # Limpar nomes das colunas (remover espaços e BOM)
            fieldnames = [field.strip().lstrip('\ufeff') for field in reader.fieldnames] if reader.fieldnames else []
            reader.fieldnames = fieldnames
            
            for num_linha, linha in enumerate(reader, start=2):  # Começa em 2 (linha 1 é header)
                stats['total_linhas'] += 1
                
                # Pular linhas vazias
                if not any(linha.values()):
                    continue
                
                # Validar linha
                valido, erros = validar_linha_csv(linha, num_linha)
                
                if not valido:
                    stats['linhas_invalidas'] += 1
                    stats['erros'].append({
                        'linha': num_linha,
                        'erros': erros,
                        'dados': linha
                    })
                    logger.warning(f"Linha {num_linha} inválida: {erros}")
                    continue
                
                stats['linhas_validas'] += 1
                
                try:
                    # Extrair dados
                    empresa = linha.get('EMPRESAS', '').strip()
                    km_str = linha.get('KM', '').strip()
                    preco_combustivel_str = linha.get('Preço Conbustível(Por Litro)', '').strip()
                    data_str = linha.get('DATA DA COLETA', '').strip()
                    quantidade_str = linha.get('QUANTIDADE(KG)', '').strip()
                    lucro_kg_str = linha.get('Lucro por Kg(Em reais)', '').strip()
                    emissao_mtr_str = linha.get('EMISSÃO DE MTR', '').strip()
                    tipo_coleta = linha.get('Tipo de coleta', '').strip()
                    tipo_coletor_nome = linha.get('TIPO DE COLETOR', '').strip()
                    parceiro_nome = linha.get('PARCEIRO', '').strip()
                    
                    # Converter dados
                    data_hora = converter_data(data_str)
                    quantidade = validar_float(quantidade_str, "QUANTIDADE(KG)", min_valor=0)
                    km = validar_float(km_str, "KM", min_valor=0)
                    preco_combustivel = validar_float(preco_combustivel_str, "Preço Combustível", min_valor=0)
                    lucro_kg = validar_float(lucro_kg_str, "Lucro por Kg", min_valor=0)
                    emissao_mtr = validar_boolean(emissao_mtr_str)
                    
                    # Normalizar tipo de coleta
                    if tipo_coleta:
                        tipo_coleta = tipo_coleta.strip()
                        if "Avulsa" in tipo_coleta:
                            tipo_operacao = "Avulsa"
                        elif "Campanha" in tipo_coleta:
                            tipo_operacao = "Campanha"
                        else:
                            tipo_operacao = tipo_coleta
                    else:
                        tipo_operacao = None
                    
                    # Buscar/criar parceiro
                    parceiro = obter_parceiro_por_nome(session, parceiro_nome) if parceiro_nome else None
                    parceiro_id = parceiro.id if parceiro else None
                    
                    # Buscar/criar tipo de coletor
                    tipo_coletor = None
                    tipo_coletor_id = None
                    if tipo_coletor_nome:
                        tipo_coletor = obter_tipo_coletor_por_nome(session, tipo_coletor_nome)
                        tipo_coletor_id = tipo_coletor.id if tipo_coletor else None
                    
                    # Criar/buscar lixeira
                    lixeira = criar_ou_buscar_lixeira(session, empresa, parceiro_id=parceiro_id)
                    
                    # Verificar se coleta já existe (mesma lixeira + data + quantidade)
                    coleta_existente = session.query(Coleta).filter(
                        Coleta.lixeira_id == lixeira.id,
                        Coleta.data_hora == data_hora,
                        Coleta.volume_estimado == quantidade
                    ).first()
                    
                    if coleta_existente:
                        if atualizar_existentes:
                            # Atualizar coleta existente
                            coleta_existente.tipo_operacao = tipo_operacao
                            coleta_existente.km_percorrido = km
                            coleta_existente.preco_combustivel = preco_combustivel
                            coleta_existente.lucro_por_kg = lucro_kg
                            coleta_existente.emissao_mtr = emissao_mtr
                            coleta_existente.tipo_coletor_id = tipo_coletor_id
                            coleta_existente.parceiro_id = parceiro_id
                            session.commit()
                            stats['coletas_atualizadas'] += 1
                            logger.debug(f"Coleta atualizada: {empresa} - {data_str}")
                        else:
                            stats['coletas_duplicadas'] += 1
                            logger.debug(f"Coleta duplicada ignorada: {empresa} - {data_str}")
                    else:
                        # Criar nova coleta
                        nova_coleta = Coleta(
                            lixeira_id=lixeira.id,
                            data_hora=data_hora,
                            volume_estimado=quantidade,
                            tipo_operacao=tipo_operacao,
                            km_percorrido=km,
                            preco_combustivel=preco_combustivel,
                            lucro_por_kg=lucro_kg,
                            emissao_mtr=emissao_mtr,
                            tipo_coletor_id=tipo_coletor_id,
                            parceiro_id=parceiro_id
                        )
                        session.add(nova_coleta)
                        session.commit()
                        stats['coletas_criadas'] += 1
                        logger.debug(f"Coleta criada: {empresa} - {data_str} - {quantidade}KG")
                
                except Exception as e:
                    stats['linhas_invalidas'] += 1
                    stats['erros'].append({
                        'linha': num_linha,
                        'erro': str(e),
                        'dados': linha
                    })
                    logger.error(f"Erro ao processar linha {num_linha}: {e}")
                    session.rollback()
                    continue
        
        logger.info("✅ Importação concluída!")
        logger.info(f"   Total de linhas: {stats['total_linhas']}")
        logger.info(f"   Linhas válidas: {stats['linhas_validas']}")
        logger.info(f"   Linhas inválidas: {stats['linhas_invalidas']}")
        logger.info(f"   Coletas criadas: {stats['coletas_criadas']}")
        logger.info(f"   Coletas atualizadas: {stats['coletas_atualizadas']}")
        logger.info(f"   Coletas duplicadas: {stats['coletas_duplicadas']}")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Erro fatal na importação: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    from sqlalchemy import create_engine
    from banco_dados.modelos import Base
    from banco_dados.seed_tipos import popular_tipos
    
    # Mudar para diretório raiz do projeto
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    
    # Criar engine
    engine = create_engine('sqlite:///tronik.db', echo=False)
    
    # Criar tabelas
    Base.metadata.create_all(engine)
    
    # Popular tipos
    popular_tipos(engine)
    
    # Importar CSV
    caminho_csv = "BaseTronik v2 (1)(FatoColetas) (1).csv"
    if os.path.exists(caminho_csv):
        stats = importar_csv(caminho_csv, engine, atualizar_existentes=False)
        print("\n" + "="*60)
        print("RESUMO DA IMPORTAÇÃO")
        print("="*60)
        print(f"Total de linhas processadas: {stats['total_linhas']}")
        print(f"Linhas válidas: {stats['linhas_validas']}")
        print(f"Linhas inválidas: {stats['linhas_invalidas']}")
        print(f"Coletas criadas: {stats['coletas_criadas']}")
        print(f"Coletas atualizadas: {stats['coletas_atualizadas']}")
        print(f"Coletas duplicadas: {stats['coletas_duplicadas']}")
        if stats['erros']:
            print(f"\nErros encontrados: {len(stats['erros'])}")
            for erro in stats['erros'][:10]:  # Mostrar apenas os 10 primeiros
                print(f"  Linha {erro['linha']}: {erro.get('erro', erro.get('erros', []))}")
    else:
        print(f"❌ Arquivo CSV não encontrado: {caminho_csv}")

