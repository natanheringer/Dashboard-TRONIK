from datetime import date

from banco_dados.services import (
    nik_prompts,
    nik_provider as nik_provider_module,
    nik_service,
    nik_validacao as val,
)
from banco_dados.services.nik_provider import NikResposta


def test_nik_conversa_exige_texto(db_session):
    data = nik_service.conversar_ops(db_session, "")
    assert "Escreva uma pergunta" in data["texto"]


def test_detecta_pedido_ultimo_ano():
    assert nik_service._pedido_relatorio_ultimo_ano("gere um relatório do último ano")
    assert nik_service._pedido_relatorio_ultimo_ano("me dá resumo dos últimos 12 meses")
    assert not nik_service._pedido_relatorio_ultimo_ano("oi nik, tudo bem?")


def test_planejador_aciona_busca_unificada():
    plano = nik_service._planejar_ferramentas("procure contratos ativos da ceilandia")
    nomes = [p["nome"] for p in plano]
    assert "busca_unificada" in nomes


def test_planejador_aciona_listar_candidatos_prospeccao():
    plano = nik_service._planejar_ferramentas("liste os top 10 candidatos de prospecção com prioridade alta")
    nomes = [p["nome"] for p in plano]
    assert "listar_candidatos_prospeccao" in nomes
    item = next(p for p in plano if p["nome"] == "listar_candidatos_prospeccao")
    assert item["kwargs"].get("prioridade") == "alta"
    assert item["kwargs"].get("limite") == 10


def test_listar_candidatos_prospeccao_retorna_estrutura(db_session, monkeypatch):
    monkeypatch.setattr(
        nik_service.nik_tools.prospeccao_svc,
        "buscar_candidatos_prospeccao",
        lambda db, **kwargs: [{"id": 1, "prioridade": "alta", "ranking_contexto": 1}],
    )
    data = nik_service.nik_tools.ferramenta_listar_candidatos_prospeccao(
        db_session, limite=5, prioridade="alta"
    )
    assert data["total"] == 1
    assert data["candidatos"][0]["prioridade"] == "alta"
    assert "resumo" in data


def test_planejador_aciona_explicar_candidato_prospeccao():
    plano = nik_service._planejar_ferramentas("por que esse lead score_id=77 está no topo?")
    nomes = [p["nome"] for p in plano]
    assert "explicar_candidato_prospeccao" in nomes
    item = next(p for p in plano if p["nome"] == "explicar_candidato_prospeccao")
    assert item["kwargs"].get("score_id") == 77


def test_planejador_aciona_status_modelo_prospeccao():
    plano = nik_service._planejar_ferramentas("qual a versão do modelo de prospecção e as métricas?")
    nomes = [p["nome"] for p in plano]
    assert "status_modelo_prospeccao" in nomes


def test_planejador_aciona_cruzar_crm_compare_leads():
    plano = nik_service._planejar_ferramentas(
        "Compare os leads do CRM com os scores de prospecção REE"
    )
    nomes = [p["nome"] for p in plano]
    assert "cruzar_crm_prospeccao" in nomes
    item = next(p for p in plano if p["nome"] == "cruzar_crm_prospeccao")
    assert item["kwargs"].get("modo_global") is True
    assert "listar_candidatos_prospeccao" in nomes


def test_planejador_aciona_export_csv():
    plano = nik_service._planejar_ferramentas(
        "me envie o arquivo do Instituto Arapoti de janeiro a maio de 2026"
    )
    nomes = [p["nome"] for p in plano]
    assert "exportar_coletas_csv" in nomes


def test_grounding_bloqueia_numero_inventado():
    ctx = {"resumo": {"volume_kg": 5, "km_percorrido_km": 30}}
    texto = val.validar_resposta_ops(
        "O volume total é de 5 km para o parceiro.",
        "fallback",
        contexto=nik_prompts.rotular_unidades_contexto(ctx),
    )
    assert texto == "fallback"


