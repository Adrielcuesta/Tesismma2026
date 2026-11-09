# evaluacion/evaluar.py
"""Evaluación determinista de un resultado contra el ground truth v3 y los espejos conformes. Sin LLM.
Solo este módulo y los tests leen evaluacion/: nunca un prompt, el índice ni el pipeline.

Uso:
  python -m evaluacion.evaluar --resultado <json> --oferta P1 [--revision extras_revision.csv]
         [--comparar <json_sin_rag>] [--revision-sinrag sinrag_coincidencias.csv]
  python -m evaluacion.evaluar --agregado <json_P1> <json_P2> ... [--comparar <json_sin_rag_P1> <json_sin_rag_P2> ...]
         [--revision-sinrag <csv> ...]
La oferta de cada JSON de --agregado y --comparar se toma de su ruta (P1, P2...) o se indica como P2=ruta.
Los extras de cada JSON van a <json>_extras.csv (la revisión humana, columna 'valido') y el juez a <json>_juez.csv, junto al JSON; con --agregado se leen de ahí."""
import argparse
import csv
import datetime
import json
import math
import os
import re
import sys
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
GROUND_TRUTH = os.path.join(AQUI, "ground_truth_v3.csv")
ESPEJOS = os.path.join(AQUI, "espejos_conformes.csv")
CLASES = ("Crítico", "Mayor", "Menor")   # de mayor a menor, para el kappa ponderado
NIVELES = ("Alto", "Medio", "Bajo")
ESTADO_DESCARTADA_CALCULO = "descartada por cálculo"
ESTADO_ALERTA_SIN_RESPUESTA = "tiempo_agotado"   # no es una alerta de contradicción: el modelo no respondió
JUEZ_VEREDICTOS = ("VALIDA", "NO_VALIDA", "DUDOSA")
NO_EVALUABLE = "no evaluable (sin lineamientos)"
MARCA_NO_VERIFICADO = "valor no verificado"
RE_PAR = re.compile(r"(NORM_\d{2})\s+(\d+\.\d+)")
NOTA_SIN_RAG = ("Nota: la columna sin RAG usa «por frase», un criterio más laxo que el de la columna con RAG: "
                "la diferencia es una cota inferior del aporte del RAG.")
NOTA_FIDELIDAD = "La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas."


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


def _id_seccion(texto) -> str:
    """Número de la sección de nivel superior: '3.5 Plazo' -> '3'; 'S3' -> '3'."""
    m = re.match(r"\D*(\d+)", str(texto or ""))
    return m.group(1) if m else norm(texto)


def _numero_subseccion(texto):
    m = re.match(r"\s*(\d+(?:\.\d+)*)", str(texto or ""))
    return m.group(1) if m else None


def _ids_secciones_de(subseccion, secciones) -> set:
    """IDs de las secciones de la oferta ('S10') cuyos títulos contienen la subsección de la trampa ('5.1 Plazo'), según resultado['secciones'].
    Coincide por número de subsección (o uno de sus descendientes) o por el título sin '(parte n)'."""
    n, t = _numero_subseccion(subseccion), norm(subseccion).split(" (parte ")[0]
    ids = set()
    for s in secciones or []:
        for titulo in s.get("titulos") or []:
            m = _numero_subseccion(titulo)
            if (n and m and (m == n or m.startswith(n + "."))) or norm(titulo).split(" (parte ")[0] == t:
                ids.add(str(s.get("id")))
    return ids


# --- Estadística sin dependencias ---

def wilson(k, n, z=1.96):
    """Intervalo de confianza de Wilson (95 % con z=1.96) para k éxitos de n; None si n == 0."""
    if not n:
        return None
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centro - margen), min(1.0, centro + margen)


def f_beta(precision, recall, beta):
    """F-beta; None si falta la precisión. F2 pondera más el recall (un desvío no detectado cuesta más que una falsa alarma)."""
    if precision is None or recall is None:
        return None
    b2 = beta * beta
    return 0.0 if precision == 0 and recall == 0 else (1 + b2) * precision * recall / (b2 * precision + recall)


def kappa_ponderado_cuadratico(confusion, clases=CLASES):
    """Kappa con pesos cuadráticos entre la clase esperada (filas) y la obtenida (columnas); `clases` va de mayor a menor.
    confusion: {(esperada, obtenida): n}. None si no hay datos o el acuerdo esperado por azar es perfecto (denominador 0)."""
    k = len(clases)
    n = sum(confusion.values())
    if not n or k < 2:
        return None
    peso = lambda i, j: (i - j) ** 2 / (k - 1) ** 2
    obs = [[confusion.get((clases[i], clases[j]), 0) for j in range(k)] for i in range(k)]
    filas, cols = [sum(f) for f in obs], [sum(obs[i][j] for i in range(k)) for j in range(k)]
    num = sum(peso(i, j) * obs[i][j] for i in range(k) for j in range(k))
    den = sum(peso(i, j) * filas[i] * cols[j] / n for i in range(k) for j in range(k))
    return None if den == 0 else 1 - num / den


