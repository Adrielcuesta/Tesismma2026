import json
import os
import shutil

import fitz
import pytest
from docx import Document as DocxDocument

from scripts import config, document_utils, lineamientos, vector_db_manager

LINEAS = [
    "CAPÍTULO 1. Disposiciones generales",
    "Art. 1.1. OBJETO",
    "Texto del objeto inventado.",
    "CAPÍTULO 2. Procedimiento",
    "Art. 2.1. PRIMER PASO",
    "Texto del primer paso inventado (ver Art. 2.2. del mismo capítulo).",
    "(Art. 2.7) referencia dentro del texto.",
    "Art. 2.2. SEGUNDO PASO",
    "Texto del segundo paso inventado.",
    "CAPÍTULO 3. Cierre",
    "Art. 3.1. FINAL",
    "Texto final inventado.",
]
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "criterios_empresa.json")
with open(FIXTURE, encoding="utf-8") as _f:
    CRITERIOS = {**json.load(_f), "texto_para_el_modelo": {"articulo_origen": "x", "capitulos": [2], "articulos": ["3.1"]}}


def _docx(ruta, lineas):
    d = DocxDocument()
    for l in lineas:
        d.add_paragraph(l)
    d.save(ruta)


def _carpeta(tmp_path, criterios=CRITERIOS, lineas=LINEAS):
    _docx(tmp_path / "NORM_07_criterios.docx", lineas)
    (tmp_path / "criterios_empresa.json").write_text(json.dumps(criterios), encoding="utf-8")
    return str(tmp_path)


def test_extrae_capitulo_y_articulo_pedidos(tmp_path):
    r = lineamientos.cargar_lineamientos(_carpeta(tmp_path))
    t = r["texto_para_el_modelo"]
    assert "Texto del primer paso inventado" in t and "Texto del segundo paso inventado." in t  # capítulo 2 completo
    assert "Texto final inventado." in t                                                         # artículo 3.1
    assert "Texto del objeto inventado." not in t                                                # capítulo 1 no pedido
    assert r["criterios"] == CRITERIOS and len(r["huella"]) == 64


def test_el_fixture_real_carga_sin_error(tmp_path):
    _docx(tmp_path / "NORM_07_criterios.docx", [l for l in LINEAS] + ["CAPÍTULO 4. Otro", "Art. 4.3. IMPACTO", "Texto de impacto inventado."])
    shutil.copy(FIXTURE, tmp_path / "criterios_empresa.json")
    r = lineamientos.cargar_lineamientos(str(tmp_path))
    assert "Texto de impacto inventado." in r["texto_para_el_modelo"] and "Texto del objeto inventado." not in r["texto_para_el_modelo"]


def test_referencia_en_el_texto_no_corta_el_articulo():
    a = lineamientos.extraer_articulo("\n".join(LINEAS), "2.1")
    assert "(Art. 2.7) referencia" in a and "ver Art. 2.2." in a and "segundo paso" not in a


def test_extraer_articulo_se_corta_en_el_siguiente():
    texto = "\n".join(LINEAS)
    a = lineamientos.extraer_articulo(texto, "2.1")
    assert "primer paso" in a and "segundo paso" not in a
    assert "Disposiciones" not in lineamientos.extraer_capitulo(texto, 2)


def test_prefiere_docx_sobre_pdf(tmp_path):
    carpeta = _carpeta(tmp_path)
    pdf = fitz.open()
    pdf.new_page().insert_text((72, 72), "CAPITULO 2. Distinto\nTexto del pdf")
    pdf.save(tmp_path / "NORM_07_criterios.pdf")
    t = lineamientos.cargar_lineamientos(carpeta)["texto_para_el_modelo"]
    assert "primer paso inventado" in t and "Texto del pdf" not in t


