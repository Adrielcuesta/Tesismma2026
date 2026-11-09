# scripts/main.py
import os
import sys
import logging
import json
import re
import time
import datetime
import threading
import httpx
from pydantic import ValidationError
from typing import Literal, Optional, Union, get_args, get_origin

from . import config, document_utils, vector_db_manager, rag_components, report_utils, dashboard_generator, lineamientos, motor_riesgos, clasificacion, comentario, costo
from .schemas import RiskReport, SourceChunk, LLMResponse, RiskItem, SeccionInforme, FragmentoRecuperado, FuenteNorma, VerificacionArticulo, ClasificacionRiesgo
from .report_utils import calcular_exposicion

logger = logging.getLogger(__name__)


class AnalisisError(Exception):
    """Falla conocida del análisis; su mensaje es el motivo real que se le muestra al usuario."""

# Modelo local fijo para el evaluador de evidencia CRAG-lite -- deliberadamente
# desacoplado de selected_llm_model_id, para que nunca consuma cuota de una API
# de pago.
EVALUADOR_EVIDENCIA_MODEL_ID = config.OLLAMA_MODEL
if not logger.handlers:
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s - %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.propagate = True

_RE_THINK = re.compile(r"<think>(.*?)</think>", re.DOTALL)
RAZONAMIENTO_MAX_CHARS = 1500


def _quitar_think(texto: str) -> str:
    """Quita los bloques <think>…</think> (si el modelo devuelve el razonamiento dentro del contenido)."""
    return _RE_THINK.sub("", texto).strip()


def _razonamiento(mensaje) -> str:
    """Razonamiento del mensaje (campo aparte o bloque <think> del contenido), recortado para auditoría."""
    texto = getattr(mensaje, "additional_kwargs", {}).get("reasoning_content") or ""
    if not texto:
        texto = "\n".join(_RE_THINK.findall(str(getattr(mensaje, "content", mensaje))))
    return texto.strip()[:RAZONAMIENTO_MAX_CHARS]


def _extraer_json(texto: str) -> str:
    """Recorta del primer '{' al último '}' (descarta cercos ```json y texto alrededor)."""
    texto = _quitar_think(texto)
    inicio, fin = texto.find("{"), texto.rfind("}")
    return texto[inicio:fin + 1] if inicio != -1 and fin > inicio else texto


_normalizaciones = {"n": 0}
_lock_normalizaciones = threading.Lock()


def normalizaciones_formato() -> int:
    """Cantidad de valores vacíos o nulos de tipo incorrecto que se normalizaron antes de validar (desde el arranque del proceso)."""
    return _normalizaciones["n"]


def normalizar_tipos_vacios(datos, esquema):
    """Red de seguridad antes de validar con pydantic: en campos opcionales numéricos o literales, '' -> null; en campos de texto obligatorios,
    null -> ''. Se guía por las anotaciones del esquema. Con una respuesta ya válida no cambia nada. Devuelve (datos, cantidad de cambios)."""
    if not isinstance(datos, dict):
        return datos, 0
    salida, cambios = dict(datos), 0
    for nombre, campo in esquema.model_fields.items():
        if nombre not in salida:
            continue
        args = get_args(campo.annotation) if get_origin(campo.annotation) is Union else (campo.annotation,)
        base = [a for a in args if a is not type(None)]
        admite_none = len(base) < len(args)
        valor = salida[nombre]
        if admite_none and isinstance(valor, str) and not valor.strip() and any(a in (int, float) or get_origin(a) is Literal for a in base):
            salida[nombre], cambios = None, cambios + 1
        elif valor is None and not admite_none and base == [str]:
            salida[nombre], cambios = "", cambios + 1
    return salida, cambios


def _validar_normalizando(texto: str, esquema):
    datos, n = normalizar_tipos_vacios(json.loads(_extraer_json(texto)), esquema)
    if n:
        with _lock_normalizaciones:
            _normalizaciones["n"] += n
    return esquema.model_validate(datos)


def _parsear_respuesta_llm(raw: str, llm, esquema=LLMResponse):
    """Parsea y valida la respuesta del LLM contra `esquema`. Si falla, hace UN reintento mostrándole el error."""
    try:
        return _validar_normalizando(raw, esquema)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"Respuesta del LLM inválida, se reintenta una vez con el error: {e}")
        prompt_reintento = (
            "Tu respuesta anterior no cumplió el formato JSON pedido.\n"
            f"ERROR DE VALIDACIÓN:\n{e}\n\n"
            f"RESPUESTA ANTERIOR:\n{raw}\n\n"
            "Devolvé ÚNICAMENTE el objeto JSON corregido, respetando exactamente el esquema pedido, "
            "sin texto adicional."
        )
        respuesta = llm.invoke(prompt_reintento)
        raw_reintento = getattr(respuesta, "content", respuesta)
        return _validar_normalizando(raw_reintento, esquema)


def _iniciar_log_de_analisis(directorio_proyecto: Optional[str] = None):
    """Guarda el log de una corrida hecha desde la app en la MISMA carpeta que el
    dashboard (datos/Resultados/<proyecto>/log_analisis_<fecha>.txt), para poder
    auditar después qué pasó en cada ejecución (modelo usado, resultado del
    evaluador de evidencia, errores). Devuelve el handler para cerrarlo al final,
    o None si no se pudo (en ese caso el análisis sigue igual, sin log a archivo)."""
    try:
        pdf_path = document_utils.obtener_ruta_pdf_proyecto(directorio_proyecto or config.DIRECTORIO_PROYECTO_ANALIZAR)
        if not pdf_path:
            return None
        nombre_pdf = os.path.basename(pdf_path)
        nombre_base = "".join(c for c in os.path.splitext(nombre_pdf)[0] if c.isalnum() or c in (' ', '_')).rstrip()
        carpeta = os.path.join(config.DIRECTORIO_RESULTADOS_BASE, nombre_base)
        os.makedirs(carpeta, exist_ok=True)
        marca_tiempo = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        ruta_log = os.path.join(carpeta, f"log_analisis_{marca_tiempo}.txt")
        handler = logging.FileHandler(ruta_log, encoding="utf-8")
        handler.marca_tiempo = marca_tiempo  # la reutilizan el JSON y el dashboard de esta corrida
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        root_logger = logging.getLogger()
        if root_logger.level > logging.INFO:
            root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)
        logger.info(f"📝 Log de este análisis guardándose en: {ruta_log}")
        return handler
    except Exception as e_log:
        logger.warning(f"No se pudo iniciar el log a archivo del análisis: {e_log}")
        return None


def _cerrar_log_de_analisis(handler):
    if handler is None:
        return
    try:
        logging.getLogger().removeHandler(handler)
        handler.close()
    except Exception:
        pass


# --- Análisis por sección de la oferta ---

def _segundos(t0: float) -> float:
    return round(time.perf_counter() - t0, 2)


