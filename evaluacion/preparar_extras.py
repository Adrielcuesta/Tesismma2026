# evaluacion/preparar_extras.py
"""Prepara el <json>_extras.csv de una configuración para etiquetar los extras (brechas que no son trampa ni caso conforme) y calcular la precisión con tabla_comparativa.

Uso (lo corre el usuario: lee datos/Resultados):
  python -m evaluacion.preparar_extras --config "gpt-oss-120b esfuerzo bajo (elegida)" [--ofertas P3 P4] [--archivo-config evaluacion/config_reeval.json]
  (--ofertas P1 P2 para las ofertas de desarrollo; por defecto P3 P4)

Por cada oferta: evalúa el JSON de la configuración (evaluar.evaluar, la misma lista de extras que usa tabla_comparativa) y escribe <json>_extras.csv junto al JSON con las columnas que
tabla_comparativa lee (oferta, seccion, norma, articulo, cita, titulo, clase, valido) más:
  origen: «heredada» si una etiqueta previa coincide en norma, artículo y cita normalizada con evaluar.norm; «pendiente» si no (o si las etiquetas previas se contradicen);
  heredada_de: de qué CSV salió la etiqueta (en las pendientes con conflicto, qué dijo cada uno);
  para las pendientes, lo necesario para etiquetar sin abrir nada más: veredicto_verificador, explicacion_verificador, oracion_citada (con su ID), texto_articulo (hasta 600 caracteres).
Las etiquetas previas se buscan en *_extras.csv y extras_revision.csv de la carpeta del JSON (solo las filas con valido sí/no).
NUNCA pisa un CSV que ya existe: si <json>_extras.csv existe, lo deja como está. Completá «valido» (sí/no) en las pendientes. No corras evaluar.py sobre un CSV ya etiquetado:
guardar_extras_csv lo reescribe con las 8 columnas de siempre (conserva «valido» pero pierde las columnas de ayuda)."""
import argparse
import csv
import glob
import os
import sys

from . import evaluar as E

AQUI = E.AQUI
CONFIG_REEVAL = os.path.join(AQUI, "config_reeval.json")
LARGO_ARTICULO = 600
COLUMNAS = ["oferta", "seccion", "norma", "articulo", "cita", "titulo", "clase", "origen", "heredada_de", "veredicto_verificador", "explicacion_verificador", "oracion_citada",
            "texto_articulo", "valido"]
COMANDO_TABLA = r"venv\Scripts\python.exe -m evaluacion.tabla_comparativa --config evaluacion/config_reeval.json"


def clave_herencia(norma, articulo, cita) -> tuple:
    """(norma, artículo, cita normalizada con evaluar.norm): con lo que se reconoce que dos extras son el mismo."""
    return (str(norma or "").strip(), E._articulo(articulo), E.norm(cita))


def cargar_etiquetas(carpeta: str, excluir: str = None) -> dict:
    """{clave: {'valor': 'sí'|'no'|None, 'fuentes': {archivo: valor}}} con las filas sí/no de los *_extras.csv y extras_revision.csv de la carpeta. Si dos archivos se contradicen
    para la misma clave, 'valor' queda en None (conflicto)."""
    excluir = os.path.abspath(excluir) if excluir else None
    archivos = sorted(set(glob.glob(os.path.join(carpeta, "*_extras.csv")) + glob.glob(os.path.join(carpeta, "extras_revision.csv"))))
    etiquetas = {}
    for ruta in archivos:
        if excluir and os.path.abspath(ruta) == excluir:
            continue
        for r in E.leer_csv(ruta):
            marca = E.norm(r.get("valido"))
            if marca not in ("si", "no"):
                continue
            e = etiquetas.setdefault(clave_herencia(r.get("norma"), r.get("articulo"), r.get("cita")), {"valor": None, "fuentes": {}})
            e["fuentes"][os.path.basename(ruta)] = (r.get("valido") or "").strip()
    for e in etiquetas.values():
        distintos = {E.norm(v) for v in e["fuentes"].values()}
        e["valor"] = next(iter(e["fuentes"].values())) if len(distintos) == 1 else None
    return etiquetas


def _resumen_articulo(texto) -> str:
    plano = " ".join(str(texto or "").split())
    return plano if len(plano) <= LARGO_ARTICULO else plano[:LARGO_ARTICULO].rstrip() + "…"


def _oracion_citada(brecha: dict) -> str:
    textos = brecha.get("oraciones_texto") or {}
    ids = brecha.get("oraciones") or list(textos)
    return " ".join(f"[{i}] {' '.join(str(textos[i]).split())}" for i in ids if i in textos) or " ".join(str(brecha.get("cita") or "").split())


def brecha_de_cada_extra(extras: list, brechas: list) -> list:
    """La brecha de registro_brechas de cada extra (en orden), emparejada por la misma clave que usa evaluar (sección, norma, artículo y cita); None si no se encuentra."""
    pendientes = {}
    for b in brechas:
        pendientes.setdefault(E._clave_extra(b.get("seccion_oferta") or b.get("seccion"), b.get("norma"), b.get("articulo"), b.get("cita")), []).append(b)
    return [(pendientes.get(E._clave_extra(x["seccion"], x["norma"], x["articulo"], x["cita"])) or [None]).pop(0) for x in extras]


