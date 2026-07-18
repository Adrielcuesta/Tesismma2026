import os
import sys
import logging
import traceback
import datetime
from flask import Flask, render_template, render_template_string, send_file, url_for, redirect, flash, request
from werkzeug.utils import secure_filename
from pydantic import ValidationError

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from scripts.main import run_analysis
    from scripts import config
    from scripts.descargar_modelo import descargar_modelo
except ImportError as e:
    logging.basicConfig(level=logging.ERROR)
    logging.error(f"Error crítico al importar módulos necesarios: {e}")
    run_analysis = None
    config = None
    descargar_modelo = None

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

if descargar_modelo and config:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logger_startup = logging.getLogger(__name__)

    logger_startup.info("--- Verificando existencia de modelo de embeddings local ---")
    if not os.path.exists(config.LOCAL_EMBEDDING_MODEL_PATH):
        logger_startup.warning(f"Modelo no encontrado en '{config.LOCAL_EMBEDDING_MODEL_PATH}'.")
        logger_startup.info("Iniciando descarga automática del modelo. Esto puede tardar unos minutos...")
        try:
            descargar_modelo(modelo_hf="sentence-transformers/all-MiniLM-L6-v2", directorio_destino=config.LOCAL_EMBEDDING_MODEL_PATH)
        except Exception as e:
             logger_startup.error(f"Fallo crítico en la descarga del modelo. La app no podrá funcionar correctamente. Error: {e}")
    else:
        logger_startup.info(f"✅ Modelo ya existe en '{config.LOCAL_EMBEDDING_MODEL_PATH}'. No se necesita descarga.")

@app.context_processor
def inject_now():
    return {'now': datetime.datetime.now()}

@app.route('/', methods=['GET'])
def home():
    app.logger.info("Acceso a la ruta de inicio ('/').")
    if config is None:
        return "Error crítico de inicialización. Revisa los logs de la consola.", 500
    
    return render_template('index.html', info_tesis=config.INFO_TESIS, llm_models=config.LLM_MODELS_CONFIG)

@app.route('/analyze', methods=['POST'])
def analyze():
    app.logger.info("Solicitud POST a /analyze recibida.")
    if run_analysis is None:
        flash("El sistema no está inicializado correctamente debido a errores de importación.", "error")
        return redirect(url_for('home'))

    selected_llm_model_id = request.form.get('llm_model')
    if not selected_llm_model_id or selected_llm_model_id not in config.LLM_MODELS_CONFIG:
        selected_llm_model_id = "gemini-1.5-flash"
        
    recreate_db_for_this_run = 'force_recreate_db' in request.form

    try:
        app.logger.info(f"Llamando a run_analysis() con modelo='{selected_llm_model_id}'")
        
        dashboard_relative_path = run_analysis(
            selected_llm_model_id=selected_llm_model_id,
            force_recreate_db=recreate_db_for_this_run
        )

        if not dashboard_relative_path:
            flash("El proceso de análisis no generó un dashboard. Revisa los logs.", "info")
            return redirect(url_for('home'))

        dashboard_absolute_path = os.path.join(PROJECT_ROOT, dashboard_relative_path)
        if not os.path.exists(dashboard_absolute_path):
            app.logger.error(f"Dashboard no encontrado en ruta: '{dashboard_absolute_path}'.")
            flash("Error: Análisis completado, pero no se encontró el dashboard HTML.", "error")
            return redirect(url_for('home'))

        return send_file(dashboard_absolute_path)

    except (ValidationError, TypeError) as e_val:
        app.logger.error(f"Error de validación o tipo en la respuesta del LLM: {e_val}")
        flash(f"Error Crítico: La respuesta del LLM no cumplió con el formato esperado. Detalles: {e_val}", "error")
    except Exception as e:
        app.logger.error(f"Ocurrió un error inesperado en la ruta /analyze: {e}", exc_info=True)
        flash(f"Ocurrió un error interno inesperado en el servidor: {str(e)}", "error")

    return redirect(url_for('home'))

if __name__ == '__main__':
    app.logger.info("Iniciando servidor Flask de desarrollo...")
    app.run(host='0.0.0.0', port=8080, debug=True)