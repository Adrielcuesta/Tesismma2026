# scripts/evaluate_rag.py
import os
import sys
import logging
import pandas as pd
from datasets import Dataset

# --- Workaround: ragas 0.4.3 tiene un import roto hacia una ruta de LangChain
# que ya no existe (ChatVertexAI se movió a otro paquete hace tiempo). No
# usamos VertexAI en este proyecto, así que le damos a Python un módulo falso
# para que ese import no rompa. Sin esto, "from ragas import evaluate" falla
# con ModuleNotFoundError apenas se ejecuta el script.
import types
if "langchain_community.chat_models.vertexai" not in sys.modules:
    _stub = types.ModuleType("langchain_community.chat_models.vertexai")
    class _ChatVertexAIStub:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("VertexAI no está soportado en este proyecto.")
    _stub.ChatVertexAI = _ChatVertexAIStub
    sys.modules["langchain_community.chat_models.vertexai"] = _stub

from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.run_config import RunConfig
import json
import shutil
import datetime
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scripts.main import run_analysis
from scripts import config, vector_db_manager, rag_components

# --- Logging a archivo, además de consola: cada corrida completa queda en un
# .txt en datos/Resultados/evaluaciones_rag/, sin depender del buffer/scroll
# de la terminal. RUN_TIMESTAMP se calcula UNA vez acá arriba y se reutiliza
# más abajo para nombrar el CSV y los respaldos, así todos los archivos de
# una misma corrida comparten el mismo timestamp y son fáciles de agrupar.
RUN_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
_RESULTS_DIR = os.path.join(config.DIRECTORIO_RESULTADOS_BASE, "evaluaciones_rag")
os.makedirs(_RESULTS_DIR, exist_ok=True)
_LOG_FILE_PATH = os.path.join(_RESULTS_DIR, f"log_corrida_{RUN_TIMESTAMP}.txt")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - EVAL - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),                              # sigue mostrando todo en consola
        logging.FileHandler(_LOG_FILE_PATH, encoding='utf-8'),  # y además lo guarda acá
    ],
)
logging.getLogger("ragas").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.info(f"📝 Log completo de esta corrida guardándose en: {_LOG_FILE_PATH}")

METRICS_TO_EVALUATE = [faithfulness, answer_relevancy, context_recall, context_precision]

# Modelo usado como "juez" de Ragas. Se usa el modelo LOCAL (Qwen2.5 vía Ollama)
# a propósito: Groq tiene un límite diario de TOKENS (no solo de velocidad) que
# se comparte entre el modelo evaluado y el juez -- con ambos roles en Groq, una
# sola corrida agota el presupuesto del día antes de terminar de puntuar. El
# modelo local no tiene límite de tokens ni de cuota, así que separamos el juez
# por completo de cualquier proveedor en la nube.
RAGAS_JUDGE_MODEL_ID = "qwen2.5:7b-instruct"
RAGAS_JUDGE_BASE_URL = "http://localhost:11434/v1"


def load_evaluation_dataset(path: str) -> Dataset:
    try:
        return Dataset.from_json(path)
    except Exception as e:
        logging.error(f"Error al cargar el dataset de evaluación desde '{path}': {e}")
        return None


def run_evaluation_for_model(model_id: str, eval_dataset: Dataset, db_connection: object):
    results = []
    # Los modelos locales (Ollama) no tienen límite de velocidad ni de cuota:
    # la pausa de 10s entre preguntas solo tiene sentido para no chocar con
    # los límites de APIs en la nube. La saltamos para modelos locales.
    model_base_url = config.LLM_MODELS.get(model_id, {}).get("base_url", "")
    is_local_model = "localhost" in model_base_url or "127.0.0.1" in model_base_url

    logging.info(f"--- Iniciando evaluación para el modelo: {model_id} ({len(eval_dataset)} preguntas) ---")
    for i, row in enumerate(eval_dataset):
        logging.info(f"Procesando pregunta {i+1}/{len(eval_dataset)}: \"{row['question'][:50]}...\"")
        try:
            result = run_analysis(
                selected_llm_model_id=model_id, is_evaluation_mode=True,
                eval_question=row["question"], eval_ground_truth=row["ground_truth"],
                db_connection=db_connection
            )
            if result: results.append(result)
        except Exception as e:
            logging.error(f"Excepción inesperada al evaluar la pregunta {i+1}: {e}", exc_info=True)
        if not is_local_model:
            logging.info("Esperando 10 segundos...")
            time.sleep(10)
    return results


