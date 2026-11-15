# evaluacion/p5.py
"""Lectura del ground truth y de los controles negativos de P5 (conjunto ciego) con el esquema propio de P5, llevados al formato de filas que ya usa evaluar.py.
Solo este módulo, evaluar.py y los tests leen evaluacion/ (nunca un prompt, el índice ni el pipeline).

Archivos (en evaluacion/), con el esquema verificado contra los archivos reales:
- ground_truth_P5.json: lista de objetos con id, proyecto, tipo («amenaza» u «oportunidad»), norma, articulo, fragmento_trampa, fuente_riesgo, clase_desvio («Critico», «Mayor»,
  «Menor» o null en las oportunidades), nivel, responsable y campos descriptivos que evaluar.py no usa (titulo, enunciado, regla_norm07, categoria_rbs, probabilidad, impacto…).
  NO trae «seccion», «articulos_equivalentes» ni «grupo».
- mapa_trampas_P5.csv (;): id, proyecto, documento, seccion, fragmento_trampa, norma, articulo, severidad, responsable. De acá sale la sección de cada trampa; el fragmento, la norma
  y el artículo tienen que coincidir con los del JSON (si no, error).
- controles_negativos_P5.json: lista de objetos con id, proyecto, norma, articulo (puede traer varios: «2.3; 2.5; 2.6»), veredicto_esperado, cita, seccion y motivo. Los controles
  sin cita traen cita y seccion con el texto «None»: se leen como vacíos y evaluar.py los cuenta por artículo.

Artículos equivalentes y agrupamiento: no están en los archivos. Vienen de la consigna del autor del ground truth para P5 (evaluacion/diagnosticos/v2_fase0.md, sección «P5»):
P5-03-IF también NORM_05 1.6, P5-02-IF también NORM_02 2.15, y el grupo P5-02-EX + P5-02-D1 + P5-02-IF (las tres sobre la sección 4.3 y NORM_02). Si un archivo trajera
«articulos_equivalentes» o «grupo», manda el archivo. El prefijo P5-NN NO es un grupo: es el número de la norma (P5-02-D2 es de otra sección)."""
import csv
import json
import os
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
GROUND_TRUTH_P5 = os.path.join(AQUI, "ground_truth_P5.json")
CONTROLES_P5 = os.path.join(AQUI, "controles_negativos_P5.json")
MAPA_P5 = os.path.join(AQUI, "mapa_trampas_P5.csv")
EQUIVALENTES_P5 = {"P5-03-IF": "NORM_05 1.6", "P5-02-IF": "NORM_02 2.15"}
GRUPOS_P5 = {"P5-02": ("P5-02-EX", "P5-02-D1", "P5-02-IF")}
CLASES = {"critico": "Crítico", "mayor": "Mayor", "menor": "Menor"}      # como ground_truth_v3.csv y evaluar.CLASES
VACIOS = ("", "none", "null", "nan")


def _clave(texto) -> str:
    t = unicodedata.normalize("NFD", str(texto or ""))
    return " ".join("".join(c for c in t if unicodedata.category(c) != "Mn").lower().split())


def _texto(valor) -> str:
    """El valor como texto; vacío si es None o un marcador de vacío («None», «null»)."""
    t = "" if valor is None else str(valor).strip()
    return "" if t.lower() in VACIOS else t


def _leer_json(ruta: str):
    with open(ruta, encoding="utf-8-sig") as f:
        datos = json.load(f)
    if not isinstance(datos, list):
        raise ValueError(f"{os.path.basename(ruta)}: se esperaba una lista de objetos.")
    return datos


def _obligatorio(entrada: dict, campo: str, archivo: str) -> str:
    valor = _texto(entrada.get(campo))
    if not valor:
        raise ValueError(f"{archivo}: la entrada «{entrada.get('id', '?')}» no tiene «{campo}».")
    return valor


def _tipo(valor) -> str:
    t = _clave(valor or "amenaza")
    if t not in ("amenaza", "oportunidad"):
        raise ValueError(f"tipo desconocido: «{valor}» (se esperaba amenaza u oportunidad).")
    return t


def _clase(valor) -> str:
    """«Critico» -> «Crítico» (la grafía de evaluar.CLASES); vacío si no hay clase (oportunidades)."""
    t = _texto(valor)
    if not t:
        return ""
    if _clave(t) not in CLASES:
        raise ValueError(f"clase desconocida: «{valor}» (se esperaba Crítico, Mayor o Menor).")
    return CLASES[_clave(t)]


