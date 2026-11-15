import json
import os

import pytest

from evaluacion import estabilidad as est
from evaluacion import evaluar as E

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _cargar(nombre):
    with open(os.path.join(FX, nombre), encoding="utf-8") as f:
        return json.load(f)


GT = E.cargar_gt("P9", os.path.join(FX, "estabilidad_gt.csv"))


def test_por_trampa_acuerdo_global_y_kappa_sobre_dos_corridas_sinteticas():
    c = est.comparar(_cargar("estabilidad_a.json"), _cargar("estabilidad_b.json"), GT, "P9")
    por_id = {f["id"]: (f["a"], f["b"], f["acuerdo"]) for f in c["trampas"]}
    assert por_id == {"P9-01-A": (True, True, True), "P9-02-A": (True, False, False), "P9-03-A": (False, True, False), "P9-04-A": (False, False, True)}
    assert c["acuerdo"] == 0.5 and c["n"] == 4 and (c["detectadas_a"], c["detectadas_b"]) == (2, 2)
    assert c["kappa"] == pytest.approx(0.0)                       # po = pe = 0,5
    assert c["cumple"] is False and c["umbral"] == 0.9 and c["avisos"] == []


def test_riesgos_por_corrida_y_jaccard_ignoran_las_brechas_descartadas_por_calculo():
    a, b = _cargar("estabilidad_a.json"), _cargar("estabilidad_b.json")
    assert est.riesgos_reportados(a) == {("S1", "NORM_01", "1.1"), ("S1", "NORM_02", "2.1"), ("S2", "NORM_05", "9.9")}
    assert est.riesgos_reportados(b) == {("S1", "NORM_01", "1.1"), ("S2", "NORM_03", "3.1")}         # la tercera está «descartada por cálculo»
    c = est.comparar(a, b, GT, "P9")
    assert (c["brechas_a"], c["brechas_b"], c["riesgos_agrupados_a"], c["riesgos_agrupados_b"]) == (3, 2, 3, 2)
    assert c["jaccard"] == pytest.approx(1 / 4) and (c["solo_a"], c["solo_b"]) == (2, 1)
    assert est.jaccard(set(), set()) == 1.0


def test_dos_corridas_iguales_cumplen_el_criterio_con_kappa_uno_o_nd():
    a = _cargar("estabilidad_a.json")
    c = est.comparar(a, a, GT, "P9")
    assert c["acuerdo"] == 1.0 and c["cumple"] is True and c["jaccard"] == 1.0
    assert c["kappa"] == pytest.approx(1.0)
    # sin ninguna detectada en las dos corridas el kappa no existe (acuerdo esperado por azar = 1) pero el acuerdo es 100 %
    vacia = dict(a, registro_brechas=[])
    c0 = est.comparar(vacia, vacia, GT, "P9")
    assert c0["acuerdo"] == 1.0 and c0["kappa"] is None and c0["cumple"] is True


def test_el_umbral_es_inclusivo_y_se_informa_sin_cortar():
    a = _cargar("estabilidad_a.json")
    c = est.comparar(a, a, GT, "P9")
    texto = est.informe_md(c)
    assert "cumple" in texto and "no cumple" not in texto
    c["acuerdo"], c["cumple"] = 0.5, False
    assert "no cumple" in est.informe_md(c)


def test_huella_distinta_y_modelo_distinto_advierten_pero_no_cortan():
    a, b = _cargar("estabilidad_a.json"), _cargar("estabilidad_b_otra_huella.json")
    assert est.huella(a) != est.huella(b)
    c = est.comparar(a, b, GT, "P9")
    assert len(c["avisos"]) == 2 and any("huella" in x for x in c["avisos"]) and any("modelos difieren" in x for x in c["avisos"])
    assert "Advertencia" in est.informe_md(c) and c["acuerdo"] is not None


def test_usa_la_definicion_de_detectada_de_evaluar_py():
    a = _cargar("estabilidad_a.json")
    ev = E.evaluar(a, GT, [], "P9")
    assert est.detectadas(a, GT, "P9") == {t["id"]: t["estado"] == "encontrada" for t in ev["trampas"]}
    # la frase sin el artículo correcto («otro artículo») no es detectada, como en evaluar.py
    otra = json.loads(json.dumps(a))
    otra["registro_brechas"][0]["articulo"] = "7.7"
    assert est.detectadas(otra, GT, "P9")["P9-01-A"] is False


def test_un_resultado_en_modo_lista_se_rechaza():
    with pytest.raises(ValueError):
        est.detectadas({"riesgos_identificados": [{"cita_oferta": "x"}]}, GT, "P9")


def test_cli_imprime_el_informe_y_no_pisa_un_archivo_existente(tmp_path, capsys):
    salida = tmp_path / "est.md"
    args = ["--a", os.path.join(FX, "estabilidad_a.json"), "--b", os.path.join(FX, "estabilidad_b.json"), "--oferta", "P9",
            "--ground-truth", os.path.join(FX, "estabilidad_gt.csv"), "--salida", str(salida)]
    c = est.main(args)
    assert c["acuerdo"] == 0.5 and "Acuerdo global" in capsys.readouterr().out and salida.read_text(encoding="utf-8").startswith("# Estabilidad P9")
    salida.write_text("previo", encoding="utf-8")
    est.main(args)
    assert salida.read_text(encoding="utf-8") == "previo" and "ya existe" in capsys.readouterr().err
