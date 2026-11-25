"""scripts.nube --reintentar-fallidas con un cliente simulado (sin API, sin Chroma, sin leer datos/): solo se vuelve a llamar a los pares sin respuesta válida y el JSON fusionado
lleva el conjunto completo, con riesgos y alertas rearmados."""
import json
import os

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage

from scripts import config, document_utils, nube
from scripts import main as M

with open(os.path.join(os.path.dirname(__file__), "fixtures", "criterios_empresa.json"), encoding="utf-8") as f:
    C = json.load(f)
LIN = {"criterios": C, "texto_para_el_modelo": "<criterios inventados>", "huella": "h" * 64, "documentos": []}
MODELO = next(iter(config.NUBE_MODELOS_RAZONAMIENTO_FIJO))       # gpt-oss: lleva mensaje de sistema, como la corrida real
PEDIDO = httpx.Request("POST", "http://x")

INCUMPLE = json.dumps({"oraciones": ["O1"], "explicacion": "no coincide", "veredicto": "Incumple"})
NO_APLICA = json.dumps({"oraciones": [], "explicacion": "no lo trata", "veredicto": "No aplica"})
DESVIO = json.dumps({"motivo": "m", "veredicto": "DESVIO", "objeto_requisito": "CUANTITATIVO_TECNICO", "valor_ofertado": "1", "valor_exigido": "2", "unidad": "unidades",
                     "tipo_limite": "CANTIDAD", "dimension_impacto": "Integridad", "impacto": 4, "titulo": "Apoyos insuficientes", "enunciado": "e", "accion": "a",
                     "solicitud_oferente": "s"})

TEXTO_S3, TEXTO_S4 = "La oferta incluye 1 unidad de apoyo.", "El taller entrega el informe firmado."
SECCIONES = [{"id": "S3", "titulos": ["3 Alcance"], "texto": TEXTO_S3, "subsecciones": [("3.1 Apoyos", TEXTO_S3)]},
             {"id": "S4", "titulos": ["4 Informes"], "texto": TEXTO_S4, "subsecciones": [("4.1 Informes", TEXTO_S4)]}]
ARTICULOS = {("NORM_01", "4.2"): "Art. 4.2. APOYOS\nSe exigen como minimo 2 unidades de apoyo.", ("NORM_02", "5.1"): "Art. 5.1. INFORMES\nEl informe se entrega firmado."}
LOCAL = {"nombre_archivo_original": "P9_oferta_X.pdf", "configuracion_analisis": {"perfil_recuperacion": "elegido"},
         "secciones": [{"id": "S3", "titulos": ["3 Alcance"], "fragmentos": [{"norma": "NORM_01", "articulo": "4.2"}, {"norma": "NORM_02", "articulo": "5.1"}]},
                       {"id": "S4", "titulos": ["4 Informes"], "fragmentos": [{"norma": "NORM_02", "articulo": "5.1"}]}]}


class LLMGuion:
    """Responde según el prompt: verificación Incumple para el Art. 4.2 y No aplica para el resto; clasificación DESVIO. `fallas`: {texto que aparece en el prompt: error}.
    Anota (sección, artículo, etapa) de cada llamada."""
    def __init__(self, fallas=None):
        self.fallas, self.llamadas = fallas or {}, []

    def invoke(self, entrada):
        mensajes = entrada if isinstance(entrada, list) else (entrada.to_messages() if hasattr(entrada, "to_messages") else [])
        texto = " ".join(str(m.content) for m in mensajes) if mensajes else str(entrada)
        seccion = "S3" if TEXTO_S3 in texto else "S4" if TEXTO_S4 in texto else "?"
        articulo = "4.2" if "Art. 4.2." in texto else "5.1" if "Art. 5.1." in texto else "?"
        etapa = "clasificacion" if "<criterios inventados>" in texto else "verificacion"
        self.llamadas.append((seccion, articulo, etapa))
        for clave, error in self.fallas.items():
            if clave in texto:
                raise error
        contenido = DESVIO if etapa == "clasificacion" else INCUMPLE if articulo == "4.2" else NO_APLICA
        return AIMessage(content=contenido, usage_metadata={"input_tokens": 1000, "output_tokens": 100, "total_tokens": 1100}, response_metadata={"finish_reason": "stop"})


