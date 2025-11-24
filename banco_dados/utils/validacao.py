"""
Utilitários de Validação - Dashboard-TRONIK
===========================================
Funções padronizadas para validação de dados de entrada.
"""

from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from banco_dados.utils.erros import ErroValidacao


def validar_obrigatorio(valor: Any, nome_campo: str) -> None:
    """
    Valida se um campo obrigatório foi fornecido.
    
    Raises:
        ErroValidacao: Se o campo não foi fornecido
    """
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ErroValidacao(f"Campo '{nome_campo}' é obrigatório")


def validar_tipo_campo(valor: Any, tipo_esperado: type, nome_campo: str) -> None:
    """
    Valida se um campo é do tipo esperado.
    
    Raises:
        ErroValidacao: Se o tipo não corresponder
    """
    if valor is None:
        return
    
    tipo_map = {
        int: (int,),
        str: (str,),
        float: (float, int),  # Aceita int também
        bool: (bool,),
        list: (list,),
        dict: (dict,)
    }
    
    tipos_aceitos = tipo_map.get(tipo_esperado, (tipo_esperado,))
    
    if not isinstance(valor, tipos_aceitos):
        raise ErroValidacao(f"Campo '{nome_campo}' deve ser do tipo {tipo_esperado.__name__}")


def validar_range(valor: float, min_val: Optional[float] = None, max_val: Optional[float] = None, nome_campo: str = "campo") -> None:
    """
    Valida se um valor numérico está dentro de um range.
    
    Raises:
        ErroValidacao: Se o valor estiver fora do range
    """
    if valor is None:
        return
    
    if not isinstance(valor, (int, float)):
        raise ErroValidacao(f"Campo '{nome_campo}' deve ser numérico")
    
    if min_val is not None and valor < min_val:
        raise ErroValidacao(f"Campo '{nome_campo}' deve ser >= {min_val}")
    
    if max_val is not None and valor > max_val:
        raise ErroValidacao(f"Campo '{nome_campo}' deve ser <= {max_val}")


def validar_tamanho_string(valor: str, min_len: Optional[int] = None, max_len: Optional[int] = None, nome_campo: str = "campo") -> None:
    """
    Valida tamanho de uma string.
    
    Raises:
        ErroValidacao: Se o tamanho estiver fora dos limites
    """
    if valor is None:
        return
    
    if not isinstance(valor, str):
        raise ErroValidacao(f"Campo '{nome_campo}' deve ser uma string")
    
    tamanho = len(valor)
    
    if min_len is not None and tamanho < min_len:
        raise ErroValidacao(f"Campo '{nome_campo}' deve ter pelo menos {min_len} caracteres")
    
    if max_len is not None and tamanho > max_len:
        raise ErroValidacao(f"Campo '{nome_campo}' deve ter no máximo {max_len} caracteres")


def validar_id_positivo(valor: Any, nome_campo: str = "id") -> int:
    """
    Valida se um valor é um ID positivo válido.
    
    Returns:
        int: ID validado
        
    Raises:
        ErroValidacao: Se o ID não for válido
    """
    if valor is None:
        raise ErroValidacao(f"Campo '{nome_campo}' é obrigatório")
    
    try:
        id_int = int(valor)
    except (ValueError, TypeError):
        raise ErroValidacao(f"Campo '{nome_campo}' deve ser um número inteiro")
    
    if id_int <= 0:
        raise ErroValidacao(f"Campo '{nome_campo}' deve ser um número positivo")
    
    return id_int


def validar_data_iso(data_str: str, nome_campo: str = "data") -> datetime:
    """
    Valida e converte uma string de data ISO 8601.
    
    Returns:
        datetime: Data validada
        
    Raises:
        ErroValidacao: Se a data não for válida
    """
    if not data_str:
        raise ErroValidacao(f"Campo '{nome_campo}' é obrigatório")
    
    try:
        # Suportar formato com e sem timezone
        data_str_clean = data_str.replace('Z', '+00:00')
        return datetime.fromisoformat(data_str_clean)
    except (ValueError, AttributeError) as e:
        raise ErroValidacao(f"Campo '{nome_campo}' deve estar no formato ISO 8601 (ex: 2025-11-24T10:00:00)")


