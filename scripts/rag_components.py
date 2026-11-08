# scripts/rag_components.py
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors.cross_encoder_rerank import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from typing import List, Optional
import logging
import math
import os
import re

from .schemas import LLMResponse, FuenteNorma, RiskItem, VerificacionArticulo, Redaccion, _sin_tildes
from . import config

logger = logging.getLogger(__name__)

_reranker_model_cache = {}

def _get_reranker_model(model_name: str):
    clave = (model_name, config.RERANKER_MAX_LENGTH)
    if clave not in _reranker_model_cache:
        logger.info(f"--- Cargando modelo de re-ranker '{model_name}' (max_length={config.RERANKER_MAX_LENGTH}) por primera vez en este proceso (se reutilizará en las siguientes preguntas) ---")
        _reranker_model_cache[clave] = HuggingFaceCrossEncoder(model_name=model_name, model_kwargs={"max_length": config.RERANKER_MAX_LENGTH})
    return _reranker_model_cache[clave]


RERANKER_MODEL_NAME = 'BAAI/bge-reranker-v2-m3'


def _normalizar_score(score) -> float:
    """El cross-encoder de una sola etiqueta (bge-reranker-v2-m3) devuelve ya valores
    entre 0 y 1 (sentence-transformers aplica sigmoide por defecto). Si por alguna
    versión llegara un logit crudo fuera de rango, se lo lleva a 0-1 con sigmoide."""
    s = float(score)
    if 0.0 <= s <= 1.0:
        return s
    return 1.0 / (1.0 + math.exp(-max(min(s, 50.0), -50.0)))


class CrossEncoderRerankerConScore(CrossEncoderReranker):
    """Igual que CrossEncoderReranker, pero conserva el score de cada fragmento en
    metadata['relevance_score']. La versión de LangChain ordena y descarta el score,
    por lo que el dashboard no podía mostrar cuán relevante fue cada fragmento."""

    def compress_documents(self, documents, query, callbacks=None):
        if not documents:
            return []
        scores = self.model.score([(query, doc.page_content) for doc in documents])
        con_score = sorted(zip(documents, scores), key=lambda x: float(x[1]), reverse=True)
        resultado = []
        for doc, score in con_score[: self.top_n]:
            metadata = dict(doc.metadata)
            metadata["relevance_score"] = _normalizar_score(score)
            resultado.append(Document(page_content=doc.page_content, metadata=metadata))
        return resultado


def puntuar_riesgos_contra_evidencia(textos_riesgos: List[str], fragmentos: List[Document]) -> List[Optional[float]]:
    """Para cada riesgo, devuelve el MEJOR score (0-1) del re-ranker entre el texto del
    riesgo y los fragmentos de la Base de Conocimiento recuperados. Mide cuánto se
    apoya el riesgo en la bibliografía de referencia. No usa el LLM (cómputo local,
    segundos) ni requiere nuevas llamadas a la API.
    Devuelve None para cada riesgo si no hay fragmentos o si el re-ranker falla."""
    if not textos_riesgos:
        return []
    if not fragmentos or not config.USE_RERANKER:
        return [None] * len(textos_riesgos)
    try:
        model = _get_reranker_model(RERANKER_MODEL_NAME)
        pares = [(texto, f.page_content) for texto in textos_riesgos for f in fragmentos]
        scores = [_normalizar_score(s) for s in model.score(pares)]
        n = len(fragmentos)
        return [max(scores[i * n:(i + 1) * n]) for i in range(len(textos_riesgos))]
    except Exception as e:
        logger.error(f"No se pudo calcular el respaldo de cada riesgo en la Base de Conocimiento: {e}")
        return [None] * len(textos_riesgos)


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

