"""Lectura del ground truth, el mapa y los controles negativos de P5 y su evaluación (evaluacion/p5.py y evaluacion/evaluar.py).
Los tests sintéticos usan el esquema real de los archivos; el de los archivos reales solo cuenta ids y campos (ningún texto de la oferta ni del ground truth)."""
import csv
import json

import pytest

from evaluacion import evaluar as E
from evaluacion import p5


def _t(id_, tipo="amenaza", norma="NORM_01", articulo="4.2", frase=None, clase="Mayor", seccion="3.1 Sección", **extra):
    """Entrada con el esquema real de ground_truth_P5.json (sin sección: va al mapa)."""
    e = {"id": id_, "proyecto": "Proyecto 5", "tipo": tipo, "norma": norma, "articulo": articulo, "fragmento_trampa": frase or f"frase {id_}",
         "fuente_riesgo": "oportunidad" if tipo == "oportunidad" else "desvio", "clase_desvio": None if tipo == "oportunidad" else clase,
         "nivel": None if tipo == "oportunidad" else "Medio", "responsable": "Gerencia X", "titulo": "t", "enunciado": "e", **extra}
    e["_seccion"] = seccion
    return e


# 11 amenazas (tres en la misma sección y norma: excepción, desvío e información faltante; P5-02-D2 en otra sección) y 2 oportunidades
GT = ([_t(f"P5-0{n}-D", articulo=f"4.{n}", norma=f"NORM_0{n}") for n in (1, 3, 4, 5)] +
      [_t("P5-01-IF", articulo="3.2", clase="Menor"), _t("P5-05-IF", articulo="2.9", norma="NORM_05", clase="Menor"),
       _t("P5-02-EX", articulo="5.7", norma="NORM_02", clase="Critico", seccion="4.3 Puesta a tierra"),
       _t("P5-02-D1", articulo="5.16", norma="NORM_02", seccion="4.3 Puesta a tierra"),
       _t("P5-02-IF", articulo="5.5", norma="NORM_02", seccion="4.3 Puesta a tierra"),
       _t("P5-02-D2", articulo="2.6", norma="NORM_02", seccion="4.1 Alimentación"),
       _t("P5-03-IF", articulo="2.2", norma="NORM_03"),
       _t("P5-04-OP", tipo="oportunidad", articulo="3.6", norma="NORM_04"), _t("P5-02-OP", tipo="oportunidad", articulo="1.10", norma="NORM_02")])
CONTROLES = ([{"id": f"P5-NC-{n:02d}", "proyecto": "Proyecto 5", "norma": "NORM_01", "articulo": f"9.{n}", "veredicto_esperado": "cumple", "cita": f"cita del control {n}",
               "seccion": "9 Sec", "motivo": "m"} for n in range(1, 11)] +
             [{"id": "P5-NC-11", "proyecto": "Proyecto 5", "norma": "NORM_04", "articulo": "2.3; 2.5", "veredicto_esperado": "no_aplica_sin_actividad", "cita": "cita del control 11",
               "seccion": "2.2 Sitio", "motivo": "m"},
              {"id": "P5-NC-12", "proyecto": "Proyecto 5", "norma": "NORM_04", "articulo": "3.20", "veredicto_esperado": "no_aplica_etapa_posterior", "cita": "None", "seccion": "None", "motivo": "m"},
              {"id": "P5-NC-13", "proyecto": "Proyecto 5", "norma": "NORM_01", "articulo": "4.1", "veredicto_esperado": "no_aplica_etapa_posterior", "cita": None, "seccion": None, "motivo": "m"}])


def _escribir(tmp_path, gt=GT, controles=CONTROLES, mapa=None):
    rg, rc, rm = tmp_path / "ground_truth_P5.json", tmp_path / "controles_negativos_P5.json", tmp_path / "mapa_trampas_P5.csv"
    rg.write_text(json.dumps([{k: v for k, v in e.items() if k != "_seccion"} for e in gt]), encoding="utf-8")
    rc.write_text(json.dumps(controles), encoding="utf-8")
    filas_mapa = mapa if mapa is not None else [{"id": e["id"], "proyecto": "Proyecto 5", "documento": "P5_oferta.docx", "seccion": e["_seccion"], "fragmento_trampa": e["fragmento_trampa"],
                                                 "norma": e["norma"], "articulo": e["articulo"], "severidad": e["clase_desvio"] or "Oportunidad", "responsable": e["responsable"]} for e in gt]
    with open(rm, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "proyecto", "documento", "seccion", "fragmento_trampa", "norma", "articulo", "severidad", "responsable"], delimiter=";")
        w.writeheader()
        w.writerows(filas_mapa)
    return str(rg), str(rc), str(rm)


def _cargar(tmp_path, **kw):
    rg, rc, rm = _escribir(tmp_path, **kw)
    return p5.cargar_trampas(rg, rm), p5.cargar_controles(rc)


def test_sin_archivos_p5_no_hay_ground_truth_ni_controles(tmp_path):
    assert p5.cargar_trampas(str(tmp_path / "no.json")) == [] and p5.cargar_controles(str(tmp_path / "no.json")) == []


