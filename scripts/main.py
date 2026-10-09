# scripts/main.py
import os
import sys
import logging
import json
import datetime
from pydantic import ValidationError
from typing import Optional

from . import config, document_utils, vector_db_manager, rag_components, report_utils, dashboard_generator
from .schemas import RiskReport, SourceChunk, LLMResponse, RiskItem
from .report_utils import get_risk_severity_score

logger = logging.getLogger(__name__)

# Modelo local fijo para el evaluador de evidencia CRAG-lite -- deliberadamente
# desacoplado de selected_llm_model_id, para que nunca consuma cuota de una API
# de pago (mismo criterio que RAGAS_JUDGE_MODEL_ID en evaluate_rag.py).
EVALUADOR_EVIDENCIA_MODEL_ID = "qwen2.5:7b-instruct"
if not logger.handlers:
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s - %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    # CORREGIDO: antes era 'False'. Con 'False', los errores de este módulo
    # nunca llegaban al archivo de log configurado por evaluate_rag.py -- solo
    # se veían en la consola en vivo. Esto nos dejó sin poder diagnosticar por
    # qué fallaron 2 modelos por completo en una ejecución anterior. Con 'True',
    # el error se sigue viendo en consola Y además queda guardado en el archivo.
    logger.propagate = True

def _iniciar_log_de_analisis():
    """Guarda el log de una corrida hecha desde la app en la MISMA carpeta que el
    dashboard (datos/Resultados/<proyecto>/log_analisis_<fecha>.txt), para poder
    auditar después qué pasó en cada ejecución (modelo usado, resultado del
    evaluador de evidencia, errores). Devuelve el handler para cerrarlo al final,
    o None si no se pudo (en ese caso el análisis sigue igual, sin log a archivo)."""
    try:
        pdf_path = document_utils.obtener_ruta_pdf_proyecto(config.DIRECTORIO_PROYECTO_ANALIZAR)
        if not pdf_path:
            return None
        nombre_pdf = os.path.basename(pdf_path)
        nombre_base = "".join(c for c in os.path.splitext(nombre_pdf)[0] if c.isalnum() or c in (' ', '_')).rstrip()
        carpeta = os.path.join(config.DIRECTORIO_RESULTADOS_BASE, nombre_base)
        os.makedirs(carpeta, exist_ok=True)
        ruta_log = os.path.join(carpeta, f"log_analisis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        handler = logging.FileHandler(ruta_log, encoding="utf-8")
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


def _run_analysis_impl(
    selected_llm_model_id: str,
    force_recreate_db: bool = False,
    is_evaluation_mode: bool = False,
    eval_question: Optional[str] = None,
    eval_ground_truth: Optional[str] = None,
    db_connection: Optional[object] = None,
    usar_rag: bool = True,
):
    if not is_evaluation_mode: logger.info(f"--- INICIANDO ANÁLISIS (Modelo: {selected_llm_model_id}) ---")
    try:
        config.inicializar_directorios_datos()

        if db_connection:
            vector_db = db_connection
        else:
            embedding_function = vector_db_manager.get_embedding_function(config.EMBEDDING_MODEL_NAME_OR_PATH)
            if not embedding_function: return None
            vector_db = vector_db_manager.crear_o_cargar_chroma_db(
                chroma_db_path=config.CHROMA_DB_PATH, docs_base_conocimiento_path=config.DIRECTORIO_BASE_CONOCIMIENTO,
                embedding_function=embedding_function, chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP,
                recrear_db_flag=force_recreate_db or config.RECREAR_DB
            )
        if not vector_db: return None

        llm = rag_components.get_llm_instance(selected_llm_model_id)
        if not llm: return None

        if not is_evaluation_mode:
            pdf_path_analizar_abs = document_utils.obtener_ruta_pdf_proyecto(config.DIRECTORIO_PROYECTO_ANALIZAR)
            if not pdf_path_analizar_abs: logger.error("No se encontró PDF en la carpeta a analizar."); return None
            nombre_pdf_proyecto_detectado = os.path.basename(pdf_path_analizar_abs)
            descripcion_nuevo_proyecto = document_utils.procesar_pdf_proyecto_para_analisis(pdf_path_analizar_abs, config.MAX_CHARS_PROYECTO)
        else:
            nombre_pdf_proyecto_detectado, descripcion_nuevo_proyecto = "Modo de Evaluación", eval_question

        if not descripcion_nuevo_proyecto: logger.error("La descripción del proyecto está vacía."); return None

        # --- NUEVO: Evaluador de evidencia CRAG-lite -----------------------------
        # Se ejecuta ANTES de generar el análisis completo, y solo si se está
        # usando RAG (sin RAG no hay evidencia que evaluar por diseño). Reutiliza
        # el mismo retriever (embeddings + re-ranker) que usaría la generación
        # normal -- a costa de una segunda llamada de recuperación más adelante
        # (barata, no involucra al LLM), se mantiene la cadena de generación ya
        # probada (crear_cadena_rag) completamente intacta.
        clasificacion_evidencia = None
        fuentes_docs_evaluador = []
        if usar_rag:
            try:
                retriever = rag_components._construir_retriever(vector_db)
                fuentes_docs_evaluador = retriever.invoke(descripcion_nuevo_proyecto)
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
            ruta_json_guardado = report_utils.formatear_y_guardar_reporte(reporte_insuficiente, nombre_pdf_proyecto_detectado, output_dir_especifico)
            if not ruta_json_guardado: return None
            dashboard_html_filename = f"dashboard_{nombre_base_proyecto}.html"
            ruta_output_dashboard_html = os.path.join(output_dir_especifico, dashboard_html_filename)
            dashboard_generator.generar_dashboard_html(
                ruta_json_resultados=ruta_json_guardado, ruta_output_dashboard_html=ruta_output_dashboard_html,
                info_tesis_config=config.INFO_TESIS
            )
            if os.path.exists(ruta_output_dashboard_html):
                return os.path.normpath(os.path.relpath(ruta_output_dashboard_html, config.PROJECT_ROOT)).replace("\\", "/")
            return None
        # --- FIN evaluador de evidencia ------------------------------------------

        if usar_rag:
            qa_chain = rag_components.crear_cadena_rag(llm, vector_db)
            if not qa_chain: return None
            logger.info("Invocando la cadena RAG principal...")
            respuesta_rag_dict = qa_chain.invoke({"query": descripcion_nuevo_proyecto})
            raw_json_string = respuesta_rag_dict.get("result", "{}")
            fuentes_docs = respuesta_rag_dict.get("source_documents", [])
        else:
            cadena_sin_rag = rag_components.crear_cadena_sin_rag(llm)
            if not cadena_sin_rag: return None
            logger.info("Invocando la cadena SIN RAG (ablation, sin contexto recuperado)...")
            raw_json_string = cadena_sin_rag.invoke({"question": descripcion_nuevo_proyecto})
            fuentes_docs = []  # Sin RAG, por diseño, no hay fragmentos recuperados

        if "```json" in raw_json_string:
            clean_json_string = raw_json_string.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_json_string:
            clean_json_string = raw_json_string.split("```")[1].split("```")[0].strip()
        else:
            clean_json_string = raw_json_string

        try:
            llm_response_data = json.loads(clean_json_string)
            llm_response_obj = LLMResponse.model_validate(llm_response_data)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Error CRÍTICO al parsear o validar la respuesta JSON del LLM: {e}")
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
        # --- FIN DE LA CORRECCIÓN ---

        logger.info(f"Metadatos de la evidencia recuperada: {[doc.metadata for doc in fuentes_docs]}")

        logger.info("Calculando score de confianza compuesto...")
        scores = [doc.metadata.get('relevance_score', 0.0) for doc in fuentes_docs if doc.metadata.get('relevance_score') is not None]
        max_relevance_score = max(scores) if scores else 0.5
        for riesgo in llm_response_obj.riesgos_identificados:
            severity_score = get_risk_severity_score(riesgo.impacto_estimado, riesgo.probabilidad_estimada)
            riesgo.score_confianza_compuesto = min((max_relevance_score * 0.6) + (severity_score * 0.4), 1.0)

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
        ruta_json_guardado = report_utils.formatear_y_guardar_reporte(reporte_final, nombre_pdf_proyecto_detectado, output_dir_especifico)
        if not ruta_json_guardado: return None

        dashboard_html_filename = f"dashboard_{nombre_base_proyecto}.html"
        ruta_output_dashboard_html = os.path.join(output_dir_especifico, dashboard_html_filename)
        dashboard_generator.generar_dashboard_html(
            ruta_json_resultados=ruta_json_guardado, ruta_output_dashboard_html=ruta_output_dashboard_html,
            info_tesis_config=config.INFO_TESIS
        )
        if os.path.exists(ruta_output_dashboard_html):
            return os.path.normpath(os.path.relpath(ruta_output_dashboard_html, config.PROJECT_ROOT)).replace("\\", "/")
        logger.error("El dashboard HTML no fue generado."); return None
    except (ValidationError, TypeError) as e:
        logger.error(f"Error de validación o tipo: {e}", exc_info=True); raise
    except Exception as e_main_flow:
        logger.error(f"Error catastrófico en el flujo principal: {e_main_flow}", exc_info=True); return None


def run_analysis(
    selected_llm_model_id: str,
    force_recreate_db: bool = False,
    is_evaluation_mode: bool = False,
    eval_question: Optional[str] = None,
    eval_ground_truth: Optional[str] = None,
    db_connection: Optional[object] = None,
    usar_rag: bool = True,
):
    """Punto de entrada público (misma firma de siempre, lo usan app.py y evaluate_rag.py).
    En modo app deja un log en la carpeta del dashboard; en modo evaluación no lo hace,
    porque evaluate_rag.py ya guarda su propio log en datos/Resultados/evaluaciones_rag/."""
    handler_log = None if is_evaluation_mode else _iniciar_log_de_analisis()
    try:
        return _run_analysis_impl(
            selected_llm_model_id=selected_llm_model_id,
            force_recreate_db=force_recreate_db,
            is_evaluation_mode=is_evaluation_mode,
            eval_question=eval_question,
            eval_ground_truth=eval_ground_truth,
            db_connection=db_connection,
            usar_rag=usar_rag,
        )
    finally:
        _cerrar_log_de_analisis(handler_log)
