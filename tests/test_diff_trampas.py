"""Diferencia trampa por trampa entre dos corridas (evaluacion/diff_trampas.py), subcausas de «otra causa» y techo del sistema (evaluacion/evaluar.py), sobre resultados armados a mano
(sin red ni modelos)."""
import pytest

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
ORACIONES = {"3": [("O1", "Se indica plazo de 14 dias.")], "4": [("O1", "Antes de todo."), ("O2", "El montaje en 3"), ("O3", "dias es suficiente.")],
             "5": [("O1", "Las pruebas | sin acta."), ("O2", "Otra oracion.")], "6": [("O1", "Entrega parcial.")]}


def _brecha(seccion, norma, articulo, frase, **extra):
    return {"seccion": seccion, "norma": norma, "articulo": articulo, "cita": f"Se indica {frase}.", "clase": "Mayor", "nivel": "Medio", "responsable": "G1", **extra}


def _verif(seccion, norma, articulo, veredicto, explicacion="porque sí", oraciones=("O1",)):
    return {"seccion": seccion, "norma": norma, "articulo": articulo, "veredicto": veredicto, "oraciones": list(oraciones), "explicacion": explicacion, "estado": "ok"}


def _clasif(seccion, norma, articulo, veredicto, motivo="", regla="3.2.b", estado=None):
    return {"seccion": seccion, "norma": norma, "articulo": articulo, "etapa": "clasificacion", "veredicto": veredicto, "motivo": motivo, "regla": regla, **({"estado": estado} if estado else {})}


# A: 01 encontrada; 02 verificada Cumple (perdida en verificación); 03 y 04 no recuperadas.
V1 = {"registro_brechas": [_brecha("3", "NORM_01", "4.2", "plazo de 14 dias")], "riesgos": [{}], "solicitudes": [], "alertas": [], "secciones": SECCIONES,
      "configuracion_analisis": {"modelo_llm_usado": "m-a", "temperature": 0, "seed": 42},
      "registro_tecnico": [_verif("3", "NORM_01", "4.2", "Incumple"), _verif("4", "NORM_01", "5.1", "Cumple", "el montaje cumple", ("O3",)), _verif("9", "NORM_09", "9.9", "Cumple")]}
# B: 01 encontrada; 02 llega, Incumple, pero la brecha cita otro artículo; 03 llega, Incumple y la brecha no contiene la frase; 04 sigue sin recuperarse
ELEGIDA_ = {"registro_brechas": [_brecha("3", "NORM_01", "4.2", "plazo de 14 dias"), _brecha("4", "NORM_01", "7.7", "montaje en 3 dias"), _brecha("5", "NORM_02", "1.1", "otra cosa distinta")],
            "riesgos": [{}], "solicitudes": [], "alertas": [], "secciones": SECCIONES, "configuracion_analisis": {"modelo_llm_usado": "m-b", "temperature": 0, "seed": 42},
            "registro_tecnico": [_verif("3", "NORM_01", "4.2", "Incumple"), _verif("4", "NORM_01", "5.1", "Incumple", "montaje en 3 días no alcanza", ("O2", "O3")),
                                 _verif("5", "NORM_02", "1.1", "Incumple", "no hay acta"), _clasif("4", "NORM_01", "5.1", "DESVIO"), _clasif("5", "NORM_02", "1.1", "DESVIO", "falta el acta")]}
# C: las subcausas: 01 encontrada; 02 vetada por cálculo (y con alerta, como hace el pipeline); 03 descartada por regla 2.5; 04 salió solo como alerta
VETOS = {"registro_brechas": [_brecha("3", "NORM_01", "4.2", "plazo de 14 dias"),
                              {**_brecha("4", "NORM_01", "5.1", "montaje en 3 dias"), "estado": ev.ESTADO_DESCARTADA_CALCULO, "brecha_relativa": 0.0,
                               "clasificacion": {"valor_ofertado": "85", "valor_exigido": "85", "tipo_limite": "max", "objeto_requisito": "CUANTITATIVO_TECNICO"}}],
         "riesgos": [{}], "solicitudes": [], "secciones": SECCIONES,
         "alertas": [{"seccion": "4", "norma": "NORM_01", "articulo": "5.1", "cita": "Se indica montaje en 3 dias.", "origen": "brecha_nula"},
                     {"seccion": "6", "norma": "NORM_02", "articulo": "2.2", "cita": "Entrega parcial.", "motivo": "duda"}],
         "registro_tecnico": [_verif("3", "NORM_01", "4.2", "Incumple"), _verif("4", "NORM_01", "5.1", "Incumple"), _verif("5", "NORM_02", "1.1", "Incumple"),
                              _verif("6", "NORM_02", "2.2", "Incumple"),
                              _clasif("5", "NORM_02", "1.1", "INFORMACION_FALTANTE", "falta el dato", regla="2.5", estado="no_es_riesgo")]}


