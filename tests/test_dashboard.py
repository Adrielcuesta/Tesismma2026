import json
import os
import re

from scripts import config, dashboard_generator as dg

AQUI = os.path.dirname(__file__)
EJEMPLO = os.path.join(AQUI, "fixtures", "resultado_ejemplo.json")
SALIDA = os.path.join(AQUI, "salida", "dashboard_ejemplo.html")


def _generar(ruta_json, ruta_html):
    dg.generar_dashboard_html(ruta_json, ruta_html, config.INFO_TESIS)
    with open(ruta_html, encoding="utf-8") as f:
        return f.read()


def _tarjeta(html, id_):
    """HTML de una tarjeta o línea de riesgo: desde su id hasta la siguiente tarjeta o sección."""
    t = re.search(rf'id="{id_}">.*?(?=<details class="risk-|<div class="risk-section"|<p class="pie-tecnico")', html, re.S).group(0)
    return t[t.index('<div class="risk-detail">'):]


def test_dashboard_de_ejemplo_modo_verificacion():
    """Genera tests/salida/dashboard_ejemplo.html (ignorado por git) para revisarlo en el navegador."""
    html = _generar(EJEMPLO, SALIDA)
    # las cuatro secciones, en orden
    posiciones = [html.index(t) for t in ("Resumen ejecutivo", "Registro de riesgos", "Solicitudes al oferente", "Alertas a revisar")]
    assert posiciones == sorted(posiciones)
    # resumen: solo la decisión con color y los conteos (sin top 5)
    assert 'class="decision no-aceptable"' in html and "No aceptable" in html
    assert "Riesgos por nivel" in html and "Riesgos por clase" in html and "Top 5" not in html and 'href="#R' not in html
    # registro dividido por nivel, de mayor a menor, con el color de borde de cada nivel
    posiciones = [html.index(t) for t in ("RIESGOS DE NIVEL ALTO (2)", "RIESGOS DE NIVEL MEDIO (2)", "RIESGOS DE NIVEL BAJO (3)")]
    assert posiciones == sorted(posiciones)
    assert len(re.findall(r'<details class="risk-card alto"', html)) == 2
    assert len(re.findall(r'<details class="risk-card medio"', html)) == 2
    # los de nivel Bajo van como lista compacta: una línea por riesgo (título · clase · responsable · norma y artículo)
    assert len(re.findall(r'<details class="risk-card bajo"', html)) == 0 and len(re.findall(r'<details class="risk-linea"', html)) == 3
    assert 'class="lista-compacta"' in html
    linea = re.search(r'id="R4">\s*<summary>(.*?)</summary>', html, re.S).group(1)
    assert linea.count(" · ") == 3 and "Registro de montaje entregado solo al final" in linea and "badge menor" in linea and "NORM_05 Art. 1.6" in linea
    assert "details.risk-card.alto{border-left-color:#e74c3c;}" in html and "details.risk-card.medio{border-left-color:#f39c12;}" in html
    # dentro de la sección, por impacto (R1: 5, R2: 4)
    assert html.index('id="R1"') < html.index('id="R2"')
    # la tarjeta cerrada muestra título, clase con color y responsable; la categoría RBS va en el detalle
    cerrada = re.search(r'id="R1">\s*<summary>(.*?)</summary>', html, re.S).group(1)
    assert "Izaje crítico sin plan aprobado" in cerrada and 'badge critico' in cerrada and "Gerencia de Seguridad Operacional y Salud Ocupacional" in cerrada
    assert "RBS" not in cerrada
    assert len(re.findall(r'<span class="badge critico">Crítico</span>', html)) >= 1
    assert "Aclaraciones menores: RBS-1" in html
    # detalle, en este orden y nada más
    detalle = _tarjeta(html, "R1")
    orden = ["La oferta dice", "La norma exige", "Ver artículo", "Qué se pide al oferente", "Fuente:", "Marcas"]
    posiciones = [detalle.find(t) for t in orden[:5]]
    assert -1 not in posiciones and posiciones == sorted(posiciones) and "Marcas del sistema" not in detalle   # sin marcas, no se muestra la línea
    assert "Presentar el plan de izaje aprobado antes de la maniobra." in detalle and "Verificación previa." in detalle
    assert "Clase:</span> Crítico (regla 3.2.b)" in detalle and "4 × 5 =" in detalle and "Estrategia:</span>" in detalle
    assert "NORM_03 Art. 2.1; NORM_03 Art. 2.4" in detalle
    assert '<details class="articulo"><summary>Ver artículo</summary>' in detalle and "Art. 2.4." in detalle   # el texto completo del artículo va plegado
    # se eliminan del detalle la categoría RBS, el umbral, el responsable, el enunciado y la acción de mitigación
    for ausente in ("Categoría RBS", "Umbral", "Acción de mitigación", "Responsable:", "Enunciado", "Dimensión del impacto", "lado-a-lado"):
        assert ausente not in detalle, ausente
    assert "Información faltante" in html
    # la trocha duplicada (Art. 2.3 y Art. 2.16, mismo valor ofertado) es UN solo riesgo, con los dos artículos
    assert html.count("Tolerancia de trocha superior a la admitida") == 2 and "Variación de trocha superior a la admitida" not in html
    trocha = _tarjeta(html, "R7")
    assert "NORM_01 Art. 2.3; NORM_01 Art. 2.16" in trocha
    dice = trocha[trocha.index("La oferta dice"):trocha.index("La norma exige")]
    assert dice.count('class="cita-oferta"') == 2 and "±3 mm" in dice   # solo las oraciones que contienen el valor, como máximo 2
    assert trocha.count("Ver artículo") == 2 and "Ofrecer una tolerancia de trocha no mayor que ±2 mm." in trocha
    # solicitudes: una fila por riesgo, con una línea por brecha del grupo
    assert html.count("<tr><td>") == 7 and "NORM_03 Art. 2.1: Presentar el plan de izaje" in html
    # alertas con su leyenda
    assert "Dudas internas del evaluador; no se envían al oferente." in html and "tensión disponible" in html
    # pie con modelo, fecha, huella y cantidad de verificaciones y clasificaciones
    assert "qwen3:8b" in html and "2026-11-08 10:30" in html and "a3f9c2e17b4d" in html and "Verificaciones: 48" in html and "Clasificaciones: 9" in html
    # resumen del informe: comentario general y acciones antes de la adjudicación, sin "suficiencia de la evidencia"
    assert "Resumen del informe" in html and "Comentario general" in html and "La oferta resulta No aceptable" in html
    assert html.index('class="decision') < html.index("Resumen del informe") < html.index("Registro de riesgos")
    assert ("<li>Gerencia de Seguridad Operacional y Salud Ocupacional: Izaje crítico sin plan aprobado (NORM_03 Art. 2.1; NORM_03 Art. 2.4)</li>"
            in html)
    assert "<li>Gerencia de Infraestructura y Vías: Cantidad de apoyos inferior a la exigida (NORM_01 Art. 4.2)</li>" in html
    assert html.count("Antes de la adjudicación</li>") == 0 and "Solicitudes con plazo «Antes de la firma del contrato»: 4." in html
    # acciones antes de la adjudicación: una línea por riesgo agrupado (la trocha, una sola vez, con sus dos artículos)
    assert html.count("Tolerancia de trocha superior a la admitida (NORM_01 Art. 2.3; NORM_01 Art. 2.16)</li>") == 1
    assert html.index("Izaje crítico sin plan aprobado (NORM_03") < html.index("Cantidad de apoyos inferior a la exigida (NORM_01")   # por clase
    assert "uficiencia" not in html and "Comentario general: modelo" in html
    # diseño: una sola familia en una variable CSS, sin fuentes descargadas ni emojis, etiquetas rectangulares
    assert re.search(r'--fuente:"Avenir LT 35 Light","Avenir LT Std","Avenir","Avenir Next","Segoe UI","Helvetica Neue",Arial,sans-serif;', html)
    assert html.count("font-family") == 1 and "font-family:var(--fuente)" in html and "@import" not in html and "fonts.googleapis" not in html
    assert not re.search("[🀀-🿿☀-➿⬀-⯿️]", html)
    assert ".badge{display:inline-block;border:1px solid;border-radius:2px;" in html and "border-radius:10px" not in html
    assert "text-transform:uppercase" in html and "font-weight:600" not in html
    # el registro técnico no se muestra y no hay recursos externos
    assert "registro_tecnico" not in html
    assert "<script src" not in html and "<link " not in html


