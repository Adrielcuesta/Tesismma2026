# evaluacion/tabla_comparativa.py
"""Tabla comparativa final y gráficos. Recalcula todo a partir de los JSON de cada configuración y oferta (con evaluar.py); no lee resultados ya calculados.
Si junto a un JSON están <json>_extras.csv / <json>_juez.csv, se usan para la precisión humana y la del juez.

Uso:
  python -m evaluacion.tabla_comparativa --config evaluacion/config_tabla_ejemplo.json [--salida evaluacion/resultados_finales]
Configuración (JSON): {"configuraciones": {"<nombre>": {"P1": "<ruta json>", "P2": "..."}, ...},
                       "conjuntos": {"<nombre>": ["P1", "P2"], ...}}      # «conjuntos» es opcional (por defecto desarrollo, prueba y total)
Los conjuntos o las ofertas sin JSON (ruta vacía o inexistente) se omiten con un aviso. Rutas relativas a la carpeta desde la que se corre.
En lugar de una ruta, una oferta puede ser {"auto": {"carpeta": "<carpeta>", "condicion": "<condicion>"}} (el JSON local más reciente con esa condición) o
{"auto": {"carpeta": "<carpeta>", "sufijo": "<sufijo>"}} (el más reciente que termina en _<sufijo>.json). Otras claves de nivel superior (p. ej. «sin_rag») se ignoran."""
import argparse
import csv
import json
import os
import sys

from scripts import elegir_json

from . import evaluar as E

AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, "resultados_finales")
CONJUNTOS = {"P1–P2 desarrollo": ["P1", "P2"], "P3–P4 prueba": ["P3", "P4"], "P1–P4 total": ["P1", "P2", "P3", "P4"]}
CONFIG_VACIA = "No hay configuraciones en {}"
AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, GRIS, TINTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#9a9a95", "#222222"
COLORES_PERDIDA = {"encontrada": AZUL, "perdida en clasificación": AMARILLO, "perdida en verificación": NARANJA, "no recuperada": GRIS, "otra causa": MAGENTA}


def cargar_config(ruta: str) -> dict:
    with open(ruta, encoding="utf-8") as f:
        cfg = json.load(f)
    if not cfg.get("configuraciones"):
        raise SystemExit(CONFIG_VACIA.format(ruta))
    cfg.setdefault("conjuntos", CONJUNTOS)
    return cfg


def resolver_ruta(valor, etiqueta: str = "") -> str:
    """Ruta del JSON de una oferta. «valor» es la ruta (cadena) o {"auto": {"carpeta": ..., "condicion": ...}} (el JSON más reciente de la carpeta con esa
    configuracion_analisis.condicion, sin deepinfra, reclasificado ni parcial; scripts.elegir_json) o {"auto": {"carpeta": ..., "sufijo": ...}}
    (el más reciente *_<sufijo>.json). Devuelve "" si no hay ninguno (con aviso)."""
    if not isinstance(valor, dict) or "auto" not in valor:
        return valor or ""
    a = valor["auto"]
    if "condicion" in a:
        elegido = elegir_json.elegir(a.get("carpeta", ""), a["condicion"])[0]
    elif "sufijo" in a:
        elegido = elegir_json.elegir_por_sufijo(a.get("carpeta", ""), a["sufijo"])
    else:
        raise SystemExit(f"{etiqueta}: «auto» necesita «condicion» o «sufijo»: {a}")
    if not elegido:
        print(f"Aviso: {etiqueta}: no hay JSON todavía para {a}; se omite.", file=sys.stderr)
        return ""
    print(f"Auto: {etiqueta} -> {elegido}", file=sys.stderr)
    return elegido


def resolver_config(cfg: dict) -> dict:
    """{configuración: {oferta: ruta o ""}} con los «auto» ya resueltos."""
    return {nombre: {oferta: resolver_ruta(v, f"{nombre} / {oferta}") for oferta, v in ofertas.items()} for nombre, ofertas in cfg["configuraciones"].items()}


