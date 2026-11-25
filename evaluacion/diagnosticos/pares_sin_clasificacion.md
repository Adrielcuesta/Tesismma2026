# Pares con Incumple/Revisar que nunca llegaron al LLM2 (P6–P12, gpt-oss-120b, v1-congelada)

Diagnóstico hecho leyendo el código, sin datos nuevos. Los números por causa salen de `evaluacion/diagnostico_sin_clasificacion.py`, que corre el usuario; acá no se da ninguna cifra que el script no haya calculado todavía.

Punto de partida (de `datos/tmp_desacuerdos.py`): 2.551 pares (sección, norma, artículo) con LLM1 = Incumple/Revisar terminan sin brecha ni alerta. En 675 de ellos no hay ninguna entrada `etapa == "clasificacion"` en `registro_tecnico`, y en esos pares caen 10 trampas.

## 1. Flujo entre la verificación y la clasificación

`scripts/nube.py::_correr_seccion` ([nube.py:176](../../scripts/nube.py#L176)) llama a `scripts/main.py::_verificar_seccion` ([main.py:306](../../scripts/main.py#L306)), la misma función que la corrida local. Para cada fragmento (par sección-artículo, una entrada por parte del artículo):

1. Verificación (LLM1): `_invocar` + `_parsear_respuesta_llm` ([main.py:319-335](../../scripts/main.py#L319-L335)).
2. Validación por código: `rag_components.procesar_verificacion` ([rag_components.py:851-872](../../scripts/rag_components.py#L851-L872)) devuelve `(verificada | None, extra)`.
3. Se escribe la entrada de verificación en `registro_tecnico` con `veredicto = (verificada or original).veredicto` ([main.py:336-338](../../scripts/main.py#L336-L338)).
4. **Solo** pasa a la clasificación si `verificada` no es `None` y su veredicto es Incumple o Revisar ([main.py:339-340](../../scripts/main.py#L339-L340)).
5. Clasificación (LLM2), una llamada por cada pendiente ([main.py:345-386](../../scripts/main.py#L345-L386)). Según el resultado, el par termina en `registro_brechas`, en `alertas` o en `registro_tecnico` con `etapa: "clasificacion"`.

## 2. Caminos por los que un Incumple/Revisar del registro queda sin entrada de clasificación

| # | Camino | Archivo y línea | ¿Deja entrada `etapa: "clasificacion"`? | ¿Deja brecha o alerta? | ¿Intencional? |
|---|---|---|---|---|---|
| A1 | La verificación cita IDs de oración que no existen en la sección: `procesar_verificacion` devuelve `None`, `estado: "descartada"`, `motivo: "IDs de oración inexistentes: …"`. El registro **sigue mostrando el veredicto original (Incumple/Revisar)** porque guarda `final = verificada or original`. | [rag_components.py:858-861](../../scripts/rag_components.py#L858-L861), [main.py:337-339](../../scripts/main.py#L337-L339) | No | No | Sí, por la regla de auditabilidad: sin cita verificable no hay riesgo. Ver la nota de robustez (§4). |
| A2 | Incumple/Revisar sin ninguna oración citada: `None`, `estado: "descartada"`, `motivo: "sin oraciones de la oferta que respalden el veredicto"`. | [rag_components.py:870-871](../../scripts/rag_components.py#L870-L871) | No | No | Sí (misma regla). |
| B | La clasificación da una brecha (`tipo == "brecha"`) o «descartada por cálculo» (brecha con `estado` descartada + alerta). No se escribe entrada de clasificación en el registro: queda en `registro_brechas`. | [main.py:372-380](../../scripts/main.py#L372-L380), [clasificacion.py:127-154](../../scripts/clasificacion.py#L127-L154) | No | Sí (brecha) | Sí. No es un descarte: el script lo excluye si las claves coinciden (§3). |
| C | La clasificación dice `ALERTA`: solo va a `alertas`. | [main.py:381-382](../../scripts/main.py#L381-L382) | No | Sí (alerta) | Sí. Igual que B. |
| D | Se agota el tiempo o el formato falla en la clasificación (`tiempo_agotado`, `clasificacion_fallida`), o el LLM2 dice CUMPLE/NO_APLICA o las reglas 2.5/2.7.c, o la clasificación queda incompleta. | [main.py:356-363](../../scripts/main.py#L356-L363), [main.py:383-386](../../scripts/main.py#L383-L386), [clasificacion.py:91-105](../../scripts/clasificacion.py#L91-L105) | **Sí** | Solo en `tiempo_agotado` (alerta sin respuesta) | Sí. Estos son los 2.551 − 675 con «llm2» distinto de «—». |
| E | Excepción no prevista dentro de la sección (por ejemplo un error HTTP que no sea 429/5xx/conexión, o un error en `procesar_clasificacion`), o presupuesto agotado: `_correr_seccion` tira **todo** lo de la sección y deja una sola entrada `seccion_fallida` / `presupuesto_agotado`. | [nube.py:183-190](../../scripts/nube.py#L183-L190) | No | No | Sí (la corrida sigue). **No aporta a los 675**: tampoco quedan las entradas de verificación, así que el par no aparece como Incumple. `--reintentar-fallidas` vuelve a correr esas secciones (P7 es `-reintento`). |
| F | Verificación con tiempo agotado o formato inválido tras el reintento: `veredicto: None`. | [main.py:326-335](../../scripts/main.py#L326-L335) | No | Alerta `tiempo_agotado` (solo tiempo) | Sí. **No aporta**: sin veredicto no cuenta como Incumple. |
| G | Fusión del reintento (P7): en las secciones reintentadas que se completaron, todo lo del par fallido (verificación, clasificación, brecha, alerta) se reemplaza por lo nuevo, con la misma clave (norma, artículo). | [nube.py:406-427](../../scripts/nube.py#L406-L427) | Lo que diga el reintento | Lo que diga el reintento | Sí. No crea huérfanos: se reemplazan juntas todas las entradas del par. |

Otros caminos que se consideraron y **no existen** en el código:

- **Filtro previo por tipo de artículo**: no hay. Todo fragmento de `secciones[].fragmentos` se verifica y todo Incumple/Revisar válido se clasifica.
- **Deduplicación por sección o por parte**: no hay entre la verificación y la clasificación. Si un artículo tiene varias partes en la sección, cada parte se verifica y se clasifica por separado. El registro **no** guarda la parte: las entradas comparten la clave (sección, norma, artículo). La brecha sí la guarda, en el id (`…#2`).
- **Presupuesto por par**: no hay. El presupuesto corta la sección entera (camino E).
- **Errores capturados en silencio dentro del bucle de clasificación**: solo se capturan tiempo y formato (D), y los dos dejan entrada en el registro. Cualquier otra excepción sube y es el camino E.
- **Diferencia de mayúsculas en el veredicto**: `VerificacionArticulo` normaliza el veredicto a su literal ([schemas.py:117-120](../../scripts/schemas.py#L117-L120)), así que el registro y la condición de la línea 339 usan la misma cadena.

**Conclusión del código:** un par con Incumple/Revisar en la verificación y **sin** entrada de clasificación, brecha ni alerta solo puede venir de A1 o A2 (la validación de citas lo descartó, con `estado: "descartada"` en su entrada de verificación) o de un error de claves del script de análisis. Si el script encuentra un par así con `estado` `ok` o `discrepancia_numerica`, lo marca **inconsistente**: el código no explica ese caso y habría que mirarlo par por par.

## 3. Claves de `tmp_desacuerdos.py`

- **Brecha por id.** El script corta el id de la brecha en «#» (`S3|NORM_01|2.5#2` → `S3|NORM_01|2.5`) y lo compara con `f"{sección}|{norma}|{_articulo(artículo)}"` del registro. El id se arma con el artículo **sin** normalizar ([clasificacion.py:146](../../scripts/clasificacion.py#L146)) y el registro se normaliza con `_articulo` (quita espacios y un punto final). Hoy los dos salen de `str(d.metadata["articulo"])`, así que deberían coincidir. Con un artículo con punto final o con espacios dejarían de coincidir, y el par se contaría como descartado aunque tenga brecha. La versión nueva compara por los **campos** (`seccion`, `norma`, `articulo` normalizado) de la brecha y la alerta, y además informa cuántos pares dan distinto con una clave y con la otra. Si da 0, las cifras de `tmp_desacuerdos.py` (2.551 y 675) quedan confirmadas en ese punto.
- **Sufijo `#parte`**: bien resuelto en el script original (lo corta).
- **Formato del id de sección**: el registro, las brechas y las alertas usan el mismo `seccion["id"]` (`S<n>`); no hay diferencia.
- **Trampas por par: dos errores que cambian el «10 trampas».**
  1. `trampas[(s, norma, art)] = (id, severidad)` **pisa**: si dos trampas comparten sección y artículo (o un artículo equivalente), solo cuenta la última. Esto subestima.
  2. Una trampa se asocia a un par descartado solo por (sección, artículo), sin mirar su estado final. Puede estar **encontrada** por otra parte del mismo artículo o por otro par. Esto sobreestima lo que se pierde por los descartes.

  La versión nueva guarda una lista de trampas por par e informa el estado final y la pérdida de cada trampa según `evaluar()`.
- **Alertas sin respuesta** (`tiempo_agotado`): `tmp_desacuerdos.py` las cuenta como «terminó en alerta». Es correcto para la pregunta «¿llegó a algo?», pero `evaluar()` no las cuenta como alerta de contradicción. La versión nueva mantiene el criterio del script original para que los totales sean comparables.

## 4. ¿Hay un error real del pipeline?

Por el código, los 675 deberían ser todos A1 o A2. Eso es comportamiento **intencional**: sin cita verificable no hay riesgo. Aun así, hay dos puntos de **robustez** que el script cuantifica y que se proponen como trabajo futuro (v2), sin corregirlos ahora:

1. **IDs mal formados (`ids_inexistentes_malformados`).** `procesar_verificacion` solo normaliza espacios y mayúsculas (`i.strip().upper()`, [rag_components.py:858](../../scripts/rag_components.py#L858)). Un ID como `[O3]`, `O 3`, `3` o un rango `O3-O5` se toma como inexistente y el par entero se descarta, aunque la oración exista. Si el script encuentra pares en esta causa, es un **error de robustez del pipeline**: el modelo identificó la oración y el código la perdió por formato.
   *Propuesta v2:* normalizar los IDs antes de validar (quitar corchetes y espacios internos, `\d+` → `O\d+`, expandir rangos) y registrar la normalización como `normalizaciones_formato`.
2. **Descarte total por un solo ID inexistente (`ids_inexistentes_fuera_de_rango` con «válidas: …» en el detalle).** Si la verificación cita `["O3", "O99"]` y O99 no existe, se descarta el par aunque O3 sea válida. Está documentado en el docstring, así que es intencional, pero es discutible.
   *Propuesta v2:* conservar las oraciones válidas, marcar `ids_descartados` en el registro y descartar solo si no queda ninguna.
3. **Trazabilidad en el registro.** La entrada de un par descartado por la validación guarda el veredicto original del LLM1, sin un campo que diga «no pasó a clasificación». Por eso `evaluar()` la cuenta como verificada Incumple y, si es una trampa, la manda a «otra causa» ([evaluar.py:269](../evaluar.py#L269)) en lugar de a una pérdida propia.
   *Propuesta v2 (evaluación, no pipeline):* una subcausa «descartada por validación de citas» en `subcausa_otra_causa`.

**Cómo estimar el efecto**, con la salida del script:

- Pares afectados por (1): la fila `ids_inexistentes_malformados` de «Por causa».
- Pares afectados por (2): los de `ids_inexistentes_fuera_de_rango` que tienen «válidas:» en `detalle` del CSV.
- Trampas: la columna «Trampas no encontradas (estado final)» de esas filas. Es una **cota superior** de lo que se recuperaría: el par pasaría al LLM2, y el LLM2 todavía podría descartarlo.

Si aparece algún par **inconsistente**, es un error que el código leído no explica. En ese caso hay que abrir esas entradas del JSON (sección y artículo en el CSV) antes de sacar conclusiones.

La corrida de prueba P6–P12 no se repite. Lo de arriba queda como limitación declarada y como trabajo futuro.

## 5. Cómo correrlo

```
venv\Scripts\python.exe -m evaluacion.diagnostico_sin_clasificacion --config evaluacion/config_p6p12.json
```

Salidas en `evaluacion/diagnosticos/p6p12/`:

- `pares_sin_clasificacion.csv`: un par por fila, con causa, detalle, trampas y su estado final.
- `pares_sin_clasificacion_resumen.md`: totales, causas, pares sin clasificación por oferta, trampas afectadas y la comparación de claves con `tmp_desacuerdos.py`.

La lógica está probada con datos sintéticos en `tests/test_externas.py::test_diagnostico_sin_clasificacion_por_causa_y_claves`.
