"""Preparación del CSV de extras (evaluacion/preparar_extras.py) con JSON y CSV armados a mano (sin leer datos/)."""
import csv
import json

import pytest

from evaluacion import evaluar as E
from evaluacion import preparar_extras as PE

LARGO = "Texto del artículo. " * 60                     # 1200 caracteres


def _brecha(n, norma, articulo, cita, seccion="S3", seccion_oferta="3 Sección", **extra):
    return {"id": f"{seccion}|{norma}|{articulo}|{n}", "seccion": seccion, "seccion_oferta": seccion_oferta, "norma": norma, "articulo": articulo, "cita": cita, "oraciones": ["O1", "O2"],
            "oraciones_texto": {"O1": "Primera oración.", "O2": "Segunda\n oración."}, "texto_articulo": LARGO, "titulo": f"título {n}", "clase": "Mayor",
            "verificacion_previa": {"veredicto": "Incumple", "explicacion": "no cumple\nel requisito", "discrepancia_numerica": False}, **extra}


BRECHAS = [
    _brecha(1, "NORM_01", "4.2", "Caída de tensión en el tramo terminal 2,1 %"),                # heredada de extras_revision.csv (la barra de la celda no importa)
    _brecha(2, "NORM_02", "5.1", "El plazo es de diez días."),                                  # heredada de otro *_extras.csv
    _brecha(3, "NORM_03", "2.4", "El registro se entrega al final."),                           # pendiente (sin etiqueta previa)
    _brecha(4, "NORM_04", "3.1", "Dos corridas dicen cosas distintas."),                        # conflicto entre archivos: pendiente
    _brecha(5, "NORM_05", "1.6", "Con etiqueta vacía antes."),                                  # una fila previa sin sí/no no cuenta
    {**_brecha(6, "NORM_01", "4.2", "Descartada por el cálculo."), "estado": "descartada por cálculo"},     # no es un extra
]