# --- Análisis por sección de la oferta ---
# Campos que pide el prompt: seccion_oferta y marcas los calcula el código (validar_riesgos),
# exposicion_riesgo y respaldo_base_conocimiento también; el modelo no debe emitirlos.
# El ejemplo usa solo marcadores neutros: ningún dominio concreto ni texto de evaluación.
_INSTRUCCIONES_CAMPOS = """
INSTRUCCIONES ESTRICTAS PARA LA RESPUESTA:
1.  Tu respuesta DEBE ser un único objeto JSON, sin texto antes ni después, con UNA SOLA CLAVE PRINCIPAL: "riesgos_identificados" (una lista de objetos).
2.  Identificá todos los riesgos que tengan base en el texto de la SECCIÓN DE LA OFERTA; no hay tope de cantidad. No inventes riesgos que el texto no sustente. Si no hay ninguno, devolvé una lista vacía.
3.  Cada riesgo tiene EXACTAMENTE estos campos:
    a. "descripcion_riesgo": descripción clara y concisa del riesgo.
    b. "tipo_de_riesgo": "Explícito" (el texto lo plantea directamente) o "Implícito" (se deduce del texto).
    c. "explicacion_riesgo": por qué es un riesgo, apoyándote en lo que dice la sección.
    d. "impacto_estimado": "Bajo", "Medio" o "Alto".
    e. "probabilidad_estimada": "Baja", "Media" o "Alta".
    f. "responsabilidad_mitigacion": rol responsable de las tareas preventivas.
    g. "responsable_accidente": rol que asumiría la responsabilidad si el riesgo se materializa.
    h. "accion_mitigacion": una acción concreta y accionable (no un rol ni un departamento).
    i. "umbral_alerta": indicador o condición medible que dispararía una alerta o escalamiento.
    j. "fuentes": {instruccion_fuentes}
    k. "cita_oferta": cita TEXTUAL de la sección (máximo 25 palabras, copiada tal cual) que origina el riesgo.
    l. "comentario": máximo 2 frases. {instruccion_comentario}
    m. "subsanacion": qué debería subsanar el oferente: "Ninguna" (no requiere subsanación), "Aclaracion" (aclarar un punto ambiguo), "Documentacion" (aportar documentación faltante) o "Correccion" (modificar lo ofertado).
4.  NO incluyas los campos "seccion_oferta", "marcas", "exposicion_riesgo" ni "respaldo_base_conocimiento": los completa el sistema.

LA RESPUESTA DEBE SER UN OBJETO JSON VÁLIDO. FORMATO (los textos entre <> son marcadores, reemplazalos por contenido real):
{{
  "riesgos_identificados": [
    {{
      "descripcion_riesgo": "<descripción>",
      "tipo_de_riesgo": "Implícito",
      "explicacion_riesgo": "<explicación>",
      "impacto_estimado": "Medio",
      "probabilidad_estimada": "Media",
      "responsabilidad_mitigacion": "<rol>",
      "responsable_accidente": "<rol>",
      "accion_mitigacion": "<acción concreta>",
      "umbral_alerta": "<condición medible>",
      "fuentes": {ejemplo_fuentes},
      "cita_oferta": "<cita textual de la sección>",
      "comentario": "<máximo 2 frases>",
      "subsanacion": "Aclaracion"
    }}
  ]
}}

Comienza tu respuesta JSON AHORA:
"""

_INSTRUCCION_FUENTES_RAG = (
    'lista de objetos {{"norma": "...", "articulo": "..."}} copiados del encabezado de los fragmentos '
    '[F<n>: <norma>, Art. <artículo>, pág. <n>] que respaldan el riesgo. Solo podés citar los fragmentos F numerados '
    'que recibiste; si ninguno lo respalda, lista vacía.'
)
_INSTRUCCION_COMENTARIO_RAG = (
    'Qué respalda la evidencia de los fragmentos y qué falta. Si los fragmentos no cubren el riesgo, decilo '
    'explícitamente en lugar de inventar un respaldo.'
)
_INSTRUCCION_FUENTES_SIN_RAG = 'siempre una lista vacía [] (no hay normativa disponible).'
_INSTRUCCION_COMENTARIO_SIN_RAG = (
    'Aclarar que el riesgo se identificó sin base normativa disponible, solo con conocimiento general, y qué '
    'habría que verificar.'
)

PROMPT_SECCION_RAG_STR = """
Sos un analista experto en riesgos normativos de ofertas técnicas. Tu tarea es analizar la SECCIÓN DE LA OFERTA e identificar riesgos de incumplimiento o de insuficiencia frente a los FRAGMENTOS NORMATIVOS entregados.

FRAGMENTOS NORMATIVOS (únicos que podés citar en "fuentes"):
{fragmentos}

SECCIÓN DE LA OFERTA:
{seccion}
""" + _INSTRUCCIONES_CAMPOS.replace("{instruccion_fuentes}", _INSTRUCCION_FUENTES_RAG) \
    .replace("{instruccion_comentario}", _INSTRUCCION_COMENTARIO_RAG) \
    .replace("{ejemplo_fuentes}", '[{{"norma": "<norma>", "articulo": "<artículo>"}}]')

# Sin RAG: mismo esquema, pero sin ninguna referencia a fragmentos ni a otro material de apoyo
PROMPT_SECCION_SIN_RAG_STR = """
Sos un analista experto en riesgos de ofertas técnicas. Tu tarea es analizar la SECCIÓN DE LA OFERTA e identificar riesgos de incumplimiento o de insuficiencia, usando únicamente tu conocimiento general.

SECCIÓN DE LA OFERTA:
{seccion}
""" + _INSTRUCCIONES_CAMPOS.replace("{instruccion_fuentes}", _INSTRUCCION_FUENTES_SIN_RAG) \
    .replace("{instruccion_comentario}", _INSTRUCCION_COMENTARIO_SIN_RAG) \
    .replace("{ejemplo_fuentes}", "[]")

