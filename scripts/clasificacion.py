# scripts/clasificacion.py
"""Validación por código de la clasificación del modelo y cálculo de todo lo demás con motor_riesgos.
El modelo juzga y redacta; la clase, la probabilidad, el nivel, la estrategia, el responsable, la categoría RBS,
el umbral, el tipo de solicitud y el plazo salen de motor_riesgos a partir de los criterios de la empresa."""
import re

from . import motor_riesgos
from .schemas import ClasificacionRiesgo, _sin_tildes

MAX_PALABRAS = {"titulo": 12, "enunciado": 40, "accion": 30, "solicitud_oferente": 40}
MARCA_VALOR_NO_VERIFICADO = "valor no verificado"
CAMPOS_OBLIGATORIOS = ("objeto_requisito", "dimension_impacto", "impacto", "titulo")


def _normalizar_valor(texto) -> str:
    """Sin tildes, mayúsculas ni espacios, y con coma decimal llevada a punto."""
    return _sin_tildes(str(texto)).replace(" ", "").replace(",", ".")


def valor_en_texto(valor, texto: str) -> bool:
    """El valor aparece en el texto como número completo ('5' no está en '0,5' ni en '25')."""
    v = _normalizar_valor(valor)
    return bool(v) and re.search(r"(?<![\d.])" + re.escape(v) + r"(?!\d|\.\d)", _normalizar_valor(texto)) is not None


def procesar_clasificacion(c: ClasificacionRiesgo, *, id_sec: str, seccion_oferta: str, norma: str, articulo: str, texto_articulo: str,
                           oraciones: list, textos: dict, verificacion: dict, criterios: dict, parte: int = 1) -> dict:
    """Pasos 2 a 7 de la validación. Devuelve {'tipo': 'no_riesgo' | 'alerta' | 'descartada' | 'brecha', ...}.
    oraciones: IDs citados por la verificación; textos: {id: texto} de la sección."""
    cita = " ".join(textos[i] for i in oraciones)
    if c.veredicto in ("CUMPLE", "NO_APLICA"):
        return {"tipo": "no_riesgo", "motivo": c.motivo}
    if c.veredicto == "ALERTA":
        return {"tipo": "alerta", "alerta": {"seccion": id_sec, "seccion_oferta": seccion_oferta, "norma": norma, "articulo": articulo,
                                             "oraciones": oraciones, "cita": cita, "motivo": c.motivo}}
    faltan = [campo for campo in CAMPOS_OBLIGATORIOS if getattr(c, campo) in (None, "")]
    if faltan:
        return {"tipo": "descartada", "motivo": f"clasificación incompleta: falta {', '.join(faltan)}"}

    marcas = []
    brecha = None
    if c.objeto_requisito == "CUANTITATIVO_TECNICO":
        if c.valor_ofertado and c.valor_exigido and c.tipo_limite \
                and valor_en_texto(c.valor_ofertado, cita) and valor_en_texto(c.valor_exigido, texto_articulo):
            brecha = motor_riesgos.brecha_relativa(c.valor_ofertado, c.valor_exigido, c.tipo_limite)
        else:
            marcas.append(MARCA_VALOR_NO_VERIFICADO)   # se calcula sin brecha (Art. 3.5)
    for campo, maximo in MAX_PALABRAS.items():
        texto = getattr(c, campo)
        if texto and len(texto.split()) > maximo:
            marcas.append(f"longitud excedida: {campo}")

    fuente = c.veredicto
    clase, regla, marcas_clase = motor_riesgos.clase(fuente, c.condicion_critico, c.objeto_requisito, brecha,
                                                     c.dimension_impacto == motor_riesgos.DIMENSION_PERSONAS, criterios)
    marcas += marcas_clase
    impacto, ajustado = motor_riesgos.acotar_impacto(clase, c.impacto, criterios)
    if ajustado:
        marcas.append(f"impacto ajustado de {c.impacto} a {impacto}")
    prob = motor_riesgos.probabilidad(fuente, criterios)
    nivel_tabla = motor_riesgos.nivel(prob, impacto, criterios)
    nivel = motor_riesgos.aplicar_consistencia(clase, nivel_tabla, criterios)
    tipo_solicitud, plazo = motor_riesgos.solicitud(fuente, clase, criterios)
    return {"tipo": "brecha", "brecha": {
        "id": f"{id_sec}|{norma}|{articulo}" + (f"#{parte}" if parte > 1 else ""), "seccion": id_sec, "seccion_oferta": seccion_oferta, "norma": norma, "articulo": articulo,
        "oraciones": oraciones, "cita": cita, "texto_articulo": texto_articulo, "verificacion_previa": verificacion,
        "clasificacion": c.model_dump(), "fuente": fuente, "brecha_relativa": brecha,
        "clase": clase, "regla": regla, "marcas": marcas,
        "probabilidad": prob, "impacto": impacto, "dimension_impacto": c.dimension_impacto,
        "nivel_tabla": nivel_tabla, "nivel": nivel, "estrategia": motor_riesgos.estrategia(nivel, criterios),
        "responsable": motor_riesgos.responsable(norma, articulo, criterios), "rbs": motor_riesgos.rbs(norma, articulo, criterios),
        "umbral": motor_riesgos.umbral([(norma, articulo)]), "tipo_solicitud": tipo_solicitud, "plazo": plazo,
        "titulo": c.titulo, "enunciado": c.enunciado, "accion": c.accion, "solicitud_oferente": c.solicitud_oferente, "motivo": c.motivo}}
