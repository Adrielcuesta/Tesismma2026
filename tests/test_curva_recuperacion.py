import math
import random

import numpy as np
import pytest
from langchain_core.documents import Document

from scripts import curva_recuperacion as cv
from scripts import diagnostico_recuperacion as dr

N = "N1"


def _doc(art, norma=N, parte=1, texto=None):
    return Document(page_content=texto or f"Art. {art}. t\ncuerpo {norma} {art}", metadata={"norma": norma, "articulo": art, "parte": parte})


def _consulta(*items):
    """items: (artículo, puntaje denso, puntaje del reranker), en el orden denso."""
    return [dr.Cand(_doc(a), d, r) for a, d, r in items]


def _fixture():
    """Dos secciones con consultas, preámbulo y oraciones de contenido conocido (los conteos de los tests están hechos a mano)."""
    q1 = _consulta(("preambulo", .90, .1), ("A", .80, .2), ("B", .70, .9), ("C", .60, .3), ("D", .50, .8))
    q2 = _consulta(("B", .95, .5), ("E", .85, .4), ("A", .75, .95), ("F", .65, .1))
    q3 = _consulta(("P", .9, .3), ("Q", .8, .6), ("R", .7, .2))
    oraciones1 = [{"con_cifras": True, "articulos": [{"norma": N, "articulo": "B", "densa": .9}, {"norma": N, "articulo": "G", "densa": .8}, {"norma": N, "articulo": "H", "densa": .7}]},
                  {"con_cifras": False, "articulos": []}]
    secciones = [{"oferta": "P1", "id": "S1", "consultas": [q1, q2], "oraciones": oraciones1}, {"oferta": "P1", "id": "S2", "consultas": [q3], "oraciones": []}]

    def fila(tipo, id_, sec, *articulos):
        return {"tipo": tipo, "id": id_, "oferta": "P1", "sec": sec, "seccion": None if sec is None else secciones[sec]["id"], "pares": {(N, a) for a in articulos}, "texto": id_, "articulo": ",".join(articulos)}
    filas = [fila("trampa", "T1", 0, "B"), fila("trampa", "T2", 0, "F"), fila("trampa", "T3", None, "B"), fila("conforme", "C1", 0, "Z", "A"), fila("conforme", "C2", 1, "Q")]
    return secciones, filas


# --- Puntos: tupla del pipeline y Config ---

def test_las_tres_variantes_arman_la_tupla_y_el_config_del_pipeline():
    assert cv.tupla_pipeline(cv.punto("densa", 7)) == (7, 7, 0, cv.SIN_TOPE, 2, 8)
    assert cv.tupla_pipeline(cv.punto("reranker", 7)) == (100, 0, 7, cv.SIN_TOPE, 2, 8)
    assert cv.tupla_pipeline(cv.punto("reranker", 100)) == (100, 0, 100, cv.SIN_TOPE, 2, 8)
    assert cv.tupla_pipeline(cv.punto("union", 3)) == (100, 3, 3, cv.SIN_TOPE, 2, 8)
    assert cv.tupla_pipeline(cv.punto("union", 50)) == (100, 50, 50, cv.SIN_TOPE, 2, 8)
    d, r, u = (cv.config_de(cv.punto(v, 7)) for v in ("densa", "reranker", "union"))
    assert (d.modo, d.k, d.top) == ("densa", 7, 7) and (r.modo, r.k, r.top) == ("reranker", 100, 7) and (u.modo, u.k, u.top, u.top_rr) == ("union", 100, 7, None)
    assert cv.KS_RERANKER == tuple(range(1, 101)) and cv.KS_UNION == tuple(range(1, 51)) and cv.N_RERANKER == 100
    assert d.oraciones == (True, 2) and d.cupo_oraciones == 8
    assert cv.config_de(cv.punto("densa", 3, 0, 0)).oraciones is None


