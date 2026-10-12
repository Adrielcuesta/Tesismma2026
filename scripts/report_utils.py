# scripts/report_utils.py
import json
import os
from datetime import datetime
import logging
from typing import Optional

from .schemas import RiskReport

logger = logging.getLogger(__name__)

# Escala ordinal 1-2-3 para cada eje de la matriz de riesgo (probabilidad x impacto)
NIVEL_ORDINAL = {
    "bajo": 1, "baja": 1,
    "medio": 2, "media": 2,
    "alto": 3, "alta": 3,
}

# Umbrales de la exposición (1 a 9) para su lectura en la matriz 3x3
UMBRAL_EXPOSICION_ALTA = 6    # 6 y 9: Alta   (p. ej. Alto x Media, Alto x Alta)
UMBRAL_EXPOSICION_MEDIA = 3   # 3 y 4: Media  (p. ej. Medio x Baja, Medio x Media)

def calcular_exposicion(impacto: str, probabilidad: str) -> Optional[int]:
    """Exposición al riesgo = impacto x probabilidad, con escala 1-2-3 en cada eje
    (resultado entre 1 y 9). Devuelve None si alguna categoría no es reconocible.
    Es la convención clásica de la matriz de riesgo: no es una medición, porque el
    impacto y la probabilidad son estimaciones categóricas del LLM."""
    i = NIVEL_ORDINAL.get((impacto or "").lower().strip())
    p = NIVEL_ORDINAL.get((probabilidad or "").lower().strip())
    if i is None or p is None:
        return None
    return i * p

def nivel_exposicion(exposicion: Optional[int]) -> str:
    """Traduce la exposición (1-9) a Baja / Media / Alta según los umbrales fijados arriba."""
    if exposicion is None:
        return "N/D"
    if exposicion >= UMBRAL_EXPOSICION_ALTA:
        return "Alta"
    if exposicion >= UMBRAL_EXPOSICION_MEDIA:
        return "Media"
    return "Baja"

def asignar_estado_rag(impacto_str: str, probabilidad_str: str) -> str:
    """Asigna un estado RAG (Rojo, Ámbar, Verde) basado en el impacto y la probabilidad."""
    impacto = impacto_str.lower().strip()
    probabilidad = probabilidad_str.lower().strip()
    if impacto == "alto":
        return "Rojo" if probabilidad in ["media", "alta"] else "Ámbar"
    elif impacto == "medio":
        return "Rojo" if probabilidad == "alta" else ("Ámbar" if probabilidad == "media" else "Verde")
    elif impacto == "bajo":
        return "Ámbar" if probabilidad == "alta" else "Verde"
    return "Gris (Indeterminado)"

def formatear_y_guardar_reporte(
    risk_report_obj: RiskReport,
    nombre_original_pdf: str,
    output_path_dir: str,
    sufijo_nombre: str = ""
) -> Optional[str]:
    """Toma el objeto RiskReport validado, le añade metadatos finales y lo guarda como JSON."""
    logger.info("Procesando objeto RiskReport para guardado final (JSON)...")

    riesgos_con_estado = []
    # La exposición (impacto x probabilidad) y el respaldo en la Base de Conocimiento ya
    # fueron calculados en main.py; acá solo se añade el estado RAG (Rojo/Ámbar/Verde) y
    # el nivel textual de la exposición para la visualización.
    for riesgo_item in risk_report_obj.riesgos_identificados:
        estado_rag = asignar_estado_rag(riesgo_item.impacto_estimado, riesgo_item.probabilidad_estimada)
        riesgo_dict = riesgo_item.model_dump()
        riesgo_dict["estado_RAG_sugerido"] = estado_rag
        riesgo_dict["nivel_exposicion"] = nivel_exposicion(riesgo_item.exposicion_riesgo)
        riesgos_con_estado.append(riesgo_dict)

    reporte_final_dict = risk_report_obj.model_dump()
    # Reemplazamos la lista de riesgos con la versión enriquecida que tiene el estado RAG
    reporte_final_dict["riesgos_identificados_estructurados"] = riesgos_con_estado
    del reporte_final_dict["riesgos_identificados"]

    # Añadimos metadatos finales al reporte
    reporte_final_dict["timestamp_analisis"] = datetime.now().isoformat()
    display_name = nombre_original_pdf.replace('.pdf', '').replace('_', ' ').strip()
    reporte_final_dict["nombre_proyecto_analizado"] = display_name
    reporte_final_dict["nombre_archivo_original"] = nombre_original_pdf

    # Guardamos el archivo JSON
    clean_filename = "".join(c if c.isalnum() else "_" for c in os.path.splitext(nombre_original_pdf)[0])
    output_filename_json = f"analisis_riesgos_{clean_filename}{sufijo_nombre}.json"
    output_file_path_json = os.path.join(output_path_dir, output_filename_json)

    try:
        with open(output_file_path_json, 'w', encoding='utf-8') as f:
            json.dump(reporte_final_dict, f, ensure_ascii=False, indent=4)
        logger.info(f"Reporte JSON guardado en: {output_file_path_json}")
        return output_file_path_json
    except Exception as e_save:
        logger.error(f"Error crítico al guardar el archivo JSON de resultados: {e_save}", exc_info=True)
        return None
