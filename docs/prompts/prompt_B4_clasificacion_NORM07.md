# B4: clasificación de riesgos según los lineamientos de la empresa, dashboard nuevo y evaluador

Rama: `kb-ferroviaria`. Leé CLAUDE.md antes de empezar. Trabajá por etapas en el orden indicado, corré los tests al cerrar cada etapa y anotá el avance en `.claude/progreso_b4.md`. Mostrame el diff antes de cada commit. Commits sin líneas Co-Authored-By ni Claude-Session.

**Prohibido:**
- ejecutar el pipeline sobre ofertas;
- llamar a APIs pagas;
- leer `datos/BaseConocimiento/**`, `datos/ProyectoAnalizar/**`, `datos/Resultados/**`, `ChromaDB*`, `modelos_locales/**` o `.cache/**`.

Los tests usan textos y LLM falsos.

No cambies la etapa de verificación (`_verificar_seccion` hasta la lista `pendientes`), la segmentación ni la recuperación: están congeladas y medidas.

## Contexto

Hoy cada "Incumple" de la verificación pasa a una llamada de redacción que inventa probabilidad, impacto y responsable. Esa llamada se reemplaza por una **clasificación según los lineamientos de la empresa**: NORM_07 (criterios de riesgo) y NORM_06 (responsables). El principio es: **el LLM juzga, el código calcula.**
- El modelo decide el veredicto, extrae datos y redacta.
- La clase, la probabilidad, el nivel, la estrategia, el responsable, la categoría RBS, el umbral, el tipo de solicitud y el plazo los calcula `scripts/motor_riesgos.py`, a partir de los parámetros que la empresa define en su carpeta de lineamientos.

**Objetivo de diseño:** cambiar de empresa es cambiar la carpeta `Lineamientos`, sin tocar código. En el código no puede quedar ningún nombre de norma, gerencia, umbral ni matriz escrito a mano: todo sale de esa carpeta.

## Salvaguardas contra forzar el resultado (obligatorias, revisalas en cada etapa)

1. **No mezclar Normativa con Lineamientos:**
   - `Normativa` (NORM_01 a 05) se indexa y se recupera por similitud; es contra lo que se verifica la oferta.
   - `Lineamientos` (NORM_06, NORM_07 y `criterios_empresa.json`) nunca se indexa; es el método.
2. **Lo único que el modelo recibe de los lineamientos** son los capítulos y artículos que declara `criterios_empresa.json` (`texto_para_el_modelo`), leídos del documento de la empresa. Nunca NORM_06 completa, nunca todo NORM_07.
3. **Los textos de los prompts no pueden contener ejemplos, valores ni frases de las ofertas ni del ground truth:** ni IP54, ni H-25, ni Icc, ni escaleras. Tampoco se repiten en el prompt los ejemplos que ya están en NORM_07; se los cita por artículo.
4. **`evaluacion/`** (ground truth, espejos) solo la leen `evaluar.py` y los tests. Nunca un prompt, el índice ni el pipeline.
5. **Si un test contra el ground truth falla, no modifiques reglas, parámetros ni prompts para que pase.** Reportá la diferencia y esperá mi decisión.

## Etapa 1. Carpetas y configuración

1. La base de conocimiento quedó así (ya lo hizo Adriel, no muevas archivos):
   - `datos/BaseConocimiento/Normativa/` → NORM_01 a NORM_05. Se indexan.
   - `datos/BaseConocimiento/Lineamientos/` → NORM_06, NORM_07 y `criterios_empresa.json` (te lo paso aparte; Adriel lo copia). **No se indexan.**
2. En `config.py`:
   - `DIRECTORIO_NORMATIVA` y `DIRECTORIO_LINEAMIENTOS`.
   - El indexado y `imprimir_resumen` leen todos los documentos de `DIRECTORIO_NORMATIVA`, sin nombres fijos. Los loaders usan `os.listdir` sin recursión: verificá que nadie siga leyendo `DIRECTORIO_BASE_CONOCIMIENTO` directamente.
   - Revisá el manifest del índice: el contenido es el mismo (NORM_01 a 05), solo cambió la ruta. Si el manifest fuerza un reindexado, que lo haga una sola vez y lo informe en el log.
