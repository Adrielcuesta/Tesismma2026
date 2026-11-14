# evaluacion/diff_trampas.py
"""Diferencia trampa por trampa entre dos configuraciones sobre las mismas ofertas (por defecto Qwen3-32B de v1 y Qwen3-32B con la recuperación elegida, P1–P4).
Sin LLM ni red: recalcula con evaluar.py y lee el registro técnico y las brechas de cada JSON. Solo este módulo, evaluar.py y los tests leen evaluacion/.

Uso:
  python -m evaluacion.diff_trampas [--config evaluacion/config_reeval.json] [--v1 "Qwen3-32B"] [--elegida "Qwen3-32B (elegida)"] [--salida <md>]
Escribe evaluacion/resultados_reeval/diff_trampas_32b_v1_vs_elegida.md: resumen por conjunto, transiciones de pérdida v1 → elegida, la tabla de las trampas
(id, artículo, pérdida en cada una; veredicto y explicación del verificador donde cambia), las trampas ganadas y perdidas, y el detalle de «otra causa» en la elegida."""
import argparse
import os
import sys

from . import evaluar as E
from . import tabla_comparativa as T

V1, ELEGIDA = "Qwen3-32B", "Qwen3-32B (elegida)"
CONFIG = os.path.join(T.AQUI, "config_reeval.json")
SALIDA = os.path.join(T.AQUI, "resultados_reeval", "diff_trampas_32b_v1_vs_elegida.md")
CATEGORIAS = ("encontrada", "perdida en clasificación", "perdida en verificación", "no recuperada", "otra causa", "n/d")
TOPE_CELDA = 600


def _celda(texto, tope: int = TOPE_CELDA) -> str:
    t = " ".join(str(texto or "").split()).replace("|", "/")
    return t if len(t) <= tope else t[:tope - 1] + "…"


def evidencia(resultado: dict, fila: dict) -> dict:
    """Lo que el resultado dice de una trampa: las entradas de verificación y de clasificación de su (sección, artículo), las brechas de ese par y las que citan su frase
    (con cualquier artículo). Mismo criterio de sección y par que evaluar.evaluar."""
    pares, frase = E.pares_trampa(fila), E.norm(fila["fragmento_trampa"])
    ids_sec = E._ids_secciones_de(fila["seccion"], resultado.get("secciones"))
    en_seccion = (lambda r: str(r.get("seccion")) in ids_sec) if ids_sec else (lambda r: E._id_seccion(r.get("seccion")) == E._id_seccion(fila["seccion"]))
    del_par = lambda r: en_seccion(r) and (r.get("norma"), E._articulo(r.get("articulo"))) in pares
    registro = resultado.get("registro_tecnico") or []
    brechas = resultado.get("registro_brechas") or []
    return {"verificacion": [r for r in registro if not r.get("etapa") and r.get("veredicto") and del_par(r)],
            "clasificacion": [r for r in registro if r.get("etapa") == "clasificacion" and r.get("veredicto") and del_par(r)],
            "brechas_par": [b for b in brechas if del_par(b)],
            "brechas_frase": [b for b in brechas if frase in E.norm(b.get("cita")) and (b.get("norma"), E._articulo(b.get("articulo"))) in pares]}


def motivo_otra_causa(t: dict, evid: dict) -> str:
    """Por qué una trampa verificada como Incumple/Revisar y clasificada como riesgo no quedó como brecha que cite su frase y su artículo."""
    if t["como_alerta"]:
        return "salió como alerta, no como brecha"
    if any(b.get("estado") == E.ESTADO_DESCARTADA_CALCULO for b in evid["brechas_frase"] + evid["brechas_par"]):
        return "la brecha fue descartada por cálculo"
    if t["estado"] == "otro artículo":
        return f"la brecha con la frase cita otro artículo ({t['articulo_citado']})"
    if evid["brechas_par"]:
        return "hay brecha en el par, pero su cita no contiene la frase de la trampa"
    return "ninguna brecha para el par: la clasificación no la convirtió en riesgo"


def texto_verificacion(evid: dict) -> str:
    """Veredicto y explicación del verificador por cada entrada del par (puede haber varias: artículos equivalentes o partes)."""
    return "; ".join(f"{e.get('norma')} {e.get('articulo')}: {e['veredicto']}" + (f" (oraciones {', '.join(map(str, e['oraciones']))})" if e.get("oraciones") else "")
                     + f" — {e.get('explicacion') or 'sin explicación'}" for e in evid["verificacion"]) or "no verificada"


def texto_clasificacion(evid: dict) -> str:
    return "; ".join(f"{e['veredicto']}" + (f" (regla {e['regla']})" if e.get("regla") else "") + (f" — {e['motivo']}" if e.get("motivo") else "") for e in evid["clasificacion"]) or "—"


def veredictos(evid: dict) -> str:
    return ", ".join(sorted({e["veredicto"] for e in evid["verificacion"]})) or "—"


