# evaluacion/figura_embeddings.py
"""Figura de los embeddings (sin correr modelos): recall de trampas en modo solo denso contra los pares verificados (escala log) de todos los embeddings del CSV de la curva, en un
solo panel, con la configuración elegida marcada y el área bajo la curva (AUC) en la leyenda.

Uso:
  python -m evaluacion.figura_embeddings [--csv evaluacion/diagnosticos/curva_recuperacion_2026-11-14.csv] [--salida evaluacion/diagnosticos] [--embeddings bge-m3 ...]
Escribe figura_embeddings.png (300 dpi). La serie de cada embedding es la misma de figura_curva_final (solo denso, N=2, cupo 8, sin tope). AUC: la del informe de la curva
(scripts.curva_recuperacion.auc_log): promedio del recall sobre log10 de K, de 0 a 1; sirve para comparar embeddings porque todos usan la misma grilla de K."""
import argparse
import csv
import math
import os

import numpy as np

from . import figura_curva_final as F

AQUI = F.AQUI
DIAGNOSTICOS = F.DIAGNOSTICOS
CSV_CURVA = F.CSV_CURVA
COLORES = [F.AZUL, F.NARANJA, F.AQUA, F.AMARILLO, F.GRIS]
K_COMPARACION = 10          # el K del perfil elegido: se marca en cada serie para ver cuántos pares y trampas da cada embedding con el mismo K


def embeddings_del_csv(ruta: str) -> list:
    """Valores de la columna «embedding» en orden de aparición, con bge-m3 primero si está."""
    vistos = []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f, delimiter=";"):
            if fila["embedding"] not in vistos:
                vistos.append(fila["embedding"])
    return sorted(vistos, key=lambda e: e != "bge-m3")


def nombre_corto(embedding: str) -> str:
    """Nombre para la leyenda: «bge-m3» → BGE-M3; «deepinfra__Qwen-Qwen3-Embedding-8B» → Qwen3-Embedding-8B; «gemini__gemini-embedding-2-3072» → gemini-embedding-2-3072."""
    if embedding == "bge-m3":
        return "BGE-M3"
    return embedding.split("__", 1)[-1].replace("Qwen-Qwen3", "Qwen3")


def auc_log(serie: list) -> float:
    """Área bajo recall–K con K en escala log, normalizada a [0, 1]: la misma cuenta que scripts.curva_recuperacion.auc_log."""
    x = [math.log10(r["k"]) for r in serie]
    y = [r["recall"] for r in serie]
    if len(x) < 2 or x[-1] == x[0]:
        return y[0] if y else 0.0
    return sum((x[i + 1] - x[i]) * (y[i] + y[i + 1]) / 2 for i in range(len(x) - 1)) / (x[-1] - x[0])


def series(ruta_csv: str, embeddings: list = None) -> dict:
    """{embedding: serie solo denso} (F.leer_serie con el filtro de la serie graficada)."""
    return {e: F.leer_serie(ruta_csv, {**F.SERIE, "embedding": e}) for e in (embeddings or embeddings_del_csv(ruta_csv))}


def figura(por_embedding: dict, ruta_png: str) -> dict:
    """Un panel: recall contra pares (log) de cada embedding, con AUC en la leyenda, el K=10 de cada serie y la configuración elegida (de BGE-M3). Devuelve {embedding: auc}."""
    plt = F._plt()
    from matplotlib.ticker import FuncFormatter, NullLocator
    fig, eje = plt.subplots(figsize=(12, 7.6))
    fig.subplots_adjust(left=0.08, right=0.98, top=0.9, bottom=0.2)
    aucs, pares_todos = {}, []
    for i, (e, serie) in enumerate(por_embedding.items()):
        color = COLORES[i % len(COLORES)]
        aucs[e] = auc_log(serie)
        pares = [r["pares"] for r in serie]
        pares_todos += pares
        eje.plot(pares, [r["recall"] for r in serie], color=color, marker="o", markersize=4, linewidth=2, zorder=3, label=f"{nombre_corto(e)} (AUC = {F._n(aucs[e], 3)})")
        en_k = next((r for r in serie if r["k"] == K_COMPARACION), None)
        if en_k:
            eje.scatter([en_k["pares"]], [en_k["recall"]], s=130, facecolor="white", edgecolor=color, linewidth=2.2, zorder=5)
    eje.scatter([], [], s=130, facecolor="white", edgecolor=F.TINTA, linewidth=2.2, label=f"K = {K_COMPARACION} en cada serie")
    if "bge-m3" in por_embedding:
        e = F.ELEGIDA
        eje.scatter([e["pares"]], [e["aciertos"] / e["total"]], marker="*", s=520, color=F.MAGENTA, edgecolor="white", linewidth=1.2, zorder=6,
                    label=f"Configuración elegida (BGE-M3): {e['aciertos']}/{e['total']} con {e['pares']} pares (K=10, cupo 15, tope 39)")
    eje.set_xscale("log")
    eje.set_xlim(min(pares_todos) * 0.85, max(pares_todos) * 1.25)
    minimo = min(r["recall"] for s in por_embedding.values() for r in s)
    eje.set_ylim(max(0.0, math.floor(minimo * 10) / 10 - 0.05), 1.03)
    eje.set_xticks([t for t in (200, 300, 500, 1000, 2000, 3000, 5000, 10000) if eje.get_xlim()[0] <= t <= eje.get_xlim()[1]])
    eje.xaxis.set_major_formatter(FuncFormatter(lambda v, _: F._n(v, 0)))
    eje.xaxis.set_minor_locator(NullLocator())
    eje.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    eje.set_xlabel("Pares verificados (escala log)")
    eje.set_ylabel(f"Recall de trampas (P1+P2, {next(iter(por_embedding.values()))[0]['n']} trampas)")
    eje.set_title("Recall de trampas contra pares verificados, por embedding (solo denso)", loc="left")
    eje.grid(color="#e8e8e8", which="both", linewidth=0.7)
    eje.set_axisbelow(True)
    eje.legend(loc="lower right", frameon=True, framealpha=0.95, fontsize=10.5)
    fig.text(0.08, 0.03, "AUC: área bajo la curva recall–K con K en escala log, de 0 a 1 (la del informe de la curva).\n"
                         "Cada punto es un K de 1 a 410; mismas ofertas, mismas oraciones (N=2, cupo 8) y sin tope.", fontsize=10, color="#555555", linespacing=1.5)
    fig.savefig(ruta_png, dpi=300)
    plt.close(fig)
    return aucs


def generar(ruta_csv: str, salida: str, embeddings: list = None) -> dict:
    por_embedding = series(ruta_csv, embeddings)
    os.makedirs(salida, exist_ok=True)
    ruta_png = os.path.join(salida, "figura_embeddings.png")
    aucs = figura(por_embedding, ruta_png)
    return {"png": ruta_png, "auc": aucs, "series": por_embedding}


def main(argv=None):
    p = argparse.ArgumentParser(description="Recall solo denso contra pares de todos los embeddings en un panel (sin correr modelos)")
    p.add_argument("--csv", default=CSV_CURVA)
    p.add_argument("--salida", default=DIAGNOSTICOS)
    p.add_argument("--embeddings", nargs="+", default=None, help="valores de la columna «embedding» a graficar (por defecto todos los del CSV)")
    a = p.parse_args(argv)
    r = generar(a.csv, a.salida, a.embeddings)
    for e, auc in r["auc"].items():
        print(f"{nombre_corto(e)}: AUC {F._n(auc, 3)}")
    print(f"Guardado: {r['png']}")
    return r


if __name__ == "__main__":
    main()