def test_grounding_aceita_numero_do_contexto():
    ctx = {"resumo": {"volume_kg": 5, "km_percorrido_km": 30}}
    texto = val.validar_resposta_ops(
        "Volume coletado: 5 kg. Quilometragem: 30 km.",
        "fallback",
        contexto=nik_prompts.rotular_unidades_contexto(ctx),
    )
    assert texto != "fallback"
    assert "5 kg" in texto


def test_sanitizar_remove_emojis_ops():
    assert "😂" not in val.sanitizar_texto("Resultado ok 😂", remover_emoji=True)


def test_planejador_aciona_cruzar_crm_carteira():
    plano = nik_service._planejar_ferramentas(
        "Quais clientes do REE não estão na minha carteira?"
    )
    nomes = [p["nome"] for p in plano]
    assert "cruzar_crm_prospeccao" in nomes


def test_planejador_aciona_cruzar_crm_prospeccao_crm_e_prospeccao():
    plano = nik_service._planejar_ferramentas("cruze CRM e prospecção da empresa Acme Ltda")
    nomes = [p["nome"] for p in plano]
    assert "cruzar_crm_prospeccao" in nomes
    item = next(p for p in plano if p["nome"] == "cruzar_crm_prospeccao")
    assert item["kwargs"].get("empresa") == "Acme Ltda"


def test_planejador_aciona_cruzar_crm_prospeccao_lead_no_ranker():
    plano = nik_service._planejar_ferramentas("esse lead no ranker está no pipeline 15?")
    nomes = [p["nome"] for p in plano]
    assert "cruzar_crm_prospeccao" in nomes
    item = next(p for p in plano if p["nome"] == "cruzar_crm_prospeccao")
    assert item["kwargs"].get("pipeline_id") == 15


def test_planejador_aciona_cruzar_crm_pipeline_id():
    plano = nik_service._planejar_ferramentas("cruzamento CRM pipeline_id=42 com scores REE")
    nomes = [p["nome"] for p in plano]
    assert "cruzar_crm_prospeccao" in nomes
    item = next(p for p in plano if p["nome"] == "cruzar_crm_prospeccao")
    assert item["kwargs"].get("pipeline_id") == 42


def test_cruzar_crm_prospeccao_retorna_estrutura(db_session, monkeypatch):
    monkeypatch.setattr(
        nik_service.nik_tools.crm_bridge,
        "cruzar_crm_prospeccao",
        lambda db, **kwargs: {
            "encontrado": True,
            "pipeline_id": kwargs.get("pipeline_id") or 15,
            "empresa": {"id": 3, "razao_social": "Acme Ltda"},
            "scores_prospeccao": [{"id": 77, "prioridade": "alta", "ranking_contexto": 1}],
            "total_scores": 1,
            "resumo": "Cruzamento CRM ↔ prospecção: pipeline #15; empresa Acme Ltda; 1 score(s) REE.",
        },
    )
    data = nik_service.nik_tools.ferramenta_cruzar_crm_prospeccao(db_session, pipeline_id=15)
    assert data["encontrado"] is True
    assert data["pipeline_id"] == 15
    assert data["total_scores"] == 1
    assert "Acme" in data["resumo"]


def test_cruzar_crm_prospeccao_sem_parametros():
    data = nik_service.nik_tools.ferramenta_cruzar_crm_prospeccao(None)
    assert data["encontrado"] is False
    assert "pipeline_id" in data["resumo"]


def test_planejador_aciona_fila_ree():
    plano = nik_service._planejar_ferramentas("mostre a fila REE com prioridade alta")
    nomes = [p["nome"] for p in plano]
    assert "listar_candidatos_prospeccao" in nomes
    item = next(p for p in plano if p["nome"] == "listar_candidatos_prospeccao")
    assert item["kwargs"].get("prioridade") == "alta"


