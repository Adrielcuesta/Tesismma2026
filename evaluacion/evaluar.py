# evaluacion/evaluar.py
"""Evaluación determinista de un resultado contra el ground truth v3 y los espejos conformes.
Solo este módulo y los tests leen evaluacion/: nunca un prompt, el índice ni el pipeline.

Uso: python -m evaluacion.evaluar --resultado <json> --oferta P1 [--revision extras_revision.csv] [--comparar <json_sin_rag>]"""
import argparse
import csv
import datetime
import json
import os
import re
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
GROUND_TRUTH = os.path.join(AQUI, "ground_truth_v3.csv")
ESPEJOS = os.path.join(AQUI, "espejos_conformes.csv")
CLASES = ("Crítico", "Mayor", "Menor")
NO_EVALUABLE = "no evaluable (sin lineamientos)"
RE_PAR = re.compile(r"(NORM_\d{2})\s+(\d+\.\d+)")


def norm(texto) -> str:
    """Minúsculas, sin acentos y con espacios simples."""
    t = unicodedata.normalize("NFD", str(texto or ""))
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn").lower()).strip()


def leer_csv(ruta):
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            with open(ruta, encoding=codificacion, newline="") as f:
                return list(csv.DictReader(f, delimiter=";"))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo leer {ruta}")


def cargar_gt(oferta, ruta=GROUND_TRUTH):
    return [r for r in leer_csv(ruta) if r["oferta"] == oferta]


def cargar_espejos(oferta, ruta=ESPEJOS):
    numero = re.sub(r"\D", "", oferta)
    proyecto = f"Proyecto {numero}"
    return [r for r in leer_csv(ruta) if r["proyecto"].strip() == proyecto]


def es_modo_brechas(resultado) -> bool:
    return bool(resultado.get("registro_brechas")) or resultado.get("resumen_ejecutivo") is not None


def _articulo(a) -> str:
    return str(a or "").strip().rstrip(".").strip()


def pares_trampa(fila) -> set:
    """(norma, artículo) de la trampa y de sus artículos equivalentes ('NORM_04 3.22; NORM_04 3.25')."""
    pares = {(fila["norma"].strip(), _articulo(fila["articulo"]))}
    pares |= {(n, a) for n, a in RE_PAR.findall(fila.get("articulos_equivalentes") or "")}
    return pares


def pares_espejo(fila) -> set:
    return {(fila["norma"].strip(), _articulo(a)) for a in re.split(r"[;,]", fila["articulo"]) if a.strip()}


def _frase_espejo(fila) -> str:
    return norm(fila["cita_conforme"])[:60]


def _clave_extra(seccion, norma, articulo, cita) -> tuple:
    return (norm(seccion), norma, _articulo(articulo), norm(cita)[:80])