def test_la_configuracion_actual_es_la_del_diagnostico_y_la_del_pipeline():
    esperada = next(c for c in dr.CONFIGURACIONES if c.nombre == "union_oraciones_cifras_N2_cupo8")
    assert cv.CONFIG_ACTUAL._replace(nombre=esperada.nombre) == esperada
    assert cv.config_de(cv.punto_actual())._replace(nombre="actual_pipeline") == cv.CONFIG_ACTUAL
    from scripts import config
    assert (config.K_SUBSECCION, config.TOP_DENSA_SUBSECCION, config.TOP_N_SUBSECCION, config.VERIFICAR_TOPE, config.ORACIONES_N, config.ORACIONES_CUPO) == (10, 5, 5, 25, 2, 8)
    assert cv.tupla_pipeline(cv.punto_actual()) == (10, 5, 5, 25, 2, 8)
    assert cv.tupla_pipeline(cv.punto("union", 5)) != cv.tupla_pipeline(cv.punto_actual())     # la referencia no es un punto de la serie (pool de 100 contra 10, sin tope)


def test_los_k_de_la_variante_densa_llegan_a_todos_los_fragmentos():
    ks = cv.ks_densa(410)
    assert ks[:50] == list(range(1, 51)) and ks[50:] == [60, 75, 100, 150, 200, 300, 410]
    assert cv.ks_densa(8) == [1, 2, 3, 4, 5, 6, 7, 8]


# --- pares = llamadas al verificador (unidad del pipeline) ---

def test_pares_es_la_suma_de_len_seleccion_final_con_union_preambulo_tope_y_oraciones():
    secciones, filas = _fixture()
    por = lambda k: cv.evaluar_punto(cv.config_de(cv.punto("densa", k, 0, 0)), filas, secciones)
    # S1, K=2: q1 -> {preámbulo, A} sin preámbulo = {A}; q2 -> {B, E}; unión {A, B, E} = 3. S2: {P, Q} = 2
    assert por(2)["pares"] == 3 + 2 and por(2)["pares_por_oferta"] == {"P1": 5}
    assert por(3)["pares"] == 3 + 3          # S1 {A,B} U {B,E,A} = 3; S2 {P,Q,R} = 3
    assert por(4)["pares"] == 5 + 3          # S1 {A,B,C} U {B,E,A,F} = 5
    # reranker (50 candidatos): top 1 de q1 = B, de q2 = A; top 2: q1 {B,D}, q2 {A,B}
    rr = lambda k: cv.evaluar_punto(cv.config_de(cv.punto("reranker", k, 0, 0)), filas, secciones)
    assert rr(1)["pares"] == 2 + 1 and rr(2)["pares"] == 3 + 2
    # unión k=1: S1: q1 -> densa 1 (preámbulo, se quita) + reranker 1 (B); q2 -> B + A => {A, B}. S2: densa P + reranker Q => {P, Q}
    assert cv.evaluar_punto(cv.config_de(cv.punto("union", 1, 0, 0)), filas, secciones)["pares"] == 2 + 2
    # coincide con seleccion_final del diagnóstico, sección por sección
    cfg = cv.config_de(cv.punto("union", 2, 0, 0))
    assert cv.evaluar_punto(cfg, filas, secciones)["pares"] == sum(len(dr.seleccion_final(s["consultas"], cfg, s["oraciones"])) for s in secciones)
    # el tope recorta la base y las oraciones se suman DETRÁS, hasta su cupo: base {B, E}; oración 1 aporta B (ya está) y G (N=2); H queda fuera
    con_tope = dr.Config("t", 4, 4, 2, "densa", None, (True, 2), 5)
    s1 = dr.seleccion_final(secciones[0]["consultas"], con_tope, secciones[0]["oraciones"])
    assert [d.metadata["articulo"] for d in s1] == ["B", "E", "G"]
    assert cv.evaluar_punto(con_tope, filas, secciones)["pares"] == 3 + 2       # S1: base 2 + G; S2: {P, Q, R} recortado a 2 por el tope
    assert cv.evaluar_punto(con_tope, filas, secciones)["max_base"] == 2


