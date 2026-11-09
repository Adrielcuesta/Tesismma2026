import csv
import json
import os
from types import SimpleNamespace

import pytest

from evaluacion import evaluar as ev
from evaluacion import juez, muestra_validacion as mv, tabla_comparativa as tc
from scripts.nube import PresupuestoAgotado

GT = [
    {"id": "P9-01", "oferta": "P9", "seccion": "3", "fragmento_trampa": "la cantidad ofertada es de una unidad", "norma": "NORM_01", "articulo": "4.2",
     "articulos_equivalentes": "", "clase": "Mayor", "nivel": "Alto", "responsable": "Gerencia A"},
    {"id": "P9-02", "oferta": "P9", "seccion": "4", "fragmento_trampa": "texto que nadie cita", "norma": "NORM_04", "articulo": "3.1",
     "articulos_equivalentes": "", "clase": "Crítico", "nivel": "Medio", "responsable": "Gerencia D"},
]
ESPEJOS = [{"proyecto": "Proyecto 9", "seccion": "3", "cita_conforme": "La cantidad de apoyos cumple con dos unidades", "norma": "NORM_01", "articulo": "4.3", "espejo_de_trampa": "P9-01"}]


def _brecha(cita, norma, articulo, seccion="3 Sección"):
    return {"seccion": "3", "seccion_oferta": seccion, "norma": norma, "articulo": articulo, "cita": cita, "clase": "Mayor", "nivel": "Alto", "responsable": "G",
            "titulo": "t", "enunciado": "e", "motivo": "m", "texto_articulo": f"Texto del {norma} {articulo}", "oraciones_texto": {"O1": cita}}


RESULTADO = {"registro_brechas": [_brecha("Se indica que la cantidad ofertada es de una unidad.", "NORM_01", "4.2"),
                                  _brecha("Los tableros se entregan sin reserva.", "NORM_02", "5.1", "8 Conexiones"),
                                  _brecha("El plazo se informa luego.", "NORM_03", "1.1", "9 Plazo")],
             "riesgos": [{}], "solicitudes": [], "alertas": []}


def _evaluado():
    return ev.evaluar(RESULTADO, [dict(r) for r in GT], [dict(r) for r in ESPEJOS], "P9")


class ClienteFalso:
    def __init__(self, respuestas):
        self.respuestas, self.llamadas = list(respuestas), 0

    def invocar(self, mensajes, config=None):
        self.llamadas += 1
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return SimpleNamespace(content=r)


def _ok(v, motivo="porque"):
    return json.dumps({"motivo": motivo, "veredicto": v})


def _carpeta(tmp_path, nombre="analisis.json"):
    """JSON de una oferta con 2 extras (sin que evaluar.py haya corrido)."""
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps(RESULTADO), encoding="utf-8")
    return str(ruta)


def _juzgar(ruta, cliente, concurrencia=1, **kw):
    return juez.procesar_json(ruta, "P9", cliente, None, concurrencia, gt=[dict(r) for r in GT], espejos=[dict(r) for r in ESPEJOS], **kw)


def _leer(ruta):
    return ev.leer_csv(ruta)


# --- juez ---

def test_juez_escribe_veredictos_sin_tocar_la_columna_humana(tmp_path):
    ruta = _carpeta(tmp_path)
    cliente = ClienteFalso([_ok("VALIDA"), _ok("DUDOSA")])
    s = _juzgar(ruta, cliente, 2)
    filas = _leer(s["csv"])
    assert [f["juez_veredicto"] for f in filas] == ["VALIDA", "DUDOSA"] and filas[0]["juez_motivo"] == "porque"
    assert all(f["valido"] == "" for f in filas) and s["cuentas"] == {"VALIDA": 1, "NO_VALIDA": 0, "DUDOSA": 1}