def validar_enum(valor: Any, valores_permitidos: List[Any], nome_campo: str = "campo") -> None:
    """
    Valida se um valor está em uma lista de valores permitidos.
    
    Raises:
        ErroValidacao: Se o valor não estiver na lista
    """
    if valor is None:
        return
    
    if valor not in valores_permitidos:
        valores_str = ', '.join(str(v) for v in valores_permitidos)
        raise ErroValidacao(f"Campo '{nome_campo}' deve ser um dos seguintes valores: {valores_str}")


def validar_paginacao(pagina: Optional[int] = None, por_pagina: Optional[int] = None) -> Tuple[int, int]:
    """
    Valida e normaliza parâmetros de paginação.
    
    Returns:
        Tuple[int, int]: (pagina, por_pagina) validados
        
    Raises:
        ErroValidacao: Se os parâmetros forem inválidos
    """
    # Valores padrão
    pagina = pagina or 1
    por_pagina = por_pagina or 50
    
    # Validar tipos
    try:
        pagina = int(pagina)
        por_pagina = int(por_pagina)
    except (ValueError, TypeError):
        raise ErroValidacao("Parâmetros de paginação devem ser números inteiros")
    
    # Validar ranges
    if pagina < 1:
        pagina = 1
    if pagina > 1000:
        raise ErroValidacao("Número de página não pode ser maior que 1000")
    
    if por_pagina < 1:
        por_pagina = 1
    if por_pagina > 500:
        raise ErroValidacao("Itens por página não pode ser maior que 500")
    
    return pagina, por_pagina


def validar_dados_requisicao(dados: Optional[Dict], campos_obrigatorios: List[str] = None) -> Dict:
    """
    Valida dados de uma requisição JSON.
    
    Args:
        dados: Dados da requisição
        campos_obrigatorios: Lista de campos obrigatórios
        
    Returns:
        Dict: Dados validados
        
    Raises:
        ErroValidacao: Se dados inválidos
    """
    if not dados:
        raise ErroValidacao("Dados não fornecidos")
    
    if not isinstance(dados, dict):
        raise ErroValidacao("Dados devem ser um objeto JSON")
    
    # Validar campos obrigatórios
    if campos_obrigatorios:
        for campo in campos_obrigatorios:
            validar_obrigatorio(dados.get(campo), campo)
    
    return dados


def sanitizar_dados_entrada(dados: Dict, campos_string: List[str] = None) -> Dict:
    """
    Sanitiza dados de entrada removendo espaços e caracteres perigosos.
    
    Args:
        dados: Dados a sanitizar
        campos_string: Lista de campos que são strings e devem ser sanitizados.
                      Se None, sanitiza todas as strings encontradas.
        
    Returns:
        Dict: Dados sanitizados
    """
    from banco_dados.seguranca import sanitizar_string
    
    dados_sanitizados = {}
    
    for chave, valor in dados.items():
        # Se campos_string for None, sanitizar todas as strings
        # Se campos_string for especificado, sanitizar apenas os campos listados
        if isinstance(valor, str):
            if campos_string is None or chave in campos_string:
                # Aplicar sanitização com limite de tamanho baseado no campo
                max_length = 1000  # Padrão
                if chave in ['titulo', 'nome']:
                    max_length = 200
                elif chave in ['descricao', 'observacoes']:
                    max_length = 2000
                elif chave in ['email']:
                    max_length = 255
                dados_sanitizados[chave] = sanitizar_string(valor, max_length=max_length)
            else:
                dados_sanitizados[chave] = valor
        else:
            dados_sanitizados[chave] = valor
    
    return dados_sanitizados