def _indice():
    return nube.indice_de_articulos({"documents": list(ARTICULOS.values()), "metadatas": [{"norma": n, "articulo": a, "parte": 1} for n, a in ARTICULOS]})


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DIRECTORIO_RESULTADOS_BASE", str(tmp_path / "Resultados"))
    monkeypatch.setattr(config, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(config, "THINKING_VERIFICACION", config.THINKING_VERIFICACION)
    monkeypatch.setattr(document_utils, "extraer_texto_oferta", lambda ruta: "texto")
    monkeypatch.setattr(document_utils, "dividir_en_secciones", lambda texto: [dict(s) for s in SECCIONES])
    monkeypatch.setattr(M.dashboard_generator, "generar_dashboard_html",
                        lambda ruta_json_resultados, ruta_output_dashboard_html, info_tesis_config=None: open(ruta_output_dashboard_html, "w").close())
    monkeypatch.setattr(nube.lineamientos, "cargar_lineamientos", lambda carpeta: LIN)
    monkeypatch.setattr(nube, "_abrir_chroma", lambda: type("C", (), {"get": lambda self, include: {"documents": list(ARTICULOS.values()),
                                                                                                     "metadatas": [{"norma": n, "articulo": a, "parte": 1} for n, a in ARTICULOS]}})())
    monkeypatch.setenv("DEEPINFRA_API_KEY", "clave-falsa")
    rec = tmp_path / "recuperacion_elegido_P9.json"
    rec.write_text(json.dumps(LOCAL), encoding="utf-8")
    return tmp_path, str(rec)


def _cliente(llm, gasto):
    return nube.ClienteNube(llm, gasto, sistema=config.NUBE_MODELOS_RAZONAMIENTO_FIJO.get(MODELO))


def _corrida_original(rec):
    """S3: el Art. 4.2 agota los reintentos (429) y el 5.1 responde; S4 cae entera por un 402 (como la corrida de P9 cortada por saldo)."""
    llm = LLMGuion({"Art. 4.2.": openai.RateLimitError("limite", response=httpx.Response(429, request=PEDIDO), body=None),
                    TEXTO_S4: openai.APIStatusError("sin saldo", response=httpx.Response(402, request=PEDIDO), body=None)})
    gasto = nube.Gasto(config.PRECIOS_NUBE[MODELO], 10.0)
    s = nube.correr_oferta(rec, "P9_oferta_X.pdf", _cliente(llm, gasto), _cliente(llm, gasto), gasto, LIN, _indice(), "deepinfra", MODELO, 1, False, None)
    with open(s["json"], encoding="utf-8") as f:
        return s["json"], json.load(f)


def _reintentar(monkeypatch, rec, ruta_original, llm, *extra):
    monkeypatch.setattr(nube.rag_components, "get_llm_openai_compatible", lambda proveedor, modelo, razonamiento=False, esquema=None: llm)
    return nube.main(["--reusar-recuperacion", rec, "--reintentar-fallidas", ruta_original, "--modelo", MODELO, "--pdf", "P9_oferta_X.pdf", *extra])


# --- Identificación de los pares fallidos ---

def test_es_par_fallido():
    assert nube.es_par_fallido({"veredicto": None, "estado": "tiempo_agotado"})
    assert nube.es_par_fallido({"veredicto": None, "estado": "descartada", "motivo": "formato inválido tras reintentar: x"})
    assert nube.es_par_fallido({"etapa": "clasificacion", "veredicto": "Incumple", "estado": "tiempo_agotado"})
    assert nube.es_par_fallido({"etapa": "clasificacion", "veredicto": "Incumple", "estado": "clasificacion_fallida"})
    assert not nube.es_par_fallido({"veredicto": "Cumple"}) and not nube.es_par_fallido({"etapa": "clasificacion", "veredicto": "NO_APLICA", "estado": "descartada"})
    assert not nube.es_par_fallido({"etapa": "clasificacion", "veredicto": "CUMPLE", "estado": "no_es_riesgo"})


def test_pares_fallidos_incluye_las_secciones_caidas_enteras_en_orden():
    registro = [{"seccion": "S3", "norma": "NORM_01", "articulo": "4.2", "veredicto": None, "estado": "tiempo_agotado"},
                {"seccion": "S3", "norma": "NORM_02", "articulo": "5.1", "veredicto": "No aplica"},
                {"seccion": "S4", "etapa": "verificacion", "estado": "seccion_fallida", "motivo": "APIStatusError: 402"}]
    assert nube.pares_fallidos(LOCAL["secciones"], registro) == {"S3": [("NORM_01", "4.2")], "S4": [("NORM_02", "5.1")]}
    assert nube.pares_fallidos(LOCAL["secciones"], registro[1:2]) == {}


def test_fusionar_no_reemplaza_una_seccion_del_reintento_que_no_se_completo():
    original = {"registro_brechas": [], "alertas": [{"seccion": "S3", "norma": "NORM_01", "articulo": "4.2", "estado": "tiempo_agotado"}],
                "registro_tecnico": [{"seccion": "S3", "norma": "NORM_01", "articulo": "4.2", "veredicto": None, "estado": "tiempo_agotado"},
                                     {"seccion": "S3", "norma": "NORM_02", "articulo": "5.1", "veredicto": "No aplica"}]}
    cortada = [("S3", {"brechas": [], "alertas": [], "registro": [{"seccion": "S3", "etapa": "verificacion", "estado": "presupuesto_agotado"}], "incompleta": True})]
    fusion, sin_completar = nube.fusionar(original, cortada, {"S3": [("NORM_01", "4.2")]}, ["S3", "S4"])
    assert sin_completar == ["S3"] and fusion["registro_tecnico"] == original["registro_tecnico"] and fusion["alertas"] == original["alertas"]
    bien = [("S3", {"brechas": [], "alertas": [], "registro": [{"seccion": "S3", "norma": "NORM_01", "articulo": "4.2", "veredicto": "Cumple"}], "incompleta": False})]
    fusion, sin_completar = nube.fusionar(original, bien, {"S3": [("NORM_01", "4.2")]}, ["S3", "S4"])
    assert sin_completar == [] and fusion["alertas"] == []
    assert fusion["registro_tecnico"] == [original["registro_tecnico"][1], bien[0][1]["registro"][0]]      # lo que estaba bien queda igual; lo nuevo al final de su sección


# --- De punta a punta con el cliente simulado ---

def test_reintento_llama_solo_a_los_pares_fallidos_y_fusiona(entorno, monkeypatch, capsys):
    tmp, rec = entorno
    ruta_original, original = _corrida_original(rec)
    reg = original["registro_tecnico"]
    assert any(r.get("estado") == "tiempo_agotado" for r in reg) and any(r.get("estado") == "seccion_fallida" for r in reg)
    assert original["registro_brechas"] == [] and any(a.get("estado") == "tiempo_agotado" for a in original["alertas"])
    bien_original = next(r for r in reg if r.get("seccion") == "S3" and r.get("articulo") == "5.1")
    contenido_original = open(ruta_original, encoding="utf-8").read()

    llm = LLMGuion()
    assert _reintentar(monkeypatch, rec, ruta_original, llm) == 0
    # S3/5.1 ya estaba bien: no se vuelve a llamar. S3/4.2 (verificación + clasificación) y S4/5.1 (sección caída) sí.
    assert sorted(llm.llamadas) == [("S3", "4.2", "clasificacion"), ("S3", "4.2", "verificacion"), ("S4", "5.1", "verificacion")]
    nuevos = [p for p in os.listdir(os.path.dirname(ruta_original)) if p.endswith(f"{nube.SUFIJO_REINTENTO}.json")]
    assert len(nuevos) == 1 and nuevos[0].endswith("-elegido-reintento.json")
    assert open(ruta_original, encoding="utf-8").read() == contenido_original           # el original no se toca
    with open(os.path.join(os.path.dirname(ruta_original), nuevos[0]), encoding="utf-8") as f:
        fusion = json.load(f)
    reg_f = fusion["registro_tecnico"]
    assert not any(nube.es_par_fallido(r) or r.get("estado") in nube.ESTADOS_SECCION_CAIDA for r in reg_f)
    assert next(r for r in reg_f if r.get("seccion") == "S3" and r.get("articulo") == "5.1") == bien_original
    assert [(b["seccion"], b["norma"], b["articulo"]) for b in fusion["registro_brechas"]] == [("S3", "NORM_01", "4.2")]
    assert fusion["riesgos"] and fusion["riesgos"][0]["id"] == "R1" and fusion["registro_brechas"][0].get("nivel")       # clasificación y motor aplicados
    assert not any(a.get("estado") == "tiempo_agotado" for a in fusion["alertas"])
    cfg = fusion["configuracion_analisis"]
    assert (cfg["reintento"]["pares_reintentados"], cfg["reintento"]["pares_siguen_fallidos"], cfg["reintento"]["pares_recuperados"]) == (2, 0, 2)
    assert cfg["llamadas_fallidas"] == 0 and cfg["costo_computacional"]["llamadas_fallidas"] == 0 and cfg["reintento"]["llamadas_fallidas_original"] > 0
    assert cfg["reintento"]["json_original"] == os.path.basename(ruta_original) and cfg["huella_pares"] == original["configuracion_analisis"]["huella_pares"]
    co, cf = original["configuracion_analisis"]["costo_computacional"], cfg["costo_computacional"]
    assert cf["costo_usd"] == pytest.approx(co["costo_usd"] + cfg["reintento"]["costo_usd_reintento"]) and cf["proveedor"] == "deepinfra"
    assert len(cfg["llamadas_detalle"]) == len(original["configuracion_analisis"]["llamadas_detalle"]) + 3
    assert "2 pares reintentados | recuperados 2 | siguen fallidos 0" in capsys.readouterr().out
    assert any(p.startswith("dashboard_") and p.endswith("-reintento.html") for p in os.listdir(os.path.dirname(ruta_original)))


def test_si_el_par_vuelve_a_fallar_sigue_fallido_y_se_cuenta(entorno, monkeypatch):
    tmp, rec = entorno
    ruta_original, _ = _corrida_original(rec)
    llm = LLMGuion({"Art. 4.2.": openai.InternalServerError("caido", response=httpx.Response(503, request=PEDIDO), body=None)})
    assert _reintentar(monkeypatch, rec, ruta_original, llm) == 0
    [nuevo] = [p for p in os.listdir(os.path.dirname(ruta_original)) if p.endswith("-reintento.json")]
    with open(os.path.join(os.path.dirname(ruta_original), nuevo), encoding="utf-8") as f:
        cfg = json.load(f)["configuracion_analisis"]
    assert (cfg["reintento"]["pares_siguen_fallidos"], cfg["reintento"]["pares_recuperados"], cfg["llamadas_fallidas"]) == (1, 1, 1)


def test_sin_pares_fallidos_no_llama_ni_escribe(entorno, monkeypatch):
    tmp, rec = entorno
    gasto = nube.Gasto(config.PRECIOS_NUBE[MODELO], 10.0)
    llm = LLMGuion()
    s = nube.correr_oferta(rec, "P9_oferta_X.pdf", _cliente(llm, gasto), _cliente(llm, gasto), gasto, LIN, _indice(), "deepinfra", MODELO, 1, False, None)
    otro = LLMGuion()
    assert _reintentar(monkeypatch, rec, s["json"], otro) == 0 and otro.llamadas == []
    assert not [p for p in os.listdir(os.path.dirname(s["json"])) if p.endswith("-reintento.json")]


@pytest.mark.parametrize("cambio,mensaje", [
    (lambda o, l: o["configuracion_analisis"].update(modelo_llm_usado="deepinfra:Qwen/Qwen3-32B"), "modelo"),
    (lambda o, l: o["configuracion_analisis"]["costo_computacional"].update(proveedor="groq"), "proveedor"),
    (lambda o, l: o["lineamientos"].update(huella="x" * 64), "huella de los lineamientos"),
    (lambda o, l: o["configuracion_analisis"].update(huella_pares="otra"), "huella de pares"),
    (lambda o, l: l["configuracion_analisis"].update(perfil_recuperacion="local"), "perfil de recuperación"),
    (lambda o, l: o["configuracion_analisis"].update(max_pares=5), "prueba de humo")])
def test_si_la_corrida_original_no_coincide_no_arranca(entorno, monkeypatch, capsys, cambio, mensaje):
    tmp, rec = entorno
    ruta_original, original = _corrida_original(rec)
    local = json.loads(open(rec, encoding="utf-8").read())
    cambio(original, local)
    open(ruta_original, "w", encoding="utf-8").write(json.dumps(original))
    open(rec, "w", encoding="utf-8").write(json.dumps(local))
    llm = LLMGuion()
    assert _reintentar(monkeypatch, rec, ruta_original, llm) == 1
    assert llm.llamadas == [] and mensaje in capsys.readouterr().err


def test_si_chroma_tiene_otro_texto_del_articulo_no_arranca(entorno, monkeypatch, capsys):
    tmp, rec = entorno
    ruta_original, _ = _corrida_original(rec)
    monkeypatch.setattr(nube, "_abrir_chroma", lambda: type("C", (), {"get": lambda self, include: {
        "documents": ["Art. 4.2. APOYOS\nTexto reindexado.", ARTICULOS[("NORM_02", "5.1")]], "metadatas": [{"norma": n, "articulo": a, "parte": 1} for n, a in ARTICULOS]}})())
    llm = LLMGuion()
    assert _reintentar(monkeypatch, rec, ruta_original, llm) == 1 and llm.llamadas == [] and "NORM_01 Art. 4.2" in capsys.readouterr().err


def test_estimar_cuenta_solo_los_pares_fallidos_sin_api(entorno, monkeypatch, capsys):
    tmp, rec = entorno
    ruta_original, _ = _corrida_original(rec)
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    monkeypatch.setattr(nube.rag_components, "get_llm_openai_compatible", lambda *a, **k: pytest.fail("--estimar no crea clientes"))
    assert nube.main(["--reusar-recuperacion", rec, "--reintentar-fallidas", ruta_original, "--modelo", MODELO, "--estimar"]) == 0
    salida = capsys.readouterr().out
    por_par, _ = nube.costo_por_par(MODELO)
    assert "2 pares sin respuesta válida" in salida and f"{2 * por_par:.4f} USD" in salida


def test_el_reintento_respeta_el_tope_de_gasto(entorno, monkeypatch):
    tmp, rec = entorno
    ruta_original, _ = _corrida_original(rec)
    monkeypatch.setattr(config, "PRESUPUESTO_USD", 0.0)
    llm = LLMGuion()
    assert _reintentar(monkeypatch, rec, ruta_original, llm) == 0 and llm.llamadas == []
    [nuevo] = [p for p in os.listdir(os.path.dirname(ruta_original)) if p.endswith("-reintento.json")]
    with open(os.path.join(os.path.dirname(ruta_original), nuevo), encoding="utf-8") as f:
        cfg = json.load(f)["configuracion_analisis"]
    assert cfg["reintento"]["pares_siguen_fallidos"] == 2 and cfg["costo_computacional"]["detenida_por_presupuesto"] is True


def test_argumentos_del_modo_reintento(entorno, capsys):
    tmp, rec = entorno
    assert nube.main(["--reusar-recuperacion", rec, rec, "--reintentar-fallidas", "a.json", "--modelo", MODELO]) == 2
    assert nube.main(["--reusar-recuperacion", rec, "--reintentar-fallidas", "a.json", "--modelo", MODELO, "--max-pares", "3"]) == 2