def test_explicar_candidato_prospeccao_retorna_estrutura(db_session, monkeypatch):
    monkeypatch.setattr(
        nik_service.nik_tools.prospeccao_svc,
        "explicar_candidato",
        lambda db, score_id, model_version=None: {
            "score": {
                "id": score_id,
                "prioridade": "alta",
                "motivos": [{"feature": "cnae_match", "peso": 0.4}],
                "empresa": {"razao_social": "Acme Ltda"},
            },
            "explicacao": [{"feature": "cnae_match", "peso": 0.4}],
        },
    )
    data = nik_service.nik_tools.ferramenta_explicar_candidato_prospeccao(db_session, score_id=12)
    assert data["encontrado"] is True
    assert data["score_id"] == 12
    assert len(data["explicacao"]) == 1
    assert "Acme" in data["resumo"]


def test_explicar_candidato_prospeccao_sem_score_id():
    data = nik_service.nik_tools.ferramenta_explicar_candidato_prospeccao(None, score_id=None)
    assert data["encontrado"] is False
    assert "score_id" in data["resumo"]


def test_status_modelo_prospeccao_retorna_estrutura(db_session, monkeypatch):
    monkeypatch.setattr(
        nik_service.nik_tools.prospeccao_svc,
        "status_modelo_prospeccao",
        lambda db, model_version=None: {
            "modelo": {"versao": "prospeccao-ree-v3.2", "ativo": True},
            "metricas": {"validation_ndcg_mean": 0.61},
            "total_scores": 120,
            "prioridade": {"alta": 10, "media": 80, "baixa": 30},
        },
    )
    data = nik_service.nik_tools.ferramenta_status_modelo_prospeccao(db_session)
    assert data["encontrado"] is True
    assert data["modelo"]["versao"] == "prospeccao-ree-v3.2"
    assert data["metricas"]["validation_ndcg_mean"] == 0.61
    assert data["total_scores"] == 120


def test_planejador_aciona_comparar_candidatos():
    plano = nik_service._planejar_ferramentas("compare os candidatos score_id=10 e score_id=20 lado a lado")
    nomes = [p["nome"] for p in plano]
    assert "comparar_candidatos" in nomes
    item = next(p for p in plano if p["nome"] == "comparar_candidatos")
    assert item["kwargs"].get("score_ids") == [10, 20]


def test_planejador_aciona_gerar_roteiro_contato():
    plano = nik_service._planejar_ferramentas("monte um script de ligação para o lead score_id=55")
    nomes = [p["nome"] for p in plano]
    assert "gerar_roteiro_contato" in nomes
    item = next(p for p in plano if p["nome"] == "gerar_roteiro_contato")
    assert item["kwargs"].get("score_id") == 55


def test_planejador_aciona_criar_tarefa_comercial():
    plano = nik_service._planejar_ferramentas(
        'criar tarefa "Ligar para Acme" pipeline_id=9 data_limite=2026-05-20'
    )
    nomes = [p["nome"] for p in plano]
    assert "criar_tarefa_comercial" in nomes
    item = next(p for p in plano if p["nome"] == "criar_tarefa_comercial")
    assert item["kwargs"].get("titulo") == "Ligar para Acme"
    assert item["kwargs"].get("pipeline_id") == 9
    assert item["kwargs"].get("data_limite") == "2026-05-20"


def test_comparar_candidatos_retorna_estrutura(db_session, monkeypatch):
    monkeypatch.setattr(
        nik_service.nik_tools.prospeccao_svc,
        "explicar_candidato",
        lambda db, score_id, model_version=None: {
            "score": {
                "id": score_id,
                "prioridade": "alta",
                "score": 0.91,
                "ranking_contexto": 1,
                "empresa": {"razao_social": f"Empresa {score_id}", "cnae_principal": "4751-2/01"},
                "local": {"bairro": "Asa Norte", "ra": "RA I"},
                "motivos": [{"feature": "cnae_match"}],
            },
            "explicacao": [],
        },
    )
    data = nik_service.nik_tools.ferramenta_comparar_candidatos(
        db_session, score_ids=[10, 20], limite=5
    )
    assert data["encontrado"] is True
    assert data["total"] == 2
    assert len(data["comparacao"]) == 2
    assert data["comparacao"][0]["cnae_principal"] == "4751-2/01"
    assert "motivos" in data["comparacao"][0]


