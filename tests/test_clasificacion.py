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
    base = dict(motivo="m", veredicto="DESVIO", objeto_requisito="CUANTITATIVO_TECNICO",
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


def test_brecha_nula_ya_no_se_clasifica_pasa_a_alerta():
    brechas, alertas, *_ = _correr([_clasif(tipo_limite="MAXIMO")])   # 1 <= 2: cumple el máximo, brecha 0, misma unidad
    assert brechas[0]["estado"] == "descartada por cálculo" and brechas[0].get("clase") is None and len(alertas) == 1


def test_dos_articulos_sobre_las_mismas_oraciones_se_agrupan_con_clase_maxima():
    docs = [_doc(), _doc("NORM_03", "2.1", "Art. 2.1. IZAJE\nTexto del articulo inventado.")]
    brechas, *_ = _correr([_clasif(), _clasif(objeto_requisito="OTRO_TECNICO", practica_peligrosa=True, medida_ofrecida="1 unidad de apoyo",
                                              valor_ofertado=None, valor_exigido=None, tipo_limite=None, unidad=None, impacto=5, titulo="Otro")], docs)
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
    c = ClasificacionRiesgo.model_validate({"motivo": "m", "veredicto": "desvio", "etapa_requisito": "posterior", "materia_3_2_a": "true",
                                            "objeto_requisito": "otro tecnico", "valor_ofertado": 1.5, "valor_exigido": "null",
                                            "valor_limite_excepcion": 2, "medida_ofrecida": "null", "dimension_impacto": "desempeno", "impacto": 3})
    assert (c.veredicto, c.etapa_requisito, c.materia_3_2_a, c.objeto_requisito, c.valor_ofertado, c.valor_exigido, c.valor_limite_excepcion,
            c.medida_ofrecida, c.dimension_impacto) == ("DESVIO", "POSTERIOR", True, "OTRO_TECNICO", "1.5", None, "2", None, "Desempeño o calidad")
    assert list(ClasificacionRiesgo.model_fields)[:2] == ["motivo", "veredicto"]   # el motivo va antes del veredicto
    assert "condicion_critico" not in ClasificacionRiesgo.model_fields   # la calcula el código


def test_el_esquema_tiene_los_hechos_entre_veredicto_y_objeto_requisito():
    campos = list(ClasificacionRiesgo.model_fields)
    assert campos[campos.index("veredicto") + 1:campos.index("objeto_requisito")] == [
        "item_contenido_minimo", "etapa_requisito", "materia_3_2_a", "medida_ofrecida", "practica_peligrosa",
        "valor_limite_excepcion", "valor_demanda_oferta"]


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
    ("Texto del prompt", "PROMPT_CLASIFICACION_STR", ["criterios", "items_contenido_minimo", "articulo", "seccion_numerada", "verificacion"]),
    ("Prompt del comentario general", "PROMPT_COMENTARIO_GENERAL_STR", ["decision", "conteo_nivel", "conteo_clase", "registro"]),
])
def test_los_prompts_son_identicos_a_los_del_documento(titulo, plantilla, variables):
    renderizado = PromptTemplate(template=getattr(rag_components, plantilla), input_variables=variables).format(
        **{v: "{" + v + "}" for v in variables})
    assert renderizado.strip() == _bloque_del_documento(titulo)


def test_el_prompt_no_contiene_ejemplos_de_las_ofertas():
    prohibidas = ["IP5", "H-2", "H-3", "kA", "escalera", "mm/m", "N·m"]
    assert [p for p in prohibidas if p in rag_components.PROMPT_CLASIFICACION_STR] == []


def test_el_prompt_no_trae_escritos_los_items_del_art_2_6():
    """Los ítems llegan por la variable {items_contenido_minimo}, desde el JSON de la empresa; no pueden estar en el texto del prompt."""
    t = rag_components.PROMPT_CLASIFICACION_STR
    assert [i["item"] for i in C["contenido_minimo_oferta"]["items"] if i["item"] in t] == []


