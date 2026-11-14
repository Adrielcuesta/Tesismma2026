# evaluacion/diff_trampas.py
"""Diferencia trampa por trampa entre dos corridas cualesquiera sobre las mismas ofertas (por defecto Qwen3-32B de v1 contra Qwen3-32B con la recuperación elegida, P1–P4).
Sin LLM ni red: recalcula con evaluar.py y lee el registro técnico y las brechas de cada JSON. Solo este módulo, evaluar.py y los tests leen evaluacion/.

Uso:
  python -m evaluacion.diff_trampas [--config evaluacion/config_reeval.json] [--a <corrida>] [--b <corrida>] [--etiqueta-a v1] [--etiqueta-b elegida] [--salida <md>]
                                    [--casos P4-02-A P4-05-M P1-04-M] [--sin-oferta]
Una corrida es el nombre de una configuración del config (por ejemplo «gpt-oss-120b esfuerzo bajo (elegida)») o una lista OFERTA=ruta ("P1=<json>" "P2=<json>" ...).
Sin --a ni --b: «Qwen3-32B» (v1) contra «Qwen3-32B (elegida)» y el archivo evaluacion/resultados_reeval/diff_trampas_32b_v1_vs_elegida.md.

Para saber si la frase de la trampa estaba entre las oraciones que cita el verificador hace falta el texto de las oraciones de cada sección: el JSON no lo guarda (solo los IDs;
el verificador recibe la sección entera numerada), así que se vuelve a segmentar la oferta de datos/ProyectoAnalizar con la misma función del pipeline (evaluacion/oferta_texto.py).
--sin-oferta lo omite (la columna queda en «n/d»)."""
import argparse
import os
import re
import sys

from . import evaluar as E
from . import tabla_comparativa as T

A_DEFECTO, B_DEFECTO = "Qwen3-32B", "Qwen3-32B (elegida)"
ETIQUETAS_DEFECTO = ("v1", "elegida")
CONFIG = os.path.join(T.AQUI, "config_reeval.json")
CARPETA_SALIDA = os.path.join(T.AQUI, "resultados_reeval")
SALIDA = os.path.join(CARPETA_SALIDA, "diff_trampas_32b_v1_vs_elegida.md")
CASOS_DEFECTO = ("P4-02-A", "P4-05-M", "P1-04-M")
CATEGORIAS = ("encontrada", "perdida en clasificación", "perdida en verificación", "no recuperada", "otra causa", "n/d")
PARAMETROS = (("modelo_llm_usado", "Modelo"), ("temperature", "Temperatura"), ("seed", "Semilla"), ("thinking_verificacion", "Razonamiento en la verificación"),
              ("razonamiento_esfuerzo", "Esfuerzo de razonamiento (modelos con razonamiento fijo)"), ("verif_temperature", "Temperatura con razonamiento"),
              ("verif_top_p", "top_p con razonamiento"), ("verif_top_k", "top_k con razonamiento"), ("embedding_backend", "Embeddings de la recuperación"),
              ("perfil_recuperacion", "Perfil de recuperación"))
TOPE_CELDA = 600


def _celda(texto, tope: int = TOPE_CELDA) -> str:
    t = " ".join(str(texto or "").split()).replace("|", "/")
    return t if len(t) <= tope else t[:tope - 1] + "…"


def _orden_id(i) -> int:
    m = re.search(r"\d+", str(i))
    return int(m.group()) if m else 0


def _ids(ids) -> str:
    return ", ".join(sorted(ids, key=_orden_id)) or "—"


# --- Evidencia de una trampa en un resultado ---

