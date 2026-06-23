"""
Endpoints da Nik.
"""

from __future__ import annotations

import base64
import contextlib
import json
import re

from flask import Blueprint, Response, jsonify, request, stream_with_context
from flask_login import current_user, login_required

from banco_dados.services import nik_service as nik, nik_tools
from banco_dados.services.nik_service import NIK_IMAGEM_MAX_BYTES
from banco_dados.utils.cache import obter_cache
from rotas.api.decorators import admin_required, escopo_parceiro_id, get_db, rate_limit

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
    parceiro_id = escopo_parceiro_id(request.args.get("parceiro_id", type=int))

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

    thread_id = (
        request.form.get("thread_id")
        or request.args.get("thread_id")
        or (request.get_json(silent=True) or {}).get("thread_id")
        or "main"
    )
    db = get_db()
    try:
        resultado = nik.analisar_imagem_coletor(
            db,
            image_bytes,
            coletor_id,
            mime=mime,
            pergunta=pergunta,
        )
        uid = current_user.id if current_user.is_authenticated else None
        pergunta_persist = ((pergunta or "Analise esta imagem do coletor.").strip() + " [imagem anexada]")
        payload_persist = {
            **resultado,
            "modo_contexto": "imagem",
            "turno": "imagem",
            "imagem": {"mime": mime, "marcador": "[imagem anexada]"},
        }
        salvo = nik.salvar_conversa_ops(db, uid, pergunta_persist, payload_persist, thread_id=thread_id)
        resultado["historico_id"] = salvo.get("historico_id")
        resultado["thread_id"] = thread_id
        return jsonify(resultado)
    finally:
        db.close()


@nik_bp.route("/ops/upload", methods=["POST"])
@login_required
@admin_required
@rate_limit("10 per minute")
def ops_upload():
    """Upload de CSV/PDF: mode=analyze (análise) ou mode=import_coletas (importação)."""
    from banco_dados.services import nik_coleta_import, nik_file_service as fsvc

    arquivo = request.files.get("file") or request.files.get("arquivo")
    if not arquivo:
        return jsonify({"erro": "Envie um arquivo no campo 'file'."}), 400
    data = arquivo.read()
    if not data:
        return jsonify({"erro": "Arquivo vazio."}), 400
    if len(data) > fsvc.NIK_ARQUIVO_MAX_BYTES:
        limite_mb = fsvc.NIK_ARQUIVO_MAX_BYTES // (1024 * 1024)
        return jsonify({"erro": f"Arquivo excede o limite de {limite_mb} MB."}), 413

    filename = arquivo.filename or "arquivo"
    tipo = fsvc.detectar_tipo(filename, data)
    if tipo is None:
        return jsonify({"erro": "Tipo não suportado. Envie um CSV ou PDF válido."}), 400

    mode = (request.form.get("mode") or "analyze").strip()
    thread_id = request.form.get("thread_id") or request.args.get("thread_id") or "main"
    pergunta = (request.form.get("pergunta") or request.form.get("mensagem") or "").strip() or None
    uid = current_user.id if current_user.is_authenticated else None
    db = get_db()
    try:
        if mode == "import_coletas":
            if tipo != "csv":
                return jsonify({"erro": "Importação aceita apenas arquivos CSV."}), 400
            linhas = fsvc.ler_linhas_csv(data)
            resultado = nik_coleta_import.preparar_import_coletas(
                db, linhas, usuario_id=uid, thread_id=thread_id, filename=filename
            )
            payload_persist = {
                "texto": resultado["texto"],
                "fonte": "transacional",
                "modo_contexto": "real",
                "import_pendente": bool(resultado.get("pendente")),
                "import_stats": resultado.get("stats"),
                "turno": "import",
            }
            salvo = nik.salvar_conversa_ops(db, uid, f"[upload] {filename}", payload_persist, thread_id=thread_id)
            return jsonify({**resultado, "mode": "import_coletas", "filename": filename,
                            "thread_id": thread_id, "historico_id": salvo.get("historico_id")}), 201

        # modo analyze
        texto = fsvc.extrair_texto_pdf(data) if tipo == "pdf" else fsvc.extrair_texto_csv(data)
        resultado = fsvc.analisar_arquivo_conversa(texto_extraido=texto, pergunta=pergunta, filename=filename)
        payload_persist = {
            **resultado,
            "modo_contexto": "arquivo",
            "turno": "arquivo",
            "imagem": None,
        }
        salvo = nik.salvar_conversa_ops(
            db, uid, f"[arquivo] {filename}: {pergunta or 'analisar'}", payload_persist, thread_id=thread_id
        )
        return jsonify({**resultado, "mode": "analyze", "filename": filename,
                        "thread_id": thread_id, "historico_id": salvo.get("historico_id")}), 201
    finally:
        db.close()


