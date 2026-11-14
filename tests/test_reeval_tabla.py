"""Fase 3: comparabilidad de la recuperación, embudo de la reevaluación, antes/después, diferencia contra v1 y gráficos de criticidad y confusión (sin red ni modelos)."""
import json
import os

import pytest

from evaluacion import evaluar as ev
from evaluacion import tabla_comparativa as tc

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GT = [
    {"id": "P9-01-A", "oferta": "P9", "seccion": "3 Plazos", "fragmento_trampa": "plazo de 14 dias", "norma": "NORM_01", "articulo": "4.2", "articulos_equivalentes": "",
     "clase": "Crítico", "nivel": "Alto", "responsable": "G1"},
    {"id": "P9-02-M", "oferta": "P9", "seccion": "4 Montaje", "fragmento_trampa": "montaje en 3 dias", "norma": "NORM_01", "articulo": "5.1", "articulos_equivalentes": "",
     "clase": "Mayor", "nivel": "Medio", "responsable": "G2"},
    {"id": "P9-03-B", "oferta": "P9", "seccion": "5 Pruebas", "fragmento_trampa": "pruebas sin acta", "norma": "NORM_02", "articulo": "1.1", "articulos_equivalentes": "",
     "clase": "Menor", "nivel": "Bajo", "responsable": "G3"},
    {"id": "P9-04-A", "oferta": "P9", "seccion": "6 Entrega", "fragmento_trampa": "entrega parcial", "norma": "NORM_02", "articulo": "2.2", "articulos_equivalentes": "",
     "clase": "Mayor", "nivel": "Alto", "responsable": "G2"},
]
SECCION = {"01": "3", "02": "4", "03": "5", "04": "6"}
CONFORMES = [{"proyecto": "Proyecto 9", "seccion": "3", "cita_conforme": "El plazo de entrega es de 28 dias", "norma": "NORM_01", "articulo": "4.2", "espejo_de_trampa": "P9-01-A"}]


def _resultado(encontradas, revisadas, clases=None):
    """Resultado de un LLM: brechas para las trampas `encontradas` y una verificación (Cumple) para cada trampa `revisadas`: lo que no se revisó es el gris."""
    clases = clases or {}
    por_id = {t["id"][3:5]: t for t in GT}
    brechas = [{"seccion": SECCION[k], "seccion_oferta": por_id[k]["seccion"], "norma": por_id[k]["norma"], "articulo": por_id[k]["articulo"], "cita": f"Se indica {por_id[k]['fragmento_trampa']}.",
                "clase": clases.get(k, por_id[k]["clase"]), "nivel": por_id[k]["nivel"], "responsable": por_id[k]["responsable"]} for k in encontradas]
    registro = [{"seccion": SECCION[k], "norma": por_id[k]["norma"], "articulo": por_id[k]["articulo"], "veredicto": "Incumple" if k in encontradas else "Cumple"} for k in revisadas]
    return {"registro_brechas": brechas, "riesgos": [{}], "solicitudes": [], "alertas": [], "registro_tecnico": registro}


def _evaluado(encontradas, revisadas, pares=(("3", "NORM_01", "4.2"),), embedding="bge-m3", k=10, clases=None, costo=None):
    e = ev.evaluar(_resultado(encontradas, revisadas, clases), [dict(t) for t in GT], [dict(c) for c in CONFORMES], "P9")
    secciones = [{"id": s, "fragmentos": [{"norma": n, "articulo": a, "score": 0.5, "parte": 1}]} for s, n, a in pares]
    e["recuperacion"] = tc.info_recuperacion({"secciones": secciones, "configuracion_analisis": {"embedding_backend": embedding, "k_subseccion": k, "top_n_subseccion": 5, "top_densa_subseccion": 5,
                                                                                                   "tope_fragmentos_por_seccion": 25}})
    e["costo"] = costo
    return e


A = _evaluado({"01", "02"}, {"01", "02", "03"})                 # gris: la 04
B = _evaluado({"01"}, {"01", "02", "03"})                       # gris: la 04 (misma recuperación, otro LLM)
C = _evaluado({"01"}, {"01", "02"}, pares=(("3", "NORM_01", "4.2"), ("4", "NORM_01", "5.1")))     # gris: la 03 y la 04
CONJUNTOS = {"P9 solo": ["P9"]}