def evidencia(resultado: dict, fila: dict) -> dict:
    """Lo que el resultado dice de una trampa: las entradas de verificación y de clasificación de su (sección, artículo), las brechas de ese par (con las vetadas por cálculo) y las
    que citan su frase. Mismo criterio de sección y par que evaluar.evaluar. «secciones» son los IDs de sección ('S3') que contienen la subsección de la trampa."""
    pares, frase = E.pares_trampa(fila), E.norm(fila["fragmento_trampa"])
    ids_sec = E._ids_secciones_de(fila["seccion"], resultado.get("secciones"))
    en_seccion = (lambda r: str(r.get("seccion")) in ids_sec) if ids_sec else (lambda r: E._id_seccion(r.get("seccion")) == E._id_seccion(fila["seccion"]))
    del_par = lambda r: en_seccion(r) and (r.get("norma"), E._articulo(r.get("articulo"))) in pares
    registro = resultado.get("registro_tecnico") or []
    brechas = resultado.get("registro_brechas") or []
    return {"secciones": ids_sec, "verificacion": [r for r in registro if not r.get("etapa") and r.get("veredicto") and del_par(r)],
            "clasificacion": [r for r in registro if r.get("etapa") == "clasificacion" and r.get("veredicto") and del_par(r)],
            "brechas_par": [b for b in brechas if del_par(b)],
            "brechas_frase": [b for b in brechas if frase in E.norm(b.get("cita")) and (b.get("norma"), E._articulo(b.get("articulo"))) in pares]}


def texto_verificacion(evid: dict) -> str:
    """Veredicto y explicación del verificador por cada entrada del par (puede haber varias: artículos equivalentes o partes)."""
    return "; ".join(f"{e.get('norma')} {e.get('articulo')}: {e['veredicto']}" + (f" (oraciones {_ids(e['oraciones'])})" if e.get("oraciones") else "")
                     + f" — {e.get('explicacion') or 'sin explicación'}" for e in evid["verificacion"]) or "no verificada"


def texto_clasificacion(evid: dict) -> str:
    return "; ".join(f"{e['veredicto']}" + (f" (regla {e['regla']})" if e.get("regla") else "") + (f" — {e['motivo']}" if e.get("motivo") else "") for e in evid["clasificacion"]) or "—"


def veredictos(evid: dict) -> str:
    return ", ".join(sorted({e["veredicto"] for e in evid["verificacion"]})) or "—"


def perdida_texto(t: dict) -> str:
    return t["perdida"] + (f" ({t['subcausa']})" if t.get("subcausa") else "")


def cifras_del_veto(evid: dict) -> str:
    """Cifras que extrajo el modelo en las brechas vetadas por cálculo del par (lo que decidió el veto)."""
    vetadas = [b for b in evid["brechas_par"] if b.get("estado") == E.ESTADO_DESCARTADA_CALCULO]
    return "; ".join(f"ofertado {c.get('valor_ofertado')} / exigido {c.get('valor_exigido')} / límite {c.get('tipo_limite')} / objeto {c.get('objeto_requisito')}"
                     f" / brecha relativa {b.get('brecha_relativa')}" for b in vetadas for c in [b.get("clasificacion") or {}]) or "—"


# --- ¿La frase de la trampa estaba entre las oraciones que cita el verificador? ---

def ids_de_la_frase(frase: str, oraciones: list):
    """IDs de las oraciones que ocupa la frase (más de una si cruza el corte entre oraciones), o None si no aparece. Compara solo alfanuméricos, así que no depende de
    espacios, '|' ni saltos de línea de las tablas."""
    alfanum = lambda t: "".join(c for c in E.norm(t) if c.isalnum())
    buscada = alfanum(frase)
    if not buscada:
        return None
    junto, duenos = "", []
    for id_, texto in oraciones:
        a = alfanum(texto)
        junto += a
        duenos += [id_] * len(a)
    i = junto.find(buscada)
    return set(duenos[i:i + len(buscada)]) if i >= 0 else None


