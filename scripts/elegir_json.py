# scripts/elegir_json.py
"""Elige, en la carpeta de resultados de una oferta, el JSON de analisis mas reciente con una condicion dada (configuracion_analisis.condicion),
sin mirar el nombre del archivo. Excluye los reclasificados, los parciales y los de la nube (deepinfra).

Uso:
  python -m scripts.elegir_json <carpeta> [--condicion sin_rag]
Imprime los candidatos y, al final, "JSON: <ruta>" (o sale con codigo 1 si no hay ninguno)."""
import argparse
import glob
import json
import os
import sys

EXCLUIDOS = ("reclasificado", "parcial", "deepinfra")


def condicion_de(ruta: str):
    """configuracion_analisis.condicion del JSON; None si no se puede leer."""
    try:
        with open(ruta, encoding="utf-8") as f:
            return (json.load(f).get("configuracion_analisis") or {}).get("condicion")
    except (OSError, ValueError, AttributeError):
        return None


def elegir(carpeta: str, condicion: str = "sin_rag") -> tuple:
    """(elegido o None, lineas): el analisis_riesgos_*.json mas reciente (por fecha de modificacion) con esa condicion, y el detalle de cada candidato."""
    candidatos = sorted(glob.glob(os.path.join(carpeta, "analisis_riesgos_*.json")), key=os.path.getmtime, reverse=True)
    lineas, elegido = [], None
    for ruta in candidatos:
        nombre = os.path.basename(ruta)
        if any(x in nombre.lower() for x in EXCLUIDOS):
            lineas.append(f"  excluido por el nombre: {nombre}")
            continue
        cond = condicion_de(ruta)
        if cond == condicion and elegido is None:
            elegido = ruta
            lineas.append(f"  ELEGIDO ({cond}): {nombre}")
        else:
            lineas.append(f"  {'ilegible' if cond is None else 'condicion ' + str(cond)}: {nombre}")
    return elegido, lineas


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Elige el JSON mas reciente de una carpeta con la condicion indicada.")
    p.add_argument("carpeta")
    p.add_argument("--condicion", default="sin_rag")
    a = p.parse_args(argv)
    elegido, lineas = elegir(a.carpeta, a.condicion)
    print(f"Candidatos en {a.carpeta} (condicion buscada: {a.condicion}):")
    print("\n".join(lineas) if lineas else "  (ninguno)")
    if not elegido:
        print(f"No hay un JSON con condicion {a.condicion} en {a.carpeta}.", file=sys.stderr)
        return 1
    print(f"JSON: {elegido}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
