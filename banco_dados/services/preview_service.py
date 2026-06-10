"""Dados agregados para o dashboard preview v2.

Mantem regras de classificacao alinhadas ao restante do sistema
(LIMIAR 80% em sensores.py; 95% critico na UI).
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from banco_dados.modelos import Coleta, Coletor, Parceiro, Sensor
from banco_dados.utils.cache import obter_cache

# Alinhado a rotas/api/auxiliares (alerta >80) e sensores.LIMIAR_NIVEL_CHEIO
NIVEL_ATENCAO = 80.0
NIVEL_CRITICO = 95.0
BATERIA_BAIXA = 20.0

# Brasilia fallback quando lat/lng nao cadastrados
_FALLBACK_LAT = -15.793889
_FALLBACK_LNG = -47.882778


def classificacao_ui(nivel: float, status: str | None) -> str:
    st = (status or "OK").upper()
    if st in {"QUEBRADA", "MANUTENCAO", "MANUTENÇÃO"}:
        return "neutral"
    if nivel >= NIVEL_CRITICO:
        return "crit"
    if nivel >= NIVEL_ATENCAO:
        return "warn"
    return "ok"


def rotulo_badge(classe: str) -> str:
    return {
        "crit": "Crítico",
        "warn": "Atenção",
        "ok": "Normal",
        "neutral": "Manutenção",
    }.get(classe, "Normal")


def empty_state(titulo: str, descricao: str, sugestao: str = "") -> dict[str, Any]:
    """Helper para criar estrutura de empty state consistente."""
    return {
        "vazio": True,
        "titulo": titulo,
        "descricao": descricao,
        "sugestao": sugestao,
    }


def _media_bateria(sensores: Sequence[Sensor]) -> float | None:
    if not sensores:
        return None
    return sum(s.bateria for s in sensores) / len(sensores)


def _fmt_data(dt: datetime | None) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d/%m/%Y")


def _coords_mapa(c: Coletor) -> tuple[float, float]:
    if c.latitude is not None and c.longitude is not None:
        return float(c.latitude), float(c.longitude)
    h = hashlib.md5(str(c.id).encode(), usedforsecurity=False).hexdigest()
    dlat = (int(h[:4], 16) / 65535 - 0.5) * 0.12
    dlng = (int(h[4:8], 16) / 65535 - 0.5) * 0.12
    return _FALLBACK_LAT + dlat, _FALLBACK_LNG + dlng


def resumo_coletores_operacional(db: Session) -> dict[str, Any]:
    from banco_dados.services.coletor_service import resumo_operacional

    return resumo_operacional(db)


def resumo_prospeccao(db: Session) -> dict[str, Any]:
    """Resumo leve da fila REE para o hub do preview (sem carregar candidatos)."""
    out: dict[str, Any] = {
        "modelo_ativo": False,
        "versao": None,
        "algoritmo": None,
        "total_scores": 0,
        "alta_prioridade": 0,
    }
    try:
        from banco_dados.modelos import ModeloProspeccao, ScoreProspeccao

        model = (
            db.query(ModeloProspeccao)
            .filter(ModeloProspeccao.ativo.is_(True))
            .order_by(ModeloProspeccao.treinado_em.desc())
            .first()
        )
        if not model:
            return out
        out["modelo_ativo"] = True
        out["versao"] = model.versao
        out["algoritmo"] = model.algoritmo
        q = db.query(ScoreProspeccao).filter(ScoreProspeccao.modelo_id == model.id)
        out["total_scores"] = q.count()
        out["alta_prioridade"] = q.filter(ScoreProspeccao.prioridade == "alta").count()
    except Exception:
        pass
    return out


def estatisticas_resumo(db: Session) -> dict[str, Any]:
    cache = obter_cache()

    def calcular() -> dict[str, Any]:
        total = db.query(func.count(Coletor.id)).scalar()
        hoje = date.today()
        inicio_hoje = datetime.combine(hoje, datetime.min.time())
        fim_hoje = inicio_hoje + timedelta(days=1)
        coletas_hoje = (
            db.query(Coleta)
            .filter(Coleta.data_hora >= inicio_hoje, Coleta.data_hora < fim_hoje)
            .count()
        )

        alertas = db.query(func.count(Coletor.id)).filter(
            Coletor.nivel_preenchimento >= NIVEL_ATENCAO
        ).scalar()
        criticos = db.query(func.count(Coletor.id)).filter(
            Coletor.nivel_preenchimento >= NIVEL_CRITICO
        ).scalar()

        nivel_medio_raw = db.query(func.avg(Coletor.nivel_preenchimento)).scalar()
        nivel_medio = round(float(nivel_medio_raw or 0), 1) if total else 0.0
        bateria_baixa = db.query(func.count(Sensor.id)).filter(
            Sensor.bateria < BATERIA_BAIXA
        ).scalar()

        return {
            "total_coletores": total,
            "alertas_ativos": alertas,
            "criticos": criticos,
            "nivel_medio": nivel_medio,
            "coletas_hoje": coletas_hoje,
            "sensores_bateria_baixa": bateria_baixa,
        }

    return cache.obter_ou_calcular(
        "preview:estatisticas_resumo", calcular, ttl_segundos=60
    )


def _media_bateria_por_coletor(db: Session) -> dict[int, float]:
    """Média de bateria por coletor em uma query (evita joinedload de sensores no mapa)."""
    rows = (
        db.query(Sensor.coletor_id, func.avg(Sensor.bateria))
        .group_by(Sensor.coletor_id)
        .all()
    )
    return {
        int(cid): round(float(avg), 1)
        for cid, avg in rows
        if cid is not None and avg is not None
    }


def coletores_para_mapa(db: Session) -> list[Coletor]:
    """Lista leve para marcadores: sem eager load de sensores."""
    return (
        db.query(Coletor)
        .options(
            joinedload(Coletor.parceiro),
            joinedload(Coletor.tipo_material),
        )
        .order_by(Coletor.id)
        .all()
    )


def coletores_monitoramento(db: Session) -> list[Coletor]:
    return (
        db.query(Coletor)
        .options(
            joinedload(Coletor.parceiro),
            joinedload(Coletor.tipo_material),
            joinedload(Coletor.sensores),
        )
        .order_by(Coletor.nivel_preenchimento.desc().nullslast(), Coletor.id)
        .all()
    )


def coletores_monitoramento_paginado(
    db: Session, page: int = 1, per_page: int = 50
) -> tuple[list[Coletor], int]:
    """Retorna coletores com paginação e total de registros.

    Args:
        db: SQLAlchemy session
        page: Número da página (1-indexed)
        per_page: Itens por página

    Returns:
        Tupla (coletores, total_count)
    """
    page = max(1, page)
    per_page = max(1, min(per_page, 200))  # Limitar a 200 por razões de performance

    query = db.query(Coletor).options(
        joinedload(Coletor.parceiro),
        joinedload(Coletor.tipo_material),
        joinedload(Coletor.sensores),
    )

    total = query.count()
    coletores = (
        query
        .order_by(Coletor.nivel_preenchimento.desc().nullslast(), Coletor.id)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return coletores, total


def montar_cards_coletores(
    coletores: Sequence[Coletor],
    filtro_texto: str = "",
    filtro_nivel: str = "todos",
) -> list[dict[str, Any]]:
    q = filtro_texto.strip().lower()
    out: list[dict[str, Any]] = []
    for c in coletores:
        cls = classificacao_ui(float(c.nivel_preenchimento or 0), c.status)
        if filtro_nivel == "crit" and cls != "crit":
            continue
        if filtro_nivel == "warn" and cls != "warn":
            continue
        if filtro_nivel == "ok" and cls not in {"ok", "neutral"}:
            continue
        if q:
            pid = f"l{c.id:03d}"
            blob = " ".join(
                [
                    (c.localizacao or "").lower(),
                    (c.parceiro.nome if c.parceiro else "") or "",
                    str(c.id),
                    pid,
                ]
            )
            if q not in blob and q.replace("#", "") not in blob:
                continue

        bat = _media_bateria(c.sensores or [])
        out.append(
            {
                "id": c.id,
                "id_fmt": f"#L{c.id:03d}",
                "nome": c.localizacao,
                "parceiro": c.parceiro.nome if c.parceiro else "—",
                "tipo_material": c.tipo_material.nome if c.tipo_material else "—",
                "nivel": round(float(c.nivel_preenchimento or 0), 1),
                "status": c.status or "OK",
                "classe": cls,
                "badge": rotulo_badge(cls),
                "bateria": round(bat, 1) if bat is not None else None,
                "ultima_coleta_fmt": _fmt_data(c.ultima_coleta),
            }
        )
    return out


def primeiro_alerta_critico(coletores: Sequence[Coletor]) -> dict[str, Any] | None:
    for c in sorted(
        coletores,
        key=lambda x: float(x.nivel_preenchimento or 0),
        reverse=True,
    ):
        if float(c.nivel_preenchimento or 0) >= NIVEL_CRITICO and (
            c.status or "OK"
        ).upper() not in {"QUEBRADA"}:
            return {
                "id": c.id,
                "id_fmt": f"L{c.id:03d}",
                "nome": c.localizacao,
                "nivel": round(float(c.nivel_preenchimento or 0), 1),
            }
    for c in coletores:
        if float(c.nivel_preenchimento or 0) >= NIVEL_ATENCAO:
            return {
                "id": c.id,
                "id_fmt": f"L{c.id:03d}",
                "nome": c.localizacao,
                "nivel": round(float(c.nivel_preenchimento or 0), 1),
            }
    return None


def coletas_recentes(db: Session, limite: int = 8) -> list[dict[str, Any]]:
    rows = (
        db.query(Coleta)
        .options(
            joinedload(Coleta.coletor),
            joinedload(Coleta.parceiro),
        )
        .order_by(Coleta.data_hora.desc().nullslast())
        .limit(limite)
        .all()
    )
    out = []
    for col in rows:
        loc = col.coletor.localizacao if col.coletor else "—"
        parc = col.parceiro.nome if col.parceiro else "—"
        vol = col.volume_estimado
        km = col.km_percorrido
        tipo = col.tipo_operacao or "—"
        meta = f"{km:.1f} km · {tipo.lower()}" if km is not None else tipo.lower()
        out.append(
            {
                "coletor_id": col.coletor_id,
                "id_short": f"L{col.coletor_id:03d}",
                "parceiro": parc,
                "local": loc[:28] + "…" if len(loc) > 28 else loc,
                "meta": meta,
                "volume": int(vol) if vol is not None else "—",
                "data_fmt": _fmt_data(col.data_hora),
            }
        )
    return out


def coletores_geojson(db: Session) -> list[dict[str, Any]]:
    cache = obter_cache()

    def calcular() -> list[dict[str, Any]]:
        coletores = coletores_para_mapa(db)
        baterias = _media_bateria_por_coletor(db)
        feats: list[dict[str, Any]] = []
        for c in coletores:
            lat, lng = _coords_mapa(c)
            cls = classificacao_ui(float(c.nivel_preenchimento or 0), c.status)
            feats.append(
                {
                    "id": c.id,
                    "lat": lat,
                    "lng": lng,
                    "label": c.localizacao,
                    "nivel": round(float(c.nivel_preenchimento or 0), 1),
                    "classe": cls,
                    "parceiro_id": c.parceiro_id,
                    "parceiro": c.parceiro.nome if c.parceiro else "—",
                    "tipo": c.tipo_material.nome if c.tipo_material else "—",
                    "bateria": baterias.get(c.id),
                    "ultima_coleta": _fmt_data(c.ultima_coleta),
                }
            )
        return feats

    return cache.obter_ou_calcular(
        "preview:coletores_geojson", calcular, ttl_segundos=20
    )


def filtrar_marcadores_mapa(
    marcadores: list[dict[str, Any]],
    nivel: str | None,
    parceiro_id: int | None,
    q: str | None,
) -> list[dict[str, Any]]:
    """Filtros alinhados à UI do mapa preview (query string)."""
    n = (nivel or "todos").strip().lower()
    if n not in {"todos", "crit", "warn", "ok", "neutral"}:
        n = "todos"
    qn = (q or "").strip().lower()
    out: list[dict[str, Any]] = []
    for m in marcadores:
        if n != "todos" and m.get("classe") != n:
            continue
        if parceiro_id is not None and m.get("parceiro_id") != parceiro_id:
            continue
        if qn:
            pid = m.get("id")
            lid = f"L{int(pid):03d}" if pid is not None else ""
            blob = " ".join(
                [
                    str(pid or ""),
                    lid,
                    str(m.get("label") or ""),
                    str(m.get("parceiro") or ""),
                ]
            ).lower()
            if qn not in blob:
                continue
        out.append(m)
    return out


def coordenadas_sede_mapa() -> dict[str, Any] | None:
    """Marcador opcional da sede (env). Sem variáveis, retorna None."""
    lat_s = (os.getenv("TRONIK_SEDE_LAT") or "").strip()
    lng_s = (os.getenv("TRONIK_SEDE_LNG") or "").strip()
    if not lat_s or not lng_s:
        return None
    try:
        lat = float(lat_s.replace(",", "."))
        lng = float(lng_s.replace(",", "."))
    except ValueError:
        return None
    label = (os.getenv("TRONIK_SEDE_LABEL") or "Sede Tronik").strip() or "Sede Tronik"
    return {"lat": lat, "lng": lng, "label": label}


def detalhe_coletor_mapa(db: Session, coletor_id: int) -> dict[str, Any] | None:
    c = (
        db.query(Coletor)
        .options(
            joinedload(Coletor.parceiro),
            joinedload(Coletor.tipo_material),
            joinedload(Coletor.sensores),
        )
        .filter(Coletor.id == coletor_id)
        .first()
    )
    if not c:
        return None
    lat, lng = _coords_mapa(c)
    cls = classificacao_ui(float(c.nivel_preenchimento or 0), c.status)
    bat = _media_bateria(c.sensores or [])
    return {
        "id": c.id,
        "id_fmt": f"#L{c.id:03d}",
        "nome": c.localizacao,
        "nivel": round(float(c.nivel_preenchimento or 0), 1),
        "classe": cls,
        "badge": rotulo_badge(cls),
        "parceiro": c.parceiro.nome if c.parceiro else "—",
        "tipo": c.tipo_material.nome if c.tipo_material else "—",
        "bateria": round(bat, 1) if bat is not None else None,
        "ultima_coleta": _fmt_data(c.ultima_coleta),
        "lat": lat,
        "lng": lng,
    }


@dataclass
class PeriodoRelatorio:
    inicio: date
    fim: date


def resolver_periodo(
    inicio_raw: str | None,
    fim_raw: str | None,
    dias_padrao: int = 30,
) -> PeriodoRelatorio:
    fim = date.today()
    if inicio_raw and fim_raw:
        try:
            ini = date.fromisoformat(inicio_raw)
            fi = date.fromisoformat(fim_raw)
            if ini <= fi:
                return PeriodoRelatorio(ini, fi)
        except ValueError:
            pass
    ini = fim - timedelta(days=dias_padrao - 1)
    return PeriodoRelatorio(ini, fim)


def resumo_relatorios(
    db: Session,
    periodo: PeriodoRelatorio,
    parceiro_id: int | None = None,
) -> dict[str, Any]:
    """Agregações SQL — evita carregar todas as coletas do período em memória."""
    from banco_dados.modelos import Coleta, Coletor, Parceiro

    t0 = datetime.combine(periodo.inicio, datetime.min.time())
    t1 = datetime.combine(periodo.fim + timedelta(days=1), datetime.min.time())
    filtros = [Coleta.data_hora >= t0, Coleta.data_hora < t1]
    if parceiro_id:
        filtros.append(Coleta.parceiro_id == parceiro_id)

    n = db.query(func.count(Coleta.id)).filter(*filtros).scalar() or 0
    vol = float(
        db.query(func.coalesce(func.sum(Coleta.volume_estimado), 0.0))
        .filter(*filtros)
        .scalar()
        or 0
    )
    km = float(
        db.query(func.coalesce(func.sum(Coleta.km_percorrido), 0.0))
        .filter(*filtros)
        .scalar()
        or 0
    )
    combustivel = float(
        db.query(
            func.coalesce(
                func.sum(
                    Coleta.km_percorrido * Coleta.preco_combustivel / 4.0
                ),
                0.0,
            )
        )
        .filter(
            *filtros,
            Coleta.km_percorrido.isnot(None),
            Coleta.preco_combustivel.isnot(None),
        )
        .scalar()
        or 0
    )
    lucro_bruto = float(
        db.query(
            func.coalesce(
                func.sum(Coleta.lucro_por_kg * Coleta.volume_estimado),
                0.0,
            )
        )
        .filter(*filtros)
        .scalar()
        or 0
    )

    serie_rows = (
        db.query(func.date(Coleta.data_hora).label("dia"), func.count(Coleta.id))
        .filter(*filtros)
        .group_by(func.date(Coleta.data_hora))
        .order_by(func.date(Coleta.data_hora))
        .all()
    )
    serie = [
        {"data": (d.isoformat() if hasattr(d, "isoformat") else str(d)), "count": int(cnt)}
        for d, cnt in serie_rows
    ]

    top_rows = (
        db.query(
            Coleta.coletor_id,
            func.count(Coleta.id).label("cnt"),
            Coletor.localizacao,
            Parceiro.nome,
        )
        .join(Coletor, Coleta.coletor_id == Coletor.id)
        .outerjoin(Parceiro, Coleta.parceiro_id == Parceiro.id)
        .filter(*filtros)
        .group_by(Coleta.coletor_id, Coletor.localizacao, Parceiro.nome)
        .order_by(func.count(Coleta.id).desc())
        .limit(5)
        .all()
    )
    top_list = []
    for rank, (cid, cnt, loc, parc_nome) in enumerate(top_rows, start=1):
        loc_s = loc or f"#{cid}"
        top_list.append(
            {
                "rank": rank,
                "id_fmt": f"L{cid:03d}",
                "nome": loc_s[:40],
                "sub": parc_nome or "—",
                "coletas": int(cnt),
            }
        )

    vol_parceiro_rows = (
        db.query(
            func.coalesce(Parceiro.nome, "Sem parceiro"),
            func.coalesce(func.sum(Coleta.volume_estimado), 0.0),
        )
        .outerjoin(Parceiro, Coleta.parceiro_id == Parceiro.id)
        .filter(*filtros)
        .group_by(Parceiro.nome)
        .order_by(func.sum(Coleta.volume_estimado).desc())
        .limit(6)
        .all()
    )
    parceiro_barras = [(nome, float(kg)) for nome, kg in vol_parceiro_rows]

    max_dia = max((s["count"] for s in serie), default=0) or 1
    kg_max = max((b[1] for b in parceiro_barras), default=0.0) or 1.0

    return {
        "total_coletas": n,
        "volume_kg": round(vol, 1),
        "km_total": round(km, 1),
        "lucro_bruto": round(lucro_bruto, 2),
        "custo_combustivel_est": round(combustivel, 2),
        "media_kg_coleta": round(vol / n, 1) if n else 0.0,
        "media_km_coleta": round(km / n, 1) if n else 0.0,
        "serie_diaria": serie,
        "serie_max_coletas": max_dia,
        "top_coletores": top_list,
        "volume_por_parceiro": [
            {"nome": nome, "kg": round(kg, 1)} for nome, kg in parceiro_barras
        ],
        "volume_parceiro_max_kg": round(kg_max, 1) if kg_max else 1.0,
    }


def parceiros_tabela(db: Session) -> list[dict[str, Any]]:
    contagem = dict(
        db.query(Coletor.parceiro_id, func.count(Coletor.id))
        .group_by(Coletor.parceiro_id)
        .all()
    )
    parceiros = db.query(Parceiro).order_by(Parceiro.nome).all()
    return [
        {
            "id": p.id,
            "nome": p.nome,
            "ativo": p.ativo,
            "n_coletores": int(contagem.get(p.id, 0)),
        }
        for p in parceiros
    ]


def listar_parceiros_select(db: Session) -> list[dict[str, Any]]:
    cache = obter_cache()

    def calcular() -> list[dict[str, Any]]:
        rows = (
            db.query(Parceiro)
            .filter(Parceiro.ativo.is_(True))
            .order_by(Parceiro.nome)
            .all()
        )
        return [{"id": p.id, "nome": p.nome} for p in rows]

    return cache.obter_ou_calcular(
        "preview:parceiros_select", calcular, ttl_segundos=600
    )


def texto_home_subtitulo(stats: dict[str, Any], nomes_atencao: list[str]) -> str:
    total = stats["total_coletores"]
    alertas = stats["alertas_ativos"]
    if total == 0:
        return "Cadastre coletores e sensores para acompanhar a operação aqui."
    if alertas == 0:
        return (
            f"Todos os {total} coletores estão abaixo de {int(NIVEL_ATENCAO)}% de preenchimento "
            "ou em manutenção planejada. Nível médio "
            f"{stats['nivel_medio']}%."
        )
    amostra = ", ".join(nomes_atencao[:2])
    extra = " e outros" if len(nomes_atencao) > 2 else ""
    return (
        f"{alertas} coletor(es) com nível ≥ {int(NIVEL_ATENCAO)}%: {amostra}{extra}. "
        f"Média geral {stats['nivel_medio']}% · {stats['coletas_hoje']} coleta(s) hoje."
    )


_MESES_PT = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def data_longa_pt(hoje: date | None = None) -> str:
    d = hoje or date.today()
    dias = (
        "Segunda-feira",
        "Terça-feira",
        "Quarta-feira",
        "Quinta-feira",
        "Sexta-feira",
        "Sábado",
        "Domingo",
    )
    return f"{dias[d.weekday()]}, {d.day} de {_MESES_PT[d.month - 1]} de {d.year}"


def coletores_nomes_atencao(db: Session, limite: int = 4) -> list[str]:
    """Top N coletores em atenção (>=80%) sem carregar a tabela inteira."""
    rows = (
        db.query(Coletor.localizacao)
        .filter(
            Coletor.nivel_preenchimento >= NIVEL_ATENCAO,
            func.coalesce(Coletor.status, "OK") != "QUEBRADA",
        )
        .order_by(Coletor.nivel_preenchimento.desc())
        .limit(limite)
        .all()
    )
    return [loc for (loc,) in rows if loc]


def nomes_coletores_atencao(coletores: Sequence[Coletor], limite: int = 4) -> list[str]:
    cands = [
        c
        for c in coletores
        if float(c.nivel_preenchimento or 0) >= NIVEL_ATENCAO
        and (c.status or "OK").upper() not in {"QUEBRADA"}
    ]
    cands.sort(key=lambda x: float(x.nivel_preenchimento or 0), reverse=True)
    return [c.localizacao for c in cands[:limite]]