def _filas(**configs):
    return tc.calcular_filas({n: {"P9": e} for n, e in configs.items()}, CONJUNTOS)


# --- Funciones puras ---

def test_sutileza_por_sufijo_del_id():
    assert [tc.sutileza_de(i) for i in ("P1-01-A", "P3-12-M", "P4-05-B", "P1-01", "xyz-Q")] == ["alto", "medio", "bajo", None, None]


def test_errores_por_sutileza_y_por_clase_sobre_un_fixture_conocido():
    trampas = ev.combinar([A])["trampas"]
    assert tc.errores_por(trampas, lambda t: tc.sutileza_de(t["id"]), tc.ORDEN_SUTILEZA) == [("alto", 2, 1), ("medio", 1, 0), ("bajo", 1, 1)]
    assert tc.errores_por(trampas, lambda t: t["clase_esperada"], ev.CLASES) == [("Crítico", 1, 0), ("Mayor", 2, 1), ("Menor", 1, 1)]
    assert tc.errores_por([], lambda t: 1, ("a",)) == []


def test_matriz_de_confusion_clase_esperada_por_asignada():
    m = tc.matriz_de_confusion({("Crítico", "Crítico"): 3, ("Mayor", "Menor"): 1, ("Mayor", "Mayor"): 2, ("Menor", None): 1, ("Menor", "Crítico"): 1, ("Otra", "Mayor"): 9})
    assert m == [[3, 0, 0, 0], [0, 2, 1, 0], [1, 0, 0, 1]]
    d = _evaluado({"01", "02", "03"}, {"01", "02", "03"}, clases={"03": "Mayor"})
    assert tc.matriz_de_confusion(d["confusion"]) == [[1, 0, 0, 0], [0, 1, 0, 0], [0, 1, 0, 0]]


def test_info_de_recuperacion_sale_de_las_secciones_del_json_y_no_depende_de_los_puntajes():
    a = tc.info_recuperacion({"secciones": [{"id": "3", "fragmentos": [{"norma": "N", "articulo": "1", "score": 0.1, "parte": 1}]}]})
    b = tc.info_recuperacion({"secciones": [{"id": "3", "fragmentos": [{"norma": "N", "articulo": "1", "score": 0.9, "parte": 1}]}],
                              "configuracion_analisis": {"embedding_backend": "gemini", "k_subseccion": 100, "recuperacion_json_sha256": "ab" * 32}})
    assert a["huella_pares"] == b["huella_pares"] and a["pares"] == 1 and a["embedding"] == "bge-m3" and b["embedding"] == "gemini" and b["sha256"] == "ab" * 32
    assert tc.info_recuperacion({})["pares"] == 0


def test_la_recuperacion_de_un_json_que_reuso_otra_sale_del_json_de_recuperacion(tmp_path):
    rec = tmp_path / "P1" / "recuperacion_elegido_P1.json"
    rec.parent.mkdir()
    rec.write_text(json.dumps({"configuracion_analisis": {"perfil_recuperacion": "elegido", "embedding_backend": "bge-m3", "k_subseccion": 10, "top_n_subseccion": 2, "top_densa_subseccion": 10,
                                                          "tope_fragmentos_por_seccion": 39}}), encoding="utf-8")
    secciones = [{"id": "3", "fragmentos": [{"norma": "N", "articulo": "1", "score": 0.1, "parte": 1}]}]
    # el JSON de la corrida local guardó los parámetros del perfil por defecto (TOP_N=5, TOP_DENSA=5, tope 25) aunque reusó la recuperación elegida
    local = {"secciones": secciones, "configuracion_analisis": {"k_subseccion": 10, "top_n_subseccion": 5, "top_densa_subseccion": 5, "tope_fragmentos_por_seccion": 25,
                                                                 "recuperacion_json_sha256": tc.huella_recuperacion.sha256_archivo(str(rec))}}
    info = tc.info_recuperacion(local, str(tmp_path))
    d = tc.descripcion_recuperacion(info)
    assert (info["top_n"], info["top_densa"], info["tope"], info["perfil"]) == (2, 10, 39, "elegido") and "TOP_N=2" in d and "TOP_DENSA=10" in d and "tope=39" in d and "tope=25" not in d
    assert tc.info_recuperacion(local)["tope"] == 25                                                   # sin carpeta no busca: queda lo que guardó el JSON
    otro = {**local, "configuracion_analisis": {**local["configuracion_analisis"], "recuperacion_json_sha256": "00" * 32}}
    assert tc.info_recuperacion(otro, str(tmp_path))["tope"] == 25                                     # sha256 que no está: queda lo que guardó el JSON


