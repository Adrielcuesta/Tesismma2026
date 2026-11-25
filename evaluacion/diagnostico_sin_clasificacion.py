# evaluacion/diagnostico_sin_clasificacion.py
"""Diagnóstico (solo lectura) de los pares (sección, norma, artículo) que la verificación (LLM1) marcó Incumple o Revisar y que terminaron sin brecha ni alerta.
Clasifica cada par por la causa, según los caminos de scripts/main.py::_verificar_seccion (ver evaluacion/diagnosticos/pares_sin_clasificacion.md):

  sin entrada de clasificación (el par nunca llegó al LLM2):
    - ids_inexistentes_malformados: la verificación citó IDs que no tienen la forma O<n> (p. ej. «[O3]», «3», «O3-O5»); rag_components.procesar_verificacion la descarta.
    - ids_inexistentes_fuera_de_rango: IDs con la forma O<n> que no existen en la sección; misma descarta.
    - sin_oraciones: Incumple/Revisar sin ninguna oración citada; misma descarta.
    - inconsistente: el registro dice que la verificación era válida (estado ok o discrepancia_numerica) y aun así no hay clasificación, brecha ni alerta. Por el código no
      debería ocurrir: si aparece, es un error (del pipeline, de la fusión del reintento o de las claves) y hay que mirarlo.
  con entrada de clasificación (el LLM2 respondió y el código o el modelo lo descartó):
    - clasificacion_<estado>: no_es_riesgo (CUMPLE / NO_APLICA, o reglas 2.5 / 2.7.c), descartada (clasificación incompleta), clasificacion_fallida, tiempo_agotado.

Claves: (sección, norma, artículo) tomadas de los CAMPOS de cada registro, brecha y alerta (no del id «S3|NORM_01|2.5#2» de la brecha). Además compara con la clave que usaba
datos/tmp_desacuerdos.py (id de la brecha cortado en «#») e informa si alguna difiere. Cada trampa se asocia a un par por su sección (S#) y su artículo o uno equivalente; se informa
también su estado final según evaluar() (una trampa puede caer en un par descartado y estar encontrada por otro par).

Uso:
  venv\\Scripts\\python.exe -m evaluacion.diagnostico_sin_clasificacion [--config evaluacion/config_p6p12.json] [--configuracion "<nombre>"] [--salida evaluacion/diagnosticos/p6p12]
Escribe <salida>/pares_sin_clasificacion.csv (un par por fila) y <salida>/pares_sin_clasificacion_resumen.md, e imprime el resumen. No llama a ninguna API."""
import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict

from . import evaluar as E

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
RE_ID = re.compile(r"^O\d+$")
MOTIVO_INEXISTENTES = "IDs de oración inexistentes:"
MOTIVO_SIN_ORACIONES = "sin oraciones de la oferta"
ESTADOS_VALIDOS = ("ok", "discrepancia_numerica")
SIN_LLM2 = ("ids_inexistentes_malformados", "ids_inexistentes_fuera_de_rango", "sin_oraciones", "inconsistente", "otra_sin_clasificacion")


def clave(x: dict) -> tuple:
    return (str(x.get("seccion")), str(x.get("norma") or ""), E._articulo(x.get("articulo")))


def _ids_inexistentes(motivo: str) -> list:
    return [i.strip() for i in str(motivo or "").split(MOTIVO_INEXISTENTES, 1)[-1].split(",") if i.strip()] if MOTIVO_INEXISTENTES in str(motivo or "") else []


def causa_sin_clasificacion(verificaciones: list) -> tuple:
    """(causa, detalle) de un par Incumple/Revisar sin ninguna entrada de clasificación. `verificaciones`: sus entradas de verificación con veredicto Incumple o Revisar
    (más de una si el artículo tiene varias partes en la sección)."""
    if any(r.get("estado") in ESTADOS_VALIDOS for r in verificaciones):
        return "inconsistente", "verificación válida sin clasificación, brecha ni alerta"
    motivos = [str(r.get("motivo") or "") for r in verificaciones]
    inexistentes = [i for m in motivos for i in _ids_inexistentes(m)]
    if inexistentes:
        validas = [str(i).strip().upper() for r in verificaciones for i in (r.get("oraciones") or []) if str(i).strip() not in inexistentes]
        detalle = f"inexistentes: {', '.join(inexistentes)}" + (f" | válidas: {', '.join(validas)}" if validas else "")
        malformados = [i for i in inexistentes if not RE_ID.match(i.strip().upper())]
        return ("ids_inexistentes_malformados" if malformados else "ids_inexistentes_fuera_de_rango"), detalle
    if any(m.startswith(MOTIVO_SIN_ORACIONES) for m in motivos):
        return "sin_oraciones", motivos[0]
    return "otra_sin_clasificacion", "; ".join(f"{r.get('estado')}: {r.get('motivo', '')}"[:120] for r in verificaciones)


