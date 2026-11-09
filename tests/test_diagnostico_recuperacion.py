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
    assert [(c.nombre, c.k, c.top, c.tope, c.modo) for c in dr.CONFIGURACIONES[:5]] == [
        ("actual", 10, 5, 15, "reranker"), ("media", 20, 8, 25, "reranker"), ("amplia", 30, 10, 40, "reranker"),
        ("densa_sin_reranker", 10, 5, 15, "densa"), ("union", 10, 5, 25, "union")]
    assert (CFG["union_k20"].k, CFG["union_k20"].top, CFG["union_k20"].top_rr, CFG["union_k20"].tope) == (20, 5, 8, 30)
    assert [c.nombre for c in dr.CONFIGURACIONES[5:12]] == [
        "union_k20", "union_oraciones_cifras_N2", "union_oraciones_cifras_N3", "union_oraciones_todas_N2",
        "union_k20_oraciones_cifras_N2", "union_k20_oraciones_cifras_N3", "union_k20_oraciones_todas_N2"]
    completas = [c for c in dr.CONFIGURACIONES if c.oraciones and "cupo" not in c.nombre]
    assert all(c.cupo_oraciones == 10 for c in completas) and dr.CUPO_ORACIONES == 10
    assert [c.tope + c.cupo_oraciones for c in completas] == [35] * 3 + [40] * 3     # tope total: base + cupo propio
    # variantes de union_oraciones_cifras_N2 con cupo 8, 6 y 4: la base union sigue igual (K=10, 5+5, tope 25)
    assert [c.nombre for c in dr.CONFIGURACIONES[12:]] == ["union_oraciones_cifras_N2_cupo8", "union_oraciones_cifras_N2_cupo6", "union_oraciones_cifras_N2_cupo4"]
    for c, cupo in zip(dr.CONFIGURACIONES[12:], (8, 6, 4)):
        assert (c.k, c.top, c.top_rr, c.tope, c.modo, c.oraciones, c.cupo_oraciones) == (10, 5, None, 25, "union", (True, 2), cupo)
    assert CFG["union_oraciones_cifras_N3"].oraciones == (True, 3) and CFG["union_k20_oraciones_todas_N2"].oraciones == (False, 2)
    assert (CFG["union_oraciones_todas_N2"].k, CFG["union_oraciones_todas_N2"].tope) == (10, 25) and CFG["union_k20_oraciones_todas_N2"].tope == 30


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
    assert [len(dr.seleccion_final([datos[0]["candidatos"]], c)) for c in dr.CONFIGURACIONES[:6]] == [5, 8, 10, 5, 5, 8]   # todo derivado de los mismos 30


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
    assert {n: f2["entra"][n] for n in ("actual", "media", "amplia", "densa_sin_reranker", "union")} == {
        "actual": False, "media": True, "amplia": True, "densa_sin_reranker": False, "union": False}
    assert f2["entra"]["union_k20"] is True                                                         # K=20 sí llega al puesto 12
    assert f2["puestos_indice"]["NORM_01|4.9"] == 40 and f2["puestos_indice"]["NORM_01|4.2"] is None
    assert (f3["seccion"], f3["puesto_densa"], f3["entra"]["actual"]) == (None, None, False)
    assert {n: pares[n] for n in ("actual", "media", "amplia", "densa_sin_reranker", "union")} == {
        "actual": 3 + 5, "media": 3 + 8, "amplia": 3 + 10, "densa_sin_reranker": 3 + 5, "union": 3 + 5}   # la unión usa K=10: el 4.9 (puesto 12) no entra
    assert pares["union_k20"] == 3 + 8 and pares["union_k20_oraciones_todas_N2"] == 3 + 8      # K=20: 4.9 + 7 del reranker (los 5 densos ya están)


def _fila(id_, **entra):
    base = {c.nombre: False for c in dr.CONFIGURACIONES}
    base.update(entra)
    return {"id": id_, "entra": base}


def _pares(**p):
    base = {c.nombre: 100 for c in dr.CONFIGURACIONES}
    base.update({"media": 150, "amplia": 200, "union": 150})
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


# --- Chequeo de ingesta: encabezado de artículo con título en minúsculas ---

