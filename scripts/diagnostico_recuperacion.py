# scripts/diagnostico_recuperacion.py
"""Mide la recuperación de la KB sobre una oferta, sin LLM y sin CRAG.

    python -m scripts.diagnostico_recuperacion <oferta.pdf|docx> --gt evaluacion/ground_truth_ofertas_v1.json --proyecto N
        [--modo seccion|subseccion] [--k 20] [--top-n 4] [--query-chars 1500] [--max-length 512] [--sin-reranker] [--csv ruta]

Extrae, divide y recupera por sección con la misma función que usa el pipeline. El ground truth solo se usa acá,
para calcular hit@K (antes del reranker) y hit@top_n (después). Los argumentos sobrescriben la config solo en este proceso.
"""
import argparse
import csv
import json
import os
import re
import sys
import time

from . import config, document_utils, vector_db_manager, rag_components

RE_PAR = re.compile(r'(NORM_\d+)\s*,\s*Art\.\s*(\S+)')
RE_PARTE = re.compile(r'\s*\(parte \d+\)\s*$')


def _base(articulo) -> str:
    """Artículo sin sufijo '(parte n)' ni punto final: '4.2.' -> '4.2'."""
    return RE_PARTE.sub("", str(articulo)).strip().rstrip(".")


def pares_ground_truth(ruta_gt: str, proyecto: int) -> list:
    """Pares únicos (norma, artículo base) de umbral_alerta de los riesgos del proyecto, en orden de aparición."""
    with open(ruta_gt, encoding="utf-8") as f:
        entradas = json.load(f)
    entrada = next((e for e in entradas if e.get("proyecto") == f"Proyecto {proyecto}"), None)
    if entrada is None:
        raise ValueError(f"El ground truth no tiene 'Proyecto {proyecto}'")
    pares = []
    for riesgo in json.loads(entrada["ground_truth"]):
        m = RE_PAR.search(riesgo.get("umbral_alerta", ""))
        if m and (m.group(1), _base(m.group(2))) not in pares:
            pares.append((m.group(1), _base(m.group(2))))
    if not pares:
        raise ValueError(f"El Proyecto {proyecto} no tiene pares (norma, artículo) en umbral_alerta")
    return pares


def _rangos(docs: list) -> dict:
    """{(norma, artículo base): posición 1-based de su primera aparición}."""
    rangos = {}
    for i, d in enumerate(docs, 1):
        rangos.setdefault((d.metadata.get("norma"), _base(d.metadata.get("articulo", ""))), i)
    return rangos


def _mejor(par, por_seccion: list, campo: str):
    """(rango, id de sección) de la mejor posición del par en `campo` ('candidatos' o 'docs') o (None, None)."""
    hallados = [(r[par], s["id"]) for s in por_seccion for r in [_rangos(s[campo])] if par in r]
    return min(hallados) if hallados else (None, None)


