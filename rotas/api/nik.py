"""
Endpoints da Nik.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from banco_dados.services import nik_service as nik
from rotas.api.decorators import get_db

nik_bp = Blueprint("nik", __name__, url_prefix="/nik")


@nik_bp.route("/ops/resumo")
@login_required
def ops_resumo():
    db = get_db()
    try:
        return jsonify(nik.resumo_operacional(db))
    finally:
        db.close()


@nik_bp.route("/ops/coletor/<int:coletor_id>")
@login_required
def ops_coletor(coletor_id: int):
    db = get_db()
    try:
        return jsonify(nik.analise_coletor(db, coletor_id))
    finally:
        db.close()


@nik_bp.route("/ops/alerta")
@login_required
def ops_alerta():
    db = get_db()
    try:
        return jsonify(nik.analise_alerta(db))
    finally:
        db.close()


@nik_bp.route("/ops/relatorio")
@login_required
def ops_relatorio():
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    parceiro_id = request.args.get("parceiro_id", type=int)
    db = get_db()
    try:
        return jsonify(nik.narrativa_relatorio(db, inicio, fim, parceiro_id))
    finally:
        db.close()


@nik_bp.route("/ops/conversa", methods=["POST"])
@login_required
def ops_conversa():
    payload = request.get_json(silent=True) or {}
    mensagem = payload.get("mensagem", "")
    thread_id = payload.get("thread_id") or request.args.get("thread_id") or "main"
    db = get_db()
    try:
        uid = current_user.id if current_user.is_authenticated else None
        resposta = nik.conversar_ops_thread(db, mensagem, thread_id=thread_id, usuario_id=uid)
        return jsonify(nik.salvar_conversa_ops(db, uid, mensagem, resposta, thread_id=thread_id))
    finally:
        db.close()


@nik_bp.route("/ops/conversas")
@login_required
def ops_conversas():
    limite = request.args.get("limite", 20, type=int)
    thread_id = request.args.get("thread_id")
    db = get_db()
    try:
        if thread_id:
            itens = nik.listar_conversas_thread(db, current_user.id, thread_id=thread_id, limite=limite)
        else:
            itens = nik.listar_conversas_ops(db, current_user.id, limite=limite)
        return jsonify({"itens": itens, "thread_id": thread_id or None})
    finally:
        db.close()


@nik_bp.route("/maiara/relatorio")
@login_required
def maiara_relatorio():
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    parceiro_id = request.args.get("parceiro_id", type=int)
    formato = request.args.get("formato", "executivo")
    db = get_db()
    try:
        return jsonify(nik.gerar_relatorio_maiara(db, current_user.id, inicio, fim, parceiro_id, formato))
    finally:
        db.close()


@nik_bp.route("/maiara/relatorio/<int:relatorio_id>/export")
@login_required
def exportar_maiara_relatorio(relatorio_id: int):
    formato = (request.args.get("formato") or "json").strip().lower()
    db = get_db()
    try:
        relatorio = nik.obter_relatorio_maiara(db, relatorio_id)
        if not relatorio:
            return jsonify({"erro": "Relatório não encontrado"}), 404
        titulo = relatorio.get("titulo", "relatorio_nik").replace(" ", "_")
        if formato in {"md", "markdown"}:
            return Response(
                relatorio.get("conteudo_markdown", ""),
                mimetype="text/markdown; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{titulo}.md"'},
            )
        return Response(
            jsonify(relatorio.get("conteudo", {})).get_data(as_text=False),
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{titulo}.json"'},
        )
    finally:
        db.close()


@nik_bp.route("/landing/<tipo_bloco>")
def landing_bloco(tipo_bloco: str):
    tipos_validos = {
        "fala_nik",
        "fato_reciclagem",
        "impacto_tronik",
        "pergunta_guiada",
        "nik_explica",
    }
    if tipo_bloco not in tipos_validos:
        return jsonify({"erro": f"Tipo inválido. Válidos: {sorted(tipos_validos)}"}), 400
    return jsonify(nik.gerar_bloco_landing(tipo_bloco))
