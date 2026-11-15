# Diferencia trampa por trampa: 32B elegida contra gpt-oss elegida

- 32B elegida: Qwen3-32B (elegida)
- gpt-oss elegida: gpt-oss-120b esfuerzo bajo (elegida)

Categorías de pérdida de evaluar.py: **encontrada** (brecha con la frase y el artículo); **no recuperada** (el artículo no llegó al verificador); **perdida en verificación** (llegó y se dijo Cumple o No aplica); **perdida en clasificación** (se dijo Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE); **otra causa** (verificada como Incumple o Revisar y clasificada como riesgo, pero ninguna brecha cita la frase de la trampa con su artículo), desglosada en subcausas.

## Parámetros de cada corrida

| Parámetro | 32B elegida | gpt-oss elegida |
|---|---|---|
| Corrida | Qwen3-32B (elegida) | gpt-oss-120b esfuerzo bajo (elegida) |
| Modelo | deepinfra:Qwen/Qwen3-32B | deepinfra:openai/gpt-oss-120b |
| Temperatura | 0 | 0 |
| Semilla | 42 | 42 |
| Razonamiento en la verificación | False | False |
| Esfuerzo de razonamiento (modelos con razonamiento fijo) | None | Reasoning: low |
| Temperatura con razonamiento | no guardada | no guardada |
| top_p con razonamiento | no guardada | no guardada |
| top_k con razonamiento | no guardada | no guardada |
| Embeddings de la recuperación | bge-m3 | bge-m3 |
| Perfil de recuperación | elegido | elegido |
| Numeración de oraciones igual a la actual (oraciones citadas por brechas) | 434/434 | 361/361 |

La temperatura y la semilla que se guardan son las que se configuraron en el cliente (`temperature` y `seed` de configuracion_analisis); el JSON no dice si el proveedor de la API las aplicó (las corridas en la nube las mandan con la semilla de config.OLLAMA_SEED).

## Resumen por conjunto

Techo del sistema = trampas − no recuperadas − vetadas por cálculo − descartadas por regla 2.5: lo máximo que lograría un verificador perfecto con esa recuperación (el recall estricto no puede pasarlo).

| Conjunto | Trampas | Recall estricto (32B elegida → gpt-oss elegida) | Techo del sistema (32B elegida → gpt-oss elegida) | Llegan al verificador (32B elegida → gpt-oss elegida) | No recuperadas | Vetadas por cálculo | Descartadas por regla 2.5 | Perdida en verificación | Perdida en clasificación | Otra causa (total) |
|---|---|---|---|---|---|---|---|---|---|---|
| P1–P2 desarrollo | 30 | 23 → 24 | 27 → 27 | 28 → 28 | 2 → 2 | 1 → 0 | 0 → 1 | 4 → 0 | 0 → 3 | 1 → 1 |
| P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1) | 30 | 19 → 23 | 22 → 25 | 26 → 26 | 4 → 4 | 1 → 0 | 3 → 1 | 3 → 1 | 0 → 1 | 4 → 1 |
| P1–P4 total | 60 | 42 → 47 | 49 → 52 | 54 → 54 | 6 → 6 | 2 → 0 | 3 → 2 | 7 → 1 | 0 → 4 | 5 → 2 |

## «Otra causa» por subcausa

Desglose informativo (evaluar.subcausa_otra_causa); no cambia la definición de «encontrada» ni del recall estricto.

| Subcausa | 32B elegida | gpt-oss elegida |
|---|---|---|
| vetada por cálculo | 2 | 0 |
| descartada por regla 2.5 | 3 | 2 |
| descartada por regla 2.7.c | 0 | 0 |
| cita otro artículo | 0 | 0 |
| salió como alerta | 0 | 0 |
| otra | 0 | 0 |

## Transiciones de pérdida (32B elegida → gpt-oss elegida)

Primero las que cambian, después las que quedan igual.