3. Retirá el mecanismo `NORMA_COMPLETA` (NORM_06 completa en el prompt).
4. `THINKING_VERIFICACION = False`.
5. Comentá `MAX_CHARS_PROYECTO` como *legacy*: solo lo usa el modo evaluación, porque el pipeline por secciones no trunca.
6. Nuevo módulo `scripts/lineamientos.py` con `cargar_lineamientos(directorio)`:
   - **Lee** todos los documentos de la carpeta. Si existen `.docx` y `.pdf` con el mismo nombre, usa el `.docx` (las tablas salen limpias). Reutiliza la limpieza de encabezados y pies.
   - **Lee y valida** `criterios_empresa.json`. Si falta una clave, o el documento de criterios que declara no está en la carpeta, lanza un error claro.
   - **Devuelve:**
     - `criterios`: el JSON;
     - `texto_para_el_modelo`: los capítulos y artículos que declara el JSON, extraídos del documento de criterios con `extraer_capitulo(texto, n)` y `extraer_articulo(texto, "X.Y")`;
     - `huella`: el sha256 del texto entregado y del JSON, para auditar qué versión se usó.
   - Guardá en el log la cantidad de caracteres de `texto_para_el_modelo`.

**Tests:**
- con una carpeta temporal y textos inventados (no el archivo real):
  - se extraen el capítulo y el artículo pedidos;
  - se prefiere `.docx` sobre `.pdf`;
  - un JSON incompleto da error;
- el indexado ignora la carpeta `Lineamientos`.

## Etapa 2. `scripts/motor_riesgos.py` (solo código, sin LLM)

"Motor de evaluación de riesgos": aplica los criterios de la empresa. Toma todos los parámetros de `criterios` (el JSON); cada función cita en su docstring el artículo que implementa.

**`brecha_relativa(ofertado, exigido, tipo_limite)` (NORM_07 Art. 3.5):**
- MINIMO y CANTIDAD: cuenta solo si ofertado < exigido; da (exigido − ofertado)/exigido.
- MAXIMO y FRECUENCIA: cuenta solo si ofertado > exigido; da (ofertado − exigido)/exigido.
- TOLERANCIA: compara amplitudes, (ofertado − exigido)/exigido.
- Parseá coma decimal y punto de miles ("1.676", "0,05"). Si no se puede parsear, devolvé None.

**`clase(fuente, condicion_critico, objeto_requisito, brecha, riesgo_personas, criterios)` → (clase, regla).** Es el procedimiento del Art. 3.6.1: se evalúa en orden y se adopta la primera regla que se cumple. El umbral sale de `criterios["umbral_brecha_relativa"]`.
- **Información faltante:** Mayor si `condicion_critico == "a"`; Menor en otro caso (Art. 3.6.4). No sigue a la tabla.
- **Excepción no acreditada:** usa las mismas reglas que el desvío (Art. 3.6.5).

| # | Condición | Resultado |
|---|---|---|
| 1 | `condicion_critico` en {a, b, c, d} | Crítico, "3.2.x" |
| 2 | DOCUMENTAL_PROCEDIMIENTO | Menor, "3.4.c" |
| 3 | RESERVA_ERGONOMIA_EFICIENCIA | Menor, "3.4.d" |
| 4 | VERIFICACION_RUTINA | Menor, "3.4.b" |
| 5 | ENSAYO_ACEPTACION | Mayor, "3.3.b" |
| 6 | ORDINAL | Mayor, "3.3.d" |
| 7 | CUANTITATIVO_TECNICO con brecha ≥ umbral | Mayor, "3.3.a" |
|   | CUANTITATIVO_TECNICO con brecha < umbral y `riesgo_personas` | Mayor, "3.3.e" |
|   | CUANTITATIVO_TECNICO con brecha < umbral sin riesgo para personas | Menor, "3.4.a" |
|   | CUANTITATIVO_TECNICO sin brecha calculable | Mayor, "3.3.c" (Art. 3.5: no cuantificable) |
| 8 | OTRO_TECNICO | Mayor, "3.3.c" |

`riesgo_personas` es `dimension_impacto == "Seguridad de personas"`.