def test_descripcion_de_la_recuperacion_dice_embedding_y_k():
    d = tc.descripcion_recuperacion(A["recuperacion"])
    assert "embedding bge-m3" in d and "K_SUBSECCION=10" in d and "TOP_N=5" in d and "tope=25" in d and tc.descripcion_recuperacion(None) == "n/d"


def test_aviso_de_comparabilidad_cuando_las_huellas_difieren():
    evaluadas = {"a": {"P9": A}, "b": {"P9": B}, "c": {"P9": C}}
    assert tc.aviso_comparabilidad(evaluadas, ["a", "b"], ["P9"]) == ""                      # mismos pares
    assert "recuperaciones distintas" in tc.aviso_comparabilidad(evaluadas, ["a", "b", "c"], ["P9"]) and "P9" in tc.aviso_comparabilidad(evaluadas, ["a", "c"], ["P9"])
    assert tc.aviso_comparabilidad({"a": {"P9": ev.evaluar(_resultado({"01"}, {"01"}), GT, [], "P9")}}, ["a"], ["P9"]) == ""      # sin datos de recuperación no hay aviso
    md = "\n".join(tc.seccion_comparabilidad_md(evaluadas, CONJUNTOS))
    assert "## Comparabilidad de la recuperación" in md and "AVISO (P9 solo, P9)" in md and A["recuperacion"]["huella_pares"][:10] in md
    sin_aviso = "\n".join(tc.seccion_comparabilidad_md({"a": {"P9": A}, "b": {"P9": B}}, CONJUNTOS))
    assert "AVISO" not in sin_aviso


# --- Diferencia contra v1 ---

def test_diferencias_contra_v1_en_numeros_y_en_la_tabla():
    filas = _filas(elegida=A, v1=C)
    (d,) = tc.diferencias_v1(filas, {"elegida": "v1"})
    assert (d["d_encontradas"], d["d_no_recuperadas"], d["d_brechas_total"], d["d_falsas_alarmas"]) == (1, -1, 1, 0)
    assert d["d_recall"] == pytest.approx(0.25) and d["d_recall_articulo"] == 1 and d["d_pares_por_oferta"] == -1
    md = "\n".join(tc.diferencias_md([d]))
    assert "## Recuperación elegida frente a v1" in md and "elegida − v1" in md and "+25.0" in md and "| −1 |" in md and "subió el ruido" in md
    assert tc.diferencias_v1(filas, {"elegida": "no_esta"}) == [] and tc.diferencias_md([]) == []


def test_la_tabla_trae_brechas_totales_y_pares_por_oferta():
    filas = _filas(a=A)
    assert filas[0]["brechas_total"] == 2 and filas[0]["pares_por_oferta"] == 1
    assert "Brechas (total)" in tc.tabla_md(filas) and tc.fila_texto(filas[0])[tc.ENCABEZADO.index("Brechas (total)")] == "2"


# --- Gráficos ---

def test_el_embudo_de_la_reevaluacion_exige_el_mismo_gris_y_dice_embedding_y_k(tmp_path):
    pytest.importorskip("matplotlib")
    evaluadas = {"8B": {"P9": A}, "32B": {"P9": B}}
    filas = tc.calcular_filas(evaluadas, CONJUNTOS)
    assert filas[0]["perdidas"]["no recuperada"] == filas[1]["perdidas"]["no recuperada"] == 1
    ruta = tmp_path / "b.png"
    assert tc.grafico_embudo_reeval(filas, str(ruta), "P9 solo", ["8B", "32B"], evaluadas) is True and ruta.stat().st_size > 1000
    assert tc.grafico_embudo_reeval(filas, str(tmp_path / "x.png"), "P9 solo", ["no_esta"], evaluadas) is False