def mapa_trampas(gt: list, secciones: list) -> dict:
    """{(S#, norma, artículo): [trampa]} con el artículo de la trampa y sus equivalentes, en las secciones que contienen su subsección."""
    salida = defaultdict(list)
    for t in gt:
        for s in E._ids_secciones_de(t["seccion"], secciones):
            for norma, art in E.pares_trampa(t):
                salida[(s, norma, art)].append(t)
    return salida


def diagnosticar(resultado: dict, gt: list, espejos: list, oferta: str) -> dict:
    """{'filas': [un dict por par descartado], 'universo': pares Incumple/Revisar sin brecha ni alerta, 'difieren_claves': pares en que la clave por campos y la de tmp_desacuerdos difieren}."""
    reg = resultado.get("registro_tecnico") or []
    brechas = {clave(b) for b in resultado.get("registro_brechas") or []}
    brechas_id = {str(b.get("id", "")).split("#")[0] for b in resultado.get("registro_brechas") or []}      # la clave de tmp_desacuerdos.py
    alertas = {clave(a) for a in resultado.get("alertas") or []}
    verif, clasif = defaultdict(list), defaultdict(list)
    for r in reg:
        if r.get("etapa") == "clasificacion":
            clasif[clave(r)].append(r)
        elif not r.get("etapa") and r.get("veredicto") and E.norm(r["veredicto"]) in ("incumple", "revisar"):
            verif[clave(r)].append(r)
    trampas = mapa_trampas(gt, resultado.get("secciones"))
    estado_trampa = {t["id"]: t for t in E.evaluar(resultado, gt, espejos, oferta)["trampas"]}
    filas, difieren = [], []
    for k, vs in verif.items():
        por_campos = k in brechas or k in alertas
        por_id = f"{k[0]}|{k[1]}|{k[2]}" in brechas_id or k in alertas
        if por_campos != por_id:
            difieren.append(k)
        if por_campos:
            continue
        cs = clasif.get(k, [])
        if cs:
            estados = sorted({str(c.get("estado")) for c in cs})
            causa = "clasificacion_" + "+".join(estados)
            detalle = "; ".join(f"{c.get('veredicto')}" + (f" (regla {c['regla']})" if c.get("regla") else "") for c in cs)
        else:
            causa, detalle = causa_sin_clasificacion(vs)
        ts = trampas.get(k, [])
        filas.append({"oferta": oferta, "seccion": k[0], "norma": k[1], "articulo": k[2], "llm1": "/".join(sorted({vv["veredicto"] for vv in vs})),
                      "llm2": "/".join(str(c.get("veredicto")) for c in cs) or "—", "causa": causa, "detalle": detalle, "partes_verificadas": len(vs),
                      "trampas": ", ".join(t["id"] for t in ts), "severidad": ", ".join(t.get("severidad") or "" for t in ts),
                      "estado_final_trampa": ", ".join(estado_trampa[t["id"]]["estado"] for t in ts if t["id"] in estado_trampa),
                      "perdida_trampa": ", ".join(estado_trampa[t["id"]]["perdida"] for t in ts if t["id"] in estado_trampa)})
    return {"filas": filas, "difieren_claves": difieren}


