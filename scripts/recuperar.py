# scripts/recuperar.py
"""Solo recuperación (sin LLM): divide la oferta en secciones, recupera los artículos de la KB con el perfil indicado y guarda un JSON con el formato que
lee `scripts.nube --reusar-recuperacion` (secciones con id, titulos y fragmentos con norma, artículo y parte). Usa la misma recuperación que el pipeline
(rag_components.recuperar_seccion en modo verificación); el perfil solo cambia los parámetros de config.PERFILES_RECUPERACION.

Uso:
  python -m scripts.recuperar <oferta.pdf|docx> [--perfil-recuperacion local|amplio] [--salida <carpeta>]
Escribe <salida>/recuperacion_<perfil>_<oferta>_<fecha_hora>.json (por defecto datos/Resultados/<oferta>/)."""
import argparse
import datetime
import hashlib
import json
import logging
import os
import sys

from . import config, document_utils, rag_components, vector_db_manager
from .schemas import FragmentoRecuperado, FuenteNorma, SeccionInforme

logger = logging.getLogger(__name__)


def aplicar_perfil(nombre: str) -> dict:
    """Pone en config los parámetros del perfil y los devuelve. «local» deja la configuración del pipeline tal como está."""
    if nombre not in config.PERFILES_RECUPERACION:
        raise ValueError(f"Perfil de recuperación desconocido: «{nombre}» (hay {', '.join(sorted(config.PERFILES_RECUPERACION))}).")
    parametros = dict(config.PERFILES_RECUPERACION[nombre])
    for clave, valor in parametros.items():
        setattr(config, clave, valor)
    return parametros


def huella_de(nombre: str, parametros: dict) -> str:
    return hashlib.sha256(json.dumps({"perfil": nombre, **parametros}, sort_keys=True).encode("utf-8")).hexdigest()


def recuperar_secciones(vector_db, secciones: list) -> list:
    """SeccionInforme por sección, con la misma llamada que hace el pipeline en modo verificación (la introducción queda sin fragmentos)."""
    informe = []
    for seccion in secciones:
        if config.EXCLUIR_INTRODUCCION and document_utils.es_introduccion(seccion):
            informe.append(SeccionInforme(id=seccion["id"], titulos=seccion["titulos"]))
            continue
        candidatos, docs = rag_components.recuperar_seccion(vector_db, seccion, tope=config.VERIFICAR_TOPE, sin_preambulo=True, con_union=True, con_oraciones=True)
        informe.append(SeccionInforme(
            id=seccion["id"], titulos=seccion["titulos"],
            candidatos=[FuenteNorma(norma=d.metadata.get("norma", ""), articulo=str(d.metadata.get("articulo", ""))) for d in candidatos],
            fragmentos=[FragmentoRecuperado(norma=d.metadata.get("norma", ""), articulo=str(d.metadata.get("articulo", "")),
                                            score=d.metadata.get("relevance_score"), parte=d.metadata.get("parte")) for d in docs]))
        logger.info(f"{seccion['id']} ({', '.join(seccion['titulos'])}): {len(docs)} fragmentos")
    return informe


def armar_json(nombre_oferta: str, informe: list, perfil: str, parametros: dict) -> dict:
    return {"nombre_archivo_original": nombre_oferta, "secciones": [s.model_dump() for s in informe], "configuracion_analisis": {
        "modo": "solo_recuperacion", "condicion": "rag_verificacion", "perfil_recuperacion": perfil, "parametros_recuperacion": parametros,
        "huella_recuperacion": huella_de(perfil, parametros), "n_secciones": len(informe), "use_reranker": config.USE_RERANKER, "recuperacion": config.RECUPERACION,
        "k_subseccion": config.K_SUBSECCION, "top_n_subseccion": config.TOP_N_SUBSECCION, "top_densa_subseccion": config.TOP_DENSA_SUBSECCION,
        "oraciones_cifras": {"n": config.ORACIONES_N, "cupo": config.ORACIONES_CUPO} if config.ORACIONES_CIFRAS else False,
        "tope_fragmentos_por_seccion": config.VERIFICAR_TOPE, "recuperacion_por_subseccion": config.RECUPERACION_POR_SUBSECCION,
        "reranker": rag_components.RERANKER_MODEL_NAME, "embeddings": config.EMBEDDING_MODEL_NAME_OR_PATH}}


def ruta_de_salida(pdf: str, perfil: str, carpeta: str = None) -> str:
    base = os.path.splitext(os.path.basename(pdf))[0]
    nombre_base = "".join(c for c in base if c.isalnum() or c in (" ", "_")).rstrip()
    carpeta = carpeta or os.path.join(config.DIRECTORIO_RESULTADOS_BASE, nombre_base)
    os.makedirs(carpeta, exist_ok=True)
    return os.path.join(carpeta, f"recuperacion_{perfil}_{nombre_base}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Solo recuperación (sin LLM) con un perfil de recuperación; guarda el JSON que lee scripts.nube --reusar-recuperacion.")
    p.add_argument("archivo", help="Ruta de la oferta (.pdf o .docx)")
    p.add_argument("--perfil-recuperacion", default=config.PERFIL_RECUPERACION_DEFECTO, choices=sorted(config.PERFILES_RECUPERACION))
    p.add_argument("--salida", help="Carpeta del JSON (por defecto datos/Resultados/<oferta>/)")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
    if not os.path.isfile(a.archivo):
        print(f"No existe el archivo: {a.archivo}", file=sys.stderr)
        return 1
    parametros = aplicar_perfil(a.perfil_recuperacion)
    secciones = document_utils.dividir_en_secciones(document_utils.extraer_texto_oferta(a.archivo))
    if not secciones:
        print("No se pudo dividir la oferta en secciones.", file=sys.stderr)
        return 1
    embeddings = vector_db_manager.get_embedding_function(config.EMBEDDING_MODEL_NAME_OR_PATH)
    if not embeddings:
        print("No se pudo inicializar el modelo de embeddings.", file=sys.stderr)
        return 1
    vector_db = vector_db_manager.crear_o_cargar_chroma_db(
        chroma_db_path=config.CHROMA_DB_PATH_KB, docs_base_conocimiento_path=config.DIRECTORIO_NORMATIVA, embedding_function=embeddings,
        chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP, recrear_db_flag=False,
        collection_name=config.CHROMA_COLLECTION_KB, manifest_path=config.CHROMA_MANIFEST_PATH_KB, por_articulos=True)
    if not vector_db:
        print("No se pudo cargar el índice de la KB por artículos.", file=sys.stderr)
        return 1
    informe = recuperar_secciones(vector_db, secciones)
    ruta = ruta_de_salida(a.archivo, a.perfil_recuperacion, a.salida)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(armar_json(os.path.basename(a.archivo), informe, a.perfil_recuperacion, parametros), f, ensure_ascii=False, indent=2)
    print(f"Perfil {a.perfil_recuperacion}: {len(informe)} secciones, {sum(len(s.fragmentos) for s in informe)} pares a verificar.\nJSON: {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
