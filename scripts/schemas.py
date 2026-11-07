# scripts/schemas.py
import unicodedata
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional, get_args

ImpactoEstimado = Literal["Bajo", "Medio", "Alto"]
ProbabilidadEstimada = Literal["Baja", "Media", "Alta"]
TipoDeRiesgo = Literal["Explícito", "Implícito"]
# --- Clasificación del evaluador de evidencia (CRAG-lite) ---
EvaluacionEvidencia = Literal["CORRECTO", "AMBIGUO", "INSUFICIENTE"]
# --- Trazabilidad por riesgo e informe del análisis por sección ---
Subsanacion = Literal["Ninguna", "Aclaracion", "Documentacion", "Correccion"]
Marca = Literal["sin respaldo normativo", "cita no verificada", "verificar calculo"]
Suficiencia = Literal["Suficiente", "Parcial", "Insuficiente"]
MAX_PALABRAS_CITA = 25
# Verificación por artículo
Veredicto = Literal["Incumple", "Revisar", "Cumple", "No aplica"]
Operador = Literal["<=", ">=", "<", ">", "="]
MotivoDuda = Literal["condicion_no_determinable"]
MAX_REQUISITOS = 3
MAX_PALABRAS_REQUISITO = 20
MAX_PALABRAS_DATO_OFERTA = 20
MAX_ACCIONES_GENERALES = 5

def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").strip().casefold()

def _clave_literal(texto: str) -> str:
    return _sin_tildes(texto).replace("_", " ").replace("-", " ").strip(" .")

def _a_literal(valor, opciones):
    """Lleva un texto del LLM ('alto', 'Aclaración', 'no_aplica'...) al valor canónico del Literal; si no coincide, lo devuelve igual."""
    if isinstance(valor, str):
        for opcion in opciones:
            if _clave_literal(opcion) == _clave_literal(valor):
                return opcion
    return valor

class FuenteNorma(BaseModel):
    """Artículo de una norma de la Base de Conocimiento que respalda un riesgo (clave de cruce con el ground truth)."""
    norma: str = Field(description="Identificador de la norma tal como figura en el fragmento entregado (ej. 'NORM_01').")
    articulo: str = Field(description="Número del artículo tal como figura en el fragmento entregado (ej. '4.2').")

class SourceChunk(BaseModel):
    """Representa un fragmento de la base de conocimiento que fue recuperado como evidencia."""
    contenido: str = Field(description="El contenido textual exacto del fragmento recuperado.")
    nombre_documento_fuente: str = Field(description="El nombre del archivo PDF de donde proviene el fragmento.")
    numero_pagina: int = Field(description="El número de página dentro del documento fuente.")
    score_relevancia: Optional[float] = Field(default=None, description="Puntuación de relevancia asignada por el re-ranker (0 a 1).")