def mcnemar_exacto(n10, n01):
    """Prueba exacta de McNemar (binomial con p = 0,5 sobre los pares discordantes), bilateral. n10: acierta solo A; n01: acierta solo B."""
    n = n10 + n01
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(n10, n01) + 1)) / 2 ** n)


# --- Evaluación de un resultado ---

def evaluar(resultado, gt, espejos, oferta="P1") -> dict:
    """Métricas de un resultado. Con brechas (modo verificación) exige la frase y el artículo; sin brechas (modo lista) solo la frase."""
    brechas_modo = es_modo_brechas(resultado)
    if brechas_modo:
        # las brechas descartadas por cálculo (contradicción con las cifras) no generan riesgo: no cuentan como riesgos
        items = [{"cita": norm(b.get("cita")), "norma": b.get("norma"), "articulo": _articulo(b.get("articulo")), "brecha": b}
                 for b in resultado.get("registro_brechas") or [] if b.get("estado") != ESTADO_DESCARTADA_CALCULO]
    else:
        riesgos = resultado.get("riesgos_identificados_estructurados") or resultado.get("riesgos_identificados") or []
        items = [{"cita": norm(r.get("cita_oferta")), "norma": None, "articulo": None, "brecha": r} for r in riesgos]
    # pares (sección, artículo) que la verificación revisó, con su veredicto; las entradas de la etapa de clasificación no cuentan
    verificados = [r for r in (resultado.get("registro_tecnico") or []) if not r.get("etapa") and r.get("veredicto")]
    clasificados = [r for r in (resultado.get("registro_tecnico") or []) if r.get("etapa") == "clasificacion" and r.get("veredicto")]

    alertas = [{"cita": norm(a.get("cita")), "norma": a.get("norma"), "articulo": _articulo(a.get("articulo"))}
               for a in resultado.get("alertas") or [] if a.get("estado") != ESTADO_ALERTA_SIN_RESPUESTA]
    trampas, confusion, coincidencias = [], {}, []
    for fila in gt:
        frase, pares = norm(fila["fragmento_trampa"]), pares_trampa(fila)
        con_frase = [i for i in items if frase in i["cita"]]
        estrictas = [i for i in con_frase if (i["norma"], i["articulo"]) in pares] if brechas_modo else []
        citado = ""
        if estrictas:
            elegida = next((i for i in estrictas if (i["norma"], i["articulo"]) == (fila["norma"].strip(), _articulo(fila["articulo"]))), estrictas[0])["brecha"]
            estado = "encontrada"
        elif con_frase:
            elegida, estado = con_frase[0]["brecha"], "otro artículo" if brechas_modo else "encontrada por frase"
            if brechas_modo:
                citado = f"{con_frase[0]['norma']} Art. {con_frase[0]['articulo']}"
        else:
            elegida, estado = None, "no"
        if not brechas_modo:
            coincidencias += [{"trampa": fila["id"], "frase": fila["fragmento_trampa"], "descripcion": i["brecha"].get("descripcion_riesgo") or "",
                               "cita": i["brecha"].get("cita_oferta") or ""} for i in con_frase]
        # la sección S# que contiene la subsección de la trampa; sin resultado['secciones'] se compara por el número de nivel superior
        ids_sec = _ids_secciones_de(fila["seccion"], resultado.get("secciones"))
        en_seccion = (lambda r: str(r.get("seccion")) in ids_sec) if ids_sec else (lambda r: _id_seccion(r.get("seccion")) == _id_seccion(fila["seccion"]))
        revisados = [r for r in verificados if en_seccion(r) and (r.get("norma"), _articulo(r.get("articulo"))) in pares]
        reclasificados = [r for r in clasificados if en_seccion(r) and (r.get("norma"), _articulo(r.get("articulo"))) in pares]
        como_alerta = brechas_modo and any(frase in a["cita"] and (a["norma"], a["articulo"]) in pares for a in alertas)
        veredictos = {norm(r["veredicto"]) for r in revisados}
        # pereza de verificación: el artículo llegó a la sección y la verificación dijo solo Cumple o No aplica
        pereza_v = bool(revisados) and estado != "encontrada" and veredictos <= {"cumple", "no aplica"}
        # pereza de clasificación: la verificación dijo Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE
        pereza_c = (estado != "encontrada" and bool(veredictos & {"incumple", "revisar"})
                    and any(norm(r["veredicto"]).replace("_", " ") in ("no aplica", "cumple") for r in reclasificados))
        if estado == "encontrada":
            perdida = "encontrada"
        elif not verificados:
            perdida = "n/d"
        elif not revisados:
            perdida = "no recuperada"
        elif pereza_v:
            perdida = "perdida en verificación"
        elif pereza_c:
            perdida = "perdida en clasificación"
        else:
            perdida = "otra causa"   # verificada como Incumple o Revisar y clasificada como riesgo, pero ninguna brecha cita la trampa (o se descartó)
        t = {"id": fila["id"], "estado": estado, "como_alerta": bool(como_alerta), "por_frase": bool(con_frase), "norma": fila["norma"], "articulo": fila["articulo"],
             "articulo_citado": citado, "verificado": bool(revisados), "perezosa": pereza_v, "perezosa_clasificacion": pereza_c, "perdida": perdida,
             "veredicto_verificacion": ", ".join(sorted({r["veredicto"] for r in revisados})) or "—",
             "veredicto_clasificacion": ", ".join(sorted({r["veredicto"] for r in reclasificados})) or "—",
             "por_frase_validada": None,
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
        "encontradas": len(encontradas), "solo_alerta": sum(t["estado"] != "encontrada" and t["como_alerta"] for t in trampas), "otro_articulo": sum(t["estado"] == "otro artículo" for t in trampas),
        "por_frase": sum(t["por_frase"] for t in trampas), "por_frase_validada": None, "coincidencias": coincidencias,
        "costo": (resultado.get("configuracion_analisis") or {}).get("costo_computacional"), "hay_registro": bool(verificados), "recall_articulo": sum(t["verificado"] for t in trampas), "perezosas": sum(t["perezosa"] for t in trampas),
        "perezosas_clasificacion": sum(t["perezosa_clasificacion"] for t in trampas),
        "marcas_no_verificadas": sum(any(norm(m).startswith(MARCA_NO_VERIFICADO) for m in (i["brecha"].get("marcas") or [])) for i in items) if brechas_modo else 0,
        "clase_ok": sum(t["clase_obtenida"] == t["clase_esperada"] for t in encontradas),
        "responsable_ok": sum(t["responsable_obtenido"] == t["responsable_esperado"] for t in encontradas),
        "nivel_ok": sum(t["nivel_obtenido"] == t["nivel_esperado"] for t in encontradas),
        "confusion": confusion, "n_espejos": len(espejos), "falsas_alarmas": falsas, "espejos": marcados,
        "extras": extras, "volumen": volumen, "n_riesgo": len(items), "precision": None, "precision_k": None, "precision_n": None,
        "juez": None, "pares_juez_humano": []}


