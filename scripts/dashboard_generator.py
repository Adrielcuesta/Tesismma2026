# scripts/dashboard_generator.py
"""Dashboard HTML (un solo archivo, sin dependencias externas ni fuentes descargadas). Dos tipos de resultado:
- modo verificación (JSON con riesgos clasificados): resumen ejecutivo, registro de riesgos, solicitudes al oferente y alertas;
- modo lista (línea de base sin clasificación): lista simple con título, descripción y cita de la oferta."""
import json
import os
import logging
import datetime
import unicodedata
from html import escape
import base64

logger = logging.getLogger(__name__)
CURRENT_YEAR = datetime.datetime.now().year

LEYENDA_SIN_RAG = "Línea de base sin base de conocimiento: sin clasificación según los lineamientos"
LEYENDA_LISTA_CON_RAG = "Modo lista con base de conocimiento: sin clasificación según los lineamientos"
LEYENDA_ALERTAS = "Dudas internas del evaluador; no se envían al oferente."
CLASES = ("Crítico", "Mayor", "Menor")
CLASE_CSS = {"Crítico": "critico", "Mayor": "mayor", "Menor": "menor"}
NIVEL_CSS = {"Alto": "alto", "Medio": "medio", "Bajo": "bajo"}
DECISION_CSS = {"No aceptable": "no-aceptable", "Aceptable con condiciones": "condiciones", "Aceptable": "aceptable"}
FUENTE_TEXTO = {"DESVIO": "Desvío", "EXCEPCION_NO_ACREDITADA": "Excepción no acreditada", "INFORMACION_FALTANTE": "Información faltante"}
# Secciones del registro, de mayor a menor nivel
SECCIONES_NIVEL = (("Alto", "RIESGOS DE NIVEL ALTO"), ("Medio", "RIESGOS DE NIVEL MEDIO"), ("Bajo", "RIESGOS DE NIVEL BAJO"))
# Plazos de las solicitudes que el resumen del informe distingue
PLAZO_ADJUDICACION = "Antes de la adjudicación"
PLAZO_FIRMA = "Antes de la firma del contrato"

