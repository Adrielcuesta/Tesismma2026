"""Fase 2: backend de embeddings en el pipeline, perfil «elegido», huellas de la recuperación y flag local --reusar-recuperacion (sin red ni modelos)."""
import json
import os

import pytest

from scripts import config, elegir_json, embeddings, huella_recuperacion, recuperar, run_oferta, vector_db_manager


@pytest.fixture
def restaurar_config(monkeypatch):
    """aplicar_perfil escribe en config: el monkeypatch restaura todo al terminar el test."""
    for clave in set().union(*(p.keys() for p in config.PERFILES_RECUPERACION.values())):
        monkeypatch.setattr(config, clave, getattr(config, clave))
    monkeypatch.setattr(config, "PERFIL_ELEGIDO_CARGADO", config.PERFIL_ELEGIDO_CARGADO)


# --- Índice por backend ---

def test_el_backend_por_defecto_es_bge_m3_y_conserva_las_rutas_de_v1():
    assert config.EMBEDDING_BACKEND == "bge-m3"
    assert config.rutas_indice() == config.rutas_indice("bge-m3") == {"path": config.CHROMA_DB_PATH_KB, "collection": config.CHROMA_COLLECTION_KB, "manifest": config.CHROMA_MANIFEST_PATH_KB}
    assert config.CHROMA_COLLECTION_KB == "kb_ferroviaria_articulos" and config.CHROMA_DB_PATH_KB.endswith("ChromaDB_KB_Ferroviaria")


def test_cada_backend_tiene_su_propio_indice_distinto_del_de_bge_m3():
    bge = config.rutas_indice("bge-m3")
    otros = [config.rutas_indice(b) for b in embeddings.BACKENDS if b != "bge-m3"]
    assert len({r["path"] for r in otros}) == 3 and len({r["collection"] for r in otros}) == 3 and len({r["manifest"] for r in otros}) == 3
    for r in otros:
        assert not set(r.values()) & set(bge.values())
        assert r["manifest"] == r["path"] + "_manifest.json" and r["path"].startswith(config.CHROMA_DB_PATH_KB + "_")
    assert config.rutas_indice("qwen3-local")["collection"] == "kb_ferroviaria_articulos_qwen3_local"


def _capturar(monkeypatch):
    llamadas = {"chroma": []}
    monkeypatch.setattr(vector_db_manager, "crear_o_cargar_chroma_db", lambda **kw: (llamadas["chroma"].append(kw), "INDICE")[1])
    return llamadas


def test_cargar_indice_kb_con_bge_m3_usa_el_modelo_y_las_rutas_de_siempre(monkeypatch):
    llamadas = _capturar(monkeypatch)
    modelos = []
    monkeypatch.setattr(vector_db_manager, "get_embedding_function", lambda nombre: (modelos.append(nombre), "FUNCION")[1])
    assert vector_db_manager.cargar_indice_kb() == "INDICE"
    (kw,) = llamadas["chroma"]
    assert modelos == [config.EMBEDDING_MODEL_NAME_OR_PATH] and kw["embedding_function"] == "FUNCION" and kw["por_articulos"] is True
    assert (kw["chroma_db_path"], kw["collection_name"], kw["manifest_path"]) == (config.CHROMA_DB_PATH_KB, config.CHROMA_COLLECTION_KB, config.CHROMA_MANIFEST_PATH_KB)
    assert kw["docs_base_conocimiento_path"] == config.DIRECTORIO_NORMATIVA and kw["recrear_db_flag"] is False


def test_cargar_indice_kb_con_otro_backend_no_toca_el_indice_ni_el_modelo_de_bge_m3(monkeypatch):
    llamadas = _capturar(monkeypatch)
    monkeypatch.setattr(vector_db_manager, "get_embedding_function", lambda nombre: pytest.fail("no debe cargar BGE-M3"))

    class Falso:
        model_name = "gemini__x"

        def disponible(self):
            return True, ""
    monkeypatch.setattr(embeddings, "crear_backend", lambda nombre, *a, **kw: Falso())
    assert vector_db_manager.cargar_indice_kb(backend="gemini", recrear=True) == "INDICE"
    (kw,) = llamadas["chroma"]
    rutas = config.rutas_indice("gemini")
    assert (kw["chroma_db_path"], kw["collection_name"], kw["manifest_path"]) == (rutas["path"], rutas["collection"], rutas["manifest"])
    assert isinstance(kw["embedding_function"], embeddings.EmbeddingsBackend) and kw["embedding_function"].model_name == "gemini__x" and kw["recrear_db_flag"] is True
    assert kw["chroma_db_path"] != config.CHROMA_DB_PATH_KB