def evaluar(resultado, gt, espejos, oferta="P1") -> dict:
    """Métricas de un resultado. Con brechas (modo verificación) exige la frase y el artículo; sin brechas (modo lista) solo la frase."""
    brechas_modo = es_modo_brechas(resultado)
    if brechas_modo:
        items = [{"cita": norm(b.get("cita")), "norma": b.get("norma"), "articulo": _articulo(b.get("articulo")), "brecha": b}
                 for b in resultado.get("registro_brechas") or []]
    else:
        riesgos = resultado.get("riesgos_identificados_estructurados") or resultado.get("riesgos_identificados") or []
        items = [{"cita": norm(r.get("cita_oferta")), "norma": None, "articulo": None, "brecha": r} for r in riesgos]

    trampas, confusion = [], {}
    for fila in gt:
        frase, pares = norm(fila["fragmento_trampa"]), pares_trampa(fila)
        con_frase = [i for i in items if frase in i["cita"]]
        estrictas = [i for i in con_frase if (i["norma"], i["articulo"]) in pares] if brechas_modo else []
        if estrictas:
            elegida = next((i for i in estrictas if (i["norma"], i["articulo"]) == (fila["norma"].strip(), _articulo(fila["articulo"]))), estrictas[0])["brecha"]
            estado = "encontrada"
        elif con_frase:
            elegida, estado = con_frase[0]["brecha"], "otro artículo" if brechas_modo else "encontrada por frase"
        else:
            elegida, estado = None, "no"
        t = {"id": fila["id"], "estado": estado, "por_frase": bool(con_frase), "norma": fila["norma"], "articulo": fila["articulo"],
             "clase_esperada": fila["clase"], "responsable_esperado": fila["responsable"], "nivel_esperado": fila["nivel"],
             "clase_obtenida": None, "responsable_obtenido": None, "nivel_obtenido": None}
        if estado == "encontrada":
            t.update(clase_obtenida=elegida.get("clase"), responsable_obtenido=elegida.get("responsable"), nivel_obtenido=elegida.get("nivel"))
            confusion[(fila["clase"], elegida.get("clase"))] = confusion.get((fila["clase"], elegida.get("clase")), 0) + 1
        trampas.append(t)

    falsas, marcados = 0, []
    for e in espejos:
        frase, pares = _frase_espejo(e), pares_espejo(e)
        marcado = any(frase in i["cita"] and (not brechas_modo or (i["norma"], i["articulo"]) in pares) for i in items)
        falsas += marcado
        marcados.append({"seccion": e["seccion"], "cita": e["cita_conforme"], "norma": e["norma"], "articulo": e["articulo"], "marcado": marcado})

    extras = []
    if brechas_modo:
        for i in items:
            es_trampa = any(norm(f["fragmento_trampa"]) in i["cita"] and (i["norma"], i["articulo"]) in pares_trampa(f) for f in gt)
            es_espejo = any(_frase_espejo(e) in i["cita"] and (i["norma"], i["articulo"]) in pares_espejo(e) for e in espejos)
            if not es_trampa and not es_espejo:
                b = i["brecha"]
                extras.append({"oferta": oferta, "seccion": b.get("seccion_oferta") or b.get("seccion"), "norma": b.get("norma"), "articulo": b.get("articulo"),
                               "cita": b.get("cita"), "titulo": b.get("titulo"), "clase": b.get("clase"), "valido": ""})

    encontradas = [t for t in trampas if t["estado"] == "encontrada"]
    volumen = ({"brechas": len(items), "riesgos agrupados": len(resultado.get("riesgos") or []), "solicitudes": len(resultado.get("solicitudes") or []),
                "alertas": len(resultado.get("alertas") or [])} if brechas_modo else {"riesgos": len(items)})
    return {
        "modo": "brechas" if brechas_modo else "lista", "oferta": oferta, "n_trampas": len(trampas), "trampas": trampas,
        "encontradas": len(encontradas), "otro_articulo": sum(t["estado"] == "otro artículo" for t in trampas),
        "por_frase": sum(t["por_frase"] for t in trampas),
        "clase_ok": sum(t["clase_obtenida"] == t["clase_esperada"] for t in encontradas),
        "responsable_ok": sum(t["responsable_obtenido"] == t["responsable_esperado"] for t in encontradas),
        "nivel_ok": sum(t["nivel_obtenido"] == t["nivel_esperado"] for t in encontradas),
        "confusion": confusion, "n_espejos": len(espejos), "falsas_alarmas": falsas, "espejos": marcados,
        "extras": extras, "volumen": volumen, "n_riesgo": len(items), "precision": None}


def calcular_precision(ev, revision):
    """(trampas encontradas + extras válidos) / total de brechas que generan riesgo; None si falta revisar algún extra."""
    if not ev["n_riesgo"]:
        return None
    if not ev["extras"]:
        return ev["encontradas"] / ev["n_riesgo"]
    if not revision:
        return None
    por_clave = {_clave_extra(r.get("seccion"), r.get("norma"), r.get("articulo"), r.get("cita")): norm(r.get("valido")) for r in revision}
    valores = [por_clave.get(_clave_extra(x["seccion"], x["norma"], x["articulo"], x["cita"])) for x in ev["extras"]]
    if any(v not in ("si", "no") for v in valores):
        return None
    return (ev["encontradas"] + valores.count("si")) / ev["n_riesgo"]


