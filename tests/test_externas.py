"""Ground truth de P6–P12 (prueba externa, evaluacion/externas.py) y su paso por evaluar.py, tabla_comparativa, preparar_extras y verificar_gt_literal. Sin leer datos/."""
import pytest

from evaluacion import evaluar as E
from evaluacion import externas as X
from evaluacion import preparar_extras as PE
from evaluacion import tabla_comparativa as T
from evaluacion import verificar_gt_literal as V

OFERTAS = ["P6", "P7", "P8", "P9", "P10", "P11", "P12"]


# --- Los archivos reales de evaluacion/ ---

def test_se_leen_las_105_trampas_y_los_166_conformes():
    trampas = {o: E.cargar_gt(o) for o in OFERTAS}
    conformes = {o: E.cargar_espejos(o) for o in OFERTAS}
    assert all(len(t) == 15 for t in trampas.values()) and sum(len(t) for t in trampas.values()) == 105
    assert sum(len(c) for c in conformes.values()) == 166 and "P6-C03" not in {c["id"] for c in conformes["P6"]}      # P6-C03 se quitó: su frase aparece dos veces en la oferta
    assert {f["severidad"] for f in trampas["P6"] + trampas["P12"]} <= {"Alta", "Media", "Baja"}
    todas = [f for t in trampas.values() for f in t]
    assert len({f["id"] for f in todas}) == 105 and all(f["tipo"] == "amenaza" for f in todas)
    assert {f["fuente"] for f in todas} <= set(X.FUENTES) and {f["clase"] for f in todas} <= set(E.CLASES) and {f["nivel"] for f in todas} <= set(E.NIVELES)
    assert all(not f["regla_norm07"].upper().startswith(("NORM", "ART")) for f in todas)
    assert all(c["cita_conforme"] and c["proyecto"] == f"Proyecto {o[1:]}" for o, cs in conformes.items() for c in cs)


def test_p6_normaliza_la_fuente_en_minusculas_y_con_tildes():
    fuentes = [f["fuente"] for f in E.cargar_gt("P6")]
    assert fuentes.count("DESVIO") == 14 and fuentes.count("EXCEPCION_NO_ACREDITADA") == 1


def test_ninguna_trampa_contiene_otra_trampa_ni_un_conforme():
    """Con frases que se contienen, una misma brecha contaría para dos casos (o una trampa encontrada sería a la vez una falsa alarma)."""
    for o in OFERTAS:
        trampas, conformes = E.cargar_gt(o), E.cargar_espejos(o)
        for t in trampas:
            ft = E.norm(t["fragmento_trampa"])
            assert not any(u is not t and ft in E.norm(u["fragmento_trampa"]) for u in trampas), t["id"]
            assert not any(E._frase_espejo(c) in ft or ft in E.norm(c["cita_conforme"]) for c in conformes), t["id"]


# --- Normalización ---

@pytest.mark.parametrize("valor,esperado", [("desvío", "DESVIO"), ("DESVIO", "DESVIO"), ("excepción no acreditada", "EXCEPCION_NO_ACREDITADA"),
                                            ("EXCEPCION_NO_ACREDITADA", "EXCEPCION_NO_ACREDITADA"), ("Información faltante", "INFORMACION_FALTANTE")])
def test_normalizar_fuente(valor, esperado):
    assert X.normalizar_fuente(valor) == esperado


def test_fuente_desconocida_falla():
    with pytest.raises(ValueError):
        X.normalizar_fuente("oportunidad")


def test_normalizar_regla():
    assert X.normalizar_regla("NORM_07 Art. 3.3.c") == "3.3.c" and X.normalizar_regla("3.3.c") == "3.3.c" and X.normalizar_regla("Art. 3.4.a") == "3.4.a"


def _csv(tmp_path, nombre, encabezado, filas):
    (tmp_path / nombre).write_text(";".join(encabezado) + "\n" + "\n".join(";".join(f) for f in filas) + "\n", encoding="utf-8")


