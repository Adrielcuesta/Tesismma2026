# scripts/rag_components.py
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors.cross_encoder_rerank import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
import logging
import os

from .schemas import LLMResponse
from . import config

logger = logging.getLogger(__name__)

# --- Caché del modelo de re-ranker a nivel de módulo: tanto app.py como
# evaluate_rag.py son procesos que quedan corriendo durante muchas preguntas
# seguidas. Sin esto, HuggingFaceCrossEncoder se recargaba desde cero en
# CADA pregunta (~3-4 segundos perdidos cada vez, medido en las ejecuciones
# de evaluación). Con el caché, solo se carga una vez por proceso.
_reranker_model_cache = {}

def _get_reranker_model(model_name: str):
    if model_name not in _reranker_model_cache:
        logger.info(f"--- Cargando modelo de re-ranker '{model_name}' por primera vez en este proceso (se reutilizará en las siguientes preguntas) ---")
        _reranker_model_cache[model_name] = HuggingFaceCrossEncoder(model_name=model_name)
    return _reranker_model_cache[model_name]

PROMPT_TEMPLATE_STR = """
Eres un asistente de IA experto en la identificación y evaluación de riesgos para proyectos de instalación de maquinaria industrial.
Tu tarea es analizar la descripción del "NUEVO PROYECTO" y, basándote ÚNICAMENTE en el "CONTEXTO PROPORCIONADO", identificar una lista de posibles riesgos.

CONTEXTO PROPORCIONADO:
{context}

NUEVO PROYECTO (PREGUNTA DEL USUARIO):
{question}
INSTRUCCIONES ESTRICTAS PARA LA RESPUESTA:
1.  Tu respuesta DEBE ser un único objeto JSON. NO incluyas ningún texto antes o después del objeto JSON.
2.  El objeto JSON debe tener UNA SOLA CLAVE PRINCIPAL: "riesgos_identificados".
3.  El valor de "riesgos_identificados" debe ser una lista de objetos.
4.  Cada objeto de la lista representa un riesgo y debe contener EXACTAMENTE los siguientes 9 campos:
    a. "descripcion_riesgo": Una descripción clara y concisa del riesgo.
    b. "tipo_de_riesgo": Clasificación del riesgo. Opciones válidas: "Explícito" (si el contexto lo menciona directamente) o "Implícito" (si se deduce lógicamente del contexto).
    c. "explicacion_riesgo": Una breve explicación de por qué es un riesgo, citando evidencia específica del "CONTEXTO PROPORCIONADO".
    d. "impacto_estimado": Opciones válidas: "Bajo", "Medio", "Alto".
    e. "probabilidad_estimada": Opciones válidas: "Baja", "Media", "Alta".
    f. "responsabilidad_mitigacion": El rol o departamento responsable de las tareas de mitigación preventivas (ej. "Ingeniería de Planta").
    g. "responsable_accidente": El rol o departamento que asumiría la responsabilidad si el riesgo se materializa (ej. "Jefe de Producción").
    h. "accion_mitigacion": Una acción CONCRETA y específica para prevenir o mitigar el riesgo (una tarea accionable, ej. "Realizar estudio de suelo y reforzar cimentación antes del montaje"). NO repitas un rol o departamento acá, eso va en los campos f y g.
    i. "umbral_alerta": Un indicador o condición medible que, de cumplirse, debería disparar una alerta o escalamiento (ej. "Vibración medida superior a 5 mm/s en la base del equipo" o "Desvío de cronograma mayor a 2 semanas respecto del plan").
5.  Si, basándote estrictamente en el contexto, no se detecta ningún riesgo relevante, debes devolver una lista vacía para el campo `riesgos_identificados`. No inventes riesgos.

LA RESPUESTA DEBE SER UN OBJETO JSON VÁLIDO, SIGUIENDO ESTRICTAMENTE EL FORMATO DESCRITO.
EJEMPLO DE RESPUESTA JSON IDEAL:
{{
  "riesgos_identificados": [
    {{
      "descripcion_riesgo": "Vibraciones excesivas de la nueva prensa hidráulica podrían afectar la estructura del edificio.",
      "tipo_de_riesgo": "Implícito",
      "explicacion_riesgo": "El Contexto 2 menciona que equipos con más de 50 toneladas de fuerza de prensado, como el del proyecto, requieren un estudio de suelo y cimentación reforzada, lo cual no se especifica en la descripción del proyecto.",
      "impacto_estimado": "Alto",
      "probabilidad_estimada": "Media",
      "responsabilidad_mitigacion": "Ingeniería Civil y de Planta",
      "responsable_accidente": "Gerencia de Operaciones",
      "accion_mitigacion": "Realizar un estudio de suelo y diseñar una cimentación reforzada antes del montaje de la prensa, según lo indicado en el manual del fabricante.",
      "umbral_alerta": "Vibración medida en la base de la prensa superior a 5 mm/s durante la puesta en marcha."
    }}
  ]
}}

Comienza tu respuesta JSON AHORA:
"""