CSS = """
        :root{--fuente:"Avenir LT 35 Light","Avenir LT Std","Avenir","Avenir Next","Segoe UI","Helvetica Neue",Arial,sans-serif;}
        body{font-family:var(--fuente);font-weight:400;margin:0;padding:0;background-color:#f0f2f5;color:#333;}
        .page-wrapper{width:100%;display:flex;flex-direction:column;align-items:center;padding:20px;box-sizing:border-box;}
        .main-dashboard-container{background-color:#fff;padding:30px 40px;border-radius:12px;box-shadow:0 6px 20px rgba(0,0,0,.1);width:100%;max-width:1200px;text-align:left;margin-bottom:30px;box-sizing:border-box;}
        .abstract-banner-container{width:100%;height:100px;margin-bottom:25px;background-image:url("__BANNER__");background-size:cover;background-position:center;border-radius:6px;}
        .header-content{text-align:center;margin-bottom:30px;}
        .title-with-logo{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:8px;}
        .title-with-logo img.logo-inline{height:37px;width:auto;}
        h1{color:#1a2533;font-size:1.7em;margin:0;} h2{color:#2c3e50;font-size:1.3em;margin-top:8px;font-weight:500;} h3{color:#4a5568;font-size:1.1em;margin:8px 0;font-weight:400;}
        .project-analysis-title{text-align:center;font-size:1.6em;color:#1a2533;margin-top:0;margin-bottom:30px;padding-bottom:15px;border-bottom:2px solid #e0e0e0;}
        .risk-section{margin-bottom:35px;}
        .risk-section-title{font-size:1.15em;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#2c3e50;border-bottom:1px solid #e0e0e0;padding-bottom:10px;margin-bottom:20px;}
        .subtitulo{font-size:.85em;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#2c3e50;margin:14px 0 6px;}
        .detail-label{font-weight:400;color:#6b7280;}
        .leyenda{border-radius:8px;padding:12px 18px;margin-bottom:20px;font-size:.95em;background-color:#fff8e1;border:1px solid #f39c12;color:#7a5c00;}
        .marca{display:inline-block;background-color:#fff6e0;border:1px solid #f0c36d;color:#7a5c00;border-radius:2px;padding:0 6px;font-size:.78em;margin-right:4px;}
        .badge{display:inline-block;border:1px solid;border-radius:2px;padding:1px 7px;font-size:.78em;white-space:nowrap;}
        .badge.critico,.badge.alto{background:#fdecea;border-color:#e74c3c;color:#9b2c20;}
        .badge.mayor{background:#fdf0e3;border-color:#e67e22;color:#8a4a0f;}
        .badge.menor{background:#eef0f1;border-color:#95a5a6;color:#55606a;}
        .badge.medio{background:#fff6e0;border-color:#f39c12;color:#8a5a00;}
        .badge.bajo{background:#e8f8ef;border-color:#2ecc71;color:#1d7a45;}
        .decision{font-size:1.15em;color:#333;margin:0 0 18px;}
        .decision .valor{color:#7f8c8d;} .decision.no-aceptable .valor{color:#c0392b;} .decision.condiciones .valor{color:#b9770e;} .decision.aceptable .valor{color:#1e8449;}
        .conteos{display:flex;flex-wrap:wrap;gap:30px;margin-bottom:18px;} .conteos div{font-size:.95em;} .conteos .badge{margin-left:4px;margin-right:10px;}
        .informe-general{background-color:#f5f8fb;border:1px solid #d6e0ea;border-radius:2px;padding:16px 20px;font-size:.95em;line-height:1.55;}
        .informe-general p{margin:6px 0;} .informe-general ul{margin:6px 0;padding-left:22px;}
        .dashboard-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:20px;align-items:start;}
        details.risk-card{background-color:#fdfdfd;border:1px solid #e9ecef;border-radius:8px;padding:0;box-shadow:0 2px 8px rgba(0,0,0,.06);border-left-width:5px;border-left-style:solid;}
        details.risk-card.alto{border-left-color:#e74c3c;} details.risk-card.medio{border-left-color:#f39c12;}
        details.risk-card[open]{grid-column:1 / -1;}
        details.risk-card summary{cursor:pointer;padding:16px 20px;list-style:none;} details.risk-card summary::-webkit-details-marker{display:none;}
        details.risk-card summary:hover{background:#f7f9fb;}
        .card-title{margin:0 0 10px;color:#34495e;font-size:1.05em;line-height:1.4;display:block;}
        .card-meta{font-size:.85em;color:#555;display:flex;gap:10px;align-items:center;flex-wrap:wrap;}
        .risk-detail{padding:4px 20px 18px;border-top:1px dashed #ccc;font-size:.92em;line-height:1.55;}
        .risk-detail p{margin:6px 0;}
        .lista-compacta{border:1px solid #e9ecef;border-radius:8px;overflow:hidden;}
        details.risk-linea{border-bottom:1px solid #e9ecef;border-left:5px solid #2ecc71;background:#fdfdfd;}
        details.risk-linea summary{cursor:pointer;padding:10px 16px;list-style:none;font-size:.92em;} details.risk-linea summary::-webkit-details-marker{display:none;}
        details.risk-linea summary:hover{background:#f7f9fb;}
        .articulo{margin:2px 0 8px;} .articulo summary{cursor:pointer;color:#2c3e50;font-size:.9em;}
        .articulo .texto{background:#f5f8fb;border:1px solid #d6e0ea;border-radius:2px;padding:10px 14px;white-space:pre-wrap;max-height:170px;overflow:auto;font-size:.9em;}
        .cita-oferta{background:#f5f8fb;border:1px solid #d6e0ea;border-radius:2px;padding:8px 14px;margin:4px 0;}
        .tabla{border-collapse:collapse;width:100%;font-size:.88em;}
        .tabla th{text-align:left;background:#f5f8fb;border-bottom:2px solid #d6e0ea;padding:8px 10px;font-size:.85em;font-weight:700;text-transform:uppercase;}
        .tabla td{border-bottom:1px solid #e9ecef;padding:8px 10px;vertical-align:top;} .tabla td.pedido{white-space:pre-wrap;}
        .tabla-wrap{overflow-x:auto;}
        .alerta{border:1px solid #e9ecef;border-left:5px solid #f39c12;border-radius:8px;padding:12px 18px;margin-bottom:12px;background:#fffdf7;font-size:.92em;line-height:1.55;}
        .alerta p{margin:4px 0;}
        .lista-simple .item{border:1px solid #e9ecef;border-left:5px solid #95a5a6;border-radius:8px;padding:12px 18px;margin-bottom:12px;font-size:.93em;line-height:1.55;}
        .lista-simple .item h4{margin:0 0 6px;color:#34495e;font-size:1.02em;font-weight:400;} .lista-simple .item p{margin:4px 0;}
        .pie-tecnico{margin-top:35px;padding-top:12px;border-top:1px solid #e0e0e0;font-size:.82em;color:#6c757d;text-align:center;}
        .vacio{font-style:italic;color:#6c757d;}
        .dashboard-page-footer{width:100%;text-align:center;padding:25px 0;font-size:.9em;color:#6c757d;margin-top:30px;border-top:1px solid #d0d0d0;}
        @media (max-width:700px){.main-dashboard-container{padding:20px;}}
"""