def test_cargar_indice_kb_sigue_config_embedding_backend_y_devuelve_none_si_el_backend_no_esta_disponible(monkeypatch):
    llamadas = _capturar(monkeypatch)
    monkeypatch.setattr(config, "EMBEDDING_BACKEND", "deepinfra")
    monkeypatch.delenv("DEEPINFRA_API_KEY", raising=False)
    assert vector_db_manager.cargar_indice_kb() is None and llamadas["chroma"] == []


# --- Perfil «elegido» ---

def test_el_perfil_elegido_es_un_relleno_igual_a_local_y_no_se_puede_usar_hasta_cargarlo(restaurar_config):
    assert config.PERFIL_ELEGIDO_CARGADO is False
    elegido = dict(config.PERFILES_RECUPERACION["elegido"])
    assert elegido.pop("EMBEDDING_BACKEND") == "bge-m3" and elegido == config.PERFILES_RECUPERACION["local"]
    with pytest.raises(ValueError, match="relleno"):
        recuperar.aplicar_perfil("elegido")
    assert config.K_SUBSECCION == 10                                   # no se aplicó nada


def test_recuperar_con_el_perfil_elegido_sin_cargar_termina_con_error_sin_tocar_nada(restaurar_config, tmp_path, capsys, monkeypatch):
    oferta = tmp_path / "oferta.pdf"
    oferta.write_text("x")
    monkeypatch.setattr(recuperar.document_utils, "extraer_texto_oferta", lambda ruta: pytest.fail("no debe leer la oferta"))
    assert recuperar.main([str(oferta), "--perfil-recuperacion", "elegido"]) == 2
    assert "PERFIL_ELEGIDO_CARGADO" in capsys.readouterr().err


def test_con_el_perfil_elegido_cargado_se_aplica_incluido_el_backend_de_embeddings(restaurar_config, monkeypatch):
    monkeypatch.setitem(config.PERFILES_RECUPERACION, "elegido", {"EMBEDDING_BACKEND": "gemini", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 33,
                                                                  "VERIFICAR_TOPE": 60, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8})
    monkeypatch.setattr(config, "PERFIL_ELEGIDO_CARGADO", True)
    parametros = recuperar.aplicar_perfil("elegido")
    assert parametros["EMBEDDING_BACKEND"] == "gemini" and config.EMBEDDING_BACKEND == "gemini" and config.TOP_N_SUBSECCION == 33 and config.VERIFICAR_TOPE == 60
    assert recuperar.huella_de("elegido", parametros) != recuperar.huella_de("elegido", {**parametros, "EMBEDDING_BACKEND": "bge-m3"})