def conteo_precision(ev, revision):
    """(trampas encontradas + extras válidos, brechas que generan riesgo); None si falta revisar algún extra."""
    if not ev["n_riesgo"]:
        return None
    if not ev["extras"]:
        return ev["encontradas"], ev["n_riesgo"]
    if not revision:
        return None
    por_clave = {_clave_extra(r.get("seccion"), r.get("norma"), r.get("articulo"), r.get("cita")): norm(r.get("valido")) for r in revision}
    valores = [por_clave.get(_clave_extra(x["seccion"], x["norma"], x["articulo"], x["cita"])) for x in ev["extras"]]
    if any(v not in ("si", "no") for v in valores):
        return None
    return ev["encontradas"] + valores.count("si"), ev["n_riesgo"]


def calcular_precision(ev, revision):
    """(trampas encontradas + extras válidos) / total de brechas que generan riesgo; None si falta revisar algún extra."""
    c = conteo_precision(ev, revision)
    return c[0] / c[1] if c else None


def asignar_precision(ev, revision):
    c = conteo_precision(ev, revision) if ev["modo"] == "brechas" else None
    ev["precision_k"], ev["precision_n"] = c if c else (None, None)
    ev["precision"] = c[0] / c[1] if c else None


def revision_con_marcas_juez(revision, juez_rows):
    """Revisión humana de los extras: <json>_extras.csv, con las marcas «valido» que se volcaron en <json>_juez.csv por encima."""
    por_clave = {_clave_extra(r.get("seccion"), r.get("norma"), r.get("articulo"), r.get("cita")): r for r in revision or []}
    for r in juez_rows or []:
        c = _clave_extra(r.get("seccion"), r.get("norma"), r.get("articulo"), r.get("cita"))
        if c not in por_clave:
            por_clave[c] = r
        elif norm(r.get("valido")) in ("si", "no"):
            por_clave[c] = {**por_clave[c], "valido": r["valido"]}
    return list(por_clave.values())


def cohen_kappa(pares):
    """Kappa de Cohen entre dos evaluadores binarios; pares: [(a, b)] de booleanos. None si no hay datos o el acuerdo esperado por azar es 1."""
    n = len(pares)
    if not n:
        return None
    po = sum(a == b for a, b in pares) / n
    pa, pb = sum(a for a, _ in pares) / n, sum(b for _, b in pares) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def asignar_juez(ev, juez_rows, revision):
    """Precisión según el juez externo: estricta (DUDOSA cuenta como no válida) y amplia (DUDOSA cuenta como válida), siempre (trampas encontradas + extras
    válidos) / brechas que generan riesgo. `juez` queda en None si algún extra no tiene veredicto. pares_juez_humano: (veredicto, válido según el humano)
    de los extras marcados por ambos. `revision`: filas con la columna humana 'valido'."""
    ev["juez"], ev["pares_juez_humano"] = None, []
    if ev["modo"] != "brechas" or not ev["n_riesgo"]:
        return
    clave = lambda r: _clave_extra(r.get("seccion"), r.get("norma"), r.get("articulo"), r.get("cita"))
    juez = {clave(r): str(r.get("juez_veredicto") or "").strip().upper() for r in juez_rows or []}
    humano = {clave(r): norm(r.get("valido")) for r in revision or []}
    claves = [clave(x) for x in ev["extras"]]
    veredictos = [juez.get(c) for c in claves]
    ev["pares_juez_humano"] = [(v, humano[c] == "si") for c, v in zip(claves, veredictos) if v in JUEZ_VEREDICTOS and humano.get(c) in ("si", "no")]
    if any(v not in JUEZ_VEREDICTOS for v in veredictos):
        return
    ev["juez"] = {"estricta": ev["encontradas"] + veredictos.count("VALIDA"), "amplia": ev["encontradas"] + veredictos.count("VALIDA") + veredictos.count("DUDOSA"),
                  "n": ev["n_riesgo"]}


