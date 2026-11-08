import json
import os

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage

from scripts import config, nube, rag_components
from scripts.main import LlamadaFallida

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
    resultados = nube.ejecutar_secciones([_seccion(1), _seccion(2), _seccion(3)], docs, cliente, LIN, concurrencia=8)
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
    resultados = nube.ejecutar_secciones([_seccion(1), _seccion(3)], _docs(), nube.ClienteNube(LLMFalso(), g), LIN, concurrencia=1)
    assert [r["incompleta"] for _, r in resultados] == [True, True]      # la 1.ª llamada pasa el tope: la 2.ª de S1 y todo S3 se frenan
    assert resultados[1][1]["registro"][0]["estado"] == "presupuesto_agotado"


def test_resumen_de_humo_cuenta_json_bien_parseado():
    registro = [{"veredicto": "Cumple"}, {"veredicto": None, "estado": "descartada", "motivo": "formato inválido tras reintentar: x"}, {"etapa": "clasificacion", "veredicto": "DESVIO"}]
    r = nube.resumen_humo(registro, {"usd": 0.01})
    assert (r["pares"], r["json_ok"], r["json_invalido"], r["usd"]) == (2, 1, 1, 0.01)


def test_sufijo_del_archivo_lleva_el_proveedor_y_el_modelo():
    assert nube.sufijo_modelo("deepinfra", "Qwen/Qwen3-32B") == "deepinfra-qwen3-32b"
    assert nube.sufijo_modelo("deepinfra", "Qwen/Qwen3-235B-A22B-Instruct-2507") == "deepinfra-qwen3-235b-a22b-instruct-2507"


def test_un_modelo_sin_precio_no_arranca(capsys):
    assert nube.main(["--reusar-recuperacion", "x.json", "--modelo", "otro/modelo"]) == 2
    assert "PRECIOS_NUBE" in capsys.readouterr().err