def cargar_configuracion(cfg: dict, nombre: str, ofertas: list) -> dict:
    """{oferta: {resultado, gt, ev}} de una configuración del config; error si falta algún JSON."""
    if nombre not in cfg["configuraciones"]:
        raise SystemExit(f"La configuración «{nombre}» no está en el config.")
    rutas = T.resolver_config({"configuraciones": {nombre: cfg["configuraciones"][nombre]}})[nombre]
    salida = {}
    for oferta in ofertas:
        ruta = rutas.get(oferta)
        if not ruta or not os.path.isfile(ruta):
            raise SystemExit(f"{nombre} / {oferta}: no hay JSON en «{ruta}».")
        resultado, gt = E._cargar(ruta), E.cargar_gt(oferta)
        salida[oferta] = {"resultado": resultado, "gt": gt, "ev": E.evaluar(resultado, gt, E.cargar_espejos(oferta), oferta), "ruta": ruta}
    return salida


def construir_filas(v1: dict, el: dict, ofertas: list) -> list:
    """Una fila por trampa: la evaluación y la evidencia de cada configuración."""
    filas = []
    for o in ofertas:
        for fila, tv, te in zip(v1[o]["gt"], v1[o]["ev"]["trampas"], el[o]["ev"]["trampas"]):
            if not (fila["id"] == tv["id"] == te["id"]):
                raise SystemExit(f"{o}: las trampas no coinciden entre las dos configuraciones ({tv['id']} / {te['id']}).")
            filas.append({"oferta": o, "id": fila["id"], "norma": fila["norma"].strip(), "articulo": E._articulo(fila["articulo"]), "v1": tv, "el": te,
                          "ev_v1": evidencia(v1[o]["resultado"], fila), "ev_el": evidencia(el[o]["resultado"], fila)})
    return filas


def _cuenta(filas: list, lado: str, categoria: str) -> int:
    return sum(f[lado]["perdida"] == categoria for f in filas)


