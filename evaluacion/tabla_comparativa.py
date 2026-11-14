# evaluacion/tabla_comparativa.py
"""Tabla comparativa final y gráficos. Recalcula todo a partir de los JSON de cada configuración y oferta (con evaluar.py); no lee resultados ya calculados.
Si junto a un JSON están <json>_extras.csv / <json>_juez.csv, se usan para la precisión humana y la del juez.

Uso:
  python -m evaluacion.tabla_comparativa --config evaluacion/config_tabla_ejemplo.json [--salida evaluacion/resultados_finales]
Configuración (JSON): {"configuraciones": {"<nombre>": {"P1": "<ruta json>", "P2": "..."}, ...},
                       "conjuntos": {"<nombre>": ["P1", "P2"], ...}}      # «conjuntos» es opcional (por defecto desarrollo, prueba y total)
«salida» (opcional) fija la carpeta de salida por defecto, relativa a la raíz del repo (config_reeval.json usa evaluacion/resultados_reeval); --salida la pisa; sin ninguna de las dos: resultados_finales.
Los conjuntos o las ofertas sin JSON (ruta vacía o inexistente) se omiten con un aviso. Rutas relativas a la carpeta desde la que se corre.
En lugar de una ruta, una oferta puede ser {"auto": {"carpeta": "<carpeta>", "condicion": "<condicion>"}} (el JSON local más reciente con esa condición) o
{"auto": {"carpeta": "<carpeta>", "sufijo": "<sufijo>"}} (el más reciente que termina en _<sufijo>.json). Con «sin_rag»: {"P1": "<ruta>", ...} (JSON en modo lista) se genera comparacion_sin_rag.md: la PRIMERA configuración
contra el sin RAG, con McNemar, para cada conjunto de 2 o más ofertas completo en ambos lados. «modo_generacion» en un «auto» por condición exige además ese modo.
Reevaluación con la recuperación elegida: {"reeval": {"elegida_vs_v1": {"<configuración con la recuperación elegida>": "<su par de v1>", ...}}} agrega el embudo de la reevaluación
(grafico_b_embudo_reeval.png; error si el gris no es idéntico entre las configuraciones), el antes/después de la recuperación (grafico_e) y la diferencia contra v1 en la tabla.
Siempre: control de comparabilidad (la huella de pares de cada JSON, calculada de secciones[].fragmentos; si dos configuraciones del mismo gráfico difieren se avisa en el informe y
en el título), grafico_d_errores_por_criticidad.png y grafico_f_confusion_clase.png (sobre el conjunto más amplio)."""
import argparse
import csv
import json
import os
import sys

from scripts import elegir_json, huella_recuperacion

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


def carpeta_salida(cfg: dict, salida: str = None) -> str:
    """--salida explícito > clave «salida» del config (relativa a la raíz del repo) > resultados_finales."""
    if salida:
        return salida
    if cfg.get("salida"):
        return os.path.join(os.path.dirname(AQUI), cfg["salida"])
    return SALIDA


def resolver_ruta(valor, etiqueta: str = "") -> str:
    """Ruta del JSON de una oferta. «valor» es la ruta (cadena) o {"auto": {"carpeta": ..., "condicion": ..., "modo_generacion": ...}} (el JSON más reciente de
    la carpeta con esa configuracion_analisis.condicion y, si se indica, ese modo_generacion; sin deepinfra, reclasificado ni parcial; scripts.elegir_json) o {"auto": {"carpeta": ..., "sufijo": ...}}
    (el más reciente *_<sufijo>.json). Devuelve "" si no hay ninguno (con aviso)."""
    if not isinstance(valor, dict) or "auto" not in valor:
        return valor or ""
    a = valor["auto"]
    if "condicion" in a:
        elegido = elegir_json.elegir(a.get("carpeta", ""), a["condicion"], a.get("modo_generacion"))[0]
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


def info_recuperacion(resultado: dict) -> dict:
    """Qué recuperación usó un JSON de análisis: la huella de los pares verificados (de secciones[].fragmentos, así sirve también para v1), cuántos son, el hash del archivo
    de recuperación reusado (si lo hay) y los parámetros con que se recuperó (embedding, K, top N, top denso, tope)."""
    cfg = resultado.get("configuracion_analisis") or {}
    secciones = resultado.get("secciones") or []
    return {"huella_pares": huella_recuperacion.huella_de_pares(secciones), "pares": sum(len(x.get("fragmentos") or []) for x in secciones),
            "sha256": cfg.get("recuperacion_json_sha256"), "embedding": cfg.get("embedding_backend") or "bge-m3", "k_subseccion": cfg.get("k_subseccion"),
            "top_n": cfg.get("top_n_subseccion"), "top_densa": cfg.get("top_densa_subseccion"), "tope": cfg.get("tope_fragmentos_por_seccion"), "perfil": cfg.get("perfil_recuperacion")}


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
            salida[nombre][oferta]["recuperacion"] = info_recuperacion(E._cargar(ruta))
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
        "brechas_por_oferta": t["n_riesgo"] / len(evs), "brechas_total": t["n_riesgo"], "riesgos_agrupados_por_oferta": t["volumen"].get("riesgos agrupados", 0) / len(evs),
        "precision_juez_estricta": j["estricta"] / j["n"] if j else None, "precision_juez_amplia": j["amplia"] / j["n"] if j else None,
        "control_juez_n": t["control_juez"]["n"] if t["control_juez"] else None, "control_juez_no_valida": t["control_juez"]["no_valida"] if t["control_juez"] else None,
        "kappa_clase": E.kappa_ponderado_cuadratico(t["confusion"]), "criticos_n": criticos[0], "criticos_encontrados": criticos[1],
        "tiempo_s": suma("tiempo_total_s"), "costo_usd": suma("costo_usd"), "tokens_entrada": suma("tokens_entrada_total"), "tokens_salida": suma("tokens_salida_total"),
        "perdidas": {k: sum(x["perdida"] == k for x in t["trampas"]) for k in COLORES_PERDIDA}, "sin_registro": no_registro,
        "pares_por_oferta": (sum(e["recuperacion"]["pares"] for e in evs) / len(evs)) if all(e.get("recuperacion") for e in evs) else None}


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