# --- Verificación por artículo y clasificación ---
# La sección con sus oraciones numeradas va PRIMERO y es idéntica en todas las llamadas de la sección (prefijo reutilizable
# por Ollama); el artículo va AL FINAL. El ejemplo usa solo marcadores neutros: ningún dominio concreto ni texto de evaluación.
PROMPT_VERIFICACION_STR = """
Sos un revisor de cumplimiento normativo de ofertas técnicas. Vas a verificar UN artículo de una norma contra la SECCIÓN DE LA OFERTA, cuyas oraciones están numeradas.

SECCIÓN DE LA OFERTA (oraciones numeradas):
{seccion_numerada}

Fecha de análisis: {fecha} (usala para evaluar vigencias y plazos).

REGLAS:
1. "Incumple": la oferta da un valor, plazo, método o equipo y el artículo fija un límite o requisito que ese dato no satisface. Es Incumple aunque el artículo prevea excepciones, salvo que la oferta invoque y justifique esa excepción. También es Incumple si el artículo exige expresamente presentar un documento, ensayo, plano o dato y la oferta no lo menciona.
2. "Revisar": SOLO cuando el artículo tiene una condición de aplicación ("cuando...", "si...", "en zonas con...") que la oferta no permite determinar. No uses "Revisar" porque la oferta no detalle un dato ni por dudas de interpretación: hay que elegir entre los otros veredictos. Con "Revisar" completá "motivo_duda" con "condicion_no_determinable".
3. "Cumple": la oferta satisface lo que el artículo exige.
4. "No aplica": la oferta no menciona lo que el artículo regula (salvo lo indicado en la regla 1 sobre documentos, ensayos, planos o datos exigidos expresamente), o el artículo es condicional y la oferta no menciona esa condición.
5. Citá siempre las oraciones de la oferta por su ID en "oraciones" (por ejemplo ["O2"]); no copies su texto. Con "No aplica" la lista puede ir vacía.
6. "requisitos": hasta 3, cada uno de hasta 20 palabras tomadas del artículo. "dato_oferta": lo que dice la oferta, hasta 20 palabras. "explicacion": una sola frase. Razoná primero y decidí el "veredicto" al final.
7. Si hay un valor numérico comparable, completá "valor_oferta", "valor_norma", "operador" y "unidad". "operador" es la condición que el valor de la oferta debe cumplir para CUMPLIR el artículo: "valor_oferta operador valor_norma". Ambos valores van en la misma unidad: compará unidades equivalentes por cuenta propia (horas y días, mm y m) y convertí. Operadores válidos: "<=", ">=", "<", ">", "=". Si no hay un valor comparable, null en esos cuatro campos.
8. Basate solo en el texto del artículo entregado.

Respondé ÚNICAMENTE con un objeto JSON, con las claves en este orden. FORMATO (los textos entre <> son marcadores, reemplazalos por contenido real):
{{
  "oraciones": ["O<n>"],
  "dato_oferta": "<lo que dice la oferta>",
  "requisitos": ["<requisito tomado del artículo>"],
  "valor_oferta": null,
  "valor_norma": null,
  "operador": null,
  "unidad": null,
  "explicacion": "<una frase>",
  "veredicto": "<Incumple | Revisar | Cumple | No aplica>",
  "motivo_duda": null
}}

ARTÍCULO A VERIFICAR:
{articulo}
"""

# Comentario general del informe (modo verificación): recibe solo la decisión, los conteos y el registro de riesgos agrupados.
PROMPT_COMENTARIO_GENERAL_STR = """
Redactá el comentario general de un informe de evaluación técnica de una oferta. Usá SOLO la información de abajo. No agregues riesgos, valores, normas ni recomendaciones que no figuren en ella.

Decisión de aceptabilidad: {decision}
Riesgos por nivel: {conteo_nivel}
Riesgos por clase: {conteo_clase}
Registro de riesgos (título | clase | nivel | responsable | normas y artículos):
{registro}

Escribí entre 3 y 4 oraciones, en tono formal e impersonal:
1. La decisión de aceptabilidad y el motivo principal.
2. En qué áreas responsables se concentran los riesgos de clase Crítico y Mayor.
3. Qué debe resolver el oferente antes de la adjudicación.
Respondé solo con el texto, sin títulos ni viñetas.
"""