class RiskItem(BaseModel):
    """Representa un único riesgo identificado con todos sus atributos."""
    descripcion_riesgo: str = Field(description="Descripción clara y concisa del riesgo identificado.")
    tipo_de_riesgo: TipoDeRiesgo = Field(description="Clasificación del riesgo como 'Explícito' (directamente mencionado) o 'Implícito' (deducido lógicamente).")
    impacto_estimado: ImpactoEstimado = Field(description="Impacto potencial del riesgo. Debe ser 'Bajo', 'Medio' o 'Alto'.")
    probabilidad_estimada: ProbabilidadEstimada = Field(description="Probabilidad de ocurrencia del riesgo. Debe ser 'Baja', 'Media', o 'Alta'.")
    responsabilidad_mitigacion: str = Field(description="Rol o departamento responsable de las tareas de mitigación preventivas.")
    responsable_accidente: str = Field(description="Rol o departamento que asumiría la responsabilidad principal si el riesgo se materializa.")
    accion_mitigacion: str = Field(description="Acción concreta y específica recomendada para prevenir o mitigar el riesgo (una tarea accionable, no un rol ni un departamento).")
    umbral_alerta: str = Field(description="Indicador o condición medible cuyo cumplimiento debería disparar una alerta o escalamiento (ej. una métrica, un plazo, un valor límite concreto).")
    explicacion_riesgo: str = Field(description="Breve explicación de por qué esto es un riesgo, citando evidencia del contexto.")
    exposicion_riesgo: Optional[int] = Field(default=None, description="Exposición al riesgo = impacto x probabilidad, con escala 1-2-3 en cada eje (resultado de 1 a 9). Es una convención de la matriz de riesgo; impacto y probabilidad los estima el LLM.")
    respaldo_base_conocimiento: Optional[float] = Field(default=None, description="Puntuación (0 a 1) del re-ranker entre el texto del riesgo y el fragmento de la Base de Conocimiento que mejor lo respalda. Mide cuánto se apoya el riesgo en la bibliografía de referencia; no es una probabilidad de que el riesgo sea real.")

    # --- Trazabilidad (análisis por sección) ---
    fuentes: List[FuenteNorma] = Field(default_factory=list, description="Artículos de la Base de Conocimiento que respaldan el riesgo; solo de los fragmentos entregados al modelo. Vacía si ninguno lo respalda.")
    seccion_oferta: str = Field(default="", description="Subsección de la oferta donde se encuentra la cita. La calcula el código, no el modelo.")
    cita_oferta: str = Field(default="", description="Cita textual de la oferta que origina el riesgo (máximo 25 palabras).")
    comentario: str = Field(default="", description="Máximo 2 frases: qué respalda la evidencia y qué falta. Si los fragmentos no cubren el riesgo, lo dice.")
    subsanacion: Subsanacion = Field(default="Ninguna", description="Qué debería subsanar el oferente: 'Ninguna', 'Aclaracion', 'Documentacion' o 'Correccion'.")
    marcas: List[Marca] = Field(default_factory=list, description="Marcas puestas por el código: 'sin respaldo normativo' y/o 'cita no verificada'.")

    # --- Modo verificación (los completa el código a partir de la verificación del artículo) ---
    veredicto: Optional[Literal["Incumple", "Revisar"]] = Field(default=None, description="Incumple (hallazgo) o Revisar (alerta); None en el modo lista.")
    oraciones: List[str] = Field(default_factory=list, description="IDs de las oraciones de la sección que originan el riesgo.")
    requisitos: List[str] = Field(default_factory=list, description="Requisitos del artículo que se contrastan con la oferta.")
    motivo: str = Field(default="", description="Qué no coincide (Incumple) o por qué hay que revisar (Revisar).")

    @field_validator("tipo_de_riesgo", "impacto_estimado", "probabilidad_estimada", "subsanacion", mode="before")
    @classmethod
    def _normalizar_literal(cls, valor, info):
        """El LLM a veces devuelve 'alto', 'ALTO', 'Explicito'... se lleva al valor canónico."""
        return _a_literal(valor, get_args(cls.model_fields[info.field_name].annotation))

    @field_validator("marcas", mode="before")
    @classmethod
    def _normalizar_marcas(cls, valor):
        if isinstance(valor, list):
            return [_a_literal(m, get_args(Marca)) for m in valor]
        return valor

    @field_validator("cita_oferta")
    @classmethod
    def _acotar_cita(cls, valor):
        """Recorta a MAX_PALABRAS_CITA palabras en vez de rechazar el riesgo."""
        palabras = valor.split()
        return " ".join(palabras[:MAX_PALABRAS_CITA]) if len(palabras) > MAX_PALABRAS_CITA else valor

def _acotar_palabras(texto: str, maximo: int) -> str:
    palabras = texto.split()
    return " ".join(palabras[:maximo]) if len(palabras) > maximo else texto

class VerificacionArticulo(BaseModel):
    """Veredicto del modelo sobre UN artículo de la KB frente a las oraciones numeradas de una sección de la oferta."""
    # El orden de los campos es el orden de generación: el modelo razona primero y decide al final.
    oraciones: List[str] = Field(default_factory=list, description="IDs ('O1', 'O2'...) de las oraciones de la sección en que se apoya el veredicto.")
    dato_oferta: str = Field(default="", description="Lo que dice la oferta sobre el requisito (hasta 20 palabras).")
    requisitos: List[str] = Field(default_factory=list, description="Hasta 3 requisitos del artículo, cada uno de hasta 20 palabras tomadas del artículo.")
    valor_oferta: Optional[float] = Field(default=None, description="Valor numérico de la oferta, si hay uno comparable.")
    valor_norma: Optional[float] = Field(default=None, description="Valor numérico del artículo, si hay uno comparable.")
    operador: Optional[Operador] = Field(default=None, description="Condición que el valor de la oferta debe cumplir para CUMPLIR el artículo: valor_oferta <operador> valor_norma.")
    unidad: Optional[str] = Field(default=None, description="Unidad de ambos valores.")
    explicacion: str = Field(default="", description="Una frase que justifica el veredicto.")
    veredicto: Veredicto = Field(description="'Incumple', 'Revisar', 'Cumple' o 'No aplica'.")
    motivo_duda: Optional[MotivoDuda] = Field(default=None, description="Solo con 'Revisar': 'condicion_no_determinable'.")

    @field_validator("veredicto", mode="before")
    @classmethod
    def _normalizar_veredicto(cls, valor):
        return _a_literal(valor, get_args(Veredicto))

    @field_validator("motivo_duda", mode="before")
    @classmethod
    def _normalizar_motivo(cls, valor):
        valor = _a_literal(valor, get_args(MotivoDuda))
        return valor if valor in get_args(MotivoDuda) else None   # valores viejos ('dato_faltante', 'interpretacion') -> None

    @field_validator("operador", mode="before")
    @classmethod
    def _normalizar_operador(cls, valor):
        return {"≤": "<=", "≥": ">=", "==": "="}.get(valor.strip(), valor.strip()) if isinstance(valor, str) else valor

    @field_validator("requisitos")
    @classmethod
    def _acotar_requisitos(cls, valor):
        return [_acotar_palabras(r, MAX_PALABRAS_REQUISITO) for r in valor[:MAX_REQUISITOS]]

    @field_validator("dato_oferta")
    @classmethod
    def _acotar_dato(cls, valor):
        return _acotar_palabras(valor, MAX_PALABRAS_DATO_OFERTA)