def test_aciertos_conforme_con_dos_articulos_acierta_con_cualquiera_y_fila_sin_seccion_no_acierta():
    secciones, filas = _fixture()
    r = cv.evaluar_punto(cv.config_de(cv.punto("densa", 2, 0, 0)), filas, secciones)
    # T1 (B) sí, T2 (F) no, T3 sin sección no; C1 (Z o A) sí por A; C2 (Q) sí
    assert (r["hits_t"], r["n_t"], r["hits_c"], r["n_c"]) == (1, 3, 2, 2)


def test_recall_y_pares_son_monotonos_en_k_en_cada_variante():
    rng = random.Random(7)
    arts = [f"1.{i}" for i in range(1, 151)]
    secciones, filas = [], []
    for s in range(6):
        consultas = []
        for _ in range(3):
            orden = rng.sample(arts, len(arts))
            # como preparar_datos: el reranker puntúa solo los 100 primeros densos (el resto, -inf)
            consultas.append([dr.Cand(_doc(a), 1 - r / 1000, rng.random() if r < cv.N_RERANKER else -math.inf) for r, a in enumerate(orden)])
        secciones.append({"oferta": "P1", "id": f"S{s}", "consultas": consultas, "oraciones": []})
        for t in range(3):
            filas.append({"tipo": "trampa" if t else "conforme", "id": f"{s}{t}", "oferta": "P1", "sec": s, "seccion": f"S{s}", "pares": {(N, rng.choice(arts))}, "texto": "", "articulo": ""})
    # las tres variantes tienen un grupo fijo de candidatos (densa: el ranking completo; reranker y unión: los 100 primeros), así que sus conjuntos son anidados
    for variante, ks in (("densa", cv.ks_densa(150)), ("reranker", cv.KS_RERANKER), ("union", cv.KS_UNION)):
        s = cv.serie(variante, ks, filas, secciones)
        assert all(a["hits_t"] <= b["hits_t"] and a["hits_c"] <= b["hits_c"] and a["pares"] <= b["pares"] for a, b in zip(s, s[1:])), variante
    # y no solo los conteos: cada conjunto de artículos contiene al anterior, también con las oraciones sumadas
    for variante, ks in (("reranker", (1, 50, 75, 100)), ("union", (1, 5, 6, 25, 50))):
        sel = [[{cv._clave(d) for d in dr.seleccion_final(sec["consultas"], cv.config_de(cv.punto(variante, k, 0, 0)), [])} for sec in secciones] for k in ks]
        assert all(x <= y for a, b in zip(sel, sel[1:]) for x, y in zip(a, b)), variante


# --- Calibración ---

def test_calibracion_exige_24_de_30_y_516_pares_y_falla_con_un_mensaje_claro():
    assert cv.ESPERADO_CALIBRACION == {"recall": 24, "n_trampas": 30, "pares": 516}
    secciones, filas = _fixture()
    r = cv.evaluar_punto(cv.CONFIG_ACTUAL, filas, secciones, cv.OFERTAS_BASE)
    esperado = {"recall": r["hits_t"], "n_trampas": r["n_t"], "pares": r["pares"]}
    assert cv.calibrar(secciones, filas, esperado)["ok"] is True
    mala = cv.calibrar(secciones, filas)          # el fixture no da 24/30 y 516
    assert mala["ok"] is False
    assert "CALIBRACIÓN FALLIDA" in mala["mensaje"] and "24/30" in mala["mensaje"] and "516" in mala["mensaje"] and "No se generaron curvas" in mala["mensaje"]
    assert f"{r['hits_t']}/{r['n_t']}" in mala["mensaje"] and str(r["pares"]) in mala["mensaje"]
    assert cv.calibrar(secciones, filas, {**esperado, "pares": esperado["pares"] + 1})["ok"] is False


# --- Filas ---

