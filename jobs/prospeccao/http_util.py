"""HTTP robusto: Session com Retry (urllib3), downloads com retomada parcial."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any, BinaryIO, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from jobs.prospeccao import config

logger = logging.getLogger(__name__)

_SESSION: requests.Session | None = None


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
    params: Optional[dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> Any:
    to = timeout if timeout is not None else config.HTTP_TIMEOUT_S
    r = session().get(url, params=params, timeout=to)
    r.raise_for_status()
    return r.json()


def post_json(url: str, *, json_body: Optional[dict[str, Any]] = None) -> Any:
    r = session().post(url, json=json_body or {}, timeout=config.HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json()


@dataclass
class DownloadResult:
    path: str
    bytes_written: int
    skipped: bool
    truncated: bool
    sha256: Optional[str] = None


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
    max_bytes: Optional[int] = None,
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
    with session().get(
        url,
        stream=True,
        timeout=config.HTTP_TIMEOUT_S,
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
            if pause_s > 0:
                time.sleep(pause_s)
    return written


def download_url_to_path(
    url: str,
    dest_path: Any,
    *,
    max_bytes: Optional[int] = None,
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
    cl: Optional[str] = None
    ar = False
    try:
        head = session().head(url, allow_redirects=True, timeout=config.HTTP_TIMEOUT_S)
        if head.ok:
            cl = head.headers.get("Content-Length")
            ar = (head.headers.get("Accept-Ranges") or "").lower() == "bytes"
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


def throttle():
    """Pausa curta entre chamadas a APIs públicas (sobrecarga)."""
    time.sleep(config.CKAN_PAGE_SLEEP_S)
