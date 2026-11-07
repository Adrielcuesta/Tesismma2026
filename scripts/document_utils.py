# scripts/document_utils.py
import os
import re
import logging
import fitz  # PyMuPDF
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from . import config

logger = logging.getLogger(__name__)

EXTENSIONES_SOPORTADAS = (".pdf", ".docx")

# --- Extracción de texto (PDF y DOCX) ---

def _texto_docx(ruta: str) -> str:
    """Párrafos y tablas en el orden del documento; las filas de tabla se unen con ' | '."""
    from docx import Document as DocxDocument
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = DocxDocument(ruta)
    partes = []
    for hijo in doc.element.body.iterchildren():
        if hijo.tag.endswith('}p'):
            texto = Paragraph(hijo, doc).text.strip()
            if texto:
                partes.append(texto)
        elif hijo.tag.endswith('}tbl'):
            for fila in Table(hijo, doc).rows:
                celdas, vistas = [], set()
                for celda in fila.cells:
                    if id(celda._tc) in vistas:  # celda combinada: aparece repetida
                        continue
                    vistas.add(id(celda._tc))
                    celdas.append(celda.text.strip())
                if any(celdas):
                    partes.append(" | ".join(celdas))
    return "\n".join(partes)

def extraer_paginas(ruta: str) -> list:
    """Extracción única para .pdf y .docx. Devuelve [(pagina, texto)]; en docx la página es None."""
    extension = os.path.splitext(ruta)[1].lower()
    if extension == ".pdf":
        with fitz.open(ruta) as pdf:
            return [(i + 1, pagina.get_text()) for i, pagina in enumerate(pdf)]
    if extension == ".docx":
        return [(None, _texto_docx(ruta))]
    raise ValueError(f"Extensión no soportada: {ruta}")

def _documentos_de_archivo(ruta: str) -> list:
    """Una página (o el docx entero) por Document; page_number=-1 si no hay página."""
    nombre = os.path.basename(ruta)
    return [
        Document(page_content=texto, metadata={"source_document": nombre, "page_number": pagina if pagina is not None else -1})
        for pagina, texto in extraer_paginas(ruta)
    ]

# --- Lógica de Filtros Locales (Con capa de Metadatos) ---

def is_ignorable_page(page_text: str, min_chars=150) -> bool:
    text = (page_text or "").strip()
    if len(text) < min_chars:
        logger.info("      └─ Página ignorada por tener muy poco contenido.")
        return True
    return False

def is_metadata_page(page_text: str) -> bool:
    """Detecta si una página parece ser principalmente de metadatos (copyright, etc.)."""
    text_lower = page_text.lower()
    metadata_keywords = ["copyright", "todos los derechos reservados", "traducción oficial", "official translation", "ics", "isbn", "user licence only"]
    
    # Con límites de palabra: "ics" como subcadena coincide con palabras comunes
    hits = sum(1 for keyword in metadata_keywords if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower))
    
    # Si la página tiene varias de estas palabras clave, es probablemente una página de metadatos.
    if hits >= 2:
        logger.info(f"      └─ Página descartada por [Filtro de Metadatos - {hits} palabras clave encontradas].")
        return True
    return False

def is_table_of_contents_page(page_text: str) -> bool:
    """Determina si una página parece ser una tabla de contenido."""
    lines = [line.strip() for line in page_text.strip().split('\n') if line.strip()]
    if len(lines) < 7: return False

    # Solo cuentan títulos cortos: "contenido" dentro de una frase de un artículo no es un índice
    first_lines_text = " ".join(l for l in lines[:3] if len(l) < 60).lower()
    toc_keywords = ["índice", "contenido", "tabla de contenido", "table of contents", "sumario"]
    if any(keyword in first_lines_text for keyword in toc_keywords):
        logger.info("      └─ Página descartada por [Filtro de Índice - Palabra Clave].")
        return True

    # Un índice tiene líneas cortas; varios párrafos largos indican texto normativo
    if sum(1 for line in lines if len(line) > 100) >= 3:
        return False

    short_numbered_lines = sum(1 for line in lines if len(line) < 150 and re.search(r'\d', line))
    ratio = short_numbered_lines / len(lines)
    if ratio > 0.4:
        logger.info(f"      └─ Página descartada por [Filtro de Índice - Densidad de Líneas Cortas y Numeradas: {ratio:.2f}].")
        return True

    dotted_lines = sum(1 for line in lines if '....' in line)
    if len(lines) > 0 and (dotted_lines / len(lines)) > 0.3:
        logger.info("      └─ Página descartada por [Filtro de Índice - Densidad de Puntos].")
        return True

    return False

