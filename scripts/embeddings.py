# scripts/embeddings.py
"""Backends de embeddings enchufables: bge-m3 (el actual), qwen3-local (Ollama), deepinfra (Qwen3-Embedding-8B) y gemini (gemini-embedding-2).

Todos devuelven vectores float32 normalizados (L2), de modo que el producto punto es el coseno. Cada backend tiene su caché en disco
(evaluacion/diagnosticos/emb_cache/<modelo>.npz, clave sha1 del texto YA formateado con su prefijo, así una consulta y un documento nunca se mezclan):
un texto ya embebido no vuelve a calcularse ni a pagarse, y con todo en caché no se carga el modelo ni se llama a la API. Antes de cualquier llamada de pago
`preflight` muestra textos, caracteres y costo estimado y pide confirmación.

EmbeddingsBackend adapta un backend a la interfaz de LangChain (embed_documents / embed_query, con `model_name`) para usarlo con Chroma."""
import hashlib
import json
import logging
import os
import time

import numpy as np
from langchain_core.embeddings import Embeddings

from . import config

logger = logging.getLogger(__name__)

BACKENDS = ("bge-m3", "qwen3-local", "deepinfra", "gemini")
DIR_CACHE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "evaluacion", "diagnosticos", "emb_cache"))
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:batchEmbedContents"
ESPERA_MAXIMA_S = 60


def _sha(texto: str) -> str:
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()


def normalizar(vectores) -> np.ndarray:
    """float32 con cada fila de norma 1 (una fila nula queda en ceros)."""
    v = np.asarray(vectores, dtype=np.float32)
    normas = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.where(normas == 0, 1, normas)


def titulo_de_fragmento(texto: str) -> str:
    """Primera línea del fragmento si es el encabezado del artículo ('Art. 4.2. Hormigón...'); si no, 'none'. Es el título de los documentos de Gemini."""
    primera = texto.lstrip().split("\n", 1)[0].strip()
    return primera if primera.startswith("Art.") else "none"


class CacheEmbeddings:
    """Caché npz {sha1 del texto formateado: vector} con escritura atómica, y un .meta.json acumulado (tiempos, tokens y gasto reales)."""

    def __init__(self, ruta: str):
        self.ruta = ruta
        self.vectores = {}
        self.meta = {"documentos_s": 0.0, "consultas_s": 0.0, "n_documentos": 0, "n_consultas": 0, "tokens": 0, "tokens_estimados": 0, "usd": 0.0}
        if os.path.isfile(ruta):
            with np.load(ruta, allow_pickle=False) as f:
                self.vectores = dict(zip((str(c) for c in f["claves"]), f["vectores"]))
        if os.path.isfile(self._ruta_meta):
            with open(self._ruta_meta, encoding="utf-8") as f:
                self.meta.update(json.load(f))

    @property
    def _ruta_meta(self) -> str:
        return os.path.splitext(self.ruta)[0] + ".meta.json"

    def __contains__(self, clave: str) -> bool:
        return clave in self.vectores

    def __getitem__(self, clave: str) -> np.ndarray:
        return self.vectores[clave]

    def agregar(self, claves: list, vectores) -> None:
        self.vectores.update(zip(claves, np.asarray(vectores, dtype=np.float32)))

    def guardar(self) -> None:
        os.makedirs(os.path.dirname(self.ruta), exist_ok=True)
        tmp = self.ruta + ".tmp.npz"
        claves = sorted(self.vectores)
        np.savez(tmp, claves=np.array(claves, dtype="U40"), vectores=np.stack([self.vectores[c] for c in claves]) if claves else np.zeros((0, 0), dtype=np.float32))
        os.replace(tmp, self.ruta)
        with open(self._ruta_meta + ".tmp", "w", encoding="utf-8") as f:
            json.dump(self.meta, f, indent=2)
        os.replace(self._ruta_meta + ".tmp", self._ruta_meta)