**Funciones que leen del JSON:**
- `probabilidad(fuente)`;
- `acotar_impacto(clase, impacto)`, que devuelve el valor acotado y un flag si hubo ajuste;
- `nivel(prob, impacto)` con la matriz;
- `aplicar_consistencia(clase, nivel)`;
- `estrategia(nivel)`;
- `responsable(norma, articulo)`:
  - la primera regla que coincide por norma y, si la regla tiene `capitulos`, por el capítulo (el primer número del artículo);
  - un riesgo agrupado toma el responsable de la brecha de mayor clase (Art. 7.4);
- `rbs(norma, articulo)`: mismo mecanismo;
- `solicitud(fuente, clase)` → (tipo, plazo);
- `umbral(pares)`: "NORM_0X, Art. X.Y", separados por "; " (Art. 7.5).

**Agrupamiento, decisión y top 5:**
- `agrupar(brechas)` (Art. 6.1): las brechas de la misma sección que citan las mismas oraciones de la oferta forman un solo riesgo, que cita todos los artículos y toma la clase y el nivel más altos.
- Art. 6.2: los Menores y las consultas técnicas de una misma categoría RBS que no quedaron agrupados en otro riesgo se juntan en un ítem por categoría, con título "Aclaraciones menores: <categoría>".
- **Importante:** el registro de brechas sin agrupar se conserva completo; la evaluación se hace sobre él.
- `decision_aceptabilidad(riesgos)` (Art. 5.4).
- `top5(riesgos)` (Art. 8.3: por nivel, después impacto, después clase).

**Tests (`tests/test_motor_riesgos.py`):**
- Con el JSON real copiado a un fixture de tests (es un archivo de parámetros, no un resultado):
  - las 25 celdas de la matriz, la consistencia y el acotado;
  - brecha: 1 de 2 (CANTIDAD) = 0,5; ±3 vs ±1,5 (TOLERANCIA) = 1,0; 2700 vs máx. 2274 = 0,187; 0,52 vs máx. 0,48 = 0,083; "1.676" se parsea como 1676;
  - `clase`: un caso por regla, incluidas 3.3.e y la información faltante;
  - con un JSON alternativo de umbral 0,10, una brecha de 0,187 sin riesgo para personas pasa de Menor a Mayor. Demuestra que el criterio sale de la empresa y no del código.
- **Consistencia con el ground truth:** para las 60 filas de `evaluacion/ground_truth_v3.csv`, `clase()` con `fuente`, `condicion_critico`, `objeto_requisito`, `brecha_relativa` y `dimension_impacto == "Seguridad"` devuelve la columna `clase`, y `responsable(norma, articulo)` devuelve la columna `responsable`.
  - Este test verifica que el código implementa la norma igual que el ground truth. No mide al modelo.
  - Si alguna fila no coincide, aplicá la salvaguarda 5.

## Etapa 3. Llamada de clasificación (reemplaza la de redacción)

1. En `schemas.py`, el esquema `ClasificacionRiesgo`. **El orden de los campos importa: el motivo va antes del veredicto.**
   - `motivo`: str, hasta 30 palabras.
   - `veredicto`: Literal["DESVIO", "EXCEPCION_NO_ACREDITADA", "INFORMACION_FALTANTE", "NO_APLICA", "CUMPLE", "ALERTA"]
   - `condicion_critico`: Optional[Literal["a", "b", "c", "d"]]
   - `objeto_requisito`: Optional[Literal[...los 7 valores...]]
   - `valor_ofertado`, `valor_exigido`: Optional[str], copiados tal cual figuran.
   - `unidad`: Optional[str]
   - `tipo_limite`: Optional[Literal["MINIMO", "MAXIMO", "TOLERANCIA", "CANTIDAD", "FRECUENCIA"]]
   - `dimension_impacto`: Optional[Literal] con las 6 dimensiones del Art. 4.3 tal como se escriben ahí.
   - `impacto`: Optional[int] entre 1 y 5.
   - `titulo`, `enunciado`, `accion`, `solicitud_oferente`: Optional[str]
