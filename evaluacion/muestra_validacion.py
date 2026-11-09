# evaluacion/muestra_validacion.py
"""Muestra aleatoria estratificada (por configuración y veredicto del juez) de las brechas que no son trampas, para que la persona las marque a mano,
y modo para volcar esas marcas en el <json>_juez.csv de origen. La muestra NO muestra el veredicto del juez (evita el anclaje).

Uso:
  python -m evaluacion.muestra_validacion --config evaluacion/config_tabla_ejemplo.json [--salida muestra_validacion.csv] [--n 30] [--seed 42]
  # se completa la columna «valido» con 1 (la brecha es real) o 0 (no lo es), y después:
  python -m evaluacion.muestra_validacion --volcar muestra_validacion.csv
Después de volcar, evaluar.py calcula la precisión humana y el kappa juez–humano (las marcas quedan en la columna «valido» de <json>_juez.csv)."""
import argparse
import csv
import json
import os
import random
import sys

from .evaluar import _clave_extra, leer_csv, norm, ruta_juez as ruta_csv_juez
from .juez import VEREDICTOS, clave_brecha, clave_fila
from .tabla_comparativa import cargar_config

COLUMNAS = ["id", "configuracion", "oferta", "seccion", "norma", "articulo", "cita", "titulo", "texto_articulo", "valido", "ruta_juez"]


def cuotas(tamanos: dict, n: int) -> dict:
    """Asignación proporcional por estrato con al menos 1 por estrato (si n alcanza), sin pasar del tamaño del estrato. Suma min(n, total)."""
    total = sum(tamanos.values())
    if total <= n:
        return dict(tamanos)
    q = {k: min(v, max(1, round(n * v / total))) for k, v in tamanos.items()}
    while sum(q.values()) > n:
        k = max((k for k in q if q[k] > 1), key=lambda k: (q[k], k))
        q[k] -= 1
    while sum(q.values()) < n:
        k = max((k for k in q if q[k] < tamanos[k]), key=lambda k: (tamanos[k] - q[k], k))
        q[k] += 1
    return q


def elegibles(cfg: dict) -> list:
    """Filas de los <json>_juez.csv con veredicto, de todas las configuraciones y ofertas, con los datos para mostrarlas."""
    filas = []
    for nombre, ofertas in cfg["configuraciones"].items():
        for oferta, ruta in ofertas.items():
            ruta_juez = ruta_csv_juez(ruta) if ruta else ""
            if not ruta or not os.path.isfile(ruta) or not os.path.isfile(ruta_juez):
                print(f"Aviso: {nombre} / {oferta}: sin JSON o sin {os.path.basename(ruta_juez) or '<json>_juez.csv'}; se omite.", file=sys.stderr)
                continue
            with open(ruta, encoding="utf-8") as f:
                brechas = {clave_brecha(b): b for b in json.load(f).get("registro_brechas") or []}
            for r in leer_csv(ruta_juez):
                if r.get("juez_veredicto") in VEREDICTOS:
                    filas.append({"configuracion": nombre, "oferta": oferta, "ruta_juez": ruta_juez, "veredicto": r["juez_veredicto"], "seccion": r["seccion"], "norma": r["norma"],
                                  "articulo": r["articulo"], "cita": r["cita"], "titulo": r.get("titulo", ""),
                                  "texto_articulo": (brechas.get(clave_fila(r)) or {}).get("texto_articulo") or ""})
    return filas


def muestrear(filas: list, n: int = 30, seed: int = 42) -> list:
    estratos = {}
    for f in sorted(filas, key=lambda f: (f["oferta"], f["seccion"], f["norma"], f["articulo"], f["cita"])):
        estratos.setdefault((f["configuracion"], f["veredicto"]), []).append(f)
    rng, q = random.Random(seed), cuotas({k: len(v) for k, v in estratos.items()}, n)
    elegidas = [x for k in sorted(estratos) for x in rng.sample(estratos[k], q[k])]
    rng.shuffle(elegidas)
    return [{**f, "id": i + 1, "valido": ""} for i, f in enumerate(elegidas)]


def escribir(filas: list, ruta: str):
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def marca(valor):
    """'sí' / 'no' para 1/0, sí/no; None si está vacía o no se entiende."""
    return {"1": "sí", "si": "sí", "0": "no", "no": "no"}.get(norm(valor))


def volcar(ruta_muestra: str) -> dict:
    """Pasa las marcas de la muestra a la columna «valido» de cada <json>_juez.csv. Devuelve {'volcadas', 'sin_marca', 'no_encontradas'}."""
    por_archivo, sin_marca = {}, 0
    for r in leer_csv(ruta_muestra):
        m = marca(r.get("valido"))
        if m is None:
            sin_marca += 1
        else:
            por_archivo.setdefault(r["ruta_juez"], []).append((_clave_extra(r["seccion"], r["norma"], r["articulo"], r["cita"]), m))
    volcadas = no_encontradas = 0
    for ruta, marcas in por_archivo.items():
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            lector = csv.DictReader(f, delimiter=";")
            columnas, filas = list(lector.fieldnames or []), list(lector)
        por_clave = {clave_fila(r): r for r in filas}
        for clave, m in marcas:
            if clave in por_clave:
                por_clave[clave]["valido"], volcadas = m, volcadas + 1
            else:
                no_encontradas += 1
        with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columnas, delimiter=";")
            w.writeheader()
            w.writerows(filas)
    return {"volcadas": volcadas, "sin_marca": sin_marca, "no_encontradas": no_encontradas}


def main(argv=None):
    p = argparse.ArgumentParser(description="Muestra estratificada para validación humana y volcado de las marcas")
    p.add_argument("--config", help="JSON de configuración (el mismo de tabla_comparativa)")
    p.add_argument("--salida", default="muestra_validacion.csv")
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--volcar", metavar="CSV", help="muestra con la columna «valido» completa (1/0): vuelca las marcas a los <json>_juez.csv")
    a = p.parse_args(argv)
    if a.volcar:
        r = volcar(a.volcar)
        print(f"Volcadas {r['volcadas']} marcas | sin marcar {r['sin_marca']} | no encontradas en su CSV {r['no_encontradas']}")
        return r
    if not a.config:
        raise SystemExit("Indicá --config (para armar la muestra) o --volcar (para volcar las marcas).")
    muestra = muestrear(elegibles(cargar_config(a.config)), a.n, a.seed)
    if not muestra:
        raise SystemExit("No hay brechas con veredicto del juez: corré antes evaluacion.juez.")
    escribir(muestra, a.salida)
    print(f"Muestra de {len(muestra)} brechas en {a.salida}: completá «valido» con 1 (brecha real) o 0 y corré --volcar.")
    return muestra


if __name__ == "__main__":
    main()