def test_gerar_roteiro_contato_retorna_estrutura(db_session, monkeypatch):
    monkeypatch.setattr(
        nik_service.nik_tools.prospeccao_svc,
        "explicar_candidato",
        lambda db, score_id, model_version=None: {
            "score": {
                "id": score_id,
                "prioridade": "alta",
                "empresa": {"razao_social": "Loja Tech DF", "cnae_principal": "4752-1/00", "bairro": "Taguatinga"},
                "local": {"bairro": "Taguatinga", "ra": "RA III"},
                "motivos": [{"feature": "densidade_comercial"}],
            },
            "explicacao": [],
        },
    )
    data = nik_service.nik_tools.ferramenta_gerar_roteiro_contato(db_session, score_id=33)
    assert data["encontrado"] is True
    roteiro = data["roteiro"]
    assert "abertura" in roteiro
    assert "argumentos_ree" in roteiro
    assert len(roteiro["objecoes"]) >= 2
    assert "proximo_passo" in roteiro
    assert "Loja Tech" in data["resumo"]


def test_gerar_roteiro_contato_sem_parametros():
    data = nik_service.nik_tools.ferramenta_gerar_roteiro_contato(None)
    assert data["encontrado"] is False
    assert "score_id" in data["resumo"]


def test_criar_tarefa_comercial_mock_crm(db_session, monkeypatch):
    class TarefaFake:
        id = 99
        titulo = "Follow-up REE"
        pipeline_id = 7
        data_vencimento = None

        def to_dict(self):
            return {"id": self.id, "titulo": self.titulo}

    monkeypatch.setattr(
        nik_service.nik_tools.CRMService,
        "criar_tarefa",
        lambda dados, uid: TarefaFake(),
    )
    data = nik_service.nik_tools.ferramenta_criar_tarefa_comercial(
        db_session,
        "Follow-up REE",
        pipeline_id=7,
        usuario_id=1,
    )
    assert data["criado"] is True
    assert data["tarefa_id"] == 99
    assert "Follow-up" in data["resumo"]


def test_criar_tarefa_comercial_sem_usuario():
    data = nik_service.nik_tools.ferramenta_criar_tarefa_comercial(
        None, "Ligar amanhã", usuario_id=None
    )
    assert data["criado"] is False
    assert "Usuário" in data["resumo"]


def test_catalogo_ferramentas_inclui_novas_tools():
    nomes = {f["nome"] for f in nik_service.nik_tools.catalogo_ferramentas()}
    assert "comparar_candidatos" in nomes
    assert "gerar_roteiro_contato" in nomes
    assert "criar_tarefa_comercial" in nomes


def test_planejador_aciona_busca_web():
    plano = nik_service._planejar_ferramentas("me traga notícia atualizada na internet sobre lixo eletrônico")
    nomes = [p["nome"] for p in plano]
    assert "busca_web" in nomes
    assert "catalogo_fontes_web" in nomes


def test_planejador_aciona_busca_por_pergunta_exploratoria():
    plano = nik_service._planejar_ferramentas("quais contratos ativos temos em taguatinga")
    nomes = [p["nome"] for p in plano]
    assert "busca_unificada" in nomes


def test_periodo_ultimo_ano_com_dados(db_session, monkeypatch):
    monkeypatch.setattr(
        nik_service.nik_tools,
        "ferramenta_limites_historico",
        lambda db: {"inicio": "2023-01-01", "fim": "2024-03-31"},
    )
    periodo = nik_service._periodo_ultimo_ano_com_dados(db_session)
    assert periodo == {"inicio": "2023-04-01", "fim": "2024-03-31"}


