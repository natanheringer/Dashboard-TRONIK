"""
Módulo de Segurança - Dashboard-TRONIK
======================================

Funções e utilitários relacionados à segurança:
- Validação de dados
- Sanitização
- Verificação de permissões
"""

import re


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


def validar_bateria(bateria: float) -> tuple[bool, str | None]:
    """
    Valida nível de bateria (deve estar entre 0 e 100).

    Args:
        bateria: Nível de bateria a validar (0-100)

    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    try:
        bateria_float = float(bateria)
        if bateria_float < 0 or bateria_float > 100:
            return False, "Bateria deve estar entre 0 e 100"
        return True, None
    except (ValueError, TypeError):
        return False, "Bateria deve ser um número"


def sanitizar_string(texto: str, max_length: int | None = None, permitir_html: bool = False) -> str:
    """
    Sanitiza uma string removendo caracteres perigosos e limitando tamanho.

    Args:
        texto: String a sanitizar
        max_length: Tamanho máximo permitido (None = sem limite)
        permitir_html: Se False, remove/escapa tags HTML (padrão: False para segurança)

    Returns:
        String sanitizada
    """
    if not texto or not isinstance(texto, str):
        return ""

    # Remove caracteres de controle e espaços extras
    texto = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', texto)
    texto = texto.strip()

    # Prevenir XSS: remover/escapar HTML se não permitido
    if not permitir_html:
        # Escapar caracteres HTML perigosos
        texto = texto.replace('&', '&amp;')
        texto = texto.replace('<', '&lt;')
        texto = texto.replace('>', '&gt;')
        texto = texto.replace('"', '&quot;')
        texto = texto.replace("'", '&#x27;')
        texto = texto.replace('/', '&#x2F;')

    # Remover scripts e eventos inline (proteção adicional)
    texto = re.sub(r'javascript:', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'on\w+\s*=', '', texto, flags=re.IGNORECASE)

    # Limita tamanho se especificado
    if max_length and len(texto) > max_length:
        texto = texto[:max_length]

    return texto


def validar_nivel_preenchimento(nivel: float) -> tuple[bool, str | None]:
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


def validar_senha(senha: str) -> tuple[bool, str | None]:
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


def validar_username(username: str) -> tuple[bool, str | None]:
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


def validar_latitude(latitude: float) -> tuple[bool, str | None]:
    """
    Valida latitude (-90 a 90).

    Args:
        latitude: Latitude a validar

    Returns:
        Tupla (é_válida, mensagem_erro)
    """
    try:
        lat = float(latitude)
        if lat < -90 or lat > 90:
            return False, "Latitude deve estar entre -90 e 90"
        return True, None
    except (ValueError, TypeError):
        return False, "Latitude deve ser um número"


def validar_longitude(longitude: float) -> tuple[bool, str | None]:
    """
    Valida longitude (-180 a 180).

    Args:
        longitude: Longitude a validar

    Returns:
        Tupla (é_válida, mensagem_erro)
    """
    try:
        lon = float(longitude)
        if lon < -180 or lon > 180:
            return False, "Longitude deve estar entre -180 e 180"
        return True, None
    except (ValueError, TypeError):
        return False, "Longitude deve ser um número"


def validar_quantidade_kg(quantidade: float) -> tuple[bool, str | None]:
    """
    Valida quantidade em quilogramas (deve ser > 0).

    Args:
        quantidade: Quantidade a validar

    Returns:
        Tupla (é_válida, mensagem_erro)
    """
    try:
        qtd = float(quantidade)
        if qtd <= 0:
            return False, "Quantidade deve ser maior que zero"
        return True, None
    except (ValueError, TypeError):
        return False, "Quantidade deve ser um número"


def validar_km_percorrido(km: float) -> tuple[bool, str | None]:
    """
    Valida quilômetros percorridos (deve ser >= 0).

    Args:
        km: Quilômetros a validar

    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    try:
        km_float = float(km)
        if km_float < 0:
            return False, "KM percorrido não pode ser negativo"
        return True, None
    except (ValueError, TypeError):
        return False, "KM percorrido deve ser um número"


def validar_preco_combustivel(preco: float) -> tuple[bool, str | None]:
    """
    Valida preço do combustível (deve ser >= 0).

    Args:
        preco: Preço a validar

    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    try:
        preco_float = float(preco)
        if preco_float < 0:
            return False, "Preço do combustível não pode ser negativo"
        return True, None
    except (ValueError, TypeError):
        return False, "Preço do combustível deve ser um número"


def validar_tipo_operacao(tipo: str) -> tuple[bool, str | None]:
    """
    Valida tipo de operação (deve ser "Avulsa" ou "Campanha").

    Args:
        tipo: Tipo de operação a validar

    Returns:
        Tupla (é_válido, mensagem_erro)
    """
    if not tipo:
        return True, None  # Opcional

    tipo_str = str(tipo).strip()
    if tipo_str not in ['Avulsa', 'Campanha']:
        return False, "Tipo de operação deve ser 'Avulsa' ou 'Campanha'"

    return True, None


def validar_meta_comercial(dados: dict) -> list:
    """
    Valida dados de uma meta comercial.

    Args:
        dados: Dicionário com dados da meta

    Returns:
        Lista de erros (vazia se válido)
    """
    erros = []

    if 'valor_meta' in dados:
        try:
            valor = float(dados['valor_meta'])
            if valor < 0:
                erros.append("Valor da meta deve ser positivo")
            if valor > 1000000:  # Limite razoável
                erros.append("Valor da meta muito alto (máximo: R$ 1.000.000)")
        except (ValueError, TypeError):
            erros.append("Valor da meta deve ser um número válido")

    if 'mes' in dados:
        mes = dados['mes']
        if not isinstance(mes, int) or mes < 1 or mes > 12:
            erros.append("Mês deve ser um número entre 1 e 12")

    if 'ano' in dados:
        ano = dados['ano']
        if not isinstance(ano, int) or ano < 2020 or ano > 2100:
            erros.append("Ano deve ser um número válido (2020-2100)")

    if 'observacoes' in dados and dados['observacoes'] and len(dados['observacoes']) > 500:
        erros.append("Observações muito longas (máximo: 500 caracteres)")

    return erros


def validar_sensor(dados: dict, criar: bool = True, db=None) -> list:
    """
    Valida dados de um sensor.

    Args:
        dados: Dicionário com dados do sensor
        criar: Se True, valida campos obrigatórios para criação
        db: Sessão do banco de dados (opcional, para validar relacionamentos)

    Returns:
        Lista de erros (vazia se válido)
    """
    from banco_dados.modelos import Coletor, TipoSensor

    erros = []

    if criar:
        if 'coletor_id' not in dados or not dados['coletor_id']:
            erros.append("Campo 'coletor_id' é obrigatório")
        else:
            # Validar que coletor existe
            if db:
                coletor = db.query(Coletor).filter(Coletor.id == dados['coletor_id']).first()
                if not coletor:
                    erros.append("Coletor não encontrada")

    # Validar bateria
    if 'bateria' in dados and dados['bateria'] is not None:
        valido, erro = validar_bateria(dados['bateria'])
        if not valido:
            erros.append(erro)

    # Validar tipo_sensor_id (se fornecido)
    if 'tipo_sensor_id' in dados and dados['tipo_sensor_id'] is not None and db:
        tipo_sensor = db.query(TipoSensor).filter(TipoSensor.id == dados['tipo_sensor_id']).first()
        if not tipo_sensor:
            erros.append("Tipo de sensor não encontrado")

    return erros

