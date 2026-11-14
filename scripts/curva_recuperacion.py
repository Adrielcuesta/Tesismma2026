# scripts/curva_recuperacion.py
"""Curva de recuperación de la KB sobre P1 y P2 (sin LLM): recall de trampas y de casos conformes frente a K y frente a los pares a verificar, por embedding.

    python -m scripts.diagnostico_recuperacion curva --oferta P1=<oferta_P1.pdf|docx> --oferta P2=<oferta_P2.pdf|docx>
        [--embedding bge-m3|qwen3-local|deepinfra|gemini ...] [--si] [--permitir-prueba] [--ranking-chroma] [--salida <carpeta>]

Fidelidad al pipeline: cada punto de la curva es una tupla (K_SUBSECCION, TOP_DENSA_SUBSECCION, TOP_N_SUBSECCION, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)
y sus artículos salen de diagnostico_recuperacion.seleccion_final (la función que replica rag_components.recuperar_seccion), no de una versión idealizada:
  densa:    solo denso            (K, K, 0)             sin reranker
  reranker: denso + reranker      (100, 0, K)           grupo fijo de 100 candidatos densos que el reranker reordena; K de 1 a 100
  union:    unión anidada         (100, k, k)           mismo grupo de 100; los k primeros densos + los k primeros del reranker; k de 1 a 50
La configuración actual (10, 5, 5, tope 25, N=2, cupo 8) es solo el punto de referencia (punto_actual): no es un punto de ninguna serie.
VERIFICAR_TOPE no limita en la curva. Los gráficos principales fijan las oraciones en la configuración actual (N=2, cupo 8); la grilla completa va al .md.

Calibración obligatoria: antes de cualquier curva se corre con bge-m3 la configuración actual del pipeline sobre P1+P2 y tiene que dar lo medido en v1
(Recall@artículo 24/30 y 516 pares). Si no coincide se escribe el error en el .md y NO se generan curvas.
No elige K: la elección es del usuario, con la curva recall-pares."""
import argparse
import csv
import datetime
import json
import math
import os
import sys

import numpy as np

from . import config, document_utils, embeddings as emb_mod, rag_components
from . import diagnostico_recuperacion as dr

SIN_TOPE = 10 ** 6
OFERTAS_BASE = ("P1", "P2")
OFERTAS_PRUEBA = ("P3", "P4")
ESPERADO_CALIBRACION = {"recall": 24, "n_trampas": 30, "pares": 516}      # lo medido en v1 sobre P1+P2 con la configuración actual
N_RERANKER = 100                                                         # grupo fijo de candidatos densos que reordena el reranker (se puntúa una vez por consulta)
ORACION_ACTUAL = (2, 8)                                                  # (ORACIONES_N, ORACIONES_CUPO) de la configuración actual
N_ORACIONES = (0, 1, 2, 3, 5)
CUPOS_ORACIONES = (0, 4, 8, 10, 15, SIN_TOPE)
N_ORACION_FILA = (1, 2, 3, 5)
KS_RERANKER = tuple(range(1, N_RERANKER + 1))
KS_UNION = tuple(range(1, 51))
K_REFERENCIA_GRILLA = {"densa": 10, "reranker": 5, "union": 5}           # K donde se mide la grilla de oraciones (el de la configuración actual)
UMBRALES_K = (0.90, 0.95, 0.99, 1.00)
IGUAL_COSTO = (400, 516, 700)
NOMBRES_VARIANTE = {"densa": "solo denso (sin reranker)", "reranker": "denso + reranker (100 candidatos)", "union": "unión denso + reranker (100 candidatos)"}
# la configuración actual del pipeline (tiene que ser igual a dr.CONFIGURACIONES['union_oraciones_cifras_N2_cupo8']; lo verifica un test)
CONFIG_ACTUAL = dr.Config("actual_pipeline", 10, 5, 25, "union", None, (True, 2), 8)


# --- Puntos: tupla del pipeline <-> Config del diagnóstico ---

def punto(variante: str, k: int, n: int = ORACION_ACTUAL[0], cupo: int = ORACION_ACTUAL[1], tope: int = SIN_TOPE) -> dict:
    """Punto de la curva con sus parámetros del pipeline: densa (K, K, 0), reranker (100, 0, K), union (100, k, k)."""
    if variante == "densa":
        k_sub, top_densa, top_n = k, k, 0
    elif variante == "reranker":
        k_sub, top_densa, top_n = N_RERANKER, 0, k
    elif variante == "union":
        k_sub, top_densa, top_n = N_RERANKER, k, k
    else:
        raise ValueError(f"Variante desconocida: {variante}")
    return {"variante": variante, "k": k, "k_sub": k_sub, "top_densa": top_densa, "top_n": top_n, "tope": tope, "oraciones_n": n, "oraciones_cupo": cupo}


def punto_actual() -> dict:
    """La configuración actual del pipeline (K_SUBSECCION 10, 5 + 5, VERIFICAR_TOPE 25, N=2, cupo 8): el punto de referencia, con su tope real."""
    return {"variante": "union", "k": 5, "k_sub": 10, "top_densa": 5, "top_n": 5, "tope": 25, "oraciones_n": ORACION_ACTUAL[0], "oraciones_cupo": ORACION_ACTUAL[1]}


def tupla_pipeline(p: dict) -> tuple:
    """(K_SUBSECCION, TOP_DENSA_SUBSECCION, TOP_N_SUBSECCION, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)."""
    return (p["k_sub"], p["top_densa"], p["top_n"], p["tope"], p["oraciones_n"], p["oraciones_cupo"])


def config_de(p: dict) -> dr.Config:
    """El Config del diagnóstico que reproduce el punto: modo densa (top dense), reranker (top del reranker sobre k_sub) o union (ambos)."""
    modo = p["variante"]
    top = p["top_densa"] if modo == "densa" else p["top_n"]
    con_oraciones = bool(p["oraciones_n"]) and bool(p["oraciones_cupo"])
    return dr.Config(f"{modo}_{p['k']}", p["k_sub"], top, p["tope"], modo, None, (True, p["oraciones_n"]) if con_oraciones else None, p["oraciones_cupo"] if con_oraciones else None)


def ks_densa(total: int) -> list:
    """1 a 50 de a uno, 60, 75, 100, 150, 200, 300 y todos los fragmentos."""
    return sorted({k for k in list(range(1, 51)) + [60, 75, 100, 150, 200, 300] if k < total} | {total})


def bloque_perfil(p: dict, embedding: str, tope: int = None) -> str:
    """Línea lista para pegar en config.PERFILES_RECUPERACION['elegido'] (VERIFICAR_TOPE: el tope con el que el pipeline reproduce el punto, si no se pasa el del punto)."""
    k_sub, top_densa, top_n, tope_p, n, cupo = tupla_pipeline(p)
    return (f'"elegido": {{"EMBEDDING_BACKEND": "{embedding}", "K_SUBSECCION": {k_sub}, "TOP_DENSA_SUBSECCION": {top_densa}, "TOP_N_SUBSECCION": {top_n}, '
            f'"VERIFICAR_TOPE": {tope if tope is not None else tope_p}, "ORACIONES_CIFRAS": {bool(n and cupo)}, "ORACIONES_N": {n}, "ORACIONES_CUPO": {cupo}}}')


