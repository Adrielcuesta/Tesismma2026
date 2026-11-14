"""_analizar_por_secciones en modo verificacion, de punta a punta, con un LLM simulado (sin red, sin Ollama, sin indices).
Regresion: una variable local del CRAG llamada `clasificacion` tapaba el modulo `clasificacion` y el analisis fallaba con AttributeError al armar las salidas."""
import glob
import json
import os
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from scripts import clasificacion, comentario, config, costo, dashboard_generator, document_utils, lineamientos, main, rag_components, vector_db_manager

with open(os.path.join(os.path.dirname(__file__), "fixtures", "criterios_empresa.json"), encoding="utf-8") as f:
    C = json.load(f)
LIN = {"criterios": C, "texto_para_el_modelo": "<criterios inventados>", "huella": "h" * 64, "documentos": []}


def _msg(**campos):
    return SimpleNamespace(content=json.dumps(campos), response_metadata={})


INCUMPLE = _msg(oraciones=["O1"], explicacion="no coincide", veredicto="Incumple")
CUMPLE = _msg(oraciones=["O1"], explicacion="coincide", veredicto="Cumple")
DESVIO = _msg(motivo="m", veredicto="DESVIO", objeto_requisito="CUANTITATIVO_TECNICO", valor_ofertado="1", valor_exigido="2", unidad="unidades",
              tipo_limite="CANTIDAD", dimension_impacto="Integridad", impacto=4, titulo="Apoyos insuficientes", enunciado="e", accion="a", solicitud_oferente="s")


class Cadena:
    """Cadena falsa: devuelve en orden los mensajes dados (el ultimo se repite)."""
    def __init__(self, *mensajes):
        self.mensajes = list(mensajes)

    def invoke(self, entrada):
        return self.mensajes.pop(0) if len(self.mensajes) > 1 else self.mensajes[0]


def _seccion(n, texto):
    return {"id": str(n), "titulos": [f"{n} Alcance"], "texto": texto, "subsecciones": [(f"{n}.1 Apoyos", texto)]}


