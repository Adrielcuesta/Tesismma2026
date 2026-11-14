# evaluacion/figura_curva_final.py
"""Figura final de la curva de recuperación (sin correr modelos): recall de trampas de BGE-M3 solo denso contra pares verificados, con USD y horas en ejes secundarios, el ajuste
recall(p) = 1 − a·p^(−b), la banda de Wilson, los K de referencia, la configuración elegida y su validación, y la ganancia marginal por K.

Uso:
  python -m evaluacion.figura_curva_final [--csv evaluacion/diagnosticos/curva_recuperacion_2026-11-14.csv] [--tabla evaluacion/resultados_reeval/tabla_comparativa.csv]
                                          [--usd-por-par X] [--seg-por-par X] [--salida evaluacion/diagnosticos]
Escribe figura_curva_final.png (300 dpi) y figura_curva_final.md. Los factores de costo salen de la tabla comparativa de la reevaluación (gpt-oss elegida para USD por par, 8B local para
segundos por par: costo o tiempo total del conjunto más amplio dividido por sus pares); si no hay costo, tiempo y pares, se usan USD_POR_PAR_DEFECTO y SEG_POR_PAR_DEFECTO. Los argumentos
--usd-por-par y --seg-por-par mandan sobre todo. El md dice de dónde salió cada factor."""
import argparse
import csv
import math
import os
import re

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
DIAGNOSTICOS = os.path.join(AQUI, "diagnosticos")
CSV_CURVA = os.path.join(DIAGNOSTICOS, "curva_recuperacion_2026-11-14.csv")
TABLA = os.path.join(AQUI, "resultados_reeval", "tabla_comparativa.csv")

# Serie graficada: BGE-M3, solo denso, ORACIONES_N=2, cupo 8, sin tope (la misma de curva_recuperacion_2026-11-14.md, "solo denso (sin reranker)")
SERIE = {"embedding": "bge-m3", "variante": "densa", "oraciones_n": "2", "oraciones_cupo": "8", "tope": "1000000"}
USD_POR_PAR_DEFECTO = 0.0005
SEG_POR_PAR_DEFECTO = 18.0
# Configuraciones de la tabla comparativa de las que salen los factores (la primera con datos completos gana)
CONFIG_USD = ("gpt-oss-120b esfuerzo bajo (elegida)",)
CONFIG_SEG = ("qwen3:8b local (elegida)", "qwen3:8b local")
CONFIG_VALIDACION = ("Qwen3-32B (elegida)", "gpt-oss-120b esfuerzo bajo (elegida)", "qwen3:8b local (elegida)")

# Configuración elegida: cargada en el commit 9e7a8ab («Perfil elegido cargado»): bge-m3 solo denso K=10 + oraciones N=2 cupo 15, tope 39.
# Sobre P1+P2 da 28/30 trampas y 721 pares verificados (evaluacion/diagnosticos/curva_recuperacion_2026-11-14.md y el commit); el cupo 15 y el tope 39 no están en la serie
# graficada (cupo 8), por eso es una constante y no una fila del CSV.
ELEGIDA = {"aciertos": 28, "total": 30, "pares": 721, "k": 10}
# Validación de la elegida sobre P3+P4 (conjunto de prueba, segunda evaluación): 26/30 trampas. Dato dado por el autor de la tesis tras la reevaluación; sus pares salen de la
# tabla comparativa si están, y si no se dibuja sobre los pares de la elegida en P1+P2.
VALIDACION = {"aciertos": 26, "total": 30}
# K de referencia (curva_recuperacion_2026-11-14.md): regla marginal (< 0,5 trampas por cada 100 pares durante 3 pasos), elegido y codo de Kneedle
K_REFERENCIA = {6: "regla marginal", 10: "elegido", 15: "codo (Kneedle)"}
UMBRAL_MARGINAL, PASOS_MARGINAL = 0.5, 3
PUESTO_ULTIMA_TRAMPA = 175          # P2-04-B está en el puesto 175 del ranking denso (dato del diagnóstico de la curva)
AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, GRIS, TINTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#9a9a95", "#222222"
PRIORIDAD_ETIQUETAS = (1, 2, 3, 5, 6, 10, 15, 25, 35, 50, 100, 200, 410)


# --- Datos ---

