# scripts/vector_db_manager.py
import os
import json
import shutil
from . import document_utils
from . import config
import logging

logger = logging.getLogger(__name__)

def get_embedding_function(model_name_or_path):
    from langchain_community.embeddings import SentenceTransformerEmbeddings  # import tardío: --resumen no carga embeddings
    device = 'cpu'
    cache_folder_path = config.CACHE_DIR_HF
    logger.info(f"Intentando inicializar modelo de embeddings desde: '{model_name_or_path}' en dispositivo '{device}'.")
    try:
        embedding_function = SentenceTransformerEmbeddings(
            model_name=model_name_or_path,
            model_kwargs={'device': device},
            cache_folder=cache_folder_path
        )
        logger.info(f"Modelo de embeddings '{os.path.basename(str(model_name_or_path))}' inicializado exitosamente.")
        return embedding_function
    except Exception as e:
        logger.error(f"ERROR CRÍTICO al inicializar SentenceTransformerEmbeddings: {e}", exc_info=True)
        return None

def _firma_indexado(docs_path, chunk_size, chunk_overlap, embedding_function, por_articulos=False):
    """Qué se indexó: archivos (nombre, tamaño, fecha) + parámetros de fragmentado + embedding."""
    archivos = []
    if os.path.isdir(docs_path):
        for nombre in sorted(os.listdir(docs_path)):
            if nombre.lower().endswith(document_utils.EXTENSIONES_SOPORTADAS):
                if por_articulos and document_utils.norma_de_archivo(nombre) == config.NORMA_COMPLETA:
                    continue  # va completa en el prompt: no forma parte del índice
                ruta = os.path.join(docs_path, nombre)
                archivos.append([nombre, os.path.getsize(ruta), int(os.path.getmtime(ruta))])
    firma = {"archivos": archivos, "embedding": str(getattr(embedding_function, "model_name", "desconocido"))}
    if por_articulos:
        firma["chunker_articulos"] = {"version": config.VERSION_CHUNKER_ARTICULOS,
                                      "max_chars_articulo": config.MAX_CHARS_ARTICULO,
                                      "umbral_encabezado": config.UMBRAL_ENCABEZADO}
    else:
        firma.update({"chunk_size": chunk_size, "chunk_overlap": chunk_overlap})
    return firma