def test_inferir_consulta_usuario_por_datas_explicitas(db_session, monkeypatch):
    monkeypatch.setattr(
        nik_service.nik_tools,
        "ferramenta_limites_historico",
        lambda db: {"inicio": "2023-01-01", "fim": "2024-03-31"},
    )
    monkeypatch.setattr(nik_service, "_extrair_parceiro_id_por_texto", lambda db, msg: None)
    consulta = nik_service._inferir_consulta_usuario(db_session, "relatório de 01/03/2024 até 31/03/2024")
    assert consulta["inicio"] == "2024-03-01"
    assert consulta["fim"] == "2024-03-31"
    assert consulta["ano_inicio"] == 2024
    assert consulta["ano_fim"] == 2024


def test_inferir_consulta_usuario_ultimos_dias(db_session, monkeypatch):
    monkeypatch.setattr(
        nik_service.nik_tools,
        "ferramenta_limites_historico",
        lambda db: {"inicio": "2023-01-01", "fim": "2024-03-31"},
    )
    monkeypatch.setattr(nik_service, "_extrair_parceiro_id_por_texto", lambda db, msg: None)
    consulta = nik_service._inferir_consulta_usuario(db_session, "quero resumo dos ultimos 10 dias")
    assert consulta["inicio"] == "2024-03-22"
    assert consulta["fim"] == "2024-03-31"


def test_inferir_consulta_usuario_mes_ano(db_session, monkeypatch):
    monkeypatch.setattr(
        nik_service.nik_tools,
        "ferramenta_limites_historico",
        lambda db: {"inicio": "2023-01-01", "fim": "2024-03-31"},
    )
    monkeypatch.setattr(nik_service, "_extrair_parceiro_id_por_texto", lambda db, msg: 7)
    consulta = nik_service._inferir_consulta_usuario(db_session, "relatorio de março 2024 do parceiro x")
    assert consulta["inicio"] == "2024-03-01"
    assert consulta["fim"] == "2024-03-31"
    assert consulta["parceiro_id"] == 7


def test_busca_unificada_retorna_estrutura(db_session):
    data = nik_service.nik_tools.ferramenta_busca_unificada(db_session, "coleta", limite=3)
    assert "itens" in data
    assert "resumo" in data
    assert "tokens" in data
    assert "cobertura" in data


def test_busca_web_desabilitada_por_padrao(db_session, monkeypatch):
    monkeypatch.setenv("NIK_WEB_ENABLED", "false")
    data = nik_service.nik_tools.ferramenta_busca_web(db_session, "logística reversa")
    assert data["status"] == "disabled"


def test_catalogo_fontes_web_tem_blocos():
    catalogo = nik_service.nik_tools.catalogo_fontes_web()
    assert "regulatorio" in catalogo
    assert "dados_publicos" in catalogo
    assert isinstance(catalogo["regulatorio"], list)


def test_gerar_bloco_landing_prefere_nemotron_integrate(monkeypatch):
    registros: list[dict] = []

    def fake_chamar(
        system_prompt,
        user_prompt,
        modelo=None,
        max_tokens=512,
        temperature=0.3,
        response_format=None,
        *,
        prefer_nvidia_integrate_first=False,
        modelo_primario_se_sem_nv=None,
    ):
        registros.append(
            {
                "modelo": modelo,
                "prefer_nvidia_integrate_first": prefer_nvidia_integrate_first,
                "modelo_primario_se_sem_nv": modelo_primario_se_sem_nv,
            }
        )
        return NikResposta(
            texto=(
                '{"titulo":"Reciclagem","corpo":"Texto educativo com tamanho mínimo para passar na validação.",'
                '"destaque":"ok"}'
            ),
            modelo_usado=modelo or "mistralai/mistral-nemotron",
            tokens_prompt=1,
            tokens_resposta=12,
            latencia_ms=5,
            sucesso=True,
        )

    monkeypatch.setattr(nik_provider_module, "chamar_modelo", fake_chamar)
    monkeypatch.setattr(nik_service, "_cache_get", lambda k, ttl: None)
    monkeypatch.setattr(nik_service, "_cache_set", lambda k, r: r)
    monkeypatch.setattr(nik_service, "_nik_habilitada", lambda: True)
    monkeypatch.setenv("NIK_LANDING_USE_NVIDIA", "true")
    monkeypatch.setenv("NIK_MODELO_LANDING_NVIDIA", "mistralai/mistral-nemotron")
    monkeypatch.setenv("NIK_MODELO_LANDING", "llama-3.1-8b-instant")

    out = nik_service.gerar_bloco_landing("fala_nik")
    assert len(registros) == 1
    assert registros[0]["modelo"] == "mistralai/mistral-nemotron"
    assert registros[0]["prefer_nvidia_integrate_first"] is True
    assert registros[0]["modelo_primario_se_sem_nv"] == "llama-3.1-8b-instant"
    assert out["fonte"] == "modelo"


