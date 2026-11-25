# scripts/nube.py
"""Experimento de diagnóstico: verificación y clasificación con un modelo en la nube (API compatible con OpenAI) sobre EXACTAMENTE los mismos
pares (sección, norma, artículo) que una corrida local, para aislar el efecto del tamaño del modelo. No cambia prompts, reglas, criterios, motor
ni recuperación: la recuperación se toma del JSON local y el texto de cada artículo se busca en ChromaDB por metadatos (sin embeddings ni reranker).
El comentario general usa la plantilla (sin llamada al modelo). Las secciones corren en paralelo; los pares de una sección, en orden.

Uso:
  python -m scripts.nube --reusar-recuperacion <json_local> [<json_local> ...] [--proveedor deepinfra] [--modelo Qwen/Qwen3-32B]
         [--max-pares N] [--thinking] [--concurrencia N] [--pdf <oferta> ...] [--estimar]
  python -m scripts.nube --reusar-recuperacion <json_recuperacion> --reintentar-fallidas <json_resultados> [--proveedor ... --modelo ...] [--estimar]
--estimar imprime los pares y el costo estimado y sale, sin API. --reintentar-fallidas vuelve a llamar solo a los pares sin respuesta válida de una corrida (tiempo agotado,
formato inválido tras reintentar o sección caída entera, p. ej. por un 402) y escribe <...>-reintento.json con el conjunto fusionado; si la corrida original no coincide
(huella de pares, perfil, modelo, proveedor, lineamientos), no arranca. Un modelo de config.NUBE_MODELOS_RAZONAMIENTO_FIJO (gpt-oss) recibe su esfuerzo en un mensaje de sistema.
Las claves se leen del .env (DEEPINFRA_API_KEY, GROQ_API_KEY)."""
import argparse
import datetime
import json
import logging
import os
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import openai
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda

from . import clasificacion, comentario, config, costo, document_utils, huella_recuperacion, lineamientos, rag_components
from .main import AnalisisError, Llamadas, LlamadaFallida, _guardar_y_generar_dashboard, _verificar_seccion, _estadisticas_tokens, normalizaciones_formato
from .schemas import ClasificacionRiesgo, LLMResponse, RiskReport, SeccionInforme, SourceChunk, VerificacionArticulo

logger = logging.getLogger(__name__)
CADA_N_LLAMADAS = 50


class PresupuestoAgotado(Exception):
    """El gasto acumulado alcanzó PRESUPUESTO_USD: la corrida se detiene de forma ordenada."""


class Gasto:
    """Tokens y costo acumulados de la corrida (seguro entre hilos). Precios en USD por millón de tokens; los tokens cacheados se cobran como entrada (cota superior)."""
    def __init__(self, precios: dict, tope: float):
        self.precios, self.tope, self.lock = precios, tope, threading.Lock()
        self.entrada = self.salida = self.cacheados = self.llamadas = 0

    @property
    def usd(self) -> float:
        return (self.entrada * self.precios["entrada"] + self.salida * self.precios["salida"]) / 1_000_000

    def verificar(self):
        if self.usd >= self.tope:
            raise PresupuestoAgotado(f"gasto {self.usd:.4f} USD alcanzó el tope de {self.tope} USD")

    def registrar(self, entrada: int, salida: int, cacheados: int = 0):
        with self.lock:
            self.entrada, self.salida, self.cacheados, self.llamadas = self.entrada + entrada, self.salida + salida, self.cacheados + cacheados, self.llamadas + 1
            if self.llamadas % CADA_N_LLAMADAS == 0:
                logger.info(f"Gasto acumulado: {self.usd:.4f} USD en {self.llamadas} llamadas ({self.entrada} tokens de entrada, {self.salida} de salida)")

    def foto(self) -> dict:
        with self.lock:
            return {"entrada": self.entrada, "salida": self.salida, "cacheados": self.cacheados, "llamadas": self.llamadas, "usd": self.usd}