def leer_serie(ruta: str, filtro: dict = None) -> list:
    """Filas de la serie (por K, sin repetidos, ordenadas): [{k, pares, hits, n, recall, inf, sup}]."""
    filtro = filtro or SERIE
    con_k = {}
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f, delimiter=";"):
            if all(fila[c] == v for c, v in filtro.items()) and int(fila["k"]) not in con_k:
                con_k[int(fila["k"])] = {"k": int(fila["k"]), "pares": int(fila["pares"]), "hits": int(fila["hits_trampas"]), "n": int(fila["n_trampas"]),
                                         "recall": float(fila["recall_trampas"]), "inf": float(fila["ic_trampas_inf"]), "sup": float(fila["ic_trampas_sup"])}
    serie = [con_k[k] for k in sorted(con_k)]
    if not serie:
        raise SystemExit(f"No hay filas de la serie {filtro} en {ruta}")
    return serie


def ganancia_marginal(serie: list) -> list:
    """Trampas por cada 100 pares extra de cada paso (None en el primero y en los pasos que no suman pares)."""
    g = [None]
    for previa, r in zip(serie, serie[1:]):
        extra = r["pares"] - previa["pares"]
        g.append((r["hits"] - previa["hits"]) / (extra / 100) if extra > 0 else None)
    return g


def k_por_umbral(serie: list, umbral: float = UMBRAL_MARGINAL, pasos: int = PASOS_MARGINAL):
    """K del último punto antes de `pasos` pasos seguidos con ganancia marginal < umbral (la regla marginal de la curva); None si no ocurre."""
    g = [0.0 if x is None else x for x in ganancia_marginal(serie)]
    for j in range(1, len(serie) - pasos + 1):
        if all(g[j + i] < umbral for i in range(pasos)):
            return serie[j - 1]["k"]
    return None


def k_codo(serie: list):
    """K del codo (Kneedle): con pares y aciertos llevados a [0, 1], el punto que más se aleja de la diagonal."""
    x, y = np.array([r["pares"] for r in serie], float), np.array([r["hits"] for r in serie], float)
    if x.max() == x.min() or y.max() == y.min():
        return None
    d = (y - y.min()) / (y.max() - y.min()) - (x - x.min()) / (x.max() - x.min())
    return serie[int(np.argmax(d))]["k"] if d.max() > 0 else None


def primera_fila_con(serie: list, aciertos: int):
    """Primera fila de la serie con al menos `aciertos` trampas; None si nunca llega."""
    return next((r for r in serie if r["hits"] >= aciertos), None)


def pares_en_k(serie: list, k: int):
    """(pares, interpolado): pares verificados en K; si K no está en la serie, interpolación lineal entre sus vecinos (interpolado=True); None fuera del rango."""
    por_k = {r["k"]: r["pares"] for r in serie}
    if k in por_k:
        return por_k[k], False
    ks = sorted(por_k)
    if not ks or k < ks[0] or k > ks[-1]:
        return None
    abajo = max(x for x in ks if x < k)
    arriba = min(x for x in ks if x > k)
    return por_k[abajo] + (k - abajo) / (arriba - abajo) * (por_k[arriba] - por_k[abajo]), True


# --- Ajuste recall(p) = 1 − a·p^(−b) ---

def _a_optimo(p: np.ndarray, y: np.ndarray, b: float):
    """Para un b dado, el a que minimiza la suma de cuadrados de y − (1 − a·p^−b) (cerrado) y esa suma."""
    q = p ** (-b)
    a = float(np.sum((1 - y) * q) / np.sum(q * q))
    return a, float(np.sum((y - (1 - a * q)) ** 2))


def ajustar(pares, recall) -> dict:
    """Mínimos cuadrados de recall(p) = 1 − a·p^(−b) sobre todos los puntos: para cada b el a es cerrado, y b se busca en una grilla fina y se refina por sección áurea. Devuelve
    {a, b, r2, sse, n}; R² = 1 − SSE / SST sobre el recall."""
    p, y = np.asarray(pares, float), np.asarray(recall, float)
    grilla = np.linspace(0.01, 3.0, 600)
    sse = [_a_optimo(p, y, b)[1] for b in grilla]
    i = int(np.argmin(sse))
    lo, hi = grilla[max(i - 1, 0)], grilla[min(i + 1, len(grilla) - 1)]
    fi = (math.sqrt(5) - 1) / 2
    for _ in range(80):
        c, d = hi - fi * (hi - lo), lo + fi * (hi - lo)
        if _a_optimo(p, y, c)[1] < _a_optimo(p, y, d)[1]:
            hi = d
        else:
            lo = c
    b = (lo + hi) / 2
    a, s = _a_optimo(p, y, b)
    sst = float(np.sum((y - y.mean()) ** 2))
    return {"a": a, "b": b, "r2": 1 - s / sst if sst else float("nan"), "sse": s, "n": len(p)}


