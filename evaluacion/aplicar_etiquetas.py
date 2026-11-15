# evaluacion/aplicar_etiquetas.py
"""Vuelca las etiquetas del CSV unificado de pendientes (evaluacion/diagnosticos/extras_pendientes_<configuración>_<ofertas>.csv, de preparar_extras) a cada <json>_extras.csv.

Uso:
  python -m evaluacion.aplicar_etiquetas [--etiquetas <csv unificado>] [--dudosa sí|no] [--forzar]

Cada fila del unificado trae en «archivo» el <json>_extras.csv de destino (relativo a la raíz del repo) y se empareja con su fila por sección, norma, artículo y cita normalizada con
evaluar.norm. La etiqueta (VALIDA, NO_VALIDA, DUDOSA) va a «etiqueta» y se deriva «valido» (sí/no, lo que lee tabla_comparativa). DUDOSA no se puede contar como sí ni como no: por
defecto «valido» queda vacío (tabla_comparativa no calcula la precisión humana hasta decidirla); --dudosa sí|no la cuenta como válida o como no válida en «valido» (la etiqueta sigue
siendo DUDOSA).
NO pisa una etiqueta existente: la fila que ya tiene «etiqueta» o «valido» se deja como está y se cuenta como omitida; --forzar las reemplaza. Las filas del unificado sin etiqueta
o con una etiqueta que no es VALIDA, NO_VALIDA o DUDOSA no se aplican y se cuentan. Imprime por archivo cuántas se aplicaron."""
import argparse
import csv
import os
import sys

from . import evaluar as E
from . import preparar_extras as PE


def clave(fila: dict) -> tuple:
    return (E.norm(fila.get("seccion")), str(fila.get("norma") or "").strip(), E._articulo(fila.get("articulo")), E.norm(fila.get("cita")))


def _leer(ruta: str) -> tuple:
    """(columnas, filas) de un CSV con «;»."""
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            with open(ruta, encoding=codificacion, newline="") as f:
                lector = csv.DictReader(f, delimiter=";")
                filas = list(lector)
                return list(lector.fieldnames or []), filas
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo leer {ruta}")


def _guardar(ruta: str, columnas: list, filas: list) -> None:
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)
    os.replace(temporal, ruta)


def aplicar_en_archivo(ruta: str, etiquetadas: list, forzar: bool = False, dudosa: str = "") -> dict:
    """Aplica `etiquetadas` (filas del unificado con etiqueta válida) a un <json>_extras.csv. Devuelve las cuentas {'aplicadas', 'omitidas', 'no_encontradas', 'dudosas_sin_valido'}."""
    columnas, filas = _leer(ruta)
    columnas += [c for c in ("etiqueta", "valido") if c not in columnas]
    por_clave = {}
    for f in filas:
        por_clave.setdefault(clave(f), []).append(f)
    cuentas = {"aplicadas": 0, "omitidas": 0, "no_encontradas": 0, "dudosas_sin_valido": 0}
    for e in etiquetadas:
        candidatas = por_clave.get(clave(e)) or []
        if not candidatas:
            cuentas["no_encontradas"] += 1
            continue
        destino = candidatas.pop(0)               # con claves repetidas, cada fila del unificado toma la siguiente fila de destino
        etiqueta = PE.normalizar_etiqueta(e.get("etiqueta"))
        previa = (destino.get("etiqueta") or "").strip() or (destino.get("valido") or "").strip()
        if previa and not forzar:
            cuentas["omitidas"] += 1
            continue
        valido = dudosa if etiqueta == "DUDOSA" else PE.VALIDO_DE[etiqueta]
        destino["etiqueta"], destino["valido"] = etiqueta, valido
        if e.get("nota"):
            destino["nota"] = " ".join(x for x in (destino.get("nota"), str(e["nota"]).strip()) if x)
        cuentas["aplicadas"] += 1
        cuentas["dudosas_sin_valido"] += etiqueta == "DUDOSA" and not valido
    if cuentas["aplicadas"]:
        _guardar(ruta, columnas, filas)
    return cuentas


def main(argv=None):
    p = argparse.ArgumentParser(description="Vuelca las etiquetas del CSV unificado de pendientes a cada <json>_extras.csv (no pisa etiquetas salvo con --forzar)")
    p.add_argument("--etiquetas", required=True, help="CSV unificado de preparar_extras, con la columna «etiqueta» completa")
    p.add_argument("--dudosa", choices=["sí", "si", "no"], default=None, help="cómo cuenta DUDOSA en «valido» (por defecto queda vacío)")
    p.add_argument("--forzar", action="store_true", help="reemplaza las etiquetas que ya existen en los <json>_extras.csv")
    a = p.parse_args(argv)
    if not os.path.isfile(a.etiquetas):
        raise SystemExit(f"No existe {a.etiquetas}")
    _, filas = _leer(a.etiquetas)
    dudosa = {"sí": "sí", "si": "sí", "no": "no"}.get(a.dudosa or "", "")
    sin_etiqueta = [f for f in filas if not (f.get("etiqueta") or "").strip()]
    invalidas = [f for f in filas if (f.get("etiqueta") or "").strip() and not PE.normalizar_etiqueta(f.get("etiqueta"))]
    por_archivo = {}
    for f in filas:
        if PE.normalizar_etiqueta(f.get("etiqueta")):
            por_archivo.setdefault(f.get("archivo") or "", []).append(f)
    total = {"aplicadas": 0, "omitidas": 0, "no_encontradas": 0, "dudosas_sin_valido": 0}
    for archivo, etiquetadas in por_archivo.items():
        ruta = os.path.join(PE.RAIZ, archivo)
        if not archivo or not os.path.isfile(ruta):
            print(f"{archivo or '(sin archivo)'}: no existe; {len(etiquetadas)} etiquetas sin aplicar.", file=sys.stderr)
            total["no_encontradas"] += len(etiquetadas)
            continue
        c = aplicar_en_archivo(ruta, etiquetadas, a.forzar, dudosa)
        total = {k: total[k] + c[k] for k in total}
        print(f"{archivo}: {c['aplicadas']} aplicadas, {c['omitidas']} omitidas (ya tenían etiqueta), {c['no_encontradas']} sin fila de destino.")
    print(f"Total: {total['aplicadas']} aplicadas, {total['omitidas']} omitidas por tener etiqueta (usá --forzar para reemplazarlas), {total['no_encontradas']} sin fila de destino; "
          f"{len(sin_etiqueta)} filas sin etiqueta y {len(invalidas)} con una etiqueta que no es VALIDA, NO_VALIDA ni DUDOSA.")
    if total["dudosas_sin_valido"]:
        print(f"Hay {total['dudosas_sin_valido']} DUDOSA con «valido» vacío: tabla_comparativa no calcula la precisión humana hasta decidirlas (repetí con --dudosa sí|no --forzar, o completá «valido»).")
    return total


if __name__ == "__main__":
    main()
