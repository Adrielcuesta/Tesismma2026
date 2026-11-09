import csv
import json
import os

import pytest

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
    assert any(n.startswith("evaluacion_P9_") and n.endswith(".csv") for n in nombres) and "resultado_extras.csv" in nombres
    texto = (tmp_path / md).read_text(encoding="utf-8")
    assert "precisión pendiente de revisión" in texto and "2/4" in texto and "esperada" in texto
    with open(tmp_path / "resultado_extras.csv", encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f, delimiter=";"))
    assert list(filas[0]) == ["oferta", "seccion", "norma", "articulo", "cita", "titulo", "clase", "valido"] and all(x["valido"] == "" for x in filas)
    # con la revisión completa se calcula la precisión
    for x in filas:
        x["valido"] = "sí"
    _escribir(tmp_path / "revisado.csv", list(filas[0]), filas)
    ev.main(["--resultado", str(res), "--oferta", "P9", "--revision", str(tmp_path / "revisado.csv"),
             "--ground-truth", str(tmp_path / "gt.csv"), "--espejos", str(tmp_path / "esp.csv")])
    ultimo = sorted(n for n in os.listdir(tmp_path) if n.endswith(".md"))[-1]
    assert "4/5 (80%)" in (tmp_path / ultimo).read_text(encoding="utf-8")      # (2 + 2) / 5


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


def _filas_tabla(tabla):
    return {l.split("|")[1].strip(): [c.strip() for c in l.split("|")[2:4]] for l in tabla.splitlines()[2:] if l.startswith("|")}


def test_comparar_con_y_sin_rag():
    gt, esp = _datos()
    con, sin = ev.evaluar(RESULTADO, gt, esp, "P9"), ev.evaluar(LISTA, gt, esp, "P9")
    tabla = ev.tabla_comparacion(con, sin)
    filas = _filas_tabla(tabla)
    # con RAG: solo el recall estricto; sin RAG: por frase (sin validar). No hay fila «por frase» para la columna con RAG
    assert filas["Trampas encontradas"] == ["2/4 (50%) (frase y artículo)", "2/4 (50%) por frase, sin validar"]
    assert "Trampas encontradas por frase" not in filas and "Recall estricto (frase y artículo)" not in filas
    assert filas["Falsas alarmas (por frase del espejo)"] == ["1/2 (50%)", "1/2 (50%)"]
    assert filas["Riesgos agrupados"] == ["4", "—"]
    assert "criterio más laxo que el de la columna con RAG: la diferencia es una cota inferior del aporte del RAG" in tabla


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


# --- Comparación con la línea de base: coincidencias a validar ---

def test_coincidencias_sin_rag_y_revision():
    gt, esp = _datos()
    sin = ev.evaluar(LISTA, gt, esp, "P9")
    assert [(c["trampa"], c["descripcion"]) for c in sin["coincidencias"]] == [("P9-01", "d"), ("P9-02", "d")]
    assert sin["por_frase"] == 2 and sin["por_frase_validada"] is None
    pendiente = [dict(c, valido="") for c in sin["coincidencias"]]
    ev.aplicar_revision_sinrag(sin, pendiente)
    assert sin["por_frase_validada"] is None                         # falta revisar: no se valida nada
    revision = [dict(pendiente[0], valido="sí"), dict(pendiente[1], valido="no")]
    ev.aplicar_revision_sinrag(sin, revision)
    assert sin["por_frase_validada"] == 1 and [t["por_frase_validada"] for t in sin["trampas"]] == [True, False, False, False]
    con = ev.evaluar(RESULTADO, gt, esp, "P9")
    assert _filas_tabla(ev.tabla_comparacion(con, sin))["Trampas encontradas"][1] == "1/4 (25%) por frase, validadas"


