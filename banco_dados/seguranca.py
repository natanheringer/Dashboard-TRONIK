"""
Módulo de Segurança - Dashboard-TRONIK
======================================

Funções e utilitários relacionados à segurança:
- Validação de dados
- Sanitização
- Verificação de permissões
"""

import re
from typing import Optional, Tuple


def validar_email(email: str) -> bool:
    """
    Valida formato de email usando regex básico.
    
    Args:
        email: String com o email a validar
        
    Returns:
        True se o email é válido, False caso contrário
    """
    if not email or not isinstance(email, str):
        return False
    
    # Regex básico para validação de email
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validar_coordenadas(latitude: float, longitude: float) -> bool:
    """
    Valida se as coordenadas geográficas estão dentro dos limites válidos.
    
    Args:
        latitude: Latitude (-90 a 90)
        longitude: Longitude (-180 a 180)
        
    Returns:
        True se as coordenadas são válidas, False caso contrário
    """
    try:
        lat = float(latitude)
        lon = float(longitude)
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (ValueError, TypeError):
        return False


def sanitizar_string(texto: str, max_length: Optional[int] = None) -> str:
    """
    Sanitiza uma string removendo caracteres perigosos e limitando tamanho.
    
    Args:
        texto: String a sanitizar
        max_length: Tamanho máximo permitido (None = sem limite)
        
    Returns:
        String sanitizada
    """
    if not texto or not isinstance(texto, str):
        return ""
    
    # Remove caracteres de controle e espaços extras
    texto = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', texto)
    texto = texto.strip()
    
    # Limita tamanho se especificado
    if max_length and len(texto) > max_length:
        texto = texto[:max_length]
    
    return texto


def validar_nivel_preenchimento(nivel: float) -> Tuple[bool, Optional[str]]:
    """
    Valida nível de preenchimento (0-100).
    
    Args:
        nivel: Nível a validar
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    try:
        nivel_float = float(nivel)
        if nivel_float < 0 or nivel_float > 100:
            return False, "Nível de preenchimento deve estar entre 0 e 100"
        return True, None
    except (ValueError, TypeError):
        return False, "Nível de preenchimento deve ser um número"


def validar_senha(senha: str) -> Tuple[bool, Optional[str]]:
    """
    Valida força da senha.
    
    Requisitos:
    - Mínimo 8 caracteres
    - Pelo menos uma letra maiúscula
    - Pelo menos uma letra minúscula
    - Pelo menos um número
    
    Args:
        senha: Senha a validar
        
    Returns:
        Tupla (é_válida, mensagem_erro)
    """
    if not senha or len(senha) < 8:
        return False, "Senha deve ter pelo menos 8 caracteres"
    
    if not re.search(r'[A-Z]', senha):
        return False, "Senha deve conter pelo menos uma letra maiúscula"
    
    if not re.search(r'[a-z]', senha):
        return False, "Senha deve conter pelo menos uma letra minúscula"
    
    if not re.search(r'\d', senha):
        return False, "Senha deve conter pelo menos um número"
    
    return True, None


def validar_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Valida formato de username.
    
    Requisitos:
    - 3 a 30 caracteres
    - Apenas letras, números, underscore e hífen
    - Deve começar com letra ou número
    
    Args:
        username: Username a validar
        
    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if not username:
        return False, "Username é obrigatório"
    
    if len(username) < 3 or len(username) > 30:
        return False, "Username deve ter entre 3 e 30 caracteres"
    
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$', username):
        return False, "Username pode conter apenas letras, números, underscore e hífen, e deve começar com letra ou número"
    
    return True, None