def aplicar_revision_sinrag(ev, revision):
    """Línea de base sin RAG: una trampa cuenta como encontrada por frase solo si alguna de sus coincidencias está marcada «sí».
    Si falta revisar alguna coincidencia, no se valida nada (por_frase_validada queda en None)."""
    por_clave = {(r.get("trampa"), norm(r.get("cita"))[:80]): norm(r.get("valido")) for r in revision or []}
    valores = [por_clave.get((c["trampa"], norm(c["cita"])[:80])) for c in ev["coincidencias"]]
    if not revision or any(v not in ("si", "no") for v in valores):
        return
    validas = {c["trampa"] for c, v in zip(ev["coincidencias"], valores) if v == "si"}
    for t in ev["trampas"]:
        t["por_frase_validada"] = t["id"] in validas
    ev["por_frase_validada"] = len(validas)


def combinar(evs):
    """Suma las evaluaciones de varias ofertas (todas en el mismo modo): las métricas se calculan sobre el total de trampas."""
    if len(evs) == 1:
        return evs[0]
    suma = lambda k: sum(e[k] for e in evs)
    todo = lambda k: None if any(e[k] is None for e in evs) else suma(k)
    confusion, volumen = {}, {}
    for e in evs:
        for k, v in e["confusion"].items():
            confusion[k] = confusion.get(k, 0) + v
        for k, v in e["volumen"].items():
            volumen[k] = volumen.get(k, 0) + v
    ev = {k: suma(k) for k in ("n_trampas", "encontradas", "solo_alerta", "otro_articulo", "por_frase", "recall_articulo", "perezosas", "perezosas_clasificacion", "marcas_no_verificadas",
                               "clase_ok", "responsable_ok", "nivel_ok", "n_espejos", "falsas_alarmas", "n_riesgo")}
    ev.update(modo=evs[0]["modo"], oferta="+".join(e["oferta"] for e in evs), costos=[(e["oferta"], e["costo"]) for e in evs], confusion=confusion, volumen=volumen,
              trampas=[t for e in evs for t in e["trampas"]], espejos=[x for e in evs for x in e["espejos"]], extras=[x for e in evs for x in e["extras"]],
              coincidencias=[x for e in evs for x in e["coincidencias"]], hay_registro=all(e["hay_registro"] for e in evs),
              por_frase_validada=todo("por_frase_validada"), precision_k=todo("precision_k"), precision_n=todo("precision_n"))
    ev["precision"] = ev["precision_k"] / ev["precision_n"] if ev["precision_n"] else None
    ev["juez"] = None if any(e["juez"] is None for e in evs) else {k: sum(e["juez"][k] for e in evs) for k in ("estricta", "amplia", "n")}
    ev["pares_juez_humano"] = [x for e in evs for x in e["pares_juez_humano"]]
    return ev


def comparar_mcnemar(con, sin):
    """Pareada por trampa: con RAG (estricto: frase y artículo) contra sin RAG (por frase, validada si hay revisión).
    Devuelve (solo con RAG, solo sin RAG, p exacto bilateral)."""
    por_id = {t["id"]: t for t in sin["trampas"]}
    n10 = n01 = 0
    for t in con["trampas"]:
        o = por_id.get(t["id"])
        a = t["estado"] == "encontrada"
        b = bool(o and (o["por_frase_validada"] if o["por_frase_validada"] is not None else o["por_frase"]))
        n10 += a and not b
        n01 += b and not a
    return int(n10), int(n01), mcnemar_exacto(n10, n01)


# --- Informe ---

def _pct(a, b) -> str:
    return f"{a}/{b} ({a / b:.0%})" if b else f"{a}/{b}"


def _con_ic(k, n) -> str:
    w = wilson(k, n)
    return f"{_pct(k, n)}, IC 95 % {w[0]:.0%}–{w[1]:.0%}" if w else _pct(k, n)


def _sin_valor(v, f="{:.2f}") -> str:
    return f.format(v) if v is not None else "n/d"