# --- Filas (trampas y casos conformes) ---

def _clave(d) -> tuple:
    return (d.metadata.get("norma"), rag_components.articulo_base(d.metadata.get("articulo", "")))


def validar_ofertas(ofertas, permitir_prueba: bool) -> None:
    """Solo P1 y P2; con P3 o P4 aborta salvo --permitir-prueba (el conjunto de prueba no se usa para elegir K)."""
    ofertas = set(ofertas)
    if not set(OFERTAS_BASE) <= ofertas:
        raise SystemExit("Hacen falta P1 y P2 (la calibración se hace sobre P1+P2).")
    extra = ofertas - set(OFERTAS_BASE)
    if extra and not (permitir_prueba and extra <= set(OFERTAS_PRUEBA)):
        raise SystemExit(f"Las ofertas {', '.join(sorted(extra))} son del conjunto de prueba: la curva se hace solo con P1 y P2 (--permitir-prueba para incluirlas, avisado en el informe).")


def _seccion_de_texto(texto: str, secciones: list):
    """Sección que contiene el texto (seccion_de_trampa); si no, con los primeros 60 caracteres normalizados (el criterio con que evaluar.py reconoce una frase)."""
    i = dr.seccion_de_trampa({"fragmento_trampa": texto}, secciones)
    if i is None:
        frase = dr._alfanumerico(texto)[:60]
        i = next((j for j, s in enumerate(secciones) if frase and frase in dr._alfanumerico(s["texto"])), None)
    return i


def construir_filas(oferta: str, secciones: list, trampas: list, conformes: list, desplazamiento: int = 0) -> list:
    """Una fila por trampa y por caso conforme: sección (índice global = desplazamiento + posición), artículos objetivo (cualquiera acierta) y la frase."""
    from evaluacion.evaluar import pares_espejo, pares_trampa
    filas = []
    for t in trampas:
        i = dr.seccion_de_trampa(t, secciones)
        filas.append({"tipo": "trampa", "id": t["id"], "oferta": oferta, "sec": None if i is None else desplazamiento + i, "seccion": None if i is None else secciones[i]["id"],
                      "pares": {(n, dr._base(a)) for n, a in pares_trampa(t)}, "texto": t["fragmento_trampa"], "articulo": f"{t['norma']} {dr._base(t['articulo'])}"})
    for k, c in enumerate(conformes, 1):
        i = _seccion_de_texto(c["cita_conforme"], secciones)
        pares = {(n, dr._base(a)) for n, a in pares_espejo(c)}
        filas.append({"tipo": "conforme", "id": f"{oferta}-C{k:02d}", "oferta": oferta, "sec": None if i is None else desplazamiento + i, "seccion": None if i is None else secciones[i]["id"],
                      "pares": pares, "texto": c["cita_conforme"], "articulo": "; ".join(f"{n} {a}" for n, a in sorted(pares))})
    return filas


def oracion_de_fila(texto: str, oraciones: list):
    """La oración de la sección que contiene la frase de la fila (o, si la frase abarca varias, la más larga contenida en ella); None si no hay."""
    frase = dr._alfanumerico(texto)
    if not frase:
        return None
    for o in oraciones:
        if frase in dr._alfanumerico(o):
            return o
    contenidas = [o for o in oraciones if len(dr._alfanumerico(o)) > 20 and dr._alfanumerico(o) in frase]
    return max(contenidas, key=len) if contenidas else None


# --- Datos por embedding: ranking denso completo, reranker sobre los 100 primeros y consultas por oración ---

def rankear_numpy(backend, vec_docs: np.ndarray):
    """textos -> [(orden de fragmentos de mayor a menor coseno, puntajes en ese orden)]; vectores normalizados: el producto punto es el coseno. Empates por posición."""
    def rankear(textos: list) -> list:
        puntajes = backend.embed_queries(textos) @ vec_docs.T
        orden = np.argsort(-puntajes, axis=1, kind="stable")
        return [(orden[i], puntajes[i, orden[i]]) for i in range(len(textos))]
    return rankear


def rankear_chroma(vector_db, fragmentos: list):
    """Igual que el pipeline: similarity_search_with_score sobre todo el índice (para bge-m3, si la calibración no cierra con el camino numpy)."""
    indice = {(f.metadata.get("norma"), str(f.metadata.get("articulo")), f.metadata.get("parte")): j for j, f in enumerate(fragmentos)}

    def rankear(textos: list) -> list:
        salida = []
        for t in textos:
            hallados = vector_db.similarity_search_with_score(t, k=len(fragmentos))
            orden = [indice[(d.metadata.get("norma"), str(d.metadata.get("articulo")), d.metadata.get("parte"))] for d, _ in hallados]
            salida.append((np.array(orden), np.array([-float(dist) for _, dist in hallados])))
        return salida
    return rankear


def vectores_de_chroma(fragmentos: list) -> np.ndarray:
    """Vectores de los fragmentos desde el índice BGE-M3 actual (sin reindexar y sin cargar el modelo), alineados con `fragmentos` por (norma, artículo, parte)."""
    from langchain_community.vectorstores import Chroma
    vector_db = Chroma(persist_directory=config.CHROMA_DB_PATH_KB, collection_name=config.CHROMA_COLLECTION_KB, embedding_function=None)
    datos = vector_db.get(include=["embeddings", "metadatas"])
    por_clave = {(m.get("norma"), str(m.get("articulo")), m.get("parte")): e for m, e in zip(datos["metadatas"], datos["embeddings"])}
    try:
        return emb_mod.normalizar([por_clave[(f.metadata.get("norma"), str(f.metadata.get("articulo")), f.metadata.get("parte"))] for f in fragmentos])
    except KeyError as e:
        raise ValueError(f"El índice ChromaDB no corresponde a la KB actual (falta {e.args[0]}): hay que reindexar antes de medir.") from e


class PuntuadorReranker:
    """Puntajes del reranker con caché en disco: clave = (max_length, sha1 de la consulta, sha1 del fragmento); no depende del embedding, así se comparte entre
    ellos. El modelo se carga solo si falta algún par. `real(consulta, docs) -> [float]` (por defecto bge-reranker-v2-m3)."""

    def __init__(self, ruta: str, real=None):
        self.ruta, self.real, self.puntajes, self.calculados = ruta, real, {}, 0
        if os.path.isfile(ruta):
            with open(ruta, encoding="utf-8") as f:
                self.puntajes = json.load(f)

    def _real(self, consulta, docs):
        if self.real is None:
            modelo = rag_components._get_reranker_model(rag_components.RERANKER_MODEL_NAME)
            self.real = lambda c, ds: [rag_components._normalizar_score(s) for s in modelo.score([(c, d.page_content) for d in ds])]
        return self.real(consulta, docs)

    def __call__(self, consulta: str, docs: list) -> list:
        base = f"{config.RERANKER_MAX_LENGTH}:{emb_mod._sha(consulta)[:16]}:"
        claves = [base + emb_mod._sha(d.page_content)[:12] for d in docs]
        faltan = [i for i, c in enumerate(claves) if c not in self.puntajes]
        if faltan:
            for i, s in zip(faltan, self._real(consulta, [docs[i] for i in faltan])):
                self.puntajes[claves[i]] = float(s)
            self.calculados += len(faltan)
            os.makedirs(os.path.dirname(self.ruta), exist_ok=True)
            with open(self.ruta + ".tmp", "w", encoding="utf-8") as f:
                json.dump(self.puntajes, f)
            os.replace(self.ruta + ".tmp", self.ruta)
        return [self.puntajes[c] for c in claves]