2. En `rag_components.py`, `PROMPT_CLASIFICACION_STR` con el texto de abajo, sin reescribirlo ni agregarle ejemplos. Las variables son:
   - `{criterios}` = `texto_para_el_modelo`, cargado una vez por análisis;
   - `{articulo}`, `{seccion_numerada}` y `{verificacion}`: lo mismo que recibía la redacción.
   
   Guardá en el JSON del resultado la `huella` y la cantidad de caracteres de `{criterios}`.
3. En `main.py`, el bucle de `pendientes` usa la clasificación en lugar de la redacción. Validación en código, en este orden. Si un paso falla, se descarta y se anota en el registro técnico con su motivo.
   1. JSON válido; si no lo es, un reintento con el error.
   2. Si el veredicto es CUMPLE o NO_APLICA: no es riesgo. Queda en el registro técnico con su motivo.
   3. Si es ALERTA: va a la lista de alertas, con su motivo.
   4. Si el veredicto genera riesgo y falta `objeto_requisito`, `dimension_impacto`, `impacto` o `titulo`: se descarta como "clasificación incompleta".
   5. Si es CUANTITATIVO_TECNICO, `valor_ofertado` tiene que aparecer en las oraciones citadas y `valor_exigido` en el artículo (normalizados). Si alguno no aparece, se marca "valor no verificado" y se calcula sin brecha (Art. 3.5).
   6. Validá las longitudes (título ≤ 12 palabras, enunciado ≤ 40, acción ≤ 30, solicitud ≤ 40); si no se cumplen, solo se agrega una marca, no se descarta.
   7. Llamá a `motor_riesgos` para calcular todo lo demás.
4. **Resumen general:** se elimina la llamada al LLM (`_generar_resumen_general`). El resumen ejecutivo lo arma el código según el Art. 8.3:
   - la decisión de aceptabilidad;
   - el conteo por nivel y por clase;
   - el top 5.
5. **Salida:** el JSON del resultado tiene:
   - `registro_brechas`: sin agrupar; cada brecha con sus citas, las oraciones, la clasificación del LLM, todo lo calculado y la regla aplicada;
   - `riesgos`: agrupados;
   - `solicitudes`;
   - `alertas`;
   - `resumen_ejecutivo`;
   - `registro_tecnico`: como hoy.
   
   Adaptá `RiskReport`. Los campos viejos del modo lista pueden quedar opcionales.

**Tests con LLM falso:**
- un desvío cuantitativo de 1 vs 2 da Mayor, nivel Alto si el impacto es 4 y Medio si es 3;
- un "la oferta no menciona" clasificado NO_APLICA no genera riesgo;
- un valor ofertado que no está en la cita se marca y cae a 3.3.c;
- un ALERTA va a alertas;
- dos artículos sobre las mismas oraciones se agrupan en un riesgo con clase máxima;
- un test que falla si `PROMPT_CLASIFICACION_STR` contiene alguna de estas cadenas: "IP5", "H-2", "H-3", "kA", "escalera", "mm/m", "N·m".

### Texto del prompt (copiar tal cual)