SECCIONES = [_seccion(3, "La oferta incluye 1 unidad de apoyo."), _seccion(4, "El taller entrega el informe firmado.")]
DOCS = {"3": Document(page_content="Art. 4.2. APOYOS\nSe exigen como minimo 2 unidades de apoyo.", metadata={"norma": "NORM_01", "articulo": "4.2", "parte": 1}),
        "4": Document(page_content="Art. 5.1. INFORMES\nEl informe se entrega firmado.", metadata={"norma": "NORM_02", "articulo": "5.1", "parte": 1})}


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DIRECTORIO_RESULTADOS_BASE", str(tmp_path))
    monkeypatch.setattr(config, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(document_utils, "obtener_ruta_pdf_proyecto", lambda carpeta: os.path.join(str(tmp_path), "oferta_prueba.pdf"))
    monkeypatch.setattr(document_utils, "extraer_texto_oferta", lambda ruta: "texto de la oferta")
    monkeypatch.setattr(document_utils, "dividir_en_secciones", lambda texto: SECCIONES)
    monkeypatch.setattr(lineamientos, "cargar_lineamientos", lambda carpeta: LIN)
    monkeypatch.setattr(vector_db_manager, "get_embedding_function", lambda nombre: object())
    monkeypatch.setattr(vector_db_manager, "crear_o_cargar_chroma_db", lambda **kw: object())
    monkeypatch.setattr(rag_components, "recuperar_seccion", lambda db, seccion, **kw: ([], [DOCS[seccion["id"]]]))
    monkeypatch.setattr(rag_components, "get_llm_instance", lambda *a, **kw: SimpleNamespace(invoke=lambda e: INCUMPLE))
    monkeypatch.setattr(rag_components, "crear_cadena_verificacion", lambda llm: Cadena(INCUMPLE, CUMPLE))
    monkeypatch.setattr(rag_components, "crear_cadena_clasificacion", lambda llm: Cadena(DESVIO))
    monkeypatch.setattr(rag_components, "crear_cadena_comentario", lambda llm: (_ for _ in ()).throw(RuntimeError("sin modelo")))   # usa la plantilla
    monkeypatch.setattr(costo, "detectar_hardware", lambda: {"gpu": None, "vram": None})
    monkeypatch.setattr(dashboard_generator, "generar_dashboard_html",
                        lambda ruta_json_resultados, ruta_output_dashboard_html, info_tesis_config=None: open(ruta_output_dashboard_html, "w").close())
    return tmp_path


def _analizar():
    return main._analizar_por_secciones("modelo-falso", False, True, "20260101_000000", None, None)


def _jsons(carpeta, patron):
    return glob.glob(os.path.join(str(carpeta), "**", patron), recursive=True)


def test_analisis_de_punta_a_punta_en_verificacion_llega_a_guardar_el_json(entorno):
    _analizar()
    [ruta] = [r for r in _jsons(entorno, "analisis_riesgos_*.json") if not r.endswith("_parcial.json")]
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    assert len(datos["registro_brechas"]) == 1 and len(datos["riesgos"]) == 1 and len(datos["solicitudes"]) >= 1
    assert datos["resumen_ejecutivo"]["decision"] and [s["id"] for s in datos["secciones"]] == ["3", "4"]
    assert [r["veredicto"] for r in datos["registro_tecnico"] if not r.get("etapa")] == ["Incumple", "Cumple"]
    assert not _jsons(entorno, "*_parcial.json")


@pytest.mark.parametrize("modulo,funcion", [(clasificacion, "armar_salidas"), (comentario, "generar_comentario"), (dashboard_generator, "generar_dashboard_html")])
def test_si_falla_el_cierre_se_guarda_un_json_parcial_y_el_error_se_propaga(entorno, monkeypatch, modulo, funcion):
    def falla(*a, **kw):
        raise RuntimeError(f"falla en {funcion}")
    monkeypatch.setattr(modulo, funcion, falla)
    with pytest.raises(RuntimeError, match=funcion):
        _analizar()
    [ruta] = _jsons(entorno, "*_parcial.json")
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    assert len(datos["registro_brechas"]) == 1 and [s["id"] for s in datos["secciones"]] == ["3", "4"]
    assert [r["veredicto"] for r in datos["registro_tecnico"] if not r.get("etapa")] == ["Incumple", "Cumple"]
    assert datos["configuracion_analisis"]["parcial"] is True and funcion in datos["configuracion_analisis"]["error"]


def test_un_fallo_al_guardar_el_parcial_no_tapa_el_error_original(entorno, monkeypatch):
    monkeypatch.setattr(clasificacion, "armar_salidas", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("error original")))
    monkeypatch.setattr(main.report_utils, "formatear_y_guardar_reporte", lambda *a, **kw: (_ for _ in ()).throw(OSError("disco lleno")))
    with pytest.raises(RuntimeError, match="error original"):
        _analizar()


# --- Recuperación reusada (run_oferta --reusar-recuperacion): se verifican exactamente los pares del JSON, sin recuperar ni cargar embeddings ---

REC = {"nombre_archivo_original": "oferta_prueba.pdf",
       "secciones": [{"id": "3", "titulos": ["3 Alcance"], "candidatos": [{"norma": "NORM_01", "articulo": "4.2"}, {"norma": "NORM_01", "articulo": "9.9"}],
                      "fragmentos": [{"norma": "NORM_01", "articulo": "4.2", "score": 0.91, "parte": 1}]},
                     {"id": "4", "titulos": ["4 Alcance"], "fragmentos": [{"norma": "NORM_02", "articulo": "5.1", "score": 0.77, "parte": 1}]}],
       "configuracion_analisis": {"perfil_recuperacion": "elegido", "embedding_backend": "gemini"}}


