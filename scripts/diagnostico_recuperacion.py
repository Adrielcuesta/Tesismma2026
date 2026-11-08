# scripts/diagnostico_recuperacion.py
"""Mide la recuperación de la KB sobre una oferta, sin LLM y sin CRAG.

    python -m scripts.diagnostico_recuperacion <oferta.pdf|docx> --gt evaluacion/ground_truth_ofertas_v1.json --proyecto N
        [--modo seccion|subseccion] [--k 20] [--top-n 4] [--query-chars 1500] [--max-length 512] [--sin-reranker] [--csv ruta]

Extrae, divide y recupera por sección con la misma función que usa el pipeline. El ground truth solo se usa acá,
para calcular hit@K (antes del reranker) y hit@top_n (después). Los argumentos sobrescriben la config solo en este proceso.

Recuperación densa contra híbrida (BM25 + densa con RRF), trampa por trampa, sobre el ground truth v3 de P1 y P2:

    python -m scripts.diagnostico_recuperacion hibrida --oferta P1=<oferta_P1.pdf|docx> --oferta P2=<oferta_P2.pdf|docx> [--csv ruta]

Dónde se pierde el artículo (K de la densa, top por subsección y tope por sección), también sobre P1 y P2 y sin LLM:

    python -m scripts.diagnostico_recuperacion recorte --oferta P1=<oferta_P1.pdf|docx> --oferta P2=<oferta_P2.pdf|docx> [--csv ruta]
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


# --- Densa contra híbrida sobre el ground truth v3 (solo P1 y P2) ---

OFERTAS_DIAGNOSTICO = ("P1", "P2")


def _alfanumerico(texto) -> str:
    return "".join(c for c in rag_components._sin_tildes(str(texto or "")) if c.isalnum())


def seccion_de_trampa(trampa: dict, secciones: list):
    """Índice de la sección de la oferta cuyo texto contiene el fragmento de la trampa (normalizado); None si ninguna."""
    frase = _alfanumerico(trampa["fragmento_trampa"])
    return next((i for i, s in enumerate(secciones) if frase and frase in _alfanumerico(s["texto"])), None)


def recall_articulo(trampas: list, secciones: list, articulos_por_seccion: list) -> list:
    """Una fila por trampa: ¿su artículo (o un equivalente) queda entre los artículos a verificar de su sección?
    articulos_por_seccion[i] = conjunto de (norma, artículo base) que se verificarían en secciones[i]."""
    from evaluacion.evaluar import pares_trampa
    filas = []
    for t in trampas:
        i = seccion_de_trampa(t, secciones)
        pares = {(n, _base(a)) for n, a in pares_trampa(t)}
        filas.append({"id": t["id"], "oferta": t["oferta"], "seccion": secciones[i]["id"] if i is not None else None,
                      "articulo": f"{t['norma']} {_base(t['articulo'])}", "recuperada": i is not None and bool(pares & articulos_por_seccion[i])})
    return filas


def decision_adopcion(densa: list, hibrida: list) -> dict:
    """Regla fijada de antemano: se adopta la híbrida si mejora el Recall@artículo sumado de P1 y P2 sin perder ninguna trampa que la densa recuperaba."""
    recuperadas_densa = {f["id"] for f in densa if f["recuperada"]}
    recuperadas_hibrida = {f["id"] for f in hibrida if f["recuperada"]}
    perdidas, ganadas = sorted(recuperadas_densa - recuperadas_hibrida), sorted(recuperadas_hibrida - recuperadas_densa)
    return {"n": len(densa), "densa": len(recuperadas_densa), "hibrida": len(recuperadas_hibrida), "perdidas": perdidas, "ganadas": ganadas,
            "adopta": len(recuperadas_hibrida) > len(recuperadas_densa) and not perdidas}


def articulos_a_verificar(vector_db, secciones: list, modo: str) -> list:
    """Por sección, los (norma, artículo base) que el pipeline verificaría con la recuperación `modo` ('densa' o 'hibrida')."""
    previo = config.RECUPERACION
    config.RECUPERACION = modo
    try:
        resultado = []
        for s in secciones:
            _, docs = rag_components.recuperar_seccion(vector_db, s, tope=config.VERIFICAR_TOPE, sin_preambulo=True)
            resultado.append({(d.metadata.get("norma"), _base(d.metadata.get("articulo", ""))) for d in docs})
        return resultado
    finally:
        config.RECUPERACION = previo


def informe_hibrida(densa: list, hibrida: list) -> str:
    por_id = {f["id"]: f for f in hibrida}
    L = ["Trampa    Artículo               Sección  densa  híbrida"]
    for f in densa:
        h = por_id[f["id"]]
        L.append(f"{f['id']:<9} {f['articulo']:<22} {str(f['seccion']):<8} {'sí' if f['recuperada'] else 'no':<6} {'sí' if h['recuperada'] else 'no'}")
    d = decision_adopcion(densa, hibrida)
    L += ["", f"Recall@artículo densa:   {d['densa']}/{d['n']} ({d['densa'] / d['n']:.0%})", f"Recall@artículo híbrida: {d['hibrida']}/{d['n']} ({d['hibrida'] / d['n']:.0%})",
          f"Ganadas por la híbrida: {', '.join(d['ganadas']) or 'ninguna'}", f"Perdidas por la híbrida: {', '.join(d['perdidas']) or 'ninguna'}",
          "Decisión: " + ("ADOPTAR la híbrida (poner RECUPERACION = \"hibrida\" en config.py)." if d["adopta"]
                          else "MANTENER la densa; la híbrida se reporta como resultado negativo.")]
    return "\n".join(L)


# --- Dónde se pierde el artículo: K, top por subsección y tope por sección ---

# (nombre, K de la densa, top por subsección tras el reranker, tope por sección); la primera es la actual del pipeline
CONFIGURACIONES = (("actual", 10, 5, 15), ("media", 20, 8, 25), ("amplia", 30, 10, 40))
K_MAXIMO = max(c[1] for c in CONFIGURACIONES)
MEJORA_MINIMA = 6   # trampas (20 puntos de 30) sobre la configuración actual


def consultas_de_seccion(seccion: dict) -> list:
    """Las consultas que usa recuperar_seccion: una por subsección de al menos MIN_CHARS_SUBSECCION caracteres o, si no hay, la sección entera."""
    consultas = [x[:config.SUBSECTION_QUERY_MAX_CHARS] for _, x in seccion["subsecciones"] if len(x) >= config.MIN_CHARS_SUBSECCION]
    return consultas or [seccion["texto"][:config.SECTION_QUERY_MAX_CHARS]]


def candidatos_con_puntaje(vector_db, consultas: list, puntuar, k: int = K_MAXIMO) -> list:
    """Por consulta, [(doc, puntaje)] de los k candidatos de la densa en su orden. El reranker corre UNA vez sobre los k: el puntaje de
    un candidato no depende de los demás, así que las configuraciones menores se derivan de estos mismos puntajes. puntuar(consulta, docs) -> [float]."""
    resultado = []
    for consulta in consultas:
        docs = vector_db.as_retriever(search_kwargs={"k": k}).invoke(consulta)
        resultado.append(list(zip(docs, puntuar(consulta, docs))) if docs else [])
    return resultado


def seleccion_final(por_consulta: list, k: int, top_n: int, tope: int) -> list:
    """Documentos que se verificarían en la sección con (k, top_n, tope), igual que recuperar_seccion(sin_preambulo=True):
    por consulta, los k primeros de la densa -> los top_n de mayor puntaje -> sin preámbulos; unión por (norma, artículo) con el mayor
    puntaje y los `tope` mejores."""
    mejores = {}
    for candidatos in por_consulta:
        top = sorted(candidatos[:k], key=lambda x: x[1], reverse=True)[:top_n]
        for d, puntaje in top:
            if d.metadata.get("articulo") == "preambulo":
                continue
            clave = (d.metadata.get("norma"), d.metadata.get("articulo"))
            if clave not in mejores or puntaje > mejores[clave][1]:
                mejores[clave] = (d, puntaje)
    return [d for d, _ in sorted(mejores.values(), key=lambda x: x[1], reverse=True)[:tope]]


def _mejor_puesto(listas: list, pares: set):
    """Mejor posición (desde 1) de un fragmento de `pares` en alguna de las listas de documentos; None si no está."""
    puestos = [i for lista in listas for i, d in enumerate(lista, 1) if (d.metadata.get("norma"), _base(d.metadata.get("articulo", ""))) in pares]
    return min(puestos) if puestos else None


def analizar_recorte(oferta: str, trampas: list, secciones: list, candidatos_por_seccion: list) -> tuple:
    """(filas, pares): una fila por trampa con el mejor puesto de su artículo (o equivalente) en la densa (k máximo) y tras el reranker, y si entra
    con cada configuración; pares = {configuración: total de artículos a verificar en la oferta}."""
    from evaluacion.evaluar import pares_trampa
    filas = []
    for t in trampas:
        i = seccion_de_trampa(t, secciones)
        pares_t = {(n, _base(a)) for n, a in pares_trampa(t)}
        fila = {"id": t["id"], "oferta": oferta, "seccion": secciones[i]["id"] if i is not None else None, "articulo": f"{t['norma']} {_base(t['articulo'])}",
                "puesto_densa": None, "puesto_reranker": None, "entra": {nombre: False for nombre, *_ in CONFIGURACIONES}}
        if i is not None:
            por_consulta = candidatos_por_seccion[i]
            fila["puesto_densa"] = _mejor_puesto([[d for d, _ in c] for c in por_consulta], pares_t)
            fila["puesto_reranker"] = _mejor_puesto([[d for d, _ in sorted(c, key=lambda x: x[1], reverse=True)] for c in por_consulta], pares_t)
            for nombre, k, top_n, tope in CONFIGURACIONES:
                fila["entra"][nombre] = _mejor_puesto([seleccion_final(por_consulta, k, top_n, tope)], pares_t) is not None
        filas.append(fila)
    pares = {nombre: sum(len(seleccion_final(c, k, top_n, tope)) for c in candidatos_por_seccion) for nombre, k, top_n, tope in CONFIGURACIONES}
    return filas, pares


def decision_recorte(filas: list) -> dict:
    """Regla fijada de antemano: se adopta la configuración más chica que suba el Recall@artículo en al menos MEJORA_MINIMA trampas sobre la actual;
    si ninguna lo logra queda la actual y el techo se reporta como limitación."""
    recall = {nombre: sum(f["entra"][nombre] for f in filas) for nombre, *_ in CONFIGURACIONES}
    base = CONFIGURACIONES[0][0]
    elegida = next((nombre for nombre, *_ in CONFIGURACIONES[1:] if recall[nombre] - recall[base] >= MEJORA_MINIMA), None)
    return {"n": len(filas), "recall": recall, "adopta": elegida}


def informe_recorte(filas: list, pares_por_oferta: dict) -> str:
    nombres = [c[0] for c in CONFIGURACIONES]
    texto = lambda v: str(v) if v is not None else "fuera"
    L = [f"{'Trampa':<9} {'Artículo':<22} {'Sec.':<6} {'Densa K=' + str(K_MAXIMO):>11} {'Reranker':>9}  " + "  ".join(f"{n:<6}" for n in nombres)]
    for f in filas:
        L.append(f"{f['id']:<9} {f['articulo']:<22} {str(f['seccion']):<6} {texto(f['puesto_densa']):>11} {texto(f['puesto_reranker']):>9}  "
                 + "  ".join(f"{'sí' if f['entra'][n] else 'no':<6}" for n in nombres))
    d = decision_recorte(filas)
    L += ["", "Recall@artículo por configuración (K, top por subsección, tope por sección):"]
    L += [f"  {n:<7} ({k}, {top}, {tope}): {d['recall'][n]}/{d['n']} ({d['recall'][n] / d['n']:.0%})" for n, k, top, tope in CONFIGURACIONES]
    L += ["", "Artículos a verificar por oferta (determina el tiempo de corrida):"]
    for oferta, pares in pares_por_oferta.items():
        L.append(f"  {oferta}: " + ", ".join(f"{n} {pares[n]}" for n in nombres))
    L.append("  total: " + ", ".join(f"{n} {sum(p[n] for p in pares_por_oferta.values())}" for n in nombres))
    L += ["", "Decisión: " + (f"ADOPTAR la configuración «{d['adopta']}» (la más chica que sube el Recall@artículo en al menos {MEJORA_MINIMA} trampas)."
                            if d["adopta"] else f"MANTENER la actual; ninguna sube el Recall@artículo en {MEJORA_MINIMA} trampas y el techo se reporta como limitación.")]
    return "\n".join(L)


def main_recorte(argv=None) -> int:
    from evaluacion.evaluar import cargar_gt
    p = argparse.ArgumentParser(prog="diagnostico_recuperacion recorte", description="Dónde se pierde el artículo: K, top y tope (sin LLM).")
    p.add_argument("--oferta", action="append", required=True, metavar="P1=ruta", help="oferta y su archivo (P1 y P2); repetible")
    p.add_argument("--csv", help="Ruta donde guardar el detalle por trampa")
    args = p.parse_args(argv)
    rutas = dict(x.split("=", 1) for x in args.oferta)
    if set(rutas) != set(OFERTAS_DIAGNOSTICO) or not all(os.path.isfile(r) for r in rutas.values()):
        print("Hacen falta --oferta P1=<archivo> y --oferta P2=<archivo>, y los archivos tienen que existir.", file=sys.stderr)
        return 1
    embedding_function = vector_db_manager.get_embedding_function(config.EMBEDDING_MODEL_NAME_OR_PATH)
    vector_db = vector_db_manager.crear_o_cargar_chroma_db(
        chroma_db_path=config.CHROMA_DB_PATH_KB, docs_base_conocimiento_path=config.DIRECTORIO_NORMATIVA,
        embedding_function=embedding_function, chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP,
        recrear_db_flag=False, collection_name=config.CHROMA_COLLECTION_KB, manifest_path=config.CHROMA_MANIFEST_PATH_KB, por_articulos=True) if embedding_function else None
    if not vector_db:
        print("No se pudo cargar el índice de la KB por artículos.", file=sys.stderr)
        return 1

    modelo = rag_components._get_reranker_model(rag_components.RERANKER_MODEL_NAME)
    puntuar = lambda consulta, docs: [rag_components._normalizar_score(s) for s in modelo.score([(consulta, d.page_content) for d in docs])]
    filas, pares_por_oferta = [], {}
    for oferta in OFERTAS_DIAGNOSTICO:
        secciones = document_utils.dividir_en_secciones(document_utils.extraer_texto_oferta(rutas[oferta]))
        if config.EXCLUIR_INTRODUCCION:
            secciones = [s for s in secciones if not document_utils.es_introduccion(s)]
        candidatos = [candidatos_con_puntaje(vector_db, consultas_de_seccion(s), puntuar) for s in secciones]
        f, pares_por_oferta[oferta] = analizar_recorte(oferta, cargar_gt(oferta), secciones, candidatos)
        filas += f
    print(informe_recorte(filas, pares_por_oferta))
    if args.csv:
        nombres = [c[0] for c in CONFIGURACIONES]
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["trampa", "oferta", "seccion", "articulo", "puesto_densa", "puesto_reranker"] + nombres)
            w.writerows([[x["id"], x["oferta"], x["seccion"], x["articulo"], x["puesto_densa"] or "", x["puesto_reranker"] or ""] + [int(x["entra"][n]) for n in nombres] for x in filas])
        print(f"CSV: {args.csv}")
    return 0


def main_hibrida(argv=None) -> int:
    from evaluacion.evaluar import cargar_gt
    p = argparse.ArgumentParser(prog="diagnostico_recuperacion hibrida", description="Recall@artículo con recuperación densa e híbrida (sin LLM).")
    p.add_argument("--oferta", action="append", required=True, metavar="P1=ruta", help="oferta y su archivo (P1 y P2); repetible")
    p.add_argument("--csv", help="Ruta donde guardar el detalle por trampa")
    args = p.parse_args(argv)
    rutas = dict(x.split("=", 1) for x in args.oferta)
    if set(rutas) != set(OFERTAS_DIAGNOSTICO) or not all(os.path.isfile(r) for r in rutas.values()):
        print("Hacen falta --oferta P1=<archivo> y --oferta P2=<archivo>, y los archivos tienen que existir.", file=sys.stderr)
        return 1

    embedding_function = vector_db_manager.get_embedding_function(config.EMBEDDING_MODEL_NAME_OR_PATH)
    vector_db = vector_db_manager.crear_o_cargar_chroma_db(
        chroma_db_path=config.CHROMA_DB_PATH_KB, docs_base_conocimiento_path=config.DIRECTORIO_NORMATIVA,
        embedding_function=embedding_function, chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP,
        recrear_db_flag=False, collection_name=config.CHROMA_COLLECTION_KB, manifest_path=config.CHROMA_MANIFEST_PATH_KB, por_articulos=True) if embedding_function else None
    if not vector_db:
        print("No se pudo cargar el índice de la KB por artículos.", file=sys.stderr)
        return 1

    densa, hibrida = [], []
    for oferta in OFERTAS_DIAGNOSTICO:
        secciones = document_utils.dividir_en_secciones(document_utils.extraer_texto_oferta(rutas[oferta]))
        if config.EXCLUIR_INTRODUCCION:
            secciones = [s for s in secciones if not document_utils.es_introduccion(s)]
        trampas = cargar_gt(oferta)
        densa += recall_articulo(trampas, secciones, articulos_a_verificar(vector_db, secciones, "densa"))
        hibrida += recall_articulo(trampas, secciones, articulos_a_verificar(vector_db, secciones, "hibrida"))
    print(informe_hibrida(densa, hibrida))
    if args.csv:
        por_id = {f["id"]: f for f in hibrida}
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["trampa", "oferta", "seccion", "articulo", "densa", "hibrida"])
            w.writerows([[x["id"], x["oferta"], x["seccion"], x["articulo"], int(x["recuperada"]), int(por_id[x["id"]]["recuperada"])] for x in densa])
        print(f"CSV: {args.csv}")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "hibrida":
        return main_hibrida(argv[1:])
    if argv and argv[0] == "recorte":
        return main_recorte(argv[1:])
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