# Clasificación según los lineamientos de la empresa. {criterios} = capítulos y artículos que declara criterios_empresa.json
# (texto_para_el_modelo); el resto de las variables es lo mismo que recibía la redacción. Sin ejemplos propios: se citan los artículos.
PROMPT_CLASIFICACION_STR = """
Sos evaluador técnico de ofertas de la empresa. Aplicás los criterios de riesgo de la empresa a UN par: una declaración de la oferta y un artículo de la normativa técnica. Todo lo que escribas tiene que surgir de la sección o del artículo. No inventes datos.

=== CRITERIOS DE LA EMPRESA ===
{criterios}

=== ÍTEMS DEL ART. 2.6 ===
{items_contenido_minimo}

=== ARTÍCULO DE LA NORMATIVA ===
{articulo}

=== SECCIÓN DE LA OFERTA (oraciones numeradas) ===
{seccion_numerada}

=== VERIFICACIÓN PREVIA ===
{verificacion}
Un verificador automático marcó este par como Incumple o Revisar. Puede estar equivocado: decidí vos aplicando los criterios.

=== TAREA ===
1. Aplicá el orden de decisión del Art. 2.2 y elegí UN veredicto: NO_APLICA, DESVIO, EXCEPCION_NO_ACREDITADA, INFORMACION_FALTANTE, CUMPLE o ALERTA.
   - Que la oferta no mencione algo no es un desvío: aplicá los Art. 2.5, 2.6 y 2.7.
   - Superar el requisito es CUMPLE (Art. 2.8).
   - Distinguí desvío de excepción no acreditada con los Art. 2.3 y 2.4.
   - Usá ALERTA solo en el caso del Art. 2.9.
2. Si el veredicto es DESVIO, EXCEPCION_NO_ACREDITADA o INFORMACION_FALTANTE, completá:
   a) Para INFORMACION_FALTANTE:
      item_contenido_minimo: el ítem de la lista del Art. 2.6 al que corresponde el dato que falta, copiado tal cual de la lista; si no corresponde a ninguno, "NINGUNO".
      etapa_requisito: "OFERTA" si el dato debe presentarse con la oferta; "POSTERIOR" si corresponde a ejecución, registros de obra, dossier, conforme a obra, actas o recepción.
      Para DESVIO o EXCEPCION_NO_ACREDITADA:
      materia_3_2_a: true si el requisito trata de alguna de las materias enumeradas en el Art. 3.2.a; si no, false.
      medida_ofrecida: la frase de la oferta que propone algo para cumplir el requisito, copiada tal cual, aunque sea insuficiente. null solo si la oferta no propone nada.
      practica_peligrosa: true solo si lo que propone la oferta crea por sí mismo el peligro que el requisito previene (Art. 3.2.b). false si solo es insuficiente o distinto de lo exigido.
      valor_limite_excepcion: si el artículo admite apartarse del valor general hasta un límite, ese límite copiado del artículo; si no, null.
      valor_demanda_oferta: si la propia oferta declara la carga o el uso que el valor ofertado debe cubrir, ese valor copiado de la oferta; si no, null.
      No decidas si el desvío es Crítico: lo calcula el sistema con estos datos.
   b) objeto_requisito, uno de:
      DOCUMENTAL_PROCEDIMIENTO: requisito del tipo descrito en el Art. 3.4.c.
      RESERVA_ERGONOMIA_EFICIENCIA: requisito del tipo descrito en el Art. 3.4.d.
      VERIFICACION_RUTINA: requisito del tipo descrito en el Art. 3.4.b.
      ENSAYO_ACEPTACION: ensayo o verificación de aceptación omitido o sustituido, como en el Art. 3.3.b.
      ORDINAL: requisito en una escala por escalones, como en el Art. 3.3.d.
      CUANTITATIVO_TECNICO: requisito técnico expresado con un valor numérico.
      OTRO_TECNICO: cualquier otro requisito técnico.
   c) Si es CUANTITATIVO_TECNICO: valor_ofertado y valor_exigido copiados tal cual de la oferta y del artículo, la unidad y tipo_limite (MINIMO, MAXIMO, TOLERANCIA, CANTIDAD o FRECUENCIA). No conviertas unidades ni calcules diferencias.
   d) dimension_impacto: la dimensión del Art. 4.3 más afectada, e impacto de 1 a 5 según sus anclas.
   e) titulo, enunciado, accion y solicitud_oferente, según los Art. 4.1, 7.4 y 8.2:
      titulo: hasta 12 palabras.
      enunciado: hasta 40 palabras, con la fórmula del Art. 4.1.
      accion: hasta 30 palabras.
      solicitud_oferente: hasta 40 palabras; el pedido formal al oferente, con el valor o el documento exigido por el artículo.
   No decidas la clase, la probabilidad, el nivel, la estrategia, el responsable ni el plazo: los calcula el sistema.
3. Con CUMPLE, NO_APLICA o ALERTA completá solo motivo y veredicto; el resto va en null.

Respondé SOLO con este JSON, en este orden:
{{"motivo": "...", "veredicto": "...", "item_contenido_minimo": null, "etapa_requisito": null, "materia_3_2_a": null, "medida_ofrecida": null, "practica_peligrosa": null, "valor_limite_excepcion": null, "valor_demanda_oferta": null, "objeto_requisito": null, "valor_ofertado": null, "valor_exigido": null, "unidad": null, "tipo_limite": null, "dimension_impacto": null, "impacto": null, "titulo": null, "enunciado": null, "accion": null, "solicitud_oferente": null}}
"""

# --- Evaluador de evidencia (CRAG-lite) ---
# Adaptado de Yan et al. (2024), "Corrective Retrieval Augmented Generation"
# (arXiv:2401.15884). Se implementan 2 de las 3 acciones del paper original
# (evidencia suficiente / evidencia insuficiente); se omite deliberadamente
# la tercera acción del paper (búsqueda web externa cuando la evidencia local
# no alcanza), porque contradice el objetivo central de este sistema: operar
# exclusivamente sobre la Base de Conocimiento validada y controlada por la
# organización, sin salir a fuentes externas no auditadas. Este es un recorte
# de diseño intencional, no una limitación técnica.
PROMPT_EVALUADOR_EVIDENCIA_STR = """
Sos un evaluador crítico de evidencia documental. Tu ÚNICA tarea es determinar si el CONTEXTO proporcionado tiene relación real y específica con el PROYECTO descrito. NO generes ningún análisis de riesgos, NO expliques tu razonamiento.

CONTEXTO RECUPERADO:
{context}

PROYECTO A ANALIZAR:
{question}

Clasificá la relación entre el contexto y el proyecto en UNA SOLA de estas tres categorías:
- CORRECTO: el contexto contiene información específica y aplicable directamente a los elementos concretos del proyecto (tecnología, ubicación, plazos, personal, normativa mencionada).
- AMBIGUO: el contexto está temáticamente relacionado (gestión de riesgos, proyectos industriales en general) pero es de carácter genérico, sin abordar los elementos específicos de este proyecto en particular.
- INSUFICIENTE: el contexto no tiene relación real con el proyecto descrito.

Responde ÚNICAMENTE con una de estas tres palabras exactas, sin ningún texto adicional: CORRECTO, AMBIGUO o INSUFICIENTE.
"""