def get_llm_instance(model_id: str):
    if model_id not in config.LLM_MODELS:
        logger.error(f"Modelo '{model_id}' no encontrado en config.LLM_MODELS.")
        raise ValueError(f"Modelo no soportado: {model_id}")

    model_config = config.LLM_MODELS[model_id]
    provider = model_config["provider"]
    api_key_env = model_config.get("api_key_env")
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
                api_key=api_key,
                temperature=0.2,
                convert_system_message_to_human=True
            )

        elif provider == "groq":
            # Opción A: Conexión nativa compatible con OpenAI (No requiere instalar librerías extra)
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_id,
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
                temperature=0.2
            )

        elif provider in ["openai", "openai_compatible"]:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_id,
                api_key=api_key,
                base_url=model_config.get("base_url"),
                temperature=0.2
            )

        elif provider == "mistral":
            from langchain_mistralai import ChatMistralAI
            return ChatMistralAI(
                model=model_id,
                api_key=api_key,
                temperature=0.2
            )

        elif provider == "cohere":
            from langchain_cohere import ChatCohere
            return ChatCohere(
                model=model_id,
                cohere_api_key=api_key,
                temperature=0.2
            )

        else:
            logger.error(f"Proveedor '{provider}' no implementado.")
            return None

    except ImportError as e:
        logger.error(f"Error de importación para el proveedor '{provider}'. ¿Instalaste la librería requerida (ej. 'pip install langchain-mistralai')? Error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error al inicializar el modelo '{model_id}': {e}", exc_info=True)
        return None

def crear_cadena_rag(llm, vector_db_instance):
    if not llm or not vector_db_instance:
        logger.error("Instancia de LLM o Vector DB no proporcionada.")
        return None
    try:
        base_retriever = vector_db_instance.as_retriever(search_kwargs={"k": config.K_RETRIEVED_DOCS_BEFORE_RERANK})
        final_retriever = base_retriever

        if config.USE_RERANKER:
            logger.info("--- Habilitando Re-ranker (CrossEncoder) ---")
            try:
                model = _get_reranker_model('BAAI/bge-reranker-v2-m3')
                compressor = CrossEncoderReranker(model=model, top_n=config.RERANKER_TOP_N)
                final_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=base_retriever)
                logger.info(f"--- Re-ranker configurado para devolver los mejores {config.RERANKER_TOP_N} fragmentos ---")
            except Exception as e_reranker:
                logger.error(f"No se pudo inicializar el Re-ranker. Se usará el retriever base. Error: {e_reranker}")

        prompt = PromptTemplate(template=PROMPT_TEMPLATE_STR, input_variables=["context", "question"])

        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=final_retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": prompt}
        )
        logger.info("--- Cadena RetrievalQA creada exitosamente ---")
        return qa_chain
    except Exception as e:
        logger.error(f"Error al crear la cadena RetrievalQA: {e}", exc_info=True)
        return None


def crear_cadena_sin_rag(llm):
    """Cadena de comparación (ablation) para medir el aporte real del RAG: mismo
    modelo, mismo prompt y mismo esquema JSON exigido, pero SIN recuperar ningún
    fragmento de la Base de Conocimiento. La única variable que cambia frente a
    crear_cadena_rag() es la presencia o ausencia de contexto recuperado -- así
    cualquier diferencia en los resultados es atribuible únicamente al RAG."""
    if not llm:
        logger.error("Instancia de LLM no proporcionada.")
        return None
    try:
        prompt_sin_contexto_str = PROMPT_TEMPLATE_STR.replace(
            "{context}",
            "(No se proporcionó ningún fragmento de la Base de Conocimiento. Respondé únicamente con tu conocimiento general, sin inventar citas ni referencias a documentos.)"
        )
        prompt = PromptTemplate(template=prompt_sin_contexto_str, input_variables=["question"])
        from langchain_core.output_parsers import StrOutputParser
        cadena_sin_rag = prompt | llm | StrOutputParser()
        logger.info("--- Cadena SIN RAG (ablation) creada exitosamente ---")
        return cadena_sin_rag
    except Exception as e:
        logger.error(f"Error al crear la cadena sin RAG: {e}", exc_info=True)
        return None