def test_encabezado_de_articulo_con_titulo_en_minusculas_o_mayusculas():
    casos = [("Art. 4.7. Reserva física y de capacidad\nTexto del artículo.", "4.7"),    # el formato de analizar_norma_por_articulos
             ("Art. 2.6. Nivelación longitudinal\nTexto del artículo.", "2.6"),
             ("Art. 3.7. CONTROL DE CALIDAD\nTexto del artículo.", "3.7"),
             ("Art. 1.8. Ñandú y otros\nTexto.", "1.8"),
             ("Art. 2.13. a mano alzada\nTexto.", "2.13")]
    for texto, articulo in casos:
        d = dr.describir_fragmento(texto)
        assert d["empieza_con"] == articulo and d["encabezados"] == [[articulo, 0]] and d["caracteres"] == len(texto)


def test_encabezado_ignora_referencias_dentro_del_texto_y_detecta_el_pegado_en_minusculas():
    texto = "Art. 2.6. Nivelación longitudinal\nSegún el (Art. 2.7). Ver Art. 2.8. Algo en medio de la línea.\nArt. 2.9. Otro artículo pegado"
    d = dr.describir_fragmento(texto)
    assert [e for e, _ in d["encabezados"]] == ["2.6", "2.9"] and d["empieza_con"] == "2.6"
    info = dr.info_fragmentos({"documents": [texto], "metadatas": [{"norma": "NORM_04", "articulo": "2.6", "parte": 1}]}, {"NORM_04|2.6"})
    assert "trae pegado: Art. 2.9" in dr._texto_fragmentos(info["NORM_04|2.6"], "NORM_04|2.6")
    sin_encabezado = dr.describir_fragmento("Reserva física y de capacidad sin encabezado")
    assert sin_encabezado["empieza_con"] is None
    assert "sin encabezado de artículo" in dr._texto_fragmentos([dict(sin_encabezado)], "NORM_04|2.6")


# --- union_k20 y consultas por oración ---

def test_union_k20_restringe_el_reranker_a_los_20_primeros_de_la_densa():
    # los candidatos 25..29 tienen el mejor puntaje del reranker, pero están fuera de K=20
    items = [(("N", f"c{i}"), -i, .99 if i >= 25 else (.8 if 10 <= i <= 17 else .1)) for i in range(30)]
    final = arts(dr.seleccion_final([_cands(*items)], CFG["union_k20"]))
    assert set(final) == {f"c{i}" for i in range(5)} | {f"c{i}" for i in range(10, 18)} and len(final) == 13      # top 5 denso + top 8 del reranker
    assert final[:8] == [f"c{i}" for i in range(10, 18)]                                                           # ordenados por puntaje del reranker
    assert not any(a in final for a in ("c25", "c26", "c29"))


def _oracion(cifras, *articulos):
    return {"hash": "h", "con_cifras": cifras, "articulos": [{"norma": "N", "articulo": a, "densa": -i} for i, a in enumerate(articulos)]}


BASE_ABC = [_cands((("N", "A"), -1, .9), (("N", "B"), -2, .8), (("N", "C"), -3, .7))]
ORACIONES = [_oracion(True, "X", "A", "Y"), _oracion(False, "Z", "W"), _oracion(True, "V")]


def _con(nombre, oraciones=ORACIONES, por_consulta=BASE_ABC):
    return arts(dr.seleccion_final(por_consulta, CFG[nombre], oraciones))


def test_oraciones_con_cifras_n2_suman_detras_de_la_base_sin_repetir():
    # oración 1 (con cifras): X (puesto 1) y A (2, ya está en la base); oración 3 (con cifras): V; la oración 2 no tiene dígitos
    assert _con("union_oraciones_cifras_N2") == ["A", "B", "C", "X", "V"]


def test_oraciones_con_cifras_n3_agrega_el_tercer_articulo_de_cada_oracion():
    assert _con("union_oraciones_cifras_N3") == ["A", "B", "C", "X", "V", "Y"]


def test_oraciones_todas_n2_incluye_las_que_no_tienen_cifras_y_ordena_por_puesto():
    # puestos 1: X (oración 1), Z (2), V (3); puesto 2: W (oración 2)
    assert _con("union_oraciones_todas_N2") == ["A", "B", "C", "X", "Z", "V", "W"]


def test_oraciones_sin_datos_dejan_la_base():
    assert _con("union_oraciones_todas_N2", oraciones=[]) == _con("union") == ["A", "B", "C"]
    assert dr.seleccion_final(BASE_ABC, CFG["union"], ORACIONES) == dr.seleccion_final(BASE_ABC, CFG["union"])    # la base sola no usa las oraciones