def test_lector_con_archivos_sinteticos(tmp_path):
    enc = ["id", "oferta", "seccion", "fragmento_trampa", "norma", "articulo", "fuente", "clase", "regla_norm07", "nivel", "responsable"]
    _csv(tmp_path, "P9_trampas_v2.csv", enc, [["P9-01-A", "P9", "3.1 Alcance", "El plazo es de 14 días.", "NORM_01", "2.5", "desvío", "Critico", "NORM_07 Art. 3.3.c", "alto", "Gerencia X"],
                                              ["P1-01-A", "P1", "3.1 Alcance", "otra oferta", "NORM_01", "2.5", "DESVIO", "Menor", "3.4.c", "Bajo", "Gerencia X"]])
    _csv(tmp_path, "P9_conformes_v2.csv", ["id", "oferta", "seccion", "frase", "norma", "articulo", "tipo", "motivo"],
         [["P9-C01", "P9", "4.1 Tableros", "Los tableros serán IP55.", "NORM_02", "4.5", "cumple", "ok"]])
    t = X.cargar_trampas("P9", str(tmp_path))
    assert len(t) == 1 and t[0]["clase"] == "Crítico" and t[0]["fuente"] == "DESVIO" and t[0]["nivel"] == "Alto" and t[0]["regla_norm07"] == "3.3.c"
    c = X.cargar_conformes("P9", str(tmp_path))
    assert c == [{"proyecto": "Proyecto 9", "id": "P9-C01", "seccion": "4.1 Tableros", "cita_conforme": "Los tableros serán IP55.", "norma": "NORM_02", "articulo": "4.5",
                  "espejo_de_trampa": "", "veredicto_esperado": "cumple"}]
    assert X.cargar_trampas("P10", str(tmp_path)) == [] and X.cargar_conformes("P10", str(tmp_path)) == []


def test_falta_un_campo_obligatorio_falla(tmp_path):
    _csv(tmp_path, "P9_trampas_v2.csv", ["id", "oferta", "seccion", "fragmento_trampa", "norma", "articulo", "fuente", "clase", "nivel", "responsable"],
         [["P9-01-A", "P9", "3.1", "", "NORM_01", "2.5", "DESVIO", "Mayor", "Alto", "G"]])
    with pytest.raises(ValueError, match="fragmento_trampa"):
        X.cargar_trampas("P9", str(tmp_path))


# --- evaluar.py con el ground truth real de P6 ---

def _brecha(seccion, norma, articulo, cita, clase="Mayor"):
    return {"seccion": seccion, "seccion_oferta": seccion, "norma": norma, "articulo": articulo, "cita": cita, "clase": clase, "responsable": "", "nivel": ""}


def test_ground_truth_como_salida_da_100_y_salida_vacia_0():
    gt, esp = E.cargar_gt("P6"), E.cargar_espejos("P6")
    perfecta = {"registro_brechas": [_brecha(f["seccion"], f["norma"], f["articulo"], f["fragmento_trampa"], f["clase"]) for f in gt], "resumen_ejecutivo": {}}
    ev = E.evaluar(perfecta, gt, esp, "P6")
    assert (ev["encontradas"], ev["n_trampas"], ev["falsas_alarmas"], ev["n_espejos"], ev["clase_ok"]) == (15, 15, 0, 24, 15) and ev["extras"] == []
    vacia = E.evaluar({"registro_brechas": [], "resumen_ejecutivo": {}}, gt, esp, "P6")
    assert (vacia["encontradas"], vacia["falsas_alarmas"]) == (0, 0)


def test_un_conforme_marcado_cuenta_como_falsa_alarma():
    gt, esp = E.cargar_gt("P12"), E.cargar_espejos("P12")
    c = esp[0]
    ev = E.evaluar({"registro_brechas": [_brecha(c["seccion"], c["norma"], c["articulo"], c["cita_conforme"])], "resumen_ejecutivo": {}}, gt, esp, "P12")
    assert ev["falsas_alarmas"] == 1 and ev["encontradas"] == 0 and ev["extras"] == []


