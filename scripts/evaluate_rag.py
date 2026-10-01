# scripts/evaluate_rag.py
import os
import sys
import logging
import pandas as pd
from datasets import Dataset
import types

# Workaround: ragas 0.4.3 tiene un import roto hacia una ruta de LangChain que
# ya no existe (ChatVertexAI se movió de paquete). No usamos VertexAI en este
# proyecto, así que se registra un módulo falso para que ese import no rompa.
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
import datetime
import time
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scripts.main import run_analysis
from scripts import config, vector_db_manager, rag_components

# Log a archivo además de consola: cada ejecución completa queda en un .txt en
# datos/Resultados/evaluaciones_rag/, sin depender del buffer de la terminal.
# RUN_TIMESTAMP se calcula UNA vez y se reutiliza para nombrar el CSV y los
# respaldos, así todos los archivos de una misma ejecución comparten nombre.
RUN_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
_RESULTS_DIR = os.path.join(config.DIRECTORIO_RESULTADOS_BASE, "evaluaciones_rag")
os.makedirs(_RESULTS_DIR, exist_ok=True)
_LOG_FILE_PATH = os.path.join(_RESULTS_DIR, f"log_ejecucion_{RUN_TIMESTAMP}.txt")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - EVAL - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_LOG_FILE_PATH, encoding='utf-8'),
    ],
)
logging.getLogger("ragas").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.info(f"📝 Log completo de esta ejecución guardándose en: {_LOG_FILE_PATH}")

METRICS_TO_EVALUATE = [faithfulness, answer_relevancy, context_recall, context_precision]
# Para el modo SIN RAG (ablation) solo tiene sentido answer_relevancy: faithfulness,
# context_recall y context_precision necesitan contexto recuperado para existir --
# sin contexto, saldrían siempre en 0 por construcción, no como un hallazgo real.
METRICS_SIN_RAG = [answer_relevancy]

# Modelo usado como "juez" de Ragas: un modelo LOCAL (Qwen2.5 vía Ollama), sin
# límite de cuota ni costo, independiente de los modelos evaluados.
RAGAS_JUDGE_MODEL_ID = "qwen2.5:7b-instruct"
RAGAS_JUDGE_BASE_URL = "http://localhost:11434/v1"


def load_evaluation_dataset(path: str) -> Dataset:
    try:
        return Dataset.from_json(path)
    except Exception as e:
        logging.error(f"Error al cargar el dataset de evaluación desde '{path}': {e}")
        return None


def run_evaluation_for_model(model_id: str, eval_dataset: Dataset, db_connection: object, usar_rag: bool = True):
    results = []
    # Los modelos locales (Ollama) no tienen límite de velocidad ni de cuota:
    # la pausa de 10s entre preguntas solo tiene sentido para no chocar con
    # los límites de APIs en la nube. Se saltea para modelos locales.
    model_base_url = config.LLM_MODELS.get(model_id, {}).get("base_url", "")
    is_local_model = "localhost" in model_base_url or "127.0.0.1" in model_base_url

    modo_txt = "con RAG" if usar_rag else "SIN RAG (ablation)"
    logging.info(f"--- Iniciando evaluación para el modelo: {model_id} [{modo_txt}] ({len(eval_dataset)} preguntas) ---")
    for i, row in enumerate(eval_dataset):
        logging.info(f"Procesando pregunta {i+1}/{len(eval_dataset)}: \"{row['question'][:50]}...\"")
        try:
            result = run_analysis(
                selected_llm_model_id=model_id, is_evaluation_mode=True,
                eval_question=row["question"], eval_ground_truth=row["ground_truth"],
                db_connection=db_connection, usar_rag=usar_rag,
            )
            if result:
                results.append(result)
            else:
                results.append({
                    "question": row["question"], "answer": None, "contexts": [],
                    "ground_truth": row["ground_truth"], "schema_valido": False, "usa_rag": usar_rag,
                })
        except Exception as e:
            logging.error(f"Excepción inesperada al evaluar la pregunta {i+1}: {e}", exc_info=True)
            results.append({
                "question": row["question"], "answer": None, "contexts": [],
                "ground_truth": row["ground_truth"], "schema_valido": False, "usa_rag": usar_rag,
            })
        if not is_local_model:
            logging.info("Esperando 10 segundos...")
            time.sleep(10)
    return results


def _cosine_similarity(vec_a, vec_b) -> float:
    vec_a, vec_b = np.array(vec_a, dtype=float), np.array(vec_b, dtype=float)
    denom = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
    if denom == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / denom)