def filas_de_extras(extras: list, brechas: list, etiquetas: dict) -> list:
    """Una fila por extra: heredada (con su etiqueta) o pendiente (con el contexto para etiquetar)."""
    filas = []
    for x, b in zip(extras, brecha_de_cada_extra(extras, brechas)):
        fila = {c: "" for c in COLUMNAS}
        fila.update({c: x.get(c) if x.get(c) is not None else "" for c in ("oferta", "seccion", "norma", "articulo", "cita", "titulo", "clase")})
        previa = etiquetas.get(clave_herencia(x["norma"], x["articulo"], x["cita"]))
        if previa and previa["valor"]:
            fila.update(origen="heredada", valido=previa["valor"], heredada_de=", ".join(previa["fuentes"]))
        else:
            verificacion = (b or {}).get("verificacion_previa") or {}
            fila.update(origen="pendiente", veredicto_verificador=verificacion.get("veredicto") or "", explicacion_verificador=" ".join(str(verificacion.get("explicacion") or "").split()),
                        oracion_citada=_oracion_citada(b) if b else " ".join(str(x.get("cita") or "").split()), texto_articulo=_resumen_articulo((b or {}).get("texto_articulo")))
            if previa:       # etiquetas previas que se contradicen: no se hereda ninguna
                fila["heredada_de"] = "conflicto: " + "; ".join(f"{a} = {v}" for a, v in previa["fuentes"].items())
        filas.append(fila)
    return filas


def escribir_csv_nuevo(filas: list, ruta: str) -> None:
    """Escribe el CSV solo si no existe («x» falla si apareció entre medio): nunca pisa."""
    with open(ruta, "x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, delimiter=";")
        w.writeheader()
        w.writerows(filas)


def preparar_oferta(oferta: str, ruta_json: str, gt: list, espejos: list) -> dict:
    """Prepara el CSV de extras de un JSON. Devuelve {'oferta', 'ruta', 'estado': 'creado' | 'ya existe' | 'sin brechas', 'extras', 'heredadas', 'pendientes'}."""
    ruta = E.ruta_extras(ruta_json)
    salida = {"oferta": oferta, "ruta": ruta, "estado": "creado", "extras": 0, "heredadas": 0, "pendientes": 0}
    if os.path.exists(ruta):
        salida["estado"] = "ya existe"
        return salida
    resultado = E._cargar(ruta_json)
    ev = E.evaluar(resultado, gt, espejos, oferta)
    if ev["modo"] != "brechas":
        salida["estado"] = "sin brechas"
        return salida
    filas = filas_de_extras(ev["extras"], resultado.get("registro_brechas") or [], cargar_etiquetas(os.path.dirname(os.path.abspath(ruta_json)), ruta))
    escribir_csv_nuevo(filas, ruta)
    salida.update(extras=len(filas), heredadas=sum(f["origen"] == "heredada" for f in filas), pendientes=sum(f["origen"] == "pendiente" for f in filas))
    return salida


def main(argv=None):
    p = argparse.ArgumentParser(description="Prepara el <json>_extras.csv de una configuración para etiquetar sus extras (nunca pisa uno existente)")
    p.add_argument("--config", required=True, help="nombre de la configuración en el archivo de configuración, p. ej. «gpt-oss-120b esfuerzo bajo (elegida)»")
    p.add_argument("--ofertas", nargs="+", default=["P3", "P4"], help="ofertas a preparar (por defecto P3 P4; P1 P2 para las de desarrollo)")
    p.add_argument("--archivo-config", default=CONFIG_REEVAL, help="config de tabla_comparativa de donde salen los JSON (por defecto evaluacion/config_reeval.json)")
    a = p.parse_args(argv)
    from . import tabla_comparativa as T
    cfg = T.cargar_config(a.archivo_config)
    if a.config not in cfg["configuraciones"]:
        raise SystemExit(f"No hay una configuración «{a.config}» en {a.archivo_config}. Hay: {', '.join(cfg['configuraciones'])}")
    rutas = {o: T.resolver_ruta(v, f"{a.config} / {o}") for o, v in cfg["configuraciones"][a.config].items() if o in a.ofertas}
    resultados = []
    for oferta in a.ofertas:
        ruta = rutas.get(oferta)
        if not ruta or not os.path.isfile(ruta):
            print(f"{oferta}: no hay JSON para «{a.config}»; se omite.", file=sys.stderr)
            continue
        r = preparar_oferta(oferta, ruta, E.cargar_gt(oferta), E.cargar_espejos(oferta))
        resultados.append(r)
        if r["estado"] == "creado":
            print(f"{oferta}: {r['extras']} extras: {r['heredadas']} heredadas, {r['pendientes']} pendientes -> {r['ruta']}")
        elif r["estado"] == "ya existe":
            print(f"{oferta}: ya existe {r['ruta']}; no se toca.")
        else:
            print(f"{oferta}: el JSON no tiene brechas (modo lista); no hay extras que etiquetar.")
    creados = [r for r in resultados if r["estado"] == "creado"]
    if creados:
        print(f"Total: {sum(r['extras'] for r in creados)} extras: {sum(r['heredadas'] for r in creados)} heredadas, {sum(r['pendientes'] for r in creados)} pendientes.")
        print("Completá «valido» (sí/no) en las filas con origen «pendiente» y después corré:\n  " + COMANDO_TABLA)
    return resultados


if __name__ == "__main__":
    main()