def test_cupo_propio_de_10_articulos_de_oraciones_detras_de_la_base():
    def consulta(j, n=10, escala=10):
        return _cands(*[(("N", f"q{j}-{i}"), -i, i / escala) for i in range(n)])           # n distintos: top 5 denso + top 5 del reranker
    tres = [consulta(0), consulta(1), consulta(2)]
    base = dr.seleccion_final(tres, CFG["union"])
    assert len(base) == 25                                                                  # la base conserva su tope
    nuevas = [_oracion(False, *[f"s{j}-{i}" for i in range(2)]) for j in range(6)]       # 12 artículos nuevos con N=2
    final = dr.seleccion_final(tres, CFG["union_oraciones_todas_N2"], nuevas)
    assert len(final) == 35 and final[:25] == base                                          # 25 de la base + cupo de 10 de las oraciones
    assert arts(final[25:]) == [f"s{j}-0" for j in range(6)] + [f"s{j}-1" for j in range(4)]   # por puesto y, a igual puesto, por orden de oración
    # con menos de 10 artículos nuevos entran todos
    assert len(dr.seleccion_final(tres, CFG["union_oraciones_todas_N2"], nuevas[:3])) == 25 + 6
    # union_k20: la base llega a 30 y las oraciones suman hasta 10 más (tope total 40)
    treinta = [_cands(*[(("N", f"k{j}-{i}"), -i, i / 20) for i in range(20)]) for j in range(3)]
    assert len(dr.seleccion_final(treinta, CFG["union_k20"])) == 30
    assert len(dr.seleccion_final(treinta, CFG["union_k20_oraciones_todas_N2"], nuevas)) == 40
    # el cupo no se llena con artículos que la base ya trae
    repetidas = [_oracion(False, "q0-9", "q1-9")]
    assert len(dr.seleccion_final(tres, CFG["union_oraciones_todas_N2"], repetidas)) == 25


def test_oraciones_de_seccion_usa_numerar_oraciones_en_cada_subseccion():
    seccion = {"id": "3", "texto": "todo",
               "subsecciones": [("3.1 A", "Primera oración con 3 mm de tolerancia en la vía. Segunda oración sin números en el texto."),
                                ("3.2 B", "Otra subsección con un texto sin cifras alguna"), ("3.3 vacía", "   ")]}
    assert dr.oraciones_de_seccion(seccion) == ["Primera oración con 3 mm de tolerancia en la vía.", "Segunda oración sin números en el texto.",
                                                "Otra subsección con un texto sin cifras alguna"]
    assert dr.oraciones_de_seccion({"id": "4", "texto": "Texto único de la sección.", "subsecciones": []}) == ["Texto único de la sección."]


class DbOraciones:
    """Densa falsa: por oración devuelve fragmentos según una palabra clave; con duplicados de artículo y un preámbulo."""
    def similarity_search_with_score(self, consulta, k):
        base = [(_doc("N", "preambulo"), 0.1), (_doc("N", "a1"), 0.2), (_doc("N", "a1 (parte 2)"), 0.25), (_doc("N", "a2"), 0.3)] + \
               [(_doc("N", f"b{i}"), 0.4 + i / 10) for i in range(8)]
        return base[:k]


def test_datos_de_oraciones_articulos_distintos_sin_preambulo_y_marca_de_cifras():
    datos = dr.datos_de_oraciones(DbOraciones(), ["La vía mide 3 mm.", "Sin cifras acá."])
    assert [d["con_cifras"] for d in datos] == [True, False]
    arts_ = [a["articulo"] for a in datos[0]["articulos"]]
    assert arts_ == ["a1", "a2", "b0", "b1", "b2"]                          # preámbulo fuera, '(parte 2)' no repite el artículo, máximo 5
    assert datos[0]["articulos"][0] == {"norma": "N", "articulo": "a1", "densa": -0.2}
    assert datos[0]["hash"] == dr._hash("La vía mide 3 mm.") != datos[1]["hash"]


