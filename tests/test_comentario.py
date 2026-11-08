import json
import os
from types import SimpleNamespace

import pytest

from scripts import comentario, rag_components

with open(os.path.join(os.path.dirname(__file__), "fixtures", "resultado_ejemplo.json"), encoding="utf-8") as f:
    DATOS = json.load(f)
RIESGOS = DATOS["riesgos"]
RESUMEN = {k: DATOS["resumen_ejecutivo"][k] for k in ("decision", "por_nivel", "por_clase")}

VALIDO = ("La oferta resulta No aceptable, principalmente por el izaje crítico sin plan aprobado (NORM_03 Art. 2.1). "
          "Los riesgos de clase Crítico y Mayor se concentran en la Gerencia de Seguridad Operacional y Salud Ocupacional. "
          "Antes de la adjudicación el oferente debe presentar el plan de izaje aprobado.")


class Cadena:
    def __init__(self, texto=None, error=None):
        self.texto, self.error, self.entradas = texto, error, []

    def invoke(self, entrada):
        self.entradas.append(entrada)
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.texto)


def test_comentario_valido_se_acepta():
    cadena = Cadena(VALIDO)
    r = comentario.generar_comentario(RESUMEN, RIESGOS, cadena)
    assert (r["origen"], r["texto"], r["llamo"]) == ("modelo", VALIDO, True)
    # el modelo recibe solo la decisión, los conteos y el registro
    entrada = cadena.entradas[0]
    assert set(entrada) == {"decision", "conteo_nivel", "conteo_clase", "registro"} and entrada["decision"] == "No aceptable"
    assert entrada["conteo_nivel"] == "Alto: 2; Medio: 2; Bajo: 3"
    assert "Izaje crítico sin plan aprobado | Crítico | Alto | Gerencia de Seguridad Operacional y Salud Ocupacional | NORM_03 Art. 2.1; NORM_03 Art. 2.4" in entrada["registro"]


def test_el_bloque_think_se_ignora():
    r = comentario.generar_comentario(RESUMEN, RIESGOS, Cadena("<think>NORM_09 Art. 9.9</think>" + VALIDO))
    assert r["origen"] == "modelo" and r["texto"] == VALIDO


@pytest.mark.parametrize("texto,motivo", [
    (VALIDO.replace("Art. 2.1", "Art. 7.7"), "Art. 7.7"),                       # artículo que no está en el registro
    (VALIDO.replace("NORM_03", "NORM_09"), "NORM_09"),                          # norma que no está en el registro
    ("Una sola oración sin más.", "1 oraciones"),
    ("Primera. Segunda. Tercera. Cuarta. Quinta. Sexta.", "6 oraciones"),
])
def test_comentario_invalido_usa_la_plantilla(texto, motivo):
    r = comentario.generar_comentario(RESUMEN, RIESGOS, Cadena(texto))
    assert r["origen"] == "plantilla" and r["texto"] == comentario.plantilla(RESUMEN, RIESGOS) and motivo in r["motivo"] and r["llamo"] is True


def test_registro_vacio_usa_la_plantilla_sin_llamar_al_modelo():
    cadena = Cadena(VALIDO)
    r = comentario.generar_comentario({"decision": "Aceptable", "por_nivel": {}, "por_clase": {}}, [], cadena)
    assert r["origen"] == "plantilla" and r["llamo"] is False and cadena.entradas == []
    assert r["texto"] == "Decisión de aceptabilidad: Aceptable. No se identificaron riesgos."


def test_falla_del_modelo_usa_la_plantilla():
    r = comentario.generar_comentario(RESUMEN, RIESGOS, Cadena(error=RuntimeError("sin conexión")))
    assert r["origen"] == "plantilla" and "sin conexión" in r["motivo"]


def test_plantilla_con_decision_conteos_y_areas_de_clase_alta():
    t = comentario.plantilla(RESUMEN, RIESGOS)
    assert "No aceptable" in t and "Alto: 2; Medio: 2; Bajo: 3" in t and "Crítico: 1; Mayor: 3; Menor: 3" in t
    areas = t.split("se concentran en: ")[1]
    assert "Gerencia de Seguridad Operacional y Salud Ocupacional" in areas and "Gerencia de Infraestructura y Vías" in areas
    assert "Material Rodante" not in areas      # esa área solo tiene riesgos Menor


def test_la_plantilla_es_valida_para_el_validador():
    assert comentario.validar_comentario(comentario.plantilla(RESUMEN, RIESGOS), RIESGOS) == (True, "")


def test_la_cadena_se_arma_con_las_cuatro_variables():
    assert rag_components.PROMPT_COMENTARIO_GENERAL_STR.count("{") == 4
