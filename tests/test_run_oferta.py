import json
import os

import pytest

from scripts import config, run_oferta

TIEMPOS = {"extraccion": 1.0, "division": 0.5, "carga_kb": 2.0, "recuperacion": 3.0, "verificacion": 4.0, "clasificacion": 5.0,
           "comentario": 0.7, "resumen_final": 0.8, "total": 20.0,
           "por_seccion": [{"id": "3", "recuperacion": 1.0, "verificacion": 2.0, "clasificacion": 2.5}]}

VERIFICACION = {
    "configuracion_analisis": {"condicion": "rag_verificacion", "modelo_llm_usado": "qwen3:8b", "n_secciones": 2, "tiempos_s": TIEMPOS},
    "registro_brechas": [{}, {}, {}], "riesgos": [{}, {}], "solicitudes": [{}, {}], "alertas": [{}],
    "resumen_ejecutivo": {"decision": "No aceptable"}, "riesgos_identificados_estructurados": []}
LISTA = {
    "configuracion_analisis": {"condicion": "sin_rag", "modelo_llm_usado": "qwen3:8b", "n_secciones": 2, "tiempos_s": {"total": 5.0, "generacion": 4.0}},
    "registro_brechas": [], "resumen_ejecutivo": None,
    "riesgos_identificados_estructurados": [{"descripcion_riesgo": "Plazo de entrega ajustado", "cita_oferta": "Entrega en 30 días."},
                                            {"descripcion_riesgo": "Sin reserva de espacio", "cita_oferta": "Tableros justos."}]}


@pytest.fixture
def simulado(tmp_path, monkeypatch):
    """run_analysis simulado: escribe el JSON y el dashboard de la corrida y devuelve la ruta del HTML (sin ejecutar el pipeline)."""
    llamadas = []

    def fabricar(reporte):
        def falso(modelo, usar_rag=True, directorio_proyecto=None, **kw):
            llamadas.append({"modelo": modelo, "usar_rag": usar_rag, "archivos": os.listdir(directorio_proyecto)})
            (tmp_path / "analisis_riesgos_oferta_20260101_101010.json").write_text(json.dumps(reporte), encoding="utf-8")
            html = tmp_path / "dashboard_oferta_20260101_101010.html"
            html.write_text("<html></html>", encoding="utf-8")
            return str(html)
        return falso

    def instalar(reporte):
        monkeypatch.setattr(run_oferta, "run_analysis", fabricar(reporte))
        return llamadas

    oferta = tmp_path / "Oferta_P2.pdf"
    oferta.write_text("x")
    return instalar, str(oferta), tmp_path


def test_modo_verificacion_imprime_volumen_etapas_y_comando(simulado, capsys):
    instalar, oferta, tmp = simulado
    llamadas = instalar(VERIFICACION)
    assert run_oferta.main([oferta]) == 0
    salida = capsys.readouterr().out
    assert llamadas == [{"modelo": config.OLLAMA_MODEL, "usar_rag": True, "archivos": ["Oferta_P2.pdf"]}]
    assert "Brechas: 3 | Riesgos: 2 | Solicitudes: 2 | Alertas: 1 | Decisión: No aceptable" in salida
    assert "clasificación (total)" in salida and "comentario general" in salida and "redacción" not in salida
    assert "clasificación     2.50" in salida                      # por sección
    json_ruta = str(tmp / "analisis_riesgos_oferta_20260101_101010.json")
    assert f'venv\\Scripts\\python.exe -m evaluacion.evaluar --resultado "{json_ruta}" --oferta P2' in salida


def test_sin_rag_imprime_los_riesgos_de_la_lista(simulado, capsys):
    instalar, oferta, _ = simulado
    llamadas = instalar(LISTA)
    assert run_oferta.main([oferta, "--sin-rag", "--oferta", "P1"]) == 0
    salida = capsys.readouterr().out
    assert llamadas[0]["usar_rag"] is False
    assert "Riesgos (modo lista, sin clasificación): 2" in salida and "1. Plazo de entrega ajustado" in salida and "cita: Tableros justos." in salida
    assert "Brechas:" not in salida and "--oferta P1" in salida


def test_oferta_se_deduce_del_nombre_o_queda_para_completar():
    assert run_oferta._oferta_de("datos/Oferta_P3_final.pdf") == "P3"
    assert run_oferta._oferta_de("P4.docx") == "P4"
    assert run_oferta._oferta_de("Oferta_taller.pdf") == "<P1|P2|P3|P4>"
    assert run_oferta._oferta_de("Oferta_taller.pdf", "P2") == "P2"


def test_archivo_inexistente(capsys):
    assert run_oferta.main(["no_existe.pdf"]) == 1