def _brecha_minima(**campos):
    base = {"id": "b", "norma": "NORM_01", "articulo": "1.1", "texto_articulo": "Art. 1.1. X", "marcas": [],
            "oraciones_texto": {"O1": "Primera oración.", "O2": "El tablero se instala a 12 m del borde.", "O3": "Tercera oración con 12 m también.",
                                "O4": "Cuarta con 12 m otra vez."},
            "clasificacion": {"valor_ofertado": "12 m", "medida_ofrecida": None}}
    base.update(campos)
    return base


def test_la_oferta_dice_solo_oraciones_con_la_medida_o_el_valor_maximo_dos():
    assert dg.la_oferta_dice([_brecha_minima()]) == ["El tablero se instala a 12 m del borde.", "Tercera oración con 12 m también."]
    con_medida = _brecha_minima(clasificacion={"valor_ofertado": None, "medida_ofrecida": "Primera oración"})
    assert dg.la_oferta_dice([con_medida]) == ["Primera oración."]


def test_la_oferta_dice_sin_coincidencias_muestra_la_primera_oracion_citada():
    sin = _brecha_minima(clasificacion={"valor_ofertado": "99 kg", "medida_ofrecida": None})
    assert dg.la_oferta_dice([sin]) == ["Primera oración."]
    antiguo = {"id": "x", "cita": "Texto completo de la cita.", "clasificacion": {}}   # resultado sin oraciones_texto
    assert dg.la_oferta_dice([antiguo]) == ["Texto completo de la cita."]
    assert dg.la_oferta_dice([]) == []


