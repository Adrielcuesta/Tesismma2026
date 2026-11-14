"""Figura de los embeddings (evaluacion/figura_embeddings.py) sobre un CSV armado a mano (sin modelos)."""
import csv

import pytest

from evaluacion import figura_embeddings as FE

COLUMNAS = ["embedding", "variante", "k", "oraciones_n", "oraciones_cupo", "tope", "pares", "hits_trampas", "n_trampas", "recall_trampas", "ic_trampas_inf", "ic_trampas_sup"]
KS = (1, 2, 3, 5, 10, 15, 25, 50, 100, 200, 410)


def _filas(embedding, escala, hits, variante="densa"):
    return [{"embedding": embedding, "variante": variante, "k": k, "oraciones_n": "2", "oraciones_cupo": "8", "tope": "1000000", "pares": int(200 + escala * k * 15),
             "hits_trampas": h, "n_trampas": 30, "recall_trampas": h / 30, "ic_trampas_inf": max(0, h / 30 - 0.1), "ic_trampas_sup": min(1, h / 30 + 0.05)} for k, h in zip(KS, hits)]


def _csv(tmp_path):
    ruta = tmp_path / "curva.csv"
    filas = (_filas("gemini__gemini-embedding-2-3072", 1.0, [18, 22, 24, 26, 28, 28, 29, 29, 30, 30, 30])
             + _filas("bge-m3", 1.2, [17, 21, 23, 24, 27, 28, 28, 29, 29, 30, 30])
             + _filas("deepinfra__Qwen-Qwen3-Embedding-8B", 0.9, [15, 20, 22, 24, 26, 27, 28, 28, 29, 29, 30])
             + _filas("bge-m3", 1.0, [1] * 11, variante="union"))                    # otras variantes no entran
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter=";")
        w.writeheader()
        w.writerows(filas)
    return str(ruta)


def test_los_embeddings_salen_del_csv_con_bge_m3_primero_y_nombres_cortos(tmp_path):
    ruta = _csv(tmp_path)
    assert FE.embeddings_del_csv(ruta) == ["bge-m3", "gemini__gemini-embedding-2-3072", "deepinfra__Qwen-Qwen3-Embedding-8B"]
    assert [FE.nombre_corto(e) for e in FE.embeddings_del_csv(ruta)] == ["BGE-M3", "gemini-embedding-2-3072", "Qwen3-Embedding-8B"]
    s = FE.series(ruta)
    assert list(s) == FE.embeddings_del_csv(ruta) and all(len(v) == len(KS) for v in s.values()) and s["bge-m3"][0]["hits"] == 17


def test_el_auc_es_el_de_scripts_curva_recuperacion():
    cv = pytest.importorskip("scripts.curva_recuperacion")
    serie = [{"k": k, "recall": h / 30} for k, h in zip(KS, [17, 21, 23, 24, 27, 28, 28, 29, 29, 30, 30])]
    assert FE.auc_log(serie) == pytest.approx(cv.auc_log([{"k": r["k"], "recall_trampas": r["recall"]} for r in serie]))
    assert FE.auc_log([{"k": 1, "recall": 0.5}] * 2) == 0.5 and FE.auc_log([{"k": 4, "recall": 0.7}]) == 0.7


def test_generar_escribe_un_png_a_300_dpi_con_los_tres_embeddings_y_su_auc(tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    leyendas = []
    from matplotlib.axes import Axes
    original = Axes.legend

    def espia(self, *a, **k):
        leg = original(self, *a, **k)
        leyendas.extend(t.get_text() for t in leg.get_texts())
        return leg

    monkeypatch.setattr(Axes, "legend", espia)
    r = FE.generar(_csv(tmp_path), str(tmp_path / "salida"))
    from matplotlib import image
    assert r["png"].endswith("figura_embeddings.png") and image.imread(r["png"]).shape[1] >= 3600       # 12 pulgadas a 300 dpi
    assert set(r["auc"]) == {"bge-m3", "gemini__gemini-embedding-2-3072", "deepinfra__Qwen-Qwen3-Embedding-8B"} and all(0.5 < v <= 1 for v in r["auc"].values())
    texto = " | ".join(leyendas)
    assert all(f"AUC = {FE.F._n(v, 3)}" in texto for v in r["auc"].values()) and "Configuración elegida (BGE-M3): 28/30 con 721 pares" in texto and "K = 10 en cada serie" in texto


def test_sin_bge_m3_no_se_dibuja_la_elegida(tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    leyendas = []
    from matplotlib.axes import Axes
    original = Axes.legend

    def espia(self, *a, **k):
        leg = original(self, *a, **k)
        leyendas.extend(t.get_text() for t in leg.get_texts())
        return leg

    monkeypatch.setattr(Axes, "legend", espia)
    FE.generar(_csv(tmp_path), str(tmp_path / "salida"), ["gemini__gemini-embedding-2-3072"])
    assert not any("elegida" in t for t in leyendas)
