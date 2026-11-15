# Diferencia trampa por trampa: v1 contra elegida

- v1: Qwen3-32B
- elegida: Qwen3-32B (elegida)

Categorías de pérdida de evaluar.py: **encontrada** (brecha con la frase y el artículo); **no recuperada** (el artículo no llegó al verificador); **perdida en verificación** (llegó y se dijo Cumple o No aplica); **perdida en clasificación** (se dijo Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE); **otra causa** (verificada como Incumple o Revisar y clasificada como riesgo, pero ninguna brecha cita la frase de la trampa con su artículo), desglosada en subcausas.

## Parámetros de cada corrida

| Parámetro | v1 | elegida |
|---|---|---|
| Corrida | Qwen3-32B | Qwen3-32B (elegida) |
| Modelo | deepinfra:Qwen/Qwen3-32B | deepinfra:Qwen/Qwen3-32B |
| Temperatura | 0 | 0 |
| Semilla | 42 | 42 |
| Razonamiento en la verificación | False | False |
| Esfuerzo de razonamiento (modelos con razonamiento fijo) | no guardada | None |
| Temperatura con razonamiento | N/A / no guardada | no guardada |
| top_p con razonamiento | N/A / no guardada | no guardada |
| top_k con razonamiento | N/A / no guardada | no guardada |
| Embeddings de la recuperación | no guardada | bge-m3 |
| Perfil de recuperación | no guardada / local | elegido |
| Numeración de oraciones igual a la actual (oraciones citadas por brechas) | 303/303 | 434/434 |

La temperatura y la semilla que se guardan son las que se configuraron en el cliente (`temperature` y `seed` de configuracion_analisis); el JSON no dice si el proveedor de la API las aplicó (las corridas en la nube las mandan con la semilla de config.OLLAMA_SEED).

## Resumen por conjunto

Techo del sistema = trampas − no recuperadas − vetadas por cálculo − descartadas por regla 2.5: lo máximo que lograría un verificador perfecto con esa recuperación (el recall estricto no puede pasarlo).

| Conjunto | Trampas | Recall estricto (v1 → elegida) | Techo del sistema (v1 → elegida) | Llegan al verificador (v1 → elegida) | No recuperadas | Vetadas por cálculo | Descartadas por regla 2.5 | Perdida en verificación | Perdida en clasificación | Otra causa (total) |
|---|---|---|---|---|---|---|---|---|---|---|
| P1–P2 desarrollo | 30 | 20 → 23 | 24 → 27 | 24 → 28 | 6 → 2 | 0 → 1 | 0 → 0 | 4 → 4 | 0 → 0 | 0 → 1 |
| P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1) | 30 | 21 → 19 | 23 → 22 | 25 → 26 | 5 → 4 | 1 → 1 | 1 → 3 | 1 → 3 | 0 → 0 | 3 → 4 |
| P1–P4 total | 60 | 41 → 42 | 47 → 49 | 49 → 54 | 11 → 6 | 1 → 2 | 1 → 3 | 5 → 7 | 0 → 0 | 3 → 5 |

## «Otra causa» por subcausa

Desglose informativo (evaluar.subcausa_otra_causa); no cambia la definición de «encontrada» ni del recall estricto.

| Subcausa | v1 | elegida |
|---|---|---|
| vetada por cálculo | 1 | 2 |
| descartada por regla 2.5 | 1 | 3 |
| descartada por regla 2.7.c | 0 | 0 |
| cita otro artículo | 1 | 0 |
| salió como alerta | 0 | 0 |
| otra | 0 | 0 |

## Transiciones de pérdida (v1 → elegida)

Primero las que cambian, después las que quedan igual.

