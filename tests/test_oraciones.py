# tests/test_oraciones.py
from scripts.document_utils import numerar_oraciones


def _textos(texto):
    return [t for _, t in numerar_oraciones(texto)]


def test_ids_consecutivos():
    assert [i for i, _ in numerar_oraciones("Primera frase. Segunda frase. Tercera frase.")] == ["O1", "O2", "O3"]


def test_no_corta_decimales_ni_rangos():
    texto = "El ancho de vía será de 1.600 mm con una tolerancia de ±1,5 mm. La planitud es 0,05 mm/m."
    assert _textos(texto) == [
        "El ancho de vía será de 1.600 mm con una tolerancia de ±1,5 mm.",
        "La planitud es 0,05 mm/m.",
    ]


def test_no_corta_referencias_a_articulos():
    texto = "Se cumplirá lo dispuesto en el Art. 4.2. del reglamento aplicable. Luego se verificará."
    assert _textos(texto) == [
        "Se cumplirá lo dispuesto en el Art. 4.2. del reglamento aplicable.",
        "Luego se verificará.",
    ]


def test_no_corta_tras_abreviatura_con_mayuscula():
    assert len(_textos("Ver Art. A.2 y el Nº Ref. Total en la tabla. Fin.")) == 2


def test_no_corta_unidades_con_punto_medio():
    assert _textos("El par de apriete será de 120 N·m. Se registrará.") == ["El par de apriete será de 120 N·m.", "Se registrará."]


def test_lineas_cortas_de_tabla_se_pegan_a_la_anterior():
    texto = "Longitud máxima de la cabina de pintura:\n12 m\nAncho:\n4,5 m\nEl taller cuenta con dos fosas."
    assert _textos(texto) == ["Longitud máxima de la cabina de pintura: 12 m Ancho: 4,5 m", "El taller cuenta con dos fosas."]


def test_lineas_visuales_de_una_misma_oracion_se_unen():
    texto = "La entrega se realizará dentro de los\n120 días corridos desde la firma del contrato.\nSe aplicarán penalidades."
    assert _textos(texto) == ["La entrega se realizará dentro de los 120 días corridos desde la firma del contrato.", "Se aplicarán penalidades."]


def test_encabezado_numerado_corto_no_se_pega_a_la_oracion_anterior():
    texto = "Fin del apartado anterior.\n2.1 Alcance\nEl oferente proveerá el servicio."
    assert _textos(texto) == ["Fin del apartado anterior.", "2.1 Alcance", "El oferente proveerá el servicio."]


def test_texto_vacio():
    assert numerar_oraciones("") == []
    assert numerar_oraciones("\n  \n") == []