def test_el_prompt_se_renderiza_con_sus_cuatro_variables():
    t = rag_components.PROMPT_CLASIFICACION_STR
    for v in ("{criterios}", "{items_contenido_minimo}", "{articulo}", "{seccion_numerada}", "{verificacion}"):
        assert v in t
    texto = rag_components.crear_cadena_clasificacion.__globals__["PromptTemplate"](
        template=t, input_variables=["criterios", "items_contenido_minimo", "articulo", "seccion_numerada", "verificacion"]).format(
        criterios="CRIT", items_contenido_minimo="ITEMS", articulo="ART", seccion_numerada="SEC", verificacion="VER")
    assert '{"motivo": "...", "veredicto": "...", "item_contenido_minimo": null, "etapa_requisito": null' in texto and "{{" not in texto
    assert "condicion_critico" not in texto
    assert texto.index("CRIT") < texto.index("=== ÍTEMS DEL ART. 2.6 ===\nITEMS") < texto.index("ART") < texto.index("SEC") < texto.index("VER")
    assert texto.index("=== CRITERIOS DE LA EMPRESA ===\nCRIT\n\n=== ÍTEMS DEL ART. 2.6 ===") >= 0


# --- B5: la condición del Art. 3.2 y el filtro de información faltante los decide el código ---

ITEM_CRITICO = next(i["item"] for i in C["contenido_minimo_oferta"]["items"] if i["materia_critica"])
ITEM_NO_CRITICO = next(i["item"] for i in C["contenido_minimo_oferta"]["items"] if not i["materia_critica"])
SECCION_B5 = {"id": "3", "titulos": ["3 Alcance"], "subsecciones": [("3.1 Apoyos", "x")],
              "texto": "La oferta propone 5 apoyos para una carga declarada de 8 apoyos y usa una cuña de madera para nivelar con hasta 3 mm."}


def _correr_b5(clasif, texto_articulo="Art. 4.2. APOYOS\nSe exigen 10 apoyos. Se admite apartarse hasta 4 mm."):
    cv, cc = Cadena(VERIF), Cadena(_clasif(**clasif))
    brechas, alertas, registro = _verificar_seccion(SECCION_B5, [_doc(texto=texto_articulo)], cv, cc, cc, cc, LIN, {}, {"verificacion": 0, "clasificacion": 0})
    return brechas, registro


# Cada fila: veredicto con los hechos del modelo -> (clase, regla, condición)
def test_regla_3_2_c_valor_fuera_del_limite_de_la_excepcion():
    texto = "Art. 4.2. APOYOS\nSe exigen 10 apoyos. Se admite hasta 6 apoyos."
    brechas, _ = _correr_b5(dict(valor_ofertado="5", valor_exigido="10", tipo_limite="MINIMO", valor_limite_excepcion="6"), texto)
    b = brechas[0]
    assert (b["clase"], b["regla"], b["condicion_critico"]) == ("Crítico", "3.2.c", "c") and any(x.startswith("3.2.c") for x in b["marcas"])


def test_regla_3_2_d_oferta_que_no_cubre_su_propia_demanda():
    brechas, _ = _correr_b5(dict(valor_ofertado="5", valor_exigido="10", tipo_limite="MINIMO", valor_demanda_oferta="8"))
    b = brechas[0]
    assert (b["clase"], b["regla"], b["condicion_critico"]) == ("Crítico", "3.2.d", "d") and any(x.startswith("3.2.d") for x in b["marcas"])


def test_regla_3_2_d_para_maximo_compara_al_reves():
    brechas, _ = _correr_b5(dict(valor_ofertado="8", valor_exigido="10", tipo_limite="MAXIMO", valor_demanda_oferta="5"))
    assert brechas[0]["regla"] == "3.2.d"
    brechas, _ = _correr_b5(dict(valor_ofertado="5", valor_exigido="10", tipo_limite="MAXIMO", valor_demanda_oferta="8"))
    assert brechas[0].get("condicion_critico") is None and brechas[0]["estado"] == "descartada por cálculo"   # cumple el máximo: brecha nula, sin 3.2.d