def procesar_y_filtrar_paginas(docs: list) -> list:
    """Filtra una lista de páginas aplicando todas las capas de filtrado."""
    filtered_pages = []
    logger.info(f"  Iniciando filtrado de {len(docs)} páginas del documento...")
    for i, doc in enumerate(docs):
        page_content = doc.page_content
        
        # Aplicar todos los filtros
        if is_ignorable_page(page_content) or is_metadata_page(page_content):
            continue

        # page_number -1 = docx sin páginas: el documento entero no puede ser un índice
        if i < config.MAX_PAGES_TO_CHECK_FOR_INDEX and doc.metadata.get("page_number") != -1:
            if is_table_of_contents_page(page_content):
                continue
        
        filtered_pages.append(doc)

    logger.info(f"  Páginas retenidas tras todos los filtros: {len(filtered_pages)} de {len(docs)}.")
    return filtered_pages

def cargar_y_procesar_pdfs_de_carpeta(carpeta_path, chunk_size, chunk_overlap):
    documentos_cargados_finales = []
    if not os.path.isdir(carpeta_path): return []
    logger.info(f"Procesando documentos desde la carpeta: {carpeta_path}")
    for filename in sorted(os.listdir(carpeta_path)):
        if filename.lower().endswith(EXTENSIONES_SOPORTADAS):
            logger.info(f"Procesando documento: {filename}")
            try:
                file_path = os.path.join(carpeta_path, filename)
                docs_del_pdf = _documentos_de_archivo(file_path)
                paginas_filtradas = procesar_y_filtrar_paginas(docs_del_pdf)
                if paginas_filtradas:
                    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap, length_function=len)
                    fragmentos = text_splitter.split_documents(paginas_filtradas)
                    logger.info(f"  Documento '{filename}' aportó {len(fragmentos)} fragmentos a la base de datos.")
                    documentos_cargados_finales.extend(fragmentos)
                else:
                    logger.warning(f"  El documento '{filename}' no generó contenido útil tras el filtrado.")
            except Exception as e:
                logger.error(f"  Error al cargar o procesar {filename}: {e}", exc_info=True)
    return documentos_cargados_finales

def procesar_pdf_proyecto_para_analisis(ruta_pdf_proyecto, max_chars_proyecto):
    if not os.path.exists(ruta_pdf_proyecto):
        logger.error(f"El archivo de proyecto no existe en la ruta: {ruta_pdf_proyecto}")
        return None
    logger.info(f"Procesando el documento para análisis: {os.path.basename(ruta_pdf_proyecto)}")
    try:
        doc_proyecto_raw = _documentos_de_archivo(ruta_pdf_proyecto)
        doc_proyecto_filtrado = [doc for doc in doc_proyecto_raw if not is_ignorable_page(doc.page_content)]
        if not doc_proyecto_filtrado:
            logger.warning(f"El documento del proyecto '{os.path.basename(ruta_pdf_proyecto)}' no contiene páginas con contenido sustancial.")
            return None
        descripcion_nuevo_proyecto = "\n\n".join([doc.page_content for doc in doc_proyecto_filtrado])
        logger.info(f"Descripción del proyecto generada desde {len(doc_proyecto_filtrado)} páginas útiles, total {len(descripcion_nuevo_proyecto)} caracteres.")
        if len(descripcion_nuevo_proyecto) > max_chars_proyecto:
            logger.warning(f"La descripción del proyecto excede el límite de {max_chars_proyecto} y será truncada.")
            descripcion_nuevo_proyecto = descripcion_nuevo_proyecto[:max_chars_proyecto]
        return descripcion_nuevo_proyecto
    except Exception as e_proc_proyecto:
        logger.error(f"Error crítico al procesar el PDF del proyecto: {e_proc_proyecto}", exc_info=True)
        return None

