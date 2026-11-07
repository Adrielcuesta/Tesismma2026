# scripts/motor_riesgos.py
"""Motor de evaluación de riesgos: aplica los criterios de la empresa. Sin LLM.
Todos los parámetros (umbral, probabilidades, matriz, responsables, RBS, solicitudes) salen de `criterios`
(criterios_empresa.json); aquí no hay nombres de normas, gerencias, umbrales ni matrices."""
import re

FUENTES = ("DESVIO", "EXCEPCION_NO_ACREDITADA", "INFORMACION_FALTANTE")
CONDICIONES_CRITICO = ("a", "b", "c", "d")
OBJETOS_REQUISITO = ("DOCUMENTAL_PROCEDIMIENTO", "RESERVA_ERGONOMIA_EFICIENCIA", "VERIFICACION_RUTINA", "ENSAYO_ACEPTACION",
                     "ORDINAL", "CUANTITATIVO_TECNICO", "OTRO_TECNICO")
TIPOS_LIMITE = ("MINIMO", "MAXIMO", "TOLERANCIA", "CANTIDAD", "FRECUENCIA")
DIMENSION_PERSONAS = "Seguridad de personas"   # Art. 4.3: dimensión que activa la regla 3.3.e
MARCA_BRECHA_NULA = "brecha nula: revisar veredicto"


# --- Números y brecha ---

def _numero(valor):
    """Primer número de un texto, con coma decimal y punto de miles ('1.676' -> 1676, '0,05' -> 0.05); None si no hay."""
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    m = re.search(r'\d[\d.,]*', str(valor))
    if not m:
        return None
    t = m.group(0).rstrip('.,')
    if ',' in t and '.' in t:
        decimal = ',' if t.rfind(',') > t.rfind('.') else '.'
        t = t.replace('.' if decimal == ',' else ',', '').replace(decimal, '.')
    elif ',' in t:
        t = t.replace(',', '') if t.count(',') > 1 else t.replace(',', '.')
    elif '.' in t and not t.startswith('0.') and (t.count('.') > 1 or re.fullmatch(r'\d{1,3}\.\d{3}', t)):
        t = t.replace('.', '')
    try:
        return float(t)
    except ValueError:
        return None


def brecha_relativa(ofertado, exigido, tipo_limite):
    """Art. 3.5. Brecha relativa entre lo ofertado y lo exigido; None si no se puede calcular.
    MINIMO y CANTIDAD cuentan solo si ofertado < exigido; MAXIMO y FRECUENCIA solo si ofertado > exigido (si no, 0.0);
    TOLERANCIA compara amplitudes: (ofertado - exigido) / exigido. Nunca es negativa: si la oferta es más estricta, 0.0."""
    o, e = _numero(ofertado), _numero(exigido)
    if o is None or e is None or e == 0:
        return None
    if tipo_limite in ("MINIMO", "CANTIDAD"):
        return (e - o) / e if o < e else 0.0
    if tipo_limite in ("MAXIMO", "FRECUENCIA"):
        return (o - e) / e if o > e else 0.0
    if tipo_limite == "TOLERANCIA":
        return max(0.0, (abs(o) - abs(e)) / abs(e))
    return None


# --- Clase ---

def clase(fuente, condicion_critico, objeto_requisito, brecha, riesgo_personas, criterios):
    """Art. 3.6.1. Devuelve (clase, regla, marcas): se evalúa en orden y se adopta la primera regla que se cumple.
    marcas: ['brecha nula: revisar veredicto'] si la brecha calculada es 0 (el veredicto genera riesgo, pero lo ofertado cumple); se clasifica igual.
    Información faltante: Mayor si condicion_critico == 'a', Menor si no (Art. 3.6.4), sin pasar por la tabla.
    Excepción no acreditada: mismas reglas que el desvío (Art. 3.6.5)."""
    if fuente not in FUENTES:
        raise ValueError(f"fuente desconocida: {fuente!r}")
    marcas = [MARCA_BRECHA_NULA] if brecha == 0 else []
    c, regla = _clase_y_regla(fuente, condicion_critico, objeto_requisito, brecha, riesgo_personas, criterios)
    return c, regla, marcas