def test_regla_3_2_b_practica_peligrosa_con_medida_citada():
    brechas, _ = _correr_b5(dict(objeto_requisito="OTRO_TECNICO", practica_peligrosa=True, medida_ofrecida="usa una cuña de madera para nivelar",
                                 valor_ofertado=None, valor_exigido=None, tipo_limite=None))
    b = brechas[0]
    assert (b["clase"], b["regla"], b["condicion_critico"]) == ("Crítico", "3.2.b", "b") and any(x.startswith("3.2.b") for x in b["marcas"])


def test_regla_3_2_a_materia_sin_medida():
    brechas, _ = _correr_b5(dict(objeto_requisito="OTRO_TECNICO", materia_3_2_a=True, medida_ofrecida=None,
                                 valor_ofertado=None, valor_exigido=None, tipo_limite=None))
    b = brechas[0]
    assert (b["clase"], b["regla"], b["condicion_critico"]) == ("Crítico", "3.2.a", "a") and any(x.startswith("3.2.a") for x in b["marcas"])


def test_sin_hechos_que_cumplan_no_hay_condicion_y_siguen_las_reglas_de_clase():
    brechas, _ = _correr_b5(dict(valor_ofertado="5", valor_exigido="10", tipo_limite="MINIMO", materia_3_2_a=False, practica_peligrosa=False,
                                 medida_ofrecida="usa una cuña de madera para nivelar"))
    assert (brechas[0]["clase"], brechas[0]["regla"], brechas[0]["condicion_critico"]) == ("Mayor", "3.3.a", None)


def test_orden_c_antes_que_d_antes_que_b_antes_que_a():
    todo = dict(valor_ofertado="5", valor_exigido="10", tipo_limite="MINIMO", materia_3_2_a=True, practica_peligrosa=True,
                medida_ofrecida="usa una cuña de madera para nivelar")
    texto = "Art. 4.2. APOYOS\nSe exigen 10 apoyos. Se admite hasta 6 apoyos."
    assert _correr_b5({**todo, "valor_limite_excepcion": "6", "valor_demanda_oferta": "8"}, texto)[0][0]["condicion_critico"] == "c"
    assert _correr_b5({**todo, "valor_demanda_oferta": "8"})[0][0]["condicion_critico"] == "d"
    assert _correr_b5(todo)[0][0]["condicion_critico"] == "b"
    assert _correr_b5({**todo, "practica_peligrosa": False, "medida_ofrecida": None})[0][0]["condicion_critico"] == "a"


# Casos negativos: lo que el modelo declara y no está en el texto se ignora y se marca

def test_practica_peligrosa_sin_cita_no_es_3_2_b():
    brechas, _ = _correr_b5(dict(objeto_requisito="OTRO_TECNICO", practica_peligrosa=True, medida_ofrecida="Se usa un andamio de acero",
                                 valor_ofertado=None, valor_exigido=None, tipo_limite=None))
    b = brechas[0]
    assert b["condicion_critico"] is None and (b["clase"], b["regla"]) == ("Mayor", "3.3.c")
    assert f"{clasificacion.MARCA_VALOR_NO_VERIFICADO}: medida_ofrecida" in b["marcas"]


def test_medida_declarada_pero_no_verificada_no_habilita_3_2_a():
    brechas, _ = _correr_b5(dict(objeto_requisito="OTRO_TECNICO", materia_3_2_a=True, medida_ofrecida="Se usa un andamio de acero",
                                 valor_ofertado=None, valor_exigido=None, tipo_limite=None))
    assert brechas[0]["condicion_critico"] is None


def test_limite_de_excepcion_que_no_esta_en_el_articulo_se_ignora():
    brechas, _ = _correr_b5(dict(valor_ofertado="5", valor_exigido="10", tipo_limite="MINIMO", valor_limite_excepcion="7"))
    b = brechas[0]
    assert b["condicion_critico"] is None and f"{clasificacion.MARCA_VALOR_NO_VERIFICADO}: valor_limite_excepcion" in b["marcas"]


