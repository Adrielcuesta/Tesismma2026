# evaluacion/juez.py
"""Juez externo de precisión. Para cada brecha del extras_revision.csv de un JSON de análisis (las que no son trampas ni espejos) pregunta a un
modelo de la nube si es VALIDA, NO_VALIDA o DUDOSA según el artículo de la KB y el contenido mínimo de la oferta (NORM_07 Art. 2.6).
El juez recibe solo: oraciones citadas, texto del artículo y título/enunciado/motivo del sistema. No ve el ground truth ni los espejos.
Escribe extras_revision_juez.csv junto al JSON (columnas de extras_revision.csv + juez_veredicto, juez_motivo); la columna humana «valido» no se toca.
Si el archivo ya existe, las brechas ya juzgadas se conservan (con --rehacer se juzgan de nuevo).

Uso:
  python -m evaluacion.juez <json> [<json> ...] [--max-items N] [--concurrencia 8] [--rehacer]
Requisito: haber corrido evaluar.py sobre cada JSON (genera extras_revision.csv). Clave en el .env: DEEPINFRA_API_KEY."""
import argparse
import csv
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from scripts import config, rag_components
from scripts.main import LlamadaFallida
from scripts.nube import ClienteNube, Gasto, PresupuestoAgotado

from .evaluar import ESTADO_DESCARTADA_CALCULO, _clave_extra, leer_csv, norm

logger = logging.getLogger(__name__)
PROVEEDOR = "deepinfra"
MODELO = "deepseek-ai/DeepSeek-V3.2"
VEREDICTOS = ("VALIDA", "NO_VALIDA", "DUDOSA")
ARCHIVO_EXTRAS = "extras_revision.csv"
ARCHIVO_JUEZ = "extras_revision_juez.csv"
COLUMNAS_JUEZ = ["juez_veredicto", "juez_motivo"]

PROMPT_SISTEMA = (
    "Sos un revisor técnico independiente. Un sistema automático marcó una brecha en una oferta técnica contra un artículo de una norma. "
    "Decidí si la brecha es real, usando SOLO lo que se muestra.\n"
    "- VALIDA: las oraciones citadas incumplen lo que exige el artículo, o la oferta omite información que el artículo o el contenido mínimo "
    "de la oferta (NORM_07 Art. 2.6) exigen.\n"
    "- NO_VALIDA: las oraciones cumplen el requisito, no tratan la materia del artículo, o el artículo no aplica a lo que dice la oferta.\n"
    "- DUDOSA: con el texto mostrado no se puede decidir.\n"
    'Respondé un JSON con "motivo" (hasta 30 palabras) y "veredicto".')


class VeredictoJuez(BaseModel):
    motivo: str = Field(description="Por qué ese veredicto (hasta 30 palabras).")
    veredicto: Literal["VALIDA", "NO_VALIDA", "DUDOSA"]


def cargar_criterios() -> dict:
    with open(os.path.join(config.DIRECTORIO_LINEAMIENTOS, "criterios_empresa.json"), encoding="utf-8") as f:
        return json.load(f)


def clave_brecha(b: dict) -> tuple:
    return _clave_extra(b.get("seccion_oferta") or b.get("seccion"), b.get("norma"), b.get("articulo"), b.get("cita"))


def clave_fila(r: dict) -> tuple:
    return _clave_extra(r.get("seccion"), r.get("norma"), r.get("articulo"), r.get("cita"))


def armar_mensajes(b: dict, contenido_minimo) -> list:
    """Mensajes para el juez a partir de una brecha del registro_brechas."""
    oraciones = b.get("oraciones_texto") or {}
    citadas = "\n".join(f"[{i}] {t}" for i, t in oraciones.items()) or str(b.get("cita") or "")
    sistema = [f"Sección de la oferta: {b.get('seccion_oferta') or b.get('seccion')}",
               f"Oraciones citadas de la oferta:\n{citadas}",
               f"Artículo {b.get('norma')} Art. {b.get('articulo')}:\n{b.get('texto_articulo') or '(sin texto)'}",
               f"Contenido mínimo de la oferta (NORM_07 Art. 2.6):\n{json.dumps(contenido_minimo, ensure_ascii=False)}",
               f"Título del sistema: {b.get('titulo') or ''}\nEnunciado: {b.get('enunciado') or ''}\nMotivo: {b.get('motivo') or ''}"]
    return [SystemMessage(content=PROMPT_SISTEMA), HumanMessage(content="\n\n".join(sistema))]


def juzgar(cliente, b: dict, contenido_minimo) -> dict:
    """{'veredicto', 'motivo'} de una brecha; un reintento si la respuesta no es un JSON válido. Puede levantar PresupuestoAgotado."""
    mensajes, error = armar_mensajes(b, contenido_minimo), ""
    for _ in range(2):
        try:
            v = VeredictoJuez.model_validate_json(cliente.invocar(mensajes).content)
            return {"veredicto": v.veredicto, "motivo": v.motivo.strip()}
        except LlamadaFallida as e:
            return {"veredicto": "", "motivo": f"llamada fallida: {e}"[:200]}
        except ValueError as e:         # pydantic.ValidationError es un ValueError
            error = str(e)[:120]
    return {"veredicto": "", "motivo": f"respuesta inválida: {error}"}