def test_construir_filas_ubica_secciones_y_acepta_cualquiera_de_los_articulos_del_conforme():
    secciones = [{"id": "S1", "texto": "Texto uno sin nada."}, {"id": "S2", "texto": "El hormigón será H-35 con 340 kg/m³ de cemento y relación 0,45."}]
    trampas = [{"id": "P1-01-A", "fragmento_trampa": "hormigón será H-35", "norma": "NORM_01", "articulo": "4.2", "articulos_equivalentes": "NORM_01 4.3"}]
    conformes = [{"cita_conforme": "340 kg/m³ de cemento", "norma": "NORM_01", "articulo": "3.1; 3.2"}, {"cita_conforme": "no está en ninguna parte", "norma": "NORM_01", "articulo": "5.1"}]
    filas = cv.construir_filas("P1", secciones, trampas, conformes, desplazamiento=10)
    t, c1, c2 = filas
    assert (t["sec"], t["seccion"], t["pares"]) == (11, "S2", {("NORM_01", "4.2"), ("NORM_01", "4.3")})
    assert (c1["sec"], c1["pares"]) == (11, {("NORM_01", "3.1"), ("NORM_01", "3.2")}) and c2["sec"] is None


def test_oracion_de_fila():
    oraciones = ["La torre tendrá 12 m de altura.", "El hormigón será H-35 y se curará 7 días."]
    assert cv.oracion_de_fila("hormigón será H-35", oraciones) == oraciones[1]
    assert cv.oracion_de_fila("algo que no está", oraciones) is None


def test_p3_sin_permitir_prueba_aborta():
    with pytest.raises(SystemExit):
        cv.validar_ofertas(["P1", "P2", "P3"], permitir_prueba=False)
    with pytest.raises(SystemExit):
        cv.validar_ofertas(["P1"], permitir_prueba=True)           # falta P2
    cv.validar_ofertas(["P1", "P2"], False)
    cv.validar_ofertas(["P1", "P2", "P3", "P4"], True)
    with pytest.raises(SystemExit):
        cv.validar_ofertas(["P1", "P2", "P5"], True)


# --- Ganancia marginal, codo, umbral y AUC sobre una curva sintética ---

def _serie_sintetica(hits, paso=100):
    return cv.completar_serie([{"k": i + 1, "hits_t": h, "pares": paso * (i + 1), "recall_trampas": h / 30} for i, h in enumerate(hits)], 25, 0.00037, 3.3)


def test_ganancia_marginal_y_proyecciones():
    s = _serie_sintetica([10, 20, 27, 29, 29, 30])
    assert [x["ganancia_marginal"] for x in s] == [None, 10.0, 7.0, 2.0, 0.0, 1.0]
    assert [x["trampas_extra"] for x in s][1:] == [10, 7, 2, 0, 1] and [x["pares_extra"] for x in s][1:] == [100] * 5
    assert s[-1]["horas_local_proy"] == pytest.approx(600 * 25 / 3600) and s[-1]["usd_nube_proy"] == pytest.approx(600 * 0.00037) and s[-1]["horas_nube_proy"] == pytest.approx(600 * 3.3 / 3600)


def test_el_codo_de_kneedle_esta_en_la_rodilla_de_la_curva_conocida():
    s = _serie_sintetica([10, 20, 27, 29, 29, 30])
    # ejes normalizados: (0,0) (.2,.5) (.4,.85) (.6,.95) (.8,.95) (1,1) -> mayor distancia a la diagonal en el tercer punto (pares 300)
    assert s[cv.indice_codo([x["pares"] for x in s], [x["hits_t"] for x in s])]["pares"] == 300
    assert cv.indice_codo([1, 2, 3], [5, 5, 5]) is None and cv.indice_codo([1, 2], [1, 2]) is None
    assert cv.indice_codo([1, 2, 3, 4], [1, 2, 3, 4]) is None        # recta: sin codo


