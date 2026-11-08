# tests/test_recuperacion.py
from langchain_core.documents import Document

from scripts import rag_components as rc


def _doc(norma, articulo, score=None, texto="t"):
    metadata = {"norma": norma, "articulo": articulo}
    if score is not None:
        metadata["relevance_score"] = score
    return Document(page_content=texto, metadata=metadata)


def _claves(docs):
    return [(d.metadata["norma"], d.metadata["articulo"]) for d in docs]


def test_duplicado_conserva_el_mejor_score():
    unidos = rc.unir_fragmentos([[_doc("NORM_01", "4.2", 0.3, "bajo")], [_doc("NORM_01", "4.2", 0.9, "alto")]], tope=8)
    assert len(unidos) == 1
    assert unidos[0].metadata["relevance_score"] == 0.9 and unidos[0].page_content == "alto"


def test_misma_norma_distinto_articulo_no_es_duplicado():
    unidos = rc.unir_fragmentos([[_doc("NORM_01", "4.2", 0.5), _doc("NORM_01", "4.3", 0.4), _doc("NORM_02", "4.2", 0.3)]], tope=8)
    assert len(unidos) == 3


def test_ordena_por_score_descendente():
    unidos = rc.unir_fragmentos([[_doc("NORM_01", "1.1", 0.2), _doc("NORM_01", "1.2", 0.8)], [_doc("NORM_02", "2.1", 0.5)]], tope=8)
    assert _claves(unidos) == [("NORM_01", "1.2"), ("NORM_02", "2.1"), ("NORM_01", "1.1")]


def test_tope_se_queda_con_los_de_mayor_score():
    docs = [_doc("NORM_01", f"1.{i}", i / 10) for i in range(1, 7)]
    unidos = rc.unir_fragmentos([docs[:3], docs[3:]], tope=2)
    assert _claves(unidos) == [("NORM_01", "1.6"), ("NORM_01", "1.5")]


def test_sin_scores_conserva_el_orden_de_aparicion():
    unidos = rc.unir_fragmentos([[_doc("NORM_01", "1.1"), _doc("NORM_01", "1.2")], [_doc("NORM_01", "1.1"), _doc("NORM_01", "1.3")]], tope=2)
    assert _claves(unidos) == [("NORM_01", "1.1"), ("NORM_01", "1.2")]


def test_listas_vacias():
    assert rc.unir_fragmentos([], tope=8) == []
    assert rc.unir_fragmentos([[], []], tope=8) == []


# --- Recuperación híbrida (BM25 + densa con RRF) ---

def test_tokenizacion_conserva_numeros_y_codigos_sin_acentos():
    assert rc.tokenizar("Grado IP55 según ISO 4406: tolerancia 1,5 mm; Art. 4.2.") == ["grado", "ip55", "segun", "iso", "4406", "tolerancia", "1,5", "mm", "art", "4.2"]
    assert rc.tokenizar("Hormigón ÁREA") == ["hormigon", "area"] and rc.tokenizar("") == [] and rc.tokenizar(None) == []
    assert rc.tokenizar("Cimentaciones") == ["cimentaciones"]   # sin stemming


def _d(articulo, parte=1, norma="NORM_01"):
    return Document(page_content=articulo, metadata={"norma": norma, "articulo": articulo, "parte": parte})


def _ids(docs):
    return [d.metadata["articulo"] for d in docs]


def test_rrf_con_rankings_conocidos():
    a, b, c, d = _d("A"), _d("B"), _d("C"), _d("D")
    # A: 1/61 + 1/63 = 0,03227; B: 1/62 + 1/61 = 0,03252; C: 1/63; D: 1/62
    assert _ids(rc.fusion_rrf([[a, b, c], [b, d, a]], k_rrf=60)) == ["B", "A", "D", "C"]