def obtener_ruta_pdf_proyecto(directorio_proyecto_analizar):
    if not os.path.isdir(directorio_proyecto_analizar): return None
    pdfs = [f for f in os.listdir(directorio_proyecto_analizar) if f.lower().endswith(EXTENSIONES_SOPORTADAS)]
    return os.path.join(directorio_proyecto_analizar, pdfs[0]) if pdfs else None

# --- Chunker de la KB por artículos ---

RE_ARTICULO = re.compile(r'^\s*Art(?:\.|[íi]culo)\s*(\d+)\.(\d+)\.(?!\d)\s*(.*)$')
RE_CAPITULO = re.compile(r'^\s*CAP[ÍI]TULO\s+\d+\.', re.IGNORECASE)
RE_CONTROL_INTERPRETACION = re.compile(r'CONTROL\s+DE\s+INTERPRETACI[ÓO]N', re.IGNORECASE)

def norma_de_archivo(nombre: str) -> str:
    m = re.search(r'NORM_\d{2}', nombre, re.IGNORECASE)
    return m.group(0).upper() if m else os.path.splitext(nombre)[0]

def _normalizar_linea(linea: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'\d+', '', linea.lower())).strip()

def _quitar_encabezados_y_pies(paginas: list, min_largo: int = 0) -> list:
    """Quita las líneas que, normalizadas y sin dígitos, se repiten en al menos UMBRAL_ENCABEZADO de las páginas.
    min_largo: solo se quitan las de al menos esa cantidad de caracteres normalizados (0 = todas)."""
    if len(paginas) < 4:  # con pocas páginas todo texto "se repite"
        return [(p, [l.strip() for l in t.split('\n')]) for p, t in paginas]
    conteo = {}
    for _, texto in paginas:
        for norm in {_normalizar_linea(l) for l in texto.split('\n')} - {''}:
            conteo[norm] = conteo.get(norm, 0) + 1
    repetidas = {n for n, c in conteo.items() if c / len(paginas) >= config.UMBRAL_ENCABEZADO and len(n) >= min_largo}
    return [(p, [l.strip() for l in t.split('\n') if _normalizar_linea(l) not in repetidas]) for p, t in paginas]

def _paginas_limpias(ruta: str) -> list:
    """[(pagina, lineas, motivo_descarte|None)] sin encabezados/pies; motivo: 'vacía', 'metadatos' o 'índice'."""
    limpias = _quitar_encabezados_y_pies(extraer_paginas(ruta))
    resultado = []
    for i, (pagina, lineas) in enumerate(limpias):
        texto = "\n".join(l for l in lineas if l)
        motivo = None
        if not texto:
            motivo = "vacía"
        elif is_metadata_page(texto):
            motivo = "metadatos"
        elif i < config.MAX_PAGES_TO_CHECK_FOR_INDEX and pagina is not None and is_table_of_contents_page(texto):
            motivo = "índice"
        resultado.append((pagina, lineas, motivo))
    return resultado

def _parrafos(lineas: list) -> list:
    """Une las líneas visuales del PDF en párrafos: un párrafo termina en una línea que acaba en . : ;"""
    parrafos, actual = [], []
    for linea in lineas:
        if not linea:
            continue
        actual.append(linea)
        if linea.endswith(('.', ':', ';')):
            parrafos.append(" ".join(actual))
            actual = []
    if actual:
        parrafos.append(" ".join(actual))
    return parrafos