def _leer_manifest(manifest_path=None):
    try:
        with open(manifest_path or config.CHROMA_MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None

def crear_o_cargar_chroma_db(chroma_db_path, docs_base_conocimiento_path, embedding_function,
                               chunk_size, chunk_overlap, recrear_db_flag,
                               collection_name=None, manifest_path=None, por_articulos=False):
    from langchain_community.vectorstores import Chroma  # import tardío: --resumen no carga Chroma
    if not embedding_function:
        logger.error("Función de embeddings no proporcionada.")
        return None

    manifest_path = manifest_path or config.CHROMA_MANIFEST_PATH
    kwargs_coleccion = {"collection_name": collection_name} if collection_name else {}
    db_exists = os.path.exists(os.path.join(chroma_db_path, 'chroma.sqlite3'))
    firma = _firma_indexado(docs_base_conocimiento_path, chunk_size, chunk_overlap, embedding_function, por_articulos)
    if db_exists and not recrear_db_flag and _leer_manifest(manifest_path) != firma:
        logger.info("La Base de Conocimiento, CHUNK_SIZE o el embedding cambiaron respecto de lo indexado: se reindexa.")
        recrear_db_flag = True
    if recrear_db_flag or not db_exists:
        if recrear_db_flag and db_exists:
            logger.info(f"Borrando DB existente en: {chroma_db_path} porque se solicitó su recreación.")
            try:
                shutil.rmtree(chroma_db_path)
            except Exception as e:
                logger.error(f"Error al borrar la carpeta de ChromaDB: {e}")
                return None
        
        logger.info(f"Creando nueva base de datos vectorial en: {chroma_db_path}")
        if por_articulos:
            fragmentos = document_utils.cargar_kb_por_articulos(docs_base_conocimiento_path)
        else:
            fragmentos = document_utils.cargar_y_procesar_pdfs_de_carpeta(
                docs_base_conocimiento_path, chunk_size, chunk_overlap
            )
        if not fragmentos:
            logger.error("No se generaron fragmentos. La DB no se creará.")
            return None

        try:
            vector_db = Chroma.from_documents(documents=fragmentos, embedding=embedding_function, persist_directory=chroma_db_path, **kwargs_coleccion)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(firma, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ ¡ÉXITO! Base de datos vectorial creada con {len(fragmentos)} fragmentos.")
            return vector_db
        except Exception as e:
            logger.error(f"ERROR FATAL durante la creación de la base de datos: {e}", exc_info=True)
            return None
    else:
        logger.info(f"Cargando base de datos vectorial existente desde: {chroma_db_path}")
        try:
            vector_db = Chroma(persist_directory=chroma_db_path, embedding_function=embedding_function, **kwargs_coleccion)
            count = vector_db._collection.count()
            if count == 0:
                logger.error("Error: La DB existente está vacía. Bórrela manualmente o active la opción para recrearla.")
                return None
            logger.info(f"✅ Base de datos vectorial cargada. Contiene {count} fragmentos.")
            return vector_db
        except Exception as e:
            logger.error(f"Error crítico al cargar la DB Chroma: {e}", exc_info=True)
            return None

def _saltos_de_numeracion(numeros):
    """Huecos entre artículos consecutivos: mismo capítulo con salto > 1, o capítulo nuevo que no empieza en 0/1."""
    saltos = []
    for (a1, b1), (a2, b2) in zip(numeros, numeros[1:]):
        if (a2 == a1 and b2 != b1 + 1) or (a2 != a1 and (a2 != a1 + 1 or b2 not in (0, 1))):
            saltos.append(f"{a1}.{b1}→{a2}.{b2}")
    return saltos

def imprimir_resumen(carpeta=None):
    """Verificación sin embeddings ni Chroma: cómo quedaría el índice por artículos, norma por norma."""
    from collections import Counter
    carpeta = carpeta or config.DIRECTORIO_BASE_CONOCIMIENTO
    archivos = [f for f in sorted(os.listdir(carpeta)) if f.lower().endswith(document_utils.EXTENSIONES_SOPORTADAS)]
    for nombre in archivos:
        ruta = os.path.join(carpeta, nombre)
        norma = document_utils.norma_de_archivo(nombre)
        print(f"\n=== {norma} ({nombre}) ===")
        if norma == config.NORMA_COMPLETA:
            print(f"  Fuera del índice. Texto completo para el prompt: {len(document_utils.cargar_norma_completa(norma, carpeta))} caracteres.")
            continue
        r = document_utils.analizar_norma_por_articulos(ruta)
        chunks = r["chunks"]
        arts = [c for c in chunks if c.metadata["articulo"] != "preambulo"]
        primeros = [c for c in arts if c.metadata["parte"] == 1]
        numeros = [tuple(int(n) for n in c.metadata["articulo"].split(".")) for c in primeros]
        repetidos = [a for a, n in Counter(c.metadata["articulo"] for c in primeros).items() if n > 1]
        vacios = [c.metadata["articulo"] for c in primeros
                  if len(c.page_content.split("\n", 1)[1] if "\n" in c.page_content else "") < 40]
        print(f"  Artículos: {len(primeros)} | chunks: {len(chunks)} (preámbulo: {len(chunks) - len(arts)}) | "
              f"chunks con parte>1: {sum(1 for c in chunks if c.metadata['parte'] > 1)} | "
              f"longitud máx. de chunk: {max((len(c.page_content) for c in chunks), default=0)}")
        print(f"  Primer artículo: {primeros[0].metadata['articulo'] if primeros else '-'} | "
              f"último: {primeros[-1].metadata['articulo'] if primeros else '-'}")
        print(f"  Duplicados: {repetidos or 'ninguno'} | vacíos: {vacios or 'ninguno'}")
        print(f"  Saltos de numeración: {_saltos_de_numeracion(numeros) or 'ninguno'}")
        print(f"  Líneas 'Art.' tratadas como texto (número no creciente): {[f'{x}.{y} (pág. {p})' for p, (x, y) in r['rechazadas']] or 'ninguna'}")
        print(f"  Texto sin artículo tras un capítulo (descartado): {r['huerfano_chars']} caracteres")
        print(f"  'Control de interpretación' conservado como preámbulo: {'sí' if r['control_interpretacion'] else 'no encontrado'}")
        pre = next((c for c in chunks if c.metadata["articulo"] == "preambulo"), None)
        print(f"  Preámbulo (200 car., pág. {pre.metadata['pagina']}): {pre.page_content[:200]!r}" if pre else "  Preámbulo: ninguno")
        print(f"  Páginas descartadas: {', '.join(f'{p} ({m})' for p, m in r['descartadas']) or 'ninguna'}")

def _pares_umbral_alerta(nodo):
    """Pares (norma, artículo) de las claves 'umbral_alerta' ("NORM_0X, Art. X.Y"); ignora cualquier otro texto del JSON."""
    import re
    pares = set()
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if clave == "umbral_alerta":
                for v in (valor if isinstance(valor, list) else [valor]):
                    if isinstance(v, str):
                        pares.update((n.upper(), a) for n, a in re.findall(r'(NORM_\d{2})\s*,\s*Art\.\s*(\d+\.\d+)', v, re.IGNORECASE))
            else:
                pares |= _pares_umbral_alerta(valor)
    elif isinstance(nodo, list):
        for v in nodo:
            pares |= _pares_umbral_alerta(v)
    elif isinstance(nodo, str) and nodo.lstrip()[:1] in ("{", "["):
        try:  # "ground_truth" es un string que contiene otro JSON
            pares |= _pares_umbral_alerta(json.loads(nodo))
        except ValueError:
            pass
    return pares

def imprimir_cobertura_gt(ruta_gt, carpeta=None):
    """Pares (norma, artículo) del ground truth que no existen como chunk en la KB (solo se leen las claves 'umbral_alerta')."""
    carpeta = carpeta or config.DIRECTORIO_BASE_CONOCIMIENTO
    with open(ruta_gt, encoding="utf-8") as f:
        pares = _pares_umbral_alerta(json.load(f))
    if len(pares) != 60:
        raise SystemExit(f"ERROR: se esperaban 60 pares únicos (norma, artículo) en 'umbral_alerta' y se leyeron {len(pares)}; la cobertura no es confiable.")
    existentes = set()
    for nombre in sorted(os.listdir(carpeta)):
        if nombre.lower().endswith(document_utils.EXTENSIONES_SOPORTADAS) and document_utils.norma_de_archivo(nombre) != config.NORMA_COMPLETA:
            existentes |= {(c.metadata["norma"], c.metadata["articulo"])
                           for c in document_utils.chunkear_norma_por_articulos(os.path.join(carpeta, nombre))}
    faltantes = sorted((n, a) for n, a in pares if n != config.NORMA_COMPLETA and (n, a) not in existentes)
    print(f"Pares únicos en el ground truth: {len(pares)} (de {config.NORMA_COMPLETA}, fuera del índice: {sum(1 for n, _ in pares if n == config.NORMA_COMPLETA)})")
    print(f"Faltantes en la KB: {len(faltantes)} {faltantes or ''}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="KB ferroviaria por artículos")
    parser.add_argument("--cobertura-gt", metavar="RUTA", help="Lista los pares (norma, artículo) del ground truth que no existen como chunk en la KB")
    parser.add_argument("--resumen", action="store_true", help="Imprime por norma el resultado del chunker, sin embeddings ni indexar")
    parser.add_argument("--indexar", action="store_true", help="Crea/actualiza el índice en config.CHROMA_DB_PATH_KB (carga el modelo de embeddings)")
    args = parser.parse_args()
    if args.cobertura_gt:
        imprimir_cobertura_gt(args.cobertura_gt)
    elif args.resumen:
        imprimir_resumen()
    elif args.indexar:
        logging.basicConfig(level=logging.INFO)
        config.inicializar_directorios_datos()
        crear_o_cargar_chroma_db(
            chroma_db_path=config.CHROMA_DB_PATH_KB, docs_base_conocimiento_path=config.DIRECTORIO_BASE_CONOCIMIENTO,
            embedding_function=get_embedding_function(config.EMBEDDING_MODEL_NAME_OR_PATH),
            chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP, recrear_db_flag=False,
            collection_name=config.CHROMA_COLLECTION_KB, manifest_path=config.CHROMA_MANIFEST_PATH_KB, por_articulos=True)
    else:
        parser.print_help()