def recall_ajustado(ajuste: dict, pares):
    return 1 - ajuste["a"] * np.asarray(pares, float) ** (-ajuste["b"])


def pares_para_recall(ajuste: dict, recall: float):
    """Pares que da el ajuste para alcanzar `recall` (None si recall >= 1: el modelo nunca llega a 100 %)."""
    return (ajuste["a"] / (1 - recall)) ** (1 / ajuste["b"]) if recall < 1 else None


# --- Factores de costo ---

def _filas_tabla(ruta: str) -> list:
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _valor(texto):
    try:
        return float(texto)
    except (TypeError, ValueError):
        return None


def factor_por_par(filas: list, configuraciones: tuple, campo: str):
    """(valor, origen) con `campo` (costo_usd o tiempo_s) dividido por los pares totales del conjunto más amplio de la primera configuración con campo y pares positivos; None si ninguna."""
    for nombre in configuraciones:
        candidatas = []
        for f in filas:
            total, pares = _valor(f.get(campo)), _valor(f.get("pares_por_oferta"))
            if f["configuracion"] == nombre and total and pares:
                n = len((f.get("ofertas") or "").split("+")) or 1
                candidatas.append((n, total, pares * n, f["conjunto"], f.get("ofertas")))
        if candidatas:
            n, total, pares, conjunto, ofertas = max(candidatas)
            return total / pares, f"«{nombre}», conjunto «{conjunto}» ({ofertas}): {campo} {_n(total, 4 if campo == 'costo_usd' else 0)} / {_n(pares)} pares"
    return None


def pares_de_validacion(filas: list, configuraciones: tuple = CONFIG_VALIDACION):
    """Pares totales de la elegida en P3+P4 según la tabla (pares por oferta × 2); None si la tabla no los trae."""
    for nombre in configuraciones:
        for f in filas:
            pares = _valor(f.get("pares_por_oferta"))
            if f["configuracion"] == nombre and (f.get("ofertas") or "") == "P3+P4" and pares:
                return pares * 2, f"«{nombre}», conjunto «{f['conjunto']}»: {pares:,.0f} pares por oferta × 2"
    return None


def factores(ruta_tabla: str, usd_arg=None, seg_arg=None) -> dict:
    """{'usd': (valor, origen), 'seg': (valor, origen), 'pares_validacion': (pares, origen) | None}. Prioridad: argumento, tabla, valor por defecto."""
    filas = _filas_tabla(ruta_tabla) if ruta_tabla and os.path.isfile(ruta_tabla) else []
    usd = (usd_arg, "argumento --usd-por-par") if usd_arg is not None else (factor_por_par(filas, CONFIG_USD, "costo_usd")
                                                                           or (USD_POR_PAR_DEFECTO, "valor por defecto (la tabla no tiene costo y pares de gpt-oss elegida)"))
    seg = (seg_arg, "argumento --seg-por-par") if seg_arg is not None else (factor_por_par(filas, CONFIG_SEG, "tiempo_s")
                                                                           or (SEG_POR_PAR_DEFECTO, "valor por defecto (la tabla no tiene tiempo y pares del 8B local)"))
    return {"usd": usd, "seg": seg, "pares_validacion": pares_de_validacion(filas)}


def _n(v, d: int = 0) -> str:
    """Número con formato español: punto de miles y coma decimal."""
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _miles(v) -> str:
    return _n(v, 0)


def _pc(v: float) -> str:
    return f"{v:.0%}"


# --- Cuenta del tribunal ---

def cola(serie: list, ajuste: dict, puesto=PUESTO_ULTIMA_TRAMPA) -> dict:
    """Pares para las primeras 28 trampas, la 29 y la 30 con la serie sin tope. Los valores medidos son los de la primera fila de la serie que llega (cota superior del K real);
    para la 30 también se interpola al puesto exacto de la última trampa (`puesto`; None si no se conoce: solo vale para BGE-M3). Si la serie no llega, se extrapola con el ajuste
    y se marca."""
    n = serie[-1]["n"]
    salida = {"n": n, "puesto": puesto}
    for clave, aciertos in (("p28", n - 2), ("p29", n - 1), ("p30", n)):
        fila = primera_fila_con(serie, aciertos)
        if fila:
            salida[clave] = {"aciertos": aciertos, "pares": fila["pares"], "k": fila["k"], "extrapolado": False}
        else:
            extra = pares_para_recall(ajuste, (aciertos - 0.5) / n)       # el ajuste no llega a 100 %: se toma el punto medio entre aciertos−1 y aciertos
            # la serie nunca llegó: no puede costar menos que su último punto
            salida[clave] = {"aciertos": aciertos, "pares": max(extra, serie[-1]["pares"]), "k": None, "extrapolado": True}
    exacto = pares_en_k(serie, puesto) if puesto else None
    salida["p30_puesto"] = {"pares": exacto[0], "interpolado": exacto[1]} if exacto else None
    salida["razon"] = salida["p30"]["pares"] / salida["p28"]["pares"]
    salida["razon_puesto"] = salida["p30_puesto"]["pares"] / salida["p28"]["pares"] if salida["p30_puesto"] else None
    salida["incremental"] = (salida["p30"]["pares"] - salida["p28"]["pares"]) / salida["p28"]["pares"]
    return salida


