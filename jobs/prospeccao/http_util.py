"""HTTP robusto: Session com Retry (urllib3), downloads com retomada parcial."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, BinaryIO

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from jobs.prospeccao import config

logger = logging.getLogger(__name__)

_SESSION: requests.Session | None = None


def request_timeout(timeout: float | None = None) -> float | tuple[float, float]:
    """Return a requests timeout with bounded connect and read phases."""
    if timeout is not None:
        return timeout
    return (config.HTTP_CONNECT_TIMEOUT_S, config.HTTP_READ_TIMEOUT_S)


def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=config.HTTP_MAX_RETRIES,
        connect=config.HTTP_MAX_RETRIES,
        read=config.HTTP_MAX_RETRIES,
        backoff_factor=config.HTTP_BACKOFF_FACTOR,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST", "HEAD"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update(
        {
            "User-Agent": config.HTTP_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
        }
    )
    return s


def session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = build_session()
    return _SESSION


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> Any:
    logger.debug("HTTP GET json: %s params=%s", url, params)
    r = session().get(url, params=params, timeout=request_timeout(timeout))
    r.raise_for_status()
    return r.json()


def post_json(url: str, *, json_body: dict[str, Any] | None = None) -> Any:
    logger.debug("HTTP POST json: %s", url)
    r = session().post(url, json=json_body or {}, timeout=request_timeout())
    r.raise_for_status()
    return r.json()


@dataclass
class DownloadResult:
    path: str
    bytes_written: int
    skipped: bool
    truncated: bool
    sha256: str | None = None


@dataclass
class LinkCheckResult:
    url: str
    ok: bool
    method: str
    status_code: int | None = None
    final_url: str | None = None
    content_type: str | None = None
    content_length: int | None = None
    error: str | None = None


def _sha256_stream(fp: BinaryIO, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    while True:
        b = fp.read(chunk)
        if not b:
            break
        h.update(b)
    return h.hexdigest()


def stream_download(
    url: str,
    dest: BinaryIO,
    *,
    max_bytes: int | None = None,
    chunk_size: int = 1 << 20,
    pause_s: float = 0.0,
    resume_offset: int = 0,
) -> int:
    """Grava corpo; resume_offset usa header Range (servidor deve suportar)."""
    headers: dict[str, str] = {}
    if resume_offset > 0:
        headers["Range"] = f"bytes={resume_offset}-"
    written = resume_offset
    mode_start = written
    started = time.monotonic()
    max_seconds = config.DOWNLOAD_MAX_SECONDS if config.DOWNLOAD_MAX_SECONDS > 0 else None
    progress_every = max(1, config.DOWNLOAD_PROGRESS_EVERY_MB) * 1024 * 1024
    next_progress = written + progress_every
    logger.info("Download start: %s resume_offset=%s max_bytes=%s", url[:160], resume_offset, max_bytes)
    with session().get(
        url,
        stream=True,
        timeout=request_timeout(),
        headers=headers,
    ) as resp:
        if resume_offset > 0 and resp.status_code not in (200, 206):
            resp.raise_for_status()
        else:
            resp.raise_for_status()
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue
            if max_bytes is not None and written - mode_start + len(chunk) > max_bytes:
                dest.write(chunk[: max_bytes - (written - mode_start)])
                written = mode_start + max_bytes
                break
            dest.write(chunk)
            written += len(chunk)
            if written >= next_progress:
                logger.info("Download progress: %.1f MB url=%s", written / (1024 * 1024), url[:120])
                next_progress = written + progress_every
            if max_seconds is not None and time.monotonic() - started > max_seconds:
                raise TimeoutError(
                    f"Download exceeded TRONIK_DOWNLOAD_MAX_SECONDS={max_seconds}: {url}"
                )
            if pause_s > 0:
                time.sleep(pause_s)
    logger.info("Download complete: %.1f MB url=%s", written / (1024 * 1024), url[:120])
    return written


def download_url_to_path(
    url: str,
    dest_path: Any,
    *,
    max_bytes: int | None = None,
    resume: bool = True,
    skip_if_same_size: bool = True,
    compute_hash: bool = False,
) -> DownloadResult:
    """
    Descarrega URL para ficheiro. Se resume=True e o servidor anunciar Content-Length
    igual ao ficheiro existente, não rebaixa. Se Range suportado e ficheiro parcial,
    tenta continuar.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    cl: str | None = None
    ar = False
    try:
        head = session().head(url, allow_redirects=True, timeout=request_timeout())
        if head.ok:
            cl = head.headers.get("Content-Length")
            ar = (head.headers.get("Accept-Ranges") or "").lower() == "bytes"
        head.close()
    except requests.RequestException:
        pass

    expected = int(cl) if cl and cl.isdigit() else None
    if skip_if_same_size and expected is not None and dest_path.exists():
        cur = dest_path.stat().st_size
        if cur == expected and max_bytes is None:
            logger.info("Já existe com mesmo tamanho (%s bytes), a saltar: %s", cur, dest_path.name)
            h = None
            if compute_hash:
                with dest_path.open("rb") as fp:
                    h = _sha256_stream(fp)
            return DownloadResult(str(dest_path), cur, True, False, h)

    offset = 0
    if resume and dest_path.exists() and expected is not None and ar:
        cur = dest_path.stat().st_size
        if 0 < cur < expected:
            offset = cur
            logger.info("Retomando download a partir de byte %s: %s", offset, dest_path.name)

    mode = "ab" if offset else "wb"
    truncated = max_bytes is not None
    with dest_path.open(mode) as fp:
        n = stream_download(url, fp, max_bytes=max_bytes, resume_offset=offset)

    sha = None
    if compute_hash and (max_bytes is None):
        with dest_path.open("rb") as fp:
            sha = _sha256_stream(fp)

    return DownloadResult(str(dest_path), n, False, truncated, sha)


def check_url(
    url: str,
    *,
    timeout: float | None = None,
    allow_get_fallback: bool = True,
) -> LinkCheckResult:
    """Validate a data URL with HEAD, falling back to a small GET when needed."""
    to = timeout if timeout is not None else config.LINK_CHECK_TIMEOUT_S
    try:
        logger.debug("Checking URL via HEAD: %s", url)
        response = session().head(url, allow_redirects=True, timeout=to)
        method = "HEAD"
        if allow_get_fallback and (response.status_code in (403, 405, 406) or response.status_code >= 500):
            logger.debug("HEAD inconclusive (%s), checking URL via GET: %s", response.status_code, url)
            response.close()
            response = session().get(
                url,
                allow_redirects=True,
                timeout=to,
                headers={"Range": "bytes=0-0"},
                stream=True,
            )
            method = "GET"
        content_length = response.headers.get("Content-Length")
        result = LinkCheckResult(
            url=url,
            ok=200 <= response.status_code < 400,
            method=method,
            status_code=response.status_code,
            final_url=response.url,
            content_type=response.headers.get("Content-Type"),
            content_length=int(content_length) if content_length and content_length.isdigit() else None,
        )
        response.close()
        return result
    except requests.RequestException as exc:
        return LinkCheckResult(
            url=url,
            ok=False,
            method="HEAD",
            error=str(exc),
        )


def throttle():
    """Pausa curta entre chamadas a APIs públicas (sobrecarga)."""
    time.sleep(config.CKAN_PAGE_SLEEP_S)
