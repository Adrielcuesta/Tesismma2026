from scripts import diagnostico_recuperacion as dr

SECCIONES = [{"id": "3", "texto": "Los tableros exteriores tendrán grado IP44 de protección."},
             {"id": "4", "texto": "El curado previo a la puesta en carga será de 14 días."}]
TRAMPAS = [
    {"id": "P1-01", "oferta": "P1", "fragmento_trampa": "grado IP44 de protección", "norma": "NORM_02", "articulo": "3.1", "articulos_equivalentes": ""},
    {"id": "P1-02", "oferta": "P1", "fragmento_trampa": "curado previo a la puesta en carga", "norma": "NORM_01", "articulo": "4.2.",
     "articulos_equivalentes": "NORM_01 4.9"},
    {"id": "P1-03", "oferta": "P1", "fragmento_trampa": "frase que no está en la oferta", "norma": "NORM_01", "articulo": "1.1", "articulos_equivalentes": ""},
]


def test_seccion_de_trampa_busca_la_frase_en_el_texto_de_la_seccion():
    assert [dr.seccion_de_trampa(t, SECCIONES) for t in TRAMPAS] == [0, 1, None]


def test_recall_articulo_con_datos_falsos_acepta_equivalentes_y_sufijos():
    densa = [{("NORM_02", "3.1")}, {("NORM_01", "4.9")}]            # el equivalente cuenta
    filas = dr.recall_articulo(TRAMPAS, SECCIONES, densa)
    assert [(f["id"], f["recuperada"]) for f in filas] == [("P1-01", True), ("P1-02", True), ("P1-03", False)]
    assert dr.recall_articulo(TRAMPAS, SECCIONES, [{("NORM_02", "3.1")}, set()])[1]["recuperada"] is False
    # el artículo en otra sección no cuenta
    assert dr.recall_articulo(TRAMPAS, SECCIONES, [set(), {("NORM_02", "3.1")}])[0]["recuperada"] is False


def _filas(*estados):
    return [{"id": f"T{i}", "oferta": "P1", "seccion": "3", "articulo": "NORM_01 1.1", "recuperada": e} for i, e in enumerate(estados)]


def test_regla_de_adopcion():
    # mejora y no pierde nada -> adopta
    d = dr.decision_adopcion(_filas(True, False, False), _filas(True, True, False))
    assert d["adopta"] and (d["densa"], d["hibrida"], d["ganadas"], d["perdidas"]) == (1, 2, ["T1"], [])
    # mejora el total pero pierde una que la densa recuperaba -> no adopta
    d = dr.decision_adopcion(_filas(True, False, False), _filas(False, True, True))
    assert not d["adopta"] and d["perdidas"] == ["T0"] and d["hibrida"] == 2
    # empata -> no adopta
    assert not dr.decision_adopcion(_filas(True, False), _filas(True, False))["adopta"]
    # sin mejora y con pérdida -> no adopta
    assert not dr.decision_adopcion(_filas(True, True), _filas(True, False))["adopta"]


def test_informe_trampa_por_trampa_y_decision():
    texto = dr.informe_hibrida(_filas(True, False), _filas(True, True))
    assert "T1" in texto and "Recall@artículo densa:   1/2 (50%)" in texto and "Recall@artículo híbrida: 2/2 (100%)" in texto and "ADOPTAR" in texto
    assert "MANTENER la densa" in dr.informe_hibrida(_filas(True, False), _filas(True, False))


def test_la_config_por_defecto_sigue_en_densa():
    from scripts import config
    assert config.RECUPERACION == "densa" and config.RRF_K == 60
