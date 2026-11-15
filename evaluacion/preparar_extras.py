# evaluacion/preparar_extras.py
"""Prepara el <json>_extras.csv de una configuración para etiquetar los extras (brechas que no son una trampa encontrada ni caen sobre un caso conforme: la misma lista que
evaluar.evaluar) y calcular la precisión con tabla_comparativa.

Uso (lo corre el usuario: lee datos/Resultados):
  python -m evaluacion.preparar_extras --config "gpt-oss-120b esfuerzo bajo (elegida)" [--ofertas P3 P4] [--archivo-config evaluacion/config_reeval.json]
                                       [--salida <csv de pendientes>] [--forzar]
  (--ofertas P1 P2 para las de desarrollo; por defecto P3 P4)

Por cada oferta escribe <json>_extras.csv junto al JSON. Columnas que lee tabla_comparativa (evaluar.evaluar_archivo): oferta, seccion, norma, articulo, cita, titulo, clase y valido (sí/no;
la clave de cada extra es sección, norma, artículo y cita). Más, para etiquetar sin abrir nada más: id, texto_articulo (hasta 800 caracteres), veredicto_verificador, explicacion_verificador,
tipo_brecha (la fuente de la clasificación: DESVIO, EXCEPCION_NO_ACREDITADA, INFORMACION_FALTANTE), origen, etiqueta y nota. La cita es el texto completo de las oraciones citadas.
Etiquetas válidas, como las del juez: VALIDA, NO_VALIDA, DUDOSA. «valido» se deriva de ellas (VALIDA = sí, NO_VALIDA = no; DUDOSA no se puede contar y queda vacío hasta decidirla).
Herencia: si en la carpeta del JSON hay CSV ya etiquetados (*_extras.csv, extras_revision.csv), se hereda la etiqueta de la fila que coincide en norma, artículo y cita normalizada con
evaluar.norm (origen «heredada», con el archivo en «nota»); si no, origen «pendiente». Si dos archivos se contradicen no se hereda ninguna y la nota lo dice.
Las pendientes de todas las ofertas pedidas se juntan en --salida (por defecto evaluacion/diagnosticos/extras_pendientes_<configuración>_<ofertas>.csv, p. ej. extras_pendientes_gpt-oss-120b-esfuerzo-bajo-elegida_P1P2.csv; --pendientes es un alias) para etiquetarlas en un solo archivo;
aplicar_etiquetas.py vuelca esas etiquetas a cada <json>_extras.csv.
NUNCA pisa un <json>_extras.csv que ya existe; el de pendientes tampoco, salvo con --forzar. No corras evaluar.py sobre un CSV ya etiquetado: guardar_extras_csv lo reescribe con sus 8 columnas
de siempre (conserva «valido» pero pierde las demás)."""
import argparse
import csv
import glob
import os
import re
import sys

from . import evaluar as E

AQUI = E.AQUI
RAIZ = os.path.dirname(AQUI)
CONFIG_REEVAL = os.path.join(AQUI, "config_reeval.json")
DIAGNOSTICOS = os.path.join(AQUI, "diagnosticos")
LARGO_ARTICULO = 800
ETIQUETAS = ("VALIDA", "NO_VALIDA", "DUDOSA")
VALIDO_DE = {"VALIDA": "sí", "NO_VALIDA": "no", "DUDOSA": ""}            # lo que lee tabla_comparativa en «valido»
COLUMNAS = ["id", "oferta", "seccion", "norma", "articulo", "cita", "texto_articulo", "veredicto_verificador", "explicacion_verificador", "tipo_brecha", "clase", "titulo",
            "origen", "etiqueta", "valido", "nota"]
COLUMNAS_PENDIENTES = ["archivo"] + [c for c in COLUMNAS if c not in ("origen", "valido")]
COMANDO_TABLA = r"venv\Scripts\python.exe -m evaluacion.tabla_comparativa --config evaluacion/config_reeval.json"


def normalizar_etiqueta(valor) -> str:
    """VALIDA / NO_VALIDA / DUDOSA a partir de lo escrito («valida», «no valida», «NO-VALIDA»); '' si no es una etiqueta válida."""
    v = E.norm(valor).upper().replace(" ", "_").replace("-", "_")
    return v if v in ETIQUETAS else ""


def etiqueta_de_fila(fila: dict) -> str:
    """La etiqueta de una fila de un CSV: la columna «etiqueta» si es válida; si no, «valido» (sí = VALIDA, no = NO_VALIDA, como las marcas humanas de siempre)."""
    return normalizar_etiqueta(fila.get("etiqueta")) or {"si": "VALIDA", "no": "NO_VALIDA"}.get(E.norm(fila.get("valido")), "")


