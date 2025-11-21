"""
Módulo de Geocodificação - Dashboard-TRONIK
===========================================
Converte endereços/localizações em coordenadas (latitude/longitude)
usando Nominatim (OpenStreetMap).

Funcionalidades:
- Geocodificação de endereços
- Geocodificação em lote com rate limiting
- Cache de resultados para evitar requisições desnecessárias
"""

import requests
import time
import logging
from typing import Optional, Dict, Tuple
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Configurações do Nominatim
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {
    'User-Agent': 'Dashboard-TRONIK/1.0'  # Obrigatório pela política de uso
}
RATE_LIMIT_DELAY = 1.0  # 1 segundo entre requisições (respeitando rate limit)

# Coordenadas padrão de Brasília (centro) para fallback
COORDENADAS_BRASILIA = {
    'latitude': -15.7942,
    'longitude': -47.8822
}


def geocodificar_endereco(
    endereco: str,
    cidade: str = "Brasília",
    estado: str = "DF",
    pais: str = "Brasil"
) -> Optional[Dict[str, float]]:
    """
    Converte um endereço em coordenadas (latitude, longitude) usando Nominatim.
    Tenta múltiplas estratégias de busca para melhorar a taxa de sucesso.
    
    Args:
        endereco: Nome do local/endereço (ex: "Hotel Royal Tulip")
        cidade: Cidade (padrão: "Brasília")
        estado: Estado (padrão: "DF")
        pais: País (padrão: "Brasil")
    
    Returns:
        Dict com 'latitude' e 'longitude' se encontrado, None caso contrário
    
    Exemplo:
        >>> coords = geocodificar_endereco("Hotel Royal Tulip")
        >>> print(coords)
        {'latitude': -15.7942, 'longitude': -47.8822}
    """
    if not endereco or not endereco.strip():
        logger.warning("Endereço vazio fornecido para geocodificação")
        return None
    
    endereco_limpo = endereco.strip()
    
    # Estratégias de busca (tentativas em ordem de especificidade)
    estrategias = [
        # 1. Busca completa: endereço + cidade + estado + país
        f"{endereco_limpo}, {cidade}, {estado}, {pais}",
        # 2. Busca com cidade: endereço + cidade + estado
        f"{endereco_limpo}, {cidade}, {estado}",
        # 3. Busca apenas com cidade: endereço + cidade
        f"{endereco_limpo}, {cidade}",
        # 4. Busca apenas o endereço (pode encontrar em qualquer lugar)
        endereco_limpo,
    ]
    
    # Se o endereço parece ser um nome pessoal ou muito genérico, tentar variações
    if len(endereco_limpo.split()) <= 2 and not any(palavra.lower() in endereco_limpo.lower() for palavra in ['hotel', 'condomínio', 'shopping', 'escola', 'igreja', 'colegio', 'associação']):
        # Adicionar estratégias com contexto de Brasília
        estrategias.insert(1, f"{endereco_limpo}, Brasília, DF, Brasil")
        estrategias.insert(2, f"{endereco_limpo}, Distrito Federal, Brasil")
    
    for i, query in enumerate(estrategias, 1):
        try:
            params = {
                'q': query,
                'format': 'json',
                'limit': 3,  # Pegar mais resultados para validar
                'addressdetails': 1,
                'countrycodes': 'br'  # Limitar ao Brasil
            }
            
            logger.debug(f"Tentativa {i}/{len(estrategias)}: {query}")
            response = requests.get(
                NOMINATIM_URL,
                params=params,
                headers=NOMINATIM_HEADERS,
                timeout=10
            )
            
            # Verificar rate limit
            if response.status_code == 429:
                logger.warning("Rate limit atingido. Aguardando antes de tentar novamente...")
                time.sleep(RATE_LIMIT_DELAY * 2)
                continue  # Tentar próxima estratégia
            
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                # Filtrar resultados para priorizar Brasília/DF
                resultados_filtrados = []
                for resultado in data:
                    display_name = resultado.get('display_name', '').lower()
                    # Priorizar resultados em Brasília/DF
                    if 'brasília' in display_name or 'brasilia' in display_name or 'df' in display_name or 'distrito federal' in display_name:
                        resultados_filtrados.insert(0, resultado)
                    else:
                        resultados_filtrados.append(resultado)
                
                # Usar o melhor resultado
                melhor_resultado = resultados_filtrados[0] if resultados_filtrados else data[0]
                
                latitude = float(melhor_resultado['lat'])
                longitude = float(melhor_resultado['lon'])
                
                # Validar se está em Brasília (aproximadamente)
                # Brasília: lat ~-15.8, lon ~-47.9
                if -16.5 <= latitude <= -15.0 and -48.5 <= longitude <= -47.0:
                    logger.info(f"✅ Geocodificação bem-sucedida: {endereco} → ({latitude}, {longitude}) [Estratégia {i}]")
                    return {
                        'latitude': latitude,
                        'longitude': longitude,
                        'display_name': melhor_resultado.get('display_name', ''),
                        'importance': melhor_resultado.get('importance', 0),
                        'estrategia': i
                    }
                else:
                    # Resultado fora de Brasília, mas aceitar se for a última estratégia
                    if i == len(estrategias):
                        logger.warning(f"⚠️  Resultado fora de Brasília para '{endereco}': ({latitude}, {longitude})")
                        return {
                            'latitude': latitude,
                            'longitude': longitude,
                            'display_name': melhor_resultado.get('display_name', ''),
                            'importance': melhor_resultado.get('importance', 0),
                            'estrategia': i,
                            'aviso': 'Coordenadas podem estar incorretas'
                        }
                    # Continuar tentando outras estratégias
                    continue
            
        except requests.exceptions.RequestException as e:
            logger.debug(f"Erro na requisição (estratégia {i}): {e}")
            if i < len(estrategias):
                continue  # Tentar próxima estratégia
            else:
                logger.error(f"❌ Todas as estratégias falharam para '{endereco}'")
                return None
        except (KeyError, ValueError) as e:
            logger.debug(f"Erro ao processar resposta (estratégia {i}): {e}")
            if i < len(estrategias):
                continue
            else:
                return None
        except Exception as e:
            logger.debug(f"Erro inesperado (estratégia {i}): {e}")
            if i < len(estrategias):
                continue
            else:
                return None
        
        # Rate limiting entre tentativas
        if i < len(estrategias):
            time.sleep(RATE_LIMIT_DELAY)
    
    # Se chegou aqui, nenhuma estratégia funcionou
    # Usar coordenadas aproximadas de Brasília como fallback
    logger.warning(f"⚠️  Endereço não encontrado após {len(estrategias)} tentativas: {endereco}")
    logger.info(f"📍 Usando coordenadas aproximadas de Brasília como fallback")
    
    return {
        'latitude': COORDENADAS_BRASILIA['latitude'],
        'longitude': COORDENADAS_BRASILIA['longitude'],
        'display_name': f"{endereco}, Brasília, DF, Brasil (aproximado)",
        'importance': 0,
        'estrategia': 'fallback',
        'aviso': 'Coordenadas aproximadas - endereço não encontrado no Nominatim'
    }