| 32B elegida | gpt-oss elegida | Total | P1–P2 desarrollo | P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1) | P1–P4 total | Trampas |
|---|---|---|---|---|---|---|
| encontrada | perdida en clasificación | 2 | 1 | 1 | 2 | P2-02-A, P4-04-M |
| encontrada | perdida en verificación | 1 | 0 | 1 | 1 | P3-01-M |
| encontrada | otra causa | 1 | 1 | 0 | 1 | P1-02-B |
| perdida en verificación | encontrada | 4 | 2 | 2 | 4 | P1-01-B, P1-05-B, P4-02-A, P4-05-M |
| perdida en verificación | perdida en clasificación | 2 | 2 | 0 | 2 | P1-04-M, P2-02-M |
| perdida en verificación | otra causa | 1 | 0 | 1 | 1 | P4-01-B |
| otra causa | encontrada | 5 | 1 | 4 | 5 | P2-03-B, P3-01-A, P3-04-B, P4-03-B, P4-05-A |
| encontrada | encontrada (igual) | 38 | 21 | 17 | 38 | P1-01-A, P1-01-M, P1-02-A, P1-02-M, P1-03-A, P1-03-M, P1-03-B, P1-04-A, P1-04-B, P1-05-A, P1-05-M, P2-01-A, P2-01-M, P2-01-B, P2-02-B, P2-03-A, P2-03-M, P2-04-A, P2-04-M, P2-05-M, P2-05-B, P3-01-B, P3-02-M, P3-02-B, P3-03-A, P3-03-M, P3-03-B, P3-04-A, P3-04-M, P4-01-A, P4-01-M, P4-02-M, P4-02-B, P4-03-A, P4-03-M, P4-04-A, P4-04-B, P4-05-B |
| no recuperada | no recuperada (igual) | 6 | 2 | 4 | 6 | P2-04-B, P2-05-A, P3-02-A, P3-05-A, P3-05-M, P3-05-B |

## Trampas ganadas y perdidas (recall estricto)

Ganadas en gpt-oss elegida: 9. Perdidas en gpt-oss elegida: 4. Neto: +5.

### Ganadas (no encontradas en 32B elegida, encontradas en gpt-oss elegida)

| Trampa | Artículo | Pérdida en la otra corrida | Veredicto del verificador (32B elegida → gpt-oss elegida) |
|---|---|---|---|
| P1-01-B | NORM_01 6.5 | perdida en verificación | Cumple → Incumple |
| P1-05-B | NORM_05 4.4 | perdida en verificación | Cumple → Incumple |
| P2-03-B | NORM_03 6.2 | otra causa (vetada por cálculo) | Incumple → Incumple |
| P3-01-A | NORM_01 6.1 | otra causa (vetada por cálculo) | Incumple → Incumple |
| P3-04-B | NORM_04 3.10 | otra causa (descartada por regla 2.5) | Incumple → Incumple |
| P4-02-A | NORM_02 4.15 | perdida en verificación | Cumple → Incumple |
| P4-03-B | NORM_03 3.6 | otra causa (descartada por regla 2.5) | Incumple → Incumple |
| P4-05-A | NORM_05 3.9 | otra causa (descartada por regla 2.5) | Revisar → Incumple |
| P4-05-M | NORM_05 4.8 | perdida en verificación | Cumple → Incumple |

### Perdidas (encontradas en 32B elegida, no encontradas en gpt-oss elegida)

| Trampa | Artículo | Pérdida en la otra corrida | Veredicto del verificador (32B elegida → gpt-oss elegida) |
|---|---|---|---|
| P1-02-B | NORM_02 5.16 | otra causa (descartada por regla 2.5) | Incumple → Incumple |
| P2-02-A | NORM_02 3.13 | perdida en clasificación | Revisar → Revisar |
| P3-01-M | NORM_01 7.3 | perdida en verificación | Revisar → No aplica |
| P4-04-M | NORM_04 3.20 | perdida en clasificación | Incumple → Incumple |

## Perdidas en verificación: ¿la frase estaba en lo que citó el verificador?

El verificador recibe la **sección entera** numerada (`seccion_numerada`), así que la frase de la trampa siempre estaba en el prompt salvo que la segmentación la corte en dos oraciones. Lo que el JSON permite separar es otra cosa: si el modelo **citó** las oraciones de la frase. **sí**: cita todas las oraciones que ocupa la frase; **parcial**: solo algunas (la frase cruza dos oraciones); **no**: cita otras (oración distractora); **sin citas**: no citó ninguna (lo normal en un Cumple); **n/d**: no se pudo calcular.