class RetrieverFijo(BaseRetriever):
    """Retriever que devuelve SIEMPRE los fragmentos ya recuperados y re-rankeados,
    sin volver a buscar en la base vectorial ni a pasar por el cross-encoder.
    Se usa para que la cadena de generación reutilice lo que ya recuperó el evaluador
    de evidencia: con consultas largas, el re-ranking en CPU es el paso más caro del
    sistema, y repetirlo daba exactamente los mismos fragmentos."""
    documentos: List[Document]

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:
        return self.documentos


def _construir_retriever(vector_db_instance, k: Optional[int] = None, top_n: Optional[int] = None):
    """Arma el retriever con re-ranking (embeddings + cross-encoder), sin
    envolverlo en ninguna cadena de generación. Se extrajo como función propia
    para poder reutilizarlo tanto en el evaluador de evidencia como en la
    cadena de generación final, sin duplicar la configuración del re-ranker.
    k y top_n (por defecto los valores de config) permiten ajustarlo por sección."""
    k = k or config.K_RETRIEVED_DOCS_BEFORE_RERANK
    top_n = top_n or config.RERANKER_TOP_N
    base_retriever = vector_db_instance.as_retriever(search_kwargs={"k": k})
    final_retriever = base_retriever
    if config.USE_RERANKER:
        logger.info("--- Habilitando Re-ranker (CrossEncoder) ---")
        try:
            model = _get_reranker_model(RERANKER_MODEL_NAME)
            compressor = CrossEncoderRerankerConScore(model=model, top_n=top_n)
            final_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=base_retriever)
            logger.info(f"--- Re-ranker configurado para devolver los mejores {top_n} fragmentos ---")
        except Exception as e_reranker:
            logger.error(f"No se pudo inicializar el Re-ranker. Se usará el retriever base. Error: {e_reranker}")
    return final_retriever


def recuperar_con_candidatos(vector_db_instance, consulta: str, k: int, top_n: int):
    """(candidatos, docs): los k de la búsqueda vectorial en su orden (antes del reranker) y los top_n finales.
    Sin reranker, docs son los primeros top_n de los candidatos."""
    candidatos = vector_db_instance.as_retriever(search_kwargs={"k": k}).invoke(consulta)
    if not config.USE_RERANKER:
        return candidatos, candidatos[:top_n]
    compressor = CrossEncoderRerankerConScore(model=_get_reranker_model(RERANKER_MODEL_NAME), top_n=top_n)
    return candidatos, compressor.compress_documents(candidatos, consulta)


def _clave_documento(d: Document) -> tuple:
    return (d.metadata.get("norma"), d.metadata.get("articulo"))


def unir_fragmentos(listas: List[List[Document]], tope: int) -> List[Document]:
    """Une listas de fragmentos sin repetir (norma, artículo), conserva el mayor score de cada uno
    y devuelve los `tope` de mayor score (a igual score, el que apareció primero)."""
    mejores = {}
    for d in (d for lista in listas for d in lista):
        clave = _clave_documento(d)
        previo = mejores.get(clave)
        if previo is None or (d.metadata.get("relevance_score") or 0) > (previo.metadata.get("relevance_score") or 0):
            mejores[clave] = d
    return sorted(mejores.values(), key=lambda d: d.metadata.get("relevance_score") or 0, reverse=True)[:tope]


def _sin_preambulo(docs: List[Document]) -> List[Document]:
    return [d for d in docs if d.metadata.get("articulo") != "preambulo"]


def recuperar_seccion(vector_db_instance, seccion: dict, tope: Optional[int] = None, sin_preambulo: bool = False):
    """(candidatos, docs) de una sección. Por defecto una sola consulta con el texto de la sección;
    con RECUPERACION_POR_SUBSECCION una consulta por subsección y unión de los resultados.
    tope: máximo de fragmentos finales (por defecto TOPE_FRAGMENTOS_SECCION); sin_preambulo: los chunks 'preambulo' no cuentan."""
    tope = tope or config.TOPE_FRAGMENTOS_SECCION
    quitar = _sin_preambulo if sin_preambulo else (lambda docs: docs)
    subsecciones = [x for _, x in seccion["subsecciones"] if len(x) >= config.MIN_CHARS_SUBSECCION]
    if not config.RECUPERACION_POR_SUBSECCION or not subsecciones:
        candidatos, docs = recuperar_con_candidatos(vector_db_instance, seccion["texto"][:config.SECTION_QUERY_MAX_CHARS], config.K_RECUPERACION, config.TOP_N_POR_SECCION)
        return candidatos, quitar(docs)
    resultados = [recuperar_con_candidatos(vector_db_instance, x[:config.SUBSECTION_QUERY_MAX_CHARS], config.K_SUBSECCION, config.TOP_N_SUBSECCION) for x in subsecciones]
    candidatos, vistos = [], set()
    for cands, _ in resultados:
        for d in cands:
            if _clave_documento(d) not in vistos:
                vistos.add(_clave_documento(d))
                candidatos.append(d)
    return candidatos, unir_fragmentos([quitar(docs) for _, docs in resultados], tope)