class Redaccion(BaseModel):
    """Campos de un hallazgo o alerta que redacta el modelo después de la verificación (el resto lo arma el código)."""
    accion_mitigacion: str = Field(description="Acción concreta; para 'Revisar', verificar o aclarar el punto.")
    umbral_alerta: str = Field(description="Condición medible que dispararía una alerta o escalamiento.")
    impacto_estimado: ImpactoEstimado
    probabilidad_estimada: ProbabilidadEstimada
    responsabilidad_mitigacion: str
    responsable_accidente: str
    comentario: str = Field(default="", description="Máximo 2 frases.")

    @field_validator("impacto_estimado", "probabilidad_estimada", mode="before")
    @classmethod
    def _normalizar_literal(cls, valor, info):
        return _a_literal(valor, get_args(cls.model_fields[info.field_name].annotation))

class LLMResponse(BaseModel):
    """Define la estructura de datos que se espera directamente del LLM."""
    riesgos_identificados: List[RiskItem] = Field(description="Una lista de todos los riesgos identificados.")

class FragmentoRecuperado(BaseModel):
    """Fragmento de la Base de Conocimiento recuperado para una sección (permite calcular hit@k)."""
    norma: str
    articulo: str
    score: Optional[float] = None

class SeccionInforme(BaseModel):
    """Qué se recuperó y cómo se clasificó la evidencia en cada sección de la oferta."""
    id: str
    titulos: List[str] = Field(default_factory=list)
    fragmentos: List[FragmentoRecuperado] = Field(default_factory=list)
    candidatos: Optional[List[FuenteNorma]] = Field(default=None, description="Los K recuperados ANTES del reranker, en orden de la búsqueda vectorial (diagnóstico de la recuperación).")
    clasificacion_crag: Optional[EvaluacionEvidencia] = Field(default=None, description="Solo informa; no bloquea la generación de la sección.")

class ResumenGeneral(BaseModel):
    """Cierre del informe, generado por el LLM a partir de los riesgos unidos y del conteo CRAG."""
    suficiencia_evidencia: Suficiencia = Field(description="'Suficiente', 'Parcial' o 'Insuficiente': cuánto respalda la Base de Conocimiento los riesgos del conjunto.")
    comentarios_generales: str = Field(description="Comentario global sobre la oferta y la evidencia disponible.")
    acciones_generales: List[str] = Field(default_factory=list, description="Hasta 5 acciones generales recomendadas.")

    @field_validator("suficiencia_evidencia", mode="before")
    @classmethod
    def _normalizar_suficiencia(cls, valor):
        return _a_literal(valor, get_args(Suficiencia))

    @field_validator("acciones_generales")
    @classmethod
    def _acotar_acciones(cls, valor):
        return valor[:MAX_ACCIONES_GENERALES]

class RiskReport(BaseModel):
    """El objeto principal que representa el informe completo de análisis de riesgos."""
    configuracion_analisis: dict = Field(default_factory=dict)
    riesgos_identificados: List[RiskItem] = Field(description="Una lista de todos los riesgos identificados en el análisis.")
    fragmentos_fuente: List[SourceChunk] = Field(default_factory=list)
    nombre_proyecto_analizado: Optional[str] = None
    timestamp_analisis: Optional[str] = None
    respuesta_cruda_llm: Optional[str] = None
    # --- Resultado del evaluador de evidencia CRAG-lite (Yan et al., 2024,
    # adaptado sin el componente de búsqueda web, para mantener el sistema 100%
    # local y auditable dentro de la Base de Conocimiento de la organización). ---
    evaluacion_evidencia: Optional[EvaluacionEvidencia] = Field(default=None, description="Clasificación de la suficiencia de la evidencia recuperada, calculada ANTES de generar el análisis: CORRECTO (específica y aplicable), AMBIGUO (temáticamente relacionada pero genérica), o INSUFICIENTE (sin relación real).")
    advertencia_evidencia: Optional[str] = Field(default=None, description="Mensaje explicativo para el usuario cuando evaluacion_evidencia es AMBIGUO o INSUFICIENTE.")
    # --- Informe del análisis por sección ---
    suficiencia_evidencia: Optional[Suficiencia] = None
    comentarios_generales: Optional[str] = None
    acciones_generales: List[str] = Field(default_factory=list)
    secciones: List[SeccionInforme] = Field(default_factory=list)
    registro_tecnico: List[dict] = Field(default_factory=list, description="Todas las verificaciones (Cumple, No aplica, descartes y correcciones del código), con sección, artículo e IDs de oración. No se muestra en el dashboard.")