ENCABEZADO = ["Configuración", "Recall estricto (IC 95 %)", "Recall@artículo", "Falsas alarmas sobre casos conformes", "Brechas / oferta", "Brechas (total)", "Riesgos agrupados / oferta", "Precisión juez estricta",
              "Precisión juez amplia", "Control del juez (casos conformes NO_VALIDA)", "Kappa de clase", "Recall de Críticos", "Tiempo (h:mm:ss)", "Costo USD", "Tokens entrada", "Tokens salida"]


def _control_juez(f: dict) -> str:
    """Especificidad del juez sobre los casos conformes (falsos positivos conocidos): NO_VALIDA / juzgados."""
    n = f["control_juez_n"]
    return "n/d" if not n else f"{f['control_juez_no_valida']}/{n} ({f['control_juez_no_valida'] / n:.0%})"


def fila_texto(f: dict) -> list:
    return [f["configuracion"], _ic(f["encontradas"], f["trampas"], f["recall_ic"]),
            "n/d" if f["recall_articulo"] is None else f"{f['recall_articulo']}/{f['trampas']} ({f['recall_articulo'] / f['trampas']:.0%})",
            _ic(f["falsas_alarmas"], f["espejos"], f["falsas_ic"]), _num(f["brechas_por_oferta"], "{:.1f}"), _num(f["brechas_total"], "{:.0f}"), _num(f["riesgos_agrupados_por_oferta"], "{:.1f}"),
            _pc(f["precision_juez_estricta"]), _pc(f["precision_juez_amplia"]), _control_juez(f), _num(f["kappa_clase"]),
            f"{f['criticos_encontrados']}/{f['criticos_n']}" if f["criticos_n"] else "n/d", _tiempo(f["tiempo_s"]), _num(f["costo_usd"]),
            _miles(f["tokens_entrada"]), _miles(f["tokens_salida"])]


def tabla_md(filas: list) -> str:
    L = ["# Comparación de configuraciones", ""]
    for conjunto in dict.fromkeys(f["conjunto"] for f in filas):
        L += [f"## {conjunto}", "", "| " + " | ".join(ENCABEZADO) + " |", "|" + "---|" * len(ENCABEZADO)]
        L += ["| " + " | ".join(fila_texto(f)) + " |" for f in filas if f["conjunto"] == conjunto] + [""]
    L += ["Recall estricto: trampa encontrada con su frase y su artículo (o uno equivalente); IC de Wilson al 95 %. Precisión según el juez: (trampas encontradas + extras válidos) / brechas; "
          "estricta cuenta DUDOSA como no válida, amplia como válida; n/d si faltan veredictos. Control del juez: de las brechas que caen sobre casos conformes "
          "(falsos positivos conocidos), cuántas marcó NO_VALIDA (especificidad); n/d si no se corrió «juez --conformes». Falsas alarmas sobre casos conformes: casos conformes marcados como brecha / total de casos conformes. Costo USD: 0 en la corrida local. Kappa de clase: ponderado cuadrático, sobre las trampas encontradas."]
    return "\n".join(L)


def guardar_csv(filas: list, ruta: str):
    campos = ["configuracion", "conjunto", "ofertas", "trampas", "encontradas", "recall", "recall_ic_inf", "recall_ic_sup", "recall_articulo", "falsas_alarmas", "espejos",
              "falsas_ic_inf", "falsas_ic_sup", "brechas_por_oferta", "brechas_total", "pares_por_oferta", "riesgos_agrupados_por_oferta", "precision_juez_estricta", "precision_juez_amplia", "control_juez_n", "control_juez_no_valida",
              "kappa_clase", "criticos_n", "criticos_encontrados", "tiempo_s", "costo_usd", "tokens_entrada", "tokens_salida"] + [f"perdida_{k.replace(' ', '_')}" for k in COLORES_PERDIDA]
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


ETIQUETAS_CORTAS = {"qwen3:8b local": "8B local", "Qwen3-32B": "32B", "Qwen3-32B con razonamiento": "32B razon.",
                    "32B con razonamiento + recuperación amplia": "32B razon. + amplia", "qwen3:8b local (elegida)": "8B elegida", "Qwen3-32B (elegida)": "32B elegida",
                    "Qwen3-32B con razonamiento (elegida)": "32B razon. elegida"}