def test_montar_queries_web_deterministico():
    q1 = nik_service.nik_tools._montar_queries_web("logística reversa de eletrônicos")
    q2 = nik_service.nik_tools._montar_queries_web("logística reversa de eletrônicos")
    assert q1 == q2
    assert len(q1) >= 1


def test_modelo_tarefa_rota_chat_vs_relatorio(monkeypatch):
    monkeypatch.setenv("NIK_MODELO_CHAT", "chat-8b")
    monkeypatch.setenv("NIK_MODELO_OPS", "chat-8b")
    monkeypatch.setenv("NIK_MODELO_RELATORIO", "report-heavy")
    monkeypatch.setenv("NIK_ROUTE_LONG_CONTEXT_TO_70B", "true")
    monkeypatch.setenv("NIK_MODELO_ANALYTICS", "scout-analytics")
    assert nik_service._modelo_tarefa("conversa", "oi") == "chat-8b"
    assert nik_service._modelo_tarefa("relatorio", "qualquer") == "report-heavy"
    long_msg = "x" * 901
    assert nik_service._modelo_tarefa("conversa", long_msg) == "scout-analytics"
    monkeypatch.setenv("NIK_MODELO_LONG_CONTEXT", "long-context-scout")
    assert nik_service._modelo_tarefa("conversa", long_msg) == "long-context-scout"


def test_modelo_tarefa_web_compound_vai_para_fallback_sem_70b(monkeypatch):
    monkeypatch.delenv("NIK_ALLOW_LLAMA_70B", raising=False)
    monkeypatch.setenv("NIK_MODELO_FALLBACK", "llama-3.1-8b-instant")
    monkeypatch.setenv("NIK_MODELO_WEB", "groq/compound-mini")
    monkeypatch.setenv("NIK_WEB_DISABLE_COMPOUND", "false")
    assert nik_service._modelo_tarefa("web", "busca na internet") == "llama-3.1-8b-instant"


def test_modelo_tarefa_web_compound_permitido_com_env(monkeypatch):
    monkeypatch.setenv("NIK_ALLOW_LLAMA_70B", "true")
    monkeypatch.setenv("NIK_MODELO_WEB", "compound-mini")
    monkeypatch.setenv("NIK_WEB_DISABLE_COMPOUND", "false")
    assert nik_service._modelo_tarefa("web", "busca na internet") == "compound-mini"


def test_modelo_web_writer_usa_env_ou_analytics(monkeypatch):
    monkeypatch.setenv("NIK_MODELO_ANALYTICS", "scout-17b")
    monkeypatch.delenv("NIK_MODELO_WEB_WRITER", raising=False)
    assert nik_service._modelo_web_writer("x") == "scout-17b"
    monkeypatch.setenv("NIK_MODELO_WEB_WRITER", "writer-custom")
    assert nik_service._modelo_web_writer("x") == "writer-custom"


def test_modelo_tarefa_web_safe(monkeypatch):
    monkeypatch.setenv("NIK_MODELO_WEB", "groq/compound-mini")
    monkeypatch.setenv("NIK_MODELO_WEB_SAFE", "llama-3.1-8b-instant")
    monkeypatch.setenv("NIK_WEB_DISABLE_COMPOUND", "true")
    assert nik_service._modelo_tarefa("web", "busca na internet") == "llama-3.1-8b-instant"


