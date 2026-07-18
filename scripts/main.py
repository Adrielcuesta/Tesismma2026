import os
import sys
import logging
import json
from pydantic import ValidationError
from typing import Optional

from . import config, document_utils, vector_db_manager, rag_components, report_utils, dashboard_generator
from .schemas import RiskReport, SourceChunk, LLMResponse, RiskItem
from .report_utils import get_risk_severity_score

logger = logging.getLogger(__name__)

if not logger.handlers:
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s - %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.propagate = False

def run_analysis(
    selected_llm_model_id: str,
    force_recreate_db: bool = False,
    is_evaluation_mode: bool = False,
    eval_question: Optional[str] = None,
    eval_ground_truth: Optional[str] = None,
    db_connection: Optional[object] = None
):
    if not is_evaluation_mode:
        logger.info(f"--- INICIANDO ANÁLISIS (Modelo: {selected_llm_model_id}) ---")
    try:
        config.inicializar_directorios()

        if selected_llm_model_id not in config.LLM_MODELS_CONFIG:
            logger.error(f"Modelo {selected_llm_model_id} no configurado en config.py")
            return None
        
        model_config = config.LLM_MODELS_CONFIG[selected_llm_model_id]
        provider = model_config["provider"]
        
        llm = rag_components.get_llm_instance(provider, selected_llm_model_id)
        if llm is None:
            logger.error("Fallo al inicializar el LLM. Abortando análisis.")
            return None

        if db_connection:
            vector_db = db_connection
            logger.info("Usando conexión a base de datos proporcionada.")
        else:
            vector_db = vector_db_manager.initialize_db(force_recreate=force_recreate_db)
        
        if vector_db is None:
            logger.error("Fallo al inicializar ChromaDB. Abortando análisis.")
            return None

        if is_evaluation_mode and eval_question:
            descripcion_nuevo_proyecto = eval_question
            nombre_pdf_proyecto_detectado = "Evaluacion_RAG_Contexto_Simulado"
        else:
            archivos_proyecto = [f for f in os.listdir(config.DIRECTORIO_PROYECTO_ANALIZAR) if f.lower().endswith('.pdf')]
            if not archivos_proyecto:
                logger.error(f"No se encontró ningún archivo PDF en el directorio del proyecto: {config.DIRECTORIO_PROYECTO_ANALIZAR}")
                return None
            ruta_pdf_proyecto = os.path.join(config.DIRECTORIO_PROYECTO_ANALIZAR, archivos_proyecto[0])
            nombre_pdf_proyecto_detectado = archivos_proyecto[0]
            logger.info(f"Procesando el documento para análisis: {nombre_pdf_proyecto_detectado}")
            descripcion_nuevo_proyecto = document_utils.extraer_texto_pdf(ruta_pdf_proyecto)
            if not descripcion_nuevo_proyecto:
                logger.error("No se pudo extraer texto del PDF del proyecto.")
                return None

        qa_chain = rag_components.get_qa_chain(llm, vector_db)
        if qa_chain is None:
            logger.error("Fallo al crear la cadena QA. Abortando análisis.")
            return None

        logger.info("Invocando la cadena RAG principal...")
        respuesta_rag_dict = qa_chain.invoke({"input": descripcion_nuevo_proyecto})

        texto_respuesta = respuesta_rag_dict.get('answer', '')
        documentos_fuente = respuesta_rag_dict.get('context', [])

        logger.info("Análisis LLM completado. Procesando y estructurando resultados...")

        logger.info("Parseando y validando JSON del LLM con Pydantic...")
        texto_limpio = report_utils.limpiar_respuesta_json(texto_respuesta)
        
        try:
            datos_json = json.loads(texto_limpio)
            respuesta_validada = LLMResponse(**datos_json)
            logger.info("✅ JSON parseado y validado correctamente por Pydantic.")
        except json.JSONDecodeError as e:
            logger.error(f"Error de sintaxis JSON en la respuesta del LLM: {e}")
            logger.error(f"Texto problemático:\n{texto_limpio}")
            return None
        except ValidationError as e:
            logger.error(f"Error de validación Pydantic en la estructura del JSON: {e}")
            logger.error(f"JSON recibido:\n{json.dumps(datos_json, indent=2)}")
            return None

        if is_evaluation_mode:
            return {
                "answer": texto_respuesta,
                "contexts": [doc.page_content for doc in documentos_fuente]
            }

        fuentes_utilizadas = []
        for i, doc in enumerate(documentos_fuente):
            nombre_fuente = doc.metadata.get('source', 'Desconocido')
            fuentes_utilizadas.append(SourceChunk(
                chunk_id=f"chunk_{i+1}",
                source_document=os.path.basename(nombre_fuente),
                content_snippet=doc.page_content[:150] + "..." if len(doc.page_content) > 150 else doc.page_content,
                relevance_score=0.0
            ))

        riesgos_procesados = []
        for r in respuesta_validada.riesgos_identificados:
            riesgos_procesados.append(RiskItem(
                descripcion_riesgo=r.descripcion_riesgo,
                tipo_de_riesgo=r.tipo_de_riesgo,
                probabilidad=r.probabilidad,
                impacto=r.impacto,
                area_responsable=r.area_responsable,
                accion_mitigacion=r.accion_mitigacion,
                umbral_alerta=r.umbral_alerta,
                severity_score=get_risk_severity_score(r.probabilidad, r.impacto)
            ))
            
        riesgos_procesados.sort(key=lambda x: x.severity_score, reverse=True)

        reporte_final = RiskReport(
            project_name=nombre_pdf_proyecto_detectado,
            summary="Análisis de riesgos generado exitosamente por RAG.",
            identified_risks=riesgos_procesados,
            sources_used=fuentes_utilizadas,
            metadata={
                "llm_model": selected_llm_model_id,
                "reranker_used": "BAAI/bge-reranker-base" if config.USE_RERANKER else "Ninguno"
            }
        )

        nombre_base_proyecto = "".join(c for c in os.path.splitext(nombre_pdf_proyecto_detectado)[0] if c.isalnum() or c in (' ', '_')).rstrip()
        output_dir_especifico = os.path.join(config.DIRECTORIO_RESULTADOS_BASE, nombre_base_proyecto)
        os.makedirs(output_dir_especifico, exist_ok=True)
        
        ruta_json_guardado = report_utils.formatear_y_guardar_reporte(reporte_final, nombre_pdf_proyecto_detectado, output_dir_especifico)
        if not ruta_json_guardado:
            return None
        
        dashboard_html_filename = f"dashboard_{nombre_base_proyecto}.html"
        ruta_output_dashboard_html = os.path.join(output_dir_especifico, dashboard_html_filename)
        
        dashboard_generator.generar_dashboard_html(
            ruta_json_resultados=ruta_json_guardado, 
            ruta_output_dashboard_html=ruta_output_dashboard_html,
            info_tesis_config=config.INFO_TESIS
        )
        
        if os.path.exists(ruta_output_dashboard_html):
            return os.path.normpath(os.path.relpath(ruta_output_dashboard_html, config.PROJECT_ROOT)).replace("\\", "/")
        else:
            logger.error("El dashboard HTML no fue generado.")
            return None

    except Exception as e:
        logger.error(f"Error crítico en run_analysis: {e}", exc_info=True)
        return None