class Backend:
    """Base: formatea, cachea, normaliza y mide. Cada subclase implementa _embed (textos ya formateados -> matriz) y, si usa la red, es_api = True."""
    nombre = ""
    es_api = False
    lote = 16
    precio_usd_m = 0.0

    def __init__(self, modelo: str, dir_cache: str = DIR_CACHE):
        self.modelo = modelo
        self.model_name = f"{self.nombre}__{modelo.replace('/', '-').replace(':', '-')}" if self.nombre != "bge-m3" else "bge-m3"
        self.cache = CacheEmbeddings(os.path.join(dir_cache, self.model_name + ".npz"))
        self.esperar = time.sleep       # inyectable en los tests

    # --- formato ---
    def formatear_consulta(self, texto: str) -> str:
        return texto

    def formatear_documento(self, texto: str) -> str:
        return texto

    # --- disponibilidad ---
    def disponible(self) -> tuple:
        """(True, '') o (False, motivo): sin clave, sin servidor o sin el modelo, el backend se saltea con aviso."""
        return True, ""

    # --- núcleo ---
    def _embed(self, textos: list):
        raise NotImplementedError

    def _registrar_uso(self, tokens: int, estimado: bool) -> None:
        self.cache.meta["tokens_estimados" if estimado else "tokens"] += tokens
        self.cache.meta["usd"] += tokens / 1e6 * self.precio_usd_m

    def pendientes(self, formateados: list) -> list:
        """Textos formateados (sin repetir, en orden) que no están en la caché."""
        return list(dict.fromkeys(t for t in formateados if _sha(t) not in self.cache))

    def _vectores(self, formateados: list, tipo: str) -> np.ndarray:
        faltan = self.pendientes(formateados)
        for i in range(0, len(faltan), self.lote):
            lote = faltan[i:i + self.lote]
            t0 = time.perf_counter()
            vecs = normalizar(self._embed(lote))
            self.cache.meta[f"{tipo}_s"] += time.perf_counter() - t0
            self.cache.meta[f"n_{tipo}"] += len(lote)
            self.cache.agregar([_sha(t) for t in lote], vecs)
            self.cache.guardar()        # cada lote queda en disco: si la API falla a mitad, lo hecho no se paga dos veces
        if not formateados:
            return np.zeros((0, 0), dtype=np.float32)
        return np.stack([self.cache[_sha(t)] for t in formateados])

    def embed_documents(self, textos: list) -> np.ndarray:
        return self._vectores([self.formatear_documento(t) for t in textos], "documentos")

    def embed_queries(self, textos: list) -> np.ndarray:
        return self._vectores([self.formatear_consulta(t) for t in textos], "consultas")

    def embed_query(self, texto: str) -> np.ndarray:
        return self.embed_queries([texto])[0]

    def estimar(self, documentos: list = (), consultas: list = ()) -> dict:
        """Lo que quedaría por calcular: textos, caracteres, tokens (caracteres / 3,5) y costo máximo en USD."""
        pendientes = self.pendientes([self.formatear_documento(t) for t in documentos] + [self.formatear_consulta(t) for t in consultas])
        caracteres = sum(len(t) for t in pendientes)
        tokens = int(caracteres / config.EMBEDDING_CHARS_POR_TOKEN)
        return {"textos": len(pendientes), "caracteres": caracteres, "tokens": tokens, "usd": tokens / 1e6 * self.precio_usd_m}


def preflight(backend: Backend, documentos: list = (), consultas: list = (), si: bool = False, entrada=input, salida=print) -> bool:
    """Imprime cuántos textos, caracteres y USD faltan por embeber y pide confirmación antes de llamar a una API (salvo `si`). Sin red o sin pendientes no pregunta."""
    e = backend.estimar(documentos, consultas)
    if not backend.es_api or e["textos"] == 0:
        return True
    salida(f"[{backend.model_name}] por embeber: {e['textos']} textos, {e['caracteres']} caracteres (~{e['tokens']} tokens); "
           f"costo estimado {e['usd']:.4f} USD (a {backend.precio_usd_m} USD por millón de tokens; cota superior si hay nivel gratuito).")
    if si:
        return True
    return entrada("¿Continuar? [s/N] ").strip().lower() in ("s", "si", "sí", "y", "yes")