def _cargado(resultado):
    return {"P9": {"resultado": resultado, "gt": [dict(t) for t in GT], "ev": ev.evaluar(resultado, [dict(t) for t in GT], [], "P9")}}


def _filas(a=V1, b=ELEGIDA_, oraciones=None):
    return D.construir_filas(_cargado(a), _cargado(b), ["P9"], oraciones)


# --- evaluar.py: subcausas y techo ---

def test_subcausas_de_otra_causa_con_nombre_propio():
    trampas = {t["id"]: t for t in _cargado(VETOS)["P9"]["ev"]["trampas"]}
    assert [(t["perdida"], t["subcausa"]) for t in trampas.values()] == [("encontrada", None), ("otra causa", "vetada por cálculo"), ("otra causa", "descartada por regla 2.5"),
                                                                       ("otra causa", "salió como alerta")]
    b = {t["id"]: t for t in _cargado(ELEGIDA_)["P9"]["ev"]["trampas"]}
    assert (b["P9-02-M"]["subcausa"], b["P9-03-B"]["subcausa"]) == ("cita otro artículo", "otra")
    assert all(t["subcausa"] is None for t in _cargado(V1)["P9"]["ev"]["trampas"])      # solo las de «otra causa» tienen subcausa


def test_la_subcausa_no_cambia_la_definicion_de_encontrada_ni_del_recall():
    r = _cargado(VETOS)["P9"]["ev"]
    assert r["encontradas"] == 1 and [t["estado"] for t in r["trampas"]] == ["encontrada", "no", "no", "no"]


def test_regla_2_7_c_tiene_su_subcausa_y_la_vetada_va_antes_que_la_regla():
    assert ev.subcausa_otra_causa("no", False, [], [{"regla": "2.7.c"}]) == "descartada por regla 2.7.c"
    assert ev.subcausa_otra_causa("no", True, [{"estado": ev.ESTADO_DESCARTADA_CALCULO}], [{"regla": "2.5"}]) == "vetada por cálculo"
    assert ev.subcausa_otra_causa("no", False, [], []) == "otra"


def test_techo_del_sistema_resta_no_recuperadas_vetadas_y_regla_2_5():
    assert ev.techo_del_sistema(_cargado(VETOS)["P9"]["ev"]["trampas"]) == {"total": 4, "no_recuperadas": 0, "vetadas": 1, "regla_2_5": 1, "techo": 2}
    assert ev.techo_del_sistema(_cargado(V1)["P9"]["ev"]["trampas"])["techo"] == 2             # 2 no recuperadas
    sin_registro = ev.evaluar({"registro_brechas": [_brecha("3", "NORM_01", "4.2", "plazo de 14 dias")], "alertas": []}, [dict(t) for t in GT], [], "P9")
    assert ev.techo_del_sistema(sin_registro["trampas"]) is None


def test_el_informe_de_evaluar_trae_el_desglose_y_el_techo():
    md = ev.informe_md(_cargado(VETOS)["P9"]["ev"])
    assert "| vetada por cálculo | 1 |" in md and "| descartada por regla 2.5 | 1 |" in md and "Techo del sistema" in md and "2/4" in md


# --- diff_trampas: filas, evidencia, cobertura ---

def test_las_filas_traen_la_perdida_y_la_subcausa_de_cada_corrida():
    f = {x["id"]: x for x in _filas()}
    assert [(x["a"]["perdida"], x["b"]["perdida"]) for x in f.values()] == [
        ("encontrada", "encontrada"), ("perdida en verificación", "otra causa"), ("no recuperada", "otra causa"), ("no recuperada", "no recuperada")]
    assert D.perdida_texto(f["P9-02-M"]["b"]) == "otra causa (cita otro artículo)" and D.perdida_texto(f["P9-04-A"]["a"]) == "no recuperada"
    assert f["P9-02-M"]["norma"] == "NORM_01" and f["P9-02-M"]["articulo"] == "5.1"


def test_la_evidencia_trae_veredicto_explicacion_y_brechas_del_par():
    e = {x["id"]: x for x in _filas()}["P9-02-M"]
    assert D.veredictos(e["ev_a"]) == "Cumple" and D.veredictos(e["ev_b"]) == "Incumple"
    assert "el montaje cumple" in D.texto_verificacion(e["ev_a"]) and "montaje en 3 días no alcanza" in D.texto_verificacion(e["ev_b"]) and "DESVIO" in D.texto_clasificacion(e["ev_b"])
    assert D.texto_verificacion({"verificacion": []}) == "no verificada" and D.texto_clasificacion({"clasificacion": []}) == "—"