```
Sos evaluador técnico de ofertas de la empresa. Aplicás los criterios de riesgo de la empresa a UN par: una declaración de la oferta y un artículo de la normativa técnica. Todo lo que escribas tiene que surgir de la sección o del artículo. No inventes datos.

=== CRITERIOS DE LA EMPRESA ===
{criterios}

=== ARTÍCULO DE LA NORMATIVA ===
{articulo}

=== SECCIÓN DE LA OFERTA (oraciones numeradas) ===
{seccion_numerada}

=== VERIFICACIÓN PREVIA ===
{verificacion}
Un verificador automático marcó este par como Incumple o Revisar. Puede estar equivocado: decidí vos aplicando los criterios.

=== TAREA ===
1. Aplicá el orden de decisión del Art. 2.2 y elegí UN veredicto: NO_APLICA, DESVIO, EXCEPCION_NO_ACREDITADA, INFORMACION_FALTANTE, CUMPLE o ALERTA.
   - Que la oferta no mencione algo no es un desvío: aplicá los Art. 2.5, 2.6 y 2.7.
   - Superar el requisito es CUMPLE (Art. 2.8).
   - Distinguí desvío de excepción no acreditada con los Art. 2.3 y 2.4.
   - Usá ALERTA solo en el caso del Art. 2.9.
2. Si el veredicto es DESVIO, EXCEPCION_NO_ACREDITADA o INFORMACION_FALTANTE, completá:
   a) condicion_critico: la letra del inciso del Art. 3.2 que se cumple (a, b, c o d), o null si no se cumple ninguno. Si la protección existe aunque sea insuficiente, no es "a". Para INFORMACION_FALTANTE, "a" indica que el dato faltante corresponde a una materia del Art. 3.2.a. Tené en cuenta el Art. 3.6.2.
   b) objeto_requisito, uno de:
      DOCUMENTAL_PROCEDIMIENTO: requisito del tipo descrito en el Art. 3.4.c.
      RESERVA_ERGONOMIA_EFICIENCIA: requisito del tipo descrito en el Art. 3.4.d.
      VERIFICACION_RUTINA: requisito del tipo descrito en el Art. 3.4.b.
      ENSAYO_ACEPTACION: ensayo o verificación de aceptación omitido o sustituido, como en el Art. 3.3.b.
      ORDINAL: requisito en una escala por escalones, como en el Art. 3.3.d.
      CUANTITATIVO_TECNICO: requisito técnico expresado con un valor numérico.
      OTRO_TECNICO: cualquier otro requisito técnico.
   c) Si es CUANTITATIVO_TECNICO: valor_ofertado y valor_exigido copiados tal cual de la oferta y del artículo, la unidad y tipo_limite (MINIMO, MAXIMO, TOLERANCIA, CANTIDAD o FRECUENCIA). No conviertas unidades ni calcules diferencias.
   d) dimension_impacto: la dimensión del Art. 4.3 más afectada, e impacto de 1 a 5 según sus anclas.
   e) titulo, enunciado, accion y solicitud_oferente, según los Art. 4.1, 7.4 y 8.2:
      titulo: hasta 12 palabras.
      enunciado: hasta 40 palabras, con la fórmula del Art. 4.1.
      accion: hasta 30 palabras.
      solicitud_oferente: hasta 40 palabras; el pedido formal al oferente, con el valor o el documento exigido por el artículo.
   No decidas la clase, la probabilidad, el nivel, la estrategia, el responsable ni el plazo: los calcula el sistema.
3. Con CUMPLE, NO_APLICA o ALERTA completá solo motivo y veredicto; el resto va en null.

Respondé SOLO con este JSON, en este orden:
{"motivo": "...", "veredicto": "...", "condicion_critico": null, "objeto_requisito": null, "valor_ofertado": null, "valor_exigido": null, "unidad": null, "tipo_limite": null, "dimension_impacto": null, "impacto": null, "titulo": null, "enunciado": null, "accion": null, "solicitud_oferente": null}
```

## Etapa 4. Dashboard

Reemplazá el contenido del dashboard, manteniendo el estilo actual, por cuatro secciones en este orden:

1. **Resumen ejecutivo:**
   - decisión de aceptabilidad (No aceptable, Aceptable con condiciones o Aceptable) con un color;
   - cantidad de riesgos por nivel y por clase;
   - el top 5 como lista de títulos con enlace a su detalle.
2. **Registro de riesgos:**
   - tarjetas ordenadas por categoría RBS, que muestran SOLO el título, la clase (con color: Crítico rojo, Mayor naranja, Menor gris) y el área responsable;
   - al hacer clic en una tarjeta se abre su detalle (desplegable o ancla), con:
     - la cita de la oferta y el requisito del artículo, lado a lado, con norma y artículo;
     - el enunciado;
     - la fuente (desvío, excepción no acreditada o información faltante), la clase y la regla aplicada;
     - probabilidad × impacto = nivel, con la dimensión del impacto;
     - la estrategia, la acción de mitigación, el umbral y el responsable.
3. **Solicitudes al oferente:** tabla con número, tipo de solicitud, norma y artículo, cita de la oferta, pedido redactado, clase, responsable y plazo. Ordenada por clase y después por RBS.
4. **Alertas a revisar:** con su motivo. Va con la leyenda "Dudas internas del evaluador; no se envían al oferente".

Al pie va una línea con el modelo, la fecha, la huella de los lineamientos y la cantidad de verificaciones y clasificaciones. El registro técnico no se muestra.

Sin dependencias externas nuevas: HTML, CSS y JS en un solo archivo.