# --- Backends ---

class BgeM3(Backend):
    """El modelo actual (SentenceTransformer en CPU). Se carga solo si falta algún texto en la caché."""
    nombre = "bge-m3"
    lote = 8

    def __init__(self, modelo: str = None, dir_cache: str = DIR_CACHE):
        super().__init__(modelo or config.EMBEDDING_MODEL_NAME_OR_PATH, dir_cache)
        self._modelo_st = None

    def _embed(self, textos: list):
        if self._modelo_st is None:
            from . import vector_db_manager
            self._modelo_st = vector_db_manager.get_embedding_function(self.modelo)
            if not self._modelo_st:
                raise RuntimeError("No se pudo inicializar el modelo de embeddings BGE-M3.")
        return self._modelo_st.embed_documents(textos)


class _Qwen3(Backend):
    def formatear_consulta(self, texto: str) -> str:
        return config.INSTRUCCION_CONSULTA_EMBEDDING + texto


class Qwen3Local(_Qwen3):
    """Qwen3-Embedding en Ollama local (POST /api/embed); la instrucción va solo en la consulta."""
    nombre = "qwen3-local"
    lote = 8

    def _post(self, cuerpo: dict) -> dict:
        import httpx
        r = httpx.post(f"{config.OLLAMA_BASE_URL}/api/embed", json=cuerpo, timeout=config.OLLAMA_TIMEOUT_S)
        r.raise_for_status()
        return r.json()

    def disponible(self) -> tuple:
        import httpx
        try:
            modelos = [m.get("name", "") for m in httpx.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=5).json().get("models", [])]
        except Exception as e:
            return False, f"Ollama no responde en {config.OLLAMA_BASE_URL} ({type(e).__name__})"
        if not any(m == self.modelo or m.split(":")[0] == self.modelo for m in modelos):
            return False, f"el modelo «{self.modelo}» no está en Ollama (ollama pull {self.modelo})"
        return True, ""

    def _embed(self, textos: list):
        datos = self._post({"model": self.modelo, "input": textos})
        self._registrar_uso(int(datos.get("prompt_eval_count") or 0), estimado=False)
        return datos["embeddings"]


class DeepInfra(_Qwen3):
    """Qwen3-Embedding-8B por el endpoint compatible con OpenAI de DeepInfra; el gasto real sale de usage.total_tokens."""
    nombre = "deepinfra"
    es_api = True
    lote = 100

    def __init__(self, modelo: str = None, dir_cache: str = DIR_CACHE):
        super().__init__(modelo or config.EMBEDDING_MODELOS["deepinfra"], dir_cache)
        self.precio_usd_m = config.PRECIOS_EMBEDDING_USD_M["deepinfra"]
        self._cliente_obj = None

    def disponible(self) -> tuple:
        env = config.PERFILES_NUBE["deepinfra"]["api_key_env"]
        return (True, "") if os.environ.get(env, "").strip() else (False, f"falta {env} en el .env")

    def _cliente(self):
        if self._cliente_obj is None:
            import openai
            perfil = config.PERFILES_NUBE["deepinfra"]
            self._cliente_obj = openai.OpenAI(base_url=perfil["base_url"], api_key=os.environ[perfil["api_key_env"]],
                                              max_retries=config.NUBE_MAX_REINTENTOS, timeout=config.NUBE_TIMEOUT_S)
        return self._cliente_obj

    def _embed(self, textos: list):
        r = self._cliente().embeddings.create(model=self.modelo, input=textos, encoding_format="float")
        self._registrar_uso(int(getattr(getattr(r, "usage", None), "total_tokens", 0) or 0), estimado=False)
        return [d.embedding for d in sorted(r.data, key=lambda d: d.index)]