def resumen_md(filas: list, conjuntos: dict, nombres: tuple) -> list:
    encabezado = ["Conjunto", "Trampas", "Encontradas (v1 → elegida)", "Llegan al verificador (v1 → elegida)", "Gris: no recuperada", "Perdida en verificación", "Perdida en clasificación", "Otra causa"]
    L = ["## Resumen por conjunto", "", f"v1 = {nombres[0]}; elegida = {nombres[1]}.", "", "| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    for nombre, ofertas in conjuntos.items():
        fs = [f for f in filas if f["oferta"] in ofertas]
        if not fs:
            continue
        par = lambda c: f"{_cuenta(fs, 'v1', c)} → {_cuenta(fs, 'el', c)}"
        llegan = lambda lado: sum(f[lado]["verificado"] for f in fs)
        L.append("| " + " | ".join([nombre, str(len(fs)), par("encontrada"), f"{llegan('v1')} → {llegan('el')}", par("no recuperada"), par("perdida en verificación"),
                                    par("perdida en clasificación"), par("otra causa")]) + " |")
    return L + [""]


def transiciones_md(filas: list, conjuntos: dict) -> list:
    """Cuántas trampas pasaron de cada categoría de v1 a cada categoría de la elegida, por conjunto, con sus ids."""
    pares = {}
    for f in filas:
        pares.setdefault((f["v1"]["perdida"], f["el"]["perdida"]), []).append(f)
    orden = sorted(pares, key=lambda p: (p[0] == p[1], CATEGORIAS.index(p[0]) if p[0] in CATEGORIAS else 99, CATEGORIAS.index(p[1]) if p[1] in CATEGORIAS else 99))
    encabezado = ["v1", "elegida", "Total", *conjuntos, "Trampas"]
    L = ["## Transiciones de pérdida (v1 → elegida)", "", "Primero las que cambian, después las que quedan igual.", "", "| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    for p in orden:
        fs = pares[p]
        L.append("| " + " | ".join([p[0], p[1] + ("" if p[0] != p[1] else " (igual)"), str(len(fs)), *[str(sum(f["oferta"] in of for f in fs)) for of in conjuntos.values()],
                                    ", ".join(f["id"] for f in fs)]) + " |")
    return L + [""]


def tabla_md(filas: list) -> list:
    encabezado = ["Trampa", "Artículo", "Pérdida en v1", "Pérdida en la elegida", "Veredicto del verificador (v1 → elegida)", "Explicación del verificador (donde cambia)"]
    L = ["## Trampa por trampa", "", "| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    for f in filas:
        cambia = f["v1"]["perdida"] != f["el"]["perdida"]
        if cambia:
            expl = f"**elegida:** {_celda(texto_verificacion(f['ev_el']))}" + (f"<br>**v1:** {_celda(texto_verificacion(f['ev_v1']))}" if f["ev_v1"]["verificacion"] else "<br>**v1:** no llegó al verificador")
            ver = f"{veredictos(f['ev_v1'])} → {veredictos(f['ev_el'])}"
        else:
            expl, ver = "", ""
        L.append(f"| {f['id']} | {f['norma']} {f['articulo']} | {f['v1']['perdida']} | {f['el']['perdida']}{' **(cambia)**' if cambia else ''} | {ver} | {expl} |")
    return L + [""]


def ganadas_perdidas_md(filas: list) -> list:
    """Las trampas que cambian de «encontrada» en una configuración a otra cosa en la otra: lo que explica el delta del recall estricto."""
    ganadas = [f for f in filas if f["v1"]["perdida"] != "encontrada" and f["el"]["perdida"] == "encontrada"]
    perdidas = [f for f in filas if f["v1"]["perdida"] == "encontrada" and f["el"]["perdida"] != "encontrada"]
    L = ["## Trampas ganadas y perdidas (recall estricto)", "", f"Ganadas con la elegida: {len(ganadas)}. Perdidas con la elegida: {len(perdidas)}. Neto: {len(ganadas) - len(perdidas):+d}.", ""]
    for titulo, grupo, lado_otro in (("Ganadas (no encontradas en v1, encontradas en la elegida)", ganadas, "v1"), ("Perdidas (encontradas en v1, no encontradas en la elegida)", perdidas, "el")):
        L += [f"### {titulo}", ""]
        if not grupo:
            L += ["Ninguna.", ""]
            continue
        L += ["| Trampa | Artículo | Pérdida en la otra | Veredicto del verificador (v1 → elegida) |", "|---|---|---|---|"]
        L += [f"| {f['id']} | {f['norma']} {f['articulo']} | {f[lado_otro]['perdida']} | {veredictos(f['ev_v1'])} → {veredictos(f['ev_el'])} |" for f in grupo]
        L.append("")
    return L


def otra_causa_md(filas: list) -> list:
    """Las trampas en «otra causa» de la elegida: verificadas como Incumple/Revisar y clasificadas como riesgo, pero sin brecha que cite frase y artículo."""
    otras = [f for f in filas if f["el"]["perdida"] == "otra causa"]
    L = ["## «Otra causa» en la elegida", "", f"{len(otras)} trampas: el artículo llegó al verificador, la verificación dijo Incumple o Revisar y la clasificación no la descartó, pero ninguna brecha cita la frase de la trampa con su artículo.", ""]
    if not otras:
        return L + ["Ninguna.", ""]
    motivos = {}
    for f in otras:
        motivos.setdefault(motivo_otra_causa(f["el"], f["ev_el"]), []).append(f["id"])
    L += ["| Motivo | n | Trampas |", "|---|---|---|"] + [f"| {m} | {len(ids)} | {', '.join(ids)} |" for m, ids in motivos.items()] + [""]
    encabezado = ["Trampa", "Artículo", "Pérdida en v1", "Verificación (elegida)", "Clasificación (elegida)", "Motivo", "Cita de la brecha del par"]
    L += ["| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    for f in otras:
        e = f["ev_el"]
        citas = "; ".join(_celda(b.get("cita"), 200) + (f" [{b['estado']}]" if b.get("estado") else "") for b in e["brechas_par"]) or "—"
        L.append(f"| {f['id']} | {f['norma']} {f['articulo']} | {f['v1']['perdida']} | {_celda(texto_verificacion(e))} | {_celda(texto_clasificacion(e), 300)} | {motivo_otra_causa(f['el'], e)} | {citas} |")
    return L + [""]


def informe_md(filas: list, conjuntos: dict, nombres: tuple) -> str:
    L = [f"# Diferencia trampa por trampa: {nombres[0]} (v1) contra {nombres[1]}", "",
         "Categorías de pérdida de evaluar.py: **encontrada** (brecha con la frase y el artículo); **no recuperada** (el artículo no llegó al verificador); **perdida en verificación** "
         "(llegó y se dijo Cumple o No aplica); **perdida en clasificación** (se dijo Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE); **otra causa** (verificada como "
         "Incumple o Revisar y clasificada como riesgo, pero ninguna brecha cita la frase de la trampa con su artículo).", ""]
    return "\n".join(L + resumen_md(filas, conjuntos, nombres) + transiciones_md(filas, conjuntos) + ganadas_perdidas_md(filas) + otra_causa_md(filas) + tabla_md(filas))


def main(argv=None):
    p = argparse.ArgumentParser(description="Diferencia trampa por trampa entre dos configuraciones del config de la reevaluación")
    p.add_argument("--config", default=CONFIG)
    p.add_argument("--v1", default=V1, help="configuración de referencia (v1)")
    p.add_argument("--elegida", default=ELEGIDA, help="configuración con la recuperación elegida")
    p.add_argument("--salida", default=SALIDA)
    a = p.parse_args(argv)
    cfg = T.cargar_config(a.config)
    conjuntos = cfg["conjuntos"]
    ofertas = sorted({o for of in conjuntos.values() for o in of})
    v1, el = cargar_configuracion(cfg, a.v1, ofertas), cargar_configuracion(cfg, a.elegida, ofertas)
    filas = construir_filas(v1, el, ofertas)
    os.makedirs(os.path.dirname(a.salida), exist_ok=True)
    with open(a.salida, "w", encoding="utf-8") as f:
        f.write(informe_md(filas, conjuntos, (a.v1, a.elegida)) + "\n")
    print(f"Guardado: {a.salida}", file=sys.stderr)
    return filas


if __name__ == "__main__":
    main()