def test_si_el_gris_no_es_identico_es_un_error(tmp_path):
    pytest.importorskip("matplotlib")
    evaluadas = {"8B": {"P9": A}, "32B": {"P9": C}}
    filas = tc.calcular_filas(evaluadas, CONJUNTOS)
    with pytest.raises(tc.GrisDistinto, match="no es idéntico"):
        tc.grafico_embudo_reeval(filas, str(tmp_path / "b.png"), "P9 solo", ["8B", "32B"], evaluadas)
    assert not (tmp_path / "b.png").exists()


def test_cada_embudo_de_la_reevaluacion_lleva_solo_su_grupo_y_el_de_v1_no_exige_el_mismo_gris(tmp_path, monkeypatch):
    pytest.importorskip("matplotlib")
    evaluadas = {"8B (elegida)": {"P9": A}, "32B (elegida)": {"P9": B}, "8B": {"P9": C}, "32B": {"P9": A}}
    filas = tc.calcular_filas(evaluadas, CONJUNTOS)
    usados = []
    original = tc.grafico_embudo
    monkeypatch.setattr(tc, "grafico_embudo", lambda f, ruta, conjunto, aviso="", nombres=None, titulo=None: (usados.append((os.path.basename(ruta), nombres, titulo)), original(f, ruta, conjunto, aviso, nombres, titulo)))
    assert tc.grafico_embudo_reeval(filas, str(tmp_path / "v1.png"), "P9 solo", ["8B", "32B"], evaluadas, "", "de v1", gris_identico=False) is True      # gris 2 y 1: no es error
    assert tc.grafico_embudo_reeval(filas, str(tmp_path / "el.png"), "P9 solo", ["8B (elegida)", "32B (elegida)"], evaluadas) is True
    assert usados[0][1] == ["8B", "32B"] and "de v1" in usados[0][2] and usados[1][1] == ["8B (elegida)", "32B (elegida)"] and "con la recuperación elegida" in usados[1][2]
    with pytest.raises(tc.GrisDistinto):
        tc.grafico_embudo_reeval(filas, str(tmp_path / "x.png"), "P9 solo", ["8B", "32B"], evaluadas)


def test_las_etiquetas_del_grafico_de_costo_no_se_pisan(tmp_path):
    plt = pytest.importorskip("matplotlib.pyplot")
    tc._plt()
    fig, eje = plt.subplots(figsize=(7, 6))
    puntos = [(0.0, 0.50, "32B v1"), (0.0, 0.51, "8B v1"), (0.0, 0.52, "32B razon. v1"), (0.01, 0.50, "gpt-oss elegida"), (0.0, 0.50, "32B elegida")]
    eje.set_xlim(-0.01, 0.1)
    eje.set_ylim(0, 1)
    fig.tight_layout()
    tc._colocar_etiquetas(fig, eje, puntos)
    renderer = fig.canvas.get_renderer()
    cajas = [tc._caja_texto(t, renderer) for t in eje.texts]
    assert len(cajas) == len(puntos) and not any(a.overlaps(b) for i, a in enumerate(cajas) for b in cajas[i + 1:])
    plt.close(fig)


def test_los_graficos_de_antes_despues_criticidad_y_confusion_se_generan(tmp_path):
    pytest.importorskip("matplotlib")
    evaluadas = {"elegida": {"P9": A}, "v1": {"P9": C}}
    filas = tc.calcular_filas(evaluadas, CONJUNTOS)
    mapa = {"elegida": "v1"}
    assert tc.grafico_recuperacion_antes_despues(filas, str(tmp_path / "e.png"), mapa, CONJUNTOS, evaluadas) is True
    assert tc.grafico_errores_por_criticidad(evaluadas, ["P9"], ["elegida", "v1"], str(tmp_path / "d.png"), "P9 solo", "Atención: recuperaciones distintas") is True
    assert tc.grafico_confusion_clase(evaluadas, ["P9"], ["elegida", "v1"], str(tmp_path / "f.png"), "P9 solo") is True
    assert all((tmp_path / n).stat().st_size > 1000 for n in ("e.png", "d.png", "f.png"))
    assert tc.grafico_recuperacion_antes_despues(filas, str(tmp_path / "e2.png"), {"x": "y"}, CONJUNTOS, evaluadas) is False
    assert tc.grafico_errores_por_criticidad(evaluadas, ["P1"], ["elegida"], str(tmp_path / "d2.png")) is False      # oferta que no tiene