def test_demanda_que_no_esta_en_la_oferta_se_ignora():
    brechas, _ = _correr_b5(dict(valor_ofertado="5", valor_exigido="10", tipo_limite="MINIMO", valor_demanda_oferta="9"))
    b = brechas[0]
    assert b["condicion_critico"] is None and f"{clasificacion.MARCA_VALOR_NO_VERIFICADO}: valor_demanda_oferta" in b["marcas"]


def test_valor_ofertado_dentro_del_limite_o_que_cubre_la_demanda_no_es_condicion():
    texto = "Art. 4.2. APOYOS\nSe exigen 10 apoyos. Se admite hasta 4 apoyos."
    assert _correr_b5(dict(valor_ofertado="5", valor_exigido="10", tipo_limite="MINIMO", valor_limite_excepcion="4"), texto)[0][0]["condicion_critico"] is None
    assert _correr_b5(dict(valor_ofertado="5", valor_exigido="10", tipo_limite="MINIMO", valor_demanda_oferta="3"))[0][0]["condicion_critico"] is None


# Información faltante

def _faltante(**campos):
    return dict(veredicto="INFORMACION_FALTANTE", objeto_requisito="OTRO_TECNICO", valor_ofertado=None, valor_exigido=None, tipo_limite=None,
                unidad=None, etapa_requisito="OFERTA", **campos)


def test_informacion_faltante_de_item_critico_es_mayor_y_de_otro_menor():
    b, _ = _correr_b5(_faltante(item_contenido_minimo=ITEM_CRITICO))
    assert (b[0]["clase"], b[0]["regla"], b[0]["condicion_critico"]) == ("Mayor", "3.6.4", "a") and any(x.startswith("3.6.4") for x in b[0]["marcas"])
    b, _ = _correr_b5(_faltante(item_contenido_minimo=ITEM_NO_CRITICO))
    assert (b[0]["clase"], b[0]["regla"], b[0]["condicion_critico"]) == ("Menor", "3.6.4", None)


def test_informacion_faltante_acepta_el_item_normalizado_y_con_su_disciplina():
    item = next(i for i in C["contenido_minimo_oferta"]["items"] if i["materia_critica"])
    for texto in (item["item"].upper(), f"{item['disciplina']}: {item['item']}", f"  {item['item']}. "):
        assert _correr_b5(_faltante(item_contenido_minimo=texto))[0][0]["clase"] == "Mayor"


@pytest.mark.parametrize("item", ["NINGUNO", None, "un dato que no está en la lista"])
def test_informacion_faltante_sin_item_del_art_2_6_pasa_a_no_aplica_regla_2_5(item):
    brechas, registro = _correr_b5(_faltante(item_contenido_minimo=item))
    assert brechas == [] and registro[-1]["estado"] == "no_es_riesgo" and registro[-1]["regla"] == "2.5"


def test_informacion_faltante_de_etapa_posterior_pasa_a_no_aplica_regla_2_7_c():
    brechas, registro = _correr_b5({**_faltante(item_contenido_minimo=ITEM_CRITICO), "etapa_requisito": "POSTERIOR"})
    assert brechas == [] and registro[-1]["estado"] == "no_es_riesgo" and registro[-1]["regla"] == "2.7.c"


def test_el_modelo_ya_no_decide_la_clase_de_la_informacion_faltante():
    # aunque declare materia_3_2_a, la clase sale del ítem del Art. 2.6
    b, _ = _correr_b5(_faltante(item_contenido_minimo=ITEM_NO_CRITICO, materia_3_2_a=True))
    assert b[0]["clase"] == "Menor"


