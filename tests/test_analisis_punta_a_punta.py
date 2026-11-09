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
