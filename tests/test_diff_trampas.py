"""Diferencia trampa por trampa entre dos configuraciones (evaluacion/diff_trampas.py), sobre resultados armados a mano (sin red ni modelos)."""
from evaluacion import diff_trampas as D
from evaluacion import evaluar as ev

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
SECCIONES = [{"id": s, "titulos": [t]} for s, t in (("3", "3 Plazos"), ("4", "4 Montaje"), ("5", "5 Pruebas"), ("6", "6 Entrega"))]


def _brecha(seccion, norma, articulo, frase, **extra):
    return {"seccion": seccion, "norma": norma, "articulo": articulo, "cita": f"Se indica {frase}.", "clase": "Mayor", "nivel": "Medio", "responsable": "G1", **extra}


def _verif(seccion, norma, articulo, veredicto, explicacion="porque sí"):
    return {"seccion": seccion, "norma": norma, "articulo": articulo, "veredicto": veredicto, "oraciones": ["O1"], "explicacion": explicacion, "estado": "ok"}


def _clasif(seccion, norma, articulo, veredicto, motivo=""):
    return {"seccion": seccion, "norma": norma, "articulo": articulo, "etapa": "clasificacion", "veredicto": veredicto, "motivo": motivo, "regla": "3.2.b"}


# v1: 01 encontrada; 02 verificada Cumple (perdida en verificación); 03 sin par verificado (no recuperada); 04 no recuperada.
V1 = {"registro_brechas": [_brecha("3", "NORM_01", "4.2", "plazo de 14 dias")], "riesgos": [{}], "solicitudes": [], "alertas": [],
      "secciones": SECCIONES,
      "registro_tecnico": [_verif("3", "NORM_01", "4.2", "Incumple"), _verif("4", "NORM_01", "5.1", "Cumple", "el montaje cumple"), _verif("9", "NORM_09", "9.9", "Cumple")]}
# elegida: 01 encontrada; 02 llega y se dice Incumple pero la brecha cita otro artículo (otra causa); 03 llega, Incumple y la brecha no contiene la frase (otra causa);
#          04 sigue sin recuperarse
ELEGIDA_ = {"registro_brechas": [_brecha("3", "NORM_01", "4.2", "plazo de 14 dias"), _brecha("4", "NORM_01", "7.7", "montaje en 3 dias"),
                                 _brecha("5", "NORM_02", "1.1", "otra cosa distinta")],
            "riesgos": [{}], "solicitudes": [], "alertas": [], "secciones": SECCIONES,
            "registro_tecnico": [_verif("3", "NORM_01", "4.2", "Incumple"), _verif("4", "NORM_01", "5.1", "Incumple", "montaje en 3 días no alcanza"),
                                 _verif("5", "NORM_02", "1.1", "Incumple", "no hay acta"), _clasif("4", "NORM_01", "5.1", "DESVIO"), _clasif("5", "NORM_02", "1.1", "DESVIO", "falta el acta")]}


def _cargado(resultado):
    return {"P9": {"resultado": resultado, "gt": [dict(t) for t in GT], "ev": ev.evaluar(resultado, [dict(t) for t in GT], [], "P9")}}


def _filas():
    return D.construir_filas(_cargado(V1), _cargado(ELEGIDA_), ["P9"])


def test_las_filas_traen_la_perdida_de_cada_configuracion():
    f = {x["id"]: x for x in _filas()}
    assert [(x["v1"]["perdida"], x["el"]["perdida"]) for x in f.values()] == [
        ("encontrada", "encontrada"), ("perdida en verificación", "otra causa"), ("no recuperada", "otra causa"), ("no recuperada", "no recuperada")]
    assert f["P9-02-M"]["norma"] == "NORM_01" and f["P9-02-M"]["articulo"] == "5.1"