class Gemini(Backend):
    """gemini-embedding-2 (Gemini API). Sin task_type: la tarea va en el prefijo del texto. Una solicitud por texto dentro de batchEmbedContents (si se mandan
    varios textos juntos en una sola entrada, el modelo devuelve UN embedding agregado). La API no informa tokens: el gasto se estima."""
    nombre = "gemini"
    es_api = True
    lote = 20           # lotes chicos: el nivel gratuito limita solicitudes y tokens por minuto
    reintentos = 6

    def __init__(self, modelo: str = None, dim: int = None, dir_cache: str = DIR_CACHE):
        self.dim = dim or config.EMBEDDING_DIM_GEMINI
        super().__init__(f"{modelo or config.EMBEDDING_MODELOS['gemini']}-{self.dim}", dir_cache)
        self.modelo_api = modelo or config.EMBEDDING_MODELOS["gemini"]
        self.precio_usd_m = config.PRECIOS_EMBEDDING_USD_M["gemini"]

    def formatear_consulta(self, texto: str) -> str:
        return f"task: search result | query: {texto}"

    def formatear_documento(self, texto: str) -> str:
        return f"title: {titulo_de_fragmento(texto)} | text: {texto}"

    def disponible(self) -> tuple:
        return (True, "") if os.environ.get("GEMINI_API_KEY", "").strip() else (False, "falta GEMINI_API_KEY en el .env")

    def _post(self, cuerpo: dict):
        import httpx
        return httpx.post(GEMINI_URL.format(modelo=self.modelo_api), json=cuerpo, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=config.NUBE_TIMEOUT_S)

    def _embed(self, textos: list):
        cuerpo = {"requests": [{"model": f"models/{self.modelo_api}", "content": {"parts": [{"text": t}]}, "output_dimensionality": self.dim} for t in textos]}
        for intento in range(self.reintentos + 1):
            r = self._post(cuerpo)
            if r.status_code == 429 or r.status_code >= 500:
                if intento == self.reintentos:
                    r.raise_for_status()
                espera = min(ESPERA_MAXIMA_S, float(r.headers.get("retry-after") or 2 ** (intento + 1)))
                logger.warning(f"Gemini respondió {r.status_code}: espero {espera:.0f} s (reintento {intento + 1} de {self.reintentos}).")
                self.esperar(espera)
                continue
            r.raise_for_status()
            break
        self._registrar_uso(int(sum(len(t) for t in textos) / config.EMBEDDING_CHARS_POR_TOKEN), estimado=True)
        return [e["values"] for e in r.json()["embeddings"]]


def crear_backend(nombre: str, modelo: str = None, dim: int = None, dir_cache: str = DIR_CACHE) -> Backend:
    """Instancia el backend por nombre; `modelo` y `dim` reemplazan los de config.EMBEDDING_MODELOS / EMBEDDING_DIM_GEMINI."""
    if nombre == "bge-m3":
        return BgeM3(None, dir_cache)
    if nombre == "qwen3-local":
        return Qwen3Local(modelo or config.EMBEDDING_MODELOS["qwen3-local"], dir_cache)
    if nombre == "deepinfra":
        return DeepInfra(modelo, dir_cache)
    if nombre == "gemini":
        return Gemini(modelo, dim, dir_cache)
    raise ValueError(f"Backend de embeddings desconocido: «{nombre}» (hay {', '.join(BACKENDS)}).")


class EmbeddingsBackend(Embeddings):
    """Adaptador de LangChain: Chroma indexa con embed_documents y busca con embed_query. `model_name` entra en la firma del manifest del índice."""

    def __init__(self, backend: Backend):
        self.backend = backend
        self.model_name = backend.model_name

    def embed_documents(self, texts: list) -> list:
        return self.backend.embed_documents(texts).tolist()

    def embed_query(self, text: str) -> list:
        return self.backend.embed_query(text).tolist()
