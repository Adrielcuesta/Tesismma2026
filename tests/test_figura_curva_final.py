"""Figura final de la curva de recuperación (evaluacion/figura_curva_final.py) sobre CSV armados a mano (sin modelos)."""
import csv

import numpy as np
import pytest

from evaluacion import figura_curva_final as F

COLUMNAS = ["embedding", "variante", "k", "oraciones_n", "oraciones_cupo", "tope", "pares", "hits_trampas", "n_trampas", "recall_trampas", "ic_trampas_inf", "ic_trampas_sup"]


def _fila(k, pares, hits, variante="densa", cupo="8", embedding="bge-m3"):
    return {"embedding": embedding, "variante": variante, "k": k, "oraciones_n": "2", "oraciones_cupo": cupo, "tope": "1000000", "pares": pares, "hits_trampas": hits, "n_trampas": 30,
            "recall_trampas": hits / 30, "ic_trampas_inf": max(0, hits / 30 - 0.1), "ic_trampas_sup": min(1, hits / 30 + 0.05)}


# K: pares y trampas encontradas (la curva sube rápido, se aplana y la última trampa aparece recién en K=200)
PUNTOS = [(1, 230, 17), (2, 290, 21), (3, 340, 23), (5, 440, 24), (6, 490, 25), (10, 680, 27), (15, 890, 28), (20, 1100, 28), (35, 1690, 29), (50, 2200, 29), (100, 3800, 29),
          (150, 5100, 29), (200, 6200, 30), (410, 8000, 30)]


def _csv(tmp_path, puntos=PUNTOS, extras=()):
    ruta = tmp_path / "curva.csv"
    filas = [_fila(*p) for p in puntos] + [_fila(10, 999, 1)] + list(extras)          # K=10 repetido (la grilla de oraciones lo repite) y otras variantes
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter=";")
        w.writeheader()
        w.writerows(filas)
    return str(ruta)


def test_la_serie_toma_solo_denso_de_bge_m3_sin_repetidos_y_ordenada(tmp_path):
    ruta = _csv(tmp_path, extras=[_fila(7, 1, 1, variante="union"), _fila(7, 1, 1, embedding="otro"), _fila(7, 1, 1, cupo="15")])
    serie = F.leer_serie(ruta)
    assert [r["k"] for r in serie] == [p[0] for p in PUNTOS] and next(r for r in serie if r["k"] == 10)["pares"] == 680       # gana la primera fila de K=10
    with pytest.raises(SystemExit, match="No hay filas"):
        F.leer_serie(ruta, {**F.SERIE, "embedding": "no_existe"})


def test_ajuste_recupera_los_parametros_de_una_curva_exacta():
    p = np.geomspace(200, 8000, 40)
    ajuste = F.ajustar(p, 1 - 0.9 * p ** (-0.12))
    assert ajuste["a"] == pytest.approx(0.9, rel=1e-3) and ajuste["b"] == pytest.approx(0.12, rel=1e-3) and ajuste["r2"] == pytest.approx(1.0, abs=1e-9) and ajuste["n"] == 40
    assert F.recall_ajustado(ajuste, [1000])[0] == pytest.approx(1 - 0.9 * 1000 ** -0.12)
    assert F.pares_para_recall(ajuste, 0.95) == pytest.approx((0.9 / 0.05) ** (1 / 0.12), rel=1e-3) and F.pares_para_recall(ajuste, 1.0) is None


def test_ganancia_marginal_regla_del_umbral_y_codo(tmp_path):
    serie = F.leer_serie(_csv(tmp_path))
    g = F.ganancia_marginal(serie)
    assert g[0] is None and g[1] == pytest.approx(4 / 0.6)             # +4 trampas con 60 pares extra, por cada 100
    assert F.k_por_umbral(serie) == 10                                 # tras K=10 los tres pasos siguientes (15, 20 y 35) suman menos de 0,5 trampas por cada 100 pares
    assert F.k_codo(serie) in {r["k"] for r in serie} and F.k_codo(serie[:1]) is None


