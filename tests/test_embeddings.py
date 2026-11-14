import numpy as np
import pytest

from scripts import config, embeddings as emb


class Falso(emb.Backend):
    """Backend de prueba: cuenta las llamadas a _embed y devuelve vectores fijos según el largo del texto."""
    nombre = "falso"
    es_api = True
    lote = 2
    precio_usd_m = 10.0

    def __init__(self, tmp_path):
        super().__init__("m", str(tmp_path))
        self.llamadas = []

    def _embed(self, textos):
        self.llamadas.append(list(textos))
        return [[len(t), 1.0, 0.0] for t in textos]


def test_los_vectores_salen_normalizados(tmp_path):
    v = Falso(tmp_path).embed_documents(["abc", "de"])
    assert v.dtype == np.float32 and np.allclose(np.linalg.norm(v, axis=1), 1)


def test_la_cache_evita_la_segunda_llamada_y_sobrevive_al_reinicio(tmp_path):
    b = Falso(tmp_path)
    primero = b.embed_documents(["uno", "dos", "tres"])
    assert [len(x) for x in b.llamadas] == [2, 1]                    # lotes de 2
    b.embed_documents(["uno", "dos", "tres", "tres"])
    assert len(b.llamadas) == 2                                      # todo en caché (y el repetido no se vuelve a pedir)
    otro = Falso(tmp_path)                                           # archivo en disco
    assert np.allclose(otro.embed_documents(["uno", "dos", "tres"]), primero) and otro.llamadas == []
    assert (tmp_path / "falso__m.npz").is_file() and b.cache.meta["n_documentos"] == 3


def test_solo_se_calculan_los_textos_que_faltan(tmp_path):
    b = Falso(tmp_path)
    b.embed_documents(["uno", "dos"])
    b.embed_documents(["dos", "nuevo"])
    assert b.llamadas[-1] == ["nuevo"]


def test_consulta_y_documento_no_se_mezclan_en_la_cache(tmp_path):
    class ConPrefijo(Falso):
        def formatear_consulta(self, texto):
            return "Q: " + texto
    b = ConPrefijo(tmp_path)
    b.embed_documents(["x"])
    b.embed_queries(["x"])
    assert b.llamadas == [["x"], ["Q: x"]]


def test_preflight_pide_confirmacion_salvo_si_y_no_pregunta_si_no_hay_pendientes(tmp_path, capsys):
    b = Falso(tmp_path)
    assert emb.preflight(b, ["a" * 70], entrada=lambda _: "n") is False
    assert emb.preflight(b, ["a" * 70], entrada=lambda _: "s") is True
    assert emb.preflight(b, ["a" * 70], si=True, entrada=lambda _: pytest.fail("no debe preguntar")) is True
    salida = capsys.readouterr().out
    assert "1 textos, 70 caracteres" in salida and "20 tokens" in salida and "USD" in salida
    b.embed_documents(["a" * 70])
    assert emb.preflight(b, ["a" * 70], entrada=lambda _: pytest.fail("todo en caché: no pregunta")) is True


def test_preflight_de_un_backend_local_no_pregunta(tmp_path):
    b = Falso(tmp_path)
    b.es_api = False
    assert emb.preflight(b, ["texto"], entrada=lambda _: pytest.fail("local: no pregunta")) is True


def test_formatos_de_consulta_y_documento(tmp_path):
    assert emb.BgeM3("x", str(tmp_path)).formatear_consulta("q") == "q"
    q = emb.Qwen3Local("qwen3-embedding:4b", str(tmp_path))
    assert q.formatear_consulta("texto") == config.INSTRUCCION_CONSULTA_EMBEDDING + "texto" and q.formatear_documento("doc") == "doc"
    assert config.INSTRUCCION_CONSULTA_EMBEDDING.endswith("\nQuery: ")
    g = emb.Gemini(dir_cache=str(tmp_path))
    assert g.formatear_consulta("texto") == "task: search result | query: texto"
    assert g.formatear_documento("Art. 4.2. Hormigón\ncuerpo") == "title: Art. 4.2. Hormigón | text: Art. 4.2. Hormigón\ncuerpo"
    assert g.formatear_documento("sin encabezado") == "title: none | text: sin encabezado"