def image_to_base64(image_filename_in_static_images):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    image_path = os.path.join(project_root, "static", "images", image_filename_in_static_images)
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        ext = image_filename_in_static_images.split('.')[-1].lower()
        mime_type_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "svg": "image/svg+xml", "gif": "image/gif"}
        mime_type = mime_type_map.get(ext, f"image/{ext}")
        return f"data:{mime_type};base64,{encoded_string}"
    except FileNotFoundError:
        logger.error(f"¡IMAGEN NO ENCONTRADA! Verifica esta ruta: {image_path}")
        return ""
    except Exception as e:
        logger.error(f"Error codificando imagen {image_path} a Base64: {e}")
        return ""


def _e(valor, vacio="N/D"):
    return escape(str(valor)) if valor not in (None, "") else vacio


def _badge(valor, mapa):
    return f'<span class="badge {mapa.get(valor, "menor")}">{_e(valor)}</span>'


def _badge_cuenta(clave, cuenta, mapa):
    return f'<span class="badge {mapa.get(clave, "menor")}">{cuenta}</span>'


def _citas_texto(citas):
    return "; ".join(f"{c.get('norma', '?')} Art. {c.get('articulo', '?')}" for c in citas or []) or "—"


# --- 1. Resumen ejecutivo ---

def acciones_previas(solicitudes, riesgos, orden_clases):
    """Líneas '<responsable>: <título del riesgo> (<norma y artículo>)' de las solicitudes con plazo previo a la adjudicación,
    ordenadas por clase, y cantidad de solicitudes con plazo previo a la firma del contrato."""
    titulos = {r.get("id"): r.get("titulo") for r in riesgos}
    rango = {c: i for i, c in enumerate(orden_clases)}
    previas = sorted({s.get("riesgo"): s for s in solicitudes if s.get("plazo") == PLAZO_ADJUDICACION}.values(), key=lambda s: rango.get(s.get("clase"), 99))   # una por riesgo agrupado
    lineas = [f"{s.get('responsable') or 'N/D'}: {titulos.get(s.get('riesgo')) or 'N/D'} ({_citas_texto(s.get('citas'))})" for s in previas]
    return lineas, sum(1 for s in solicitudes if s.get("plazo") == PLAZO_FIRMA)


