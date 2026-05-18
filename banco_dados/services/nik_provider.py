"""
Abstracao de chamadas para a Nik via API compativel com OpenAI.

O provider nunca levanta excecao para a camada de servico. Em caso de erro,
retorna uma resposta marcada como falha para que o chamador degrade para
cache ou fallback estatico.

Ordem de tentativa:
1. Opcional (chat): se prefer_nvidia_integrate_first + credenciais Integrate,
   NVIDIA Integrate API (NIK_NVIDIA_INTEGRATE_* / NIK_NVAPI_KEY) com NIK_MODELO_CHAT_NVIDIA ou NIK_MODELO_LANDING_NVIDIA (ex. Nemotron / Mistral Nemotron).
2. Provedor primario (NIK_API_BASE_URL + NVIDIA_API_KEY): modelo pedido, depois NIK_MODELO_FALLBACK.
3. Se tudo falhar e NIK_PROVIDER_FALLBACK_ENABLED + NIK_API_FALLBACK_* estiverem definidos,
   chama o segundo provedor com NIK_NVIDIA_MODELO_DEFAULT (ou NIK_NVIDIA_MODELO).
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)
# Cooldown aplicado apenas ao provedor primario (ex.: Groq em 429/TPD).
_RATE_LIMIT_UNTIL_TS_PRIMARY: float = 0.0

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - ambiente sem dependencia instalada
    OpenAI = None  # type: ignore[assignment]


@dataclass
class NikToolCall:
    """Chamada de ferramenta retornada pelo modelo (formato OpenAI)."""

    id: str
    name: str
    arguments: str


@dataclass
class NikResposta:
    texto: str
    modelo_usado: str
    tokens_prompt: int
    tokens_resposta: int
    latencia_ms: int
    sucesso: bool
    erro: str | None = None
    tool_calls: list[NikToolCall] = field(default_factory=list)


_client_lock = threading.Lock()
_openai_clients: dict[str, Any] = {}


def _strip_bearer(api_key: str) -> str:
    k = (api_key or "").strip()
    if k.lower().startswith("bearer "):
        return k[7:].strip()
    return k


def _http_timeout_s() -> float:
    try:
        return max(15.0, float(os.getenv("NIK_HTTP_TIMEOUT_S", "120") or "120"))
    except ValueError:
        return 120.0


def _network_retry_count() -> int:
    try:
        return max(0, min(5, int(os.getenv("NIK_NETWORK_RETRY_COUNT", "2") or "2")))
    except ValueError:
        return 2


def _network_retry_backoff_s() -> float:
    try:
        return max(0.05, float(os.getenv("NIK_NETWORK_RETRY_BACKOFF_MS", "400") or "400") / 1000.0)
    except ValueError:
        return 0.4


def _cliente_cache_key(prefix: str, base_url: str, api_key: str) -> str:
    import hashlib

    raw = f"{prefix}|{base_url.strip().rstrip('/')}|{api_key}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_openai_client(base_url: str, api_key: str) -> Any:
    """Cliente OpenAI SDK; base_url+key sao usados na documentacao da Groq, NVIDIA Integrate, etc."""
    if OpenAI is None:
        raise RuntimeError("Dependencia 'openai' indisponivel")
    key = _strip_bearer(api_key)
    b = (base_url or "").strip().rstrip("/")
    if not b:
        raise ValueError("base_url do cliente OpenAI vazio")
    return OpenAI(
        base_url=b,
        api_key=key,
        max_retries=int(os.getenv("NIK_PROVIDER_MAX_RETRIES", "0") or "0"),
        timeout=_http_timeout_s(),
    )


def _cliente_para_cached(prefix: str, base_url: str, api_key: str) -> Any:
    key = _strip_bearer(api_key)
    b = (base_url or "").strip().rstrip("/")
    ck = _cliente_cache_key(prefix, b, key)
    with _client_lock:
        cached = _openai_clients.get(ck)
        if cached is not None:
            return cached
        cli = _build_openai_client(b, key)
        _openai_clients[ck] = cli
        return cli


def _cliente_para(base_url: str, api_key: str) -> Any:
    """Compat: cria cliente sem cache (ex.: testes isolados). Preferir _cliente_para_cached."""
    return _build_openai_client((base_url or "").strip().rstrip("/"), api_key)


def _cliente_primario() -> Any:
    return _cliente_para_cached(
        "primary",
        os.getenv("NIK_API_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        os.getenv("NVIDIA_API_KEY", "") or "",
    )


def _nvidia_integrate_api_key() -> str:
    """Chave para `https://integrate.api.nvidia.com/v1` (OpenAI-compatible). Nao usa gsk (Groq)."""
    for k in (
        (os.getenv("NIK_NVIDIA_INTEGRATE_API_KEY") or "").strip(),
        (os.getenv("NIK_NVAPI_KEY") or "").strip(),
        (os.getenv("NIK_API_FALLBACK_KEY") or "").strip(),
    ):
        if k:
            return k
    nik = (os.getenv("NVIDIA_API_KEY") or "").strip()
    if nik.lower().startswith("nvapi-"):
        return nik
    return ""


def _nvidia_integrate_base_url() -> str:
    return (os.getenv("NIK_NVIDIA_INTEGRATE_BASE_URL") or "https://integrate.api.nvidia.com/v1").strip().rstrip("/")


def _nvidia_integrate_ok() -> bool:
    return bool(_nvidia_integrate_api_key() and _nvidia_integrate_base_url())


def _cliente_nvidia_integrate() -> Any:
    return _cliente_para_cached(
        "nvidia_integrate",
        _nvidia_integrate_base_url(),
        _nvidia_integrate_api_key(),
    )


def _nemotron_reasoning_disabled() -> bool:
    """Por defeito sem reasoning (enable_thinking / reasoning_budget)."""
    return os.getenv("NIK_NEMOTRON_REASONING_DISABLED", "true").strip().lower() in {"1", "true", "yes"}


def _strip_nemotron_reasoning_fields(body: dict[str, Any]) -> dict[str, Any]:
    out = dict(body)
    out.pop("reasoning_budget", None)
    ct = out.get("chat_template_kwargs")
    if isinstance(ct, dict):
        ct2 = dict(ct)
        ct2.pop("enable_thinking", None)
        if ct2:
            out["chat_template_kwargs"] = ct2
        else:
            out.pop("chat_template_kwargs", None)
    return out


def _nemotron_extra_body() -> dict[str, Any] | None:
    """Opcional: JSON em NIK_NEMOTRON_EXTRA_BODY ou atalho NIK_NEMOTRON_THINKING (só se reasoning não estiver desligado)."""
    reasoning_off = _nemotron_reasoning_disabled()

    raw = (os.getenv("NIK_NEMOTRON_EXTRA_BODY") or "").strip()
    if raw:
        try:
            out = json.loads(raw)
            if not isinstance(out, dict):
                return None
            if reasoning_off:
                out = _strip_nemotron_reasoning_fields(out)
                return out if out else None
            return out
        except json.JSONDecodeError:
            logger.warning("NIK_NEMOTRON_EXTRA_BODY invalido (JSON)")
            return None

    if reasoning_off:
        return None

    if os.getenv("NIK_NEMOTRON_THINKING", "").strip().lower() in {"1", "true", "yes"}:
        try:
            budget = int(os.getenv("NIK_NEMOTRON_REASONING_BUDGET", "4096") or "4096")
        except ValueError:
            budget = 4096
        return {"reasoning_budget": budget, "chat_template_kwargs": {"enable_thinking": True}}
    return None


def _fallback_provedor_ok() -> bool:
    if os.getenv("NIK_PROVIDER_FALLBACK_ENABLED", "true").strip().lower() not in {"1", "true", "yes"}:
        return False
    b = (os.getenv("NIK_API_FALLBACK_BASE_URL") or "").strip()
    k = (os.getenv("NIK_API_FALLBACK_KEY") or "").strip()
    return bool(b and k)


def _modelo_nvidia_fallback() -> str:
    """Sem Llama 70B: defeito alinhado ao fallback Groq pequeno (NIK_MODELO_FALLBACK)."""
    explicit = (os.getenv("NIK_NVIDIA_MODELO") or os.getenv("NIK_NVIDIA_MODELO_DEFAULT") or "").strip()
    if explicit:
        return explicit
    return (os.getenv("NIK_MODELO_FALLBACK", "") or "").strip() or "llama-3.1-8b-instant"


def _resposta_erro(modelo: str, erro: str) -> NikResposta:
    return NikResposta(
        texto="",
        modelo_usado=modelo,
        tokens_prompt=0,
        tokens_resposta=0,
        latencia_ms=0,
        sucesso=False,
        erro=erro,
    )


def _parse_retry_seconds(erro: str) -> int | None:
    txt = (erro or "").lower()
    m = re.search(r"try again in\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(\d+(?:\.\d+)?)s", txt)
    if not m:
        return None
    horas = int(m.group(1) or 0)
    minutos = int(m.group(2) or 0)
    segundos = float(m.group(3) or 0)
    total = int(horas * 3600 + minutos * 60 + segundos)
    return max(30, total)


def _is_rate_limit_error(erro: str) -> bool:
    txt = (erro or "").lower()
    return "rate_limit_exceeded" in txt or "too many requests" in txt or "tokens per day" in txt


def _is_compound_tpd_error(erro: str) -> bool:
    txt = (erro or "").lower()
    return "type': 'compound'" in txt or '"type": "compound"' in txt or ("service tier" in txt and "tokens per day" in txt)


def _is_transient_network_error(msg: str) -> bool:
    """Erros de infra que costumam sumir com retry curto (nao inclui 429/TPD)."""
    if _is_rate_limit_error(msg):
        return False
    m = (msg or "").lower()
    needles = (
        "timeout",
        "timed out",
        "readtimeout",
        "connecttimeout",
        "connection refused",
        "connection reset",
        "econnrefused",
        "econnreset",
        "remoteprotocolerror",
        "unexpected_eof",
        "broken pipe",
        "502",
        "503",
        "504",
        "temporarily unavailable",
        "nodename nor servname",
        "name or service not known",
        "network is unreachable",
        "ssl",
        "tls",
        "certificate",
        "bad gateway",
        "gateway timeout",
        "connection aborted",
        "connection error",
    )
    return any(n in m for n in needles)


def _sleep_backoff_tentativa(attempt_index: int) -> None:
    """attempt_index 0 = sem espera; após falha 0, espera antes da tentativa 1."""
    if attempt_index <= 0:
        return
    base = _network_retry_backoff_s()
    t = base * (1.35 ** (attempt_index - 1)) * random.uniform(0.85, 1.15)
    time.sleep(min(float(t), 8.0))


def multimodal_habilitado() -> bool:
    return os.getenv("NIK_MULTIMODAL_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def modelo_suporta_visao(modelo: str) -> bool:
    """Gemma 3 27B (NIK_MODELO_OPS) é multimodal; outros via NIK_MODELOS_VISAO."""
    m = (modelo or "").strip().lower()
    if not m:
        return False
    if "gemma-3-27" in m:
        return True
    allow = (os.getenv("NIK_MODELOS_VISAO") or "").strip()
    if allow:
        return any(tok.strip().lower() in m for tok in allow.split(",") if tok.strip())
    return False


def _executar_uma_chamada_visao(
    client: Any,
    tentativa_modelo: str,
    system_prompt: str,
    user_text: str,
    image_b64: str,
    mime: str,
    max_tokens: int,
    temperature: float,
) -> NikResposta:
    inicio = time.perf_counter()
    retries = _network_retry_count()
    ultima_exc: Exception | None = None
    mime_safe = (mime or "image/jpeg").split(";")[0].strip() or "image/jpeg"
    data_url = f"data:{mime_safe};base64,{image_b64}"
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    for attempt in range(retries + 1):
        _sleep_backoff_tentativa(attempt)
        kwargs: dict[str, Any] = {
            "model": tentativa_modelo,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:
            ultima_exc = exc
            msg = str(exc)
            if attempt < retries and _is_transient_network_error(msg):
                logger.warning(
                    "Nik visão rede transitória (modelo=%s tentativa=%s/%s): %s",
                    tentativa_modelo,
                    attempt + 1,
                    retries + 1,
                    exc,
                )
                continue
            raise exc

        latencia_ms = int((time.perf_counter() - inicio) * 1000)
        choice = resp.choices[0] if resp.choices else None
        texto = ""
        if choice and getattr(choice, "message", None):
            texto = choice.message.content or ""
        usage = getattr(resp, "usage", None)
        return NikResposta(
            texto=texto,
            modelo_usado=tentativa_modelo,
            tokens_prompt=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_resposta=getattr(usage, "completion_tokens", 0) or 0,
            latencia_ms=latencia_ms,
            sucesso=bool(texto.strip()),
            erro=None if texto.strip() else "Resposta vazia do modelo",
        )

    raise ultima_exc or RuntimeError("Falha sem exceção registrada")


def chamar_modelo_visao(
    system_prompt: str,
    user_text: str,
    image_b64: str,
    mime: str = "image/jpeg",
    modelo: str | None = None,
    max_tokens: int = 512,
    temperature: float = 0.3,
) -> NikResposta:
    """Chamada vision (image_url data URL) para modelos OpenAI-compatible com visão."""
    modelo_principal = modelo or os.getenv("NIK_MODELO_OPS", "google/gemma-3-27b-it")
    if not modelo_suporta_visao(modelo_principal):
        return _resposta_erro(modelo_principal, f"Modelo {modelo_principal} não suporta visão")

    api_key = _strip_bearer(os.getenv("NVIDIA_API_KEY") or "")
    if not api_key:
        return _resposta_erro(modelo_principal, "NVIDIA_API_KEY ausente (provedor primario)")

    # Preferir NVIDIA Integrate (Gemma 3 27B multimodal no NIM)
    if _nvidia_integrate_ok():
        try:
            out_nv = _executar_uma_chamada_visao(
                _cliente_nvidia_integrate(),
                modelo_principal,
                system_prompt,
                user_text,
                image_b64,
                mime,
                max_tokens,
                temperature,
            )
            if out_nv.sucesso:
                return out_nv
        except Exception as exc:  # pragma: no cover
            logger.warning("Nik visão (NVIDIA Integrate): %s", exc)

    try:
        out = _executar_uma_chamada_visao(
            _cliente_primario(),
            modelo_principal,
            system_prompt,
            user_text,
            image_b64,
            mime,
            max_tokens,
            temperature,
        )
        if out.sucesso:
            return out
        return _resposta_erro(modelo_principal, out.erro or "Resposta vazia")
    except Exception as exc:  # pragma: no cover
        return _resposta_erro(modelo_principal, str(exc))


def _executar_uma_chamada(
    client: Any,
    tentativa_modelo: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    response_format: dict[str, Any] | None,
    extra_body: dict[str, Any] | None = None,
) -> NikResposta:
    inicio = time.perf_counter()
    retries = _network_retry_count()
    ultima_exc: Exception | None = None

    for attempt in range(retries + 1):
        _sleep_backoff_tentativa(attempt)
        kwargs: dict[str, Any] = {
            "model": tentativa_modelo,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if extra_body:
            kwargs["extra_body"] = extra_body
        if response_format:
            kwargs["response_format"] = response_format
        try:
            try:
                resp = client.chat.completions.create(**kwargs)
            except Exception as first_exc:
                if response_format:
                    kwargs.pop("response_format", None)
                    resp = client.chat.completions.create(**kwargs)
                else:
                    raise first_exc
        except Exception as exc:
            ultima_exc = exc
            msg = str(exc)
            if attempt < retries and _is_transient_network_error(msg):
                logger.warning(
                    "Nik provider rede transitória (modelo=%s tentativa=%s/%s): %s",
                    tentativa_modelo,
                    attempt + 1,
                    retries + 1,
                    exc,
                )
                continue
            raise exc

        latencia_ms = int((time.perf_counter() - inicio) * 1000)
        choice = resp.choices[0] if resp.choices else None
        texto = ""
        if choice and getattr(choice, "message", None):
            texto = choice.message.content or ""
        usage = getattr(resp, "usage", None)
        return NikResposta(
            texto=texto,
            modelo_usado=tentativa_modelo,
            tokens_prompt=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_resposta=getattr(usage, "completion_tokens", 0) or 0,
            latencia_ms=latencia_ms,
            sucesso=bool(texto.strip()),
            erro=None if texto.strip() else "Resposta vazia do modelo",
        )

    raise ultima_exc or RuntimeError("Falha sem exceção registrada")


def chamar_modelo(
    system_prompt: str,
    user_prompt: str,
    modelo: str | None = None,
    max_tokens: int = 512,
    temperature: float = 0.3,
    response_format: dict[str, Any] | None = None,
    *,
    prefer_nvidia_integrate_first: bool = False,
    modelo_primario_se_sem_nv: str | None = None,
) -> NikResposta:
    """Chama o modelo no provedor primario; se falhar, tenta fallback de modelo e depois provedor secundario (NVIDIA)."""
    global _RATE_LIMIT_UNTIL_TS_PRIMARY
    modelo_principal = modelo or os.getenv("NIK_MODELO_OPS", "google/gemma-3-27b-it")
    modelo_fallback = os.getenv("NIK_MODELO_FALLBACK", "google/gemma-3-1b-it")
    ultimo_erro = "Falha desconhecida"

    # 1) Chat via NVIDIA Integrate (Nemotron): antes do cooldown Groq — usa chave nvapi, nao a gsk da Groq.
    if prefer_nvidia_integrate_first and _nvidia_integrate_ok():
        logger.info(
            "Nik provider: NVIDIA Integrate primeiro (modelo=%s, base=%s)",
            modelo_principal,
            _nvidia_integrate_base_url(),
        )
        try:
            extra_nv = _nemotron_extra_body()
            out_nv_i = _executar_uma_chamada(
                _cliente_nvidia_integrate(),
                modelo_principal,
                system_prompt,
                user_prompt,
                max_tokens,
                temperature,
                response_format,
                extra_body=extra_nv,
            )
            if out_nv_i.sucesso:
                return out_nv_i
            ultimo_erro = out_nv_i.erro or ultimo_erro
        except Exception as exc:  # pragma: no cover - depende da API externa
            ultimo_erro = str(exc)
            logger.warning("Nik provider (NVIDIA Integrate / chat): %s", exc)
    elif prefer_nvidia_integrate_first and not _nvidia_integrate_ok():
        logger.warning(
            "NIK_CHAT_USE_NVIDIA ativo mas falta chave Integrate (nvapi): "
            "NIK_NVAPI_KEY / NIK_API_FALLBACK_KEY, ou NVIDIA_API_KEY com prefixo nvapi-."
        )

    api_key = _strip_bearer(os.getenv("NVIDIA_API_KEY") or "")

    if not api_key:
        return _resposta_erro(modelo_principal, "NVIDIA_API_KEY ausente (provedor primario)")

    agora = time.time()
    em_cooldown_primario = agora < _RATE_LIMIT_UNTIL_TS_PRIMARY
    if em_cooldown_primario and not _fallback_provedor_ok():
        restante = int(_RATE_LIMIT_UNTIL_TS_PRIMARY - agora)
        return _resposta_erro(modelo_principal, f"Provedor primario em cooldown por rate limit. Tente novamente em ~{restante}s.")

    start_primary = (
        modelo_primario_se_sem_nv
        if (prefer_nvidia_integrate_first and modelo_primario_se_sem_nv)
        else modelo_principal
    )
    modelos_tentativa = [start_primary]
    if modelo_fallback and modelo_fallback != start_primary:
        modelos_tentativa.append(modelo_fallback)

    if not em_cooldown_primario:
        for tentativa_modelo in modelos_tentativa:
            try:
                client = _cliente_primario()
                out = _executar_uma_chamada(
                    client,
                    tentativa_modelo,
                    system_prompt,
                    user_prompt,
                    max_tokens,
                    temperature,
                    response_format,
                    None,
                )
                if out.sucesso:
                    return out
                ultimo_erro = out.erro or "Resposta vazia"
            except Exception as exc:  # pragma: no cover - depende da API externa
                ultimo_erro = str(exc)
                logger.warning("Nik provider falhou para %s: %s", tentativa_modelo, exc)
                if _is_rate_limit_error(ultimo_erro):
                    retry_secs = _parse_retry_seconds(ultimo_erro)
                    if retry_secs is None:
                        retry_secs = int(os.getenv("NIK_RATE_LIMIT_COOLDOWN_SECONDS", "900") or "900")
                    _RATE_LIMIT_UNTIL_TS_PRIMARY = time.time() + max(30, retry_secs)
                    try_fallback = os.getenv("NIK_TRY_FALLBACK_ON_RATE_LIMIT", "true").strip().lower() in {"1", "true", "yes"}
                    if (
                        try_fallback
                        and tentativa_modelo != (modelo_fallback or "")
                        and modelo_fallback
                        and modelo_fallback != tentativa_modelo
                        and _is_compound_tpd_error(ultimo_erro)
                    ):
                        continue
                    break

    if _fallback_provedor_ok():
        fb_key = _strip_bearer(os.getenv("NIK_API_FALLBACK_KEY", "") or "")
        fb_base = (os.getenv("NIK_API_FALLBACK_BASE_URL") or "").strip().rstrip("/")
        modelo_nv = _modelo_nvidia_fallback()
        try:
            client_fb = _cliente_para_cached("fallback_nvidia", fb_base, fb_key)
            out_nv = _executar_uma_chamada(
                client_fb,
                modelo_nv,
                system_prompt,
                user_prompt,
                max_tokens,
                temperature,
                response_format,
            )
            if out_nv.sucesso:
                return out_nv
            ultimo_erro = out_nv.erro or ultimo_erro
        except Exception as exc:  # pragma: no cover
            ultimo_erro = str(exc)
            logger.warning("Nik provider (fallback NVIDIA) falhou para %s: %s", modelo_nv, exc)

    return _resposta_erro(modelo_fallback or modelo_principal, ultimo_erro)


def _extrair_tool_calls(choice: Any) -> list[NikToolCall]:
    if not choice or not getattr(choice, "message", None):
        return []
    msg = choice.message
    bruto = getattr(msg, "tool_calls", None) or []
    saida: list[NikToolCall] = []
    for tc in bruto:
        fn = getattr(tc, "function", None)
        if not fn:
            continue
        nome = str(getattr(fn, "name", "") or "").strip()
        if not nome:
            continue
        saida.append(
            NikToolCall(
                id=str(getattr(tc, "id", "") or ""),
                name=nome,
                arguments=str(getattr(fn, "arguments", "") or "{}"),
            )
        )
    return saida


def _executar_uma_chamada_com_ferramentas(
    client: Any,
    tentativa_modelo: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    max_tokens: int,
    temperature: float,
    extra_body: dict[str, Any] | None = None,
) -> NikResposta:
    inicio = time.perf_counter()
    retries = _network_retry_count()
    ultima_exc: Exception | None = None
    msgs = [{"role": "system", "content": system_prompt}, *list(messages)]

    for attempt in range(retries + 1):
        _sleep_backoff_tentativa(attempt)
        kwargs: dict[str, Any] = {
            "model": tentativa_modelo,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "tools": tools,
            "tool_choice": "auto",
        }
        if extra_body:
            kwargs["extra_body"] = extra_body
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as exc:
            ultima_exc = exc
            msg = str(exc)
            if attempt < retries and _is_transient_network_error(msg):
                logger.warning(
                    "Nik provider tools rede transitória (modelo=%s tentativa=%s/%s): %s",
                    tentativa_modelo,
                    attempt + 1,
                    retries + 1,
                    exc,
                )
                continue
            raise exc

        latencia_ms = int((time.perf_counter() - inicio) * 1000)
        choice = resp.choices[0] if resp.choices else None
        texto = ""
        tool_calls: list[NikToolCall] = []
        if choice and getattr(choice, "message", None):
            texto = choice.message.content or ""
            tool_calls = _extrair_tool_calls(choice)
        usage = getattr(resp, "usage", None)
        ok = bool(texto.strip()) or bool(tool_calls)
        return NikResposta(
            texto=texto,
            modelo_usado=tentativa_modelo,
            tokens_prompt=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_resposta=getattr(usage, "completion_tokens", 0) or 0,
            latencia_ms=latencia_ms,
            sucesso=ok,
            erro=None if ok else "Resposta vazia do modelo",
            tool_calls=tool_calls,
        )

    raise ultima_exc or RuntimeError("Falha sem exceção registrada")


def chamar_modelo_com_ferramentas(
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    modelo: str | None = None,
    *,
    max_tokens: int = 1024,
    temperature: float = 0.4,
    max_rounds: int = 4,
) -> NikResposta:
    """
    Uma rodada de chat com tools nativas (OpenAI-compatible).
    O loop multi-turn fica em nik_agent_loop; max_rounds é metadado para o chamador.
    """
    _ = max_rounds  # reservado para o orquestrador do loop
    modelo_principal = modelo or os.getenv("NIK_MODELO_OPS", "google/gemma-3-27b-it")
    modelo_fallback = os.getenv("NIK_MODELO_FALLBACK", "google/gemma-3-1b-it")
    ultimo_erro = "Falha desconhecida"

    api_key = _strip_bearer(os.getenv("NVIDIA_API_KEY") or "")
    if not api_key:
        return _resposta_erro(modelo_principal, "NVIDIA_API_KEY ausente (provedor primario)")

    modelos_tentativa = [modelo_principal]
    if modelo_fallback and modelo_fallback != modelo_principal:
        modelos_tentativa.append(modelo_fallback)

    for tentativa_modelo in modelos_tentativa:
        try:
            client = _cliente_primario()
            out = _executar_uma_chamada_com_ferramentas(
                client,
                tentativa_modelo,
                system_prompt,
                messages,
                tools,
                max_tokens,
                temperature,
                None,
            )
            if out.sucesso:
                return out
            ultimo_erro = out.erro or "Resposta vazia"
        except Exception as exc:  # pragma: no cover
            ultimo_erro = str(exc)
            logger.warning("Nik provider (tools) falhou para %s: %s", tentativa_modelo, exc)

    if _fallback_provedor_ok():
        fb_key = _strip_bearer(os.getenv("NIK_API_FALLBACK_KEY", "") or "")
        fb_base = (os.getenv("NIK_API_FALLBACK_BASE_URL") or "").strip().rstrip("/")
        modelo_nv = _modelo_nvidia_fallback()
        try:
            client_fb = _cliente_para_cached("fallback_nvidia_tools", fb_base, fb_key)
            out_nv = _executar_uma_chamada_com_ferramentas(
                client_fb,
                modelo_nv,
                system_prompt,
                messages,
                tools,
                max_tokens,
                temperature,
            )
            if out_nv.sucesso:
                return out_nv
            ultimo_erro = out_nv.erro or ultimo_erro
        except Exception as exc:  # pragma: no cover
            ultimo_erro = str(exc)
            logger.warning("Nik provider (tools fallback) falhou: %s", exc)

    return _resposta_erro(modelo_fallback or modelo_principal, ultimo_erro)
