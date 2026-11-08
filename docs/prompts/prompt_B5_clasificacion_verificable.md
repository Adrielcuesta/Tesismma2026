# B5: condiciones de clase verificables por código y filtro de información faltante

Rama `kb-ferroviaria`. Rigen las mismas salvaguardas y prohibiciones de B4 (ver `docs/prompts/prompt_B4_clasificacion_NORM07.md`):
- no ejecutar el pipeline;
- no leer `datos/BaseConocimiento/**` ni `datos/Resultados/**`;
- si un test contra el ground truth falla, no ajustar reglas ni prompts para que pase.

Mostrame el diff antes de commitear. Commits sin líneas de co-autor.

## Diagnóstico de la primera corrida de P1 (por qué se hace este cambio)

La clasificación del modelo sobre P1 dio:
- 67 brechas, de las cuales 44 son INFORMACION_FALTANTE;
- `condicion_critico` completado en las 67 (a: 46, d: 16, b: 3, c: 2);
- `dimension_impacto` = "Seguridad de personas" en 63 de las 67.

Resultado: todos los desvíos salen Crítico y la clase coincide con el ground truth en solo 2 de 8 trampas. El modelo de 8B no deja nada en null cuando se le ofrece una letra, y no aplica la lista cerrada del Art. 2.6 ni el Art. 2.7.c.

**Solución:** el modelo deja de elegir la letra. Extrae hechos verificables y el código decide la condición, como ya hace con la brecha.

## 1. `criterios_empresa.json`: bloque nuevo

Adriel actualiza el archivo en `Lineamientos/` y en `tests/fixtures/`. Trae `contenido_minimo_oferta.items`, una lista de {`disciplina`, `item`, `materia_critica`} copiada del Art. 2.6.
- `materia_critica` indica si el dato corresponde a una materia del Art. 3.2.a.
- Agregalo a las claves requeridas de `lineamientos.py`, con su test.

## 2. Esquema `ClasificacionRiesgo`

**Sacar:** `condicion_critico`.

**Agregar**, en este orden, entre `veredicto` y `objeto_requisito`:
- `item_contenido_minimo`: str | null, copiado de la lista de ítems, o "NINGUNO".
- `etapa_requisito`: Literal["OFERTA", "POSTERIOR"] | null.
- `materia_3_2_a`: bool | null.
- `medida_ofrecida`: str | null.
- `practica_peligrosa`: bool | null.
- `valor_limite_excepcion`: str | null.
- `valor_demanda_oferta`: str | null.

## 3. Reglas en código (`clasificacion.py` y `motor_riesgos.py`)

Cada regla queda registrada en `regla` y en `marcas`, para que el dashboard muestre por qué.

1. **INFORMACION_FALTANTE:**
   - pasa a NO_APLICA si `item_contenido_minimo` es "NINGUNO" o no coincide (normalizado) con un ítem de la lista. Regla "2.5";
   - también pasa a NO_APLICA si `etapa_requisito` == "POSTERIOR". Regla "2.7.c";
   - si sigue en pie, la clase es Mayor si el ítem tiene `materia_critica` == true y Menor si no (Art. 3.6.4). Ya no depende del modelo.
2. **DESVIO o EXCEPCION_NO_ACREDITADA:** la condición del Art. 3.2 la calcula el código, en este orden:
   - **c:** `valor_limite_excepcion` parseable, presente en el texto del artículo (normalizado), y el valor ofertado queda fuera de ese límite según `tipo_limite`.
   - **d:** `valor_demanda_oferta` parseable, presente en las oraciones citadas de la oferta, y el valor ofertado no la cubre: para MINIMO, CANTIDAD o TOLERANCIA, ofertado < demanda; para MAXIMO, ofertado > demanda.
   - **b:** `practica_peligrosa` == true y `medida_ofrecida` presente en las oraciones citadas.
   - **a:** `materia_3_2_a` == true y `medida_ofrecida` es null.
   - Si no se cumple ninguna, sin condición, y siguen las reglas de clase actuales.
3. **Valores declarados que no se encuentran** en el texto correspondiente: el campo se ignora, con la marca "valor no verificado: <campo>".

