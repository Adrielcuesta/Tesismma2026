import importlib.util
import os

import pytest

from scripts import config, rag_components, recuperar
from scripts.schemas import VerificacionArticulo

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)


@pytest.fixture
def app_mod(tmp_path, monkeypatch):
    """app.py importado sin descargar nada: el modelo de embeddings «existe» (una carpeta temporal)."""
    monkeypatch.setattr(config, "LOCAL_EMBEDDING_MODEL_PATH", str(tmp_path))
    spec = importlib.util.spec_from_file_location("app_bajo_prueba", os.path.join(RAIZ, "app.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulo.app.config["TESTING"] = True
    return modulo


def test_la_configuracion_del_mvp_es_el_perfil_elegido_con_gpt_oss_y_el_local_como_opcion():
    assert config.PERFIL_APP_DEFECTO == "elegido" and config.PERFIL_ELEGIDO_CARGADO is True
    assert config.MODELO_APP_DEFECTO == "openai/gpt-oss-120b" and config.MODELOS_APP == ("openai/gpt-oss-120b", config.OLLAMA_MODEL)
    assert config.LLM_MODELS["openai/gpt-oss-120b"]["provider"] == "deepinfra" and config.LLM_MODELS["openai/gpt-oss-120b"]["api_key_env"] == "DEEPINFRA_API_KEY"
    assert "openai/gpt-oss-120b" in config.PRECIOS_NUBE and "openai/gpt-oss-120b" in config.NUBE_MODELOS_RAZONAMIENTO_FIJO     # sin precio no arranca


def test_la_interfaz_ofrece_solo_gpt_oss_primero_y_el_modelo_local(app_mod):
    html = app_mod.app.test_client().get("/").get_data(as_text=True)
    opciones = [l for l in html.splitlines() if "<option" in l]
    assert len(opciones) == 2
    assert 'value="openai/gpt-oss-120b"' in opciones[0] and f'value="{config.OLLAMA_MODEL}"' in opciones[1]      # la primera opción es la que queda seleccionada


def test_analizar_aplica_el_perfil_elegido_y_llama_a_run_analysis_con_el_modelo_elegido(app_mod, monkeypatch):
    aplicados, llamadas = [], []
    monkeypatch.setattr(app_mod.recuperar, "aplicar_perfil", lambda nombre: aplicados.append(nombre) or {})
    monkeypatch.setattr(app_mod, "run_analysis", lambda **kw: llamadas.append(kw) or "README.md")
    r = app_mod.app.test_client().post("/analyze", data={"llm_model": config.MODELO_APP_DEFECTO, "use_default_kb": "yes", "use_existing_project_file": "yes"})
    assert r.status_code == 200
    assert aplicados == ["elegido"]
    assert llamadas == [{"selected_llm_model_id": "openai/gpt-oss-120b", "directorio_kb": None, "directorio_proyecto": None}]
    r.close()
    llamadas.clear(); aplicados.clear()
    app_mod.app.test_client().post("/analyze", data={"llm_model": config.OLLAMA_MODEL, "use_default_kb": "yes", "use_existing_project_file": "yes"}).close()
    assert aplicados == ["elegido"] and llamadas[0]["selected_llm_model_id"] == config.OLLAMA_MODEL           # el local usa el mismo perfil


def test_aplicar_el_perfil_elegido_deja_la_recuperacion_medida():
    previo = {k: getattr(config, k) for k in config.PERFILES_RECUPERACION["elegido"]}
    try:
        recuperar.aplicar_perfil("elegido")
        assert (config.K_SUBSECCION, config.TOP_DENSA_SUBSECCION, config.TOP_N_SUBSECCION, config.VERIFICAR_TOPE) == (10, 10, 0, 39)
        assert (config.ORACIONES_N, config.ORACIONES_CUPO, config.EMBEDDING_BACKEND) == (2, 15, "bge-m3")
    finally:
        for k, v in previo.items():
            setattr(config, k, v)


def test_get_llm_instance_deepinfra_arma_el_cliente_de_nube_con_json_schema_estricto(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "clave-de-prueba")
    runnable = rag_components.get_llm_instance("openai/gpt-oss-120b", formato=VerificacionArticulo.model_json_schema(), num_predict=1024)
    assert hasattr(runnable, "invoke")
    llm = rag_components.get_llm_openai_compatible("deepinfra", "openai/gpt-oss-120b", esquema=VerificacionArticulo.model_json_schema())
    rf = llm.model_kwargs["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True and rf["json_schema"]["name"] == "VerificacionArticulo"
    # el comentario general es texto libre: sin response_format
    assert "response_format" not in rag_components.get_llm_openai_compatible("deepinfra", "openai/gpt-oss-120b", texto=True).model_kwargs
    # con una clase pydantic sigue igual que antes
    assert rag_components.get_llm_openai_compatible("deepinfra", "openai/gpt-oss-120b", esquema=VerificacionArticulo).model_kwargs["response_format"]["json_schema"]["name"] == "VerificacionArticulo"


def test_get_llm_instance_deepinfra_sin_clave_falla_con_un_mensaje_claro(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DEEPINFRA|Clave API"):
        rag_components.get_llm_instance("openai/gpt-oss-120b", formato={"title": "X"})