def cargar_mapa(ruta: str = MAPA_P5) -> dict:
    """{id: fila} de mapa_trampas_P5.csv."""
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return {fila["id"].strip(): fila for fila in csv.DictReader(f, delimiter=";")}


def cargar_trampas(ruta: str = GROUND_TRUTH_P5, ruta_mapa: str = MAPA_P5, equivalentes: dict = None, grupos: dict = None) -> list:
    """Filas con el formato de ground_truth_v3.csv (id, oferta, seccion, fragmento_trampa, norma, articulo, articulos_equivalentes, clase, nivel, responsable) más «tipo»,
    «fuente» y «grupo»; [] si el ground truth no existe. La sección sale del mapa; sin mapa, o con una trampa que no está en él o que no coincide, falla."""
    if not os.path.isfile(ruta):
        return []
    equivalentes = EQUIVALENTES_P5 if equivalentes is None else equivalentes
    grupos = GRUPOS_P5 if grupos is None else grupos
    if not os.path.isfile(ruta_mapa):
        raise ValueError(f"Falta {os.path.basename(ruta_mapa)}: la sección de cada trampa de P5 sale de ese archivo.")
    archivo, mapa, filas = os.path.basename(ruta), cargar_mapa(ruta_mapa), []
    for e in _leer_json(ruta):
        id_ = _obligatorio(e, "id", archivo)
        frase, norma, articulo = (_obligatorio(e, c, archivo) for c in ("fragmento_trampa", "norma", "articulo"))
        m = mapa.get(id_)
        if m is None:
            raise ValueError(f"La trampa «{id_}» no está en {os.path.basename(ruta_mapa)}.")
        if _clave(m.get("fragmento_trampa")) != _clave(frase) or (_texto(m.get("norma")), _texto(m.get("articulo"))) != (norma, articulo):
            raise ValueError(f"La trampa «{id_}» no coincide entre {archivo} y {os.path.basename(ruta_mapa)} (fragmento, norma o artículo).")
        seccion = _texto(e.get("seccion")) or _texto(m.get("seccion"))
        if not seccion:
            raise ValueError(f"La trampa «{id_}» no tiene sección en {os.path.basename(ruta_mapa)}.")
        eq = e.get("articulos_equivalentes") if _texto(e.get("articulos_equivalentes")) else equivalentes.get(id_, "")
        filas.append({"id": id_, "oferta": "P5", "tipo": _tipo(e.get("tipo")), "seccion": seccion, "fragmento_trampa": frase, "norma": norma, "articulo": articulo,
                      "articulos_equivalentes": "; ".join(eq) if isinstance(eq, list) else str(eq), "fuente": _texto(e.get("fuente_riesgo")).upper(),
                      "clase": _clase(e.get("clase") or e.get("clase_desvio")), "nivel": _texto(e.get("nivel")),
                      "responsable": _texto(e.get("responsable")) or _texto(m.get("responsable")), "grupo": _texto(e.get("grupo"))})
    ids = {f["id"] for f in filas}
    faltan = sorted({i for i in equivalentes if i not in ids} | {i for miembros in grupos.values() for i in miembros if i not in ids})
    if faltan:
        raise ValueError(f"Los equivalentes o grupos de P5 nombran trampas que no están en {archivo}: {', '.join(faltan)}.")
    for grupo, miembros in grupos.items():
        for f in filas:
            if f["id"] in miembros and not f["grupo"]:
                f["grupo"] = grupo
    return filas


def cargar_controles(ruta: str = CONTROLES_P5) -> list:
    """Filas con el formato de espejos_conformes.csv («proyecto», «seccion», «cita_conforme», «norma», «articulo», «espejo_de_trampa») más id y veredicto_esperado;
    [] si el archivo no existe. Un control sin cita (null, vacío o «None») queda con cita_conforme vacía: evaluar.py lo cuenta por artículo."""
    if not os.path.isfile(ruta):
        return []
    archivo = os.path.basename(ruta)
    return [{"proyecto": "Proyecto 5", "id": _texto(e.get("id")), "seccion": _texto(e.get("seccion")), "cita_conforme": _texto(e.get("cita")),
             "norma": _obligatorio(e, "norma", archivo), "articulo": _obligatorio(e, "articulo", archivo), "espejo_de_trampa": _texto(e.get("espejo_de_trampa")),
             "veredicto_esperado": _texto(e.get("veredicto_esperado"))}
            for e in _leer_json(ruta)]