def _con_cifras(texto: str) -> bool:
    return any(c.isdigit() for c in texto)


def textos_de_consulta(plano: list, oraciones_filas: dict) -> list:
    """Textos que se buscan, sin repetir y en orden: consultas por subsección, oraciones con cifras y la oración de cada fila (recortados como en el pipeline)."""
    maximo = config.SUBSECTION_QUERY_MAX_CHARS
    textos = []
    for _, s in plano:
        textos += dr.consultas_de_seccion(s)
        textos += [o[:maximo] for o in rag_components.oraciones_de_seccion(s) if _con_cifras(o)]
    textos += [o[:maximo] for o in oraciones_filas.values()]
    return list(dict.fromkeys(textos))


def articulos_de_ranking(orden, puntajes, fragmentos: list, k: int = rag_components.K_ORACION, n: int = dr.N_MAXIMO_ORACION) -> list:
    """[(norma, artículo, puntaje)] de los n primeros artículos distintos (sin preámbulo) entre los k primeros fragmentos: como consultar_oraciones."""
    vistos = {}
    for r, j in enumerate(orden[:k]):
        d = fragmentos[j]
        if d.metadata.get("articulo", "") != "preambulo":
            vistos.setdefault(_clave(d), float(puntajes[r]))
    return [(nn, a, v) for (nn, a), v in list(vistos.items())[:n]]


def preparar_datos(rankear, fragmentos: list, plano: list, oraciones_filas: dict, puntuar) -> dict:
    """{'secciones': [{oferta, id, consultas: [[Cand]], oraciones: [{con_cifras, articulos}]}], 'oracion_fila': {índice de fila: [(norma, artículo)]}}.
    Cada consulta lleva el ranking denso COMPLETO como Cand(doc, densa, reranker); el reranker puntúa solo los N_RERANKER primeros (el resto, -inf)."""
    maximo = config.SUBSECTION_QUERY_MAX_CHARS
    textos = textos_de_consulta(plano, oraciones_filas)
    ranking = dict(zip(textos, rankear(textos)))
    secciones = []
    for oferta, s in plano:
        consultas = []
        for q in dr.consultas_de_seccion(s):
            orden, puntajes = ranking[q]
            reranker = puntuar(q, [fragmentos[j] for j in orden[:N_RERANKER]])
            consultas.append([dr.Cand(fragmentos[j], float(puntajes[r]), float(reranker[r]) if r < len(reranker) else -math.inf) for r, j in enumerate(orden)])
        oraciones = []
        for o in rag_components.oraciones_de_seccion(s):
            if not _con_cifras(o):
                oraciones.append({"con_cifras": False, "articulos": []})
                continue
            orden, puntajes = ranking[o[:maximo]]
            oraciones.append({"con_cifras": True, "articulos": [{"norma": n, "articulo": a, "densa": v} for n, a, v in articulos_de_ranking(orden, puntajes, fragmentos)]})
        secciones.append({"oferta": oferta, "id": s["id"], "consultas": consultas, "oraciones": oraciones})
    oracion_fila = {i: [(n, a) for n, a, _ in articulos_de_ranking(*ranking[o[:maximo]], fragmentos)] for i, o in oraciones_filas.items()}
    return {"secciones": secciones, "oracion_fila": oracion_fila}


# --- Medición ---

def evaluar_punto(cfg, filas: list, secciones: list, ofertas=None) -> dict:
    """Aciertos y pares de una configuración. pares = Σ por sección de len(seleccion_final): artículos únicos (norma, artículo) sin preámbulo, es decir las llamadas
    al verificador. max_base: el mayor tamaño de la base de una sección (lo que tendría que cubrir VERIFICAR_TOPE para no recortar nada)."""
    ofertas = set(ofertas) if ofertas else None
    seleccion, pares, max_base, por_oferta = {}, 0, 0, {}
    for i, s in enumerate(secciones):
        if ofertas and s["oferta"] not in ofertas:
            continue
        elegidos = dr.seleccion_final(s["consultas"], cfg, s["oraciones"])
        seleccion[i] = {_clave(d) for d in elegidos}
        pares += len(elegidos)
        por_oferta[s["oferta"]] = por_oferta.get(s["oferta"], 0) + len(elegidos)
        max_base = max(max_base, len(dr._seleccion_base(s["consultas"], cfg)))
    hits, n = {"trampa": 0, "conforme": 0}, {"trampa": 0, "conforme": 0}
    for f in filas:
        if ofertas and f["oferta"] not in ofertas:
            continue
        n[f["tipo"]] += 1
        hits[f["tipo"]] += f["sec"] is not None and bool(f["pares"] & seleccion[f["sec"]])
    return {"hits_t": hits["trampa"], "n_t": n["trampa"], "hits_c": hits["conforme"], "n_c": n["conforme"], "pares": pares, "pares_por_oferta": por_oferta, "max_base": max_base}


def medir(p: dict, filas: list, secciones: list) -> dict:
    """Fila de resultados de un punto: aciertos, recall con IC de Wilson, pares y los parámetros del pipeline."""
    from evaluacion.evaluar import wilson
    r = evaluar_punto(config_de(p), filas, secciones)
    ic = wilson(r["hits_t"], r["n_t"]) or (None, None)
    total = r["n_t"] + r["n_c"]
    return {**p, **r, "recall_trampas": r["hits_t"] / r["n_t"] if r["n_t"] else None, "ic_inf": ic[0], "ic_sup": ic[1],
            "recall_conformes": r["hits_c"] / r["n_c"] if r["n_c"] else None, "recall_total": (r["hits_t"] + r["hits_c"]) / total if total else None}


def serie(variante: str, ks, filas: list, secciones: list, n: int = ORACION_ACTUAL[0], cupo: int = ORACION_ACTUAL[1]) -> list:
    return [medir(punto(variante, k, n, cupo), filas, secciones) for k in ks]


def grilla_oraciones(variante: str, filas: list, secciones: list) -> list:
    """Una medición por celda (ORACIONES_N × ORACIONES_CUPO) en el K de referencia de la variante."""
    k = K_REFERENCIA_GRILLA[variante]
    return [medir(punto(variante, k, n, cupo), filas, secciones) for n in N_ORACIONES for cupo in CUPOS_ORACIONES if n or cupo == CUPOS_ORACIONES[0]]


