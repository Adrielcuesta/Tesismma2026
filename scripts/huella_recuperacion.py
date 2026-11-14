# scripts/huella_recuperacion.py
"""Huellas de la recuperación, sin dependencias pesadas (las usan recuperar, nube, el camino local y la tabla comparativa).

- huella_de_pares: hash de QUÉ pares (sección, norma, artículo, parte) se verifican; dos corridas con la misma huella verificaron exactamente los mismos pares,
  sea cual sea el perfil, el orden o los puntajes con que se recuperaron. Sirve también para los JSON de v1, que no guardan ninguna huella.
- sha256_archivo: hash del archivo JSON de recuperación que se reusó."""
import hashlib
import json


def huella_de_pares(secciones: list) -> str:
    """sha256 de los pares (id de sección, norma, artículo, parte) de secciones[].fragmentos, ordenados (el orden y los puntajes no cuentan; las repeticiones sí)."""
    pares = sorted((str(s.get("id")), str(f.get("norma")), str(f.get("articulo")), str(f.get("parte"))) for s in secciones or [] for f in s.get("fragmentos") or [])
    return hashlib.sha256(json.dumps(pares, ensure_ascii=False).encode("utf-8")).hexdigest()


def sha256_archivo(ruta: str) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()