def tabla_comparacion(con, sin, mcnemar=None) -> str:
    """Con RAG: recall estricto (frase y artículo). Sin RAG: por frase (validada si hay revisión), un criterio más laxo."""
    n = con["n_trampas"]
    if sin["por_frase_validada"] is not None:
        sin_enc = _pct(sin["por_frase_validada"], sin["n_trampas"]) + " por frase, validadas"
    else:
        sin_enc = _pct(sin["por_frase"], sin["n_trampas"]) + " por frase, sin validar"
    filas = [
        ("Trampas encontradas", _pct(con["encontradas"], n) + " (frase y artículo)", sin_enc),
        ("Falsas alarmas (por frase del espejo)", _pct(con["falsas_alarmas"], con["n_espejos"]), _pct(sin["falsas_alarmas"], sin["n_espejos"])),
        ("Riesgos / brechas", str(con["volumen"].get("brechas", con["volumen"].get("riesgos"))), str(sin["volumen"].get("riesgos", sin["volumen"].get("brechas")))),
        ("Riesgos agrupados", str(con["volumen"].get("riesgos agrupados", "—")), "—"),
        ("Solicitudes", str(con["volumen"].get("solicitudes", "—")), "—"),
        ("Alertas", str(con["volumen"].get("alertas", "—")), "—"),
    ]
    texto = "| Métrica | Con RAG | Sin RAG |\n|---|---|---|\n" + "\n".join(f"| {a} | {b} | {c} |" for a, b, c in filas) + f"\n\n{NOTA_SIN_RAG}"
    if mcnemar:
        texto += (f"\n\nPrueba exacta de McNemar (pareada por trampa): solo con RAG {mcnemar[0]}, solo sin RAG {mcnemar[1]}, p = {mcnemar[2]:.4f}.")
    return texto


PERDIDAS = ("no recuperada", "perdida en verificación", "perdida en clasificación", "otra causa", "encontrada")


def _bloque_falsas_y_volumen(ev):
    L = ["## Falsas alarmas", "", "| Métrica | Valor |", "|---|---|", f"| Espejos marcados | {_con_ic(ev['falsas_alarmas'], ev['n_espejos'])} |", "",
         "## Volumen", "", "| Concepto | Cantidad |", "|---|---|"]
    return L + [f"| {k.capitalize()} | {v} |" for k, v in ev["volumen"].items()] + [""]


def recall_por(trampas, campo, orden) -> list:
    """[(valor esperado, n, encontradas como riesgo, encontradas como riesgo o alerta)] por el valor esperado de `campo`; primero `orden`, después el resto."""
    valores = list(orden) + sorted({t[campo] for t in trampas} - set(orden))
    filas = []
    for v in valores:
        grupo = [t for t in trampas if t[campo] == v]
        if grupo:
            riesgo = sum(t["estado"] == "encontrada" for t in grupo)
            filas.append((v, len(grupo), riesgo, riesgo + sum(t["estado"] != "encontrada" and t["como_alerta"] for t in grupo)))
    return filas


def _bloque_recall_por_categoria(ev):
    L = []
    for titulo, campo, orden in (("Recall por clase esperada", "clase_esperada", CLASES), ("Recall por nivel esperado", "nivel_esperado", NIVELES)):
        L += [f"## {titulo}", "", "| Esperada | Trampas | Solo riesgos | Riesgos + alertas |", "|---|---|---|---|"]
        L += [f"| {v} | {n} | {_pct(r, n)} | {_pct(ra, n)} |" for v, n, r, ra in recall_por(ev["trampas"], campo, orden)] + [""]
    return L


def _bloque_perdidas(ev):
    """Dónde se pierde cada trampa: no recuperada / perdida en verificación / perdida en clasificación / encontrada (y otra causa)."""
    if not ev["hay_registro"]:
        return ["## Dónde se pierde cada trampa", "", "n/d (el resultado no trae registro técnico)", ""]
    cuentas = {k: sum(t["perdida"] == k for t in ev["trampas"]) for k in PERDIDAS}
    L = ["## Dónde se pierde cada trampa", "", "| Etapa | Trampas |", "|---|---|"] + [f"| {k} | {_pct(v, ev['n_trampas'])} |" for k, v in cuentas.items() if v or k != "otra causa"]
    L += ["", "| Trampa no encontrada | Dónde se pierde | Artículo | Veredicto de verificación | Veredicto de clasificación |", "|---|---|---|---|---|"]
    L += [f"| {t['id']} | {t['perdida']} | {t['norma']} Art. {t['articulo']} | {t['veredicto_verificacion']} | {t['veredicto_clasificacion']} |"
          for t in ev["trampas"] if t["perdida"] != "encontrada"]
    return L + [""]


def _segundos_texto(s) -> str:
    return "n/d" if s is None else f"{s:,.1f} s ({int(s) // 3600}:{int(s) % 3600 // 60:02d}:{int(s) % 60:02d})".replace(",", "X").replace(".", ",").replace("X", ".")