def seccion_resumen(resumen, riesgos, solicitudes, orden_clases):
    decision = resumen.get("decision", "N/D")
    por_nivel, por_clase = resumen.get("por_nivel", {}), resumen.get("por_clase", {})
    niveles = " ".join(f'<span>{_e(n)}{_badge_cuenta(n, c, NIVEL_CSS)}</span>' for n, c in por_nivel.items())
    clases = " ".join(f'<span>{_e(k)}{_badge_cuenta(k, c, CLASE_CSS)}</span>' for k, c in por_clase.items())
    lineas, firma = acciones_previas(solicitudes, riesgos, orden_clases)
    comentario = resumen.get("comentario_general")
    comentario_html = f'<p class="subtitulo">Comentario general</p><p>{_e(comentario)}</p>' if comentario else ""
    acciones = "".join(f"<li>{escape(l)}</li>" for l in lineas) or '<li class="vacio">No hay acciones previas a la adjudicación.</li>'
    return f'''
    <div class="risk-section" id="resumen">
        <h3 class="risk-section-title">Resumen ejecutivo</h3>
        <div class="decision {DECISION_CSS.get(decision, "otra")}">Decisión de aceptabilidad: <span class="valor">{_e(decision)}</span></div>
        <div class="conteos"><div><span class="detail-label">Riesgos por nivel</span> {niveles}</div><div><span class="detail-label">Riesgos por clase</span> {clases}</div></div>
        <div class="informe-general">
            <p class="subtitulo" style="margin-top:0">Resumen del informe</p>
            {comentario_html}
            <p class="subtitulo">Acciones antes de la adjudicación</p>
            <ul>{acciones}</ul>
            <p>Solicitudes con plazo «{PLAZO_FIRMA}»: {firma}.</p>
        </div>
    </div>'''


# --- 2. Registro de riesgos ---

def _alnum(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "").casefold()) if c.isalnum())


def _oraciones_citadas(componentes):
    """[(clave, texto)] de las oraciones citadas por los componentes, sin repetir. Si la brecha no trae el texto de cada oración
    (resultados anteriores), la cita completa cuenta como una sola."""
    vistas = {}
    for b in componentes:
        if b.get("oraciones_texto"):
            vistas.update({i: t for i, t in b["oraciones_texto"].items() if i not in vistas})
        elif b.get("cita"):
            vistas.setdefault(("cita", b.get("id")), b["cita"])
    return sorted(vistas.items(), key=lambda x: (isinstance(x[0], tuple), len(str(x[0])), str(x[0])))


def la_oferta_dice(componentes):
    """Solo las oraciones citadas que contienen la medida ofrecida o el valor ofertado, como máximo 2; si no hay ninguna, la primera citada."""
    items = _oraciones_citadas(componentes)
    claves = [_alnum(v) for b in componentes for v in ((b.get("clasificacion") or {}).get("medida_ofrecida"), (b.get("clasificacion") or {}).get("valor_ofertado")) if v]
    coinciden = [t for _, t in items if any(k and k in _alnum(t) for k in claves)][:2]
    return coinciden or ([items[0][1]] if items else [])


def _bloque_norma_exige(b):
    c = b.get("clasificacion") or {}
    valor = " ".join(str(x) for x in (c.get("valor_exigido"), c.get("unidad")) if x)
    explicacion = (b.get("verificacion_previa") or {}).get("explicacion")
    texto = ". ".join(x for x in (valor, explicacion) if x)
    return (f'<p><span class="detail-label">{_e(b.get("norma"))} Art. {_e(b.get("articulo"))}:</span> {_e(texto)}</p>'
            f'<details class="articulo"><summary>Ver artículo</summary><div class="texto">{_e(b.get("texto_articulo"))}</div></details>')


