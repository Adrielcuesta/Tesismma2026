# tests/test_verificacion.py
import pytest
from langchain_core.documents import Document

from scripts.main import _unir_y_deduplicar
from scripts.rag_components import armar_descripcion, armar_riesgo, procesar_verificacion
from scripts.schemas import Redaccion, VerificacionArticulo

ORACIONES = [
    ("O1", "El valor ofertado es de 7 mm en la zona de trabajo."),
    ("O2", "El par de apriete será de 120 N·m."),
    ("O3", "Se entregará documentación al finalizar."),
]
ARTICULO = "Art. 1.1. Tolerancias\nEl valor no excederá 5 mm. El par de apriete mínimo es de 150 N·m."


def _v(**kw):
    base = {"veredicto": "Cumple", "oraciones": ["O1"]}
    return VerificacionArticulo(**{**base, **kw})


# --- veredictos con literales raros ---

@pytest.mark.parametrize("crudo, esperado", [
    ("incumple", "Incumple"), ("INCUMPLE", "Incumple"), (" Incumple. ", "Incumple"), ("revisar", "Revisar"),
    ("Cumple", "Cumple"), ("CUMPLE", "Cumple"), ("no aplica", "No aplica"), ("No_Aplica", "No aplica"), ("NO-APLICA", "No aplica"),
])
def test_veredicto_con_literales_raros(crudo, esperado):
    assert _v(veredicto=crudo).veredicto == esperado


def test_veredicto_desconocido_se_rechaza():
    with pytest.raises(ValueError):
        _v(veredicto="Quizás")


def test_motivo_duda_y_operador_normalizados():
    v = _v(veredicto="Revisar", motivo_duda="Condicion no determinable", operador="≤")
    assert v.motivo_duda == "condicion_no_determinable" and v.operador == "<="


@pytest.mark.parametrize("viejo", ["dato_faltante", "interpretacion", "Dato faltante"])
def test_motivo_duda_viejo_se_mapea_a_none(viejo):
    assert _v(veredicto="Revisar", motivo_duda=viejo).motivo_duda is None


def test_veredicto_es_el_ultimo_campo_de_razonamiento():
    campos = list(VerificacionArticulo.model_fields)
    assert campos.index("explicacion") < campos.index("veredicto") and campos[-2:] == ["veredicto", "motivo_duda"]
    assert campos.index("dato_oferta") < campos.index("veredicto") and campos[0] == "oraciones"


def test_requisitos_y_dato_oferta_se_acotan():
    v = _v(requisitos=["palabra " * 30] * 5, dato_oferta="x " * 40)
    assert len(v.requisitos) == 3 and all(len(r.split()) == 20 for r in v.requisitos)
    assert len(v.dato_oferta.split()) == 20


# --- IDs de oración inválidos ---

def test_id_inexistente_descarta_la_verificacion():
    v, registro = procesar_verificacion(_v(veredicto="Incumple", oraciones=["O1", "O9"]), ORACIONES, ARTICULO)
    assert v is None
    assert registro["estado"] == "descartada" and "O9" in registro["motivo"]


def test_id_en_minuscula_se_normaliza():
    v, registro = procesar_verificacion(_v(veredicto="Incumple", oraciones=["o1"]), ORACIONES, ARTICULO)
    assert v.oraciones == ["O1"] and registro["estado"] == "ok"


def test_incumple_o_revisar_sin_oraciones_se_descartan_pero_no_aplica_no():
    assert procesar_verificacion(_v(veredicto="Incumple", oraciones=[]), ORACIONES, ARTICULO)[0] is None
    assert procesar_verificacion(_v(veredicto="Revisar", oraciones=[]), ORACIONES, ARTICULO)[0] is None
    v, _ = procesar_verificacion(_v(veredicto="No aplica", oraciones=[]), ORACIONES, ARTICULO)
    assert v.veredicto == "No aplica"


# --- comparación numérica: marca discrepancias sin cambiar el veredicto ---

def test_discrepancia_incumple_con_valores_que_cumplen_no_cambia_veredicto():
    v, registro = procesar_verificacion(_v(veredicto="Incumple", valor_oferta=4, valor_norma=5, operador="<=", unidad="mm"), ORACIONES, ARTICULO)
    assert v.veredicto == "Incumple" and registro["estado"] == "discrepancia_numerica"


