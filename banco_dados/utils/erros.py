"""
Tratamento de Erros - Dashboard-TRONIK
=======================================
Centraliza o tratamento de erros e mensagens de erro seguras.
"""

from typing import Dict, Optional
from flask import jsonify
import logging

logger = logging.getLogger(__name__)


class ErroAPI(Exception):
    """Exceção base para erros da API"""
    def __init__(self, mensagem: str, codigo: int = 400, detalhes: Optional[Dict] = None):
        self.mensagem = mensagem
        self.codigo = codigo
        self.detalhes = detalhes or {}
        super().__init__(self.mensagem)


class ErroValidacao(ErroAPI):
    """Erro de validação de dados"""
    def __init__(self, mensagem: str, detalhes: Optional[Dict] = None):
        super().__init__(mensagem, codigo=400, detalhes=detalhes)


class ErroNaoEncontrado(ErroAPI):
    """Recurso não encontrado"""
    def __init__(self, recurso: str, id_recurso: Optional[int] = None):
        mensagem = f"{recurso} não encontrado"
        if id_recurso:
            mensagem += f" (ID: {id_recurso})"
        super().__init__(mensagem, codigo=404)


class ErroAcessoNegado(ErroAPI):
    """Acesso negado"""
    def __init__(self, mensagem: str = "Acesso negado"):
        super().__init__(mensagem, codigo=403)


def tratar_erro_api(erro: Exception) -> tuple:
    """
    Trata erros da API e retorna resposta JSON apropriada.
    
    Args:
        erro: Exceção capturada
    
    Returns:
        Tuple (jsonify_response, status_code)
    """
    # Se for erro conhecido da API
    if isinstance(erro, ErroAPI):
        logger.warning(f"Erro API: {erro.mensagem} (código: {erro.codigo})")
        resposta = {"erro": erro.mensagem}
        if erro.detalhes:
            resposta["detalhes"] = erro.detalhes
        return jsonify(resposta), erro.codigo
    
    # Erro desconhecido - não expor detalhes em produção
    logger.error(f"Erro interno: {str(erro)}", exc_info=True)
    
    # Em produção, não expor detalhes do erro
    from flask import current_app
    if current_app.config.get('FLASK_ENV') == 'production':
        mensagem = "Erro interno do servidor"
    else:
        mensagem = f"Erro interno: {str(erro)}"
    
    return jsonify({"erro": mensagem}), 500


def validar_requisicao_json(dados: Optional[Dict]) -> None:
    """
    Valida se a requisição contém dados JSON válidos.
    
    Raises:
        ErroValidacao: Se dados não fornecidos
    """
    if not dados:
        raise ErroValidacao("Dados JSON não fornecidos")


def validar_recurso_existe(recurso, nome_recurso: str, id_recurso: Optional[int] = None) -> None:
    """
    Valida se um recurso existe.
    
    Args:
        recurso: Objeto do recurso (ou None)
        nome_recurso: Nome do recurso (ex: "Coletor")
        id_recurso: ID do recurso (opcional)
    
    Raises:
        ErroNaoEncontrado: Se recurso não existe
    """
    if not recurso:
        raise ErroNaoEncontrado(nome_recurso, id_recurso)


def validar_tipo(valor, tipo_esperado, nome_campo: str = "campo"):
    """
    Valida se um valor é do tipo esperado.
    
    Args:
        valor: Valor a validar
        tipo_esperado: Tipo esperado (int, str, float, bool, list, dict)
        nome_campo: Nome do campo para mensagem de erro
    
    Raises:
        ErroValidacao se o tipo não corresponder
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
        raise ErroValidacao(f"{nome_campo} deve ser do tipo {tipo_esperado.__name__}")


def validar_range(valor, min_val=None, max_val=None, nome_campo: str = "campo"):
    """
    Valida se um valor numérico está dentro de um range.
    
    Args:
        valor: Valor a validar
        min_val: Valor mínimo (inclusive)
        max_val: Valor máximo (inclusive)
        nome_campo: Nome do campo para mensagem de erro
    
    Raises:
        ErroValidacao se o valor estiver fora do range
    """
    if valor is None:
        return
    
    if not isinstance(valor, (int, float)):
        raise ErroValidacao(f"{nome_campo} deve ser numérico")
    
    if min_val is not None and valor < min_val:
        raise ErroValidacao(f"{nome_campo} deve ser >= {min_val}")
    
    if max_val is not None and valor > max_val:
        raise ErroValidacao(f"{nome_campo} deve ser <= {max_val}")