def clave_herencia(norma, articulo, cita) -> tuple:
    """(norma, artículo, cita normalizada con evaluar.norm): con lo que se reconoce que dos extras son el mismo."""
    return (str(norma or "").strip(), E._articulo(articulo), E.norm(cita))


def cargar_etiquetas(carpeta: str, excluir: str = None) -> dict:
    """{clave: {'valor': etiqueta | None, 'fuentes': {archivo: etiqueta}}} con las filas ya etiquetadas de los *_extras.csv y extras_revision.csv de la carpeta. Si dos archivos se
    contradicen para la misma clave, 'valor' queda en None (conflicto)."""
    excluir = os.path.abspath(excluir) if excluir else None
    archivos = sorted(set(glob.glob(os.path.join(carpeta, "*_extras.csv")) + glob.glob(os.path.join(carpeta, "extras_revision.csv"))))
    etiquetas = {}
    for ruta in archivos:
        if excluir and os.path.abspath(ruta) == excluir:
            continue
        for r in E.leer_csv(ruta):
            et = etiqueta_de_fila(r)
            if et:
                etiquetas.setdefault(clave_herencia(r.get("norma"), r.get("articulo"), r.get("cita")), {"valor": None, "fuentes": {}})["fuentes"][os.path.basename(ruta)] = et
    for e in etiquetas.values():
        distintas = set(e["fuentes"].values())
        e["valor"] = next(iter(distintas)) if len(distintas) == 1 else None
    return etiquetas


def _resumen_articulo(texto) -> str:
    plano = " ".join(str(texto or "").split())
    return plano if len(plano) <= LARGO_ARTICULO else plano[:LARGO_ARTICULO].rstrip() + "…"


def brecha_de_cada_extra(extras: list, brechas: list) -> list:
    """La brecha de registro_brechas de cada extra (en orden), emparejada por la misma clave que usa evaluar (sección, norma, artículo y cita); None si no se encuentra."""
    pendientes = {}
    for b in brechas:
        pendientes.setdefault(E._clave_extra(b.get("seccion_oferta") or b.get("seccion"), b.get("norma"), b.get("articulo"), b.get("cita")), []).append(b)
    return [(pendientes.get(E._clave_extra(x["seccion"], x["norma"], x["articulo"], x["cita"])) or [None]).pop(0) for x in extras]


def filas_de_extras(extras: list, brechas: list, etiquetas: dict) -> list:
    """Una fila por extra, con el contexto para etiquetarlo: heredada (con su etiqueta) o pendiente."""
    filas = []
    for x, b in zip(extras, brecha_de_cada_extra(extras, brechas)):
        b = b or {}
        verificacion = b.get("verificacion_previa") or {}
        fila = {c: "" for c in COLUMNAS}
        fila.update({c: x.get(c) if x.get(c) is not None else "" for c in ("oferta", "seccion", "norma", "articulo", "cita", "titulo", "clase")})
        fila.update(id=b.get("id") or "", texto_articulo=_resumen_articulo(b.get("texto_articulo")), veredicto_verificador=verificacion.get("veredicto") or "",
                    explicacion_verificador=" ".join(str(verificacion.get("explicacion") or "").split()), tipo_brecha=b.get("fuente") or "", origen="pendiente")
        previa = etiquetas.get(clave_herencia(x["norma"], x["articulo"], x["cita"]))
        if previa and previa["valor"]:
            fila.update(origen="heredada", etiqueta=previa["valor"], valido=VALIDO_DE[previa["valor"]], nota="heredada de " + ", ".join(previa["fuentes"]))
        elif previa:       # etiquetas previas que se contradicen: no se hereda ninguna
            fila["nota"] = "conflicto entre etiquetas previas: " + "; ".join(f"{a} = {v}" for a, v in previa["fuentes"].items())
        filas.append(fila)
    return filas


def nombre_pendientes(configuracion: str, ofertas: list) -> str:
    """Nombre del archivo unificado de pendientes: extras_pendientes_<configuración>_<ofertas>.csv; la configuración va en [a-z0-9.-] y las ofertas pegadas
    (p. ej. «gpt-oss-120b esfuerzo bajo (elegida)» con P1 y P2 -> extras_pendientes_gpt-oss-120b-esfuerzo-bajo-elegida_P1P2.csv)."""
    modelo = re.sub(r"[^a-z0-9.\-]+", "-", configuracion.lower()).strip("-") or "config"
    return f"extras_pendientes_{modelo}_{''.join(sorted(ofertas))}.csv"


