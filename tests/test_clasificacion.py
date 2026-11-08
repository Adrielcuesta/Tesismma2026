import json
import os
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

from scripts import clasificacion, motor_riesgos as m, rag_components
from scripts.main import _verificar_seccion
from scripts.schemas import ClasificacionRiesgo

with open(os.path.join(os.path.dirname(__file__), "fixtures", "criterios_empresa.json"), encoding="utf-8") as f:
    C = json.load(f)
LIN = {"criterios": C, "texto_para_el_modelo": "<criterios inventados>", "huella": "h" * 64}

SECCION = {"id": "3", "texto": "La oferta incluye 1 unidad de apoyo.", "titulos": ["3 Alcance"],
           "subsecciones": [("3.1 Apoyos", "La oferta incluye 1 unidad de apoyo.")]}


def _doc(norma="NORM_01", articulo="4.2", texto="Art. 4.2. APOYOS\nSe exigen como mínimo 2 unidades de apoyo."):
    return Document(page_content=texto, metadata={"norma": norma, "articulo": articulo, "titulo": "Apoyos", "parte": 1})


def _msg(**campos):
    return SimpleNamespace(content=json.dumps(campos))


VERIF = _msg(oraciones=["O1"], explicacion="no coincide", veredicto="Incumple")


class Cadena:
    """Cadena falsa: devuelve en orden los mensajes dados (el último se repite)."""
    def __init__(self, *mensajes):
        self.mensajes, self.entradas = list(mensajes), []

    def invoke(self, entrada):
        self.entradas.append(entrada)
        return self.mensajes.pop(0) if len(self.mensajes) > 1 else self.mensajes[0]


def _clasif(**campos):
    base = dict(motivo="m", veredicto="DESVIO", condicion_critico=None, objeto_requisito="CUANTITATIVO_TECNICO",
                valor_ofertado="1", valor_exigido="2", unidad="unidades", tipo_limite="CANTIDAD",
                dimension_impacto="Integridad", impacto=4, titulo="Apoyos insuficientes", enunciado="e", accion="a",
                solicitud_oferente="s")
    base.update(campos)
    return _msg(**base)


def _correr(clasifs, docs=None, verif=VERIF):
    docs = docs or [_doc()]
    cv, cc = Cadena(verif), Cadena(*clasifs)
    llamadas = {"verificacion": 0, "clasificacion": 0}
    r = _verificar_seccion(SECCION, docs, cv, cc, cc, cc, LIN, {}, llamadas)
    return (*r, cc, llamadas)


# --- Casos con LLM falso ---

@pytest.mark.parametrize("impacto,nivel", [(4, "Alto"), (3, "Medio")])
def test_desvio_cuantitativo_1_vs_2_es_mayor(impacto, nivel):
    brechas, alertas, registro, cc, llamadas = _correr([_clasif(impacto=impacto)])
    b = brechas[0]
    assert (b["clase"], b["regla"], b["nivel"], b["brecha_relativa"]) == ("Mayor", "3.3.a", nivel, 0.5)
    assert b["probabilidad"] == 4 and b["estrategia"] == m.estrategia(nivel, C)
    assert b["responsable"] == "Gerencia de Infraestructura y Vías" and b["rbs"].startswith("RBS-1")
    assert b["umbral"] == "NORM_01, Art. 4.2" and b["oraciones"] == ["O1"] and b["cita"] == "La oferta incluye 1 unidad de apoyo."
    assert (b["tipo_solicitud"], b["plazo"]) == m.solicitud("DESVIO", "Mayor", C)
    assert llamadas == {"verificacion": 1, "clasificacion": 1}
    assert cc.entradas[0]["criterios"] == LIN["texto_para_el_modelo"]


def test_no_aplica_y_cumple_no_generan_riesgo():
    for veredicto in ("NO_APLICA", "CUMPLE"):
        brechas, alertas, registro, *_ = _correr([_msg(motivo="la oferta no menciona el tema", veredicto=veredicto)])
        assert brechas == [] and alertas == []
        assert registro[-1]["estado"] == "no_es_riesgo" and registro[-1]["motivo"] == "la oferta no menciona el tema"


