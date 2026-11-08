import json
import socket
import threading
import time
from types import SimpleNamespace

import httpx
import pytest
from langchain_core.documents import Document

from scripts import config, rag_components
from scripts.main import MOTIVO_TIEMPO_AGOTADO, LlamadaFallida, _invocar, _verificar_seccion
from tests.test_clasificacion import LIN, SECCION, VERIF, _clasif, _doc


class Cadena:
    """Cadena falsa: cada elemento es un mensaje a devolver o una excepción a lanzar (el último se repite)."""
    def __init__(self, *pasos):
        self.pasos, self.llamadas = list(pasos), 0

    def invoke(self, entrada):
        self.llamadas += 1
        paso = self.pasos.pop(0) if len(self.pasos) > 1 else self.pasos[0]
        if isinstance(paso, Exception):
            raise paso
        return paso


def _cortado():
    """JSON truncado por num_predict: Ollama informa done_reason 'length'."""
    return SimpleNamespace(content='{"oraciones": ["O1"], "explicacion": "no coin', response_metadata={"done_reason": "length"})


def _lento():
    """Lo que lanza el cliente cuando el servidor tarda más que el timeout."""
    return httpx.ReadTimeout("timed out")


def _correr(cv, cc, docs=None):
    llamadas = {"verificacion": 0, "clasificacion": 0}
    r = _verificar_seccion(SECCION, docs or [_doc()], cv, cc, cc, cc, LIN, {}, llamadas)
    return (*r, llamadas)


# --- _invocar ---

def test_un_fallo_se_reintenta_una_vez_y_se_cuenta():
    llamadas = {"verificacion": 0}
    cadena = Cadena(_lento(), VERIF)
    assert _invocar(cadena, {}, "S1", llamadas, "verificacion") is VERIF
    assert cadena.llamadas == 2 and llamadas == {"verificacion": 2, "fallidas": 1}


@pytest.mark.parametrize("fallo", [_lento(), _cortado(), TimeoutError()])
def test_dos_fallos_levantan_llamada_fallida_tras_exactamente_dos_intentos(fallo, caplog):
    llamadas = {"verificacion": 0}
    cadena = Cadena(fallo)
    with pytest.raises(LlamadaFallida):
        _invocar(cadena, {}, "S1 NORM_01 Art. 4.2", llamadas, "verificacion")
    assert cadena.llamadas == 2 and llamadas["fallidas"] == 2
    avisos = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert len(avisos) == 2 and "se reintenta" in avisos[0] and "se descarta el par" in avisos[1]   # una línea por reintento y por par descartado


def test_respuesta_normal_no_cuenta_fallos():
    llamadas = {"verificacion": 0}
    _invocar(Cadena(VERIF), {}, "S1", llamadas, "verificacion")
    assert llamadas == {"verificacion": 1}


# --- Verificación: el análisis sigue con el par siguiente ---

def test_llm_que_tarda_mas_del_timeout_descarta_el_par_y_sigue_con_el_siguiente():
    docs = [_doc(), _doc("NORM_05", "1.6", "Art. 1.6. X\nSe exigen 2 unidades.")]
    cv = Cadena(_lento(), _lento(), VERIF)   # primer par: dos intentos agotados; segundo par: responde
    cc = Cadena(_clasif())
    brechas, alertas, registro, llamadas = _correr(cv, cc, docs)
    assert registro[0]["estado"] == "tiempo_agotado" and registro[0]["articulo"] == "4.2" and registro[0]["motivo"] == MOTIVO_TIEMPO_AGOTADO
    assert len(alertas) == 1 and alertas[0]["motivo"] == "el modelo no respondió en el tiempo límite"
    assert (alertas[0]["norma"], alertas[0]["articulo"], alertas[0]["oraciones"]) == ("NORM_01", "4.2", ["O1"]) and alertas[0]["cita"]
    assert len(brechas) == 1 and brechas[0]["articulo"] == "1.6"   # el segundo par se procesó
    assert llamadas == {"verificacion": 3, "clasificacion": 1, "fallidas": 2}


def test_json_truncado_se_reintenta_y_si_vuelve_a_cortarse_se_informa_como_alerta():
    brechas, alertas, registro, llamadas = _correr(Cadena(_cortado()), Cadena(_clasif()))
    assert brechas == [] and registro[0]["estado"] == "tiempo_agotado" and len(alertas) == 1
    assert llamadas["fallidas"] == 2 and llamadas["verificacion"] == 2


def test_json_truncado_una_vez_y_luego_valido_sigue_normal():
    brechas, alertas, registro, llamadas = _correr(Cadena(_cortado(), VERIF), Cadena(_clasif()))
    assert len(brechas) == 1 and alertas == [] and llamadas["fallidas"] == 1


def test_timeout_en_el_reintento_por_formato_invalido_tambien_se_maneja():
    class LlmLento:
        def invoke(self, prompt):
            raise _lento()
    cv = Cadena(SimpleNamespace(content="no es json"))
    llamadas = {"verificacion": 0, "clasificacion": 0}
    brechas, alertas, registro = _verificar_seccion(SECCION, [_doc()], cv, Cadena(_clasif()), LlmLento(), LlmLento(), LIN, {}, llamadas)
    assert brechas == [] and registro[0]["estado"] == "tiempo_agotado" and len(alertas) == 1


