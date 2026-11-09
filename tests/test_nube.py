import json
import os

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage

from scripts import config, nube, rag_components
from scripts.main import LlamadaFallida, _parsear_respuesta_llm, normalizar_tipos_vacios, normalizaciones_formato
from scripts.schemas import ClasificacionRiesgo, VerificacionArticulo

with open(os.path.join(os.path.dirname(__file__), "fixtures", "criterios_empresa.json"), encoding="utf-8") as f:
    C = json.load(f)
LIN = {"criterios": C, "texto_para_el_modelo": "<criterios inventados>", "huella": "h" * 64}
PRECIOS = {"entrada": 1.0, "salida": 2.0}      # USD por millón de tokens
NO_APLICA = json.dumps({"oraciones": [], "explicacion": "no la menciona", "veredicto": "No aplica"})


class LLMFalso:
    """Devuelve siempre `contenido` con el uso de tokens de una respuesta de la API; no llama a ninguna red."""
    def __init__(self, contenido=NO_APLICA, error=None):
        self.contenido, self.error, self.llamadas = contenido, error, 0

    def invoke(self, entrada):
        self.llamadas += 1
        if self.error:
            raise self.error
        return AIMessage(content=self.contenido, usage_metadata={"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100,
                                                                 "input_token_details": {"cache_read": 400}},
                         response_metadata={"finish_reason": "stop"})


def _seccion(n):
    texto = f"La oferta {n} incluye una unidad."
    return {"id": f"S{n}", "titulos": [f"{n} Alcance"], "subsecciones": [(f"{n}.1 Apoyos", texto)], "texto": texto}


def _indice():
    pares = [("NORM_01", "4.2"), ("NORM_02", "5.1"), ("NORM_03", "2.4"), ("NORM_01", "1.1")]
    return nube.indice_de_articulos({"documents": [f"Art. {a}. texto" for _, a in pares],
                                     "metadatas": [{"norma": n, "articulo": a, "parte": 1} for n, a in pares]})


LOCAL = {"secciones": [
    {"id": "S1", "titulos": ["1 Alcance"], "fragmentos": [{"norma": "NORM_02", "articulo": "5.1", "score": 0.9}, {"norma": "NORM_01", "articulo": "4.2", "score": 0.8}]},
    {"id": "S2", "titulos": ["2 Alcance"], "fragmentos": []},
    {"id": "S3", "titulos": ["3 Alcance"], "fragmentos": [{"norma": "NORM_03", "articulo": "2.4", "score": 0.7}, {"norma": "NORM_01", "articulo": "1.1", "score": 0.6}]},
]}


def _docs():
    return {s["id"]: nube.documentos_de_seccion(s["fragmentos"], _indice()) for s in LOCAL["secciones"]}


# --- Cliente y perfiles ---

def test_el_cliente_usa_el_perfil_temperatura_0_seed_json_y_sin_razonamiento(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "clave-falsa")
    llm = rag_components.get_llm_openai_compatible("deepinfra", "Qwen/Qwen3-32B")
    assert llm.openai_api_base == "https://api.deepinfra.com/v1/openai" and llm.temperature == 0 and llm.seed == config.OLLAMA_SEED
    assert llm.max_retries == 5 and llm.model_kwargs["response_format"] == {"type": "json_object"}
    assert llm.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}
    pensando = rag_components.get_llm_openai_compatible("deepinfra", "Qwen/Qwen3-32B", razonamiento=True)
    assert pensando.extra_body == {"chat_template_kwargs": {"enable_thinking": True}} and pensando.temperature == config.VERIF_TEMPERATURE
    monkeypatch.setenv("GROQ_API_KEY", "otra")
    assert rag_components.get_llm_openai_compatible("groq", "m").openai_api_base == "https://api.groq.com/openai/v1"