@nik_bp.route("/ops/upload/confirm", methods=["POST"])
@login_required
@admin_required
@rate_limit("5 per minute")
def ops_upload_confirm():
    """Confirma a importação pendente (alternativa a digitar CONFIRMAR no chat)."""
    from banco_dados.services import nik_coleta_import

    payload = request.get_json(silent=True) or {}
    thread_id = payload.get("thread_id") or request.args.get("thread_id") or "main"
    uid = current_user.id if current_user.is_authenticated else None
    db = get_db()
    try:
        resultado = nik_coleta_import.executar_import_coletas(db, uid, thread_id)
        return jsonify(resultado)
    finally:
        db.close()


@nik_bp.route("/ops/export/<token>")
@login_required
@admin_required
def ops_export_download(token: str):
    """Download de CSV gerado pela ferramenta exportar_coletas_csv."""
    cache = obter_cache()
    payload = cache.obter(f"nik:export:{token}", ttl_segundos=3600)
    if not payload or not isinstance(payload, dict):
        return jsonify({"erro": "Exportação expirada ou inválida."}), 404
    if (
        payload.get("usuario_id") is not None
        and current_user.is_authenticated
        and payload["usuario_id"] != current_user.id
        and not current_user.admin
    ):
        return jsonify({"erro": "Sem permissão para este arquivo."}), 403
    csv_text = payload.get("csv") or ""
    filename = payload.get("filename") or "coletas.csv"
    return Response(
        csv_text,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _sse_pack(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@nik_bp.route("/ops/conversa", methods=["POST"])
@admin_required
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
    reenviar_de_id = payload.get("reenviar_de_id")
    stream = (
        bool(payload.get("stream"))
        or request.args.get("stream") == "1"
        or "text/event-stream" in (request.headers.get("Accept") or "")
    )

    db = get_db()
    uid = current_user.id if current_user.is_authenticated else None
    if reenviar_de_id is not None:
        tid = nik.truncar_thread_a_partir_de(db, uid, int(reenviar_de_id))
        if tid:
            thread_id = tid

    if not stream:
        try:
            resposta = nik.conversar_ops_thread(db, mensagem, thread_id=thread_id, usuario_id=uid)
            return jsonify(nik.salvar_conversa_ops(db, uid, mensagem, resposta, thread_id=thread_id))
        finally:
            db.close()

    def generate():
        try:
            for item in nik.conversar_ops_thread_stream(db, mensagem, thread_id=thread_id, usuario_id=uid):
                ev = item["event"]
                data = item["data"]
                if ev == "done":
                    saved = nik.salvar_conversa_ops(db, uid, mensagem, data, thread_id=thread_id)
                    yield _sse_pack("done", saved)
                else:
                    yield _sse_pack(ev, data)
        finally:
            db.close()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


@nik_bp.route("/ops/threads", methods=["GET", "POST"])
@login_required
def ops_threads():
    db = get_db()
    try:
        if request.method == "POST":
            thread_id = nik.criar_thread_id()
            return jsonify({"thread_id": thread_id, "titulo": "Nova conversa"}), 201
        limite = request.args.get("limite", 40, type=int)
        threads = nik.listar_threads_ops(db, current_user.id, limite=limite)
        return jsonify({"threads": threads})
    finally:
        db.close()


@nik_bp.route("/ops/threads/<thread_id>", methods=["DELETE"])
@login_required
def ops_thread_delete(thread_id: str):
    db = get_db()
    try:
        removidos = nik.excluir_thread_ops(db, current_user.id, thread_id)
        if removidos <= 0:
            return jsonify({"erro": "Conversa não encontrada ou já vazia."}), 404
        return jsonify({"ok": True, "thread_id": thread_id, "removidos": removidos})
    finally:
        db.close()


@nik_bp.route("/ops/conversas/<int:conversa_id>", methods=["DELETE"])
@login_required
def ops_conversa_delete(conversa_id: int):
    db = get_db()
    try:
        ok = nik.excluir_mensagem_ops(db, current_user.id, conversa_id)
        if not ok:
            return jsonify({"erro": "Mensagem não encontrada."}), 404
        return jsonify({"ok": True, "id": conversa_id})
    finally:
        db.close()


@nik_bp.route("/maiara/relatorio")
@login_required
def maiara_relatorio():
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    parceiro_id = escopo_parceiro_id(request.args.get("parceiro_id", type=int))
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
        relatorio = nik.obter_relatorio_maiara(
            db,
            relatorio_id,
            usuario_id=current_user.id,
            admin=bool(current_user.admin),
        )
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