def test_rrf_valores_exactos_y_desempate():
    # un documento en el primer lugar de las dos listas le gana a uno que está primero en una sola
    x, y, z = _d("X"), _d("Y"), _d("Z")
    assert _ids(rc.fusion_rrf([[x, y], [x, z]])) == ["X", "Y", "Z"]      # Y y Z empatan (1/62): gana el que apareció primero
    assert _ids(rc.fusion_rrf([[y], [z]])) == ["Y", "Z"]
    assert rc.fusion_rrf([]) == [] and rc.fusion_rrf([[], []]) == []
    # con k = 1: X = 1/2, Y = 1/3, Z = 1/4 + 1/2
    assert _ids(rc.fusion_rrf([[x, y, z], [z]], k_rrf=1)) == ["Z", "X", "Y"]


def test_rrf_no_repite_el_mismo_fragmento_pero_distingue_las_partes():
    uno, dos = _d("A", 1), _d("A", 2)
    assert len(rc.fusion_rrf([[uno, dos], [uno]])) == 2
    assert rc.fusion_rrf([[uno], [Document(page_content="otro objeto", metadata=dict(uno.metadata))]])[0] is uno


class _Chroma:
    """Base vectorial falsa: la búsqueda densa devuelve lo que se le indica; get() entrega todos los fragmentos."""
    def __init__(self, fragmentos, densa):
        self.fragmentos, self.densa = fragmentos, densa

    def get(self, include=None):
        return {"documents": [d.page_content for d in self.fragmentos], "metadatas": [d.metadata for d in self.fragmentos]}

    def as_retriever(self, search_kwargs):
        k = search_kwargs["k"]
        return type("R", (), {"invoke": lambda s, q: self.densa[:k]})()


FRAGMENTOS = [
    Document(page_content="El grado IP55 es obligatorio para los tableros exteriores", metadata={"norma": "NORM_02", "articulo": "3.1", "parte": 1}),
    Document(page_content="La limpieza del aceite hidráulico cumplirá la clase ISO 4406 18/16/13", metadata={"norma": "NORM_03", "articulo": "7.2", "parte": 1}),
    Document(page_content="Los cimientos se hormigonan por etapas", metadata={"norma": "NORM_01", "articulo": "1.1", "parte": 1}),
    Document(page_content="El plazo de curado es de veintiocho días", metadata={"norma": "NORM_01", "articulo": "4.2", "parte": 1}),
]


def test_bm25_encuentra_codigos_exactos_y_el_indice_se_arma_una_vez(monkeypatch):
    db = _Chroma(FRAGMENTOS, [])
    rc._indices_bm25.clear()
    assert _ids(rc.buscar_bm25(db, "tableros IP55", 2)) == ["3.1"]
    assert _ids(rc.buscar_bm25(db, "ISO 4406", 3)) == ["7.2"]          # solo los de puntaje positivo
    assert rc.buscar_bm25(db, "", 3) == [] and rc.buscar_bm25(db, "xyz inexistente", 3) == []
    construidos = []
    original = rc.construir_indice_bm25
    monkeypatch.setattr(rc, "construir_indice_bm25", lambda v: construidos.append(1) or original(v))
    rc.buscar_bm25(db, "curado", 2)
    assert construidos == []                                           # ya estaba en memoria
    assert rc.buscar_bm25(_Chroma([], []), "curado", 2) == []          # base vacía
    rc._indices_bm25.clear()


def test_candidatos_densa_o_hibrida_segun_la_config(monkeypatch):
    rc._indices_bm25.clear()
    densa = [FRAGMENTOS[2], FRAGMENTOS[3], FRAGMENTOS[0]]
    db = _Chroma(FRAGMENTOS, densa)
    monkeypatch.setattr(rc.config, "RECUPERACION", "densa")
    assert _ids(rc.candidatos_de_consulta(db, "grado IP55 en tableros", 3)) == ["1.1", "4.2", "3.1"]
    monkeypatch.setattr(rc.config, "RECUPERACION", "hibrida")
    hibrida = rc.candidatos_de_consulta(db, "grado IP55 en tableros", 3)
    assert _ids(hibrida)[0] == "3.1" and len(hibrida) == 3             # BM25 sube el artículo con el código exacto; el reranker recibe k candidatos
    assert len(rc.candidatos_de_consulta(db, "grado IP55 en tableros", 2)) == 2
    rc._indices_bm25.clear()


