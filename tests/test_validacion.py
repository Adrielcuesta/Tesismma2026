# tests/test_validacion.py
from scripts.rag_components import normalizar_para_comparar, validar_riesgos
from scripts.schemas import RiskItem, FuenteNorma


def _riesgo(cita="", fuentes=()):
    return RiskItem(
        descripcion_riesgo="<descripción>", tipo_de_riesgo="Implícito", impacto_estimado="Medio",
        probabilidad_estimada="Media", responsabilidad_mitigacion="<rol>", responsable_accidente="<rol>",
        accion_mitigacion="<acción concreta>", umbral_alerta="<condición>", explicacion_riesgo="<explicación>",
        cita_oferta=cita, fuentes=[FuenteNorma(norma=n, articulo=a) for n, a in fuentes],
    )


ENTREGADOS = [{"norma": "NORM_01", "articulo": "4.2"}, {"norma": "NORM_02", "articulo": "1.1"}]
SUBSECCIONES = [
    ("1.1 Objeto", "El oferente proveerá el servicio completo."),
    ("1.2 Plazos", "La entrega se realizará en 120 días corridos, sin penalidades."),
]


# --- normalizar_para_comparar ---

def test_normalizar_quita_tildes_mayusculas_y_signos():
    assert normalizar_para_comparar("Año: 1.600 mm, ÁÉÍÓÚ — Ñandú!") == "ano1600mmaeiounandu"


def test_normalizar_ignora_espacios_y_saltos_de_linea():
    assert normalizar_para_comparar("La entrega\nse realizará  en") == normalizar_para_comparar("la entrega se realizara en")


def test_normalizar_vacio():
    assert normalizar_para_comparar("") == ""
    assert normalizar_para_comparar(None) == ""


# --- validar_riesgos ---

def test_fuente_entregada_se_conserva():
    r, = validar_riesgos([_riesgo(fuentes=[("NORM_01", "4.2")])], ENTREGADOS, SUBSECCIONES)
    assert [(f.norma, f.articulo) for f in r.fuentes] == [("NORM_01", "4.2")]
    assert "sin respaldo normativo" not in r.marcas


def test_fuente_inventada_se_quita_y_se_marca():
    r, = validar_riesgos([_riesgo(fuentes=[("NORM_03", "9.9")])], ENTREGADOS, SUBSECCIONES)
    assert r.fuentes == []
    assert "sin respaldo normativo" in r.marcas


def test_mezcla_de_fuentes_conserva_solo_las_entregadas():
    r, = validar_riesgos([_riesgo(fuentes=[("NORM_03", "9.9"), ("norm_02", "1.1.")])], ENTREGADOS, SUBSECCIONES)
    assert [(f.norma, f.articulo) for f in r.fuentes] == [("NORM_02", "1.1")]
    assert "sin respaldo normativo" not in r.marcas


def test_sin_fuentes_ni_fragmentos_marca_sin_respaldo():
    r, = validar_riesgos([_riesgo()], [], SUBSECCIONES)
    assert "sin respaldo normativo" in r.marcas


def test_cita_en_segunda_subseccion_fija_seccion_oferta():
    r, = validar_riesgos([_riesgo(cita="entrega se realizará en 120 días corridos")], ENTREGADOS, SUBSECCIONES)
    assert r.seccion_oferta == "1.2 Plazos"
    assert "cita no verificada" not in r.marcas


def test_cita_no_encontrada_marca_y_usa_primera_subseccion():
    r, = validar_riesgos([_riesgo(cita="texto que no está en la oferta")], ENTREGADOS, SUBSECCIONES)
    assert r.seccion_oferta == "1.1 Objeto"
    assert "cita no verificada" in r.marcas


def test_cita_vacia_se_marca_como_no_verificada():
    r, = validar_riesgos([_riesgo(cita="")], ENTREGADOS, SUBSECCIONES)
    assert "cita no verificada" in r.marcas


def test_cita_distinta_en_mayusculas_y_tildes_se_verifica():
    r, = validar_riesgos([_riesgo(cita="LA ENTREGA SE REALIZARA EN 120 DIAS CORRIDOS")], ENTREGADOS, SUBSECCIONES)
    assert "cita no verificada" not in r.marcas


def test_las_marcas_del_modelo_se_reemplazan_por_las_del_codigo():
    riesgo = _riesgo(cita="entrega se realizará en 120 días corridos", fuentes=[("NORM_01", "4.2")])
    riesgo.marcas = ["cita no verificada", "sin respaldo normativo"]
    r, = validar_riesgos([riesgo], ENTREGADOS, SUBSECCIONES)
    assert r.marcas == []


def test_nunca_descarta_riesgos():
    riesgos = [_riesgo(cita="inventada", fuentes=[("NORM_09", "1.1")]) for _ in range(5)]
    assert len(validar_riesgos(riesgos, ENTREGADOS, SUBSECCIONES)) == 5