def _escribir(ruta, filas, columnas=("oferta", "seccion", "norma", "articulo", "cita", "titulo", "clase", "valido")):
    with open(ruta, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(columnas), delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def _leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


@pytest.fixture
def carpeta(tmp_path):
    ruta = tmp_path / "analisis_riesgos_P9_oferta_X_20261114_gpt-oss-elegido.json"
    ruta.write_text(json.dumps({"registro_brechas": BRECHAS, "riesgos": [], "alertas": []}), encoding="utf-8")
    _escribir(tmp_path / "extras_revision.csv", [{"norma": "NORM_01", "articulo": "4.2.", "cita": "Caída de tensión en el tramo terminal | 2,1 %", "valido": "Sí"},
                                                 {"norma": "NORM_04", "articulo": "3.1", "cita": "Dos corridas dicen cosas distintas.", "valido": "sí"},
                                                 {"norma": "NORM_05", "articulo": "1.6", "cita": "Con etiqueta vacía antes.", "valido": ""}])
    _escribir(tmp_path / "analisis_riesgos_P9_otra_corrida_extras.csv", [{"norma": "NORM_02", "articulo": "5.1", "cita": "EL PLAZO es de diez días.", "valido": "no"},
                                                                         {"norma": "NORM_04", "articulo": "3.1", "cita": "Dos corridas dicen cosas distintas.", "valido": "no"}])
    return tmp_path, ruta


def test_clave_de_herencia_ignora_barras_mayusculas_y_el_punto_final_del_articulo():
    assert PE.clave_herencia("NORM_01", "4.2.", "Caída de tensión | 2,1 %") == PE.clave_herencia(" NORM_01", "4.2", "caida de tension\n2,1 %")
    assert PE.clave_herencia("NORM_01", "4.2", "a") != PE.clave_herencia("NORM_02", "4.2", "a")


def test_las_etiquetas_previas_salen_de_los_csv_de_la_carpeta_y_los_conflictos_no_se_heredan(carpeta):
    tmp, _ = carpeta
    e = PE.cargar_etiquetas(str(tmp))
    assert e[PE.clave_herencia("NORM_01", "4.2", "Caída de tensión en el tramo terminal 2,1 %")]["valor"] == "Sí"
    assert e[PE.clave_herencia("NORM_02", "5.1", "El plazo es de diez días.")]["fuentes"] == {"analisis_riesgos_P9_otra_corrida_extras.csv": "no"}
    conflicto = e[PE.clave_herencia("NORM_04", "3.1", "Dos corridas dicen cosas distintas.")]
    assert conflicto["valor"] is None and set(conflicto["fuentes"].values()) == {"sí", "no"}
    assert PE.clave_herencia("NORM_05", "1.6", "Con etiqueta vacía antes.") not in e


def test_prepara_el_csv_con_heredadas_y_pendientes_y_las_columnas_de_ayuda(carpeta):
    tmp, ruta = carpeta
    r = PE.preparar_oferta("P9", str(ruta), [], [])
    assert (r["estado"], r["extras"], r["heredadas"], r["pendientes"]) == ("creado", 5, 2, 3) and r["ruta"] == E.ruta_extras(str(ruta))
    filas = _leer(r["ruta"])
    assert list(filas[0]) == PE.COLUMNAS and [f["origen"] for f in filas] == ["heredada", "heredada", "pendiente", "pendiente", "pendiente"]
    assert [f["valido"] for f in filas] == ["Sí", "no", "", "", ""] and filas[0]["heredada_de"] == "extras_revision.csv"
    pendiente = filas[2]
    assert pendiente["veredicto_verificador"] == "Incumple" and pendiente["explicacion_verificador"] == "no cumple el requisito"
    assert pendiente["oracion_citada"] == "[O1] Primera oración. [O2] Segunda oración." and pendiente["seccion"] == "3 Sección" and pendiente["clase"] == "Mayor"
    assert PE.LARGO_ARTICULO <= len(pendiente["texto_articulo"]) <= PE.LARGO_ARTICULO + 1 and pendiente["texto_articulo"].endswith("…")       # 600 caracteres y la marca de recorte
    assert filas[3]["heredada_de"].startswith("conflicto:") and filas[0]["oracion_citada"] == "" and filas[0]["texto_articulo"] == ""     # las heredadas no llevan el contexto


def test_el_csv_generado_lo_lee_evaluar_y_con_todo_etiquetado_da_la_precision(carpeta):
    tmp, ruta = carpeta
    r = PE.preparar_oferta("P9", str(ruta), [], [])
    resultado = E._cargar(str(ruta))
    ev = E.evaluar(resultado, [], [], "P9")
    E.asignar_precision(ev, E.leer_csv(r["ruta"]))
    assert ev["precision"] is None                                                       # faltan las pendientes
    filas = _leer(r["ruta"])
    for f in filas:
        f["valido"] = f["valido"] or "sí"
    _escribir(r["ruta"], filas, PE.COLUMNAS)
    E.asignar_precision(ev, E.leer_csv(r["ruta"]))
    assert (ev["precision_k"], ev["precision_n"]) == (4, 5)                              # 4 válidos de 5 brechas (la vetada por cálculo no cuenta)


def test_nunca_pisa_un_csv_existente(carpeta):
    tmp, ruta = carpeta
    existente = tmp / (ruta.stem + "_extras.csv")
    existente.write_text("etiquetado a mano\n", encoding="utf-8")
    r = PE.preparar_oferta("P9", str(ruta), [], [])
    assert r["estado"] == "ya existe" and existente.read_text(encoding="utf-8") == "etiquetado a mano\n"
    with pytest.raises(FileExistsError):
        PE.escribir_csv_nuevo([], str(existente))
    assert existente.read_text(encoding="utf-8") == "etiquetado a mano\n"


def test_main_resuelve_la_configuracion_imprime_los_conteos_y_el_comando(carpeta, tmp_path_factory, monkeypatch, capsys):
    tmp, ruta = carpeta
    cfg = tmp_path_factory.mktemp("cfg") / "config.json"
    cfg.write_text(json.dumps({"configuraciones": {"mi config": {"P9": str(ruta), "P8": "no_existe.json"}}}), encoding="utf-8")
    monkeypatch.setattr(PE.E, "cargar_gt", lambda oferta: [])
    monkeypatch.setattr(PE.E, "cargar_espejos", lambda oferta: [])
    r = PE.main(["--config", "mi config", "--ofertas", "P9", "P8", "--archivo-config", str(cfg)])
    salida = capsys.readouterr()
    assert [x["oferta"] for x in r] == ["P9"] and "P9: 5 extras: 2 heredadas, 3 pendientes" in salida.out and "Total: 5 extras: 2 heredadas, 3 pendientes." in salida.out
    assert "evaluacion.tabla_comparativa --config evaluacion/config_reeval.json" in salida.out and "P8: no hay JSON" in salida.err
    PE.main(["--config", "mi config", "--ofertas", "P9", "--archivo-config", str(cfg)])
    assert "ya existe" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="No hay una configuración"):
        PE.main(["--config", "otra", "--archivo-config", str(cfg)])
