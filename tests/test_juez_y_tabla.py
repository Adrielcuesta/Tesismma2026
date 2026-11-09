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


def _carpeta(tmp_path):
    """JSON + extras_revision.csv de una oferta con 2 extras, como los deja evaluar.py."""
    ruta = tmp_path / "analisis.json"
    ruta.write_text(json.dumps(RESULTADO), encoding="utf-8")
    ev.guardar_extras_csv(_evaluado(), str(tmp_path / "extras_revision.csv"))
    return str(ruta)


def _leer(ruta):
    return ev.leer_csv(ruta)


# --- juez ---

def test_juez_escribe_veredictos_sin_tocar_la_columna_humana(tmp_path):
    ruta = _carpeta(tmp_path)
    cliente = ClienteFalso([_ok("VALIDA"), _ok("DUDOSA")])
    s = juez.procesar_json(ruta, cliente, ["item"], 2)
    filas = _leer(s["csv"])
    assert [f["juez_veredicto"] for f in filas] == ["VALIDA", "DUDOSA"] and filas[0]["juez_motivo"] == "porque"
    assert all(f["valido"] == "" for f in filas) and s["cuentas"] == {"VALIDA": 1, "NO_VALIDA": 0, "DUDOSA": 1}


def test_juez_no_repite_lo_ya_juzgado_y_conserva_marca_humana(tmp_path):
    ruta = _carpeta(tmp_path)
    s = juez.procesar_json(ruta, ClienteFalso([_ok("VALIDA"), _ok("NO_VALIDA")]), None, 1)
    filas = _leer(s["csv"])
    filas[0]["valido"] = "sí"
    with open(s["csv"], "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]), delimiter=";")
        w.writeheader()
        w.writerows(filas)
    cliente = ClienteFalso([])
    s = juez.procesar_json(ruta, cliente, None, 1)
    assert cliente.llamadas == 0 and s["juzgados"] == 0
    assert _leer(s["csv"])[0]["valido"] == "sí"


def test_juez_max_items_y_reintento_por_respuesta_invalida(tmp_path):
    ruta = _carpeta(tmp_path)
    cliente = ClienteFalso(["no es json", _ok("NO_VALIDA")])
    s = juez.procesar_json(ruta, cliente, None, 1, max_items=1)
    filas = _leer(s["csv"])
    assert cliente.llamadas == 2 and filas[0]["juez_veredicto"] == "NO_VALIDA" and filas[1]["juez_veredicto"] == "" and s["sin_veredicto"] == 1


def test_juez_se_detiene_si_se_agota_el_presupuesto(tmp_path):
    ruta = _carpeta(tmp_path)
    s = juez.procesar_json(ruta, ClienteFalso([PresupuestoAgotado("tope"), PresupuestoAgotado("tope")]), None, 1)
    assert s["detenida"] and s["sin_veredicto"] == 2


def test_juez_exige_extras_revision(tmp_path):
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        juez.procesar_json(str(tmp_path / "a.json"), ClienteFalso([]), None, 1)


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
    s = juez.procesar_json(ruta, ClienteFalso([_ok("VALIDA"), _ok("NO_VALIDA")]), None, 1)
    filas = _leer(s["csv"])
    muestra = [{"id": i, "configuracion": "c", "oferta": "P9", "seccion": f["seccion"], "norma": f["norma"], "articulo": f["articulo"], "cita": f["cita"], "titulo": "",
                "texto_articulo": "", "valido": v, "ruta_juez": s["csv"]} for i, (f, v) in enumerate(zip(filas, ["1", ""]))]
    mv.escribir(muestra, str(tmp_path / "m.csv"))
    r = mv.volcar(str(tmp_path / "m.csv"))
    despues = _leer(s["csv"])
    assert r == {"volcadas": 1, "sin_marca": 1, "no_encontradas": 0} and despues[0]["valido"] == "sí" and despues[1]["valido"] == ""
    assert despues[0]["juez_veredicto"] == "VALIDA"


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