def _guardar_y_generar_dashboard(reporte: RiskReport, nombre_pdf: str, marca_tiempo: str) -> str:
    """Guarda el JSON y el dashboard del reporte en datos/Resultados/<proyecto>/ y devuelve la ruta relativa del HTML."""
    nombre_base = "".join(c for c in os.path.splitext(nombre_pdf)[0] if c.isalnum() or c in (' ', '_')).rstrip()
    carpeta = os.path.join(config.DIRECTORIO_RESULTADOS_BASE, nombre_base)
    os.makedirs(carpeta, exist_ok=True)
    ruta_json = report_utils.formatear_y_guardar_reporte(reporte, nombre_pdf, carpeta, sufijo_nombre=f"_{marca_tiempo}")
    if not ruta_json: raise AnalisisError("No se pudo guardar el reporte JSON.")
    ruta_html = os.path.join(carpeta, f"dashboard_{nombre_base}_{marca_tiempo}.html")
    dashboard_generator.generar_dashboard_html(ruta_json_resultados=ruta_json, ruta_output_dashboard_html=ruta_html, info_tesis_config=config.INFO_TESIS)
    if not os.path.exists(ruta_html): raise AnalisisError("El dashboard HTML no fue generado.")
    return os.path.normpath(os.path.relpath(ruta_html, config.PROJECT_ROOT)).replace("\\", "/")


def _guardar_parcial(nombre_pdf: str, marca_tiempo: str, brechas: list, alertas: list, registro_tecnico: list, secciones: list, fragmentos: list, error: Exception) -> None:
    """Red de seguridad: si falla el cierre del análisis (armado de salidas, comentario, dashboard), guarda un JSON con lo ya calculado (registro_brechas,
    alertas, registro_tecnico y secciones) con el sufijo _parcial. Nunca levanta: el error original es el que se propaga."""
    try:
        nombre_base = "".join(c for c in os.path.splitext(nombre_pdf)[0] if c.isalnum() or c in (' ', '_')).rstrip()
        carpeta = os.path.join(config.DIRECTORIO_RESULTADOS_BASE, nombre_base)
        os.makedirs(carpeta, exist_ok=True)
        parcial = RiskReport(fragmentos_fuente=fragmentos, registro_brechas=brechas, alertas=alertas, registro_tecnico=registro_tecnico, secciones=secciones,
                             configuracion_analisis={"parcial": True, "error": f"{type(error).__name__}: {str(error)[:300]}"})
        ruta = report_utils.formatear_y_guardar_reporte(parcial, nombre_pdf, carpeta, sufijo_nombre=f"_{marca_tiempo}_parcial")
        logger.error(f"JSON parcial guardado en: {ruta}")
    except Exception as e_parcial:
        logger.error(f"No se pudo guardar el JSON parcial: {type(e_parcial).__name__}: {e_parcial}")


def _unir_y_deduplicar(riesgos: list) -> list:
    """Deduplica por (norma, artículo principal, cita normalizada), conservando el primero.
    Un riesgo sin cita no se deduplica: la clave quedaría vacía y colapsaría riesgos distintos."""
    vistos, unidos = set(), []
    for r in riesgos:
        cita = rag_components.normalizar_para_comparar(r.cita_oferta)
        if cita:
            principal = r.fuentes[0] if r.fuentes else None
            clave = (principal.norma if principal else "", principal.articulo if principal else "", cita)
            if clave in vistos:
                continue
            vistos.add(clave)
        unidos.append(r)
    return unidos


def _eval_count(mensaje):
    """Tokens generados en la llamada (eval_count de Ollama); None si el mensaje no lo informa."""
    return (getattr(mensaje, "response_metadata", None) or {}).get("eval_count")


def _estadisticas_tokens(llamadas):
    """{tipo de llamada: {'n', 'max', 'promedio'}} de los eval_count guardados en llamadas['eval_count']."""
    return {tipo: {"n": len(v), "max": max(v), "promedio": round(sum(v) / len(v), 1)} for tipo, v in llamadas.get("eval_count", {}).items() if v}


