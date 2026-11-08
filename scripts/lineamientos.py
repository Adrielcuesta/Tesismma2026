# scripts/lineamientos.py
"""Lineamientos de la empresa (método de evaluación). Nunca se indexan: de aquí sale solo lo que declara criterios_empresa.json."""
import os
import re
import json
import hashlib
import logging

from . import document_utils

logger = logging.getLogger(__name__)

ARCHIVO_CRITERIOS = "criterios_empresa.json"
# Claves obligatorias de criterios_empresa.json. 'documento_criterios' nombra el documento de criterios (p. ej. NORM_07);
# 'texto_para_el_modelo' declara qué capítulos y artículos de ese documento se le entregan al modelo.
CLAVES_REQUERIDAS = ("documento_criterios", "texto_para_el_modelo", "contenido_minimo_oferta", "probabilidad_por_fuente", "umbral_brecha_relativa",
                     "rango_impacto_por_clase", "matriz_nivel", "consistencia", "decision_aceptabilidad", "estrategia_por_nivel",
                     "responsables", "categorias_rbs", "solicitudes_al_oferente")
CLAVES_TEXTO_MODELO = ("capitulos", "articulos")

RE_CAPITULO_NUMERO = re.compile(r'^\s*CAP[ÍI]TULO\s+(\d+)\b', re.IGNORECASE)
# Encabezado de artículo: número y título que empieza en mayúsculas. Una referencia "(Art. 2.7)" dentro del texto no corta.
RE_ENCABEZADO_ARTICULO = re.compile(r'^Art\.\s+(\d+)\.(\d+)\.\s+[A-ZÁÉÍÓÚÑ]{2}')


class LineamientosError(Exception):
    pass


def _fin_de_bloque(lineas: list, desde: int, hasta_capitulo_solo: bool) -> int:
    """Índice de la línea donde termina el bloque que empieza en `desde` (la siguiente de capítulo o, si corresponde, de artículo)."""
    for i in range(desde + 1, len(lineas)):
        if RE_CAPITULO_NUMERO.match(lineas[i]) or (not hasta_capitulo_solo and RE_ENCABEZADO_ARTICULO.match(lineas[i])):
            return i
    return len(lineas)


def _mejor_bloque(lineas: list, inicios: list, hasta_capitulo_solo: bool) -> str:
    """De varias apariciones (p. ej. índice y cuerpo) se queda con la de más texto."""
    bloques = ["\n".join(lineas[i:_fin_de_bloque(lineas, i, hasta_capitulo_solo)]).strip() for i in inicios]
    return max(bloques, key=len, default="")


def extraer_capitulo(texto: str, n: int) -> str:
    """Texto del capítulo n (desde su línea 'CAPÍTULO n.' hasta el siguiente capítulo)."""
    lineas = texto.split("\n")
    inicios = [i for i, l in enumerate(lineas) if (m := RE_CAPITULO_NUMERO.match(l)) and int(m.group(1)) == int(n)]
    bloque = _mejor_bloque(lineas, inicios, True)
    if not bloque:
        raise LineamientosError(f"No se encontró el capítulo {n} en el documento de criterios.")
    return bloque


def extraer_articulo(texto: str, numero: str) -> str:
    """Texto del artículo 'X.Y' (desde su línea 'Art. X.Y.' hasta el siguiente artículo o capítulo)."""
    x, y = (int(p) for p in str(numero).split("."))
    lineas = texto.split("\n")
    inicios = [i for i, l in enumerate(lineas) if (m := RE_ENCABEZADO_ARTICULO.match(l)) and (int(m.group(1)), int(m.group(2))) == (x, y)]
    bloque = _mejor_bloque(lineas, inicios, False)
    if not bloque:
        raise LineamientosError(f"No se encontró el artículo {numero} en el documento de criterios.")
    return bloque


def _archivos_de_la_carpeta(directorio: str) -> dict:
    """{nombre_base: ruta}: si existen .docx y .pdf con el mismo nombre, se usa el .docx."""
    elegidos = {}
    for nombre in sorted(os.listdir(directorio)):
        base, ext = os.path.splitext(nombre)
        if ext.lower() not in document_utils.EXTENSIONES_SOPORTADAS:
            continue
        if base not in elegidos or ext.lower() == ".docx":
            elegidos[base] = os.path.join(directorio, nombre)
    return elegidos


def cargar_lineamientos(directorio: str) -> dict:
    """Lee los documentos y criterios_empresa.json de `directorio`.
    Devuelve {'criterios', 'texto_para_el_modelo', 'huella', 'documentos'}."""
    if not os.path.isdir(directorio):
        raise LineamientosError(f"No existe la carpeta de lineamientos: {directorio}")
    ruta_json = os.path.join(directorio, ARCHIVO_CRITERIOS)
    if not os.path.isfile(ruta_json):
        raise LineamientosError(f"Falta {ARCHIVO_CRITERIOS} en {directorio}")
    try:
        with open(ruta_json, encoding="utf-8") as f:
            criterios = json.load(f)
    except ValueError as e:
        raise LineamientosError(f"{ARCHIVO_CRITERIOS} no es un JSON válido: {e}") from e

    faltantes = [c for c in CLAVES_REQUERIDAS if c not in criterios]
    if faltantes:
        raise LineamientosError(f"{ARCHIVO_CRITERIOS} no tiene las claves: {faltantes}")
    declarado = criterios["texto_para_el_modelo"]
    faltantes = [c for c in CLAVES_TEXTO_MODELO if not isinstance(declarado, dict) or c not in declarado]
    if faltantes:
        raise LineamientosError(f"'texto_para_el_modelo' de {ARCHIVO_CRITERIOS} no tiene las claves: {faltantes}")

    documentos = {document_utils.norma_de_archivo(base): ruta for base, ruta in _archivos_de_la_carpeta(directorio).items()}
    norma = str(criterios["documento_criterios"]).upper()
    if norma not in documentos:
        raise LineamientosError(f"El documento de criterios {norma} que declara {ARCHIVO_CRITERIOS} no está en {directorio} (hay: {sorted(documentos)})")

    texto = document_utils.texto_limpio_de_archivo(documentos[norma])
    partes = [extraer_capitulo(texto, n) for n in declarado["capitulos"]] + [extraer_articulo(texto, a) for a in declarado["articulos"]]
    texto_modelo = "\n\n".join(partes)

    huella = hashlib.sha256((texto_modelo + json.dumps(criterios, sort_keys=True, ensure_ascii=False)).encode("utf-8")).hexdigest()
    logger.info(f"Lineamientos: {len(documentos)} documentos ({sorted(documentos)}); texto_para_el_modelo de {norma}: "
                f"{len(texto_modelo)} caracteres; huella {huella[:12]}.")
    return {"criterios": criterios, "texto_para_el_modelo": texto_modelo, "huella": huella,
            "documentos": {n: os.path.basename(r) for n, r in documentos.items()}}
