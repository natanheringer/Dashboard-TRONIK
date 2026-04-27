"""
Orquestrador da Nik.
"""

from __future__ import annotations

import os
import json
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from banco_dados.modelos import NikConversa, NikRelatorioGerado, Parceiro
from banco_dados.services import nik_contexto as ctx
from banco_dados.services import nik_prompts as prompts
from banco_dados.services import nik_provider as provider
from banco_dados.services import nik_tools
from banco_dados.services import nik_validacao as val
from banco_dados.utils.cache import obter_cache

_FALLBACK_RESUMO = (
    "Painel operacional carregado. Consulte os indicadores e o monitoramento para priorizar os coletores em atenção."
)
_FALLBACK_COLETOR = (
    "Os dados do coletor já estão disponíveis no painel. A análise automática não está disponível neste momento."
)
_FALLBACK_ALERTA = (
    "Existe um alerta ativo no painel. Priorize o coletor destacado e valide a rota de coleta."
)
_FALLBACK_RELATORIO = (
    "Os dados do período estão consolidados acima. A narrativa automática não está disponível neste momento."
)
_FALLBACK_BLOCO_LANDING: dict[str, dict[str, str]] = {
    "fala_nik": {
        "titulo": "Lixo eletrônico não desaparece sozinho",
        "corpo": "Cada equipamento descartado do jeito certo evita contaminação e devolve materiais valiosos para a cadeia produtiva.",
        "destaque": "Reciclar eletrônico é também redesenhar o futuro da cidade.",
    },
    "fato_reciclagem": {
        "fato": "Placas eletrônicas concentram metais de alto valor e mostram por que a reciclagem correta é estratégica.",
        "fonte": "Contexto setorial de reciclagem eletrônica",
    },
    "impacto_tronik": {
        "titulo": "Logística reversa com propósito",
        "metrica": "Coleta, triagem e destinação responsável em uma mesma operação",
        "explicacao": "A Tronik conecta geradores, parceiros e recicladores para transformar descarte em reaproveitamento.",
    },
    "pergunta_guiada": {
        "pergunta": "O que fazer com eletrônicos parados na empresa?",
        "resposta_curta": "Separar, registrar a origem do material e encaminhar para uma operação de coleta e destinação rastreável.",
    },
    "nik_explica": {
        "titulo": "O que é logística reversa?",
        "corpo": "É o caminho de volta do produto após o uso, para desmontagem, reaproveitamento e destinação ambientalmente correta.",
        "analogia": "Em vez de terminar no lixo comum, o equipamento entra em uma rota de retorno para voltar à cadeia produtiva.",
    },
}


