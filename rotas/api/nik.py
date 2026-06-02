"""
Endpoints da Nik.
"""

from __future__ import annotations

import base64
import contextlib
import re

from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from banco_dados.services import nik_service as nik, nik_tools
from banco_dados.services.nik_service import NIK_IMAGEM_MAX_BYTES
from rotas.api.decorators import admin_required, get_db

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
    # [SEGURANÇA] Validação de parâmetros de entrada
    MAX_PARAM = 1_000

    inicio = request.args.get("inicio", "").strip()
    fim = request.args.get("fim", "").strip()
    parceiro_id = request.args.get("parceiro_id", type=int)

    # Validar tamanho dos parâmetros de data
    if len(inicio) > MAX_PARAM or len(fim) > MAX_PARAM:
        return jsonify({"erro": f"Parâmetros excedem limite de {MAX_PARAM} caracteres"}), 413

    db = get_db()
    try:
        return jsonify(nik.narrativa_relatorio(db, inicio if inicio else None, fim if fim else None, parceiro_id))
    finally:
        db.close()


_DATA_URL_B64 = re.compile(r"^data:image/[\w+.-]+;base64,", re.IGNORECASE)


def _validar_magic_bytes_imagem(image_bytes: bytes) -> bool:
    """Valida os magic bytes reais do arquivo de imagem."""
    if not image_bytes or len(image_bytes) < 3:
        return False

    # Magic bytes para formatos suportados
    # JPEG: FF D8 FF
    if image_bytes[:3] == b'\xFF\xD8\xFF':
        return True
    # PNG: 89 50 4E 47
    if image_bytes[:4] == b'\x89PNG':
        return True
    # GIF: 47 49 46 38 (GIF8)
    if image_bytes[:6].startswith(b'GIF8'):
        return True
    # WebP: RIFF ... WEBP
    return len(image_bytes) >= 12 and image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP'


def _decodificar_base64_imagem(raw: str) -> bytes:
    texto = (raw or "").strip()
    if _DATA_URL_B64.match(texto):
        texto = texto.split(",", 1)[1]
    return base64.b64decode(texto, validate=True)


def _extrair_imagem_ops_request() -> tuple[bytes | None, str, int | None, str | None, str | None]:
    """Multipart (campo imagem/image) ou JSON com image_base64 / imagem_base64."""
    coletor_id: int | None = None
    pergunta: str | None = None
    mime = "image/jpeg"

    if request.files:
        arquivo = request.files.get("imagem") or request.files.get("image")
        if arquivo:
            coletor_id = request.form.get("coletor_id", type=int)
            pergunta = (request.form.get("pergunta") or request.form.get("mensagem") or "").strip() or None
            mime = (arquivo.mimetype or mime).split(";")[0].strip() or mime
            return arquivo.read(), mime, coletor_id, pergunta, None

    payload = request.get_json(silent=True) or {}
    if payload.get("coletor_id") is not None:
        with contextlib.suppress(TypeError, ValueError):
            coletor_id = int(payload["coletor_id"])
    pergunta = (payload.get("pergunta") or payload.get("mensagem") or "").strip() or None
    mime = (payload.get("mime") or payload.get("mime_type") or mime).split(";")[0].strip() or mime
    b64 = payload.get("image_base64") or payload.get("imagem_base64") or payload.get("data")
    if b64:
        try:
            return _decodificar_base64_imagem(str(b64)), mime, coletor_id, pergunta, None
        except (ValueError, base64.binascii.Error):
            return None, mime, coletor_id, None, "image_base64 inválido"
    return None, mime, coletor_id, None, "Envie multipart (imagem) ou JSON com image_base64"


@nik_bp.route("/ops/analisar-imagem", methods=["POST"])
@login_required
@admin_required
def ops_analisar_imagem():
    image_bytes, mime, coletor_id, pergunta, erro = _extrair_imagem_ops_request()
    if erro or not image_bytes:
        return jsonify({"erro": erro or "Imagem ausente"}), 400
    if len(image_bytes) > NIK_IMAGEM_MAX_BYTES:
        return jsonify({"erro": "Imagem excede o limite de 4 MB"}), 413

    # [SEGURANÇA] Validar magic bytes reais do arquivo, não confiar no mimetype declarado
    if not _validar_magic_bytes_imagem(image_bytes):
        return jsonify({"erro": "Arquivo não é uma imagem válida (JPEG, PNG, GIF ou WebP)"}), 400

    db = get_db()
    try:
        resultado = nik.analisar_imagem_coletor(
            db,
            image_bytes,
            coletor_id,
            mime=mime,
            pergunta=pergunta,
        )
        return jsonify(resultado)
    finally:
        db.close()


@nik_bp.route("/ops/conversa", methods=["POST"])
@login_required
def ops_conversa():
    # [SEGURANÇA] Validação de tamanho de mensagem
    MAX_MENSAGEM = 50_000

    payload = request.get_json(silent=True) or {}
    mensagem = payload.get("mensagem", "").strip() if isinstance(payload.get("mensagem"), str) else ""

    # Validar mensagem vazia
    if not mensagem:
        return jsonify({"erro": "Mensagem é obrigatória"}), 400

    # Validar tamanho máximo
    if len(mensagem) > MAX_MENSAGEM:
        return jsonify({"erro": f"Mensagem excede limite de {MAX_MENSAGEM} caracteres"}), 413

    thread_id = payload.get("thread_id") or request.args.get("thread_id") or "main"
    db = get_db()
    try:
        uid = current_user.id if current_user.is_authenticated else None
        resposta = nik.conversar_ops_thread(db, mensagem, thread_id=thread_id, usuario_id=uid)
        return jsonify(nik.salvar_conversa_ops(db, uid, mensagem, resposta, thread_id=thread_id))
    finally:
        db.close()


@nik_bp.route("/ops/ferramentas")
@login_required
@admin_required
def ops_ferramentas():
    """Catálogo de ferramentas agentic da Nik (debug/admin)."""
    return jsonify({"ferramentas": nik_tools.catalogo_ferramentas()})


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