def ruta_pendientes(configuracion: str, ofertas: list, carpeta: str = None) -> str:
    return os.path.join(carpeta or DIAGNOSTICOS, nombre_pendientes(configuracion, ofertas))


def _escribir_nuevo(filas: list, columnas: list, ruta: str, forzar: bool = False) -> None:
    """Escribe el CSV solo si no existe («x» falla si apareció entre medio): nunca pisa, salvo con `forzar`."""
    with open(ruta, "w" if forzar else "x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)


def escribir_csv_nuevo(filas: list, ruta: str) -> None:
    _escribir_nuevo(filas, COLUMNAS, ruta)


def ruta_relativa(ruta: str) -> str:
    """Ruta relativa a la raíz del repo y con «/» (para que el archivo de pendientes no lleve rutas de la máquina)."""
    return os.path.relpath(os.path.abspath(ruta), RAIZ).replace("\\", "/")


def filas_pendientes(filas: list, ruta_extras: str) -> list:
    """Las filas pendientes con el archivo de destino (relativo a la raíz del repo), para el CSV unificado."""
    return [{**f, "archivo": ruta_relativa(ruta_extras)} for f in filas if f["origen"] == "pendiente"]


def preparar_oferta(oferta: str, ruta_json: str, gt: list, espejos: list) -> dict:
    """Prepara el CSV de extras de un JSON. Devuelve {'oferta', 'ruta', 'estado': 'creado' | 'ya existe' | 'sin brechas', 'extras', 'heredadas', 'pendientes', 'filas_pendientes'}."""
    ruta = E.ruta_extras(ruta_json)
    salida = {"oferta": oferta, "ruta": ruta, "estado": "creado", "extras": 0, "heredadas": 0, "pendientes": 0, "filas_pendientes": []}
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
    salida.update(extras=len(filas), heredadas=sum(f["origen"] == "heredada" for f in filas), pendientes=sum(f["origen"] == "pendiente" for f in filas),
                  filas_pendientes=filas_pendientes(filas, ruta))
    return salida


def main(argv=None):
    p = argparse.ArgumentParser(description="Prepara el <json>_extras.csv de una configuración para etiquetar sus extras (nunca pisa un archivo existente)")
    p.add_argument("--config", required=True, help="nombre de la configuración en el archivo de configuración, p. ej. «gpt-oss-120b esfuerzo bajo (elegida)»")
    p.add_argument("--ofertas", nargs="+", default=["P3", "P4"], help="ofertas a preparar (por defecto P3 P4; P1 P2 para las de desarrollo)")
    p.add_argument("--archivo-config", default=CONFIG_REEVAL, help="config de tabla_comparativa de donde salen los JSON (por defecto evaluacion/config_reeval.json)")
    p.add_argument("--salida", "--pendientes", dest="salida", default=None,
                   help="CSV unificado con las pendientes de todas las ofertas; por defecto evaluacion/diagnosticos/extras_pendientes_<configuración>_<ofertas>.csv")
    p.add_argument("--forzar", action="store_true", help="pisa el CSV unificado de pendientes si ya existe (nunca toca los <json>_extras.csv)")
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
            print(f"{oferta}: ya existe {r['ruta']}; no se toca (sus pendientes no entran al archivo unificado).")
        else:
            print(f"{oferta}: el JSON no tiene brechas (modo lista); no hay extras que etiquetar.")
    creados = [r for r in resultados if r["estado"] == "creado"]
    if creados:
        print(f"Total: {sum(r['extras'] for r in creados)} extras: {sum(r['heredadas'] for r in creados)} heredadas, {sum(r['pendientes'] for r in creados)} pendientes.")
        pendientes = [f for r in creados for f in r["filas_pendientes"]]
        destino = a.salida or ruta_pendientes(a.config, a.ofertas)
        if os.path.exists(destino) and not a.forzar:
            print(f"Ya existe {destino}: no se toca (usá --forzar para pisarlo o --salida con otro nombre).")
        elif pendientes:
            os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
            _escribir_nuevo(pendientes, COLUMNAS_PENDIENTES, destino, forzar=a.forzar)
            print(f"Pendientes de todas las ofertas ({len(pendientes)}) en {destino}. Etiquetá la columna «etiqueta» con VALIDA, NO_VALIDA o DUDOSA y volcalas con aplicar_etiquetas.")
        print("Después de volcar las etiquetas, corré la tabla:\n  " + COMANDO_TABLA)
    return resultados


if __name__ == "__main__":
    main()