def detalle_riesgo(r, brechas_por_id):
    """Detalle del riesgo, en este orden y nada más: la oferta dice, la norma exige, qué se pide, una línea de datos y las marcas."""
    componentes = [brechas_por_id[i] for i in r.get("brechas", []) if i in brechas_por_id]
    dice = "".join(f'<div class="cita-oferta">{_e(t)}</div>' for t in la_oferta_dice(componentes)) or '<p class="vacio">N/D</p>'
    pedidos = list(dict.fromkeys(b.get("solicitud_oferente") for b in componentes if b.get("solicitud_oferente")))
    pide = "".join(f"<p>{escape(p)}</p>" for p in pedidos) or "<p>N/D</p>"
    fuente = FUENTE_TEXTO.get(r.get("fuente"), _e(r.get("fuente")))
    datos = (f'<p><span class="detail-label">Fuente:</span> {escape(fuente)} · <span class="detail-label">Clase:</span> {_e(r.get("clase"))} (regla {_e(r.get("regla"))}) · '
             f'<span class="detail-label">P × I = Nivel:</span> {_e(r.get("probabilidad"))} × {_e(r.get("impacto"))} = {_badge(r.get("nivel"), NIVEL_CSS)} · '
             f'<span class="detail-label">Estrategia:</span> {_e(r.get("estrategia"))} · <span class="detail-label">Norma y artículo:</span> {escape(_citas_texto(r.get("citas")))}</p>')
    marcas = list(dict.fromkeys(m for b in componentes for m in b.get("marcas", [])))
    marcas_html = f'<p><span class="detail-label">Marcas del sistema:</span> {" ".join(f"<span class=marca>{escape(str(m))}</span>" for m in marcas)}</p>' if marcas else ""
    return (f'<div class="risk-detail"><p class="subtitulo">La oferta dice</p>{dice}<p class="subtitulo">La norma exige</p>'
            f'{"".join(_bloque_norma_exige(b) for b in componentes)}<p class="subtitulo">Qué se pide al oferente</p>{pide}{datos}{marcas_html}</div>')


def tarjeta_riesgo(r, brechas_por_id):
    """Tarjeta de los riesgos de nivel Alto y Medio."""
    return f'''
        <details class="risk-card {NIVEL_CSS.get(r.get("nivel"), "medio")}" id="{escape(str(r.get("id", "")))}">
            <summary>
                <span class="card-title">{_e(r.get("titulo"))}</span>
                <span class="card-meta">{_badge(r.get("clase"), CLASE_CSS)} <span><span class="detail-label">Responsable:</span> {_e(r.get("responsable"))}</span></span>
            </summary>
            {detalle_riesgo(r, brechas_por_id)}
        </details>'''


def linea_riesgo(r, brechas_por_id):
    """Riesgos de nivel Bajo: una línea (título · clase · responsable · norma y artículo) que al abrirse muestra el mismo detalle."""
    return f'''
        <details class="risk-linea" id="{escape(str(r.get("id", "")))}">
            <summary>{_e(r.get("titulo"))} · {_badge(r.get("clase"), CLASE_CSS)} · {_e(r.get("responsable"))} · {escape(_citas_texto(r.get("citas")))}</summary>
            {detalle_riesgo(r, brechas_por_id)}
        </details>'''


def seccion_registro(riesgos, brechas, orden_clases):
    if not riesgos:
        return '<div class="risk-section"><h3 class="risk-section-title">Registro de riesgos</h3><p class="vacio">No se identificaron riesgos.</p></div>'
    por_id = {b.get("id"): b for b in brechas}
    rango = {c: i for i, c in enumerate(orden_clases)}
    secciones = []
    for nivel, titulo in SECCIONES_NIVEL:
        items = sorted((r for r in riesgos if r.get("nivel") == nivel), key=lambda x: (-(x.get("impacto") or 0), rango.get(x.get("clase"), 99)))
        if not items:   # una sección sin riesgos no se muestra
            continue
        if nivel == "Bajo":
            cuerpo = f'<div class="lista-compacta">{"".join(linea_riesgo(r, por_id) for r in items)}</div>'
        else:
            cuerpo = f'<div class="dashboard-grid">{"".join(tarjeta_riesgo(r, por_id) for r in items)}</div>'
        secciones.append(f'<div class="risk-section"><h3 class="risk-section-title">{titulo} ({len(items)})</h3>{cuerpo}</div>')
    return f'<div class="risk-section"><h3 class="risk-section-title">Registro de riesgos ({len(riesgos)})</h3></div>{"".join(secciones)}'