def _bloque_costo(ev):
    """Costo computacional por oferta, tal como lo midió el análisis (configuracion_analisis.costo_computacional)."""
    L = ["## Costo computacional", ""]
    for oferta, c in ev.get("costos") or [(ev["oferta"], ev.get("costo"))]:
        if not c:
            L += [f"**{oferta}**: n/d (el resultado no trae la medición)", ""]
            continue
        hw, pp = c.get("hardware") or {}, c.get("segundos_por_par") or {}
        n = lambda v: "n/d" if v is None else f"{v:,.0f}".replace(",", ".")
        L += [f"**{oferta}**", "", "| Concepto | Valor |", "|---|---|", f"| Modelo | {c.get('modelo', 'n/d')} |",
              f"| Hardware | {hw.get('gpu') or 'n/d'}" + (f", {hw['vram']}" if hw.get("vram") else "") + " |",
              f"| Pares verificados | {c.get('pares_verificados', 'n/d')} |", f"| Llamadas totales (con comentario y reintentos) | {c.get('llamadas_totales', 'n/d')} |",
              f"| Tiempo total | {_segundos_texto(c.get('tiempo_total_s'))} |",
              f"| Segundos por par (mediana / p90) | {_sin_valor(pp.get('mediana'), '{:.1f}')} / {_sin_valor(pp.get('p90'), '{:.1f}')} |",
              f"| Tokens de entrada (total / por par) | {n(c.get('tokens_entrada_total'))} / {n(c.get('tokens_entrada_por_par'))} |",
              f"| Tokens de salida (total / por par) | {n(c.get('tokens_salida_total'))} / {n(c.get('tokens_salida_por_par'))} |", ""]
    return L


def informe_md(ev, comparacion=None) -> str:
    lista = ev["modo"] == "lista"
    n, e = ev["n_trampas"], ev["encontradas"]
    L = [f"# Evaluación {ev['oferta']}", ""]
    if lista:
        L += ["> **Resultado en modo lista (sin brechas).** Una trampa cuenta como «encontrada por frase» si la cita de algún riesgo contiene el "
              f"fragmento de la trampa, sin exigir el artículo. Clase, responsable y nivel: {NO_EVALUABLE}.", ""]
        L += ["## Detección", "", "| Métrica | Valor |", "|---|---|", f"| Trampas encontradas por frase | {_con_ic(ev['por_frase'], n)} |"]
        if ev["por_frase_validada"] is not None:
            L.append(f"| Trampas encontradas por frase, validadas | {_con_ic(ev['por_frase_validada'], n)} |")
        L.append("")
        L += _bloque_falsas_y_volumen(ev)
    else:
        recall = e / n if n else None
        L += ["## Recuperación", "", "| Métrica | Valor |", "|---|---|",
              "| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | "
              + (_con_ic(ev["recall_articulo"], n) if ev["hay_registro"] else "n/d (el resultado no trae registro técnico)") + " |", ""]
        L += ["## Detección", "", "| Métrica | Valor |", "|---|---|", f"| Recall solo riesgos (frase y artículo) | {_con_ic(e, n)} |",
              f"| Recall riesgos + alertas (la alerta de contradicción cita la frase y el artículo) | {_con_ic(e + ev['solo_alerta'], n)} |"]
        if ev["precision_n"]:
            L.append(f"| Precisión | {_con_ic(ev['precision_k'], ev['precision_n'])} |")
        else:
            L.append("| Precisión | precisión pendiente de revisión |")
        L += [f"| F1 | {_sin_valor(f_beta(ev['precision'], recall, 1))} |", f"| F2 | {_sin_valor(f_beta(ev['precision'], recall, 2))} |"]
        if ev.get("juez"):
            for nombre, k in (("estricta (DUDOSA = no válida)", ev["juez"]["estricta"]), ("amplia (DUDOSA = válida)", ev["juez"]["amplia"])):
                p_juez = k / ev["juez"]["n"]
                L += [f"| Precisión según el juez, {nombre} | {_con_ic(k, ev['juez']['n'])} |",
                      f"| F1 / F2 según el juez, {nombre} | {_sin_valor(f_beta(p_juez, recall, 1))} / {_sin_valor(f_beta(p_juez, recall, 2))} |"]
        if ev.get("pares_juez_humano"):
            pares = ev["pares_juez_humano"]
            ke, ka = cohen_kappa([(v == "VALIDA", h) for v, h in pares]), cohen_kappa([(v != "NO_VALIDA", h) for v, h in pares])
            L.append(f"| Acuerdo juez–humano (kappa de Cohen, {len(pares)} extras marcados por ambos) | estricta {_sin_valor(ke)}; amplia {_sin_valor(ka)} |")
        L += [
              "| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | "
              + (_pct(ev["perezosas"], n) if ev["hay_registro"] else "n/d") + " |",
              "| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | "
              + (_pct(ev["perezosas_clasificacion"], n) if ev["hay_registro"] else "n/d") + " |", ""]
        L += ["## Clasificación (de las trampas encontradas)", "", "| Métrica | Valor |", "|---|---|",
              f"| Exactitud de clase | {_pct(ev['clase_ok'], e)} |",
              f"| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | {_sin_valor(kappa_ponderado_cuadratico(ev['confusion']))} |",
              f"| Responsable correcto | {_pct(ev['responsable_ok'], e)} |", ""]
        L += ["Matriz de confusión de clase (filas: esperada; columnas: obtenida)", "", "| esperada \\ obtenida | " + " | ".join(CLASES) + " |", "|---|" + "---|" * len(CLASES)]
        L += [f"| {c} | " + " | ".join(str(ev["confusion"].get((c, o), 0)) for o in CLASES) + " |" for c in CLASES] + [""]
        nb = ev["volumen"].get("brechas", 0)
        L += ["## Fidelidad", "", "| Métrica | Valor |", "|---|---|", f"| Brechas con alguna marca «{MARCA_NO_VERIFICADO}» | {_pct(ev['marcas_no_verificadas'], nb)} |", "",
              NOTA_FIDELIDAD, ""]
        L += _bloque_recall_por_categoria(ev) + _bloque_falsas_y_volumen(ev) + _bloque_perdidas(ev)
    L += _bloque_costo(ev)
    L += ["## Detalle por trampa", "",
          "| Trampa | Encontrada | Artículo citado | Artículo verificado | Clase esperada | Clase obtenida | Responsable esperado | Responsable obtenido | Nivel esperado | Nivel obtenido |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for t in ev["trampas"]:
        enc = {"encontrada": "sí", "otro artículo": "otro artículo", "encontrada por frase": "sí (por frase)", "no": "no"}[t["estado"]]
        obt = (lambda v: v if v is not None else ("—" if not lista else NO_EVALUABLE))
        ver = "—" if lista or not ev["hay_registro"] else ("sí" if t["verificado"] else "no")
        L.append(f"| {t['id']} | {enc} | {t['articulo_citado'] or '—'} | {ver} | {t['clase_esperada']} | {obt(t['clase_obtenida'])} | {t['responsable_esperado']} | "
                 f"{obt(t['responsable_obtenido'])} | {t['nivel_esperado']} | {obt(t['nivel_obtenido'])} |")
    L.append("")
    if comparacion:
        L += ["## Comparación con la línea de base sin RAG", "", comparacion, ""]
    return "\n".join(L)


def guardar_detalle_csv(ev, ruta):
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["trampa", "encontrada", "norma", "articulo", "articulo_citado", "articulo_verificado", "perezosa", "perezosa_clasificacion", "perdida", "clase_esperada", "clase_obtenida",
                    "responsable_esperado", "responsable_obtenido", "nivel_esperado", "nivel_obtenido", "como_alerta"])
        for t in ev["trampas"]:
            w.writerow([t["id"], t["estado"], t["norma"], t["articulo"], t["articulo_citado"], int(t["verificado"]), int(t["perezosa"]), int(t["perezosa_clasificacion"]), t["perdida"], t["clase_esperada"],
                        t["clase_obtenida"] or "", t["responsable_esperado"], t["responsable_obtenido"] or "", t["nivel_esperado"], t["nivel_obtenido"] or "", int(t["como_alerta"])])