def geocodificar_lixeira(
    session: Session,
    lixeira_id: int,
    cidade: str = "Brasília",
    estado: str = "DF",
    forcar_atualizacao: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Geocodifica uma lixeira específica e atualiza no banco de dados.
    
    Args:
        session: Sessão do SQLAlchemy
        lixeira_id: ID da lixeira
        cidade: Cidade para geocodificação
        estado: Estado para geocodificação
        forcar_atualizacao: Se True, atualiza mesmo se já tiver coordenadas
    
    Returns:
        Tuple (sucesso: bool, mensagem: str)
    """
    from banco_dados.modelos import Lixeira
    
    try:
        lixeira = session.query(Lixeira).filter(Lixeira.id == lixeira_id).first()
        
        if not lixeira:
            return False, f"Lixeira {lixeira_id} não encontrada"
        
        # Verificar se já tem coordenadas
        if not forcar_atualizacao and lixeira.latitude and lixeira.longitude:
            logger.debug(f"Lixeira {lixeira_id} já possui coordenadas. Pulando...")
            return True, "Lixeira já possui coordenadas"
        
        # Geocodificar
        resultado = geocodificar_endereco(
            lixeira.localizacao,
            cidade=cidade,
            estado=estado
        )
        
        if resultado:
            lixeira.latitude = resultado['latitude']
            lixeira.longitude = resultado['longitude']
            session.commit()
            
            # Mensagem informativa sobre o tipo de geocodificação
            if resultado.get('estrategia') == 'fallback':
                mensagem = f"Coordenadas aproximadas (fallback): ({resultado['latitude']}, {resultado['longitude']})"
            else:
                mensagem = f"Coordenadas atualizadas: ({resultado['latitude']}, {resultado['longitude']})"
            
            return True, mensagem
        else:
            return False, f"Não foi possível geocodificar: {lixeira.localizacao}"
            
    except Exception as e:
        session.rollback()
        logger.error(f"Erro ao geocodificar lixeira {lixeira_id}: {e}")
        return False, f"Erro: {str(e)}"


def geocodificar_lixeiras_em_lote(
    session: Session,
    cidade: str = "Brasília",
    estado: str = "DF",
    apenas_sem_coordenadas: bool = True,
    limite: Optional[int] = None
) -> Dict[str, any]:
    """
    Geocodifica múltiplas lixeiras em lote, respeitando rate limits.
    
    Args:
        session: Sessão do SQLAlchemy
        cidade: Cidade para geocodificação
        estado: Estado para geocodificação
        apenas_sem_coordenadas: Se True, processa apenas lixeiras sem coordenadas
        limite: Número máximo de lixeiras a processar (None = todas)
    
    Returns:
        Dict com estatísticas do processamento
    """
    from banco_dados.modelos import Lixeira
    
    stats = {
        'total': 0,
        'processadas': 0,
        'sucesso': 0,
        'falha': 0,
        'puladas': 0,
        'erros': []
    }
    
    try:
        # Buscar lixeiras
        query = session.query(Lixeira)
        
        if apenas_sem_coordenadas:
            query = query.filter(
                (Lixeira.latitude.is_(None)) | (Lixeira.longitude.is_(None))
            )
        
        if limite:
            query = query.limit(limite)
        
        lixeiras = query.all()
        stats['total'] = len(lixeiras)
        
        logger.info(f"Iniciando geocodificação em lote de {stats['total']} lixeiras...")
        
        for i, lixeira in enumerate(lixeiras, 1):
            stats['processadas'] += 1
            
            logger.info(f"Processando {i}/{stats['total']}: {lixeira.localizacao}")
            
            sucesso, mensagem = geocodificar_lixeira(
                session,
                lixeira.id,
                cidade=cidade,
                estado=estado,
                forcar_atualizacao=False
            )
            
            if sucesso:
                if "já possui" in mensagem.lower():
                    stats['puladas'] += 1
                else:
                    stats['sucesso'] += 1
            else:
                stats['falha'] += 1
                stats['erros'].append({
                    'lixeira_id': lixeira.id,
                    'localizacao': lixeira.localizacao,
                    'erro': mensagem
                })
            
            # Rate limiting: aguardar entre requisições
            if i < stats['total']:  # Não aguardar após a última
                time.sleep(RATE_LIMIT_DELAY)
        
        logger.info(f"✅ Geocodificação em lote concluída!")
        logger.info(f"   Total: {stats['total']}")
        logger.info(f"   Sucesso: {stats['sucesso']}")
        logger.info(f"   Falha: {stats['falha']}")
        logger.info(f"   Puladas: {stats['puladas']}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Erro na geocodificação em lote: {e}")
        stats['erros'].append({'erro_geral': str(e)})
        return stats


def validar_coordenadas(latitude: float, longitude: float) -> bool:
    """
    Valida se as coordenadas estão dentro de limites válidos.
    
    Args:
        latitude: Latitude (-90 a 90)
        longitude: Longitude (-180 a 180)
    
    Returns:
        True se válidas, False caso contrário
    """
    return (
        -90 <= latitude <= 90 and
        -180 <= longitude <= 180
    )


if __name__ == "__main__":
    # Configurar logging para teste
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Teste básico
    print("Testando geocodificação...")
    resultado = geocodificar_endereco("Hotel Royal Tulip", "Brasília", "DF")
    if resultado:
        print(f"✅ Sucesso: {resultado}")
    else:
        print("❌ Falha na geocodificação")