def _cortar(texto: str, max_chars: int) -> list:
    """Parte un párrafo largo por oraciones; una oración que aún excede se corta por palabras."""
    piezas, actual = [], ""
    for oracion in re.split(r'(?<=[.;:])\s+', texto):
        while len(oracion) > max_chars:
            corte = oracion.rfind(' ', 0, max_chars) or max_chars
            if corte <= 0:
                corte = max_chars
            if actual:
                piezas.append(actual)
                actual = ""
            piezas.append(oracion[:corte])
            oracion = oracion[corte:].lstrip()
        if actual and len(actual) + 1 + len(oracion) > max_chars:
            piezas.append(actual)
            actual = ""
        actual = (actual + " " + oracion).strip()
    if actual:
        piezas.append(actual)
    return piezas

def _partes(encabezado: str, parrafos: list, max_chars: int) -> list:
    """Agrupa párrafos en partes de hasta max_chars en total (encabezado incluido); un párrafo más largo se corta por oraciones."""
    max_chars = max_chars - len(encabezado) - 1
    parrafos = [q for p in parrafos for q in (_cortar(p, max_chars) if len(p) > max_chars else [p])]
    cuerpo = "\n".join(parrafos)
    if len(cuerpo) <= max_chars:
        return [(encabezado + "\n" + cuerpo).strip()]
    partes, actual, largo = [], [], 0
    for p in parrafos:
        if actual and largo + len(p) + 1 > max_chars:
            partes.append((encabezado + "\n" + "\n".join(actual)).strip())
            actual, largo = [], 0
        actual.append(p)
        largo += len(p) + 1
    if actual:
        partes.append((encabezado + "\n" + "\n".join(actual)).strip())
    return partes

def analizar_norma_por_articulos(ruta: str) -> dict:
    """Divide una norma en artículos. Devuelve {'chunks', 'descartadas', 'rechazadas', 'huerfano_chars', 'control_interpretacion'}
    (los últimos cuatro son diagnóstico para --resumen)."""
    archivo = os.path.basename(ruta)
    norma = norma_de_archivo(archivo)
    paginas = _paginas_limpias(ruta)
    descartadas = [(p, m) for p, _, m in paginas if m]

    articulos, preambulo, control = [], [], []   # preambulo/control: [(pagina, linea)]
    actual, ultimo, titulo_pendiente = None, (-1, -1), False
    rechazadas, huerfano, hubo_capitulo = [], 0, False

    for pagina, lineas, motivo in paginas:
        if motivo:
            # El texto de interpretación puede estar en portada/índice: se conserva aparte
            m = RE_CONTROL_INTERPRETACION.search("\n".join(lineas))
            if m and motivo != "vacía":
                texto = "\n".join(lineas)[m.start():]
                control.extend((pagina, l.strip()) for l in texto.split('\n'))
            continue
        for linea in lineas:
            if not linea:
                continue
            if RE_CAPITULO.match(linea):
                actual, titulo_pendiente, hubo_capitulo = None, False, True
                continue
            m = RE_ARTICULO.match(linea)
            if m:
                numero = (int(m.group(1)), int(m.group(2)))
                if numero > ultimo:
                    titulo = m.group(3).strip().rstrip('.').strip()
                    actual = {"numero": numero, "titulo": titulo, "pagina": pagina, "lineas": []}
                    articulos.append(actual)
                    ultimo, titulo_pendiente = numero, not titulo
                    continue
                rechazadas.append((pagina, numero))  # no crece: es texto, no un artículo nuevo
            if actual is None:
                if articulos:
                    huerfano += len(linea)
                else:
                    preambulo.append((pagina, linea))
            elif titulo_pendiente:
                actual["titulo"], titulo_pendiente = linea.rstrip('.').strip(), False
            else:
                actual["lineas"].append(linea)

    chunks = []
    def agregar(partes, articulo, titulo, pagina):
        for n, texto in enumerate(partes, 1):
            chunks.append(Document(page_content=texto, metadata={
                "norma": norma, "articulo": articulo, "titulo": titulo,
                "pagina": pagina if pagina is not None else -1, "fuente": archivo, "parte": n}))

    for a in articulos:
        x, y = a["numero"]
        encabezado = f"Art. {x}.{y}. {a['titulo']}".strip()
        agregar(_partes(encabezado, _parrafos(a["lineas"]), config.MAX_CHARS_ARTICULO), f"{x}.{y}", a["titulo"], a["pagina"])
    for bloque, titulo in ((preambulo, "Preámbulo"), (control, "Control de interpretación")):
        if bloque and any(l for _, l in bloque):
            partes = _partes(titulo, _parrafos([l for _, l in bloque]), config.MAX_CHARS_ARTICULO)
            agregar(partes, "preambulo", titulo, bloque[0][0])
    return {"chunks": chunks, "descartadas": descartadas, "rechazadas": rechazadas,
            "huerfano_chars": huerfano, "control_interpretacion": bool(control)}