def test_esquema_real_seccion_del_mapa_clase_con_tilde_y_controles_sin_cita(tmp_path):
    filas, controles = _cargar(tmp_path)
    assert len(filas) == 13 and sum(f["tipo"] == "amenaza" for f in filas) == 11 and sum(f["tipo"] == "oportunidad" for f in filas) == 2
    por_id = {f["id"]: f for f in filas}
    assert por_id["P5-02-EX"]["seccion"] == "4.3 Puesta a tierra" and all(f["seccion"] for f in filas)          # la sección sale del mapa
    assert por_id["P5-02-EX"]["clase"] == "Crítico" and por_id["P5-01-IF"]["clase"] == "Menor" and por_id["P5-04-OP"]["clase"] == ""
    assert por_id["P5-02-EX"]["fuente"] == "DESVIO" and por_id["P5-04-OP"]["nivel"] == ""
    assert len(controles) == 13 and {c["proyecto"] for c in controles} == {"Proyecto 5"}
    assert [(c["cita_conforme"], c["seccion"]) for c in controles[-2:]] == [("", ""), ("", "")]                  # «None» y null se leen como vacíos
    assert E.pares_espejo(controles[10]) == {("NORM_04", "2.3"), ("NORM_04", "2.5")}                            # varios artículos en un control


def test_equivalentes_y_grupo_salen_de_la_consigna_no_del_prefijo(tmp_path):
    filas, _ = _cargar(tmp_path)
    por_id = {f["id"]: f for f in filas}
    assert E.pares_trampa(por_id["P5-03-IF"]) == {("NORM_03", "2.2"), ("NORM_05", "1.6")}
    assert E.pares_trampa(por_id["P5-02-IF"]) == {("NORM_02", "5.5"), ("NORM_02", "2.15")}
    assert {i for i, f in por_id.items() if f["grupo"] == "P5-02"} == {"P5-02-EX", "P5-02-D1", "P5-02-IF"}
    assert por_id["P5-02-D2"]["grupo"] == "" and por_id["P5-01-IF"]["grupo"] == "" and por_id["P5-01-D"]["grupo"] == ""      # mismo prefijo, otro grupo (o ninguno)


def test_si_el_archivo_trae_equivalentes_o_grupo_manda_el_archivo(tmp_path):
    gt = [_t("A-1", articulos_equivalentes=["NORM_02 2.2"], grupo="G1"), _t("A-2", grupo="G1")]
    rg, _, rm = _escribir(tmp_path, gt=gt)
    filas = p5.cargar_trampas(rg, rm, equivalentes={}, grupos={})
    assert filas[0]["articulos_equivalentes"] == "NORM_02 2.2" and {f["grupo"] for f in filas} == {"G1"}


def test_errores_claros_si_el_mapa_falta_o_no_coincide_o_la_consigna_nombra_otra_trampa(tmp_path):
    rg, _, rm = _escribir(tmp_path)
    with pytest.raises(ValueError, match="Falta no.csv: la secci"):
        p5.cargar_trampas(rg, str(tmp_path / "no.csv"))
    mapa = list(csv.DictReader(open(rm, encoding="utf-8-sig"), delimiter=";"))
    _, _, rm2 = _escribir(tmp_path, mapa=mapa[1:])
    with pytest.raises(ValueError, match="no está en mapa_trampas_P5.csv"):
        p5.cargar_trampas(rg, rm2)
    mapa[0]["articulo"] = "9.9"
    _, _, rm3 = _escribir(tmp_path, mapa=mapa)
    with pytest.raises(ValueError, match="no coincide"):
        p5.cargar_trampas(rg, rm3)
    rg4, _, rm4 = _escribir(tmp_path, gt=[_t("A-1")])
    with pytest.raises(ValueError, match="nombran trampas que no están.*P5-02-EX"):
        p5.cargar_trampas(rg4, rm4)                                   # con los equivalentes y el grupo por defecto
    rg5, _, rm5 = _escribir(tmp_path, gt=[_t("A-1", clase="Gravísimo")])
    with pytest.raises(ValueError, match="clase desconocida"):
        p5.cargar_trampas(rg5, rm5, equivalentes={}, grupos={})


def test_archivos_reales_de_p5_cuadran_con_el_cargador():
    """Contra evaluacion/ground_truth_P5.json, controles_negativos_P5.json y mapa_trampas_P5.csv (solo ids y campos; sin textos)."""
    if not (p5.os.path.isfile(p5.GROUND_TRUTH_P5) and p5.os.path.isfile(p5.MAPA_P5) and p5.os.path.isfile(p5.CONTROLES_P5)):
        pytest.skip("los archivos de P5 no están en evaluacion/")
    filas, controles = E.cargar_gt("P5"), E.cargar_espejos("P5")
    amenazas = [f for f in filas if f["tipo"] == "amenaza"]
    assert len(filas) == 13 and len(amenazas) == 11 and {f["id"] for f in filas if f["tipo"] == "oportunidad"} == {"P5-04-OP", "P5-02-OP"}
    assert all(f["seccion"] for f in filas) and {f["clase"] for f in amenazas} <= set(E.CLASES) and {f["nivel"] for f in amenazas} <= set(E.NIVELES)
    assert [f["id"] for f in filas if f["grupo"]] and {f["id"] for f in filas if f["grupo"] == "P5-02"} == {"P5-02-EX", "P5-02-D1", "P5-02-IF"}
    assert len({f["seccion"] for f in filas if f["grupo"] == "P5-02"}) == 1                     # el grupo es la misma sección
    assert len(controles) == 13 and sum(not c["cita_conforme"] for c in controles) == 2
    assert {(c["norma"], c["articulo"]) for c in controles if not c["cita_conforme"]} == {("NORM_04", "3.20"), ("NORM_01", "4.1")}