def test_juez_no_repite_lo_ya_juzgado_y_conserva_marca_humana(tmp_path):
    ruta = _carpeta(tmp_path)
    s = _juzgar(ruta, ClienteFalso([_ok("VALIDA"), _ok("NO_VALIDA")]))
    filas = _leer(s["csv"])
    filas[0]["valido"] = "sí"
    with open(s["csv"], "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]), delimiter=";")
        w.writeheader()
        w.writerows(filas)
    cliente = ClienteFalso([])
    s = _juzgar(ruta, cliente)
    assert cliente.llamadas == 0 and s["juzgados"] == 0
    assert _leer(s["csv"])[0]["valido"] == "sí"


def test_juez_max_items_y_reintento_por_respuesta_invalida(tmp_path):
    ruta = _carpeta(tmp_path)
    cliente = ClienteFalso(["no es json", _ok("NO_VALIDA")])
    s = _juzgar(ruta, cliente, max_items=1)
    filas = _leer(s["csv"])
    assert cliente.llamadas == 2 and filas[0]["juez_veredicto"] == "NO_VALIDA" and filas[1]["juez_veredicto"] == "" and s["sin_veredicto"] == 1


def test_juez_se_detiene_si_se_agota_el_presupuesto(tmp_path):
    ruta = _carpeta(tmp_path)
    s = _juzgar(ruta, ClienteFalso([PresupuestoAgotado("tope"), PresupuestoAgotado("tope")]))
    assert s["detenida"] and s["sin_veredicto"] == 2


def test_juez_calcula_los_extras_sin_que_evaluar_haya_corrido(tmp_path):
    ruta = _carpeta(tmp_path)
    assert os.listdir(tmp_path) == ["analisis.json"]
    s = _juzgar(ruta, ClienteFalso([_ok("VALIDA"), _ok("NO_VALIDA")]))
    filas = _leer(s["csv"])
    assert [f["norma"] for f in filas] == ["NORM_02", "NORM_03"] and list(filas[0])[:8] == juez.COLUMNAS_EXTRAS     # la trampa no es un extra


# --- control del juez sobre espejos ---

def _con_espejo(tmp_path, nombre="analisis_esp.json"):
    """JSON con una trampa, un extra, una brecha sobre el espejo (misma frase y artículo), la misma frase con otro artículo y una descartada sobre el espejo."""
    frase = "La cantidad de apoyos cumple con dos unidades."
    resultado = {**RESULTADO, "registro_brechas": RESULTADO["registro_brechas"][:2] + [
        _brecha(frase, "NORM_01", "4.3", "3 Sección"), _brecha(frase, "NORM_02", "9.9"), {**_brecha(frase, "NORM_01", "4.3"), "estado": ev.ESTADO_DESCARTADA_CALCULO}]}
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps(resultado), encoding="utf-8")
    return str(ruta)


def test_brechas_sobre_espejos_solo_la_misma_frase_y_articulo_sin_descartadas(tmp_path):
    resultado = json.loads(open(_con_espejo(tmp_path), encoding="utf-8").read())
    b = juez.brechas_sobre_espejos(resultado, [dict(r) for r in ESPEJOS])
    assert [(x["norma"], x["articulo"]) for x in b] == [("NORM_01", "4.3")]
    assert juez.brechas_sobre_espejos(RESULTADO, [dict(r) for r in ESPEJOS]) == []


def test_control_del_juez_escribe_csv_y_cuenta_no_valida(tmp_path):
    ruta = _con_espejo(tmp_path)
    cliente = ClienteFalso([_ok("NO_VALIDA")])
    s = juez.procesar_espejos(ruta, "P9", cliente, None, 1, espejos=[dict(r) for r in ESPEJOS])
    assert s["csv"] == ev.ruta_juez_espejos(ruta) and s["csv"].endswith("analisis_esp_juez_espejos.csv")
    assert (s["items"], s["juzgados"], s["no_valida"], s["sin_veredicto"]) == (1, 1, 1, 0) and _leer(s["csv"])[0]["juez_veredicto"] == "NO_VALIDA"
    assert not os.path.exists(ev.ruta_juez(ruta))                      # el CSV del juez normal no se toca
    otra = ClienteFalso([])
    assert juez.procesar_espejos(ruta, "P9", otra, None, 1, espejos=[dict(r) for r in ESPEJOS])["juzgados"] == 1 and otra.llamadas == 0     # no repite lo juzgado
    s = juez.procesar_espejos(ruta, "P9", ClienteFalso([_ok("VALIDA")]), None, 1, rehacer=True, espejos=[dict(r) for r in ESPEJOS])
    assert s["no_valida"] == 0 and s["juzgados"] == 1