def evaluar_configuraciones(cfg: dict) -> dict:
    """{configuración: {oferta: ev}} con las ofertas cuyo JSON existe."""
    salida = {}
    for nombre, ofertas in resolver_config(cfg).items():
        salida[nombre] = {}
        for oferta, ruta in ofertas.items():
            if not ruta or not os.path.isfile(ruta):
                print(f"Aviso: {nombre} / {oferta}: no hay JSON en «{ruta}»; se omite.", file=sys.stderr)
                continue
            gt, esp = E.cargar_gt(oferta), E.cargar_espejos(oferta)
            if not gt:
                raise SystemExit(f"No hay trampas de la oferta {oferta} en {E.GROUND_TRUTH}")
            salida[nombre][oferta] = E.evaluar_archivo(ruta, oferta, gt, esp)      # lee <json>_extras.csv y <json>_juez.csv
    return salida


def metricas(evs: list) -> dict:
    """Métricas de un conjunto de ofertas (lista de ev, una por oferta) sobre el total de sus trampas."""
    t = E.combinar(evs)
    n, enc = t["n_trampas"], t["encontradas"]
    costos = [e.get("costo") or {} for e in evs]
    suma = lambda campo: sum(c.get(campo) or 0 for c in costos)
    criticos = next(((nn, r) for v, nn, r, _ in E.recall_por(t["trampas"], "clase_esperada", E.CLASES) if v == "Crítico"), (0, 0))
    j = t.get("juez")
    no_registro = not t["hay_registro"]
    return {
        "ofertas": "+".join(e["oferta"] for e in evs), "trampas": n, "encontradas": enc, "recall": enc / n, "recall_ic": E.wilson(enc, n),
        "recall_articulo": None if no_registro else t["recall_articulo"], "falsas_alarmas": t["falsas_alarmas"], "espejos": t["n_espejos"],
        "falsas_ic": E.wilson(t["falsas_alarmas"], t["n_espejos"]),
        "brechas_por_oferta": t["n_riesgo"] / len(evs), "riesgos_agrupados_por_oferta": t["volumen"].get("riesgos agrupados", 0) / len(evs),
        "precision_juez_estricta": j["estricta"] / j["n"] if j else None, "precision_juez_amplia": j["amplia"] / j["n"] if j else None,
        "kappa_clase": E.kappa_ponderado_cuadratico(t["confusion"]), "criticos_n": criticos[0], "criticos_encontrados": criticos[1],
        "tiempo_s": suma("tiempo_total_s"), "costo_usd": suma("costo_usd"), "tokens_entrada": suma("tokens_entrada_total"), "tokens_salida": suma("tokens_salida_total"),
        "perdidas": {k: sum(x["perdida"] == k for x in t["trampas"]) for k in COLORES_PERDIDA}, "sin_registro": no_registro}


def calcular_filas(evaluadas: dict, conjuntos: dict) -> list:
    """[{configuracion, conjunto, **métricas}] solo para los conjuntos con todas sus ofertas."""
    filas = []
    for conjunto, ofertas in conjuntos.items():
        for nombre, por_oferta in evaluadas.items():
            if all(o in por_oferta for o in ofertas):
                filas.append({"configuracion": nombre, "conjunto": conjunto, **metricas([por_oferta[o] for o in ofertas])})
            else:
                faltan = [o for o in ofertas if o not in por_oferta]
                print(f"Aviso: {nombre} / {conjunto}: faltan {', '.join(faltan)}; no se calcula.", file=sys.stderr)
    return filas


# --- Tablas ---

def _ic(k, n, ic) -> str:
    return f"{k}/{n} ({k / n:.0%}; {ic[0]:.0%}–{ic[1]:.0%})" if n and ic else "n/d"


def _pc(v) -> str:
    return "n/d" if v is None else f"{v:.0%}"


def _num(v, f="{:.2f}") -> str:
    return "n/d" if v is None else f.format(v)