def test_los_graficos_existentes_aceptan_el_aviso_de_comparabilidad(tmp_path):
    pytest.importorskip("matplotlib")
    filas = _filas(a=A, c=C)
    tc.grafico_recall_falsas(filas, str(tmp_path / "a.png"), "P9 solo", "P9 solo", "Atención: x")
    tc.grafico_embudo(filas, str(tmp_path / "b.png"), "P9 solo", "Atención: x")
    tc.grafico_recall_costo_tiempo(filas, str(tmp_path / "c.png"), "P9 solo", "Atención: x")
    assert all((tmp_path / n).stat().st_size > 1000 for n in ("a.png", "b.png", "c.png"))


# --- generar (el flujo completo, con las evaluaciones ya hechas) ---

def _cfg(elegidas, v1):
    return {"configuraciones": {n: {} for n in (*elegidas, *v1)}, "reeval": {"elegida_vs_v1": dict(zip(elegidas, v1))}, "conjuntos": CONJUNTOS}


def test_generar_con_reeval_escribe_informe_y_todos_los_graficos(monkeypatch, tmp_path):
    pytest.importorskip("matplotlib")
    evaluadas = {"8B (elegida)": {"P9": A}, "32B (elegida)": {"P9": B}, "8B": {"P9": C}, "32B": {"P9": C}}
    monkeypatch.setattr(tc, "evaluar_configuraciones", lambda cfg: evaluadas)
    r = tc.generar(_cfg(["8B (elegida)", "32B (elegida)"], ["8B", "32B"]), str(tmp_path))
    assert {"a", "c", "d", "e", "f", "b_reeval", "b_v1"} <= set(r["rutas"]) and "b" not in r["rutas"]       # con la reevaluación el embudo va separado, no mezclado
    assert all(os.path.getsize(p) > 100 for p in r["rutas"].values())
    assert os.path.basename(r["rutas"]["b_reeval"]) == "grafico_b_embudo_reeval.png" and os.path.basename(r["rutas"]["b_v1"]) == "grafico_b_embudo_v1.png"
    assert os.path.basename(r["rutas"]["e"]) == "grafico_e_recuperacion_antes_despues.png"
    assert not (tmp_path / "grafico_b_embudo.png").exists()
    assert os.path.basename(r["rutas"]["d"]) == "grafico_d_errores_por_criticidad.png" and os.path.basename(r["rutas"]["f"]) == "grafico_f_confusion_clase.png"
    md = (tmp_path / "tabla_comparativa.md").read_text(encoding="utf-8")
    assert "## Recuperación elegida frente a v1" in md and "## Comparabilidad de la recuperación" in md and "AVISO (P9 solo, P9)" in md      # elegidas y v1 comparan pares distintos
    with open(r["rutas"]["csv"], encoding="utf-8-sig") as f:
        assert "brechas_total" in f.readline()


def test_si_el_gris_de_las_elegidas_difiere_generar_guarda_todo_lo_demas_y_despues_falla(monkeypatch, tmp_path):
    pytest.importorskip("matplotlib")
    monkeypatch.setattr(tc, "evaluar_configuraciones", lambda cfg: {"8B (elegida)": {"P9": A}, "32B (elegida)": {"P9": C}, "8B": {"P9": C}, "32B": {"P9": C}})
    with pytest.raises(tc.GrisDistinto):
        tc.generar(_cfg(["8B (elegida)", "32B (elegida)"], ["8B", "32B"]), str(tmp_path))
    assert (tmp_path / "tabla_comparativa.md").is_file() and (tmp_path / "grafico_d_errores_por_criticidad.png").is_file() and not (tmp_path / "grafico_b_embudo_reeval.png").exists()


def test_sin_reeval_no_se_generan_los_graficos_de_la_reevaluacion_y_el_informe_no_cambia_de_estructura(monkeypatch, tmp_path):
    pytest.importorskip("matplotlib")
    monkeypatch.setattr(tc, "evaluar_configuraciones", lambda cfg: {"a": {"P9": A}, "b": {"P9": B}})
    r = tc.generar({"configuraciones": {"a": {}, "b": {}}, "conjuntos": CONJUNTOS}, str(tmp_path))
    assert "e" not in r["rutas"] and "b_reeval" not in r["rutas"] and {"a", "b", "c", "d", "f"} <= set(r["rutas"])
    md = (tmp_path / "tabla_comparativa.md").read_text(encoding="utf-8")
    assert "frente a v1" not in md and "AVISO" not in md and "mismos pares" in md