| v1 | elegida | Total | P1–P2 desarrollo | P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1) | P1–P4 total | Trampas |
|---|---|---|---|---|---|---|
| encontrada | perdida en verificación | 3 | 1 | 2 | 3 | P1-04-M, P4-02-A, P4-05-M |
| encontrada | otra causa | 1 | 1 | 0 | 1 | P2-03-B |
| perdida en verificación | encontrada | 1 | 1 | 0 | 1 | P2-03-A |
| no recuperada | encontrada | 4 | 4 | 0 | 4 | P1-04-B, P1-05-M, P2-01-M, P2-01-B |
| no recuperada | otra causa | 1 | 0 | 1 | 1 | P4-05-A |
| encontrada | encontrada (igual) | 37 | 18 | 19 | 37 | P1-01-A, P1-01-M, P1-02-A, P1-02-M, P1-02-B, P1-03-A, P1-03-M, P1-03-B, P1-04-A, P1-05-A, P2-01-A, P2-02-A, P2-02-B, P2-03-M, P2-04-A, P2-04-M, P2-05-M, P2-05-B, P3-01-M, P3-01-B, P3-02-M, P3-02-B, P3-03-A, P3-03-M, P3-03-B, P3-04-A, P3-04-M, P4-01-A, P4-01-M, P4-02-M, P4-02-B, P4-03-A, P4-03-M, P4-04-A, P4-04-M, P4-04-B, P4-05-B |
| perdida en verificación | perdida en verificación (igual) | 4 | 3 | 1 | 4 | P1-01-B, P1-05-B, P2-02-M, P4-01-B |
| no recuperada | no recuperada (igual) | 6 | 2 | 4 | 6 | P2-04-B, P2-05-A, P3-02-A, P3-05-A, P3-05-M, P3-05-B |
| otra causa | otra causa (igual) | 3 | 0 | 3 | 3 | P3-01-A, P3-04-B, P4-03-B |

## Trampas ganadas y perdidas (recall estricto)

Ganadas en elegida: 5. Perdidas en elegida: 4. Neto: +1.

### Ganadas (no encontradas en v1, encontradas en elegida)

| Trampa | Artículo | Pérdida en la otra corrida | Veredicto del verificador (v1 → elegida) |
|---|---|---|---|
| P1-04-B | NORM_04 2.5 | no recuperada | — → Incumple |
| P1-05-M | NORM_05 2.1 | no recuperada | — → Incumple |
| P2-01-M | NORM_01 3.2 | no recuperada | — → Incumple |
| P2-01-B | NORM_01 3.7 | no recuperada | — → Incumple |
| P2-03-A | NORM_03 2.8 | perdida en verificación | Cumple → Incumple |

### Perdidas (encontradas en v1, no encontradas en elegida)

| Trampa | Artículo | Pérdida en la otra corrida | Veredicto del verificador (v1 → elegida) |
|---|---|---|---|
| P1-04-M | NORM_04 3.8 | perdida en verificación | Revisar → Cumple |
| P2-03-B | NORM_03 6.2 | otra causa (vetada por cálculo) | Incumple → Incumple |
| P4-02-A | NORM_02 4.15 | perdida en verificación | Incumple → Cumple |
| P4-05-M | NORM_05 4.8 | perdida en verificación | Incumple → Cumple |

## Perdidas en verificación: ¿la frase estaba en lo que citó el verificador?

El verificador recibe la **sección entera** numerada (`seccion_numerada`), así que la frase de la trampa siempre estaba en el prompt salvo que la segmentación la corte en dos oraciones. Lo que el JSON permite separar es otra cosa: si el modelo **citó** las oraciones de la frase. **sí**: cita todas las oraciones que ocupa la frase; **parcial**: solo algunas (la frase cruza dos oraciones); **no**: cita otras (oración distractora); **sin citas**: no citó ninguna (lo normal en un Cumple); **n/d**: no se pudo calcular.