def test_control_del_juez_en_la_tabla_y_n_d_sin_csv(tmp_path):
    ruta = _con_espejo(tmp_path)
    juez.procesar_espejos(ruta, "P9", ClienteFalso([_ok("NO_VALIDA")]), None, 1, espejos=[dict(r) for r in ESPEJOS])
    con = ev.evaluar_archivo(ruta, "P9", [dict(r) for r in GT], [dict(r) for r in ESPEJOS])
    sin = ev.evaluar_archivo(_con_espejo(tmp_path, "otro.json"), "P9", [dict(r) for r in GT], [dict(r) for r in ESPEJOS])
    assert con["control_juez"] == {"n": 1, "no_valida": 1} and sin["control_juez"] is None
    md = tc.tabla_md(tc.calcular_filas({"c": {"P9": con}, "d": {"P9": sin}}, {"P9 solo": ["P9"]}))
    assert "Control del juez" in md and "1/1 (100%)" in md


# --- nombres de los CSV por JSON ---

def test_nombres_de_csv_por_json(tmp_path):
    assert ev.ruta_extras(tmp_path / "a_32b.json") == str(tmp_path / "a_32b_extras.csv")
    assert ev.ruta_juez(tmp_path / "a_32b.json") == str(tmp_path / "a_32b_juez.csv")


def test_dos_json_en_la_misma_carpeta_no_se_pisan(tmp_path):
    a, b = _carpeta(tmp_path, "analisis_8b.json"), _carpeta(tmp_path, "analisis_32b.json")
    ev.guardar_extras_csv(_evaluado(), ev.ruta_extras(a))
    ev.guardar_extras_csv(_evaluado(), ev.ruta_extras(b))
    sa = _juzgar(a, ClienteFalso([_ok("VALIDA"), _ok("VALIDA")]))
    sb = _juzgar(b, ClienteFalso([_ok("NO_VALIDA"), _ok("DUDOSA")]))
    assert sa["csv"] != sb["csv"] and sorted(os.listdir(tmp_path)) == ["analisis_32b.json", "analisis_32b_extras.csv", "analisis_32b_juez.csv",
                                                                       "analisis_8b.json", "analisis_8b_extras.csv", "analisis_8b_juez.csv"]
    assert [f["juez_veredicto"] for f in _leer(sa["csv"])] == ["VALIDA", "VALIDA"] and [f["juez_veredicto"] for f in _leer(sb["csv"])] == ["NO_VALIDA", "DUDOSA"]


def test_la_marca_humana_de_extras_pasa_al_csv_del_juez_y_no_se_pierde_al_reevaluar(tmp_path):
    ruta = _carpeta(tmp_path)
    ev.guardar_extras_csv(_evaluado(), ev.ruta_extras(ruta))
    filas = _leer(ev.ruta_extras(ruta))
    filas[0]["valido"] = "sí"
    with open(ev.ruta_extras(ruta), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]), delimiter=";")
        w.writeheader()
        w.writerows(filas)
    ev.guardar_extras_csv(_evaluado(), ev.ruta_extras(ruta))              # evaluar de nuevo no borra la revisión
    assert _leer(ev.ruta_extras(ruta))[0]["valido"] == "sí"
    assert _leer(_juzgar(ruta, ClienteFalso([_ok("VALIDA"), _ok("VALIDA")]))["csv"])[0]["valido"] == "sí"


