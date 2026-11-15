"""Preparación del CSV de extras (evaluacion/preparar_extras.py) y vuelco de etiquetas (evaluacion/aplicar_etiquetas.py) con JSON y CSV armados a mano (sin leer datos/)."""
import csv
import json
import os

import pytest

from evaluacion import aplicar_etiquetas as AE
from evaluacion import evaluar as E
from evaluacion import preparar_extras as PE

LARGO = "Texto del artículo. " * 60                     # 1200 caracteres


def _brecha(n, norma, articulo, cita, seccion="S3", seccion_oferta="3 Sección", **extra):
    return {"id": f"{seccion}|{norma}|{articulo}|{n}", "seccion": seccion, "seccion_oferta": seccion_oferta, "norma": norma, "articulo": articulo, "cita": cita, "oraciones": ["O1", "O2"],
            "oraciones_texto": {"O1": "Primera oración.", "O2": "Segunda\n oración."}, "texto_articulo": LARGO, "titulo": f"título {n}", "clase": "Mayor", "fuente": "DESVIO",
            "verificacion_previa": {"veredicto": "Incumple", "explicacion": "no cumple\nel requisito", "discrepancia_numerica": False}, **extra}


BRECHAS = [
    _brecha(1, "NORM_01", "4.2", "Caída de tensión en el tramo terminal 2,1 %"),                # heredada de extras_revision.csv (la barra de la celda no importa)
    _brecha(2, "NORM_02", "5.1", "El plazo es de diez días."),                                  # heredada de otro *_extras.csv
    _brecha(3, "NORM_03", "2.4", "El registro se entrega al final."),                           # pendiente (sin etiqueta previa)
    _brecha(4, "NORM_04", "3.1", "Dos corridas dicen cosas distintas."),                        # conflicto entre archivos: pendiente
    _brecha(5, "NORM_05", "1.6", "Con etiqueta vacía antes."),                                  # una fila previa sin etiqueta no cuenta
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


def test_etiquetas_validas_como_las_del_juez_y_marcas_humanas_de_siempre():
    assert [PE.normalizar_etiqueta(x) for x in ("VALIDA", "valida", "no valida", "NO-VALIDA", "Dudosa", "sí", "", None)] == ["VALIDA", "VALIDA", "NO_VALIDA", "NO_VALIDA", "DUDOSA", "", "", ""]
    assert PE.etiqueta_de_fila({"valido": "Sí"}) == "VALIDA" and PE.etiqueta_de_fila({"valido": "no"}) == "NO_VALIDA" and PE.etiqueta_de_fila({"etiqueta": "DUDOSA", "valido": ""}) == "DUDOSA"
    assert PE.etiqueta_de_fila({"valido": ""}) == "" and PE.VALIDO_DE == {"VALIDA": "sí", "NO_VALIDA": "no", "DUDOSA": ""}


def test_las_etiquetas_previas_salen_de_los_csv_de_la_carpeta_y_los_conflictos_no_se_heredan(carpeta):
    tmp, _ = carpeta
    e = PE.cargar_etiquetas(str(tmp))
    assert e[PE.clave_herencia("NORM_01", "4.2", "Caída de tensión en el tramo terminal 2,1 %")]["valor"] == "VALIDA"
    assert e[PE.clave_herencia("NORM_02", "5.1", "El plazo es de diez días.")]["fuentes"] == {"analisis_riesgos_P9_otra_corrida_extras.csv": "NO_VALIDA"}
    conflicto = e[PE.clave_herencia("NORM_04", "3.1", "Dos corridas dicen cosas distintas.")]
    assert conflicto["valor"] is None and set(conflicto["fuentes"].values()) == {"VALIDA", "NO_VALIDA"}
    assert PE.clave_herencia("NORM_05", "1.6", "Con etiqueta vacía antes.") not in e


def test_prepara_el_csv_con_las_columnas_de_tabla_comparativa_y_las_de_ayuda(carpeta):
    tmp, ruta = carpeta
    r = PE.preparar_oferta("P9", str(ruta), [], [])
    assert (r["estado"], r["extras"], r["heredadas"], r["pendientes"]) == ("creado", 5, 2, 3) and r["ruta"] == E.ruta_extras(str(ruta))
    filas = _leer(r["ruta"])
    assert list(filas[0]) == PE.COLUMNAS and {"oferta", "seccion", "norma", "articulo", "cita", "titulo", "clase", "valido"} <= set(PE.COLUMNAS)
    assert [f["origen"] for f in filas] == ["heredada", "heredada", "pendiente", "pendiente", "pendiente"]
    assert [f["etiqueta"] for f in filas] == ["VALIDA", "NO_VALIDA", "", "", ""] and [f["valido"] for f in filas] == ["sí", "no", "", "", ""]
    assert filas[0]["nota"] == "heredada de extras_revision.csv"
    p = filas[2]
    assert (p["id"], p["oferta"], p["seccion"], p["norma"], p["articulo"], p["clase"], p["tipo_brecha"]) == ("S3|NORM_03|2.4|3", "P9", "3 Sección", "NORM_03", "2.4", "Mayor", "DESVIO")
    assert p["veredicto_verificador"] == "Incumple" and p["explicacion_verificador"] == "no cumple el requisito" and p["cita"] == "El registro se entrega al final."
    assert PE.LARGO_ARTICULO == 800 and 800 <= len(p["texto_articulo"]) <= 801 and p["texto_articulo"].endswith("…")
    assert filas[3]["nota"].startswith("conflicto entre etiquetas previas:")


def test_el_csv_generado_lo_lee_evaluar_y_con_todo_etiquetado_da_la_precision(carpeta):
    tmp, ruta = carpeta
    r = PE.preparar_oferta("P9", str(ruta), [], [])
    ev = E.evaluar(E._cargar(str(ruta)), [], [], "P9")
    E.asignar_precision(ev, E.leer_csv(r["ruta"]))
    assert ev["precision"] is None                                                       # faltan las pendientes
    filas = _leer(r["ruta"])
    for f in filas:
        f["etiqueta"], f["valido"] = f["etiqueta"] or "VALIDA", f["valido"] or "sí"
    _escribir(r["ruta"], filas, PE.COLUMNAS)
    E.asignar_precision(ev, E.leer_csv(r["ruta"]))
    assert (ev["precision_k"], ev["precision_n"]) == (4, 5)                              # 4 válidas de 5 (la heredada NO_VALIDA no suma); la vetada por cálculo no cuenta como brecha


def test_las_pendientes_de_todas_las_ofertas_van_a_un_archivo_unificado_sin_rutas_absolutas(carpeta, monkeypatch, tmp_path_factory, capsys):
    tmp, ruta = carpeta
    cfg = tmp_path_factory.mktemp("cfg") / "config.json"
    cfg.write_text(json.dumps({"configuraciones": {"mi config": {"P9": str(ruta), "P8": "no_existe.json"}}}), encoding="utf-8")
    unificado = tmp_path_factory.mktemp("diag") / "extras_pendientes.csv"
    monkeypatch.setattr(PE.E, "cargar_gt", lambda oferta: [])
    monkeypatch.setattr(PE.E, "cargar_espejos", lambda oferta: [])
    r = PE.main(["--config", "mi config", "--ofertas", "P9", "P8", "--archivo-config", str(cfg), "--pendientes", str(unificado)])
    salida = capsys.readouterr()
    assert [x["oferta"] for x in r] == ["P9"] and "P9: 5 extras: 2 heredadas, 3 pendientes" in salida.out and "Total: 5 extras: 2 heredadas, 3 pendientes." in salida.out
    assert "evaluacion.tabla_comparativa --config evaluacion/config_reeval.json" in salida.out and "P8: no hay JSON" in salida.err
    filas = _leer(str(unificado))
    assert list(filas[0]) == PE.COLUMNAS_PENDIENTES and len(filas) == 3 and {f["etiqueta"] for f in filas} == {""} and "valido" not in filas[0] and "origen" not in filas[0]
    assert all(not os.path.isabs(f["archivo"]) and f["archivo"].endswith("_extras.csv") and "\\" not in f["archivo"] for f in filas)
    PE.main(["--config", "mi config", "--ofertas", "P9", "--archivo-config", str(cfg), "--pendientes", str(unificado)])
    assert "ya existe" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="No hay una configuración"):
        PE.main(["--config", "otra", "--archivo-config", str(cfg)])


