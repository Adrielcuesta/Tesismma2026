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


# --- Dónde se pierde el artículo (K, top, tope) ---

from langchain_core.documents import Document


def _doc(norma, articulo):
    return Document(page_content=f"{norma} {articulo}", metadata={"norma": norma, "articulo": articulo})


def _candidatos(*pares_y_puntajes):
    """Lista [(doc, puntaje)] en el orden de la densa."""
    return [(_doc(n, a), p) for (n, a), p in pares_y_puntajes]


def test_seleccion_final_respeta_k_top_n_y_tope():
    # orden de la densa: A, B, C, D (puntajes del reranker 0,1 / 0,9 / 0,5 / 0,8)
    cands = _candidatos((("N", "A"), 0.1), (("N", "B"), 0.9), (("N", "C"), 0.5), (("N", "D"), 0.8))
    claves = lambda docs: [d.metadata["articulo"] for d in docs]
    assert claves(dr.seleccion_final([cands], k=2, top_n=5, tope=15)) == ["B", "A"]          # K=2: C y D ni se consideran
    assert claves(dr.seleccion_final([cands], k=4, top_n=2, tope=15)) == ["B", "D"]          # top_n=2 tras el reranker
    assert claves(dr.seleccion_final([cands], k=4, top_n=4, tope=3)) == ["B", "D", "C"]      # tope por sección
    # preámbulo ocupa un lugar del top_n y después se descarta
    con_preambulo = _candidatos((("N", "preambulo"), 0.95), (("N", "B"), 0.9), (("N", "C"), 0.5))
    assert claves(dr.seleccion_final([con_preambulo], k=3, top_n=2, tope=15)) == ["B"]


def test_seleccion_final_une_consultas_por_articulo_con_el_mayor_puntaje():
    c1 = _candidatos((("N", "A"), 0.2), (("N", "B"), 0.6))
    c2 = _candidatos((("N", "A"), 0.7))
    assert [d.metadata["articulo"] for d in dr.seleccion_final([c1, c2], 10, 5, 15)] == ["A", "B"]


def test_reranker_corre_una_sola_vez_y_los_puntajes_alcanzan_para_las_tres_configuraciones():
    class Db:
        def as_retriever(self, search_kwargs):
            k = search_kwargs["k"]
            return type("R", (), {"invoke": lambda s, q: [_doc("N", str(i)) for i in range(1, 31)][:k]})()
    llamadas = []
    def puntuar(consulta, docs):
        llamadas.append(len(docs))
        return [1 - i / 100 for i in range(len(docs))]         # el puntaje sigue el orden de la densa
    por_consulta = dr.candidatos_con_puntaje(Db(), ["q1", "q2"], puntuar)
    assert llamadas == [30, 30] and [len(c) for c in por_consulta] == [30, 30]    # una llamada por consulta, con los 30 candidatos
    finales = {n: len(dr.seleccion_final(por_consulta, k, top, tope)) for n, k, top, tope in dr.CONFIGURACIONES}
    assert finales == {"actual": 5, "media": 8, "amplia": 10}                      # ambas consultas devuelven los mismos artículos


def test_consultas_de_seccion_usa_las_subsecciones_largas_o_la_seccion_entera():
    larga = "x" * (dr.config.MIN_CHARS_SUBSECCION + 5)
    assert dr.consultas_de_seccion({"texto": "t", "subsecciones": [("a", larga), ("b", "corta")]}) == [larga]
    assert dr.consultas_de_seccion({"texto": "texto entero", "subsecciones": [("b", "corta")]}) == ["texto entero"]


def test_analizar_recorte_puestos_entrada_y_pares_por_oferta():
    secciones = [{"id": "3", "texto": "Los tableros exteriores tendrán grado IP44 de protección.", "subsecciones": []},
                 {"id": "4", "texto": "El curado previo a la puesta en carga será de 14 días.", "subsecciones": []}]
    # sección 3: el artículo de la trampa está 3.º en la densa y 3.º tras el reranker -> entra con actual (top 5)
    s3 = [_candidatos(*[(("NORM_09", f"x{i}"), 0.9 - i / 10) for i in range(2)], (("NORM_02", "3.1"), 0.5))]
    # sección 4: está 12.º en la densa (fuera de K=10) y tiene el mejor puntaje -> entra con media (K=20) y amplia, no con actual
    relleno = [(("NORM_09", f"y{i}"), 0.3) for i in range(11)]
    s4 = [_candidatos(*relleno, (("NORM_01", "4.9"), 0.99))]
    filas, pares = dr.analizar_recorte("P1", TRAMPAS, secciones, [s3, s4])
    f1, f2, f3 = filas
    assert (f1["puesto_densa"], f1["puesto_reranker"], f1["entra"]) == (3, 3, {"actual": True, "media": True, "amplia": True})
    assert (f2["puesto_densa"], f2["puesto_reranker"], f2["entra"]) == (12, 1, {"actual": False, "media": True, "amplia": True})   # equivalente NORM_01 4.9
    assert (f3["seccion"], f3["puesto_densa"], f3["entra"]) == (None, None, {"actual": False, "media": False, "amplia": False})
    assert pares == {"actual": 3 + 5, "media": 3 + 8, "amplia": 3 + 10}


def _fila(entra_actual, entra_media, entra_amplia):
    return {"id": "t", "entra": {"actual": entra_actual, "media": entra_media, "amplia": entra_amplia}}


def test_regla_de_adopcion_del_recorte():
    def filas(base, media, amplia):
        return [_fila(i < base, i < media, i < amplia) for i in range(30)]
    assert dr.decision_recorte(filas(13, 19, 25))["adopta"] == "media"        # +6 con la media: la más chica que lo logra
    assert dr.decision_recorte(filas(13, 18, 19))["adopta"] == "amplia"       # la media sube 5, la amplia 6
    assert dr.decision_recorte(filas(13, 18, 18))["adopta"] is None           # ninguna llega a +6: queda la actual
    d = dr.decision_recorte(filas(13, 14, 16))
    assert d["adopta"] is None and d["recall"] == {"actual": 13, "media": 14, "amplia": 16} and d["n"] == 30


def test_informe_recorte_tabla_recall_pares_y_decision():
    filas = [{"id": "P1-01", "oferta": "P1", "seccion": "3", "articulo": "NORM_02 3.1", "puesto_densa": 12, "puesto_reranker": 1,
              "entra": {"actual": False, "media": True, "amplia": True}},
             {"id": "P1-02", "oferta": "P1", "seccion": "4", "articulo": "NORM_01 4.2", "puesto_densa": None, "puesto_reranker": None,
              "entra": {"actual": False, "media": False, "amplia": False}}]
    texto = dr.informe_recorte(filas, {"P1": {"actual": 40, "media": 60, "amplia": 80}, "P2": {"actual": 30, "media": 50, "amplia": 70}})
    assert "P1-01" in texto and "fuera" in texto and "actual  (10, 5, 15): 0/2 (0%)" in texto and "amplia  (30, 10, 40): 1/2 (50%)" in texto
    assert "P1: actual 40, media 60, amplia 80" in texto and "total: actual 70, media 110, amplia 150" in texto
    assert "MANTENER la actual" in texto