def _pct(a, b) -> str:
    return f"{a}/{b} ({a / b:.0%})" if b else f"{a}/{b}"


def tabla_comparacion(con, sin) -> str:
    filas = [
        ("Trampas encontradas por frase", _pct(con["por_frase"], con["n_trampas"]), _pct(sin["por_frase"], sin["n_trampas"])),
        ("Falsas alarmas (por frase del espejo)", _pct(con["falsas_alarmas"], con["n_espejos"]), _pct(sin["falsas_alarmas"], sin["n_espejos"])),
        ("Recall estricto (frase y artículo)", _pct(con["encontradas"], con["n_trampas"]), "—"),
        ("Riesgos / brechas", str(con["volumen"].get("brechas", con["volumen"].get("riesgos"))), str(sin["volumen"].get("riesgos", sin["volumen"].get("brechas")))),
        ("Riesgos agrupados", str(con["volumen"].get("riesgos agrupados", "—")), "—"),
        ("Solicitudes", str(con["volumen"].get("solicitudes", "—")), "—"),
        ("Alertas", str(con["volumen"].get("alertas", "—")), "—"),
    ]
    return "| Métrica | Con RAG | Sin RAG |\n|---|---|---|\n" + "\n".join(f"| {a} | {b} | {c} |" for a, b, c in filas)


def informe_md(ev, comparacion=None) -> str:
    lista = ev["modo"] == "lista"
    L = [f"# Evaluación {ev['oferta']}", ""]
    if lista:
        L += ["> **Resultado en modo lista (sin brechas).** Se usa `riesgos_identificados_estructurados`: una trampa cuenta como "
              "«encontrada por frase» si la cita de algún riesgo contiene el fragmento de la trampa, sin exigir el artículo; las falsas alarmas "
              f"se cuentan por la frase del espejo, sin artículo. Clase, responsable y nivel: {NO_EVALUABLE}.", ""]
    n = ev["n_trampas"]
    resumen = [("Trampas encontradas por frase" if lista else "Trampas encontradas (frase y artículo)", _pct(ev["por_frase"] if lista else ev["encontradas"], n))]
    if lista:
        resumen += [("Clase correcta", NO_EVALUABLE), ("Responsable correcto", NO_EVALUABLE), ("Nivel correcto", NO_EVALUABLE)]
    else:
        e = ev["encontradas"]
        resumen += [("Encontradas con otro artículo (no suman al recall estricto)", str(ev["otro_articulo"])),
                    ("Clase correcta (de las encontradas)", _pct(ev["clase_ok"], e)), ("Responsable correcto (de las encontradas)", _pct(ev["responsable_ok"], e)),
                    ("Nivel correcto (de las encontradas)", _pct(ev["nivel_ok"], e))]
    resumen.append(("Falsas alarmas", _pct(ev["falsas_alarmas"], ev["n_espejos"])))
    if not lista:
        resumen.append(("Extras para revisar", str(len(ev["extras"]))))
        resumen.append(("Precisión", f"{ev['precision']:.0%}" if ev["precision"] is not None else "precisión pendiente de revisión"))
    resumen += [(f"Volumen: {k}", str(v)) for k, v in ev["volumen"].items()]
    L += ["| Métrica | Valor |", "|---|---|"] + [f"| {a} | {b} |" for a, b in resumen] + [""]
    if not lista:
        L += ["## Matriz de confusión de clase (filas: esperada; columnas: obtenida)", "", "| esperada \\ obtenida | " + " | ".join(CLASES) + " |", "|---|" + "---|" * len(CLASES)]
        L += [f"| {c} | " + " | ".join(str(ev["confusion"].get((c, o), 0)) for o in CLASES) + " |" for c in CLASES] + [""]
    L += ["## Detalle por trampa", "", "| Trampa | Encontrada | Clase esperada | Clase obtenida | Responsable esperado | Responsable obtenido | Nivel esperado | Nivel obtenido |", "|---|---|---|---|---|---|---|---|"]
    for t in ev["trampas"]:
        enc = {"encontrada": "sí", "otro artículo": "otro artículo", "encontrada por frase": "sí (por frase)", "no": "no"}[t["estado"]]
        obt = (lambda v: v if v is not None else ("—" if not lista else NO_EVALUABLE))
        L.append(f"| {t['id']} | {enc} | {t['clase_esperada']} | {obt(t['clase_obtenida'])} | {t['responsable_esperado']} | {obt(t['responsable_obtenido'])} | {t['nivel_esperado']} | {obt(t['nivel_obtenido'])} |")
    L.append("")
    if comparacion:
        L += ["## Comparación con la línea de base sin RAG", "", comparacion, ""]
    return "\n".join(L)


