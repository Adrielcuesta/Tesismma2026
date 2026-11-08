# scripts/clasificacion.py
"""Validación por código de la clasificación del modelo y cálculo de todo lo demás con motor_riesgos.
El modelo juzga y redacta; la clase, la probabilidad, el nivel, la estrategia, el responsable, la categoría RBS,
el umbral, el tipo de solicitud y el plazo salen de motor_riesgos a partir de los criterios de la empresa."""
import re

from . import motor_riesgos
from .schemas import ClasificacionRiesgo, _sin_tildes

MAX_PALABRAS = {"titulo": 12, "enunciado": 40, "accion": 30, "solicitud_oferente": 40}
MARCA_VALOR_NO_VERIFICADO = "valor no verificado"
MOTIVO_BRECHA_NULA = "contradicción entre el veredicto del modelo y las cifras extraídas: revisar"
ESTADO_DESCARTADA_CALCULO = "descartada por cálculo"
CAMPOS_OBLIGATORIOS =("objeto_requisito", "dimension_impacto", "impacto", "titulo")


def _normalizar_valor(texto) -> str:
    """Sin tildes, mayúsculas ni espacios, y con coma decimal llevada a punto."""
    return _sin_tildes(str(texto)).replace(" ", "").replace(",", ".")


def valor_en_texto(valor, texto: str) -> bool:
    """El valor aparece en el texto como número completo ('5' no está en '0,5' ni en '25')."""
    v = _normalizar_valor(valor)
    return bool(v) and re.search(r"(?<![\d.])" + re.escape(v) + r"(?!\d|\.\d)", _normalizar_valor(texto)) is not None


def _alfanumerico(texto) -> str:
    """Minúsculas, sin tildes y solo alfanuméricos: compara sin depender de espacios, signos ni saltos de línea."""
    return "".join(c for c in _sin_tildes(str(texto)) if c.isalnum())


def item_contenido_minimo(texto, criterios):
    """Ítem de la lista del Art. 2.6 que coincide (normalizado) con `texto`, solo o con su disciplina; None si ninguno ('NINGUNO' incluido)."""
    if not texto:
        return None
    n = _alfanumerico(texto)
    return next((i for i in criterios["contenido_minimo_oferta"]["items"]
                 if n in (_alfanumerico(i["item"]), _alfanumerico(i["disciplina"] + i["item"]))), None)


def condicion_critico(c: ClasificacionRiesgo, cita: str, texto_articulo: str):
    """Art. 3.2 calculado por código a partir de los hechos que extrae el modelo; en este orden: c, d, b, a.
    Devuelve (letra | None, marcas). Un valor o una medida declarados que no están en el texto correspondiente se ignoran con una marca."""
    marcas = []

    def verificado(campo, texto):
        valor = getattr(c, campo)
        if not valor:
            return False
        if valor_en_texto(valor, texto):
            return True
        marcas.append(f"{MARCA_VALOR_NO_VERIFICADO}: {campo}")
        return False

    ofertado_ok = bool(c.valor_ofertado) and valor_en_texto(c.valor_ofertado, cita)
    medida_ok = bool(c.medida_ofrecida) and _alfanumerico(c.medida_ofrecida) in _alfanumerico(cita)
    if c.medida_ofrecida and not medida_ok:
        marcas.append(f"{MARCA_VALOR_NO_VERIFICADO}: medida_ofrecida")

    # 3.2.c solo si el límite de la excepción es numérico y distinto del exigido (si es igual, el modelo copió el límite normal)
    if motor_riesgos.limite_excepcion_propio(c.valor_limite_excepcion, c.valor_exigido) and verificado("valor_limite_excepcion", texto_articulo) and ofertado_ok \
            and motor_riesgos.fuera_de_limite(c.valor_ofertado, c.valor_limite_excepcion, c.tipo_limite):
        return "c", marcas + [f"3.2.c: {c.valor_ofertado} queda fuera del límite {c.valor_limite_excepcion} que admite el artículo"]
    if verificado("valor_demanda_oferta", cita) and ofertado_ok             and motor_riesgos.no_cubre_demanda(c.valor_ofertado, c.valor_demanda_oferta, c.tipo_limite):
        return "d", marcas + [f"3.2.d: {c.valor_ofertado} no cubre la demanda {c.valor_demanda_oferta} que declara la oferta"]
    if c.practica_peligrosa is True and medida_ok:
        return "b", marcas + ["3.2.b: la medida ofrecida crea el peligro que el requisito previene"]
    if c.materia_3_2_a is True and c.medida_ofrecida is None:   # una medida declarada pero no verificada no habilita "a"
        return "a", marcas + ["3.2.a: materia del Art. 3.2.a sin medida ofrecida"]
    return None, marcas