def crear_evaluador_evidencia(llm):
    """Cadena CRAG-lite: clasifica CORRECTO/AMBIGUO/INSUFICIENTE, sin generar
    ningún análisis de riesgos. Se invoca ANTES de la cadena de generación
    principal, con los mismos fragmentos ya recuperados por el re-ranker."""
    prompt = PromptTemplate(template=PROMPT_EVALUADOR_EVIDENCIA_STR, input_variables=["context", "question"])
    return prompt | llm | StrOutputParser()


def clasificar_evidencia(respuesta_cruda: str) -> str:
    """Normaliza la respuesta del evaluador a una de las 3 categorías válidas. Solo acepta
    coincidencia exacta (ignorando mayúsculas y puntuación); cualquier otra respuesta cae
    en AMBIGUO, el valor prudente, en vez de dar por buena la evidencia."""
    texto = (respuesta_cruda or "").strip().strip(".,;:!\"'*` \n").upper()
    if texto in ("CORRECTO", "AMBIGUO", "INSUFICIENTE"):
        return texto
    logger.warning(f"Respuesta del evaluador de evidencia sin coincidencia exacta ({texto[:60]!r}); se asume AMBIGUO.")
    return "AMBIGUO"


def get_llm_instance(model_id: str, formato: Optional[dict] = None, razonamiento: bool = False, num_predict: Optional[int] = None):
    """formato: esquema JSON con el que Ollama restringe la salida (solo aplica al proveedor ollama).
    razonamiento: activa el thinking con el muestreo VERIF_* (solo ollama).
    num_predict: tope de tokens de salida (solo ollama); sin valor, sin tope. En ollama todas las llamadas tienen timeout."""
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
        if provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=model_id,
                base_url=config.OLLAMA_BASE_URL,
                num_ctx=config.OLLAMA_NUM_CTX,
                reasoning=razonamiento,
                temperature=config.VERIF_TEMPERATURE if razonamiento else 0,
                seed=config.OLLAMA_SEED,
                client_kwargs={"timeout": config.OLLAMA_TIMEOUT_S},
                **({"num_predict": num_predict} if num_predict else {}),
                **({"top_p": config.VERIF_TOP_P, "top_k": config.VERIF_TOP_K} if razonamiento else {}),
                **({"format": formato} if formato else {})
            )

        elif provider == "google":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=model_id,
                api_key=api_key,
                temperature=0.2,
                convert_system_message_to_human=True
            )

        elif provider == "groq":
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
        logger.error(f"Error de importación para el proveedor '{provider}'. {e}")
        return None
    except Exception as e:
        logger.error(f"Error al inicializar el modelo '{model_id}': {e}", exc_info=True)
        return None