def test_los_perfiles_local_y_amplio_no_cambian_y_no_traen_backend():
    assert config.PERFILES_RECUPERACION["local"] == {"K_SUBSECCION": 10, "TOP_DENSA_SUBSECCION": 5, "TOP_N_SUBSECCION": 5, "VERIFICAR_TOPE": 25, "ORACIONES_CIFRAS": True,
                                                     "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
    assert config.PERFILES_RECUPERACION["amplio"] == {"K_SUBSECCION": 20, "TOP_DENSA_SUBSECCION": 5, "TOP_N_SUBSECCION": 8, "VERIFICAR_TOPE": 30, "ORACIONES_CIFRAS": True,
                                                      "ORACIONES_N": 2, "ORACIONES_CUPO": 10}


# --- Huellas ---

SECCIONES = [{"id": "3", "fragmentos": [{"norma": "NORM_01", "articulo": "4.2", "score": 0.9, "parte": 1}, {"norma": "NORM_02", "articulo": "5.1", "score": 0.5, "parte": 1}]},
             {"id": "4", "fragmentos": [{"norma": "NORM_01", "articulo": "4.3", "score": 0.7, "parte": 2}]}, {"id": "1", "fragmentos": []}]


def test_la_huella_de_pares_no_depende_del_orden_ni_de_los_puntajes_pero_si_de_los_pares():
    base = huella_recuperacion.huella_de_pares(SECCIONES)
    assert len(base) == 64
    invertida = [{**SECCIONES[0], "fragmentos": [dict(f, score=0.1) for f in reversed(SECCIONES[0]["fragmentos"])]}, SECCIONES[2], SECCIONES[1]]
    assert huella_recuperacion.huella_de_pares(invertida) == base
    otra_parte = [SECCIONES[0], {"id": "4", "fragmentos": [dict(SECCIONES[1]["fragmentos"][0], parte=1)]}, SECCIONES[2]]
    otra_seccion = [SECCIONES[0], {"id": "5", "fragmentos": SECCIONES[1]["fragmentos"]}, SECCIONES[2]]
    repetido = [{**SECCIONES[0], "fragmentos": SECCIONES[0]["fragmentos"] * 2}, SECCIONES[1], SECCIONES[2]]
    assert len({base, huella_recuperacion.huella_de_pares(otra_parte), huella_recuperacion.huella_de_pares(otra_seccion), huella_recuperacion.huella_de_pares(repetido)}) == 4
    assert huella_recuperacion.huella_de_pares(None) == huella_recuperacion.huella_de_pares([])


def test_sha256_del_archivo(tmp_path):
    f = tmp_path / "r.json"
    f.write_bytes(b"abc")
    assert huella_recuperacion.sha256_archivo(str(f)) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_el_json_de_recuperacion_trae_backend_y_huella_de_pares(restaurar_config):
    from scripts.schemas import FragmentoRecuperado, SeccionInforme
    seccion = SeccionInforme(id="3", titulos=["3 Alcance"], fragmentos=[FragmentoRecuperado(norma="NORM_01", articulo="4.2", score=0.9, parte=1)])
    datos = recuperar.armar_json("oferta.pdf", [seccion], "local", config.PERFILES_RECUPERACION["local"])
    cfg = datos["configuracion_analisis"]
    assert cfg["embedding_backend"] == "bge-m3" and cfg["huella_pares"] == huella_recuperacion.huella_de_pares(datos["secciones"]) and cfg["embeddings"] == config.EMBEDDING_MODEL_NAME_OR_PATH


# --- run_oferta --reusar-recuperacion ---

def test_sufijo_local_y_busqueda_del_json_con_sufijo(tmp_path):
    assert run_oferta.sufijo_local("qwen3:8b", "elegido") == "local-qwen3-8b-elegido" and run_oferta.sufijo_local("qwen3:8b", None) == "local-qwen3-8b"
    html = tmp_path / "dashboard_oferta_20260101_101010_local-qwen3-8b-elegido.html"
    html.write_text("<html></html>")
    json_ = tmp_path / "analisis_riesgos_oferta_20260101_101010_local-qwen3-8b-elegido.json"
    json_.write_text("{}")
    assert run_oferta._buscar_json(str(html)) == str(json_)


def _simular_run_analysis(monkeypatch, tmp_path):
    llamadas = []

    def falso(modelo, usar_rag=True, directorio_proyecto=None, **kw):
        llamadas.append(kw)
        sufijo = f"_{kw['sufijo_marca']}" if kw.get("sufijo_marca") else ""
        (tmp_path / f"analisis_riesgos_oferta_20260101_101010{sufijo}.json").write_text(json.dumps({"configuracion_analisis": {"condicion": "rag_seccion", "tiempos_s": {}},
                                                                                                "registro_brechas": [], "resumen_ejecutivo": {"decision": "x"}}), encoding="utf-8")
        html = tmp_path / f"dashboard_oferta_20260101_101010{sufijo}.html"
        html.write_text("<html></html>")
        return str(html)
    monkeypatch.setattr(run_oferta, "run_analysis", falso)
    return llamadas


def test_run_oferta_con_reusar_recuperacion_pasa_el_json_y_el_sufijo(monkeypatch, tmp_path, capsys):
    llamadas = _simular_run_analysis(monkeypatch, tmp_path)
    oferta, rec = tmp_path / "Oferta_P1.pdf", tmp_path / "rec.json"
    oferta.write_text("x")
    rec.write_text(json.dumps({"configuracion_analisis": {"perfil_recuperacion": "elegido"}}))
    assert run_oferta.main([str(oferta), "--reusar-recuperacion", str(rec)]) == 0
    assert llamadas == [{"recuperacion_json": os.path.abspath(str(rec)), "sufijo_marca": "local-qwen3-8b-elegido"}]
    assert "analisis_riesgos_oferta_20260101_101010_local-qwen3-8b-elegido.json" in capsys.readouterr().out


def test_run_oferta_sin_el_flag_no_pasa_nada_nuevo_y_con_el_flag_valida(monkeypatch, tmp_path, capsys):
    llamadas = _simular_run_analysis(monkeypatch, tmp_path)
    oferta = tmp_path / "Oferta_P1.pdf"
    oferta.write_text("x")
    assert run_oferta.main([str(oferta)]) == 0 and llamadas == [{}]
    assert run_oferta.main([str(oferta), "--reusar-recuperacion", str(tmp_path / "no_existe.json")]) == 1
    rec = tmp_path / "rec.json"
    rec.write_text("{}")
    assert run_oferta.main([str(oferta), "--reusar-recuperacion", str(rec), "--sin-rag"]) == 1 and len(llamadas) == 1


def test_elegir_json_excluye_las_corridas_con_la_recuperacion_elegida_de_los_auto_por_condicion(tmp_path):
    for nombre, t in (("analisis_riesgos_P3_a.json", 1000), ("analisis_riesgos_P3_b_local-qwen3-8b-elegido.json", 2000), ("analisis_riesgos_P3_c_elegido.json", 3000)):
        (tmp_path / nombre).write_text(json.dumps({"configuracion_analisis": {"condicion": "rag_seccion"}}))
        os.utime(tmp_path / nombre, (t, t))
    elegido, _ = elegir_json.elegir(str(tmp_path), "rag_seccion")
    assert os.path.basename(elegido) == "analisis_riesgos_P3_c_elegido.json"        # «_elegido» sin guion no es el sufijo de perfil
    assert os.path.basename(elegir_json.elegir_por_sufijo(str(tmp_path), "local-qwen3-8b-elegido")) == "analisis_riesgos_P3_b_local-qwen3-8b-elegido.json"


# --- Scripts de corrida ---

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ps1(nombre):
    with open(os.path.join(RAIZ, "scripts", nombre), "rb") as f:
        crudo = f.read()
    assert all(b < 128 for b in crudo), f"{nombre} tiene que ser ASCII"
    return crudo.decode("ascii")


def test_script_de_la_nube_recupera_una_vez_con_el_perfil_elegido_y_corre_32b_sin_y_con_razonamiento():
    t = _ps1("correr_reeval_nube.ps1")
    assert t.index('"scripts.recuperar"') < t.index("Guardar-Manifiesto") < t.index('"scripts.nube"')
    assert '"--perfil-recuperacion", $script:perfil' in t and '$script:perfil = "elegido"' in t and '"--reusar-recuperacion", $rec' in t
    assert 'Qwen/Qwen3-32B' in t and '"--thinking"' in t
    assert "Thinking = $false" in t and "Thinking = $true" in t and "ReusarRecuperacion" in t and "SoloRecuperar" in t
    assert "recuperacion_elegido.json" in t and "deepinfra-qwen3-32b-thinking-elegido" in t


def test_script_local_reusa_los_mismos_json_de_recuperacion_en_run_oferta():
    t = _ps1("correr_reeval_local.ps1")
    assert "recuperacion_elegido.json" in t and '"scripts.run_oferta"' in t and '"--reusar-recuperacion", $rec' in t and "local-qwen3-8b-elegido" in t
    for o in ("P1", "P2", "P3", "P4"):
        assert f'Nombre = "{o}"' in t
    assert "shutdown /s /f /t 120" in t and "param([switch]$Apagar)" in t and "--sin-rag" not in t


def test_nube_deja_la_huella_de_pares_en_la_configuracion_del_reporte():
    from scripts import nube
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "criterios_empresa.json"), encoding="utf-8") as f:
        criterios = json.load(f)
    lin = {"criterios": criterios, "texto_para_el_modelo": "<criterios>", "huella": "h" * 64, "documentos": []}
    secciones = [{"id": "3", "titulos": ["3 Alcance"], "fragmentos": [{"norma": "NORM_01", "articulo": "4.2", "score": 0.9, "parte": 1}]}]
    local = {"secciones": secciones, "configuracion_analisis": {"perfil_recuperacion": "elegido", "embedding_backend": "gemini"}}
    reporte = nube.armar_reporte(local, [], {}, [], lin, "Qwen/Qwen3-32B", "deepinfra", 8, {"usd": 0.0, "cacheados": 0, "llamadas": 0}, 1.0, False, None, False)
    cfg = reporte.configuracion_analisis
    assert cfg["huella_pares"] == huella_recuperacion.huella_de_pares(secciones) and cfg["embedding_backend"] == "gemini" and cfg["perfil_recuperacion"] == "elegido"
