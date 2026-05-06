"""Blueprint do preview v2 (dashboard novo).

Renderiza views com dados reais do banco (coletores, sensores, coletas).
Acesso: login por padrao; ``PREVIEW_PUBLIC=true`` libera sem autenticacao
(apenas para revisao local / demo interna).
"""

from __future__ import annotations

import os
from functools import wraps

from flask import Blueprint, render_template, request
from flask_login import current_user, login_required

from banco_dados.services import preview_service as pv
from rotas.api.decorators import get_db

preview_bp = Blueprint("preview", __name__, url_prefix="/preview")


def _preview_publico() -> bool:
    return os.getenv("PREVIEW_PUBLIC", "false").strip().lower() in {"1", "true", "yes"}


def auth_preview(view):
    protegido = login_required(view)

    @wraps(view)
    def wrapper(*args, **kwargs):
        if _preview_publico():
            return view(*args, **kwargs)
        return protegido(*args, **kwargs)

    return wrapper


def _nome_usuario() -> str:
    if current_user.is_authenticated:
        return (
            (current_user.nome_completo or current_user.username or current_user.email)
            or "Operador"
        )
    return "Visitante"


@preview_bp.route("/")
@auth_preview
def home():
    db = get_db()
    try:
        stats = pv.estatisticas_resumo(db)
        coletores = pv.coletores_monitoramento(db)
        ctx = {
            "current": "home",
            "total_coletores": stats["total_coletores"],
            "stats": stats,
            "data_longa": pv.data_longa_pt(),
            "usuario_nome": _nome_usuario(),
            "home_subtitulo": pv.texto_home_subtitulo(
                stats, pv.nomes_coletores_atencao(coletores)
            ),
        }
        return render_template("preview/home.html", **ctx)
    finally:
        db.close()


@preview_bp.route("/monitoramento")
@auth_preview
def monitoramento():
    db = get_db()
    try:
        q = (request.args.get("q") or "").strip()
        nivel = (request.args.get("nivel") or "todos").strip().lower()
        page = request.args.get("page", 1, type=int)
        
        if nivel not in {"todos", "crit", "warn", "ok"}:
            nivel = "todos"
        
        # Fetch paginated coletores
        coletores_pagina, total_coletores = pv.coletores_monitoramento_paginado(db, page=page, per_page=50)
        
        # Get full list for stats (reuse para não recarregar)
        stats = pv.estatisticas_resumo(db)
        
        # Build cards with filters
        cards = pv.montar_cards_coletores(coletores_pagina, q, nivel)
        alerta = pv.primeiro_alerta_critico(coletores_pagina)
        recentes = pv.coletas_recentes(db, 8)
        
        # Pagination info
        per_page = 50
        total_pages = (total_coletores + per_page - 1) // per_page
        page = min(page, total_pages) if total_pages > 0 else 1
        
        ctx = {
            "current": "monit",
            "total_coletores": stats["total_coletores"],
            "stats": stats,
            "cards": cards,
            "filtro_q": q,
            "filtro_nivel": nivel,
            "alerta_destaque": alerta,
            "coletas_recentes": recentes,
            "paginacao": {
                "pagina_atual": page,
                "total_paginas": total_pages,
                "total_itens": total_coletores,
                "itens_por_pagina": per_page,
                "tem_proxima": page < total_pages,
                "tem_anterior": page > 1,
            },
        }
        return render_template("preview/monitoramento.html", **ctx)
    finally:
        db.close()


@preview_bp.route("/mapa")
@auth_preview
def mapa():
    db = get_db()
    try:
        stats = pv.estatisticas_resumo(db)
        raw = pv.coletores_geojson(db)
        nivel_f = (request.args.get("nivel") or "todos").strip().lower()
        if nivel_f not in {"todos", "crit", "warn", "ok", "neutral"}:
            nivel_f = "todos"
        parceiro_f = request.args.get("parceiro_id", type=int)
        q_f = (request.args.get("q") or "").strip()
        marcadores = pv.filtrar_marcadores_mapa(raw, nivel_f, parceiro_f, q_f)
        parceiros = pv.listar_parceiros_select(db)
        sede = pv.coordenadas_sede_mapa()

        sel_id = request.args.get("coletor_id", type=int)
        detalhe = pv.detalhe_coletor_mapa(db, sel_id) if sel_id else None

        ctx = {
            "current": "mapa",
            "total_coletores": stats["total_coletores"],
            "stats": stats,
            "marcadores": marcadores,
            "marcadores_total": len(raw),
            "parceiros": parceiros,
            "filtro_mapa_nivel": nivel_f,
            "filtro_mapa_parceiro_id": parceiro_f,
            "filtro_mapa_q": q_f,
            "sede_mapa": sede,
            "detalhe": detalhe,
            "coletor_selecionado_id": detalhe["id"] if detalhe else None,
        }
        return render_template("preview/mapa.html", **ctx)
    finally:
        db.close()


@preview_bp.route("/relatorios")
@auth_preview
def relatorios():
    db = get_db()
    try:
        stats = pv.estatisticas_resumo(db)
        parceiros = pv.listar_parceiros_select(db)
        periodo = pv.resolver_periodo(
            request.args.get("inicio"),
            request.args.get("fim"),
        )
        parceiro_id = request.args.get("parceiro_id", type=int)
        resumo = pv.resumo_relatorios(db, periodo, parceiro_id=parceiro_id)
        ctx = {
            "current": "relatorios",
            "total_coletores": stats["total_coletores"],
            "stats": stats,
            "parceiros": parceiros,
            "periodo": periodo,
            "parceiro_id": parceiro_id,
            "resumo": resumo,
        }
        return render_template("preview/relatorios.html", **ctx)
    finally:
        db.close()


@preview_bp.route("/parceiro")
@auth_preview
def parceiro():
    db = get_db()
    try:
        stats = pv.estatisticas_resumo(db)
        parceiros_rows = pv.parceiros_tabela(db)
        ctx = {
            "current": "parceiro",
            "total_coletores": stats["total_coletores"],
            "stats": stats,
            "parceiros_rows": parceiros_rows,
        }
        return render_template("preview/parceiro.html", **ctx)
    finally:
        db.close()


@preview_bp.route("/gestao")
@auth_preview
def gestao():
    db = get_db()
    try:
        stats = pv.estatisticas_resumo(db)
        ctx = {
            "current": "gestao",
            "total_coletores": stats["total_coletores"],
            "stats": stats,
            "usuario_nome": _nome_usuario(),
        }
        return render_template("preview/gestao.html", **ctx)
    finally:
        db.close()