def procesar_json(ruta: str, cliente, contenido_minimo, concurrencia: int, max_items=None, rehacer=False) -> dict:
    carpeta = os.path.dirname(os.path.abspath(ruta))
    ruta_extras, ruta_juez = os.path.join(carpeta, ARCHIVO_EXTRAS), os.path.join(carpeta, ARCHIVO_JUEZ)
    if not os.path.isfile(ruta_extras):
        raise SystemExit(f"Falta {ruta_extras}: corré antes evaluar.py sobre {os.path.basename(ruta)}.")
    with open(ruta, encoding="utf-8") as f:
        resultado = json.load(f)
    brechas = {}
    for b in resultado.get("registro_brechas") or []:
        if b.get("estado") != ESTADO_DESCARTADA_CALCULO:
            brechas.setdefault(clave_brecha(b), b)
    with open(ruta_extras, encoding="utf-8-sig", newline="") as f:
        columnas = list(csv.DictReader(f, delimiter=";").fieldnames or [])
    filas = leer_csv(ruta_extras)
    previas = {clave_fila(r): r for r in leer_csv(ruta_juez)} if os.path.isfile(ruta_juez) else {}
    for r in filas:
        p = previas.get(clave_fila(r)) or {}
        r["juez_veredicto"], r["juez_motivo"] = p.get("juez_veredicto", ""), p.get("juez_motivo", "")
        if p.get("valido", "").strip():     # la marca humana que se volcó en el CSV del juez no se pierde
            r["valido"] = p["valido"]
    pendientes = [r for r in filas if rehacer or r["juez_veredicto"] not in VEREDICTOS]
    sin_brecha = [r for r in pendientes if clave_fila(r) not in brechas]
    for r in sin_brecha:
        r["juez_motivo"] = "brecha no encontrada en el JSON"
    pendientes = [r for r in pendientes if r not in sin_brecha][:max_items]

    def tarea(r):
        try:
            return juzgar(cliente, brechas[clave_fila(r)], contenido_minimo)
        except PresupuestoAgotado:
            return None
    with ThreadPoolExecutor(max_workers=max(1, concurrencia)) as pool:
        respuestas = list(pool.map(tarea, pendientes))
    detenida = any(x is None for x in respuestas)
    for r, x in zip(pendientes, respuestas):
        if x:
            r["juez_veredicto"], r["juez_motivo"] = x["veredicto"], x["motivo"]
    with open(ruta_juez, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas + COLUMNAS_JUEZ, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)
    cuentas = {v: sum(r["juez_veredicto"] == v for r in filas) for v in VEREDICTOS}
    return {"json": ruta, "csv": ruta_juez, "items": len(filas), "juzgados": sum(x is not None for x in respuestas), "sin_brecha": len(sin_brecha),
            "cuentas": cuentas, "sin_veredicto": sum(r["juez_veredicto"] not in VEREDICTOS for r in filas), "detenida": detenida}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Juez externo de precisión sobre las brechas que no son trampas")
    p.add_argument("jsons", nargs="+", metavar="JSON", help="JSON(s) de análisis (con extras_revision.csv al lado)")
    p.add_argument("--max-items", type=int, help="juzga solo las primeras N brechas pendientes de cada JSON (prueba de humo)")
    p.add_argument("--concurrencia", type=int, default=config.NUBE_CONCURRENCIA)
    p.add_argument("--rehacer", action="store_true", help="vuelve a juzgar las brechas que ya tienen veredicto")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
    if MODELO not in config.PRECIOS_NUBE:
        print(f"El modelo «{MODELO}» no tiene precio en config.PRECIOS_NUBE: no se arranca.", file=sys.stderr)
        return 2
    gasto = Gasto(config.PRECIOS_NUBE[MODELO], config.PRESUPUESTO_JUEZ_USD)
    try:
        llm = lambda esquema: rag_components.get_llm_openai_compatible(PROVEEDOR, MODELO, esquema=esquema)
        cliente = ClienteNube(llm(VeredictoJuez), gasto, respaldo=llm(None), nombre="VeredictoJuez")
        contenido_minimo = cargar_criterios()["contenido_minimo_oferta"]
    except (ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    detenida = False
    for ruta in a.jsons:
        if detenida:
            break
        s = procesar_json(ruta, cliente, contenido_minimo, a.concurrencia, a.max_items, a.rehacer)
        detenida = s["detenida"]
        print(f"\n{os.path.basename(ruta)}: {s['items']} brechas | juzgadas ahora {s['juzgados']} | " + " | ".join(f"{k} {v}" for k, v in s["cuentas"].items())
              + f" | sin veredicto {s['sin_veredicto']}" + (f" | no encontradas en el JSON {s['sin_brecha']}" if s["sin_brecha"] else ""))
        print(f"  CSV: {s['csv']}" + ("\n  DETENIDA: se alcanzó el freno de gasto; volvé a correr el mismo comando para completar." if detenida else ""))
    print(f"\nGasto del juez: {gasto.usd:.4f} USD de {config.PRESUPUESTO_JUEZ_USD} USD ({gasto.entrada} tokens de entrada, {gasto.salida} de salida)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