def test_valor_ofertado_ausente_en_la_cita_se_marca_y_cae_a_3_3_c():
    brechas, *_ = _correr([_clasif(valor_ofertado="7")])
    b = brechas[0]
    assert clasificacion.MARCA_VALOR_NO_VERIFICADO in b["marcas"]
    assert (b["clase"], b["regla"], b["brecha_relativa"]) == ("Mayor", "3.3.c", None)


def test_valor_exigido_ausente_en_el_articulo_se_marca():
    brechas, *_ = _correr([_clasif(valor_exigido="9")])
    assert clasificacion.MARCA_VALOR_NO_VERIFICADO in brechas[0]["marcas"] and brechas[0]["regla"] == "3.3.c"


def test_alerta_va_a_alertas():
    brechas, alertas, registro, *_ = _correr([_msg(motivo="duda interna", veredicto="ALERTA")])
    assert brechas == [] and len(alertas) == 1
    assert alertas[0]["motivo"] == "duda interna" and alertas[0]["norma"] == "NORM_01" and alertas[0]["articulo"] == "4.2"
    assert alertas[0]["oraciones"] == ["O1"] and alertas[0]["cita"].startswith("La oferta incluye")


@pytest.mark.parametrize("faltante", ["objeto_requisito", "dimension_impacto", "impacto", "titulo"])
def test_clasificacion_incompleta_se_descarta(faltante):
    brechas, alertas, registro, *_ = _correr([_clasif(**{faltante: None})])
    assert brechas == [] and registro[-1]["estado"] == "descartada" and "clasificación incompleta" in registro[-1]["motivo"]


def test_json_invalido_se_reintenta_una_vez_y_luego_se_descarta():
    brechas, alertas, registro, cc, llamadas = _correr([SimpleNamespace(content="no es json")])
    assert brechas == [] and registro[-1]["estado"] == "clasificacion_fallida"
    assert llamadas["clasificacion"] == 1 and len(cc.entradas) == 2   # 1 llamada + 1 reintento (el reintento usa llm.invoke)


def test_json_invalido_y_reintento_valido():
    class Llm:
        def invoke(self, prompt):
            return _clasif()
    cv, cc = Cadena(VERIF), Cadena(SimpleNamespace(content="{"))
    brechas, *_ = _verificar_seccion(SECCION, [_doc()], cv, cc, cc, Llm(), LIN, {}, {"verificacion": 0, "clasificacion": 0})
    assert len(brechas) == 1


def test_longitudes_solo_agregan_marca():
    brechas, *_ = _correr([_clasif(titulo=" ".join(["palabra"] * 13), accion=" ".join(["a"] * 31))])
    assert {"longitud excedida: titulo", "longitud excedida: accion"} <= set(brechas[0]["marcas"])


def test_brecha_nula_se_marca_y_se_clasifica_igual():
    brechas, *_ = _correr([_clasif(tipo_limite="MAXIMO")])   # 1 <= 2: cumple el máximo, brecha 0
    assert m.MARCA_BRECHA_NULA in brechas[0]["marcas"] and brechas[0]["clase"] == "Menor"


def test_dos_articulos_sobre_las_mismas_oraciones_se_agrupan_con_clase_maxima():
    docs = [_doc(), _doc("NORM_03", "2.1", "Art. 2.1. IZAJE\nTexto del articulo inventado.")]
    brechas, *_ = _correr([_clasif(), _clasif(objeto_requisito="OTRO_TECNICO", condicion_critico="b", valor_ofertado=None,
                                              valor_exigido=None, tipo_limite=None, unidad=None, impacto=5, titulo="Otro")], docs)
    assert [b["clase"] for b in brechas] == ["Mayor", "Crítico"]
    riesgos = m.agrupar(brechas, C)
    assert len(riesgos) == 1
    r = riesgos[0]
    assert r["clase"] == "Crítico" and r["nivel"] == "Alto" and len(r["brechas"]) == 2
    assert r["umbral"] == "NORM_01, Art. 4.2; NORM_03, Art. 2.1"
    assert r["responsable"] == m.responsable("NORM_03", "2.1", C)
    assert len(brechas) == 2   # el registro sin agrupar queda completo


