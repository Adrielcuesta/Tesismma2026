# scripts/diagnostico_recuperacion.py
"""Mide la recuperación de la KB sobre una oferta, sin LLM y sin CRAG.

    python -m scripts.diagnostico_recuperacion <oferta.pdf|docx> --gt evaluacion/ground_truth_ofertas_v1.json --proyecto N
        [--modo seccion|subseccion] [--k 20] [--top-n 4] [--query-chars 1500] [--max-length 512] [--sin-reranker] [--csv ruta]

Extrae, divide y recupera por sección con la misma función que usa el pipeline. El ground truth solo se usa acá,
para calcular hit@K (antes del reranker) y hit@top_n (después). Los argumentos sobrescriben la config solo en este proceso.

Recuperación densa contra híbrida (BM25 + densa con RRF), trampa por trampa, sobre el ground truth v3 de P1 y P2:

    python -m scripts.diagnostico_recuperacion hibrida --oferta P1=<oferta_P1.pdf|docx> --oferta P2=<oferta_P2.pdf|docx> [--csv ruta]
(los CSV de hibrida y recorte se guardan por defecto en evaluacion/diagnosticos/)

Dónde se pierde el artículo (K de la densa, top por subsección y tope por sección), también sobre P1 y P2 y sin LLM:

    python -m scripts.diagnostico_recuperacion recorte --oferta P1=<oferta_P1.pdf|docx> --oferta P2=<oferta_P2.pdf|docx> [--csv ruta]

La primera corrida guarda diagnostico_cache.json (30 candidatos densos con sus puntajes y el del reranker, por consulta, y los resultados de las
consultas por oración); con --usar-cache las configuraciones se derivan de ahí, sin recalcular el reranker. Si la caché es anterior a la versión 2
(o le faltan las oraciones), esa corrida abre el índice (sin reranker) para completarla y la vuelve a guardar.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from collections import namedtuple

from langchain_core.documents import Document

from . import config, document_utils, vector_db_manager, rag_components

RE_PAR = re.compile(r'(NORM_\d+)\s*,\s*Art\.\s*(\S+)')
RE_PARTE = re.compile(r'\s*\(parte \d+\)\s*$')


_base = rag_components.articulo_base   # la misma función que usa el pipeline


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

# modo "reranker": los k primeros de la densa -> los `top` de mayor puntaje del reranker (como el pipeline).
# modo "densa": los `top` primeros de la densa por su puntaje denso, sin reranker.
# modo "union": los `top` primeros de la densa ∪ los `top_rr or top` del reranker (sobre los k primeros), ordenados por puntaje del reranker.
# El puntaje del reranker de un candidato no depende de los demás: usar el de los 30 candidatos restringido a los k primeros de la densa
# equivale a reranquear solo esos k.
# top_rr: cuántos toma el reranker en el modo "union" (si no, `top`). oraciones: (solo_con_cifras, N) agrega, por cada oración de la subsección, sus N primeros
# artículos de la densa (sin reranker), con un cupo propio de `cupo_oraciones` artículos por sección, detrás de la base (que conserva su tope).
Config = namedtuple("Config", "nombre k top tope modo top_rr oraciones cupo_oraciones", defaults=(None, None, None))
CUPO_ORACIONES = 10   # tope total con oraciones: 35 en union (25 + 10) y 40 en union_k20 (30 + 10)
_VARIANTES_ORACIONES = (("oraciones_cifras_N2", True, 2), ("oraciones_cifras_N3", True, 3), ("oraciones_todas_N2", False, 2))
_BASES_UNION = (Config("union", 10, 5, 25, "union"), Config("union_k20", 20, 5, 30, "union", top_rr=8))
CONFIGURACIONES = (Config("actual", 10, 5, 15, "reranker"), Config("media", 20, 8, 25, "reranker"), Config("amplia", 30, 10, 40, "reranker"),
                   Config("densa_sin_reranker", 10, 5, 15, "densa")) + _BASES_UNION + tuple(
    base._replace(nombre=f"{base.nombre}_{variante}", oraciones=(solo_cifras, n), cupo_oraciones=CUPO_ORACIONES)
    for base in _BASES_UNION for variante, solo_cifras, n in _VARIANTES_ORACIONES)
CUPOS_REDUCIDOS = (8, 6, 4)
CONFIGURACIONES += tuple(_BASES_UNION[0]._replace(nombre=f"union_oraciones_cifras_N2_cupo{c}", oraciones=(True, 2), cupo_oraciones=c) for c in CUPOS_REDUCIDOS)
K_MAXIMO = 30
K_ORACION = rag_components.K_ORACION                      # fragmentos que se piden a la densa por oración
N_MAXIMO_ORACION = rag_components.MAX_ARTICULOS_ORACION   # artículos distintos que se guardan por oración (las variantes usan N = 2 o 3)
FACTOR_MAXIMO_PARES = 2   # tope de la regla de adopción: el doble de los pares a verificar de la configuración actual
Cand = namedtuple("Cand", "doc densa reranker")   # densa: -distancia (más alto, mejor); reranker: puntaje normalizado
# Encabezado de artículo al comienzo de una línea: 'Art. 4.7. Reserva física...' o 'Art. 3.7. CONTROL DE CALIDAD'. El título puede estar en
# mayúsculas o en minúsculas (la versión anterior exigía dos mayúsculas y no reconocía los títulos en minúsculas).
RE_ENCABEZADO = re.compile(r"(?m)^\s*Art\.\s+(\d+\.\d+)\.\s+[A-Za-zÁÉÍÓÚÑáéíóúñ]")
ARCHIVO_CACHE = "diagnostico_cache.json"   # en el directorio de trabajo; está en .gitignore
DIR_DIAGNOSTICOS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "evaluacion", "diagnosticos"))


def csv_por_defecto(nombre: str) -> str:
    """Los CSV del diagnóstico se guardan por defecto en evaluacion/diagnosticos/."""
    return os.path.join(DIR_DIAGNOSTICOS, nombre)


def consultas_de_seccion(seccion: dict) -> list:
    """Las consultas que usa recuperar_seccion: una por subsección de al menos MIN_CHARS_SUBSECCION caracteres o, si no hay, la sección entera."""
    consultas = [x[:config.SUBSECTION_QUERY_MAX_CHARS] for _, x in seccion["subsecciones"] if len(x) >= config.MIN_CHARS_SUBSECCION]
    return consultas or [seccion["texto"][:config.SECTION_QUERY_MAX_CHARS]]


def _clave(norma, articulo) -> str:
    return f"{norma}|{_base(articulo)}"


def _hash(consulta: str) -> str:
    return hashlib.sha1(consulta.encode("utf-8")).hexdigest()[:12]


def datos_de_consultas(vector_db, consultas: list, puntuar, total: int, k: int = K_MAXIMO) -> list:
    """Por consulta {'candidatos': [Cand], 'ranking': [clave]}: los k primeros de la densa (con su puntaje denso y el del reranker) y el ranking de
    TODOS los artículos del índice (sin repetir, en el orden de la densa). El reranker corre UNA vez sobre los k: el puntaje de un candidato no depende
    de los demás, así que todas las configuraciones se derivan de estos mismos puntajes. puntuar(consulta, docs) -> [float]; total: fragmentos del índice."""
    resultado = []
    for consulta in consultas:
        todos = vector_db.similarity_search_with_score(consulta, k=total)
        primeros = todos[:k]
        reranker = puntuar(consulta, [d for d, _ in primeros]) if primeros else []
        resultado.append({"candidatos": [Cand(d, -float(dist), float(r)) for (d, dist), r in zip(primeros, reranker)],
                          "ranking": list(dict.fromkeys(_clave(d.metadata.get("norma"), d.metadata.get("articulo", "")) for d, _ in todos))})
    return resultado


def _elegidos(candidatos: list, cfg) -> list:
    """[(doc, puntaje)] que quedan de UNA consulta con la configuración cfg."""
    primeros = candidatos[:cfg.k]
    por_reranker = sorted(primeros, key=lambda c: c.reranker, reverse=True)[:cfg.top_rr or cfg.top]
    if cfg.modo == "reranker":
        return [(c.doc, c.reranker) for c in por_reranker]
    if cfg.modo == "densa":
        return [(c.doc, c.densa) for c in primeros[:cfg.top]]
    elegidos = {id(c) for c in primeros[:cfg.top] + por_reranker}
    # en el orden del reranker, igual que recuperar_con_candidatos(top_densa=...) del pipeline
    return [(c.doc, c.reranker) for c in sorted(primeros, key=lambda c: c.reranker, reverse=True) if id(c) in elegidos]


def seleccion_final(por_consulta: list, cfg, oraciones: list = ()) -> list:
    """Documentos que se verificarían en la sección con la configuración cfg, igual que recuperar_seccion(sin_preambulo=True): por consulta los
    elegidos sin preámbulos; unión por (norma, artículo) con el mayor puntaje y los `cfg.tope` mejores. por_consulta: [[Cand]].
    Con cfg.oraciones se agregan, detrás de los de la base, los artículos de las consultas por oración (`oraciones`: datos_de_oraciones) que no estén ya,
    hasta un cupo propio de cfg.cupo_oraciones artículos por sección (la base conserva su tope)."""
    base = _seleccion_base(por_consulta, cfg)
    if not cfg.oraciones:
        return base
    solo_cifras, n = cfg.oraciones
    return rag_components.agregar_articulos_de_oraciones(base, oraciones, solo_cifras, n, cfg.cupo_oraciones)   # la misma función que usa el pipeline


def _seleccion_base(por_consulta: list, cfg) -> list:
    mejores = {}
    for candidatos in por_consulta:
        for d, puntaje in _elegidos(candidatos, cfg):
            if d.metadata.get("articulo") == "preambulo":
                continue
            clave = (d.metadata.get("norma"), d.metadata.get("articulo"))
            if clave not in mejores or puntaje > mejores[clave][1]:
                mejores[clave] = (d, puntaje)
    return [d for d, _ in sorted(mejores.values(), key=lambda x: x[1], reverse=True)[:cfg.tope]]


def _mejor_puesto(listas: list, pares: set):
    """Mejor posición (desde 1) de un fragmento de `pares` en alguna de las listas de documentos; None si no está."""
    puestos = [i for lista in listas for i, d in enumerate(lista, 1) if (d.metadata.get("norma"), _base(d.metadata.get("articulo", ""))) in pares]
    return min(puestos) if puestos else None


def analizar_recorte(oferta: str, trampas: list, secciones: list, datos_por_seccion: list, oraciones_por_seccion: list = None) -> tuple:
    """(filas, pares): una fila por trampa con el mejor puesto de su artículo (o equivalente) en la densa (k máximo), tras el reranker y en todo el índice,
    y si entra con cada configuración; pares = {configuración: total de artículos a verificar en la oferta}. datos_por_seccion: salida de datos_de_consultas;
    oraciones_por_seccion: salida de datos_de_oraciones por sección (sin ellos, las configuraciones con oraciones quedan iguales a su base)."""
    from evaluacion.evaluar import pares_trampa
    oraciones_por_seccion = oraciones_por_seccion or [[] for _ in secciones]
    filas = []
    for t in trampas:
        i = seccion_de_trampa(t, secciones)
        pares_t = {(n, _base(a)) for n, a in pares_trampa(t)}
        fila = {"id": t["id"], "oferta": oferta, "seccion": secciones[i]["id"] if i is not None else None, "articulo": f"{t['norma']} {_base(t['articulo'])}",
                "clave_principal": _clave(t["norma"], t["articulo"]), "puesto_densa": None, "puesto_reranker": None, "puestos_indice": {_clave(*p): None for p in pares_t},
                "entra": {c.nombre: False for c in CONFIGURACIONES}}
        if i is not None:
            consultas = datos_por_seccion[i]
            por_consulta = [q["candidatos"] for q in consultas]
            fila["puesto_densa"] = _mejor_puesto([[c.doc for c in cs] for cs in por_consulta], pares_t)
            fila["puesto_reranker"] = _mejor_puesto([[c.doc for c in sorted(cs, key=lambda c: c.reranker, reverse=True)] for cs in por_consulta], pares_t)
            for cfg in CONFIGURACIONES:
                fila["entra"][cfg.nombre] = _mejor_puesto([seleccion_final(por_consulta, cfg, oraciones_por_seccion[i])], pares_t) is not None
            for clave in fila["puestos_indice"]:
                puestos = [q["ranking"].index(clave) + 1 for q in consultas if clave in q["ranking"]]
                fila["puestos_indice"][clave] = min(puestos) if puestos else None
        filas.append(fila)
    pares = {c.nombre: sum(len(seleccion_final([q["candidatos"] for q in qs], c, oraciones_por_seccion[i])) for i, qs in enumerate(datos_por_seccion))
             for c in CONFIGURACIONES}
    return filas, pares


def decision_recorte(filas: list, pares_por_oferta: dict) -> dict:
    """Regla fijada de antemano: se adopta la configuración con mayor Recall@artículo cuyo total de pares a verificar no supere el doble del de la actual;
    si empatan, la de menos pares. Si la mejor es la actual, se mantiene y el techo se reporta como limitación."""
    recall = {c.nombre: sum(f["entra"][c.nombre] for f in filas) for c in CONFIGURACIONES}
    pares = {c.nombre: sum(p[c.nombre] for p in pares_por_oferta.values()) for c in CONFIGURACIONES}
    base = CONFIGURACIONES[0].nombre
    limite = FACTOR_MAXIMO_PARES * pares[base]
    elegibles = [c.nombre for c in CONFIGURACIONES if pares[c.nombre] <= limite]
    mejor = max(elegibles, key=lambda n: (recall[n], -pares[n]))
    return {"n": len(filas), "recall": recall, "pares": pares, "limite": limite, "elegibles": elegibles, "adopta": None if mejor == base else mejor}


# --- Caché: los 30 candidatos densos con sus puntajes, por consulta, para derivar las configuraciones sin recalcular ---

unidades_de_seccion = rag_components.unidades_de_seccion   # las mismas funciones que usa el pipeline
oraciones_de_seccion = rag_components.oraciones_de_seccion


def datos_de_oraciones(vector_db, oraciones: list, k: int = K_ORACION) -> list:
    """Por oración, buscada en la densa sola (sin reranker, con rag_components.consultar_oraciones): {'hash', 'con_cifras' (tiene algún dígito),
    'articulos': [{norma, articulo, densa}]} con los N_MAXIMO_ORACION primeros artículos distintos (sin preámbulos), en su orden. Es lo que se guarda en la caché."""
    return [{"hash": _hash(o), "con_cifras": e["con_cifras"], "articulos": [{k_: v for k_, v in a.items() if k_ != "doc"} for a in e["articulos"]]}
            for o, e in zip(oraciones, rag_components.consultar_oraciones(vector_db, oraciones, k, N_MAXIMO_ORACION))]


def a_cache(secciones_por_oferta: dict, datos_por_oferta: dict, fragmentos: dict, oraciones_por_oferta: dict = None) -> dict:
    """Estructura JSON (versión 2): por oferta y sección, una entrada por consulta con el hash de su texto, los candidatos (norma, artículo, puntajes) y el
    ranking completo; los fragmentos de las trampas; y, por oferta y sección, los resultados de las consultas por oración."""
    ofertas = {}
    for oferta, secciones in secciones_por_oferta.items():
        ofertas[oferta] = {s["id"]: [{"hash": _hash(c), "ranking": q["ranking"],
                                      "candidatos": [{"norma": x.doc.metadata.get("norma"), "articulo": x.doc.metadata.get("articulo"), "densa": x.densa, "reranker": x.reranker}
                                                     for x in q["candidatos"]]}
                                     for c, q in zip(consultas_de_seccion(s), datos)]
                           for s, datos in zip(secciones, datos_por_oferta[oferta])}
    oraciones = {o: {s["id"]: entradas for s, entradas in zip(secciones_por_oferta[o], lista)} for o, lista in (oraciones_por_oferta or {}).items() if lista}
    return {"version": 2, "ofertas": ofertas, "fragmentos": fragmentos, "oraciones": oraciones}


def oraciones_desde_cache(cache: dict, oferta: str, secciones: list):
    """Los resultados por oración guardados de la oferta, por sección; None si faltan o si el texto de la oferta cambió (hay que volver a buscarlos)."""
    guardadas = (cache.get("oraciones") or {}).get(oferta)
    if not guardadas:
        return None
    resultado = []
    for s in secciones:
        entradas, textos = guardadas.get(str(s["id"])), oraciones_de_seccion(s)
        if entradas is None or len(entradas) != len(textos) or any(e["hash"] != _hash(t) for e, t in zip(entradas, textos)):
            return None
        resultado.append(entradas)
    return resultado


def datos_desde_cache(cache: dict, oferta: str, secciones: list) -> list:
    """Inverso de a_cache para una oferta. Falla si la oferta cambió desde que se armó la caché (el hash de alguna consulta no coincide)."""
    guardadas = (cache.get("ofertas") or {}).get(oferta)
    if guardadas is None:
        raise ValueError(f"La caché no tiene la oferta {oferta}")
    resultado = []
    for s in secciones:
        consultas, entradas = consultas_de_seccion(s), guardadas.get(str(s["id"]))
        if entradas is None or len(entradas) != len(consultas) or any(e["hash"] != _hash(c) for c, e in zip(consultas, entradas)):
            raise ValueError(f"La caché no corresponde a la oferta {oferta} (sección {s['id']}); volvé a correr sin --usar-cache")
        resultado.append([{"ranking": e["ranking"], "candidatos": [Cand(Document(page_content="", metadata={"norma": c["norma"], "articulo": c["articulo"]}),
                                                                      c["densa"], c["reranker"]) for c in e["candidatos"]]} for e in entradas])
    return resultado


def describir_fragmento(texto: str) -> dict:
    """Largo, encabezados 'Art. X.Y. TÍTULO' que trae el texto (con su posición) y con cuál empieza (en los primeros 80 caracteres)."""
    encabezados = [(m.group(1), m.start()) for m in RE_ENCABEZADO.finditer(texto)]
    return {"caracteres": len(texto), "encabezados": [list(e) for e in encabezados],
            "empieza_con": encabezados[0][0] if encabezados and encabezados[0][1] <= 80 else None}


def info_fragmentos(datos_chroma: dict, claves: set) -> dict:
    """{clave 'NORM|art': [descripción de cada fragmento (parte) con esa (norma, artículo)]} a partir de vector_db.get(include=documents+metadatas)."""
    resultado = {c: [] for c in claves}
    for texto, meta in zip(datos_chroma.get("documents") or [], datos_chroma.get("metadatas") or []):
        clave = _clave((meta or {}).get("norma"), (meta or {}).get("articulo", ""))
        if clave in resultado:
            resultado[clave].append({"articulo": (meta or {}).get("articulo"), "parte": (meta or {}).get("parte"), **describir_fragmento(texto)})
    return resultado


# --- Informe ---

def _texto_fragmentos(fragmentos: list, clave: str) -> str:
    if not fragmentos:
        return "NO existe un fragmento con esa (norma, artículo) en el índice"
    partes = []
    for f in fragmentos:
        pegados = [e for e, _ in f["encabezados"] if e != clave.split("|")[1]]
        partes.append(f"{f['caracteres']} caracteres, empieza con " + (f"Art. {f['empieza_con']}" if f["empieza_con"] else "otra cosa (sin encabezado de artículo)")
                      + (f", trae pegado: {', '.join('Art. ' + e for e in pegados)}" if pegados else ", sin otro artículo pegado"))
    return f"{len(fragmentos)} fragmento(s): " + " | ".join(partes)


def informe_recorte(filas: list, pares_por_oferta: dict, fragmentos: dict = None) -> str:
    nombres = [c.nombre for c in CONFIGURACIONES]
    texto = lambda v: str(v) if v is not None else "fuera"
    L = [f"{'Trampa':<9} {'Artículo':<22} {'Sec.':<5} {'Densa K=' + str(K_MAXIMO):>10} {'Reranker':>9}  " + "  ".join(f"{n:<{len(n)}}" for n in nombres)]
    for f in filas:
        L.append(f"{f['id']:<9} {f['articulo']:<22} {str(f['seccion']):<5} {texto(f['puesto_densa']):>10} {texto(f['puesto_reranker']):>9}  "
                 + "  ".join(f"{'sí' if f['entra'][n] else 'no':<{len(n)}}" for n in nombres))
    d = decision_recorte(filas, pares_por_oferta)
    L += ["", "Recall@artículo por configuración (K, top por subsección, tope por sección) y artículos a verificar (determinan el tiempo de corrida):"]
    for c in CONFIGURACIONES:
        L.append(f"  {c.nombre:<19} ({c.k}, {c.top}, {c.tope}): {d['recall'][c.nombre]}/{d['n']} ({d['recall'][c.nombre] / d['n']:.0%})  |  pares: "
                 + ", ".join(f"{o} {p[c.nombre]}" for o, p in pares_por_oferta.items()) + f", total {d['pares'][c.nombre]}"
                 + ("" if c.nombre in d["elegibles"] else "  (supera el límite)"))
    L += [f"  límite de pares: {d['limite']} (el doble de la actual)",
          "  Notas: union_k20 usa el puntaje del reranker de los candidatos con puesto denso <= 20 (el puntaje de cada candidato no depende de los demás: es equivalente a reranquear solo esos 20).",
          "  Las variantes *_oraciones_* suman, a la base, los N primeros artículos de la densa para cada oración de la subsección (sin reranker; solo texto de la oferta),",
          f"  con un cupo propio de {CUPO_ORACIONES} artículos por sección (_cupo8, _cupo6 y _cupo4: ese cupo), detrás de la base (que conserva su tope); «cifras» = oraciones con algún dígito.", "",
          "Decisión: " + (f"ADOPTAR «{d['adopta']}» (mayor Recall@artículo dentro del límite de pares; a igual recall, la de menos pares)."
                          if d["adopta"] else "MANTENER la actual; ninguna configuración dentro del límite de pares la supera y el techo se reporta como limitación.")]
    fuera = [f for f in filas if f["puesto_densa"] is None]
    if fuera:
        L += ["", f"Trampas cuyo artículo no está en los {K_MAXIMO} primeros de la densa:"]
        for f in fuera:
            if f["seccion"] is None:
                L.append(f"  {f['id']}: la trampa no se ubicó en ninguna sección de la oferta")
                continue
            L.append(f"  {f['id']} (sección {f['seccion']}):")
            for clave, puesto in f["puestos_indice"].items():
                etiqueta = "artículo de la trampa" if clave == f["clave_principal"] else "equivalente"
                L.append(f"    {clave.replace('|', ' ')} ({etiqueta}): puesto en toda la densa (artículos distintos) "
                         + (str(puesto) if puesto else "no aparece") + "; "
                         + (_texto_fragmentos((fragmentos or {}).get(clave), clave) if fragmentos is not None else "sin datos del índice"))
    return "\n".join(L)


def _abrir_indice():
    """Índice vectorial de la KB (carga el modelo de embeddings, no el reranker); None si no se puede."""
    embedding_function = vector_db_manager.get_embedding_function(config.EMBEDDING_MODEL_NAME_OR_PATH)
    vector_db = vector_db_manager.crear_o_cargar_chroma_db(
        chroma_db_path=config.CHROMA_DB_PATH_KB, docs_base_conocimiento_path=config.DIRECTORIO_NORMATIVA,
        embedding_function=embedding_function, chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP,
        recrear_db_flag=False, collection_name=config.CHROMA_COLLECTION_KB, manifest_path=config.CHROMA_MANIFEST_PATH_KB, por_articulos=True) if embedding_function else None
    if not vector_db:
        print("No se pudo cargar el índice de la KB por artículos.", file=sys.stderr)
    return vector_db


def main_recorte(argv=None) -> int:
    from evaluacion.evaluar import cargar_gt, pares_trampa
    p = argparse.ArgumentParser(prog="diagnostico_recuperacion recorte", description="Dónde se pierde el artículo: K, top y tope (sin LLM).")
    p.add_argument("--oferta", action="append", required=True, metavar="P1=ruta", help="oferta y su archivo (P1 y P2); repetible")
    p.add_argument("--csv", default=csv_por_defecto("diagnostico_recorte.csv"), help="Ruta del CSV con el detalle por trampa (por defecto en evaluacion/diagnosticos/)")
    p.add_argument("--cache", default=ARCHIVO_CACHE, help=f"Archivo de caché (por defecto {ARCHIVO_CACHE})")
    p.add_argument("--usar-cache", action="store_true", help="Deriva las configuraciones de la caché; solo abre el índice (sin reranker) si le falta algo")
    args = p.parse_args(argv)
    rutas = dict(x.split("=", 1) for x in args.oferta)
    if set(rutas) != set(OFERTAS_DIAGNOSTICO) or not all(os.path.isfile(r) for r in rutas.values()):
        print("Hacen falta --oferta P1=<archivo> y --oferta P2=<archivo>, y los archivos tienen que existir.", file=sys.stderr)
        return 1
    if args.usar_cache and not os.path.isfile(args.cache):
        print(f"No existe la caché {args.cache}: corré primero sin --usar-cache.", file=sys.stderr)
        return 1

    secciones_por_oferta = {}
    for oferta in OFERTAS_DIAGNOSTICO:
        secciones = document_utils.dividir_en_secciones(document_utils.extraer_texto_oferta(rutas[oferta]))
        secciones_por_oferta[oferta] = [s for s in secciones if not (config.EXCLUIR_INTRODUCCION and document_utils.es_introduccion(s))]
    trampas = {o: cargar_gt(o) for o in OFERTAS_DIAGNOSTICO}
    claves = {_clave(n, a) for o in OFERTAS_DIAGNOSTICO for t in trampas[o] for n, a in pares_trampa(t)}

    def buscar_oraciones(vector_db, ofertas):
        return {o: [datos_de_oraciones(vector_db, oraciones_de_seccion(s)) for s in secciones_por_oferta[o]] for o in ofertas}

    if args.usar_cache:
        with open(args.cache, encoding="utf-8") as f:
            cache = json.load(f)
        try:
            datos = {o: datos_desde_cache(cache, o, secciones_por_oferta[o]) for o in OFERTAS_DIAGNOSTICO}
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        fragmentos = cache.get("fragmentos") or {}
        oraciones = {o: oraciones_desde_cache(cache, o, secciones_por_oferta[o]) for o in OFERTAS_DIAGNOSTICO}
        refrescar = cache.get("version", 1) < 2          # la descripción de fragmentos de la versión 1 usaba un encabezado de artículo incorrecto
        faltan = [o for o, v in oraciones.items() if v is None]
        if refrescar or faltan:
            print("La caché está incompleta" + (" (fragmentos de una versión anterior)" if refrescar else "") + (f" (sin consultas por oración de {', '.join(faltan)})" if faltan else "")
                  + ": se abre el índice, sin reranker, para completarla.")
            vector_db = _abrir_indice()
            if not vector_db:
                return 1
            if refrescar:
                fragmentos = info_fragmentos(vector_db.get(include=["documents", "metadatas"]), claves)
            oraciones.update(buscar_oraciones(vector_db, faltan))
            with open(args.cache, "w", encoding="utf-8") as f:
                json.dump(a_cache(secciones_por_oferta, datos, fragmentos, oraciones), f, ensure_ascii=False)
            print(f"Caché actualizada en {args.cache}")
    else:
        vector_db = _abrir_indice()
        if not vector_db:
            return 1
        modelo = rag_components._get_reranker_model(rag_components.RERANKER_MODEL_NAME)
        puntuar = lambda consulta, docs: [rag_components._normalizar_score(s) for s in modelo.score([(consulta, d.page_content) for d in docs])]
        en_chroma = vector_db.get(include=["documents", "metadatas"])
        total = len(en_chroma["ids"])
        datos = {o: [datos_de_consultas(vector_db, consultas_de_seccion(s), puntuar, total) for s in secciones_por_oferta[o]] for o in OFERTAS_DIAGNOSTICO}
        fragmentos = info_fragmentos(en_chroma, claves)
        oraciones = buscar_oraciones(vector_db, OFERTAS_DIAGNOSTICO)
        with open(args.cache, "w", encoding="utf-8") as f:
            json.dump(a_cache(secciones_por_oferta, datos, fragmentos, oraciones), f, ensure_ascii=False)
        print(f"Caché guardada en {args.cache}")

    filas, pares_por_oferta = [], {}
    for oferta in OFERTAS_DIAGNOSTICO:
        f, pares_por_oferta[oferta] = analizar_recorte(oferta, trampas[oferta], secciones_por_oferta[oferta], datos[oferta], oraciones[oferta])
        filas += f
    print(informe_recorte(filas, pares_por_oferta, fragmentos))
    if args.csv:
        nombres = [c.nombre for c in CONFIGURACIONES]
        os.makedirs(os.path.dirname(os.path.abspath(args.csv)), exist_ok=True)
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["trampa", "oferta", "seccion", "articulo", "puesto_densa", "puesto_reranker", "puesto_indice_completo"] + nombres)
            w.writerows([[x["id"], x["oferta"], x["seccion"], x["articulo"], x["puesto_densa"] or "", x["puesto_reranker"] or "",
                          min((v for v in x["puestos_indice"].values() if v), default="")] + [int(x["entra"][n]) for n in nombres] for x in filas])
        print(f"CSV: {args.csv}")
    return 0


def main_hibrida(argv=None) -> int:
    from evaluacion.evaluar import cargar_gt
    p = argparse.ArgumentParser(prog="diagnostico_recuperacion hibrida", description="Recall@artículo con recuperación densa e híbrida (sin LLM).")
    p.add_argument("--oferta", action="append", required=True, metavar="P1=ruta", help="oferta y su archivo (P1 y P2); repetible")
    p.add_argument("--csv", default=csv_por_defecto("diagnostico_hibrida.csv"), help="Ruta del CSV con el detalle por trampa (por defecto en evaluacion/diagnosticos/)")
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
        os.makedirs(os.path.dirname(os.path.abspath(args.csv)), exist_ok=True)
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
