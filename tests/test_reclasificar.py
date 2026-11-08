import copy
import json
import os

from scripts import clasificacion, comentario, reclasificar as rc
from scripts.schemas import ClasificacionRiesgo

with open(os.path.join(os.path.dirname(__file__), "fixtures", "criterios_empresa.json"), encoding="utf-8") as f:
    C = json.load(f)

TEXTOS = {"O1": "La oferta incluye 1 unidad de apoyo.", "O2": "El espesor ofertado es de 12 mm."}


def _c(**campos):
    base = dict(motivo="m", veredicto="DESVIO", objeto_requisito="CUANTITATIVO_TECNICO", dimension_impacto="Integridad", impacto=4,
                titulo="t", enunciado="e", accion="a", solicitud_oferente="s")
    return ClasificacionRiesgo(**{**base, **campos})


def _original(criterios):
    """Resultado como lo deja main: brechas, brecha descartada por cálculo, alertas y salidas del código."""
    brechas = []
    alertas = [{"seccion": "S1", "norma": "NORM_01", "articulo": "9.9", "oraciones": ["O1"], "cita": "x", "motivo": "tiempo", "estado": "tiempo_agotado"}]
    casos = [("O1", "NORM_01", "4.2", "Art. 4.2. Se exigen 2 unidades.", _c(valor_ofertado="1", valor_exigido="2", unidad="unidades", tipo_limite="CANTIDAD")),
             ("O2", "NORM_02", "5.1", "Art. 5.1. Se exigen 10 mm como mínimo.", _c(valor_ofertado="12 mm", valor_exigido="10 mm", tipo_limite="MINIMO")),
             ("O1", "NORM_03", "1.1", "Art. 1.1. Se debe informar.", _c(veredicto="ALERTA", motivo="revisar a mano"))]
    for oracion, norma, articulo, texto, c in casos:
        r = clasificacion.procesar_clasificacion(
            c, id_sec="S1", seccion_oferta="1.1 Apoyos", norma=norma, articulo=articulo, texto_articulo=texto, oraciones=[oracion], textos=TEXTOS,
            verificacion={"veredicto": "Incumple", "explicacion": "x", "discrepancia_numerica": None}, criterios=criterios)
        if r["tipo"] in ("brecha", "descartada_por_calculo"):
            r["brecha"]["eval_count"] = 7
            brechas.append(r["brecha"])
        if r["tipo"] in ("alerta", "descartada_por_calculo"):
            alertas.append(r["alerta"])
    riesgos, solicitudes, resumen = clasificacion.armar_salidas(brechas, criterios)
    resumen.update(comentario_general="comentario del modelo", origen_comentario="modelo")
    return {"registro_brechas": brechas, "riesgos": riesgos, "solicitudes": solicitudes, "alertas": alertas, "resumen_ejecutivo": resumen,
            "lineamientos": {"huella": "vieja"}, "registro_tecnico": [{"x": 1}], "secciones": [{"id": "S1"}]}


def test_el_original_tiene_la_brecha_nula_en_el_registro_y_como_alerta_pero_no_como_riesgo():
    d = _original(C)
    assert [b.get("estado") for b in d["registro_brechas"]] == [None, "descartada por cálculo"]
    assert len(d["riesgos"]) == 1 and len(d["solicitudes"]) == 1
    assert [a.get("origen") for a in d["alertas"]] == [None, "brecha_nula", None]


def test_regresion_con_el_motor_sin_cambios_reproduce_el_resultado_original():
    d = _original(C)
    nuevo, cambios = rc.reclasificar(d, C, "h" * 64, "original.json")
    for k in d:
        assert nuevo[k] == d[k], k
    assert cambios == [] and nuevo["reclasificacion"]["huella_criterios"] == "h" * 64 and nuevo["reclasificacion"]["huella_criterios_original"] == "vieja"


def test_con_criterios_distintos_cambian_las_clases_se_listan_y_el_comentario_pasa_a_plantilla():
    d = _original(C)
    copia = copy.deepcopy(d)
    otros = copy.deepcopy(C)
    otros["umbral_brecha_relativa"]["valor"] = 0.9      # la brecha 0,5 ya no llega al umbral: deja de ser 3.3.a
    nuevo, cambios = rc.reclasificar(d, otros, "otra", "original.json")
    assert d == copia                                    # no modifica la entrada
    assert [(c["id"], c["clase_antes"], c["regla_antes"], c["clase_despues"], c["regla_despues"]) for c in cambios] == [
        ("S1|NORM_01|4.2", "Mayor", "3.3.a", "Menor", "3.4.a")]
    assert nuevo["riesgos"][0]["clase"] == "Menor"
    resumen = nuevo["resumen_ejecutivo"]
    assert resumen["origen_comentario"] == "plantilla"
    assert resumen["comentario_general"] == comentario.plantilla({k: resumen[k] for k in ("decision", "por_nivel", "por_clase")}, nuevo["riesgos"])
    assert nuevo["registro_tecnico"] == d["registro_tecnico"] and nuevo["secciones"] == d["secciones"]


def test_reclasificar_dos_veces_es_estable():
    una, _ = rc.reclasificar(_original(C), C, "h")
    dos, cambios = rc.reclasificar(una, C, "h")
    assert dos["registro_brechas"] == una["registro_brechas"] and dos["alertas"] == una["alertas"] and cambios == []


def test_rutas_de_salida():
    j, h = rc.rutas_salida(os.path.join("carpeta", "analisis_riesgos_P1_oferta_TBP01_20261108_151743.json"))
    assert j == os.path.join("carpeta", "analisis_riesgos_P1_oferta_TBP01_20261108_151743_reclasificado.json")
    assert h == os.path.join("carpeta", "dashboard_P1_oferta_TBP01_20261108_151743_reclasificado.html")