# --- 3. Solicitudes al oferente ---

def seccion_solicitudes(solicitudes):
    if not solicitudes:
        return '<div class="risk-section"><h3 class="risk-section-title">Solicitudes al oferente</h3><p class="vacio">No hay solicitudes.</p></div>'
    filas = "".join(
        f'<tr><td>{_e(s.get("numero"))}</td><td>{_e(s.get("tipo"))}</td><td>{escape(_citas_texto(s.get("citas")))}</td><td>{_e(s.get("cita_oferta"))}</td>'
        f'<td class="pedido">{_e(s.get("pedido"))}</td><td>{_badge(s.get("clase"), CLASE_CSS)}</td><td>{_e(s.get("responsable"))}</td><td>{_e(s.get("plazo"))}</td></tr>'
        for s in solicitudes)
    return f'''<div class="risk-section"><h3 class="risk-section-title">Solicitudes al oferente ({len(solicitudes)})</h3>
        <div class="tabla-wrap"><table class="tabla"><tr><th>N°</th><th>Tipo de solicitud</th><th>Norma y artículo</th><th>Cita de la oferta</th><th>Pedido</th><th>Clase</th><th>Responsable</th><th>Plazo</th></tr>{filas}</table></div></div>'''


# --- 4. Alertas ---

def seccion_alertas(alertas):
    items = "".join(f'''
        <div class="alerta"><p>{_e(a.get("norma"))} Art. {_e(a.get("articulo"))} · sección {_e(a.get("seccion_oferta"))}</p>
        <p><span class="detail-label">Motivo:</span> {_e(a.get("motivo"))}</p><p><span class="detail-label">Cita de la oferta:</span> {_e(a.get("cita"))}</p></div>''' for a in alertas)
    return f'''<div class="risk-section"><h3 class="risk-section-title">Alertas a revisar ({len(alertas)})</h3>
        <p class="vacio">{LEYENDA_ALERTAS}</p>{items or '<p class="vacio">No hay alertas.</p>'}</div>'''


def pie_tecnico(datos):
    cfg = datos.get("configuracion_analisis") or {}
    llamadas = cfg.get("llamadas_llm") if isinstance(cfg.get("llamadas_llm"), dict) else {}
    huella = (datos.get("lineamientos") or {}).get("huella", "")
    fecha = str(datos.get("timestamp_analisis") or "N/D")[:16].replace("T", " ")
    origen = (datos.get("resumen_ejecutivo") or {}).get("origen_comentario")
    return (f'<p class="pie-tecnico">Modelo: {_e(cfg.get("modelo_llm_usado"))} · Fecha: {escape(fecha)} · '
            f'Huella de los lineamientos: <span title="{escape(huella)}">{escape(huella[:12]) or "N/D"}</span> · '
            f'Verificaciones: {_e(llamadas.get("verificacion"))} · Clasificaciones: {_e(llamadas.get("clasificacion"))} · '
            f'Comentario general: {_e(origen)}</p>')


# --- Modo lista ---

def lista_simple(datos):
    riesgos = datos.get("riesgos_identificados_estructurados") or datos.get("riesgos_identificados") or []
    if not riesgos:
        return '<p class="vacio">No se identificaron riesgos.</p>'
    items = []
    for r in riesgos:
        descripcion = r.get("descripcion_riesgo") or ""
        palabras = descripcion.split()
        titulo = " ".join(palabras[:12]) + ("…" if len(palabras) > 12 else "")
        items.append(f'<div class="item"><h4>{_e(titulo)}</h4><p><span class="detail-label">Descripción:</span> {_e(r.get("explicacion_riesgo") or descripcion)}</p>'
                     f'<p><span class="detail-label">Cita de la oferta:</span> {_e(r.get("cita_oferta"))}</p></div>')
    return f'<div class="lista-simple">{"".join(items)}</div>'