class ClienteNube:
    """Envuelve el cliente del modelo: corta si se agotó el presupuesto, cuenta los tokens de `usage` y los deja en response_metadata con los nombres
    que ya lee main._invocar (prompt_eval_count, eval_count, done_reason). Un 429, un 5xx o un corte de conexión que el cliente no pudo resolver tras sus
    reintentos se informa como LlamadaFallida: el par queda como alerta «tiempo_agotado» (sin un reintento más, el cliente ya reintentó)."""
    def __init__(self, llm, gasto: Gasto, respaldo=None, nombre: str = "", sistema: str = None):
        """respaldo: cliente con json_object, al que se cae (y se avisa) si el proveedor rechaza el json_schema con un 400 o 422.
        sistema: mensaje de sistema que se antepone a cada llamada (esfuerzo de razonamiento de los modelos con razonamiento fijo, p. ej. «Reasoning: low»)."""
        self.llm, self.gasto, self.respaldo, self.nombre, self.usa_respaldo, self.sistema = llm, gasto, respaldo, nombre, False, sistema

    def _con_sistema(self, entrada):
        if not self.sistema:
            return entrada
        mensajes = entrada.to_messages() if hasattr(entrada, "to_messages") else ([HumanMessage(content=entrada)] if isinstance(entrada, str) else list(entrada))
        return [SystemMessage(content=self.sistema), *mensajes]

    @property
    def formato(self) -> str:
        return "json_object (respaldo)" if self.usa_respaldo else ("json_schema" if self.respaldo is not None else "json_object")

    def _llamar(self, entrada):
        if self.usa_respaldo or self.respaldo is None:
            return (self.respaldo if self.usa_respaldo else self.llm).invoke(entrada)
        try:
            return self.llm.invoke(entrada)
        except (openai.BadRequestError, openai.UnprocessableEntityError) as e:
            mensaje = self.respaldo.invoke(entrada)      # si también falla, el error del respaldo sube y no se cambia de formato
            self.usa_respaldo = True
            logger.warning(f"El proveedor rechazó json_schema para {self.nombre or 'el esquema'} ({type(e).__name__}: {str(e)[:150]}): se sigue con json_object.")
            return mensaje

    def invocar(self, entrada, config=None):
        self.gasto.verificar()
        try:
            mensaje = self._llamar(self._con_sistema(entrada))
        except (openai.RateLimitError, openai.InternalServerError, openai.APIConnectionError) as e:
            raise LlamadaFallida(f"{type(e).__name__}: {str(e)[:120]}") from e
        except openai.LengthFinishReasonError as e:
            # el modelo agotó max_tokens antes de cerrar el JSON: el SDK levanta en vez de devolver el mensaje. Se devuelve un mensaje vacío con
            # finish_reason=length para que _invocar lo trate como corte por largo (un reintento y luego LlamadaFallida) y el reintento de formato
            # lo descarte como formato inválido; se cobran los tokens que informa la excepción.
            usage = getattr(getattr(e, "completion", None), "usage", None)
            logger.warning(f"{self.nombre or 'respuesta'} cortada por largo ({type(e).__name__}): se trata como respuesta truncada.")
            mensaje = AIMessage(content="", response_metadata={"finish_reason": "length", "token_usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0, "completion_tokens": getattr(usage, "completion_tokens", 0) or 0}})
        meta = dict(getattr(mensaje, "response_metadata", None) or {})
        uso, uso_meta = getattr(mensaje, "usage_metadata", None) or {}, meta.get("token_usage") or {}
        entrada_tok = uso.get("input_tokens") or uso_meta.get("prompt_tokens") or 0
        salida_tok = uso.get("output_tokens") or uso_meta.get("completion_tokens") or 0
        cacheados = (uso.get("input_token_details") or {}).get("cache_read") or (uso_meta.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        self.gasto.registrar(entrada_tok, salida_tok, cacheados)
        mensaje.response_metadata = {**meta, "prompt_eval_count": entrada_tok, "eval_count": salida_tok, "cached_tokens": cacheados,
                                     "done_reason": "length" if meta.get("finish_reason") == "length" else "stop"}
        return mensaje

    invoke = invocar

    def runnable(self):
        return RunnableLambda(self.invocar)


# --- Recuperación reusada ---

def pares_de_json(local: dict) -> list:
    """[(sección, norma, artículo)] en el orden de secciones[].fragmentos del JSON local."""
    return [(s["id"], f["norma"], str(f["articulo"])) for s in local.get("secciones") or [] for f in s.get("fragmentos") or []]


def indice_de_articulos(datos_chroma: dict) -> dict:
    """{(norma, artículo): [Document por parte, de la 1 en adelante]} a partir de vector_db.get(include=documents+metadatas)."""
    indice = {}
    for texto, meta in zip(datos_chroma.get("documents") or [], datos_chroma.get("metadatas") or []):
        meta = meta or {}
        indice.setdefault((meta.get("norma"), str(meta.get("articulo"))), []).append(Document(page_content=texto, metadata=meta))
    for partes in indice.values():
        partes.sort(key=lambda d: d.metadata.get("parte") or 1)
    return indice


def documentos_de_seccion(fragmentos: list, indice: dict, avisos: list = None) -> list:
    """Un documento por fragmento, en el mismo orden. Si el JSON repite un artículo en la sección, la repetición k toma la parte k;
    si el artículo tiene varias partes y el JSON no dice cuál se usó, toma la primera (se anota en `avisos`)."""
    vistos, docs = Counter(), []
    for f in fragmentos:
        clave = (f["norma"], str(f["articulo"]))
        partes = indice.get(clave)
        if not partes:
            raise AnalisisError(f"{clave[0]} Art. {clave[1]} no está en la base ChromaDB (¿se reindexó la KB después de la corrida local?)")
        k = vistos[clave]
        vistos[clave] += 1
        exacta = [p for p in partes if f.get("parte") is not None and (p.metadata.get("parte") or 1) == f["parte"]]
        if exacta:      # el JSON dice qué parte se recuperó
            d = exacta[0]
        else:
            if len(partes) > 1 and k == 0 and avisos is not None:
                avisos.append(clave)
            d = partes[min(k, len(partes) - 1)]
        docs.append(Document(page_content=d.page_content, metadata=dict(d.metadata)))
    return docs


def _abrir_chroma():
    from langchain_community.vectorstores import Chroma   # sin función de embeddings: solo se lee por metadatos
    return Chroma(persist_directory=config.CHROMA_DB_PATH_KB, collection_name=config.CHROMA_COLLECTION_KB, embedding_function=None)


# --- Ejecución por secciones ---

def _correr_seccion(seccion, docs, cadena_verif, cadena_clasif, cliente_verif, cliente_clasif, lin):
    llamadas, t_sec = Llamadas({"verificacion": 0, "clasificacion": 0, "comentario": 0, "lista": 0, "correccion_formato": 0}), {"id": seccion["id"]}
    try:
        brechas, alertas, registro = _verificar_seccion(seccion, docs, cadena_verif, cadena_clasif, cliente_verif, cliente_clasif, lin, t_sec, llamadas)
        # los pares descartados por formato inválido (tras el reintento de formato) también son llamadas fallidas
        llamadas["fallidas"] = llamadas.get("fallidas", 0) + sum(1 for r in registro if r.get("estado") in ("descartada", "clasificacion_fallida"))
        return {"brechas": brechas, "alertas": alertas, "registro": registro, "llamadas": llamadas, "t_sec": t_sec, "incompleta": False}
    except PresupuestoAgotado:
        registro = [{"seccion": seccion["id"], "etapa": "verificacion", "estado": "presupuesto_agotado", "motivo": "la corrida se detuvo al alcanzar el presupuesto"}]
        return {"brechas": [], "alertas": [], "registro": registro, "llamadas": llamadas, "t_sec": t_sec, "incompleta": True}
    except Exception as e:      # imprevisto en la sección: no corta la corrida; se pierde lo de esta sección y queda marcada
        logger.error(f"{seccion['id']}: error inesperado ({type(e).__name__}: {str(e)[:200]}); la sección queda incompleta y la corrida sigue.")
        registro = [{"seccion": seccion["id"], "etapa": "verificacion", "estado": "seccion_fallida", "motivo": f"{type(e).__name__}: {str(e)[:200]}"}]
        llamadas["fallidas"] = llamadas.get("fallidas", 0) + 1
        return {"brechas": [], "alertas": [], "registro": registro, "llamadas": llamadas, "t_sec": t_sec, "incompleta": False}


def ejecutar_secciones(secciones, docs_por_seccion, cliente_verif, cliente_clasif, lin, concurrencia) -> list:
    """Corre las secciones en paralelo y devuelve los resultados en el orden de `secciones` (igual que la corrida secuencial)."""
    cadena_verif = rag_components.crear_cadena_verificacion(cliente_verif.runnable())
    cadena_clasif = rag_components.crear_cadena_clasificacion(cliente_clasif.runnable())
    pendientes = [(s, docs_por_seccion[s["id"]]) for s in secciones if docs_por_seccion.get(s["id"])]
    with ThreadPoolExecutor(max_workers=max(1, concurrencia)) as pool:
        futuros = [pool.submit(_correr_seccion, s, docs, cadena_verif, cadena_clasif, cliente_verif, cliente_clasif, lin) for s, docs in pendientes]
        return [(s["id"], f.result()) for (s, _), f in zip(pendientes, futuros)]


def limitar_pares(docs_por_seccion: dict, orden: list, maximo) -> dict:
    """Se queda con los primeros `maximo` pares (en el orden de las secciones); None deja todo."""
    if maximo is None:
        return docs_por_seccion
    restantes, salida = maximo, {}
    for id_sec in orden:
        docs = docs_por_seccion.get(id_sec) or []
        salida[id_sec], restantes = docs[:max(0, restantes)], max(0, restantes - len(docs))
    return salida


def resumen_humo(registro: list, gasto: dict) -> dict:
    """Pares verificados, tokens, costo y cuántas respuestas de verificación se parsearon bien (las demás se descartan como «formato inválido»)."""
    verif = [r for r in registro if not r.get("etapa")]
    invalidas = [r for r in verif if str(r.get("motivo", "")).startswith("formato inválido")]
    return {"pares": len(verif), "json_ok": sum(1 for r in verif if r.get("veredicto")), "json_invalido": len(invalidas), **gasto}


# --- Estimación previa de costo (sin API) ---

def estimar_costo(rutas_locales: list, modelo: str, thinking: bool = False) -> dict:
    """Pares (los fragmentos de secciones[] de cada JSON de recuperación) y costo estimado en USD de verificarlos con `modelo`: tokens por par medidos con Qwen3-32B
    en v1 (config.NUBE_TOKENS_POR_PAR; con razonamiento si thinking o si el modelo lo tiene fijo) por el precio del modelo. Es una estimación, no un tope."""
    pares = []
    for ruta in rutas_locales:
        with open(ruta, encoding="utf-8") as f:
            pares.append(len(pares_de_json(json.load(f))))
    por_par, tokens = costo_por_par(modelo, thinking)
    return {"pares_por_oferta": pares, "pares": sum(pares), "usd_por_par": por_par, "usd": sum(pares) * por_par, "tokens_por_par": tokens}


def costo_por_par(modelo: str, thinking: bool = False) -> tuple:
    """(USD estimados por par, (tokens de entrada, tokens de salida) por par) con config.NUBE_TOKENS_POR_PAR y el precio del modelo."""
    entrada, salida = config.NUBE_TOKENS_POR_PAR["con_razonamiento" if (thinking or modelo in config.NUBE_MODELOS_RAZONAMIENTO_FIJO) else "sin_razonamiento"]
    precios = config.PRECIOS_NUBE[modelo]
    return (entrada * precios["entrada"] + salida * precios["salida"]) / 1_000_000, (entrada, salida)


# --- Reporte ---

def sufijo_modelo(proveedor: str, modelo: str) -> str:
    return re.sub(r"[^a-z0-9.\-]+", "-", f"{proveedor}-{modelo.split('/')[-1]}".lower()).strip("-")


def sufijo_corrida(proveedor: str, modelo: str, thinking: bool, perfil=None, max_pares=None) -> str:
    """Sufijo del nombre de salida: modelo, -thinking, perfil de recuperación (si el JSON local lo trae) y -humoN. Todo en [a-z0-9.-]: evaluar.py deduce la oferta del nombre."""
    return sufijo_modelo(proveedor, modelo) + ("-thinking" if thinking else "") + (f"-{perfil}" if perfil else "") + (f"-humo{max_pares}" if max_pares else "")


def _unir_llamadas(resultados: list) -> Llamadas:
    total = Llamadas({"verificacion": 0, "clasificacion": 0, "comentario": 0, "lista": 0, "correccion_formato": 0})
    for _, r in resultados:
        ll = r["llamadas"]
        for k, v in ll.items():
            if k == "eval_count":
                for tipo, valores in v.items():
                    total.setdefault("eval_count", {}).setdefault(tipo, []).extend(valores)
            else:
                total[k] = total.get(k, 0) + v
        total.detalle += ll.detalle
    return total


def armar_reporte(local, secciones, docs_por_seccion, resultados, lin, modelo, proveedor, concurrencia, gasto_oferta, tiempo_total, thinking, max_pares, detenida,
                  normalizaciones=0, formatos=None) -> RiskReport:
    brechas = [b for _, r in resultados for b in r["brechas"]]
    alertas = [a for _, r in resultados for a in r["alertas"]]
    registro = [x for _, r in resultados for x in r["registro"]]
    riesgos, solicitudes, resumen = clasificacion.armar_salidas(brechas, lin["criterios"])
    com = comentario.generar_comentario(resumen, riesgos, None)
    resumen.update(comentario_general=com["texto"], origen_comentario=com["origen"])
    llamadas = _unir_llamadas(resultados)
    hardware = {"gpu": None, "vram": None}
    costo_comp = costo.resumen_costo(llamadas.detalle, tiempo_total, f"{proveedor}:{modelo}", hardware)
    costo_comp.update(proveedor=proveedor, concurrencia=concurrencia, costo_usd=round(gasto_oferta["usd"], 6), tokens_cacheados=gasto_oferta["cacheados"],
                      llamadas_cobradas=gasto_oferta["llamadas"], presupuesto_usd=config.PRESUPUESTO_USD, detenida_por_presupuesto=detenida,
                      normalizaciones_formato=normalizaciones, formato_respuesta=formatos or {})
    fragmentos = {}
    for docs in docs_por_seccion.values():
        for d in docs:
            m = d.metadata
            fragmentos.setdefault((m.get("norma"), m.get("articulo"), m.get("parte")),
                                  SourceChunk(contenido=d.page_content, nombre_documento_fuente=m.get("fuente", "Desconocido"), numero_pagina=m.get("pagina", -1)))
    por_seccion = [r["t_sec"] for _, r in resultados]
    cfg = dict(local.get("configuracion_analisis") or {})
    cfg.update(modelo_llm_usado=f"{proveedor}:{modelo}", display_name_modelo=f"{modelo} ({proveedor}, nube)", temperature=0 if not thinking else config.VERIF_TEMPERATURE,
               seed=config.OLLAMA_SEED, thinking_verificacion=bool(thinking), razonamiento_esfuerzo=config.NUBE_MODELOS_RAZONAMIENTO_FIJO.get(modelo),
               recuperacion_reusada=True, max_pares=max_pares,
               huella_pares=huella_recuperacion.huella_de_pares(local.get("secciones") or []),
               llamadas_llm={k: v for k, v in llamadas.items() if k in ("verificacion", "clasificacion", "comentario", "correccion_formato")},
               llamadas_fallidas=llamadas.get("fallidas", 0), costo_computacional=costo_comp, hardware=hardware, llamadas_detalle=llamadas.detalle,
               tokens_generados_por_tipo=_estadisticas_tokens(llamadas), tiempos_s={"total": round(tiempo_total, 2), "por_seccion": por_seccion})
    return RiskReport(
        riesgos_identificados=[], fragmentos_fuente=list(fragmentos.values()), respuesta_cruda_llm=LLMResponse(riesgos_identificados=[]).model_dump_json(indent=2),
        registro_brechas=brechas, riesgos=riesgos, solicitudes=solicitudes, alertas=alertas, resumen_ejecutivo=resumen,
        lineamientos={"huella": lin["huella"], "caracteres_criterios": len(lin["texto_para_el_modelo"]), "documentos": lin["documentos"]},
        secciones=[SeccionInforme(**s) for s in local.get("secciones") or []], registro_tecnico=registro, configuracion_analisis=cfg)


def buscar_pdf(nombre: str):
    for carpeta, _, archivos in os.walk(config.DIRECTORIO_PROYECTO_ANALIZAR):
        if nombre in archivos:
            return os.path.join(carpeta, nombre)
    return None


def correr_oferta(ruta_local, ruta_pdf, cliente_verif, cliente_clasif, gasto, lin, indice, proveedor, modelo, concurrencia, thinking, max_pares, salida_dir=None) -> dict:
    with open(ruta_local, encoding="utf-8") as f:
        local = json.load(f)
    pdf = ruta_pdf or buscar_pdf(local.get("nombre_archivo_original") or "")
    if not pdf:
        raise AnalisisError(f"No se encontró la oferta «{local.get('nombre_archivo_original')}» bajo {config.DIRECTORIO_PROYECTO_ANALIZAR}: indicala con --pdf.")
    t0 = time.perf_counter()
    secciones = document_utils.dividir_en_secciones(document_utils.extraer_texto_oferta(pdf))
    if [(s["id"], s["titulos"]) for s in secciones] != [(s["id"], s["titulos"]) for s in local.get("secciones") or []]:
        raise AnalisisError(f"La división en secciones de {os.path.basename(pdf)} no coincide con la del JSON local: no es la misma oferta.")
    avisos = []
    docs_por_seccion = {s["id"]: documentos_de_seccion(s.get("fragmentos") or [], indice, avisos) for s in local["secciones"]}
    docs_por_seccion = limitar_pares(docs_por_seccion, [s["id"] for s in secciones], max_pares)
    if avisos:
        logger.warning(f"{len(avisos)} artículos con varias partes: el JSON local no dice cuál se verificó, se usa la primera.")
    antes, normalizaciones_antes = gasto.foto(), normalizaciones_formato()
    resultados = ejecutar_secciones(secciones, docs_por_seccion, cliente_verif, cliente_clasif, lin, concurrencia)
    detenida = any(r["incompleta"] for _, r in resultados)
    despues = gasto.foto()
    gasto_oferta = {k: despues[k] - antes[k] for k in ("entrada", "salida", "cacheados", "llamadas", "usd")}
    reporte = armar_reporte(local, secciones, docs_por_seccion, resultados, lin, modelo, proveedor, concurrencia, gasto_oferta, time.perf_counter() - t0,
                            thinking, max_pares, detenida, normalizaciones_formato() - normalizaciones_antes,
                            {"verificacion": cliente_verif.formato, "clasificacion": cliente_clasif.formato})
    reporte.configuracion_analisis["recuperacion_json_sha256"] = huella_recuperacion.sha256_archivo(ruta_local)      # el archivo de recuperación que se reusó
    perfil = (local.get("configuracion_analisis") or {}).get("perfil_recuperacion")    # solo los JSON de scripts.recuperar lo traen
    sufijo = sufijo_corrida(proveedor, modelo, thinking, perfil, max_pares)
    marca = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{sufijo}"
    ruta_html = _guardar_y_generar_dashboard(reporte, os.path.basename(pdf), marca, carpeta_base=salida_dir)
    ruta_json = os.path.join(os.path.dirname(os.path.join(config.PROJECT_ROOT, ruta_html)), os.path.basename(ruta_html).replace("dashboard_", "analisis_riesgos_", 1)[:-5] + ".json")
    return {"oferta": os.path.basename(pdf), "html": ruta_html, "json": ruta_json if os.path.isfile(ruta_json) else None, "gasto": gasto_oferta, "detenida": detenida,
            "resumen": resumen_humo(reporte.registro_tecnico, gasto_oferta), "brechas": len(reporte.registro_brechas), "riesgos": len(reporte.riesgos), "alertas": len(reporte.alertas)}


# --- Reintento de los pares sin respuesta válida (--reintentar-fallidas) ---

ESTADOS_SECCION_CAIDA = ("seccion_fallida", "presupuesto_agotado")
SUFIJO_REINTENTO = "-reintento"


def _clave_par(x) -> tuple:
    """(norma, artículo) de un fragmento, un registro, una alerta o una brecha."""
    return (str(x.get("norma") or ""), str(x.get("articulo") or ""))


def es_par_fallido(r: dict) -> bool:
    """¿Este registro técnico es de un par sin respuesta válida? Verificación: agotó los reintentos (tiempo_agotado: 429, 5xx, timeout o corte por largo) o el formato
    siguió inválido tras el reintento de formato (descartada, sin veredicto). Clasificación: agotó los reintentos o el formato falló (clasificacion_fallida)."""
    estado = r.get("estado")
    if r.get("etapa") == "clasificacion":
        return estado in ("tiempo_agotado", "clasificacion_fallida")
    if r.get("etapa"):
        return False
    return estado == "tiempo_agotado" or (estado == "descartada" and r.get("veredicto") is None)


def pares_fallidos(secciones: list, registro: list) -> dict:
    """{id de sección: [(norma, artículo)]} de los pares sin respuesta válida, en el orden de secciones[].fragmentos. Una sección caída entera (seccion_fallida, p. ej. por un
    402 o un error imprevisto; presupuesto_agotado) aporta todos sus pares: se perdió su resultado completo, también el de los pares que ya habían respondido."""
    caidas = {r.get("seccion") for r in registro if r.get("estado") in ESTADOS_SECCION_CAIDA}
    sueltos = {(r.get("seccion"), *_clave_par(r)) for r in registro if es_par_fallido(r)}
    salida = {}
    for s in secciones:
        for f in s.get("fragmentos") or []:
            if s["id"] in caidas or (s["id"], *_clave_par(f)) in sueltos:
                salida.setdefault(s["id"], {})[_clave_par(f)] = None
    return {sid: list(claves) for sid, claves in salida.items()}


def contar_pares(fallidos: dict) -> int:
    return sum(len(v) for v in fallidos.values())


def comprobar_coincidencia(original: dict, local: dict, proveedor: str, modelo: str, thinking: bool, lin: dict) -> list:
    """Diferencias entre la corrida original y lo que pide el reintento (lista vacía = coinciden): huella de pares y perfil de recuperación (contra el JSON de recuperación),
    modelo, proveedor, razonamiento, esfuerzo, seed y huella de los lineamientos. No se reintenta un parcial ni una prueba de humo."""
    cfg = original.get("configuracion_analisis") or {}
    cfg_local = local.get("configuracion_analisis") or {}
    problemas = []
    if cfg.get("parcial"):
        problemas.append("el JSON es un parcial (_parcial), no una corrida completa")
    if cfg.get("max_pares"):
        problemas.append(f"es una prueba de humo (max_pares={cfg['max_pares']})")
    if not cfg.get("recuperacion_reusada"):
        problemas.append("no es una corrida de scripts.nube (sin recuperación reusada)")
    comparaciones = [
        ("modelo", cfg.get("modelo_llm_usado"), f"{proveedor}:{modelo}"),
        ("proveedor", (cfg.get("costo_computacional") or {}).get("proveedor"), proveedor),
        ("razonamiento (--thinking)", bool(cfg.get("thinking_verificacion")), bool(thinking)),
        ("esfuerzo de razonamiento", cfg.get("razonamiento_esfuerzo"), config.NUBE_MODELOS_RAZONAMIENTO_FIJO.get(modelo)),
        ("seed", cfg.get("seed"), config.OLLAMA_SEED),
        ("huella de pares", cfg.get("huella_pares"), huella_recuperacion.huella_de_pares(local.get("secciones") or [])),
        ("perfil de recuperación", cfg.get("perfil_recuperacion"), cfg_local.get("perfil_recuperacion")),
        ("huella de los lineamientos", (original.get("lineamientos") or {}).get("huella"), lin["huella"])]
    problemas += [f"{nombre}: la corrida original tiene «{o}» y el reintento usaría «{n}»" for nombre, o, n in comparaciones if o != n]
    return problemas


def fusionar(original: dict, resultados: list, fallidos: dict, orden_secciones: list) -> tuple:
    """Fusiona el reintento con la corrida original. Una sección del reintento que se completó (sin presupuesto_agotado ni seccion_fallida) reemplaza, en registro_brechas,
    alertas y registro_tecnico, todo lo de sus pares reintentados (y la marca de sección caída); lo nuevo va al final del bloque de su sección. Lo que ya estaba bien queda
    igual y en el mismo orden. Una sección del reintento que no se completó no reemplaza nada: sus pares siguen como estaban (fallidos).
    Devuelve ({registro_brechas, alertas, registro_tecnico}, [ids de sección del reintento que no se completaron])."""
    completas = {sid: r for sid, r in resultados if not r["incompleta"] and not any(x.get("estado") in ESTADOS_SECCION_CAIDA for x in r["registro"])}
    sin_completar = [sid for sid, _ in resultados if sid not in completas]

    def reemplazado(x):
        sid = x.get("seccion")
        return sid in completas and (_clave_par(x) in fallidos.get(sid, []) or x.get("estado") in ESTADOS_SECCION_CAIDA)

    salida = {}
    for campo, nuevo in (("registro_brechas", "brechas"), ("alertas", "alertas"), ("registro_tecnico", "registro")):
        quedan = [x for x in original.get(campo) or [] if not reemplazado(x)]
        bloques, sueltos = {sid: [] for sid in orden_secciones}, []
        for x in quedan:
            bloques[x.get("seccion")].append(x) if x.get("seccion") in bloques else sueltos.append(x)
        for sid, r in completas.items():
            bloques.setdefault(sid, []).extend(r[nuevo])
        salida[campo] = [x for sid in bloques for x in bloques[sid]] + sueltos
    return salida, sin_completar


def armar_reporte_fusionado(original, local, secciones, docs_por_seccion, fusion, resultados, lin, modelo, proveedor, concurrencia, gasto_r, tiempo_r, thinking,
                            detenida, normalizaciones, formatos, reintento: dict) -> RiskReport:
    """El reporte del conjunto fusionado: riesgos, solicitudes, resumen y comentario se rearman con armar_reporte (mismas reglas que la corrida normal) sobre las brechas,
    alertas y registro fusionados. Costo, tokens, llamadas y tiempo suman la corrida original y el reintento (el detalle de llamadas va completo); llamadas_fallidas
    refleja el estado final (pares que siguen sin respuesta válida) y el bloque «reintento» guarda la historia."""
    llamadas_r = _unir_llamadas(resultados)
    unico = [("fusion", {"brechas": fusion["registro_brechas"], "alertas": fusion["alertas"], "registro": fusion["registro_tecnico"], "llamadas": llamadas_r, "t_sec": {}})]
    reporte = armar_reporte(local, secciones, docs_por_seccion, unico, lin, modelo, proveedor, concurrencia, gasto_r, tiempo_r, thinking, None, detenida, normalizaciones, formatos)
    cfg_o, cfg = original.get("configuracion_analisis") or {}, reporte.configuracion_analisis
    cc_o = cfg_o.get("costo_computacional") or {}
    detalle = list(cfg_o.get("llamadas_detalle") or []) + llamadas_r.detalle
    tiempo_total = ((cfg_o.get("tiempos_s") or {}).get("total") or 0) + tiempo_r
    suma = lambda campo, valor: (cc_o.get(campo) or 0) + valor
    costo_comp = costo.resumen_costo(detalle, tiempo_total, f"{proveedor}:{modelo}", cfg["hardware"])
    costo_comp.update(proveedor=proveedor, concurrencia=concurrencia, costo_usd=round(suma("costo_usd", gasto_r["usd"]), 6), tokens_cacheados=suma("tokens_cacheados", gasto_r["cacheados"]),
                      llamadas_cobradas=suma("llamadas_cobradas", gasto_r["llamadas"]), presupuesto_usd=config.PRESUPUESTO_USD, detenida_por_presupuesto=detenida,
                      normalizaciones_formato=suma("normalizaciones_formato", normalizaciones), formato_respuesta=formatos or {}, llamadas_fallidas=reintento["pares_siguen_fallidos"])
    llamadas_o = cfg_o.get("llamadas_llm") or {}
    cfg.update(llamadas_detalle=detalle, costo_computacional=costo_comp, llamadas_fallidas=reintento["pares_siguen_fallidos"],
               llamadas_llm={k: llamadas_o.get(k, 0) + v for k, v in cfg["llamadas_llm"].items()}, tokens_generados_por_tipo=cfg_o.get("tokens_generados_por_tipo"),
               tiempos_s={"total": round(tiempo_total, 2), "por_seccion": (cfg_o.get("tiempos_s") or {}).get("por_seccion") or [], "reintento": [r["t_sec"] for _, r in resultados]},
               reintento=reintento)
    return reporte


def _leer_json(ruta: str) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _pendientes_de_reintento(ruta_resultado: str, ruta_local: str, proveedor: str, modelo: str, thinking: bool, lin: dict) -> tuple:
    """(original, local, pares fallidos) si la corrida original coincide con lo que pide el reintento; si no, AnalisisError con todas las diferencias (no arranca)."""
    original, local = _leer_json(ruta_resultado), _leer_json(ruta_local)
    problemas = comprobar_coincidencia(original, local, proveedor, modelo, thinking, lin)
    if problemas:
        raise AnalisisError(f"{os.path.basename(ruta_resultado)} no coincide con el reintento pedido; no se arranca:\n  - " + "\n  - ".join(problemas))
    return original, local, pares_fallidos(local.get("secciones") or [], original.get("registro_tecnico") or [])


def reintentar_oferta(ruta_resultado, ruta_local, ruta_pdf, cliente_verif, cliente_clasif, gasto, lin, indice, proveedor, modelo, concurrencia, thinking) -> dict:
    """Vuelve a llamar al modelo solo para los pares sin respuesta válida de una corrida de scripts.nube, con los mismos prompts, contexto y parámetros, y guarda el conjunto
    fusionado como un JSON nuevo (y su dashboard) con el sufijo -reintento junto al original. Los pares que estaban bien no se vuelven a llamar ni se tocan."""
    original, local, fallidos = _pendientes_de_reintento(ruta_resultado, ruta_local, proveedor, modelo, thinking, lin)
    n = contar_pares(fallidos)
    salida = {"original": os.path.basename(ruta_resultado), "reintentados": n, "siguen_fallidos": 0, "json": None, "html": None, "gasto": None, "detenida": False}
    if not n:
        logger.info(f"{os.path.basename(ruta_resultado)}: no hay pares sin respuesta válida; no se llama al modelo ni se escribe nada.")
        return salida
    pdf = ruta_pdf or buscar_pdf(local.get("nombre_archivo_original") or "")
    if not pdf:
        raise AnalisisError(f"No se encontró la oferta «{local.get('nombre_archivo_original')}» bajo {config.DIRECTORIO_PROYECTO_ANALIZAR}: indicala con --pdf.")
    secciones = document_utils.dividir_en_secciones(document_utils.extraer_texto_oferta(pdf))
    if [(s["id"], s["titulos"]) for s in secciones] != [(s["id"], s["titulos"]) for s in local.get("secciones") or []]:
        raise AnalisisError(f"La división en secciones de {os.path.basename(pdf)} no coincide con la del JSON de recuperación: no es la misma oferta.")
    docs_todos = {s["id"]: documentos_de_seccion(s.get("fragmentos") or [], indice) for s in local["secciones"]}
    docs_reintento = {sid: [d for d in docs if _clave_par(d.metadata) in fallidos.get(sid, [])] for sid, docs in docs_todos.items()}
    # mismo contexto: el texto de cada artículo a reintentar tiene que ser el que recibió la corrida original (si no, se reindexó la KB entre medio)
    contenidos = {f.get("contenido") for f in original.get("fragmentos_fuente") or []}
    distintos = sorted({f"{d.metadata.get('norma')} Art. {d.metadata.get('articulo')}" for docs in docs_reintento.values() for d in docs if d.page_content not in contenidos})
    if distintos:
        raise AnalisisError(f"El texto en ChromaDB de {', '.join(distintos)} no es el que usó la corrida original (¿se reindexó la KB?); no se arranca.")
    if (local_sha := huella_recuperacion.sha256_archivo(ruta_local)) != (original.get("configuracion_analisis") or {}).get("recuperacion_json_sha256"):
        logger.warning("El archivo de recuperación no es byte a byte el de la corrida original, aunque los pares y el perfil coinciden; se sigue.")
    logger.info(f"{os.path.basename(ruta_resultado)}: se reintentan {n} pares en {len(fallidos)} secciones; los demás no se tocan.")
    antes, normalizaciones_antes, t0 = gasto.foto(), normalizaciones_formato(), time.perf_counter()
    resultados = ejecutar_secciones(secciones, docs_reintento, cliente_verif, cliente_clasif, lin, concurrencia)
    tiempo_r, despues = time.perf_counter() - t0, gasto.foto()
    gasto_r = {k: despues[k] - antes[k] for k in ("entrada", "salida", "cacheados", "llamadas", "usd")}
    detenida = any(r["incompleta"] for _, r in resultados)
    fusion, sin_completar = fusionar(original, resultados, fallidos, [s["id"] for s in local["secciones"]])
    siguen = contar_pares(pares_fallidos(local["secciones"], fusion["registro_tecnico"]))
    cfg_o = original.get("configuracion_analisis") or {}
    reintento = {"json_original": os.path.basename(ruta_resultado), "sha256_original": huella_recuperacion.sha256_archivo(ruta_resultado),
                 "fecha": datetime.datetime.now().isoformat(timespec="seconds"), "pares_reintentados": n, "pares_siguen_fallidos": siguen, "pares_recuperados": n - siguen,
                 "secciones_reintentadas": list(fallidos), "secciones_sin_completar": sin_completar, "llamadas_fallidas_original": cfg_o.get("llamadas_fallidas"),
                 "intentos_fallidos_reintento": _unir_llamadas(resultados).get("fallidas", 0), "costo_usd_reintento": round(gasto_r["usd"], 6), "tiempo_s_reintento": round(tiempo_r, 2)}
    reporte = armar_reporte_fusionado(original, local, secciones, docs_todos, fusion, resultados, lin, modelo, proveedor, concurrencia, gasto_r, tiempo_r, thinking, detenida,
                                      normalizaciones_formato() - normalizaciones_antes, {"verificacion": cliente_verif.formato, "clasificacion": cliente_clasif.formato}, reintento)
    reporte.configuracion_analisis["recuperacion_json_sha256"] = local_sha
    sufijo = sufijo_corrida(proveedor, modelo, thinking, (local.get("configuracion_analisis") or {}).get("perfil_recuperacion")) + SUFIJO_REINTENTO
    marca = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{sufijo}"
    carpeta_base = os.path.dirname(os.path.dirname(os.path.abspath(ruta_resultado)))      # junto al JSON original (<base>/<oferta>/)
    ruta_html = _guardar_y_generar_dashboard(reporte, os.path.basename(pdf), marca, carpeta_base=carpeta_base)
    ruta_json = os.path.join(os.path.dirname(os.path.join(config.PROJECT_ROOT, ruta_html)), os.path.basename(ruta_html).replace("dashboard_", "analisis_riesgos_", 1)[:-5] + ".json")
    salida.update(siguen_fallidos=siguen, json=ruta_json if os.path.isfile(ruta_json) else None, html=ruta_html, gasto=gasto_r, detenida=detenida, sin_completar=sin_completar)
    return salida


def estimar_reintento(rutas_resultado: list, rutas_locales: list, proveedor: str, modelo: str, thinking: bool, lin: dict) -> dict:
    """Pares sin respuesta válida de cada corrida y costo estimado de reintentarlos (mismo costo por par que --estimar). Sin API; también comprueba la coincidencia."""
    pares = [contar_pares(_pendientes_de_reintento(r, l, proveedor, modelo, thinking, lin)[2]) for r, l in zip(rutas_resultado, rutas_locales)]
    por_par, tokens = costo_por_par(modelo, thinking)
    return {"pares_por_oferta": pares, "pares": sum(pares), "usd_por_par": por_par, "usd": sum(pares) * por_par, "tokens_por_par": tokens}


def _crear_clientes(a, gasto):
    """Clientes de verificación y clasificación: json_schema estricto como el format= de Ollama; si el proveedor lo rechaza, cae a json_object."""
    def cliente_de(esquema):
        def llm(e): return rag_components.get_llm_openai_compatible(a.proveedor, a.modelo, razonamiento=a.thinking, esquema=e)
        return ClienteNube(llm(esquema), gasto, respaldo=llm(None), nombre=esquema.__name__, sistema=config.NUBE_MODELOS_RAZONAMIENTO_FIJO.get(a.modelo))
    return cliente_de(VerificacionArticulo), cliente_de(ClasificacionRiesgo)


def _main_reintento(a) -> int:
    """--reintentar-fallidas: comprueba la coincidencia con cada corrida original (si no coincide, no arranca), y con --estimar solo cuenta los pares sin respuesta y estima
    el costo; si no, los reintenta con el mismo tope de gasto de siempre (config.PRESUPUESTO_USD por invocación)."""
    if len(a.reintentar_fallidas) != len(a.reusar_recuperacion):
        print("--reintentar-fallidas tiene que traer un JSON de resultados por cada JSON de --reusar-recuperacion, en el mismo orden.", file=sys.stderr)
        return 2
    if a.max_pares:
        print("--max-pares no se combina con --reintentar-fallidas: se reintentan todos los pares fallidos o ninguno.", file=sys.stderr)
        return 2
    try:
        lin = lineamientos.cargar_lineamientos(config.DIRECTORIO_LINEAMIENTOS)
        if a.estimar:
            e = estimar_reintento(a.reintentar_fallidas, a.reusar_recuperacion, a.proveedor, a.modelo, a.thinking, lin)
            print(f"{a.modelo}: {e['pares']} pares sin respuesta válida ({', '.join(map(str, e['pares_por_oferta']))} por oferta), costo estimado del reintento {e['usd']:.4f} USD "
                  f"({e['tokens_por_par'][0]} + {e['tokens_por_par'][1]} tokens por par; tope de la corrida {config.PRESUPUESTO_USD} USD por invocación)")
            return 0
        config.THINKING_VERIFICACION = a.thinking
        gasto = Gasto(config.PRECIOS_NUBE[a.modelo], config.PRESUPUESTO_USD)
        cliente_verif, cliente_clasif = _crear_clientes(a, gasto)
        indice = indice_de_articulos(_abrir_chroma().get(include=["documents", "metadatas"]))
        salidas = []
        for i, (ruta, local) in enumerate(zip(a.reintentar_fallidas, a.reusar_recuperacion)):
            if salidas and salidas[-1]["detenida"]:
                break
            salidas.append(reintentar_oferta(ruta, local, a.pdf[i] if a.pdf else None, cliente_verif, cliente_clasif, gasto, lin, indice, a.proveedor, a.modelo,
                                             a.concurrencia, a.thinking))
    except (AnalisisError, ValueError, lineamientos.LineamientosError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    for s in salidas:
        print(f"\n{s['original']}: {s['reintentados']} pares reintentados | recuperados {s['reintentados'] - s['siguen_fallidos']} | siguen fallidos {s['siguen_fallidos']}")
        if s["gasto"]:
            print(f"  costo del reintento {s['gasto']['usd']:.4f} USD | JSON fusionado: {s['json']}\n  Dashboard: {s['html']}")
        if s.get("sin_completar"):
            print(f"  Secciones del reintento que no se completaron (quedan como estaban): {', '.join(s['sin_completar'])}")
        if s["detenida"]:
            print("  DETENIDA: se alcanzó el presupuesto; los pares que no llegaron a reintentarse siguen fallidos.")
    print(f"\nGasto total del reintento: {gasto.usd:.4f} USD de {config.PRESUPUESTO_USD} USD")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Verificación y clasificación en la nube sobre los mismos pares de una corrida local.")
    p.add_argument("--reusar-recuperacion", nargs="+", required=True, metavar="JSON_LOCAL", help="JSON(s) de la corrida local con la recuperación a reusar")
    p.add_argument("--pdf", nargs="+", help="oferta de cada JSON, en el mismo orden (por defecto se busca por nombre bajo datos/ProyectoAnalizar)")
    p.add_argument("--proveedor", default=config.NUBE_PROVEEDOR, choices=sorted(config.PERFILES_NUBE))
    p.add_argument("--modelo", default=config.NUBE_MODELO)
    p.add_argument("--thinking", action="store_true", help="activa el razonamiento (solo para un experimento aparte)")
    p.add_argument("--max-pares", type=int, help="corre solo los primeros N pares de cada oferta (prueba de humo)")
    p.add_argument("--concurrencia", type=int, default=config.NUBE_CONCURRENCIA)
    p.add_argument("--estimar", action="store_true", help="solo imprime los pares y el costo estimado (sin llamar a la API ni leer la clave) y sale")
    p.add_argument("--salida-dir", help="carpeta base de la salida (<carpeta>/<oferta>/); por defecto datos/Resultados. Para corridas que no deben entrar en la tabla "
                                        "oficial (p. ej. la repetición de estabilidad): los «auto» de config_reeval.json solo buscan en datos/Resultados/<oferta>/")
    p.add_argument("--reintentar-fallidas", nargs="+", metavar="JSON_RESULTADO",
                   help="JSON(s) de resultados de una corrida de scripts.nube, uno por cada JSON de --reusar-recuperacion y en el mismo orden: vuelve a llamar solo a los pares sin "
                        "respuesta válida y escribe <...>-reintento.json con el conjunto fusionado. Con --estimar solo cuenta esos pares y estima el costo")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")

    if a.modelo not in config.PRECIOS_NUBE:
        print(f"El modelo «{a.modelo}» no tiene precio en config.PRECIOS_NUBE: no se arranca.", file=sys.stderr)
        return 2
    if a.pdf and len(a.pdf) != len(a.reusar_recuperacion):
        print("--pdf tiene que traer una oferta por cada JSON de --reusar-recuperacion.", file=sys.stderr)
        return 2
    if a.reintentar_fallidas:
        return _main_reintento(a)
    if a.estimar:
        e = estimar_costo(a.reusar_recuperacion, a.modelo, a.thinking)
        print(f"{a.modelo}{' (razonamiento)' if a.thinking else ''}: {e['pares']} pares ({', '.join(map(str, e['pares_por_oferta']))} por oferta), "
              f"costo estimado {e['usd']:.2f} USD ({e['tokens_por_par'][0]} + {e['tokens_por_par'][1]} tokens por par; tope de la corrida {config.PRESUPUESTO_USD} USD por invocación)")
        return 0
    try:
        lin = lineamientos.cargar_lineamientos(config.DIRECTORIO_LINEAMIENTOS)
        config.THINKING_VERIFICACION = a.thinking
        gasto = Gasto(config.PRECIOS_NUBE[a.modelo], config.PRESUPUESTO_USD)
        cliente_verif, cliente_clasif = _crear_clientes(a, gasto)
        indice = indice_de_articulos(_abrir_chroma().get(include=["documents", "metadatas"]))
        salidas, fallos = [], []
        for i, ruta in enumerate(a.reusar_recuperacion):
            if salidas and salidas[-1]["detenida"]:
                break
            logger.info(f"--- {os.path.basename(ruta)} con {a.proveedor}:{a.modelo} (concurrencia {a.concurrencia}) ---")
            try:
                salidas.append(correr_oferta(ruta, a.pdf[i] if a.pdf else None, cliente_verif, cliente_clasif, gasto, lin, indice, a.proveedor, a.modelo, a.concurrencia, a.thinking, a.max_pares,
                                             salida_dir=os.path.abspath(a.salida_dir) if a.salida_dir else None))
            except (AnalisisError, ValueError):
                raise
            except Exception as e:      # imprevisto al armar o guardar una oferta: se avisa y se sigue con la siguiente
                logger.exception(f"{os.path.basename(ruta)}: error inesperado, no se guardó esta oferta ({type(e).__name__}: {e})")
                fallos.append(os.path.basename(ruta))
    except (AnalisisError, ValueError, lineamientos.LineamientosError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    for s in salidas:
        r = s["resumen"]
        print(f"\n{s['oferta']}: {r['pares']} pares | JSON bien parseado {r['json_ok']}/{r['pares']} | brechas {s['brechas']} | riesgos {s['riesgos']} | alertas {s['alertas']}")
        print(f"  tokens: {s['gasto']['entrada']} de entrada ({s['gasto']['cacheados']} cacheados), {s['gasto']['salida']} de salida | costo {s['gasto']['usd']:.4f} USD")
        if s.get("json"):
            print(f"  JSON: {s['json']}")
        print(f"  Dashboard: {s['html']}" + ("\n  DETENIDA: se alcanzó el presupuesto; las secciones incompletas figuran como presupuesto_agotado en el registro técnico." if s["detenida"] else ""))
    print(f"\nGasto total de la corrida: {gasto.usd:.4f} USD de {config.PRESUPUESTO_USD} USD")
    if fallos:
        print(f"Ofertas que fallaron sin guardarse: {', '.join(fallos)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