def chunkear_norma_por_articulos(ruta: str) -> list:
    return analizar_norma_por_articulos(ruta)["chunks"]

def cargar_kb_por_articulos(carpeta_path: str) -> list:
    """Chunks por artículo de todas las normas de la carpeta, salvo config.NORMA_COMPLETA (va entera en el prompt)."""
    chunks = []
    if not os.path.isdir(carpeta_path): return chunks
    for filename in sorted(os.listdir(carpeta_path)):
        if not filename.lower().endswith(EXTENSIONES_SOPORTADAS) or norma_de_archivo(filename) == config.NORMA_COMPLETA:
            continue
        try:
            nuevos = chunkear_norma_por_articulos(os.path.join(carpeta_path, filename))
            logger.info(f"  '{filename}' aportó {len(nuevos)} chunks por artículo.")
            chunks.extend(nuevos)
        except Exception as e:
            logger.error(f"  Error al procesar {filename}: {e}", exc_info=True)
    return chunks

def cargar_norma_completa(norma: str = None, carpeta: str = None) -> str:
    """Texto limpio (sin encabezados/pies ni páginas de metadatos/índice) de una norma, para usarla entera en prompts."""
    norma = norma or config.NORMA_COMPLETA
    carpeta = carpeta or config.DIRECTORIO_BASE_CONOCIMIENTO
    archivos = [f for f in sorted(os.listdir(carpeta)) if f.lower().endswith(EXTENSIONES_SOPORTADAS) and norma_de_archivo(f) == norma.upper()]
    if not archivos:
        raise FileNotFoundError(f"No se encontró {norma} en {carpeta}")
    paginas = _paginas_limpias(os.path.join(carpeta, archivos[0]))
    return "\n".join("\n".join(l for l in lineas if l) for _, lineas, motivo in paginas if not motivo)

# --- Oferta: texto limpio y división en secciones ---

# Encabezado estricto: línea completa, numeración seguida de un título que empieza con mayúscula y minúscula
# ("42 t", "1.600 mm", "2.5 MPa" no cumplen). Nivel 2 se prueba primero porque "1.2 Título" también abre con "1."
RE_ENCABEZADO_NIVEL2 = re.compile(r'^(\d+)\.(\d+)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]')
RE_ENCABEZADO_NIVEL1 = re.compile(r'^(\d+)\.\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]')
# "7.2 SAT bajo carga": nivel 2 con acrónimo; solo vale si la numeración es consecutiva (ver _numeracion_encabezado)
RE_ENCABEZADO_NIVEL2_ACRONIMO = re.compile(r'^(\d+)\.(\d+)\s+[A-ZÁÉÍÓÚÑ]{2,}(?![A-Za-záéíóúñ])')
MAX_LARGO_ENCABEZADO = 90
MIN_CHARS_INTRODUCCION = 200

