# scripts/comentario.py
"""Comentario general del informe: lo redacta el modelo a partir de la decisión, los conteos y el registro de riesgos agrupados;
el código valida el texto y, si no es válido (o no hay riesgos), arma una plantilla con los mismos datos."""
import re
import logging

logger = logging.getLogger(__name__)

MIN_ORACIONES, MAX_ORACIONES = 2, 5
RE_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
RE_NORMA = re.compile(r"NORM_\d{2}")
RE_ARTICULO = re.compile(r"Arts?\.?\s*(\d+\.\d+)")
RE_ORACION = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])")


def conteo_texto(conteos: dict) -> str:
    return "; ".join(f"{k}: {v}" for k, v in conteos.items()) or "ninguno"


def registro_texto(riesgos: list) -> str:
    """Una línea por riesgo agrupado: título | clase | nivel | responsable | normas y artículos."""
    return "\n".join(
        f"{r.get('titulo')} | {r.get('clase')} | {r.get('nivel')} | {r.get('responsable')} | "
        + "; ".join(f"{c['norma']} Art. {c['articulo']}" for c in r.get("citas", []))
        for r in riesgos)


def validar_comentario(texto: str, riesgos: list):
    """(válido, motivo). Cada NORM_0X y cada Art. X.Y del texto tiene que estar en el registro; entre 2 y 5 oraciones."""
    normas = {c["norma"] for r in riesgos for c in r.get("citas", [])}
    articulos = {c["articulo"] for r in riesgos for c in r.get("citas", [])}
    fuera = [n for n in RE_NORMA.findall(texto) if n not in normas] + [f"Art. {a}" for a in RE_ARTICULO.findall(texto) if a not in articulos]
    if fuera:
        return False, f"cita fuera del registro: {', '.join(dict.fromkeys(fuera))}"
    oraciones = len([o for o in RE_ORACION.split(texto.strip()) if o.strip()])
    if not MIN_ORACIONES <= oraciones <= MAX_ORACIONES:
        return False, f"{oraciones} oraciones (se esperan de {MIN_ORACIONES} a {MAX_ORACIONES})"
    return True, ""


def plantilla(resumen: dict, riesgos: list) -> str:
    """Texto armado por código con la decisión, los conteos y las áreas responsables con riesgos de las clases más altas."""
    por_clase = resumen.get("por_clase", {})
    s1 = f"Decisión de aceptabilidad: {resumen.get('decision', 'N/D')}."
    if not riesgos:
        return f"{s1} No se identificaron riesgos."
    s2 = f"Se identificaron {len(riesgos)} riesgos; por nivel: {conteo_texto(resumen.get('por_nivel', {}))}; por clase: {conteo_texto(por_clase)}."
    altas = list(por_clase)[:-1] or list(por_clase)   # todas las clases salvo la menor (en orden de mayor a menor)
    areas = list(dict.fromkeys(r.get("responsable") for r in riesgos if r.get("clase") in altas and r.get("responsable")))
    nombre = " o ".join(altas)
    s3 = f"Los riesgos de clase {nombre} se concentran en: {'; '.join(areas)}." if areas else f"No hay riesgos de clase {nombre}."
    return f"{s1} {s2} {s3}"


def generar_comentario(resumen: dict, riesgos: list, cadena=None) -> dict:
    """{'texto', 'origen' ('modelo' | 'plantilla'), 'motivo' (por qué se usó la plantilla), 'llamo' (si se invocó al modelo)}.
    cadena: crear_cadena_comentario(llm); sin cadena o sin riesgos se usa la plantilla."""
    if not riesgos or cadena is None:
        return {"texto": plantilla(resumen, riesgos), "origen": "plantilla", "motivo": "sin riesgos" if not riesgos else "sin modelo", "llamo": False}
    eval_count = prompt_eval_count = None
    try:
        mensaje = cadena.invoke({"decision": resumen.get("decision", "N/D"), "conteo_nivel": conteo_texto(resumen.get("por_nivel", {})),
                                 "conteo_clase": conteo_texto(resumen.get("por_clase", {})), "registro": registro_texto(riesgos)})
        metadatos = getattr(mensaje, "response_metadata", None) or {}
        eval_count, prompt_eval_count = metadatos.get("eval_count"), metadatos.get("prompt_eval_count")
        texto = RE_THINK.sub("", str(getattr(mensaje, "content", mensaje))).strip()
        valido, motivo = validar_comentario(texto, riesgos)
    except Exception as e:
        texto, valido, motivo = "", False, f"falló la llamada: {e}"
    if valido:
        return {"texto": texto, "origen": "modelo", "motivo": "", "llamo": True, "eval_count": eval_count, "prompt_eval_count": prompt_eval_count}
    logger.warning(f"Comentario general del modelo descartado ({motivo}); se usa la plantilla.")
    return {"texto": plantilla(resumen, riesgos), "origen": "plantilla", "motivo": motivo, "llamo": True, "eval_count": eval_count, "prompt_eval_count": prompt_eval_count}