**Tests:**
- un caso por regla;
- casos negativos: `practica_peligrosa` true sin cita, c con un límite que no está en el artículo, d con una demanda que no está en la oferta;
- el test contra el ground truth sigue pasando sin cambios: `clase()` recibe la condición ya calculada.

## 4. Prompt de clasificación

En `PROMPT_CLASIFICACION_STR` y en `docs/prompts/prompt_B4_clasificacion_NORM07.md`, reemplazá el punto 2 a) de la TAREA y el JSON final por lo de abajo. El resto del texto no cambia.

La variable nueva `{items_contenido_minimo}` es la lista de ítems del JSON, uno por línea, con el formato "- <disciplina>: <item>". Va inmediatamente después de la línea "=== CRITERIOS DE LA EMPRESA ===" + `{criterios}`, con el encabezado "=== ÍTEMS DEL ART. 2.6 ===".

Actualizá el test de igualdad del prompt y el de cadenas prohibidas.

Texto del nuevo punto 2 a) (copiar tal cual):

```
   a) Para INFORMACION_FALTANTE:
      item_contenido_minimo: el ítem de la lista del Art. 2.6 al que corresponde el dato que falta, copiado tal cual de la lista; si no corresponde a ninguno, "NINGUNO".
      etapa_requisito: "OFERTA" si el dato debe presentarse con la oferta; "POSTERIOR" si corresponde a ejecución, registros de obra, dossier, conforme a obra, actas o recepción.
      Para DESVIO o EXCEPCION_NO_ACREDITADA:
      materia_3_2_a: true si el requisito trata de alguna de las materias enumeradas en el Art. 3.2.a; si no, false.
      medida_ofrecida: la frase de la oferta que propone algo para cumplir el requisito, copiada tal cual, aunque sea insuficiente. null solo si la oferta no propone nada.
      practica_peligrosa: true solo si lo que propone la oferta crea por sí mismo el peligro que el requisito previene (Art. 3.2.b). false si solo es insuficiente o distinto de lo exigido.
      valor_limite_excepcion: si el artículo admite apartarse del valor general hasta un límite, ese límite copiado del artículo; si no, null.
      valor_demanda_oferta: si la propia oferta declara la carga o el uso que el valor ofertado debe cubrir, ese valor copiado de la oferta; si no, null.
      No decidas si el desvío es Crítico: lo calcula el sistema con estos datos.
```

JSON final (copiar tal cual):

```
{"motivo": "...", "veredicto": "...", "item_contenido_minimo": null, "etapa_requisito": null, "materia_3_2_a": null, "medida_ofrecida": null, "practica_peligrosa": null, "valor_limite_excepcion": null, "valor_demanda_oferta": null, "objeto_requisito": null, "valor_ofertado": null, "valor_exigido": null, "unidad": null, "tipo_limite": null, "dimension_impacto": null, "impacto": null, "titulo": null, "enunciado": null, "accion": null, "solicitud_oferente": null}
```

## 5. `evaluar.py`: la comparación con la línea de base

En la corrida con RAG, la cita de una brecha tiene en promedio 4 oraciones (unos 600 caracteres). Por eso "encontrada por frase" acredita trampas que el riesgo no trata: por ejemplo, "plan bienal de calibraciones" aparece citada en un riesgo sobre cables de potencia. En la corrida sin RAG, la cita tiene una frase (unos 100 caracteres).

1. En la tabla `--comparar`:
   - la columna con RAG usa solo el recall estricto (frase y artículo, más equivalentes);
   - la columna sin RAG usa "por frase", con la nota: "criterio más laxo que el de la columna con RAG: la diferencia es una cota inferior del aporte del RAG";
   - sacá la fila "por frase" de la columna con RAG.
2. Para la línea de base, exportá `sinrag_coincidencias.csv` con trampa, frase, descripción del riesgo, cita y una columna vacía `valido` (sí/no). Con `--revision-sinrag <csv>`, la fila sin RAG cuenta solo las marcadas como válidas.
3. En el modo brechas, sacá la métrica "encontradas con otro artículo" del resumen y dejala solo en el detalle por trampa, con el artículo citado.