def crear_cadena_rag(llm, vector_db_instance, documentos_precalculados: Optional[List[Document]] = None):
    if not llm or not vector_db_instance:
        logger.error("Instancia de LLM o Vector DB no proporcionada.")
        return None
    try:
        if documentos_precalculados:
            logger.info(f"--- Se reutilizan los {len(documentos_precalculados)} fragmentos ya recuperados (sin repetir búsqueda ni re-ranking) ---")
            final_retriever = RetrieverFijo(documentos=documentos_precalculados)
        else:
            final_retriever = _construir_retriever(vector_db_instance)
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
    fragmento de la Base de Conocimiento."""
    if not llm:
        logger.error("Instancia de LLM no proporcionada.")
        return None
    try:
        prompt_sin_contexto_str = PROMPT_TEMPLATE_STR.replace(
            "{context}",
            "(No se proporcionó ningún fragmento de la Base de Conocimiento. Respondé únicamente con tu conocimiento general, sin inventar citas ni referencias a documentos.)"
        )
        prompt = PromptTemplate(template=prompt_sin_contexto_str, input_variables=["question"])
        cadena_sin_rag = prompt | llm | StrOutputParser()
        logger.info("--- Cadena SIN RAG (ablation) creada exitosamente ---")
        return cadena_sin_rag
    except Exception as e:
        logger.error(f"Error al crear la cadena sin RAG: {e}", exc_info=True)
        return None


# --- Análisis por sección: cadenas, fragmentos numerados y validación por código ---

def formatear_fragmentos(docs: List[Document]) -> str:
    """Fragmentos numerados para el prompt: '[F1: NORM_01, Art. 4.2, pág. 12] texto'. El modelo solo puede citar estos F."""
    bloques = []
    for i, d in enumerate(docs, 1):
        m = d.metadata
        pagina = m.get("pagina", -1)
        pag_txt = f", pág. {pagina}" if pagina not in (None, -1) else ""
        bloques.append(f"[F{i}: {m.get('norma', '?')}, Art. {m.get('articulo', '?')}{pag_txt}] {d.page_content}")
    return "\n\n".join(bloques) or "(sin fragmentos recuperados)"


def claves_fragmentos(docs: List[Document]) -> List[dict]:
    """[{norma, articulo}] de los fragmentos entregados al modelo (lo que acepta validar_riesgos)."""
    return [{"norma": d.metadata.get("norma", ""), "articulo": str(d.metadata.get("articulo", ""))} for d in docs]


def crear_cadena_seccion(llm, usar_rag: bool = True):
    """Prompt de una sección de la oferta -> mensaje del LLM (su .content es el texto JSON). Con RAG recibe fragmentos y sección;
    sin RAG solo la sección (misma estructura de salida, sin ninguna referencia a contexto)."""
    if usar_rag:
        prompt = PromptTemplate(template=PROMPT_SECCION_RAG_STR, input_variables=["fragmentos", "seccion"])
    else:
        prompt = PromptTemplate(template=PROMPT_SECCION_SIN_RAG_STR, input_variables=["seccion"])
    return prompt | llm   # devuelve el mensaje (no solo el texto) para leer prompt_eval_count de Ollama


def crear_cadena_verificacion(llm):
    """Verificación de UN artículo contra la sección numerada -> mensaje del LLM (su .content es el JSON de VerificacionArticulo)."""
    prompt = PromptTemplate(template=PROMPT_VERIFICACION_STR, input_variables=["seccion_numerada", "articulo"],
                            partial_variables={"fecha": config.FECHA_REFERENCIA})
    return prompt | llm


def crear_cadena_clasificacion(llm):
    """Clasificación de un Incumple o Revisar según los lineamientos -> mensaje del LLM (su .content es el JSON de ClasificacionRiesgo)."""
    return PromptTemplate(template=PROMPT_CLASIFICACION_STR, input_variables=["criterios", "items_contenido_minimo", "articulo", "seccion_numerada", "verificacion"]) | llm


def crear_cadena_comentario(llm):
    """Comentario general -> mensaje del LLM (su .content es el texto). Temperatura 0 y seed fija (get_llm_instance)."""
    return PromptTemplate(template=PROMPT_COMENTARIO_GENERAL_STR, input_variables=["decision", "conteo_nivel", "conteo_clase", "registro"]) | llm


def formatear_oraciones(oraciones: List[tuple]) -> str:
    """'[O1] texto' por línea."""
    return "\n".join(f"[{id_}] {texto}" for id_, texto in oraciones)


def formatear_articulo(doc: Document) -> str:
    """Identificador del artículo y su texto: '[NORM_01, Art. 4.2]' + contenido."""
    return f"[{doc.metadata.get('norma', '?')}, Art. {doc.metadata.get('articulo', '?')}]\n{doc.page_content}"


_COMPARADORES = {
    "<=": lambda a, b: a <= b or math.isclose(a, b), ">=": lambda a, b: a >= b or math.isclose(a, b),
    "<": lambda a, b: a < b and not math.isclose(a, b), ">": lambda a, b: a > b and not math.isclose(a, b),
    "=": math.isclose,
}


def _contiene_unidad(texto: str, unidad: str) -> bool:
    """La unidad aparece en el texto como palabra propia (no dentro de otra), sin tildes ni mayúsculas ('N·m' y 'Nm' son iguales)."""
    t = _sin_tildes(texto).replace("·", "")
    u = _sin_tildes(unidad).replace("·", "").replace(" ", "")
    return bool(u) and re.search(r"(?<![a-z])" + re.escape(u) + r"(?![a-z])", t) is not None


def procesar_verificacion(v: VerificacionArticulo, oraciones: List[tuple], texto_articulo: str):
    """Validación por código de una verificación. Devuelve (verificacion | None, registro):
    - IDs de oración inexistentes (o Incumple/Revisar sin oraciones) -> None y estado 'descartada'.
    - Si valor_oferta, valor_norma, operador y unidad están completos y la unidad figura en las oraciones citadas y en el
      artículo, el código compara; si el resultado contradice Incumple/Cumple NO cambia el veredicto: registra 'discrepancia_numerica'.
    oraciones: [(id, texto)] de la sección. registro: {estado, motivo?}."""
    textos = dict(oraciones)
    ids = [i.strip().upper() for i in v.oraciones]
    inexistentes = [i for i in ids if i not in textos]
    if inexistentes:
        return None, {"estado": "descartada", "motivo": f"IDs de oración inexistentes: {', '.join(inexistentes)}"}
    v = v.model_copy(update={"oraciones": list(dict.fromkeys(ids))})
    registro = {"estado": "ok"}
    if v.valor_oferta is not None and v.valor_norma is not None and v.operador and v.unidad \
            and _contiene_unidad(" ".join(textos[i] for i in v.oraciones), v.unidad) and _contiene_unidad(texto_articulo, v.unidad):
        cumple = _COMPARADORES[v.operador](v.valor_oferta, v.valor_norma)
        if (cumple and v.veredicto == "Incumple") or (not cumple and v.veredicto == "Cumple"):
            registro = {"estado": "discrepancia_numerica",
                        "motivo": f"{v.valor_oferta:g} {v.operador} {v.valor_norma:g} {v.unidad} es {'cierto' if cumple else 'falso'}"}
    if v.veredicto in ("Incumple", "Revisar") and not v.oraciones:
        return None, {**registro, "estado": "descartada", "motivo": "sin oraciones de la oferta que respalden el veredicto"}
    return v, registro


def _dato_incumple(v: VerificacionArticulo) -> str:
    """Lo que dice la oferta; si el modelo no lo dio, los valores comparados."""
    if v.dato_oferta or None in (v.valor_oferta, v.valor_norma, v.operador):
        return v.dato_oferta
    return f"{v.valor_oferta:g} {v.unidad or ''} frente a {v.operador} {v.valor_norma:g} {v.unidad or ''}".replace("  ", " ").strip()


def armar_descripcion(cita: str, norma: str, articulo: str, requisitos: List[str], v: VerificacionArticulo) -> str:
    """'La oferta indica «<cita>». <NORMA> Art. <art> exige: <requisitos>. No coincide: <dato>. | A revisar: <explicación>.'"""
    def limpio(t):
        return t.strip().rstrip(".").strip()
    exige = "; ".join(limpio(r) for r in requisitos)
    if v.veredicto == "Incumple":
        cierre = f"No coincide: {limpio(_dato_incumple(v))}."
    else:
        cierre = f"A revisar: {limpio(v.explicacion)}."
    return f"La oferta indica «{cita}». {norma} Art. {articulo} exige: {exige}. {cierre}"


def armar_riesgo(v: VerificacionArticulo, redaccion: Redaccion, doc: Document, oraciones: List[tuple], subsecciones: List[tuple], discrepancia_numerica: bool = False) -> RiskItem:
    """Hallazgo (Incumple) o alerta (Revisar) con todo lo verificable armado por código: cita exacta, fuentes del fragmento
    verificado, sección y descripción. El modelo solo aporta la redacción de gestión."""
    textos = dict(oraciones)
    norma, articulo = doc.metadata.get("norma", ""), str(doc.metadata.get("articulo", ""))
    cita = " ".join(textos[i] for i in v.oraciones)
    primera = normalizar_para_comparar(textos[v.oraciones[0]])
    seccion = next((titulo for titulo, texto in subsecciones if primera in normalizar_para_comparar(texto)), subsecciones[0][0] if subsecciones else "")
    requisitos = v.requisitos or [doc.metadata.get("titulo", "")]
    if v.veredicto == "Incumple":
        motivo = f"No coincide: {_dato_incumple(v)}".strip()
    else:
        motivo = f"{(v.motivo_duda or 'condicion_no_determinable').replace('_', ' ')}: {v.explicacion}".strip()
    riesgo = RiskItem(
        descripcion_riesgo=armar_descripcion(cita, norma, articulo, requisitos, v),
        tipo_de_riesgo="Explícito" if v.veredicto == "Incumple" else "Implícito",
        explicacion_riesgo=v.explicacion or motivo,
        impacto_estimado=redaccion.impacto_estimado, probabilidad_estimada=redaccion.probabilidad_estimada,
        responsabilidad_mitigacion=redaccion.responsabilidad_mitigacion, responsable_accidente=redaccion.responsable_accidente,
        accion_mitigacion=redaccion.accion_mitigacion, umbral_alerta=redaccion.umbral_alerta, comentario=redaccion.comentario,
        fuentes=[FuenteNorma(norma=norma, articulo=articulo)], seccion_oferta=seccion,
        subsanacion="Correccion" if v.veredicto == "Incumple" else "Aclaracion",
        veredicto=v.veredicto, oraciones=v.oraciones, requisitos=requisitos, motivo=motivo,
        marcas=["verificar calculo"] if discrepancia_numerica else [])
    riesgo.cita_oferta = cita   # exacta: se asigna después de construir para que no la recorte el límite de palabras del modo lista
    return riesgo


def normalizar_para_comparar(texto: str) -> str:
    """Minúsculas, sin tildes y solo caracteres alfanuméricos: compara citas sin depender de espacios, saltos de línea ni signos."""
    return "".join(c for c in _sin_tildes(texto or "") if c.isalnum())


def _clave_fuente(norma: str, articulo: str) -> tuple:
    return (str(norma).strip().upper(), str(articulo).strip().rstrip(".").strip())


def validar_riesgos(riesgos: list, fragmentos_entregados: List[dict], subsecciones: List[tuple]) -> list:
    """Valida por código, sin descartar nunca un riesgo:
    - fuentes: se quitan las que no estén entre los fragmentos entregados (se reescriben con los valores del
      fragmento); si no queda ninguna, marca 'sin respaldo normativo'.
    - cita_oferta: si su forma normalizada no es subcadena del texto de la sección, marca 'cita no verificada'.
    - seccion_oferta: la subsección donde se encuentra la cita; si no se encuentra, la primera de la sección.
    fragmentos_entregados: [{norma, articulo}]; subsecciones: [(titulo, texto)] de la sección."""
    entregados = {_clave_fuente(f["norma"], f["articulo"]): (f["norma"], str(f["articulo"])) for f in fragmentos_entregados}
    normalizadas = [(titulo, normalizar_para_comparar(texto)) for titulo, texto in subsecciones]
    seccion_completa = "".join(t for _, t in normalizadas)
    primera = subsecciones[0][0] if subsecciones else ""
    for riesgo in riesgos:
        validas = []
        for f in riesgo.fuentes:
            canonica = entregados.get(_clave_fuente(f.norma, f.articulo))
            if canonica and canonica not in [(v.norma, v.articulo) for v in validas]:
                validas.append(FuenteNorma(norma=canonica[0], articulo=canonica[1]))
        riesgo.fuentes = validas
        marcas = [] if validas else ["sin respaldo normativo"]
        cita = normalizar_para_comparar(riesgo.cita_oferta)
        if cita and cita in seccion_completa:
            riesgo.seccion_oferta = next((titulo for titulo, texto in normalizadas if cita in texto), primera)
        else:
            marcas.append("cita no verificada")
            riesgo.seccion_oferta = primera
        riesgo.marcas = marcas
    return riesgos
