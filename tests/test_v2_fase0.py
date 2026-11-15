"""Propuestas A y B de la v2 (evaluacion/v2_listar_no_verificables.py y evaluacion/v2_medir_ab.py) con datos sintéticos."""
import pytest
from langchain_core.documents import Document

from evaluacion import v2_listar_no_verificables as L
from evaluacion import v2_medir_ab as M

TITULOS_GENERICOS = ["OBJETO Y CARÁCTER", "Alcance funcional", "Alcance físico y funcional", "Campo de aplicación", "Ámbito de aplicación", "Orden de prevalencia",
                     "Objeto y alcance", "Alcance", "Prevalencia documental", "Art. 1.2. Alcance general", "  alcance técnico. "]
TITULOS_REQUISITO = ["Objeto y alcance del SAT", "Objeto de la tabla de control S-01", "Identificación de capacidad nominal", "Distancia libre en playas de maniobra",
                     "Gálibos en fosas, torno bajo piso y equipos de levante", "Prohibiciones sobre superficies mecanizadas y componentes de precisión", "Balancines, puntos de anclaje",
                     "Alcance de los ensayos de recepción en obra", "Prevalencia de la placa del fabricante sobre el catálogo", ""]


def test_el_criterio_es_por_titulo_entero_y_no_por_palabra_inicial():
    assert all(L.es_no_verificable(t) for t in TITULOS_GENERICOS)
    assert not any(L.es_no_verificable(t) for t in TITULOS_REQUISITO)


def test_los_dudosos_se_listan_pero_no_se_excluyen():
    for t in ["Referencias técnicas y marco de seguridad", "Documentos de referencia", "Definiciones", "Generalidades"]:
        assert L.es_dudoso(t) and not L.es_no_verificable(t)
    assert not L.es_dudoso("Alcance funcional") and not L.es_dudoso("Gálibos en fosas")


def test_el_criterio_no_mira_el_numero_del_articulo():
    chunks = [Document(page_content="Art. 1.10. Requisito de puesta a tierra\nTexto.", metadata={"norma": "NORM_02", "articulo": "1.10", "titulo": "Requisito de puesta a tierra", "parte": 1}),
              Document(page_content="Art. 1.2. Alcance funcional\nTexto.", metadata={"norma": "NORM_02", "articulo": "1.2", "titulo": "Alcance funcional", "parte": 1}),
              Document(page_content="Art. 1.2. Alcance funcional\nParte 2.", metadata={"norma": "NORM_02", "articulo": "1.2", "titulo": "Alcance funcional", "parte": 2}),
              Document(page_content="Preámbulo\nTexto", metadata={"norma": "NORM_02", "articulo": "preambulo", "titulo": "Preámbulo", "parte": 1}),
              Document(page_content="Art. 3.4. Campo de aplicación\nTexto.", metadata={"norma": "NORM_05", "articulo": "3.4", "titulo": "", "parte": 1})]
    articulos = L.articulos_de_chunks(chunks)
    assert [(a["norma"], a["articulo"]) for a in articulos] == [("NORM_02", "1.10"), ("NORM_02", "1.2"), ("NORM_05", "3.4")]       # sin partes repetidas ni preámbulo
    excluidos, dudosos = L.clasificar(articulos)
    assert [(a["norma"], a["articulo"]) for a in excluidos] == [("NORM_02", "1.2"), ("NORM_05", "3.4")]                          # un 3.4 sin título en los metadatos usa la primera línea
    assert dudosos == []


def _trampa(id_, norma, articulo, equivalentes=""):
    return {"id": id_, "oferta": "P9", "seccion": "1 X", "fragmento_trampa": "frase " + id_, "norma": norma, "articulo": articulo, "articulos_equivalentes": equivalentes,
            "clase": "Mayor", "responsable": "G", "nivel": "Medio"}