def frase_tribunal(c: dict, nombre: str = "BGE-M3") -> str:
    n = c["n"]
    miles = _miles
    marca = lambda d: " (extrapolado con el ajuste)" if d["extrapolado"] else ""
    puesto = (f" (≈{miles(c['p30_puesto']['pares'])} si se corta exactamente en el puesto {c['puesto']} de su ranking{', interpolado' if c['p30_puesto']['interpolado'] else ''})"
              if c["p30_puesto"] else "")
    return (f"Con {nombre} en modo solo denso, las primeras {n - 2} de {n} trampas se recuperan verificando {miles(c['p28']['pares'])} pares{marca(c['p28'])}; la trampa {n - 1} exige "
            f"{miles(c['p29']['pares'])} pares{marca(c['p29'])} y la última, {miles(c['p30']['pares'])} pares{marca(c['p30'])}{puesto}: {_n(c['razon'], 1)} veces los pares de las primeras {n - 2}, "
            f"para sumar {_n(100 / n, 1)} puntos de recall. Por eso la configuración elegida se detiene antes de esa cola de costo creciente.")


# --- Figura ---

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white", "font.size": 13, "axes.titlesize": 15, "axes.labelsize": 13,
                         "legend.fontsize": 11, "axes.edgecolor": "#888888", "text.color": TINTA, "axes.labelcolor": TINTA, "xtick.color": TINTA, "ytick.color": TINTA,
                         "axes.spines.top": False, "axes.spines.right": False})
    return plt


OFFSETS = [(0, 9), (0, -17), (-14, 9), (14, -17), (14, 9), (-14, -17), (0, 22), (0, -30), (-20, 20), (20, -30)]


def etiquetar_puntos(fig, eje, puntos: list, prioridad: tuple = PRIORIDAD_ETIQUETAS, fontsize: int = 8.5) -> int:
    """Rotula cada punto (x, y, texto, k) con su K sin pisar otro texto ni los ya puestos: primero los K de `prioridad`, después el resto por orden. El que no encuentra lugar libre
    queda sin rótulo (se lista en el md). Devuelve cuántos quedaron rotulados."""
    renderer = fig.canvas.get_renderer()
    cajas, puestos = [], 0
    orden = sorted(puntos, key=lambda p: (p[3] not in prioridad, prioridad.index(p[3]) if p[3] in prioridad else p[3]))
    for x, y, texto, _ in orden:
        for dx, dy in OFFSETS:
            nota = eje.annotate(texto, (x, y), textcoords="offset points", xytext=(dx, dy), fontsize=fontsize, ha="center", color="#333333")
            caja = nota.get_window_extent(renderer)
            if not any(caja.overlaps(o) for o in cajas):
                cajas.append(caja)
                puestos += 1
                break
            nota.remove()
    return puestos


