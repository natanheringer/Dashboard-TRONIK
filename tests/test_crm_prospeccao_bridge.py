"""Tests for CRM ↔ prospection bridge."""

from unittest.mock import MagicMock, patch

from banco_dados.modelos import EmpresaCandidata, Pipeline, ScoreProspeccao
from banco_dados.services import prospeccao_crm_bridge


class TestBuscarCandidatosPorNomeEmpresa:
    def test_retorna_vazio_sem_nome_util(self):
        db = MagicMock()
        assert prospeccao_crm_bridge.buscar_candidatos_por_nome_empresa(db, "   ") == []

    @patch("banco_dados.services.prospeccao_crm_bridge.resolve_model")
    def test_retorna_vazio_sem_modelo_ativo(self, mock_resolve):
        mock_resolve.return_value = None
        db = MagicMock()
        assert prospeccao_crm_bridge.buscar_candidatos_por_nome_empresa(db, "Eco Recicla") == []

    @patch("banco_dados.services.prospeccao_crm_bridge.resolve_model")
    @patch("banco_dados.services.prospeccao_crm_bridge._percentile_map_for_score_ids")
    def test_filtra_por_nome_normalizado(self, mock_pct, mock_resolve):
        mock_resolve.return_value = MagicMock(id=1)
        mock_pct.return_value = {1: 100.0}

        empresa_match = EmpresaCandidata(
            id=10,
            cnpj="12345678000195",
            razao_social="Eco Recicla Ltda",
            nome_fantasia=None,
        )
        empresa_outra = EmpresaCandidata(
            id=11,
            cnpj="98765432000100",
            razao_social="Outra Empresa SA",
            nome_fantasia=None,
        )
        score_match = ScoreProspeccao(
            id=1,
            snapshot_id=1,
            modelo_id=1,
            empresa_id=10,
            qid="bairro:teste",
            score=0.9,
            ranking_contexto=1,
            prioridade="alta",
            motivos_json='["cnae_ree"]',
        )

        db = MagicMock()
        db.query.return_value.filter.return_value.limit.return_value.all.return_value = [(10,)]
        db.query.return_value.outerjoin.return_value.outerjoin.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            (score_match, empresa_match, None),
        ]

        resultado = prospeccao_crm_bridge.buscar_candidatos_por_nome_empresa(
            db, "eco recicla", limite=5
        )
        assert len(resultado) == 1
        assert resultado[0]["id"] == 1
        assert resultado[0]["match_source"] == "razao_social"
        assert resultado[0]["empresa"]["razao_social"] == "Eco Recicla Ltda"


class TestSqlLikeEscape:
    def test_escapa_curingas_like(self):
        assert prospeccao_crm_bridge._sql_like_contains("100%_off") == "%100\\%\\_off%"


class TestBuscarScoresParaPipeline:
    @patch("banco_dados.services.prospeccao_crm_bridge.buscar_candidatos_por_nome_empresa")
    @patch("banco_dados.services.prospeccao_xgb_service.explicar_candidato")
    def test_monta_payload_com_hints(self, mock_explain, mock_buscar):
        mock_buscar.return_value = [
            {
                "id": 7,
                "score": 0.88,
                "prioridade": "alta",
                "match_source": "razao_social",
                "motivos": ["porte_grande"],
                "empresa": {"razao_social": "Cliente Teste"},
            }
        ]
        mock_explain.return_value = {
            "score": {"id": 7},
            "explicacao": ["porte_grande", "cnae_ree"],
        }

        coletor = MagicMock()
        coletor.localizacao = "Cliente Teste"
        pipeline = Pipeline(id=3, status="lead", coletor_id=1, observacoes=None)
        pipeline.coletor = coletor

        db = MagicMock()
        db.query.return_value.options.return_value.filter_by.return_value.first.return_value = pipeline

        resultado = prospeccao_crm_bridge.buscar_scores_para_pipeline(db, 3)
        assert resultado is not None
        assert resultado["pipeline_id"] == 3
        assert resultado["scores"][0]["id"] == 7
        assert resultado["hints"][0]["score_id"] == 7
        assert resultado["hints"][0]["explicacao"] == ["porte_grande", "cnae_ree"]
        mock_buscar.assert_called_once_with(db, "Cliente Teste", limite=5, model_version=None)

    def test_pipeline_inexistente(self):
        db = MagicMock()
        db.query.return_value.options.return_value.filter_by.return_value.first.return_value = None
        assert prospeccao_crm_bridge.buscar_scores_para_pipeline(db, 999) is None


def test_pipeline_prospeccao_exige_login(client):
    resp = client.get("/api/crm/pipeline/1/prospeccao")
    assert resp.status_code in {302, 401}


def test_pipeline_prospeccao_autenticado(admin_client, monkeypatch):
    monkeypatch.setattr(
        "rotas.api.crm.buscar_scores_para_pipeline",
        lambda db, pipeline_id, model_version=None: {
            "pipeline_id": pipeline_id,
            "pipeline_status": "lead",
            "scores": [
                {
                    "id": 1,
                    "score": 0.9,
                    "prioridade": "alta",
                    "qid": "bairro:teste",
                    "empresa": {
                        "razao_social": "Eco Recicla Ltda",
                        "cnpj": "12345678000195",
                        "bairro": "Centro",
                    },
                }
            ],
            "hints": [{"score_id": 1, "explicacao": ["cnae_ree"]}],
        },
    )
    resp = admin_client.get("/api/crm/pipeline/42/prospeccao")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["dados"]["pipeline_id"] == 42
    assert body["dados"]["scores"][0]["id"] == 1
    assert body["dados"]["hints"][0]["explicacao"] == ["cnae_ree"]
    assert body["pipeline_id"] == 42
    assert body["scores"][0]["id"] == 1
    candidato = body["dados"]["candidato"]
    assert candidato["score_id"] == 1
    assert candidato["score"] == 0.9
    assert candidato["prioridade"] == "alta"
    assert candidato["empresa_nome"] == "Eco Recicla Ltda"
    assert candidato["empresa_cnpj"] == "12345678000195"
    assert candidato["bairro"] == "Centro"
    assert candidato["qid"] == "bairro:teste"


def test_pipeline_prospeccao_nao_encontrado(admin_client, monkeypatch):
    monkeypatch.setattr(
        "rotas.api.crm.buscar_scores_para_pipeline",
        lambda db, pipeline_id, model_version=None: None,
    )
    resp = admin_client.get("/api/crm/pipeline/99/prospeccao")
    assert resp.status_code == 404
    assert resp.get_json()["erro"] == "Pipeline não encontrado"