def test_pares_sin_respuesta():
    reg = [{"seccion": "S2", "norma": "NORM_01", "articulo": "2.5", "veredicto": None, "estado": "tiempo_agotado"},
           {"seccion": "S2", "norma": "NORM_01", "articulo": "2.6", "veredicto": None, "estado": "descartada", "motivo": "formato inválido tras reintentar"},
           {"seccion": "S2", "norma": "NORM_01", "articulo": "2.7", "veredicto": "Incumple", "estado": "clasificacion_fallida", "etapa": "clasificacion"},
           {"seccion": "S2", "norma": "NORM_01", "articulo": "2.8", "veredicto": "Cumple"},
           {"seccion": "S2", "norma": "NORM_01", "articulo": "2.9", "veredicto": "NO_APLICA", "estado": "descartada", "etapa": "clasificacion"}]
    ev = E.evaluar({"registro_brechas": [], "resumen_ejecutivo": {}, "registro_tecnico": reg}, [], [], "P7")
    assert ev["sin_respuesta"] == 3


@pytest.mark.parametrize("ruta,esperado", [
    ("datos/Resultados/P10_oferta_TVP/analisis_riesgos_P10_oferta_TVP_x.json", "P10"),
    ("P12=otra/ruta.json", "P12"),
    ("datos/Resultados/P1_oferta_TBP01/analisis_riesgos_P1_oferta_TBP01_x.json", "P1"),
    ("datos/Resultados/P7_oferta_PG25/a.json", "P7")])
def test_la_oferta_se_deduce_de_la_ruta_con_dos_digitos(ruta, esperado):
    assert E._oferta_de_ruta(ruta)[0] == esperado


# --- tabla_comparativa: bloque aparte para P6–P12 ---

def _ev(oferta, encontradas, falsas, brechas=10, agrupados=4, sin_respuesta=0):
    trampas = [{"id": f"{oferta}-{k:02d}-A", "estado": "encontrada" if k < encontradas else "no", "como_alerta": False, "por_frase": False, "verificado": True,
                "perezosa": False, "perezosa_clasificacion": False, "perdida": "encontrada" if k < encontradas else "no recuperada", "clase_esperada": "Mayor"} for k in range(15)]
    return {"modo": "brechas", "oferta": oferta, "n_trampas": 15, "encontradas": encontradas, "trampas": trampas, "n_espejos": 25, "falsas_alarmas": falsas, "espejos": [],
            "n_riesgo": brechas, "volumen": {"brechas": brechas, "riesgos agrupados": agrupados}, "extras": [], "coincidencias": [], "confusion": {}, "costo": None,
            "hay_registro": True, "solo_alerta": 0, "otro_articulo": 0, "por_frase": 0, "recall_articulo": 15, "perezosas": 0, "perezosas_clasificacion": 0,
            "marcas_no_verificadas": 0, "clase_ok": 0, "responsable_ok": 0, "nivel_ok": 0, "por_frase_validada": None, "precision": None, "precision_k": None,
            "precision_n": None, "extras_etiquetados": 0, "juez": None, "pares_juez_humano": [], "control_juez": None, "sin_respuesta": sin_respuesta}


def test_conjunto_externo():
    assert T.es_conjunto_externo(OFERTAS) and not T.es_conjunto_externo(["P1", "P6"]) and not T.es_conjunto_externo(["P5"]) and not T.es_conjunto_externo([])


def test_bloque_externo_por_oferta_con_ic_falsas_alarmas_y_riesgos():
    evaluadas = {"gpt-oss": {"P6": _ev("P6", 9, 1), "P7": _ev("P7", 6, 0, sin_respuesta=1)}}
    md = "\n".join(T.seccion_externa_md(evaluadas, {T.CONJUNTO_EXTERNO: ["P6", "P7"], "P1–P2 desarrollo": ["P1", "P2"]}))
    w = E.wilson(9, 15)
    assert f"## {T.CONJUNTO_EXTERNO}: detalle por oferta, gpt-oss" in md and "P1–P2" not in md
    assert f"| P6 | 9/15 (60%; {w[0]:.0%}–{w[1]:.0%}) |" in md and "| 1/25 (4%;" in md
    assert "| P7 | 6/15 (40%;" in md and "| 10 | 4 | 1 |" in md
    assert "| **Total P6+P7** | 15/30 (50%;" in md and "20 (10.0 / oferta) | 8 (4.0 / oferta) | 1 |" in md