def figura(serie: list, ajuste: dict, fact: dict, ruta_png: str, ks_ref: dict = None, pares_validacion=None, embedding: str = "bge-m3") -> dict:
    """Dos paneles: A) recall contra pares (log) con USD y horas en ejes secundarios; B) ganancia marginal contra K. La configuración elegida y su validación son de BGE-M3 y solo se
    dibujan con ese embedding. Devuelve {'rotulados': n, 'total': puntos}."""
    plt = _plt()
    ks_ref = K_REFERENCIA if ks_ref is None else ks_ref
    usd, seg = fact["usd"][0], fact["seg"][0]
    pares, recall = np.array([r["pares"] for r in serie], float), np.array([r["recall"] for r in serie])
    from matplotlib.ticker import FuncFormatter, NullLocator
    fig, (eje, marg) = plt.subplots(1, 2, figsize=(21, 10.5), gridspec_kw={"width_ratios": [1.45, 1]})
    fig.subplots_adjust(left=0.05, right=0.99, top=0.84, bottom=0.25, wspace=0.14)      # a mano: tight_layout aplasta los paneles con el segundo eje inferior
    plano = FuncFormatter(lambda v, _: _n(v, 0 if v >= 10 else (1 if v >= 1 else 2)))
    # Panel A
    eje.fill_between(pares, [r["inf"] for r in serie], [r["sup"] for r in serie], color=AZUL, alpha=0.13, linewidth=0, label="Banda de Wilson 95 %")
    eje.plot(pares, recall, color=AZUL, marker="o", markersize=4.5, linewidth=1.8, label=f"{nombre_embedding(embedding)} solo denso (P1+P2)", zorder=3)
    grilla = np.geomspace(pares.min(), pares.max(), 300)
    eje.plot(grilla, recall_ajustado(ajuste, grilla), color=NARANJA, linestyle="--", linewidth=1.8, zorder=2,
             label=f"Ajuste 1 − a·p^(−b): a = {ajuste['a']:.2f}, b = {ajuste['b']:.3f}, R² = {ajuste['r2']:.3f}")
    por_k = {r["k"]: r for r in serie}
    for k, nombre in ks_ref.items():
        if k in por_k:
            x = por_k[k]["pares"]
            eje.axvline(x, color=GRIS, linestyle=":", linewidth=1.4, zorder=1)
            eje.text(x, 0.02, f" K={k} · {nombre} ", rotation=90, ha="right", va="bottom", fontsize=10.5, color="#555555", transform=eje.get_xaxis_transform(),
                     bbox={"fc": "white", "ec": "none", "alpha": 0.8, "pad": 1})
    if embedding == "bge-m3":
        eleg = ELEGIDA
        eje.scatter([eleg["pares"]], [eleg["aciertos"] / eleg["total"]], marker="*", s=420, color=MAGENTA, edgecolor="white", linewidth=1.2, zorder=6,
                    label=f"Elegida: {eleg['aciertos']}/{eleg['total']} con {eleg['pares']} pares (K=10, cupo 15, tope 39)")
        x_val = pares_validacion or eleg["pares"]
        eje.scatter([x_val], [VALIDACION["aciertos"] / VALIDACION["total"]], marker="D", s=170, color=AQUA, edgecolor="white", linewidth=1.2, zorder=6,
                    label=f"Validación P3+P4: {VALIDACION['aciertos']}/{VALIDACION['total']}" + ("" if pares_validacion else " (sobre los pares de P1+P2)"))
    eje.set_xscale("log")
    eje.set_xlabel("Pares verificados (escala log)")
    eje.set_ylabel("Recall de trampas")
    eje.set_ylim(0.5, 1.03)
    eje.set_xlim(pares.min() * 0.85, pares.max() * 1.25)
    eje.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    eje.grid(color="#e8e8e8", which="both", linewidth=0.7)
    eje.set_axisbelow(True)
    eje.set_title("A. Recall de trampas contra pares verificados", loc="left")
    eje.set_xticks([t for t in (200, 300, 500, 1000, 2000, 3000, 5000, 10000) if eje.get_xlim()[0] <= t <= eje.get_xlim()[1]])
    eje.xaxis.set_major_formatter(FuncFormatter(lambda v, _: _n(v, 0)))
    eje.xaxis.set_minor_locator(NullLocator())
    arriba = eje.secondary_xaxis("top", functions=(lambda p: p * usd, lambda u: u / usd))
    arriba.set_xlabel(f"Costo en la nube (USD) = pares × {_n(usd, 5)}")
    arriba.set_xticks([t for t in (0.1, 0.2, 0.3, 0.5, 1, 2, 3, 5, 10) if eje.get_xlim()[0] * usd <= t <= eje.get_xlim()[1] * usd])
    arriba.xaxis.set_major_formatter(plano)
    arriba.xaxis.set_minor_locator(NullLocator())
    abajo = eje.secondary_xaxis(-0.14, functions=(lambda p: p * seg / 3600, lambda h: h * 3600 / seg))
    abajo.set_xlabel(f"Tiempo en local (horas) = pares × {_n(seg, 1)} s / 3600")
    abajo.set_xticks([t for t in (1, 2, 3, 5, 10, 20, 40, 80) if eje.get_xlim()[0] * seg / 3600 <= t <= eje.get_xlim()[1] * seg / 3600])
    abajo.xaxis.set_major_formatter(plano)
    abajo.xaxis.set_minor_locator(NullLocator())
    abajo.spines["bottom"].set_visible(True)
    eje.legend(loc="lower right", frameon=True, framealpha=0.95, fontsize=10.5)
    fig.canvas.draw()
    puntos = [(r["pares"], r["recall"], f"{r['k']}", r["k"]) for r in serie]
    rotulados = etiquetar_puntos(fig, eje, puntos)
    # Panel B
    g = ganancia_marginal(serie)
    xs = [r["k"] for r, v in zip(serie, g) if v is not None]
    ys = [v for v in g if v is not None]
    marg.plot(xs, ys, color=AZUL, marker="o", markersize=4.5, linewidth=1.6, zorder=3, label="Ganancia marginal por paso")
    marg.axhline(UMBRAL_MARGINAL, color=NARANJA, linestyle="--", linewidth=1.6, label=f"Umbral: {_n(UMBRAL_MARGINAL, 1)} trampas por cada 100 pares extra")
    for k, nombre in ks_ref.items():
        marg.axvline(k, color=GRIS, linestyle=":", linewidth=1.4, zorder=1)
        marg.text(k, 0.98, f" K={k} · {nombre} ", rotation=90, ha="right", va="top", fontsize=10.5, color="#555555", transform=marg.get_xaxis_transform(),
                  bbox={"fc": "white", "ec": "none", "alpha": 0.8, "pad": 1})
    marg.set_xscale("log")
    marg.set_xticks([t for t in (2, 3, 5, 6, 10, 15, 25, 50, 100, 200, 400)])
    marg.xaxis.set_major_formatter(FuncFormatter(lambda v, _: _n(v, 0)))
    marg.xaxis.set_minor_locator(NullLocator())
    marg.set_xlabel("K (escala log)")
    marg.set_ylabel("Trampas por cada 100 pares extra")
    marg.set_ylim(0, max(ys) * 1.08)
    marg.grid(color="#e8e8e8", which="both", linewidth=0.7)
    marg.set_axisbelow(True)
    marg.set_title("B. Ganancia marginal por K", loc="left")
    marg.legend(loc="upper right", frameon=True, framealpha=0.95, fontsize=10.5)
    fig.savefig(ruta_png, dpi=300)
    plt.close(fig)
    return {"rotulados": rotulados, "total": len(serie)}