| Trampa | Artículo | Corrida | Pérdida | Veredicto | Oraciones de la frase | Oraciones citadas | ¿La frase estaba en lo citado? |
|---|---|---|---|---|---|---|---|
| P1-01-B | NORM_01 6.5 | 32B elegida | perdida en verificación | Cumple | O6 | O7 | no |
| P1-01-B | NORM_01 6.5 | gpt-oss elegida | encontrada | Incumple | O6 | O6, O7 | sí |
| P1-04-M | NORM_04 3.8 | 32B elegida | perdida en verificación | Cumple | O6 | O6 | sí |
| P1-04-M | NORM_04 3.8 | gpt-oss elegida | perdida en clasificación | Incumple | O6 | O4, O6, O8 | sí |
| P1-05-B | NORM_05 4.4 | 32B elegida | perdida en verificación | Cumple | O16 | O16 | sí |
| P1-05-B | NORM_05 4.4 | gpt-oss elegida | encontrada | Incumple | O16 | O15, O16 | sí |
| P2-02-M | NORM_02 2.16 | 32B elegida | perdida en verificación | Cumple | O8 | O8 | sí |
| P2-02-M | NORM_02 2.16 | gpt-oss elegida | perdida en clasificación | Incumple | O8 | O8 | sí |
| P3-01-M | NORM_01 7.3 | 32B elegida | encontrada | Revisar | O12 | O12 | sí |
| P3-01-M | NORM_01 7.3 | gpt-oss elegida | perdida en verificación | No aplica | O12 | O12 | sí |
| P4-01-B | NORM_01 4.1 | 32B elegida | perdida en verificación | Cumple | O15 | O14 | no |
| P4-01-B | NORM_01 4.1 | gpt-oss elegida | otra causa | Incumple | O15 | O14, O15, O17 | sí |
| P4-02-A | NORM_02 4.15 | 32B elegida | perdida en verificación | Cumple | O11 | O12 | no |
| P4-02-A | NORM_02 4.15 | gpt-oss elegida | encontrada | Incumple | O11 | O11, O12 | sí |
| P4-05-M | NORM_05 4.8 | 32B elegida | perdida en verificación | Cumple | O17 | O18 | no |
| P4-05-M | NORM_05 4.8 | gpt-oss elegida | encontrada | Incumple | O17 | O17 | sí |

Cuántas de las perdidas en verificación caen en cada caso:

| Corrida | sí | parcial | no | sin citas | n/d |
|---|---|---|---|---|---|
| 32B elegida | 3 | 0 | 4 | 0 | 0 |
| gpt-oss elegida | 1 | 0 | 0 | 0 | 0 |

### Casos señalados

#### P1-04-M · NORM_04 3.8

Frase de la trampa: «pasadas de acabado de 0,5 mm»

- **32B elegida** (perdida en verificación): frase en O6; citó O6 → **sí**. NORM_04 3.8: Cumple (oraciones O6) — La oferta menciona el uso de material ferroviario real y aplica una profundidad de pasada de 0,5 mm, lo cual cumple con el requisito de usar material real y parámetros de corte aprobados.
- **gpt-oss elegida** (perdida en clasificación): frase en O6; citó O4, O6, O8 → **sí**. NORM_04 3.8: Incumple (oraciones O4, O6, O8) — La oferta no menciona parámetros de corte aprobados, procesamiento en el punto de mayor carga ni comparación con la referencia del fabricante.
  - O4: El plan de pruebas contempla FAT en fábrica, pruebas en vacío en sitio (giro, sentido, lubricación, refrigeración, ejes y lógica de seguridad), SAT bajo carga y prueba de integración con el sistema de gestión de mantenimiento.
  - O6: Para no comprometer la vida útil de las ruedas de la flota, el SAT se ejecutará con 3 pares montados reales provistos por el Comitente, identificados individualmente, aplicando únicamente pasadas de acabado de 0,5 mm de profundidad.
  - O8: Se registrarán la corriente y potencia de los accionamientos, el régimen de los cabezales, el avance, la profundidad de pasada y las alarmas.

