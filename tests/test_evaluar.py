import csv
import json
import os

from evaluacion import evaluar as ev

CABECERA_GT = ["id", "oferta", "seccion", "fragmento_trampa", "norma", "articulo", "articulos_equivalentes", "clase", "nivel", "responsable"]
CABECERA_ESP = ["proyecto", "seccion", "cita_conforme", "norma", "articulo", "espejo_de_trampa"]
GT = [
    {"id": "P9-01", "oferta": "P9", "seccion": "3", "fragmento_trampa": "la cantidad ofertada es de una unidad", "norma": "NORM_01", "articulo": "4.2",
     "articulos_equivalentes": "", "clase": "Mayor", "nivel": "Alto", "responsable": "Gerencia A"},
    {"id": "P9-02", "oferta": "P9", "seccion": "4", "fragmento_trampa": "el plazo ofertado es de diez días", "norma": "NORM_02", "articulo": "5.1",
     "articulos_equivalentes": "NORM_02 5.12; NORM_03 2.4", "clase": "Crítico", "nivel": "Alto", "responsable": "Gerencia B"},
    {"id": "P9-03", "oferta": "P9", "seccion": "5", "fragmento_trampa": "el registro se entrega al final", "norma": "NORM_05", "articulo": "1.6",
     "articulos_equivalentes": "", "clase": "Menor", "nivel": "Bajo", "responsable": "Gerencia C"},
    {"id": "P9-04", "oferta": "P9", "seccion": "6", "fragmento_trampa": "texto que nadie cita", "norma": "NORM_04", "articulo": "3.1",
     "articulos_equivalentes": "", "clase": "Mayor", "nivel": "Medio", "responsable": "Gerencia D"},
    {"id": "P8-01", "oferta": "P8", "seccion": "9", "fragmento_trampa": "otra oferta", "norma": "NORM_01", "articulo": "1.1",
     "articulos_equivalentes": "", "clase": "Menor", "nivel": "Bajo", "responsable": "Gerencia A"},
]
ESPEJOS = [
    {"proyecto": "Proyecto 9", "seccion": "3", "cita_conforme": "La cantidad de apoyos cumple con dos unidades por equipo", "norma": "NORM_01", "articulo": "4.2; 4.3", "espejo_de_trampa": "P9-01"},
    {"proyecto": "Proyecto 9", "seccion": "5", "cita_conforme": "El registro se entrega con cada etapa del montaje", "norma": "NORM_05", "articulo": "1.6", "espejo_de_trampa": "P9-03"},
    {"proyecto": "Proyecto 8", "seccion": "1", "cita_conforme": "Texto de otro proyecto", "norma": "NORM_01", "articulo": "1.1", "espejo_de_trampa": "P8-01"},
]


def _escribir(ruta, cabecera, filas):
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cabecera, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def _brecha(cita, norma, articulo, clase="Mayor", nivel="Alto", responsable="Gerencia A", seccion="3 Sección", titulo="t"):
    return {"id": f"{norma}|{articulo}|{cita[:5]}", "seccion": "3", "seccion_oferta": seccion, "norma": norma, "articulo": articulo, "cita": cita,
            "clase": clase, "nivel": nivel, "responsable": responsable, "titulo": titulo}


def _datos():
    return [dict(r) for r in GT if r["oferta"] == "P9"], [dict(r) for r in ESPEJOS if r["proyecto"] == "Proyecto 9"]


RESULTADO = {
    "registro_brechas": [
        # trampa con el artículo correcto (y clase, responsable y nivel correctos)
        _brecha("Según la propuesta, la cantidad ofertada es de una unidad por equipo.", "NORM_01", "4.2", "Mayor", "Alto", "Gerencia A"),
        # trampa con un artículo equivalente (clase equivocada)
        _brecha("Se informa que el plazo ofertado es de diez días.", "NORM_03", "2.4", "Menor", "Bajo", "Gerencia X"),
        # frase de una trampa pero con otro artículo: no suma al recall estricto
        _brecha("Se aclara que el registro se entrega al final de la obra.", "NORM_02", "9.9", "Menor", "Bajo", "Gerencia C", titulo="otro artículo"),
        # espejo marcado (falsa alarma): misma norma y uno de sus artículos
        _brecha("La cantidad de apoyos cumple con dos unidades por equipo.", "NORM_01", "4.3", "Menor", "Bajo", "Gerencia A", titulo="falsa alarma"),
        # extra: ni trampa ni espejo
        _brecha("Los tableros se entregan sin reserva de espacio.", "NORM_02", "5.12", "Menor", "Bajo", "Gerencia B", seccion="8 Conexiones", titulo="extra"),
    ],
    "riesgos": [{}, {}, {}, {}], "solicitudes": [{}, {}], "alertas": [{}],
}


