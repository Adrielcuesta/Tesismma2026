# scripts/config.py
import os
import datetime
import certifi
import logging

logger = logging.getLogger(__name__)

# --- Configuración de Certificados SSL ---
try:
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
except Exception as e_certifi:
    logger.warning(f"No se pudo establecer SSL_CERT_FILE/REQUESTS_CA_BUNDLE usando certifi: {e_certifi}")

from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), os.pardir, '.env')
load_dotenv(dotenv_path)

if 'SSL_CERT_FILE' in os.environ:
    logger.info(f"Usando bundle de certificados de certifi en: {os.environ['SSL_CERT_FILE']}")

# --- Rutas del Proyecto ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DATA_DIR = os.path.join(PROJECT_ROOT, "datos")
DIRECTORIO_BASE_CONOCIMIENTO = os.path.join(DATA_DIR, "BaseConocimiento")
# Normativa (NORM_01 a 05): se indexa y se recupera por similitud. Lineamientos (NORM_06, NORM_07 y criterios_empresa.json):
# es el método de la empresa, nunca se indexa. Nadie debe leer DIRECTORIO_BASE_CONOCIMIENTO directamente.
DIRECTORIO_NORMATIVA = os.path.join(DIRECTORIO_BASE_CONOCIMIENTO, "Normativa")
DIRECTORIO_LINEAMIENTOS = os.path.join(DIRECTORIO_BASE_CONOCIMIENTO, "Lineamientos")
DIRECTORIO_PROYECTO_ANALIZAR = os.path.join(DATA_DIR, "ProyectoAnalizar")
# PDFs subidos desde la app como Base de Conocimiento propia (nunca pisan DIRECTORIO_BASE_CONOCIMIENTO)
DIRECTORIO_BASE_CONOCIMIENTO_USUARIO = os.path.join(DATA_DIR, "BaseConocimiento_Usuario")
# Proyecto subido desde la app (nunca pisa DIRECTORIO_PROYECTO_ANALIZAR)
DIRECTORIO_PROYECTO_ANALIZAR_USUARIO = os.path.join(DATA_DIR, "ProyectoAnalizar_Usuario")
CHROMA_DB_PATH = os.path.join(DATA_DIR, "ChromaDB_V1")
# Firma de lo indexado (archivos + CHUNK_SIZE + embedding), junto a ChromaDB; si cambia, se reindexa
CHROMA_MANIFEST_PATH = CHROMA_DB_PATH + "_manifest.json"
# Índice de la KB ferroviaria, un chunk por artículo (el índice anterior no se toca)
CHROMA_DB_PATH_KB = os.path.join(DATA_DIR, "ChromaDB_KB_Ferroviaria")
CHROMA_COLLECTION_KB = "kb_ferroviaria_articulos"
CHROMA_MANIFEST_PATH_KB = CHROMA_DB_PATH_KB + "_manifest.json"
DIRECTORIO_RESULTADOS_BASE = os.path.join(DATA_DIR, "Resultados")
MODELOS_LOCALES_PATH = os.path.join(PROJECT_ROOT, "modelos_locales")
CACHE_DIR_HF = os.path.join(PROJECT_ROOT, ".cache", "huggingface_cache")

# --- Lógica de selección del modelo de Embeddings ---
DEFAULT_EMBEDDING_MODEL_HF_REPO_ID = 'BAAI/bge-m3'
MODEL_SAVE_SUBFOLDER = DEFAULT_EMBEDDING_MODEL_HF_REPO_ID.split('/')[-1]
LOCAL_EMBEDDING_MODEL_PATH = os.path.join(MODELOS_LOCALES_PATH, MODEL_SAVE_SUBFOLDER)

if os.path.exists(LOCAL_EMBEDDING_MODEL_PATH):
    EMBEDDING_MODEL_NAME_OR_PATH = LOCAL_EMBEDDING_MODEL_PATH
else:
    EMBEDDING_MODEL_NAME_OR_PATH = os.environ.get('EMBEDDING_MODEL_PATH', '').strip() or DEFAULT_EMBEDDING_MODEL_HF_REPO_ID

