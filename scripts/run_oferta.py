# scripts/run_oferta.py
"""Analiza una oferta desde la consola e imprime el tiempo por etapa.

    python -m scripts.run_oferta <archivo.pdf|docx> [--modelo ID] [--sin-rag] [--sin-reranker]

Reutiliza run_analysis: el JSON (con timestamp) y el dashboard quedan en datos/Resultados/<oferta>/.
"""
import argparse
import glob
import json
import os
import shutil
import sys
import tempfile
import time

from . import config
from .main import run_analysis, AnalisisError

# (clave en tiempos_s, etiqueta)
ETAPAS = [
    ("extraccion", "extracción"), ("division", "división"), ("carga_kb", "carga de KB y modelos"),
    ("recuperacion", "recuperación (total)"), ("crag", "evaluación CRAG (total)"), ("generacion", "generación (total)"),
    ("verificacion", "verificación por artículo (total)"), ("redaccion", "redacción (total)"),
    ("validacion", "validación y respaldo (total)"), ("union", "unión y deduplicado"), ("resumen_final", "resumen final"),
    ("total", "total del pipeline"),
]


def _buscar_json(ruta_html: str):
    """El JSON de la corrida comparte carpeta y timestamp con el dashboard (dashboard_<base>_<fecha>_<hora>.html)."""
    carpeta, nombre = os.path.split(ruta_html)
    timestamp = "_".join(os.path.splitext(nombre)[0].split("_")[-2:])
    candidatos = glob.glob(os.path.join(carpeta, f"analisis_riesgos_*_{timestamp}.json"))
    return candidatos[0] if candidatos else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Analiza una oferta técnica por secciones.")
    parser.add_argument("archivo", help="Ruta de la oferta (.pdf o .docx)")
    parser.add_argument("--modelo", default=config.OLLAMA_MODEL, help=f"Modelo de generación (por defecto {config.OLLAMA_MODEL})")
    parser.add_argument("--sin-rag", action="store_true", help="Condición sin_rag: sin recuperar fragmentos de la KB")
    parser.add_argument("--sin-reranker", action="store_true", help="Condición rag_seccion_sin_reranker")
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
    print(f"Secciones: {cfg.get('n_secciones', len(reporte.get('secciones', [])))} | Riesgos: {len(reporte.get('riesgos_identificados_estructurados', []))}")
    print("\nTiempo por etapa (s):")
    for clave, etiqueta in ETAPAS:
        if clave in tiempos:
            print(f"  {etiqueta:<32}{tiempos[clave]:>9.2f}")
    print("\nPor sección (s):")
    for t in tiempos.get("por_seccion", []):
        print(f"  {t['id']:<6} recuperación {t.get('recuperacion', 0):>7.2f} | CRAG {t.get('crag', 0):>7.2f} | generación {t.get('generacion', 0):>8.2f} | verificación {t.get('verificacion', 0):>8.2f} | redacción {t.get('redaccion', 0):>7.2f}")
    print(f"\nDuración del script: {duracion:.2f} s")
    print(f"JSON:      {ruta_json}")
    print(f"Dashboard: {ruta_html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