def test_k_por_umbral_marginal_tres_pasos_seguidos():
    s = _serie_sintetica([10, 20, 27, 29, 29, 29, 29, 30])
    assert s[cv.indice_por_umbral(s, 0.5)]["pares"] == 400           # los pasos 400->500, 500->600 y 600->700 ya no suman trampas
    assert cv.indice_por_umbral(_serie_sintetica([10, 20, 27, 29, 29, 30]), 0.5) is None
    assert cv.indice_por_umbral(s, 0.5, pasos=4) is None


def test_k_para_recall_y_auc():
    s = _serie_sintetica([10, 20, 27, 29, 29, 30])
    assert cv.k_para_recall(s, 0.90)["k"] == 3 and cv.k_para_recall(s, 0.95)["k"] == 4 and cv.k_para_recall(s, 0.99)["k"] == 6 and cv.k_para_recall(s, 1.0)["k"] == 6
    assert cv.k_para_recall(_serie_sintetica([10, 20]), 0.9) is None
    plana = [{"k": k, "recall_trampas": 0.5} for k in (1, 10, 100)]
    assert cv.auc_log(plana) == pytest.approx(0.5)


def test_aviso_si_el_reranker_todavia_sube_mas_de_una_trampa_entre_75_y_100():
    def con(h75, h100):
        return [{"k": 75, "hits_t": h75, "n_t": 30}, {"k": 100, "hits_t": h100, "n_t": 30}]
    assert cv.aviso_reranker_sigue_subiendo(con(25, 27)) and "200" in cv.aviso_reranker_sigue_subiendo(con(25, 27)) and "2 trampas" in cv.aviso_reranker_sigue_subiendo(con(25, 27))
    assert cv.aviso_reranker_sigue_subiendo(con(25, 26)) is None and cv.aviso_reranker_sigue_subiendo(con(25, 25)) is None
    assert cv.aviso_reranker_sigue_subiendo([{"k": 10, "hits_t": 1, "n_t": 30}]) is None


def test_punto_mas_cercano_en_pares():
    s = _serie_sintetica([10, 20, 27, 29, 29, 30])
    assert cv.punto_mas_cercano(s, 420)["pares"] == 400 and cv.punto_mas_cercano(s, 1000)["pares"] == 600


# --- Reranker con caché y preparación de datos ---

def test_el_puntuador_del_reranker_cachea_en_disco_y_solo_calcula_lo_que_falta(tmp_path):
    llamadas = []

    def real(consulta, docs):
        llamadas.append([d.metadata["articulo"] for d in docs])
        return [0.5] * len(docs)
    p = cv.PuntuadorReranker(str(tmp_path / "reranker.json"), real)
    docs = [_doc("A"), _doc("B")]
    assert p("consulta", docs) == [0.5, 0.5] and p("consulta", docs) == [0.5, 0.5] and len(llamadas) == 1
    p("consulta", docs + [_doc("C")])
    assert llamadas[-1] == ["C"]
    nuevo = cv.PuntuadorReranker(str(tmp_path / "reranker.json"), lambda c, d: pytest.fail("todo en caché"))
    assert nuevo("consulta", docs) == [0.5, 0.5] and nuevo.calculados == 0


