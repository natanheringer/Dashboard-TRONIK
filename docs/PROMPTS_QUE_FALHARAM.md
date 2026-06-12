# Prompts que Falharam — Nik (Tronik Recicla)

Relato exigido no item 1.5 da entrega final. Os dois casos abaixo são reais e rastreáveis no
histórico do repositório (arquivo `banco_dados/services/nik_prompts.py`, commits `0d3dd7b` → `8b023ef`).

## Caso 1 — Análise de coletor: o modelo repetia o que o operador já via na tela

**Prompt original (v1):** o system prompt `SYSTEM_OPS_COLETOR` instruía o modelo com regras
negativas — "NÃO repita o que ele já vê (preenchimento %, data última coleta, etc.)" — e
misturava o exemplo de tom no meio das regras.

**Falha observada:** o modelo (Llama 3.3 70B via Groq) ignorava a proibição com frequência e
abria a resposta repetindo exatamente os números que já estavam no painel ("O coletor está em
92% de preenchimento..."), desperdiçando as 4 frases do limite sem interpretar nada.

**Ajuste:** reescrita v2 com regras positivas em vez de negativas — a tarefa passou a ser
"INTERPRETE: isso é normal para este coletor? É tendência ou padrão esperado?" — e o exemplo
de tom foi movido para um bloco `<exemplo>` separado das regras. A persona foi dividida em
`_CORE` (identidade) e `_VOZ` (estilo), reduzindo ~30-40% dos tokens por prompt.

**Validação:** comparação manual de respostas antes/depois com os mesmos dados de contexto
(mock e banco real), além da camada `nik_validacao.py`, que sanitiza e trunca todo output
antes de servir ao frontend. O critério de aceite: a primeira frase da resposta precisa conter
interpretação (tendência, comparação com a média), não um número já exibido na tela.

## Caso 2 — Blocos da landing: JSON quebrado por cercas de código e prosa extra

**Prompt original (v1):** o `SYSTEM_LANDING` pedia "Responda APENAS com JSON válido no formato
especificado. Sem texto antes ou depois do JSON", confiando só na instrução textual.

**Falha observada:** os modelos retornavam o JSON embrulhado em ```` ```json ... ``` ````,
com frases introdutórias ("Claro! Aqui está o bloco:") ou com campos faltando — o
`json.loads()` falhava e o bloco da landing não renderizava.

**Ajuste:** dois movimentos. (1) Passamos a usar `response_format={"type": "json_object"}`
da API (suportado pela Groq e pela NVIDIA Integrate), tirando a responsabilidade da instrução
textual. (2) Criamos uma persona `_PERSONA_JSON` sem a camada de estilo — output estruturado
não precisa de "tom de voz", e a camada de voz era justamente o que induzia o modelo a
adicionar prosa em volta do JSON.

**Validação:** a função `extrair_json_do_output()` em `nik_validacao.py` continua como rede de
segurança (remove cercas de código e extrai o primeiro `{...}` válido), e
`validar_resposta_landing()` verifica campos obrigatórios por tipo de bloco (`fala_nik` exige
`titulo` e `corpo`; `fato_reciclagem` exige `fato`; etc.). Bloco inválido → `None` → o frontend
oculta o container em vez de renderizar conteúdo quebrado. Casos cobertos por testes unitários
em `tests/test_nik_*.py`.

## Aprendizado transversal

Condicionais complexas dentro do prompt (ex.: "se o período estiver zerado...", "se houver
busca web...") também falhavam de forma intermitente. A solução foi tirar a lógica condicional
do prompt e movê-la para código (`nik_service.py` / `nik_contexto.py`): o prompt recebe apenas
o contexto já resolvido. Prompt é para interpretação; ramificação é para código.