def test_discrepancia_cumple_con_valores_que_incumplen_no_cambia_veredicto():
    v, registro = procesar_verificacion(_v(veredicto="Cumple", valor_oferta=7, valor_norma=5, operador="<=", unidad="mm"), ORACIONES, ARTICULO)
    assert v.veredicto == "Cumple" and registro["estado"] == "discrepancia_numerica"


def test_discrepancia_agrega_la_marca_al_hallazgo():
    v, registro = procesar_verificacion(_v(veredicto="Incumple", valor_oferta=4, valor_norma=5, operador="<=", unidad="mm"), ORACIONES, ARTICULO)
    r = armar_riesgo(v, REDACCION, DOC, ORACIONES, SUBSECCIONES, registro["estado"] == "discrepancia_numerica")
    assert r.veredicto == "Incumple" and r.marcas == ["verificar calculo"]


def test_borde_igual_cumple_con_mayor_o_igual():
    _, registro = procesar_verificacion(_v(veredicto="Cumple", oraciones=["O2"], valor_oferta=150, valor_norma=150, operador=">=", unidad="N·m"), ORACIONES, ARTICULO)
    assert registro["estado"] == "ok"


def test_si_el_resultado_coincide_con_el_veredicto_no_se_corrige():
    v, registro = procesar_verificacion(_v(veredicto="Incumple", valor_oferta=7, valor_norma=5, operador="<=", unidad="mm"), ORACIONES, ARTICULO)
    assert v.veredicto == "Incumple" and registro["estado"] == "ok"


def test_unidad_que_no_figura_en_oferta_o_articulo_no_compara():
    # 'm' no figura como palabra propia en las oraciones citadas ('7 mm' es otra unidad)
    v, registro = procesar_verificacion(_v(veredicto="Incumple", valor_oferta=4, valor_norma=5, operador="<=", unidad="m"), ORACIONES, ARTICULO)
    assert v.veredicto == "Incumple" and registro["estado"] == "ok"
    # 'kg' no figura en el artículo
    v, registro = procesar_verificacion(_v(veredicto="Incumple", valor_oferta=4, valor_norma=5, operador="<=", unidad="kg"), ORACIONES, ARTICULO)
    assert v.veredicto == "Incumple" and registro["estado"] == "ok"


def test_datos_numericos_incompletos_no_comparan():
    for falta in ("valor_oferta", "valor_norma", "operador", "unidad"):
        datos = {"valor_oferta": 4, "valor_norma": 5, "operador": "<=", "unidad": "mm", falta: None}
        v, registro = procesar_verificacion(_v(veredicto="Incumple", **datos), ORACIONES, ARTICULO)
        assert v.veredicto == "Incumple" and registro["estado"] == "ok"


def test_revisar_y_no_aplica_no_se_corrigen_por_numeros():
    for veredicto in ("Revisar", "No aplica"):
        v, _ = procesar_verificacion(_v(veredicto=veredicto, valor_oferta=4, valor_norma=5, operador="<=", unidad="mm"), ORACIONES, ARTICULO)
        assert v.veredicto == veredicto


# --- descripción armada por código ---

DOC = Document(page_content=ARTICULO, metadata={"norma": "NORM_01", "articulo": "1.1", "titulo": "Tolerancias"})
REDACCION = Redaccion(accion_mitigacion="<acción>", umbral_alerta="<umbral>", impacto_estimado="alto", probabilidad_estimada="media",
                      responsabilidad_mitigacion="<rol>", responsable_accidente="<rol>", comentario="<comentario>")
SUBSECCIONES = [("1 Alcance", "Otro texto."), ("2 Valores", "El valor ofertado es de 7 mm en la zona de trabajo. El par de apriete será de 120 N·m.")]


def test_descripcion_incumple():
    v = _v(veredicto="Incumple", requisitos=["El valor no excederá 5 mm."], dato_oferta="7 mm")
    assert armar_descripcion("El valor ofertado es de 7 mm.", "NORM_01", "1.1", v.requisitos, v) == (
        "La oferta indica «El valor ofertado es de 7 mm.». NORM_01 Art. 1.1 exige: El valor no excederá 5 mm. No coincide: 7 mm.")


