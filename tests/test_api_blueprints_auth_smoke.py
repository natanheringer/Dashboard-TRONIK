"""
Smoke: importação de todos os blueprints da API e regressão de auth (prospecção + CRM).
Garante que novos módulos não quebram o registro central nem expõem GETs sem login.
"""

import importlib

import pytest

API_BLUEPRINT_MODULES = [
    "rotas.api.auxiliares",
    "rotas.api.coletas",
    "rotas.api.coletores",
    "rotas.api.comercial",
    "rotas.api.contratos",
    "rotas.api.crm",
    "rotas.api.ml",
    "rotas.api.nik",
    "rotas.api.notificacoes",
    "rotas.api.prospeccao",
    "rotas.api.relatorios",
    "rotas.api.sensores",
]

# GETs que exigem sessão (prospecção + CRM + operacional/comercial + auxiliares)
PROTECTED_GET_PATHS = [
    "/api/prospeccao/candidatos",
    "/api/prospeccao/modelo-ativo",
    "/api/crm/pipeline",
    "/api/crm/funil",
    "/api/crm/estatisticas",
    "/api/crm/tarefas",
    "/api/coletores",
    "/api/coletas",
    "/api/comercial/dashboard",
    "/api/estatisticas",
    "/api/parceiros",
    "/api/tipos/material",
    "/api/tipos/sensor",
    "/api/tipos/coletor",
    "/api/configuracoes",
]

# GETs auxiliares que permanecem públicos (health probe)
PUBLIC_AUX_GET_PATHS = [
    "/api/health",
]


class TestApiBlueprintImports:
    @pytest.mark.parametrize("module_path", API_BLUEPRINT_MODULES)
    def test_import_module(self, module_path):
        mod = importlib.import_module(module_path)
        assert mod is not None

    def test_api_routes_registered_on_app(self, client):
        """Rotas de prospecção, CRM e operacional aparecem no url_map após import."""
        rules = {r.rule for r in client.application.url_map.iter_rules()}
        expected_paths = {
            "/api/prospeccao/candidatos",
            "/api/prospeccao/modelo-ativo",
            "/api/crm/pipeline",
            "/api/crm/estatisticas",
            "/api/coletores",
            "/api/coletas",
            "/api/comercial/dashboard",
        }
        missing = expected_paths - rules
        assert not missing, f"rotas ausentes no app: {missing}"


class TestProtectedEndpointsRequireLogin:
    @pytest.mark.parametrize("path", PROTECTED_GET_PATHS)
    def test_get_sem_sessao_retorna_nao_autorizado(self, client, path):
        resp = client.get(path)
        assert resp.status_code in {302, 401}, (
            f"{path} deveria exigir login, obteve {resp.status_code}"
        )


class TestPublicAuxEndpoints:
    @pytest.mark.parametrize("path", PUBLIC_AUX_GET_PATHS)
    def test_get_sem_sessao_permanece_publico(self, client, path):
        resp = client.get(path)
        assert resp.status_code == 200, (
            f"{path} deveria ser público, obteve {resp.status_code}"
        )