def test_trampas_espejo_y_extra():
    gt, esp = _datos()
    r = ev.evaluar(RESULTADO, gt, esp, "P9")
    estados = {t["id"]: t["estado"] for t in r["trampas"]}
    assert estados == {"P9-01": "encontrada", "P9-02": "encontrada", "P9-03": "otro artículo", "P9-04": "no"}
    assert (r["encontradas"], r["otro_articulo"], r["por_frase"], r["n_trampas"]) == (2, 1, 3, 4)
    # clase, responsable y nivel, de las encontradas
    assert (r["clase_ok"], r["responsable_ok"], r["nivel_ok"]) == (1, 1, 1)
    assert r["confusion"] == {("Mayor", "Mayor"): 1, ("Crítico", "Menor"): 1}
    # espejo marcado: uno de dos
    assert (r["falsas_alarmas"], r["n_espejos"]) == (1, 2)
    assert [e["marcado"] for e in r["espejos"]] == [True, False]
    # extras: la brecha con otro artículo (para revisar) y la que no es ni trampa ni espejo
    assert sorted(x["titulo"] for x in r["extras"]) == ["extra", "otro artículo"]
    assert r["volumen"] == {"brechas": 5, "riesgos agrupados": 4, "solicitudes": 2, "alertas": 1}


def test_ground_truth_filtra_por_oferta_y_espejos_por_proyecto(tmp_path):
    _escribir(tmp_path / "gt.csv", CABECERA_GT, GT)
    _escribir(tmp_path / "esp.csv", CABECERA_ESP, ESPEJOS)
    assert [t["id"] for t in ev.cargar_gt("P9", str(tmp_path / "gt.csv"))] == ["P9-01", "P9-02", "P9-03", "P9-04"]
    assert len(ev.cargar_espejos("P9", str(tmp_path / "esp.csv"))) == 2 and len(ev.cargar_espejos("P8", str(tmp_path / "esp.csv"))) == 1


def test_precision_con_revision():
    gt, esp = _datos()
    r = ev.evaluar(RESULTADO, gt, esp, "P9")
    assert ev.calcular_precision(r, None) is None                      # pendiente de revisión
    rev = [dict(x) for x in r["extras"]]
    assert ev.calcular_precision(r, rev) is None                       # columna 'valido' vacía
    rev[0]["valido"], rev[1]["valido"] = "sí", "no"
    assert ev.calcular_precision(r, rev) == (2 + 1) / 5                 # (trampas encontradas + extras válidos) / brechas


def test_cli_genera_md_csv_y_extras(tmp_path):
    _escribir(tmp_path / "gt.csv", CABECERA_GT, GT)
    _escribir(tmp_path / "esp.csv", CABECERA_ESP, ESPEJOS)
    res = tmp_path / "resultado.json"
    res.write_text(json.dumps(RESULTADO), encoding="utf-8")
    ev.main(["--resultado", str(res), "--oferta", "P9", "--ground-truth", str(tmp_path / "gt.csv"), "--espejos", str(tmp_path / "esp.csv")])
    nombres = os.listdir(tmp_path)
    md = next(n for n in nombres if n.startswith("evaluacion_P9_") and n.endswith(".md"))
    assert any(n.startswith("evaluacion_P9_") and n.endswith(".csv") for n in nombres) and "extras_revision.csv" in nombres
    texto = (tmp_path / md).read_text(encoding="utf-8")
    assert "precisión pendiente de revisión" in texto and "2/4" in texto and "1/2" in texto and "esperada" in texto
    with open(tmp_path / "extras_revision.csv", encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f, delimiter=";"))
    assert list(filas[0]) == ["oferta", "seccion", "norma", "articulo", "cita", "titulo", "clase", "valido"] and all(x["valido"] == "" for x in filas)
    # con la revisión completa se calcula la precisión
    for x in filas:
        x["valido"] = "sí"
    _escribir(tmp_path / "revisado.csv", list(filas[0]), filas)
    ev.main(["--resultado", str(res), "--oferta", "P9", "--revision", str(tmp_path / "revisado.csv"),
             "--ground-truth", str(tmp_path / "gt.csv"), "--espejos", str(tmp_path / "esp.csv")])
    ultimo = sorted(n for n in os.listdir(tmp_path) if n.endswith(".md"))[-1]
    assert "80%" in (tmp_path / ultimo).read_text(encoding="utf-8")      # (2 + 2) / 5


