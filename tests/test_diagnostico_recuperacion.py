import pytest

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


# --- Dónde se pierde el artículo (K, top, tope, densa sin reranker, unión) ---

import json

from langchain_core.documents import Document


def _doc(norma, articulo):
    return Document(page_content=f"{norma} {articulo}", metadata={"norma": norma, "articulo": articulo})


def _cands(*items):
    """[Cand] en el orden de la densa; cada item: ((norma, artículo), puntaje denso, puntaje del reranker)."""
    return [dr.Cand(_doc(*par), densa, reranker) for par, densa, reranker in items]


CFG = {c.nombre: c for c in dr.CONFIGURACIONES}
arts = lambda docs: [d.metadata["articulo"] for d in docs]


def test_configuraciones_definidas():
    assert [(c.nombre, c.k, c.top, c.tope, c.modo) for c in dr.CONFIGURACIONES] == [
        ("actual", 10, 5, 15, "reranker"), ("media", 20, 8, 25, "reranker"), ("amplia", 30, 10, 40, "reranker"),
        ("densa_sin_reranker", 10, 5, 15, "densa"), ("union", 10, 5, 25, "union")]


def test_seleccion_reranker_respeta_k_top_y_tope():
    # orden de la densa: A, B, C, D (puntajes del reranker 0,1 / 0,9 / 0,5 / 0,8)
    cands = _cands((("N", "A"), -.1, .1), (("N", "B"), -.2, .9), (("N", "C"), -.3, .5), (("N", "D"), -.4, .8))
    sel = lambda k, top, tope: arts(dr.seleccion_final([cands], dr.Config("x", k, top, tope, "reranker")))
    assert sel(2, 5, 15) == ["B", "A"] and sel(4, 2, 15) == ["B", "D"] and sel(4, 4, 3) == ["B", "D", "C"]
    # el preámbulo ocupa un lugar del top y después se descarta
    con_preambulo = _cands((("N", "preambulo"), -.1, .95), (("N", "B"), -.2, .9), (("N", "C"), -.3, .5))
    assert arts(dr.seleccion_final([con_preambulo], dr.Config("x", 3, 2, 15, "reranker"))) == ["B"]


def test_seleccion_densa_sin_reranker_usa_el_orden_y_el_puntaje_denso():
    # el reranker baja al puesto 1 de la densa; sin reranker se conserva
    cands = _cands((("N", "A"), -.1, .01), (("N", "B"), -.2, .9), (("N", "C"), -.3, .8), (("N", "D"), -.4, .7), (("N", "E"), -.5, .6), (("N", "F"), -.6, .99))
    assert arts(dr.seleccion_final([cands], CFG["densa_sin_reranker"])) == ["A", "B", "C", "D", "E"]       # top 5 densos; F (puesto 6) queda fuera
    assert "A" not in arts(dr.seleccion_final([cands], dr.Config("x", 10, 5, 15, "reranker")))              # el reranker la deja afuera
    # unión entre consultas por el mayor puntaje denso, con tope
    c1, c2 = _cands((("N", "A"), -.5, 0), (("N", "B"), -.9, 0)), _cands((("N", "A"), -.1, 0), (("N", "C"), -.2, 0))
    assert arts(dr.seleccion_final([c1, c2], dr.Config("x", 10, 5, 2, "densa"))) == ["A", "C"]


def test_seleccion_union_conserva_el_top_denso_y_el_top_del_reranker():
    cands = _cands(*[(("N", f"d{i}"), -i / 10, 0.1) for i in range(5)], (("N", "r1"), -.6, .95), (("N", "r2"), -.7, .9), (("N", "x"), -.8, .01))
    union = arts(dr.seleccion_final([cands], CFG["union"]))
    assert {"d0", "d1", "d2", "d3", "d4"} <= set(union) and {"r1", "r2"} <= set(union) and "x" not in union
    assert union[:2] == ["r1", "r2"]                                      # ordenados por puntaje del reranker
    # sin duplicados cuando los dos criterios coinciden
    iguales = _cands(*[(("N", f"a{i}"), -i / 10, 1 - i / 10) for i in range(6)])
    assert arts(dr.seleccion_final([iguales], CFG["union"])) == ["a0", "a1", "a2", "a3", "a4"]
    # el tope de la unión es 25
    muchas = [_cands(*[(("N", f"q{j}-{i}"), -i / 10, i / 10) for i in range(10)]) for j in range(6)]
    assert len(dr.seleccion_final(muchas, CFG["union"])) == 25


class Db:
    """Base vectorial falsa: 40 fragmentos x0..x39 en orden de la densa (distancia creciente)."""
    def get(self, include=None):
        return {"ids": [str(i) for i in range(40)]}

    def similarity_search_with_score(self, consulta, k):
        return [(_doc("N", f"x{i}"), i / 100) for i in range(40)][:k]