def _clase_y_regla(fuente, condicion_critico, objeto_requisito, brecha, riesgo_personas, criterios):
    if fuente == "INFORMACION_FALTANTE":
        return ("Mayor" if condicion_critico == "a" else "Menor"), "3.6.4"
    if condicion_critico in CONDICIONES_CRITICO:
        return "Crítico", f"3.2.{condicion_critico}"
    if objeto_requisito == "DOCUMENTAL_PROCEDIMIENTO":
        return "Menor", "3.4.c"
    if objeto_requisito == "RESERVA_ERGONOMIA_EFICIENCIA":
        return "Menor", "3.4.d"
    if objeto_requisito == "VERIFICACION_RUTINA":
        return "Menor", "3.4.b"
    if objeto_requisito == "ENSAYO_ACEPTACION":
        return "Mayor", "3.3.b"
    if objeto_requisito == "ORDINAL":
        return "Mayor", "3.3.d"
    if objeto_requisito == "CUANTITATIVO_TECNICO":
        if brecha is None:
            return "Mayor", "3.3.c"     # Art. 3.5: no cuantificable
        if brecha >= criterios["umbral_brecha_relativa"]["valor"]:
            return "Mayor", "3.3.a"
        return ("Mayor", "3.3.e") if riesgo_personas else ("Menor", "3.4.a")
    if objeto_requisito == "OTRO_TECNICO":
        return "Mayor", "3.3.c"
    raise ValueError(f"objeto_requisito desconocido: {objeto_requisito!r}")


# --- Probabilidad, impacto, nivel, estrategia ---

def _rango(claves):
    """{valor: posición}: las listas del JSON declaran sus valores de mayor a menor (más alto = número mayor)."""
    claves = list(claves)
    return {k: len(claves) - i for i, k in enumerate(claves)}


def rango_clase(criterios):
    return _rango(criterios["rango_impacto_por_clase"]["valores"])


def rango_nivel(criterios):
    return _rango(criterios["estrategia_por_nivel"]["valores"])


def probabilidad(fuente, criterios):
    """Art. 4.2."""
    return criterios["probabilidad_por_fuente"]["valores"][fuente]


def acotar_impacto(clase_, impacto, criterios):
    """Art. 4.4. Devuelve (impacto acotado al rango de la clase, True si hubo ajuste)."""
    minimo, maximo = criterios["rango_impacto_por_clase"]["valores"][clase_]
    acotado = max(minimo, min(maximo, impacto))
    return acotado, acotado != impacto


def nivel(prob, impacto, criterios):
    """Art. 5.1. Matriz probabilidad (filas) x impacto 1 a 5 (columnas)."""
    return criterios["matriz_nivel"]["valores"][str(prob)][impacto - 1]


def aplicar_consistencia(clase_, nivel_, criterios):
    """Art. 5.3. Sube el nivel al mínimo o lo baja al máximo que la empresa fija para la clase."""
    orden = rango_nivel(criterios)
    c = criterios["consistencia"]
    minimo, maximo = c.get("nivel_minimo", {}).get(clase_), c.get("nivel_maximo", {}).get(clase_)
    if minimo and orden[nivel_] < orden[minimo]:
        return minimo
    if maximo and orden[nivel_] > orden[maximo]:
        return maximo
    return nivel_


def estrategia(nivel_, criterios):
    """Art. 7.3."""
    return criterios["estrategia_por_nivel"]["valores"][nivel_]


# --- Responsable, RBS, solicitud, umbral ---

def _primera_regla(reglas, norma, articulo, campo):
    """La primera regla que coincide por norma y, si tiene 'capitulos', por el capítulo (primer número del artículo)."""
    try:
        capitulo = int(str(articulo).split(".")[0])
    except ValueError:
        capitulo = None
    for r in reglas:
        if r["norma"] == norma and ("capitulos" not in r or capitulo in r["capitulos"]):
            return r[campo]
    return None