def test_cruce_con_el_ground_truth_detecta_trampas_en_articulos_excluidos_y_equivalentes():
    articulos = [{"norma": "NORM_01", "articulo": "1.1", "titulo": "Objeto y carácter"}, {"norma": "NORM_02", "articulo": "1.10", "titulo": "Requisito de tierra"},
                 {"norma": "NORM_05", "articulo": "1.6", "titulo": "Alcance funcional"}]
    excluidos, _ = L.clasificar(articulos)
    gt = [_trampa("T1", "NORM_02", "1.10"), _trampa("T2", "NORM_04", "3.1", "NORM_05 1.6"), _trampa("T3", "NORM_01", "4.2")]
    assert L.cruce_con_ground_truth(excluidos, [gt[0], gt[2]]) == []
    (c,) = L.cruce_con_ground_truth(excluidos, gt)
    assert (c["id"], c["norma"], c["articulo"]) == ("T2", "NORM_05", "1.6")                       # el equivalente cae en un artículo excluido
    uno_x = L.articulos_1x_de_trampas(articulos, gt)
    assert [(t["id"], t["conservado"]) for t in uno_x] == [("T1", True)] and "Requisito de tierra" == uno_x[0]["titulo"]
    texto = L.informe_md(excluidos, [], [c], uno_x, ["P9"])
    assert "ATENCIÓN" in texto and "T2" in texto


def test_postproceso_sobre_las_brechas_usa_el_titulo_del_texto_del_articulo():
    assert L.titulo_de_brecha({"texto_articulo": "Art. 1.2. Alcance funcional\nQuedan comprendidos..."}) == "Alcance funcional"
    assert L.brecha_excluida({"texto_articulo": "Art. 1.2. Alcance funcional\nTexto"}) and not L.brecha_excluida({"texto_articulo": "Art. 1.10. Requisito de tierra\nTexto"})
    assert not L.brecha_excluida({})


# --- medición de A y B ---

def _brecha(seccion, norma, articulo, cita, titulo, fuente="DESVIO", etapa=None, **extra):
    return {"id": f"{seccion}|{norma}|{articulo}", "seccion": seccion, "seccion_oferta": seccion, "norma": norma, "articulo": articulo, "cita": cita, "titulo": "t",
            "texto_articulo": f"Art. {articulo}. {titulo}\ncuerpo", "fuente": fuente, "clase": "Mayor", "nivel": "Medio", "responsable": "G", "clasificacion": {"etapa_requisito": etapa}, **extra}


def _entrada(con_trampa_posterior=False):
    brechas = [
        _brecha("S1", "NORM_01", "4.2", "Frase T1 de la oferta.", "Requisito uno"),                                            # trampa T1
        _brecha("S1", "NORM_02", "5.1", "Frase T2 de la oferta.", "Requisito dos", etapa="POSTERIOR" if con_trampa_posterior else None),   # trampa T2
        _brecha("S2", "NORM_01", "1.1", "Otra frase alcance.", "Objeto y carácter"),                                         # extra NO_VALIDA, lo quita A
        _brecha("S2", "NORM_03", "6.1", "Otra frase etapa.", "Requisito tres", fuente="INFORMACION_FALTANTE", etapa="POSTERIOR"),   # extra NO_VALIDA, lo quita B
        _brecha("S3", "NORM_03", "7.7", "Una frase buena.", "Requisito cuatro"),                                            # extra VALIDA
        _brecha("S3", "NORM_04", "8.8", "Una frase mala.", "Requisito cinco"),                                              # extra NO_VALIDA que ninguna regla quita
    ]
    revision = [{"seccion": "S2", "norma": "NORM_01", "articulo": "1.1", "cita": "Otra frase alcance.", "valido": "no"},
                {"seccion": "S2", "norma": "NORM_03", "articulo": "6.1", "cita": "Otra frase etapa.", "valido": "no"},
                {"seccion": "S3", "norma": "NORM_03", "articulo": "7.7", "cita": "Una frase buena.", "valido": "sí"},
                {"seccion": "S3", "norma": "NORM_04", "articulo": "8.8", "cita": "Una frase mala.", "valido": "no"}]
    gt = [_trampa("T1", "NORM_01", "4.2"), _trampa("T2", "NORM_02", "5.1")]
    gt[0]["fragmento_trampa"], gt[1]["fragmento_trampa"] = "Frase T1 de la oferta", "Frase T2 de la oferta"
    return {"oferta": "P9", "resultado": {"registro_brechas": brechas, "resumen_ejecutivo": {}, "riesgos": []}, "gt": gt, "espejos": [], "revision": revision}


