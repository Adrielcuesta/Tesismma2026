# Fase 0 de la v2: análisis de las propuestas A, B y C

Solo análisis: no se cambió el pipeline ni se llamó a ningún modelo. No leí `datos/**`. Todo lo que dependía de esos datos queda como «no verificado» con el comando para que lo corra el usuario.

## 0. Punto de partida

| Conjunto | Precisión humana | Cuenta |
|---|---|---|
| P3+P4, gpt-oss-120b (perfil elegido) | 42,1 % | (23 trampas + 9 extras válidos) / 76 brechas = 32/76 (`evaluacion/resultados_reeval/tabla_comparativa.csv`: `precision_humana_k` 32, `brechas_total` 76; 50 extras etiquetados: 41 NO_VALIDA y 9 VALIDA) |
| P1+P2, preetiquetas | 38,2 % | (24 + 18) / 110 = 42/110 (dato del usuario; `brechas_total` 110 y 24 trampas coinciden con la tabla; en la tabla los extras etiquetados de P1+P2 son 0 de 80: los 18 válidos todavía no están volcados en los `_extras.csv`) |

Causas de las 41 NO_VALIDA de P3+P4 (dato del usuario): 15 dato declarado en otra sección, 11 etapa posterior, 8 artículo de alcance u objeto, 7 norma mal aplicada.

**Aviso metodológico.** Las propuestas A, B y C salen de este análisis de errores de P3+P4. Eso ya contamina P3+P4 como conjunto de prueba (que además se vio en v1). Por eso las decisiones se miden con P1+P2 y la validación limpia es P5 (ciego, una sola corrida). Lo que calculo abajo con P3+P4 es **informativo**: no se usó para elegir ningún parámetro.

## A. Excluir artículos de alcance, objeto o prevalencia (por título)

### Criterio exacto

Un artículo se excluye si su **título completo** (normalizado: sin mayúsculas, tildes ni prefijo «Art. X.Y.») es uno de: *objeto*, *alcance*, *campo de aplicación*, *ámbito de aplicación*, *orden de prevalencia*, *prevalencia* o *precedencia*; admitiendo a lo sumo «y carácter» / «y alcance» y un calificativo genérico (*funcional*, *físico*, *general*, *técnico*, *documental*). Implementado en `evaluacion/v2_listar_no_verificables.py` (`RE_EXCLUIDO`), con tests en `tests/test_v2_fase0.py`.

Por qué «título completo» y no «empieza con». Un criterio por palabra inicial captura requisitos reales. En las pendientes etiquetadas de P3+P4 hay dos casos que lo muestran:

- NORM_04 5.1, «Objeto de la tabla de control S-01…»: etiquetada **VALIDA**. Un `startswith("objeto")` la excluiría y perdería un hallazgo válido.
- NORM_04 3.1, «Objeto y alcance del SAT» (dos brechas NO_VALIDA): es un artículo con contenido específico. Con el criterio estricto **no** se excluye; si se quisiera excluir, habría que decidirlo a mano.

Tampoco depende del número: hay trampas en artículos 1.x que son requisitos (NORM_02 1.10 y 1.11, NORM_04 1.6 y 1.10, NORM_05 1.8). El script verifica expresamente esos casos y termina con código 1 si alguna trampa, o un artículo equivalente suyo, cae en un artículo excluido.

«Dudosos» (se listan, **no** se excluyen): títulos que empiezan con *referencias*, *marco*, *normas/documentos de referencia*, *generalidades*, *definiciones*, *terminología*, *vigencia*. Ejemplo visto: NORM_05 1.4, «Referencias técnicas y marco de seguridad» (NO_VALIDA).

### Lista de artículos que se excluirían y cruce con el ground truth

**No verificado:** requiere los títulos de la KB, que están en `datos/BaseConocimiento/Normativa/`. El script lee la KB con el chunker del pipeline (sin LLM ni red), lista los excluidos y los dudosos, y cruza con el ground truth de P1–P4 (y P5 cuando esté su archivo):