def _corta(nombre: str) -> str:
    """Etiqueta corta para los gráficos (la tabla mantiene el nombre largo); lo que no está en el mapa queda igual."""
    return ETIQUETAS_CORTAS.get(nombre, nombre)


def _poner_aviso(fig, aviso: str):
    """Aviso de comparabilidad (recuperaciones distintas) arriba del gráfico, en rojo."""
    if aviso:
        fig.suptitle(aviso, color="#b00020", fontsize=12, y=0.995)


def _por_configuracion(filas: list, conjunto: str) -> dict:
    return {f["configuracion"]: f for f in filas if f["conjunto"] == conjunto}


def _conjunto_amplio(filas: list):
    """El conjunto con más ofertas entre los calculados (para los gráficos que muestran un solo conjunto)."""
    return max((f["conjunto"] for f in filas), key=lambda c: max(len(f["ofertas"].split("+")) for f in filas if f["conjunto"] == c), default=None)


def grafico_recall_falsas(filas: list, ruta: str, dev: str, prueba: str, aviso: str = ""):
    plt = _plt()
    nombres = list(dict.fromkeys(f["configuracion"] for f in filas))
    fig, ejes = plt.subplots(1, 2, figsize=(16, 7))
    ancho = 0.38
    for eje, titulo, num, den, ic in ((ejes[0], "Recall estricto", "encontradas", "trampas", "recall_ic"), (ejes[1], "Falsas alarmas sobre casos conformes", "falsas_alarmas", "espejos", "falsas_ic"),):
        for k, (conjunto, color) in enumerate(((dev, AZUL), (prueba, NARANJA))):
            datos = _por_configuracion(filas, conjunto)
            xs = [i + (k - 0.5) * ancho for i, n in enumerate(nombres) if n in datos]
            vs = [datos[n][num] / datos[n][den] for n in nombres if n in datos]
            errores = [[v - datos[n][ic][0] for v, n in zip(vs, [n for n in nombres if n in datos])], [datos[n][ic][1] - v for v, n in zip(vs, [n for n in nombres if n in datos])]]
            eje.bar(xs, vs, ancho * 0.92, color=color, label=conjunto, yerr=errores, ecolor="#555555", capsize=4)
            for x, v, techo in zip(xs, vs, errores[1]):
                eje.text(x, v + techo + 0.01, f"{v:.0%}", ha="center", va="bottom", fontsize=13)
        eje.set_title(titulo, loc="left")
        eje.set_xticks(range(len(nombres)), [_corta(n).replace(" ", "\n", 1) for n in nombres])
        eje.set_ylim(0, 1.15)
        eje.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
        eje.grid(axis="y", color="#e5e5e5")
        eje.set_axisbelow(True)
    ejes[0].legend(frameon=False, loc="upper left")
    fig.text(0.01, 0.005, "Barras de error: IC 95 % de Wilson.", fontsize=12, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95 if aviso else 1))
    _poner_aviso(fig, aviso)
    fig.savefig(ruta, dpi=200)
    plt.close(fig)


def grafico_embudo(filas: list, ruta: str, conjunto: str, aviso: str = "", nombres: list = None, titulo: str = None):
    """nombres: solo esas configuraciones (por defecto todas las que traen registro técnico); titulo: reemplaza al título por defecto."""
    plt = _plt()
    datos = _por_configuracion(filas, conjunto)
    nombres = [n for n, f in datos.items() if not f["sin_registro"] and (nombres is None or n in nombres)]
    fig, eje = plt.subplots(figsize=(14, 6.5))
    izq = [0.0] * len(nombres)
    etiquetas = [_corta(n) for n in nombres]
    for categoria, color in COLORES_PERDIDA.items():
        vs = [datos[n]["perdidas"][categoria] / datos[n]["trampas"] for n in nombres]
        if not any(vs):
            continue
        eje.barh(etiquetas, vs, left=izq, color=color, label=categoria, edgecolor="white", linewidth=2)
        for i, v in enumerate(vs):
            if v >= 0.06:
                eje.text(izq[i] + v / 2, i, f"{v:.0%}", ha="center", va="center", color="white" if color in (AZUL, NARANJA, GRIS) else TINTA, fontsize=14)
        izq = [a + v for a, v in zip(izq, vs)]
    eje.invert_yaxis()
    eje.set_xlim(0, 1)
    eje.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    eje.set_title(titulo or f"Dónde se pierde cada trampa ({conjunto})", loc="left")
    eje.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    _poner_aviso(fig, aviso)
    fig.savefig(ruta, dpi=200, bbox_inches="tight")
    plt.close(fig)