def test_bloque_externo_avisa_si_falta_una_oferta_y_no_aparece_sin_conjunto_externo():
    md = "\n".join(T.seccion_externa_md({"c": {"P6": _ev("P6", 9, 1)}}, {T.CONJUNTO_EXTERNO: ["P6", "P7"]}))
    assert "Faltan P7 (sin JSON)" in md
    assert T.seccion_externa_md({"c": {"P1": _ev("P1", 9, 1)}}, {"P1": ["P1"]}) == []


def test_los_intervalos_no_toman_p6_p12_como_total_si_hay_p1_p4():
    filas = T.calcular_filas({"c": {o: _ev(o, 10, 0) for o in ["P1", "P2", "P3", "P4"] + OFERTAS}},
                             {"P1–P4 total": ["P1", "P2", "P3", "P4"], T.CONJUNTO_EXTERNO: OFERTAS})
    md = "\n".join(T.seccion_intervalos_md(filas))
    assert "| c | P1+P2+P3+P4 |" in md and "P6+P7" not in md
    solo = T.calcular_filas({"c": {o: _ev(o, 10, 0) for o in OFERTAS}}, {T.CONJUNTO_EXTERNO: OFERTAS})
    assert "| c | P6+P7+P8+P9+P10+P11+P12 |" in "\n".join(T.seccion_intervalos_md(solo))


def test_config_p6p12_tiene_las_siete_ofertas_en_un_conjunto_externo():
    cfg = T.cargar_config(T.os.path.join(T.AQUI, "config_p6p12.json"))
    assert list(cfg["conjuntos"]) == [T.CONJUNTO_EXTERNO] and cfg["conjuntos"][T.CONJUNTO_EXTERNO] == OFERTAS
    assert all(set(v) == set(OFERTAS) for v in cfg["configuraciones"].values())


# --- preparar_extras y verificar_gt_literal ---

def test_nombre_de_pendientes_ordena_las_ofertas_por_numero():
    assert PE.nombre_pendientes("gpt-oss-120b esfuerzo bajo (elegida)", ["P10", "P6", "P12", "P7"]) == "extras_pendientes_gpt-oss-120b-esfuerzo-bajo-elegida_P6P7P10P12.csv"
    assert PE.nombre_pendientes("x", ["P2", "P1"]) == "extras_pendientes_x_P1P2.csv"


def test_preparar_extras_acepta_p6(tmp_path):
    gt, esp = E.cargar_gt("P6"), E.cargar_espejos("P6")
    f = gt[0]
    ruta = tmp_path / "analisis_riesgos_P6_x.json"
    ruta.write_text(E.json.dumps({"resumen_ejecutivo": {}, "registro_brechas": [_brecha(f["seccion"], f["norma"], f["articulo"], f["fragmento_trampa"]),
                                                                                 _brecha("9.9 Otra", "NORM_03", "1.1", "Una oración que no es trampa.")]}), encoding="utf-8")
    r = PE.preparar_oferta("P6", str(ruta), gt, esp)
    assert (r["estado"], r["extras"], r["pendientes"]) == ("creado", 1, 1)


def test_verificar_gt_literal_marca_las_frases_que_aparecen_dos_veces():
    secciones = [{"id": "S2", "titulos": ["3 Alcance"], "introduccion": False, "texto": "", "oraciones": [("O1", "El plazo es de 14 días."), ("O2", "Otra cosa.")]},
                 {"id": "S3", "titulos": ["4 Plazos"], "introduccion": False, "texto": "", "oraciones": [("O1", "El plazo es de 14 días.")]}]
    filas = V.analizar("P9", "El plazo es de 14 días. Otra cosa. El plazo es de 14 días.", secciones,
                       [{"id": "P9-01-A", "fragmento_trampa": "El plazo es de 14 días"}], [{"id": "P9-C07", "cita_conforme": "Otra cosa."}])
    t, c = filas
    assert (t["ocurrencias"], t["reconocible"]) == (2, False) and (c["id"], c["ocurrencias"], c["reconocible"]) == ("P9-C07", 1, True)
    md = V.informe_md(filas)
    assert "P9-01-A (2)" in md and "trampas 0/1, conformes 1/1" in md


# --- Sensibilidad, detalle por trampa y embudo de P6–P12; diagnóstico de los pares sin clasificación ---