def test_extras_revision_viejo_no_se_usa_y_se_avisa(tmp_path, capsys):
    ruta = _carpeta(tmp_path)
    ev.guardar_extras_csv(_evaluado(), str(tmp_path / "extras_revision.csv"))
    filas = _leer(str(tmp_path / "extras_revision.csv"))
    with open(tmp_path / "extras_revision.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]), delimiter=";")
        w.writeheader()
        w.writerows([{**x, "valido": "sí"} for x in filas])
    e = ev.evaluar_archivo(ruta, "P9", [dict(r) for r in GT], [dict(r) for r in ESPEJOS])
    assert "extras_revision.csv" in capsys.readouterr().err and e["precision"] is None      # sigue pendiente: la revisión vieja se ignora


def test_mensajes_del_juez_no_llevan_nada_del_ground_truth():
    texto = "\n".join(m.content for m in juez.armar_mensajes(RESULTADO["registro_brechas"][1], ["ítem 1"]))
    assert "Texto del NORM_02 5.1" in texto and "Los tableros se entregan sin reserva." in texto and "ground" not in texto.lower()


# --- evaluar: precisión según el juez ---

def _juez_rows(ve):
    return [{"seccion": x["seccion"], "norma": x["norma"], "articulo": x["articulo"], "cita": x["cita"], "juez_veredicto": v}
            for x, v in zip(_evaluado()["extras"], ve)]


def test_precision_del_juez_estricta_y_amplia():
    e = _evaluado()
    assert e["encontradas"] == 1 and e["n_riesgo"] == 3 and len(e["extras"]) == 2
    ev.asignar_juez(e, _juez_rows(["VALIDA", "DUDOSA"]), None)
    assert e["juez"] == {"estricta": 2, "amplia": 3, "n": 3}
    ev.asignar_juez(e, _juez_rows(["VALIDA", ""]), None)
    assert e["juez"] is None


def test_acuerdo_juez_humano_con_kappa_de_cohen():
    e = _evaluado()
    rev = [{**r, "valido": h} for r, h in zip(_juez_rows(["VALIDA", "NO_VALIDA"]), ["sí", "no"])]
    ev.asignar_juez(e, _juez_rows(["VALIDA", "NO_VALIDA"]), rev)
    assert e["pares_juez_humano"] == [("VALIDA", True), ("NO_VALIDA", False)]
    assert ev.cohen_kappa([(True, True), (False, False)]) == 1.0
    assert ev.cohen_kappa([(True, False), (False, True)]) == -1.0
    assert ev.cohen_kappa([]) is None and ev.cohen_kappa([(True, True), (True, True)]) is None


def test_informe_incluye_juez_f1_f2_y_kappa():
    e = _evaluado()
    rev = [{**r, "valido": h} for r, h in zip(_juez_rows(["VALIDA", "DUDOSA"]), ["sí", "no"])]
    ev.asignar_juez(e, _juez_rows(["VALIDA", "DUDOSA"]), rev)
    texto = ev.informe_md(e)
    assert "Precisión según el juez, estricta" in texto and "amplia" in texto and "F1 / F2 según el juez" in texto and "kappa de Cohen" in texto


def test_marcas_humanas_del_csv_del_juez_pisan_las_de_extras_revision():
    base = [{"seccion": "s", "norma": "N", "articulo": "1", "cita": "c", "valido": ""}]
    fusion = ev.revision_con_marcas_juez(base, [{**base[0], "valido": "no"}])
    assert len(fusion) == 1 and fusion[0]["valido"] == "no"


# --- muestra de validación ---

def test_cuotas_suman_n_y_respetan_tamanos():
    q = mv.cuotas({("a", "VALIDA"): 100, ("a", "DUDOSA"): 3, ("b", "VALIDA"): 40, ("b", "NO_VALIDA"): 1}, 30)
    assert sum(q.values()) == 30 and q[("a", "DUDOSA")] >= 1 and q[("b", "NO_VALIDA")] == 1 and all(v >= 1 for v in q.values())
    assert mv.cuotas({"x": 5}, 30) == {"x": 5}


def test_muestra_determinista_y_sin_veredicto():
    filas = [{"configuracion": "c" + str(i % 2), "oferta": "P1", "ruta_juez": "r", "veredicto": ("VALIDA", "NO_VALIDA", "DUDOSA")[i % 3], "seccion": "s", "norma": "N",
              "articulo": str(i), "cita": f"cita {i}", "titulo": "", "texto_articulo": ""} for i in range(60)]
    a, b = mv.muestrear(filas, 30, 42), mv.muestrear(filas, 30, 42)
    assert len(a) == 30 and [x["cita"] for x in a] == [x["cita"] for x in b] and "veredicto" not in mv.COLUMNAS


def test_volcar_marcas_en_el_csv_del_juez(tmp_path):
    ruta = _carpeta(tmp_path)
    s = _juzgar(ruta, ClienteFalso([_ok("VALIDA"), _ok("NO_VALIDA")]))
    filas = _leer(s["csv"])
    muestra = [{"id": i, "configuracion": "c", "oferta": "P9", "seccion": f["seccion"], "norma": f["norma"], "articulo": f["articulo"], "cita": f["cita"], "titulo": "",
                "texto_articulo": "", "valido": v, "ruta_juez": s["csv"]} for i, (f, v) in enumerate(zip(filas, ["1", ""]))]
    mv.escribir(muestra, str(tmp_path / "m.csv"))
    r = mv.volcar(str(tmp_path / "m.csv"))
    despues = _leer(s["csv"])
    assert r == {"volcadas": 1, "sin_marca": 1, "no_encontradas": 0} and despues[0]["valido"] == "sí" and despues[1]["valido"] == ""
    assert despues[0]["juez_veredicto"] == "VALIDA"


# --- modo "auto" de la configuración ---

def _json_con_condicion(carpeta, nombre, condicion, mtime):
    ruta = carpeta / nombre
    ruta.write_text(json.dumps({"configuracion_analisis": {"condicion": condicion}}), encoding="utf-8")
    os.utime(ruta, (mtime, mtime))


def test_auto_por_condicion_elige_el_mas_reciente_sin_deepinfra_reclasificado_ni_parcial(tmp_path):
    _json_con_condicion(tmp_path, "analisis_riesgos_P3_a_viejo.json", "rag_verificacion", 1000)
    _json_con_condicion(tmp_path, "analisis_riesgos_P3_b_elegido.json", "rag_verificacion", 2000)
    _json_con_condicion(tmp_path, "analisis_riesgos_P3_c_otra_condicion.json", "sin_rag", 3000)
    _json_con_condicion(tmp_path, "analisis_riesgos_P3_d_deepinfra-qwen3-32b.json", "rag_verificacion", 4000)
    _json_con_condicion(tmp_path, "analisis_riesgos_P3_e_reclasificado.json", "rag_verificacion", 5000)
    _json_con_condicion(tmp_path, "analisis_riesgos_P3_f_parcial.json", "rag_verificacion", 6000)
    valor = {"auto": {"carpeta": str(tmp_path), "condicion": "rag_verificacion"}}
    assert os.path.basename(tc.resolver_ruta(valor, "x")) == "analisis_riesgos_P3_b_elegido.json"


def test_auto_por_sufijo_elige_el_mas_reciente_y_no_confunde_humo(tmp_path):
    for nombre, t in (("analisis_riesgos_P4_1_deepinfra-qwen3-32b-thinking-amplio.json", 1000), ("analisis_riesgos_P4_2_deepinfra-qwen3-32b-thinking-amplio.json", 2000),
                      ("analisis_riesgos_P4_3_deepinfra-qwen3-32b-thinking-amplio-humo10.json", 3000), ("analisis_riesgos_P4_4_deepinfra-qwen3-32b-thinking.json", 4000)):
        _json_con_condicion(tmp_path, nombre, "rag_verificacion", t)
    valor = {"auto": {"carpeta": str(tmp_path), "sufijo": "deepinfra-qwen3-32b-thinking-amplio"}}
    assert os.path.basename(tc.resolver_ruta(valor, "x")) == "analisis_riesgos_P4_2_deepinfra-qwen3-32b-thinking-amplio.json"


def test_auto_sin_resultado_se_omite_con_aviso_y_las_rutas_normales_pasan_igual(tmp_path, capsys):
    cfg = {"configuraciones": {"c": {"P3": {"auto": {"carpeta": str(tmp_path), "condicion": "rag_verificacion"}}, "P1": "ruta/fija.json", "P2": ""}}}
    assert tc.resolver_config(cfg) == {"c": {"P3": "", "P1": "ruta/fija.json", "P2": ""}}
    assert "no hay JSON todavía" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        tc.resolver_ruta({"auto": {"carpeta": str(tmp_path)}}, "x")


def test_resolver_imprime_json_ascii_para_el_script(tmp_path, capsys):
    _json_con_condicion(tmp_path, "analisis_riesgos_P3_ok.json", "rag_verificacion", 1000)
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"configuraciones": {"32B con razonamiento + recuperación amplia": {"P3": {"auto": {"carpeta": str(tmp_path), "condicion": "rag_verificacion"}}}}}), encoding="utf-8")
    tc.main(["--config", str(cfg), "--resolver"])
    salida = json.loads(capsys.readouterr().out)
    assert list(salida["configuraciones"]) == ["32B con razonamiento + recuperación amplia"]
    assert salida["configuraciones"]["32B con razonamiento + recuperación amplia"]["P3"].endswith("analisis_riesgos_P3_ok.json")