def extraer_texto_oferta(ruta: str) -> str:
    """Texto completo de la oferta (sin truncar), sin encabezados/pies repetidos y concatenado de todas las
    páginas: un encabezado que queda al pie de una página y su cuerpo en la siguiente quedan contiguos."""
    paginas = _quitar_encabezados_y_pies(extraer_paginas(ruta), config.MIN_LARGO_ENCABEZADO_OFERTA)
    return "\n".join("\n".join(l for l in lineas if l) for _, lineas in paginas).strip()

def _numeracion_encabezado(linea: str, ultimo: tuple = ()):
    """Tupla de enteros ((1,) o (1, 2)) si la línea es un encabezado por su forma, o None. `ultimo` es la numeración
    del encabezado anterior: un nivel 2 con acrónimo ("7.2 SAT") solo cuenta si sigue a `ultimo` de forma consecutiva."""
    if len(linea) >= MAX_LARGO_ENCABEZADO:
        return None
    m = RE_ENCABEZADO_NIVEL2.match(linea)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = RE_ENCABEZADO_NIVEL2_ACRONIMO.match(linea)
    if m:
        capitulo, menor = int(m.group(1)), int(m.group(2))
        ultimo_cap = ultimo[0] if ultimo else 0
        ultimo_menor = ultimo[1] if len(ultimo) == 2 else 0
        if (capitulo == ultimo_cap and menor == ultimo_menor + 1) or (menor == 1 and capitulo > ultimo_cap):
            return (capitulo, menor)
        return None
    m = RE_ENCABEZADO_NIVEL1.match(linea)
    return (int(m.group(1)),) if m else None

def _bloques_por_encabezado(texto: str) -> list:
    """[{capitulo, titulo, lineas}]. Un encabezado solo cuenta si su numeración supera la del anterior;
    si no, es texto del bloque en curso. El bloque 0 es el texto previo al primer encabezado."""
    bloques, ultimo = [], ()
    actual = {"capitulo": 0, "titulo": "Introducción", "lineas": []}
    for linea in (l.strip() for l in texto.split('\n')):
        if not linea:
            continue
        numero = _numeracion_encabezado(linea, ultimo)
        if numero and numero > ultimo:
            bloques.append(actual)
            actual = {"capitulo": numero[0], "titulo": linea, "lineas": [linea]}
            ultimo = numero
        else:
            actual["lineas"].append(linea)
    bloques.append(actual)
    return bloques

def _partir_subseccion(titulo: str, lineas: list) -> list:
    """[(titulo, texto)]; si la subsección sola supera SECTION_MAX_CHARS se parte por párrafos."""
    texto = "\n".join(lineas)
    if len(texto) <= config.SECTION_MAX_CHARS:
        return [(titulo, texto)]
    partes = _partes("", _parrafos(lineas), config.SECTION_MAX_CHARS)
    if len(partes) == 1:
        return [(titulo, partes[0])]
    return [(f"{titulo} (parte {n})", p) for n, p in enumerate(partes, 1)]

def es_introduccion(seccion: dict) -> bool:
    """True si la sección es el texto previo al primer encabezado (título 'Introducción', con o sin '(parte n)')."""
    return all(t.split(" (parte ")[0] == "Introducción" for t in seccion["titulos"])