```
venv\Scripts\python.exe -m evaluacion.v2_listar_no_verificables --salida evaluacion\diagnosticos\v2_no_verificables.md
```

Con lo que se ve en las pendientes etiquetadas de P3+P4 (solo los artículos que dieron una brecha extra), el criterio estricto excluiría: NORM_01 1.1 («Objeto y carácter»), NORM_02 1.2 («Alcance funcional»), NORM_03 1.2 («Alcance físico y funcional»), NORM_05 1.2 («Campo de aplicación») y NORM_03 7.4 («Orden de prevalencia…», si su título es solo ese). Las cinco son NO_VALIDA. El resto de la lista, y el cruce con las 60 trampas, es lo que imprime el comando.

### ¿Se puede aplicar como postproceso?

**Sí.** Cada brecha del `registro_brechas` guarda `texto_articulo`, que empieza con «Art. X.Y. <título>»; el título sale de ahí, sin KB. El resultado del informe es el mismo que si el artículo no se hubiera verificado (los pares se verifican de forma independiente). Lo único que el postproceso no ahorra son las llamadas al LLM de esos pares; para ahorrarlas hay que filtrar después de `recuperar_seccion` (por `metadata["titulo"]`) en `scripts/main.py`, y eso toca la capa 1 («congelada y medida» según `CLAUDE.md`): se decide aparte.

## B. Filtro de etapa (NORM_07 2.6/2.7) para todos los tipos de brecha

### Dónde se aplica hoy y por qué solo a INFORMACION_FALTANTE

- Código: `scripts/clasificacion.py:96-102`. Dentro del bloque `if c.veredicto == "INFORMACION_FALTANTE"`: (1) si el dato no es un ítem de la lista de contenido mínimo, regla 2.5; (2) si `etapa_requisito == "POSTERIOR"`, regla 2.7.c. Ambos descartan la brecha al registro técnico.
- Prompt: `etapa_requisito` se le pide al modelo **solo** en el apartado «Para INFORMACION_FALTANTE» (`scripts/rag_components.py:298-302`). Para DESVIO y EXCEPCION_NO_ACREDITADA el campo queda vacío.
- Por qué solo ahí: el repo no lo explica (no hay comentario ni commit que lo justifique). Es **no verificado** si responde a lo que dice NORM_07 (no la leí).

### Qué cambiaría extenderlo

Habría que mover el chequeo de `POSTERIOR` fuera del bloque de INFORMACION_FALTANTE (aplicarlo a las tres fuentes) **y** pedir `etapa_requisito` en el prompt para DESVIO y EXCEPCION_NO_ACREDITADA. Sin lo segundo, el código solo descartaría las brechas de desvío donde el modelo informara la etapa por su cuenta.

### ¿Se puede recalcular sin LLM con `reclasificar.py`?

**No, salvo en casos marginales.** `reclasificar.py` vuelve a aplicar `procesar_clasificacion` con la clasificación que el modelo guardó en cada brecha. Si el campo `etapa_requisito` está vacío en las brechas de desvío (lo esperable por el prompt), extender el código no cambia nada. El script `evaluacion/v2_medir_ab.py` informa esa **cobertura de B** (cuántas brechas de cada fuente traen el campo) y mide B como postproceso solo donde existe. Para medir B de verdad hay que volver a llamar a LLM2 con el prompt ampliado sobre las brechas existentes. Cada llamada necesita la sección numerada completa, que el JSON no guarda (solo las oraciones citadas), así que requiere las ofertas de `datos/ProyectoAnalizar`. Costo, cota superior: la corrida completa de gpt-oss sobre P1+P2 cuesta USD 0,37 (verificación + clasificación; `tabla_comparativa.csv`); reclasificar solo las brechas costaría una fracción.

## C. Verificación cruzada del dato en toda la oferta (opcional)

### Diseño mínimo