def test_sin_clave_o_con_proveedor_desconocido_falla(monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DEEPINFRA_API_KEY"):
        rag_components.get_llm_openai_compatible("deepinfra", "Qwen/Qwen3-32B")
    with pytest.raises(ValueError, match="desconocido"):
        rag_components.get_llm_openai_compatible("otro", "m")


def test_gasto_calcula_el_costo_y_frena_al_llegar_al_tope():
    g = nube.Gasto(PRECIOS, 0.003)
    g.registrar(1_000_000, 0)
    assert g.usd == pytest.approx(1.0)
    g = nube.Gasto(PRECIOS, 0.003)
    g.verificar()
    g.registrar(1000, 1000, 400)      # 0,001 + 0,002 = 0,003
    assert g.usd == pytest.approx(0.003) and g.cacheados == 400
    with pytest.raises(nube.PresupuestoAgotado):
        g.verificar()


def test_cliente_toma_los_tokens_de_usage_y_los_deja_donde_los_lee_main():
    g = nube.Gasto(PRECIOS, 4.0)
    m = nube.ClienteNube(LLMFalso(), g).invocar("hola")
    assert (m.response_metadata["prompt_eval_count"], m.response_metadata["eval_count"], m.response_metadata["done_reason"]) == (1000, 100, "stop")
    assert (g.entrada, g.salida, g.cacheados, g.llamadas) == (1000, 100, 400, 1)


def test_el_corte_por_largo_se_marca_length():
    llm = LLMFalso()
    llm.invoke = lambda e: AIMessage(content="{", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}, response_metadata={"finish_reason": "length"})
    assert nube.ClienteNube(llm, nube.Gasto(PRECIOS, 4.0)).invocar("x").response_metadata["done_reason"] == "length"


def test_429_y_5xx_que_el_cliente_no_resolvio_son_llamada_fallida_y_otros_errores_propagan():
    pedido = httpx.Request("POST", "http://x")
    limite = openai.RateLimitError("limite", response=httpx.Response(429, request=pedido), body=None)
    servidor = openai.InternalServerError("caido", response=httpx.Response(503, request=pedido), body=None)
    malo = openai.BadRequestError("formato", response=httpx.Response(400, request=pedido), body=None)
    for error in (limite, servidor):
        with pytest.raises(LlamadaFallida):
            nube.ClienteNube(LLMFalso(error=error), nube.Gasto(PRECIOS, 4.0)).invocar("x")
    with pytest.raises(openai.BadRequestError):
        nube.ClienteNube(LLMFalso(error=malo), nube.Gasto(PRECIOS, 4.0)).invocar("x")


def _error_largo():
    usage = type("U", (), {"prompt_tokens": 150, "completion_tokens": 1024})()
    return openai.LengthFinishReasonError(completion=type("C", (), {"usage": usage})())


def test_length_finish_reason_error_se_convierte_en_mensaje_cortado_y_cobra_los_tokens():
    g = nube.Gasto(PRECIOS, 4.0)
    m = nube.ClienteNube(LLMFalso(error=_error_largo()), g).invocar("x")
    assert m.response_metadata["done_reason"] == "length" and m.content == ""
    assert (g.entrada, g.salida) == (150, 1024)


def test_un_par_truncado_no_corta_la_corrida_y_queda_registrado_y_contado():
    llm = LLMFalso(error=_error_largo())
    cliente = nube.ClienteNube(llm, nube.Gasto(PRECIOS, 4.0))
    resultados = nube.ejecutar_secciones([_seccion(1), _seccion(3)], _docs(), cliente, cliente, LIN, concurrencia=1)
    assert [i for i, _ in resultados] == ["S1", "S3"]
    registro = [r for _, res in resultados for r in res["registro"]]
    assert len(registro) == 4 and all(r["estado"] == "tiempo_agotado" for r in registro)
    assert sum(res["llamadas"]["fallidas"] for _, res in resultados) == 8      # 4 pares x 2 intentos


def test_reintento_de_formato_truncado_descarta_el_par_y_lo_cuenta_como_fallida():
    class LLMInvalidoYLargo(LLMFalso):
        def invoke(self, entrada):
            self.llamadas += 1
            if isinstance(entrada, str):        # el reintento de formato (prompt en texto) se corta por largo
                raise _error_largo()
            return AIMessage(content="no es json", response_metadata={"finish_reason": "stop"})
    cliente = nube.ClienteNube(LLMInvalidoYLargo(), nube.Gasto(PRECIOS, 4.0))
    [(_, res)] = nube.ejecutar_secciones([_seccion(1)], {"S1": _docs()["S1"][:1]}, cliente, cliente, LIN, concurrencia=1)
    assert res["registro"][0]["estado"] == "descartada" and res["registro"][0]["motivo"].startswith("formato inválido")
    assert res["llamadas"]["fallidas"] == 1