def guardar_detalle_csv(ev, ruta):
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["trampa", "encontrada", "norma", "articulo", "clase_esperada", "clase_obtenida", "responsable_esperado", "responsable_obtenido", "nivel_esperado", "nivel_obtenido"])
        for t in ev["trampas"]:
            w.writerow([t["id"], t["estado"], t["norma"], t["articulo"], t["clase_esperada"], t["clase_obtenida"] or "", t["responsable_esperado"],
                        t["responsable_obtenido"] or "", t["nivel_esperado"], t["nivel_obtenido"] or ""])


def guardar_extras_csv(ev, ruta):
    columnas = ["oferta", "seccion", "norma", "articulo", "cita", "titulo", "clase", "valido"]
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, delimiter=";")
        w.writeheader()
        w.writerows(ev["extras"])


def main(argv=None):
    p = argparse.ArgumentParser(description="Evalúa un resultado contra el ground truth v3 y los espejos conformes")
    p.add_argument("--resultado", required=True, help="JSON del resultado")
    p.add_argument("--oferta", required=True, help="P1, P2, P3 o P4")
    p.add_argument("--revision", help="extras_revision.csv con la columna 'valido' completa (sí/no)")
    p.add_argument("--comparar", metavar="JSON_SIN_RAG", help="resultado sin RAG: agrega la tabla con RAG / sin RAG")
    p.add_argument("--ground-truth", default=GROUND_TRUTH)
    p.add_argument("--espejos", default=ESPEJOS)
    a = p.parse_args(argv)

    with open(a.resultado, encoding="utf-8") as f:
        resultado = json.load(f)
    gt, espejos = cargar_gt(a.oferta, a.ground_truth), cargar_espejos(a.oferta, a.espejos)
    if not gt:
        raise SystemExit(f"No hay trampas de la oferta {a.oferta} en {a.ground_truth}")
    ev = evaluar(resultado, gt, espejos, a.oferta)
    ev["precision"] = calcular_precision(ev, leer_csv(a.revision) if a.revision else None) if ev["modo"] == "brechas" else None

    comparacion = None
    if a.comparar:
        with open(a.comparar, encoding="utf-8") as f:
            sin = evaluar(json.load(f), gt, espejos, a.oferta)
        comparacion = tabla_comparacion(ev, sin)

    carpeta, marca = os.path.dirname(os.path.abspath(a.resultado)), datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_md = os.path.join(carpeta, f"evaluacion_{a.oferta}_{marca}.md")
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(informe_md(ev, comparacion))
    guardar_detalle_csv(ev, os.path.join(carpeta, f"evaluacion_{a.oferta}_{marca}.csv"))
    if ev["modo"] == "brechas":
        guardar_extras_csv(ev, os.path.join(carpeta, "extras_revision.csv"))
    print(f"Evaluación guardada en {ruta_md}")
    if comparacion:
        print(comparacion)
    return ev


if __name__ == "__main__":
    main()