def responsable(norma, articulo, criterios):
    """Art. 7.4 (NORM_06 Cap. 2, según el JSON). Gerencia responsable de la norma y el capítulo; None si ninguna regla coincide."""
    return _primera_regla(criterios["responsables"]["reglas"], norma, articulo, "gerencia")


def rbs(norma, articulo, criterios):
    """Art. 6.3. Categoría RBS de la norma y el capítulo; None si ninguna regla coincide."""
    return _primera_regla(criterios["categorias_rbs"]["reglas"], norma, articulo, "rbs")


def solicitud(fuente, clase_, criterios):
    """Art. 8.4. Devuelve (tipo, plazo) de la primera regla que coincide por fuente y, si tiene 'clases', por clase."""
    for r in criterios["solicitudes_al_oferente"]["reglas"]:
        if r["fuente"] == fuente and ("clases" not in r or clase_ in r["clases"]):
            return r["tipo"], r["plazo"]
    return None, None


def umbral(pares):
    """Art. 7.5. 'NORM_0X, Art. X.Y' por cada par (norma, artículo), sin repetir y separados por '; '."""
    vistos = []
    for norma, articulo in pares:
        texto = f"{norma}, Art. {articulo}"
        if texto not in vistos:
            vistos.append(texto)
    return "; ".join(vistos)


# --- Agrupamiento, decisión, top 5 ---

def _clave_mayor(b, criterios):
    return (rango_clase(criterios)[b["clase"]], rango_nivel(criterios)[b["nivel"]], b.get("impacto") or 0)


def _fusionar(brechas, criterios, **extra):
    """Un riesgo a partir de varias brechas: cita todos los artículos; clase y nivel más altos; responsable y RBS de la brecha mayor (Art. 7.4)."""
    principal = max(brechas, key=lambda b: _clave_mayor(b, criterios))
    pares = [(b["norma"], b["articulo"]) for b in brechas]
    citas = []
    for p in pares:
        if {"norma": p[0], "articulo": p[1]} not in citas:
            citas.append({"norma": p[0], "articulo": p[1]})
    oraciones = sorted({o for b in brechas for o in b.get("oraciones", [])}, key=lambda o: (len(o), o))
    riesgo = {
        "seccion": principal.get("seccion"), "oraciones": oraciones, "brechas": [b.get("id") for b in brechas], "citas": citas,
        "clase": max((b["clase"] for b in brechas), key=lambda c: rango_clase(criterios)[c]),
        "nivel": max((b["nivel"] for b in brechas), key=lambda n: rango_nivel(criterios)[n]),
        "impacto": max(b.get("impacto") or 0 for b in brechas),
        "probabilidad": max(b.get("probabilidad") or 0 for b in brechas),
        "fuente": principal.get("fuente"), "dimension_impacto": principal.get("dimension_impacto"), "regla": principal.get("regla"),
        "rbs": principal.get("rbs"), "responsable": principal.get("responsable"),
        "titulo": principal.get("titulo"), "enunciado": principal.get("enunciado"), "accion": principal.get("accion"),
        "umbral": umbral(pares),
    }
    riesgo["estrategia"] = estrategia(riesgo["nivel"], criterios)
    riesgo.update(extra)
    return riesgo


