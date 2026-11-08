import os

RUTA = os.path.join(os.path.dirname(__file__), os.pardir, "scripts", "correr_prueba_B5.ps1")


def _texto():
    with open(RUTA, encoding="utf-8") as f:
        return f.read()


def test_el_script_corre_p1_y_p2_con_rag_y_evalua():
    t = _texto()
    assert r"datos\ProyectoAnalizar\P1_oferta_TBP01.pdf" in t and r"datos\ProyectoAnalizar\P2_oferta_PH400.pdf" in t
    assert "scripts.run_oferta" in t and "evaluacion.evaluar" in t and "--agregado" in t
    codigo = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("#")).lower()
    assert "--sin-rag" not in codigo and "estabilidad" not in codigo and "sin_rag" not in codigo    # sin RAG y la repetición van en la corrida final


def test_el_script_loguea_con_tee_object_y_out_host_y_no_devuelve_salida_de_consola():
    t = _texto()
    assert "Tee-Object" in t and "Out-Host" in t and r"datos\Resultados" in t
    funciones = [l for l in t.splitlines() if l.startswith("function ")]
    assert funciones, "se esperan funciones"
    assert "return " not in t.lower().replace("returncode", "")                        # ninguna función devuelve nada: el estado va en variables del script
    assert "$script:" in t


def test_el_script_sigue_con_la_otra_oferta_si_una_falla_y_cierra_con_los_tiempos():
    t = _texto()
    assert "FALLO" in t and "catch" in t.lower() and "tiempo total" in t.lower()
    assert all(ord(c) < 128 for c in t), "el script es ASCII para no depender de la codificacion de PowerShell 5.1"