def test_un_error_inesperado_en_una_seccion_la_marca_y_las_demas_siguen():
    class LLMRoto(LLMFalso):
        def invoke(self, entrada):
            if self.llamadas == 0:
                self.llamadas += 1
                raise RuntimeError("falla rara")
            return super().invoke(entrada)
    cliente = nube.ClienteNube(LLMRoto(), nube.Gasto(PRECIOS, 4.0))
    resultados = nube.ejecutar_secciones([_seccion(1), _seccion(3)], _docs(), cliente, cliente, LIN, concurrencia=1)
    assert resultados[0][1]["registro"][0]["estado"] == "seccion_fallida" and resultados[0][1]["incompleta"] is False
    assert [r["veredicto"] for r in resultados[1][1]["registro"]] == ["No aplica", "No aplica"]


def test_sin_presupuesto_no_llama_al_modelo():
    llm = LLMFalso()
    g = nube.Gasto(PRECIOS, 0.0)
    with pytest.raises(nube.PresupuestoAgotado):
        nube.ClienteNube(llm, g).invocar("x")
    assert llm.llamadas == 0


# --- Recuperación reusada y ejecución ---

def test_los_pares_verificados_son_identicos_a_los_del_json_y_en_el_mismo_orden():
    docs = _docs()
    assert [d.page_content for d in docs["S1"]] == ["Art. 5.1. texto", "Art. 4.2. texto"] and docs["S2"] == []
    llm = LLMFalso()
    cliente = nube.ClienteNube(llm, nube.Gasto(PRECIOS, 4.0))
    resultados = nube.ejecutar_secciones([_seccion(1), _seccion(2), _seccion(3)], docs, cliente, cliente, LIN, concurrencia=8)
    verificados = [(r["seccion"], r["norma"], r["articulo"]) for _, res in resultados for r in res["registro"] if not r.get("etapa")]
    assert verificados == nube.pares_de_json(LOCAL) and [i for i, _ in resultados] == ["S1", "S3"]
    assert llm.llamadas == 4


def test_articulo_que_no_esta_en_chroma_es_un_error_claro():
    with pytest.raises(nube.AnalisisError, match="NORM_09 Art. 1.1"):
        nube.documentos_de_seccion([{"norma": "NORM_09", "articulo": "1.1"}], _indice())


def test_articulo_con_varias_partes_repetido_toma_una_parte_por_repeticion_y_avisa():
    indice = nube.indice_de_articulos({"documents": ["p2", "p1"], "metadatas": [{"norma": "N", "articulo": "1", "parte": 2}, {"norma": "N", "articulo": "1", "parte": 1}]})
    avisos = []
    docs = nube.documentos_de_seccion([{"norma": "N", "articulo": "1"}, {"norma": "N", "articulo": "1"}], indice, avisos)
    assert [d.page_content for d in docs] == ["p1", "p2"] and avisos == [("N", "1")]


def test_max_pares_se_queda_con_los_primeros_n_en_orden():
    docs = nube.limitar_pares(_docs(), ["S1", "S2", "S3"], 3)
    assert [len(docs[s]) for s in ("S1", "S2", "S3")] == [2, 0, 1]
    assert [len(v) for v in nube.limitar_pares(_docs(), ["S1", "S2", "S3"], None).values()] == [2, 0, 2]


def test_al_alcanzar_el_presupuesto_las_secciones_quedan_incompletas_y_se_informa():
    g = nube.Gasto(PRECIOS, 0.0005)    # la primera llamada (0,0012 USD) ya lo supera
    resultados = nube.ejecutar_secciones([_seccion(1), _seccion(3)], _docs(), nube.ClienteNube(LLMFalso(), g), nube.ClienteNube(LLMFalso(), g), LIN, concurrencia=1)
    assert [r["incompleta"] for _, r in resultados] == [True, True]      # la 1.ª llamada pasa el tope: la 2.ª de S1 y todo S3 se frenan
    assert resultados[1][1]["registro"][0]["estado"] == "presupuesto_agotado"


def test_resumen_de_humo_cuenta_json_bien_parseado():
    registro = [{"veredicto": "Cumple"}, {"veredicto": None, "estado": "descartada", "motivo": "formato inválido tras reintentar: x"}, {"etapa": "clasificacion", "veredicto": "DESVIO"}]
    r = nube.resumen_humo(registro, {"usd": 0.01})
    assert (r["pares"], r["json_ok"], r["json_invalido"], r["usd"]) == (2, 1, 1, 0.01)


def test_sufijo_del_archivo_lleva_el_proveedor_y_el_modelo():
    assert nube.sufijo_modelo("deepinfra", "Qwen/Qwen3-32B") == "deepinfra-qwen3-32b"
    assert nube.sufijo_modelo("deepinfra", "Qwen/Qwen3-235B-A22B-Instruct-2507") == "deepinfra-qwen3-235b-a22b-instruct-2507"