# --- Clasificación ---

def test_clasificacion_que_no_responde_va_a_alertas_con_las_oraciones_de_la_verificacion():
    brechas, alertas, registro, llamadas = _correr(Cadena(VERIF), Cadena(_lento()))
    assert brechas == [] and llamadas == {"verificacion": 1, "clasificacion": 2, "fallidas": 2}
    assert registro[-1]["estado"] == "tiempo_agotado" and registro[-1]["etapa"] == "clasificacion"
    assert alertas[0]["motivo"] == MOTIVO_TIEMPO_AGOTADO and alertas[0]["oraciones"] == ["O1"] and alertas[0]["articulo"] == "4.2"


def test_clasificacion_cortada_una_vez_se_reintenta():
    cortada = SimpleNamespace(content='{"motivo": "m", "veredi', response_metadata={"done_reason": "length"})
    brechas, alertas, registro, llamadas = _correr(Cadena(VERIF), Cadena(cortada, _clasif()))
    assert len(brechas) == 1 and alertas == [] and llamadas["fallidas"] == 1


# --- Configuración de ChatOllama ---

def test_llm_de_ollama_lleva_timeout_y_tope_de_salida():
    llm = rag_components.get_llm_instance(config.OLLAMA_MODEL, num_predict=config.OLLAMA_NUM_PREDICT)
    assert llm.num_predict == 1024 and llm.client_kwargs == {"timeout": config.OLLAMA_TIMEOUT_S} == {"timeout": 240}
    assert config.OLLAMA_NUM_PREDICT_COMENTARIO == 400
    assert rag_components.get_llm_instance(config.OLLAMA_MODEL).num_predict is None   # el modo lista no se acota


def test_el_timeout_del_cliente_corta_a_un_servidor_que_no_responde():
    """ChatOllama real contra un socket que acepta y no contesta: tiene que lanzar un timeout, no colgarse."""
    servidor = socket.socket()
    servidor.bind(("127.0.0.1", 0))
    servidor.listen(1)
    conexiones = []
    threading.Thread(target=lambda: conexiones.append(servidor.accept()), daemon=True).start()
    try:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model="x", base_url=f"http://127.0.0.1:{servidor.getsockname()[1]}", client_kwargs={"timeout": 0.5})
        t0 = time.perf_counter()
        with pytest.raises((httpx.TimeoutException, TimeoutError)):
            llm.invoke("hola")
        assert time.perf_counter() - t0 < 10
    finally:
        servidor.close()


# --- Modo lista ---

LISTA_OK = SimpleNamespace(content=json.dumps({"riesgos_identificados": []}), response_metadata={"eval_count": 300, "prompt_eval_count": 900})


def test_lista_que_falla_dos_veces_deja_la_seccion_sin_riesgos_y_la_corrida_sigue(caplog):
    from scripts.main import _generar_lista
    llamadas = {"lista": 0}
    riesgos, mensaje = _generar_lista(Cadena(_lento()), {}, None, "S2", llamadas)
    assert riesgos == [] and mensaje is None and llamadas == {"lista": 2, "fallidas": 2}
    assert any("S2" in r.message and "sin riesgos" in r.message for r in caplog.records if r.levelname == "WARNING")
    # la sección siguiente se procesa normalmente
    riesgos, mensaje = _generar_lista(Cadena(LISTA_OK), {}, None, "S3", llamadas)
    assert riesgos == [] and mensaje is LISTA_OK


def test_lista_cortada_por_largo_se_reintenta_una_vez():
    from scripts.main import _generar_lista
    llamadas = {"lista": 0}
    _, mensaje = _generar_lista(Cadena(_cortado(), LISTA_OK), {}, None, "S1", llamadas)
    assert mensaje is LISTA_OK and llamadas["fallidas"] == 1


def test_el_modo_lista_tiene_su_propio_tope():
    assert config.OLLAMA_NUM_PREDICT_LISTA == 2048


# --- eval_count ---

def test_eval_count_queda_en_el_registro_y_en_las_estadisticas():
    from scripts.main import _estadisticas_tokens
    verif = SimpleNamespace(content=VERIF.content, response_metadata={"eval_count": 120})
    clasif = SimpleNamespace(content=_clasif().content, response_metadata={"eval_count": 480})
    brechas, alertas, registro, llamadas = _correr(Cadena(verif), Cadena(clasif))
    assert registro[0]["eval_count"] == 120 and brechas[0]["eval_count"] == 480
    assert _estadisticas_tokens(llamadas) == {"verificacion": {"n": 1, "max": 120, "promedio": 120.0},
                                              "clasificacion": {"n": 1, "max": 480, "promedio": 480.0}}


def test_estadisticas_max_y_promedio_por_tipo():
    from scripts.main import _estadisticas_tokens
    assert _estadisticas_tokens({"eval_count": {"verificacion": [100, 300], "clasificacion": []}}) == {"verificacion": {"n": 2, "max": 300, "promedio": 200.0}}
    assert _estadisticas_tokens({}) == {}