#### P4-02-A · NORM_02 4.15

Frase de la trampa: «diferencial general de 300 mA»

- **32B elegida** (perdida en verificación): frase en O11; citó O12 → **no**. NORM_02 4.15: Cumple (oraciones O12) — La oferta especifica una protección diferencial de 30 mA para las tomas de uso general, lo cual cumple con el límite máximo establecido por el artículo.
- **gpt-oss elegida** (encontrada): frase en O11; citó O11, O12 → **sí**. NORM_02 4.15: Incumple (oraciones O11, O12) — Las tomas de mantenimiento solo tienen diferencial de 300 mA, incumpliendo el límite de 30 mA exigido.
  - O11: Las tomas de mantenimiento dentro de la fosa quedarán protegidas por el diferencial general de 300 mA del tablero seccional, evitando disparos por humedad que interrumpen las tareas de limpieza.
  - O12: Las tomas de uso general de la nave conservan su protección diferencial de 30 mA.

#### P4-05-M · NORM_05 4.8

Frase de la trampa: «separados 50 mm»

- **32B elegida** (perdida en verificación): frase en O17; citó O18 → **no**. NORM_05 4.8: Cumple (oraciones O18) — La oferta especifica que las pantallas de los cables de encoder se terminan con abrazadera de 360° en ambos extremos, lo cual cumple con el requisito del artículo.
- **gpt-oss elegida** (encontrada): frase en O17; citó O17 → **sí**. NORM_05 4.8: Incumple (oraciones O17) — La oferta indica una separación de 50 mm, inferior al mínimo de 200 mm exigido por la norma.
  - O17: Los cables de encoder y de motor compartirán bandeja, separados 50 mm mediante precintos, para simplificar el tendido y reducir el número de bandejas en la zona del torno.
  - O18: Las pantallas de los cables de encoder se terminarán con abrazadera de 360° en ambos extremos.

## «Otra causa» en 32B elegida

5 trampas: el artículo llegó al verificador, la verificación dijo Incumple o Revisar y la clasificación no la descartó como CUMPLE/NO_APLICA, pero ninguna brecha cita la frase de la trampa con su artículo.

| Trampa | Artículo | Subcausa | Verificación | Clasificación | Cifras extraídas (si fue vetada por cálculo) | Cita de la brecha del par |
|---|---|---|---|---|---|---|
| P2-03-B | NORM_03 6.2 | vetada por cálculo | NORM_03 6.2: Incumple (oraciones O17, O18) — La oferta garantiza un nivel sonoro ≤ 85 dB(A), pero la medición se realiza a 3 m, no a 1 m como exige el artículo. | — | ofertado 85 / exigido 85 / límite MAXIMO / objeto CUANTITATIVO_TECNICO / brecha relativa 0.0 | El nivel sonoro de la central hidráulica se verificará en comisionamiento a 3 m del equipo, garantizándose un valor ≤ 85 dB(A). La central se suministra con capota acústica y bomba de bajo nivel sono… [descartada por cálculo] |
| P3-01-A | NORM_01 6.1 | vetada por cálculo | NORM_01 6.1: Incumple (oraciones O8, O9) — La excavación tiene 2,10 m de profundidad, por lo que según el artículo 6.1, requiere un sistema de contención lateral metálico calculado, lo cual no se cumple al usar taludes naturales. | — | ofertado 2,10 / exigido 1,20 / límite MINIMO / objeto CUANTITATIVO_TECNICO / brecha relativa 0.0 | La excavación para el bloque de fundación (2,10 m de profundidad bajo NPT, planta de 5,2 × 4,6 m) se ejecutará con taludes naturales 1:0,5, dada la buena cohesión del suelo observada en el sitio y en… [descartada por cálculo] |
| P3-04-B | NORM_04 3.10 | descartada por regla 2.5 | NORM_04 3.10: Incumple (oraciones O9, O10) — La oferta especifica Ra ≤ 3,2 μm, pero no menciona que se realicen al menos tres trazas distribuidas a 120 grados ni que el límite esté definido en la ficha de aceptación del proyecto. | INFORMACION_FALTANTE (regla 2.5) — La oferta describe la actividad de verificación de rugosidad superficial, pero omite declarar que se realicen al menos tres trazas distribuidas a 120 grados y que el límite de rugosidad esté definido en la ficha de aceptación del proyecto, datos exigibles según el… | — | — |
| P4-03-B | NORM_03 3.6 | descartada por regla 2.5 | NORM_03 3.6: Incumple (oraciones O9, O10) — La oferta menciona verificación diaria, pero no menciona inspección trimestral por personal especializado, que es un requisito del artículo. | INFORMACION_FALTANTE (regla 2.5) — La oferta menciona verificación diaria, pero no menciona inspección trimestral por personal especializado, que es un requisito del artículo. [Art. 2.5: no es un ítem del Art. 2.6] | — | — |
| P4-05-A | NORM_05 3.9 | descartada por regla 2.5 | NORM_05 3.9: Revisar (oraciones O4) — La oferta menciona la eliminación de trazas de condensado, pero no especifica cómo se mide ni si cumple con los límites de humedad establecidos por la norma. | INFORMACION_FALTANTE (regla 2.5) — La oferta menciona la eliminación de trazas de condensado, pero no especifica cómo se mide ni si cumple con los límites de humedad establecidos por la norma. [Art. 2.5: no es un ítem del Art. 2.6] | — | — |