# --- Configuración de RAG y Embeddings ---
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
MAX_CHARS_PROYECTO = 15000  # legacy: solo lo usa el modo evaluación; el pipeline por secciones no trunca la oferta
# Largo máximo (en caracteres) del texto con el que se BUSCA en la base vectorial y se re-rankea.
# El análisis sigue recibiendo la descripción completa (hasta MAX_CHARS_PROYECTO); esto solo acota
# la consulta de recuperación. Las preguntas de evaluación miden entre 217 y 301 caracteres.
# Medido en una CPU sin GPU, con el mismo proyecto (56.458 caracteres, truncado a 15.000):
#   1500 caracteres  -> búsqueda ~70 s  (análisis completo ~2 min),  relevancia máx. del re-ranker ~11 %
#   15000 caracteres -> búsqueda ~11 min (análisis completo ~12,5 min), relevancia máx. del re-ranker ~89 %
# Se deja el valor completo por defecto (mejor evidencia); bajarlo a 1500 si se prioriza la velocidad.
MAX_CHARS_CONSULTA_RECUPERACION = 15000
RECREAR_DB = False
MAX_PAGES_TO_CHECK_FOR_INDEX = 5

# --- Chunker de la KB por artículos ---
VERSION_CHUNKER_ARTICULOS = 1
MAX_CHARS_ARTICULO = 3000
# Una línea (normalizada, sin dígitos) repetida en al menos esta fracción de páginas es encabezado/pie
UMBRAL_ENCABEZADO = 0.5

# --- Análisis de la oferta por sección ---
# True: la oferta se divide en secciones y cada una se analiza contra el índice por artículos
USAR_KB_ARTICULOS = True
# Tope de caracteres de una sección (se agrupan subsecciones contiguas sin cruzar capítulos)
SECTION_MAX_CHARS = 2500
# Largo máximo del texto con el que se busca en la KB para cada sección
SECTION_QUERY_MAX_CHARS = 1500
# Fragmentos recuperados por sección antes del re-ranking, y cuántos se conservan después
K_RECUPERACION = 20
TOP_N_POR_SECCION = 4
# Recuperación por subsección (activa): cada subsección de al menos MIN_CHARS_SUBSECCION caracteres busca con su
# propio texto (K_SUBSECCION -> reranker -> TOP_N_SUBSECCION) y los fragmentos se unen por (norma, artículo)
# quedándose con los TOPE_FRAGMENTOS_SECCION de mayor score
RECUPERACION_POR_SUBSECCION = True
SUBSECTION_QUERY_MAX_CHARS = 800
K_SUBSECCION = 10
TOP_N_SUBSECCION = 5
TOPE_FRAGMENTOS_SECCION = 12
MIN_CHARS_SUBSECCION = 150
# Evaluador de evidencia CRAG por sección (solo informa): apagado por defecto, el código se conserva
USAR_CRAG = False
# "verificacion": una llamada por fragmento recuperado (veredicto Incumple/Revisar/Cumple/No aplica) y redacción de los
# Incumple y Revisar. "lista": una llamada por sección que devuelve la lista de riesgos (la usa la condición sin_rag)
MODO_GENERACION = "verificacion"
# Máximo de fragmentos que se verifican por sección (sin preámbulos)
VERIFICAR_TOPE = 15
# Líneas más cortas que esto (normalizadas, sin dígitos) no se quitan como encabezado/pie en la oferta:
# "Página 3 de 9" (9) sí se quita; unidades de tablas como "1.600 mm" (4) se conservan
MIN_LARGO_ENCABEZADO_OFERTA = 6
# La sección "Introducción" (texto previo al primer encabezado) no se recupera ni se genera; se lista en el informe con 0 riesgos
EXCLUIR_INTRODUCCION = True
# False: no se puntúa cada riesgo contra la evidencia (507 s en P1 y no discrimina); respaldo_base_conocimiento queda en None (el dashboard muestra N/D)
CALCULAR_RESPALDO = False

# --- Configuración para el Re-ranker ---
USE_RERANKER = True
K_RETRIEVED_DOCS_BEFORE_RERANK = 50
RERANKER_TOP_N = 4
# Tokens máximos por par (consulta, fragmento) que ve el cross-encoder; acota el costo del re-ranking en CPU
RERANKER_MAX_LENGTH = 512