class Llamadas(dict):
    """Contadores de llamadas al modelo. `detalle` guarda un registro por llamada (duración, tokens de entrada y de salida); no entra en la comparación del dict."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.detalle = []


class LlamadaFallida(Exception):
    """El modelo no respondió en el tiempo límite o la respuesta se cortó por num_predict, también tras el reintento."""


_FALLOS_DE_TIEMPO = (LlamadaFallida, httpx.TimeoutException, TimeoutError)
MOTIVO_TIEMPO_AGOTADO = "el modelo no respondió en el tiempo límite"


def _registrar_llamada(llamadas, clave, par, etiqueta, t0, tokens_entrada, tokens_salida, intentos, exitosa):
    """Un registro por llamada al modelo (si `llamadas` lleva detalle): duracion_s es reloj de pared e incluye los reintentos; los tokens suman todos los intentos."""
    detalle = getattr(llamadas, "detalle", None)
    if detalle is not None:
        detalle.append({"tipo": clave, "par": par, "etiqueta": etiqueta, "duracion_s": round(time.perf_counter() - t0, 3), "prompt_eval_count": tokens_entrada,
                        "eval_count": tokens_salida, "intentos": intentos, "exitosa": exitosa})


def _invocar(cadena, entrada, etiqueta, llamadas, clave, par=None):
    """Una llamada al modelo con UN reintento si se agota el tiempo o la respuesta se corta por num_predict (done_reason 'length').
    Cuenta cada intento en llamadas[clave], cada fallo en llamadas['fallidas'] y guarda eval_count en llamadas['eval_count'][clave]; si `llamadas` es una
    Llamadas, registra además la duración y los tokens de la llamada en llamadas.detalle (par identifica el par sección-artículo). Si el segundo intento
    también falla, levanta LlamadaFallida."""
    causa = ""
    t0, tokens_entrada, tokens_salida = time.perf_counter(), 0, 0
    for intento in (1, 2):
        llamadas[clave] += 1
        try:
            mensaje = cadena.invoke(entrada)
        except (httpx.TimeoutException, TimeoutError) as e:
            causa = f"tiempo agotado ({type(e).__name__})"
        else:
            metadatos = getattr(mensaje, "response_metadata", None) or {}
            tokens_entrada += metadatos.get("prompt_eval_count") or 0
            tokens_salida += metadatos.get("eval_count") or 0
            if _eval_count(mensaje) is not None:
                llamadas.setdefault("eval_count", {}).setdefault(clave, []).append(_eval_count(mensaje))
            if metadatos.get("done_reason") == "length":
                causa = "respuesta cortada por num_predict"
            else:
                _registrar_llamada(llamadas, clave, par, etiqueta, t0, tokens_entrada, tokens_salida, intento, True)
                return mensaje
        llamadas["fallidas"] = llamadas.get("fallidas", 0) + 1
        logger.warning(f"{etiqueta}: {causa}; " + ("se reintenta una vez." if intento == 1 else "se descarta el par."))
    _registrar_llamada(llamadas, clave, par, etiqueta, t0, tokens_entrada, tokens_salida, 2, False)
    raise LlamadaFallida(causa)


def _alerta_sin_respuesta(seccion, textos, norma, articulo, ids):
    """Alerta de un par que el modelo no respondió: cita las oraciones indicadas y se ubica en la subsección de la primera."""
    primera = rag_components.normalizar_para_comparar(textos[ids[0]])
    subsecciones = seccion["subsecciones"]
    seccion_oferta = next((titulo for titulo, texto in subsecciones if primera in rag_components.normalizar_para_comparar(texto)),
                          subsecciones[0][0] if subsecciones else "")
    return {"seccion": seccion["id"], "seccion_oferta": seccion_oferta, "norma": norma, "articulo": articulo, "oraciones": ids,
            "cita": " ".join(textos[i] for i in ids), "motivo": MOTIVO_TIEMPO_AGOTADO, "estado": "tiempo_agotado"}


def _generar_lista(cadena, entrada, llm, id_sec, llamadas):
    """Modo lista: UNA llamada por sección con un reintento ante timeout o corte por largo. Devuelve (riesgos, mensaje).
    Si vuelve a fallar, la sección queda sin riesgos (mensaje None) con una advertencia y la corrida sigue."""
    raw = None
    try:
        mensaje = _invocar(cadena, entrada, f"{id_sec} (lista de riesgos)", llamadas, "lista")
        raw = getattr(mensaje, "content", mensaje)
        return _parsear_respuesta_llm(raw, llm).riesgos_identificados, mensaje
    except _FALLOS_DE_TIEMPO:
        logger.warning(f"{id_sec}: la sección queda sin riesgos, el modelo no respondió en el tiempo límite.")
        return [], None
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Respuesta del LLM para {id_sec} (string crudo):\n---INICIO---\n{raw}\n---FIN---")
        raise AnalisisError(f"La respuesta del modelo para la sección {id_sec} no cumplió el formato JSON ni tras reintentar: {e}") from e


def _verificar_seccion(seccion, docs, cadena_verif, cadena_clasif, llm_verif, llm_clasif, lin, t_sec, llamadas):
    """Modo verificación de una sección: una llamada por fragmento (veredicto), validación por código, y una llamada de
    clasificación (según los lineamientos de la empresa) por cada Incumple o Revisar válido. `lin` es el resultado de
    lineamientos.cargar_lineamientos. Devuelve (brechas, alertas, registro); registro tiene TODAS las verificaciones y descartes."""
    id_sec = seccion["id"]
    oraciones = document_utils.numerar_oraciones(seccion["texto"])
    seccion_numerada = rag_components.formatear_oraciones(oraciones)
    registro, pendientes, brechas, alertas = [], [], [], []
    textos = dict(oraciones)

    t0 = time.perf_counter()
    for d in docs:
        meta = {"seccion": id_sec, "norma": d.metadata.get("norma", ""), "articulo": str(d.metadata.get("articulo", ""))}
        try:
            mensaje = _invocar(cadena_verif, {"seccion_numerada": seccion_numerada, "articulo": rag_components.formatear_articulo(d)},
                               f"{id_sec} {meta['norma']} Art. {meta['articulo']} (verificación)", llamadas, "verificacion",
                               par=f"{id_sec}|{meta['norma']}|{meta['articulo']}")
            razon = {"razonamiento": _razonamiento(mensaje)} if config.THINKING_VERIFICACION else {}
            original = _parsear_respuesta_llm(getattr(mensaje, "content", mensaje), llm_verif, VerificacionArticulo)
        except _FALLOS_DE_TIEMPO:
            # no hay oraciones identificadas: el par se verificó contra toda la sección, que es la cita
            registro.append({**meta, "veredicto": None, "oraciones": [], "estado": "tiempo_agotado", "motivo": MOTIVO_TIEMPO_AGOTADO})
            if textos:
                alertas.append(_alerta_sin_respuesta(seccion, textos, meta["norma"], meta["articulo"], list(textos)))
            continue
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"{id_sec} {meta['norma']} Art. {meta['articulo']}: verificación con formato inválido tras reintentar, se descarta: {e}")
            registro.append({**meta, "veredicto": None, "oraciones": [], "estado": "descartada", "motivo": f"formato inválido tras reintentar: {str(e)[:200]}", "eval_count": _eval_count(mensaje), **razon})
            continue
        verificada, extra = rag_components.procesar_verificacion(original, oraciones, d.page_content)
        final = verificada or original
        registro.append({**meta, "veredicto": final.veredicto, "oraciones": final.oraciones, "explicacion": original.explicacion, "eval_count": _eval_count(mensaje), **extra, **razon})
        if verificada and verificada.veredicto in ("Incumple", "Revisar"):
            pendientes.append((d, verificada, extra["estado"] == "discrepancia_numerica"))
    t_sec["verificacion"] = _segundos(t0)

    t0 = time.perf_counter()
    items_2_6 = motor_riesgos.items_contenido_minimo_texto(lin["criterios"])
    for d, v, discrepancia in pendientes:
        norma, articulo = d.metadata.get("norma", ""), str(d.metadata.get("articulo", ""))
        meta = {"seccion": id_sec, "norma": norma, "articulo": articulo, "etapa": "clasificacion"}
        try:
            mensaje = _invocar(cadena_clasif, {"criterios": lin["texto_para_el_modelo"], "items_contenido_minimo": items_2_6,
                                               "articulo": rag_components.formatear_articulo(d), "seccion_numerada": seccion_numerada,
                                               "verificacion": v.model_dump_json(exclude_none=True)},
                               f"{id_sec} {norma} Art. {articulo} (clasificación)", llamadas, "clasificacion",
                               par=f"{id_sec}|{norma}|{articulo}")
            c = _parsear_respuesta_llm(getattr(mensaje, "content", mensaje), llm_clasif, ClasificacionRiesgo)
        except _FALLOS_DE_TIEMPO:
            registro.append({**meta, "veredicto": v.veredicto, "oraciones": v.oraciones, "estado": "tiempo_agotado", "motivo": MOTIVO_TIEMPO_AGOTADO})
            alertas.append(_alerta_sin_respuesta(seccion, textos, norma, articulo, v.oraciones))
            continue
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"{id_sec} {norma} Art. {articulo}: clasificación con formato inválido tras reintentar, se descarta: {e}")
            registro.append({**meta, "veredicto": v.veredicto, "oraciones": v.oraciones, "estado": "clasificacion_fallida", "motivo": str(e)[:200], "eval_count": _eval_count(mensaje)})
            continue
        primera = rag_components.normalizar_para_comparar(textos[v.oraciones[0]])
        subsecciones = seccion["subsecciones"]
        seccion_oferta = next((titulo for titulo, texto in subsecciones if primera in rag_components.normalizar_para_comparar(texto)),
                              subsecciones[0][0] if subsecciones else "")
        r = clasificacion.procesar_clasificacion(
            c, id_sec=id_sec, seccion_oferta=seccion_oferta, norma=norma, articulo=articulo, texto_articulo=d.page_content,
            oraciones=v.oraciones, textos=textos, criterios=lin["criterios"], parte=d.metadata.get("parte", 1) or 1,
            verificacion={"veredicto": v.veredicto, "explicacion": v.explicacion, "discrepancia_numerica": discrepancia})
        if r["tipo"] == "brecha":
            if discrepancia:
                r["brecha"]["marcas"].append("verificar calculo")
            r["brecha"]["eval_count"] = _eval_count(mensaje)
            brechas.append(r["brecha"])
        elif r["tipo"] == "descartada_por_calculo":   # queda en el registro de brechas (sin riesgo) y como alerta
            r["brecha"]["eval_count"] = _eval_count(mensaje)
            brechas.append(r["brecha"])
            alertas.append(r["alerta"])
        elif r["tipo"] == "alerta":
            alertas.append(r["alerta"])
        else:
            registro.append({**meta, "veredicto": c.veredicto, "oraciones": v.oraciones,
                             "estado": "no_es_riesgo" if r["tipo"] == "no_riesgo" else "descartada", "motivo": r["motivo"],
                             "eval_count": _eval_count(mensaje), **({"regla": r["regla"]} if r.get("regla") else {})})
    t_sec["clasificacion"] = _segundos(t0)
    return brechas, alertas, registro


def _analizar_por_secciones(selected_llm_model_id, force_recreate_db, usar_rag, marca_tiempo, directorio_kb, directorio_proyecto):
    """Oferta completa (sin truncar) -> secciones -> por sección: recuperación (K -> rerank top N), CRAG informativo y
    generación JSON -> validación de fuentes y citas por código -> unión sin tope de riesgos -> resumen final."""
    t_total = time.perf_counter()
    normalizaciones_al_inicio = normalizaciones_formato()
    tiempos = {}
    condicion = "sin_rag" if not usar_rag else ("rag_seccion" if config.USE_RERANKER else "rag_seccion_sin_reranker")
    # sin_rag no tiene artículos que verificar: siempre genera la lista de riesgos
    modo = config.MODO_GENERACION if usar_rag else "lista"
    verificacion = modo == "verificacion"
    usar_crag = usar_rag and config.USAR_CRAG
    llamadas = Llamadas({"verificacion": 0, "clasificacion": 0, "comentario": 0, "lista": 0})
    logger.info(f"--- ANÁLISIS POR SECCIÓN (Modelo: {selected_llm_model_id}, condición: {condicion}, modo: {modo}) ---")

    pdf_path = document_utils.obtener_ruta_pdf_proyecto(directorio_proyecto or config.DIRECTORIO_PROYECTO_ANALIZAR)
    if not pdf_path: raise AnalisisError("No se encontró ningún PDF o DOCX en la carpeta del proyecto a analizar.")
    nombre_pdf = os.path.basename(pdf_path)

    t0 = time.perf_counter()
    try:
        texto_oferta = document_utils.extraer_texto_oferta(pdf_path)
    except Exception as e:
        raise AnalisisError(f"No se pudo leer '{nombre_pdf}': {e}") from e
    tiempos["extraccion"] = _segundos(t0)
    if not texto_oferta:
        raise AnalisisError("No se pudo extraer texto del documento de la oferta (¿es un PDF escaneado, sin texto, o está dañado?).")

    t0 = time.perf_counter()
    secciones = document_utils.dividir_en_secciones(texto_oferta)
    tiempos["division"] = _segundos(t0)
    if not secciones: raise AnalisisError("No se pudo dividir la oferta en secciones.")
    logger.info(f"Oferta de {len(texto_oferta)} caracteres dividida en {len(secciones)} secciones.")

    vector_db = evaluador = None
    lin = None
    if verificacion:
        try:
            lin = lineamientos.cargar_lineamientos(config.DIRECTORIO_LINEAMIENTOS)
        except lineamientos.LineamientosError as e:
            raise AnalisisError(f"Lineamientos de la empresa: {e}") from e
        logger.info(f"Lineamientos cargados: {len(lin['texto_para_el_modelo'])} caracteres para el modelo, huella {lin['huella'][:12]}.")
    t0 = time.perf_counter()
    if usar_rag:
        carpeta_kb = directorio_kb or config.DIRECTORIO_NORMATIVA
        embedding_function = vector_db_manager.get_embedding_function(config.EMBEDDING_MODEL_NAME_OR_PATH)
        if not embedding_function: raise AnalisisError("No se pudo inicializar el modelo de embeddings.")
        vector_db = vector_db_manager.crear_o_cargar_chroma_db(
            chroma_db_path=config.CHROMA_DB_PATH_KB, docs_base_conocimiento_path=carpeta_kb, embedding_function=embedding_function,
            chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP, recrear_db_flag=force_recreate_db or config.RECREAR_DB,
            collection_name=config.CHROMA_COLLECTION_KB, manifest_path=config.CHROMA_MANIFEST_PATH_KB, por_articulos=True)
        if not vector_db: raise AnalisisError("No se pudo crear o cargar el índice de la KB por artículos (¿la carpeta de normas tiene PDFs o DOCX con texto?).")
        if usar_crag:
            # El evaluador CRAG usa el modelo local fijo, sin formato JSON (responde una sola palabra)
            llm_evaluador = rag_components.get_llm_instance(EVALUADOR_EVIDENCIA_MODEL_ID)
            if not llm_evaluador: raise AnalisisError(f"No se pudo inicializar el modelo '{EVALUADOR_EVIDENCIA_MODEL_ID}' del evaluador de evidencia.")
            evaluador = rag_components.crear_evaluador_evidencia(llm_evaluador)
    tiempos["carga_kb"] = _segundos(t0)

    if verificacion:
        llm_verif = rag_components.get_llm_instance(selected_llm_model_id, formato=VerificacionArticulo.model_json_schema(),
                                                    razonamiento=config.THINKING_VERIFICACION, num_predict=config.OLLAMA_NUM_PREDICT)
        llm_clasif = rag_components.get_llm_instance(selected_llm_model_id, formato=ClasificacionRiesgo.model_json_schema(),
                                                     num_predict=config.OLLAMA_NUM_PREDICT)
        if not llm_verif or not llm_clasif: raise AnalisisError(f"No se pudo inicializar el modelo '{selected_llm_model_id}'.")
        cadena_verif, cadena_clasif = rag_components.crear_cadena_verificacion(llm_verif), rag_components.crear_cadena_clasificacion(llm_clasif)
    else:
        llm_generacion = rag_components.get_llm_instance(selected_llm_model_id, formato=LLMResponse.model_json_schema(), num_predict=config.OLLAMA_NUM_PREDICT_LISTA)
        if not llm_generacion: raise AnalisisError(f"No se pudo inicializar el modelo '{selected_llm_model_id}'.")
        cadena = rag_components.crear_cadena_seccion(llm_generacion, usar_rag)

    informe_secciones, riesgos_todos, fragmentos_unicos, por_seccion, registro_tecnico = [], [], {}, [], []
    brechas_todas, alertas_todas = [], []
    for seccion in secciones:
        id_sec, t_sec = seccion["id"], {"id": seccion["id"]}
        if config.EXCLUIR_INTRODUCCION and document_utils.es_introduccion(seccion):
            logger.info(f"{id_sec} ({', '.join(seccion['titulos'])}): introducción excluida, 0 riesgos")
            informe_secciones.append(SeccionInforme(id=id_sec, titulos=seccion["titulos"]))
            por_seccion.append(t_sec)
            continue
        docs, candidatos, clasif_crag = [], None, None
        if usar_rag:
            t0 = time.perf_counter()
            candidatos, docs = rag_components.recuperar_seccion(vector_db, seccion, **({"tope": config.VERIFICAR_TOPE, "sin_preambulo": True, "con_union": True, "con_oraciones": True} if verificacion else {}))
            t_sec["recuperacion"] = _segundos(t0)
            if usar_crag:
                # CRAG por sección: solo informa, no bloquea la generación
                t0 = time.perf_counter()
                try:
                    respuesta = evaluador.invoke({"context": "\n\n".join(d.page_content for d in docs) or "(sin fragmentos recuperados)", "question": seccion["texto"]})
                    clasif_crag = rag_components.clasificar_evidencia(respuesta)
                except Exception as e_crag:
                    logger.warning(f"El evaluador de evidencia falló en {id_sec}, se continúa sin clasificarla: {e_crag}")
                t_sec["crag"] = _segundos(t0)
            for d in docs:
                m = d.metadata
                clave = (m.get("norma"), m.get("articulo"), m.get("parte"))
                score = m.get("relevance_score")
                previo = fragmentos_unicos.get(clave)
                if previo is None or (score or 0) > (previo.score_relevancia or 0):
                    fragmentos_unicos[clave] = SourceChunk(contenido=d.page_content, nombre_documento_fuente=m.get("fuente", "Desconocido"),
                                                           numero_pagina=m.get("pagina", -1), score_relevancia=score)
        logger.info(f"{id_sec} ({', '.join(seccion['titulos'])}): {len(docs)} fragmentos, evidencia {clasif_crag}")

        if verificacion:
            brechas, alertas, registro = _verificar_seccion(seccion, docs, cadena_verif, cadena_clasif, llm_verif, llm_clasif, lin, t_sec, llamadas)
            riesgos = []   # el modo verificación no genera RiskItem: sus resultados son brechas, riesgos agrupados y alertas
            brechas_todas.extend(brechas)
            alertas_todas.extend(alertas)
            registro_tecnico.extend(registro)
        else:
            t0 = time.perf_counter()
            entrada = {"fragmentos": rag_components.formatear_fragmentos(docs), "seccion": seccion["texto"]} if usar_rag else {"seccion": seccion["texto"]}
            riesgos, mensaje = _generar_lista(cadena, entrada, llm_generacion, id_sec, llamadas)
            if mensaje is None:
                registro_tecnico.append({"seccion": id_sec, "etapa": "lista", "estado": "tiempo_agotado", "motivo": MOTIVO_TIEMPO_AGOTADO})
            else:
                t_sec["tokens_prompt"] = (getattr(mensaje, "response_metadata", None) or {}).get("prompt_eval_count")
                registro_tecnico.append({"seccion": id_sec, "etapa": "lista", "estado": "ok", "eval_count": _eval_count(mensaje)})
            t_sec["generacion"] = _segundos(t0)

        t0 = time.perf_counter()
        if not verificacion:
            riesgos = rag_components.validar_riesgos(riesgos, rag_components.claves_fragmentos(docs), seccion["subsecciones"])
        for r in riesgos:
            r.exposicion_riesgo = calcular_exposicion(r.impacto_estimado, r.probabilidad_estimada)
        if config.CALCULAR_RESPALDO:
            for r, respaldo in zip(riesgos, rag_components.puntuar_riesgos_contra_evidencia([f"{r.descripcion_riesgo}. {r.explicacion_riesgo}" for r in riesgos], docs)):
                r.respaldo_base_conocimiento = respaldo
        t_sec["validacion"] = _segundos(t0)
        logger.info(f"{id_sec}: {len(brechas) if verificacion else len(riesgos)} " + ("brechas" if verificacion else "riesgos") + (f" ({len(docs)} verificaciones, {t_sec['verificacion']} s de verificación, {t_sec['clasificacion']} s de clasificación)" if verificacion else f" ({t_sec['generacion']} s de generación)"))

        riesgos_todos.extend(riesgos)
        informe_secciones.append(SeccionInforme(
            id=id_sec, titulos=seccion["titulos"], clasificacion_crag=clasif_crag,
            candidatos=[FuenteNorma(norma=d.metadata.get("norma", ""), articulo=str(d.metadata.get("articulo", ""))) for d in candidatos] if usar_rag else None,
            fragmentos=[FragmentoRecuperado(norma=d.metadata.get("norma", ""), articulo=str(d.metadata.get("articulo", "")), score=d.metadata.get("relevance_score"), parte=d.metadata.get("parte")) for d in docs]))
        por_seccion.append(t_sec)
    for etapa in ("recuperacion", "crag", "generacion", "verificacion", "clasificacion", "validacion"):
        tiempos[etapa] = round(sum(t.get(etapa, 0) for t in por_seccion), 2)
    tiempos["por_seccion"] = por_seccion
    tokens_prompt = {t["id"]: t["tokens_prompt"] for t in por_seccion if t.get("tokens_prompt") is not None}

    try:   # red de seguridad: si algo falla despues de verificar y clasificar, no se pierde el computo (JSON _parcial)
        t0 = time.perf_counter()
        riesgos_unidos = _unir_y_deduplicar(riesgos_todos)
        tiempos["union"] = _segundos(t0)
        logger.info(f"Unión: {len(riesgos_todos)} riesgos -> {len(riesgos_unidos)} tras deduplicar.")

        # Modo verificación: agrupamiento, solicitudes y resumen ejecutivo los arma el código (Art. 6, 8.3 y 8.4); sin llamada al LLM
        t0 = time.perf_counter()
        riesgos_agrupados, solicitudes, resumen_ejecutivo = [], [], None
        if verificacion:
            riesgos_agrupados, solicitudes, resumen_ejecutivo = clasificacion.armar_salidas(brechas_todas, lin["criterios"])
            t_com = time.perf_counter()
            cadena_comentario = None
            if riesgos_agrupados:
                try:   # temperatura 0 y seed fija; sin formato JSON (devuelve texto)
                    cadena_comentario = rag_components.crear_cadena_comentario(rag_components.get_llm_instance(selected_llm_model_id, num_predict=config.OLLAMA_NUM_PREDICT_COMENTARIO))
                except Exception as e_llm:
                    logger.warning(f"No se pudo inicializar el modelo para el comentario general, se usa la plantilla: {e_llm}")
            com = comentario.generar_comentario(resumen_ejecutivo, riesgos_agrupados, cadena_comentario)
            tiempos["comentario"] = _segundos(t_com)
            llamadas["comentario"] += int(com["llamo"])
            if com["llamo"]:
                llamadas.detalle.append({"tipo": "comentario", "par": None, "etiqueta": "comentario general", "duracion_s": tiempos["comentario"],
                                         "prompt_eval_count": com.get("prompt_eval_count") or 0, "eval_count": com.get("eval_count") or 0, "intentos": 1,
                                         "exitosa": com["origen"] == "modelo"})
            if com.get("eval_count") is not None:
                llamadas.setdefault("eval_count", {}).setdefault("comentario", []).append(com["eval_count"])
            resumen_ejecutivo.update(comentario_general=com["texto"], origen_comentario=com["origen"])
            logger.info(f"Comentario general: origen {com['origen']}" + (f" ({com['motivo']})" if com["motivo"] else ""))
            logger.info(f"Clasificación: {len(brechas_todas)} brechas -> {len(riesgos_agrupados)} riesgos, {len(solicitudes)} solicitudes, "
                        f"{len(alertas_todas)} alertas; decisión: {resumen_ejecutivo['decision']}.")
        tiempos["resumen_final"] = _segundos(t0)
        tiempos["total"] = _segundos(t_total)
        hardware = costo.detectar_hardware()
        costo_computacional = costo.resumen_costo(llamadas.detalle, tiempos["total"], selected_llm_model_id, hardware)
        costo_computacional["normalizaciones_formato"] = normalizaciones_formato() - normalizaciones_al_inicio

        reporte = RiskReport(
            riesgos_identificados=riesgos_unidos,
            fragmentos_fuente=list(fragmentos_unicos.values()),
            respuesta_cruda_llm=LLMResponse(riesgos_identificados=riesgos_unidos).model_dump_json(indent=2),
            registro_brechas=brechas_todas, riesgos=riesgos_agrupados, solicitudes=solicitudes, alertas=alertas_todas,
            resumen_ejecutivo=resumen_ejecutivo,
            lineamientos={"huella": lin["huella"], "caracteres_criterios": len(lin["texto_para_el_modelo"]), "documentos": lin["documentos"]} if lin else None,
            secciones=informe_secciones,
            registro_tecnico=registro_tecnico,
            configuracion_analisis={
                "modelo_llm_usado": selected_llm_model_id, "display_name_modelo": config.LLM_MODELS.get(selected_llm_model_id, {}).get("display_name", "N/A"),
                "condicion": condicion, "n_secciones": len(secciones), "k_recuperacion": config.K_RECUPERACION if usar_rag else "N/A",
                "top_n_por_seccion": config.TOP_N_POR_SECCION if usar_rag else "N/A",
                "reranker_max_length": config.RERANKER_MAX_LENGTH if usar_rag and config.USE_RERANKER else "N/A",
                "recuperacion_por_subseccion": config.RECUPERACION_POR_SUBSECCION if usar_rag else "N/A",
                "k_subseccion": config.K_SUBSECCION if usar_rag and config.RECUPERACION_POR_SUBSECCION else "N/A",
                "top_n_subseccion": config.TOP_N_SUBSECCION if usar_rag and config.RECUPERACION_POR_SUBSECCION else "N/A",
                "top_densa_subseccion": config.TOP_DENSA_SUBSECCION if usar_rag and verificacion and config.RECUPERACION_POR_SUBSECCION else "N/A",
                "oraciones_cifras": ({"n": config.ORACIONES_N, "cupo": config.ORACIONES_CUPO} if config.ORACIONES_CIFRAS else False) if usar_rag and verificacion else "N/A",
                "tope_fragmentos_por_seccion": (config.VERIFICAR_TOPE if verificacion else config.TOPE_FRAGMENTOS_SECCION) if usar_rag else "N/A",
                "modo_generacion": modo, "usar_crag": usar_crag,
                "temperature": 0 if config.LLM_MODELS.get(selected_llm_model_id, {}).get("provider") == "ollama" else "N/A",
                "seed": config.OLLAMA_SEED if config.LLM_MODELS.get(selected_llm_model_id, {}).get("provider") == "ollama" else "N/A",
                "thinking_verificacion": config.THINKING_VERIFICACION if verificacion else "N/A",
                "verif_temperature": config.VERIF_TEMPERATURE if verificacion and config.THINKING_VERIFICACION else "N/A",
                "verif_top_p": config.VERIF_TOP_P if verificacion and config.THINKING_VERIFICACION else "N/A",
                "verif_top_k": config.VERIF_TOP_K if verificacion and config.THINKING_VERIFICACION else "N/A",
                "llamadas_llm": {k: v for k, v in llamadas.items() if k in ("verificacion", "clasificacion", "comentario")} if verificacion else {"lista": llamadas["lista"]},
                "llamadas_fallidas": llamadas.get("fallidas", 0),
                "costo_computacional": costo_computacional, "hardware": hardware, "llamadas_detalle": llamadas.detalle,
                "tokens_generados_por_tipo": _estadisticas_tokens(llamadas),
                "excluir_introduccion": config.EXCLUIR_INTRODUCCION, "calcular_respaldo": config.CALCULAR_RESPALDO, "tiempos_s": tiempos,
                "tokens_prompt_por_seccion": tokens_prompt,
            })
        return _guardar_y_generar_dashboard(reporte, nombre_pdf, marca_tiempo)
    except Exception as e_cierre:
        logger.error(f"Fallo al cerrar el analisis ({type(e_cierre).__name__}: {e_cierre}); se guarda igual un JSON parcial con las brechas y el registro tecnico.")
        _guardar_parcial(nombre_pdf, marca_tiempo, brechas_todas, alertas_todas, registro_tecnico, informe_secciones, list(fragmentos_unicos.values()), e_cierre)
        raise


def _run_analysis_impl(
    selected_llm_model_id: str,
    force_recreate_db: bool = False,
    is_evaluation_mode: bool = False,
    eval_question: Optional[str] = None,
    eval_ground_truth: Optional[str] = None,
    db_connection: Optional[object] = None,
    usar_rag: bool = True,
    marca_tiempo: Optional[str] = None,
    directorio_kb: Optional[str] = None,
    directorio_proyecto: Optional[str] = None,
):
    if not is_evaluation_mode: logger.info(f"--- INICIANDO ANÁLISIS (Modelo: {selected_llm_model_id}) ---")
    # Cada ejecución guarda su JSON y su dashboard con esta marca en el nombre, para no
    # pisar los análisis anteriores del mismo proyecto (el log usa la misma marca).
    marca_tiempo = marca_tiempo or datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        config.inicializar_directorios_datos()

        # Análisis por sección (índice por artículos). El modo evaluación sigue con el flujo de abajo.
        if config.USAR_KB_ARTICULOS and not is_evaluation_mode:
            return _analizar_por_secciones(
                selected_llm_model_id, force_recreate_db, usar_rag, marca_tiempo, directorio_kb, directorio_proyecto)

        if db_connection:
            vector_db = db_connection
        else:
            embedding_function = vector_db_manager.get_embedding_function(config.EMBEDDING_MODEL_NAME_OR_PATH)
            if not embedding_function: raise AnalisisError("No se pudo inicializar el modelo de embeddings.")
            vector_db = vector_db_manager.crear_o_cargar_chroma_db(
                chroma_db_path=config.CHROMA_DB_PATH, docs_base_conocimiento_path=directorio_kb or config.DIRECTORIO_NORMATIVA,
                embedding_function=embedding_function, chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP,
                recrear_db_flag=force_recreate_db or config.RECREAR_DB
            )
        if not vector_db: raise AnalisisError("No se pudo crear o cargar la base vectorial (¿la Base de Conocimiento no tiene PDFs con texto?).")

        llm = rag_components.get_llm_instance(selected_llm_model_id)
        if not llm: raise AnalisisError(f"No se pudo inicializar el modelo '{selected_llm_model_id}'.")

        if not is_evaluation_mode:
            pdf_path_analizar_abs = document_utils.obtener_ruta_pdf_proyecto(directorio_proyecto or config.DIRECTORIO_PROYECTO_ANALIZAR)
            if not pdf_path_analizar_abs: raise AnalisisError("No se encontró ningún PDF o DOCX en la carpeta del proyecto a analizar.")
            nombre_pdf_proyecto_detectado = os.path.basename(pdf_path_analizar_abs)
            descripcion_nuevo_proyecto = document_utils.procesar_pdf_proyecto_para_analisis(pdf_path_analizar_abs, config.MAX_CHARS_PROYECTO)
        else:
            nombre_pdf_proyecto_detectado, descripcion_nuevo_proyecto = "Modo de Evaluación", eval_question

        if not descripcion_nuevo_proyecto:
            raise AnalisisError("No se pudo extraer texto del documento del proyecto (¿es un PDF escaneado, sin texto, o está dañado?).")

        # -------------------------Evaluador de evidencia CRAG-lite -----------------------------
        #
        # Se ejecuta ANTES de generar el análisis completo, y solo si se está
        # usando RAG (sin RAG no hay evidencia que evaluar por diseño). Reutiliza
        # el mismo retriever (embeddings + re-ranker) que usaría la generación
        # normal a costa de una segunda llamada de recuperación más adelante
        # (barata, no involucra al LLM), se mantiene la cadena de generación ya
        # probada (crear_cadena_rag) completamente intacta.
        clasificacion_evidencia = None
        fuentes_docs_evaluador = []
        if usar_rag:
            try:
                retriever = rag_components._construir_retriever(vector_db)
                consulta_recuperacion = descripcion_nuevo_proyecto[:config.MAX_CHARS_CONSULTA_RECUPERACION]
                fuentes_docs_evaluador = retriever.invoke(consulta_recuperacion)
                contexto_para_evaluador = "\n\n".join(d.page_content for d in fuentes_docs_evaluador) or "(sin fragmentos recuperados)"
                # El evaluador SIEMPRE usa un modelo local fijo (igual criterio que
                # el juez de Ragas), sin importar qué modelo haya elegido el usuario
                # para el analisis final. Asi el chequeo de calidad de evidencia
                # nunca consume cuota de una API paga (Gemini/Groq/Mistral), incluso
                # cuando esos son los modelos seleccionados para generar la respuesta.
                evaluador_llm = rag_components.get_llm_instance(EVALUADOR_EVIDENCIA_MODEL_ID)
                evaluador = rag_components.crear_evaluador_evidencia(evaluador_llm)
                respuesta_evaluador = evaluador.invoke({"context": contexto_para_evaluador, "question": descripcion_nuevo_proyecto})
                clasificacion_evidencia = rag_components.clasificar_evidencia(respuesta_evaluador)
                logger.info(f"Evaluador de evidencia (CRAG-lite, modelo local fijo {EVALUADOR_EVIDENCIA_MODEL_ID}): {clasificacion_evidencia}")
            except Exception as e_eval:
                logger.error(f"El evaluador de evidencia falló, se continúa sin él: {e_eval}", exc_info=True)
                clasificacion_evidencia = None  # Fallback: seguir el flujo normal si el evaluador mismo falla

        if clasificacion_evidencia == "INSUFICIENTE":
            mensaje_advertencia = (
                "La Base de Conocimiento no contiene evidencia con relación real al proyecto descrito. "
                "En vez de forzar una identificación de riesgos poco fundamentada, el sistema recomienda "
                "revisión manual por el equipo de gestión de riesgos, o ampliar la Base de Conocimiento "
                "con documentación relevante a este tipo de proyecto."
            )
            logger.warning(f"Evidencia insuficiente detectada. Análisis no generado. {mensaje_advertencia}")
            if is_evaluation_mode:
                return {
                    "question": eval_question,
                    "answer": json.dumps({"riesgos_identificados": []}, ensure_ascii=False),
                    "contexts": [d.page_content for d in fuentes_docs_evaluador],
                    "ground_truth": eval_ground_truth,
                    "schema_valido": True,
                    "usa_rag": usar_rag,
                    "evaluacion_evidencia": "INSUFICIENTE",
                }
            reporte_insuficiente = RiskReport(
                riesgos_identificados=[],
                fragmentos_fuente=[SourceChunk(
                    contenido=d.page_content,
                    nombre_documento_fuente=d.metadata.get('source_document', 'Desconocido'),
                    numero_pagina=d.metadata.get('page_number', -1),
                    score_relevancia=d.metadata.get('relevance_score')
                ) for d in fuentes_docs_evaluador],
                evaluacion_evidencia="INSUFICIENTE",
                advertencia_evidencia=mensaje_advertencia,
                configuracion_analisis={"modelo_llm_usado": selected_llm_model_id, "display_name_modelo": config.LLM_MODELS.get(selected_llm_model_id, {}).get("display_name", "N/A")}
            )
            nombre_base_proyecto = "".join(c for c in os.path.splitext(nombre_pdf_proyecto_detectado)[0] if c.isalnum() or c in (' ', '_')).rstrip()
            output_dir_especifico = os.path.join(config.DIRECTORIO_RESULTADOS_BASE, nombre_base_proyecto)
            os.makedirs(output_dir_especifico, exist_ok=True)
            ruta_json_guardado = report_utils.formatear_y_guardar_reporte(reporte_insuficiente, nombre_pdf_proyecto_detectado, output_dir_especifico, sufijo_nombre=f"_{marca_tiempo}")
            if not ruta_json_guardado: raise AnalisisError("No se pudo guardar el reporte JSON.")
            dashboard_html_filename = f"dashboard_{nombre_base_proyecto}_{marca_tiempo}.html"
            ruta_output_dashboard_html = os.path.join(output_dir_especifico, dashboard_html_filename)
            dashboard_generator.generar_dashboard_html(
                ruta_json_resultados=ruta_json_guardado, ruta_output_dashboard_html=ruta_output_dashboard_html,
                info_tesis_config=config.INFO_TESIS
            )
            if os.path.exists(ruta_output_dashboard_html):
                return os.path.normpath(os.path.relpath(ruta_output_dashboard_html, config.PROJECT_ROOT)).replace("\\", "/")
            raise AnalisisError("El dashboard HTML no fue generado.")
        # --- FIN evaluador de evidencia ---

        if usar_rag:
            # Se reutilizan los fragmentos que ya recuperó el evaluador (misma búsqueda, mismo
            # re-ranking): no se repite el paso más caro. Si no hubo recuperación previa, la
            # cadena busca por su cuenta como antes.
            qa_chain = rag_components.crear_cadena_rag(llm, vector_db, documentos_precalculados=fuentes_docs_evaluador or None)
            if not qa_chain: raise AnalisisError("No se pudo crear la cadena RAG.")
            logger.info("Invocando la cadena RAG principal...")
            respuesta_rag_dict = qa_chain.invoke({"query": descripcion_nuevo_proyecto})
            raw_json_string = respuesta_rag_dict.get("result", "{}")
            fuentes_docs = respuesta_rag_dict.get("source_documents", [])
        else:
            cadena_sin_rag = rag_components.crear_cadena_sin_rag(llm)
            if not cadena_sin_rag: raise AnalisisError("No se pudo crear la cadena sin RAG.")
            logger.info("Invocando la cadena SIN RAG (ablation, sin contexto recuperado)...")
            raw_json_string = cadena_sin_rag.invoke({"question": descripcion_nuevo_proyecto})
            fuentes_docs = []  # Sin RAG, por diseño, no hay fragmentos recuperados

        try:
            llm_response_obj = _parsear_respuesta_llm(raw_json_string, llm)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Error CRÍTICO al parsear o validar la respuesta JSON del LLM (tras 1 reintento): {e}")
            logger.error(f"Respuesta recibida del LLM (string crudo):\n---INICIO---\n{raw_json_string}\n---FIN---")
            if is_evaluation_mode:
                return {
                    "question": eval_question,
                    "answer": raw_json_string,
                    "contexts": [doc.page_content for doc in fuentes_docs],
                    "ground_truth": eval_ground_truth,
                    "schema_valido": False,
                    "usa_rag": usar_rag,
                }
            raise

        logger.info(f"Metadatos de la evidencia recuperada: {[doc.metadata for doc in fuentes_docs]}")

        # Dos indicadores separados por riesgo (no se mezclan en un solo número):
        #  - exposición = impacto x probabilidad (convención de matriz de riesgo, 1-9)
        #  - respaldo en la Base de Conocimiento = mejor score del re-ranker entre el
        #    texto del riesgo y los fragmentos recuperados (0-1). Solo fuera de la evaluación
        #    Ragas, para no sumar cómputo a las corridas masivas.
        logger.info("Calculando exposición al riesgo y respaldo en la Base de Conocimiento...")
        riesgos_generados = llm_response_obj.riesgos_identificados
        for riesgo in riesgos_generados:
            riesgo.exposicion_riesgo = calcular_exposicion(riesgo.impacto_estimado, riesgo.probabilidad_estimada)
        if not is_evaluation_mode:
            respaldos = rag_components.puntuar_riesgos_contra_evidencia(
                [f"{r.descripcion_riesgo}. {r.explicacion_riesgo}" for r in riesgos_generados],
                fuentes_docs,
            )
            for riesgo, respaldo in zip(riesgos_generados, respaldos):
                riesgo.respaldo_base_conocimiento = respaldo

        if is_evaluation_mode:
            return {
                "question": eval_question,
                "answer": llm_response_obj.model_dump_json(),
                "contexts": [doc.page_content for doc in fuentes_docs],
                "ground_truth": eval_ground_truth,
                "schema_valido": True,
                "usa_rag": usar_rag,
                "evaluacion_evidencia": clasificacion_evidencia,
            }

        logger.info("Ensamblando el reporte final...")

        fragmentos_fuente_mapeados = [
            SourceChunk(
                contenido=doc.page_content,
                nombre_documento_fuente=doc.metadata.get('source_document', 'Desconocido'),
                numero_pagina=doc.metadata.get('page_number', -1),
                score_relevancia=doc.metadata.get('relevance_score')
            ) for doc in fuentes_docs
        ]

        advertencia_ambigua = None
        if clasificacion_evidencia == "AMBIGUO":
            advertencia_ambigua = (
                "La evidencia recuperada de la Base de Conocimiento está temáticamente relacionada, "
                "pero es de carácter genérico y no aborda con especificidad los elementos concretos de "
                "este proyecto. Se recomienda revisar los riesgos identificados con especial cautela."
            )

        reporte_final = RiskReport(
            riesgos_identificados=llm_response_obj.riesgos_identificados,
            fragmentos_fuente=fragmentos_fuente_mapeados,
            respuesta_cruda_llm=llm_response_obj.model_dump_json(indent=2),
            evaluacion_evidencia=clasificacion_evidencia,
            advertencia_evidencia=advertencia_ambigua,
            configuracion_analisis={
                "modelo_llm_usado": selected_llm_model_id, "display_name_modelo": config.LLM_MODELS.get(selected_llm_model_id, {}).get("display_name", "N/A"),
                "reranker_top_n": config.RERANKER_TOP_N if config.USE_RERANKER else "N/A"
            }
        )

        nombre_base_proyecto = "".join(c for c in os.path.splitext(nombre_pdf_proyecto_detectado)[0] if c.isalnum() or c in (' ', '_')).rstrip()
        output_dir_especifico = os.path.join(config.DIRECTORIO_RESULTADOS_BASE, nombre_base_proyecto)
        os.makedirs(output_dir_especifico, exist_ok=True)
        ruta_json_guardado = report_utils.formatear_y_guardar_reporte(reporte_final, nombre_pdf_proyecto_detectado, output_dir_especifico, sufijo_nombre=f"_{marca_tiempo}")
        if not ruta_json_guardado: raise AnalisisError("No se pudo guardar el reporte JSON.")

        dashboard_html_filename = f"dashboard_{nombre_base_proyecto}_{marca_tiempo}.html"
        ruta_output_dashboard_html = os.path.join(output_dir_especifico, dashboard_html_filename)
        dashboard_generator.generar_dashboard_html(
            ruta_json_resultados=ruta_json_guardado, ruta_output_dashboard_html=ruta_output_dashboard_html,
            info_tesis_config=config.INFO_TESIS
        )
        if os.path.exists(ruta_output_dashboard_html):
            return os.path.normpath(os.path.relpath(ruta_output_dashboard_html, config.PROJECT_ROOT)).replace("\\", "/")
        raise AnalisisError("El dashboard HTML no fue generado.")
    except (ValidationError, TypeError, AnalisisError) as e:
        logger.error(f"Error en el análisis: {e}", exc_info=True); raise
    except Exception as e_main_flow:
        logger.error(f"Error catastrófico en el flujo principal: {e_main_flow}", exc_info=True)
        raise AnalisisError(str(e_main_flow)) from e_main_flow


def run_analysis(
    selected_llm_model_id: str,
    force_recreate_db: bool = False,
    is_evaluation_mode: bool = False,
    eval_question: Optional[str] = None,
    eval_ground_truth: Optional[str] = None,
    db_connection: Optional[object] = None,
    usar_rag: bool = True,
    directorio_kb: Optional[str] = None,
    directorio_proyecto: Optional[str] = None,
):
    """Punto de entrada público (misma firma de siempre, lo usan app.py y evaluate_rag.py).
    En modo app deja un log en la carpeta del dashboard; en modo evaluación no lo hace,
    porque evaluate_rag.py ya guarda su propio log en datos/Resultados/evaluaciones_rag/."""
    handler_log = None if is_evaluation_mode else _iniciar_log_de_analisis(directorio_proyecto)
    try:
        return _run_analysis_impl(
            selected_llm_model_id=selected_llm_model_id,
            force_recreate_db=force_recreate_db,
            is_evaluation_mode=is_evaluation_mode,
            eval_question=eval_question,
            eval_ground_truth=eval_ground_truth,
            db_connection=db_connection,
            usar_rag=usar_rag,
            marca_tiempo=getattr(handler_log, "marca_tiempo", None),
            directorio_kb=directorio_kb,
            directorio_proyecto=directorio_proyecto,
        )
    finally:
        _cerrar_log_de_analisis(handler_log)
