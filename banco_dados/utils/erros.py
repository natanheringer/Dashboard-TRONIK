"""
Tratamento de Erros - Dashboard-TRONIK
=======================================
Centraliza o tratamento de erros e mensagens de erro seguras.

As classes de erro (ErroAPI e filhas) sao puras: podem ser importadas
de qualquer camada (contratos, services, rotas) sem puxar Flask junto.
So a funcao `tratar_erro_api` depende do Flask, e o import e feito
on-demand dentro dela.
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# Envelope padronizado de resposta da API
# ---------------------------------------
# Sucesso: {"ok": true,  "dados": <payload>, "erros": null}
# Erro:    {"ok": false, "dados": null,       "erros": [{codigo, mensagem, campo?}], "erro": "<msg primaria>"}
#
# A chave "erro" (singular, string) e mantida no envelope de erro por
# compatibilidade com clientes antigos. Novos clientes devem consumir "erros".


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


def _erro_codigo(erro: "ErroAPI") -> str:
    """Mapeia classe de erro para codigo textual estavel (consumido pelo frontend)."""
    if isinstance(erro, ErroValidacao):
        return "VALIDACAO"
    if isinstance(erro, ErroNaoEncontrado):
        return "NAO_ENCONTRADO"
    if isinstance(erro, ErroAcessoNegado):
        return "ACESSO_NEGADO"
    return "ERRO_API"


def resposta_ok(dados: Any = None, status: int = 200) -> tuple:
    """Retorna uma resposta de sucesso no envelope padrao.

    Args:
        dados: Qualquer estrutura serializavel (dict, list, modelo Pydantic via .model_dump()).
        status: HTTP status (default 200).
    """
    from flask import jsonify

    return jsonify({"ok": True, "dados": dados, "erros": None}), status


def resposta_erro(
    mensagem: str,
    status: int = 400,
    codigo: str = "ERRO_API",
    campo: Optional[str] = None,
    detalhes: Optional[Dict[str, Any]] = None,
) -> tuple:
    """Retorna uma resposta de erro no envelope padrao.

    Mantem a chave legacy "erro" (string) para backward-compat.
    """
    from flask import jsonify

    item: Dict[str, Any] = {"codigo": codigo, "mensagem": mensagem}
    if campo:
        item["campo"] = campo
    if detalhes:
        item["detalhes"] = detalhes

    envelope = {
        "ok": False,
        "dados": None,
        "erros": [item],
        "erro": mensagem,  # legacy alias
    }
    return jsonify(envelope), status


def tratar_erro_api(erro: Exception) -> tuple:
    """Handler global: converte qualquer Exception no envelope padrao da API.

    Registrado em app.py via ``app.register_error_handler(ErroAPI, tratar_erro_api)``
    e tambem como fallback para Exception. Mantem backward-compat com clientes que
    consomem a chave "erro" (string).
    """
    from flask import current_app

    if isinstance(erro, ErroAPI):
        logger.warning("Erro API: %s (codigo HTTP: %s)", erro.mensagem, erro.codigo)
        return resposta_erro(
            mensagem=erro.mensagem,
            status=erro.codigo,
            codigo=_erro_codigo(erro),
            detalhes=erro.detalhes or None,
        )

    logger.error("Erro interno: %s", erro, exc_info=True)
    em_prod = (current_app.config.get("FLASK_ENV") == "production")
    mensagem = "Erro interno do servidor" if em_prod else f"Erro interno: {erro}"
    return resposta_erro(mensagem=mensagem, status=500, codigo="ERRO_INTERNO")


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