def proyecciones(pares: int, seg_local: float, usd_par: float, seg_nube: float) -> dict:
    return {"horas_local_proy": pares * seg_local / 3600, "usd_nube_proy": pares * usd_par, "horas_nube_proy": pares * seg_nube / 3600}


def completar_serie(filas_serie: list, seg_local: float, usd_par: float, seg_nube: float) -> list:
    """Agrega proyecciones y la ganancia marginal por paso: trampas_extra / (pares_extra / 100); None si el paso no suma pares."""
    previa = None
    for r in filas_serie:
        r.update(proyecciones(r["pares"], seg_local, usd_par, seg_nube))
        r["trampas_extra"] = r["hits_t"] - previa["hits_t"] if previa else None
        r["pares_extra"] = r["pares"] - previa["pares"] if previa else None
        r["ganancia_marginal"] = (r["trampas_extra"] / (r["pares_extra"] / 100)) if previa and r["pares_extra"] > 0 else None
        previa = r
    return filas_serie


def k_para_recall(filas_serie: list, umbral: float):
    """Primera fila de la serie con recall de trampas >= umbral; None si nunca lo alcanza."""
    return next((r for r in filas_serie if r["recall_trampas"] is not None and r["recall_trampas"] >= umbral - 1e-9), None)


def indice_codo(pares: list, aciertos: list):
    """Codo de la curva (Kneedle, Satopää et al. 2011): con ambos ejes llevados a [0, 1], el punto que más se aleja de la diagonal. None si la curva es plana o no hay codo."""
    if len(pares) < 3:
        return None
    x, y = np.asarray(pares, dtype=float), np.asarray(aciertos, dtype=float)
    if x.max() == x.min() or y.max() == y.min():
        return None
    orden = np.argsort(x, kind="stable")
    d = (y[orden] - y.min()) / (y.max() - y.min()) - (x[orden] - x.min()) / (x.max() - x.min())
    mejor = int(np.argmax(d))
    return int(orden[mejor]) if d[mejor] > 0 else None


def indice_por_umbral(filas_serie: list, umbral: float, pasos: int = 3):
    """Índice del último punto antes de `pasos` pasos seguidos con ganancia marginal < umbral (trampas por cada 100 pares extra); None si no ocurre."""
    # un paso que no suma trampas (o las pierde, como puede pasar en la unión al crecer el pool) no tiene ganancia; uno que las suma sin sumar pares, ganancia infinita
    g = [0.0 if (r["trampas_extra"] or 0) <= 0 else (r["ganancia_marginal"] if r["ganancia_marginal"] is not None else math.inf) for r in filas_serie]
    for j in range(1, len(filas_serie) - pasos + 1):
        if all(g[j + i] < umbral for i in range(pasos)):
            return j - 1
    return None


def auc_log(filas_serie: list) -> float:
    """Área bajo la curva recall-K con K en escala logarítmica, normalizada a [0, 1] (promedio del recall sobre log K)."""
    x = [math.log10(r["k"]) for r in filas_serie]
    y = [r["recall_trampas"] for r in filas_serie]
    if len(x) < 2 or x[-1] == x[0]:
        return y[0] if y else 0.0
    return sum((x[i + 1] - x[i]) * (y[i] + y[i + 1]) / 2 for i in range(len(x) - 1)) / (x[-1] - x[0])


def aviso_reranker_sigue_subiendo(filas_serie: list):
    """Texto de aviso si la curva con reranker todavía suma más de 1 trampa entre K=75 y K=100 (el grupo de 100 candidatos podría estar corto: conviene probar 200); None si no."""
    por_k = {r["k"]: r for r in filas_serie}
    if 75 not in por_k or 100 not in por_k:
        return None
    extra = por_k[100]["hits_t"] - por_k[75]["hits_t"]
    if extra <= 1:
        return None
    return (f"**AVISO:** la curva con reranker todavía sube {extra} trampas entre K=75 ({por_k[75]['hits_t']}/{por_k[75]['n_t']}) y K=100 ({por_k[100]['hits_t']}/{por_k[100]['n_t']}): "
            f"el grupo de {N_RERANKER} candidatos puede estar corto; conviene probar con 200.")


def punto_mas_cercano(filas_serie: list, pares: int) -> dict:
    return min(filas_serie, key=lambda r: (abs(r["pares"] - pares), r["pares"]))


def calibrar(secciones: list, filas: list, esperado: dict = None) -> dict:
    """Corre la configuración actual del pipeline sobre P1+P2 y la compara con lo medido en v1. {'ok', 'obtenido', 'esperado', 'mensaje'}."""
    esperado = esperado or ESPERADO_CALIBRACION
    r = evaluar_punto(CONFIG_ACTUAL, filas, secciones, OFERTAS_BASE)
    obtenido = {"recall": r["hits_t"], "n_trampas": r["n_t"], "pares": r["pares"], "pares_por_oferta": r["pares_por_oferta"]}
    ok = (obtenido["recall"], obtenido["n_trampas"], obtenido["pares"]) == (esperado["recall"], esperado["n_trampas"], esperado["pares"])
    mensaje = (f"Calibración OK: la configuración actual del pipeline (K 10, 5 + 5, tope 25, N=2, cupo 8) sobre P1+P2 da Recall@artículo {obtenido['recall']}/{obtenido['n_trampas']} "
               f"y {obtenido['pares']} pares, igual que v1." if ok else
               f"CALIBRACIÓN FALLIDA: la configuración actual del pipeline (K 10, 5 + 5, tope 25, N=2, cupo 8) sobre P1+P2 dio Recall@artículo {obtenido['recall']}/{obtenido['n_trampas']} "
               f"y {obtenido['pares']} pares; v1 midió {esperado['recall']}/{esperado['n_trampas']} y {esperado['pares']}. No se generaron curvas.")
    return {"ok": ok, "obtenido": obtenido, "esperado": esperado, "mensaje": mensaje}


# --- Salidas ---

COLUMNAS_CSV = ["embedding", "variante", "k", "k_sub", "top_densa", "top_n", "tope", "oraciones_n", "oraciones_cupo", "es_actual", "hits_trampas", "n_trampas", "recall_trampas",
                "ic_trampas_inf", "ic_trampas_sup", "recall_conformes", "recall_total", "pares", "horas_local_proy", "usd_nube_proy", "horas_nube_proy", "trampas_extra",
                "pares_extra", "ganancia_marginal"]


