# evaluacion/v2_medir_ab.py
"""Medición en desarrollo de las propuestas A y B de la v2 como POSTPROCESO sobre los JSON de resultados existentes (sin LLM ni red, sin volver a recuperar):
  A: se descartan las brechas cuyo artículo es de alcance, objeto o prevalencia (por título; evaluacion/v2_listar_no_verificables.py).
  B: se descartan las brechas cuya clasificación marcó etapa_requisito == POSTERIOR, sea cual sea su fuente (hoy solo se aplica a INFORMACION_FALTANTE).
Cruza con las etiquetas humanas de los extras (<json>_extras.csv, columna «valido») y da la precisión nueva frente a la base. Solo LEE: no escribe ningún CSV de extras y no
llama a evaluar.main (que reescribe esos CSV); usa evaluar.evaluar y evaluar.asignar_precision.

Uso (lo corre el usuario: lee datos/Resultados):
  python -m evaluacion.v2_medir_ab --config "gpt-oss-120b esfuerzo bajo (elegida)" [--ofertas P1 P2] [--archivo-config evaluacion/config_reeval.json] [--salida <md>]
Límite de B: el prompt de clasificación pide etapa_requisito solo para INFORMACION_FALTANTE; en las brechas de otra fuente el campo viene vacío y B no las puede descartar sin volver a
llamar al modelo. El informe muestra cuántas brechas de cada fuente traen el campo (cobertura de B).

Criterios de decisión, fijados antes de validar (propuesta): A+B se adopta si en P1+P2 la precisión sube al menos 10 puntos y no se pierde ninguna trampa detectada."""
import argparse
import copy
import os
import sys

from . import evaluar as E
from .v2_listar_no_verificables import brecha_excluida, titulo_de_brecha

SUBE_MINIMO = 0.10                 # puntos de precisión (0,10 = 10 puntos)
VARIANTES = (("base", False, False), ("A", True, False), ("B", False, True), ("A+B", True, True))


def brecha_posterior(brecha: dict) -> bool:
    """Regla 2.7.c extendida: la clasificación dijo que el dato se exige en una etapa posterior."""
    return (brecha.get("clasificacion") or {}).get("etapa_requisito") == "POSTERIOR"


def filtrar(resultado: dict, a: bool, b: bool) -> dict:
    """Copia del resultado con registro_brechas sin las brechas que descartan A y/o B. Las «descartadas por cálculo» no se tocan (ya no cuentan como riesgo)."""
    nuevo = copy.deepcopy(resultado)
    nuevo["registro_brechas"] = [x for x in resultado.get("registro_brechas") or []
                                 if x.get("estado") == E.ESTADO_DESCARTADA_CALCULO or not ((a and brecha_excluida(x)) or (b and brecha_posterior(x)))]
    return nuevo


def cobertura_b(resultado: dict) -> dict:
    """{fuente: (brechas, con etapa_requisito informada, con POSTERIOR)} sobre las brechas que generan riesgo."""
    salida = {}
    for x in resultado.get("registro_brechas") or []:
        if x.get("estado") == E.ESTADO_DESCARTADA_CALCULO:
            continue
        n, con, post = salida.get(x.get("fuente"), (0, 0, 0))
        etapa = (x.get("clasificacion") or {}).get("etapa_requisito")
        salida[x.get("fuente")] = (n + 1, con + bool(etapa), post + (etapa == "POSTERIOR"))
    return salida


def _etiquetas(revision) -> dict:
    return {E._clave_extra(r.get("seccion"), r.get("norma"), r.get("articulo"), r.get("cita")): E.norm(r.get("valido")) for r in revision or []}