**Tests** para los tres puntos. Corré todos los tests, mostrame el diff y commiteá: "B5: condición Crítico y filtro de información faltante verificables por código; comparación con la línea de base corregida". No ejecutes el pipeline.

## 6. Dashboard: menos información, solo la que sirve para decidir

En la corrida de P1, el detalle de cada tarjeta mostraba el texto completo de uno o dos artículos, líneas genéricas como "Corregir la declaración para cumplir con la norma", y riesgos duplicados: la misma trocha de ±3 mm aparecía dos veces, una por el Art. 2.3 y otra por el 2.16.

1. **Agrupamiento (Art. 6.1):** dos brechas de la misma sección que comparten al menos una oración citada, o el mismo `valor_ofertado` normalizado, forman un solo riesgo. El riesgo toma la clase y el nivel más altos y lista todos los artículos. Agregá un test con el caso de la trocha.
2. **Tarjetas:** solo para riesgos de nivel Alto y Medio. Los de nivel Bajo van como una lista compacta, una línea por riesgo: título · clase · responsable · norma y artículo. Al hacer clic, se abre el mismo detalle.
3. **Detalle del riesgo**, en este orden y nada más:
   - "La oferta dice": solo las oraciones citadas que contienen `medida_ofrecida` o `valor_ofertado`, como máximo 2. Si no hay ninguna, la primera oración citada.
   - "La norma exige": `valor_exigido` con su unidad y la explicación breve de la verificación (los requisitos). El texto completo del artículo va plegado, en "Ver artículo".
   - "Qué se pide al oferente": `solicitud_oferente`.
   - Una línea de datos: Fuente · Clase (regla) · P×I = Nivel · Estrategia · Norma y artículo.
   - Las marcas del sistema, solo si existen.
   - Se eliminan del detalle las líneas de categoría RBS, umbral y responsable (el responsable ya figura en la tarjeta) y la acción de mitigación (`solicitud_oferente` la reemplaza).
4. **"Acciones antes de la adjudicación":** una línea por riesgo agrupado, no por brecha.

Regenerá `tests/salida/dashboard_ejemplo.html` e incluí en el fixture el caso de la trocha duplicada.

## 7. Métricas estándar en `evaluar.py` (todas deterministas, sin LLM)

Se alinea el reporte con cómo se evalúan los sistemas comparables: ContractNLI, CUAD y ContractEval para la revisión de documentos, RAGChecker para RAG y RegNLP para la recuperación regulatoria. No agrega corridas.

1. **Recuperación: Recall@artículo.** Proporción de trampas cuyo artículo (o un equivalente) fue verificado en la sección de la trampa, según `registro_tecnico`, cualquiera sea el veredicto. Es el "context recall" de RAGAS y RAGChecker, calculado sin juez.
2. **Detección: precisión, recall, F1 y F2.** La precisión es la que ya existe con `--revision`. F2 pondera más el recall, como en ContractEval, porque en revisión de cumplimiento un desvío no detectado cuesta más que una falsa alarma.
   - Agregá el intervalo de confianza del 95 % de Wilson para recall y precisión.
   - Agregá la "tasa de pereza" (Laziness Rate de ContractEval): trampas cuyo artículo llegó a la sección pero el veredicto fue Cumple o No aplica.
3. **Clasificación:** exactitud de clase, matriz de confusión y **kappa ponderado cuadrático** (Crítico > Mayor > Menor) contra el ground truth. Responsable correcto.
4. **Fidelidad:** proporción de brechas con alguna marca "valor no verificado". Indicá en el `.md` que la fidelidad de la cita es del 100 % por diseño, porque la cita la arma el código a partir de las oraciones numeradas.
5. **Informe agregado:** `--agregado <json_P1> <json_P2> ...` suma las ofertas y calcula todo lo anterior sobre el total de trampas.
   - Con `--comparar` sobre varias ofertas, agregá la prueba exacta de McNemar (pareada por trampa) entre con RAG (estricto) y sin RAG (por frase validada).
   - Implementá Wilson, kappa ponderado y McNemar exacto sin dependencias nuevas (la binomial exacta con `math.comb`), con tests contra valores conocidos.