def test_cli_exporta_sinrag_coincidencias_y_usa_la_revision(tmp_path):
    _escribir(tmp_path / "gt.csv", CABECERA_GT, GT)
    _escribir(tmp_path / "esp.csv", CABECERA_ESP, ESPEJOS)
    (tmp_path / "con.json").write_text(json.dumps(RESULTADO), encoding="utf-8")
    (tmp_path / "sin.json").write_text(json.dumps(LISTA), encoding="utf-8")
    args = ["--resultado", str(tmp_path / "con.json"), "--oferta", "P9", "--comparar", str(tmp_path / "sin.json"),
            "--ground-truth", str(tmp_path / "gt.csv"), "--espejos", str(tmp_path / "esp.csv")]
    ev.main(args)
    with open(tmp_path / "sinrag_coincidencias.csv", encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f, delimiter=";"))
    assert list(filas[0]) == ["trampa", "frase", "descripcion_riesgo", "cita", "valido"] and len(filas) == 2 and all(x["valido"] == "" for x in filas)
    filas[0]["valido"], filas[1]["valido"] = "sí", "no"
    _escribir(tmp_path / "rev.csv", list(filas[0]), filas)
    ev.main(args + ["--revision-sinrag", str(tmp_path / "rev.csv")])
    ultimo = sorted(n for n in os.listdir(tmp_path) if n.endswith(".md"))[-1]
    assert "1/4 (25%) por frase, validadas" in (tmp_path / ultimo).read_text(encoding="utf-8")


# --- Informe: «otro artículo» solo en el detalle ---

def test_otro_articulo_no_esta_en_el_resumen_pero_si_en_el_detalle():
    gt, esp = _datos()
    md = ev.informe_md(ev.evaluar(RESULTADO, gt, esp, "P9"))
    assert "Encontradas con otro artículo" not in md
    fila = next(l for l in md.splitlines() if l.startswith("| P9-03"))
    assert "otro artículo" in fila and "NORM_02 Art. 9.9" in fila
    # el .md solo trae las secciones pedidas
    assert [l for l in md.splitlines() if l.startswith("## ")] == ["## Recuperación", "## Detección", "## Clasificación (de las trampas encontradas)",
                                                                   "## Fidelidad", "## Recall por clase esperada", "## Recall por nivel esperado", "## Falsas alarmas", "## Volumen", "## Dónde se pierde cada trampa",
                                                                   "## Costo computacional", "## Detalle por trampa"]
    assert "100 % por diseño" in md


# --- Métricas estándar ---

def test_wilson_valores_conocidos():
    lo, hi = ev.wilson(8, 10)
    assert round(lo, 4) == 0.4902 and round(hi, 4) == 0.9433
    lo, hi = ev.wilson(0, 10)
    assert lo == 0.0 and round(hi, 4) == 0.2775
    assert ev.wilson(5, 0) is None
    assert ev.wilson(10, 10)[1] == 1.0


def test_mcnemar_exacto_valores_conocidos():
    assert ev.mcnemar_exacto(2, 8) == 112 / 1024          # 2 * P(X <= 2 | n=10)
    assert ev.mcnemar_exacto(0, 5) == 2 / 32
    assert ev.mcnemar_exacto(0, 0) == 1.0 and ev.mcnemar_exacto(5, 5) == 1.0
    assert ev.mcnemar_exacto(1, 1) == 1.0


def _kappa_por_pares(esperadas, obtenidas, clases):
    """Implementación independiente: a partir de los pares, sin matriz."""
    k, n = len(clases), len(esperadas)
    w = lambda a, b: (clases.index(a) - clases.index(b)) ** 2 / (k - 1) ** 2
    observado = sum(w(a, b) for a, b in zip(esperadas, obtenidas)) / n
    azar = sum(w(a, b) for a in esperadas for b in obtenidas) / n ** 2
    return 1 - observado / azar