def es_modo_verificacion(datos):
    return bool(datos.get("registro_brechas")) or datos.get("resumen_ejecutivo") is not None


def generar_dashboard_html(ruta_json_resultados, ruta_output_dashboard_html, info_tesis_config=None):
    try:
        with open(ruta_json_resultados, 'r', encoding='utf-8') as f:
            datos = json.load(f)
    except Exception as e:
        logger.error(f"Error abriendo o parseando JSON en {ruta_json_resultados}: {e}")
        return

    it = info_tesis_config or {}
    nombre_proyecto = escape(datos.get("nombre_proyecto_analizado", "Proyecto No Especificado"))
    logo_inline, logo_footer = image_to_base64("logo-itba.png"), image_to_base64("itba.png")

    if es_modo_verificacion(datos):
        riesgos, brechas, solicitudes = datos.get("riesgos") or [], datos.get("registro_brechas") or [], datos.get("solicitudes") or []
        resumen = datos.get("resumen_ejecutivo") or {}
        orden_clases = list(resumen.get("por_clase", {})) or list(CLASES)
        cuerpo = (seccion_resumen(resumen, riesgos, solicitudes, orden_clases) + seccion_registro(riesgos, brechas, orden_clases)
                  + seccion_solicitudes(solicitudes) + seccion_alertas(datos.get("alertas") or []) + pie_tecnico(datos))
    else:
        condicion = (datos.get("configuracion_analisis") or {}).get("condicion", "sin_rag")
        leyenda = LEYENDA_SIN_RAG if condicion == "sin_rag" else LEYENDA_LISTA_CON_RAG
        cuerpo = f'<div class="leyenda">{leyenda}</div>' + lista_simple(datos)

    final_html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard de Análisis de Riesgos: {nombre_proyecto}</title>
    <style>{CSS.replace("__BANNER__", image_to_base64("header_banner_abstract.png"))}</style>
</head>
<body>
<div class="page-wrapper">
    <div class="main-dashboard-container">
        <div class="abstract-banner-container"></div>
        <div class="header-content">
            <div class="title-with-logo"><img src="{logo_inline}" alt="Logo" class="logo-inline"><h1>{escape(it.get("titulo_tesis_h1", ""))}</h1></div>
            <h2>{escape(it.get("titulo_tesis_h2", ""))}</h2><h3>{escape(it.get("titulo_tesis_h3", ""))}</h3>
        </div>
        <h2 class="project-analysis-title">Resultados del Análisis para: {nombre_proyecto}</h2>
        {cuerpo}
    </div>
    <div class="dashboard-page-footer">
        <img src="{logo_footer}" alt="Logo ITBA" style="max-height:45px;margin-bottom:10px;">
        <p>{escape(it.get("institucion_line1",""))} - {escape(it.get("institucion_line2",""))}</p>
        <p><a href="{escape(str(it.get('github_repo_url','#')))}" target="_blank">Ver Repositorio en GitHub</a></p>
        <p>&copy; {CURRENT_YEAR} {escape(it.get("alumno",""))}. Todos los derechos reservados.</p>
    </div>
</div>
</body></html>'''

    try:
        os.makedirs(os.path.dirname(os.path.abspath(ruta_output_dashboard_html)), exist_ok=True)
        with open(ruta_output_dashboard_html, 'w', encoding='utf-8') as f_html:
            f_html.write(final_html)
        logger.info(f"Dashboard HTML generado exitosamente en: {ruta_output_dashboard_html}")
    except IOError as e:
        logger.error(f"Error al guardar el dashboard HTML en {ruta_output_dashboard_html}: {e}")