| Trampa | Artículo | Corrida | Pérdida | Veredicto | Oraciones de la frase | Oraciones citadas | ¿La frase estaba en lo citado? |
|---|---|---|---|---|---|---|---|
| P1-01-B | NORM_01 6.5 | v1 | perdida en verificación | Cumple | O6 | O7 | no |
| P1-01-B | NORM_01 6.5 | elegida | perdida en verificación | Cumple | O6 | O7 | no |
| P1-04-M | NORM_04 3.8 | v1 | encontrada | Revisar | O6 | O6 | sí |
| P1-04-M | NORM_04 3.8 | elegida | perdida en verificación | Cumple | O6 | O6 | sí |
| P1-05-B | NORM_05 4.4 | v1 | perdida en verificación | Cumple | O16 | O16 | sí |
| P1-05-B | NORM_05 4.4 | elegida | perdida en verificación | Cumple | O16 | O16 | sí |
| P2-02-M | NORM_02 2.16 | v1 | perdida en verificación | Cumple | O8 | O8 | sí |
| P2-02-M | NORM_02 2.16 | elegida | perdida en verificación | Cumple | O8 | O8 | sí |
| P2-03-A | NORM_03 2.8 | v1 | perdida en verificación | Cumple | O4 | O4, O7 | sí |
| P2-03-A | NORM_03 2.8 | elegida | encontrada | Incumple | O4 | O4, O6, O7 | sí |
| P4-01-B | NORM_01 4.1 | v1 | perdida en verificación | Cumple | O15 | O14, O15 | sí |
| P4-01-B | NORM_01 4.1 | elegida | perdida en verificación | Cumple | O15 | O14 | no |
| P4-02-A | NORM_02 4.15 | v1 | encontrada | Incumple | O11 | O11, O12 | sí |
| P4-02-A | NORM_02 4.15 | elegida | perdida en verificación | Cumple | O11 | O12 | no |
| P4-05-M | NORM_05 4.8 | v1 | encontrada | Incumple | O17 | O17, O18 | sí |
| P4-05-M | NORM_05 4.8 | elegida | perdida en verificación | Cumple | O17 | O18 | no |

Cuántas de las perdidas en verificación caen en cada caso:

| Corrida | sí | parcial | no | sin citas | n/d |
|---|---|---|---|---|---|
| v1 | 4 | 0 | 1 | 0 | 0 |
| elegida | 3 | 0 | 4 | 0 | 0 |

### Casos señalados

#### P1-04-M · NORM_04 3.8

Frase de la trampa: «pasadas de acabado de 0,5 mm»

- **v1** (encontrada): frase en O6; citó O6 → **sí**. NORM_04 3.8: Revisar (oraciones O6) — La oferta menciona el uso de material real y pasadas de acabado de 0,5 mm, pero no especifica que al menos una unidad se procese en el punto de mayor exigencia de carga de corte.
- **elegida** (perdida en verificación): frase en O6; citó O6 → **sí**. NORM_04 3.8: Cumple (oraciones O6) — La oferta menciona el uso de material ferroviario real y aplica una profundidad de pasada de 0,5 mm, lo cual cumple con el requisito de usar material real y parámetros de corte aprobados.
  - O6: Para no comprometer la vida útil de las ruedas de la flota, el SAT se ejecutará con 3 pares montados reales provistos por el Comitente, identificados individualmente, aplicando únicamente pasadas de acabado de 0,5 mm de profundidad.

#### P4-02-A · NORM_02 4.15

Frase de la trampa: «diferencial general de 300 mA»

- **v1** (encontrada): frase en O11; citó O11, O12 → **sí**. NORM_02 4.15: Incumple (oraciones O11, O12) — La oferta protege las tomas de mantenimiento con un diferencial de 300 mA, lo que incumple el requisito de sensibilidad ≤ 30 mA para protección complementaria.
- **elegida** (perdida en verificación): frase en O11; citó O12 → **no**. NORM_02 4.15: Cumple (oraciones O12) — La oferta especifica una protección diferencial de 30 mA para las tomas de uso general, lo cual cumple con el límite máximo establecido por el artículo.
  - O11: Las tomas de mantenimiento dentro de la fosa quedarán protegidas por el diferencial general de 300 mA del tablero seccional, evitando disparos por humedad que interrumpen las tareas de limpieza.
  - O12: Las tomas de uso general de la nave conservan su protección diferencial de 30 mA.

#### P4-05-M · NORM_05 4.8

Frase de la trampa: «separados 50 mm»