@pytest.fixture
def reuso(entorno, monkeypatch):
    from scripts import huella_recuperacion, nube
    monkeypatch.setattr(rag_components, "recuperar_seccion", lambda *a, **kw: pytest.fail("no debe recuperar: los pares vienen del JSON"))
    monkeypatch.setattr(vector_db_manager, "cargar_indice_kb", lambda *a, **kw: pytest.fail("no debe abrir el índice de embeddings"))
    monkeypatch.setattr(vector_db_manager, "get_embedding_function", lambda *a, **kw: pytest.fail("no debe cargar embeddings"))
    monkeypatch.setattr(rag_components, "_get_reranker_model", lambda *a, **kw: pytest.fail("no debe cargar el reranker"))
    textos = list(DOCS.values())
    monkeypatch.setattr(nube, "_abrir_chroma", lambda: SimpleNamespace(get=lambda include: {"documents": [d.page_content for d in textos], "metadatas": [d.metadata for d in textos]}))
    ruta = entorno / "recuperacion.json"
    ruta.write_text(json.dumps(REC), encoding="utf-8")
    vistos = []
    original = main._verificar_seccion

    def espia(seccion, docs, *a, **kw):
        vistos.append((seccion["id"], [(d.metadata["norma"], d.metadata["articulo"], d.metadata.get("parte")) for d in docs]))
        return original(seccion, docs, *a, **kw)
    monkeypatch.setattr(main, "_verificar_seccion", espia)
    return ruta, vistos, huella_recuperacion


def test_con_recuperacion_reusada_se_verifican_exactamente_los_pares_del_json(reuso, entorno):
    ruta, vistos, huella = reuso
    main._analizar_por_secciones("modelo-falso", False, True, "20260101_000000", None, None, recuperacion_json=str(ruta))
    assert vistos == [("3", [("NORM_01", "4.2", 1)]), ("4", [("NORM_02", "5.1", 1)])]
    [salida] = [r for r in _jsons(entorno, "analisis_riesgos_*.json") if not r.endswith("_parcial.json")]
    with open(salida, encoding="utf-8") as f:
        datos = json.load(f)
    cfg = datos["configuracion_analisis"]
    assert cfg["recuperacion_reusada"] is True and cfg["recuperacion_json_sha256"] == huella.sha256_archivo(str(ruta)) and cfg["huella_pares"] == huella.huella_de_pares(REC["secciones"])
    assert cfg["perfil_recuperacion"] == "elegido" and cfg["embedding_backend"] == "gemini" and cfg["condicion"] == "rag_seccion"
    # el informe conserva los candidatos y los puntajes del JSON; el registro verifica los mismos pares
    s3 = next(s for s in datos["secciones"] if s["id"] == "3")
    assert [(c["norma"], c["articulo"]) for c in s3["candidatos"]] == [("NORM_01", "4.2"), ("NORM_01", "9.9")] and s3["fragmentos"][0]["score"] == 0.91
    assert [r["veredicto"] for r in datos["registro_tecnico"] if not r.get("etapa")] == ["Incumple", "Cumple"]


def test_sin_recuperacion_reusada_nada_cambia_en_el_json(entorno):
    _analizar()
    [ruta] = [r for r in _jsons(entorno, "analisis_riesgos_*.json") if not r.endswith("_parcial.json")]
    with open(ruta, encoding="utf-8") as f:
        cfg = json.load(f)["configuracion_analisis"]
    assert cfg["embedding_backend"] == "bge-m3" and "recuperacion_reusada" not in cfg and "recuperacion_json_sha256" not in cfg


def test_recuperacion_reusada_de_otra_oferta_o_sin_verificacion_falla(reuso, monkeypatch, tmp_path):
    ruta, _, _ = reuso
    otra = json.loads(json.dumps(REC))
    otra["secciones"][0]["titulos"] = ["3 Otro título"]
    ruta_otra = tmp_path / "otra.json"
    ruta_otra.write_text(json.dumps(otra), encoding="utf-8")
    with pytest.raises(main.AnalisisError, match="no coincide"):
        main._analizar_por_secciones("modelo-falso", False, True, "20260101_000000", None, None, recuperacion_json=str(ruta_otra))
    with pytest.raises(main.AnalisisError, match="solo se aplica"):
        main._analizar_por_secciones("modelo-falso", False, False, "20260101_000000", None, None, recuperacion_json=str(ruta))
    monkeypatch.setattr(config, "MODO_GENERACION", "lista")
    with pytest.raises(main.AnalisisError, match="solo se aplica"):
        main._analizar_por_secciones("modelo-falso", False, True, "20260101_000000", None, None, recuperacion_json=str(ruta))
