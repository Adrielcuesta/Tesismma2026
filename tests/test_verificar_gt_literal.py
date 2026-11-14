"""Verificación del ground truth contra el texto de las ofertas (evaluacion/verificar_gt_literal.py) sobre una oferta armada a mano (sin leer datos/)."""
import csv

from evaluacion import verificar_gt_literal as V

TEXTO = ("Introducción\nEl equipo llega con su dossier completo.\n"
         "3 Alcance\nEl plazo de entrega es de 14 días. Caída de tensión en el tramo terminal\n2,1 %\nOtra oración sin nada.")
SECCIONES = [
    {"id": "S1", "titulos": ["Introducción"], "introduccion": True, "texto": "El equipo llega con su dossier completo.", "oraciones": [("O1", "El equipo llega con su dossier completo.")]},
    {"id": "S2", "titulos": ["3 Alcance"], "introduccion": False, "texto": "El plazo de entrega es de 14 días. Caída de tensión en el tramo terminal\n2,1 %\nOtra oración sin nada.",
     "oraciones": [("O1", "El plazo de entrega es de 14 días."), ("O2", "Caída de tensión en el tramo terminal 2,1 %"), ("O3", "Otra oración sin nada.")]}]
TRAMPAS = [{"id": "P9-01-A", "fragmento_trampa": "plazo de entrega es de 14 días"},
           {"id": "P9-02-M", "fragmento_trampa": "Caída de tensión en el tramo terminal | 2,1 %"},           # una celda de tabla: en el texto no hay barra ni salto igual
           {"id": "P9-03-B", "fragmento_trampa": "frase que la oferta no tiene"},
           {"id": "P9-04-B", "fragmento_trampa": "El equipo llega con su dossier completo"}]            # solo está en la introducción
CONFORMES = [{"cita_conforme": "Otra oración sin nada."}, {"cita_conforme": "Otra oración sin nada, y además un resto que la oferta no trae después de los sesenta caracteres iniciales"}]


def _filas():
    return V.analizar("P9", TEXTO, SECCIONES, TRAMPAS, CONFORMES)


def test_niveles_de_coincidencia_literal_normalizada_alfanumerica_y_ninguna():
    assert V.nivel_de_coincidencia("plazo de entrega es de 14 días", TEXTO) == "literal"
    assert V.nivel_de_coincidencia("PLAZO de entrega ES de 14 dias", TEXTO) == "normalizada"
    assert V.nivel_de_coincidencia("Caída de tensión en el tramo terminal | 2,1 %", TEXTO) == "normalizada"        # la barra de la tabla y el salto de línea son espacios
    assert V.nivel_de_coincidencia("caida-de-tension en el tramo terminal 2,1", TEXTO) == "alfanumérica"
    assert V.nivel_de_coincidencia("frase que la oferta no tiene", TEXTO) == "no encontrada" and V.nivel_de_coincidencia("", TEXTO) == "no encontrada"


def test_cada_fila_dice_que_ve_evaluar_y_que_ve_la_curva():
    f = {x["id"]: x for x in _filas()}
    assert [f[i]["nivel"] for i in ("P9-01-A", "P9-02-M", "P9-03-B", "P9-04-B")] == ["literal", "normalizada", "no encontrada", "literal"]
    assert (f["P9-01-A"]["evaluar"], f["P9-01-A"]["curva"], f["P9-01-A"]["seccion"]) == (True, True, "S2")
    # evaluar.norm conserva la barra: la frase de la celda no está en las oraciones unidas, aunque la curva (alfanumérica) sí la ubica
    assert (f["P9-02-M"]["evaluar"], f["P9-02-M"]["curva"], f["P9-02-M"]["conocido"]) == (False, True, True) and not f["P9-01-A"]["conocido"]
    assert (f["P9-03-B"]["evaluar"], f["P9-03-B"]["curva"]) == (False, False)
    # solo en la introducción: el texto la tiene (literal) pero no se verifica
    assert f["P9-04-B"]["solo_introduccion"] and f["P9-04-B"]["curva"] is False and f["P9-04-B"]["evaluar"] is True


def test_los_casos_conformes_usan_los_primeros_60_caracteres_para_evaluar():
    f = [x for x in _filas() if x["tipo"] == "conforme"]
    assert [x["id"] for x in f] == ["P9-C01", "P9-C02"] and f[0]["evaluar"] is True
    assert f[1]["nivel"] == "no encontrada" and f[1]["evaluar"] is False         # la frase completa no está; los primeros 60 caracteres traen el resto inventado


def test_el_informe_lista_las_no_literales_y_cuenta_las_que_evaluar_no_puede_ver():
    md = V.informe_md(_filas())
    assert "## No encontradas en forma literal (3 de 6)" in md
    assert "| P9 | trampa | P9-02-M | normalizada | **no** | sí |" in md and "| sí | Caída de tensión en el tramo terminal / 2,1 %" in md       # conocido, con la barra reemplazada en la tabla
    assert "| P9 | trampa | P9-03-B | no encontrada | **no** | **no** |" in md
    assert "| P9 | trampa | 4 | 2 | 1 | 0 | 1 | 2 | 2 |" in md and "no puede reconocer aunque el sistema cite la oración correcta" in md and ": P9-02-M, P9-03-B." in md
    assert "P9-04-B" not in md.split("## No encontradas")[1].split("## Lectura")[0]          # la 04 es literal (aunque solo esté en la introducción): no figura entre las no literales


def test_main_escribe_md_y_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "cargar_oferta", lambda oferta: {"texto": TEXTO, "secciones": SECCIONES})
    monkeypatch.setattr(V.E, "cargar_gt", lambda oferta: TRAMPAS)
    monkeypatch.setattr(V.E, "cargar_espejos", lambda oferta: CONFORMES)
    filas = V.main(["--ofertas", "P9", "--salida", str(tmp_path)])
    assert len(filas) == 6 and (tmp_path / "verificar_gt_literal.md").is_file()
    with open(tmp_path / "verificar_gt_literal.csv", encoding="utf-8-sig") as f:
        leidas = list(csv.DictReader(f, delimiter=";"))
    assert len(leidas) == 6 and leidas[1]["evaluar"] == "0" and leidas[1]["curva"] == "1" and leidas[1]["conocido"] == "1" and "|" in leidas[1]["frase"]