- **Dónde se engancha:** después de `clasificacion.procesar_clasificacion`, solo cuando devuelve `tipo == "brecha"` (en `_verificar_seccion`, `scripts/main.py:355-363`). Una llamada extra por brecha. Hace falta pasar el texto numerado completo de la oferta a `_verificar_seccion` (hoy solo recibe la sección).
- **Qué ve el LLM:** la oferta completa con oraciones numeradas por sección (IDs `S3-O4`), el artículo (texto), el requisito en una frase, el valor o la medida que la brecha dice que falta o que no cumple, y la pregunta: «¿la oferta declara en otro lugar ese dato o un valor que cumple el requisito?». Sin lineamientos ni ejemplos.
- **Qué devuelve:** `{"encontrado": bool, "oraciones": ["S5-O2"], "cumple": bool, "motivo": "..."}`. El código verifica que los IDs existan y que la oración contenga el valor citado; solo entonces la brecha pasa al registro técnico (`estado = "dato_en_otra_seccion"`). Una respuesta inválida deja la brecha como está.

### Llamadas extra y costo (estimación; supuestos marcados)

| Concepto | Valor |
|---|---|
| Llamadas extra por oferta | una por brecha: 55 por oferta en P1+P2 y 38 en P3+P4 con gpt-oss (`brechas_por_oferta` de la tabla); 186 en las cuatro ofertas |
| Tokens de entrada por llamada | la oferta completa más el prompt. **No verificado:** el tamaño de las ofertas. Único dato disponible: un comentario de `scripts/config.py:63-67` cita un proyecto de 56.458 caracteres, unos 16.000 tokens a 3,5 caracteres por token (`scripts/config.py:224`) |
| Tokens de salida por llamada | ~1.900 (`NUBE_TOKENS_POR_PAR["con_razonamiento"]`, `scripts/config.py:216`: medida de Qwen3-32B con razonamiento, que el propio código usa como cota superior para gpt-oss con esfuerzo bajo) |
| Precio gpt-oss-120b, DeepInfra | entrada 0,037 USD / M, salida 0,17 USD / M (`scripts/config.py:209`) |
| Costo por llamada | ≈ 17.000 × 0,037/1e6 + 1.900 × 0,17/1e6 ≈ **USD 0,001** |
| Costo por oferta | ≈ USD 0,04–0,05 |
| Costo P1+P2 / las cuatro / P5 | ≈ USD 0,10 / 0,18 / 0,04 |
| Modelo local | **no viable**: `qwen3:8b` tiene `num_ctx = 16384` (`scripts/config.py:166`), menos que la oferta más el prompt |

### Recomendación

**Hacerlo, pero como experimento aparte y después de A+B.** Razones: ataca la causa más grande (15 de 41 NO_VALIDA, 37 %), cuesta menos de USD 0,20 y es solo nube. Condiciones: se mide con P1+P2 con el mismo criterio de decisión (sección final); no entra al pipeline hasta cumplirlo; y se vigila el recall, porque una oferta que se contradice a sí misma es justamente una trampa real que C podría descartar.

## Riesgo de recall de A y B

Cuántas trampas detectadas hoy en P1+P2 se perderían: **no verificado** (los JSON de resultados están en `datos/Resultados/`). El script está listo; lo da directamente en la columna «Trampas perdidas vs base» y en la fila «Trampas perdidas». Comando 2 abajo.

Lo que sí se puede decir sin los JSON:

- Para A, el criterio estricto no excluye ningún artículo cuyo título no sea genérico, así que una trampa solo se perdería si su artículo (o equivalente) tuviera un título de alcance u objeto. El comando de la sección A lo comprueba.
- Para B, una trampa se perdería si el modelo informó `etapa_requisito = POSTERIOR` en su brecha. Por el prompt, eso solo ocurre en brechas de INFORMACION_FALTANTE, y el ground truth v3 **no tiene ninguna trampa con fuente INFORMACION_FALTANTE** (las 60 son DESVIO o EXCEPCION_NO_ACREDITADA): el riesgo de B sobre trampas es bajo, y por la misma razón su efecto sobre las brechas existentes también.