def evaluar_variante(entradas: list, a: bool, b: bool) -> dict:
    """Métricas agregadas de una variante sobre las ofertas. entradas: [{oferta, resultado, gt, espejos, revision}]."""
    evs = []
    for e in entradas:
        ev = E.evaluar(filtrar(e["resultado"], a, b), e["gt"], e["espejos"], e["oferta"])
        E.asignar_precision(ev, e["revision"])
        evs.append(ev)
    t = E.combinar(evs)
    etiquetas = {}
    for e in entradas:
        etiquetas.update(_etiquetas(e["revision"]))
    valores = [etiquetas.get(E._clave_extra(x["seccion"], x["norma"], x["articulo"], x["cita"])) for x in t["extras"]]
    validos, no_validos = valores.count("si"), valores.count("no")
    sin_etiqueta = len(valores) - validos - no_validos
    k = t["encontradas"] + validos
    return {"encontradas": t["encontradas"], "n_trampas": t["n_trampas"], "perdidas": sorted(x["id"] for x in t["trampas"] if x["estado"] != "encontrada"),
            "encontradas_ids": sorted(x["id"] for x in t["trampas"] if x["estado"] == "encontrada"), "brechas": t["n_riesgo"], "extras": len(t["extras"]),
            "validos": validos, "no_validos": no_validos, "sin_etiqueta": sin_etiqueta, "falsas_alarmas": t["falsas_alarmas"], "n_espejos": t["n_espejos"],
            "precision": t["precision"], "precision_k": t["precision_k"], "precision_n": t["precision_n"],
            "cota_inferior": k / t["n_riesgo"] if t["n_riesgo"] else None, "cota_superior": (k + sin_etiqueta) / t["n_riesgo"] if t["n_riesgo"] else None,
            "claves_extras": {E._clave_extra(x["seccion"], x["norma"], x["articulo"], x["cita"]): etiquetas.get(E._clave_extra(x["seccion"], x["norma"], x["articulo"], x["cita"])) or "" for x in t["extras"]}}


def comparar(entradas: list) -> dict:
    """Las cuatro variantes (base, A, B, A+B), con lo que cada una elimina respecto de la base y el veredicto contra los criterios de decisión."""
    res = {nombre: evaluar_variante(entradas, a, b) for nombre, a, b in VARIANTES}
    base = res["base"]
    for nombre, r in res.items():
        quitadas = {k: v for k, v in base["claves_extras"].items() if k not in r["claves_extras"]}
        r["extras_eliminados"] = {"validos": sum(v == "si" for v in quitadas.values()), "no_validos": sum(v == "no" for v in quitadas.values()),
                                  "sin_etiqueta": sum(v not in ("si", "no") for v in quitadas.values())}
        r["trampas_perdidas_vs_base"] = sorted(set(base["encontradas_ids"]) - set(r["encontradas_ids"]))
    ab = res["A+B"]
    p0, p1 = base["precision"], ab["precision"]
    sube = None if p0 is None or p1 is None else p1 - p0
    res["decision"] = {"sube_puntos": sube, "trampas_perdidas": ab["trampas_perdidas_vs_base"], "umbral": SUBE_MINIMO,
                       "adopta": None if sube is None else (sube >= SUBE_MINIMO - 1e-9 and not ab["trampas_perdidas_vs_base"]),
                       "concluyente": sube is not None}
    return res


def _pc(v) -> str:
    return "n/d" if v is None else f"{v:.1%}"


def informe_md(res: dict, ofertas: list, cobertura: dict, titulos_excluidos: list) -> str:
    L = [f"# Medición de A y B como postproceso ({'+'.join(ofertas)})", "",
         "| Variante | Trampas encontradas | Brechas | Extras (válidos / no válidos / sin etiquetar) | Precisión humana | Cota (inferior–superior) | Δ vs base (pts) | Trampas perdidas vs base |",
         "|---|---|---|---|---|---|---|---|"]
    p0 = res["base"]["precision"]
    for nombre, _, _ in VARIANTES:
        r = res[nombre]
        delta = "—" if nombre == "base" or r["precision"] is None or p0 is None else f"{(r['precision'] - p0) * 100:+.1f}"
        k = f" ({r['precision_k']}/{r['precision_n']})" if r["precision"] is not None else ""
        L.append(f"| {nombre} | {r['encontradas']}/{r['n_trampas']} | {r['brechas']} | {r['extras']} ({r['validos']} / {r['no_validos']} / {r['sin_etiqueta']}) | {_pc(r['precision'])}{k} | "
                 f"{_pc(r['cota_inferior'])}–{_pc(r['cota_superior'])} | {delta} | {', '.join(r['trampas_perdidas_vs_base']) or 'ninguna'} |")
    L += ["", "La precisión es (trampas encontradas + extras válidos) / brechas que generan riesgo; «n/d» si faltan etiquetas de algún extra (la cota inferior cuenta los sin etiquetar "
          "como no válidos y la superior como válidos).", "", "## Qué elimina cada variante respecto de la base (extras por etiqueta)", "",
          "| Variante | Válidos eliminados | No válidos eliminados | Sin etiqueta eliminados |", "|---|---|---|---|"]
    L += [f"| {n} | {res[n]['extras_eliminados']['validos']} | {res[n]['extras_eliminados']['no_validos']} | {res[n]['extras_eliminados']['sin_etiqueta']} |" for n, _, _ in VARIANTES[1:]]
    L += ["", "## Cobertura de B (etapa_requisito informada por fuente)", "", "| Fuente | Brechas | Con etapa_requisito | Con POSTERIOR |", "|---|---|---|---|"]
    L += [f"| {f} | {n} | {con} | {post} |" for f, (n, con, post) in sorted(cobertura.items(), key=lambda x: str(x[0]))]
    L += ["", "B solo puede descartar donde el modelo informó la etapa; el prompt la pide únicamente para INFORMACION_FALTANTE.", "",
          f"## Artículos eliminados por A en estas ofertas ({len(titulos_excluidos)})", ""] + [f"- {t}" for t in titulos_excluidos]
    d = res["decision"]
    L += ["", "## Criterio de decisión (fijado antes de validar)", "",
          f"- La precisión sube al menos {SUBE_MINIMO * 100:.0f} puntos con A+B: " + ("sin datos (faltan etiquetas)" if d["sube_puntos"] is None else f"{d['sube_puntos'] * 100:+.1f} pts → {'cumple' if d['sube_puntos'] >= SUBE_MINIMO - 1e-9 else 'no cumple'}"),
          f"- No se pierde ninguna trampa detectada: {'cumple' if not d['trampas_perdidas'] else 'no cumple (' + ', '.join(d['trampas_perdidas']) + ')'}",
          f"- Conclusión: {'se adopta' if d['adopta'] else ('no se adopta' if d['adopta'] is False else 'no concluyente: faltan etiquetas')}."]
    return "\n".join(L) + "\n"