def filas_csv(resultados: dict) -> list:
    """Una fila por punto de las series y de la grilla de oraciones de cada embedding, más el punto «actual_pipeline» con su tope real."""
    salida = []
    for embedding, r in resultados.items():
        grupos = [(s, False) for s in r["series"].values()] + [(g, False) for g in r["grillas"].values()] + [([r["actual"]], True)]
        for grupo, es_actual in grupos:
            for x in grupo:
                salida.append({"embedding": embedding, **{k: x.get(k) for k in ("variante", "k", "k_sub", "top_densa", "top_n", "tope", "oraciones_n", "oraciones_cupo")},
                               "es_actual": int(es_actual), "hits_trampas": x["hits_t"], "n_trampas": x["n_t"], "recall_trampas": x["recall_trampas"], "ic_trampas_inf": x["ic_inf"],
                               "ic_trampas_sup": x["ic_sup"], "recall_conformes": x["recall_conformes"], "recall_total": x["recall_total"], "pares": x["pares"],
                               **{k: x.get(k) for k in ("horas_local_proy", "usd_nube_proy", "horas_nube_proy", "trampas_extra", "pares_extra", "ganancia_marginal")}})
    return salida


def guardar_csv(resultados: dict, ruta: str) -> None:
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS_CSV, delimiter=";")
        w.writeheader()
        for fila in filas_csv(resultados):
            w.writerow({k: ("" if v is None else v) for k, v in fila.items()})


AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, GRIS, TINTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#9a9a95", "#222222"
COLORES_EMBEDDING = [AZUL, NARANJA, AQUA, MAGENTA, AMARILLO, GRIS]


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white", "font.size": 13, "axes.titlesize": 14, "axes.labelsize": 13,
                         "legend.fontsize": 11, "axes.edgecolor": "#888888", "text.color": TINTA, "axes.labelcolor": TINTA, "xtick.color": TINTA, "ytick.color": TINTA,
                         "axes.spines.top": False, "axes.spines.right": False})
    return plt


def _estilo(variante: str, i: int) -> dict:
    """Con reranker sólida, sin reranker punteada."""
    return {"color": COLORES_EMBEDDING[i % len(COLORES_EMBEDDING)], "linestyle": ":" if variante == "densa" else "-", "marker": "o", "markersize": 3.5, "linewidth": 1.8}


def _pct(v, y=None) -> str:
    return f"{v:.0%}"