def test_main_termina_con_error_si_el_gris_no_es_identico(monkeypatch, tmp_path, capsys):
    def falla(*a, **kw):
        raise tc.GrisDistinto("gris distinto")
    monkeypatch.setattr(tc, "generar", falla)
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"configuraciones": {"a": {}}}), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        tc.main(["--config", str(cfg), "--salida", str(tmp_path)])
    assert e.value.code == 1 and "gris distinto" in capsys.readouterr().err


def test_evaluar_configuraciones_agrega_la_recuperacion_de_cada_json(monkeypatch, tmp_path):
    secciones = [{"id": "3", "titulos": ["3 Plazos"], "fragmentos": [{"norma": "NORM_01", "articulo": "4.2", "score": 0.4, "parte": 1}]}]
    resultado = {**_resultado({"01"}, {"01"}), "secciones": secciones, "configuracion_analisis": {"embedding_backend": "gemini", "recuperacion_json_sha256": "cd" * 32}}
    ruta = tmp_path / "analisis_riesgos_P9_x.json"
    ruta.write_text(json.dumps(resultado), encoding="utf-8")
    monkeypatch.setattr(tc.E, "cargar_gt", lambda oferta: [dict(t) for t in GT])
    monkeypatch.setattr(tc.E, "cargar_espejos", lambda oferta: [])
    evaluadas = tc.evaluar_configuraciones({"configuraciones": {"c": {"P9": str(ruta)}}})
    info = evaluadas["c"]["P9"]["recuperacion"]
    assert info["huella_pares"] == tc.huella_recuperacion.huella_de_pares(secciones) and info["embedding"] == "gemini" and info["sha256"] == "cd" * 32 and info["pares"] == 1


# --- config_reeval.json ---

def test_config_reeval_arma_las_configuraciones_elegidas_y_sus_referencias_de_v1():
    cfg = tc.cargar_config(os.path.join(RAIZ, "evaluacion", "config_reeval.json"))
    with open(os.path.join(RAIZ, "evaluacion", "config_final.json"), encoding="utf-8") as f:
        final = json.load(f)
    mapa = cfg["reeval"]["elegida_vs_v1"]
    assert len(mapa) == 4 and (set(mapa) | set(mapa.values())) - {None} == set(cfg["configuraciones"]) and len(cfg["configuraciones"]) == 7
    assert mapa["gpt-oss-120b esfuerzo bajo (elegida)"] is None                             # modelo nuevo: sin par de v1
    for elegida, v1 in mapa.items():
        assert v1 is None or cfg["configuraciones"][v1] == final["configuraciones"][v1]     # las referencias de v1 son las de config_final.json
        assert set(cfg["configuraciones"][elegida]) == {"P1", "P2", "P3", "P4"}
        sufijos = {v["auto"]["sufijo"] for v in cfg["configuraciones"][elegida].values()}
        assert len(sufijos) == 1 and sufijos.pop().endswith("-elegido")
    assert cfg["sin_rag"] == final["sin_rag"] and "amplia" not in " ".join(cfg["configuraciones"])
    dev, prueba, total = cfg["conjuntos"]
    assert dev == "P1–P2 desarrollo" and prueba.startswith("P3–P4 prueba (segunda evaluación") and "ya fue visto en v1" in prueba and total == "P1–P4 total"
    assert cfg["conjuntos"][dev] == ["P1", "P2"] and cfg["conjuntos"][prueba] == ["P3", "P4"]


def test_salida_de_la_reevaluacion_no_es_resultados_finales():
    reeval = tc.cargar_config(os.path.join(RAIZ, "evaluacion", "config_reeval.json"))
    final = tc.cargar_config(os.path.join(RAIZ, "evaluacion", "config_final.json"))
    destino = tc.carpeta_salida(reeval)
    assert os.path.normpath(destino) == os.path.normpath(os.path.join(RAIZ, "evaluacion", "resultados_reeval"))
    assert os.path.normpath(destino) != os.path.normpath(tc.SALIDA)
    assert tc.carpeta_salida(final) == tc.SALIDA                      # v1 sigue escribiendo en resultados_finales
    assert tc.carpeta_salida(reeval, "otra") == "otra"                # --salida explícito manda