def _nik_habilitada() -> bool:
    return os.getenv("NIK_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _ttl(env_key: str, default: int) -> int:
    try:
        return int(os.getenv(env_key, str(default)))
    except ValueError:
        return default


def _modelo_tarefa(tarefa: str, mensagem: str = "") -> str:
    """Roteação determinística de modelos por tipo de tarefa."""
    # Prioriza NIK_MODELO_OPS para manter um único "modelo base" efetivo.
    # NIK_MODELO_CHAT fica apenas como legado/fallback.
    chat_default = os.getenv("NIK_MODELO_OPS", os.getenv("NIK_MODELO_CHAT", "llama-3.1-8b-instant"))
    analytics_default = os.getenv("NIK_MODELO_ANALYTICS", os.getenv("NIK_MODELO_OPS", chat_default))
    relatorio_default = os.getenv("NIK_MODELO_RELATORIO", "llama-3.3-70b-versatile")
    landing_default = os.getenv("NIK_MODELO_LANDING", chat_default)
    web_default = os.getenv("NIK_MODELO_WEB", chat_default)
    web_safe = os.getenv("NIK_MODELO_WEB_SAFE", os.getenv("NIK_MODELO_FALLBACK", chat_default))

    msg = (mensagem or "").lower()
    if tarefa == "relatorio":
        return relatorio_default
    if tarefa == "landing":
        return landing_default
    if tarefa == "web":
        disable_compound = os.getenv("NIK_WEB_DISABLE_COMPOUND", "true").strip().lower() in {"1", "true", "yes"}
        if disable_compound and "compound" in (web_default or "").lower():
            return web_safe
        return web_default
    if tarefa in {"analytics", "ops_resumo", "ops_alerta", "ops_coletor"}:
        return analytics_default
    if tarefa == "conversa":
        # Prompts longos: por defeito usa o mesmo tier que OPS/analytics (evita queimar TPD do 70B).
        # NIK_ROUTE_LONG_CONTEXT_TO_70B: se true, escala para NIK_MODELO_LONG_CONTEXT ou NIK_MODELO_ANALYTICS (não para RELATORIO).
        route_long = os.getenv("NIK_ROUTE_LONG_CONTEXT_TO_70B", "false").strip().lower() in {"1", "true", "yes"}
        if route_long:
            if len(msg) > 900 or any(k in msg for k in ["relatório completo", "analise profunda", "plano estratégico"]):
                explicit_lc = (os.getenv("NIK_MODELO_LONG_CONTEXT") or "").strip()
                if explicit_lc:
                    return explicit_lc
                return os.getenv("NIK_MODELO_ANALYTICS", chat_default)
        return chat_default
    return chat_default


def _modelo_web_writer(mensagem: str) -> str:
    """Modelo que redige a resposta final após pesquisa web (evita 70B/TPD na cola do fluxo web)."""
    explicit = (os.getenv("NIK_MODELO_WEB_WRITER") or "").strip()
    if explicit:
        return explicit
    return _modelo_tarefa("analytics", mensagem)


def _mensagem_pede_web(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    sinais_web = [
        "internet",
        "na web",
        "web",
        "notícia",
        "noticia",
        "fonte externa",
        "atualizado hoje",
        "dados recentes",
        "dados atualizados",
        "cenário atual",
        "cenario atual",
        "panorama atual",
        "estado da arte",
    ]
    if any(k in msg for k in sinais_web):
        return True

    if any(k in msg for k in ["fonte", "fontes", "links", "referência", "referencias", "referências"]):
        return True

    # Verbos de pesquisa + tema externo também disparam web research.
    verbos_busca = [
        "pesquise",
        "pesquisar",
        "busque",
        "buscar",
        "procure",
        "encontre",
        "pesquisa",
        "levantamento",
        "estudo",
    ]
    temas_externos = [
        "e-waste",
        "ewaste",
        "lixo eletronico",
        "lixo eletrônico",
        "residuo eletronico",
        "resíduo eletrônico",
        "reciclagem",
        "logistica reversa",
        "logística reversa",
        "residuos",
        "resíduos",
        "ambiental",
        "esg",
        "mercado",
        "setor",
        "concorr",
        "tendência",
        "tendencia",
        "benchmark",
        "demanda",
        "oportunidade",
        "legislação",
        "legislacao",
    ]
    if any(v in msg for v in verbos_busca) and any(t in msg for t in temas_externos):
        return True

    # Intenções frequentes sem verbo explícito de busca.
    frases_pesquisa = [
        "pesquisa de mercado",
        "analise de mercado",
        "análise de mercado",
        "estudo de mercado",
        "levantamento de mercado",
        "panorama de mercado",
        "mapeamento de mercado",
        "quais são as principais iniciativas",
        "quais sao as principais iniciativas",
    ]
    if any(f in msg for f in frases_pesquisa):
        return True

    # Perguntas de contexto geográfico/setorial tendem a exigir fonte externa.
    locais = ["brasil", "brasilia", "distrito federal", "df", "regional", "local", "mundo", "global"]
    if any(t in msg for t in temas_externos) and any(l in msg for l in locais):
        return True

    return False


def _mensagem_pede_documento(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    gatilhos = [
        "gere um documento",
        "gerar documento",
        "modo documento",
        "com sumário",
        "com sumario",
        "relatório detalhado",
        "estilo manus",
        "documento executivo",
        "gere"
        "crie"
        "criar"
    ]
    return any(g in msg for g in gatilhos)


def _cache_get(chave: str, ttl: int) -> Optional[dict[str, Any]]:
    return obter_cache().obter(chave, ttl)


def _cache_set(chave: str, valor: dict[str, Any]) -> dict[str, Any]:
    obter_cache().definir(chave, valor)
    return valor


def _resposta_ops(cache_key: str, ttl: int, fallback: str, chamada_modelo, contexto):
    cached = _cache_get(cache_key, ttl)
    if cached:
        return cached
    if not _nik_habilitada():
        return {"texto": fallback, "fonte": "desabilitada", "modelo": None}

    resposta = chamada_modelo(contexto)
    texto = val.validar_resposta_ops(
        resposta.texto if resposta.sucesso else "",
        fallback,
        max_chars=_ttl("NIK_MAX_CHARS_CONVERSA", 3200),
    )
    resultado = {
        "texto": texto,
        "fonte": "modelo" if resposta.sucesso and texto != fallback else "fallback",
        "modelo": resposta.modelo_usado if resposta.sucesso else None,
        "tokens_prompt": resposta.tokens_prompt,
        "tokens_resposta": resposta.tokens_resposta,
        "latencia_ms": resposta.latencia_ms,
    }
    return _cache_set(cache_key, resultado)


def resumo_operacional(db: Session) -> dict[str, Any]:
    contexto = ctx.contexto_resumo_operacional(db)
    return _resposta_ops(
        "nik:ops:resumo",
        _ttl("NIK_CACHE_TTL_RESUMO_OPS", 1800),
        _FALLBACK_RESUMO,
        lambda c: provider.chamar_modelo(
            prompts.SYSTEM_OPS_RESUMO,
            prompts.montar_prompt_ops_resumo(c),
            modelo=_modelo_tarefa("ops_resumo"),
            max_tokens=_ttl("NIK_MAX_TOKENS_OPS", 512),
            temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
        ),
        contexto,
    )


def analise_coletor(db: Session, coletor_id: int) -> dict[str, Any]:
    contexto = ctx.contexto_coletor(db, coletor_id)
    if not contexto:
        return {"texto": "Coletor não encontrado.", "fonte": "sistema", "modelo": None}
    return _resposta_ops(
        f"nik:ops:coletor:{coletor_id}",
        _ttl("NIK_CACHE_TTL_COLETOR_OPS", 600),
        _FALLBACK_COLETOR,
        lambda c: provider.chamar_modelo(
            prompts.SYSTEM_OPS_COLETOR,
            prompts.montar_prompt_ops_coletor(c),
            modelo=_modelo_tarefa("ops_coletor"),
            max_tokens=_ttl("NIK_MAX_TOKENS_OPS", 512),
            temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
        ),
        contexto,
    )


def analise_alerta(db: Session) -> dict[str, Any]:
    contexto = ctx.contexto_alerta(db)
    if not contexto:
        return {"texto": "Nenhum alerta crítico ativo no momento.", "fonte": "sistema", "modelo": None}
    return _resposta_ops(
        "nik:ops:alerta",
        _ttl("NIK_CACHE_TTL_RESUMO_OPS", 1800),
        _FALLBACK_ALERTA,
        lambda c: provider.chamar_modelo(
            prompts.SYSTEM_OPS_ALERTA,
            prompts.montar_prompt_ops_alerta(c),
            modelo=_modelo_tarefa("ops_alerta"),
            max_tokens=_ttl("NIK_MAX_TOKENS_OPS", 512),
            temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
        ),
        contexto,
    )


def narrativa_relatorio(
    db: Session,
    inicio: Optional[str],
    fim: Optional[str],
    parceiro_id: Optional[int],
) -> dict[str, Any]:
    contexto = ctx.contexto_relatorio(db, inicio, fim, parceiro_id)
    chave = f"nik:ops:relatorio:{contexto['periodo']['inicio']}:{contexto['periodo']['fim']}:{parceiro_id or 'all'}"
    return _resposta_ops(
        chave,
        _ttl("NIK_CACHE_TTL_RELATORIO_OPS", 3600),
        _FALLBACK_RELATORIO,
        lambda c: provider.chamar_modelo(
            prompts.SYSTEM_OPS_RELATORIO,
            prompts.montar_prompt_ops_relatorio(c),
            modelo=_modelo_tarefa("relatorio"),
            max_tokens=_ttl("NIK_MAX_TOKENS_OPS", 512),
            temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.3")),
        ),
        contexto,
    )


def gerar_bloco_landing(tipo_bloco: str) -> dict[str, Any]:
    cache_key = f"nik:landing:{tipo_bloco}"
    cached = _cache_get(cache_key, _ttl("NIK_CACHE_TTL_LANDING", 3600))
    if cached:
        return cached

    fallback = _FALLBACK_BLOCO_LANDING.get(tipo_bloco)
    if not fallback:
        return {"bloco": None, "fonte": "invalido", "modelo": None}
    if not _nik_habilitada():
        return {"bloco": fallback, "fonte": "desabilitada", "modelo": None}

    resposta = provider.chamar_modelo(
        prompts.SYSTEM_LANDING,
        prompts.montar_prompt_landing(tipo_bloco, ctx.contexto_landing()),
        modelo=_modelo_tarefa("landing"),
        max_tokens=_ttl("NIK_MAX_TOKENS_LANDING", 384),
        temperature=float(os.getenv("NIK_TEMPERATURE_LANDING", "0.7")),
    )
    bloco = (
        val.validar_resposta_landing(resposta.texto, tipo_bloco)
        if resposta.sucesso
        else None
    )
    resultado = {
        "bloco": bloco or fallback,
        "fonte": "modelo" if bloco else "fallback",
        "modelo": resposta.modelo_usado if resposta.sucesso else None,
    }
    return _cache_set(cache_key, resultado)


def conversar_ops(db: Session, mensagem: str) -> dict[str, Any]:
    return conversar_ops_thread(db, mensagem, thread_id="main", usuario_id=None)


def _normalizar_thread_id(thread_id: Optional[str]) -> str:
    raw = (thread_id or "main").strip().lower()
    if not raw:
        return "main"
    safe = re.sub(r"[^a-z0-9._-]", "-", raw)
    return safe[:80] or "main"


def _historico_thread(
    db: Session,
    usuario_id: Optional[int],
    thread_id: str,
    limite: int = 8,
) -> list[dict[str, Any]]:
    q = db.query(NikConversa)
    if usuario_id is not None:
        q = q.filter(NikConversa.usuario_id == usuario_id)
    q = q.filter(NikConversa.thread_id == thread_id)
    rows = q.order_by(NikConversa.criado_em.desc()).limit(max(1, min(limite, 20))).all()
    rows.reverse()
    return [{"pergunta": r.pergunta, "resposta": r.resposta, "criado_em": r.criado_em.isoformat() if r.criado_em else None} for r in rows]


def _planejar_ferramentas(mensagem: str) -> list[dict[str, Any]]:
    msg = (mensagem or "").lower()
    anos = _extrair_anos(msg)
    ano_inicio = min(anos) if anos else None
    ano_fim = max(anos) if anos else None

    plano: list[dict[str, Any]] = [{"nome": "snapshot_operacional", "kwargs": {}}]
    pede_web = _mensagem_pede_web(mensagem)
    pede_busca_interna = any(k in msg for k in ["busque", "buscar", "procure", "encontre", "no sistema"])
    pergunta_exploratoria = any(k in msg for k in ["quais", "qual", "quem", "onde"]) and not any(
        k in msg for k in ["relatório", "relatorio", "timeline", "impacto"]
    )

    if pede_busca_interna or pergunta_exploratoria:
        plano.append({"nome": "busca_unificada", "kwargs": {"consulta": mensagem.strip()}})
    if pede_web:
        plano.append({"nome": "catalogo_fontes_web", "kwargs": {}})
        plano.append({"nome": "busca_web", "kwargs": {"consulta": mensagem.strip()}})
    if any(k in msg for k in ["linha do tempo", "timeline", "dados antigos", "histórico", "historico", "desde"]) or len(anos) >= 1:
        plano.append({"nome": "timeline_anual", "kwargs": {"ano_inicio": ano_inicio, "ano_fim": ano_fim}})
    if any(k in msg for k in ["impacto", "completo", "ostensivo", "estratég", "estrateg"]):
        plano.append({"nome": "impacto_geral", "kwargs": {"ano_inicio": ano_inicio, "ano_fim": ano_fim}})
    if "relatório" in msg or "relatorio" in msg:
        plano.append({"nome": "resumo_periodo", "kwargs": {}})
    # Dedupe mantendo ordem (evita chamadas repetidas)
    vistos: set[str] = set()
    final: list[dict[str, Any]] = []
    for p in plano:
        nome = str(p.get("nome") or "")
        if not nome or nome in vistos:
            continue
        vistos.add(nome)
        final.append(p)
    return final


def _extrair_datas_iso_ou_br(texto: str) -> list[date]:
    out: list[date] = []
    for a, b, c in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", texto):
        try:
            out.append(date(int(a), int(b), int(c)))
        except ValueError:
            pass
    for d, m, y in re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b", texto):
        try:
            out.append(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    return out


def _extrair_mes_ano(texto: str) -> Optional[tuple[int, int]]:
    meses = {
        "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6,
        "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
    }
    msg = (texto or "").lower()
    for nome, numero in meses.items():
        m = re.search(rf"\b{re.escape(nome)}\s+(?:de\s+)?(20\d{{2}})\b", msg)
        if m:
            return numero, int(m.group(1))
    return None


def _fim_mes(ano: int, mes: int) -> date:
    if mes == 12:
        return date(ano, 12, 31)
    return date(ano, mes + 1, 1) - timedelta(days=1)


def _periodo_ultimo_ano_com_dados(db: Session) -> Optional[dict[str, str]]:
    limites = nik_tools.ferramenta_limites_historico(db)
    fim_raw = limites.get("fim")
    if not fim_raw:
        return None
    fim = datetime.fromisoformat(fim_raw).date()
    inicio = fim - timedelta(days=365)
    return {"inicio": inicio.isoformat(), "fim": fim.isoformat()}


def _pedido_relatorio_ultimo_ano(mensagem: str) -> bool:
    msg = (mensagem or "").lower()
    gatilhos = [
        "último ano",
        "ultimo ano",
        "últimos 12 meses",
        "ultimos 12 meses",
        "12 meses",
        "ano passado",
    ]
    return any(g in msg for g in gatilhos) and ("relatório" in msg or "relatorio" in msg or "resumo" in msg)


def _extrair_parceiro_id_por_texto(db: Session, mensagem: str) -> Optional[int]:
    msg = (mensagem or "").lower()
    rows = db.query(Parceiro.id, Parceiro.nome).all()
    for pid, nome in sorted(rows, key=lambda r: len(r[1] or ""), reverse=True):
        nome_l = (nome or "").strip().lower()
        if nome_l and nome_l in msg:
            return int(pid)
    m = re.search(r"\bparceiro\s*#?\s*(\d{1,6})\b", msg)
    return int(m.group(1)) if m else None


def _inferir_consulta_usuario(db: Session, mensagem: str) -> dict[str, Any]:
    msg = (mensagem or "").lower()
    limites = nik_tools.ferramenta_limites_historico(db)
    data_max = date.fromisoformat(limites["fim"]) if limites.get("fim") else date.today()
    datas = sorted(_extrair_datas_iso_ou_br(mensagem))
    anos = _extrair_anos(msg)
    mes_ano = _extrair_mes_ano(msg)
    parceiro_id = _extrair_parceiro_id_por_texto(db, mensagem)

    inicio: Optional[date] = None
    fim: Optional[date] = None
    ano_inicio: Optional[int] = None
    ano_fim: Optional[int] = None

    if len(datas) >= 2:
        inicio, fim = datas[0], datas[-1]
    elif len(datas) == 1:
        inicio = datas[0]
        fim = datas[0]
    elif _pedido_relatorio_ultimo_ano(mensagem):
        per = _periodo_ultimo_ano_com_dados(db)
        if per:
            inicio = date.fromisoformat(per["inicio"])
            fim = date.fromisoformat(per["fim"])
    elif re.search(r"\bultim[oa]s?\s+(\d{1,3})\s+dias\b", msg):
        dias = int(re.search(r"\bultim[oa]s?\s+(\d{1,3})\s+dias\b", msg).group(1))
        fim = data_max
        inicio = fim - timedelta(days=max(1, dias) - 1)
    elif "ultima semana" in msg or "última semana" in msg:
        fim = data_max
        inicio = fim - timedelta(days=6)
    elif "ultimo trimestre" in msg or "último trimestre" in msg:
        fim = data_max
        inicio = fim - timedelta(days=89)
    elif "ultimo mes" in msg or "último mês" in msg:
        fim = data_max
        inicio = fim - timedelta(days=29)
    elif "este mes" in msg or "este mês" in msg:
        fim = data_max
        inicio = date(fim.year, fim.month, 1)
    elif mes_ano:
        mes, ano = mes_ano
        inicio = date(ano, mes, 1)
        fim = _fim_mes(ano, mes)
    elif len(anos) >= 2:
        ano_inicio = min(anos)
        ano_fim = max(anos)
    elif len(anos) == 1:
        ano_inicio = anos[0]
        ano_fim = anos[0]

    if inicio and fim:
        ano_inicio = inicio.year
        ano_fim = fim.year

    return {
        "inicio": inicio.isoformat() if inicio else None,
        "fim": fim.isoformat() if fim else None,
        "ano_inicio": ano_inicio,
        "ano_fim": ano_fim,
        "parceiro_id": parceiro_id,
    }


def _executar_plano_ferramentas(db: Session, plano: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    resultado_contexto: dict[str, Any] = {}
    trace: list[dict[str, Any]] = []
    mapa = {
        "snapshot_operacional": nik_tools.ferramenta_snapshot_operacional,
        "resumo_periodo": nik_tools.ferramenta_resumo_periodo,
        "timeline_anual": nik_tools.ferramenta_timeline_anual,
        "impacto_geral": nik_tools.ferramenta_impacto_geral,
        "limites_historico": nik_tools.ferramenta_limites_historico,
        "busca_unificada": nik_tools.ferramenta_busca_unificada,
        "busca_web": nik_tools.ferramenta_busca_web,
        "catalogo_fontes_web": lambda _db: nik_tools.catalogo_fontes_web(),
    }
    for item in plano:
        nome = item.get("nome")
        kwargs = item.get("kwargs", {}) or {}
        fn = mapa.get(nome)
        if not fn:
            trace.append({"tool": nome, "status": "unknown_tool", "kwargs": kwargs})
            continue
        try:
            if nome == "resumo_periodo" and not kwargs:
                kwargs = item["kwargs"] = {}
            saida = fn(db, **kwargs)
            if nome == "snapshot_operacional":
                resultado_contexto.update(saida if isinstance(saida, dict) else {"snapshot_operacional": saida})
            else:
                resultado_contexto[nome] = saida
            trace.append({"tool": nome, "status": "ok", "kwargs": kwargs})
        except Exception as exc:
            trace.append({"tool": nome, "status": "error", "kwargs": kwargs, "erro": str(exc)})
    return resultado_contexto, trace


def _quebrar_em_blocos(texto: str) -> list[str]:
    bruto = (texto or "").strip()
    if not bruto:
        return []
    partes = [p.strip() for p in re.split(r"\n{2,}", bruto) if p.strip()]
    if len(partes) >= 2:
        return partes[:6]
    sentencas = [s.strip() for s in re.split(r"(?<=[.!?])\s+", bruto) if s.strip()]
    if len(sentencas) <= 2:
        return [bruto]
    blocos: list[str] = []
    i = 0
    while i < len(sentencas):
        blocos.append(" ".join(sentencas[i:i + 2]).strip())
        i += 2
    return blocos[:6]


def _fontes_para_bloco(bloco: str, fontes_disponiveis: list[str]) -> list[str]:
    b = (bloco or "").lower()
    fontes: list[str] = []
    if any(k in b for k in ["timeline", "histórico", "historico", "ano"]):
        fontes.append("timeline_anual")
    if any(k in b for k in ["impacto", "eficiência", "eficiencia", "kg/km", "quilometragem", "km"]):
        fontes.append("impacto_geral")
    if any(k in b for k in ["período", "periodo", "resumo", "coletas", "volume"]):
        fontes.append("resumo_periodo")
    if not fontes:
        fontes.append("snapshot_operacional")
    finais = [f for f in fontes if f in fontes_disponiveis]
    return finais or (fontes_disponiveis[:1] if fontes_disponiveis else ["snapshot_operacional"])


def _gerar_citacoes_por_bloco(texto: str, contexto: dict[str, Any]) -> list[dict[str, Any]]:
    blocos = _quebrar_em_blocos(texto)
    fontes_disponiveis = contexto.get("used_tools", []) or ["snapshot_operacional"]
    citacoes: list[dict[str, Any]] = []
    for idx, bloco in enumerate(blocos, start=1):
        citacoes.append(
            {
                "bloco_id": idx,
                "trecho": bloco,
                "fontes": _fontes_para_bloco(bloco, fontes_disponiveis),
            }
        )
    return citacoes


def _contexto_para_modelo(contexto: dict[str, Any]) -> dict[str, Any]:
    """Reduz payload para economizar tokens sem perder sinal analítico."""
    slim = dict(contexto)
    hist = slim.get("historico_thread", [])
    if isinstance(hist, list):
        slim["historico_thread"] = [
            {
                "pergunta": str(h.get("pergunta", ""))[:240],
                "resposta": str(h.get("resposta", ""))[:320],
                "criado_em": h.get("criado_em"),
            }
            for h in hist[-3:]
            if isinstance(h, dict)
        ]
    bu = slim.get("busca_unificada")
    if isinstance(bu, dict):
        itens = bu.get("itens", [])
        if isinstance(itens, list):
            bu["itens"] = itens[:6]
    bw = slim.get("busca_web")
    if isinstance(bw, dict):
        itensw = bw.get("itens", [])
        if isinstance(itensw, list):
            bw["itens"] = [
                {"titulo": i.get("titulo"), "url": i.get("url"), "fonte": i.get("fonte")}
                for i in itensw[:4]
                if isinstance(i, dict)
            ]
            bw.pop("queries_executadas", None)
            bw.pop("dominios_catalogo", None)
    # Catálogo completo aumenta muito o prompt e pouco ajuda no raciocínio final.
    slim.pop("catalogo_ferramentas", None)
    return slim


def _fontes_web_contexto(contexto: dict[str, Any]) -> list[dict[str, str]]:
    bruto = (contexto.get("busca_web") or {}).get("itens", [])
    fontes: list[dict[str, str]] = []
    for item in bruto[:5]:
        if not isinstance(item, dict):
            continue
        titulo = str(item.get("titulo") or "").strip()
        url = str(item.get("url") or "").strip()
        fonte = str(item.get("fonte") or "").strip()
        if not url:
            continue
        fontes.append({"titulo": titulo[:140], "url": url[:500], "fonte": fonte[:80]})
    return fontes


def _resumo_web_sem_modelo(fontes_web: list[dict[str, str]], consulta: str) -> str:
    if not fontes_web:
        return "Não encontrei fontes externas válidas para esta pesquisa."
    linhas = [f"Pesquisa web concluída para: {consulta.strip()}."]
    for idx, src in enumerate(fontes_web[:3], start=1):
        titulo = (src.get("titulo") or src.get("fonte") or src.get("url") or "Fonte").strip()
        linhas.append(f"{idx}) {titulo}")
    linhas.append("Abri as fontes abaixo para você conferir os links.")
    return " ".join(linhas)


def _remover_links_texto(texto: str) -> str:
    bruto = texto or ""
    sem_urls = re.sub(r"https?://\S+", "", bruto)
    sem_www = re.sub(r"\bwww\.\S+", "", sem_urls)
    limpo = re.sub(r"\s{2,}", " ", sem_www).strip()
    return limpo


def _contexto_web_para_sintese(contexto: dict[str, Any]) -> dict[str, Any]:
    base = _contexto_para_modelo(contexto)
    bw = base.get("busca_web")
    if isinstance(bw, dict):
        itens = bw.get("itens", [])
        if isinstance(itens, list):
            bw["itens"] = [
                {
                    "titulo": i.get("titulo"),
                    "fonte": i.get("fonte"),
                    "snippet": i.get("snippet") or i.get("resumo") or "",
                }
                for i in itens[:6]
                if isinstance(i, dict)
            ]
    return base


def _sintese_web_modelo(contexto: dict[str, Any], mensagem: str) -> Optional[dict[str, Any]]:
    resposta = provider.chamar_modelo(
        prompts.SYSTEM_OPS_WEB_RESEARCH,
        prompts.montar_prompt_ops_web_research(_contexto_web_para_sintese(contexto), mensagem),
        modelo=_modelo_tarefa("web", mensagem),
        max_tokens=_ttl("NIK_MAX_TOKENS_WEB_SYNTH", 700),
        temperature=float(os.getenv("NIK_TEMPERATURE_WEB_SYNTH", "0.1")),
        response_format={"type": "json_object"},
    )
    if not resposta.sucesso:
        return None
    parsed = val.extrair_json_do_output(resposta.texto)
    if not parsed:
        return None
    achados = parsed.get("achados")
    if not isinstance(achados, list) or not achados:
        return None
    return parsed


def _fallback_documento_chat(mensagem: str, contexto: dict[str, Any]) -> dict[str, Any]:
    topicos = ["Contexto e objetivo", "Achados principais", "Riscos e oportunidades", "Recomendações"]
    resumo_contexto = "Documento gerado em fallback estruturado com base no contexto disponível."
    return {
        "titulo": f"Documento Nik · {mensagem[:80].strip()}",
        "sumario": topicos,
        "secoes": [
            {"titulo": "Contexto e objetivo", "conteudo": resumo_contexto},
            {"titulo": "Achados principais", "conteudo": "Os principais sinais operacionais foram consolidados a partir das ferramentas acionadas."},
            {"titulo": "Riscos e oportunidades", "conteudo": "Há oportunidade de aprofundar análise por período, parceiro e eficiência logística."},
            {"titulo": "Recomendações", "conteudo": "Validar dados críticos e executar plano de ação de curto prazo com acompanhamento semanal."},
        ],
        "conclusao": "Este documento oferece uma leitura executiva inicial e deve ser refinado com novos dados conforme necessário.",
        "proximos_passos": [
            "Revisar indicadores com o time operacional.",
            "Definir prioridades da semana com base nos riscos identificados.",
        ],
    }


def conversar_ops_thread(
    db: Session,
    mensagem: str,
    thread_id: Optional[str] = None,
    usuario_id: Optional[int] = None,
) -> dict[str, Any]:
    mensagem = (mensagem or "").strip()
    if not mensagem:
        return {"texto": "Escreva uma pergunta para a Nik.", "fonte": "sistema", "modelo": None}

    thread = _normalizar_thread_id(thread_id)
    contexto = _montar_contexto_conversa_integrada(db, mensagem, usuario_id=usuario_id, thread_id=thread)
    pediu_web = _mensagem_pede_web(mensagem)
    modo_routing = "web_research_report" if pediu_web else "chat_ops"
    modelo_conversa_groq = _modelo_tarefa("conversa", mensagem)
    use_nv_chat = (
        os.getenv("NIK_CHAT_USE_NVIDIA", "").strip().lower() in {"1", "true", "yes"}
        and not pediu_web
    )
    modelo_chat_nvidia = (os.getenv("NIK_MODELO_CHAT_NVIDIA") or "nvidia/nemotron-3-super-120b-a12b").strip()
    modelo_planejado = (
        f"{_modelo_tarefa('web', mensagem)} -> {_modelo_web_writer(mensagem)}"
        if pediu_web
        else (f"{modelo_chat_nvidia} -> {modelo_conversa_groq}" if use_nv_chat else modelo_conversa_groq)
    )
    web_payload = contexto.get("busca_web") if isinstance(contexto.get("busca_web"), dict) else {}
    web_status = str((web_payload or {}).get("status") or "").strip().lower()
    web_itens = (web_payload or {}).get("itens") if isinstance(web_payload, dict) else []

    # Guardrail determinístico: quando o usuário pede internet e a tool não está operacional,
    # devolvemos status explícito sem "simular" busca.
    if pediu_web and (web_status in {"disabled", "missing_key", "rate_limited", "unsupported_provider", "error"} or not web_itens):
        mapa = {
            "disabled": "A busca na internet está desabilitada (NIK_WEB_ENABLED=false).",
            "missing_key": "A busca na internet está habilitada, mas falta configurar NIK_WEB_API_KEY.",
            "rate_limited": "A busca na internet atingiu limite temporário. Tente novamente em instantes.",
            "unsupported_provider": "O provider web configurado não é suportado nesta versão.",
            "error": "A busca na internet falhou nesta tentativa por erro de integração.",
        }
        detalhe = mapa.get(web_status, "Não encontrei fontes externas válidas para essa consulta nesta tentativa.")
        texto_web = (
            f"{detalhe} "
            "Se você quiser, eu já faço a busca assim que a integração web estiver operacional e retorno com links auditáveis."
        )
        return {
            "texto": texto_web,
            "fonte": "sistema",
            "modelo": None,
            "routing_mode": modo_routing,
            "routing_model": modelo_planejado,
            "modo_contexto": contexto.get("modo", "real"),
            "used_tools": contexto.get("used_tools", []),
            "data_sources": contexto.get("data_sources", []),
            "tool_trace": contexto.get("tool_trace", []),
            "citacoes": [],
            "fontes_web": [],
            "thread_id": thread,
            "web_status": web_status or "empty",
        }

    fontes_web = _fontes_web_contexto(contexto)
    sintese_web = _sintese_web_modelo(contexto, mensagem) if pediu_web else None
    if sintese_web:
        contexto["sintese_web"] = sintese_web
    pediu_documento = _mensagem_pede_documento(mensagem)
    if pediu_documento:
        resposta_doc = provider.chamar_modelo(
            prompts.SYSTEM_OPS_DOCUMENTO,
            prompts.montar_prompt_ops_documento(_contexto_para_modelo(contexto), mensagem),
            modelo=_modelo_tarefa("relatorio", mensagem),
            max_tokens=_ttl("NIK_MAX_TOKENS_DOCUMENTO", 1400),
            temperature=float(os.getenv("NIK_TEMPERATURE_DOCUMENTO", "0.2")),
            response_format={"type": "json_object"},
        )
        documento = val.validar_documento_chat(resposta_doc.texto) if resposta_doc.sucesso else None
        if not documento:
            documento = _fallback_documento_chat(mensagem, contexto)
        texto_doc = f"Documento pronto: {documento.get('titulo', 'Documento Nik')}"
        return {
            "texto": texto_doc,
            "fonte": "modelo" if resposta_doc.sucesso else "fallback",
            "modelo": resposta_doc.modelo_usado if resposta_doc.sucesso else None,
            "routing_mode": "documento",
            "routing_model": modelo_planejado if pediu_web else _modelo_tarefa("relatorio", mensagem),
            "modo_contexto": contexto.get("modo", "real"),
            "used_tools": contexto.get("used_tools", []),
            "data_sources": contexto.get("data_sources", []),
            "tool_trace": contexto.get("tool_trace", []),
            "citacoes": [],
            "fontes_web": fontes_web,
            "documento": documento,
            "thread_id": thread,
            "web_status": web_status or ("ok" if fontes_web else "n/a"),
        }

    fallback = (
        "Ainda não consegui interpretar essa pergunta com confiança. "
        "Se quiser, pergunte sobre operação do dia, alertas, coletores ou o impacto geral da Tronik."
    )
    if pediu_web:
        resposta = provider.chamar_modelo(
            prompts.SYSTEM_OPS_RELATORIO_PESQUISA_WEB,
            prompts.montar_prompt_ops_relatorio_pesquisa_web(_contexto_para_modelo(contexto), mensagem),
            modelo=_modelo_web_writer(mensagem),
            max_tokens=_ttl("NIK_MAX_TOKENS_WEB_RELATORIO", 1600),
            temperature=float(os.getenv("NIK_TEMPERATURE_WEB_RELATORIO", os.getenv("NIK_TEMPERATURE_OPS", "0.45"))),
        )
    else:
        resposta = provider.chamar_modelo(
            prompts.SYSTEM_OPS_CONVERSA,
            prompts.montar_prompt_ops_conversa(_contexto_para_modelo(contexto), mensagem),
            modelo=modelo_chat_nvidia if use_nv_chat else modelo_planejado,
            max_tokens=_ttl("NIK_MAX_TOKENS_CONVERSA", max(_ttl("NIK_MAX_TOKENS_OPS", 512), 420)),
            temperature=float(os.getenv("NIK_TEMPERATURE_OPS", "0.55")),
            prefer_nvidia_integrate_first=use_nv_chat,
            modelo_primario_se_sem_nv=modelo_conversa_groq if use_nv_chat else None,
        )
    if pediu_web and not resposta.sucesso and fontes_web:
        texto = _resumo_web_sem_modelo(fontes_web, mensagem)
        return {
            "texto": texto,
            "fonte": "sistema",
            "modelo": None,
            "routing_mode": modo_routing,
            "routing_model": modelo_planejado,
            "modo_contexto": contexto.get("modo", "real"),
            "used_tools": contexto.get("used_tools", []),
            "data_sources": contexto.get("data_sources", []),
            "tool_trace": contexto.get("tool_trace", []),
            "citacoes": [],
            "fontes_web": fontes_web,
            "thread_id": thread,
            "web_status": web_status or "ok",
        }

    max_chars = _ttl("NIK_MAX_CHARS_WEB_RELATORIO", 5200) if pediu_web else _ttl("NIK_MAX_CHARS_CONVERSA", 3200)
    texto = val.validar_resposta_ops(resposta.texto if resposta.sucesso else "", fallback, max_chars=max_chars)
    if fontes_web:
        texto = _remover_links_texto(texto)
    citacoes = _gerar_citacoes_por_bloco(texto, contexto)
    return {
        "texto": texto,
        "fonte": "modelo" if resposta.sucesso and texto != fallback else "fallback",
        "modelo": resposta.modelo_usado if resposta.sucesso else None,
        "routing_mode": modo_routing,
        "routing_model": modelo_planejado,
        "modo_contexto": contexto.get("modo", "real"),
        "used_tools": contexto.get("used_tools", []),
        "data_sources": contexto.get("data_sources", []),
        "tool_trace": contexto.get("tool_trace", []),
        "citacoes": citacoes,
        "fontes_web": fontes_web,
        "thread_id": thread,
        "web_status": web_status or ("ok" if fontes_web else "n/a"),
    }


def _extrair_anos(texto: str) -> list[int]:
    anos = re.findall(r"\b(20\d{2})\b", texto)
    return [int(a) for a in anos]


def _montar_contexto_conversa_integrada(
    db: Session,
    mensagem: str,
    usuario_id: Optional[int] = None,
    thread_id: str = "main",
) -> dict[str, Any]:
    consulta = _inferir_consulta_usuario(db, mensagem)
    plano = _planejar_ferramentas(mensagem)

    for item in plano:
        nome = item.get("nome")
        if nome == "resumo_periodo":
            if consulta.get("inicio"):
                item["kwargs"]["inicio"] = consulta["inicio"]
            if consulta.get("fim"):
                item["kwargs"]["fim"] = consulta["fim"]
            if consulta.get("parceiro_id"):
                item["kwargs"]["parceiro_id"] = consulta["parceiro_id"]
        if nome == "busca_unificada":
            if consulta.get("parceiro_id"):
                item["kwargs"]["parceiro_id"] = consulta["parceiro_id"]
        if nome in {"timeline_anual", "impacto_geral"}:
            if consulta.get("ano_inicio"):
                item["kwargs"]["ano_inicio"] = consulta["ano_inicio"]
            if consulta.get("ano_fim"):
                item["kwargs"]["ano_fim"] = consulta["ano_fim"]
            if consulta.get("parceiro_id"):
                item["kwargs"]["parceiro_id"] = consulta["parceiro_id"]

    if consulta.get("inicio") and consulta.get("fim") and not any(i.get("nome") == "resumo_periodo" for i in plano):
        plano.append({"nome": "resumo_periodo", "kwargs": {"inicio": consulta["inicio"], "fim": consulta["fim"], "parceiro_id": consulta.get("parceiro_id")}})

    contexto_exec, trace = _executar_plano_ferramentas(db, plano)
    contexto: dict[str, Any] = dict(contexto_exec)
    contexto["used_tools"] = [t["tool"] for t in trace if t.get("status") == "ok"]
    contexto["data_sources"] = [t["tool"] for t in trace if t.get("status") == "ok"]
    contexto["tool_trace"] = trace
    contexto["catalogo_ferramentas"] = nik_tools.catalogo_ferramentas()
    contexto["consulta_interpretada"] = consulta
    contexto["thread_id"] = thread_id
    contexto["historico_thread"] = _historico_thread(db, usuario_id, thread_id, limite=8)
    if _pedido_relatorio_ultimo_ano(mensagem):
        contexto["periodo_interpretado"] = "ultimo_ano_com_dados"
        contexto["nota_periodo"] = (
            "Quando a pergunta pede último ano, usar o último intervalo de 12 meses com dados efetivos na base."
        )
    return contexto


def salvar_conversa_ops(
    db: Session,
    usuario_id: Optional[int],
    pergunta: str,
    resposta_payload: dict[str, Any],
    thread_id: Optional[str] = None,
) -> dict[str, Any]:
    registro = NikConversa(
        usuario_id=usuario_id,
        thread_id=_normalizar_thread_id(thread_id),
        pergunta=(pergunta or "").strip(),
        resposta=resposta_payload.get("texto", ""),
        contexto_modo=resposta_payload.get("modo_contexto", "real"),
        modelo_usado=resposta_payload.get("modelo"),
        fonte=resposta_payload.get("fonte", "modelo"),
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)
    saida = dict(resposta_payload)
    saida["historico_id"] = registro.id
    return saida


def listar_conversas_ops(db: Session, usuario_id: Optional[int], limite: int = 20) -> list[dict[str, Any]]:
    q = db.query(NikConversa)
    if usuario_id is not None:
        q = q.filter(NikConversa.usuario_id == usuario_id)
    rows = q.order_by(NikConversa.criado_em.desc()).limit(max(1, min(limite, 50))).all()
    return [row.to_dict() for row in rows]


def listar_conversas_thread(
    db: Session,
    usuario_id: Optional[int],
    thread_id: Optional[str],
    limite: int = 50,
) -> list[dict[str, Any]]:
    tid = _normalizar_thread_id(thread_id)
    q = db.query(NikConversa).filter(NikConversa.thread_id == tid)
    if usuario_id is not None:
        q = q.filter(NikConversa.usuario_id == usuario_id)
    rows = q.order_by(NikConversa.criado_em.desc()).limit(max(1, min(limite, 100))).all()
    return [row.to_dict() for row in rows]


def _fallback_relatorio_maiara(contexto: dict[str, Any], formato: str) -> dict[str, Any]:
    resumo = contexto.get("resumo", {})
    periodo = contexto.get("periodo", {})
    top_coletor = contexto.get("top_coletor") or {}
    top_parceiro = contexto.get("top_parceiro") or {}
    eficiencia = (contexto.get("insights_base") or {}).get("eficiencia_kg_km", 0)
    metricas = [
        {
            "nome": "Total de coletas",
            "valor": str(resumo.get("total_coletas", 0)),
            "insight": "Mede o ritmo operacional do período.",
        },
        {
            "nome": "Volume coletado",
            "valor": f"{resumo.get('volume_kg', 0)} kg",
            "insight": "Indica a escala real de material movimentado.",
        },
        {
            "nome": "Quilometragem",
            "valor": f"{resumo.get('km_total', 0)} km",
            "insight": "Ajuda a avaliar custo logístico e desenho de rota.",
        },
        {
            "nome": "Eficiência kg/km",
            "valor": str(eficiencia),
            "insight": "Aproxima a relação entre massa movimentada e esforço logístico.",
        },
    ]
    titulo_prefixo = {
        "executivo": "Relatório executivo",
        "comercial": "Relatório comercial",
        "stakeholders": "Relatório para stakeholders",
    }.get(formato, "Relatório executivo")
    return {
        "titulo": f"{titulo_prefixo} Tronik · {periodo.get('inicio', '')} a {periodo.get('fim', '')}",
        "visao": formato,
        "resumo_executivo": (
            f"No período analisado, a operação registrou {resumo.get('total_coletas', 0)} coleta(s), "
            f"{resumo.get('volume_kg', 0)} kg movimentados e {resumo.get('km_total', 0)} km percorridos. "
            f"O principal coletor foi {top_coletor.get('nome', 'N/D')} e o maior volume por parceiro ficou com "
            f"{top_parceiro.get('nome', 'N/D')}. A leitura abaixo é um fallback estruturado para apoiar a Maiara mesmo quando a geração avançada não estiver disponível."
        ),
        "riscos": [
            "Oscilação de volume entre parceiros pode mascarar gargalos operacionais.",
            "Quilometragem elevada sem revisão de rota pressiona margem e combustível.",
        ],
        "oportunidades": [
            "Priorizar parceiros com maior volume pode elevar eficiência de coleta.",
            "Consolidar dados por período ajuda a preparar narrativa comercial e institucional.",
        ],
        "recomendacoes": [
            "Revisar os coletores com maior recorrência de coleta e avaliar redistribuição de capacidade.",
            "Cruzar volume, quilometragem e parceiro para identificar rotas e contratos mais rentáveis.",
        ],
        "metricas_chave": metricas,
    }


def _markdown_relatorio_maiara(relatorio: dict[str, Any]) -> str:
    linhas = [
        f"# {relatorio.get('titulo', 'Relatório Nik')}",
        "",
        "## Resumo executivo",
        relatorio.get("resumo_executivo", ""),
        "",
        "## Riscos",
    ]
    for item in relatorio.get("riscos", []):
        linhas.append(f"- {item}")
    linhas.extend(["", "## Oportunidades"])
    for item in relatorio.get("oportunidades", []):
        linhas.append(f"- {item}")
    linhas.extend(["", "## Recomendações"])
    for item in relatorio.get("recomendacoes", []):
        linhas.append(f"- {item}")
    linhas.extend(["", "## Métricas-chave"])
    for item in relatorio.get("metricas_chave", []):
        linhas.append(f"- **{item.get('nome')}**: {item.get('valor')} — {item.get('insight')}")
    return "\n".join(linhas)


def gerar_relatorio_maiara(
    db: Session,
    usuario_id: Optional[int],
    inicio: Optional[str],
    fim: Optional[str],
    parceiro_id: Optional[int],
    formato: str = "executivo",
) -> dict[str, Any]:
    formato = (formato or "executivo").strip().lower()
    if formato not in {"executivo", "comercial", "stakeholders"}:
        formato = "executivo"
    contexto = ctx.contexto_relatorio(db, inicio, fim, parceiro_id)
    cache_key = (
        f"nik:maiara:{formato}:{contexto['periodo']['inicio']}:{contexto['periodo']['fim']}:{parceiro_id or 'all'}:{usuario_id or 'anon'}"
    )
    cached = _cache_get(cache_key, _ttl("NIK_CACHE_TTL_RELATORIO_OPS", 3600))
    if cached:
        return cached
    resposta = provider.chamar_modelo(
        prompts.SYSTEM_MAIARA_RELATORIO,
        prompts.montar_prompt_maiara_relatorio(contexto, formato),
        modelo=_modelo_tarefa("relatorio"),
        max_tokens=max(_ttl("NIK_MAX_TOKENS_OPS", 512), 700),
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    relatorio = (
        val.validar_relatorio_maiara(resposta.texto)
        if resposta.sucesso
        else None
    )
    if not relatorio:
        relatorio = _fallback_relatorio_maiara(contexto, formato)
    else:
        relatorio["visao"] = formato

    markdown = _markdown_relatorio_maiara(relatorio)
    periodo_inicio = datetime.fromisoformat(contexto["periodo"]["inicio"])
    periodo_fim = datetime.combine(datetime.fromisoformat(contexto["periodo"]["fim"]).date(), time.max)

    registro = NikRelatorioGerado(
        usuario_id=usuario_id,
        parceiro_id=parceiro_id,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        formato=formato,
        titulo=relatorio["titulo"],
        conteudo_json=json.dumps(relatorio, ensure_ascii=False),
        conteudo_markdown=markdown,
        modelo_usado=resposta.modelo_usado if resposta.sucesso else None,
        fonte="modelo" if resposta.sucesso and val.validar_relatorio_maiara(resposta.texto) else "fallback",
    )
    db.add(registro)
    db.commit()
    db.refresh(registro)

    resultado = {
        "id": registro.id,
        "titulo": relatorio["titulo"],
        "visao": formato,
        "conteudo": relatorio,
        "markdown": markdown,
        "fonte": registro.fonte,
        "modelo": registro.modelo_usado,
        "periodo": contexto["periodo"],
        "parceiro_id": parceiro_id,
    }
    return _cache_set(cache_key, resultado)


def obter_relatorio_maiara(db: Session, relatorio_id: int) -> Optional[dict[str, Any]]:
    row = db.get(NikRelatorioGerado, relatorio_id)
    return row.to_dict() if row else None
