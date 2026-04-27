from banco_dados.services import nik_validacao as val


def test_sanitizar_texto_remove_html():
    texto = "<script>alert(1)</script> Olá   mundo "
    assert val.sanitizar_texto(texto) == "alert(1) Olá mundo"


def test_extrair_json_de_code_fence():
    bruto = '```json\n{"titulo":"Nik","corpo":"Teste"}\n```'
    assert val.extrair_json_do_output(bruto) == {"titulo": "Nik", "corpo": "Teste"}


def test_validar_resposta_landing_exige_campos():
    assert val.validar_resposta_landing('{"titulo":"Oi"}', "fala_nik") is None