def armar_salidas(brechas: list, criterios: dict):
    """(riesgos agrupados con id, solicitudes con número, resumen ejecutivo) a partir del registro de brechas; las descartadas por cálculo no cuentan."""
    activas = [b for b in brechas if b.get("estado") != ESTADO_DESCARTADA_CALCULO]
    riesgos = motor_riesgos.agrupar(activas, criterios)
    for i, r in enumerate(riesgos, 1):
        r["id"] = f"R{i}"
    solicitudes = motor_riesgos.solicitudes(riesgos, activas, criterios)
    for i, s in enumerate(solicitudes, 1):
        s["numero"] = i
    return riesgos, solicitudes, motor_riesgos.resumen_ejecutivo(riesgos, criterios)


def procesar_clasificacion(c: ClasificacionRiesgo, *, id_sec: str, seccion_oferta: str, norma: str, articulo: str, texto_articulo: str,
                           oraciones: list, textos: dict, verificacion: dict, criterios: dict, parte: int = 1) -> dict:
    """Pasos 2 a 7 de la validación. Devuelve {'tipo': 'no_riesgo' | 'alerta' | 'descartada' | 'descartada_por_calculo' | 'brecha', ...}.
    oraciones: IDs citados por la verificación; textos: {id: texto} de la sección."""
    cita = " ".join(textos[i] for i in oraciones)
    if c.veredicto in ("CUMPLE", "NO_APLICA"):
        return {"tipo": "no_riesgo", "motivo": c.motivo}
    if c.veredicto == "ALERTA":
        return {"tipo": "alerta", "alerta": {"seccion": id_sec, "seccion_oferta": seccion_oferta, "norma": norma, "articulo": articulo,
                                             "oraciones": oraciones, "cita": cita, "motivo": c.motivo}}
    item = None
    if c.veredicto == "INFORMACION_FALTANTE":   # Art. 2.5 y 2.7.c: el dato tiene que ser un ítem del Art. 2.6 que se presenta con la oferta
        item = item_contenido_minimo(c.item_contenido_minimo, criterios)
        if item is None:
            return {"tipo": "no_riesgo", "regla": "2.5", "motivo": f"{c.motivo} [Art. 2.5: no es un ítem del Art. 2.6]"}
        if c.etapa_requisito == "POSTERIOR":
            return {"tipo": "no_riesgo", "regla": "2.7.c", "motivo": f"{c.motivo} [Art. 2.7.c: se exige en una etapa posterior]"}
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
    if item is not None:   # Art. 3.6.4: Mayor si el ítem es materia crítica del Art. 3.2.a, Menor si no; no depende del modelo
        condicion = "a" if item["materia_critica"] else None
        marcas.append(f"3.6.4: ítem del Art. 2.6 «{item['item']}» ({'' if item['materia_critica'] else 'no '}materia crítica)")
    else:
        condicion, marcas_condicion = condicion_critico(c, cita, texto_articulo)
        marcas += marcas_condicion
    if brecha == 0 and condicion is None and item is None and motor_riesgos.misma_unidad_numerica(c.valor_ofertado, c.valor_exigido):
        # Las reglas 3.3.a, 3.3.e y 3.4.a suponen brecha > 0: con las cifras extraídas la oferta cumple, así que no hay riesgo, hay una contradicción
        base = {"seccion": id_sec, "seccion_oferta": seccion_oferta, "norma": norma, "articulo": articulo, "oraciones": oraciones, "cita": cita}
        return {"tipo": "descartada_por_calculo", "motivo": MOTIVO_BRECHA_NULA,
                "alerta": {**base, "motivo": MOTIVO_BRECHA_NULA, "origen": "brecha_nula"},
                "brecha": {"id": f"{id_sec}|{norma}|{articulo}" + (f"#{parte}" if parte > 1 else ""), **base, "oraciones_texto": {i: textos[i] for i in oraciones},
                           "texto_articulo": texto_articulo, "verificacion_previa": verificacion, "clasificacion": c.model_dump(), "fuente": fuente,
                           "brecha_relativa": brecha, "estado": ESTADO_DESCARTADA_CALCULO, "marcas": marcas, "titulo": c.titulo, "motivo": MOTIVO_BRECHA_NULA}}
    clase, regla, marcas_clase = motor_riesgos.clase(fuente, condicion, c.objeto_requisito, brecha,
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
        "oraciones": oraciones, "oraciones_texto": {i: textos[i] for i in oraciones}, "cita": cita, "texto_articulo": texto_articulo, "verificacion_previa": verificacion,
        "clasificacion": c.model_dump(), "fuente": fuente, "brecha_relativa": brecha, "condicion_critico": condicion,
        "clase": clase, "regla": regla, "marcas": marcas,
        "probabilidad": prob, "impacto": impacto, "dimension_impacto": c.dimension_impacto,
        "nivel_tabla": nivel_tabla, "nivel": nivel, "estrategia": motor_riesgos.estrategia(nivel, criterios),
        "responsable": motor_riesgos.responsable(norma, articulo, criterios), "rbs": motor_riesgos.rbs(norma, articulo, criterios),
        "umbral": motor_riesgos.umbral([(norma, articulo)]), "tipo_solicitud": tipo_solicitud, "plazo": plazo,
        "titulo": c.titulo, "enunciado": c.enunciado, "accion": c.accion, "solicitud_oferente": c.solicitud_oferente, "motivo": c.motivo}}