# --- Informe ---

def nombre_embedding(embedding: str) -> str:
    """Nombre legible del embedding de la columna «embedding» del CSV («bge-m3» → BGE-M3; «gemini__gemini-embedding-2-3072» queda tal cual)."""
    return "BGE-M3" if embedding == "bge-m3" else embedding


def ks_de_referencia(serie: list, embedding: str) -> dict:
    """K de referencia de la figura. Con BGE-M3, los de curva_recuperacion_2026-11-14.md (regla marginal, elegido y codo); con otro embedding, los que da su propia serie
    (regla marginal y codo): el K «elegido» es de BGE-M3."""
    if embedding == "bge-m3":
        return dict(K_REFERENCIA)
    propios = {}
    for k, nombre in ((k_por_umbral(serie), "regla marginal"), (k_codo(serie), "codo (Kneedle)")):
        if k:
            propios[k] = f"{propios[k]} = {nombre}" if k in propios else nombre
    return propios


def informe_md(serie: list, ajuste: dict, fact: dict, c: dict, ks: dict, ruta_csv: str, figura_info: dict, ks_ref: dict = None, embedding: str = "bge-m3", nombre_png: str = "figura_curva_final.png") -> str:
    ks_ref = ks_de_referencia(serie, embedding) if ks_ref is None else ks_ref
    bge = embedding == "bge-m3"
    usd, seg = fact["usd"][0], fact["seg"][0]
    por_k = {r["k"]: r for r in serie}
    fila = lambda nombre, k, p, h, n, inf, sup: (f"| {nombre} | {k} | {_miles(p)} | {h}/{n} ({_pc(h / n)}; {_pc(inf)}–{_pc(sup)}) | {_n(p * usd, 2)} | {_n(p * seg / 3600, 1)} |")
    L = ["# Figura final de la curva de recuperación" + ("" if bge else f" ({nombre_embedding(embedding)})"), "",
         f"- Datos: `{os.path.relpath(ruta_csv, os.path.dirname(AQUI))}` ({nombre_embedding(embedding)}, solo denso, N=2, cupo 8, sin tope; {len(serie)} puntos, K de {serie[0]['k']} a {serie[-1]['k']}; "
         f"{serie[0]['n']} trampas de P1+P2).",
         f"- Figura: `{nombre_png}` (300 dpi). Panel A: recall contra pares verificados (log) con USD y horas en ejes secundarios; panel B: ganancia marginal contra K.",
         *([] if bge else ["- La configuración elegida (28/30, 721 pares) y su validación en P3+P4 son de BGE-M3: no se dibujan con otro embedding, que no tiene perfil elegido."]),
         f"- Rótulos con el K de cada punto: {figura_info['rotulados']} de {figura_info['total']} (los que no entran sin pisar otro texto quedan sin rótulo; todos los puntos están en el CSV de origen).", "",
         "## Factores de costo", "", "| Factor | Valor | Origen |", "|---|---|---|",
         f"| USD por par | {_n(usd, 5)} | {fact['usd'][1]} |", f"| Segundos por par | {_n(seg, 1)} | {fact['seg'][1]} |", "",
         "## Ajuste recall(p) = 1 − a·p^(−b)", "", f"Mínimos cuadrados sobre los {ajuste['n']} puntos de la serie: **a = {_n(ajuste['a'], 4)}**, **b = {_n(ajuste['b'], 4)}**, **R² = {_n(ajuste['r2'], 4)}** (sobre el recall). "
         f"La banda del gráfico es el intervalo de Wilson al 95 % de cada punto (n = {serie[0]['n']}).", "",
         "## Puntos de referencia", "", "| Punto | K | Pares | Recall (Wilson 95 %) | USD (nube) | Horas (local) |", "|---|---|---|---|---|---|"]
    for k, nombre in ks_ref.items():
        if k in por_k:
            r = por_k[k]
            L.append(fila(nombre, k, r["pares"], r["hits"], r["n"], r["inf"], r["sup"]))
    pv = fact["pares_validacion"]
    if bge:
        from_wilson = _wilson(ELEGIDA["aciertos"], ELEGIDA["total"])
        L.append(fila("**configuración elegida** (constante)", "10 (cupo 15, tope 39)", ELEGIDA["pares"], ELEGIDA["aciertos"], ELEGIDA["total"], *from_wilson))
        v = _wilson(VALIDACION["aciertos"], VALIDACION["total"])
        L.append(f"| validación de la elegida en P3+P4 (constante) | — | {_miles(pv[0])} | {VALIDACION['aciertos']}/{VALIDACION['total']} ({_pc(VALIDACION['aciertos'] / VALIDACION['total'])}; {_pc(v[0])}–{_pc(v[1])}) | "
                 f"{_n(pv[0] * usd, 2)} | {_n(pv[0] * seg / 3600, 1)} |" if pv else f"| validación de la elegida en P3+P4 (constante) | — | n/d | {VALIDACION['aciertos']}/{VALIDACION['total']} ({_pc(v[0])}–{_pc(v[1])}) | n/d | n/d |")
        L += ["", "Origen de las constantes: la elegida (28/30, 721 pares, K=10, cupo 15, tope 39) es la del commit 9e7a8ab y del informe de la curva; el 26/30 en P3+P4 es la validación de la elegida"
              + (f" y dibuja en {_miles(pv[0])} pares ({pv[1]})." if pv else " (sin pares en la tabla comparativa: se dibuja sobre los pares de P1+P2)."), "",
              "## Verificación de los K de referencia", "", f"- Regla marginal calculada aquí: K = {ks['umbral']} (esperado {min(ks_ref, key=lambda k: k)}).", f"- Codo de Kneedle calculado aquí: K = {ks['codo']} (esperado {max(ks_ref)}).", ""]
    else:
        L += ["", f"Los K de referencia son los que da la propia serie de {nombre_embedding(embedding)}: regla marginal K = {ks['umbral']}, codo de Kneedle K = {ks['codo']}.", ""]
    p28, p29, p30 = c["p28"], c["p29"], c["p30"]
    marca = lambda d: " (extrapolado con el ajuste)" if d["extrapolado"] else ""
    L += ["## La cola de la curva: pares para las últimas trampas (solo denso, sin tope)", "", "| Trampas | K (primer K medido) | Pares | Costo USD | Horas |", "|---|---|---|---|---|"]
    for d in (p28, p29, p30):
        L.append(f"| {d['aciertos']}/{c['n']}{marca(d)} | {d['k'] if d['k'] else '—'} | {_miles(d['pares'])} | {_n(d['pares'] * usd, 2)} | {_n(d['pares'] * seg / 3600, 1)} |")
    if c["p30_puesto"]:
        L.append(f"| {c['n']}/{c['n']} en el puesto exacto {c['puesto']} ({'interpolado' if c['p30_puesto']['interpolado'] else 'medido'}) | {c['puesto']} | {_miles(c['p30_puesto']['pares'])} | "
                 f"{_n(c['p30_puesto']['pares'] * usd, 2)} | {_n(c['p30_puesto']['pares'] * seg / 3600, 1)} |")
    L += ["", f"- Razón pares para la última trampa ÷ pares para las primeras {c['n'] - 2}: **{_n(c['razon'], 2)}** (con el primer K medido que llega a {c['n']}/{c['n']}"
          + (f"; {_n(c['razon_puesto'], 2)} con el puesto exacto {c['puesto']} interpolado" if c["razon_puesto"] else "") + ").",
          f"- Los pares que hay que agregar para pasar de {c['n'] - 2} a {c['n']} trampas son {_n(c['incremental'], 2)} veces los pares de las primeras {c['n'] - 2}.",
          "- Los valores «medidos» son los de la primera fila de la serie que llega al número de trampas: como la serie salta de K=150 a K=200, son una cota superior de los pares exactos."]
    p_aj = pares_para_recall(ajuste, (c["n"] - 0.5) / c["n"])
    L += [f"- Control con el ajuste: llegar a {_n((c['n'] - 0.5) / c['n'] * 100, 1)} % de recall (punto medio entre {c['n'] - 1}/{c['n']} y {c['n']}/{c['n']}) cuesta ≈{_miles(p_aj)} pares; el ajuste no alcanza 100 % nunca.", "",
          "## Frase para el tribunal", "", f"> {frase_tribunal(c, nombre_embedding(embedding))}", ""]
    return "\n".join(L)