def _trampa_sintetica(id_, articulo, frase, severidad):
    return {"id": id_, "oferta": "P9", "tipo": "amenaza", "seccion": "3.1 Alcance", "fragmento_trampa": frase, "norma": "NORM_01", "articulo": articulo,
            "articulos_equivalentes": "", "clase": "Mayor", "nivel": "Alto", "responsable": "G", "severidad": severidad}


def _resultado_sintetico():
    """S1 = 3.1 Alcance. 2.5: brecha con su artículo; 2.6: Incumple con IDs malformados; 2.7: la frase de la trampa citada con otro artículo (2.8)."""
    reg = [{"seccion": "S1", "norma": "NORM_01", "articulo": "2.5", "veredicto": "Incumple", "estado": "ok"},
           {"seccion": "S1", "norma": "NORM_01", "articulo": "2.6", "veredicto": "Incumple", "estado": "descartada", "oraciones": ["[O3]"], "motivo": "IDs de oración inexistentes: [O3]"},
           {"seccion": "S1", "norma": "NORM_01", "articulo": "2.7", "veredicto": "Revisar", "estado": "descartada", "oraciones": ["O1", "O99"], "motivo": "IDs de oración inexistentes: O99"},
           {"seccion": "S1", "norma": "NORM_01", "articulo": "2.8", "veredicto": "Incumple", "estado": "ok"},
           {"seccion": "S1", "norma": "NORM_01", "articulo": "2.9", "veredicto": "Incumple", "estado": "descartada", "oraciones": [], "motivo": "sin oraciones de la oferta que respalden el veredicto"},
           {"seccion": "S1", "norma": "NORM_01", "articulo": "3.0", "veredicto": "Incumple", "estado": "ok"},
           {"seccion": "S1", "norma": "NORM_01", "articulo": "3.0", "veredicto": "CUMPLE", "estado": "no_es_riesgo", "etapa": "clasificacion"},
           {"seccion": "S1", "norma": "NORM_01", "articulo": "3.1", "veredicto": "Incumple", "estado": "ok"},
           {"seccion": "S1", "norma": "NORM_01", "articulo": "3.2", "veredicto": "Incumple", "estado": "ok"},
           {"seccion": "S1", "norma": "NORM_01", "articulo": "3.3", "veredicto": "Cumple", "estado": "ok"},
           {"seccion": "S1", "norma": "NORM_01", "articulo": "3.4.", "veredicto": "Incumple", "estado": "ok"}]
    brechas = [dict(_brecha("S1", "NORM_01", "2.5", "El plazo es de 14 días."), id="S1|NORM_01|2.5#2"),
               dict(_brecha("S1", "NORM_01", "2.8", "La garantía es de 6 meses."), id="S1|NORM_01|2.8"),
               dict(_brecha("S1", "NORM_01", "3.4.", "Otra frase."), id="S1|NORM_01|3.4.")]
    alertas = [{"seccion": "S1", "norma": "NORM_01", "articulo": "3.2", "cita": "x"}]
    return {"registro_brechas": brechas, "alertas": alertas, "resumen_ejecutivo": {}, "registro_tecnico": reg, "secciones": [{"id": "S1", "titulos": ["3.1 Alcance"]}]}


GT_SINTETICO = [_trampa_sintetica("P9-01-A", "2.5", "El plazo es de 14 días", "Alta"), _trampa_sintetica("P9-02-M", "2.6", "Los tableros serán IP54", "Media"),
                _trampa_sintetica("P9-03-B", "2.7", "La garantía es de 6 meses", "Baja")]


def test_evaluar_da_severidad_y_frase_en_su_seccion():
    ev = E.evaluar(_resultado_sintetico(), GT_SINTETICO, [], "P9")
    t = {x["id"]: x for x in ev["trampas"]}
    assert t["P9-01-A"]["estado"] == "encontrada" and t["P9-03-B"]["estado"] == "otro artículo" and t["P9-02-M"]["estado"] == "no"
    assert [t[i]["por_frase_seccion"] for i in ("P9-01-A", "P9-02-M", "P9-03-B")] == [True, False, True] and t["P9-02-M"]["severidad"] == "Media"
    otra_seccion = _resultado_sintetico()
    otra_seccion["registro_brechas"][1]["seccion"] = "S7"      # la frase citada fuera de su sección no cuenta para el recall por frase
    assert not {x["id"]: x for x in E.evaluar(otra_seccion, GT_SINTETICO, [], "P9")["trampas"]}["P9-03-B"]["por_frase_seccion"]


