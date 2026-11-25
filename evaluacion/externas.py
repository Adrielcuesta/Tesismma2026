# evaluacion/externas.py
"""Lectura del ground truth de P6–P12 (prueba externa: ofertas de otro generador) llevado al formato de filas que ya usa evaluar.py. Misma lógica de detección que P1–P5:
este módulo solo cambia la lectura. Solo este módulo, evaluar.py y los tests leen evaluacion/ (nunca un prompt, el índice ni el pipeline).

Archivos (en evaluacion/, separador ;), uno por oferta:
- P<n>_trampas_v2.csv: id, oferta, seccion, fragmento_trampa, norma, articulo, cita_articulo, severidad, fuente, clase, regla_norm07, probabilidad, impacto, nivel, responsable,
  descripcion_riesgo, accion_mitigacion. No trae «tipo» (todas son amenazas), «articulos_equivalentes» ni «grupo»: si un archivo los trajera, se usan.
- P<n>_conformes_v2.csv: id, oferta, seccion, frase, norma, articulo, tipo (cumple, cumple_frontera) y motivo.
  Se quitó P6-C03 («La puesta en carga dinámica de la bancada se programará después de 28 días corridos…», NORM_01 4.2): la frase aparece dos veces en el texto de la oferta
  y verificar_gt_literal la marca como no reconocible (no se puede atribuir una brecha a una sola ocurrencia). Quedan 166 conformes en P6–P12 (24 en P6).
Normalización: «fuente» llega en minúsculas y con tildes en P6 («desvío», «excepción no acreditada») y en mayúsculas en el resto («DESVIO», «EXCEPCION_NO_ACREDITADA»): se lleva a
la forma de la clasificación (DESVIO, EXCEPCION_NO_ACREDITADA, INFORMACION_FALTANTE). «regla_norm07» llega como «NORM_07 Art. 3.3.c» (P6) o «3.3.c» (resto): queda «3.3.c».
La clase se escribe como evaluar.CLASES (Crítico, Mayor, Menor)."""
import os
import re

from . import evaluar as E
from .p5 import _clase, _clave, _texto

OFERTAS = tuple(f"P{n}" for n in range(6, 13))
FUENTES = ("DESVIO", "EXCEPCION_NO_ACREDITADA", "INFORMACION_FALTANTE")
NIVELES = ("Alto", "Medio", "Bajo")
RE_REGLA = re.compile(r"^\s*(?:NORM_07\s*)?(?:Art\.?\s*)?", re.IGNORECASE)


def es_externa(oferta: str) -> bool:
    return oferta in OFERTAS


def ruta_trampas(oferta: str, carpeta: str = E.AQUI) -> str:
    return os.path.join(carpeta, f"{oferta}_trampas_v2.csv")


def ruta_conformes(oferta: str, carpeta: str = E.AQUI) -> str:
    return os.path.join(carpeta, f"{oferta}_conformes_v2.csv")


def normalizar_fuente(valor) -> str:
    """«desvío», «DESVIO», «excepción no acreditada», «EXCEPCION_NO_ACREDITADA» -> DESVIO / EXCEPCION_NO_ACREDITADA; error si no es una fuente conocida."""
    f = _clave(valor).upper().replace(" ", "_").replace("-", "_")
    if f not in FUENTES:
        raise ValueError(f"fuente desconocida: «{valor}» (se esperaba {', '.join(FUENTES)}).")
    return f


def normalizar_regla(valor) -> str:
    """«NORM_07 Art. 3.3.c» o «3.3.c» -> «3.3.c»."""
    return RE_REGLA.sub("", _texto(valor)).strip()


def _nivel(valor, id_) -> str:
    n = _texto(valor).capitalize()
    if n not in NIVELES:
        raise ValueError(f"La trampa «{id_}» tiene un nivel desconocido: «{valor}».")
    return n


def _filas(ruta: str, oferta: str, campos: tuple) -> list:
    """Filas del CSV de la oferta (las de otra oferta, si las hubiera, se descartan); [] si el archivo no existe. Falta un campo obligatorio -> error."""
    if not os.path.isfile(ruta):
        return []
    filas = [r for r in E.leer_csv(ruta) if _texto(r.get("oferta")) == oferta]
    for r in filas:
        for c in campos:
            if not _texto(r.get(c)):
                raise ValueError(f"{os.path.basename(ruta)}: la fila «{r.get('id', '?')}» no tiene «{c}».")
    return filas


def cargar_trampas(oferta: str, carpeta: str = E.AQUI) -> list:
    """Filas con el formato de ground_truth_v3.csv (id, oferta, seccion, fragmento_trampa, norma, articulo, articulos_equivalentes, clase, nivel, responsable) más «tipo»,
    «fuente», «regla_norm07» y «grupo»; [] si el archivo no existe."""
    ruta = ruta_trampas(oferta, carpeta)
    salida = []
    for r in _filas(ruta, oferta, ("id", "seccion", "fragmento_trampa", "norma", "articulo", "fuente", "clase", "nivel", "responsable")):
        id_ = _texto(r["id"])
        salida.append({"id": id_, "oferta": oferta, "tipo": _clave(r.get("tipo") or "amenaza"), "seccion": _texto(r["seccion"]), "fragmento_trampa": _texto(r["fragmento_trampa"]),
                       "norma": _texto(r["norma"]), "articulo": _texto(r["articulo"]), "articulos_equivalentes": _texto(r.get("articulos_equivalentes")),
                       "fuente": normalizar_fuente(r["fuente"]), "clase": _clase(r["clase"]), "nivel": _nivel(r["nivel"], id_), "responsable": _texto(r["responsable"]),
                       "regla_norm07": normalizar_regla(r.get("regla_norm07")), "grupo": _texto(r.get("grupo")), "severidad": _texto(r.get("severidad")).capitalize()})
    return salida


def cargar_conformes(oferta: str, carpeta: str = E.AQUI) -> list:
    """Filas con el formato de espejos_conformes.csv («proyecto», «seccion», «cita_conforme», «norma», «articulo», «espejo_de_trampa») más id y veredicto_esperado (el «tipo»
    del CSV); [] si el archivo no existe."""
    ruta = ruta_conformes(oferta, carpeta)
    return [{"proyecto": f"Proyecto {oferta[1:]}", "id": _texto(r["id"]), "seccion": _texto(r["seccion"]), "cita_conforme": _texto(r["frase"]), "norma": _texto(r["norma"]),
             "articulo": _texto(r["articulo"]), "espejo_de_trampa": "", "veredicto_esperado": _texto(r.get("tipo"))}
            for r in _filas(ruta, oferta, ("id", "seccion", "frase", "norma", "articulo"))]