def test_cache_con_oraciones_ida_y_vuelta_y_validacion(tmp_path):
    secciones = [{"id": "3", "texto": "Los tableros exteriores tendrán grado IP44 de protección.", "subsecciones": []}]
    ors = [dr.datos_de_oraciones(DbOraciones(), dr.oraciones_de_seccion(s)) for s in secciones]
    datos = {"P1": [_datos_r()[0]]}
    cache = dr.a_cache({"P1": secciones}, datos, {}, {"P1": ors})
    ruta = tmp_path / "c.json"
    ruta.write_text(json.dumps(cache), encoding="utf-8")
    leida = json.loads(ruta.read_text(encoding="utf-8"))
    assert leida["version"] == 2 and dr.oraciones_desde_cache(leida, "P1", secciones) == ors
    assert dr.oraciones_desde_cache(leida, "P2", secciones) is None                                  # faltan
    cambiada = [dict(secciones[0], texto="Otro texto de la oferta, distinto.")]
    assert dr.oraciones_desde_cache(leida, "P1", cambiada) is None                                    # el texto cambió: hay que volver a buscar
    assert dr.oraciones_desde_cache({"version": 1, "ofertas": {}}, "P1", secciones) is None           # caché anterior


def test_analizar_recorte_con_oraciones_suma_el_articulo_que_la_base_no_trae():
    secciones = [SECCIONES_R[0]]
    trampas = [TRAMPAS[0]]                                                                           # artículo NORM_02 3.1
    datos = [[{"candidatos": _cands((("NORM_09", "x"), -1, .9)), "ranking": ["NORM_09|x", "NORM_02|3.1"]}]]
    oraciones = [[{"hash": "h", "con_cifras": True, "articulos": [{"norma": "NORM_02", "articulo": "3.1", "densa": -.1}]}]]
    filas, pares = dr.analizar_recorte("P1", trampas, secciones, datos, oraciones)
    assert filas[0]["entra"]["union"] is False and filas[0]["entra"]["union_oraciones_cifras_N2"] is True
    assert filas[0]["entra"]["union_oraciones_todas_N2"] is True and filas[0]["entra"]["union_k20_oraciones_cifras_N3"] is True
    assert pares["union"] == 1 and pares["union_oraciones_cifras_N2"] == 2
    sin = dr.analizar_recorte("P1", trampas, secciones, datos)[0]                                    # sin datos por oración: iguales a la base
    assert sin[0]["entra"]["union_oraciones_cifras_N2"] is False


def test_informe_incluye_las_columnas_nuevas_y_las_notas():
    f = _fila("P1-01", union_k20=True, union_oraciones_cifras_N2=True)
    f.update(oferta="P1", seccion="3", articulo="NORM_02 3.1", puesto_densa=2, puesto_reranker=1, clave_principal="NORM_02|3.1", puestos_indice={"NORM_02|3.1": 2})
    texto = dr.informe_recorte([f], _pares())
    for nombre in ("union_k20", "union_oraciones_cifras_N2", "union_oraciones_cifras_N3", "union_oraciones_todas_N2", "union_k20_oraciones_todas_N2"):
        assert nombre in texto
    assert "equivalente a reranquear solo esos 20" in texto and "solo texto de la oferta" in texto and "cupo propio de 10 artículos por sección" in texto
    assert "límite de pares: 200" in texto


# --- CSV en evaluacion/diagnosticos/ ---

def test_los_csv_del_diagnostico_van_por_defecto_a_evaluacion_diagnosticos():
    import os
    ruta = dr.csv_por_defecto("diagnostico_recorte.csv")
    assert os.path.normpath(ruta).endswith(os.path.join("evaluacion", "diagnosticos", "diagnostico_recorte.csv"))
    assert os.path.isdir(dr.DIR_DIAGNOSTICOS)
    assert os.path.isfile(os.path.join(dr.DIR_DIAGNOSTICOS, ".gitkeep"))


def test_el_cache_del_diagnostico_esta_ignorado_por_git():
    import os
    raiz = os.path.join(os.path.dirname(__file__), os.pardir)
    with open(os.path.join(raiz, ".gitignore"), encoding="utf-8") as f:
        assert "diagnostico_cache.json" in [l.strip() for l in f]