def test_config_final_se_carga_y_tiene_las_cuatro_configuraciones_y_los_dos_auto():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evaluacion", "config_final.json")
    cfg = tc.cargar_config(ruta)
    assert len(cfg["configuraciones"]) == 4 and set(cfg["sin_rag"]) == {"P1", "P2", "P3", "P4"}
    autos = [(n, o) for n, ofertas in cfg["configuraciones"].items() for o, v in ofertas.items() if isinstance(v, dict)]
    assert autos == [("qwen3:8b local", "P3"), ("qwen3:8b local", "P4"), ("32B con razonamiento + recuperación amplia", "P4")]
    for oferta in ("P3", "P4"):      # el 8B: condición rag_seccion y, además, modo verificación (no el modo lista)
        a = cfg["configuraciones"]["qwen3:8b local"][oferta]["auto"]
        assert a["condicion"] == "rag_seccion" and a["modo_generacion"] == "verificacion"


def test_auto_con_modo_generacion_exige_verificacion(tmp_path):
    def escribir(nombre, modo, mtime):
        ruta = tmp_path / nombre
        ruta.write_text(json.dumps({"configuracion_analisis": {"condicion": "rag_seccion", "modo_generacion": modo}}), encoding="utf-8")
        os.utime(ruta, (mtime, mtime))
    escribir("analisis_riesgos_P3_a_verif.json", "verificacion", 1000)
    escribir("analisis_riesgos_P3_b_lista.json", "lista", 2000)           # más reciente, pero en modo lista
    valor = {"auto": {"carpeta": str(tmp_path), "condicion": "rag_seccion", "modo_generacion": "verificacion"}}
    assert os.path.basename(tc.resolver_ruta(valor, "x")) == "analisis_riesgos_P3_a_verif.json"
    sin_filtro = {"auto": {"carpeta": str(tmp_path), "condicion": "rag_seccion"}}
    assert os.path.basename(tc.resolver_ruta(sin_filtro, "x")) == "analisis_riesgos_P3_b_lista.json"      # el filtro es opcional