- **v1** (encontrada): frase en O17; citó O17, O18 → **sí**. NORM_05 4.8: Incumple (oraciones O17, O18) — La oferta no cumple con la separación mínima de 200 mm entre cables de motor y encoder, y aunque la terminación de la pantalla es correcta, la compartición de bandeja con separación insuficiente incumple el artículo.
- **elegida** (perdida en verificación): frase en O17; citó O18 → **no**. NORM_05 4.8: Cumple (oraciones O18) — La oferta especifica que las pantallas de los cables de encoder se terminan con abrazadera de 360° en ambos extremos, lo cual cumple con el requisito del artículo.
  - O17: Los cables de encoder y de motor compartirán bandeja, separados 50 mm mediante precintos, para simplificar el tendido y reducir el número de bandejas en la zona del torno.
  - O18: Las pantallas de los cables de encoder se terminarán con abrazadera de 360° en ambos extremos.

## «Otra causa» en v1

3 trampas: el artículo llegó al verificador, la verificación dijo Incumple o Revisar y la clasificación no la descartó como CUMPLE/NO_APLICA, pero ninguna brecha cita la frase de la trampa con su artículo.

| Trampa | Artículo | Subcausa | Verificación | Clasificación | Cifras extraídas (si fue vetada por cálculo) | Cita de la brecha del par |
|---|---|---|---|---|---|---|
| P3-01-A | NORM_01 6.1 | vetada por cálculo | NORM_01 6.1: Incumple (oraciones O8, O9) — La excavación tiene una profundidad de 2,10 m, por lo que según el artículo 6.1, se requiere un sistema de contención lateral metálico, lo cual no se cumple al usar taludes naturales. | — | ofertado 2,10 / exigido 1,20 / límite MINIMO / objeto CUANTITATIVO_TECNICO / brecha relativa 0.0 | La excavación para el bloque de fundación (2,10 m de profundidad bajo NPT, planta de 5,2 × 4,6 m) se ejecutará con taludes naturales 1:0,5, dada la buena cohesión del suelo observada en el sitio y en… [descartada por cálculo] |
| P3-04-B | NORM_04 3.10 | cita otro artículo | NORM_04 3.10: Incumple (oraciones O9) — La oferta especifica una sola traza por rueda, mientras que el artículo exige al menos tres trazas distribuidas angularmente a 120 grados. | — | — | Palpador y medición independiente; desviación ≤ 0,15 mm Concentricidad ≤ 0,10 mm Rugosidad superficial |
| P4-03-B | NORM_03 3.6 | descartada por regla 2.5 | NORM_03 3.6: Incumple (oraciones O9, O10) — La oferta menciona una verificación diaria antes del uso, lo cual cumple con el artículo, pero no menciona la inspección trimestral por personal especializado, ni se especifica si se cumplirá con la documentación completa de la inspección. | INFORMACION_FALTANTE (regla 2.5) — La oferta menciona una verificación diaria antes del uso, lo cual cumple con el artículo, pero no menciona la inspección trimestral por personal especializado ni la documentación completa de la inspección. [Art. 2.5: no es un ítem del Art. 2.6] | — | — |

## «Otra causa» en elegida

5 trampas: el artículo llegó al verificador, la verificación dijo Incumple o Revisar y la clasificación no la descartó como CUMPLE/NO_APLICA, pero ninguna brecha cita la frase de la trampa con su artículo.