## Etapa 5. `evaluacion/evaluar.py`

**Uso:** `python -m evaluacion.evaluar --resultado <json> --oferta P1 [--revision extras_revision.csv]`

**Entradas:**
- el JSON del resultado (usa `registro_brechas`, sin agrupar);
- `evaluacion/ground_truth_v3.csv`;
- `evaluacion/espejos_conformes.csv` (separador ";"; filtrá la columna `proyecto` == "Proyecto N"; la columna `articulo` puede traer varios, separados por ";").

Normalizá el texto en minúsculas, sin acentos y con espacios simples.

**Métricas por oferta:**
1. **Trampas encontradas (x/15):** una trampa cuenta si alguna brecha que genera riesgo tiene una cita que contiene `fragmento_trampa` y cita (norma, artículo) igual al de la trampa o a uno de `articulos_equivalentes`.
   - Si la frase coincide pero el artículo es otro, contala aparte como "encontrada con otro artículo". No suma al recall estricto.
2. **Clase correcta:** de las encontradas, cuántas tienen la misma clase que el ground truth. Agregá la matriz de confusión 3×3.
3. **Responsable correcto** y **nivel correcto:** de las encontradas.
4. **Falsas alarmas:** espejos cuya `cita_conforme` (primeros 60 caracteres normalizados) aparece en la cita de una brecha que genera riesgo con la misma norma y uno de sus artículos. Se reporta x/32 para P1.
5. **Extras:** brechas que generan riesgo y no son ni trampa ni espejo. Se exportan a `extras_revision.csv` con oferta, sección, norma, artículo, cita, título, clase y una columna vacía `valido` (sí/no) para Adriel.
   - Si se pasa `--revision` con la columna completa, se calcula la **precisión** = (trampas encontradas + extras válidos) / total de brechas que generan riesgo.
   - Si no se pasa, se informa "precisión pendiente de revisión".
6. **Volumen:**
   - brechas;
   - riesgos agrupados;
   - solicitudes;
   - alertas.

**Salidas** en la carpeta del resultado:
- `evaluacion_<oferta>_<timestamp>.md`, con la tabla resumen y el detalle trampa por trampa (encontrada sí/no, clase esperada y obtenida, responsable, nivel);
- `evaluacion_<oferta>_<timestamp>.csv`, con el detalle;
- `extras_revision.csv`.

**Tests con un JSON falso:**
- una trampa encontrada con el artículo correcto;
- una con un artículo equivalente;
- una con otro artículo;
- un espejo marcado;
- un extra.

## Cierre

- Corré todos los tests. Tienen que pasar los de antes y los nuevos.
- Actualizá CLAUDE.md:
  - arquitectura de dos capas: verificación congelada y clasificación con los lineamientos;
  - las carpetas Normativa y Lineamientos, y el rol de `criterios_empresa.json`;
  - el principio "el LLM juzga, el código calcula";
  - las salvaguardas;
  - cómo correr `evaluar.py`.
- Indicame el comando para correr P1 y el de evaluarlo. No los ejecutes.

## Prompt del comentario general

Una llamada al LLM al final del análisis (temperatura 0 y seed fija). Recibe solo la decisión, los conteos y el registro de riesgos agrupados.
El código valida la respuesta (cada NORM_0X y Art. X.Y tiene que estar en el registro; entre 2 y 5 oraciones). Si falla, o si el registro está vacío, usa una plantilla armada por código.

```
Redactá el comentario general de un informe de evaluación técnica de una oferta. Usá SOLO la información de abajo. No agregues riesgos, valores, normas ni recomendaciones que no figuren en ella.

Decisión de aceptabilidad: {decision}
Riesgos por nivel: {conteo_nivel}
Riesgos por clase: {conteo_clase}
Registro de riesgos (título | clase | nivel | responsable | normas y artículos):
{registro}

Escribí entre 3 y 4 oraciones, en tono formal e impersonal:
1. La decisión de aceptabilidad y el motivo principal.
2. En qué áreas responsables se concentran los riesgos de clase Crítico y Mayor.
3. Qué debe resolver el oferente antes de la adjudicación.
Respondé solo con el texto, sin títulos ni viñetas.
```