## Cuánto podrían mejorar la precisión A y B: cotas con P3+P4 (informativo)

La precisión es (trampas encontradas + extras válidos) / brechas. Quitar solo extras NO_VALIDA no cambia el numerador (32). Con 76 brechas:

| Escenario (se quitan solo NO_VALIDA) | Brechas | Precisión | Δ |
|---|---|---|---|
| Base | 76 | 42,1 % | — |
| A estricto: 5 artículos de la lista de arriba (medido en las pendientes) | 71 | 45,1 % | +3,0 pts |
| A según el conteo del usuario (8 de «alcance/objeto») | 68 | 47,1 % | +5,0 pts |
| A criterio por palabra inicial (8 filas: 7 NO_VALIDA + 1 VALIDA, que se pierde) | 68 | 31/68 = 45,6 % | +3,5 pts (y se pierde un extra válido) |
| B (11, cota superior: todas se descartan) | 65 | 49,2 % | +7,1 pts |
| A+B (19, cota superior: sin superposición) | 57 | 56,1 % | +14,0 pts |

Para el criterio de decisión (+10 puntos sin perder ninguna trampa) hacen falta, con zero extras válidos perdidos:

- P3+P4: quitar al menos **15** brechas de las 44 que no suman al numerador (76 − 32: las 41 extras NO_VALIDA y 3 brechas que no son ni trampa encontrada ni extra).
- P1+P2: quitar al menos **23** de las 68 brechas que no suman al numerador (110 − 42).

Es decir, A+B solo alcanza el criterio si descarta casi todo lo que su cota superior permite. **A solo no alcanza; B es incierto porque casi no se puede medir sin LLM.** Conviene decidir con la medición real en P1+P2 y no con estas cotas.

## Medición en desarrollo (A+B como postproceso)

Script: `evaluacion/v2_medir_ab.py` (tests en `tests/test_v2_fase0.py`). Solo lee: no reescribe los `_extras.csv` ni llama a `evaluar.main`. Aplica A y B por separado y juntas a los JSON de P1+P2, cruza con las etiquetas (`<json>_extras.csv`, columna `valido`) y da, por variante: trampas encontradas, brechas, extras por etiqueta, precisión humana, cotas si faltan etiquetas, trampas perdidas respecto de la base, la cobertura de B y los artículos que A eliminó.

Precondición: los extras de P1+P2 tienen que estar etiquetados (comando 1). Si faltan etiquetas, el informe da «n/d» y cotas inferior y superior, y marca el resultado «no concluyente».

```
venv\Scripts\python.exe -m evaluacion.v2_medir_ab --config "gpt-oss-120b esfuerzo bajo (elegida)" --ofertas P1 P2 --salida evaluacion\diagnosticos\v2_medicion_AB_P1P2.md
```

Esa medición no mira P3 ni P4 (el script avisa si se le pide).

## P5

Estado en el repo: **no están** `evaluacion/ground_truth_P5.json`, `evaluacion/controles_negativos_P5.json` ni `evaluacion/mapa_trampas_P5.csv` (búsqueda por nombre en `evaluacion/`). La oferta (`.docx`) no la leí ni la busqué. Si alguno falta cuando se copie, `evaluar` no encuentra trampas de P5 y se detiene con un mensaje claro.

### Qué se adaptó en `evaluar.py` (implementado, con tests sintéticos)

Como los archivos reales no estaban, el esquema es **supuesto** (documentado al principio de `evaluacion/p5.py`; **no verificado**). Si el esquema real difiere, el cargador lo dice nombrando la entrada y los alias aceptados.