def test_nunca_pisa_un_csv_existente_ni_el_unificado(carpeta, tmp_path_factory, monkeypatch):
    tmp, ruta = carpeta
    existente = tmp / (ruta.stem + "_extras.csv")
    existente.write_text("etiquetado a mano\n", encoding="utf-8")
    r = PE.preparar_oferta("P9", str(ruta), [], [])
    assert r["estado"] == "ya existe" and existente.read_text(encoding="utf-8") == "etiquetado a mano\n"
    with pytest.raises(FileExistsError):
        PE.escribir_csv_nuevo([], str(existente))
    unificado = tmp_path_factory.mktemp("diag") / "u.csv"
    unificado.write_text("etiquetado a mano\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        PE._escribir_nuevo([], PE.COLUMNAS_PENDIENTES, str(unificado))
    assert unificado.read_text(encoding="utf-8") == "etiquetado a mano\n"


# --- aplicar_etiquetas ---

@pytest.fixture
def con_unificado(carpeta, monkeypatch, tmp_path_factory):
    tmp, ruta = carpeta
    r = PE.preparar_oferta("P9", str(ruta), [], [])
    monkeypatch.setattr(PE, "RAIZ", str(tmp))                                           # las rutas del unificado son relativas a la raíz del repo
    pendientes = [{**f, "archivo": PE.ruta_relativa(r["ruta"])} for f in _leer(r["ruta"]) if f["origen"] == "pendiente"]
    unificado = tmp_path_factory.mktemp("diag") / "extras_pendientes.csv"
    return tmp, r["ruta"], pendientes, unificado


def _etiquetar(pendientes, unificado, etiquetas):
    for f, e in zip(pendientes, etiquetas):
        f["etiqueta"] = e
    _escribir(unificado, pendientes, PE.COLUMNAS_PENDIENTES)


def test_aplicar_vuelca_las_etiquetas_y_deriva_valido(con_unificado, monkeypatch, capsys):
    tmp, destino, pendientes, unificado = con_unificado
    monkeypatch.setattr(AE.PE, "RAIZ", str(tmp))
    _etiquetar(pendientes, unificado, ["NO_VALIDA", "valida", "DUDOSA"])
    total = AE.main(["--etiquetas", str(unificado)])
    assert (total["aplicadas"], total["omitidas"], total["no_encontradas"], total["dudosas_sin_valido"]) == (3, 0, 0, 1)
    filas = {f["id"]: f for f in _leer(destino)}
    assert (filas["S3|NORM_03|2.4|3"]["etiqueta"], filas["S3|NORM_03|2.4|3"]["valido"]) == ("NO_VALIDA", "no")
    assert (filas["S3|NORM_04|3.1|4"]["etiqueta"], filas["S3|NORM_04|3.1|4"]["valido"]) == ("VALIDA", "sí")
    assert (filas["S3|NORM_05|1.6|5"]["etiqueta"], filas["S3|NORM_05|1.6|5"]["valido"]) == ("DUDOSA", "")
    assert filas["S3|NORM_01|4.2|1"]["etiqueta"] == "VALIDA" and list(next(iter(filas.values()))) == PE.COLUMNAS         # las heredadas no se tocan y las columnas se conservan
    assert "DUDOSA con «valido» vacío" in capsys.readouterr().out


def test_aplicar_dudosa_cuenta_como_si_o_no_y_la_precision_se_calcula(con_unificado, monkeypatch):
    tmp, destino, pendientes, unificado = con_unificado
    monkeypatch.setattr(AE.PE, "RAIZ", str(tmp))
    _etiquetar(pendientes, unificado, ["VALIDA", "NO_VALIDA", "DUDOSA"])
    AE.main(["--etiquetas", str(unificado), "--dudosa", "no"])
    filas = _leer(destino)
    assert [f["valido"] for f in filas] == ["sí", "no", "sí", "no", "no"] and filas[4]["etiqueta"] == "DUDOSA"
    ev = E.evaluar(E._cargar(destino[:-len("_extras.csv")] + ".json"), [], [], "P9")
    E.asignar_precision(ev, E.leer_csv(destino))
    assert (ev["precision_k"], ev["precision_n"]) == (2, 5)


def test_aplicar_no_pisa_etiquetas_existentes_salvo_con_forzar(con_unificado, monkeypatch, capsys):
    tmp, destino, pendientes, unificado = con_unificado
    monkeypatch.setattr(AE.PE, "RAIZ", str(tmp))
    _etiquetar(pendientes, unificado, ["VALIDA", "VALIDA", "VALIDA"])
    AE.main(["--etiquetas", str(unificado)])
    _etiquetar(pendientes, unificado, ["NO_VALIDA", "NO_VALIDA", "NO_VALIDA"])
    total = AE.main(["--etiquetas", str(unificado)])
    assert (total["aplicadas"], total["omitidas"]) == (0, 3) and [f["etiqueta"] for f in _leer(destino)][2:] == ["VALIDA"] * 3
    total = AE.main(["--etiquetas", str(unificado), "--forzar"])
    assert total["aplicadas"] == 3 and [f["etiqueta"] for f in _leer(destino)][2:] == ["NO_VALIDA"] * 3
    assert "omitidas por tener etiqueta" in capsys.readouterr().out


def test_aplicar_cuenta_las_filas_sin_etiqueta_invalidas_y_sin_destino(con_unificado, monkeypatch, capsys):
    tmp, destino, pendientes, unificado = con_unificado
    monkeypatch.setattr(AE.PE, "RAIZ", str(tmp))
    pendientes.append({**pendientes[0], "cita": "una cita que no está en el destino", "etiqueta": "VALIDA"})
    _etiquetar(pendientes[:3], unificado, ["", "quizás", "VALIDA"])
    _escribir(unificado, pendientes, PE.COLUMNAS_PENDIENTES)
    total = AE.main(["--etiquetas", str(unificado)])
    out = capsys.readouterr().out
    assert (total["aplicadas"], total["no_encontradas"]) == (1, 1) and "1 filas sin etiqueta y 1 con una etiqueta que no es VALIDA" in out
    assert [f["etiqueta"] for f in _leer(destino)][2:] == ["", "", "VALIDA"]


# --- nombre del archivo de pendientes según la configuración y las ofertas ---

def test_el_nombre_de_las_pendientes_sale_de_la_configuracion_y_las_ofertas():
    assert PE.nombre_pendientes("gpt-oss-120b esfuerzo bajo (elegida)", ["P1", "P2"]) == "extras_pendientes_gpt-oss-120b-esfuerzo-bajo-elegida_P1P2.csv"
    assert PE.nombre_pendientes("qwen3:8b local (elegida)", ["P4", "P3"]) == "extras_pendientes_qwen3-8b-local-elegida_P3P4.csv"          # las ofertas van ordenadas
    assert PE.ruta_pendientes("m", ["P1"], "carpeta") == os.path.join("carpeta", "extras_pendientes_m_P1.csv")


def test_sin_salida_el_archivo_se_nombra_por_ofertas_y_no_se_pisa_sin_forzar(carpeta, monkeypatch, tmp_path_factory, capsys):
    tmp, ruta = carpeta
    cfg = tmp_path_factory.mktemp("cfg") / "config.json"
    cfg.write_text(json.dumps({"configuraciones": {"mi config": {"P9": str(ruta)}}}), encoding="utf-8")
    diag = tmp_path_factory.mktemp("diag")
    monkeypatch.setattr(PE, "DIAGNOSTICOS", str(diag))
    monkeypatch.setattr(PE.E, "cargar_gt", lambda oferta: [])
    monkeypatch.setattr(PE.E, "cargar_espejos", lambda oferta: [])
    PE.main(["--config", "mi config", "--ofertas", "P9", "--archivo-config", str(cfg)])
    esperado = diag / "extras_pendientes_mi-config_P9.csv"
    assert esperado.is_file() and len(_leer(str(esperado))) == 3
    assert not (diag / "extras_pendientes_gptoss_P3P4.csv").exists()                         # ya no hay un nombre fijo
    # un archivo existente de pendientes no se pisa sin --forzar
    esperado.write_text("previo", encoding="utf-8")
    os.remove(E.ruta_extras(str(ruta)))                                                       # para que haya pendientes que escribir otra vez
    capsys.readouterr()
    PE.main(["--config", "mi config", "--ofertas", "P9", "--archivo-config", str(cfg)])
    assert esperado.read_text(encoding="utf-8") == "previo" and "--forzar" in capsys.readouterr().out
    # con --forzar sí, y con --salida (o su alias --pendientes) se fuerza el nombre
    os.remove(E.ruta_extras(str(ruta)))
    PE.main(["--config", "mi config", "--ofertas", "P9", "--archivo-config", str(cfg), "--forzar"])
    assert esperado.read_text(encoding="utf-8-sig").startswith("archivo;") and len(_leer(str(esperado))) == 3
    os.remove(E.ruta_extras(str(ruta)))
    otro = diag / "otro.csv"
    PE.main(["--config", "mi config", "--ofertas", "P9", "--archivo-config", str(cfg), "--salida", str(otro)])
    assert otro.is_file()