def test_impacto_se_acota_a_la_clase():
    brechas, *_ = _correr([_clasif(objeto_requisito="DOCUMENTAL_PROCEDIMIENTO", impacto=5)])   # Menor: impacto máx. 2
    b = brechas[0]
    assert b["clase"] == "Menor" and b["impacto"] == 2 and any(x.startswith("impacto ajustado") for x in b["marcas"])


# --- Solicitudes y resumen ejecutivo ---

def test_solicitudes_y_resumen_ejecutivo():
    c = json.loads(json.dumps(C))
    brechas, *_ = _correr([_clasif(solicitud_oferente="pedido A"), _clasif(solicitud_oferente="pedido B")],
                          [_doc(), _doc("NORM_05", "1.6", "Art. 1.6. X\nSe exigen 2 unidades.")])
    riesgos = m.agrupar(brechas, c)
    for i, r in enumerate(riesgos, 1):
        r["id"] = f"R{i}"
    sol = m.solicitudes(riesgos, brechas, c)
    assert len(sol) == 1 and sol[0]["tipo"] == "Solicitud de modificación de la oferta"
    assert sol[0]["pedido"].split("\n") == ["NORM_01 Art. 4.2: pedido A", "NORM_05 Art. 1.6: pedido B"]   # una línea por brecha
    res = m.resumen_ejecutivo(riesgos, c)
    assert res["decision"] == "Aceptable con condiciones" and res["por_clase"]["Mayor"] == 1 and "top5" not in res


# --- Valores y esquema ---

def test_valor_en_texto():
    assert clasificacion.valor_en_texto("1,5", "tolerancia de 1,5 mm")
    assert clasificacion.valor_en_texto("1.676", "mide 1.676 mm")
    assert not clasificacion.valor_en_texto("5", "mide 0,5 mm") and not clasificacion.valor_en_texto("2", "mide 25 mm")
    assert clasificacion.valor_en_texto("14", "a los 14 días.")


def test_esquema_normaliza_la_salida_del_modelo():
    c = ClasificacionRiesgo.model_validate({"motivo": "m", "veredicto": "desvio", "condicion_critico": "B", "objeto_requisito": "otro tecnico",
                                            "valor_ofertado": 1.5, "valor_exigido": "null", "dimension_impacto": "desempeno", "impacto": 3})
    assert (c.veredicto, c.condicion_critico, c.objeto_requisito, c.valor_ofertado, c.valor_exigido, c.dimension_impacto) == \
        ("DESVIO", "b", "OTRO_TECNICO", "1.5", None, "Desempeño o calidad")
    assert list(ClasificacionRiesgo.model_fields)[:2] == ["motivo", "veredicto"]   # el motivo va antes del veredicto


def test_solicitud_agrupada_toma_tipo_y_plazo_del_componente_de_mayor_clase():
    brechas, *_ = _correr([_clasif(objeto_requisito="DOCUMENTAL_PROCEDIMIENTO", impacto=2, solicitud_oferente="menor"),
                           _clasif(objeto_requisito="OTRO_TECNICO", impacto=4, solicitud_oferente="mayor")],
                          [_doc(), _doc("NORM_05", "1.6", "Art. 1.6. X\nTexto inventado.")])
    assert [b["clase"] for b in brechas] == ["Menor", "Mayor"]
    riesgos = m.agrupar(brechas, C)
    riesgos[0]["id"] = "R1"
    sol = m.solicitudes(riesgos, brechas, C)[0]
    assert (sol["tipo"], sol["plazo"]) == m.solicitud("DESVIO", "Mayor", C) and sol["clase"] == "Mayor"


# --- Dimensiones del Art. 4.3 ---

@pytest.mark.parametrize("texto,completo", [
    ("Integridad", "Integridad del equipo u obra civil"), ("integridad del equipo", "Integridad del equipo u obra civil"),
    ("INTEGRIDAD DEL EQUIPO U OBRA CIVIL", "Integridad del equipo u obra civil"), ("Costo", "Costo (sobre monto del contrato)"),
    ("Seguridad de personas", "Seguridad de personas"), ("seguridad", "Seguridad de personas"), ("Plazo", "Plazo"),
    ("Desempeño", "Desempeño o calidad"), ("desempeno o calidad", "Desempeño o calidad"), ("Cumplimiento", "Cumplimiento legal"),
])
def test_dimension_tolerante_guarda_el_nombre_completo(texto, completo):
    assert ClasificacionRiesgo.model_validate({"motivo": "m", "veredicto": "DESVIO", "dimension_impacto": texto}).dimension_impacto == completo


