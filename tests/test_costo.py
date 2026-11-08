import subprocess
from types import SimpleNamespace

import pytest

from scripts import costo
from scripts.main import Llamadas, _invocar
from tests.test_robustez_llm import Cadena


def test_percentil_valores_conocidos():
    assert costo.percentil([1, 2, 3, 4, 5], 50) == 3
    assert costo.percentil([10, 20, 30, 40], 50) == 25                       # interpolación lineal
    assert costo.percentil(list(range(1, 11)), 90) == pytest.approx(9.1)
    assert costo.percentil([7], 90) == 7 and costo.percentil([], 50) is None
    assert costo.percentil([3, 1, 2], 100) == 3                              # no necesita estar ordenado


def test_detectar_hardware_con_nvidia_smi():
    llamada = []
    def falso(cmd, **kw):
        llamada.append(cmd)
        return SimpleNamespace(returncode=0, stdout="NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB\n")
    assert costo.detectar_hardware(falso) == {"gpu": "NVIDIA GeForce RTX 4060 Laptop GPU", "vram": "8188 MiB"}
    assert llamada[0] == ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]
    dos = lambda cmd, **kw: SimpleNamespace(returncode=0, stdout="GPU A, 8192 MiB\nGPU B, 24576 MiB\n")
    assert costo.detectar_hardware(dos) == {"gpu": "GPU A; GPU B", "vram": "8192 MiB; 24576 MiB"}


def test_detectar_hardware_sin_nvidia_smi_no_falla():
    def no_existe(cmd, **kw):
        raise FileNotFoundError("nvidia-smi")
    r = costo.detectar_hardware(no_existe)
    assert r["gpu"] is None and r["vram"] is None and "nvidia-smi" in r["nota"]
    assert costo.detectar_hardware(lambda cmd, **kw: SimpleNamespace(returncode=9, stdout=""))["gpu"] is None
    def lento(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 10)
    assert costo.detectar_hardware(lento)["gpu"] is None


def _l(tipo, par, duracion, entrada, salida, intentos=1, exitosa=True):
    return {"tipo": tipo, "par": par, "etiqueta": "x", "duracion_s": duracion, "prompt_eval_count": entrada, "eval_count": salida, "intentos": intentos, "exitosa": exitosa}


def test_resumen_costo_pares_llamadas_tiempos_y_tokens():
    detalle = [_l("verificacion", "1|N|a", 10.0, 1000, 100), _l("clasificacion", "1|N|a", 20.0, 3000, 400),       # par 1: 30 s
               _l("verificacion", "1|N|b", 5.0, 1000, 80),                                                         # par 2: 5 s
               _l("verificacion", "2|N|c", 15.0, 1200, 120, intentos=2), _l("clasificacion", "2|N|c", 5.0, 2800, 300),   # par 3: 20 s, con un reintento
               _l("comentario", None, 8.0, 500, 200)]
    c = costo.resumen_costo(detalle, 100.0, "qwen3:8b", {"gpu": "G", "vram": "8 GiB"})
    assert c["pares_verificados"] == 3 and c["llamadas_totales"] == 7              # 6 llamadas + 1 reintento (el comentario cuenta una)
    assert c["tiempo_total_s"] == 100.0 and c["modelo"] == "qwen3:8b" and c["hardware"] == {"gpu": "G", "vram": "8 GiB"}
    assert c["segundos_por_par"] == {"mediana": 20.0, "p90": pytest.approx(28.0)}                                    # pares: 5, 20, 30
    assert (c["tokens_entrada_total"], c["tokens_salida_total"]) == (1000 + 3000 + 1000 + 1200 + 2800 + 500, 100 + 400 + 80 + 120 + 300 + 200)
    assert c["tokens_entrada_por_par"] == round(9000 / 3, 1) and c["tokens_salida_por_par"] == round(1000 / 3, 1)   # sin el comentario


def test_resumen_costo_sin_pares_no_divide_por_cero():
    c = costo.resumen_costo([_l("lista", None, 3.0, 100, 50)], 4.0, "m", {})
    assert c["pares_verificados"] == 0 and c["tokens_entrada_por_par"] is None and c["segundos_por_par"] == {"mediana": None, "p90": None}
    assert c["tokens_entrada_total"] == 100 and costo.resumen_costo([], 1.0, "m", {})["llamadas_totales"] == 0


def test_invocar_registra_duracion_y_tokens_incluyendo_los_reintentos():
    import httpx
    mensaje = SimpleNamespace(content="{}", response_metadata={"prompt_eval_count": 900, "eval_count": 70})
    cortado = SimpleNamespace(content="{", response_metadata={"done_reason": "length", "prompt_eval_count": 900, "eval_count": 1024})
    llamadas = Llamadas({"verificacion": 0})
    _invocar(Cadena(cortado, mensaje), {}, "S1", llamadas, "verificacion", par="1|N|a")
    (r,) = llamadas.detalle
    assert (r["tipo"], r["par"], r["intentos"], r["exitosa"]) == ("verificacion", "1|N|a", 2, True)
    assert (r["prompt_eval_count"], r["eval_count"]) == (1800, 1094) and r["duracion_s"] >= 0       # los tokens suman los dos intentos
    # una llamada que falla del todo también se registra
    fallida = Llamadas({"clasificacion": 0})
    with pytest.raises(Exception):
        _invocar(Cadena(httpx.ReadTimeout("t")), {}, "S1", fallida, "clasificacion", par="1|N|a")
    assert fallida.detalle[0]["exitosa"] is False and fallida.detalle[0]["intentos"] == 2
    # con un dict común (los tests viejos) no se registra y no falla
    simple = {"verificacion": 0}
    _invocar(Cadena(mensaje), {}, "S1", simple, "verificacion")
    assert simple == {"verificacion": 1, "eval_count": {"verificacion": [70]}}


def test_duracion_es_reloj_de_pared(monkeypatch):
    import scripts.main as m
    reloj = iter([100.0, 107.5])                                                # al empezar y al terminar la llamada
    monkeypatch.setattr(m, "time", SimpleNamespace(perf_counter=lambda: next(reloj)))
    llamadas = Llamadas({"verificacion": 0})
    _invocar(Cadena(SimpleNamespace(content="{}", response_metadata={})), {}, "S1", llamadas, "verificacion")
    assert llamadas.detalle[0]["duracion_s"] == 7.5