def _tiempo(s) -> str:
    return "n/d" if not s else f"{int(s) // 3600}:{int(s) % 3600 // 60:02d}:{int(s) % 60:02d}"


def _miles(v) -> str:
    return "n/d" if not v else f"{v:,.0f}".replace(",", ".")


ENCABEZADO = ["Configuración", "Recall estricto (IC 95 %)", "Recall@artículo", "Falsas alarmas", "Brechas / oferta", "Riesgos agrupados / oferta", "Precisión juez estricta",
              "Precisión juez amplia", "Kappa de clase", "Recall de Críticos", "Tiempo (h:mm:ss)", "Costo USD", "Tokens entrada", "Tokens salida"]


def fila_texto(f: dict) -> list:
    return [f["configuracion"], _ic(f["encontradas"], f["trampas"], f["recall_ic"]),
            "n/d" if f["recall_articulo"] is None else f"{f['recall_articulo']}/{f['trampas']} ({f['recall_articulo'] / f['trampas']:.0%})",
            _ic(f["falsas_alarmas"], f["espejos"], f["falsas_ic"]), _num(f["brechas_por_oferta"], "{:.1f}"), _num(f["riesgos_agrupados_por_oferta"], "{:.1f}"),
            _pc(f["precision_juez_estricta"]), _pc(f["precision_juez_amplia"]), _num(f["kappa_clase"]),
            f"{f['criticos_encontrados']}/{f['criticos_n']}" if f["criticos_n"] else "n/d", _tiempo(f["tiempo_s"]), _num(f["costo_usd"]),
            _miles(f["tokens_entrada"]), _miles(f["tokens_salida"])]


def tabla_md(filas: list) -> str:
    L = ["# Comparación de configuraciones", ""]
    for conjunto in dict.fromkeys(f["conjunto"] for f in filas):
        L += [f"## {conjunto}", "", "| " + " | ".join(ENCABEZADO) + " |", "|" + "---|" * len(ENCABEZADO)]
        L += ["| " + " | ".join(fila_texto(f)) + " |" for f in filas if f["conjunto"] == conjunto] + [""]
    L += ["Recall estricto: trampa encontrada con su frase y su artículo (o uno equivalente); IC de Wilson al 95 %. Precisión según el juez: (trampas encontradas + extras válidos) / brechas; "
          "estricta cuenta DUDOSA como no válida, amplia como válida; n/d si faltan veredictos. Costo USD: 0 en la corrida local. Kappa de clase: ponderado cuadrático, sobre las trampas encontradas."]
    return "\n".join(L)


def guardar_csv(filas: list, ruta: str):
    campos = ["configuracion", "conjunto", "ofertas", "trampas", "encontradas", "recall", "recall_ic_inf", "recall_ic_sup", "recall_articulo", "falsas_alarmas", "espejos",
              "falsas_ic_inf", "falsas_ic_sup", "brechas_por_oferta", "riesgos_agrupados_por_oferta", "precision_juez_estricta", "precision_juez_amplia", "kappa_clase",
              "criticos_n", "criticos_encontrados", "tiempo_s", "costo_usd", "tokens_entrada", "tokens_salida"] + [f"perdida_{k.replace(' ', '_')}" for k in COLORES_PERDIDA]
    with open(ruta, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, delimiter=";")
        w.writeheader()
        for f in filas:
            ic, fic = f["recall_ic"] or (None, None), f["falsas_ic"] or (None, None)
            w.writerow({**{k: ("" if f.get(k) is None else f[k]) for k in campos if k in f}, "recall_ic_inf": ic[0], "recall_ic_sup": ic[1], "falsas_ic_inf": fic[0], "falsas_ic_sup": fic[1],
                        **{f"perdida_{k.replace(' ', '_')}": v for k, v in f["perdidas"].items()}})


