"""Blueprint do preview v2 (dashboard novo).

Renderiza views com dados reais do banco (coletores, sensores, coletas).
Acesso: login por padrao; ``PREVIEW_PUBLIC=true`` libera sem autenticacao
(apenas para revisao local / demo interna).
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import wraps

from flask import Blueprint, abort, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from banco_dados.services import preview_service as pv
from banco_dados.services import nik_service
from rotas.api.decorators import get_db

preview_bp = Blueprint("preview", __name__, url_prefix="/preview")
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
    return redirect(url_for("preview.landing_preview"))


@preview_bp.route("/home")
@auth_preview
def dashboard_home():
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

        # --- ML: Prospecção geográfica (Módulo 4) ---
        prospects = _obter_marcadores_prospeccao(db)
        show_prospects = request.args.get("prospects", "false").lower() in ("1", "true")

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
            "prospects": prospects,
            "show_prospects": show_prospects,
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


@preview_bp.route("/prospeccao")
@auth_preview
def prospeccao():
    """Página dedicada de prospecção geográfica (Módulo 4)."""
    db = get_db()
    try:
        stats = pv.estatisticas_resumo(db)
        prospects = _obter_marcadores_prospeccao(db)
        sede = pv.coordenadas_sede_mapa()

        # Filtros
        cat_f = request.args.get("categoria", "").strip()
        score_min = request.args.get("score_min", 0, type=float)

        if cat_f:
            prospects = [p for p in prospects if p.get('categoria') == cat_f]
        if score_min > 0:
            prospects = [p for p in prospects if (p.get('score') or 0) >= score_min]

        # Categorias únicas
        categorias_todas = sorted(set(p.get('categoria', '') for p in _obter_marcadores_prospeccao(db) if p.get('categoria')))

        ctx = {
            "current": "prospeccao",
            "total_coletores": stats["total_coletores"],
            "stats": stats,
            "prospects": prospects,
            "sede_mapa": sede,
            "categorias": categorias_todas,
            "filtro_categoria": cat_f,
            "filtro_score_min": score_min,
        }
        return render_template("preview/prospeccao.html", **ctx)
    finally:
        db.close()


@preview_bp.route("/nik")
@auth_preview
def nik():
    db = get_db()
    try:
        stats = pv.estatisticas_resumo(db)
        parceiros = pv.listar_parceiros_select(db)
        historico = nik_service.listar_conversas_ops(
            db,
            current_user.id if current_user.is_authenticated else None,
            limite=12,
        )
    except Exception:
        stats = {"total_coletores": 0}
        parceiros = []
        historico = []
    finally:
        db.close()
    return render_template(
        "preview/nik.html",
        current="nik",
        total_coletores=stats.get("total_coletores", 0),
        stats=stats,
        usuario_nome=_nome_usuario(),
        parceiros=parceiros,
        historico_nik=historico,
    )


@preview_bp.route("/landing")
def landing_preview():
    db = get_db()
    try:
        stats = pv.estatisticas_resumo(db)
    except Exception:
        stats = {"total_coletores": 0}
    finally:
        db.close()
    return render_template(
        "preview/landing_preview.html",
        current="landing_preview",
        total_coletores=stats.get("total_coletores", 0),
        stats=stats,
        usuario_nome=_nome_usuario(),
    )


@preview_bp.route("/assets/nik/<path:filename>")
def nik_assets(filename: str):
    if filename not in _NIK_ASSETS_ALLOWLIST:
        abort(404)
    return send_from_directory(_NIK_ASSETS_DIR, filename)


# ==============================================================
# HELPERS ML (queries leves, com try/except para não quebrar views)
# ==============================================================

def _obter_ranking_ml(db):
    """Retorna ranking do TRONIK Score, ou [] se tabela não existir."""
    try:
        from banco_dados.services.ml_score import obter_ranking
        return obter_ranking(db, limite=50)
    except Exception:
        return []


def _obter_predicoes_map(db):
    """Retorna dict {coletor_id: predicao_dict} com predições ativas."""
    try:
        from banco_dados.modelos import PredicaoEnchimento
        preds = db.query(PredicaoEnchimento).filter(
            PredicaoEnchimento.dados_suficientes.is_(True)
        ).all()
        result = {}
        for p in preds:
            result[p.coletor_id] = {
                'horas_restantes': p.horas_restantes,
                'velocidade': p.velocidade_enchimento,
                'modelo': p.modelo_usado,
            }
        return result
    except Exception:
        return {}


def _obter_marcadores_prospeccao(db):
    """Retorna lista de prospects como dicts para o mapa."""
    try:
        from banco_dados.modelos import LocalProspeccao
        locais = db.query(LocalProspeccao).filter(
            LocalProspeccao.score_prospeccao > 0
        ).order_by(LocalProspeccao.score_prospeccao.desc()).limit(200).all()
        return [
            {
                'id': l.id,
                'nome': l.nome,
                'lat': l.latitude,
                'lng': l.longitude,
                'score': l.score_prospeccao,
                'categoria': l.categoria,
                'cnae': l.cnae_descricao or '',
                'endereco': l.endereco or '',
                'fonte': l.fonte,
                'ja_contatado': l.ja_contatado,
            }
            for l in locais
        ]
    except Exception:
        return []


def _obter_narrativa_parceiro(db, parceiro_id):
    """Retorna última narrativa gerada para um parceiro, ou None."""
    if not parceiro_id:
        return None
    try:
        from banco_dados.services.ml_narrativa import obter_ultima_narrativa
        return obter_ultima_narrativa(db, parceiro_id)
    except Exception:
        return None