def test_las_cifras_de_una_brecha_vetada_se_ven_en_el_informe():
    f = {x["id"]: x for x in _filas(b=VETOS)}["P9-02-M"]
    assert "ofertado 85 / exigido 85 / límite max" in D.cifras_del_veto(f["ev_b"]) and "brecha relativa 0.0" in D.cifras_del_veto(f["ev_b"])
    assert D.cifras_del_veto({"brechas_par": []}) == "—"


def test_la_frase_puede_ocupar_mas_de_una_oracion_y_se_busca_sin_espacios_ni_barras():
    assert D.ids_de_la_frase("montaje en 3 dias", ORACIONES["4"]) == {"O2", "O3"}
    assert D.ids_de_la_frase("pruebas sin acta", ORACIONES["5"]) == {"O1"}          # la barra de la tabla no cuenta
    assert D.ids_de_la_frase("algo que no está", ORACIONES["4"]) is None and D.ids_de_la_frase("", ORACIONES["4"]) is None


@pytest.mark.parametrize("citadas,esperado", [(("O2", "O3"), "sí"), (("O3",), "parcial"), (("O1",), "no"), ((), "sin citas")])
def test_cobertura_de_la_frase_en_lo_que_cito_el_verificador(citadas, esperado):
    resultado = {**V1, "registro_tecnico": [_verif("4", "NORM_01", "5.1", "Cumple", oraciones=citadas)]}
    f = {x["id"]: x for x in _filas(a=resultado, oraciones={"P9": ORACIONES})}["P9-02-M"]
    assert f["cob_a"]["estado"] == esperado and f["cob_a"]["necesarias"] == {"O2", "O3"} and f["cob_a"]["seccion"] == "4"


def test_cobertura_sin_texto_de_oraciones_o_con_la_frase_fuera_de_la_seccion_es_nd():
    f = {x["id"]: x for x in _filas()}["P9-02-M"]
    assert f["cob_a"]["estado"] == "n/d" and "sin el texto" in f["cob_a"]["motivo"]
    otras = {**ORACIONES, "4": [("O1", "Nada que ver.")]}
    g = {x["id"]: x for x in _filas(oraciones={"P9": otras})}["P9-02-M"]
    assert g["cob_a"]["estado"] == "n/d" and "no aparece" in g["cob_a"]["motivo"]


def test_consistencia_de_la_numeracion_con_los_textos_que_guardaron_las_brechas():
    con_texto = {**V1, "registro_brechas": [_brecha("4", "NORM_01", "5.1", "x", oraciones_texto={"O1": "Antes de todo.", "O3": "texto distinto"})]}
    assert D.consistencia_numeracion(con_texto, ORACIONES) == (1, 2) and D.consistencia_numeracion(con_texto, None) == (0, 0)


# --- diff_trampas: informe y argumentos ---

def test_el_informe_separa_lo_que_cambia_las_ganadas_y_perdidas_la_evidencia_y_otra_causa():
    conjuntos = {"P9 solo": ["P9"]}
    a, b = _cargado(V1), _cargado(ELEGIDA_)
    filas = _filas(oraciones={"P9": ORACIONES})
    md = D.informe_md(filas, conjuntos, ("v1", "elegida"), ("Qwen3-32B", "Qwen3-32B (elegida)"), a, b, {"P9": ORACIONES}, ("P9-02-M",))
    assert "## Parámetros de cada corrida" in md and "| Temperatura | 0 | 0 |" in md and "| Semilla | 42 | 42 |" in md and "| Top_p" not in md
    assert "| Razonamiento en la verificación | no guardada | no guardada |" in md
    assert "| P9 solo | 4 | 1 → 1 | 2 → 3 | 2 → 3 |" in md       # recall 1 → 1; techo 4 − 2 no recuperadas = 2 y 4 − 1 = 3; llegan al verificador 01 y 02 contra 01, 02 y 03
    assert "| cita otro artículo | 0 | 1 |" in md and "| otra | 0 | 1 |" in md
    assert "| perdida en verificación | otra causa | 1 |" in md and "| no recuperada | otra causa | 1 |" in md and "no recuperada | no recuperada (igual) | 1" in md
    assert "Ganadas en elegida: 0. Perdidas en elegida: 0. Neto: +0." in md
    evidencia = md.split("## Perdidas en verificación")[1].split("### Casos señalados")[0]
    assert "| P9-02-M | NORM_01 5.1 | v1 | perdida en verificación | Cumple | O2, O3 | O3 | parcial |" in evidencia          # citó solo una de las dos oraciones de la frase
    assert "| P9-02-M | NORM_01 5.1 | elegida | otra causa | Incumple | O2, O3 | O2, O3 | sí |" in evidencia
    assert "| v1 | 0 | 1 | 0 | 0 | 0 |" in evidencia and "| elegida | 0 | 0 | 0 | 0 | 0 |" in evidencia
    casos = md.split("### Casos señalados")[1]
    assert "#### P9-02-M" in casos and "O2: El montaje en 3" in casos and "**parcial**" in casos
    assert "## «Otra causa» en elegida" in md and "2 trampas" in md.split("## «Otra causa» en elegida")[1] and "## «Otra causa» en v1\n\n0 trampas" in md
    tabla = md.split("## Trampa por trampa")[1]
    assert "**(cambia)**" in tabla and "montaje en 3 días no alcanza" in tabla and "**v1:** no llegó al verificador" in tabla and "parcial → sí" in tabla
    fila_igual = next(l for l in tabla.splitlines() if l.startswith("| P9-04-A"))
    assert fila_igual.endswith("|  |  |  |") and "cambia" not in fila_igual                # sin cobertura, veredicto ni explicación donde no cambia