def test_descripcion_revisar():
    v = _v(veredicto="Revisar", requisitos=["Requisito uno", "Requisito dos."], explicacion="Falta el dato de la zona.", motivo_duda="condicion_no_determinable")
    assert armar_descripcion("Cita.", "NORM_02", "3.4", v.requisitos, v) == (
        "La oferta indica «Cita.». NORM_02 Art. 3.4 exige: Requisito uno; Requisito dos. A revisar: Falta el dato de la zona.")


def test_riesgo_armado_por_codigo():
    v = _v(veredicto="Incumple", oraciones=["O1", "O2"], requisitos=["El valor no excederá 5 mm."], dato_oferta="7 mm", explicacion="Excede el máximo.")
    r = armar_riesgo(v, REDACCION, DOC, ORACIONES, SUBSECCIONES)
    assert r.cita_oferta == f"{ORACIONES[0][1]} {ORACIONES[1][1]}"   # exacta, sin recorte a 25 palabras
    assert [(f.norma, f.articulo) for f in r.fuentes] == [("NORM_01", "1.1")]
    assert r.seccion_oferta == "2 Valores" and r.veredicto == "Incumple" and r.marcas == []
    assert r.descripcion_riesgo.startswith("La oferta indica «El valor ofertado es de 7 mm") and r.descripcion_riesgo.endswith("No coincide: 7 mm.")
    assert r.impacto_estimado == "Alto" and r.probabilidad_estimada == "Media" and r.subsanacion == "Correccion"


def test_incumple_sin_dato_oferta_describe_con_los_valores():
    v, _ = procesar_verificacion(_v(veredicto="Incumple", valor_oferta=7, valor_norma=5, operador="<=", unidad="mm", requisitos=["Máximo 5 mm"]), ORACIONES, ARTICULO)
    assert armar_riesgo(v, REDACCION, DOC, ORACIONES, SUBSECCIONES).descripcion_riesgo.endswith("No coincide: 7 mm frente a <= 5 mm.")


# --- deduplicado ---

def _riesgo(oraciones, norma="NORM_01", articulo="1.1", veredicto="Incumple"):
    v = _v(veredicto=veredicto, oraciones=oraciones, requisitos=["req"], dato_oferta="dato", explicacion="exp")
    doc = Document(page_content="x", metadata={"norma": norma, "articulo": articulo})
    return armar_riesgo(v, REDACCION, doc, ORACIONES, SUBSECCIONES)


def test_deduplica_mismo_articulo_y_mismas_oraciones():
    assert len(_unir_y_deduplicar([_riesgo(["O1"]), _riesgo(["O1"])])) == 1


def test_no_deduplica_si_cambia_articulo_norma_u_oraciones():
    riesgos = [_riesgo(["O1"]), _riesgo(["O1"], articulo="1.2"), _riesgo(["O1"], norma="NORM_02"), _riesgo(["O2"])]
    assert len(_unir_y_deduplicar(riesgos)) == 4


# --- razonamiento (thinking) en verificación ---

def test_think_se_quita_antes_de_parsear():
    from scripts.main import _parsear_respuesta_llm
    raw = '<think>Pienso {en llaves} y dudo.</think>\n{"veredicto": "Cumple", "oraciones": ["O1"]}'
    assert _parsear_respuesta_llm(raw, None, VerificacionArticulo).veredicto == "Cumple"


def test_razonamiento_recortado_y_sin_thinking_no_cambia(monkeypatch):
    from types import SimpleNamespace
    from scripts import config
    from scripts.main import _razonamiento
    m = SimpleNamespace(content="<think>" + "x" * 3000 + "</think>{}", additional_kwargs={})
    assert len(_razonamiento(m)) == 1500
    m2 = SimpleNamespace(content="{}", additional_kwargs={"reasoning_content": "razón"})
    assert _razonamiento(m2) == "razón"


def test_llm_sin_thinking_es_el_actual(monkeypatch):
    from scripts import config, rag_components
    llm = rag_components.get_llm_instance(config.OLLAMA_MODEL)
    assert not llm.reasoning and llm.temperature == 0 and llm.top_p is None and llm.top_k is None
    llm = rag_components.get_llm_instance(config.OLLAMA_MODEL, razonamiento=True)
    assert llm.reasoning is True and llm.temperature == config.VERIF_TEMPERATURE and llm.top_k == config.VERIF_TOP_K
