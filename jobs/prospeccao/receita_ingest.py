"""CNPJ dados abertos — URLs explícitas ou descoberta por bases candidatas."""

from __future__ import annotations

import logging
from pathlib import Path

from jobs.prospeccao import config, paths as pathutil
from jobs.prospeccao.http_util import download_url_to_path, request_timeout, session

logger = logging.getLogger(__name__)

# Ficheiros típicos do layout aberto (nomes podem variar; ajustável)
DEFAULT_ZIP_NAMES_EMPRESAS = [f"Empresas{i}.zip" for i in range(10)]
DEFAULT_ZIP_NAMES_ESTABELECIMENTOS = [f"Estabelecimentos{i}.zip" for i in range(10)]
DEFAULT_ZIP_NAMES_LOOKUPS = ["Municipios.zip", "Cnaes.zip", "Naturezas.zip", "Motivos.zip", "Qualificacoes.zip"]


def _bases() -> list[str]:
    raw = (config.RECEITA_CNPJ_BASE_URLS or "").strip()
    return [b.strip().rstrip("/") + "/" for b in raw.split(",") if b.strip()]


def discover_working_base(
    probe_files: list[str] | None = None,
) -> str | None:
    """Faz HEAD a Empresas0.zip (ou primeiro probe) em cada base até 200 OK."""
    probes = probe_files or ["Empresas0.zip", "Estabelecimentos0.zip", "Cnaes.zip"]
    for base in _bases():
        for probe in probes:
            url = base + probe
            try:
                r = session().head(url, allow_redirects=True, timeout=request_timeout())
                ok = r.ok
                r.close()
                if ok:
                    logger.info("Receita: base OK %s (probe %s)", base, probe)
                    return base.rstrip("/") + "/"
            except Exception as e:
                logger.debug("Probe falhou %s: %s", url, e)
    return None


def download_receita_zips_from_env() -> list[Path]:
    """TRONIK_RECEITA_CNPJ_ZIP_URLS — lista separada por vírgulas."""
    raw = (config.RECEITA_CNPJ_ZIP_URLS or "").strip()
    if not raw:
        raise RuntimeError(
            "Defina TRONIK_RECEITA_CNPJ_ZIP_URLS ou use: "
            "python -m jobs.prospeccao receita-auto --tipo estabelecimentos --max 2"
        )
    dirs = pathutil.ensure_raw_layout()
    out_dir = dirs["receita"]
    saved: list[Path] = []
    for i, url in enumerate(u.strip() for u in raw.split(",") if u.strip()):
        name = url.rstrip("/").split("/")[-1] or f"receita_{i}.zip"
        dest = out_dir / name
        logger.info("Receita: %s -> %s", url[:120], dest)
        download_url_to_path(url, dest, resume=True, skip_if_same_size=True)
        saved.append(dest)
    pathutil.write_manifest("receita_cnpj", {"urls": raw, "files": [str(p) for p in saved]})
    return saved


def download_receita_auto(
    *,
    tipo: str = "estabelecimentos",
    max_files: int = 2,
    probe_only: bool = False,
) -> list[Path]:
    """
    Descobre base oficial e descarrega os primeiros N ZIPs do tipo.
    tipo: empresas | estabelecimentos
    """
    base = discover_working_base()
    if not base:
        raise RuntimeError(
            "Não foi possível detetar base da Receita. "
            "Defina TRONIK_RECEITA_CNPJ_BASE_URLS ou TRONIK_RECEITA_CNPJ_ZIP_URLS."
        )
    if probe_only:
        logger.info("Probe OK, base: %s", base)
        return []

    if tipo.lower() == "empresas":
        names = DEFAULT_ZIP_NAMES_EMPRESAS
    elif tipo.lower() == "lookups":
        names = DEFAULT_ZIP_NAMES_LOOKUPS
    else:
        names = DEFAULT_ZIP_NAMES_ESTABELECIMENTOS
    dirs = pathutil.ensure_raw_layout()
    out_dir = dirs["receita"]
    saved: list[Path] = []
    for name in names[:max_files]:
        url = base + name
        dest = out_dir / name
        logger.info("Receita auto: %s", url[:160])
        download_url_to_path(url, dest, resume=True, skip_if_same_size=True)
        saved.append(dest)
    pathutil.write_manifest(
        "receita_auto",
        {"base": base, "tipo": tipo, "files": [str(p) for p in saved]},
    )
    return saved