def test_huella_cambia_con_el_json(tmp_path):
    h1 = lineamientos.cargar_lineamientos(_carpeta(tmp_path))["huella"]
    h2 = lineamientos.cargar_lineamientos(_carpeta(tmp_path, {**CRITERIOS, "umbral_brecha_relativa": {"valor": 0.10}}))["huella"]
    assert h1 != h2


def test_json_incompleto_da_error(tmp_path):
    incompleto = {k: v for k, v in CRITERIOS.items() if k != "umbral_brecha_relativa"}
    with pytest.raises(lineamientos.LineamientosError, match="umbral_brecha_relativa"):
        lineamientos.cargar_lineamientos(_carpeta(tmp_path, incompleto))
    with pytest.raises(lineamientos.LineamientosError, match="capitulos"):
        lineamientos.cargar_lineamientos(_carpeta(tmp_path, {**CRITERIOS, "texto_para_el_modelo": {"articulos": []}}))


def test_json_sin_contenido_minimo_de_la_oferta_da_error(tmp_path):
    sin_bloque = {k: v for k, v in CRITERIOS.items() if k != "contenido_minimo_oferta"}
    with pytest.raises(lineamientos.LineamientosError, match="contenido_minimo_oferta"):
        lineamientos.cargar_lineamientos(_carpeta(tmp_path, sin_bloque))


def test_documento_de_criterios_ausente_da_error(tmp_path):
    carpeta = _carpeta(tmp_path, {**CRITERIOS, "documento_criterios": "NORM_09"})
    with pytest.raises(lineamientos.LineamientosError, match="NORM_09"):
        lineamientos.cargar_lineamientos(carpeta)


def test_falta_el_json_da_error(tmp_path):
    _docx(tmp_path / "NORM_07_criterios.docx", LINEAS)
    with pytest.raises(lineamientos.LineamientosError, match="criterios_empresa.json"):
        lineamientos.cargar_lineamientos(str(tmp_path))


def test_capitulo_inexistente_da_error(tmp_path):
    carpeta = _carpeta(tmp_path, {**CRITERIOS, "texto_para_el_modelo": {"capitulos": [9], "articulos": []}})
    with pytest.raises(lineamientos.LineamientosError, match="capítulo 9"):
        lineamientos.cargar_lineamientos(carpeta)


def test_el_indexado_ignora_lineamientos(tmp_path, monkeypatch):
    base = tmp_path / "BaseConocimiento"
    (base / "Normativa").mkdir(parents=True)
    (base / "Lineamientos").mkdir()
    _docx(base / "Normativa" / "NORM_01_x.docx", ["Art. 1.1. Uno", "Texto de la norma inventada, suficientemente largo."])
    _docx(base / "Lineamientos" / "NORM_07_criterios.docx", LINEAS)
    monkeypatch.setattr(config, "DIRECTORIO_BASE_CONOCIMIENTO", str(base))
    monkeypatch.setattr(config, "DIRECTORIO_NORMATIVA", str(base / "Normativa"))

    chunks = document_utils.cargar_kb_por_articulos(config.DIRECTORIO_NORMATIVA)
    assert chunks and {c.metadata["norma"] for c in chunks} == {"NORM_01"}
    firma = vector_db_manager._firma_indexado(config.DIRECTORIO_NORMATIVA, 1000, 100, None, por_articulos=True)
    assert [a[0] for a in firma["archivos"]] == ["NORM_01_x.docx"]
    # la carpeta padre no tiene documentos propios: leerla directamente no indexa nada
    assert document_utils.cargar_kb_por_articulos(config.DIRECTORIO_BASE_CONOCIMIENTO) == []


def test_rutas_de_config_separadas():
    assert os.path.dirname(config.DIRECTORIO_NORMATIVA) == os.path.dirname(config.DIRECTORIO_LINEAMIENTOS) == config.DIRECTORIO_BASE_CONOCIMIENTO
    assert config.DIRECTORIO_NORMATIVA != config.DIRECTORIO_LINEAMIENTOS
    assert not hasattr(config, "NORMA_COMPLETA")