def test_con_esquema_el_cliente_pide_json_schema_estricto_igual_que_el_format_de_ollama(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "clave-falsa")
    for esquema in (VerificacionArticulo, ClasificacionRiesgo):
        rf = rag_components.get_llm_openai_compatible("deepinfra", "Qwen/Qwen3-32B", esquema=esquema).model_kwargs["response_format"]
        assert rf == {"type": "json_schema", "json_schema": {"name": esquema.__name__, "schema": esquema.model_json_schema(), "strict": True}}


def _error_400():
    return openai.BadRequestError("json_schema no soportado", response=httpx.Response(400, request=httpx.Request("POST", "http://x")), body=None)


def test_si_el_proveedor_rechaza_json_schema_cae_a_json_object_y_lo_avisa(caplog):
    g = nube.Gasto(PRECIOS, 4.0)
    primario, respaldo = LLMFalso(error=_error_400()), LLMFalso()
    c = nube.ClienteNube(primario, g, respaldo=respaldo, nombre="VerificacionArticulo")
    assert c.formato == "json_schema"
    with caplog.at_level("WARNING"):
        c.invocar("x")
        c.invocar("y")
    assert c.formato == "json_object (respaldo)" and primario.llamadas == 1 and respaldo.llamadas == 2    # el rechazo se prueba una sola vez
    assert sum("json_schema" in r.message for r in caplog.records) == 1


def test_si_tambien_falla_el_respaldo_no_se_cambia_de_formato():
    c = nube.ClienteNube(LLMFalso(error=_error_400()), nube.Gasto(PRECIOS, 4.0), respaldo=LLMFalso(error=_error_400()))
    with pytest.raises(openai.BadRequestError):
        c.invocar("x")
    assert c.formato == "json_schema"


# --- Normalización de tipos vacíos (red de seguridad) ---

VALIDA = {"oraciones": ["O1"], "dato_oferta": "dice 5", "requisitos": ["r"], "valor_oferta": 5, "valor_norma": 10, "operador": ">=", "unidad": "mm",
          "explicacion": "e", "veredicto": "Incumple", "motivo_duda": None}


def test_normalizar_es_un_no_op_con_una_respuesta_valida():
    for esquema, datos in ((VerificacionArticulo, VALIDA), (VerificacionArticulo, {**VALIDA, "valor_oferta": None, "valor_norma": None, "operador": None, "unidad": ""}),
                           (ClasificacionRiesgo, {"motivo": "m", "veredicto": "CUMPLE", "valor_ofertado": None, "impacto": None})):
        salida, n = normalizar_tipos_vacios(datos, esquema)
        assert salida == datos and n == 0
    antes = normalizaciones_formato()
    r = _parsear_respuesta_llm(json.dumps(VALIDA), None, VerificacionArticulo)
    assert r.veredicto == "Incumple" and r.valor_oferta == 5 and normalizaciones_formato() == antes


def test_normalizar_vacios_de_los_campos_opcionales_y_nulos_de_los_de_texto_obligatorio():
    roto = {**VALIDA, "dato_oferta": None, "explicacion": None, "valor_oferta": "", "valor_norma": " ", "operador": "", "unidad": ""}
    salida, n = normalizar_tipos_vacios(roto, VerificacionArticulo)
    assert n == 5 and salida["dato_oferta"] == "" and salida["explicacion"] == "" and salida["valor_oferta"] is None and salida["operador"] is None and salida["unidad"] == ""
    assert roto["valor_oferta"] == ""      # no modifica la entrada
    antes = normalizaciones_formato()
    r = _parsear_respuesta_llm(json.dumps(roto), None, VerificacionArticulo)    # sin la normalización esto es un ValidationError
    assert (r.dato_oferta, r.valor_oferta, r.operador, r.veredicto) == ("", None, None, "Incumple") and normalizaciones_formato() == antes + 5
    c, n = normalizar_tipos_vacios({"motivo": "m", "veredicto": "DESVIO", "impacto": "", "tipo_limite": "", "valor_ofertado": ""}, ClasificacionRiesgo)
    assert n == 2 and c["impacto"] is None and c["tipo_limite"] is None and c["valor_ofertado"] == ""


def test_un_modelo_sin_precio_no_arranca(capsys):
    assert nube.main(["--reusar-recuperacion", "x.json", "--modelo", "otro/modelo"]) == 2
    assert "PRECIOS_NUBE" in capsys.readouterr().err