# --- Recuperación por defecto: unión de la densa y el reranker (K=10, top 5 + top 5, tope 25) ---

def test_la_recuperacion_por_defecto_es_la_union_k10_top5_top5_tope25():
    from scripts import config
    assert (config.K_SUBSECCION, config.TOP_N_SUBSECCION, config.TOP_DENSA_SUBSECCION, config.VERIFICAR_TOPE) == (10, 5, 5, 25)
    assert config.RECUPERACION == "densa" and config.RECUPERACION_POR_SUBSECCION and config.USE_RERANKER


class _ModeloFalso:
    """Cross-encoder falso: el puntaje de cada fragmento es el número que lleva en el texto."""
    def score(self, pares):
        return [float(texto.split()[-1]) / 100 for _, texto in pares]


def _preparar_reranker(monkeypatch):
    from langchain_community.cross_encoders.base import BaseCrossEncoder

    class Modelo(BaseCrossEncoder):
        def score(self, text_pairs):
            return _ModeloFalso().score(text_pairs)
    monkeypatch.setattr(rc, "_get_reranker_model", lambda nombre: Modelo())
    monkeypatch.setattr(rc.config, "USE_RERANKER", True)
    monkeypatch.setattr(rc.config, "RECUPERACION", "densa")


def _db_diez():
    # densa: a0..a9; el reranker prefiere los últimos (a9 el mejor)
    docs = [Document(page_content=f"texto {i}", metadata={"norma": "N", "articulo": f"a{i}", "parte": 1}) for i in range(10)]
    return _Chroma(docs, docs)


def test_union_agrega_el_top_denso_al_top_del_reranker(monkeypatch):
    _preparar_reranker(monkeypatch)
    candidatos, docs = rc.recuperar_con_candidatos(_db_diez(), "q", 10, 5, top_densa=5)
    assert len(candidatos) == 10
    assert _ids(docs) == ["a9", "a8", "a7", "a6", "a5", "a4", "a3", "a2", "a1", "a0"]      # los 5 del reranker + los 5 primeros de la densa, por puntaje
    assert all("relevance_score" in d.metadata for d in docs)                                  # todos llevan puntaje del reranker
    _, solo_reranker = rc.recuperar_con_candidatos(_db_diez(), "q", 10, 5)
    assert _ids(solo_reranker) == ["a9", "a8", "a7", "a6", "a5"]


def test_union_sin_repetidos_cuando_los_dos_criterios_coinciden(monkeypatch):
    _preparar_reranker(monkeypatch)
    docs = [Document(page_content=f"texto {10 - i}", metadata={"norma": "N", "articulo": f"b{i}", "parte": 1}) for i in range(6)]   # el reranker coincide con la densa
    _, final = rc.recuperar_con_candidatos(_Chroma(docs, docs), "q", 6, 3, top_densa=3)
    assert _ids(final) == ["b0", "b1", "b2"]


def test_recuperar_seccion_con_union_aplica_top_densa_y_el_tope_por_seccion(monkeypatch):
    _preparar_reranker(monkeypatch)
    seccion = {"texto": "x" * 400, "subsecciones": [("1 Tema", "x" * 400)]}
    _, sin = rc.recuperar_seccion(_db_diez(), seccion, tope=25, sin_preambulo=True)
    _, con = rc.recuperar_seccion(_db_diez(), seccion, tope=25, sin_preambulo=True, con_union=True)
    assert len(sin) == 5 and len(con) == 10
    _, acotada = rc.recuperar_seccion(_db_diez(), seccion, tope=7, sin_preambulo=True, con_union=True)
    assert _ids(acotada) == ["a9", "a8", "a7", "a6", "a5", "a4", "a3"]


def test_main_pide_la_union_solo_en_modo_verificacion():
    import inspect
    from scripts import main
    codigo = inspect.getsource(main._analizar_por_secciones)
    assert '"con_union": True} if verificacion else {}' in codigo
