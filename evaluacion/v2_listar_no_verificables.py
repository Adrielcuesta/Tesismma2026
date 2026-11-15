# evaluacion/v2_listar_no_verificables.py
"""Propuesta A de la v2: artículos de alcance, objeto o prevalencia que no se deberían verificar, identificados POR TÍTULO (nunca por número: hay requisitos en artículos 1.x).
Sin LLM ni red. Lee la KB con el chunker del pipeline (lo corre el usuario: lee datos/BaseConocimiento/Normativa) y la cruza con el ground truth.

Uso:
  python -m evaluacion.v2_listar_no_verificables [--ofertas P1 P2 P3 P4 P5] [--salida <md>]
Imprime los artículos que el criterio excluiría (norma, número, título), los títulos «dudosos» (se listan pero NO se excluyen) y el cruce con el ground truth: si alguna trampa
(o un artículo equivalente suyo) cae en un artículo excluido, lo avisa y el programa termina con código 1.

Criterio (el título normalizado, sin mayúsculas ni tildes, tiene que ser ENTERO uno de estos): objeto, alcance, campo de aplicación, ámbito de aplicación, orden de prevalencia,
prevalencia o precedencia; con, a lo sumo, «y carácter» / «y alcance» y un calificativo genérico (funcional, físico, general, técnico, documental). Un título con un complemento
específico («Objeto y alcance del SAT», «Objeto de la tabla de control…») NO se excluye: trata de un requisito concreto.

Como postproceso: cada brecha del registro_brechas trae el texto del artículo (`texto_articulo`, que empieza con «Art. X.Y. <título>»), de modo que el criterio se puede aplicar
sobre los JSON existentes sin volver a llamar al LLM (ver evaluacion/v2_medir_ab.py)."""
import argparse
import os
import re
import sys
import unicodedata

from . import evaluar as E

GENERICOS = r"(objeto|alcance|campo de aplicacion|ambito de aplicacion|orden de prevalencia|prevalencia|precedencia)"
RE_EXCLUIDO = re.compile(rf"^{GENERICOS}( y (caracter|alcance))?( (funcional|fisico|general|tecnico|documental))?( y (funcional|fisico))?$")
# Se listan para decidir a mano, pero no se excluyen
RE_DUDOSO = re.compile(r"^(referencias?|marco|normas? de referencia|documentos? de referencia|generalidades|definiciones|terminologia|vigencia)\b")
RE_PREFIJO = re.compile(r"^\s*art(?:\.|iculo)\s*\d+\.\d+\.?\s*", re.IGNORECASE)