def cobertura(frase: str, evid: dict, oraciones_por_seccion) -> dict:
    """{'estado': 'sí' | 'parcial' | 'no' | 'sin citas' | 'n/d', 'necesarias': IDs que ocupa la frase, 'citadas': IDs que citó el verificador, 'seccion'}.
    sí: algún veredicto del par cita todas las oraciones de la frase; parcial: cita algunas pero ninguno todas (típico cuando la frase cruza dos oraciones); no: cita otras;
    sin citas: el verificador no citó ninguna oración (lo normal en un Cumple); n/d: no hay texto de las oraciones o la frase no aparece en la sección."""
    if not oraciones_por_seccion:
        return {"estado": "n/d", "necesarias": set(), "citadas": set(), "seccion": None, "motivo": "sin el texto de las oraciones"}
    for sec in sorted(evid["secciones"], key=_orden_id):
        necesarias = ids_de_la_frase(frase, oraciones_por_seccion.get(sec) or [])
        if necesarias:
            break
    else:
        return {"estado": "n/d", "necesarias": set(), "citadas": set(), "seccion": None, "motivo": "la frase no aparece en las oraciones de la sección"}
    citadas = [set(e.get("oraciones") or []) for e in evid["verificacion"] if str(e.get("seccion")) == sec]
    union = set().union(*citadas) if citadas else set()
    if not union:
        estado = "sin citas"
    elif any(necesarias <= c for c in citadas):
        estado = "sí"
    elif necesarias & union:
        estado = "parcial"
    else:
        estado = "no"
    return {"estado": estado, "necesarias": necesarias, "citadas": union, "seccion": sec, "motivo": ""}


def consistencia_numeracion(resultado: dict, oraciones_por_seccion) -> tuple:
    """(coinciden, total) de las oraciones citadas por las brechas del resultado (el JSON guarda su texto) contra la numeración actual: si no coinciden, el JSON se numeró con
    otra versión de la segmentación y los IDs no son comparables."""
    if not oraciones_por_seccion:
        return 0, 0
    ok = total = 0
    for b in resultado.get("registro_brechas") or []:
        textos = dict(oraciones_por_seccion.get(str(b.get("seccion"))) or [])
        for id_, texto in (b.get("oraciones_texto") or {}).items():
            total += 1
            ok += E.norm(textos.get(id_)) == E.norm(texto)
    return ok, total


# --- Carga ---

def parsear_corrida(valores: list, por_defecto: str, cfg: dict):
    """(nombre de la corrida, {oferta: ruta}) a partir de los argumentos: un nombre de configuración del config, o una lista OFERTA=ruta."""
    valores = valores or [por_defecto]
    if all("=" in v for v in valores):
        return " + ".join(valores), dict(v.split("=", 1) for v in valores)
    if len(valores) > 1 or valores[0] not in cfg["configuraciones"]:
        raise SystemExit(f"«{' '.join(valores)}» no es una configuración del config ni una lista OFERTA=ruta. Configuraciones: {', '.join(cfg['configuraciones'])}")
    return valores[0], T.resolver_config({"configuraciones": {valores[0]: cfg["configuraciones"][valores[0]]}})[valores[0]]


def cargar_corrida(nombre: str, rutas: dict, ofertas: list) -> dict:
    """{oferta: {resultado, gt, ev, ruta}}; error si falta algún JSON."""
    salida = {}
    for oferta in ofertas:
        ruta = rutas.get(oferta)
        if not ruta or not os.path.isfile(ruta):
            raise SystemExit(f"{nombre} / {oferta}: no hay JSON en «{ruta}».")
        resultado, gt = E._cargar(ruta), E.cargar_gt(oferta)
        salida[oferta] = {"resultado": resultado, "gt": gt, "ev": E.evaluar(resultado, gt, E.cargar_espejos(oferta), oferta), "ruta": ruta}
    return salida


