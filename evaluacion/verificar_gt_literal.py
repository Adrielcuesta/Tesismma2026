# evaluacion/verificar_gt_literal.py
"""Verificación del ground truth contra el texto de las ofertas P1–P4: ¿cada trampa y cada caso conforme aparece en la oferta?
Lo busca en cuatro niveles y lista los que no se encuentran en forma literal:
  1. literal: la frase tal cual es un fragmento del texto extraído de la oferta (el que ve el pipeline: scripts.document_utils.extraer_texto_oferta);
  2. normalizada: sin mayúsculas ni acentos, con «|» y saltos de línea de tabla como espacios y espacios colapsados;
  3. alfanumérica: solo letras y números (el criterio con que la curva de recuperación ubica una trampa en su sección);
y, aparte, dos controles de cómo cuentan los programas:
  - evaluar.py: ¿la frase (evaluar.norm, que NO quita «|» ni puntuación) está en las oraciones de alguna sección unidas con espacios, como queda la cita de una brecha? (los casos
    conformes solo usan los primeros 60 caracteres, como _frase_espejo). Si no, evaluar.py no puede encontrar esa trampa aunque el sistema cite la oración correcta.
  - curva: ¿la frase (alfanumérica) está en el texto de alguna sección que se verifica (sin la introducción)?

Uso (lo corre el usuario: lee datos/ProyectoAnalizar):
  python -m evaluacion.verificar_gt_literal [--ofertas P1 P2 P3 P4] [--salida evaluacion/diagnosticos]
Escribe verificar_gt_literal.md y verificar_gt_literal.csv."""
import argparse
import csv
import os
import sys

from . import evaluar as E

OFERTAS = ("P1", "P2", "P3", "P4")
DIAGNOSTICOS = os.path.join(E.AQUI, "diagnosticos")
CONOCIDOS = ("Caída de tensión en el tramo terminal", "Conductor de protección PE de la máquina")       # los dos que ya se sabía que no están literales (P1 / P2)
NIVELES = ("literal", "normalizada", "alfanumérica", "no encontrada")


def alfanumerico(texto) -> str:
    """Minúsculas, sin acentos y solo letras y números."""
    return "".join(c for c in E.norm(texto) if c.isalnum())


def normalizada(texto) -> str:
    """Minúsculas, sin acentos, con «|» y saltos de línea como espacios y espacios colapsados."""
    return E.norm(str(texto or "").replace("|", " "))


def nivel_de_coincidencia(frase: str, texto: str) -> str:
    """El primer nivel (literal, normalizada, alfanumérica) en que la frase aparece en el texto; «no encontrada» si en ninguno."""
    if frase and frase in texto:
        return NIVELES[0]
    if normalizada(frase) and normalizada(frase) in normalizada(texto):
        return NIVELES[1]
    if alfanumerico(frase) and alfanumerico(frase) in alfanumerico(texto):
        return NIVELES[2]
    return NIVELES[3]


def ve_evaluar(frase: str, es_conforme: bool, secciones: list) -> bool:
    """¿evaluar.py podría reconocer esta frase en la cita de una brecha? La cita une oraciones de una sección con espacios y se compara con evaluar.norm (que conserva «|» y la puntuación)."""
    buscada = E.norm(frase)[:60] if es_conforme else E.norm(frase)
    return any(buscada and buscada in E.norm(" ".join(o for _, o in s["oraciones"])) for s in secciones)


def ve_curva(frase: str, secciones: list):
    """(¿la curva ubica la frase?, id de la sección o None): alfanumérica dentro del texto de una sección que se verifica (sin la introducción)."""
    buscada = alfanumerico(frase)
    for s in secciones:
        if not s["introduccion"] and buscada and buscada in alfanumerico(s["texto"]):
            return True, s["id"]
    return False, None


def solo_en_introduccion(frase: str, secciones: list) -> bool:
    buscada = alfanumerico(frase)
    en = [s for s in secciones if buscada and buscada in alfanumerico(s["texto"])]
    return bool(en) and all(s["introduccion"] for s in en)


def analizar(oferta: str, texto: str, secciones: list, trampas: list, conformes: list) -> list:
    """Una fila por trampa y por caso conforme. secciones: [{id, titulos, texto, oraciones [(id, texto)], introduccion}]."""
    filas = []
    items = [("trampa", t["id"], t["fragmento_trampa"], False) for t in trampas] + [("conforme", f"{oferta}-C{k:02d}", c["cita_conforme"], True) for k, c in enumerate(conformes, 1)]
    for tipo, id_, frase, conforme in items:
        nivel = nivel_de_coincidencia(frase, texto)
        curva, seccion = ve_curva(frase, secciones)
        filas.append({"oferta": oferta, "tipo": tipo, "id": id_, "frase": frase, "nivel": nivel, "evaluar": ve_evaluar(frase, conforme, secciones), "curva": curva,
                      "seccion": seccion or "", "solo_introduccion": solo_en_introduccion(frase, secciones), "conocido": any(E.norm(k) in E.norm(frase) for k in CONOCIDOS)})
    return filas