@pytest.mark.parametrize("texto", ["Calidad total", "Medio ambiente", "Otra"])
def test_dimension_desconocida_se_rechaza(texto):
    with pytest.raises(Exception):
        ClasificacionRiesgo.model_validate({"motivo": "m", "veredicto": "DESVIO", "dimension_impacto": texto})


def test_riesgo_personas_es_la_dimension_seguridad_de_personas():
    doc = _doc(texto="Art. 4.2. APOYOS\nSe exigen como mínimo 1,2 unidades de apoyo.")
    campos = dict(valor_ofertado="1", valor_exigido="1,2", tipo_limite="MINIMO")   # brecha 0,17 < umbral
    brechas, *_ = _correr([_clasif(**campos, dimension_impacto="seguridad")], [doc])
    assert (brechas[0]["clase"], brechas[0]["regla"], brechas[0]["dimension_impacto"]) == ("Mayor", "3.3.e", "Seguridad de personas")
    brechas, *_ = _correr([_clasif(**campos, dimension_impacto="Integridad")], [doc])
    assert (brechas[0]["clase"], brechas[0]["regla"]) == ("Menor", "3.4.a")


# --- Prompt ---

def _bloque_del_documento(titulo):
    """Texto entre las tres comillas invertidas que siguen a `titulo` en docs/prompts/prompt_B4_clasificacion_NORM07.md."""
    ruta = os.path.join(os.path.dirname(__file__), os.pardir, "docs", "prompts", "prompt_B4_clasificacion_NORM07.md")
    with open(ruta, encoding="utf-8") as f:
        lineas = f.read().split("\n")
    inicio = next(i for i, l in enumerate(lineas) if titulo in l)
    abre = next(i for i in range(inicio, len(lineas)) if lineas[i].strip() == "```")
    cierra = next(i for i in range(abre + 1, len(lineas)) if lineas[i].strip() == "```")
    return "\n".join(lineas[abre + 1:cierra]).strip()


@pytest.mark.parametrize("titulo,plantilla,variables", [
    ("Texto del prompt", "PROMPT_CLASIFICACION_STR", ["criterios", "articulo", "seccion_numerada", "verificacion"]),
    ("Prompt del comentario general", "PROMPT_COMENTARIO_GENERAL_STR", ["decision", "conteo_nivel", "conteo_clase", "registro"]),
])
def test_los_prompts_son_identicos_a_los_del_documento(titulo, plantilla, variables):
    renderizado = PromptTemplate(template=getattr(rag_components, plantilla), input_variables=variables).format(
        **{v: "{" + v + "}" for v in variables})
    assert renderizado.strip() == _bloque_del_documento(titulo)


def test_el_prompt_no_contiene_ejemplos_de_las_ofertas():
    prohibidas = ["IP5", "H-2", "H-3", "kA", "escalera", "mm/m", "N·m"]
    assert [p for p in prohibidas if p in rag_components.PROMPT_CLASIFICACION_STR] == []


def test_el_prompt_se_renderiza_con_sus_cuatro_variables():
    t = rag_components.PROMPT_CLASIFICACION_STR
    for v in ("{criterios}", "{articulo}", "{seccion_numerada}", "{verificacion}"):
        assert v in t
    texto = rag_components.crear_cadena_clasificacion.__globals__["PromptTemplate"](
        template=t, input_variables=["criterios", "articulo", "seccion_numerada", "verificacion"]).format(
        criterios="CRIT", articulo="ART", seccion_numerada="SEC", verificacion="VER")
    assert '{"motivo": "...", "veredicto": "...", "condicion_critico": null' in texto and "{{" not in texto
    assert texto.index("CRIT") < texto.index("ART") < texto.index("SEC") < texto.index("VER")