def _wilson(k: int, n: int, z: float = 1.96) -> tuple:
    p = k / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centro - margen), min(1.0, centro + margen)


def sufijo_de(embedding: str) -> str:
    """Sufijo de los archivos de salida: ninguno con BGE-M3; con otro embedding, su nombre corto («gemini__gemini-embedding-2-3072» → «_gemini»)."""
    return "" if embedding == "bge-m3" else "_" + re.sub(r"[^a-z0-9]+", "-", embedding.split("__")[0].lower()).strip("-")


def generar(ruta_csv: str, ruta_tabla: str, salida: str, usd_arg=None, seg_arg=None, embedding: str = "bge-m3", sufijo: str = None) -> dict:
    serie = leer_serie(ruta_csv, {**SERIE, "embedding": embedding})
    ajuste = ajustar([r["pares"] for r in serie], [r["recall"] for r in serie])
    fact = factores(ruta_tabla, usd_arg, seg_arg)
    c = cola(serie, ajuste, PUESTO_ULTIMA_TRAMPA if embedding == "bge-m3" else None)      # el puesto 175 de P2-04-B es del ranking de BGE-M3
    ks = {"umbral": k_por_umbral(serie), "codo": k_codo(serie)}
    os.makedirs(salida, exist_ok=True)
    sufijo = sufijo_de(embedding) if sufijo is None else sufijo
    nombre = f"figura_curva_final{sufijo}"
    ruta_png, ruta_md = os.path.join(salida, nombre + ".png"), os.path.join(salida, nombre + ".md")
    info = figura(serie, ajuste, fact, ruta_png, ks_de_referencia(serie, embedding), fact["pares_validacion"][0] if fact["pares_validacion"] else None, embedding)
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(informe_md(serie, ajuste, fact, c, ks, ruta_csv, info, None, embedding, nombre + ".png") + "\n")
    return {"serie": serie, "ajuste": ajuste, "factores": fact, "cola": c, "ks": ks, "png": ruta_png, "md": ruta_md, "figura": info}