def test_relatorio_pesquisa_web_prompt_tem_estrutura():
    assert "OBJETIVO DA PESQUISA" in nik_prompts.SYSTEM_OPS_RELATORIO_PESQUISA_WEB
    assert "O QUE CADA FONTE INDICA" in nik_prompts.SYSTEM_OPS_RELATORIO_PESQUISA_WEB
    assert "CONCLUSÃO" in nik_prompts.SYSTEM_OPS_RELATORIO_PESQUISA_WEB


def test_mensagem_pede_web():
    assert nik_service._mensagem_pede_web("pesquise na web as noticias de reciclagem")
    assert nik_service._mensagem_pede_web("pesquise sobre reciclagem")
    assert not nik_service._mensagem_pede_web("quais contratos ativos temos?")


def test_resumo_web_sem_modelo():
    itens = [
        {
            "titulo": "Reciclagem no Brasil cresce",
            "url": "https://exemplo.com/a",
            "fonte": "exemplo.com",
            "snippet": "Volume subiu 12% no ano.",
        },
        {"titulo": "Dados públicos de resíduos", "url": "https://dados.gov.br/b", "fonte": "dados.gov.br"},
    ]
    texto = nik_service._resumo_web_sem_modelo("pesquise sobre reciclagem", itens)
    assert "Resumo automático" in texto
    assert "Reciclagem no Brasil cresce" in texto
    assert "Volume subiu" in texto


def test_mensagem_pede_documento():
    assert nik_service._mensagem_pede_documento("gere um documento com sumario sobre reciclagem")
    assert nik_service._mensagem_pede_documento("quero relatório detalhado estilo manus")
    assert not nik_service._mensagem_pede_documento("oi nik")


def test_remove_links_texto():
    texto = "Veja em https://exemplo.com e também www.teste.org para detalhes."
    limpo = nik_service._remover_links_texto(texto)
    assert "http" not in limpo.lower()
    assert "www." not in limpo.lower()


def test_nik_conversa_api(admin_client, monkeypatch):
    monkeypatch.setattr(
        nik_service,
        "conversar_ops_thread",
        lambda db, mensagem, thread_id=None, usuario_id=None: {
            "texto": f"Resposta para: {mensagem}",
            "fonte": "fallback",
            "modelo": None,
            "modo_contexto": "mock",
            "used_tools": ["snapshot_operacional"],
            "data_sources": ["snapshot_operacional"],
            "tool_trace": [{"tool": "snapshot_operacional", "status": "ok", "kwargs": {}}],
            "thread_id": thread_id or "main",
        },
    )
    resp = admin_client.post("/api/nik/ops/conversa", json={"mensagem": "Oi, Nik", "thread_id": "maiara"})
    assert resp.status_code == 200
    assert resp.get_json()["texto"] == "Resposta para: Oi, Nik"
    assert resp.get_json()["thread_id"] == "maiara"


def test_nik_historico_api(auth_client, monkeypatch):
    monkeypatch.setattr(
        nik_service,
        "listar_conversas_ops",
        lambda db, usuario_id, limite=20: [{"id": 1, "pergunta": "Oi", "resposta": "Olá"}],
    )
    resp = auth_client.get("/api/nik/ops/conversas")
    assert resp.status_code == 200
    assert resp.get_json()["itens"][0]["pergunta"] == "Oi"


def test_nik_historico_api_por_thread(auth_client, monkeypatch):
    monkeypatch.setattr(
        nik_service,
        "listar_conversas_thread",
        lambda db, usuario_id, thread_id, limite=50: [{"id": 2, "thread_id": thread_id, "pergunta": "Q", "resposta": "A"}],
    )
    resp = auth_client.get("/api/nik/ops/conversas?thread_id=maiara")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["thread_id"] == "maiara"
    assert body["itens"][0]["thread_id"] == "maiara"


