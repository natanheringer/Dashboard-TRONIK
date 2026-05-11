"""
PNCP — API pública de **consultas** (dados abertos), distinta da API de gestão /v1.

Base: https://pncp.gov.br/api/consulta/v1
Manual: https://pncp.gov.br/api/consulta/swaggerui/index.html
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterator, Optional

from jobs.prospeccao import config
from jobs.prospeccao import paths as pathutil
from jobs.prospeccao.http_util import get_json, throttle

logger = logging.getLogger(__name__)


def _consulta_url(path: str) -> str:
    return f"{config.PNCP_CONSULTA_BASE}/{path.lstrip('/')}"


def fetch_contratacoes_publicacao(
    *,
    data_inicial: str,
    data_final: str,
    uf: str = "DF",
    pagina: int = 1,
    codigo_modalidade_contratacao: Optional[int] = None,
    codigo_municipio_ibge: Optional[str] = None,
    tamanho_pagina: int = 20,
) -> dict[str, Any]:
    """
    data_inicial / data_final: AAAAMMDD (manual PNCP consultas).
    Alguns ambientes exigem ``codigoModalidadeContratacao`` ou ``tamanhoPagina``.
    """
    params: dict[str, Any] = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina,
    }
    if uf:
        params["uf"] = uf
    if codigo_modalidade_contratacao is not None:
        params["codigoModalidadeContratacao"] = codigo_modalidade_contratacao
    if codigo_municipio_ibge:
        params["codigoMunicipioIbge"] = codigo_municipio_ibge

    throttle()
    url = _consulta_url("contratacoes/publicacao")
    try:
        return get_json(url, params=params)
    except Exception as first:
        # Fallbacks comuns (documentação / versões de gateway)
        if codigo_modalidade_contratacao is None:
            params2 = dict(params)
            params2["codigoModalidadeContratacao"] = 8
            try:
                return get_json(url, params=params2)
            except Exception:
                pass
        params3 = {k: v for k, v in params.items() if k != "uf"}
        try:
            return get_json(url, params=params3)
        except Exception:
            raise first


def iter_contratacoes_publicacao(
    *,
    data_inicial: str,
    data_final: str,
    uf: str = "DF",
    max_pages: int = 50,
) -> Iterator[dict[str, Any]]:
    """Pagina até max_pages ou até resposta vazia."""
    for p in range(1, max_pages + 1):
        data = fetch_contratacoes_publicacao(
            data_inicial=data_inicial,
            data_final=data_final,
            uf=uf,
            pagina=p,
        )
        # Estrutura comum: lista em "data" ou raiz — normalizar
        items = data.get("data") if isinstance(data, dict) else None
        if items is None and isinstance(data, dict):
            items = data.get("resultado") or data.get("itens")
        if not items:
            break
        yield from items if isinstance(items, list) else [items]


def sync_contratacoes_df_periodo(
    *,
    dias: int = 14,
    max_pages: int = 500,
    uf: str = "DF",
    tamanho_pagina: int = 20,
) -> Path:
    """Últimos ``dias`` no DF; grava JSONL. Usa ``totalPaginas`` da API quando disponível."""
    end = date.today()
    start = end - timedelta(days=dias)
    di = start.strftime("%Y%m%d")
    df = end.strftime("%Y%m%d")

    dirs = pathutil.ensure_raw_layout()
    out = dirs["pncp_consulta"] / f"contratacoes_publicacao_{di}_{df}.jsonl"

    n = 0
    total_pages: Optional[int] = None
    with out.open("w", encoding="utf-8") as fp:
        for p in range(1, max_pages + 1):
            if total_pages is not None and p > total_pages:
                break
            try:
                data = fetch_contratacoes_publicacao(
                    data_inicial=di,
                    data_final=df,
                    uf=uf,
                    pagina=p,
                    tamanho_pagina=tamanho_pagina,
                )
            except Exception as e:
                logger.error("PNCP página %s: %s", p, e)
                break
            if total_pages is None and isinstance(data, dict):
                tp = data.get("totalPaginas")
                if isinstance(tp, int) and tp > 0:
                    total_pages = min(tp, max_pages)
            items = data.get("data") if isinstance(data, dict) else None
            if items is None and isinstance(data, dict):
                items = data.get("resultado") or data.get("itens")
            if not items:
                break
            if not isinstance(items, list):
                items = [items]
            for row in items:
                fp.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
            if len(items) < tamanho_pagina:
                break

    logger.info("PNCP consulta: %s linhas -> %s", n, out)
    pathutil.write_manifest(
        "pncp_contratacoes",
        {"path": str(out), "lines": n, "periodo": [di, df], "uf": uf},
    )
    return out


# --- API de gestão (exige contexto autenticado na maioria dos endpoints) — manter mínimo ---


def dump_pncp_v1_usuarios_query(login: str) -> Path:
    """GET /api/pncp/v1/usuarios?login=… — pode falhar se exigir auth."""
    dirs = pathutil.ensure_raw_layout()
    dest = dirs["pncp"] / f"usuarios_login_{login}.json"
    url = f"{config.PNCP_API_BASE}/usuarios"
    throttle()
    data = get_json(url, params={"login": login})
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    pathutil.write_manifest("pncp_v1_usuarios", {"path": str(dest)})
    return dest