def test_el_informe_sin_oraciones_deja_la_cobertura_en_nd():
    md = D.informe_md(_filas(), {"P9 solo": ["P9"]}, ("v1", "elegida"), ("a", "b"), _cargado(V1), _cargado(ELEGIDA_), None, ())
    assert "| P9-02-M | NORM_01 5.1 | v1 | perdida en verificación | Cumple | — | — | n/d (sin el texto de las oraciones) |" in md and "Numeración de oraciones" not in md


def test_ganadas_y_perdidas_cuentan_el_delta_del_recall_estricto():
    # al revés: B pierde la 01 (A la encontraba) y gana la 02
    perdiendo = {**ELEGIDA_, "registro_brechas": [_brecha("4", "NORM_01", "5.1", "montaje en 3 dias")]}
    md = "\n".join(D.ganadas_perdidas_md(_filas(b=perdiendo), ("v1", "elegida")))
    assert "Ganadas en elegida: 1. Perdidas en elegida: 1. Neto: +0." in md
    assert "| P9-02-M | NORM_01 5.1 | perdida en verificación |" in md and "| P9-01-A | NORM_01 4.2 | otra causa" in md


def test_las_corridas_se_eligen_por_nombre_de_configuracion_o_por_oferta_igual_ruta():
    cfg = {"configuraciones": {"X": {"P1": "uno.json", "P2": "dos.json"}, "Y": {"P1": "tres.json"}}}
    assert D.parsear_corrida(None, "X", cfg) == ("X", {"P1": "uno.json", "P2": "dos.json"})
    assert D.parsear_corrida(["Y"], "X", cfg) == ("Y", {"P1": "tres.json"})
    assert D.parsear_corrida(["P1=a.json", "P2=b.json"], "X", cfg) == ("P1=a.json + P2=b.json", {"P1": "a.json", "P2": "b.json"})
    with pytest.raises(SystemExit, match="no es una configuración"):
        D.parsear_corrida(["Z"], "X", cfg)


def test_main_acepta_dos_corridas_cualesquiera_con_etiquetas(tmp_path, monkeypatch):
    import json
    ra, rb = tmp_path / "a.json", tmp_path / "b.json"
    ra.write_text(json.dumps(V1), encoding="utf-8")
    rb.write_text(json.dumps(VETOS), encoding="utf-8")
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"configuraciones": {"otra corrida": {"P9": str(rb)}}, "conjuntos": {"P9 solo": ["P9"]}}), encoding="utf-8")
    monkeypatch.setattr(D.E, "cargar_gt", lambda oferta: [dict(t) for t in GT])
    monkeypatch.setattr(D.E, "cargar_espejos", lambda oferta: [])
    salida = tmp_path / "diff.md"
    D.main(["--config", str(cfg), "--a", f"P9={ra}", "--b", "otra corrida", "--etiqueta-a", "viejo", "--sin-oferta", "--salida", str(salida), "--casos"])
    md = salida.read_text(encoding="utf-8")
    assert "contra otra corrida" in md and "Diferencia trampa por trampa: viejo" in md and "| vetada por cálculo | 0 | 1 |" in md and "Techo del sistema" in md
    assert D._slug("32B (elegida)") == "32b_elegida"
