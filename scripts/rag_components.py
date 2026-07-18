import logging
import os
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

from .schemas import LLMResponse
from . import config

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE_STR = """
Eres un asistente de IA experto en la identificación y evaluación de riesgos para proyectos de instalación de maquinaria industrial.
Tu tarea es analizar la descripción del "NUEVO PROYECTO" y, basándote ÚNICAMENTE en el "CONTEXTO PROPORCIONADO", identificar una lista de posibles riesgos.

CONTEXTO PROPORCIONADO:
{context}

NUEVO PROYECTO (PREGUNTA DEL USUARIO):
{input}

INSTRUCCIONES ESTRICTAS PARA LA RESPUESTA:
1.  Tu respuesta DEBE ser un único objeto JSON. NO incluyas ningún texto antes o después del objeto JSON.
2.  El objeto JSON debe tener UNA SOLA CLAVE PRINCIPAL: "riesgos_identificados".
3.  El valor de "riesgos_identificados" debe ser una lista de objetos.
4.  Cada objeto de la lista representa un riesgo y debe contener EXACTAMENTE los siguientes 7 campos:
    a. "descripcion_riesgo": Una descripción clara y concisa del riesgo.
    b. "tipo_de_riesgo": Clasificación del riesgo (ej. Operativo, Financiero, Seguridad, Reputacional).
    c. "probabilidad": "Alta", "Media" o "Baja".
    d. "impacto": "Alto", "Medio" o "Bajo".
    e. "area_responsable": El departamento o rol responsable (ej. "Mantenimiento", "HSE", "Logística").
    f. "accion_mitigacion": Una o dos acciones concretas para prevenir o reducir el impacto.
    g. "umbral_alerta": El indicador (KPI/KRI) o evento que dispara la acción de mitigación.
"""

def get_llm_instance(provider: str, model_id: str):
    api_key_env = config.LLM_MODELS_CONFIG[model_id].get("api_key_env")
    api_key = os.getenv(api_key_env) if api_key_env else None

    logger.info(f"Intentando inicializar el modelo: '{model_id}' del proveedor: '{provider}'")

    if api_key_env and not api_key:
        logger.error(f"Clave API no encontrada. Asegúrese de que la variable de entorno '{api_key_env}' esté definida en su archivo .env.")
        raise ValueError(f"Clave API no encontrada para el modelo {model_id}")

    try:
        if provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_id,
                google_api_key=api_key,
                temperature=0.2
            )
        elif provider == "groq":
            from langchain_groq import ChatGroq
            return ChatGroq(
                model_name=model_id, 
                api_key=api_key,
                temperature=0.2
            )
        else:
            logger.error(f"Proveedor '{provider}' no implementado.")
            return None
    except Exception as e:
        logger.error(f"Error inicializando el LLM {provider} ({model_id}): {e}")
        return None

def get_qa_chain(llm, vector_db_instance):
    if vector_db_instance is None:
        logger.error("No se puede crear la cadena QA: vector_db_instance es None.")
        return None
    try:
        base_retriever = vector_db_instance.as_retriever(search_kwargs={"k": config.K_RETRIEVED_DOCS_BEFORE_RERANK})
        final_retriever = base_retriever

        if config.USE_RERANKER:
            logger.info("--- Habilitando Re-ranker (CrossEncoder) ---")
            try:
                model = HuggingFaceCrossEncoder(model_name='BAAI/bge-reranker-base')
                compressor = CrossEncoderReranker(model=model, top_n=config.RERANKER_TOP_N)
                final_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=base_retriever)
                logger.info(f"--- Re-ranker configurado para devolver los mejores {config.RERANKER_TOP_N} fragmentos ---")
            except Exception as e_reranker:
                logger.error(f"No se pudo inicializar el Re-ranker. Se usará el retriever base. Error: {e_reranker}")

        prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE_STR)
        combine_docs_chain = create_stuff_documents_chain(llm, prompt)
        qa_chain = create_retrieval_chain(final_retriever, combine_docs_chain)
        
        logger.info("--- Cadena RetrievalQA (LCEL) creada exitosamente ---")
        return qa_chain
    except Exception as e:
        logger.error(f"Error al crear la cadena RAG: {e}", exc_info=True)
        return None