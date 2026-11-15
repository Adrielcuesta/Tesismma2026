# evaluacion/estabilidad.py
"""Estabilidad entre dos corridas de la misma oferta, el mismo modelo y el mismo perfil de recuperación. Sin LLM ni red.
«Detectada» es exactamente la de evaluar.py (trampa «encontrada»: frase y artículo): se importa evaluar.evaluar, no se reimplementa.

Uso:
  python -m evaluacion.estabilidad --a <json_A> --b <json_B> --oferta P3 [--ground-truth <csv>] [--salida <md>]

Por trampa: detectada en A, detectada en B y acuerdo. Además: acuerdo global (% de trampas con la misma decisión en A y B), kappa de Cohen sobre detectada sí/no,
cantidad de riesgos por corrida (brechas que generan riesgo y riesgos agrupados) y Jaccard de los conjuntos (sección, norma, artículo) de las brechas reportadas.
Valida que las dos corridas tengan la misma huella de pares (scripts.huella_recuperacion) y el mismo modelo; si no, advierte (no corta).
Umbral informativo: acuerdo >= 90 % (el criterio de la tesis); se imprime «cumple» o «no cumple» y la ejecución sigue en cualquier caso."""
import argparse
import json
import os
import sys

from scripts import huella_recuperacion

from . import evaluar as E

UMBRAL_ACUERDO = 0.90


def detectadas(resultado: dict, gt: list, oferta: str) -> dict:
    """{id de trampa: detectada} con la misma definición de evaluar.py (estado «encontrada»: la frase está en la cita de una brecha y el artículo coincide)."""
    ev = E.evaluar(resultado, gt, [], oferta)
    if ev["modo"] != "brechas":
        raise ValueError("La estabilidad se mide sobre corridas en modo verificación (con registro_brechas); este resultado está en modo lista.")
    return {t["id"]: t["estado"] == "encontrada" for t in ev["trampas"]}


def riesgos_reportados(resultado: dict) -> set:
    """Conjunto de (sección, norma, artículo) de las brechas que generan riesgo (las descartadas por cálculo no cuentan, como en evaluar.py)."""
    return {(str(b.get("seccion")), b.get("norma"), E._articulo(b.get("articulo")))
            for b in resultado.get("registro_brechas") or [] if b.get("estado") != E.ESTADO_DESCARTADA_CALCULO}


def jaccard(a: set, b: set):
    """|A ∩ B| / |A ∪ B|; 1.0 si los dos conjuntos están vacíos."""
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def huella(resultado: dict) -> str:
    return huella_recuperacion.huella_de_pares(resultado.get("secciones"))


def avisos(a: dict, b: dict) -> list:
    """Condiciones para que la comparación tenga sentido: misma huella de pares y mismo modelo."""
    salida = []
    if huella(a) != huella(b):
        salida.append("Las dos corridas NO tienen la misma huella de pares: verificaron pares distintos, así que la diferencia mezcla recuperación y verificador.")
    ca, cb = a.get("configuracion_analisis") or {}, b.get("configuracion_analisis") or {}
    if ca.get("modelo_llm_usado") != cb.get("modelo_llm_usado"):
        salida.append(f"Los modelos difieren: A = {ca.get('modelo_llm_usado')!r}, B = {cb.get('modelo_llm_usado')!r}.")
    if ca.get("perfil_recuperacion") != cb.get("perfil_recuperacion"):
        salida.append(f"Los perfiles de recuperación difieren: A = {ca.get('perfil_recuperacion')!r}, B = {cb.get('perfil_recuperacion')!r}.")
    return salida


