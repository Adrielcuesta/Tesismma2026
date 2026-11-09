# scripts/elegir_json.py
"""Elige, en la carpeta de resultados de una oferta, el JSON de analisis mas reciente con una condicion dada (configuracion_analisis.condicion),
sin mirar el nombre del archivo. Excluye los reclasificados, los parciales y los de la nube (deepinfra).

Uso:
  python -m scripts.elegir_json <carpeta> [--condicion sin_rag] [--modo-generacion verificacion|lista]
Imprime los candidatos y, al final, "JSON: <ruta>" (o sale con codigo 1 si no hay ninguno)."""
import argparse
import glob
import json
import os
import sys

EXCLUIDOS = ("reclasificado", "parcial", "deepinfra")


def _campo_de(ruta: str, campo: str):
    """configuracion_analisis.<campo> del JSON; None si no se puede leer."""
    try:
        with open(ruta, encoding="utf-8") as f:
            return (json.load(f).get("configuracion_analisis") or {}).get(campo)
    except (OSError, ValueError, AttributeError):
        return None


def condicion_de(ruta: str):
    """configuracion_analisis.condicion del JSON; None si no se puede leer."""
    return _campo_de(ruta, "condicion")


def elegir(carpeta: str, condicion: str = "sin_rag", modo_generacion: str = None) -> tuple:
    """(elegido o None, lineas): el analisis_riesgos_*.json mas reciente (por fecha de modificacion) con esa condicion, y el detalle de cada candidato.
    Con `modo_generacion` ('verificacion' o 'lista') exige ademas configuracion_analisis.modo_generacion igual a ese valor."""
    candidatos = sorted(glob.glob(os.path.join(carpeta, "analisis_riesgos_*.json")), key=os.path.getmtime, reverse=True)
    lineas, elegido = [], None
    for ruta in candidatos:
        nombre = os.path.basename(ruta)
        if any(x in nombre.lower() for x in EXCLUIDOS):
            lineas.append(f"  excluido por el nombre: {nombre}")
            continue
        cond = condicion_de(ruta)
        modo = _campo_de(ruta, "modo_generacion") if modo_generacion else None
        if cond == condicion and (not modo_generacion or modo == modo_generacion) and elegido is None:
            elegido = ruta
            lineas.append(f"  ELEGIDO ({cond}{', ' + str(modo) if modo_generacion else ''}): {nombre}")
        else:
            lineas.append(f"  {'ilegible' if cond is None else 'condicion ' + str(cond)}{', modo ' + str(modo) if modo_generacion else ''}: {nombre}")
    return elegido, lineas


def elegir_por_sufijo(carpeta: str, sufijo: str):
    """El analisis_riesgos_*_<sufijo>.json mas reciente (por fecha de modificacion) de la carpeta, o None. El sufijo es el final exacto del nombre,
    sin la extension (por ejemplo 'deepinfra-qwen3-32b-thinking-amplio'): un '-humo10' detras no coincide."""
    candidatos = sorted(glob.glob(os.path.join(carpeta, f"analisis_riesgos_*_{sufijo}.json")), key=os.path.getmtime, reverse=True)
    return candidatos[0] if candidatos else None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Elige el JSON mas reciente de una carpeta con la condicion indicada.")
    p.add_argument("carpeta")
    p.add_argument("--condicion", default="sin_rag")
    p.add_argument("--modo-generacion", choices=["verificacion", "lista"], help="exige ademas configuracion_analisis.modo_generacion (opcional)")
    a = p.parse_args(argv)
    elegido, lineas = elegir(a.carpeta, a.condicion, a.modo_generacion)
    print(f"Candidatos en {a.carpeta} (condicion buscada: {a.condicion}):")
    print("\n".join(lineas) if lineas else "  (ninguno)")
    if not elegido:
        print(f"No hay un JSON con condicion {a.condicion} en {a.carpeta}.", file=sys.stderr)
        return 1
    print(f"JSON: {elegido}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