def test_la_evidencia_trae_veredicto_explicacion_y_brechas_del_par():
    e = {x["id"]: x for x in _filas()}["P9-02-M"]
    assert D.veredictos(e["ev_v1"]) == "Cumple" and D.veredictos(e["ev_el"]) == "Incumple"
    assert "el montaje cumple" in D.texto_verificacion(e["ev_v1"]) and "montaje en 3 días no alcanza" in D.texto_verificacion(e["ev_el"]) and "DESVIO" in D.texto_clasificacion(e["ev_el"])
    assert D.texto_verificacion({"verificacion": []}) == "no verificada" and D.texto_clasificacion({"clasificacion": []}) == "—"


def test_motivos_de_otra_causa():
    f = {x["id"]: x for x in _filas()}
    assert "cita otro artículo (NORM_01 Art. 7.7)" in D.motivo_otra_causa(f["P9-02-M"]["el"], f["P9-02-M"]["ev_el"])
    assert "no contiene la frase" in D.motivo_otra_causa(f["P9-03-B"]["el"], f["P9-03-B"]["ev_el"])
    sin_brecha = {"estado": "no", "como_alerta": False, "articulo_citado": ""}
    assert "ninguna brecha" in D.motivo_otra_causa(sin_brecha, {"brechas_frase": [], "brechas_par": []})
    assert "alerta" in D.motivo_otra_causa({**sin_brecha, "como_alerta": True}, {"brechas_frase": [], "brechas_par": []})
    assert "descartada por cálculo" in D.motivo_otra_causa(sin_brecha, {"brechas_frase": [], "brechas_par": [{"estado": ev.ESTADO_DESCARTADA_CALCULO}]})


def test_el_informe_separa_lo_que_cambia_las_ganadas_y_perdidas_y_otra_causa():
    conjuntos = {"P9 solo": ["P9"]}
    md = D.informe_md(_filas(), conjuntos, ("Qwen3-32B", "Qwen3-32B (elegida)"))
    assert "## Resumen por conjunto" in md and "| P9 solo | 4 | 1 → 1 | 2 → 3 |" in md       # llegan al verificador: 01 y 02 en v1; 01, 02 y 03 en la elegida
    assert "| perdida en verificación | otra causa | 1 |" in md and "| no recuperada | otra causa | 1 |" in md and "no recuperada | no recuperada (igual) | 1" in md
    assert "Ganadas con la elegida: 0. Perdidas con la elegida: 0. Neto: +0." in md
    assert "## «Otra causa» en la elegida" in md and "2 trampas" in md and "P9-02-M" in md.split("## «Otra causa» en la elegida")[1]
    tabla = md.split("## Trampa por trampa")[1]
    assert "**(cambia)**" in tabla and "montaje en 3 días no alcanza" in tabla and "**v1:** no llegó al verificador" in tabla
    fila_igual = next(l for l in tabla.splitlines() if l.startswith("| P9-04-A"))
    assert fila_igual.endswith("|  |  |") and "cambia" not in fila_igual                                  # sin veredicto ni explicación donde no cambia


def test_ganadas_y_perdidas_cuentan_el_delta_del_recall_estricto():
    # al revés: la elegida pierde la 01 (v1 la encontraba) y gana la 02
    perdiendo = {**ELEGIDA_, "registro_brechas": [_brecha("4", "NORM_01", "5.1", "montaje en 3 dias")]}
    filas = D.construir_filas(_cargado(V1), _cargado(perdiendo), ["P9"])
    md = "\n".join(D.ganadas_perdidas_md(filas))
    assert "Ganadas con la elegida: 1. Perdidas con la elegida: 1. Neto: +0." in md
    assert "| P9-02-M | NORM_01 5.1 | perdida en verificación |" in md and "| P9-01-A | NORM_01 4.2 | otra causa" in md


def test_celdas_sin_barras_ni_saltos_y_con_tope():
    assert D._celda("a | b\nc") == "a / b c" and len(D._celda("x" * 1000)) == D.TOPE_CELDA and D._celda(None) == ""