def _cargar_entradas(config: str, archivo_config: str, ofertas: list) -> list:
    from . import tabla_comparativa as T
    cfg = T.cargar_config(archivo_config)
    if config not in cfg["configuraciones"]:
        raise SystemExit(f"No hay una configuración «{config}» en {archivo_config}. Hay: {', '.join(cfg['configuraciones'])}")
    entradas = []
    for oferta in ofertas:
        ruta = T.resolver_ruta(cfg["configuraciones"][config].get(oferta), f"{config} / {oferta}")
        if not ruta or not os.path.isfile(ruta):
            raise SystemExit(f"{oferta}: no hay JSON para «{config}» (ruta: «{ruta}»).")
        extras = E.ruta_extras(ruta)
        entradas.append({"oferta": oferta, "ruta": ruta, "resultado": E._cargar(ruta), "gt": E.cargar_gt(oferta), "espejos": E.cargar_espejos(oferta),
                         "revision": E.leer_csv(extras) if os.path.isfile(extras) else None})
    return entradas


def main(argv=None) -> dict:
    p = argparse.ArgumentParser(description="Mide A y B de la v2 como postproceso sobre los JSON existentes (solo lectura)")
    p.add_argument("--config", required=True, help="configuración de config_reeval.json, p. ej. «gpt-oss-120b esfuerzo bajo (elegida)»")
    p.add_argument("--ofertas", nargs="+", default=["P1", "P2"], help="ofertas (por defecto P1 P2: el ajuste se hace con desarrollo)")
    p.add_argument("--archivo-config", default=os.path.join(E.AQUI, "config_reeval.json"))
    p.add_argument("--salida", help="ruta de un .md con el informe (no se pisa un archivo existente)")
    a = p.parse_args(argv)
    if any(o in ("P3", "P4", "P5") for o in a.ofertas):
        print("Aviso: P3 y P4 no se usan para ajustar y P5 es el conjunto ciego; esta medición es para elegir A y B con P1+P2.", file=sys.stderr)
    entradas = _cargar_entradas(a.config, a.archivo_config, a.ofertas)
    res = comparar(entradas)
    cobertura = {}
    titulos = []
    for e in entradas:
        for f, (n, con, post) in cobertura_b(e["resultado"]).items():
            c = cobertura.get(f, (0, 0, 0))
            cobertura[f] = (c[0] + n, c[1] + con, c[2] + post)
        titulos += sorted({f"{x.get('norma')} {x.get('articulo')} «{titulo_de_brecha(x)}»" for x in e["resultado"].get("registro_brechas") or [] if brecha_excluida(x)})
    texto = informe_md(res, a.ofertas, cobertura, sorted(set(titulos)))
    print(texto)
    if a.salida:
        if os.path.exists(a.salida):
            print(f"No se escribió {a.salida}: ya existe.", file=sys.stderr)
        else:
            with open(a.salida, "w", encoding="utf-8") as f:
                f.write(texto)
    return res


if __name__ == "__main__":
    main()