def test_primera_fila_que_llega_y_pares_interpolados(tmp_path):
    serie = F.leer_serie(_csv(tmp_path))
    assert F.primera_fila_con(serie, 28)["k"] == 15 and F.primera_fila_con(serie, 30)["k"] == 200 and F.primera_fila_con(serie, 31) is None
    assert F.pares_en_k(serie, 15) == (890, False)
    pares, interpolado = F.pares_en_k(serie, 175)
    assert interpolado and pares == pytest.approx(5100 + 0.5 * (6200 - 5100)) and F.pares_en_k(serie, 1000) is None


def test_la_cola_calcula_pares_razon_y_marca_lo_extrapolado(tmp_path):
    serie = F.leer_serie(_csv(tmp_path))
    ajuste = F.ajustar([r["pares"] for r in serie], [r["recall"] for r in serie])
    c = F.cola(serie, ajuste)
    assert (c["p28"]["pares"], c["p29"]["pares"], c["p30"]["pares"]) == (890, 1690, 6200) and not any(c[k]["extrapolado"] for k in ("p28", "p29", "p30"))
    assert c["razon"] == pytest.approx(6200 / 890) and c["incremental"] == pytest.approx((6200 - 890) / 890) and c["p30_puesto"]["interpolado"] and c["razon_puesto"] < c["razon"]
    frase = F.frase_tribunal(c)
    assert "890 pares" in frase and "6.200 pares" in frase and "7,0 veces" in frase and "extrapolado" not in frase
    sin_ultima = F.leer_serie(_csv(tmp_path, [p for p in PUNTOS if p[2] < 30]))
    c2 = F.cola(sin_ultima, F.ajustar([r["pares"] for r in sin_ultima], [r["recall"] for r in sin_ultima]))
    assert c2["p30"]["extrapolado"] and c2["p30"]["k"] is None and c2["p30"]["pares"] >= sin_ultima[-1]["pares"] and c2["p30_puesto"] is None
    assert "extrapolado con el ajuste" in F.frase_tribunal(c2)


# --- Factores ---

def _tabla(tmp_path, filas):
    ruta = tmp_path / "tabla.csv"
    campos = ["configuracion", "conjunto", "ofertas", "pares_por_oferta", "tiempo_s", "costo_usd"]
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        w.writerows([{**{c: "" for c in campos}, **x} for x in filas])
    return str(ruta)


def test_los_factores_salen_de_la_tabla_con_el_conjunto_mas_amplio(tmp_path):
    ruta = _tabla(tmp_path, [
        {"configuracion": "gpt-oss-120b esfuerzo bajo (elegida)", "conjunto": "dev", "ofertas": "P1+P2", "pares_por_oferta": 300, "costo_usd": 0.2},
        {"configuracion": "gpt-oss-120b esfuerzo bajo (elegida)", "conjunto": "total", "ofertas": "P1+P2+P3+P4", "pares_por_oferta": 250, "costo_usd": 0.5},
        {"configuracion": "qwen3:8b local (elegida)", "conjunto": "total", "ofertas": "P1+P2+P3+P4", "pares_por_oferta": 250, "tiempo_s": "0"},       # sin tiempo: no sirve
        {"configuracion": "qwen3:8b local", "conjunto": "total", "ofertas": "P1+P2+P3+P4", "pares_por_oferta": 240, "tiempo_s": 19200},
        {"configuracion": "Qwen3-32B (elegida)", "conjunto": "prueba", "ofertas": "P3+P4", "pares_por_oferta": 300}])
    f = F.factores(ruta)
    assert f["usd"][0] == pytest.approx(0.5 / 1000) and "gpt-oss" in f["usd"][1] and "total" in f["usd"][1]
    assert f["seg"][0] == pytest.approx(19200 / 960) and "«qwen3:8b local»" in f["seg"][1]
    assert f["pares_validacion"][0] == 600
    forzado = F.factores(ruta, usd_arg=0.01, seg_arg=30)
    assert forzado["usd"] == (0.01, "argumento --usd-por-par") and forzado["seg"][0] == 30