| Trampa | Artículo | Subcausa | Verificación | Clasificación | Cifras extraídas (si fue vetada por cálculo) | Cita de la brecha del par |
|---|---|---|---|---|---|---|
| P2-03-B | NORM_03 6.2 | vetada por cálculo | NORM_03 6.2: Incumple (oraciones O17, O18) — La oferta garantiza un nivel sonoro ≤ 85 dB(A), pero la medición se realiza a 3 m, no a 1 m como exige el artículo. | — | ofertado 85 / exigido 85 / límite MAXIMO / objeto CUANTITATIVO_TECNICO / brecha relativa 0.0 | El nivel sonoro de la central hidráulica se verificará en comisionamiento a 3 m del equipo, garantizándose un valor ≤ 85 dB(A). La central se suministra con capota acústica y bomba de bajo nivel sono… [descartada por cálculo] |
| P3-01-A | NORM_01 6.1 | vetada por cálculo | NORM_01 6.1: Incumple (oraciones O8, O9) — La excavación tiene 2,10 m de profundidad, por lo que según el artículo 6.1, requiere un sistema de contención lateral metálico calculado, lo cual no se cumple al usar taludes naturales. | — | ofertado 2,10 / exigido 1,20 / límite MINIMO / objeto CUANTITATIVO_TECNICO / brecha relativa 0.0 | La excavación para el bloque de fundación (2,10 m de profundidad bajo NPT, planta de 5,2 × 4,6 m) se ejecutará con taludes naturales 1:0,5, dada la buena cohesión del suelo observada en el sitio y en… [descartada por cálculo] |
| P3-04-B | NORM_04 3.10 | descartada por regla 2.5 | NORM_04 3.10: Incumple (oraciones O9, O10) — La oferta especifica Ra ≤ 3,2 μm, pero no menciona que se realicen al menos tres trazas distribuidas a 120 grados ni que el límite esté definido en la ficha de aceptación del proyecto. | INFORMACION_FALTANTE (regla 2.5) — La oferta describe la actividad de verificación de rugosidad superficial, pero omite declarar que se realicen al menos tres trazas distribuidas a 120 grados y que el límite de rugosidad esté definido en la ficha de aceptación del proyecto, datos exigibles según el… | — | — |
| P4-03-B | NORM_03 3.6 | descartada por regla 2.5 | NORM_03 3.6: Incumple (oraciones O9, O10) — La oferta menciona verificación diaria, pero no menciona inspección trimestral por personal especializado, que es un requisito del artículo. | INFORMACION_FALTANTE (regla 2.5) — La oferta menciona verificación diaria, pero no menciona inspección trimestral por personal especializado, que es un requisito del artículo. [Art. 2.5: no es un ítem del Art. 2.6] | — | — |
| P4-05-A | NORM_05 3.9 | descartada por regla 2.5 | NORM_05 3.9: Revisar (oraciones O4) — La oferta menciona la eliminación de trazas de condensado, pero no especifica cómo se mide ni si cumple con los límites de humedad establecidos por la norma. | INFORMACION_FALTANTE (regla 2.5) — La oferta menciona la eliminación de trazas de condensado, pero no especifica cómo se mide ni si cumple con los límites de humedad establecidos por la norma. [Art. 2.5: no es un ítem del Art. 2.6] | — | — |

## Trampa por trampa