def resumen_md(filas: list, difieren: dict, n_ofertas: int, nombre: str) -> str:
    sin = [f for f in filas if f["llm2"] == "—"]
    L = [f"# Pares Incumple/Revisar sin brecha ni alerta: {nombre}", "",
         f"- Pares (sección, norma, artículo) con LLM1 = Incumple/Revisar que terminan sin brecha ni alerta: **{len(filas)}** ({len(filas) / n_ofertas:.1f} por oferta).",
         f"- De esos, sin ninguna entrada de clasificación (llm2 = «—»): **{len(sin)}**.",
         f"- Pares en que la clave por campos y la de tmp_desacuerdos.py (id de la brecha) difieren: **{sum(len(v) for v in difieren.values())}**"
         + (" (" + "; ".join(f"{o}: {', '.join('|'.join(k) for k in v[:5])}" for o, v in difieren.items() if v) + ")" if any(difieren.values()) else "") + ".", "",
         "## Por causa", "", "| Causa | Pares | Trampas en esos pares | Trampas no encontradas (estado final) |", "|---|---|---|---|"]
    for causa, n in Counter(f["causa"] for f in filas).most_common():
        sel = [f for f in filas if f["causa"] == causa]
        ids = {(i.strip(), e.strip()) for f in sel if f["trampas"] for i, e in zip(f["trampas"].split(","), f["estado_final_trampa"].split(","))}
        L.append(f"| {causa} | {n} | {len({i for i, _ in ids})} | {len({i for i, e in ids if e != 'encontrada'})} |")
    L += ["", "## Pares sin clasificación (llm2 = «—») por oferta y causa", "", "| Oferta | " + " | ".join(SIN_LLM2) + " | Total |", "|" + "---|" * (len(SIN_LLM2) + 2)]
    for oferta in dict.fromkeys(f["oferta"] for f in filas):
        c = Counter(f["causa"] for f in sin if f["oferta"] == oferta)
        L.append(f"| {oferta} | " + " | ".join(str(c.get(x, 0)) for x in SIN_LLM2) + f" | {sum(c.values())} |")
    L += ["", "## Trampas que caen en pares sin clasificación", "", "| Oferta | Trampa | Severidad | Par | Causa | Detalle | Estado final | Pérdida (evaluar) |", "|---|---|---|---|---|---|---|---|"]
    for f in sin:
        for i, s, e, p in zip(*(f[c].split(", ") for c in ("trampas", "severidad", "estado_final_trampa", "perdida_trampa"))) if f["trampas"] else []:
            L.append(f"| {f['oferta']} | {i} | {s} | {f['seccion']} {f['norma']} {f['articulo']} | {f['causa']} | {f['detalle'][:90]} | {e} | {p} |")
    L += ["", "Causas: ver la cabecera de evaluacion/diagnostico_sin_clasificacion.py y evaluacion/diagnosticos/pares_sin_clasificacion.md.", ""]
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(description="Pares Incumple/Revisar sin brecha ni alerta, por causa (solo lectura)")
    p.add_argument("--config", default=os.path.join(AQUI, "config_p6p12.json"))
    p.add_argument("--configuracion", help="nombre de la configuración (por defecto la primera)")
    p.add_argument("--salida", default=os.path.join(AQUI, "diagnosticos", "p6p12"))
    a = p.parse_args(argv)
    with open(a.config, encoding="utf-8") as fh:
        cfg = json.load(fh)
    nombre = a.configuracion or next(iter(cfg["configuraciones"]))
    filas, difieren = [], {}
    for oferta, ruta in cfg["configuraciones"][nombre].items():
        ruta = ruta if os.path.isabs(ruta) else os.path.join(RAIZ, ruta)
        with open(ruta, encoding="utf-8") as fh:
            res = json.load(fh)
        d = diagnosticar(res, E.cargar_gt(oferta), E.cargar_espejos(oferta), oferta)
        filas += d["filas"]
        difieren[oferta] = d["difieren_claves"]
    os.makedirs(a.salida, exist_ok=True)
    ruta_csv, ruta_md = os.path.join(a.salida, "pares_sin_clasificacion.csv"), os.path.join(a.salida, "pares_sin_clasificacion_resumen.md")
    campos = ["oferta", "seccion", "norma", "articulo", "llm1", "llm2", "causa", "detalle", "partes_verificadas", "trampas", "severidad", "estado_final_trampa", "perdida_trampa"]
    with open(ruta_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, delimiter=";")
        w.writeheader()
        w.writerows(filas)
    md = resumen_md(filas, difieren, len(cfg["configuraciones"][nombre]), nombre)
    with open(ruta_md, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(md)
    print(f"Guardado: {ruta_csv}\nGuardado: {ruta_md}")


if __name__ == "__main__":
    main()