def test_datos_de_consultas_corre_el_reranker_una_vez_por_consulta_con_los_30():
    llamadas = []
    def puntuar(consulta, docs):
        llamadas.append(len(docs))
        return [1 - i / 100 for i in range(len(docs))]
    datos = dr.datos_de_consultas(Db(), ["q1", "q2"], puntuar, total=40)
    assert llamadas == [30, 30] and [len(q["candidatos"]) for q in datos] == [30, 30]
    assert datos[0]["ranking"][:2] == ["N|x0", "N|x1"] and len(datos[0]["ranking"]) == 40      # el ranking cubre todo el índice
    assert datos[0]["candidatos"][0].densa == -0.0 and datos[0]["candidatos"][1].densa == -0.01
    assert [len(dr.seleccion_final([datos[0]["candidatos"]], c)) for c in dr.CONFIGURACIONES] == [5, 8, 10, 5, 5]   # todo derivado de los mismos 30


def test_consultas_de_seccion_usa_las_subsecciones_largas_o_la_seccion_entera():
    larga = "x" * (dr.config.MIN_CHARS_SUBSECCION + 5)
    assert dr.consultas_de_seccion({"texto": "t", "subsecciones": [("a", larga), ("b", "corta")]}) == [larga]
    assert dr.consultas_de_seccion({"texto": "texto entero", "subsecciones": [("b", "corta")]}) == ["texto entero"]


SECCIONES_R = [{"id": "3", "texto": "Los tableros exteriores tendrán grado IP44 de protección.", "subsecciones": []},
               {"id": "4", "texto": "El curado previo a la puesta en carga será de 14 días.", "subsecciones": []}]


def _datos_r():
    # sección 3: el artículo de la trampa está 3.º en la densa y 3.º tras el reranker
    s3 = [{"candidatos": _cands(*[(("NORM_09", f"x{i}"), -i, .9 - i / 10) for i in range(2)], (("NORM_02", "3.1"), -2, .5)),
           "ranking": ["NORM_09|x0", "NORM_09|x1", "NORM_02|3.1"]}]
    # sección 4: el equivalente NORM_01 4.9 está 12.º en la densa, tiene el mejor puntaje del reranker y es el 40.º artículo del índice
    relleno = [(("NORM_09", f"y{i}"), -i, .3) for i in range(11)]
    s4 = [{"candidatos": _cands(*relleno, (("NORM_01", "4.9"), -11, .99)), "ranking": [f"NORM_09|z{i}" for i in range(39)] + ["NORM_01|4.9"]}]
    return [s3, s4]


def test_analizar_recorte_puestos_entrada_y_pares_por_oferta():
    filas, pares = dr.analizar_recorte("P1", TRAMPAS, SECCIONES_R, _datos_r())
    f1, f2, f3 = filas
    assert (f1["puesto_densa"], f1["puesto_reranker"]) == (3, 3)
    assert all(f1["entra"].values())
    assert (f2["puesto_densa"], f2["puesto_reranker"]) == (12, 1)                                  # equivalente NORM_01 4.9
    assert f2["entra"] == {"actual": False, "media": True, "amplia": True, "densa_sin_reranker": False, "union": False}
    assert f2["puestos_indice"]["NORM_01|4.9"] == 40 and f2["puestos_indice"]["NORM_01|4.2"] is None
    assert (f3["seccion"], f3["puesto_densa"], f3["entra"]["actual"]) == (None, None, False)
    assert pares == {"actual": 3 + 5, "media": 3 + 8, "amplia": 3 + 10, "densa_sin_reranker": 3 + 5, "union": 3 + 5}   # la unión usa K=10: el 4.9 (puesto 12) no entra


def _fila(id_, **entra):
    base = {c.nombre: False for c in dr.CONFIGURACIONES}
    base.update(entra)
    return {"id": id_, "entra": base}


def _pares(**p):
    base = {"actual": 100, "media": 150, "amplia": 200, "densa_sin_reranker": 100, "union": 150}
    base.update(p)
    return {"P1": base}


def test_regla_de_adopcion_mayor_recall_dentro_del_doble_de_pares():
    filas = [_fila("a", actual=True, amplia=True, union=True), _fila("b", amplia=True, union=True), _fila("c", amplia=True), _fila("d", union=True)]
    # amplia: 3 trampas con 200 pares (== límite, elegible); union: 3 con 150 -> empatan en recall, gana la de menos pares
    d = dr.decision_recorte(filas, _pares())
    assert d["recall"]["amplia"] == 3 == d["recall"]["union"] and d["limite"] == 200 and d["adopta"] == "union"
    # si la amplia supera el doble del actual queda fuera aunque tenga más recall
    filas2 = [_fila(str(i), actual=i < 1, amplia=True, union=i < 2) for i in range(4)]
    d = dr.decision_recorte(filas2, _pares(amplia=201))
    assert "amplia" not in d["elegibles"] and d["adopta"] == "union"
    # si ninguna supera a la actual, se mantiene (y una de igual recall con menos pares sí la reemplaza)
    sin_mejora = [_fila("a", actual=True, media=True, densa_sin_reranker=True)]
    assert dr.decision_recorte(sin_mejora, _pares(densa_sin_reranker=100))["adopta"] is None
    assert dr.decision_recorte(sin_mejora, _pares(densa_sin_reranker=90))["adopta"] == "densa_sin_reranker"