## «Otra causa» en gpt-oss elegida

2 trampas: el artículo llegó al verificador, la verificación dijo Incumple o Revisar y la clasificación no la descartó como CUMPLE/NO_APLICA, pero ninguna brecha cita la frase de la trampa con su artículo.

| Trampa | Artículo | Subcausa | Verificación | Clasificación | Cifras extraídas (si fue vetada por cálculo) | Cita de la brecha del par |
|---|---|---|---|---|---|---|
| P1-02-B | NORM_02 5.16 | descartada por regla 2.5 | NORM_02 5.16: Incumple (oraciones O4) — El protocolo presentado tiene fecha de marzo 2025, por lo que supera la vigencia de 12 meses requerida. | INFORMACION_FALTANTE (regla 2.5) — Falta de datos requeridos en el protocolo de puesta a tierra según NORM_02 Art. 5.16 [Art. 2.5: no es un ítem del Art. 2.6] | — | — |
| P4-01-B | NORM_01 4.1 | descartada por regla 2.5 | NORM_01 4.1: Incumple (oraciones O14, O15, O17) — Falta mencionar cumplimiento del CIRSOC 200-2024, requisito explícito del artículo. | INFORMACION_FALTANTE (regla 2.5) — Falta de información requerida por el artículo NORM_01 Art. 4.1 para demostrar cumplimiento del curado continuo según CIRSOC 200-2024 y registro de temperatura, humedad e interrupciones durante los 28 días de curado. [Art. 2.5: no es un ítem del Art. 2.6] | — | — |

## Trampa por trampa