def test_motor_comparaciones_y_texto_de_items():
    assert m.fuera_de_limite("5", "6", "MINIMO") and not m.fuera_de_limite("6", "6", "MINIMO")
    assert m.fuera_de_limite("7", "6", "MAXIMO") and m.fuera_de_limite("-3,5", "3", "TOLERANCIA") and not m.fuera_de_limite("2", "3", "TOLERANCIA")
    assert not m.fuera_de_limite("x", "6", "MINIMO") and not m.fuera_de_limite("5", "6", None)
    assert m.no_cubre_demanda("5", "8", "CANTIDAD") and m.no_cubre_demanda("5", "8", "TOLERANCIA") and not m.no_cubre_demanda("8", "8", "MINIMO")
    assert m.no_cubre_demanda("9", "8", "MAXIMO") and not m.no_cubre_demanda("5", "8", "FRECUENCIA") and not m.no_cubre_demanda("a", "8", "MINIMO")
    lineas = m.items_contenido_minimo_texto(C).split("\n")
    assert len(lineas) == len(C["contenido_minimo_oferta"]["items"]) and all(l.startswith("- ") and ": " in l for l in lineas)


# --- Brecha nula (cifras que cumplen) y 3.2.c con límite igual al exigido ---

def _correr_con_alertas(clasif, texto_articulo):
    cv, cc = Cadena(VERIF), Cadena(_clasif(**clasif))
    return _verificar_seccion(SECCION_B5, [_doc(texto=texto_articulo)], cv, cc, cc, cc, LIN, {}, {"verificacion": 0, "clasificacion": 0})[:2]


def test_brecha_nula_con_misma_unidad_no_genera_riesgo_y_pasa_a_alerta():
    texto = "Art. 4.2. APOYOS\nSe exigen como mínimo 3 apoyos."
    brechas, alertas = _correr_con_alertas(dict(valor_ofertado="5 apoyos", valor_exigido="3 apoyos", tipo_limite="MINIMO"), texto)
    assert len(brechas) == 1 and brechas[0]["estado"] == "descartada por cálculo" and brechas[0]["brecha_relativa"] == 0.0 and brechas[0].get("clase") is None
    assert len(alertas) == 1 and alertas[0]["motivo"] == "contradicción entre el veredicto del modelo y las cifras extraídas: revisar"
    assert (alertas[0]["norma"], alertas[0]["articulo"]) == ("NORM_01", "4.2") and alertas[0]["cita"] and alertas[0]["oraciones"] == ["O1"]
    assert clasificacion.armar_salidas(brechas, C)[0] == []     # no entra al agrupamiento ni a las solicitudes


def test_brecha_nula_con_unidades_distintas_sigue_el_camino_de_siempre():
    texto = "Art. 4.2. APOYOS\nSe exigen como mínimo 3 mm."
    brechas, alertas = _correr_con_alertas(dict(valor_ofertado="5 apoyos", valor_exigido="3 mm", tipo_limite="MINIMO"), texto)
    b = brechas[0]
    assert alertas == [] and "estado" not in b and (b["clase"], b["regla"]) == ("Menor", "3.4.a") and m.MARCA_BRECHA_NULA in b["marcas"]


def test_brecha_nula_no_oculta_una_condicion_critica():
    brechas, alertas = _correr_con_alertas(dict(valor_ofertado="5", valor_exigido="3", tipo_limite="MINIMO", valor_demanda_oferta="8"),
                                           "Art. 4.2. APOYOS\nSe exigen como mínimo 3 apoyos.")
    assert alertas == [] and brechas[0]["regla"] == "3.2.d"


def test_3_2_c_se_ignora_si_el_limite_de_excepcion_es_igual_al_exigido():
    texto = "Art. 4.2. APOYOS\nSe exigen 10 apoyos."
    b = _correr_b5(dict(valor_ofertado="5", valor_exigido="10", tipo_limite="MINIMO", valor_limite_excepcion="10"), texto)[0][0]
    assert b["condicion_critico"] is None and (b["clase"], b["regla"]) == ("Mayor", "3.3.a")
    assert m.limite_excepcion_propio("6", "10") and m.limite_excepcion_propio("6", None) and not m.limite_excepcion_propio("10 apoyos", "10")
    assert not m.limite_excepcion_propio("hasta algo", "10")