# --- Configuración de Ollama (único modelo local: generación y evaluador de evidencia) ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/")
OLLAMA_MODEL = "qwen3:8b"
OLLAMA_NUM_CTX = 16384
# Reproducibilidad: temperature=0 y esta semilla en todas las llamadas a ChatOllama
OLLAMA_SEED = 42
# Tope de tokens de salida (num_predict) por llamada: verificación y clasificación 1024, comentario general 400.
# Sin tope, con format JSON el modelo puede quedar generando hasta llenar el contexto. Las listas del modo lista no lo usan.
OLLAMA_NUM_PREDICT = 1024
OLLAMA_NUM_PREDICT_COMENTARIO = 400
# Modo lista (sin_rag, rag_seccion): la lista de riesgos de una sección es más larga que un JSON de verificación.
OLLAMA_NUM_PREDICT_LISTA = 2048
# Timeout (s) por llamada a Ollama; si se agota o la respuesta se corta por num_predict: un reintento y luego se descarta el par.
OLLAMA_TIMEOUT_S = 240
# Prueba controlada: razonamiento de Qwen3 SOLO en las llamadas de verificación (redacción y resumen siguen sin él).
# Muestreo recomendado por Qwen para thinking; misma semilla.
THINKING_VERIFICACION = False
VERIF_TEMPERATURE = 0.6
VERIF_TOP_P = 0.95
VERIF_TOP_K = 20
# Fecha que ve el modelo al verificar vigencias y plazos (AAAA-MM-DD); por defecto, la del día
FECHA_REFERENCIA = os.environ.get("FECHA_REFERENCIA", "").strip() or datetime.date.today().isoformat()
# KV q8_0 y flash attention son variables del SERVIDOR de Ollama (no se fijan por request):
# arrancarlo con OLLAMA_KV_CACHE_TYPE=q8_0 y OLLAMA_FLASH_ATTENTION=1.
OLLAMA_KV_CACHE_TYPE = "q8_0"
OLLAMA_FLASH_ATTENTION = "1"

# --- Configuración de LLMs ---
LLM_MODELS = {
    # --- Modelos disponibles ---
    "gemini-3.5-flash": {
        "provider": "google",
        "display_name": "Gemini 3.5 Flash (Gratuito - Recomendado)",
        "api_key_env": "GEMINI_API_KEY"
    },
    "llama-3.3-70b-versatile": {
        "provider": "groq",
        "display_name": "Llama 3.3 70B vía Groq (Gratuito)",
        "api_key_env": "GROQ_API_KEY"
    },
    OLLAMA_MODEL: {
        "provider": "ollama",
        "display_name": "Qwen3 8B (Local, sin costo)"
    },
    "mistral-large-latest": {
        "provider": "mistral",
        "display_name": "Mistral Large  (Suscripción Requerida)",
        "api_key_env": "MISTRAL_API_KEY"
    },
    "gpt-4o": {
        "provider": "openai",
        "display_name": "OpenAI GPT-4o (Suscripcion Requerida)",
        "api_key_env": "OPENAI_API_KEY"
    },
    "deepseek-chat": {
        "provider": "openai_compatible",
        "display_name": "DeepSeek Chat (Suscripción Requerida)",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com/v1"
    },
    "qwen-plus": {
        "provider": "openai_compatible",
        "display_name": "Qwen Plus (Alibaba) (Suscripción Requerida)",
        "api_key_env": "QWEN_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
    },
    "command-r-plus": {
        "provider": "cohere",
        "display_name": "Cohere Command R+ (Suscripción Requerida)",
        "api_key_env": "COHERE_API_KEY"
    }
}

# --- Información de la Tesis ---
INFO_TESIS = {
    "titulo_tesis_h1": "TESIS FIN DE MAESTRÍA",
    "titulo_tesis_h2": "Innovación en entornos empresariales",
    "titulo_tesis_h3": "Sistemas RAG para la Optimización de la Gestión de Proyectos y Análisis Estratégico.",
    "app_subtitle_h4": "ANALIZADOR DE RIESGOS CON IA.",
    "alumno": "Adriel J. Cuesta",
    "institucion_line1": "ITBA - Instituto Tecnológico Buenos Aires",
    "institucion_line2": "Maestría en Management & Analytics",
    "github_repo_url": "https://github.com/Adrielcuesta/tesismma2026"
}

# --- Funciones de Inicialización ---
def inicializar_directorios_datos():
    directorios_a_crear = [
        DIRECTORIO_NORMATIVA, DIRECTORIO_LINEAMIENTOS, DIRECTORIO_BASE_CONOCIMIENTO_USUARIO, DIRECTORIO_PROYECTO_ANALIZAR,
        DIRECTORIO_PROYECTO_ANALIZAR_USUARIO, CHROMA_DB_PATH, DIRECTORIO_RESULTADOS_BASE, MODELOS_LOCALES_PATH, CACHE_DIR_HF
    ]
    try:
        for dir_path in directorios_a_crear:
            os.makedirs(dir_path, exist_ok=True)
        return True
    except OSError as e:
        logger.error(f"Error al crear directorios: {e}")
        return False