# --- Modo lista (sin RAG) ---

LISTA = {"configuracion_analisis": {"condicion": "sin_rag"}, "registro_brechas": [], "resumen_ejecutivo": None,
         "riesgos_identificados_estructurados": [
             {"descripcion_riesgo": "d", "cita_oferta": "Según la propuesta, la cantidad ofertada es de una unidad por equipo."},
             {"descripcion_riesgo": "d", "cita_oferta": "Se informa que el plazo ofertado es de diez días."},
             {"descripcion_riesgo": "d", "cita_oferta": "La cantidad de apoyos cumple con dos unidades por equipo."}]}


def test_modo_lista_cuenta_por_frase_sin_articulo():
    gt, esp = _datos()
    r = ev.evaluar(LISTA, gt, esp, "P9")
    assert r["modo"] == "lista" and (r["por_frase"], r["encontradas"], r["n_trampas"]) == (2, 0, 4)
    assert (r["falsas_alarmas"], r["n_espejos"]) == (1, 2)
    assert r["volumen"] == {"riesgos": 3} and r["extras"] == []
    md = ev.informe_md(r)
    assert "modo lista" in md.split("##")[0].lower() and ev.NO_EVALUABLE in md and "Trampas encontradas por frase" in md


def test_comparar_con_y_sin_rag():
    gt, esp = _datos()
    con, sin = ev.evaluar(RESULTADO, gt, esp, "P9"), ev.evaluar(LISTA, gt, esp, "P9")
    tabla = ev.tabla_comparacion(con, sin)
    filas = {l.split("|")[1].strip(): [c.strip() for c in l.split("|")[2:4]] for l in tabla.splitlines()[2:]}
    assert filas["Trampas encontradas por frase"] == ["3/4 (75%)", "2/4 (50%)"]
    assert filas["Falsas alarmas (por frase del espejo)"] == ["1/2 (50%)", "1/2 (50%)"]
    assert filas["Recall estricto (frase y artículo)"] == ["2/4 (50%)", "—"]
    assert filas["Riesgos agrupados"] == ["4", "—"]


def test_cli_comparar_agrega_la_tabla_al_informe(tmp_path):
    _escribir(tmp_path / "gt.csv", CABECERA_GT, GT)
    _escribir(tmp_path / "esp.csv", CABECERA_ESP, ESPEJOS)
    (tmp_path / "con.json").write_text(json.dumps(RESULTADO), encoding="utf-8")
    (tmp_path / "sin.json").write_text(json.dumps(LISTA), encoding="utf-8")
    ev.main(["--resultado", str(tmp_path / "con.json"), "--oferta", "P9", "--comparar", str(tmp_path / "sin.json"),
             "--ground-truth", str(tmp_path / "gt.csv"), "--espejos", str(tmp_path / "esp.csv")])
    md = next(n for n in os.listdir(tmp_path) if n.endswith(".md"))
    assert "| Métrica | Con RAG | Sin RAG |" in (tmp_path / md).read_text(encoding="utf-8")


def test_el_resultado_sin_cita_no_rompe():
    r = ev.evaluar({"riesgos_identificados_estructurados": [{"descripcion_riesgo": "d"}]}, *_datos(), "P9")
    assert r["por_frase"] == 0


# --- Con el ground truth real: el ground truth como salida da 100 %; una salida vacía, 0 % ---

def _resultado_desde_gt(gt):
    return {"registro_brechas": [_brecha(t["fragmento_trampa"], t["norma"], t["articulo"], t["clase"], t["nivel"], t["responsable"]) for t in gt]}


def test_ground_truth_como_salida_da_100_por_ciento_y_salida_vacia_0():
    for oferta in ("P1", "P2", "P3", "P4"):
        gt, esp = ev.cargar_gt(oferta), ev.cargar_espejos(oferta)
        assert len(gt) == 15
        r = ev.evaluar(_resultado_desde_gt(gt), gt, esp, oferta)
        assert (r["encontradas"], r["clase_ok"], r["responsable_ok"], r["nivel_ok"], r["falsas_alarmas"], r["extras"]) == (15, 15, 15, 15, 0, [])
        vacio = ev.evaluar({"registro_brechas": [], "resumen_ejecutivo": {"decision": "Aceptable"}}, gt, esp, oferta)
        assert (vacio["encontradas"], vacio["por_frase"], vacio["falsas_alarmas"]) == (0, 0, 0)
    assert len(ev.cargar_espejos("P1")) == 32
