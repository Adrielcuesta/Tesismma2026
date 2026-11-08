# scripts/reclasificar.py
"""Vuelve a aplicar motor_riesgos sobre el registro_brechas de un JSON guardado. Sin LLM: usa los hechos que ya extrajo el modelo.
Regenera riesgos, solicitudes, alertas, decisión y dashboard, y guarda un JSON nuevo con sufijo _reclasificado.

Uso: python -m scripts.reclasificar <json> [<json> ...]"""
import argparse
import copy
import json
import os
import re
import sys

from . import clasificacion, comentario, config, dashboard_generator, lineamientos
from .schemas import ClasificacionRiesgo

SUFIJO = "_reclasificado"


def _parte(id_brecha) -> int:
    m = re.search(r"#(\d+)$", str(id_brecha))
    return int(m.group(1)) if m else 1


def _clave_alerta(a) -> tuple:
    return (a["seccion"], a["norma"], a["articulo"], tuple(a["oraciones"]))


def _resumen_numerico(resumen) -> dict:
    return {k: (resumen or {}).get(k) for k in ("decision", "por_nivel", "por_clase")}


def _cambio(antes, despues) -> dict:
    return {"id": antes["id"], "estado_antes": antes.get("estado") or "riesgo", "estado_despues": despues.get("estado") or "riesgo",
            **{f"{k}_{lado}": d.get(k) for k in ("clase", "regla", "nivel") for lado, d in (("antes", antes), ("despues", despues))}}


def reclasificar(datos: dict, criterios: dict, huella: str, origen: str = "") -> tuple:
    """(datos nuevos, lista de cambios). `datos` no se modifica. La clase, el nivel, etc. se recalculan con `criterios` a partir de la
    clasificación (hechos) que guardó el modelo en cada brecha; el comentario general se conserva si el resumen no cambia, si no pasa a plantilla."""
    nuevo = copy.deepcopy(datos)
    brechas, nulas, alertas_ajenas, cambios = [], {}, [], []
    for b in datos.get("registro_brechas") or []:
        r = clasificacion.procesar_clasificacion(
            ClasificacionRiesgo(**b["clasificacion"]), id_sec=b["seccion"], seccion_oferta=b["seccion_oferta"], norma=b["norma"], articulo=b["articulo"],
            texto_articulo=b["texto_articulo"], oraciones=b["oraciones"], textos=b["oraciones_texto"], verificacion=b["verificacion_previa"],
            criterios=criterios, parte=_parte(b["id"]))
        if r["tipo"] == "alerta":
            alertas_ajenas.append(r["alerta"])
        if r["tipo"] not in ("brecha", "descartada_por_calculo"):   # el veredicto del modelo ya no genera brecha: sale del registro
            cambios.append({**_cambio(b, {}), "estado_despues": r["tipo"]})
            continue
        n = r["brecha"]
        if r["tipo"] == "brecha" and (b.get("verificacion_previa") or {}).get("discrepancia_numerica"):
            n["marcas"].append("verificar calculo")
        if r["tipo"] == "descartada_por_calculo":
            nulas[_clave_alerta(r["alerta"])] = r["alerta"]
        if "eval_count" in b:
            n["eval_count"] = b["eval_count"]
        brechas.append(n)
        if any(n.get(k) != b.get(k) for k in ("clase", "regla", "nivel", "estado")):
            cambios.append(_cambio(b, n))

    # las alertas se rehacen en su lugar: las de brecha nula que siguen vigentes conservan su posición, las nuevas van al final
    alertas = []
    for a in datos.get("alertas") or []:
        if a.get("origen") != "brecha_nula":
            alertas.append(a)
        elif _clave_alerta(a) in nulas:
            alertas.append(nulas.pop(_clave_alerta(a)))
    alertas += alertas_ajenas + list(nulas.values())

    riesgos, solicitudes, resumen = clasificacion.armar_salidas(brechas, criterios)
    previo = datos.get("resumen_ejecutivo") or {}
    if _resumen_numerico(resumen) == _resumen_numerico(previo) and previo.get("comentario_general"):
        resumen.update(comentario_general=previo["comentario_general"], origen_comentario=previo.get("origen_comentario"))
    else:
        resumen.update(comentario_general=comentario.plantilla(resumen, riesgos), origen_comentario="plantilla")
    nuevo.update(registro_brechas=brechas, riesgos=riesgos, solicitudes=solicitudes, alertas=alertas, resumen_ejecutivo=resumen)
    nuevo["reclasificacion"] = {"origen": origen, "huella_criterios": huella,
                                "huella_criterios_original": (datos.get("lineamientos") or {}).get("huella"), "cambios": cambios}
    return nuevo, cambios


def rutas_salida(ruta_json: str) -> tuple:
    base, ext = os.path.splitext(ruta_json)
    carpeta, nombre = os.path.split(base)
    return base + SUFIJO + ext, os.path.join(carpeta, re.sub(r"^analisis_riesgos_", "dashboard_", nombre) + SUFIJO + ".html")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reaplica motor_riesgos al registro_brechas de un JSON guardado, sin llamar al modelo.")
    ap.add_argument("json", nargs="+")
    args = ap.parse_args(argv)
    lin = lineamientos.cargar_lineamientos(config.DIRECTORIO_LINEAMIENTOS)
    for ruta in args.json:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        nuevo, cambios = reclasificar(datos, lin["criterios"], lin["huella"], origen=os.path.basename(ruta))
        ruta_json, ruta_html = rutas_salida(ruta)
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(nuevo, f, ensure_ascii=False, indent=4)
        dashboard_generator.generar_dashboard_html(ruta_json_resultados=ruta_json, ruta_output_dashboard_html=ruta_html, info_tesis_config=config.INFO_TESIS)
        print(f"{ruta}\n  -> {ruta_json}\n  -> {ruta_html}\n  huella de los criterios: {lin['huella']}\n  cambios: {len(cambios)}")
        for c in cambios:
            print(f"    {c['id']}: {c['clase_antes']} {c['regla_antes']} {c['nivel_antes']} ({c['estado_antes']}) -> "
                  f"{c['clase_despues']} {c['regla_despues']} {c['nivel_despues']} ({c['estado_despues']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