def dividir_en_secciones(texto: str) -> list:
    """Divide la oferta en secciones [{id, titulos, subsecciones[(titulo, texto)], texto}].
    Agrupa subsecciones contiguas hasta SECTION_MAX_CHARS sin cruzar capítulos de nivel 1."""
    bloques = _bloques_por_encabezado(texto)
    sin_encabezados = len(bloques) == 1
    subsecciones = []   # (capitulo, titulo, texto)
    for b in bloques:
        if not b["lineas"]:
            continue
        # Sin ningún encabezado el texto es el documento entero; si no, la introducción solo cuenta si es sustancial
        if b["capitulo"] == 0 and not sin_encabezados and len("\n".join(b["lineas"])) <= MIN_CHARS_INTRODUCCION:
            continue
        titulo = "Documento" if sin_encabezados else b["titulo"]
        subsecciones.extend((b["capitulo"], t, x) for t, x in _partir_subseccion(titulo, b["lineas"]))

    secciones, grupo = [], None
    for capitulo, titulo, contenido in subsecciones:
        if grupo and grupo["capitulo"] == capitulo and grupo["largo"] + 1 + len(contenido) <= config.SECTION_MAX_CHARS:
            grupo["subsecciones"].append((titulo, contenido))
            grupo["largo"] += 1 + len(contenido)
        else:
            grupo = {"capitulo": capitulo, "subsecciones": [(titulo, contenido)], "largo": len(contenido)}
            secciones.append(grupo)
    return [
        {"id": f"S{n}", "titulos": [t for t, _ in g["subsecciones"]], "subsecciones": g["subsecciones"],
         "texto": "\n".join(x for _, x in g["subsecciones"])}
        for n, g in enumerate(secciones, 1)
    ]


# --- Oraciones numeradas de una sección (verificación por artículo) ---

MAX_CHARS_LINEA_CORTA = 25
# Abreviaturas cuyo punto no termina la oración, aunque lo siga una mayúscula
ABREVIATURAS = {"art", "arts", "nº", "n°", "no", "núm", "pág", "págs", "cap", "sec", "fig", "tab", "inc", "ej", "etc",
                "aprox", "máx", "mín", "sr", "sra", "ing", "dr", "dra", "lic", "vs", "ref"}
RE_FIN_ORACION = re.compile(r'([.!?]+)\s+(?=[A-ZÁÉÍÓÚÑ¿¡«"(\[])')

def _oraciones_de_unidad(unidad: str) -> list:
    """Parte una unidad en oraciones: corta tras . ! ? seguidos de espacio y mayúscula, salvo tras una abreviatura o
    una inicial. Los decimales ('1.600', '0,05') y las referencias ('Art. 4.2') no tienen espacio tras el punto."""
    oraciones, inicio = [], 0
    for m in RE_FIN_ORACION.finditer(unidad):
        previa = unidad[inicio:m.start()].split()
        palabra = previa[-1].lower().strip('()[]"«»') if previa else ""
        if m.group(1) == "." and (palabra in ABREVIATURAS or (len(palabra) == 1 and palabra.isalpha())):
            continue
        oraciones.append(unidad[inicio:m.end(1)])
        inicio = m.end()
    oraciones.append(unidad[inicio:])
    return [o.strip() for o in oraciones if o.strip()]

def numerar_oraciones(texto_seccion: str) -> list:
    """[(id 'O1'.., texto)] de una sección. Las líneas visuales del PDF se unen como en _parrafos (una unidad termina en una
    línea que acaba en . : ; ! ?, en un encabezado numerado o en una línea corta); las líneas cortas
    (<= MAX_CHARS_LINEA_CORTA, p. ej. celdas de tabla) se pegan a la oración anterior. Después cada unidad se parte en oraciones."""
    unidades, actual, termina_en_celda = [], None, False
    for linea in (l.strip() for l in texto_seccion.split('\n')):
        if not linea:
            continue
        corta = len(linea) <= MAX_CHARS_LINEA_CORTA and not _numeracion_encabezado(linea)
        if actual is None:
            actual = linea
        elif corta:
            actual += " " + linea
        elif termina_en_celda or actual.endswith(('.', ':', ';', '!', '?')) or _numeracion_encabezado(actual):
            unidades.append(actual)
            actual = linea
        else:
            actual += " " + linea
        termina_en_celda = corta and actual != linea
    if actual:
        unidades.append(actual)
    oraciones = [o for u in unidades for o in _oraciones_de_unidad(u)]
    return [(f"O{n}", o) for n, o in enumerate(oraciones, 1)]
