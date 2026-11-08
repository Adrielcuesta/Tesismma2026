import copy
import csv
import json
import os

import pytest

from scripts import motor_riesgos as m

AQUI = os.path.dirname(__file__)
with open(os.path.join(AQUI, "fixtures", "criterios_empresa.json"), encoding="utf-8") as f:
    C = json.load(f)
RAIZ = os.path.dirname(AQUI)


# --- Matriz, consistencia, acotado ---

MATRIZ = {  # probabilidad -> niveles para impacto 1..5 (Art. 5.1)
    5: ["Bajo", "Medio", "Medio", "Alto", "Alto"],
    4: ["Bajo", "Bajo", "Medio", "Alto", "Alto"],
    3: ["Bajo", "Bajo", "Medio", "Alto", "Alto"],
    2: ["Bajo", "Bajo", "Bajo", "Medio", "Alto"],
    1: ["Bajo", "Bajo", "Bajo", "Medio", "Medio"],
}


@pytest.mark.parametrize("prob", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("impacto", [1, 2, 3, 4, 5])
def test_las_25_celdas_de_la_matriz(prob, impacto):
    assert m.nivel(prob, impacto, C) == MATRIZ[prob][impacto - 1]


def test_probabilidad_y_estrategia():
    assert [m.probabilidad(f, C) for f in m.FUENTES] == [4, 3, 2]
    assert [m.estrategia(n, C) for n in ("Alto", "Medio", "Bajo")] == ["Evitar", "Mitigar", "Aceptar"]


def test_consistencia():
    assert m.aplicar_consistencia("Crítico", "Bajo", C) == "Alto"
    assert m.aplicar_consistencia("Crítico", "Medio", C) == "Alto"
    assert m.aplicar_consistencia("Menor", "Alto", C) == "Bajo"
    assert m.aplicar_consistencia("Menor", "Medio", C) == "Bajo"
    assert m.aplicar_consistencia("Mayor", "Bajo", C) == "Bajo" and m.aplicar_consistencia("Mayor", "Alto", C) == "Alto"


def test_acotar_impacto():
    assert m.acotar_impacto("Menor", 4, C) == (2, True)
    assert m.acotar_impacto("Crítico", 2, C) == (4, True)
    assert m.acotar_impacto("Mayor", 3, C) == (3, False)
    assert m.acotar_impacto("Mayor", 5, C) == (4, True)


# --- Brecha ---

def test_brecha_relativa():
    assert m.brecha_relativa("1", "2", "CANTIDAD") == 0.5
    assert m.brecha_relativa("±3", "±1,5", "TOLERANCIA") == 1.0
    assert m.brecha_relativa("2700", "2274", "MAXIMO") == pytest.approx(0.187, abs=0.001)
    assert m.brecha_relativa("0,52", "0,48", "MAXIMO") == pytest.approx(0.083, abs=0.001)
    assert m.brecha_relativa("14 días", "28 días", "MINIMO") == 0.5
    assert m.brecha_relativa("60", "50", "FRECUENCIA") == pytest.approx(0.2)


def test_brecha_solo_cuenta_si_incumple():
    assert m.brecha_relativa("30", "20", "MINIMO") == 0.0
    assert m.brecha_relativa("10", "20", "MAXIMO") == 0.0
    assert m.brecha_relativa("±1", "±1,5", "TOLERANCIA") == 0.0     # más estricta que el requisito: nunca negativa


def test_brecha_parsea_numeros():
    assert m._numero("1.676") == 1676
    assert m._numero("0,05") == 0.05
    assert m._numero("0.05") == 0.05
    assert m._numero("1.234,5 mm") == 1234.5
    assert m._numero("sin dato") is None
    assert m.brecha_relativa("1.676", "2.000", "MINIMO") == pytest.approx((2000 - 1676) / 2000)


def test_brecha_no_calculable():
    assert m.brecha_relativa("a definir", "2", "MINIMO") is None
    assert m.brecha_relativa("1", "0", "MINIMO") is None
    assert m.brecha_relativa("1", "2", None) is None


# --- Clase: un caso por regla ---

CASOS_CLASE = [
    ("DESVIO", "a", "CUANTITATIVO_TECNICO", 0.1, False, ("Crítico", "3.2.a")),
    ("DESVIO", "d", "DOCUMENTAL_PROCEDIMIENTO", None, False, ("Crítico", "3.2.d")),
    ("DESVIO", None, "DOCUMENTAL_PROCEDIMIENTO", None, False, ("Menor", "3.4.c")),
    ("DESVIO", None, "RESERVA_ERGONOMIA_EFICIENCIA", None, False, ("Menor", "3.4.d")),
    ("DESVIO", None, "VERIFICACION_RUTINA", None, False, ("Menor", "3.4.b")),
    ("DESVIO", None, "ENSAYO_ACEPTACION", None, False, ("Mayor", "3.3.b")),
    ("DESVIO", None, "ORDINAL", None, False, ("Mayor", "3.3.d")),
    ("DESVIO", None, "CUANTITATIVO_TECNICO", 0.5, False, ("Mayor", "3.3.a")),
    ("DESVIO", None, "CUANTITATIVO_TECNICO", 0.25, False, ("Mayor", "3.3.a")),   # el umbral es inclusivo (≥)
    ("DESVIO", None, "CUANTITATIVO_TECNICO", 0.1, True, ("Mayor", "3.3.e")),
    ("DESVIO", None, "CUANTITATIVO_TECNICO", 0.1, False, ("Menor", "3.4.a")),
    ("DESVIO", None, "CUANTITATIVO_TECNICO", None, False, ("Mayor", "3.3.c")),
    ("DESVIO", None, "OTRO_TECNICO", None, False, ("Mayor", "3.3.c")),
    ("EXCEPCION_NO_ACREDITADA", None, "CUANTITATIVO_TECNICO", 0.5, False, ("Mayor", "3.3.a")),
    ("EXCEPCION_NO_ACREDITADA", "b", "OTRO_TECNICO", None, False, ("Crítico", "3.2.b")),
    ("INFORMACION_FALTANTE", "a", "CUANTITATIVO_TECNICO", 0.5, False, ("Mayor", "3.6.4")),
    ("INFORMACION_FALTANTE", None, "CUANTITATIVO_TECNICO", 0.5, False, ("Menor", "3.6.4")),
    ("INFORMACION_FALTANTE", "b", "OTRO_TECNICO", None, False, ("Menor", "3.6.4")),
]


@pytest.mark.parametrize("fuente,cc,objeto,brecha,personas,esperado", CASOS_CLASE)
def test_clase_por_regla(fuente, cc, objeto, brecha, personas, esperado):
    assert m.clase(fuente, cc, objeto, brecha, personas, C)[:2] == esperado


def test_brecha_nula_agrega_marca_y_clasifica_igual():
    assert m.clase("DESVIO", None, "CUANTITATIVO_TECNICO", 0.0, False, C) == ("Menor", "3.4.a", [m.MARCA_BRECHA_NULA])
    assert m.clase("DESVIO", "b", "CUANTITATIVO_TECNICO", 0.0, False, C) == ("Crítico", "3.2.b", [m.MARCA_BRECHA_NULA])
    assert m.clase("DESVIO", None, "CUANTITATIVO_TECNICO", 0.5, False, C)[2] == []
    assert m.clase("DESVIO", None, "OTRO_TECNICO", None, False, C)[2] == []


def test_el_umbral_sale_de_la_empresa_y_no_del_codigo():
    otra = copy.deepcopy(C)
    otra["umbral_brecha_relativa"]["valor"] = 0.10
    assert m.clase("DESVIO", None, "CUANTITATIVO_TECNICO", 0.187, False, C)[:2] == ("Menor", "3.4.a")
    assert m.clase("DESVIO", None, "CUANTITATIVO_TECNICO", 0.187, False, otra)[:2] == ("Mayor", "3.3.a")


def test_clase_rechaza_valores_desconocidos():
    with pytest.raises(ValueError):
        m.clase("OTRA", None, "OTRO_TECNICO", None, False, C)
    with pytest.raises(ValueError):
        m.clase("DESVIO", None, "INVENTADO", None, False, C)


# --- Responsable, RBS, solicitud, umbral ---

def test_responsable_y_rbs_por_norma_y_capitulo():
    assert m.responsable("NORM_01", "4.2", C) == "Gerencia de Infraestructura y Vías"
    assert m.responsable("NORM_04", "3.22", C) == "Gerencia de Material Rodante y Equipamiento de Talleres"
    assert m.responsable("NORM_04", "2.1", C) == "Gerencia de Infraestructura y Vías"
    assert m.rbs("NORM_04", "3.22", C) == "RBS-6 Pruebas y recepción"
    assert m.rbs("NORM_04", "2.1", C) == "RBS-4 Vía, trocha y gálibos"
    assert m.responsable("NORM_99", "1.1", C) is None and m.rbs("NORM_99", "1.1", C) is None


def test_solicitud():
    assert m.solicitud("DESVIO", "Crítico", C) == ("Solicitud de modificación de la oferta", "Antes de la adjudicación")
    assert m.solicitud("DESVIO", "Menor", C) == ("Nota aclaratoria o ajuste", "Antes de la firma del contrato")
    assert m.solicitud("EXCEPCION_NO_ACREDITADA", "Mayor", C)[0] == "Pedido de evidencia que acredite la excepción"
    assert m.solicitud("INFORMACION_FALTANTE", "Mayor", C)[0] == "Consulta técnica"


def test_umbral():
    assert m.umbral([("NORM_01", "4.2"), ("NORM_02", "5.12"), ("NORM_01", "4.2")]) == "NORM_01, Art. 4.2; NORM_02, Art. 5.12"


# --- Agrupamiento, decisión, top 5 ---

def _brecha(id_, seccion, oraciones, norma, articulo, clase_, nivel_, impacto, fuente="DESVIO", titulo="t"):
    return {"id": id_, "seccion": seccion, "oraciones": oraciones, "norma": norma, "articulo": articulo, "clase": clase_,
            "nivel": nivel_, "impacto": impacto, "probabilidad": 4, "fuente": fuente, "dimension_impacto": "Integridad",
            "regla": "x", "rbs": m.rbs(norma, articulo, C), "responsable": m.responsable(norma, articulo, C),
            "titulo": titulo, "enunciado": "e", "accion": "a"}


def test_agrupar_mismas_oraciones_toma_clase_maxima_y_su_responsable():
    brechas = [
        _brecha("B1", "3.5", ["O1", "O2"], "NORM_01", "4.2", "Mayor", "Medio", 3),
        _brecha("B2", "3.5", ["O2", "O1"], "NORM_03", "2.1", "Crítico", "Alto", 5),
        _brecha("B3", "3.6", ["O1", "O2"], "NORM_05", "1.6", "Mayor", "Alto", 4),
    ]
    antes = copy.deepcopy(brechas)
    riesgos = m.agrupar(brechas, C)
    assert brechas == antes                       # el registro sin agrupar no se toca
    assert len(riesgos) == 2
    r = next(r for r in riesgos if r["seccion"] == "3.5")
    assert r["clase"] == "Crítico" and r["nivel"] == "Alto" and r["brechas"] == ["B1", "B2"]
    assert r["responsable"] == m.responsable("NORM_03", "2.1", C)
    assert r["umbral"] == "NORM_01, Art. 4.2; NORM_03, Art. 2.1"
    assert [c["norma"] for c in r["citas"]] == ["NORM_01", "NORM_03"]


def _b(id_, seccion, oraciones, valor=None, norma="NORM_01", articulo="1.1", clase="Mayor", nivel="Medio"):
    return {"id": id_, "seccion": seccion, "oraciones": oraciones, "clasificacion": {"valor_ofertado": valor}, "clase": clase, "nivel": nivel,
            "norma": norma, "articulo": articulo, "impacto": 3, "probabilidad": 4, "titulo": id_, "rbs": "RBS-1", "responsable": "G", "fuente": "DESVIO",
            "regla": "3.3.a", "enunciado": "", "accion": ""}


def test_agrupar_trocha_duplicada_comparte_el_valor_ofertado():
    """La misma tolerancia aparecía dos veces (Art. 2.3 y 2.16) en oraciones distintas: un solo riesgo con la clase y el nivel más altos."""
    a = _b("a", "9", ["O1"], "±3 mm", articulo="2.3", clase="Mayor", nivel="Medio")
    b = _b("b", "9", ["O2"], "± 3 mm", articulo="2.16", clase="Menor", nivel="Bajo")
    riesgos = m.agrupar([a, b], C)
    assert len(riesgos) == 1
    r = riesgos[0]
    assert (r["clase"], r["nivel"], r["brechas"]) == ("Mayor", "Medio", ["a", "b"])
    assert [c["articulo"] for c in r["citas"]] == ["2.3", "2.16"] and r["oraciones"] == ["O1", "O2"]


def test_agrupar_6_1_une_por_oracion_o_por_valor_solo_dentro_de_la_seccion_y_es_transitivo():
    # misma oración -> un riesgo; mismo valor en otra sección -> no se une; valor distinto y oraciones distintas -> no se une
    assert len(m.agrupar([_b("a", "1", ["O1", "O2"]), _b("b", "1", ["O2"])], C)) == 1
    assert len(m.agrupar([_b("a", "1", ["O1"], "3 mm"), _b("b", "2", ["O1"], "3 mm")], C)) == 2
    assert len(m.agrupar([_b("a", "1", ["O1"], "3 mm"), _b("b", "1", ["O2"], "4 mm")], C)) == 2
    assert len(m.agrupar([_b("a", "1", ["O1"]), _b("b", "1", ["O2"])], C)) == 2        # sin valor ofertado, el vacío no une
    # a-b por la oración, b-c por el valor: los tres forman un riesgo
    assert len(m.agrupar([_b("a", "1", ["O1"]), _b("c", "1", ["O3"], "5 mm"), _b("b", "1", ["O1", "O2"], "5 mm")], C)) == 1


def test_agrupar_por_valor_solo_si_tiene_unidad_o_tres_caracteres_significativos():
    uno = [_b("a", "1", ["O1"], "1", articulo="1.1"), _b("b", "1", ["O2"], "1", articulo="1.2")]
    assert len(m.agrupar(uno, C)) == 2                                   # «1» suelto no agrupa
    assert len(m.agrupar([_b("a", "1", ["O1"], "10"), _b("b", "1", ["O2"], "10")], C)) == 2    # dos dígitos sin unidad tampoco
    assert len(m.agrupar([_b("a", "1", ["O1"], "± 1"), _b("b", "1", ["O2"], "±1")], C)) == 2   # los signos y espacios no cuentan
    assert len(m.agrupar([_b("a", "1", ["O1"], "1 m"), _b("b", "1", ["O2"], "1m")], C)) == 1   # con unidad, agrupa
    assert len(m.agrupar([_b("a", "1", ["O1"], "125"), _b("b", "1", ["O2"], "125")], C)) == 1  # tres caracteres significativos
    assert len(m.agrupar([_b("a", "1", ["O1"], "1"), _b("b", "1", ["O1"], "1")], C)) == 1      # la misma oración sigue agrupando


def test_agrupar_aclaraciones_menores_por_categoria_rbs():
    brechas = [
        _brecha("B1", "1", ["O1"], "NORM_01", "4.2", "Menor", "Bajo", 2, titulo="uno"),
        _brecha("B2", "2", ["O5"], "NORM_01", "4.3", "Menor", "Bajo", 1, titulo="dos"),
        _brecha("B3", "3", ["O7"], "NORM_01", "4.4", "Mayor", "Alto", 4, fuente="INFORMACION_FALTANTE", titulo="tres"),  # Mayor: individual
        _brecha("B6", "6", ["O13"], "NORM_01", "4.6", "Menor", "Bajo", 2, fuente="INFORMACION_FALTANTE", titulo="seis"),
        _brecha("B4", "4", ["O9"], "NORM_05", "1.6", "Menor", "Bajo", 2, titulo="solo"),   # único de su categoría: no se junta
        _brecha("B5", "5", ["O11"], "NORM_01", "4.5", "Mayor", "Alto", 4, titulo="mayor"),  # Mayor por desvío: queda aparte
    ]
    riesgos = m.agrupar(brechas, C)
    ag = [r for r in riesgos if r.get("agrupado_6_2")]
    assert len(ag) == 1 and ag[0]["titulo"] == "Aclaraciones menores: RBS-1 Obra civil y fundaciones"
    assert ag[0]["brechas"] == ["B1", "B2", "B6"] and ag[0]["clase"] == "Menor"
    assert {r["titulo"] for r in riesgos} == {ag[0]["titulo"], "solo", "mayor", "tres"}


def test_decision_aceptabilidad_resultados():
    assert m.decision_aceptabilidad([{"clase": "Crítico", "nivel": "Alto"}, {"clase": "Menor", "nivel": "Bajo"}], C) == "No aceptable"
    assert m.decision_aceptabilidad([{"clase": "Mayor", "nivel": "Medio"}, {"clase": "Menor", "nivel": "Bajo"}], C) == "Aceptable con condiciones"
    assert m.decision_aceptabilidad([{"clase": "Menor", "nivel": "Bajo"}], C) == "Aceptable"
    assert m.decision_aceptabilidad([], C) == "Aceptable"


def test_decision_clase_y_nivel_sobre_el_mismo_riesgo():
    # un Crítico con nivel Medio y un Mayor con nivel Alto: ningún riesgo es Crítico Y Alto a la vez
    riesgos = [{"clase": "Crítico", "nivel": "Medio"}, {"clase": "Mayor", "nivel": "Alto"}]
    assert m.decision_aceptabilidad(riesgos, C) == "Aceptable con condiciones"


def test_regla_sin_condiciones_nunca_se_cumple():
    c = copy.deepcopy(C)
    c["decision_aceptabilidad"]["reglas"].insert(0, {"decision": "No aceptable"})
    assert m.decision_aceptabilidad([{"clase": "Menor", "nivel": "Bajo"}], c) == "Aceptable"


# --- Consistencia con el ground truth: el código implementa la norma igual que el ground truth (no mide al modelo) ---

def _filas_gt():
    ruta = os.path.join(RAIZ, "evaluacion", "ground_truth_v3.csv")
    try:
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))
    except UnicodeDecodeError:
        with open(ruta, encoding="cp1252", newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))


def test_ground_truth_clase_y_responsable():
    filas = _filas_gt()
    assert len(filas) == 60
    errores = []
    for r in filas:
        brecha = float(r["brecha_relativa"]) if r["brecha_relativa"] else None
        c, regla, _ = m.clase(r["fuente"], r["condicion_critico"] or None, r["objeto_requisito"], brecha,
                           r["dimension_impacto"] == "Seguridad", C)
        resp = m.responsable(r["norma"], r["articulo"], C)
        if c != r["clase"] or resp != r["responsable"] or regla != r["regla_norm07"]:
            errores.append((r["id"], c, r["clase"], regla, r["regla_norm07"], resp, r["responsable"]))
    assert not errores, errores