def test_a_y_b_suben_la_precision_sin_perder_trampas():
    res = M.comparar([_entrada()])
    assert (res["base"]["encontradas"], res["base"]["brechas"], res["base"]["extras"]) == (2, 6, 4)
    assert res["base"]["precision"] == pytest.approx(3 / 6)                                   # (2 trampas + 1 extra válido) / 6 brechas
    assert res["A"]["precision"] == pytest.approx(3 / 5) and res["B"]["precision"] == pytest.approx(3 / 5)
    assert res["A+B"]["precision"] == pytest.approx(3 / 4) and res["A+B"]["brechas"] == 4
    assert res["A+B"]["extras_eliminados"] == {"validos": 0, "no_validos": 2, "sin_etiqueta": 0}
    d = res["decision"]
    assert d["sube_puntos"] == pytest.approx(0.25) and d["trampas_perdidas"] == [] and d["adopta"] is True


def test_si_b_descarta_la_brecha_de_una_trampa_no_se_adopta_aunque_suba_la_precision():
    res = M.comparar([_entrada(con_trampa_posterior=True)])
    assert res["B"]["trampas_perdidas_vs_base"] == ["T2"] and res["A+B"]["encontradas"] == 1
    assert res["decision"]["trampas_perdidas"] == ["T2"] and res["decision"]["adopta"] is False


def test_sin_etiquetas_la_precision_es_nd_con_cotas_y_la_decision_no_es_concluyente():
    e = _entrada()
    e["revision"] = None
    res = M.comparar([e])
    assert res["base"]["precision"] is None and res["base"]["sin_etiqueta"] == 4
    assert res["base"]["cota_inferior"] == pytest.approx(2 / 6) and res["base"]["cota_superior"] == pytest.approx(6 / 6)
    assert res["decision"]["adopta"] is None and res["decision"]["concluyente"] is False
    assert "no concluyente" in M.informe_md(res, ["P9"], M.cobertura_b(e["resultado"]), [])


def test_filtrar_no_modifica_el_original_y_respeta_las_descartadas_por_calculo():
    e = _entrada()
    e["resultado"]["registro_brechas"].append(_brecha("S4", "NORM_01", "1.1", "x", "Objeto", estado="descartada por cálculo"))
    original = len(e["resultado"]["registro_brechas"])
    filtrado = M.filtrar(e["resultado"], True, True)
    assert len(e["resultado"]["registro_brechas"]) == original and len(filtrado["registro_brechas"]) == original - 2
    assert any(b.get("estado") == "descartada por cálculo" for b in filtrado["registro_brechas"])


def test_cobertura_de_b_cuenta_la_etapa_informada_por_fuente():
    c = M.cobertura_b(_entrada()["resultado"])
    assert c["DESVIO"] == (5, 0, 0) and c["INFORMACION_FALTANTE"] == (1, 1, 1)               # en las brechas de desvío el campo viene vacío


def test_el_informe_trae_los_criterios_de_decision_y_el_cli_no_pisa_archivos(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(M, "_cargar_entradas", lambda *a, **k: [_entrada()])
    salida = tmp_path / "ab.md"
    res = M.main(["--config", "x", "--salida", str(salida)])
    assert res["decision"]["adopta"] is True
    texto = salida.read_text(encoding="utf-8")
    assert "Criterio de decisión" in texto and "se adopta" in texto and "Objeto y carácter" in texto
    salida.write_text("previo", encoding="utf-8")
    M.main(["--config", "x", "--salida", str(salida)])
    assert salida.read_text(encoding="utf-8") == "previo" and "ya existe" in capsys.readouterr().err