def test_rankear_numpy_ordena_por_coseno_con_empates_por_posicion():
    class Backend:
        def embed_queries(self, textos):
            return np.array([[1, 0, 0] if t == "a" else [0, 1, 0] for t in textos], dtype=np.float32)
    docs = np.array([[0, 1, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
    (orden_a, p_a), (orden_b, _) = cv.rankear_numpy(Backend(), docs)(["a", "b"])
    assert list(orden_a) == [1, 0, 2, 3] and p_a[0] == 1 and list(orden_b) == [0, 2, 1, 3]


def test_preparar_datos_cand_completo_reranker_solo_en_los_primeros_y_oraciones_con_cifras(monkeypatch):
    monkeypatch.setattr(cv, "N_RERANKER", 2)
    fragmentos = [_doc(a) for a in ("preambulo", "1.1", "1.2", "1.3")]
    seccion = {"id": "S1", "texto": "El plazo será de 28 días. Se entregará el informe final.", "titulos": ["T"], "subsecciones": [("1", "El plazo será de 28 días. Se entregará el informe final.")]}
    pedidos = []

    def rankear(textos):
        pedidos.extend(textos)
        return [(np.array([1, 2, 0, 3]), np.array([.9, .8, .7, .6])) for _ in textos]
    llamadas = []
    datos = cv.preparar_datos(rankear, fragmentos, [("P1", seccion)], {}, lambda q, docs: (llamadas.append(len(docs)), [.4, .3][:len(docs)])[1])
    (cands,) = datos["secciones"][0]["consultas"]
    assert [c.doc.metadata["articulo"] for c in cands] == ["1.1", "1.2", "preambulo", "1.3"] and llamadas == [2]
    assert [c.reranker for c in cands[:2]] == [.4, .3] and all(c.reranker == -math.inf for c in cands[2:])
    o1, o2 = datos["secciones"][0]["oraciones"]
    assert o1["con_cifras"] and [(a["norma"], a["articulo"]) for a in o1["articulos"]] == [(N, "1.1"), (N, "1.2"), (N, "1.3")] and o2 == {"con_cifras": False, "articulos": []}
    assert len(pedidos) == 2 and len(set(pedidos)) == 2        # la consulta de la sección y la oración con cifras; la que no tiene dígitos no se busca


# --- Salidas y orquestación ---

class BackendFalso:
    model_name = "falso"
    cache = type("C", (), {"meta": {"documentos_s": 1.5, "consultas_s": 0.5, "n_documentos": 8, "n_consultas": 3, "tokens": 0, "tokens_estimados": 0, "usd": 0.0}})()


def _correr(monkeypatch, tmp_path, calibra: bool, extra=()):
    secciones, filas = _fixture()
    fragmentos = [_doc(a) for a in ("A", "B", "C", "D", "E", "F", "G", "H")]
    datos = {"secciones": secciones, "oracion_fila": {0: [(N, "B")], 3: [(N, "A")]}, "usd_corrida": 0.0}
    monkeypatch.setattr(cv, "_cargar_contexto", lambda rutas: {"plano": [], "filas": filas, "oraciones_filas": {}, "fragmentos": fragmentos})
    monkeypatch.setattr(cv, "_datos_de_embedding", lambda nombre, ctx, a, puntuar, directorio: (datos, BackendFalso(), ""))
    if calibra:
        r = cv.evaluar_punto(cv.CONFIG_ACTUAL, filas, secciones, cv.OFERTAS_BASE)
        monkeypatch.setattr(cv, "ESPERADO_CALIBRACION", {"recall": r["hits_t"], "n_trampas": r["n_t"], "pares": r["pares"]})
    archivos = []
    for o in ("P1", "P2", *extra):
        f = tmp_path / f"{o}.pdf"
        f.write_text("x")
        archivos += ["--oferta", f"{o}={f}"]
    salida = tmp_path / "salida"
    return cv.main(archivos + ["--salida", str(salida)]), salida


def test_si_la_calibracion_falla_se_escribe_el_error_y_no_se_genera_ninguna_curva(monkeypatch, tmp_path, capsys):
    codigo, salida = _correr(monkeypatch, tmp_path, calibra=False)
    assert codigo == 2
    nombres = sorted(p.name for p in salida.iterdir())
    assert len(nombres) == 1 and nombres[0].startswith("curva_recuperacion_") and nombres[0].endswith(".md")
    md = (salida / nombres[0]).read_text(encoding="utf-8")
    assert "CALIBRACIÓN FALLIDA" in md and "24/30" in md and "516" in md and "ranking-chroma" in md and "No se escribió ningún CSV ni gráfico" in md
    assert "CALIBRACIÓN FALLIDA" in capsys.readouterr().out


def test_con_la_calibracion_ok_se_generan_csv_md_y_los_tres_graficos(monkeypatch, tmp_path):
    codigo, salida = _correr(monkeypatch, tmp_path, calibra=True)
    assert codigo == 0
    nombres = {p.name.rsplit("_20", 1)[0] for p in salida.iterdir()}
    assert nombres == {"curva_recuperacion", "curva_recall", "curva_recall_vs_pares", "curva_costo"}
    md = next(salida.glob("curva_recuperacion_*.md")).read_text(encoding="utf-8")
    assert "Calibración OK" in md and "Comparación a igual costo" in md and "Grilla de oraciones" in md and '"elegido": {"EMBEDDING_BACKEND": "falso"' in md
    assert "conjunto de prueba" not in md and "conviene probar con 200" not in md and "con reranker todavía sube" not in md
    import csv
    with open(next(salida.glob("curva_recuperacion_*.csv")), encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f, delimiter=";"))
    assert list(filas[0]) == cv.COLUMNAS_CSV and {f["variante"] for f in filas} == {"densa", "reranker", "union"}
    serie = lambda v: [f for f in filas if f["variante"] == v and f["oraciones_n"] == "2" and f["oraciones_cupo"] == "8" and f["tope"] == str(cv.SIN_TOPE)]
    assert max(int(f["k"]) for f in serie("reranker")) == 100 and max(int(f["k"]) for f in serie("union")) == 50
    assert {f["k_sub"] for f in serie("reranker")} == {"100"} and {f["k_sub"] for f in serie("union")} == {"100"} and {f["top_densa"] for f in serie("reranker")} == {"0"}
    assert sum(f["es_actual"] == "1" for f in filas) == 1
    actual = next(f for f in filas if f["es_actual"] == "1")
    assert (actual["k_sub"], actual["top_densa"], actual["top_n"], actual["tope"], actual["oraciones_n"], actual["oraciones_cupo"]) == ("10", "5", "5", "25", "2", "8")


def test_con_prueba_permitida_el_informe_lo_avisa(monkeypatch, tmp_path):
    secciones, filas = _fixture()
    monkeypatch.setattr(cv, "_cargar_contexto", lambda rutas: {"plano": [], "filas": filas, "oraciones_filas": {}, "fragmentos": [_doc("A")]})
    r = cv.evaluar_punto(cv.CONFIG_ACTUAL, filas, secciones, cv.OFERTAS_BASE)
    monkeypatch.setattr(cv, "ESPERADO_CALIBRACION", {"recall": r["hits_t"], "n_trampas": r["n_t"], "pares": r["pares"]})
    monkeypatch.setattr(cv, "_datos_de_embedding", lambda *a: ({"secciones": secciones, "oracion_fila": {}, "usd_corrida": 0.0}, BackendFalso(), ""))
    archivos = []
    for o in ("P1", "P2", "P3"):
        f = tmp_path / f"{o}.pdf"
        f.write_text("x")
        archivos += ["--oferta", f"{o}={f}"]
    with pytest.raises(SystemExit):                                                  # sin --permitir-prueba aborta antes de calcular nada
        cv.main(archivos + ["--salida", str(tmp_path / "s")])
    assert cv.main(archivos + ["--permitir-prueba", "--salida", str(tmp_path / "s")]) == 0
    assert "AVISO" in next((tmp_path / "s").glob("curva_recuperacion_*.md")).read_text(encoding="utf-8")


def test_el_md_avisa_si_el_reranker_sigue_subiendo(monkeypatch, tmp_path):
    monkeypatch.setattr(cv, "aviso_reranker_sigue_subiendo", lambda s: "**AVISO:** sube más de 1 trampa; conviene probar con 200.")
    codigo, salida = _correr(monkeypatch, tmp_path, calibra=True)
    md = next(salida.glob("curva_recuperacion_*.md")).read_text(encoding="utf-8")
    assert codigo == 0 and "conviene probar con 200" in md and "con falso la curva con reranker todavía sube más de 1 trampa entre K=75 y K=100" in md


def test_el_subcomando_curva_esta_conectado():
    with pytest.raises(SystemExit) as e:
        dr.main(["curva", "--help"])
    assert e.value.code == 0