# --- Gráficos (matplotlib se importa acá: el resto del módulo no lo necesita) ---

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white", "font.size": 15, "axes.titlesize": 18, "axes.labelsize": 15,
                         "xtick.labelsize": 14, "ytick.labelsize": 14, "legend.fontsize": 14, "axes.edgecolor": "#888888", "text.color": TINTA, "axes.labelcolor": TINTA,
                         "xtick.color": TINTA, "ytick.color": TINTA, "axes.spines.top": False, "axes.spines.right": False})
    return plt


def _por_configuracion(filas: list, conjunto: str) -> dict:
    return {f["configuracion"]: f for f in filas if f["conjunto"] == conjunto}


def _conjunto_amplio(filas: list):
    """El conjunto con más ofertas entre los calculados (para los gráficos que muestran un solo conjunto)."""
    return max((f["conjunto"] for f in filas), key=lambda c: max(len(f["ofertas"].split("+")) for f in filas if f["conjunto"] == c), default=None)


def grafico_recall_falsas(filas: list, ruta: str, dev: str, prueba: str):
    plt = _plt()
    nombres = list(dict.fromkeys(f["configuracion"] for f in filas))
    fig, ejes = plt.subplots(1, 2, figsize=(16, 7))
    ancho = 0.38
    for eje, titulo, num, den, ic in ((ejes[0], "Recall estricto", "encontradas", "trampas", "recall_ic"), (ejes[1], "Falsas alarmas (espejos marcados)", "falsas_alarmas", "espejos", "falsas_ic"),):
        for k, (conjunto, color) in enumerate(((dev, AZUL), (prueba, NARANJA))):
            datos = _por_configuracion(filas, conjunto)
            xs = [i + (k - 0.5) * ancho for i, n in enumerate(nombres) if n in datos]
            vs = [datos[n][num] / datos[n][den] for n in nombres if n in datos]
            errores = [[v - datos[n][ic][0] for v, n in zip(vs, [n for n in nombres if n in datos])], [datos[n][ic][1] - v for v, n in zip(vs, [n for n in nombres if n in datos])]]
            eje.bar(xs, vs, ancho * 0.92, color=color, label=conjunto, yerr=errores, ecolor="#555555", capsize=4)
            for x, v, techo in zip(xs, vs, errores[1]):
                eje.text(x, v + techo + 0.01, f"{v:.0%}", ha="center", va="bottom", fontsize=13)
        eje.set_title(titulo, loc="left")
        eje.set_xticks(range(len(nombres)), [n.replace(" ", "\n", 1) for n in nombres])
        eje.set_ylim(0, 1.15)
        eje.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
        eje.grid(axis="y", color="#e5e5e5")
        eje.set_axisbelow(True)
    ejes[0].legend(frameon=False, loc="upper left")
    fig.text(0.01, 0.005, "Barras de error: IC 95 % de Wilson.", fontsize=12, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(ruta, dpi=200)
    plt.close(fig)


def grafico_embudo(filas: list, ruta: str, conjunto: str):
    plt = _plt()
    datos = _por_configuracion(filas, conjunto)
    nombres = [n for n, f in datos.items() if not f["sin_registro"]]
    fig, eje = plt.subplots(figsize=(14, 6.5))
    izq = [0.0] * len(nombres)
    for categoria, color in COLORES_PERDIDA.items():
        vs = [datos[n]["perdidas"][categoria] / datos[n]["trampas"] for n in nombres]
        if not any(vs):
            continue
        eje.barh(nombres, vs, left=izq, color=color, label=categoria, edgecolor="white", linewidth=2)
        for i, v in enumerate(vs):
            if v >= 0.06:
                eje.text(izq[i] + v / 2, i, f"{v:.0%}", ha="center", va="center", color="white" if color in (AZUL, NARANJA, GRIS) else TINTA, fontsize=14)
        izq = [a + v for a, v in zip(izq, vs)]
    eje.invert_yaxis()
    eje.set_xlim(0, 1)
    eje.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    eje.set_title(f"Dónde se pierde cada trampa ({conjunto})", loc="left")
    eje.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    fig.savefig(ruta, dpi=200, bbox_inches="tight")
    plt.close(fig)


def grafico_recall_costo_tiempo(filas: list, ruta: str, conjunto: str):
    plt = _plt()
    datos = _por_configuracion(filas, conjunto)
    colores = [AZUL, NARANJA, AQUA, MAGENTA, AMARILLO, GRIS]
    fig, ejes = plt.subplots(1, 2, figsize=(16, 7))
    for eje, titulo, x_de, etiqueta_x in ((ejes[0], "Recall frente al costo", lambda f: f["costo_usd"], "Costo (USD)"),
                                           (ejes[1], "Recall frente al tiempo", lambda f: f["tiempo_s"] / 60, "Tiempo (minutos)")):
        for i, (n, f) in enumerate(datos.items()):
            eje.scatter(x_de(f), f["recall"], s=260, color=colores[i % len(colores)], edgecolor="white", linewidth=2, zorder=3)
            eje.annotate(n, (x_de(f), f["recall"]), textcoords="offset points", xytext=(12, 8), fontsize=14)
        eje.set_title(f"{titulo} ({conjunto})", loc="left", fontsize=16)
        eje.set_xlabel(etiqueta_x)
        eje.set_ylabel("Recall estricto")
        eje.set_ylim(0, 1)
        eje.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
        eje.margins(x=0.25)
        eje.grid(color="#e5e5e5")
        eje.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(ruta, dpi=200)
    plt.close(fig)


def generar(cfg: dict, salida: str, graficos: bool = True) -> dict:
    os.makedirs(salida, exist_ok=True)
    filas = calcular_filas(evaluar_configuraciones(cfg), cfg["conjuntos"])
    if not filas:
        raise SystemExit("No hay ningún conjunto con todos sus JSON: completá las rutas de la configuración.")
    rutas = {"md": os.path.join(salida, "tabla_comparativa.md"), "csv": os.path.join(salida, "tabla_comparativa.csv")}
    with open(rutas["md"], "w", encoding="utf-8") as f:
        f.write(tabla_md(filas))
    guardar_csv(filas, rutas["csv"])
    if graficos:
        nombres = list(cfg["conjuntos"])
        dev, prueba = nombres[0], nombres[1] if len(nombres) > 1 else nombres[0]
        if any(f["conjunto"] == dev for f in filas) and any(f["conjunto"] == prueba for f in filas):
            rutas["a"] = os.path.join(salida, "grafico_a_recall_falsas_alarmas.png")
            grafico_recall_falsas(filas, rutas["a"], dev, prueba)
        amplio = _conjunto_amplio(filas)
        rutas["b"], rutas["c"] = os.path.join(salida, "grafico_b_embudo.png"), os.path.join(salida, "grafico_c_recall_costo_tiempo.png")
        grafico_embudo(filas, rutas["b"], amplio)
        grafico_recall_costo_tiempo(filas, rutas["c"], amplio)
    return {"filas": filas, "rutas": rutas}


def main(argv=None):
    p = argparse.ArgumentParser(description="Tabla comparativa y gráficos por configuración y conjunto de ofertas")
    p.add_argument("--config", required=True, help="JSON con las rutas de cada configuración y oferta")
    p.add_argument("--salida", default=SALIDA)
    p.add_argument("--sin-graficos", action="store_true")
    p.add_argument("--resolver", action="store_true", help="solo imprime la configuración con los «auto» resueltos (JSON en ASCII) y sale; lo usa cerrar_evaluacion.ps1")
    a = p.parse_args(argv)
    if a.resolver:
        print(json.dumps({"configuraciones": resolver_config(cargar_config(a.config))}, ensure_ascii=True))
        return None
    r = generar(cargar_config(a.config), a.salida, not a.sin_graficos)
    for ruta in r["rutas"].values():
        print(f"Guardado: {ruta}")
    return r


if __name__ == "__main__":
    main()
