import json
import os

from scripts import elegir_json

RUTA = os.path.join(os.path.dirname(__file__), os.pardir, "scripts", "relanzar_con_rag_p3p4.ps1")


def _json(carpeta, nombre, condicion, mtime, contenido=None):
    ruta = os.path.join(str(carpeta), nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido if contenido is not None else json.dumps({"configuracion_analisis": {"condicion": condicion}}))
    os.utime(ruta, (mtime, mtime))
    return ruta


def test_elige_el_mas_reciente_con_la_condicion_sin_mirar_el_nombre(tmp_path):
    _json(tmp_path, "analisis_riesgos_P3_oferta_20261101_000000.json", "sin_rag", 100)
    nuevo = _json(tmp_path, "analisis_riesgos_P3_oferta_20261102_000000.json", "sin_rag", 300)
    _json(tmp_path, "analisis_riesgos_P3_oferta_20261103_000000.json", "rag_verificacion", 500)      # el mas reciente, pero con RAG
    elegido, lineas = elegir_json.elegir(str(tmp_path))
    assert elegido == nuevo
    assert sum("ELEGIDO" in l for l in lineas) == 1 and any("rag_verificacion" in l for l in lineas)


def test_excluye_reclasificados_parciales_y_de_la_nube_aunque_sean_sin_rag(tmp_path):
    for nombre in ("analisis_riesgos_P1_x_reclasificado.json", "analisis_riesgos_P1_x_20261102_parcial.json", "analisis_riesgos_P1_x_deepinfra-qwen3-32b.json"):
        _json(tmp_path, nombre, "sin_rag", 900)
    bueno = _json(tmp_path, "analisis_riesgos_P1_x_20261101_000000.json", "sin_rag", 100)
    elegido, lineas = elegir_json.elegir(str(tmp_path))
    assert elegido == bueno and sum("excluido" in l for l in lineas) == 3


def test_archivos_ilegibles_o_sin_condicion_se_saltean_y_sin_candidatos_no_elige(tmp_path):
    _json(tmp_path, "analisis_riesgos_a.json", None, 100, contenido="{no es json")
    _json(tmp_path, "analisis_riesgos_b.json", None, 200, contenido=json.dumps({"configuracion_analisis": {}}))
    _json(tmp_path, "otro_archivo.json", "sin_rag", 300)                                              # no es analisis_riesgos_*
    elegido, lineas = elegir_json.elegir(str(tmp_path))
    assert elegido is None and any("ilegible" in l for l in lineas)
    assert elegir_json.elegir(str(tmp_path / "no_existe"))[0] is None


def test_la_condicion_buscada_es_un_parametro(tmp_path):
    con = _json(tmp_path, "analisis_riesgos_P3_a.json", "rag_verificacion", 100)
    _json(tmp_path, "analisis_riesgos_P3_b.json", "sin_rag", 200)
    assert elegir_json.elegir(str(tmp_path), "rag_verificacion")[0] == con


def test_el_programa_imprime_la_linea_json_que_captura_el_script_o_sale_con_1(tmp_path, capsys):
    ruta = _json(tmp_path, "analisis_riesgos_P3_a.json", "sin_rag", 100)
    assert elegir_json.main([str(tmp_path)]) == 0
    assert f"JSON: {ruta}" in capsys.readouterr().out.splitlines()
    assert elegir_json.main([str(tmp_path), "--condicion", "otra"]) == 1


def _texto():
    with open(RUTA, encoding="utf-8") as f:
        return f.read()


def test_el_script_relanza_solo_p3_y_p4_con_rag_y_compara_contra_los_sin_rag_elegidos_por_condicion():
    t = _texto()
    codigo = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("#"))
    assert "scripts.run_oferta" in codigo and "--sin-rag" not in codigo        # los sin RAG no se vuelven a correr: se eligen
    assert 'if ($o.Nombre -eq "P3" -or $o.Nombre -eq "P4")' in codigo and "scripts.elegir_json" in codigo and "sin_rag" in codigo
    assert codigo.count("--comparar") == 1 and "--agregado" in codigo and '"P1", "P2", "P3", "P4"' in codigo and '"P3", "P4"' in codigo
    assert "analisis_riesgos_P1_oferta_TBP01_20261108_151743_reclasificado.json" in t and "analisis_riesgos_P2_oferta_PH400_20261108_172507_reclasificado.json" in t
    assert "omitido" in t and "param([switch]$Apagar)" in t and "shutdown /s /f /t 120" in t


def test_el_script_sigue_el_patron_de_los_otros_ascii_tee_funciones_sin_return_y_tiempos():
    t = _texto()
    assert all(ord(c) < 128 for c in t) and "Tee-Object" in t and "Out-Host" in t and r"datos\Resultados\relanzar_con_rag_" in t
    assert "return " not in t.lower() and "$script:" in t and "FALLO" in t and "catch" in t.lower() and "tiempo total" in t.lower()