def grafico_recall(resultados: dict, ruta: str) -> None:
    plt = _plt()
    fig, ejes = plt.subplots(1, 3, figsize=(19, 6.2), sharey=True)
    for eje, variante in zip(ejes, NOMBRES_VARIANTE):
        for i, (nombre, r) in enumerate(resultados.items()):
            s = r["series"][variante]
            eje.plot([x["k"] for x in s], [x["recall_trampas"] for x in s], label=nombre, **_estilo(variante, i))
        for nivel in (0.9, 0.95, 1.0):
            eje.axhline(nivel, color="#bbbbbb", linewidth=0.8, linestyle="--")
        if variante == "union":
            actual = next(iter(resultados.values()))["actual"]
            eje.scatter([5], [actual["recall_trampas"]], s=140, marker="D", color="black", zorder=5, label="configuración actual (K 10, 5 + 5, tope 25)")
        eje.set_xscale("log")
        eje.set_title(NOMBRES_VARIANTE[variante] + (" (K)" if variante != "union" else " (k)"), loc="left")
        eje.set_xlabel("K (escala logarítmica)")
        eje.yaxis.set_major_formatter(_pct)
        eje.grid(color="#eeeeee")
    ejes[0].set_ylabel("Recall de trampas (P1 y P2)")
    ejes[0].set_ylim(0, 1.04)
    ejes[-1].legend(frameon=False, loc="lower right")
    fig.text(0.01, 0.005, "Oraciones fijas en la configuración actual (N=2, cupo 8); VERIFICAR_TOPE sin límite. Con reranker, línea sólida; sin reranker, punteada.", fontsize=10, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(ruta, dpi=170)
    plt.close(fig)


ETIQUETAR_K = {1, 2, 3, 5, 8, 10, 15, 20, 25, 30, 40, 50, 75, 100, 200, 300}


def grafico_recall_vs_pares(resultados: dict, ruta: str) -> None:
    """El gráfico para elegir K: recall de trampas contra los pares a verificar (el costo real), un punto por K, el codo marcado y la configuración actual."""
    plt = _plt()
    fig, ejes = plt.subplots(1, 3, figsize=(19, 6.5), sharey=True)
    for eje, variante in zip(ejes, NOMBRES_VARIANTE):
        for i, (nombre, r) in enumerate(resultados.items()):
            s = r["series"][variante]
            estilo = _estilo(variante, i)
            eje.plot([x["pares"] for x in s], [x["recall_trampas"] for x in s], label=nombre, **estilo)
            for x in s:
                if x["k"] in ETIQUETAR_K:
                    eje.annotate(str(x["k"]), (x["pares"], x["recall_trampas"]), textcoords="offset points", xytext=(3, -11), fontsize=8, color=estilo["color"])
            j = indice_codo([x["pares"] for x in s], [x["hits_t"] for x in s])
            if j is not None:
                eje.scatter([s[j]["pares"]], [s[j]["recall_trampas"]], s=170, marker="*", color=estilo["color"], edgecolor="black", zorder=6)
        actual = next(iter(resultados.values()))["actual"]
        eje.scatter([actual["pares"]], [actual["recall_trampas"]], s=120, marker="D", color="black", zorder=7, label=f"actual ({actual['pares']} pares)")
        for nivel in (0.9, 0.95, 1.0):
            eje.axhline(nivel, color="#bbbbbb", linewidth=0.8, linestyle="--")
        eje.set_title(NOMBRES_VARIANTE[variante], loc="left")
        eje.set_xlabel("Pares a verificar (llamadas al LLM)")
        eje.yaxis.set_major_formatter(_pct)
        eje.grid(color="#eeeeee")
    ejes[0].set_ylabel("Recall de trampas (P1 y P2)")
    ejes[0].set_ylim(0, 1.04)
    ejes[-1].legend(frameon=False, loc="lower right")
    fig.text(0.01, 0.005, "Estrella: codo (Kneedle). Rombo negro: configuración actual con su tope real (25). Los números son K (k en la unión). Oraciones fijas: N=2, cupo 8.", fontsize=10, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(ruta, dpi=170)
    plt.close(fig)


def grafico_costo(resultados: dict, ruta: str, seg_local: float, usd_par: float) -> None:
    plt = _plt()
    fig, ejes = plt.subplots(1, 3, figsize=(19, 6.2), sharey=True)
    for eje, variante in zip(ejes, NOMBRES_VARIANTE):
        for i, (nombre, r) in enumerate(resultados.items()):
            s = r["series"][variante]
            eje.plot([x["k"] for x in s], [x["pares"] for x in s], label=nombre, **_estilo(variante, i))
        eje.set_xscale("log")
        eje.set_title(NOMBRES_VARIANTE[variante], loc="left")
        eje.set_xlabel("K (escala logarítmica)")
        eje.grid(color="#eeeeee")
        horas = eje.secondary_yaxis(1.0, functions=(lambda p: p * seg_local / 3600, lambda h: h * 3600 / seg_local))
        usd = eje.secondary_yaxis(1.22, functions=(lambda p: p * usd_par, lambda u: u / usd_par))
        horas.set_ylabel("horas locales (proyección)")
        usd.set_ylabel("USD en la nube (proyección)")
    ejes[0].set_ylabel("Pares a verificar")
    ejes[0].legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(ruta, dpi=170, bbox_inches="tight")
    plt.close(fig)


# --- Informe .md ---

def _tabla(encabezado: list, filas: list) -> list:
    return ["| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)] + ["| " + " | ".join(str(c) for c in f) + " |" for f in filas] + [""]


def _rec(r: dict) -> str:
    return f"{r['hits_t']}/{r['n_t']} ({r['recall_trampas']:.0%}; {r['ic_inf']:.0%}–{r['ic_sup']:.0%})" if r["n_t"] else "n/d"


def _costo(r: dict) -> str:
    return f"{r['pares']} pares, {r['horas_local_proy']:.1f} h local, {r['usd_nube_proy']:.2f} USD nube"


def informe_calibracion_fallida(cal: dict, fecha: str, argumentos: str = "") -> str:
    o, e = cal["obtenido"], cal["esperado"]
    return "\n".join([f"# Curva de recuperación ({fecha}): CALIBRACIÓN FALLIDA", "", f"**{cal['mensaje']}**", "",
                      *_tabla(["", "Recall@artículo (trampas)", "Pares"], [["v1 (esperado)", f"{e['recall']}/{e['n_trampas']}", e["pares"]], ["Esta corrida", f"{o['recall']}/{o['n_trampas']}", o["pares"]]]),
                      "Pares por oferta en esta corrida: " + ", ".join(f"{k} {v}" for k, v in sorted(o["pares_por_oferta"].items())), "",
                      "Posibles causas: el orden denso del camino numpy difiere del de Chroma (probar `--ranking-chroma`, que busca como el pipeline); la KB o el índice cambiaron desde v1; "
                      "las ofertas no son las de v1; la segmentación o el reranker (max_length) son otros; o alguna fila del ground truth no se ubicó en su sección.",
                      "No se escribió ningún CSV ni gráfico: no se puede confiar en las curvas hasta que la calibración cierre.", f"Argumentos: {argumentos}" if argumentos else ""])


def informe_md(cal: dict, resultados: dict, salteados: dict, contexto: dict, args: dict) -> str:
    umbral = args["umbral_marginal"]
    L = [f"# Curva de recuperación ({contexto['fecha']})", "", f"**{cal['mensaje']}**", "",
         f"- Ofertas: {', '.join(contexto['ofertas'])}. Filas: {contexto['n_trampas']} trampas y {contexto['n_conformes']} casos conformes"
         + (f" ({contexto['sin_ubicar']} sin ubicar en ninguna sección: cuentan como no recuperadas)." if contexto["sin_ubicar"] else "."),
         f"- Base de conocimiento: {contexto['n_fragmentos']} fragmentos, {contexto['n_articulos']} artículos (norma, artículo), {contexto['n_normas']} normas.",
         f"- Proyecciones: {args['seg_por_par_local']} s por par en local, {args['usd_por_par_nube']} USD y {args['seg_por_par_nube']} s por par en la nube. Umbral marginal: {umbral} trampas por cada 100 pares extra (3 pasos seguidos)."]
    if contexto["con_prueba"]:
        L += ["", "> **AVISO:** esta corrida incluye ofertas del conjunto de prueba (`--permitir-prueba`); no usar estas curvas para elegir K."]
    if salteados:
        L += ["", "Embeddings salteados: " + "; ".join(f"{k} ({v})" for k, v in salteados.items())]
    avisos = [n for n, r in resultados.items() if aviso_reranker_sigue_subiendo(r["series"]["reranker"])]
    if avisos:
        L += ["", f"> **AVISO:** con {', '.join(avisos)} la curva con reranker todavía sube más de 1 trampa entre K=75 y K=100; conviene probar con un grupo de 200 candidatos (detalle en la sección de cada embedding)."]
    L += ["", "## Calibración", "", *_tabla(["Oferta", "Pares con la configuración actual"], [[k, v] for k, v in sorted(cal["obtenido"]["pares_por_oferta"].items())]),
          "## Embeddings: tiempos y costo", "", *_tabla(["Embedding", "Indexación (s, n)", "Consultas (s, n)", "Tokens reales / estimados", "USD esta corrida", "USD acumulado en caché"],
                                                         [[n, f"{r['meta']['documentos_s']:.1f}, {r['meta']['n_documentos']}", f"{r['meta']['consultas_s']:.1f}, {r['meta']['n_consultas']}",
                                                           f"{r['meta']['tokens']} / {r['meta']['tokens_estimados']}", f"{r['usd_corrida']:.4f}", f"{r['meta']['usd']:.4f}"] for n, r in resultados.items()])]
    for nombre, r in resultados.items():
        L += [f"## {nombre}", ""]
        for variante, s in r["series"].items():
            L += [f"### {NOMBRES_VARIANTE[variante]}", ""]
            aviso = aviso_reranker_sigue_subiendo(s) if variante == "reranker" else None
            if aviso:
                L += [aviso, ""]
            filas = []
            for u in UMBRALES_K:
                x = k_para_recall(s, u)
                filas.append([f"K{int(round(u * 100))}" if u < 1 else "K100", x["k"] if x else "nunca", _costo(x) if x else "—", f"`{tupla_pipeline(x)}`" if x else "—"])
            L += ["Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):", "",
                  *_tabla(["Punto", "K", "Costo", "Tupla del pipeline"], filas)]
            por_k = {x["k"]: x for x in s}
            L += ["Recall de trampas en K = 10, 25 y 50: " + " | ".join(f"K={k}: {_rec(por_k[k])}" if k in por_k else f"K={k}: —" for k in (10, 25, 50)), "",
                  f"Área bajo la curva (K en escala log, 0–1): {auc_log(s):.3f}", ""]
            codo, marg = indice_codo([x["pares"] for x in s], [x["hits_t"] for x in s]), indice_por_umbral(s, umbral)
            destacados = [("K90", k_para_recall(s, 0.90)), ("K95", k_para_recall(s, 0.95)), ("codo (Kneedle)", s[codo] if codo is not None else None),
                          (f"umbral marginal < {umbral}", s[marg] if marg is not None else None)]
            L += ["Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):", ""]
            for etiqueta, x in destacados:
                L.append(f"- {etiqueta}: " + (f"K={x['k']}, recall {_rec(x)}, {_costo(x)}\n  ```\n  {bloque_perfil(x, r['embedding'], tope=max(x['max_base'], 1))}\n  ```" if x else "no se alcanza"))
            L.append("")
        L += ["### Grilla de oraciones (ORACIONES_N × ORACIONES_CUPO), en el K de la configuración actual de cada variante", ""]
        for variante, g in r["grillas"].items():
            cupos = [c for c in CUPOS_ORACIONES]
            filas = []
            mejor = max(g, key=lambda x: (x["hits_t"], -x["pares"]))
            for n in N_ORACIONES:
                celdas = []
                for c in cupos:
                    x = next((y for y in g if y["oraciones_n"] == n and y["oraciones_cupo"] == c), None)
                    celdas.append("—" if x is None else f"{x['hits_t']}/{x['n_t']} · {x['pares']}" + (" **←**" if x is mejor else ""))
                filas.append([f"N={n}"] + celdas)
            L += [f"{NOMBRES_VARIANTE[variante]} (K={K_REFERENCIA_GRILLA[variante]}); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):", "",
                  *_tabla([""] + [("sin tope" if c == SIN_TOPE else f"cupo {c}") for c in cupos], filas)]
        fila_ref = r["oracion_fila"]
        L += ["### Referencia: recall usando solo la oración de la fila (no es una tupla del pipeline)", "",
              *_tabla(["N artículos de la oración", "Trampas", "Casos conformes", "Total"], [[n, *(f"{h}/{t}" for h, t in fila_ref[n])] for n in N_ORACION_FILA])]
        L += ["### Filas que no recupera el solo denso en K=50 (sin oraciones)", ""]
        L += ([f"- {x['id']} ({x['tipo']}, sección {x['seccion']}, {x['articulo']}): puesto del artículo en el ranking completo: {x['puesto'] or 'no aparece'}" for x in r["no_recuperadas"]] or ["- ninguna"]) + [""]
    L += ["## Comparación a igual costo (oraciones N=2, cupo 8; punto más cercano en pares)", ""]
    filas = []
    for objetivo in IGUAL_COSTO:
        for nombre, r in resultados.items():
            for variante, s in r["series"].items():
                x = punto_mas_cercano(s, objetivo)
                filas.append([f"~{objetivo}", nombre, NOMBRES_VARIANTE[variante], x["k"], x["pares"], _rec(x), f"`{tupla_pipeline(x)}`"])
    L += _tabla(["Pares objetivo", "Embedding", "Variante", "K", "Pares reales", "Recall de trampas (IC 95 %)", "Tupla"], filas)
    L += ["## Costo real gastado en API", "", *_tabla(["Embedding", "USD esta corrida", "USD acumulado"], [[n, f"{r['usd_corrida']:.4f}", f"{r['meta']['usd']:.4f}"] for n, r in resultados.items()]),
          "Los embeddings de Gemini se estiman (la API no informa tokens)."]
    return "\n".join(L)


# --- Orquestación ---

def resultados_de_embedding(nombre: str, embedding: str, datos: dict, filas: list, total: int, args: dict) -> dict:
    secciones = datos["secciones"]
    series = {"densa": serie("densa", ks_densa(total), filas, secciones), "reranker": serie("reranker", KS_RERANKER, filas, secciones), "union": serie("union", KS_UNION, filas, secciones)}
    for s in series.values():
        completar_serie(s, args["seg_por_par_local"], args["usd_por_par_nube"], args["seg_por_par_nube"])
    grillas = {v: grilla_oraciones(v, filas, secciones) for v in series}
    for g in grillas.values():
        for x in g:
            x.update(proyecciones(x["pares"], args["seg_por_par_local"], args["usd_por_par_nube"], args["seg_por_par_nube"]))
    actual = {**punto_actual(), **evaluar_punto(CONFIG_ACTUAL, filas, secciones)}
    from evaluacion.evaluar import wilson
    ic = wilson(actual["hits_t"], actual["n_t"]) or (None, None)
    actual.update(recall_trampas=actual["hits_t"] / actual["n_t"], ic_inf=ic[0], ic_sup=ic[1], recall_conformes=actual["hits_c"] / actual["n_c"] if actual["n_c"] else None,
                  recall_total=(actual["hits_t"] + actual["hits_c"]) / (actual["n_t"] + actual["n_c"]), **proyecciones(actual["pares"], args["seg_por_par_local"], args["usd_por_par_nube"], args["seg_por_par_nube"]))
    # referencia: solo la oración de la fila
    tot_filas = {"trampa": sum(f["tipo"] == "trampa" for f in filas), "conforme": sum(f["tipo"] == "conforme" for f in filas)}
    por_tipo = {n: {"trampa": 0, "conforme": 0} for n in N_ORACION_FILA}
    for i, f in enumerate(filas):
        for n in N_ORACION_FILA:
            if f["pares"] & {(a, b) for a, b in datos["oracion_fila"].get(i, [])[:n]}:
                por_tipo[n][f["tipo"]] += 1
    oracion_fila = {n: [(por_tipo[n]["trampa"], tot_filas["trampa"]), (por_tipo[n]["conforme"], tot_filas["conforme"]),
                        (por_tipo[n]["trampa"] + por_tipo[n]["conforme"], tot_filas["trampa"] + tot_filas["conforme"])] for n in N_ORACION_FILA}
    elegidos = {i: {_clave(d) for d in dr.seleccion_final(s["consultas"], config_de(punto("densa", 50, 0, 0)), [])} for i, s in enumerate(secciones)}
    no_recuperadas = []
    for f in filas:
        if f["sec"] is not None and f["pares"] & elegidos[f["sec"]]:
            continue
        puestos = [next((r for r, c in enumerate(q, 1) if _clave(c.doc) in f["pares"]), None) for q in (secciones[f["sec"]]["consultas"] if f["sec"] is not None else [])]
        puestos = [p for p in puestos if p]
        no_recuperadas.append({"id": f["id"], "tipo": f["tipo"], "seccion": f["seccion"], "articulo": f["articulo"], "puesto": min(puestos) if puestos else None})
    return {"embedding": embedding, "series": series, "grillas": grillas, "actual": actual, "oracion_fila": oracion_fila, "no_recuperadas": no_recuperadas}


def _cargar_contexto(rutas: dict) -> dict:
    """Lee las ofertas y el ground truth (sin LLM) y arma las secciones planas, las filas y los fragmentos de la KB."""
    from evaluacion.evaluar import cargar_espejos, cargar_gt
    plano, filas = [], []
    for oferta in sorted(rutas):
        secciones = document_utils.dividir_en_secciones(document_utils.extraer_texto_oferta(rutas[oferta]))
        secciones = [s for s in secciones if not (config.EXCLUIR_INTRODUCCION and document_utils.es_introduccion(s))]
        filas += construir_filas(oferta, secciones, cargar_gt(oferta), cargar_espejos(oferta), len(plano))
        plano += [(oferta, s) for s in secciones]
    oraciones_filas = {}
    for i, f in enumerate(filas):
        if f["sec"] is not None:
            o = oracion_de_fila(f["texto"], rag_components.oraciones_de_seccion(plano[f["sec"]][1]))
            if o:
                oraciones_filas[i] = o
    fragmentos = document_utils.cargar_kb_por_articulos(config.DIRECTORIO_NORMATIVA)
    return {"plano": plano, "filas": filas, "oraciones_filas": oraciones_filas, "fragmentos": fragmentos}


def _datos_de_embedding(nombre: str, ctx: dict, a, puntuar, directorio_cache: str):
    """(datos, backend, resultado de disponibilidad). Devuelve (None, backend, motivo) si hay que saltear el embedding."""
    fragmentos = ctx["fragmentos"]
    backend = emb_mod.crear_backend(nombre, {"qwen3-local": a.modelo_ollama, "deepinfra": a.modelo_deepinfra}.get(nombre), a.dim_gemini, directorio_cache)
    ok, motivo = backend.disponible()
    if not ok:
        return None, backend, motivo
    textos = textos_de_consulta(ctx["plano"], ctx["oraciones_filas"])
    chroma = nombre == "bge-m3"
    if not emb_mod.preflight(backend, [] if chroma else [f.page_content for f in fragmentos], textos, si=a.si):
        return None, backend, "no confirmado por el usuario"
    t0 = backend.cache.meta["usd"]
    if chroma and a.ranking_chroma:
        vector_db = dr._abrir_indice()
        if not vector_db:
            return None, backend, "no se pudo abrir el índice Chroma"
        rankear = rankear_chroma(vector_db, fragmentos)
    else:
        vec_docs = vectores_de_chroma(fragmentos) if chroma else backend.embed_documents([f.page_content for f in fragmentos])
        rankear = rankear_numpy(backend, vec_docs)
    datos = preparar_datos(rankear, fragmentos, ctx["plano"], ctx["oraciones_filas"], puntuar)
    datos["usd_corrida"] = backend.cache.meta["usd"] - t0
    return datos, backend, ""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="diagnostico_recuperacion curva", description="Curva de recuperación (recall frente a K y a pares) sobre P1 y P2, sin LLM.")
    p.add_argument("--oferta", action="append", required=True, metavar="P1=ruta", help="oferta y su archivo (P1 y P2; repetible)")
    p.add_argument("--embedding", action="append", choices=emb_mod.BACKENDS, help="embedding a medir (repetible; por defecto bge-m3)")
    p.add_argument("--modelo-ollama", default=config.EMBEDDING_MODELOS["qwen3-local"])
    p.add_argument("--modelo-deepinfra", default=config.EMBEDDING_MODELOS["deepinfra"])
    p.add_argument("--dim-gemini", type=int, default=config.EMBEDDING_DIM_GEMINI)
    p.add_argument("--si", action="store_true", help="no pide confirmación antes de llamar a una API de pago")
    p.add_argument("--permitir-prueba", action="store_true", help="admite P3 y P4 (conjunto de prueba; queda avisado en el informe)")
    p.add_argument("--ranking-chroma", action="store_true", help="bge-m3: ranking con similarity_search_with_score de Chroma (como el pipeline) en vez del camino numpy")
    p.add_argument("--seg-por-par-local", type=float, default=25.0, help="segundos por par con qwen3:8b local (3 h 35 min / 516 pares)")
    p.add_argument("--usd-por-par-nube", type=float, default=0.00037, help="USD por par con Qwen3-32B en la nube (0,19 USD / 516 pares)")
    p.add_argument("--seg-por-par-nube", type=float, default=3.3)
    p.add_argument("--umbral-marginal", type=float, default=0.5, help="trampas por cada 100 pares extra, durante 3 pasos seguidos")
    p.add_argument("--salida", default=dr.DIR_DIAGNOSTICOS)
    a = p.parse_args(argv)
    rutas = dict(x.split("=", 1) for x in a.oferta)
    validar_ofertas(rutas, a.permitir_prueba)
    if not all(os.path.isfile(r) for r in rutas.values()):
        print("Los archivos de las ofertas tienen que existir.", file=sys.stderr)
        return 1
    fecha = datetime.date.today().isoformat()
    os.makedirs(a.salida, exist_ok=True)
    ruta_md = os.path.join(a.salida, f"curva_recuperacion_{fecha}.md")
    directorio_cache = os.path.join(a.salida, "emb_cache")
    ctx = _cargar_contexto(rutas)
    puntuar = PuntuadorReranker(os.path.join(directorio_cache, "reranker.json"))

    # calibración con bge-m3 (siempre, aunque se pidan solo otros modelos)
    nombres = list(dict.fromkeys(a.embedding or ["bge-m3"]))
    datos_bge, backend_bge, motivo = _datos_de_embedding("bge-m3", ctx, a, puntuar, directorio_cache)
    if datos_bge is None:
        print(f"No se pudo calibrar con bge-m3: {motivo}", file=sys.stderr)
        return 1
    cal = calibrar(datos_bge["secciones"], ctx["filas"])
    print(cal["mensaje"])
    if not cal["ok"]:
        with open(ruta_md, "w", encoding="utf-8") as f:
            f.write(informe_calibracion_fallida(cal, fecha, " ".join(argv if argv is not None else sys.argv[1:])))
        print(f"Informe: {ruta_md}", file=sys.stderr)
        return 2

    args = {"seg_por_par_local": a.seg_por_par_local, "usd_por_par_nube": a.usd_por_par_nube, "seg_por_par_nube": a.seg_por_par_nube, "umbral_marginal": a.umbral_marginal}
    resultados, salteados = {}, {}
    for nombre in nombres:
        datos, backend, motivo = (datos_bge, backend_bge, "") if nombre == "bge-m3" else _datos_de_embedding(nombre, ctx, a, puntuar, directorio_cache)
        if datos is None:
            print(f"Aviso: se saltea {nombre}: {motivo}", file=sys.stderr)
            salteados[nombre] = motivo
            continue
        r = resultados_de_embedding(nombre, backend.model_name, datos, ctx["filas"], len(ctx["fragmentos"]), args)
        r.update(meta=dict(backend.cache.meta), usd_corrida=datos["usd_corrida"])
        resultados[backend.model_name] = r
    if not resultados:
        print("Ningún embedding disponible.", file=sys.stderr)
        return 1
    filas = ctx["filas"]
    contexto = {"fecha": fecha, "ofertas": sorted(rutas), "n_trampas": sum(f["tipo"] == "trampa" for f in filas), "n_conformes": sum(f["tipo"] == "conforme" for f in filas),
                "sin_ubicar": sum(f["sec"] is None for f in filas), "con_prueba": bool(set(rutas) & set(OFERTAS_PRUEBA)), "n_fragmentos": len(ctx["fragmentos"]),
                "n_articulos": len({_clave(d) for d in ctx["fragmentos"]}), "n_normas": len({d.metadata.get("norma") for d in ctx["fragmentos"]})}
    guardar_csv(resultados, os.path.join(a.salida, f"curva_recuperacion_{fecha}.csv"))
    grafico_recall(resultados, os.path.join(a.salida, f"curva_recall_{fecha}.png"))
    grafico_recall_vs_pares(resultados, os.path.join(a.salida, f"curva_recall_vs_pares_{fecha}.png"))
    grafico_costo(resultados, os.path.join(a.salida, f"curva_costo_{fecha}.png"), a.seg_por_par_local, a.usd_por_par_nube)
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(informe_md(cal, resultados, salteados, contexto, args))
    print(f"Informe y gráficos en {a.salida} (curva_recuperacion_{fecha}.md/.csv, curva_recall_*, curva_costo_*).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
