# evaluacion/oferta_texto.py
"""Texto de las ofertas (P1–P12) y sus oraciones numeradas tal como las ve el verificador (segmentación de scripts.document_utils, sin LLM ni embeddings).
Lo usan diff_trampas.py y verificar_gt_literal.py. Lee datos/ProyectoAnalizar, así que solo lo corre el usuario; los imports de scripts van tardíos (son pesados)."""
import glob
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
CARPETA_OFERTAS = os.path.join(RAIZ, "datos", "ProyectoAnalizar")


def ruta_oferta(oferta: str, carpeta: str = CARPETA_OFERTAS, extension: str = None) -> str:
    """Archivo de la oferta («P1» → P1_oferta_*.pdf o .docx en datos/ProyectoAnalizar; con `extension`, solo ese formato, para leer el mismo archivo que la corrida);
    error claro si no está. Sin `extension` y con los dos formatos, el primero en orden alfabético (.docx)."""
    extensiones = (extension.lstrip("."),) if extension else ("pdf", "docx")
    candidatos = sorted(r for e in extensiones for r in glob.glob(os.path.join(carpeta, f"{oferta}_oferta_*.{e}")))
    if not candidatos:
        raise FileNotFoundError(f"No hay un archivo {oferta}_oferta_*.{'/.'.join(extensiones)} en {carpeta}")
    return candidatos[0]


def texto_de_oferta(oferta: str, carpeta: str = CARPETA_OFERTAS) -> str:
    from scripts import document_utils
    return document_utils.extraer_texto_oferta(ruta_oferta(oferta, carpeta))


def oraciones_por_seccion(oferta: str, carpeta: str = CARPETA_OFERTAS) -> dict:
    """{id de sección ('S3'): [(id de oración, texto)]} con la división en secciones y la numeración que usa el verificador (incluye la introducción, que el pipeline no
    verifica; no cambia los IDs de las demás secciones)."""
    from scripts import document_utils
    secciones = document_utils.dividir_en_secciones(document_utils.extraer_texto_oferta(ruta_oferta(oferta, carpeta)))
    return {s["id"]: document_utils.numerar_oraciones(s["texto"]) for s in secciones}