def test_kappa_ponderado_cuadratico():
    assert ev.kappa_ponderado_cuadratico({("Crítico", "Crítico"): 3, ("Mayor", "Mayor"): 4, ("Menor", "Menor"): 2}) == 1.0
    # con dos categorías equivale al kappa de Cohen: po = 0,7, pe = 0,5 -> 0,4
    cohen = {("a", "a"): 20, ("a", "b"): 5, ("b", "a"): 10, ("b", "b"): 15}
    assert round(ev.kappa_ponderado_cuadratico(cohen, ("a", "b")), 10) == 0.4
    esperadas = ["Crítico", "Crítico", "Mayor", "Mayor", "Mayor", "Menor", "Menor", "Crítico", "Mayor", "Menor"]
    obtenidas = ["Crítico", "Mayor", "Mayor", "Menor", "Mayor", "Menor", "Mayor", "Crítico", "Crítico", "Menor"]
    confusion = {}
    for par in zip(esperadas, obtenidas):
        confusion[par] = confusion.get(par, 0) + 1
    assert abs(ev.kappa_ponderado_cuadratico(confusion) - _kappa_por_pares(esperadas, obtenidas, list(ev.CLASES))) < 1e-12
    # un error de dos escalones (Crítico por Menor) pesa más que uno de un escalón
    uno = ev.kappa_ponderado_cuadratico({("Crítico", "Mayor"): 1, ("Crítico", "Crítico"): 2, ("Menor", "Menor"): 2})
    dos = ev.kappa_ponderado_cuadratico({("Crítico", "Menor"): 1, ("Crítico", "Crítico"): 2, ("Menor", "Menor"): 2})
    assert dos < uno
    assert ev.kappa_ponderado_cuadratico({}) is None and ev.kappa_ponderado_cuadratico({("Mayor", "Mayor"): 3}) is None


def test_f1_y_f2():
    assert round(ev.f_beta(0.5, 1.0, 1), 4) == 0.6667
    assert round(ev.f_beta(0.5, 1.0, 2), 4) == 0.8333       # pondera más el recall
    assert ev.f_beta(0, 0, 2) == 0.0 and ev.f_beta(None, 0.5, 1) is None


def _con_registro(resultado, registro):
    return {**resultado, "registro_tecnico": registro}


def test_recall_articulo_y_tasa_de_pereza():
    gt, esp = _datos()
    registro = [
        {"seccion": "3", "norma": "NORM_01", "articulo": "4.2", "veredicto": "Incumple"},           # P9-01: verificado y encontrado
        {"seccion": "4", "norma": "NORM_03", "articulo": "2.4", "veredicto": "Revisar"},            # P9-02: por un artículo equivalente
        {"seccion": "5", "norma": "NORM_05", "articulo": "1.6", "veredicto": "Cumple"},             # P9-03: verificado, no encontrado, Cumple -> pereza
        {"seccion": "6", "norma": "NORM_04", "articulo": "3.1", "veredicto": "No aplica", "etapa": "clasificacion"},   # no cuenta: etapa de clasificación
        {"seccion": "9", "norma": "NORM_01", "articulo": "4.2", "veredicto": "Cumple"},             # otra sección: no cuenta
    ]
    r = ev.evaluar(_con_registro(RESULTADO, registro), gt, esp, "P9")
    assert [t["verificado"] for t in r["trampas"]] == [True, True, True, False]
    assert (r["recall_articulo"], r["perezosas"], r["hay_registro"]) == (3, 1, True)
    assert [t["perezosa"] for t in r["trampas"]] == [False, False, True, False]
    md = ev.informe_md(r)
    assert "3/4 (75%)" in md and "Pereza de verificación" in md and "Pereza de clasificación" in md
    assert [t["perdida"] for t in r["trampas"]] == ["encontrada", "encontrada", "perdida en verificación", "no recuperada"]
    sin_registro = ev.evaluar(RESULTADO, gt, esp, "P9")
    assert sin_registro["hay_registro"] is False and "n/d (el resultado no trae registro técnico)" in ev.informe_md(sin_registro)


def test_falsas_alarmas_y_volumen_en_el_informe():
    gt, esp = _datos()
    md = ev.informe_md(ev.evaluar(RESULTADO, gt, esp, "P9"))
    assert "| Espejos marcados | 1/2 (50%), IC 95 % 9%–91% |" in md
    assert "| Brechas | 5 |" in md and "| Riesgos agrupados | 4 |" in md and "| Solicitudes | 2 |" in md and "| Alertas | 1 |" in md
    lista = ev.informe_md(ev.evaluar(LISTA, gt, esp, "P9"))
    assert "## Falsas alarmas" in lista and "| Riesgos | 3 |" in lista