def agrupar(brechas, criterios):
    """Art. 6.1 y 6.2. No modifica `brechas` (el registro sin agrupar se conserva completo).
    6.1: las brechas de una misma sección que citan las mismas oraciones forman un riesgo.
    6.2: los riesgos de clase Menor (incluidas las consultas técnicas Menores) de una misma categoría RBS que no quedaron
    agrupados en otro riesgo se juntan en un ítem 'Aclaraciones menores: <categoría>' (solo si son dos o más).
    Los de otra clase (p. ej. información faltante Mayor) quedan como riesgo individual."""
    grupos = {}
    for b in brechas:
        grupos.setdefault((b.get("seccion"), tuple(sorted(b.get("oraciones", [])))), []).append(b)
    riesgos = [_fusionar(g, criterios) for g in grupos.values()]

    menor = list(criterios["rango_impacto_por_clase"]["valores"])[-1]
    sueltos = {}
    for r in riesgos:
        if len(r["brechas"]) == 1 and r["clase"] == menor:
            sueltos.setdefault(r["rbs"], []).append(r)
    for categoria, items in sueltos.items():
        if len(items) < 2:
            continue
        componentes = [b for b in brechas if b.get("id") in {i for r in items for i in r["brechas"]}]
        fusion = _fusionar(componentes, criterios, titulo=f"Aclaraciones menores: {categoria}", rbs=categoria,
                           enunciado="; ".join(r["titulo"] for r in items if r["titulo"]), agrupado_6_2=True)
        riesgos = [r for r in riesgos if not any(r is i for i in items)] + [fusion]
    return riesgos


def decision_aceptabilidad(riesgos, criterios):
    """Art. 5.4. Lee criterios['decision_aceptabilidad']: {'reglas': [{'decision', 'clases'?, 'niveles'?}], 'por_defecto'}.
    Una regla se cumple si algún riesgo satisface todas sus condiciones a la vez (clase y nivel sobre el MISMO riesgo);
    la primera que se cumple fija la decisión. Una regla sin condiciones nunca se cumple."""
    bloque = criterios["decision_aceptabilidad"]

    def cumple(riesgo, regla):
        return (("clases" in regla or "niveles" in regla)
                and ("clases" not in regla or riesgo["clase"] in regla["clases"])
                and ("niveles" not in regla or riesgo["nivel"] in regla["niveles"]))

    for r in bloque["reglas"]:
        if any(cumple(x, r) for x in riesgos):
            return r["decision"]
    return bloque["por_defecto"]


def top5(riesgos, criterios):
    """Art. 8.3. Los cinco mayores por nivel, después impacto, después clase."""
    c, n = rango_clase(criterios), rango_nivel(criterios)
    return sorted(riesgos, key=lambda r: (n[r["nivel"]], r.get("impacto") or 0, c[r["clase"]]), reverse=True)[:5]


def solicitudes(riesgos, brechas, criterios):
    """Art. 8.4. Una solicitud por riesgo. El pedido lista una línea por cada brecha del grupo, con su norma y artículo; el tipo y
    el plazo son los del componente de mayor clase. Ordenadas por clase y después por categoría RBS."""
    por_id = {b.get("id"): b for b in brechas}
    salida = []
    for r in riesgos:
        componentes = [por_id[i] for i in r["brechas"] if i in por_id]
        pedidos = [f"{b['norma']} Art. {b['articulo']}: {b['solicitud_oferente']}" for b in componentes if b.get("solicitud_oferente")]
        mayor = max(componentes, key=lambda b: _clave_mayor(b, criterios)) if componentes else r
        tipo, plazo = solicitud(mayor["fuente"], mayor["clase"], criterios)
        salida.append({"riesgo": r.get("id"), "tipo": tipo, "plazo": plazo, "citas": r["citas"], "oraciones": r["oraciones"],
                       "cita_oferta": " ".join(dict.fromkeys(b["cita"] for b in componentes)),
                       "pedido": "\n".join(pedidos), "clase": r["clase"], "responsable": r["responsable"], "rbs": r["rbs"]})
    orden = rango_clase(criterios)
    return sorted(salida, key=lambda s: (-orden[s["clase"]], s["rbs"] or ""))


def resumen_ejecutivo(riesgos, criterios):
    """Art. 8.3. Decisión de aceptabilidad, conteo por nivel y por clase, y top 5."""
    return {"decision": decision_aceptabilidad(riesgos, criterios),
            "por_nivel": {n: sum(1 for r in riesgos if r["nivel"] == n) for n in criterios["estrategia_por_nivel"]["valores"]},
            "por_clase": {c: sum(1 for r in riesgos if r["clase"] == c) for c in criterios["rango_impacto_por_clase"]["valores"]},
            "top5": [r.get("id") for r in top5(riesgos, criterios)]}
