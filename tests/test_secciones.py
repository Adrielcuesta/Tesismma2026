# tests/test_secciones.py
from scripts import config, document_utils as du


def _relleno(n, palabra="texto"):
    """Una oración de relleno que termina en punto."""
    return f"Esta es la oración {n} con {palabra} de relleno para la sección."


def _titulos(secciones):
    return [t for s in secciones for t in s["titulos"]]


TEXTO = "\n".join([
    "1. Alcance",
    "1.1 Objeto",
    _relleno(1),
    "1.2 Plazos",
    _relleno(2),
    "2. Equipos",
    "2.1 Gruas",
    _relleno(3),
])


def test_encabezados_de_nivel_1_y_2():
    secciones = du.dividir_en_secciones(TEXTO)
    assert _titulos(secciones) == ["1. Alcance", "1.1 Objeto", "1.2 Plazos", "2. Equipos", "2.1 Gruas"]


def test_ids_consecutivos():
    assert [s["id"] for s in du.dividir_en_secciones(TEXTO)] == ["S1", "S2"]


def test_lineas_de_unidades_y_tablas_no_son_encabezados():
    texto = "\n".join([
        "3. Datos técnicos",
        "3.1 Material rodante",
        "42 t", "1.600 mm", "2.5 MPa", "1.676 mm (trocha ancha)", "125 kVA",
        "Peso", "Trocha", "3.1 kV",
        _relleno(1),
    ])
    secciones = du.dividir_en_secciones(texto)
    assert _titulos(secciones) == ["3. Datos técnicos", "3.1 Material rodante"]
    # las líneas de tabla siguen estando en el texto de la sección
    assert "1.600 mm" in secciones[0]["texto"] and "42 t" in secciones[0]["texto"]


def test_encabezado_largo_no_cuenta():
    largo = "1.1 " + "Título muy largo " * 8
    assert len(largo) >= 90
    texto = "\n".join(["1. Alcance", _relleno(1), largo, _relleno(2)])
    assert _titulos(du.dividir_en_secciones(texto)) == ["1. Alcance"]


def test_numeracion_no_creciente_es_texto():
    texto = "\n".join([
        "1. Alcance", "1.1 Objeto", _relleno(1),
        "2. Equipos", "2.1 Gruas", _relleno(2),
        "1.1 Objeto repetido en una tabla",   # no supera a 2.1
        "1. Anexo",                            # no supera a 2.1
        _relleno(3),
    ])
    secciones = du.dividir_en_secciones(texto)
    assert _titulos(secciones) == ["1. Alcance", "1.1 Objeto", "2. Equipos", "2.1 Gruas"]
    assert "1.1 Objeto repetido en una tabla" in secciones[-1]["texto"]


def test_agrupacion_no_cruza_capitulos():
    # todo cabe en SECTION_MAX_CHARS, pero hay dos capítulos de nivel 1: dos secciones
    secciones = du.dividir_en_secciones(TEXTO)
    assert len(secciones) == 2
    assert secciones[0]["titulos"] == ["1. Alcance", "1.1 Objeto", "1.2 Plazos"]
    assert secciones[1]["titulos"] == ["2. Equipos", "2.1 Gruas"]
    assert "Gruas" not in secciones[0]["texto"]


def test_agrupacion_respeta_el_tope(monkeypatch):
    monkeypatch.setattr(config, "SECTION_MAX_CHARS", 200)
    texto = "\n".join(["1. Alcance"] + [f"1.{n} Punto\n{_relleno(n)}" for n in range(1, 6)])
    secciones = du.dividir_en_secciones(texto)
    assert len(secciones) > 1
    assert all(len(s["texto"]) <= 200 for s in secciones)


def test_subseccion_grande_se_parte_por_parrafos(monkeypatch):
    monkeypatch.setattr(config, "SECTION_MAX_CHARS", 300)
    cuerpo = [_relleno(n) for n in range(1, 21)]
    secciones = du.dividir_en_secciones("\n".join(["1. Alcance", "1.1 Objeto"] + cuerpo))
    assert len(secciones) > 1
    assert all(len(s["texto"]) <= 300 for s in secciones)
    assert any("(parte" in t for t in _titulos(secciones))


def test_introduccion_solo_si_es_sustancial():
    corta = du.dividir_en_secciones("Portada breve\n" + TEXTO)
    assert "Introducción" not in _titulos(corta)
    larga = du.dividir_en_secciones(" ".join(_relleno(n) for n in range(1, 8)) + "\n" + TEXTO)
    assert larga[0]["titulos"] == ["Introducción"]


def test_sin_encabezados_conserva_el_documento():
    secciones = du.dividir_en_secciones("Texto corto sin numeración.")
    assert len(secciones) == 1 and secciones[0]["titulos"] == ["Documento"]
    assert du.dividir_en_secciones("") == []


def test_quita_encabezado_y_pie_pero_conserva_unidades():
    palabras = ["alfa", "bravo", "charlie", "delta", "eco", "foxtrot"]
    paginas = [
        (i + 1, f"Operador SA — Oferta Técnica Ferrocarril\nContenido {palabras[i]}\n1.600 mm\nPágina {i + 1} de 6")
        for i in range(6)
    ]
    lineas = [l for _, ls in du._quitar_encabezados_y_pies(paginas, config.MIN_LARGO_ENCABEZADO_OFERTA) for l in ls]
    assert not any("Oferta Técnica" in l for l in lineas)
    assert not any(l.startswith("Página") for l in lineas)
    assert lineas.count("1.600 mm") == 6
    # sin min_largo (comportamiento de la KB) la unidad repetida sí se perdería
    sin_minimo = [l for _, ls in du._quitar_encabezados_y_pies(paginas) for l in ls]
    assert "1.600 mm" not in sin_minimo


def test_encabezado_con_acronimo_solo_si_es_consecutivo():
    texto = "\n".join([
        "7. Ensayos", "7.1 Inspección visual", _relleno(1),
        "7.2 SAT bajo carga", _relleno(2),
        "1.250 MPa", "4.000 kN", _relleno(3),
    ])
    assert _titulos(du.dividir_en_secciones(texto)) == ["7. Ensayos", "7.1 Inspección visual", "7.2 SAT bajo carga"]


def test_acronimo_no_consecutivo_es_texto():
    texto = "\n".join(["7. Ensayos", "7.1 Inspección visual", _relleno(1), "7.5 SAT bajo carga", _relleno(2)])
    assert "7.5 SAT bajo carga" not in _titulos(du.dividir_en_secciones(texto))