def test_dashboard_sin_rag_muestra_lista_simple_con_leyenda(tmp_path):
    datos = {"nombre_proyecto_analizado": "Oferta de prueba", "registro_brechas": [], "resumen_ejecutivo": None,
             "configuracion_analisis": {"condicion": "sin_rag"},
             "riesgos_identificados_estructurados": [
                 {"descripcion_riesgo": "Plazo de entrega demasiado ajustado para la obra completa de montaje y puesta en marcha",
                  "explicacion_riesgo": "El plazo no deja margen.", "cita_oferta": "Entrega en 30 días."}]}
    ruta = tmp_path / "r.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    html = _generar(str(ruta), str(tmp_path / "d.html"))
    assert "Línea de base sin base de conocimiento: sin clasificación según los lineamientos" in html
    assert "El plazo no deja margen." in html and "Entrega en 30 días." in html and "Plazo de entrega demasiado ajustado" in html
    for seccion in ("Resumen ejecutivo", "Registro de riesgos", "Solicitudes al oferente", "Alertas a revisar"):
        assert seccion not in html


def test_dashboard_modo_lista_con_rag_no_dice_que_es_sin_base(tmp_path):
    datos = {"configuracion_analisis": {"condicion": "rag_seccion"}, "riesgos_identificados_estructurados": []}
    ruta = tmp_path / "r.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    html = _generar(str(ruta), str(tmp_path / "d.html"))
    assert "Línea de base sin base de conocimiento" not in html and "Modo lista con base de conocimiento" in html


def test_dashboard_escapa_el_texto(tmp_path):
    with open(EJEMPLO, encoding="utf-8") as f:
        datos = json.load(f)
    datos["riesgos"][0]["titulo"] = "<script>alert(1)</script>"
    datos["alertas"][0]["motivo"] = "<b>x</b>"
    ruta = tmp_path / "r.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    html = _generar(str(ruta), str(tmp_path / "d.html"))
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html and "<b>x</b>" not in html


def test_resultado_verificacion_sin_riesgos_muestra_las_secciones(tmp_path):
    datos = {"registro_brechas": [], "riesgos": [], "solicitudes": [], "alertas": [],
             "resumen_ejecutivo": {"decision": "Aceptable", "por_nivel": {}, "por_clase": {}}}
    ruta = tmp_path / "r.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    html = _generar(str(ruta), str(tmp_path / "d.html"))
    assert 'class="decision aceptable"' in html and "No hay solicitudes." in html and "No hay alertas." in html


def test_una_seccion_de_nivel_sin_riesgos_no_se_muestra(tmp_path):
    with open(EJEMPLO, encoding="utf-8") as f:
        datos = json.load(f)
    datos["riesgos"] = [r for r in datos["riesgos"] if r["nivel"] != "Medio"]
    ruta = tmp_path / "r.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    html = _generar(str(ruta), str(tmp_path / "d.html"))
    assert "RIESGOS DE NIVEL ALTO" in html and "RIESGOS DE NIVEL BAJO" in html and "RIESGOS DE NIVEL MEDIO" not in html
