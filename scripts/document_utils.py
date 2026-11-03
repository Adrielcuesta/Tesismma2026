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

def _quitar_encabezados_y_pies(paginas: list) -> list:
    """Quita las líneas que, normalizadas y sin dígitos, se repiten en al menos UMBRAL_ENCABEZADO de las páginas."""
    if len(paginas) < 4:  # con pocas páginas todo texto "se repite"
        return [(p, [l.strip() for l in t.split('\n')]) for p, t in paginas]
    conteo = {}
    for _, texto in paginas:
        for norm in {_normalizar_linea(l) for l in texto.split('\n')} - {''}:
            conteo[norm] = conteo.get(norm, 0) + 1
    repetidas = {n for n, c in conteo.items() if c / len(paginas) >= config.UMBRAL_ENCABEZADO}
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