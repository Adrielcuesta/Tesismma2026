# scripts/run_oferta.py
"""Analiza una oferta desde la consola e imprime el tiempo por etapa.

    python -m scripts.run_oferta <archivo.pdf|docx> [--modelo ID] [--sin-rag] [--sin-reranker] [--oferta P1]

Reutiliza run_analysis: el JSON (con timestamp) y el dashboard quedan en datos/Resultados/<oferta>/.
Imprime el volumen (brechas, riesgos, solicitudes, alertas), el tiempo por etapa y el comando de evaluar.py con la ruta del JSON.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys
import tempfile
import time

from . import config
from .main import run_analysis, AnalisisError
from .dashboard_generator import es_modo_verificacion

# (clave en tiempos_s, etiqueta)
ETAPAS = [
    ("extraccion", "extracción"), ("division", "división"), ("carga_kb", "carga de KB y modelos"),
    ("recuperacion", "recuperación (total)"), ("crag", "evaluación CRAG (total)"), ("generacion", "generación (total)"),
    ("verificacion", "verificación por artículo (total)"), ("clasificacion", "clasificación (total)"),
    ("validacion", "validación y respaldo (total)"), ("union", "unión y deduplicado"),
    ("resumen_final", "agrupamiento y resumen (con comentario)"), ("comentario", "  del cual: comentario general"),
    ("total", "total del pipeline"),
]


def _buscar_json(ruta_html: str):
    """El JSON de la corrida comparte carpeta y timestamp con el dashboard (dashboard_<base>_<fecha>_<hora>.html)."""
    carpeta, nombre = os.path.split(ruta_html)
    timestamp = "_".join(os.path.splitext(nombre)[0].split("_")[-2:])
    candidatos = glob.glob(os.path.join(carpeta, f"analisis_riesgos_*_{timestamp}.json"))
    return candidatos[0] if candidatos else None


def _oferta_de(archivo: str, oferta: str = None) -> str:
    """P1..P4 indicado o deducido del nombre del archivo; si no, un marcador para completar."""
    if oferta:
        return oferta
    m = re.search(r"(?<![A-Za-z0-9])P([1-4])(?![0-9])", os.path.basename(archivo), re.IGNORECASE)
    return f"P{m.group(1)}" if m else "<P1|P2|P3|P4>"


def comando_evaluar(ruta_json: str, oferta: str) -> str:
    return 'venv\\Scripts\\python.exe -m evaluacion.evaluar --resultado "' + ruta_json + '" --oferta ' + oferta


def imprimir_resultado(reporte: dict):
    """Volumen del resultado. Modo verificación: brechas, riesgos agrupados, solicitudes y alertas. Modo lista: los riesgos."""
    if es_modo_verificacion(reporte):
        decision = (reporte.get("resumen_ejecutivo") or {}).get("decision", "N/D")
        print(f"Brechas: {len(reporte.get('registro_brechas', []))} | Riesgos: {len(reporte.get('riesgos', []))} | "
              f"Solicitudes: {len(reporte.get('solicitudes', []))} | Alertas: {len(reporte.get('alertas', []))} | Decisión: {decision}")
        return
    riesgos = reporte.get("riesgos_identificados_estructurados", [])
    print(f"Riesgos (modo lista, sin clasificación): {len(riesgos)}")
    for i, r in enumerate(riesgos, 1):
        print(f"  {i}. {r.get('descripcion_riesgo', 'N/D')}\n     cita: {r.get('cita_oferta') or 'N/D'}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Analiza una oferta técnica por secciones.")
    parser.add_argument("archivo", help="Ruta de la oferta (.pdf o .docx)")
    parser.add_argument("--modelo", default=config.OLLAMA_MODEL, help=f"Modelo de generación (por defecto {config.OLLAMA_MODEL})")
    parser.add_argument("--sin-rag", action="store_true", help="Condición sin_rag: sin recuperar fragmentos de la KB")
    parser.add_argument("--sin-reranker", action="store_true", help="Condición rag_seccion_sin_reranker")
    parser.add_argument("--oferta", help="P1, P2, P3 o P4 (para el comando de evaluar.py; por defecto se deduce del nombre del archivo)")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.archivo):
        print(f"No existe el archivo: {args.archivo}", file=sys.stderr)
        return 1
    if args.sin_reranker:
        config.USE_RERANKER = False

    t0 = time.perf_counter()
    # run_analysis recibe una carpeta con la oferta: se copia el archivo a una carpeta temporal
    with tempfile.TemporaryDirectory() as carpeta_tmp:
        shutil.copy(args.archivo, carpeta_tmp)
        try:
            ruta_html_rel = run_analysis(args.modelo, usar_rag=not args.sin_rag, directorio_proyecto=carpeta_tmp)
        except AnalisisError as e:
            print(f"Error en el análisis: {e}", file=sys.stderr)
            return 1
    duracion = time.perf_counter() - t0

    ruta_html = os.path.join(config.PROJECT_ROOT, ruta_html_rel)
    ruta_json = _buscar_json(ruta_html)
    if not ruta_json:
        print(f"Análisis terminado, pero no se encontró el JSON junto a {ruta_html}", file=sys.stderr)
        return 1
    with open(ruta_json, encoding="utf-8") as f:
        reporte = json.load(f)
    cfg = reporte.get("configuracion_analisis", {})
    tiempos = cfg.get("tiempos_s", {})

    print(f"\nOferta: {os.path.basename(args.archivo)} | condición: {cfg.get('condicion', 'N/D')} | modelo: {cfg.get('modelo_llm_usado', 'N/D')}")
    print(f"Secciones: {cfg.get('n_secciones', len(reporte.get('secciones', [])))}")
    imprimir_resultado(reporte)
    print("\nTiempo por etapa (s):")
    for clave, etiqueta in ETAPAS:
        if clave in tiempos:
            print(f"  {etiqueta:<32}{tiempos[clave]:>9.2f}")
    print("\nPor sección (s):")
    for t in tiempos.get("por_seccion", []):
        print(f"  {t['id']:<6} recuperación {t.get('recuperacion', 0):>7.2f} | CRAG {t.get('crag', 0):>7.2f} | generación {t.get('generacion', 0):>8.2f} | verificación {t.get('verificacion', 0):>8.2f} | clasificación {t.get('clasificacion', 0):>8.2f}")
    print(f"\nDuración del script: {duracion:.2f} s")
    print(f"JSON:      {ruta_json}")
    print(f"Dashboard: {ruta_html}")
    print(f"\nEvaluar:\n{comando_evaluar(ruta_json, _oferta_de(args.archivo, args.oferta))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