def test_donde_se_pierde_cada_trampa_en_dos_capas_de_pereza():
    gt, esp = _datos()
    registro = [
        {"seccion": "3", "norma": "NORM_01", "articulo": "4.2", "veredicto": "Incumple"},                   # P9-01 encontrada
        {"seccion": "4", "norma": "NORM_02", "articulo": "5.1", "veredicto": "Incumple"},                   # P9-02: verificación Incumple...
        {"seccion": "4", "norma": "NORM_02", "articulo": "5.1", "etapa": "clasificacion", "veredicto": "NO_APLICA", "estado": "no_es_riesgo"},   # ...y clasificación NO_APLICA
        {"seccion": "5", "norma": "NORM_05", "articulo": "1.6", "veredicto": "Cumple"},                     # P9-03: la verificación dijo Cumple
    ]                                                                                                       # P9-04: el artículo nunca llegó
    resultado = {"registro_brechas": [_brecha("la cantidad ofertada es de una unidad", "NORM_01", "4.2")], "registro_tecnico": registro}
    r = ev.evaluar(resultado, gt, esp, "P9")
    assert [t["perdida"] for t in r["trampas"]] == ["encontrada", "perdida en clasificación", "perdida en verificación", "no recuperada"]
    assert (r["perezosas"], r["perezosas_clasificacion"]) == (1, 1)
    md = ev.informe_md(r)
    assert "| P9-02 | perdida en clasificación | NORM_02 Art. 5.1 | Incumple | NO_APLICA |" in md
    assert "| P9-04 | no recuperada |" in md and "| P9-01 | encontrada" not in md.split("## Dónde se pierde cada trampa")[1].split("## Detalle")[0]
    assert "| no recuperada | 1/4 (25%) |" in md and "| encontrada | 1/4 (25%) |" in md
    assert "n/d (el resultado no trae registro técnico)" in ev.informe_md(ev.evaluar({"registro_brechas": resultado["registro_brechas"]}, gt, esp, "P9"))


def test_trampa_con_veredicto_incumple_no_es_perezosa_aunque_no_se_encuentre():
    gt, esp = _datos()
    registro = [{"seccion": "6", "norma": "NORM_04", "articulo": "3.1", "veredicto": "Incumple"}]
    r = ev.evaluar(_con_registro(RESULTADO, registro), gt, esp, "P9")
    assert r["trampas"][3]["verificado"] and not r["trampas"][3]["perezosa"]


def test_fidelidad_cuenta_brechas_con_marca_valor_no_verificado():
    gt, esp = _datos()
    marcada = dict(_brecha("Texto cualquiera de una brecha.", "NORM_01", "1.1"), marcas=["impacto ajustado de 5 a 2", "valor no verificado: valor_limite_excepcion"])
    r = ev.evaluar({"registro_brechas": [marcada, _brecha("Otra brecha sin marcas.", "NORM_01", "1.2")]}, gt, esp, "P9")
    assert r["marcas_no_verificadas"] == 1 and "1/2 (50%)" in ev.informe_md(r)


def test_precision_f1_f2_e_ic_en_el_informe():
    gt, esp = _datos()
    r = ev.evaluar(RESULTADO, gt, esp, "P9")
    ev.asignar_precision(r, [dict(x, valido="sí") for x in r["extras"]])
    assert (r["precision_k"], r["precision_n"], r["precision"]) == (4, 5, 0.8)
    md = ev.informe_md(r)
    p, rc = 0.8, 0.5
    assert f"{2 * p * rc / (p + rc):.2f}" in md and f"{5 * p * rc / (4 * p + rc):.2f}" in md
    assert "4/5 (80%), IC 95 %" in md and "2/4 (50%), IC 95 %" in md


# --- Agregado y McNemar ---

def test_oferta_de_ruta():
    assert ev._oferta_de_ruta("datos/Resultados/P1_oferta_TBP01/analisis.json") == ("P1", "datos/Resultados/P1_oferta_TBP01/analisis.json")
    assert ev._oferta_de_ruta("P3=x/y.json") == ("P3", "x/y.json")
    with pytest.raises(SystemExit):
        ev._oferta_de_ruta("TBP01/analisis.json")