def grafico_recall_costo_tiempo(filas: list, ruta: str, conjunto: str, aviso: str = ""):
    plt = _plt()
    datos = _por_configuracion(filas, conjunto)
    colores = [AZUL, NARANJA, AQUA, MAGENTA, AMARILLO, GRIS]
    fig, ejes = plt.subplots(1, 2, figsize=(16, 7))
    for eje, titulo, x_de, etiqueta_x in ((ejes[0], "Recall frente al costo", lambda f: f["costo_usd"], "Costo (USD)"),
                                           (ejes[1], "Recall frente al tiempo", lambda f: f["tiempo_s"] / 60, "Tiempo (minutos)")):
        for i, (n, f) in enumerate(datos.items()):
            eje.scatter(x_de(f), f["recall"], s=260, color=colores[i % len(colores)], edgecolor="white", linewidth=2, zorder=3)
            eje.annotate(_corta(n), (x_de(f), f["recall"]), textcoords="offset points", xytext=(12, 8 if i % 2 == 0 else -20), fontsize=14)
        xs = [x_de(f) for f in datos.values()]
        ancho = (max(xs) - min(xs)) or max(xs) or 1
        eje.set_xlim(min(xs) - 0.1 * ancho, max(xs) + 0.7 * ancho)
        eje.set_title(f"{titulo} ({conjunto})", loc="left", fontsize=16)
        eje.set_xlabel(etiqueta_x)
        eje.set_ylabel("Recall estricto")
        eje.set_ylim(0, 1)
        eje.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
        eje.grid(color="#e5e5e5")
        eje.set_axisbelow(True)
    fig.tight_layout(rect=(0, 0, 1, 0.95 if aviso else 1))
    _poner_aviso(fig, aviso)
    fig.savefig(ruta, dpi=200)
    plt.close(fig)


def comparacion_sin_rag(cfg: dict, evaluadas: dict):
    """Markdown con la tabla con RAG / sin RAG y el McNemar (las mismas funciones que evaluar --comparar) de la PRIMERA configuración del archivo contra
    el grupo «sin_rag», para cada conjunto de 2 o más ofertas que tenga JSON en ambos lados. None si no hay nada que comparar."""
    if not cfg.get("sin_rag"):
        return None
    nombre = next(iter(cfg["configuraciones"]))
    con, sins = evaluadas.get(nombre, {}), {}
    for oferta, valor in cfg["sin_rag"].items():
        ruta = resolver_ruta(valor, f"sin RAG / {oferta}")
        if ruta and os.path.isfile(ruta):
            sins[oferta] = E.evaluar(E._cargar(ruta), E.cargar_gt(oferta), E.cargar_espejos(oferta), oferta)
        else:
            print(f"Aviso: sin RAG / {oferta}: no hay JSON en «{ruta}»; se omite.", file=sys.stderr)
    L = [f"# Comparación con RAG ({nombre}) frente a sin RAG", ""]
    for conjunto, ofertas in cfg["conjuntos"].items():
        if len(ofertas) > 1 and all(o in con and o in sins for o in ofertas):
            t, s = E.combinar([con[o] for o in ofertas]), E.combinar([sins[o] for o in ofertas])
            L += [f"## {conjunto}", "", E.tabla_comparacion(t, s, E.comparar_mcnemar(t, s)), ""]
    return "\n".join(L) if len(L) > 2 else None


# --- Comparabilidad de la recuperación, antes/después y criticidad (reevaluación con la recuperación elegida) ---

class GrisDistinto(ValueError):
    """Las configuraciones con la recuperación elegida verificaron los mismos pares, así que su gris («no recuperada») tiene que ser idéntico: si no, hay un error."""


SUTILEZA = {"A": "alto", "M": "medio", "B": "bajo"}      # sufijo del id de la trampa (P1-01-A)
ORDEN_SUTILEZA = ("alto", "medio", "bajo")


def sutileza_de(id_trampa: str):
    """Nivel de sutileza de la trampa según el sufijo -A / -M / -B de su id; None si no lo trae."""
    return SUTILEZA.get(str(id_trampa).rsplit("-", 1)[-1])


def errores_por(trampas: list, clave, orden) -> list:
    """[(valor, n, errores)] por el valor que da `clave(trampa)` en el orden dado; error = la trampa no se encontró (1 − recall estricto). Solo los valores con trampas."""
    filas = []
    for v in orden:
        grupo = [t for t in trampas if clave(t) == v]
        if grupo:
            filas.append((v, len(grupo), sum(t["estado"] != "encontrada" for t in grupo)))
    return filas


def _evs(evaluadas: dict, nombre: str, ofertas: list):
    por = evaluadas.get(nombre, {})
    return [por[o] for o in ofertas] if all(o in por for o in ofertas) else None


def grupos_de_recuperacion(evaluadas: dict, nombres: list, oferta: str) -> dict:
    """{huella de pares: [configuraciones]} de una oferta, entre las configuraciones `nombres` que la tienen."""
    grupos = {}
    for n in nombres:
        info = (evaluadas.get(n, {}).get(oferta) or {}).get("recuperacion")
        if info:
            grupos.setdefault(info["huella_pares"], []).append(n)
    return grupos


def ofertas_con_recuperaciones_distintas(evaluadas: dict, nombres: list, ofertas: list) -> list:
    return [o for o in ofertas if len(grupos_de_recuperacion(evaluadas, nombres, o)) > 1]


def aviso_comparabilidad(evaluadas: dict, nombres: list, ofertas: list) -> str:
    """Texto para el título de un gráfico si las configuraciones comparadas usan recuperaciones distintas (huella de pares) en alguna oferta; '' si todas coinciden."""
    distintas = ofertas_con_recuperaciones_distintas(evaluadas, nombres, ofertas)
    return f"Atención: las configuraciones de este gráfico usan recuperaciones distintas (huella de pares) en {', '.join(distintas)}" if distintas else ""