def normalizar_titulo(titulo) -> str:
    """Minúsculas, sin tildes, sin el prefijo «Art. X.Y.», sin puntuación al final y con espacios simples."""
    t = unicodedata.normalize("NFD", str(titulo or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    t = RE_PREFIJO.sub("", t)
    return re.sub(r"\s+", " ", t).strip(" .:;,-")


def es_no_verificable(titulo) -> bool:
    """El título es de alcance, objeto o prevalencia (criterio de la propuesta A)."""
    return bool(RE_EXCLUIDO.match(normalizar_titulo(titulo)))


def es_dudoso(titulo) -> bool:
    return not es_no_verificable(titulo) and bool(RE_DUDOSO.match(normalizar_titulo(titulo)))


def titulo_de_texto_articulo(texto) -> str:
    """Título de un fragmento del índice: la primera línea sin «Art. X.Y.» (el chunker arma «Art. X.Y. <título>\\n<cuerpo>»)."""
    return RE_PREFIJO.sub("", str(texto or "").split("\n", 1)[0]).strip()


def titulo_de_brecha(brecha: dict) -> str:
    return titulo_de_texto_articulo(brecha.get("texto_articulo"))


def brecha_excluida(brecha: dict) -> bool:
    """Postproceso: la brecha cita un artículo cuyo título es de alcance, objeto o prevalencia."""
    return es_no_verificable(titulo_de_brecha(brecha))


def articulos_de_chunks(chunks: list) -> list:
    """[{norma, articulo, titulo}] únicos por (norma, artículo), en orden, sin preámbulo; el título sale de los metadatos del chunk (o de su primera línea)."""
    vistos, salida = set(), []
    for c in chunks:
        m = c.metadata
        clave = (m.get("norma"), str(m.get("articulo")))
        if m.get("articulo") == "preambulo" or clave in vistos:
            continue
        vistos.add(clave)
        salida.append({"norma": m.get("norma"), "articulo": str(m.get("articulo")), "titulo": m.get("titulo") or titulo_de_texto_articulo(c.page_content)})
    return salida


def _orden(a: dict):
    return (a["norma"] or "", [int(p) if p.isdigit() else 0 for p in a["articulo"].split(".")])


def clasificar(articulos: list) -> tuple:
    """(excluidos, dudosos), ordenados por norma y número."""
    return (sorted((a for a in articulos if es_no_verificable(a["titulo"])), key=_orden), sorted((a for a in articulos if es_dudoso(a["titulo"])), key=_orden))


def cruce_con_ground_truth(excluidos: list, trampas: list) -> list:
    """Trampas cuyo artículo (o un equivalente) está entre los excluidos: [{id, norma, articulo, titulo}]. Lo esperado es una lista vacía."""
    por_par = {(a["norma"], E._articulo(a["articulo"])): a for a in excluidos}
    salida = []
    for fila in trampas:
        for par in sorted(E.pares_trampa(fila)):
            if par in por_par:
                salida.append({"id": fila["id"], "norma": par[0], "articulo": par[1], "titulo": por_par[par]["titulo"]})
    return salida


def articulos_1x_de_trampas(articulos: list, trampas: list) -> list:
    """Trampas ancladas en artículos 1.x (que son requisitos y no se pueden perder por su número) con su título y si el criterio los conserva."""
    por_par = {(a["norma"], E._articulo(a["articulo"])): a for a in articulos}
    salida = []
    for fila in trampas:
        norma, art = fila["norma"].strip(), E._articulo(fila["articulo"])
        if art.startswith("1."):
            a = por_par.get((norma, art))
            salida.append({"id": fila["id"], "norma": norma, "articulo": art, "titulo": a["titulo"] if a else "(no está en la KB)", "conservado": not (a and es_no_verificable(a["titulo"]))})
    return salida


def informe_md(excluidos: list, dudosos: list, colisiones: list, trampas_1x: list, ofertas: list) -> str:
    fila = lambda a: f"| {a['norma']} | {a['articulo']} | {a['titulo']} |"
    L = ["# Artículos no verificables por título (propuesta A de la v2)", "",
         f"Ofertas cruzadas con el ground truth: {', '.join(ofertas) or 'ninguna'}.", "",
         f"## Excluidos por el criterio ({len(excluidos)})", "", "| Norma | Número | Título |", "|---|---|---|"] + [fila(a) for a in excluidos]
    L += ["", f"## Títulos dudosos: se listan, NO se excluyen ({len(dudosos)})", "", "| Norma | Número | Título |", "|---|---|---|"] + [fila(a) for a in dudosos]
    L += ["", "## Cruce con el ground truth", ""]
    if colisiones:
        L += ["**ATENCIÓN: hay trampas ancladas en un artículo excluido (el criterio las haría perder):**", "", "| Trampa | Norma | Artículo | Título |", "|---|---|---|---|"]
        L += [f"| {c['id']} | {c['norma']} | {c['articulo']} | {c['titulo']} |" for c in colisiones]
    else:
        L += ["Ninguna trampa (ni artículo equivalente) cae en un artículo excluido."]
    L += ["", "### Trampas en artículos 1.x (requisitos que no deben excluirse)", "", "| Trampa | Norma | Artículo | Título | Conservado |", "|---|---|---|---|---|"]
    L += [f"| {t['id']} | {t['norma']} | {t['articulo']} | {t['titulo']} | {'sí' if t['conservado'] else 'NO'} |" for t in trampas_1x]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Lista los artículos de alcance, objeto o prevalencia (por título) y los cruza con el ground truth")
    p.add_argument("--ofertas", nargs="+", default=["P1", "P2", "P3", "P4", "P5"], help="ofertas del ground truth con las que se cruza (P5 se omite si no está su ground truth)")
    p.add_argument("--salida", help="ruta de un .md con el informe (no se pisa un archivo existente)")
    a = p.parse_args(argv)
    from scripts import config, document_utils     # import tardío: leen la KB (datos/BaseConocimiento/Normativa)
    articulos = articulos_de_chunks(document_utils.cargar_kb_por_articulos(config.DIRECTORIO_NORMATIVA))
    if not articulos:
        print(f"No se encontraron artículos en {config.DIRECTORIO_NORMATIVA}.", file=sys.stderr)
        return 2
    excluidos, dudosos = clasificar(articulos)
    trampas, usadas = [], []
    for oferta in a.ofertas:
        gt = E.cargar_gt(oferta)
        if gt:
            trampas += gt
            usadas.append(oferta)
        else:
            print(f"{oferta}: no hay ground truth; se omite.", file=sys.stderr)
    colisiones = cruce_con_ground_truth(excluidos, trampas)
    texto = informe_md(excluidos, dudosos, colisiones, articulos_1x_de_trampas(articulos, trampas), usadas)
    print(texto)
    if a.salida:
        if os.path.exists(a.salida):
            print(f"No se escribió {a.salida}: ya existe.", file=sys.stderr)
        else:
            with open(a.salida, "w", encoding="utf-8") as f:
                f.write(texto)
    return 1 if colisiones else 0


if __name__ == "__main__":
    sys.exit(main())