def calcular_metricas_propias(model_results_list, embedding_function):
    """Métricas propias, deterministas (sin juez LLM, sin costo, sin varianza):

    1. Tasa de Cumplimiento de Esquema: proporción de preguntas que devuelven
       un JSON válido según el esquema RiskItem (9 campos).
    2. Coherencia Interna Acción/Umbral: similitud semántica (embeddings BGE-M3,
       el mismo modelo del pipeline) entre la descripción de cada riesgo y, por
       separado, su acción de mitigación y su umbral de alerta -- se toma el
       mínimo de las dos comparaciones, no el promedio de ambas concatenadas,
       para que un campo bien generado no diluya uno mal generado.
    3. Distribución del Evaluador de Evidencia (CRAG-lite): cuántas preguntas
       fueron clasificadas CORRECTO / AMBIGUO / INSUFICIENTE. Sirve para
       reportar con qué frecuencia el sistema identificaría, por sí mismo, los
       mismos casos que el juez externo de Ragas calificó con precisión de
       contexto baja.
    """
    total_intentos = len(model_results_list)
    validos = [r for r in model_results_list if r.get("schema_valido", False)]
    tasa_cumplimiento_esquema = (len(validos) / total_intentos) if total_intentos else 0.0

    similitudes = []
    for r in validos:
        try:
            data = json.loads(r["answer"])
            riesgos = data.get("riesgos_identificados", [])
        except Exception:
            continue
        for riesgo in riesgos:
            descripcion = (riesgo.get("descripcion_riesgo") or "").strip()
            accion = (riesgo.get("accion_mitigacion") or "").strip()
            umbral = (riesgo.get("umbral_alerta") or "").strip()
            if not descripcion or (not accion and not umbral):
                continue
            try:
                emb_desc = embedding_function.embed_query(descripcion)
                sims_riesgo = []
                if accion:
                    sims_riesgo.append(_cosine_similarity(emb_desc, embedding_function.embed_query(accion)))
                if umbral:
                    sims_riesgo.append(_cosine_similarity(emb_desc, embedding_function.embed_query(umbral)))
                similitudes.append(min(sims_riesgo))
            except Exception as e_emb:
                logging.warning(f"No se pudo calcular coherencia interna para un riesgo: {e_emb}")

    conteo_evidencia = {"CORRECTO": 0, "AMBIGUO": 0, "INSUFICIENTE": 0, "N/A": 0}
    for r in validos:
        clave = r.get("evaluacion_evidencia") or "N/A"
        conteo_evidencia[clave] = conteo_evidencia.get(clave, 0) + 1

    return {
        "tasa_cumplimiento_esquema": tasa_cumplimiento_esquema,
        "preguntas_totales": total_intentos,
        "preguntas_validas": len(validos),
        "coherencia_interna_promedio": (sum(similitudes) / len(similitudes)) if similitudes else None,
        "coherencia_interna_minima": min(similitudes) if similitudes else None,
        "riesgos_evaluados_coherencia": len(similitudes),
        "evidencia_correcto": conteo_evidencia["CORRECTO"],
        "evidencia_ambiguo": conteo_evidencia["AMBIGUO"],
        "evidencia_insuficiente": conteo_evidencia["INSUFICIENTE"],
    }


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

    if not os.getenv("OLLAMA_API_KEY"):
        logging.warning("No se encontró 'OLLAMA_API_KEY' (cualquier valor no vacío sirve). Usando un valor por defecto.")
    from langchain_openai import ChatOpenAI
    judge_llm_raw = ChatOpenAI(
        model=RAGAS_JUDGE_MODEL_ID,
        api_key="ollama-local",
        base_url=RAGAS_JUDGE_BASE_URL,
        temperature=0.2,
    )
    ragas_judge_llm = LangchainLLMWrapper(judge_llm_raw)
    ragas_judge_embeddings = LangchainEmbeddingsWrapper(embedding_function)
    logging.info(f"✅ Ragas usará '{RAGAS_JUDGE_MODEL_ID}' (gratuito) como modelo juez. No se usa OpenAI en ningún paso.")

    results_dir = _RESULTS_DIR
    timestamp = RUN_TIMESTAMP
    csv_path = os.path.join(results_dir, f"ragas_eval_TODOS_{timestamp}.csv")
    # Nombres reales que usa Ragas 0.4.x en to_pandas() (esquema v2): user_input
    # en vez de question, response en vez de answer, retrieved_contexts en vez
    # de contexts, reference en vez de ground_truth.
    cols = ['model_id', 'user_input', 'response', 'retrieved_contexts', 'reference',
            'faithfulness', 'answer_relevancy', 'context_recall', 'context_precision']

    all_results = []
    metricas_propias_todas = []
    models_to_evaluate = list(config.LLM_MODELS.keys())

    for model_id in models_to_evaluate:
        if not os.getenv(config.LLM_MODELS[model_id].get("api_key_env")):
            logging.warning(f"No se encontró API Key para '{model_id}'. Saltando su evaluación."); continue

        # Ablation automático: cada modelo se evalúa dos veces, con RAG y sin
        # RAG (mismo modelo, mismas preguntas, único cambio es la presencia de
        # contexto recuperado). 'etiqueta' es el nombre que aparece en el CSV
        # final, así una sola ejecución deja todo junto, sin pasos manuales.
        modos = [(True, model_id, METRICS_TO_EVALUATE), (False, f"{model_id} [SIN RAG]", METRICS_SIN_RAG)]

        for usar_rag, etiqueta, metricas_ragas_a_usar in modos:
            model_results_list = run_evaluation_for_model(model_id, eval_dataset, db_connection, usar_rag=usar_rag)
            if not model_results_list:
                logging.warning(f"No se obtuvieron resultados para {etiqueta}. Saltando Ragas."); continue

            # Métricas propias: se calculan sobre TODOS los intentos (éxitos y
            # fallos de esquema), antes de filtrar nada -- necesitan el
            # denominador completo para que la tasa de cumplimiento sea real.
            metricas = calcular_metricas_propias(model_results_list, embedding_function)
            metricas["model_id"] = etiqueta
            metricas_propias_todas.append(metricas)
            coherencia_txt = f"{metricas['coherencia_interna_promedio']:.3f}" if metricas['coherencia_interna_promedio'] is not None else "N/D"
            logging.info(
                f"📊 Métricas propias de {etiqueta}: cumplimiento de esquema "
                f"{metricas['tasa_cumplimiento_esquema']:.0%} ({metricas['preguntas_validas']}/{metricas['preguntas_totales']}), "
                f"coherencia interna acción/umbral promedio {coherencia_txt}, "
                f"evidencia [correcto={metricas['evidencia_correcto']}, ambiguo={metricas['evidencia_ambiguo']}, insuficiente={metricas['evidencia_insuficiente']}]"
            )

            sufijo_archivo = etiqueta.replace(':', '_').replace(' ', '_').replace('[', '').replace(']', '')
            raw_backup_path = os.path.join(results_dir, f"respuestas_crudas_{sufijo_archivo}_{timestamp}.json")
            try:
                with open(raw_backup_path, 'w', encoding='utf-8') as f:
                    json.dump(model_results_list, f, ensure_ascii=False, indent=2)
                logging.info(f"Respaldo de respuestas crudas guardado en: {raw_backup_path}")
            except Exception as e_backup:
                logging.warning(f"No se pudo guardar el respaldo crudo de {etiqueta}: {e_backup}")

            # Ragas solo puede puntuar respuestas con esquema válido. Se descarta
            # también la clave interna 'schema_valido' y 'evaluacion_evidencia',
            # que no forman parte del dataset que espera Ragas.
            intentos_validos_ragas = [
                {k: v for k, v in r.items() if k not in ("schema_valido", "evaluacion_evidencia")}
                for r in model_results_list if r.get("schema_valido", False)
            ]
            if not intentos_validos_ragas:
                logging.warning(f"Ningún intento con esquema válido para {etiqueta}. Saltando Ragas."); continue

            ragas_dataset = Dataset.from_list(intentos_validos_ragas)
            logging.info(f"Calculando métricas con Ragas para: {etiqueta}...")
            try:
                score = evaluate(
                    ragas_dataset,
                    metrics=metricas_ragas_a_usar,
                    llm=ragas_judge_llm,
                    embeddings=ragas_judge_embeddings,
                    run_config=RunConfig(max_workers=3, timeout=300),
                )
                score_df = score.to_pandas()
                score_df["model_id"] = etiqueta
                all_results.append(score_df)
                logging.info(f"Evaluación para {etiqueta} completada.")
            except Exception as e:
                logging.error(f"Error durante la evaluación de Ragas para {etiqueta}: {e}", exc_info=True)
                continue

            # Guardado incremental: se reescribe el CSV con todo lo acumulado
            # hasta ahora, después de cada modo evaluado. Si el siguiente falla
            # o se corta el script, esto ya quedó a salvo en disco.
            try:
                partial_df = pd.concat(all_results, ignore_index=True)
                partial_df = partial_df[[c for c in cols if c in partial_df.columns]]
                partial_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
                logging.info(f"✅ CSV actualizado ({len(all_results)} entrada(s) hasta ahora) en: {csv_path}")
            except Exception as e_save:
                logging.error(f"No se pudo guardar el CSV parcial: {e_save}")

    if not all_results: logging.error("No se pudieron completar las evaluaciones."); return

    final_df = pd.concat(all_results, ignore_index=True)
    final_df = final_df[[c for c in cols if c in final_df.columns]]
    summary_df = final_df.groupby('model_id')[['faithfulness', 'answer_relevancy', 'context_recall', 'context_precision']].mean(numeric_only=True).reset_index()
    print("\n\n--- RESUMEN DE MÉTRICAS PROMEDIO POR MODELO (Ragas) ---")
    print(summary_df.to_string(index=False))
    print("-------------------------------------------------")

    if metricas_propias_todas:
        metricas_df = pd.DataFrame(metricas_propias_todas)
        metricas_csv_path = os.path.join(results_dir, f"metricas_propias_{timestamp}.csv")
        metricas_df.to_csv(metricas_csv_path, index=False, encoding='utf-8-sig')
        print("\n--- MÉTRICAS PROPIAS (cumplimiento de esquema + coherencia + evaluador de evidencia) ---")
        print(metricas_df.to_string(index=False))
        print("-------------------------------------------------")
        logging.info(f"Métricas propias guardadas en: {metricas_csv_path}")

    logging.info(f"Resultados finales en: {csv_path}")
    logging.info("================ FIN EVALUACIÓN PIPELINE RAG ================")


if __name__ == "__main__":
    main()