| Requisito | Dónde y cómo |
|---|---|
| Esquema distinto al CSV v3 | `evaluacion/p5.py`: lee los dos JSON y los lleva al formato de filas de `evaluar.py`; `evaluar.cargar_gt("P5")` y `cargar_espejos("P5")` lo usan por defecto |
| Campo `tipo` (amenaza / oportunidad) | las oportunidades quedan **fuera del recall** (11 amenazas) y se informan aparte con «marcada como brecha: sí/no» |
| Artículos equivalentes (P5-03-IF también NORM_05 1.6; P5-02-IF también NORM_02 2.15) | `articulos_equivalentes` como lista o texto; se convierte al texto «NORM_05 1.6; NORM_02 2.15» que ya lee `pares_trampa` |
| Agrupamiento P5-02-EX + D1 + IF | campo `grupo`, o por defecto el prefijo `P5-NN` de ids `-EX`, `-D<k>`, `-IF`; el informe agrega una tabla «grupo cubierto si se encontró alguna de sus trampas». El recall estricto sigue siendo por trampa |
| Falsas alarmas sobre los 13 controles negativos | control con cita: la brecha cuya cita la contiene y cuyo artículo coincide; control **sin cita** (NORM_04 3.20 y NORM_01 4.1): cuenta **por artículo**; una brecha que es la trampa encontrada no cuenta como falsa alarma de un control sin cita; en modo lista un control sin cita nunca se marca |
| Oferta P5 en `run_oferta` | `_oferta_de` reconoce P1–P5 |

Dudas a confirmar con los archivos reales: (a) qué hacer si una brecha cae sobre una oportunidad (hoy solo se informa); (b) si los controles con cita deben contar por artículo igual que los dos sin cita (hoy: frase y artículo, como los casos conformes de v3); (c) el nombre real de los campos.

### Comandos para P5 (una sola corrida, con la configuración final)

Recuperación (sin LLM) con el perfil elegido; imprime la ruta del JSON de recuperación:

```
venv\Scripts\python.exe -m scripts.recuperar datos\ProyectoAnalizar\P5_oferta_CMP5000.docx --perfil-recuperacion elegido
```

gpt-oss-120b (DeepInfra). Primero la estimación, que no llama a la API:

```
venv\Scripts\python.exe -m scripts.nube --estimar --reusar-recuperacion <json_de_recuperacion> --modelo openai/gpt-oss-120b
venv\Scripts\python.exe -m scripts.nube --reusar-recuperacion <json_de_recuperacion> --pdf datos\ProyectoAnalizar\P5_oferta_CMP5000.docx --modelo openai/gpt-oss-120b
```

`qwen3:8b` local (con Ollama en marcha), sobre exactamente los mismos pares:

```
venv\Scripts\python.exe -m scripts.run_oferta datos\ProyectoAnalizar\P5_oferta_CMP5000.docx --oferta P5 --reusar-recuperacion <json_de_recuperacion>
```

Evaluación de cada JSON resultante:

```
venv\Scripts\python.exe -m evaluacion.evaluar --resultado <json_resultado> --oferta P5
```

Costo estimado. gpt-oss: USD 0,00051 por par (0,6843 USD / 1.334 pares en la tabla). Con los 306–361 pares por oferta que se vieron en P1–P4 son unos **USD 0,16–0,19** (el tamaño de P5 es no verificado; `--estimar` da el número exacto). Local: 19,3 s por par (25.748 s / 1.334 pares) → unas **1,8 h** con ~330 pares y USD 0.

## Criterios de decisión (propuesta, fijados antes de validar; los aprueba el usuario)

1. **A+B se adopta** si, en P1+P2, la precisión humana sube al menos **10 puntos** respecto de la base (38,2 %) **y** no se pierde ninguna trampa detectada. Lo calcula `v2_medir_ab` (fila «Criterio de decisión»).
2. **C se adopta** con el mismo criterio, medido sobre la configuración que ya incluya A+B si esta se adoptó.
3. **Ni P3+P4 ni P5 se usan para ajustar.** P3+P4 es la segunda evaluación. **P5 se corre una sola vez**, con la configuración final y con ambos modelos, y no se vuelve a correr después de ver el resultado.
4. Se informa el resultado aunque no cumpla el criterio.