def test_nik_maiara_relatorio_api(auth_client, monkeypatch):
    monkeypatch.setattr(
        nik_service,
        "gerar_relatorio_maiara",
        lambda db, usuario_id, inicio, fim, parceiro_id, formato="executivo": {
            "id": 7,
            "titulo": "Relatório executivo",
            "visao": formato,
            "conteudo": {
                "titulo": "Relatório executivo",
                "visao": formato,
                "resumo_executivo": "Resumo",
                "riscos": ["R1", "R2"],
                "oportunidades": ["O1", "O2"],
                "recomendacoes": ["C1", "C2"],
                "metricas_chave": [{"nome": "Coletas", "valor": "10", "insight": "ok"}],
            },
            "markdown": "# Relatório",
            "fonte": "fallback",
            "modelo": None,
            "periodo": {"inicio": "2026-01-01", "fim": "2026-01-31"},
            "parceiro_id": None,
        },
    )
    resp = auth_client.get("/api/nik/maiara/relatorio?inicio=2026-01-01&fim=2026-01-31")
    assert resp.status_code == 200
    assert resp.get_json()["conteudo"]["titulo"] == "Relatório executivo"


def test_nik_maiara_export_markdown(auth_client, monkeypatch):
    monkeypatch.setattr(
        nik_service,
        "obter_relatorio_maiara",
        lambda db, relatorio_id, **kwargs: {
            "conteudo": {"titulo": "Relatório"},
            "conteudo_markdown": "# Relatório",
        },
    )
    resp = auth_client.get("/api/nik/maiara/relatorio/7/export?formato=md")
    assert resp.status_code == 200
    assert "# Relatório" in resp.get_data(as_text=True)


def test_extrair_intervalo_meses_abreviado_sem_ano():
    ini, fim = nik_service._extrair_intervalo_meses(
        "me envie o arquivo do Instituto Arapoti de jan a mai'",
        ano_default=2026,
    )
    assert ini == date(2026, 1, 1)
    assert fim == date(2026, 5, 31)


def test_resposta_deterministica_fila_ree():
    contexto = {
        "listar_candidatos_prospeccao": {
            "total": 2,
            "resumo": "Fila de prospecção com 2 candidato(s) ranqueado(s).",
            "candidatos": [
                {
                    "score": -0.001,
                    "prioridade": "alta",
                    "ranking_contexto": 1,
                    "empresa": {"razao_social": "Empresa Alpha"},
                    "local": {"bairro": "Asa Norte"},
                },
                {
                    "score": -0.002,
                    "prioridade": "alta",
                    "ranking_contexto": 2,
                    "empresa": {"razao_social": "Empresa Beta"},
                    "local": {},
                },
            ],
        }
    }
    txt = nik_service._tentar_resposta_deterministica(
        "Liste os top candidatos REE da fila de prospecção",
        contexto,
    )
    assert txt is not None
    assert "Empresa Alpha" in txt
    assert "rank 1" in txt


def test_resposta_deterministica_status_modelo():
    contexto = {
        "status_modelo_prospeccao": {
            "encontrado": True,
            "resumo": "Modelo ativo v1 (100 scores publicados).",
            "modelo": {"versao": "v1", "feature_count": 42},
            "metricas": {"validation_ndcg_mean": 0.8123},
            "prioridade": {"alta": 10, "media": 5, "baixa": 2},
        }
    }
    txt = nik_service._tentar_resposta_deterministica("Status do modelo REE", contexto)
    assert txt is not None
    assert "Modelo ativo v1" in txt
    assert "NDCG" in txt


def test_payload_resposta_inclui_arquivo_export():
    contexto = {
        "exportar_coletas_csv": {
            "status": "ok",
            "download_url": "/api/nik/ops/export/token123",
            "filename": "coletas_2026-01-01_2026-05-31.csv",
            "total_linhas": 12,
            "periodo": {"inicio": "2026-01-01", "fim": "2026-05-31"},
        }
    }
    payload = nik_service._payload_resposta_ops({"texto": "ok"}, contexto)
    assert payload["arquivo_export"]["url"] == "/api/nik/ops/export/token123"
    assert payload["arquivo_export"]["total_linhas"] == 12