def test_comparacion_con_rag_frente_a_sin_rag_con_mcnemar(tmp_path, monkeypatch):
    monkeypatch.setattr(tc.E, "cargar_gt", lambda oferta: [dict(r) for r in GT])
    monkeypatch.setattr(tc.E, "cargar_espejos", lambda oferta: [dict(r) for r in ESPEJOS])
    lista = {"configuracion_analisis": {"condicion": "sin_rag"}, "registro_brechas": [], "resumen_ejecutivo": None,
             "riesgos_identificados_estructurados": [{"descripcion_riesgo": "d", "cita_oferta": "Se indica que la cantidad ofertada es de una unidad."}]}
    sin = {}
    for oferta in ("P8", "P9"):
        ruta = tmp_path / f"sin_{oferta}.json"
        ruta.write_text(json.dumps(lista), encoding="utf-8")
        sin[oferta] = str(ruta)
    ev_con = {o: ev.evaluar(RESULTADO, [dict(r) for r in GT], [dict(r) for r in ESPEJOS], o) for o in ("P8", "P9")}
    cfg = {"configuraciones": {"8B": {}, "otra": {}}, "sin_rag": {**sin, "P7": ""}, "conjuntos": {"P8–P9": ["P8", "P9"], "solo P9": ["P9"], "con P7": ["P7", "P8"]}}
    texto = tc.comparacion_sin_rag(cfg, {"8B": ev_con})
    assert "## P8–P9" in texto and "McNemar" in texto and "Con RAG" in texto and "Sin RAG" in texto
    assert "## solo P9" not in texto and "## con P7" not in texto            # solo conjuntos de 2 o más ofertas completos en ambos lados
    assert tc.comparacion_sin_rag({"configuraciones": {"8B": {}}, "conjuntos": {}}, {}) is None


