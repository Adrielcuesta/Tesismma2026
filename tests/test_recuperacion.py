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