def test_sin_datos_en_la_tabla_se_usan_los_valores_por_defecto_y_el_md_lo_dice(tmp_path):
    f = F.factores(str(tmp_path / "no_existe.csv"))
    assert f["usd"][0] == F.USD_POR_PAR_DEFECTO and f["seg"][0] == F.SEG_POR_PAR_DEFECTO and "por defecto" in f["usd"][1] and "por defecto" in f["seg"][1] and f["pares_validacion"] is None


# --- Figura e informe ---

def test_generar_escribe_png_a_300_dpi_y_md_con_la_frase(tmp_path):
    pytest.importorskip("matplotlib")
    r = F.generar(_csv(tmp_path), str(tmp_path / "no_existe.csv"), str(tmp_path / "salida"))
    from matplotlib import image
    assert image.imread(r["png"]).shape[1] > 5000                       # 21 pulgadas a 300 dpi
    md = open(r["md"], encoding="utf-8").read()
    assert "## Frase para el tribunal" in md and "valor por defecto" in md and "## Ajuste" in md and "R² =" in md and "configuración elegida" in md and "26/30" in md
    assert "Regla marginal calculada aquí: K = " in md and r["figura"]["rotulados"] > 0 and r["ajuste"]["r2"] > 0.8


def test_con_otro_embedding_se_grafica_su_serie_sin_la_elegida_ni_el_puesto_175(tmp_path):
    pytest.importorskip("matplotlib")
    ruta = _csv(tmp_path, extras=[_fila(k, p + 100, h, embedding="gemini__gemini-embedding-2-3072") for k, p, h in PUNTOS])
    assert F.sufijo_de("bge-m3") == "" and F.sufijo_de("gemini__gemini-embedding-2-3072") == "_gemini"
    r = F.generar(ruta, str(tmp_path / "no_existe.csv"), str(tmp_path / "salida"), embedding="gemini__gemini-embedding-2-3072")
    assert r["png"].endswith("figura_curva_final_gemini.png") and r["md"].endswith("figura_curva_final_gemini.md") and r["serie"][0]["pares"] == 330
    md = open(r["md"], encoding="utf-8").read()
    assert "(gemini__gemini-embedding-2-3072)" in md and "no se dibujan con otro embedding" in md and "configuración elegida** (constante)" not in md and "en el puesto exacto" not in md
    assert r["cola"]["p30_puesto"] is None and "Con gemini__gemini-embedding-2-3072 en modo solo denso" in md and "K propios" not in md
    assert set(F.ks_de_referencia(r["serie"], "gemini__x")) <= {r2["k"] for r2 in r["serie"]} and F.ks_de_referencia(r["serie"], "bge-m3") == F.K_REFERENCIA
    con_bge = F.generar(ruta, str(tmp_path / "no_existe.csv"), str(tmp_path / "salida2"))
    assert con_bge["png"].endswith("figura_curva_final.png") and "en el puesto exacto 175" in open(con_bge["md"], encoding="utf-8").read()


def test_los_rotulos_de_k_no_se_pisan():
    plt = pytest.importorskip("matplotlib.pyplot")
    F._plt()
    fig, eje = plt.subplots(figsize=(8, 5))
    puntos = [(100 + 3 * i, 0.5 + 0.004 * i, str(i), i) for i in range(1, 30)]
    eje.set_xlim(90, 220)
    eje.set_ylim(0.45, 0.7)
    fig.canvas.draw()
    puestos = F.etiquetar_puntos(fig, eje, puntos)
    renderer = fig.canvas.get_renderer()
    cajas = [t.get_window_extent(renderer) for t in eje.texts]
    assert len(cajas) == puestos > 0 and not any(a.overlaps(b) for i, a in enumerate(cajas) for b in cajas[i + 1:])
    plt.close(fig)
