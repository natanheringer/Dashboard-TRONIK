"""
Dados mock e helpers para a Nik em desenvolvimento local.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


def _mock_json() -> dict[str, Any]:
    caminho = Path(__file__).resolve().parents[1] / "dados" / "sensores_mock.json"
    with caminho.open(encoding="utf-8") as fh:
        return json.load(fh)


def _coletor_para_card(item: dict[str, Any]) -> dict[str, Any]:
    nivel = float(item.get("nivel_preenchimento", 0))
    if str(item.get("status", "")).lower() == "manutencao":
        classe = "neutral"
        badge = "Manutenção"
    elif nivel >= 95:
        classe = "crit"
        badge = "Crítico"
    elif nivel >= 80:
        classe = "warn"
        badge = "Atenção"
    else:
        classe = "ok"
        badge = "Normal"
    return {
        "id": item["id"],
        "id_fmt": f"#L{int(item['id']):03d}",
        "nome": item["localizacao"],
        "nivel": round(nivel, 1),
        "classe": classe,
        "badge": badge,
        "parceiro": "Mock parceiro local",
        "tipo": "Resíduos eletrônicos",
        "bateria": 72.0 - (int(item["id"]) * 4),
        "ultima_coleta": datetime.fromisoformat(item["ultima_coleta"]).strftime("%d/%m/%Y"),
        "lat": float(item["coordenadas"]["latitude"]),
        "lng": float(item["coordenadas"]["longitude"]),
    }


def mock_coletores() -> list[dict[str, Any]]:
    return [_coletor_para_card(item) for item in _mock_json()["lixeiras"]]


def mock_stats() -> dict[str, Any]:
    coletores = mock_coletores()
    total = len(coletores)
    alertas = sum(1 for c in coletores if c["nivel"] >= 80 and c["classe"] != "neutral")
    criticos = sum(1 for c in coletores if c["nivel"] >= 95)
    media = round(sum(c["nivel"] for c in coletores) / total, 1) if total else 0.0
    return {
        "total_coletores": total,
        "alertas_ativos": alertas,
        "criticos": criticos,
        "nivel_medio": media,
        "coletas_hoje": 3,
        "sensores_bateria_baixa": 1,
    }


def mock_alerta() -> dict[str, Any] | None:
    coletores = sorted(mock_coletores(), key=lambda x: x["nivel"], reverse=True)
    return coletores[0] if coletores else None


def mock_recentes(limite: int = 5) -> list[dict[str, Any]]:
    historico = _mock_json()["historico_coletas"][-limite:]
    indice = {c["id"]: c for c in mock_coletores()}
    saida = []
    for row in reversed(historico):
        c = indice.get(int(row["id_lixeira"]))
        if not c:
            continue
        saida.append(
            {
                "coletor_id": c["id"],
                "id_short": f"L{c['id']:03d}",
                "parceiro": c["parceiro"],
                "local": c["nome"],
                "meta": row.get("tipo_coleta", "programada"),
                "volume": max(0, float(row.get("nivel_antes", 0)) - float(row.get("nivel_depois", 0))),
                "data_fmt": datetime.fromisoformat(row["data_coleta"]).strftime("%d/%m/%Y"),
            }
        )
    return saida


def mock_detalhe_coletor(coletor_id: int) -> dict[str, Any] | None:
    return next((c for c in mock_coletores() if c["id"] == coletor_id), None)


def mock_relatorio() -> dict[str, Any]:
    recentes = _mock_json()["historico_coletas"][-30:]
    total = len(recentes)
    volume = sum(float(r.get("nivel_antes", 0)) - float(r.get("nivel_depois", 0)) for r in recentes)
    parceiros = [{"nome": "Mock parceiro local", "kg": round(volume, 1)}]
    top = sorted(mock_coletores(), key=lambda x: x["nivel"], reverse=True)[:5]
    return {
        "total_coletas": total,
        "volume_kg": round(volume, 1),
        "km_total": round(total * 12.4, 1),
        "lucro_bruto": round(volume * 1.8, 2),
        "custo_combustivel_est": round(total * 8.5, 2),
        "media_kg_coleta": round(volume / total, 1) if total else 0.0,
        "media_km_coleta": 12.4 if total else 0.0,
        "serie_diaria": _serie_diaria_mock(total),
        "serie_max_coletas": 4,
        "top_coletores": [
            {
                "rank": idx + 1,
                "id_fmt": c["id_fmt"].replace("#", ""),
                "nome": c["nome"],
                "sub": c["parceiro"],
                "coletas": max(1, 6 - idx),
            }
            for idx, c in enumerate(top)
        ],
        "volume_por_parceiro": parceiros,
        "volume_parceiro_max_kg": parceiros[0]["kg"] if parceiros else 1.0,
    }


def _serie_diaria_mock(total: int) -> list[dict[str, Any]]:
    hoje = date.today()
    pontos = []
    for offset in range(10):
        d = hoje - timedelta(days=9 - offset)
        pontos.append({"data": d.isoformat(), "count": 1 + (offset % 4)})
    return pontos


def mock_contexto_conversa() -> dict[str, Any]:
    return {
        "modo": "mock",
        "empresa": "Tronik Recicla",
        "estatisticas": mock_stats(),
        "alerta_destaque": mock_alerta(),
        "coletas_recentes": mock_recentes(5),
        "observacao": "Contexto sintético local para desenvolvimento quando a base real não estiver povoada.",
    }
