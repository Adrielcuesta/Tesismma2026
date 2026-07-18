import os
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
DIRECTORIO_PROYECTO_ANALIZAR = os.path.join(DATA_DIR, "ProyectoAnalizar")
CHROMA_DB_PATH = os.path.join(DATA_DIR, "ChromaDB_V1")
DIRECTORIO_RESULTADOS_BASE = os.path.join(DATA_DIR, "resultados")

LOCAL_EMBEDDING_MODEL_PATH = os.path.join(PROJECT_ROOT, "modelos_locales", "all-MiniLM-L6-v2")

# --- Configuración RAG ---
USE_RERANKER = True
RERANKER_TOP_N = 4
K_RETRIEVED_DOCS_BEFORE_RERANK = 10

# --- Modelos LLM Soportados ---
LLM_MODELS_CONFIG = {
    "gemini-1.5-flash": {
        "provider": "google",
        "display_name": "Google Gemini 1.5 Flash",
        "api_key_env": "GEMINI_API_KEY"
    },
    "llama3-70b-8192": {
        "provider": "groq",
        "display_name": "Llama 3 70B (vía Groq)",
        "api_key_env": "GROQ_API_KEY"
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
    "github_repo_url": "https://github.com/Adrielcuesta/tesismma"
}

def inicializar_directorios():
    rutas = [DATA_DIR, DIRECTORIO_BASE_CONOCIMIENTO, DIRECTORIO_PROYECTO_ANALIZAR, CHROMA_DB_PATH, DIRECTORIO_RESULTADOS_BASE]
    for ruta in rutas:
        os.makedirs(ruta, exist_ok=True)
    logger.info("Directorios verificados/creados exitosamente.")