def ruta_extras(ruta_json) -> str:
    """CSV de extras (y de la revisión humana) de un JSON: <json sin extensión>_extras.csv, junto al JSON. Cada JSON tiene el suyo."""
    return os.path.splitext(os.path.abspath(ruta_json))[0] + "_extras.csv"


def ruta_juez(ruta_json) -> str:
    """CSV del juez externo de un JSON: <json sin extensión>_juez.csv, junto al JSON."""
    return os.path.splitext(os.path.abspath(ruta_json))[0] + "_juez.csv"


def avisar_si_hay_extras_viejo(ruta_json):
    """El extras_revision.csv de nombre fijo (uno por carpeta) puede ser de otra configuración: no se usa, solo se avisa."""
    viejo = os.path.join(os.path.dirname(os.path.abspath(ruta_json)), "extras_revision.csv")
    if os.path.isfile(viejo) and not os.path.isfile(ruta_extras(ruta_json)):
        print(f"Aviso: existe {viejo} (nombre antiguo, uno por carpeta) pero no {ruta_extras(ruta_json)}: NO se usa. Si es de este JSON, renombralo.", file=sys.stderr)


def guardar_extras_csv(ev, ruta):
    """Escribe los extras; si el archivo ya existe, conserva la marca «valido» de los extras que siguen estando (no se pierde la revisión humana)."""
    columnas = ["oferta", "seccion", "norma", "articulo", "cita", "titulo", "clase", "valido"]
    marcas = {_clave_extra(r.get("seccion"), r.get("norma"), r.get("articulo"), r.get("cita")): r.get("valido") or "" for r in (leer_csv(ruta) if os.path.isfile(ruta) else [])}
    filas = [{**x, "valido": marcas.get(_clave_extra(x["seccion"], x["norma"], x["articulo"], x["cita"]), x.get("valido") or "")} for x in ev["extras"]]
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, delimiter=";")
        w.writeheader()
        w.writerows(filas)


def guardar_coincidencias_sinrag_csv(ev, ruta):
    """Coincidencias por frase de la línea de base para que el usuario marque en `valido` (sí/no) cuáles tratan realmente la trampa."""
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["trampa", "frase", "descripcion_riesgo", "cita", "valido"])
        for c in ev["coincidencias"]:
            w.writerow([c["trampa"], c["frase"], c["descripcion"], c["cita"], ""])


# --- Línea de comandos ---