def test_sensibilidad_por_frase_y_por_severidad():
    md = "\n".join(T.sensibilidad_externa_md(E.evaluar(_resultado_sintetico(), GT_SINTETICO, [], "P9")["trampas"]))
    w = E.wilson(2, 3)
    assert "Análisis posterior" in md and f"Recall por frase (fragmento de la trampa citado en su sección, con cualquier artículo): 2/3 (67%; {w[0]:.0%}–{w[1]:.0%})" in md
    assert "Alta 1/1 (100%;" in md and "Media 0/1 (0%;" in md and "Baja 0/1 (0%;" in md
    assert "n/d (el ground truth no trae severidad)" in "\n".join(T.sensibilidad_externa_md(_ev("P6", 3, 0)["trampas"]))


def test_detalle_trampas_csv(tmp_path):
    ruta = tmp_path / "detalle_trampas.csv"
    T.guardar_detalle_trampas({"c": {"P9": E.evaluar(_resultado_sintetico(), GT_SINTETICO, [], "P9")}}, str(ruta))
    filas = E.leer_csv(str(ruta))
    assert list(filas[0]) == T.CAMPOS_DETALLE_TRAMPAS and len(filas) == 3
    f = {x["id"]: x for x in filas}
    assert (f["P9-03-B"]["estado"], f["P9-03-B"]["articulo_citado"], f["P9-03-B"]["por_frase"], f["P9-03-B"]["severidad"]) == ("otro artículo", "NORM_01 Art. 2.8", "1", "Baja")
    assert (f["P9-02-M"]["verificacion"], f["P9-02-M"]["clasificacion"], f["P9-01-A"]["articulo_gt"]) == ("Incumple", "—", "NORM_01 2.5")


def test_embudo_externo(tmp_path):
    ev = E.evaluar(_resultado_sintetico(), GT_SINTETICO, [], "P9")
    assert T.etapas_embudo(ev["trampas"]) == {"trampas": 3, "recuperadas": 3, "incumple": 3, "encontradas": 1, "otro_articulo": 1}
    ruta = tmp_path / "b.png"
    assert T.grafico_embudo_externo({"c": {"P9": ev}}, ["P9"], ["c"], str(ruta), "P9") is True and ruta.stat().st_size > 1000
    assert T.grafico_embudo_externo({"c": {"P9": ev}}, ["P9", "P10"], ["c"], str(tmp_path / "x.png")) is False


def test_diagnostico_sin_clasificacion_por_causa_y_claves():
    from evaluacion import diagnostico_sin_clasificacion as D
    d = D.diagnosticar(_resultado_sintetico(), GT_SINTETICO, [], "P9")
    causas = {f["articulo"]: f["causa"] for f in d["filas"]}
    # 2.5 y 2.8 tienen brecha (2.5 con #parte en el id), 3.2 tiene alerta, 3.3 es Cumple: no entran
    assert causas == {"2.6": "ids_inexistentes_malformados", "2.7": "ids_inexistentes_fuera_de_rango", "2.9": "sin_oraciones", "3.0": "clasificacion_no_es_riesgo",
                      "3.1": "inconsistente"}
    f = {x["articulo"]: x for x in d["filas"]}
    assert f["2.6"]["llm2"] == "—" and f["3.0"]["llm2"] == "CUMPLE" and "válidas: O1" in f["2.7"]["detalle"]
    assert (f["2.6"]["trampas"], f["2.6"]["estado_final_trampa"], f["2.7"]["estado_final_trampa"]) == ("P9-02-M", "no", "otro artículo")
    # «3.4.»: la brecha existe por campos pero la clave por id (sin normalizar el artículo) no la ve
    assert d["difieren_claves"] == [("S1", "NORM_01", "3.4")]
    md = D.resumen_md(d["filas"], {"P9": d["difieren_claves"]}, 1, "c")
    assert "**5**" in md and "| P9 | 1 | 1 | 1 | 1 | 0 | 4 |" in md and "| P9 | P9-02-M | Media | S1 NORM_01 2.6 | ids_inexistentes_malformados |" in md