| Trampa | Artículo | Pérdida en v1 | Pérdida en elegida | Frase en lo que citó el verificador (v1 → elegida; solo si se perdió en verificación) | Veredicto del verificador (v1 → elegida) | Explicación del verificador (donde cambia) |
|---|---|---|---|---|---|---|
| P1-01-A | NORM_01 4.2 | encontrada | encontrada |  |  |  |
| P1-01-M | NORM_01 6.3 | encontrada | encontrada |  |  |  |
| P1-01-B | NORM_01 6.5 | perdida en verificación | perdida en verificación | no → no |  |  |
| P1-02-A | NORM_02 5.4 | encontrada | encontrada |  |  |  |
| P1-02-M | NORM_02 4.5 | encontrada | encontrada |  |  |  |
| P1-02-B | NORM_02 5.16 | encontrada | encontrada |  |  |  |
| P1-03-A | NORM_03 2.2 | encontrada | encontrada |  |  |  |
| P1-03-M | NORM_03 2.6 | encontrada | encontrada |  |  |  |
| P1-03-B | NORM_03 5.1 | encontrada | encontrada |  |  |  |
| P1-04-A | NORM_04 2.3 | encontrada | encontrada |  |  |  |
| P1-04-M | NORM_04 3.8 | encontrada | perdida en verificación **(cambia)** | sí → sí | Revisar → Cumple | **elegida:** NORM_04 3.8: Cumple (oraciones O6) — La oferta menciona el uso de material ferroviario real y aplica una profundidad de pasada de 0,5 mm, lo cual cumple con el requisito de usar material real y parámetros de corte aprobados.<br>**v1:** NORM_04 3.8: Revisar (oraciones O6) — La oferta menciona el uso de material real y pasadas de acabado de 0,5 mm, pero no especifica que al menos una unidad se procese en el punto de mayor exigencia de carga de corte. |
| P1-04-B | NORM_04 2.5 | no recuperada | encontrada **(cambia)** |  | — → Incumple | **elegida:** NORM_04 2.5: Incumple (oraciones O12) — La oferta establece una separación entre secciones de 1,00 m, lo que excede el límite máximo de 0,50 m fijado por la norma.<br>**v1:** no llegó al verificador |
| P1-05-A | NORM_05 3.4 | encontrada | encontrada |  |  |  |
| P1-05-M | NORM_05 2.1 | no recuperada | encontrada **(cambia)** |  | — → Incumple | **elegida:** NORM_05 2.1: Incumple (oraciones O5) — La desviación máxima de nivelación final de la oferta (0,05 mm/m) excede el límite máximo permitido por la norma (0,02 mm/m).<br>**v1:** no llegó al verificador |
| P1-05-B | NORM_05 4.4 | perdida en verificación | perdida en verificación | sí → sí |  |  |
| P2-01-A | NORM_01 5.2 | encontrada | encontrada |  |  |  |
| P2-01-M | NORM_01 3.2 | no recuperada | encontrada **(cambia)** |  | — → Incumple | **elegida:** NORM_01 3.2: Incumple (oraciones O12, O13) — La oferta especifica un contenido de cemento de 330 kg/m³, que cumple el mínimo de 300 kg/m³, pero la relación agua/cemento de 0,52 excede el límite máximo de 0,48 establecido por el artículo.<br>**v1:** no llegó al verificador |
| P2-01-B | NORM_01 3.7 | no recuperada | encontrada **(cambia)** |  | — → Incumple | **elegida:** NORM_01 3.7: Incumple (oraciones O17) — La oferta menciona exclusivamente el uso de un ensayo esclerométrico aislado para validar la resistencia del hormigón, lo cual no cumple con el artículo que prohíbe este uso sin correlación con otros métodos.<br>**v1:** no llegó al verificador |
| P2-02-A | NORM_02 3.13 | encontrada | encontrada |  |  |  |
| P2-02-M | NORM_02 2.16 | perdida en verificación | perdida en verificación | sí → sí |  |  |
| P2-02-B | NORM_02 4.7 | encontrada | encontrada |  |  |  |
| P2-03-A | NORM_03 2.8 | perdida en verificación | encontrada **(cambia)** | sí → sí | Cumple → Incumple | **elegida:** NORM_03 2.8: Incumple (oraciones O4, O6, O7) — La oferta menciona que cada grúa tomará 12 t, pero el artículo prohíbe dividir el peso total por el número de grúas sin cálculo detallado.<br>**v1:** NORM_03 2.8: Cumple (oraciones O4, O7) — La oferta menciona el uso de dos grúas en tándem y la presencia de un director de izaje único con comunicación en canal dedicado, lo cual cumple con los requisitos del artículo. |
| P2-03-M | NORM_03 2.4 | encontrada | encontrada |  |  |  |
| P2-03-B | NORM_03 6.2 | encontrada | otra causa (vetada por cálculo) **(cambia)** |  | Incumple → Incumple | **elegida:** NORM_03 6.2: Incumple (oraciones O17, O18) — La oferta garantiza un nivel sonoro ≤ 85 dB(A), pero la medición se realiza a 3 m, no a 1 m como exige el artículo.<br>**v1:** NORM_03 6.2: Incumple (oraciones O17, O18) — La oferta garantiza un nivel sonoro ≤ 85 dB(A), pero la medición se realiza a 3 m, no a 1 m de la envolvente exterior como exige el artículo. |
| P2-04-A | NORM_04 3.2 | encontrada | encontrada |  |  |  |
| P2-04-M | NORM_04 2.6 | encontrada | encontrada |  |  |  |
| P2-04-B | NORM_04 2.13 | no recuperada | no recuperada |  |  |  |
| P2-05-A | NORM_05 1.8 | no recuperada | no recuperada |  |  |  |
| P2-05-M | NORM_05 3.5 | encontrada | encontrada |  |  |  |
| P2-05-B | NORM_05 3.8 | encontrada | encontrada |  |  |  |
| P3-01-A | NORM_01 6.1 | otra causa (vetada por cálculo) | otra causa (vetada por cálculo) |  |  |  |
| P3-01-M | NORM_01 7.3 | encontrada | encontrada |  |  |  |
| P3-01-B | NORM_01 8.2 | encontrada | encontrada |  |  |  |
| P3-02-A | NORM_02 5.14 | no recuperada | no recuperada |  |  |  |
| P3-02-M | NORM_02 5.5 | encontrada | encontrada |  |  |  |
| P3-02-B | NORM_02 1.11 | encontrada | encontrada |  |  |  |
| P3-03-A | NORM_03 4.7 | encontrada | encontrada |  |  |  |
| P3-03-M | NORM_03 5.5 | encontrada | encontrada |  |  |  |
| P3-03-B | NORM_03 5.2 | encontrada | encontrada |  |  |  |
| P3-04-A | NORM_04 3.6 | encontrada | encontrada |  |  |  |
| P3-04-M | NORM_04 1.6 | encontrada | encontrada |  |  |  |
| P3-04-B | NORM_04 3.10 | otra causa (cita otro artículo) | otra causa (descartada por regla 2.5) |  |  |  |
| P3-05-A | NORM_05 4.3 | no recuperada | no recuperada |  |  |  |
| P3-05-M | NORM_05 2.9 | no recuperada | no recuperada |  |  |  |
| P3-05-B | NORM_05 2.3 | no recuperada | no recuperada |  |  |  |
| P4-01-A | NORM_01 3.1 | encontrada | encontrada |  |  |  |
| P4-01-M | NORM_01 3.5 | encontrada | encontrada |  |  |  |
| P4-01-B | NORM_01 4.1 | perdida en verificación | perdida en verificación | sí → no |  |  |
| P4-02-A | NORM_02 4.15 | encontrada | perdida en verificación **(cambia)** | sí → no | Incumple → Cumple | **elegida:** NORM_02 4.15: Cumple (oraciones O12) — La oferta especifica una protección diferencial de 30 mA para las tomas de uso general, lo cual cumple con el límite máximo establecido por el artículo.<br>**v1:** NORM_02 4.15: Incumple (oraciones O11, O12) — La oferta protege las tomas de mantenimiento con un diferencial de 300 mA, lo que incumple el requisito de sensibilidad ≤ 30 mA para protección complementaria. |
| P4-02-M | NORM_02 1.10 | encontrada | encontrada |  |  |  |
| P4-02-B | NORM_02 4.10 | encontrada | encontrada |  |  |  |
| P4-03-A | NORM_03 3.4 | encontrada | encontrada |  |  |  |
| P4-03-M | NORM_03 4.2 | encontrada | encontrada |  |  |  |
| P4-03-B | NORM_03 3.6 | otra causa (descartada por regla 2.5) | otra causa (descartada por regla 2.5) |  |  |  |
| P4-04-A | NORM_04 1.10 | encontrada | encontrada |  |  |  |
| P4-04-M | NORM_04 3.20 | encontrada | encontrada |  |  |  |
| P4-04-B | NORM_04 3.12 | encontrada | encontrada |  |  |  |
| P4-05-A | NORM_05 3.9 | no recuperada | otra causa (descartada por regla 2.5) **(cambia)** |  | — → Revisar | **elegida:** NORM_05 3.9: Revisar (oraciones O4) — La oferta menciona la eliminación de trazas de condensado, pero no especifica cómo se mide ni si cumple con los límites de humedad establecidos por la norma.<br>**v1:** no llegó al verificador |
| P4-05-M | NORM_05 4.8 | encontrada | perdida en verificación **(cambia)** | sí → no | Incumple → Cumple | **elegida:** NORM_05 4.8: Cumple (oraciones O18) — La oferta especifica que las pantallas de los cables de encoder se terminan con abrazadera de 360° en ambos extremos, lo cual cumple con el requisito del artículo.<br>**v1:** NORM_05 4.8: Incumple (oraciones O17, O18) — La oferta no cumple con la separación mínima de 200 mm entre cables de motor y encoder, y aunque la terminación de la pantalla es correcta, la compartición de bandeja con separación insuficiente incumple el artículo. |
| P4-05-B | NORM_05 4.5 | encontrada | encontrada |  |  |  |