def main():
    logging.info("================ INICIO EVALUACIÓN PIPELINE RAG ================")
    eval_dataset_path = os.path.join(config.DATA_DIR, "eval_dataset.jsonl")
    eval_dataset = load_evaluation_dataset(eval_dataset_path)
    if not eval_dataset or len(eval_dataset) == 0:
        logging.error("El dataset de evaluación está vacío o no se pudo cargar."); return

    logging.info("Preparando la base de datos vectorial...")
    embedding_function = vector_db_manager.get_embedding_function(config.EMBEDDING_MODEL_NAME_OR_PATH)
    if not embedding_function: logging.error("No se pudo crear la función de embeddings."); return
    db_connection = vector_db_manager.crear_o_cargar_chroma_db(
        chroma_db_path=config.CHROMA_DB_PATH, docs_base_conocimiento_path=config.DIRECTORIO_BASE_CONOCIMIENTO,
        embedding_function=embedding_function, chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP, recrear_db_flag=True
    )
    if not db_connection: logging.error("No se pudo crear la base de datos vectorial."); return
    logging.info("✅ Base de datos lista para ser reutilizada.")

    # --- Juez de Ragas 100% gratuito y sin límites: modelo local (Ollama) + tu mismo modelo local de embeddings ---
    from langchain_openai import ChatOpenAI
    judge_llm_raw = ChatOpenAI(
        model=RAGAS_JUDGE_MODEL_ID,
        api_key="ollama-local",  # Ollama no valida esta clave, pero el SDK exige que exista
        base_url=RAGAS_JUDGE_BASE_URL,
        temperature=0.2,
    )
    ragas_judge_llm = LangchainLLMWrapper(judge_llm_raw)
    ragas_judge_embeddings = LangchainEmbeddingsWrapper(embedding_function)
    logging.info(f"✅ Ragas usará '{RAGAS_JUDGE_MODEL_ID}' (gratuito) como modelo juez. No se usa OpenAI en ningún paso.")

    # --- Rutas de guardado. Reutilizan RUN_TIMESTAMP (calculado arriba, al
    # importar el módulo) para que el CSV, los respaldos por modelo y el log
    # de esta corrida compartan el mismo nombre y sean fáciles de agrupar. ---
    results_dir = _RESULTS_DIR
    timestamp = RUN_TIMESTAMP
    csv_path = os.path.join(results_dir, f"ragas_eval_TODOS_{timestamp}.csv")
    # Nombres reales que usa Ragas 0.4.x en to_pandas() (esquema v2): user_input
    # en vez de question, response en vez de answer, retrieved_contexts en vez
    # de contexts, reference en vez de ground_truth. Con los nombres viejos el
    # filtro no encontraba nada y el CSV quedaba sin texto, solo con números.
    cols = ['model_id', 'user_input', 'response', 'retrieved_contexts', 'reference',
            'faithfulness', 'answer_relevancy', 'context_recall', 'context_precision']

    all_results = []
    models_to_evaluate = list(config.LLM_MODELS.keys())

    for model_id in models_to_evaluate:
        if not os.getenv(config.LLM_MODELS[model_id].get("api_key_env")):
            logging.warning(f"No se encontró API Key para '{model_id}'. Saltando su evaluación."); continue

        model_results_list = run_evaluation_for_model(model_id, eval_dataset, db_connection)
        if not model_results_list:
            logging.warning(f"No se obtuvieron resultados para {model_id}. Saltando Ragas."); continue

        # Guardado de respaldo de las respuestas crudas (pregunta/respuesta/contextos),
        # ANTES de intentar puntuarlas con Ragas. Si Ragas falla después, esto no se pierde.
        raw_backup_path = os.path.join(results_dir, f"respuestas_crudas_{model_id.replace(':', '_')}_{timestamp}.json")
        try:
            with open(raw_backup_path, 'w', encoding='utf-8') as f:
                json.dump(model_results_list, f, ensure_ascii=False, indent=2)
            logging.info(f"Respaldo de respuestas crudas guardado en: {raw_backup_path}")
        except Exception as e_backup:
            logging.warning(f"No se pudo guardar el respaldo crudo de {model_id}: {e_backup}")

        ragas_dataset = Dataset.from_list(model_results_list)
        logging.info(f"Calculando métricas con Ragas para el modelo: {model_id}...")
        try:
            score = evaluate(
                ragas_dataset,
                metrics=METRICS_TO_EVALUATE,
                llm=ragas_judge_llm,
                embeddings=ragas_judge_embeddings,
                # max_workers más alto que en la versión "nube": sin Groq/Gemini en la
                # corrida no hay riesgo de rate limit externo. Ollama procesa en cola
                # sobre una sola GPU, así que esto acelera la espera de red/CPU sin
                # saturar nada; si tu GPU se queda corta de VRAM, bajalo a 2 o 3.
                # timeout más alto (antes 120s) y menos concurrencia: context_precision
                # es la métrica más pesada para el juez y venía fallando por timeout en
                # varias preguntas cuando corría con 6 llamadas en paralelo sobre un
                # modelo local de 7B.
                run_config=RunConfig(max_workers=3, timeout=300),
            )
            score_df = score.to_pandas()
            score_df["model_id"] = model_id
            all_results.append(score_df)
            logging.info(f"Evaluación para {model_id} completada.")
        except Exception as e:
            logging.error(f"Error durante la evaluación de Ragas para {model_id}: {e}", exc_info=True)
            continue

        # --- GUARDADO INCREMENTAL: se reescribe el CSV con todo lo acumulado hasta
        # ahora, después de CADA modelo. Si el siguiente modelo falla o se corta el
        # script, esto ya quedó a salvo en disco. ---
        try:
            partial_df = pd.concat(all_results, ignore_index=True)
            partial_df = partial_df[[c for c in cols if c in partial_df.columns]]
            partial_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            logging.info(f"✅ CSV actualizado ({len(all_results)} modelo(s) hasta ahora) en: {csv_path}")
        except Exception as e_save:
            logging.error(f"No se pudo guardar el CSV parcial: {e_save}")

    if not all_results: logging.error("No se pudieron completar las evaluaciones."); return

    final_df = pd.concat(all_results, ignore_index=True)
    final_df = final_df[[c for c in cols if c in final_df.columns]]
    summary_df = final_df.groupby('model_id')[['faithfulness', 'answer_relevancy', 'context_recall', 'context_precision']].mean(numeric_only=True).reset_index()
    print("\n\n--- RESUMEN DE MÉTRICAS PROMEDIO POR MODELO ---")
    print(summary_df.to_string(index=False))
    print("-------------------------------------------------")
    logging.info(f"Resultados finales en: {csv_path}")
    logging.info("================ FIN EVALUACIÓN PIPELINE RAG ================")


if __name__ == "__main__":
    main()