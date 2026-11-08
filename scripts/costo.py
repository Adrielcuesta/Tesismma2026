# scripts/costo.py
"""Costo computacional de un análisis (para comparar local contra nube): tiempo, llamadas y tokens, más el hardware y el modelo.
Todo sale de los registros por llamada que arma main._invocar; aquí no se llama al modelo."""
import math
import subprocess


def percentil(valores, p: float):
    """Percentil p (0 a 100) por interpolación lineal entre los valores ordenados; None si no hay valores."""
    v = sorted(valores)
    if not v:
        return None
    k = (len(v) - 1) * p / 100
    abajo, arriba = math.floor(k), math.ceil(k)
    return v[abajo] + (v[arriba] - v[abajo]) * (k - abajo)


def detectar_hardware(ejecutar=subprocess.run) -> dict:
    """GPU y VRAM según `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader`; sin nvidia-smi, gpu y vram quedan en None."""
    try:
        r = ejecutar(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
        lineas = [l.strip() for l in (r.stdout or "").splitlines() if l.strip()] if r.returncode == 0 else []
    except (OSError, subprocess.SubprocessError):
        lineas = []
    if not lineas:
        return {"gpu": None, "vram": None, "nota": "nvidia-smi no disponible"}
    partes = [l.rpartition(",") for l in lineas]
    return {"gpu": "; ".join(p[0].strip() for p in partes), "vram": "; ".join(p[2].strip() for p in partes)}


def resumen_costo(detalle: list, tiempo_total_s: float, modelo: str, hardware: dict) -> dict:
    """Costo computacional del análisis a partir de los registros por llamada (tipo, par, duracion_s, prompt_eval_count, eval_count, intentos, exitosa).
    Un par es una verificación (y su clasificación, si la hubo): segundos por par = suma de las duraciones de sus llamadas. Los tokens por par promedian
    solo las llamadas de verificación y clasificación; los totales incluyen también el comentario general y la lista de riesgos."""
    verificados = {d["par"] for d in detalle if d.get("tipo") == "verificacion" and d.get("par") and d.get("exitosa")}
    segundos = {}
    for d in detalle:
        if d.get("par") in verificados:
            segundos[d["par"]] = segundos.get(d["par"], 0.0) + d["duracion_s"]
    por_par = [d for d in detalle if d.get("par") in verificados]
    n = len(verificados)
    entrada_total, salida_total = sum(d.get("prompt_eval_count") or 0 for d in detalle), sum(d.get("eval_count") or 0 for d in detalle)
    return {
        "modelo": modelo, "hardware": hardware, "pares_verificados": n,
        "llamadas_totales": sum(d.get("intentos", 1) for d in detalle), "llamadas_fallidas": sum(not d.get("exitosa", True) for d in detalle),
        "tiempo_total_s": tiempo_total_s,
        "segundos_por_par": {"mediana": percentil(segundos.values(), 50), "p90": percentil(segundos.values(), 90)},
        "tokens_entrada_total": entrada_total, "tokens_salida_total": salida_total,
        "tokens_entrada_por_par": round(sum(d.get("prompt_eval_count") or 0 for d in por_par) / n, 1) if n else None,
        "tokens_salida_por_par": round(sum(d.get("eval_count") or 0 for d in por_par) / n, 1) if n else None,
    }