def _brecha(norma, articulo, cita, seccion="S1"):
    return {"id": f"{seccion}|{norma}|{articulo}", "seccion": seccion, "norma": norma, "articulo": articulo, "cita": cita, "clase": "Mayor", "nivel": "Medio", "responsable": "G", "titulo": "t"}


def _resultado(brechas):
    return {"registro_brechas": brechas, "resumen_ejecutivo": {}, "riesgos": [], "alertas": []}


def test_el_recall_de_p5_cuenta_11_amenazas_y_las_oportunidades_van_aparte(tmp_path):
    gt, espejos = _cargar(tmp_path)
    brechas = [_brecha("NORM_01", "4.1", "Aquí dice frase P5-01-D tal cual."),
               _brecha("NORM_05", "1.6", "Dice frase P5-03-IF y nada más."),                     # artículo equivalente
               _brecha("NORM_04", "3.6", "Esto es la frase P5-04-OP de la oferta.")]              # sobre la oportunidad
    ev = E.evaluar(_resultado(brechas), gt, espejos, "P5")
    assert ev["n_trampas"] == 11 and ev["encontradas"] == 2                                       # las oportunidades no entran al recall
    assert [(o["id"], o["marcada"]) for o in ev["oportunidades"]] == [("P5-04-OP", True), ("P5-02-OP", False)]
    texto = E.informe_md(ev)
    assert "Oportunidades (P5" in texto and "P5-04-OP" in texto


def test_el_grupo_se_cubre_con_que_se_encuentre_una_de_sus_trampas(tmp_path):
    gt, espejos = _cargar(tmp_path)
    ev = E.evaluar(_resultado([_brecha("NORM_02", "2.15", "Se lee frase P5-02-IF en la oferta.")]), gt, espejos, "P5")
    (g,) = ev["grupos"]
    assert g["grupo"] == "P5-02" and g["ids"] == ["P5-02-EX", "P5-02-D1", "P5-02-IF"] and g["cubierto"] is True and g["encontradas"] == 1      # solo IF (equivalente 2.15)
    assert ev["encontradas"] == 1                                                              # el recall estricto sigue siendo por trampa
    vacio = E.evaluar(_resultado([]), gt, espejos, "P5")
    assert vacio["grupos"][0]["cubierto"] is False and "Grupos de trampas (P5)" in E.informe_md(vacio)


def test_falsas_alarmas_sobre_los_13_controles_con_y_sin_cita(tmp_path):
    gt, espejos = _cargar(tmp_path)
    brechas = [_brecha("NORM_01", "9.3", "texto con cita del control 3 incluida"),               # control con cita: frase y artículo
               _brecha("NORM_01", "9.4", "otra cosa distinta que cae en el mismo artículo"),            # mismo artículo pero otra frase: no cuenta
               _brecha("NORM_04", "3.20", "cualquier frase anclada al artículo del control 12"),  # control sin cita («None»): cuenta por artículo
               _brecha("NORM_01", "4.1", "Aquí dice frase P5-01-D tal cual.")]                     # artículo del control 13 pero es la trampa encontrada: no es falsa alarma
    ev = E.evaluar(_resultado(brechas), gt, espejos, "P5")
    marcados = {m["cita"] or m["articulo"]: m["marcado"] for m in ev["espejos"]}
    assert ev["n_espejos"] == 13 and ev["falsas_alarmas"] == 2 and ev["encontradas"] == 1
    assert marcados["cita del control 3"] and not marcados["cita del control 4"] and marcados["3.20"] and not marcados["4.1"]


def test_un_control_sin_cita_en_modo_lista_nunca_se_marca(tmp_path):
    gt, espejos = _cargar(tmp_path)
    ev = E.evaluar({"riesgos_identificados": [{"cita_oferta": "algo cualquiera none"}]}, gt, espejos, "P5")
    assert ev["modo"] == "lista" and ev["falsas_alarmas"] == 0


def test_combinar_suma_grupos_y_oportunidades_de_varias_ofertas(tmp_path):
    gt, espejos = _cargar(tmp_path)
    ev = E.evaluar(_resultado([]), gt, espejos, "P5")
    total = E.combinar([ev, ev])
    assert len(total["grupos"]) == 2 and len(total["oportunidades"]) == 4