def comparar(a: dict, b: dict, gt: list, oferta: str) -> dict:
    """Estabilidad de B respecto de A sobre las trampas del ground truth de la oferta."""
    da, db = detectadas(a, gt, oferta), detectadas(b, gt, oferta)
    filas = [{"id": i, "a": da[i], "b": db[i], "acuerdo": da[i] == db[i]} for i in da]
    n = len(filas)
    acuerdo = sum(f["acuerdo"] for f in filas) / n if n else None
    ra, rb = riesgos_reportados(a), riesgos_reportados(b)
    return {"oferta": oferta, "trampas": filas, "n": n, "acuerdo": acuerdo, "kappa": E.cohen_kappa([(f["a"], f["b"]) for f in filas]),
            "detectadas_a": sum(f["a"] for f in filas), "detectadas_b": sum(f["b"] for f in filas),
            "brechas_a": len(ra), "brechas_b": len(rb), "riesgos_agrupados_a": len(a.get("riesgos") or []), "riesgos_agrupados_b": len(b.get("riesgos") or []),
            "jaccard": jaccard(ra, rb), "solo_a": len(ra - rb), "solo_b": len(rb - ra), "umbral": UMBRAL_ACUERDO,
            "cumple": acuerdo is not None and acuerdo >= UMBRAL_ACUERDO - 1e-9, "avisos": avisos(a, b),
            "huella_a": huella(a), "huella_b": huella(b)}


def _pc(v) -> str:
    return "n/d" if v is None else f"{v:.1%}"


def informe_md(c: dict) -> str:
    L = [f"# Estabilidad {c['oferta']}", ""]
    L += [f"**Advertencia:** {x}" for x in c["avisos"]] + ([""] if c["avisos"] else [])
    kappa = "n/d (acuerdo esperado por azar = 1)" if c["kappa"] is None else f"{c['kappa']:.3f}"
    L += ["| Métrica | Valor |", "|---|---|",
          f"| Acuerdo global (misma decisión en A y B) | {_pc(c['acuerdo'])} ({sum(f['acuerdo'] for f in c['trampas'])}/{c['n']}) |",
          f"| Criterio de la tesis (acuerdo ≥ {c['umbral']:.0%}) | {'cumple' if c['cumple'] else 'no cumple'} |",
          f"| Kappa de Cohen (detectada sí/no) | {kappa} |",
          f"| Trampas detectadas A / B | {c['detectadas_a']} / {c['detectadas_b']} de {c['n']} |",
          f"| Brechas que generan riesgo A / B | {c['brechas_a']} / {c['brechas_b']} |",
          f"| Riesgos agrupados A / B | {c['riesgos_agrupados_a']} / {c['riesgos_agrupados_b']} |",
          f"| Jaccard de (sección, norma, artículo) | {c['jaccard']:.3f} (solo en A: {c['solo_a']}, solo en B: {c['solo_b']}) |", "",
          "| Trampa | Detectada en A | Detectada en B | Acuerdo |", "|---|---|---|---|"]
    L += [f"| {f['id']} | {'sí' if f['a'] else 'no'} | {'sí' if f['b'] else 'no'} | {'sí' if f['acuerdo'] else 'no'} |" for f in c["trampas"]]
    return "\n".join(L) + "\n"


def _cargar(ruta: str) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> dict:
    p = argparse.ArgumentParser(description="Estabilidad entre dos corridas de la misma oferta, modelo y perfil")
    p.add_argument("--a", required=True, help="JSON de resultados de la corrida A")
    p.add_argument("--b", required=True, help="JSON de resultados de la corrida B")
    p.add_argument("--oferta", required=True, help="P1, P2, P3 o P4")
    p.add_argument("--ground-truth", default=E.GROUND_TRUTH)
    p.add_argument("--salida", help="ruta de un .md con el informe (opcional; no se pisa un archivo existente)")
    a = p.parse_args(argv)
    gt = E.cargar_gt(a.oferta, a.ground_truth)
    if not gt:
        raise SystemExit(f"No hay trampas de la oferta {a.oferta} en {a.ground_truth}")
    c = comparar(_cargar(a.a), _cargar(a.b), gt, a.oferta)
    texto = informe_md(c)
    print(texto)
    if a.salida:
        if os.path.exists(a.salida):
            print(f"No se escribió {a.salida}: ya existe.", file=sys.stderr)
        else:
            with open(a.salida, "w", encoding="utf-8") as f:
                f.write(texto)
            print(f"Informe guardado en {a.salida}")
    return c


if __name__ == "__main__":
    main()
