"""Blueprint do preview v2 (dashboard novo).

Renderiza views com dados reais do banco (coletores, sensores, coletas).
Acesso: login por padrao; ``PREVIEW_PUBLIC=true`` libera sem autenticacao
(apenas para revisao local / demo interna).
"""

from __future__ import annotations

import os
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required

from banco_dados.services import nik_service, preview_service as pv
from rotas.api._limiter import limiter
from rotas.api.decorators import get_db

preview_bp = Blueprint("preview", __name__, url_prefix="/preview")
limiter.exempt(preview_bp)
_NIK_ASSETS_DIR = Path(__file__).resolve().parents[1] / "nik_bot"
_NIK_ASSETS_ALLOWLIST = {
    "Nik_normal.svg",
    "Nik_escrevendo.svg",
    "Nik_encontra_resposta_no_bg.svg",
    "nik_duvida_nobg.svg",
    "tronik_logo_only_nobg.svg",
    "nik-acenando-lbadev.webm",
    "nik-pensando-lbadev.webm",
    "nik-encontra-resposta-lbadev.webm",
    "nik_duvida-lbadev.webm",
    "nik_cannon.png",
    "nik_cannon_1.png",
    "nik_cannon_animated_bg.webm",
    "nik_cannon_animated_bg.mp4",
    "nik_cannon_animated_nobg.webm",
    "operation_tronik.png",
}


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


def admin_preview(view):
    """Restringe acesso apenas para usuários administradores."""
    protegido = auth_preview(view)

    @wraps(view)
    def wrapper(*args, **kwargs):
        if _preview_publico():
            return view(*args, **kwargs)
        if current_user.is_authenticated and not current_user.admin:
            abort(403)
        return protegido(*args, **kwargs)

    return wrapper


def _nome_usuario() -> str:
    if current_user.is_authenticated:
        return (
            (current_user.nome_completo or current_user.username or current_user.email)
            or "Operador"
        )
    return "Visitante"


@preview_bp.route("/solicitar-coletor", methods=["POST"])
def solicitar_coletor():
    """Rota pública para receber solicitações de novos coletores da landing."""
    from flask import jsonify

    from banco_dados.modelos import SolicitacaoColetor

    try:
        dados = request.get_json()
        if not dados:
            return jsonify({"ok": False, "erro": "Nenhum dado recebido"}), 400

        nome = str(dados.get("nome", "")).strip()
        email = str(dados.get("email", "")).strip()
        localizacao = str(dados.get("localizacao", "")).strip()

        if not nome or not email or not localizacao:
            return jsonify({"ok": False, "erro": "Nome, e-mail e localização são obrigatórios"}), 400

        db = get_db()
        try:
            nova_solicitacao = SolicitacaoColetor(
                nome=nome,
                email=email,
                empresa=str(dados.get("empresa", "")).strip(),
                localizacao=localizacao,
                mensagem=str(dados.get("mensagem", "")).strip()[:1000]
            )
            db.add(nova_solicitacao)
            db.commit()
            return jsonify({"ok": True})
        finally:
            db.close()
    except Exception as e:
        import logging
        logging.error(f"Erro ao salvar solicitação: {e}")
        return jsonify({"ok": False, "erro": "Erro interno no servidor"}), 500


@preview_bp.route("/")
@auth_preview
def home():
    if current_user.is_authenticated:
        if current_user.admin:
            return redirect(url_for("preview.dashboard_home"))
        return redirect(url_for("preview.parceiro"))
    return redirect(url_for("preview.landing_preview"))


@preview_bp.route("/home")
@auth_preview
def dashboard_home():
    # Se não for admin, direciona para o portal de parceiro
    if current_user.is_authenticated and not current_user.admin:
        return redirect(url_for("preview.parceiro"))

    db = get_db()
    try:
        stats = pv.estatisticas_resumo(db)
        coletores = pv.coletores_monitoramento(db)
        ctx = {
            "current": "home",
            "total_coletores": stats["total_coletores"],
            "resumo_coletores": pv.resumo_coletores_operacional(db),
            "resumo_prospeccao": pv.resumo_prospeccao(db),
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
@admin_preview
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

        # --- ML: TRONIK Score ranking (Módulo 2) ---
        ranking_ml = _obter_ranking_ml(db)

        # --- ML: Predições rápidas (Módulo 1) ---
        predicoes_map = _obter_predicoes_map(db)

        # Enriquecer cards com dados ML
        for card in cards:
            cid = card.get('id')
            if cid in predicoes_map:
                card['ml_predicao'] = predicoes_map[cid]
            # Score do ranking
            for r in ranking_ml:
                if r.get('coletor_id') == cid:
                    card['ml_score'] = r.get('score')
                    break

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
            "ranking_ml": ranking_ml[:5],
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
@admin_preview
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

        # Candidato de prospecção focado (vindo de /preview/prospeccao via "Ver mapa")
        prosp_lat = request.args.get("prosp_lat", type=float)
        prosp_lon = request.args.get("prosp_lon", type=float)
        prosp_label = (request.args.get("prosp_label") or "").strip()[:120]
        prosp_pin = None
        if prosp_lat is not None and prosp_lon is not None:
            prosp_pin = {"lat": prosp_lat, "lon": prosp_lon, "label": prosp_label or "Candidato REE"}

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
            "prosp_pin": prosp_pin,
        }
        return render_template("preview/mapa.html", **ctx)
    finally:
        db.close()


@preview_bp.route("/relatorios")
@admin_preview
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
        # Parceiros: se for admin, vê todos. Se for parceiro, vê só o dele.
        parceiros_rows = pv.parceiros_tabela(db)
        if current_user.is_authenticated and not current_user.admin and getattr(current_user, 'parceiro_id', None):
            parceiros_rows = [p for p in parceiros_rows if p['id'] == current_user.parceiro_id]

        # --- ML: Narrativa de impacto (Módulo 3) ---
        for p in parceiros_rows:
            p['narrativa'] = _obter_narrativa_parceiro(db, p.get('id'))

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
@preview_bp.route("/prospeccao")
@admin_preview
def prospeccao():
    db = get_db()
    try:
        stats = pv.estatisticas_resumo(db)
        ctx = {
            "current": "prospeccao",
            "total_coletores": stats["total_coletores"],
            "stats": stats,
            "usuario_nome": _nome_usuario(),
        }
        return render_template("preview/prospeccao.html", **ctx)
    finally:
        db.close()


def _ctx_admin_shell(current: str) -> dict:
    db = get_db()
    try:
        stats = pv.estatisticas_resumo(db)
        return {
            "current": current,
            "total_coletores": stats["total_coletores"],
            "stats": stats,
            "usuario_nome": _nome_usuario(),
        }
    finally:
        db.close()


@preview_bp.route("/crm")
@admin_preview
def crm():
    return render_template("preview/crm.html", **_ctx_admin_shell("crm"))


@preview_bp.route("/comercial")
@admin_preview
def comercial():
    return render_template("preview/comercial.html", **_ctx_admin_shell("comercial"))


@preview_bp.route("/contratos")
@admin_preview
def contratos():
    return render_template("preview/contratos.html", **_ctx_admin_shell("contratos"))


@preview_bp.route("/gestao")
@admin_preview
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