def test_variantes_con_cupo_reducido_suman_solo_su_cupo():
    def consulta(j):
        return _cands(*[(("N", f"q{j}-{i}"), -i, i / 10) for i in range(10)])
    tres = [consulta(0), consulta(1), consulta(2)]
    nuevas = [_oracion(True, *[f"s{j}-{i}" for i in range(2)]) for j in range(6)]       # 12 artículos nuevos, todas con cifras
    base = dr.seleccion_final(tres, CFG["union"])
    assert len(base) == 25
    for cupo in (8, 6, 4):
        final = dr.seleccion_final(tres, CFG[f"union_oraciones_cifras_N2_cupo{cupo}"], nuevas)
        assert len(final) == 25 + cupo and final[:25] == base
    # los cupos chicos son prefijos de los grandes: se queda con los mejores por puesto
    c8 = arts(dr.seleccion_final(tres, CFG["union_oraciones_cifras_N2_cupo8"], nuevas))
    c4 = arts(dr.seleccion_final(tres, CFG["union_oraciones_cifras_N2_cupo4"], nuevas))
    assert c8[:29] == c4


# --- El pipeline y el diagnóstico usan la MISMA selección ---

import hashlib

from scripts import config as cfg_pipeline
from scripts import rag_components as rc


class DbSintetica:
    """Base vectorial falsa y determinista: 60 fragmentos a0..a59; el orden de la densa depende del texto de la consulta."""
    def __init__(self, n=60):
        self.docs = [Document(page_content=f"frag {i}", metadata={"norma": "N", "articulo": f"a{i}", "parte": 1}) for i in range(n)]
        self.busquedas_por_oracion = 0

    def _orden(self, consulta):
        valor = lambda i: int(hashlib.sha1(f"{consulta}|{i}".encode()).hexdigest(), 16) % 10007
        return sorted(range(len(self.docs)), key=lambda i: (valor(i), i)), valor

    def get(self, include=None):
        return {"ids": [str(i) for i in range(len(self.docs))]}

    def as_retriever(self, search_kwargs):
        k = search_kwargs["k"]
        return type("R", (), {"invoke": lambda s, q: [self.docs[i] for i in self._orden(q)[0][:k]]})()

    def similarity_search_with_score(self, consulta, k):
        self.busquedas_por_oracion += 1
        orden, valor = self._orden(consulta)
        return [(self.docs[i], valor(i) / 10007) for i in orden[:k]]


def _preparar_pipeline(monkeypatch, oraciones=True, cupo=10):
    from langchain_community.cross_encoders.base import BaseCrossEncoder

    class Modelo(BaseCrossEncoder):
        def score(self, text_pairs):
            return [(int(texto.split()[-1]) * 7 % 101) / 100 for _, texto in text_pairs]     # distinto para cada fragmento
    monkeypatch.setattr(rc, "_get_reranker_model", lambda nombre: Modelo())
    for nombre, valor in (("USE_RERANKER", True), ("RECUPERACION", "densa"), ("ORACIONES_CIFRAS", oraciones), ("ORACIONES_N", 2), ("ORACIONES_CUPO", cupo)):
        monkeypatch.setattr(cfg_pipeline, nombre, valor)
    return Modelo()


SECCION_SINTETICA = {"id": "7", "texto": "completo", "subsecciones": [
    ("7.1 Montaje", " ".join(f"La medida {i} del tramo {chr(97 + i)} debe verificarse con calibre digital en obra durante el montaje. "
                             f"El responsable de la zona {chr(97 + i)} firma el parte diario de trabajos." for i in range(3))),
    ("7.2 Pruebas", "Se realizará una prueba de carga con 12 toneladas durante 24 horas. El informe de la prueba se entrega firmado por el responsable "
                    "del taller. Los registros se conservan en el archivo de la obra por varios años.")]}


def _claves(docs):
    return [(d.metadata["norma"], d.metadata["articulo"]) for d in docs]