def test_cli_agregado_suma_las_ofertas_y_hace_mcnemar(tmp_path):
    _escribir(tmp_path / "gt.csv", CABECERA_GT, GT)
    _escribir(tmp_path / "esp.csv", CABECERA_ESP, ESPEJOS)
    resultado8 = {"registro_brechas": [_brecha("Texto de la otra oferta.", "NORM_01", "1.1")]}
    lista8 = {"riesgos_identificados_estructurados": [{"descripcion_riesgo": "d", "cita_oferta": "Hay otra oferta con su propio texto."}]}
    for nombre, contenido in (("P9_con", RESULTADO), ("P8_con", resultado8), ("P9_sin", LISTA), ("P8_sin", lista8)):
        (tmp_path / nombre).mkdir()
        (tmp_path / nombre / "r.json").write_text(json.dumps(contenido), encoding="utf-8")
    total = ev.main(["--agregado", str(tmp_path / "P9_con" / "r.json"), str(tmp_path / "P8_con" / "r.json"),
                     "--comparar", str(tmp_path / "P9_sin" / "r.json"), str(tmp_path / "P8_sin" / "r.json"),
                     "--ground-truth", str(tmp_path / "gt.csv"), "--espejos", str(tmp_path / "esp.csv")])
    assert (total["n_trampas"], total["encontradas"], total["oferta"]) == (5, 3, "P9+P8")
    md = next(n for n in os.listdir(tmp_path / "P9_con") if n.startswith("evaluacion_agregado_") and n.endswith(".md"))
    texto = (tmp_path / "P9_con" / md).read_text(encoding="utf-8")
    # con RAG (estricto): P9-01, P9-02 y P8-01. Sin RAG (por frase): las mismas, más la de P8 -> sin discordancias
    assert "McNemar" in texto and "solo con RAG 0, solo sin RAG 0, p = 1.0000" in texto
    assert (tmp_path / "P9_sin" / "sinrag_coincidencias.csv").exists() and (tmp_path / "P8_sin" / "sinrag_coincidencias.csv").exists()


def test_combinar_suma_confusion_y_conteos():
    gt, esp = _datos()
    t = ev.combinar([ev.evaluar(RESULTADO, gt, esp, "P9"), ev.evaluar(RESULTADO, gt, esp, "P9")])
    assert (t["n_trampas"], t["encontradas"], t["n_espejos"], t["falsas_alarmas"]) == (8, 4, 4, 2)
    assert t["confusion"] == {("Mayor", "Mayor"): 2, ("Crítico", "Menor"): 2} and t["volumen"]["brechas"] == 10
    assert t["precision"] is None and len(t["trampas"]) == 8


# --- Costo computacional ---

COSTO = {"modelo": "qwen3:8b", "hardware": {"gpu": "NVIDIA GeForce RTX 4060", "vram": "8188 MiB"}, "pares_verificados": 120, "llamadas_totales": 190,
         "llamadas_fallidas": 1, "tiempo_total_s": 5025.5, "segundos_por_par": {"mediana": 14.2, "p90": 31.75},
         "tokens_entrada_total": 612345, "tokens_salida_total": 23456, "tokens_entrada_por_par": 4980.5, "tokens_salida_por_par": 170.2}


def test_informe_incluye_el_costo_computacional_de_la_oferta():
    gt, esp = _datos()
    resultado = {**RESULTADO, "configuracion_analisis": {"costo_computacional": COSTO}}
    md = ev.informe_md(ev.evaluar(resultado, gt, esp, "P9"))
    seccion = md.split("## Costo computacional")[1].split("## Detalle")[0]
    for esperado in ("qwen3:8b", "NVIDIA GeForce RTX 4060, 8188 MiB", "| Pares verificados | 120 |", "| Llamadas totales (con comentario y reintentos) | 190 |",
                     "5.025,5 s (1:23:45)", "14.2 / 31.8", "612.345 / 4.980", "23.456 / 170"):
        assert esperado in seccion, esperado
    sin = ev.informe_md(ev.evaluar(RESULTADO, gt, esp, "P9"))
    assert "n/d (el resultado no trae la medición)" in sin
    assert "## Costo computacional" in ev.informe_md(ev.evaluar(LISTA, gt, esp, "P9"))        # también en modo lista