def construir_filas(a: dict, b: dict, ofertas: list, oraciones: dict = None) -> list:
    """Una fila por trampa: evaluación, evidencia y cobertura de la frase en cada corrida. oraciones: {oferta: {id de sección: [(id, texto)]}} o None."""
    filas = []
    for o in ofertas:
        por_seccion = (oraciones or {}).get(o)
        for fila, ta, tb in zip(a[o]["gt"], a[o]["ev"]["trampas"], b[o]["ev"]["trampas"]):
            if not (fila["id"] == ta["id"] == tb["id"]):
                raise SystemExit(f"{o}: las trampas no coinciden entre las dos corridas ({ta['id']} / {tb['id']}).")
            f = {"oferta": o, "id": fila["id"], "norma": fila["norma"].strip(), "articulo": E._articulo(fila["articulo"]), "frase": fila["fragmento_trampa"], "a": ta, "b": tb,
                 "ev_a": evidencia(a[o]["resultado"], fila), "ev_b": evidencia(b[o]["resultado"], fila), "oraciones": por_seccion}
            f["cob_a"], f["cob_b"] = cobertura(fila["fragmento_trampa"], f["ev_a"], por_seccion), cobertura(fila["fragmento_trampa"], f["ev_b"], por_seccion)
            filas.append(f)
    return filas


def parametros_md(a: dict, b: dict, etiquetas: tuple, nombres: tuple, oraciones: dict) -> list:
    """Temperatura, semilla y demás parámetros que guardó cada corrida (por oferta, sin repetir valores iguales); «no guardada» si el JSON no los trae."""
    def valor(corrida, clave):
        vistos = []
        for o, d in corrida.items():
            v = (d["resultado"].get("configuracion_analisis") or {}).get(clave, "no guardada")
            if f"{v}" not in vistos:
                vistos.append(f"{v}")
        return " / ".join(vistos)
    L = ["## Parámetros de cada corrida", "", f"| Parámetro | {etiquetas[0]} | {etiquetas[1]} |", "|---|---|---|", f"| Corrida | {_celda(nombres[0])} | {_celda(nombres[1])} |"]
    L += [f"| {titulo} | {valor(a, clave)} | {valor(b, clave)} |" for clave, titulo in PARAMETROS]
    if oraciones:
        cons = [consistencia_numeracion(c[o]["resultado"], oraciones.get(o)) for c in (a, b) for o in c]
        n = len(a)
        ca, cb = cons[:n], cons[n:]
        L.append(f"| Numeración de oraciones igual a la actual (oraciones citadas por brechas) | {sum(x for x, _ in ca)}/{sum(y for _, y in ca)} | {sum(x for x, _ in cb)}/{sum(y for _, y in cb)} |")
    return L + ["", "La temperatura y la semilla que se guardan son las que se configuraron en el cliente (`temperature` y `seed` de configuracion_analisis); el JSON no dice si el proveedor de la API "
                    "las aplicó (las corridas en la nube las mandan con la semilla de config.OLLAMA_SEED).", ""]


# --- Informe ---

def _cuenta(filas: list, lado: str, categoria: str) -> int:
    return sum(f[lado]["perdida"] == categoria for f in filas)