| Trampa | Artículo | Pérdida en 32B elegida | Pérdida en gpt-oss elegida | Frase en lo que citó el verificador (32B elegida → gpt-oss elegida; solo si se perdió en verificación) | Veredicto del verificador (32B elegida → gpt-oss elegida) | Explicación del verificador (donde cambia) |
|---|---|---|---|---|---|---|
| P1-01-A | NORM_01 4.2 | encontrada | encontrada |  |  |  |
| P1-01-M | NORM_01 6.3 | encontrada | encontrada |  |  |  |
| P1-01-B | NORM_01 6.5 | perdida en verificación | encontrada **(cambia)** | no → sí | Cumple → Incumple | **gpt-oss elegida:** NORM_01 6.5: Incumple (oraciones O6, O7) — La oferta no menciona aditivo cristalino, waterstops ni el ensayo de penetración ≤30 mm requerido<br>**32B elegida:** NORM_01 6.5: Cumple (oraciones O7) — La oferta menciona banda hidroexpansiva y sellador poliuretánico, lo cual puede considerarse un sistema equivalente a las bandas hidrófilas o waterstops mencionados en el artículo. |
| P1-02-A | NORM_02 5.4 | encontrada | encontrada |  |  |  |
| P1-02-M | NORM_02 4.5 | encontrada | encontrada |  |  |  |
| P1-02-B | NORM_02 5.16 | encontrada | otra causa (descartada por regla 2.5) **(cambia)** |  | Incumple → Incumple | **gpt-oss elegida:** NORM_02 5.16: Incumple (oraciones O4) — El protocolo presentado tiene fecha de marzo 2025, por lo que supera la vigencia de 12 meses requerida.<br>**32B elegida:** NORM_02 5.16: Incumple (oraciones O4) — El protocolo se realizó en marzo de 2025, pero la fecha de análisis es noviembre de 2026, por lo que el protocolo ha vencido. |
| P1-03-A | NORM_03 2.2 | encontrada | encontrada |  |  |  |
| P1-03-M | NORM_03 2.6 | encontrada | encontrada |  |  |  |
| P1-03-B | NORM_03 5.1 | encontrada | encontrada |  |  |  |
| P1-04-A | NORM_04 2.3 | encontrada | encontrada |  |  |  |
| P1-04-M | NORM_04 3.8 | perdida en verificación | perdida en clasificación **(cambia)** | sí → sí | Cumple → Incumple | **gpt-oss elegida:** NORM_04 3.8: Incumple (oraciones O4, O6, O8) — La oferta no menciona parámetros de corte aprobados, procesamiento en el punto de mayor carga ni comparación con la referencia del fabricante.<br>**32B elegida:** NORM_04 3.8: Cumple (oraciones O6) — La oferta menciona el uso de material ferroviario real y aplica una profundidad de pasada de 0,5 mm, lo cual cumple con el requisito de usar material real y parámetros de corte aprobados. |
| P1-04-B | NORM_04 2.5 | encontrada | encontrada |  |  |  |
| P1-05-A | NORM_05 3.4 | encontrada | encontrada |  |  |  |
| P1-05-M | NORM_05 2.1 | encontrada | encontrada |  |  |  |
| P1-05-B | NORM_05 4.4 | perdida en verificación | encontrada **(cambia)** | sí → sí | Cumple → Incumple | **gpt-oss elegida:** NORM_05 4.4: Incumple (oraciones O15, O16) — El plan de calibración bienal supera el intervalo máximo de 12 meses exigido por la norma.<br>**32B elegida:** NORM_05 4.4: Cumple (oraciones O16) — La oferta menciona que las llaves dinamométricas tienen calibración vigente según ISO 6789-2, lo cual cumple con el requisito normativo. |
| P2-01-A | NORM_01 5.2 | encontrada | encontrada |  |  |  |
| P2-01-M | NORM_01 3.2 | encontrada | encontrada |  |  |  |
| P2-01-B | NORM_01 3.7 | encontrada | encontrada |  |  |  |
| P2-02-A | NORM_02 3.13 | encontrada | perdida en clasificación **(cambia)** |  | Revisar → Revisar | **gpt-oss elegida:** NORM_02 3.13: Revisar (oraciones O10) — La oferta menciona un interruptor de 25 kA pero no incluye el estudio de cortocircuito necesario para validar su idoneidad.<br>**32B elegida:** NORM_02 3.13: Revisar (oraciones O10) — El artículo establece que un interruptor de 25 kA es inadmisible si el estudio indica 25,1 kA o más, pero la oferta no menciona el resultado del estudio de Icu/Icn/Icc. |
| P2-02-M | NORM_02 2.16 | perdida en verificación | perdida en clasificación **(cambia)** | sí → sí | Cumple → Incumple | **gpt-oss elegida:** NORM_02 2.16: Incumple (oraciones O8) — La caída indicada (4,2 %) supera el límite del 3 % para el tramo terminal de fuerza motriz pesada.<br>**32B elegida:** NORM_02 2.16: Cumple (oraciones O8) — La caída de tensión del alimentador es del 4,2 %, que es menor al límite del 5 % establecido por la norma. |
| P2-02-B | NORM_02 4.7 | encontrada | encontrada |  |  |  |
| P2-03-A | NORM_03 2.8 | encontrada | encontrada |  |  |  |
| P2-03-M | NORM_03 2.4 | encontrada | encontrada |  |  |  |
| P2-03-B | NORM_03 6.2 | otra causa (vetada por cálculo) | encontrada **(cambia)** |  | Incumple → Incumple | **gpt-oss elegida:** NORM_03 6.2: Incumple (oraciones O17) — La oferta mide el nivel a 3 m, no a 1 m requerido, y no describe la documentación exigida.<br>**32B elegida:** NORM_03 6.2: Incumple (oraciones O17, O18) — La oferta garantiza un nivel sonoro ≤ 85 dB(A), pero la medición se realiza a 3 m, no a 1 m como exige el artículo. |
| P2-04-A | NORM_04 3.2 | encontrada | encontrada |  |  |  |
| P2-04-M | NORM_04 2.6 | encontrada | encontrada |  |  |  |
| P2-04-B | NORM_04 2.13 | no recuperada | no recuperada |  |  |  |
| P2-05-A | NORM_05 1.8 | no recuperada | no recuperada |  |  |  |
| P2-05-M | NORM_05 3.5 | encontrada | encontrada |  |  |  |
| P2-05-B | NORM_05 3.8 | encontrada | encontrada |  |  |  |
| P3-01-A | NORM_01 6.1 | otra causa (vetada por cálculo) | encontrada **(cambia)** |  | Incumple → Incumple | **gpt-oss elegida:** NORM_01 6.1: Incumple (oraciones O8, O9) — La oferta ejecuta una excavación de 2,10 m sin entibado metálico, incumpliendo la exigencia de contención lateral para profundidades superiores a 1,20 m<br>**32B elegida:** NORM_01 6.1: Incumple (oraciones O8, O9) — La excavación tiene 2,10 m de profundidad, por lo que según el artículo 6.1, requiere un sistema de contención lateral metálico calculado, lo cual no se cumple al usar taludes naturales. |
| P3-01-M | NORM_01 7.3 | encontrada | perdida en verificación **(cambia)** | sí → sí | Revisar → No aplica | **gpt-oss elegida:** NORM_01 7.3: No aplica (oraciones O12) — La oferta indica la masa del bloque pero no la masa operativa de la máquina ni la relación requerida.<br>**32B elegida:** NORM_01 7.3: Revisar (oraciones O12) — La oferta menciona una masa de inercia de 45 t, pero no se proporciona la masa operativa de la máquina para verificar si la relación Mf/Mm está entre 2 y 3. |
| P3-01-B | NORM_01 8.2 | encontrada | encontrada |  |  |  |
| P3-02-A | NORM_02 5.14 | no recuperada | no recuperada |  |  |  |
| P3-02-M | NORM_02 5.5 | encontrada | encontrada |  |  |  |
| P3-02-B | NORM_02 1.11 | encontrada | encontrada |  |  |  |
| P3-03-A | NORM_03 4.7 | encontrada | encontrada |  |  |  |
| P3-03-M | NORM_03 5.5 | encontrada | encontrada |  |  |  |
| P3-03-B | NORM_03 5.2 | encontrada | encontrada |  |  |  |
| P3-04-A | NORM_04 3.6 | encontrada | encontrada |  |  |  |
| P3-04-M | NORM_04 1.6 | encontrada | encontrada |  |  |  |
| P3-04-B | NORM_04 3.10 | otra causa (descartada por regla 2.5) | encontrada **(cambia)** |  | Incumple → Incumple | **gpt-oss elegida:** NORM_04 3.10: Incumple (oraciones O9, O10) — La oferta solo contempla una traza por rueda, mientras la norma exige al menos tres trazas distribuidas a 120°<br>**32B elegida:** NORM_04 3.10: Incumple (oraciones O9, O10) — La oferta especifica Ra ≤ 3,2 μm, pero no menciona que se realicen al menos tres trazas distribuidas a 120 grados ni que el límite esté definido en la ficha de aceptación del proyecto. |
| P3-05-A | NORM_05 4.3 | no recuperada | no recuperada |  |  |  |
| P3-05-M | NORM_05 2.9 | no recuperada | no recuperada |  |  |  |
| P3-05-B | NORM_05 2.3 | no recuperada | no recuperada |  |  |  |
| P4-01-A | NORM_01 3.1 | encontrada | encontrada |  |  |  |
| P4-01-M | NORM_01 3.5 | encontrada | encontrada |  |  |  |
| P4-01-B | NORM_01 4.1 | perdida en verificación | otra causa (descartada por regla 2.5) **(cambia)** | no → sí | Cumple → Incumple | **gpt-oss elegida:** NORM_01 4.1: Incumple (oraciones O14, O15, O17) — Falta mencionar cumplimiento del CIRSOC 200-2024, requisito explícito del artículo.<br>**32B elegida:** NORM_01 4.1: Cumple (oraciones O14) — La oferta menciona un curado con mantas húmedas durante 28 días corridos antes del posicionamiento del torno, lo cual cumple con el requisito normativo. |
| P4-02-A | NORM_02 4.15 | perdida en verificación | encontrada **(cambia)** | no → sí | Cumple → Incumple | **gpt-oss elegida:** NORM_02 4.15: Incumple (oraciones O11, O12) — Las tomas de mantenimiento solo tienen diferencial de 300 mA, incumpliendo el límite de 30 mA exigido.<br>**32B elegida:** NORM_02 4.15: Cumple (oraciones O12) — La oferta especifica una protección diferencial de 30 mA para las tomas de uso general, lo cual cumple con el límite máximo establecido por el artículo. |
| P4-02-M | NORM_02 1.10 | encontrada | encontrada |  |  |  |
| P4-02-B | NORM_02 4.10 | encontrada | encontrada |  |  |  |
| P4-03-A | NORM_03 3.4 | encontrada | encontrada |  |  |  |
| P4-03-M | NORM_03 4.2 | encontrada | encontrada |  |  |  |
| P4-03-B | NORM_03 3.6 | otra causa (descartada por regla 2.5) | encontrada **(cambia)** |  | Incumple → Incumple | **gpt-oss elegida:** NORM_03 3.6: Incumple (oraciones O9, O10) — La oferta propone inspección anual, mientras la norma exige inspección trimestral y documentación completa, por lo que no cumple.<br>**32B elegida:** NORM_03 3.6: Incumple (oraciones O9, O10) — La oferta menciona verificación diaria, pero no menciona inspección trimestral por personal especializado, que es un requisito del artículo. |
| P4-04-A | NORM_04 1.10 | encontrada | encontrada |  |  |  |
| P4-04-M | NORM_04 3.20 | encontrada | perdida en clasificación **(cambia)** |  | Incumple → Incumple | **gpt-oss elegida:** NORM_04 3.20: Incumple (oraciones O4, O10) — La oferta no menciona la supervisión conjunta ni la participación del responsable de Prevención ni la firma del receptor técnico requerida por la norma.<br>**32B elegida:** NORM_04 3.20: Incumple (oraciones O4, O10) — La oferta menciona la ejecución del SAT con ejes aprobados por el Comitente y la firma del acta por el Jefe de Puesta en Marcha, pero no especifica la supervisión conjunta requerida por el artículo ni la participación del responsable de Prevención ni la firma del receptor técnico. |
| P4-04-B | NORM_04 3.12 | encontrada | encontrada |  |  |  |
| P4-05-A | NORM_05 3.9 | otra causa (descartada por regla 2.5) | encontrada **(cambia)** |  | Revisar → Incumple | **gpt-oss elegida:** NORM_05 3.9: Incumple (oraciones O4) — La oferta no indica método ni límite de medición de humedad del aceite, requisito exigido por la norma.<br>**32B elegida:** NORM_05 3.9: Revisar (oraciones O4) — La oferta menciona la eliminación de trazas de condensado, pero no especifica cómo se mide ni si cumple con los límites de humedad establecidos por la norma. |
| P4-05-M | NORM_05 4.8 | perdida en verificación | encontrada **(cambia)** | no → sí | Cumple → Incumple | **gpt-oss elegida:** NORM_05 4.8: Incumple (oraciones O17) — La oferta indica una separación de 50 mm, inferior al mínimo de 200 mm exigido por la norma.<br>**32B elegida:** NORM_05 4.8: Cumple (oraciones O18) — La oferta especifica que las pantallas de los cables de encoder se terminan con abrazadera de 360° en ambos extremos, lo cual cumple con el requisito del artículo. |
| P4-05-B | NORM_05 4.5 | encontrada | encontrada |  |  |  |