Sacá del `.md` todo lo que no esté en esta lista o en el detalle por trampa.

## 8. Recuperación híbrida (BM25 + densa), decidida con datos antes de adoptarla

**Motivo:** en P1, 6 de las 15 trampas no se verifican porque su artículo nunca llega a la sección. La recuperación densa confunde valores y códigos exactos (IP, ISO, cifras). En recuperación regulatoria, la configuración estándar es la híbrida (RegNLP 2025: Recall@10 de 0,81 con densa y 0,83 con híbrida).

1. **Índice BM25** sobre los mismos fragmentos de la normativa (un fragmento por artículo), con `rank_bm25` (agregalo a `requirements.txt`). Tokenización en minúsculas y sin acentos, que conserve números y códigos ("ip55", "4406", "1,5"), sin stemming. Se construye en memoria al cargar la base vectorial: no requiere reindexar Chroma.
2. **Fusión por Reciprocal Rank Fusion** (RRF, k = 60, el valor estándar de la literatura; sin pesos que haya que ajustar):
   - por cada consulta de subsección se toman los K mejores de la densa y los K mejores de BM25, se fusionan con RRF y se pasa al reranker el mismo número de candidatos que hoy;
   - el reranker, `TOP_N_SUBSECCION` y `VERIFICAR_TOPE` no cambian.
   - Parámetro `RECUPERACION = "densa" | "hibrida"` en `config.py`.
3. **Diagnóstico sin LLM** (extender `scripts/diagnostico_recuperacion.py`): para cada trampa de **P1 y P2 únicamente** (`evaluacion/ground_truth_v3.csv`, filtrado por oferta), ¿el artículo de la trampa o un equivalente queda entre los artículos a verificar de su sección? Informá Recall@artículo con densa y con híbrida, trampa por trampa. No ejecutes este diagnóstico: dejame el comando.
4. **Regla de adopción, fijada de antemano:** se adopta la híbrida si mejora el Recall@artículo sumado de P1 y P2, sin perder ninguna trampa que la densa sí recuperaba. Si no mejora, queda `densa` y la híbrida se reporta como resultado negativo.

**Tests** de tokenización, de RRF con rankings conocidos y del diagnóstico con datos falsos.

## 9. Robustez de las llamadas al modelo (corrección de un error, no de un parámetro)

**Motivo:** en la corrida de P2 del 8/11, la sección S8 quedó más de una hora en una sola llamada, con la GPU al 100 % y sin salida, cuando cada sección tarda entre 1 y 3 minutos. `ChatOllama` hoy no tiene límite de tokens de salida (`num_predict`) ni timeout. Con `format` JSON, un modelo puede quedar generando espacios o repeticiones hasta llenar el contexto de 16 384 tokens.

1. **`OLLAMA_NUM_PREDICT`** en `config.py`, con el valor 1024 para verificación y clasificación, y 400 para el comentario general. Las respuestas válidas de hoy rondan los 300 a 600 tokens: revisá el largo real en los fixtures o logs que tengas y confirmá que 1024 deja margen.
2. **Timeout por llamada:** `OLLAMA_TIMEOUT_S = 240`, pasado a `ChatOllama` (parámetro `client_kwargs={"timeout": ...}` o el que corresponda a la versión de `langchain-ollama` instalada; verificalo).
3. **Si la respuesta se corta por `num_predict` o se agota el tiempo:** un reintento. Si vuelve a fallar:
   - el par se registra en `registro_tecnico` con el estado `"tiempo_agotado"` y se informa como ALERTA con el motivo "el modelo no respondió en el tiempo límite";
   - el análisis sigue con el par siguiente;
   - **nunca se cuelga ni se cae.**
4. **Log:** una línea de advertencia por cada reintento y cada par descartado, y un contador en el JSON (`configuracion_analisis.llamadas_fallidas`).

**Tests** con un LLM falso que tarda más del timeout y con otro que devuelve JSON truncado.