def resumen_md(filas: list, conjuntos: dict, etiquetas: tuple) -> list:
    encabezado = ["Conjunto", "Trampas", f"Recall estricto ({etiquetas[0]} → {etiquetas[1]})", f"Techo del sistema ({etiquetas[0]} → {etiquetas[1]})", f"Llegan al verificador ({etiquetas[0]} → {etiquetas[1]})",
                  "No recuperadas", "Vetadas por cálculo", "Descartadas por regla 2.5", "Perdida en verificación", "Perdida en clasificación", "Otra causa (total)"]
    L = ["## Resumen por conjunto", "", "Techo del sistema = trampas − no recuperadas − vetadas por cálculo − descartadas por regla 2.5: lo máximo que lograría un verificador perfecto con esa "
         "recuperación (el recall estricto no puede pasarlo).", "", "| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    for nombre, ofertas in conjuntos.items():
        fs = [f for f in filas if f["oferta"] in ofertas]
        if not fs:
            continue
        par = lambda c: f"{_cuenta(fs, 'a', c)} → {_cuenta(fs, 'b', c)}"
        sub = lambda s: f"{sum(f['a'].get('subcausa') == s for f in fs)} → {sum(f['b'].get('subcausa') == s for f in fs)}"
        llegan = lambda lado: sum(f[lado]["verificado"] for f in fs)
        techo = lambda lado: (E.techo_del_sistema([f[lado] for f in fs]) or {}).get("techo", "n/d")
        L.append("| " + " | ".join([nombre, str(len(fs)), par("encontrada"), f"{techo('a')} → {techo('b')}", f"{llegan('a')} → {llegan('b')}", par("no recuperada"), sub(E.SUBCAUSAS[0]),
                                    sub(E.SUBCAUSAS[1]), par("perdida en verificación"), par("perdida en clasificación"), par("otra causa")]) + " |")
    return L + [""]


def subcausas_md(filas: list, etiquetas: tuple) -> list:
    L = ["## «Otra causa» por subcausa", "", "Desglose informativo (evaluar.subcausa_otra_causa); no cambia la definición de «encontrada» ni del recall estricto.", "",
         f"| Subcausa | {etiquetas[0]} | {etiquetas[1]} |", "|---|---|---|"]
    L += [f"| {s} | {sum(f['a'].get('subcausa') == s for f in filas)} | {sum(f['b'].get('subcausa') == s for f in filas)} |" for s in E.SUBCAUSAS]
    return L + [""]


def transiciones_md(filas: list, conjuntos: dict, etiquetas: tuple) -> list:
    """Cuántas trampas pasaron de cada categoría de la corrida A a cada categoría de la B, por conjunto, con sus ids."""
    pares = {}
    for f in filas:
        pares.setdefault((f["a"]["perdida"], f["b"]["perdida"]), []).append(f)
    orden = sorted(pares, key=lambda p: (p[0] == p[1], CATEGORIAS.index(p[0]) if p[0] in CATEGORIAS else 99, CATEGORIAS.index(p[1]) if p[1] in CATEGORIAS else 99))
    encabezado = [etiquetas[0], etiquetas[1], "Total", *conjuntos, "Trampas"]
    L = [f"## Transiciones de pérdida ({etiquetas[0]} → {etiquetas[1]})", "", "Primero las que cambian, después las que quedan igual.", "", "| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    for p in orden:
        fs = pares[p]
        L.append("| " + " | ".join([p[0], p[1] + ("" if p[0] != p[1] else " (igual)"), str(len(fs)), *[str(sum(f["oferta"] in of for f in fs)) for of in conjuntos.values()],
                                    ", ".join(f["id"] for f in fs)]) + " |")
    return L + [""]


def _en_verificacion(f: dict) -> bool:
    return "perdida en verificación" in (f["a"]["perdida"], f["b"]["perdida"])


def tabla_md(filas: list, etiquetas: tuple) -> list:
    encabezado = ["Trampa", "Artículo", f"Pérdida en {etiquetas[0]}", f"Pérdida en {etiquetas[1]}", f"Frase en lo que citó el verificador ({etiquetas[0]} → {etiquetas[1]}; solo si se perdió en verificación)",
                  f"Veredicto del verificador ({etiquetas[0]} → {etiquetas[1]})", "Explicación del verificador (donde cambia)"]
    L = ["## Trampa por trampa", "", "| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    for f in filas:
        cambia = f["a"]["perdida"] != f["b"]["perdida"]
        cob = f"{f['cob_a']['estado']} → {f['cob_b']['estado']}" if _en_verificacion(f) else ""
        if cambia:
            expl = f"**{etiquetas[1]}:** {_celda(texto_verificacion(f['ev_b']))}" + (f"<br>**{etiquetas[0]}:** {_celda(texto_verificacion(f['ev_a']))}" if f["ev_a"]["verificacion"]
                                                                                       else f"<br>**{etiquetas[0]}:** no llegó al verificador")
            ver = f"{veredictos(f['ev_a'])} → {veredictos(f['ev_b'])}"
        else:
            expl, ver = "", ""
        L.append(f"| {f['id']} | {f['norma']} {f['articulo']} | {perdida_texto(f['a'])} | {perdida_texto(f['b'])}{' **(cambia)**' if cambia else ''} | {cob} | {ver} | {expl} |")
    return L + [""]


def ganadas_perdidas_md(filas: list, etiquetas: tuple) -> list:
    """Las trampas que cambian de «encontrada» en una corrida a otra cosa en la otra: lo que explica el delta del recall estricto."""
    ganadas = [f for f in filas if f["a"]["perdida"] != "encontrada" and f["b"]["perdida"] == "encontrada"]
    perdidas = [f for f in filas if f["a"]["perdida"] == "encontrada" and f["b"]["perdida"] != "encontrada"]
    L = ["## Trampas ganadas y perdidas (recall estricto)", "", f"Ganadas en {etiquetas[1]}: {len(ganadas)}. Perdidas en {etiquetas[1]}: {len(perdidas)}. Neto: {len(ganadas) - len(perdidas):+d}.", ""]
    for titulo, grupo, lado_otro in ((f"Ganadas (no encontradas en {etiquetas[0]}, encontradas en {etiquetas[1]})", ganadas, "a"),
                                     (f"Perdidas (encontradas en {etiquetas[0]}, no encontradas en {etiquetas[1]})", perdidas, "b")):
        L += [f"### {titulo}", ""]
        if not grupo:
            L += ["Ninguna.", ""]
            continue
        L += ["| Trampa | Artículo | Pérdida en la otra corrida | Veredicto del verificador (" + f"{etiquetas[0]} → {etiquetas[1]}" + ") |", "|---|---|---|---|"]
        L += [f"| {f['id']} | {f['norma']} {f['articulo']} | {perdida_texto(f[lado_otro])} | {veredictos(f['ev_a'])} → {veredictos(f['ev_b'])} |" for f in grupo]
        L.append("")
    return L


def evidencia_md(filas: list, etiquetas: tuple, casos: tuple) -> list:
    """Las trampas perdidas en verificación en alguna de las dos corridas: ¿la frase estaba entre las oraciones que citó el verificador? Separa «el modelo eligió otra oración»
    (no / parcial) de «el modelo no citó nada» (sin citas) y de «no se puede saber» (n/d)."""
    L = ["## Perdidas en verificación: ¿la frase estaba en lo que citó el verificador?", "",
         "El verificador recibe la **sección entera** numerada (`seccion_numerada`), así que la frase de la trampa siempre estaba en el prompt salvo que la segmentación la corte en dos oraciones. "
         "Lo que el JSON permite separar es otra cosa: si el modelo **citó** las oraciones de la frase. **sí**: cita todas las oraciones que ocupa la frase; **parcial**: solo algunas "
         "(la frase cruza dos oraciones); **no**: cita otras (oración distractora); **sin citas**: no citó ninguna (lo normal en un Cumple); **n/d**: no se pudo calcular.", ""]
    perdidas = [f for f in filas if _en_verificacion(f)]
    if not perdidas:
        return L + ["Ninguna trampa se perdió en verificación en estas corridas.", ""]
    encabezado = ["Trampa", "Artículo", "Corrida", "Pérdida", "Veredicto", "Oraciones de la frase", "Oraciones citadas", "¿La frase estaba en lo citado?"]
    L += ["| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    resumen = {}
    for f in perdidas:
        for lado, etiqueta in (("a", etiquetas[0]), ("b", etiquetas[1])):
            c, t = f[f"cob_{lado}"], f[lado]
            if t["perdida"] == "perdida en verificación":
                resumen[(etiqueta, c["estado"])] = resumen.get((etiqueta, c["estado"]), 0) + 1
            L.append(f"| {f['id']} | {f['norma']} {f['articulo']} | {etiqueta} | {t['perdida']} | {veredictos(f['ev_' + lado])} | {_ids(c['necesarias'])} | {_ids(c['citadas'])} | {c['estado']}"
                     + (f" ({c['motivo']})" if c["motivo"] else "") + " |")
    L += ["", "Cuántas de las perdidas en verificación caen en cada caso:", "", "| Corrida | sí | parcial | no | sin citas | n/d |", "|---|---|---|---|---|---|"]
    for etiqueta in etiquetas:
        L.append(f"| {etiqueta} | " + " | ".join(str(resumen.get((etiqueta, e), 0)) for e in ("sí", "parcial", "no", "sin citas", "n/d")) + " |")
    L.append("")
    elegidos = [f for f in filas if f["id"] in casos]
    if elegidos:
        L += ["### Casos señalados", ""]
        for f in elegidos:
            L += [f"#### {f['id']} · {f['norma']} {f['articulo']}", "", f"Frase de la trampa: «{_celda(f['frase'], 300)}»", ""]
            textos = dict((f["oraciones"] or {}).get(f["cob_b"]["seccion"] or f["cob_a"]["seccion"]) or [])
            for lado, etiqueta in (("a", etiquetas[0]), ("b", etiquetas[1])):
                c = f[f"cob_{lado}"]
                L.append(f"- **{etiqueta}** ({perdida_texto(f[lado])}): frase en {_ids(c['necesarias'])}; citó {_ids(c['citadas'])} → **{c['estado']}**. {_celda(texto_verificacion(f['ev_' + lado]), 400)}")
            for i in sorted(set(f["cob_a"]["necesarias"]) | set(f["cob_b"]["necesarias"]) | set(f["cob_a"]["citadas"]) | set(f["cob_b"]["citadas"]), key=_orden_id):
                if textos.get(i):
                    L.append(f"  - {i}: {_celda(textos[i], 300)}")
            L.append("")
    return L


def otra_causa_md(filas: list, lado: str, etiqueta: str) -> list:
    """Las trampas en «otra causa» de una corrida, con su subcausa y, si fue vetada por cálculo, las cifras que extrajo el modelo."""
    otras = [f for f in filas if f[lado]["perdida"] == "otra causa"]
    L = [f"## «Otra causa» en {etiqueta}", "", f"{len(otras)} trampas: el artículo llegó al verificador, la verificación dijo Incumple o Revisar y la clasificación no la descartó como CUMPLE/NO_APLICA, "
         "pero ninguna brecha cita la frase de la trampa con su artículo.", ""]
    if not otras:
        return L + ["Ninguna.", ""]
    encabezado = ["Trampa", "Artículo", "Subcausa", "Verificación", "Clasificación", "Cifras extraídas (si fue vetada por cálculo)", "Cita de la brecha del par"]
    L += ["| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    for f in otras:
        e = f["ev_" + lado]
        citas = "; ".join(_celda(b.get("cita"), 200) + (f" [{b['estado']}]" if b.get("estado") else "") for b in e["brechas_par"]) or "—"
        L.append(f"| {f['id']} | {f['norma']} {f['articulo']} | {f[lado]['subcausa']} | {_celda(texto_verificacion(e))} | {_celda(texto_clasificacion(e), 300)} | "
                 f"{cifras_del_veto(e) if f[lado]['subcausa'] == E.SUBCAUSAS[0] else '—'} | {citas} |")
    return L + [""]


def informe_md(filas: list, conjuntos: dict, etiquetas: tuple, nombres: tuple, a: dict = None, b: dict = None, oraciones: dict = None, casos: tuple = ()) -> str:
    L = [f"# Diferencia trampa por trampa: {etiquetas[0]} contra {etiquetas[1]}", "", f"- {etiquetas[0]}: {nombres[0]}", f"- {etiquetas[1]}: {nombres[1]}", "",
         "Categorías de pérdida de evaluar.py: **encontrada** (brecha con la frase y el artículo); **no recuperada** (el artículo no llegó al verificador); **perdida en verificación** "
         "(llegó y se dijo Cumple o No aplica); **perdida en clasificación** (se dijo Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE); **otra causa** (verificada como "
         "Incumple o Revisar y clasificada como riesgo, pero ninguna brecha cita la frase de la trampa con su artículo), desglosada en subcausas.", ""]
    L += parametros_md(a, b, etiquetas, nombres, oraciones) if a and b else []
    return "\n".join(L + resumen_md(filas, conjuntos, etiquetas) + subcausas_md(filas, etiquetas) + transiciones_md(filas, conjuntos, etiquetas) + ganadas_perdidas_md(filas, etiquetas)
                     + evidencia_md(filas, etiquetas, casos) + otra_causa_md(filas, "a", etiquetas[0]) + otra_causa_md(filas, "b", etiquetas[1]) + tabla_md(filas, etiquetas))


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")


def main(argv=None):
    p = argparse.ArgumentParser(description="Diferencia trampa por trampa entre dos corridas")
    p.add_argument("--config", default=CONFIG)
    p.add_argument("--a", nargs="+", help=f"corrida A: nombre de una configuración del config o OFERTA=ruta (por defecto «{A_DEFECTO}»)")
    p.add_argument("--b", nargs="+", help=f"corrida B (por defecto «{B_DEFECTO}»)")
    p.add_argument("--etiqueta-a", help="etiqueta de A en el informe (por defecto «v1» si no se da --a; si no, el nombre de la corrida)")
    p.add_argument("--etiqueta-b", help="etiqueta de B en el informe (por defecto «elegida» si no se da --b; si no, el nombre de la corrida)")
    p.add_argument("--salida", help="markdown de salida (por defecto el de v1 contra elegida, o diff_trampas_<a>_vs_<b>.md en resultados_reeval)")
    p.add_argument("--casos", nargs="*", default=list(CASOS_DEFECTO), help="trampas con detalle de oraciones")
    p.add_argument("--sin-oferta", action="store_true", help="no vuelve a segmentar las ofertas: la columna de cobertura queda en n/d")
    args = p.parse_args(argv)
    cfg = T.cargar_config(args.config)
    conjuntos = cfg["conjuntos"]
    ofertas = sorted({o for of in conjuntos.values() for o in of})
    nombre_a, rutas_a = parsear_corrida(args.a, A_DEFECTO, cfg)
    nombre_b, rutas_b = parsear_corrida(args.b, B_DEFECTO, cfg)
    etiquetas = (args.etiqueta_a or (ETIQUETAS_DEFECTO[0] if not args.a else nombre_a), args.etiqueta_b or (ETIQUETAS_DEFECTO[1] if not args.b else nombre_b))
    a, b = cargar_corrida(nombre_a, rutas_a, ofertas), cargar_corrida(nombre_b, rutas_b, ofertas)
    oraciones = None
    if not args.sin_oferta:
        from . import oferta_texto
        oraciones = {o: oferta_texto.oraciones_por_seccion(o) for o in ofertas}
    filas = construir_filas(a, b, ofertas, oraciones)
    por_defecto = not args.a and not args.b
    salida = args.salida or (SALIDA if por_defecto else os.path.join(CARPETA_SALIDA, f"diff_trampas_{_slug(etiquetas[0])}_vs_{_slug(etiquetas[1])}.md"))
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        f.write(informe_md(filas, conjuntos, etiquetas, (nombre_a, nombre_b), a, b, oraciones, tuple(args.casos)) + "\n")
    print(f"Guardado: {salida}", file=sys.stderr)
    return filas


if __name__ == "__main__":
    main()