def test_costo_computacional_por_oferta_en_el_agregado():
    gt, esp = _datos()
    a = ev.evaluar({**RESULTADO, "configuracion_analisis": {"costo_computacional": COSTO}}, gt, esp, "P9")
    b = ev.evaluar(RESULTADO, gt, esp, "P8")
    md = ev.informe_md(ev.combinar([a, b]))
    seccion = md.split("## Costo computacional")[1].split("## Detalle")[0]
    assert "**P9**" in seccion and "**P8**: n/d" in seccion and seccion.index("**P9**") < seccion.index("**P8**")


# --- Recall@artículo por la sección S# que contiene la subsección; alertas; recall por clase y nivel ---

def test_recall_articulo_usa_los_titulos_de_las_secciones_y_no_el_numero_de_S():
    gt, esp = _datos()
    gt[0]["seccion"] = "3.1 Apoyos"
    secciones = [{"id": "S7", "titulos": ["3.1 Apoyos", "3.2 Otro"]}, {"id": "S8", "titulos": ["4.1 Plazo"]}]
    verificado_en = lambda sec: ev.evaluar({**RESULTADO, "secciones": secciones, "registro_tecnico": [
        {"seccion": sec, "norma": "NORM_01", "articulo": "4.2", "veredicto": "Incumple"}]}, gt, esp, "P9")["trampas"][0]["verificado"]
    assert verificado_en("S7") is True       # la S7 contiene la subsección 3.1 (el 7 no tiene nada que ver con la sección 3 del GT)
    assert verificado_en("S8") is False
    assert ev._ids_secciones_de("3", secciones) == {"S7"} and ev._ids_secciones_de("9.9 Nada", secciones) == set()


def test_encontrada_como_alerta_recall_separado_y_tablas_por_clase_y_nivel():
    gt, esp = _datos()
    descartada = dict(_brecha("texto que nadie cita", "NORM_04", "3.1"), estado="descartada por cálculo")
    resultado = {**RESULTADO, "registro_brechas": RESULTADO["registro_brechas"] + [descartada], "alertas": [
        {"cita": "Se aclara que el registro se entrega al final de la obra.", "norma": "NORM_05", "articulo": "1.6", "motivo": "contradicción"},
        {"cita": "texto que nadie cita", "norma": "NORM_04", "articulo": "3.1", "estado": "tiempo_agotado"}]}
    r = ev.evaluar(resultado, gt, esp, "P9")
    assert [t["como_alerta"] for t in r["trampas"]] == [False, False, True, False]
    assert (r["encontradas"], r["solo_alerta"], r["n_riesgo"]) == (2, 1, 5)      # la descartada por cálculo no es riesgo ni extra
    assert r["trampas"][3]["estado"] == "no" and len(r["extras"]) == 2   # los mismos extras que sin la descartada
    assert ev.recall_por(r["trampas"], "clase_esperada", ev.CLASES) == [("Crítico", 1, 1, 1), ("Mayor", 2, 1, 1), ("Menor", 1, 0, 1)]
    assert ev.recall_por(r["trampas"], "nivel_esperado", ev.NIVELES) == [("Alto", 2, 2, 2), ("Medio", 1, 0, 0), ("Bajo", 1, 0, 1)]
    md = ev.informe_md(r)
    assert "| Recall solo riesgos (frase y artículo) | 2/4 (50%)" in md and "| Recall riesgos + alertas" in md and "3/4 (75%)" in md
    assert "## Recall por clase esperada" in md and "| Menor | 1 | 0/1 (0%) | 1/1 (100%) |" in md and "## Recall por nivel esperado" in md
    assert ev.combinar([r, r])["solo_alerta"] == 2