def test_pipeline_y_diagnostico_eligen_los_mismos_articulos_en_el_mismo_orden(monkeypatch):
    modelo = _preparar_pipeline(monkeypatch, cupo=10)       # el diagnóstico mide la variante de cupo 10; las de 8, 6 y 4 están abajo
    db = DbSintetica()
    _, docs_pipeline = rc.recuperar_seccion(db, SECCION_SINTETICA, tope=25, sin_preambulo=True, con_union=True, con_oraciones=True)

    puntuar = lambda consulta, docs: [rc._normalizar_score(s) for s in modelo.score([(consulta, d.page_content) for d in docs])]
    datos = dr.datos_de_consultas(db, dr.consultas_de_seccion(SECCION_SINTETICA), puntuar, total=60)
    oraciones = dr.datos_de_oraciones(db, dr.oraciones_de_seccion(SECCION_SINTETICA))
    por_consulta = [q["candidatos"] for q in datos]
    cfg = CFG["union_oraciones_cifras_N2"]
    assert (cfg.k, cfg.top, cfg.tope, cfg.oraciones, cfg.cupo_oraciones) == (cfg_pipeline.K_SUBSECCION, cfg_pipeline.TOP_N_SUBSECCION, 25, (True, cfg_pipeline.ORACIONES_N), 10)
    docs_diagnostico = dr.seleccion_final(por_consulta, cfg, oraciones)

    assert _claves(docs_pipeline) == _claves(docs_diagnostico)
    base = dr.seleccion_final(por_consulta, CFG["union"])
    assert len(docs_diagnostico) > len(base)                                  # el caso es significativo: las oraciones aportan artículos
    assert _claves(docs_diagnostico)[:len(base)] == _claves(base)


def test_pipeline_con_el_cupo_configurado_coincide_con_la_variante_del_diagnostico(monkeypatch):
    from scripts import config
    modelo = _preparar_pipeline(monkeypatch, cupo=config.ORACIONES_CUPO)
    db = DbSintetica()
    _, docs_pipeline = rc.recuperar_seccion(db, SECCION_SINTETICA, tope=25, sin_preambulo=True, con_union=True, con_oraciones=True)
    puntuar = lambda consulta, docs: [rc._normalizar_score(s) for s in modelo.score([(consulta, d.page_content) for d in docs])]
    datos = dr.datos_de_consultas(db, dr.consultas_de_seccion(SECCION_SINTETICA), puntuar, total=60)
    oraciones = dr.datos_de_oraciones(db, dr.oraciones_de_seccion(SECCION_SINTETICA))
    variante = CFG[f"union_oraciones_cifras_N2_cupo{config.ORACIONES_CUPO}"]
    assert _claves(dr.seleccion_final([q["candidatos"] for q in datos], variante, oraciones)) == _claves(docs_pipeline)


def test_pipeline_extras_son_fragmentos_reales_sin_repetir_la_base_y_con_su_cupo(monkeypatch):
    _preparar_pipeline(monkeypatch, cupo=3)
    db = DbSintetica()
    _, base = rc.recuperar_seccion(db, SECCION_SINTETICA, tope=25, sin_preambulo=True, con_union=True)
    _, con = rc.recuperar_seccion(db, SECCION_SINTETICA, tope=25, sin_preambulo=True, con_union=True, con_oraciones=True)
    extras = con[len(base):]
    assert _claves(con[:len(base)]) == _claves(base) and 0 < len(extras) <= 3
    assert all(d.page_content.startswith("frag") for d in extras)                 # el fragmento recuperado, con su texto, para verificarlo
    assert not set(_claves(extras)) & set(_claves(base)) and len(set(_claves(con))) == len(con)


def test_pipeline_oraciones_encendidas_por_defecto_con_n2_y_cupo8():
    assert (cfg_pipeline.ORACIONES_CIFRAS, cfg_pipeline.ORACIONES_N, cfg_pipeline.ORACIONES_CUPO) == (True, 2, 8)


def test_pipeline_con_oraciones_apagadas_no_busca_ni_cambia_nada(monkeypatch):
    _preparar_pipeline(monkeypatch, oraciones=False)
    db = DbSintetica()
    _, sin = rc.recuperar_seccion(db, SECCION_SINTETICA, tope=25, sin_preambulo=True, con_union=True)
    _, apagado = rc.recuperar_seccion(db, SECCION_SINTETICA, tope=25, sin_preambulo=True, con_union=True, con_oraciones=True)
    assert _claves(apagado) == _claves(sin) and db.busquedas_por_oracion == 0


def test_solo_las_oraciones_con_cifras_se_buscan_en_el_pipeline(monkeypatch):
    _preparar_pipeline(monkeypatch)
    db = DbSintetica()
    rc.recuperar_seccion(db, SECCION_SINTETICA, tope=25, sin_preambulo=True, con_union=True, con_oraciones=True)
    todas = rc.oraciones_de_seccion(SECCION_SINTETICA)
    con_digitos = [o for o in todas if any(c.isdigit() for c in o)]
    assert 0 < len(con_digitos) < len(todas) and db.busquedas_por_oracion == len(con_digitos)    # las oraciones sin dígitos ni se buscan
    datos = rc.consultar_oraciones(db, todas)
    assert [d["con_cifras"] for d in datos] == [any(c.isdigit() for c in o) for o in todas] and not all(d["con_cifras"] for d in datos)
    assert rc.articulos_de_oraciones(datos, True, 2) != rc.articulos_de_oraciones(datos, False, 2)