def main(argv=None):
    p = argparse.ArgumentParser(description="Figura final de la curva de recuperación (sin correr modelos)")
    p.add_argument("--csv", default=CSV_CURVA)
    p.add_argument("--tabla", default=TABLA, help="tabla comparativa de la reevaluación, de donde salen los factores de costo")
    p.add_argument("--usd-por-par", type=float, default=None, help=f"USD por par (por defecto de la tabla; si no, {USD_POR_PAR_DEFECTO})")
    p.add_argument("--seg-por-par", type=float, default=None, help=f"segundos por par en local (por defecto de la tabla; si no, {SEG_POR_PAR_DEFECTO})")
    p.add_argument("--salida", default=DIAGNOSTICOS)
    p.add_argument("--embedding", default="bge-m3", help="valor de la columna «embedding» del CSV (bge-m3; con Gemini, gemini__gemini-embedding-2-3072)")
    p.add_argument("--sufijo", default=None, help="sufijo de los archivos de salida (por defecto ninguno con bge-m3 y «_gemini» con Gemini)")
    a = p.parse_args(argv)
    r = generar(a.csv, a.tabla, a.salida, a.usd_por_par, a.seg_por_par, a.embedding, a.sufijo)
    print(f"Guardado: {r['png']}\nGuardado: {r['md']}")
    return r


if __name__ == "__main__":
    main()
