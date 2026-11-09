# scripts/nube.py
"""Experimento de diagnóstico: verificación y clasificación con un modelo en la nube (API compatible con OpenAI) sobre EXACTAMENTE los mismos
pares (sección, norma, artículo) que una corrida local, para aislar el efecto del tamaño del modelo. No cambia prompts, reglas, criterios, motor
ni recuperación: la recuperación se toma del JSON local y el texto de cada artículo se busca en ChromaDB por metadatos (sin embeddings ni reranker).
El comentario general usa la plantilla (sin llamada al modelo). Las secciones corren en paralelo; los pares de una sección, en orden.

Uso:
  python -m scripts.nube --reusar-recuperacion <json_local> [<json_local> ...] [--proveedor deepinfra] [--modelo Qwen/Qwen3-32B]
         [--max-pares N] [--thinking] [--concurrencia N] [--pdf <oferta> ...]
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
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from . import clasificacion, comentario, config, costo, document_utils, lineamientos, rag_components
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
    def __init__(self, llm, gasto: Gasto, respaldo=None, nombre: str = ""):
        """respaldo: cliente con json_object, al que se cae (y se avisa) si el proveedor rechaza el json_schema con un 400 o 422."""
        self.llm, self.gasto, self.respaldo, self.nombre, self.usa_respaldo = llm, gasto, respaldo, nombre, False

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
            mensaje = self._llamar(entrada)
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
    llamadas, t_sec = Llamadas({"verificacion": 0, "clasificacion": 0, "comentario": 0, "lista": 0}), {"id": seccion["id"]}
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


# --- Reporte ---

def sufijo_modelo(proveedor: str, modelo: str) -> str:
    return re.sub(r"[^a-z0-9.\-]+", "-", f"{proveedor}-{modelo.split('/')[-1]}".lower()).strip("-")


def _unir_llamadas(resultados: list) -> Llamadas:
    total = Llamadas({"verificacion": 0, "clasificacion": 0, "comentario": 0, "lista": 0})
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
               seed=config.OLLAMA_SEED, thinking_verificacion=bool(thinking), recuperacion_reusada=True, max_pares=max_pares,
               llamadas_llm={k: v for k, v in llamadas.items() if k in ("verificacion", "clasificacion", "comentario")},
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


def correr_oferta(ruta_local, ruta_pdf, cliente_verif, cliente_clasif, gasto, lin, indice, proveedor, modelo, concurrencia, thinking, max_pares) -> dict:
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
    sufijo = sufijo_modelo(proveedor, modelo) + (f"-humo{max_pares}" if max_pares else "")
    marca = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{sufijo}"
    ruta_html = _guardar_y_generar_dashboard(reporte, os.path.basename(pdf), marca)
    return {"oferta": os.path.basename(pdf), "html": ruta_html, "gasto": gasto_oferta, "detenida": detenida,
            "resumen": resumen_humo(reporte.registro_tecnico, gasto_oferta), "brechas": len(reporte.registro_brechas), "riesgos": len(reporte.riesgos), "alertas": len(reporte.alertas)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Verificación y clasificación en la nube sobre los mismos pares de una corrida local.")
    p.add_argument("--reusar-recuperacion", nargs="+", required=True, metavar="JSON_LOCAL", help="JSON(s) de la corrida local con la recuperación a reusar")
    p.add_argument("--pdf", nargs="+", help="oferta de cada JSON, en el mismo orden (por defecto se busca por nombre bajo datos/ProyectoAnalizar)")
    p.add_argument("--proveedor", default=config.NUBE_PROVEEDOR, choices=sorted(config.PERFILES_NUBE))
    p.add_argument("--modelo", default=config.NUBE_MODELO)
    p.add_argument("--thinking", action="store_true", help="activa el razonamiento (solo para un experimento aparte)")
    p.add_argument("--max-pares", type=int, help="corre solo los primeros N pares de cada oferta (prueba de humo)")
    p.add_argument("--concurrencia", type=int, default=config.NUBE_CONCURRENCIA)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")

    if a.modelo not in config.PRECIOS_NUBE:
        print(f"El modelo «{a.modelo}» no tiene precio en config.PRECIOS_NUBE: no se arranca.", file=sys.stderr)
        return 2
    if a.pdf and len(a.pdf) != len(a.reusar_recuperacion):
        print("--pdf tiene que traer una oferta por cada JSON de --reusar-recuperacion.", file=sys.stderr)
        return 2
    try:
        def cliente_de(esquema):    # json_schema estricto como el format= de Ollama; si el proveedor lo rechaza, cae a json_object
            def llm(e): return rag_components.get_llm_openai_compatible(a.proveedor, a.modelo, razonamiento=a.thinking, esquema=e)
            return ClienteNube(llm(esquema), gasto, respaldo=llm(None), nombre=esquema.__name__)
        lin = lineamientos.cargar_lineamientos(config.DIRECTORIO_LINEAMIENTOS)
        config.THINKING_VERIFICACION = a.thinking
        gasto = Gasto(config.PRECIOS_NUBE[a.modelo], config.PRESUPUESTO_USD)
        cliente_verif, cliente_clasif = cliente_de(VerificacionArticulo), cliente_de(ClasificacionRiesgo)
        indice = indice_de_articulos(_abrir_chroma().get(include=["documents", "metadatas"]))
        salidas, fallos = [], []
        for i, ruta in enumerate(a.reusar_recuperacion):
            if salidas and salidas[-1]["detenida"]:
                break
            logger.info(f"--- {os.path.basename(ruta)} con {a.proveedor}:{a.modelo} (concurrencia {a.concurrencia}) ---")
            try:
                salidas.append(correr_oferta(ruta, a.pdf[i] if a.pdf else None, cliente_verif, cliente_clasif, gasto, lin, indice, a.proveedor, a.modelo, a.concurrencia, a.thinking, a.max_pares))
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
        print(f"  Dashboard: {s['html']}" + ("\n  DETENIDA: se alcanzó el presupuesto; las secciones incompletas figuran como presupuesto_agotado en el registro técnico." if s["detenida"] else ""))
    print(f"\nGasto total de la corrida: {gasto.usd:.4f} USD de {config.PRESUPUESTO_USD} USD")
    if fallos:
        print(f"Ofertas que fallaron sin guardarse: {', '.join(fallos)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