# --- Perfiles de recuperación (scripts.recuperar) ---

def _selecciones(monkeypatch, perfil, variante):
    from scripts import recuperar
    modelo = _preparar_pipeline(monkeypatch)
    for nombre in cfg_pipeline.PERFILES_RECUPERACION["local"]:       # el monkeypatch restaura lo que aplicar_perfil cambie en config
        monkeypatch.setattr(cfg_pipeline, nombre, getattr(cfg_pipeline, nombre))
    recuperar.aplicar_perfil(perfil)
    db = DbSintetica()
    informe = recuperar.recuperar_secciones(db, [{**SECCION_SINTETICA, "titulos": ["7 Montaje"]}])
    puntuar = lambda consulta, docs: [rc._normalizar_score(s) for s in modelo.score([(consulta, d.page_content) for d in docs])]
    datos = dr.datos_de_consultas(db, dr.consultas_de_seccion(SECCION_SINTETICA), puntuar, total=60)
    oraciones = dr.datos_de_oraciones(db, dr.oraciones_de_seccion(SECCION_SINTETICA))
    esperado = dr.seleccion_final([q["candidatos"] for q in datos], CFG[variante], oraciones)
    return informe[0], esperado


def test_perfil_amplio_elige_los_mismos_articulos_que_union_k20_oraciones_cifras_N2(monkeypatch):
    seccion, esperado = _selecciones(monkeypatch, "amplio", "union_k20_oraciones_cifras_N2")
    assert [(f.norma, f.articulo) for f in seccion.fragmentos] == _claves(esperado) and all(f.parte == 1 for f in seccion.fragmentos)
    c = CFG["union_k20_oraciones_cifras_N2"]
    assert (c.k, c.top, c.top_rr, c.tope, c.oraciones, c.cupo_oraciones) == (20, 5, 8, 30, (True, 2), 10)
    assert {k: v for k, v in cfg_pipeline.PERFILES_RECUPERACION["amplio"].items()} == {
        "K_SUBSECCION": 20, "TOP_DENSA_SUBSECCION": 5, "TOP_N_SUBSECCION": 8, "VERIFICAR_TOPE": 30, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 10}


def test_perfil_local_es_la_configuracion_actual_y_elige_lo_mismo_que_la_variante_cupo8(monkeypatch):
    seccion, esperado = _selecciones(monkeypatch, "local", "union_oraciones_cifras_N2_cupo8")
    assert [(f.norma, f.articulo) for f in seccion.fragmentos] == _claves(esperado)
    assert cfg_pipeline.PERFIL_RECUPERACION_DEFECTO == "local"
    assert cfg_pipeline.PERFILES_RECUPERACION["local"] == {"K_SUBSECCION": 10, "TOP_DENSA_SUBSECCION": 5, "TOP_N_SUBSECCION": 5, "VERIFICAR_TOPE": 25,
                                                           "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}


def test_json_de_solo_recuperacion_lo_puede_leer_nube_con_la_parte(monkeypatch):
    from scripts import nube, recuperar
    seccion, _ = _selecciones(monkeypatch, "amplio", "union_k20_oraciones_cifras_N2")
    datos = recuperar.armar_json("oferta.pdf", [seccion], "amplio", cfg_pipeline.PERFILES_RECUPERACION["amplio"])
    cfg = datos["configuracion_analisis"]
    assert (cfg["modo"], cfg["perfil_recuperacion"], len(cfg["huella_recuperacion"])) == ("solo_recuperacion", "amplio", 64)
    assert cfg["huella_recuperacion"] != recuperar.huella_de("local", cfg_pipeline.PERFILES_RECUPERACION["local"])
    pares = nube.pares_de_json(datos)
    assert len(pares) == len(seccion.fragmentos) and datos["secciones"][0]["fragmentos"][0]["parte"] == 1
    with pytest.raises(ValueError):
        recuperar.aplicar_perfil("inexistente")