def test_cache_ida_y_vuelta_y_validacion_del_hash(tmp_path):
    datos = {"P1": _datos_r()}
    cache = dr.a_cache({"P1": SECCIONES_R}, datos, {"NORM_01|4.2": [{"caracteres": 10}]})
    ruta = tmp_path / "c.json"
    ruta.write_text(json.dumps(cache), encoding="utf-8")
    leida = json.loads(ruta.read_text(encoding="utf-8"))
    recuperados = dr.datos_desde_cache(leida, "P1", SECCIONES_R)
    f1, _ = dr.analizar_recorte("P1", TRAMPAS, SECCIONES_R, recuperados)
    f2, _ = dr.analizar_recorte("P1", TRAMPAS, SECCIONES_R, datos["P1"])
    assert f1 == f2 and leida["fragmentos"]["NORM_01|4.2"][0]["caracteres"] == 10          # las configuraciones salen de la caché sin recalcular
    cambiadas = [dict(SECCIONES_R[0], texto="otro texto de la oferta"), SECCIONES_R[1]]
    with pytest.raises(ValueError, match="no corresponde"):
        dr.datos_desde_cache(leida, "P1", cambiadas)
    with pytest.raises(ValueError, match="no tiene la oferta"):
        dr.datos_desde_cache(leida, "P2", SECCIONES_R)


def test_describir_fragmento_encabezados_y_largo():
    solo = "Art. 4.2. APOYOS\nSe exigen 2 unidades."
    assert dr.describir_fragmento(solo) == {"caracteres": len(solo), "encabezados": [["4.2", 0]], "empieza_con": "4.2"}
    pegado = "Art. 4.1. PLAZO\nTexto.\nArt. 4.2. APOYOS\nOtro texto."
    d = dr.describir_fragmento(pegado)
    assert [e for e, _ in d["encabezados"]] == ["4.1", "4.2"] and d["empieza_con"] == "4.1"
    sin = dr.describir_fragmento("Texto sin encabezado de artículo (ver Art. 2.7).")
    assert sin["encabezados"] == [] and sin["empieza_con"] is None


def test_info_fragmentos_existencia_largo_y_artículo_pegado():
    datos = {"documents": ["Art. 4.2. APOYOS\nTexto.", "Art. 5.1. PLAZO\nTexto.\nArt. 5.2. OTRO\nTexto.", "Art. 9.9. X\nY"],
             "metadatas": [{"norma": "NORM_01", "articulo": "4.2", "parte": 1}, {"norma": "NORM_02", "articulo": "5.2", "parte": 1},
                           {"norma": "NORM_03", "articulo": "9.9"}]}
    info = dr.info_fragmentos(datos, {"NORM_01|4.2", "NORM_02|5.2", "NORM_04|1.1"})
    assert info["NORM_04|1.1"] == []                                                         # no existe
    assert info["NORM_01|4.2"][0]["empieza_con"] == "4.2" and info["NORM_01|4.2"][0]["caracteres"] == len(datos["documents"][0])
    assert info["NORM_02|5.2"][0]["empieza_con"] == "5.1"                                    # el 5.2 está pegado detrás del 5.1
    assert "NORM_03|9.9" not in info


def test_informe_recorte_tabla_recall_pares_decision_y_articulos_fuera():
    f_in = _fila("P1-01", media=True, amplia=True, union=True)
    f_in.update(oferta="P1", seccion="3", articulo="NORM_02 3.1", puesto_densa=2, puesto_reranker=1, clave_principal="NORM_02|3.1", puestos_indice={"NORM_02|3.1": 2})
    f_fuera = _fila("P1-02")
    f_fuera.update(oferta="P1", seccion="4", articulo="NORM_01 4.2", puesto_densa=None, puesto_reranker=None, clave_principal="NORM_01|4.2",
                   puestos_indice={"NORM_01|4.2": 87, "NORM_01|4.9": None})
    fragmentos = {"NORM_01|4.2": [{"caracteres": 2150, "encabezados": [["4.1", 0], ["4.2", 900]], "empieza_con": "4.1"}], "NORM_01|4.9": []}
    texto = dr.informe_recorte([f_in, f_fuera], _pares(union=140), fragmentos)
    assert "P1-02" in texto and "fuera" in texto and "actual" in texto and "densa_sin_reranker" in texto and "union" in texto
    assert "límite de pares: 200" in texto and "ADOPTAR «union»" in texto
    assert "NORM_01 4.2 (artículo de la trampa): puesto en toda la densa (artículos distintos) 87; 1 fragmento(s): 2150 caracteres, empieza con Art. 4.1, trae pegado: Art. 4.1" in texto
    assert "NORM_01 4.9 (equivalente): puesto en toda la densa (artículos distintos) no aparece; NO existe un fragmento" in texto
    assert "MANTENER la actual" in dr.informe_recorte([f_fuera], _pares())