def _donde(par, por_seccion: list, campo: str) -> str:
    return ";".join(f"{s['id']}:{_rangos(s[campo])[par]}" for s in por_seccion if par in _rangos(s[campo]))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Diagnóstico de la recuperación por sección (sin LLM).")
    p.add_argument("oferta", help="Ruta de la oferta (.pdf o .docx)")
    p.add_argument("--gt", required=True, help="Ground truth (JSON); solo se usa para las métricas")
    p.add_argument("--proyecto", type=int, required=True, help="Número de proyecto del ground truth")
    p.add_argument("--modo", choices=("seccion", "subseccion"), default="seccion")
    p.add_argument("--k", type=int, help="Fragmentos recuperados antes del reranker (por consulta)")
    p.add_argument("--top-n", type=int, help="Fragmentos que se conservan tras el reranker (por consulta)")
    p.add_argument("--query-chars", type=int, help="Largo máximo de la consulta (por consulta)")
    p.add_argument("--max-length", type=int, help="RERANKER_MAX_LENGTH")
    p.add_argument("--sin-reranker", action="store_true")
    p.add_argument("--csv", help="Ruta donde guardar el detalle por par del ground truth")
    args = p.parse_args(argv)

    if not os.path.isfile(args.oferta):
        print(f"No existe el archivo: {args.oferta}", file=sys.stderr)
        return 1
    pares = pares_ground_truth(args.gt, args.proyecto)

    por_sub = args.modo == "subseccion"
    config.RECUPERACION_POR_SUBSECCION = por_sub
    if args.sin_reranker:
        config.USE_RERANKER = False
    if args.max_length:
        config.RERANKER_MAX_LENGTH = args.max_length
    if args.k:
        if por_sub: config.K_SUBSECCION = args.k
        else: config.K_RECUPERACION = args.k
    if args.top_n:
        if por_sub: config.TOP_N_SUBSECCION = args.top_n
        else: config.TOP_N_POR_SECCION = args.top_n
    if args.query_chars:
        if por_sub: config.SUBSECTION_QUERY_MAX_CHARS = args.query_chars
        else: config.SECTION_QUERY_MAX_CHARS = args.query_chars
    k = config.K_SUBSECCION if por_sub else config.K_RECUPERACION
    top_n = config.TOPE_FRAGMENTOS_SECCION if por_sub else config.TOP_N_POR_SECCION

    t_total = time.perf_counter()
    secciones = document_utils.dividir_en_secciones(document_utils.extraer_texto_oferta(args.oferta))
    if config.EXCLUIR_INTRODUCCION:
        secciones = [s for s in secciones if not document_utils.es_introduccion(s)]
    if not secciones:
        print("No se pudo dividir la oferta en secciones.", file=sys.stderr)
        return 1

    embedding_function = vector_db_manager.get_embedding_function(config.EMBEDDING_MODEL_NAME_OR_PATH)
    if not embedding_function:
        print("No se pudo inicializar el modelo de embeddings.", file=sys.stderr)
        return 1
    vector_db = vector_db_manager.crear_o_cargar_chroma_db(
        chroma_db_path=config.CHROMA_DB_PATH_KB, docs_base_conocimiento_path=config.DIRECTORIO_NORMATIVA,
        embedding_function=embedding_function, chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP,
        recrear_db_flag=False, collection_name=config.CHROMA_COLLECTION_KB, manifest_path=config.CHROMA_MANIFEST_PATH_KB, por_articulos=True)
    if not vector_db:
        print("No se pudo cargar el índice de la KB por artículos.", file=sys.stderr)
        return 1

    por_seccion = []
    for s in secciones:
        candidatos, docs = rag_components.recuperar_seccion(vector_db, s)
        por_seccion.append({"id": s["id"], "candidatos": candidatos, "docs": docs})
    duracion = time.perf_counter() - t_total

    filas = []
    for par in pares:
        r_cand, s_cand = _mejor(par, por_seccion, "candidatos")
        r_fin, s_fin = _mejor(par, por_seccion, "docs")
        filas.append({"norma": par[0], "articulo": par[1], "rank_candidatos": r_cand, "seccion_candidatos": s_cand, "rank_final": r_fin,
                      "seccion_final": s_fin, "secciones_candidatos": _donde(par, por_seccion, "candidatos"),
                      "secciones_final": _donde(par, por_seccion, "docs")})
    hit_k = sum(f["rank_candidatos"] is not None for f in filas)
    hit_n = sum(f["rank_final"] is not None for f in filas)

    reranker = f"reranker max_length={config.RERANKER_MAX_LENGTH}" if config.USE_RERANKER else "sin reranker"
    print(f"\nOferta: {os.path.basename(args.oferta)} | Proyecto {args.proyecto} | modo: {args.modo} | K={k} top_n={top_n} | {reranker}")
    print(f"Secciones: {len(secciones)} | pares únicos del ground truth: {len(pares)}")
    print(f"\nhit@{k} antes del reranker: {hit_k}/{len(pares)} ({hit_k / len(pares):.0%})")
    print(f"hit@{top_n} después:        {hit_n}/{len(pares)} ({hit_n / len(pares):.0%})")
    print("\nPares del ground truth (rank en candidatos | rank final):")
    for f in filas:
        cand = f"#{f['rank_candidatos']} en {f['seccion_candidatos']}" if f["rank_candidatos"] else "no recuperado"
        fin = f"#{f['rank_final']} en {f['seccion_final']}" if f["rank_final"] else "no recuperado"
        print(f"  {f['norma']} Art. {f['articulo']:<8} candidatos: {cand:<22} final: {fin}")
    print("\nFragmentos por sección (candidatos | finales):")
    for s in por_seccion:
        print(f"  {s['id']:<6}{len(s['candidatos']):>4} | {len(s['docs']):>2}")
    print(f"\nTiempo total: {duracion:.2f} s")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            escritor = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
            escritor.writeheader()
            escritor.writerows(filas)
        print(f"CSV: {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