def descripcion_recuperacion(info) -> str:
    """Embedding y K con que se recuperó (de configuracion_analisis del JSON), para los títulos."""
    if not info:
        return "n/d"
    partes = [f"embedding {info.get('embedding') or 'bge-m3'}"]
    partes += [f"{etiqueta}={info[clave]}" for etiqueta, clave in (("K_SUBSECCION", "k_subseccion"), ("TOP_N", "top_n"), ("TOP_DENSA", "top_densa"), ("tope", "tope")) if info.get(clave) is not None]
    return ", ".join(partes)


def _info_de(evaluadas: dict, nombre: str):
    return next((e["recuperacion"] for e in evaluadas.get(nombre, {}).values() if e.get("recuperacion")), None)


def seccion_comparabilidad_md(evaluadas: dict, conjuntos: dict) -> list:
    """Sección del informe: huella de pares y pares por oferta de cada configuración, y un aviso por cada conjunto cuyas configuraciones comparan recuperaciones distintas."""
    ofertas = sorted({o for por in evaluadas.values() for o in por})
    filas = []
    for nombre, por in evaluadas.items():
        celdas = [f"`{por[o]['recuperacion']['huella_pares'][:10]}` ({por[o]['recuperacion']['pares']})" if o in por and por[o].get("recuperacion") else "—" for o in ofertas]
        filas.append([nombre, descripcion_recuperacion(_info_de(evaluadas, nombre)), *celdas])
    L = ["## Comparabilidad de la recuperación", "", "Huella de los pares verificados (sha256 de sección, norma, artículo y parte; primeros 10 caracteres) y, entre paréntesis, los pares de cada oferta. "
         "Dos configuraciones con la misma huella verificaron exactamente los mismos pares.", "", "| Configuración | Recuperación | " + " | ".join(ofertas) + " |", "|" + "---|" * (len(ofertas) + 2)]
    L += ["| " + " | ".join(f) + " |" for f in filas] + [""]
    sha = {n: {e["recuperacion"]["sha256"] for e in por.values() if e.get("recuperacion") and e["recuperacion"].get("sha256")} for n, por in evaluadas.items()}
    if any(sha.values()):
        L += ["Archivo de recuperación reusado (sha256, primeros 12 caracteres): " + "; ".join(f"{n}: {', '.join(sorted(x[:12] for x in v))}" for n, v in sha.items() if v), ""]
    for conjunto, of in conjuntos.items():
        nombres = [n for n in evaluadas if all(o in evaluadas[n] for o in of)]
        for o in ofertas_con_recuperaciones_distintas(evaluadas, nombres, of):
            grupos = grupos_de_recuperacion(evaluadas, nombres, o)
            L.append(f"**AVISO ({conjunto}, {o}):** las configuraciones comparan recuperaciones distintas: " + " | ".join(f"`{h[:10]}`: {', '.join(g)}" for h, g in grupos.items()))
    return L + [""]


def diferencias_v1(filas: list, mapa: dict) -> list:
    """Por conjunto y por configuración con la recuperación elegida (clave de `mapa`) frente a su par de v1 (valor): diferencia de cada métrica (elegida − v1)."""
    salida = []
    for conjunto in dict.fromkeys(f["conjunto"] for f in filas):
        datos = _por_configuracion(filas, conjunto)
        for elegida, v1 in mapa.items():
            if elegida not in datos or v1 not in datos:
                continue
            e, b = datos[elegida], datos[v1]
            resta = lambda k: None if e.get(k) is None or b.get(k) is None else e[k] - b[k]
            salida.append({"conjunto": conjunto, "configuracion": elegida, "v1": v1, "d_recall": resta("recall"), "d_encontradas": resta("encontradas"), "d_recall_articulo": resta("recall_articulo"),
                           "d_no_recuperadas": e["perdidas"]["no recuperada"] - b["perdidas"]["no recuperada"], "d_falsas_alarmas": resta("falsas_alarmas"), "d_brechas_total": resta("brechas_total"),
                           "d_brechas_por_oferta": resta("brechas_por_oferta"), "d_riesgos_agrupados_por_oferta": resta("riesgos_agrupados_por_oferta"), "d_kappa": resta("kappa_clase"),
                           "d_tiempo_s": resta("tiempo_s"), "d_costo_usd": resta("costo_usd"), "d_pares_por_oferta": resta("pares_por_oferta")})
    return salida


def _delta(v, formato="{:+.0f}") -> str:
    if v is None:
        return "n/d"
    return "0" if abs(v) < 1e-9 else formato.format(v).replace("-", "−")