# --- script de cierre ---

def test_script_cerrar_evaluacion_es_ascii_y_llama_a_los_modulos_en_orden():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "cerrar_evaluacion.ps1")
    with open(ruta, "rb") as f:
        crudo = f.read()
    crudo.decode("ascii")
    texto = crudo.decode("ascii")
    assert texto.index("evaluacion.evaluar") < texto.index("evaluacion.juez") < texto.index("evaluacion.tabla_comparativa") and "--max-items" in texto and "-SoloHumo" in texto
    assert "return" not in texto
    assert texto.index("evaluacion.juez") < texto.index('"--espejos"') < texto.index("evaluacion.tabla_comparativa")      # el control corre después del juez normal


# --- tabla comparativa ---

def _filas():
    e = _evaluado()
    ev.asignar_juez(e, _juez_rows(["VALIDA", "NO_VALIDA"]), None)
    e["costo"] = {"tiempo_total_s": 3725, "costo_usd": 0.12, "tokens_entrada_total": 1000, "tokens_salida_total": 200}
    return tc.calcular_filas({"8B local": {"P9": e}, "32B": {"P9": e}}, {"P9 solo": ["P9"], "P9–P8": ["P9", "P8"]})


def test_tabla_calcula_metricas_y_omite_conjuntos_incompletos():
    filas = _filas()
    assert {f["conjunto"] for f in filas} == {"P9 solo"} and len(filas) == 2
    f = filas[0]
    assert f["encontradas"] == 1 and f["trampas"] == 2 and f["recall"] == 0.5 and f["precision_juez_estricta"] == pytest.approx(2 / 3)
    assert f["costo_usd"] == 0.12 and f["tokens_entrada"] == 1000 and f["brechas_por_oferta"] == 3 and f["falsas_alarmas"] == 0
    md = tc.tabla_md(filas)
    assert "## P9 solo" in md and "1/2 (50%" in md and "1:02:05" in md


def test_tabla_guarda_csv(tmp_path):
    tc.guardar_csv(_filas(), str(tmp_path / "t.csv"))
    filas = _leer(str(tmp_path / "t.csv"))
    assert len(filas) == 2 and filas[0]["configuracion"] == "8B local" and filas[0]["recall"] == "0.5"


def test_graficos_se_generan(tmp_path):
    pytest.importorskip("matplotlib")
    filas = _filas()
    tc.grafico_recall_falsas(filas, str(tmp_path / "a.png"), "P9 solo", "P9 solo")
    tc.grafico_embudo(filas, str(tmp_path / "b.png"), "P9 solo")
    tc.grafico_recall_costo_tiempo(filas, str(tmp_path / "c.png"), "P9 solo")
    assert all(os.path.getsize(tmp_path / n) > 1000 for n in ("a.png", "b.png", "c.png"))


def test_etiquetas_cortas_solo_para_graficos_y_la_tabla_conserva_el_nombre_largo():
    assert [tc._corta(n) for n in ("qwen3:8b local", "Qwen3-32B", "Qwen3-32B con razonamiento", "32B con razonamiento + recuperación amplia")] == [
        "8B local", "32B", "32B razon.", "32B razon. + amplia"]
    assert tc._corta("otro nombre") == "otro nombre"
    assert "8B local" in tc.tabla_md(_filas())  # la tabla usa el nombre de la configuración tal cual