def _oferta_de_ruta(ruta):
    """('P2', ruta) para 'P2=ruta'; si no, la oferta se toma de la ruta (P1, P2... como palabra suelta, no dentro de 'TBP01')."""
    m = re.match(r"^(P\d)=(.+)$", ruta)
    if m:
        return m.group(1), m.group(2)
    m = re.search(r"(?<![A-Za-z0-9])(P\d)(?!\d)", ruta)
    if not m:
        raise SystemExit(f"No se pudo deducir la oferta de «{ruta}»: usá P1=ruta, P2=ruta...")
    return m.group(1), ruta


def _cargar(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def evaluar_archivo(ruta, oferta, gt, espejos, revision=None) -> dict:
    """Evalúa un JSON y le asigna la precisión humana (`revision`, por defecto <json>_extras.csv) y la del juez (<json>_juez.csv), si existen."""
    ev = evaluar(_cargar(ruta), gt, espejos, oferta)
    if not revision:
        revision = ruta_extras(ruta)
        avisar_si_hay_extras_viejo(ruta)
    archivo_juez = ruta_juez(ruta)
    juez_rows = leer_csv(archivo_juez) if os.path.isfile(archivo_juez) else None
    rev_rows = leer_csv(revision) if os.path.isfile(revision) else None
    if juez_rows:
        rev_rows = revision_con_marcas_juez(rev_rows, juez_rows)
    asignar_precision(ev, rev_rows)
    asignar_juez(ev, juez_rows, rev_rows)
    return ev


def main(argv=None):
    p = argparse.ArgumentParser(description="Evalúa un resultado contra el ground truth v3 y los espejos conformes")
    p.add_argument("--resultado", help="JSON del resultado")
    p.add_argument("--oferta", help="P1, P2, P3 o P4 (con --resultado)")
    p.add_argument("--agregado", nargs="+", metavar="JSON", help="JSON de varias ofertas: las métricas se calculan sobre el total de trampas")
    p.add_argument("--revision", help="CSV de extras con la columna 'valido' completa (sí/no); por defecto <json>_extras.csv")
    p.add_argument("--comparar", nargs="+", metavar="JSON_SIN_RAG", help="resultado(s) sin RAG: agrega la tabla con RAG / sin RAG")
    p.add_argument("--revision-sinrag", nargs="+", metavar="CSV", help="sinrag_coincidencias.csv con 'valido' completo: la fila sin RAG cuenta solo las válidas")
    p.add_argument("--ground-truth", default=GROUND_TRUTH)
    p.add_argument("--espejos", default=ESPEJOS)
    a = p.parse_args(argv)

    if a.agregado:
        entradas = [_oferta_de_ruta(r) for r in a.agregado]
    elif a.resultado and a.oferta:
        entradas = [(a.oferta, a.resultado)]
    else:
        raise SystemExit("Indicá --resultado y --oferta, o --agregado.")

    evs, gts, espejos_por_oferta = [], {}, {}
    for oferta, ruta in entradas:
        gts[oferta], espejos_por_oferta[oferta] = cargar_gt(oferta, a.ground_truth), cargar_espejos(oferta, a.espejos)
        if not gts[oferta]:
            raise SystemExit(f"No hay trampas de la oferta {oferta} en {a.ground_truth}")
        evs.append(evaluar_archivo(ruta, oferta, gts[oferta], espejos_por_oferta[oferta], None if a.agregado else a.revision))
    total = combinar(evs)

    comparacion = None
    if a.comparar:
        sin_entradas = [_oferta_de_ruta(r) for r in a.comparar] if a.agregado or len(a.comparar) > 1 else [(entradas[0][0], a.comparar[0])]
        revision_sinrag = [r for ruta in a.revision_sinrag or [] for r in leer_csv(ruta)]
        sins = []
        for oferta, ruta in sin_entradas:
            sin = evaluar(_cargar(ruta), gts[oferta], espejos_por_oferta[oferta], oferta)
            aplicar_revision_sinrag(sin, revision_sinrag)
            guardar_coincidencias_sinrag_csv(sin, os.path.join(os.path.dirname(os.path.abspath(ruta)), "sinrag_coincidencias.csv"))
            sins.append(sin)
        sin_total = combinar(sins)
        mcnemar = comparar_mcnemar(total, sin_total) if len(evs) > 1 else None
        comparacion = tabla_comparacion(total, sin_total, mcnemar)

    carpeta, marca = os.path.dirname(os.path.abspath(entradas[0][1])), datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre = "agregado" if a.agregado else a.oferta
    ruta_md = os.path.join(carpeta, f"evaluacion_{nombre}_{marca}.md")
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(informe_md(total, comparacion))
    guardar_detalle_csv(total, os.path.join(carpeta, f"evaluacion_{nombre}_{marca}.csv"))
    if total["modo"] == "brechas" and not a.agregado:
        guardar_extras_csv(total, ruta_extras(entradas[0][1]))
    print(f"Evaluación guardada en {ruta_md}")
    if comparacion:
        print(comparacion)
    return total


if __name__ == "__main__":
    main()