def diferencias_md(difs: list) -> list:
    """Tabla de diferencias contra v1: si bajar el gris (menos trampas no recuperadas) subió el ruido (más falsas alarmas, brechas y riesgos)."""
    if not difs:
        return []
    encabezado = ["Configuración (elegida − v1)", "Δ recall estricto (pp)", "Δ trampas encontradas", "Δ trampas no recuperadas (gris)", "Δ Recall@artículo", "Δ falsas alarmas sobre casos conformes",
                  "Δ brechas / oferta", "Δ brechas (total)", "Δ riesgos agrupados / oferta", "Δ pares / oferta", "Δ kappa de clase", "Δ tiempo", "Δ costo USD"]
    L = ["## Recuperación elegida frente a v1", ""]
    for conjunto in dict.fromkeys(d["conjunto"] for d in difs):
        filas = [[f"{d['configuracion']} − {d['v1']}", _delta(None if d["d_recall"] is None else d["d_recall"] * 100, "{:+.1f}"), _delta(d["d_encontradas"]), _delta(d["d_no_recuperadas"]),
                  _delta(d["d_recall_articulo"]), _delta(d["d_falsas_alarmas"]), _delta(d["d_brechas_por_oferta"], "{:+.1f}"), _delta(d["d_brechas_total"]),
                  _delta(d["d_riesgos_agrupados_por_oferta"], "{:+.1f}"), _delta(d["d_pares_por_oferta"], "{:+.0f}"), _delta(d["d_kappa"], "{:+.2f}"),
                  _delta(d["d_tiempo_s"], "{:+.0f} s"), _delta(d["d_costo_usd"], "{:+.2f}")] for d in difs if d["conjunto"] == conjunto]
        L += [f"### {conjunto}", "", "| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)] + ["| " + " | ".join(f) + " |" for f in filas] + [""]
    L += ["Lectura: Δ trampas no recuperadas negativo = el gris bajó; Δ falsas alarmas, Δ brechas y Δ riesgos positivos = subió el ruido (el costo de bajar el gris). Δ tiempo en segundos, Δ costo en USD.", ""]
    return L


def grafico_embudo_reeval(filas: list, ruta: str, conjunto: str, nombres: list, evaluadas: dict, aviso: str = "") -> bool:
    """Una barra por LLM con la recuperación elegida (sin la de v1 ni la amplia). El gris es idéntico en todas por construcción (mismos pares verificados): si no lo es, es un
    error (GrisDistinto). El título dice qué embedding y qué K. False si no hay ninguna configuración con ese conjunto."""
    datos = _por_configuracion(filas, conjunto)
    nombres = [n for n in nombres if n in datos and not datos[n]["sin_registro"]]
    if not nombres:
        return False
    gris = {n: datos[n]["perdidas"]["no recuperada"] for n in nombres}
    if len(set(gris.values())) > 1:
        raise GrisDistinto("El gris (trampas no recuperadas) no es idéntico entre las configuraciones con la recuperación elegida: " + ", ".join(f"{n}: {v}" for n, v in gris.items())
                           + ". Verificaron los mismos pares, así que tiene que coincidir: revisá si algún par falló (llamada fallida) o si algún JSON es de otra recuperación.")
    titulo = f"Dónde se pierde cada trampa con la recuperación elegida ({conjunto})\n{descripcion_recuperacion(_info_de(evaluadas, nombres[0]))}"
    grafico_embudo(filas, ruta, conjunto, aviso, nombres, titulo)
    return True


def grafico_recuperacion_antes_despues(filas: list, ruta: str, mapa: dict, conjuntos: dict, evaluadas: dict) -> bool:
    """El gris de v1 (BGE-M3, K=10) contra el de la recuperación elegida, por conjunto: trampas recuperadas (llegan al verificador) sobre el total y pares por oferta."""
    plt = _plt()
    elegidas, v1s = list(mapa), list(dict.fromkeys(mapa.values()))
    filas_g = []
    for conjunto in conjuntos:
        datos = _por_configuracion(filas, conjunto)
        e, b = (next((datos[n] for n in nombres if n in datos), None) for nombres in (elegidas, v1s))
        if e and b:
            filas_g.append((conjunto, b, e))
    if not filas_g:
        return False
    fig, ejes = plt.subplots(1, 2, figsize=(16, 7))
    ancho = 0.38
    for eje, titulo, valor, texto in ((ejes[0], "Trampas recuperadas (el artículo llega al verificador)", lambda f: f["trampas"] - f["perdidas"]["no recuperada"], lambda f, v: f"{v}/{f['trampas']}"),
                                      (ejes[1], "Pares a verificar por oferta", lambda f: f.get("pares_por_oferta") or 0, lambda f, v: f"{v:.0f}")):
        for k, (etiqueta, color, i) in enumerate((("v1 (BGE-M3, K=10)", GRIS, 1), ("recuperación elegida", AZUL, 2))):
            xs = [j + (k - 0.5) * ancho for j in range(len(filas_g))]
            vs = [valor(g[i]) for g in filas_g]
            eje.bar(xs, vs, ancho * 0.92, color=color, label=etiqueta)
            for x, g, v in zip(xs, filas_g, vs):
                eje.text(x, v, texto(g[i], v), ha="center", va="bottom", fontsize=13)
        eje.set_xticks(range(len(filas_g)), [g[0].replace(" ", "\n", 1) for g in filas_g])
        eje.set_title(titulo, loc="left", fontsize=15)
        eje.set_ylim(0, max(valor(g[i]) for g in filas_g for i in (1, 2)) * 1.18 or 1)
        eje.grid(axis="y", color="#e5e5e5")
        eje.set_axisbelow(True)
    ejes[0].legend(frameon=False, loc="lower right")
    primero = next((n for n in elegidas if _info_de(evaluadas, n)), None)
    fig.suptitle(f"Recuperación antes y después. Elegida: {descripcion_recuperacion(_info_de(evaluadas, primero)) if primero else 'n/d'}", fontsize=14, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(ruta, dpi=200)
    plt.close(fig)
    return True


def grafico_errores_por_criticidad(evaluadas: dict, ofertas: list, nombres: list, ruta: str, conjunto: str = "", aviso: str = "") -> bool:
    """Tasa de error (1 − recall estricto) por nivel de sutileza de la trampa (sufijo -A/-M/-B: alto, medio, bajo) y por clase esperada; una serie por configuración, con x/n en cada barra."""
    plt = _plt()
    trampas = {n: E.combinar(_evs(evaluadas, n, ofertas))["trampas"] for n in nombres if _evs(evaluadas, n, ofertas)}
    if not trampas:
        return False
    colores = [AZUL, NARANJA, AQUA, MAGENTA, AMARILLO, GRIS]
    fig, ejes = plt.subplots(1, 2, figsize=(17, 7.5))
    paneles = ((ejes[0], "Por nivel de sutileza de la trampa", lambda t: sutileza_de(t["id"]), ORDEN_SUTILEZA), (ejes[1], "Por clase esperada", lambda t: t["clase_esperada"], E.CLASES))
    for eje, titulo, clave, orden in paneles:
        por_config = {n: errores_por(ts, clave, orden) for n, ts in trampas.items()}
        categorias = [v for v in orden if any(v == x[0] for filas_c in por_config.values() for x in filas_c)]
        ancho = 0.84 / len(por_config)
        for i, (n, filas_c) in enumerate(por_config.items()):
            por_valor = {v: (cant, err) for v, cant, err in filas_c}
            for j, v in enumerate(categorias):
                cant, err = por_valor.get(v, (0, 0))
                x = j + (i - (len(por_config) - 1) / 2) * ancho
                tasa = err / cant if cant else 0
                eje.bar(x, tasa, ancho * 0.92, color=colores[i % len(colores)], label=_corta(n) if j == 0 else None)
                eje.text(x, tasa + 0.01, f"{tasa:.0%}\n{err}/{cant}", ha="center", va="bottom", fontsize=9)
        eje.set_xticks(range(len(categorias)), categorias)
        eje.set_title(titulo, loc="left")
        eje.set_ylabel("Tasa de error (1 − recall estricto)")
        eje.set_ylim(0, 1.3)
        eje.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
        eje.grid(axis="y", color="#e5e5e5")
        eje.set_axisbelow(True)
    ejes[0].legend(frameon=False, loc="upper right", ncol=2, fontsize=10)
    fig.suptitle(f"Errores por criticidad ({conjunto}); en cada barra: trampas no encontradas / trampas del grupo" + (f"\n{aviso}" if aviso else ""), fontsize=13, y=0.995,
                 color="#b00020" if aviso else TINTA)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(ruta, dpi=200)
    plt.close(fig)
    return True


def matriz_de_confusion(confusion: dict) -> list:
    """Filas = clase esperada (Crítico, Mayor, Menor); columnas = clase asignada (esas tres y «otra»: sin clase o fuera de las tres)."""
    matriz = [[0] * (len(E.CLASES) + 1) for _ in E.CLASES]
    for (esperada, obtenida), n in confusion.items():
        if esperada in E.CLASES:
            matriz[E.CLASES.index(esperada)][E.CLASES.index(obtenida) if obtenida in E.CLASES else len(E.CLASES)] += n
    return matriz


def grafico_confusion_clase(evaluadas: dict, ofertas: list, nombres: list, ruta: str, conjunto: str = "", aviso: str = "") -> bool:
    """Matriz de confusión clase esperada × clase asignada sobre las trampas encontradas, una por configuración, con los conteos."""
    plt = _plt()
    matrices = {n: matriz_de_confusion(E.combinar(_evs(evaluadas, n, ofertas))["confusion"]) for n in nombres if _evs(evaluadas, n, ofertas)}
    if not matrices:
        return False
    columnas = 3 if len(matrices) > 2 else len(matrices)
    filas_g = -(-len(matrices) // columnas)
    fig, ejes = plt.subplots(filas_g, columnas, figsize=(5.6 * columnas, 5.4 * filas_g), squeeze=False)
    etiquetas_x = list(E.CLASES) + ["otra"]
    for eje in ejes.flat:
        eje.axis("off")
    for eje, (n, m) in zip(ejes.flat, matrices.items()):
        eje.axis("on")
        eje.imshow(m, cmap="Blues", vmin=0, vmax=max(1, max(max(f) for f in m)))
        for i, fila in enumerate(m):
            for j, v in enumerate(fila):
                eje.text(j, i, str(v), ha="center", va="center", fontsize=15, color="white" if v > max(1, max(max(f) for f in m)) / 2 else TINTA)
        eje.set_xticks(range(len(etiquetas_x)), etiquetas_x, fontsize=11)
        eje.set_yticks(range(len(E.CLASES)), list(E.CLASES), fontsize=11)
        eje.set_xlabel("clase asignada")
        eje.set_ylabel("clase esperada")
        eje.set_title(f"{_corta(n)} ({sum(map(sum, m))} encontradas)", fontsize=13)
    fig.suptitle(f"Matriz de confusión de la clase ({conjunto})" + (f"\n{aviso}" if aviso else ""), fontsize=14, y=0.995, color="#b00020" if aviso else TINTA)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(ruta, dpi=200)
    plt.close(fig)
    return True


def generar(cfg: dict, salida: str, graficos: bool = True) -> dict:
    os.makedirs(salida, exist_ok=True)
    evaluadas = evaluar_configuraciones(cfg)
    filas = calcular_filas(evaluadas, cfg["conjuntos"])
    if not filas:
        raise SystemExit("No hay ningún conjunto con todos sus JSON: completá las rutas de la configuración.")
    rutas = {"md": os.path.join(salida, "tabla_comparativa.md"), "csv": os.path.join(salida, "tabla_comparativa.csv")}
    mapa = (cfg.get("reeval") or {}).get("elegida_vs_v1") or {}
    extra = diferencias_md(diferencias_v1(filas, mapa)) if mapa else []
    extra += seccion_comparabilidad_md(evaluadas, cfg["conjuntos"])
    with open(rutas["md"], "w", encoding="utf-8") as f:
        f.write(tabla_md(filas) + "\n\n" + "\n".join(extra))
    guardar_csv(filas, rutas["csv"])
    comparacion = comparacion_sin_rag(cfg, evaluadas)
    if comparacion:
        rutas["sin_rag"] = os.path.join(salida, "comparacion_sin_rag.md")
        with open(rutas["sin_rag"], "w", encoding="utf-8") as f:
            f.write(comparacion)
    if graficos:
        nombres = list(cfg["conjuntos"])
        dev, prueba = nombres[0], nombres[1] if len(nombres) > 1 else nombres[0]

        def aviso(*conjuntos):
            """Aviso para el título si las configuraciones del gráfico (las de las filas de esos conjuntos) usan recuperaciones distintas."""
            plotted = [n for n in evaluadas if any(f["configuracion"] == n and f["conjunto"] in conjuntos for f in filas)]
            return aviso_comparabilidad(evaluadas, plotted, sorted({o for c in conjuntos for o in cfg["conjuntos"][c]}))
        if any(f["conjunto"] == dev for f in filas) and any(f["conjunto"] == prueba for f in filas):
            rutas["a"] = os.path.join(salida, "grafico_a_recall_falsas_alarmas.png")
            grafico_recall_falsas(filas, rutas["a"], dev, prueba, aviso(dev, prueba))
        amplio = _conjunto_amplio(filas)
        conjunto_c = prueba if any(f["conjunto"] == prueba for f in filas) else amplio
        rutas["b"], rutas["c"] = os.path.join(salida, "grafico_b_embudo.png"), os.path.join(salida, "grafico_c_recall_costo_tiempo.png")
        grafico_embudo(filas, rutas["b"], amplio, aviso(amplio))
        grafico_recall_costo_tiempo(filas, rutas["c"], conjunto_c, aviso(conjunto_c))
        ofertas_amplio = cfg["conjuntos"][amplio]
        completas = [n for n in evaluadas if _evs(evaluadas, n, ofertas_amplio)]
        rutas["d"], rutas["f"] = os.path.join(salida, "grafico_d_errores_por_criticidad.png"), os.path.join(salida, "grafico_f_confusion_clase.png")
        if not grafico_errores_por_criticidad(evaluadas, ofertas_amplio, completas, rutas["d"], amplio, aviso(amplio)):
            rutas.pop("d")
        if not grafico_confusion_clase(evaluadas, ofertas_amplio, completas, rutas["f"], amplio, aviso(amplio)):
            rutas.pop("f")
        if mapa:
            rutas["e"], rutas["b_reeval"] = os.path.join(salida, "grafico_e_recuperacion_antes_despues.png"), os.path.join(salida, "grafico_b_embudo_reeval.png")
            if not grafico_recuperacion_antes_despues(filas, rutas["e"], mapa, {c: cfg["conjuntos"][c] for c in (dev, prueba)}, evaluadas):
                rutas.pop("e")
            # el embudo de la reevaluación va al final: si el gris no es idéntico, GrisDistinto corta después de haber guardado todo lo demás
            if not grafico_embudo_reeval(filas, rutas["b_reeval"], amplio, [n for n in mapa], evaluadas, aviso(amplio)):
                rutas.pop("b_reeval")
    return {"filas": filas, "rutas": rutas}


def main(argv=None):
    p = argparse.ArgumentParser(description="Tabla comparativa y gráficos por configuración y conjunto de ofertas")
    p.add_argument("--config", required=True, help="JSON con las rutas de cada configuración y oferta")
    p.add_argument("--salida", default=None, help="carpeta de salida; por defecto la clave «salida» del config (relativa a la raíz del repo) o evaluacion/resultados_finales")
    p.add_argument("--sin-graficos", action="store_true")
    p.add_argument("--resolver", action="store_true", help="solo imprime la configuración con los «auto» resueltos (JSON en ASCII) y sale; lo usa cerrar_evaluacion.ps1")
    a = p.parse_args(argv)
    if a.resolver:
        print(json.dumps({"configuraciones": resolver_config(cargar_config(a.config))}, ensure_ascii=True))
        return None
    try:
        cfg = cargar_config(a.config)
        r = generar(cfg, carpeta_salida(cfg, a.salida), not a.sin_graficos)
    except GrisDistinto as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
    for ruta in r["rutas"].values():
        print(f"Guardado: {ruta}")
    return r


if __name__ == "__main__":
    main()