def cargar_oferta(oferta: str) -> dict:
    """{'texto', 'secciones'} de la oferta con la división y la numeración de oraciones del pipeline (lee datos/ProyectoAnalizar)."""
    from scripts import document_utils
    from . import oferta_texto
    texto = document_utils.extraer_texto_oferta(oferta_texto.ruta_oferta(oferta))
    secciones = [{"id": s["id"], "titulos": s["titulos"], "texto": s["texto"], "oraciones": document_utils.numerar_oraciones(s["texto"]), "introduccion": document_utils.es_introduccion(s)}
                 for s in document_utils.dividir_en_secciones(texto)]
    return {"texto": texto, "secciones": secciones}


def resumen_md(filas: list) -> list:
    L = ["## Resumen por oferta", "", "| Oferta | Tipo | Total | Literal | Normalizada | Alfanumérica | No encontrada | evaluar.py no la ve | la curva no la ubica |", "|---|---|---|---|---|---|---|---|---|"]
    for oferta in dict.fromkeys(f["oferta"] for f in filas):
        for tipo in ("trampa", "conforme"):
            fs = [f for f in filas if f["oferta"] == oferta and f["tipo"] == tipo]
            if fs:
                L.append(f"| {oferta} | {tipo} | {len(fs)} | " + " | ".join(str(sum(f['nivel'] == n for f in fs)) for n in NIVELES) + f" | {sum(not f['evaluar'] for f in fs)} | {sum(not f['curva'] for f in fs)} |")
    return L + [""]


def informe_md(filas: list) -> str:
    no_literales = [f for f in filas if f["nivel"] != NIVELES[0]]
    L = ["# Verificación del ground truth contra el texto de las ofertas", "",
         "Niveles: **literal** (la frase tal cual está en el texto extraído de la oferta), **normalizada** (sin mayúsculas ni acentos, «|» y saltos de línea como espacios), **alfanumérica** "
         "(solo letras y números; el criterio de la curva). **evaluar.py** dice si `evaluar.norm` (que no quita «|» ni puntuación) encuentra la frase en las oraciones de alguna sección unidas con "
         "espacios, como queda la cita de una brecha; en los casos conformes solo cuentan los primeros 60 caracteres. **Curva**: la frase alfanumérica está en una sección que se verifica.", ""]
    L += resumen_md(filas)
    L += [f"## No encontradas en forma literal ({len(no_literales)} de {len(filas)})", ""]
    if not no_literales:
        L += ["Todas las frases del ground truth y todos los casos conformes están literales en el texto de su oferta.", ""]
    else:
        L += ["| Oferta | Tipo | Id | Nivel | evaluar.py | Curva | Sección | Conocido | Frase |", "|---|---|---|---|---|---|---|---|---|"]
        L += [f"| {f['oferta']} | {f['tipo']} | {f['id']} | {f['nivel']} | {'sí' if f['evaluar'] else '**no**'} | {'sí' if f['curva'] else '**no**'}"
              f"{' (solo en la introducción)' if f['solo_introduccion'] else ''} | {f['seccion'] or '—'} | {'sí' if f['conocido'] else ''} | {' '.join(f['frase'].split()).replace('|', '/')} |" for f in no_literales]
        L.append("")
    invisibles = [f for f in filas if not f["evaluar"] and f["tipo"] == "trampa"]
    L += ["## Lectura", "",
          f"- Trampas que `evaluar.py` no puede reconocer aunque el sistema cite la oración correcta (la frase, con `evaluar.norm`, no está en las oraciones unidas de ninguna sección): "
          f"{len(invisibles)}" + (": " + ", ".join(f["id"] for f in invisibles) + "." if invisibles else "."),
          f"- Casos conformes que `evaluar.py` no puede reconocer (nunca contarían como falsa alarma): {sum(not f['evaluar'] and f['tipo'] == 'conforme' for f in filas)}.",
          f"- Frases que la curva no ubica en ninguna sección que se verifica: {sum(not f['curva'] for f in filas)}"
          + (": " + ", ".join(f['id'] for f in filas if not f['curva']) + "." if any(not f['curva'] for f in filas) else "."), ""]
    return "\n".join(L)


def guardar_csv(filas: list, ruta: str) -> None:
    campos = ["oferta", "tipo", "id", "nivel", "evaluar", "curva", "seccion", "solo_introduccion", "conocido", "frase"]
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        for fila in filas:
            w.writerow({**{c: fila[c] for c in campos}, "frase": " ".join(fila["frase"].split()), **{c: int(fila[c]) for c in ("evaluar", "curva", "solo_introduccion", "conocido")}})


def main(argv=None):
    p = argparse.ArgumentParser(description="Busca cada trampa y cada caso conforme del ground truth en el texto de su oferta")
    p.add_argument("--ofertas", nargs="+", default=list(OFERTAS))
    p.add_argument("--salida", default=DIAGNOSTICOS)
    a = p.parse_args(argv)
    filas = []
    for oferta in a.ofertas:
        datos = cargar_oferta(oferta)
        filas += analizar(oferta, datos["texto"], datos["secciones"], E.cargar_gt(oferta), E.cargar_espejos(oferta))
    os.makedirs(a.salida, exist_ok=True)
    ruta_md, ruta_csv = os.path.join(a.salida, "verificar_gt_literal.md"), os.path.join(a.salida, "verificar_gt_literal.csv")
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(informe_md(filas) + "\n")
    guardar_csv(filas, ruta_csv)
    print(f"Guardado: {ruta_md}\nGuardado: {ruta_csv}", file=sys.stderr)
    return filas


if __name__ == "__main__":
    main()