def test_cada_backend_tiene_su_propia_cache(tmp_path):
    nombres = {emb.crear_backend(n, dir_cache=str(tmp_path)).model_name for n in emb.BACKENDS}
    assert len(nombres) == 4 and "bge-m3" in nombres
    assert emb.crear_backend("gemini", dim=768, dir_cache=str(tmp_path)).model_name != emb.crear_backend("gemini", dir_cache=str(tmp_path)).model_name
    with pytest.raises(ValueError):
        emb.crear_backend("otro")


class Respuesta:
    def __init__(self, codigo, datos=None, cabeceras=None):
        self.status_code, self._datos, self.headers = codigo, datos, cabeceras or {}

    def json(self):
        return self._datos

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_gemini_manda_una_solicitud_por_texto_y_reintenta_ante_429(tmp_path):
    g = emb.Gemini(dir_cache=str(tmp_path), dim=3)
    cuerpos, esperas = [], []
    respuestas = iter([Respuesta(429, cabeceras={"retry-after": "7"}), Respuesta(503), Respuesta(200, {"embeddings": [{"values": [3, 0, 4]}, {"values": [0, 1, 0]}]})])
    g._post = lambda cuerpo: (cuerpos.append(cuerpo), next(respuestas))[1]
    g.esperar = esperas.append
    v = g.embed_queries(["uno", "dos"])
    assert len(cuerpos) == 3 and len(cuerpos[0]["requests"]) == 2        # una solicitud por texto, no una entrada con varios
    r = cuerpos[0]["requests"][0]
    assert r["model"] == "models/gemini-embedding-2" and r["output_dimensionality"] == 3
    assert r["content"]["parts"][0]["text"] == "task: search result | query: uno"
    assert esperas == [7.0, 4.0]                                         # retry-after, luego espera exponencial
    assert np.allclose(v[0], [0.6, 0, 0.8]) and g.cache.meta["tokens_estimados"] > 0


def test_gemini_se_rinde_tras_los_reintentos(tmp_path):
    g = emb.Gemini(dir_cache=str(tmp_path))
    g.reintentos = 1
    g._post = lambda cuerpo: Respuesta(429)
    g.esperar = lambda s: None
    with pytest.raises(RuntimeError):
        g.embed_queries(["x"])
    assert g.cache.vectores == {}


def test_ollama_parsea_embeddings(tmp_path):
    q = emb.Qwen3Local("qwen3-embedding:4b", str(tmp_path))
    pedidos = []
    q._post = lambda cuerpo: (pedidos.append(cuerpo), {"embeddings": [[1, 0], [0, 2]], "prompt_eval_count": 5})[1]
    v = q.embed_documents(["a", "b"])
    assert pedidos == [{"model": "qwen3-embedding:4b", "input": ["a", "b"]}] and np.allclose(v, [[1, 0], [0, 1]])


def test_deepinfra_usa_el_gasto_real_y_ordena_por_indice(tmp_path):
    d = emb.DeepInfra(dir_cache=str(tmp_path))

    class Dato:
        def __init__(self, i, e):
            self.index, self.embedding = i, e

    class Cliente:
        class embeddings:
            @staticmethod
            def create(model, input, encoding_format):
                assert model == "Qwen/Qwen3-Embedding-8B" and encoding_format == "float" and input[0].startswith(config.INSTRUCCION_CONSULTA_EMBEDDING)
                return type("R", (), {"data": [Dato(1, [0, 1]), Dato(0, [1, 0])], "usage": type("U", (), {"total_tokens": 1000})()})()
    d._cliente_obj = Cliente()
    v = d.embed_queries(["a", "b"])
    assert np.allclose(v, [[1, 0], [0, 1]]) and d.cache.meta["tokens"] == 1000 and d.cache.meta["usd"] == pytest.approx(1000 / 1e6 * 0.01)


def test_backends_de_api_sin_clave_no_estan_disponibles(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert emb.DeepInfra(dir_cache=str(tmp_path)).disponible()[0] is False
    ok, motivo = emb.Gemini(dir_cache=str(tmp_path)).disponible()
    assert ok is False and "GEMINI_API_KEY" in motivo
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    assert emb.Gemini(dir_cache=str(tmp_path)).disponible()[0] is True


def test_adaptador_de_langchain_expone_model_name_y_las_dos_funciones(tmp_path):
    a = emb.EmbeddingsBackend(Falso(tmp_path))
    assert a.model_name == "falso__m"
    assert len(a.embed_documents(["abc", "de"])) == 2 and len(a.embed_query("abc")) == 3
