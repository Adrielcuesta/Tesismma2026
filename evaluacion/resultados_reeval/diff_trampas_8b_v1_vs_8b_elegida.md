# Diferencia trampa por trampa: 8B v1 contra 8B elegida

- 8B v1: qwen3:8b local
- 8B elegida: qwen3:8b local (elegida)

Categorías de pérdida de evaluar.py: **encontrada** (brecha con la frase y el artículo); **no recuperada** (el artículo no llegó al verificador); **perdida en verificación** (llegó y se dijo Cumple o No aplica); **perdida en clasificación** (se dijo Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE); **otra causa** (verificada como Incumple o Revisar y clasificada como riesgo, pero ninguna brecha cita la frase de la trampa con su artículo), desglosada en subcausas.

## Parámetros de cada corrida

| Parámetro | 8B v1 | 8B elegida |
|---|---|---|
| Corrida | qwen3:8b local | qwen3:8b local (elegida) |
| Modelo | qwen3:8b | qwen3:8b |
| Temperatura | 0 | 0 |
| Semilla | 42 | 42 |
| Razonamiento en la verificación | False | False |
| Esfuerzo de razonamiento (modelos con razonamiento fijo) | no guardada | no guardada |
| Temperatura con razonamiento | N/A | N/A |
| top_p con razonamiento | N/A | N/A |
| top_k con razonamiento | N/A | N/A |
| Embeddings de la recuperación | no guardada | bge-m3 |
| Perfil de recuperación | no guardada | elegido |
| Numeración de oraciones igual a la actual (oraciones citadas por brechas) | 1095/1095 | 1406/1406 |

La temperatura y la semilla que se guardan son las que se configuraron en el cliente (`temperature` y `seed` de configuracion_analisis); el JSON no dice si el proveedor de la API las aplicó (las corridas en la nube las mandan con la semilla de config.OLLAMA_SEED).

## Resumen por conjunto

Techo del sistema = trampas − no recuperadas − vetadas por cálculo − descartadas por regla 2.5: lo máximo que lograría un verificador perfecto con esa recuperación (el recall estricto no puede pasarlo).

| Conjunto | Trampas | Recall estricto (8B v1 → 8B elegida) | Techo del sistema (8B v1 → 8B elegida) | Llegan al verificador (8B v1 → 8B elegida) | No recuperadas | Vetadas por cálculo | Descartadas por regla 2.5 | Perdida en verificación | Perdida en clasificación | Otra causa (total) |
|---|---|---|---|---|---|---|---|---|---|---|
| P1–P2 desarrollo | 30 | 19 → 23 | 24 → 28 | 24 → 28 | 6 → 2 | 0 → 0 | 0 → 0 | 4 → 4 | 0 → 0 | 1 → 1 |
| P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1) | 30 | 19 → 19 | 24 → 24 | 25 → 26 | 5 → 4 | 1 → 1 | 0 → 1 | 4 → 4 | 0 → 0 | 2 → 3 |
| P1–P4 total | 60 | 38 → 42 | 48 → 52 | 49 → 54 | 11 → 6 | 1 → 1 | 0 → 1 | 8 → 8 | 0 → 0 | 3 → 4 |

## «Otra causa» por subcausa

Desglose informativo (evaluar.subcausa_otra_causa); no cambia la definición de «encontrada» ni del recall estricto.

| Subcausa | 8B v1 | 8B elegida |
|---|---|---|
| vetada por cálculo | 1 | 1 |
| descartada por regla 2.5 | 0 | 1 |
| descartada por regla 2.7.c | 0 | 0 |
| cita otro artículo | 2 | 2 |
| salió como alerta | 0 | 0 |
| otra | 0 | 0 |

## Transiciones de pérdida (8B v1 → 8B elegida)

Primero las que cambian, después las que quedan igual.

| 8B v1 | 8B elegida | Total | P1–P2 desarrollo | P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1) | P1–P4 total | Trampas |
|---|---|---|---|---|---|---|
| perdida en verificación | otra causa | 1 | 0 | 1 | 1 | P3-03-M |
| no recuperada | encontrada | 4 | 4 | 0 | 4 | P1-04-B, P1-05-M, P2-01-M, P2-01-B |
| no recuperada | perdida en verificación | 1 | 0 | 1 | 1 | P4-05-A |
| encontrada | encontrada (igual) | 38 | 19 | 19 | 38 | P1-01-A, P1-01-M, P1-02-A, P1-02-M, P1-03-A, P1-03-M, P1-03-B, P1-04-A, P1-04-M, P1-05-A, P2-01-A, P2-02-A, P2-02-B, P2-03-A, P2-03-M, P2-04-A, P2-04-M, P2-05-M, P2-05-B, P3-01-M, P3-01-B, P3-02-M, P3-02-B, P3-03-A, P3-04-A, P3-04-M, P3-04-B, P4-01-A, P4-01-M, P4-01-B, P4-02-A, P4-02-B, P4-03-A, P4-03-M, P4-04-A, P4-04-B, P4-05-M, P4-05-B |
| perdida en verificación | perdida en verificación (igual) | 7 | 4 | 3 | 7 | P1-02-B, P1-05-B, P2-02-M, P2-03-B, P4-02-M, P4-03-B, P4-04-M |
| no recuperada | no recuperada (igual) | 6 | 2 | 4 | 6 | P2-04-B, P2-05-A, P3-02-A, P3-05-A, P3-05-M, P3-05-B |
| otra causa | otra causa (igual) | 3 | 1 | 2 | 3 | P1-01-B, P3-01-A, P3-03-B |

## Trampas ganadas y perdidas (recall estricto)

Ganadas en 8B elegida: 4. Perdidas en 8B elegida: 0. Neto: +4.

### Ganadas (no encontradas en 8B v1, encontradas en 8B elegida)

| Trampa | Artículo | Pérdida en la otra corrida | Veredicto del verificador (8B v1 → 8B elegida) |
|---|---|---|---|
| P1-04-B | NORM_04 2.5 | no recuperada | — → Incumple |
| P1-05-M | NORM_05 2.1 | no recuperada | — → Incumple |
| P2-01-M | NORM_01 3.2 | no recuperada | — → Incumple |
| P2-01-B | NORM_01 3.7 | no recuperada | — → Incumple |

### Perdidas (encontradas en 8B v1, no encontradas en 8B elegida)

Ninguna.

## Perdidas en verificación: ¿la frase estaba en lo que citó el verificador?

El verificador recibe la **sección entera** numerada (`seccion_numerada`), así que la frase de la trampa siempre estaba en el prompt salvo que la segmentación la corte en dos oraciones. Lo que el JSON permite separar es otra cosa: si el modelo **citó** las oraciones de la frase. **sí**: cita todas las oraciones que ocupa la frase; **parcial**: solo algunas (la frase cruza dos oraciones); **no**: cita otras (oración distractora); **sin citas**: no citó ninguna (lo normal en un Cumple); **n/d**: no se pudo calcular.

| Trampa | Artículo | Corrida | Pérdida | Veredicto | Oraciones de la frase | Oraciones citadas | ¿La frase estaba en lo citado? |
|---|---|---|---|---|---|---|---|
| P1-02-B | NORM_02 5.16 | 8B v1 | perdida en verificación | Cumple | O4 | O4 | sí |
| P1-02-B | NORM_02 5.16 | 8B elegida | perdida en verificación | Cumple | O4 | O4 | sí |
| P1-05-B | NORM_05 4.4 | 8B v1 | perdida en verificación | Cumple | O16 | O15, O16 | sí |
| P1-05-B | NORM_05 4.4 | 8B elegida | perdida en verificación | Cumple | O16 | O15, O16 | sí |
| P2-02-M | NORM_02 2.16 | 8B v1 | perdida en verificación | Cumple | O8 | O8 | sí |
| P2-02-M | NORM_02 2.16 | 8B elegida | perdida en verificación | Cumple | O8 | O8 | sí |
| P2-03-B | NORM_03 6.2 | 8B v1 | perdida en verificación | Cumple | O17 | O17 | sí |
| P2-03-B | NORM_03 6.2 | 8B elegida | perdida en verificación | Cumple | O17 | O17 | sí |
| P3-03-M | NORM_03 5.5 | 8B v1 | perdida en verificación | Cumple | O14 | O14, O15 | sí |
| P3-03-M | NORM_03 5.5 | 8B elegida | otra causa | Incumple | O14 | O14, O15 | sí |
| P4-02-M | NORM_02 1.10 | 8B v1 | perdida en verificación | Cumple | O4 | O1, O4 | sí |
| P4-02-M | NORM_02 1.10 | 8B elegida | perdida en verificación | Cumple | O4 | O1, O4 | sí |
| P4-03-B | NORM_03 3.6 | 8B v1 | perdida en verificación | Cumple | O10 | O9, O10 | sí |
| P4-03-B | NORM_03 3.6 | 8B elegida | perdida en verificación | Cumple | O10 | O9, O10 | sí |
| P4-04-M | NORM_04 3.20 | 8B v1 | perdida en verificación | No aplica | O10 | O4, O5, O6, O7, O8, O9, O10, O11 | sí |
| P4-04-M | NORM_04 3.20 | 8B elegida | perdida en verificación | No aplica | O10 | O4, O5, O6, O7, O8, O9, O10, O11 | sí |
| P4-05-A | NORM_05 3.9 | 8B v1 | no recuperada | — | O4 | — | sin citas |
| P4-05-A | NORM_05 3.9 | 8B elegida | perdida en verificación | No aplica | O4 | O2, O3, O4, O8, O10 | sí |

Cuántas de las perdidas en verificación caen en cada caso:

| Corrida | sí | parcial | no | sin citas | n/d |
|---|---|---|---|---|---|
| 8B v1 | 8 | 0 | 0 | 0 | 0 |
| 8B elegida | 8 | 0 | 0 | 0 | 0 |

### Casos señalados

#### P1-04-M · NORM_04 3.8

Frase de la trampa: «pasadas de acabado de 0,5 mm»

- **8B v1** (encontrada): frase en O6; citó O4, O5, O6, O7, O8, O9, O10, O11, O12, O13 → **sí**. NORM_04 3.8: Incumple (oraciones O4, O5, O6, O7, O8, O9, O10, O11, O12, O13) — La oferta menciona el uso de pasadas de acabado de 0,5 mm de profundidad, pero el artículo exige que el SAT se ejecute bajo carga, lo cual no se cumple en la oferta.
- **8B elegida** (encontrada): frase en O6; citó O4, O5, O6, O7, O8, O9, O10, O11, O12, O13 → **sí**. NORM_04 3.8: Incumple (oraciones O4, O5, O6, O7, O8, O9, O10, O11, O12, O13) — La oferta menciona una profundidad de pasada de 0,5 mm, pero el artículo prohíbe realizar SAT bajo carga si la prueba se limita a girar el componente sin mecanizado o sin solicitar la carga de trabajo definida en el plan de pruebas.
  - O4: El plan de pruebas contempla FAT en fábrica, pruebas en vacío en sitio (giro, sentido, lubricación, refrigeración, ejes y lógica de seguridad), SAT bajo carga y prueba de integración con el sistema de gestión de mantenimiento.
  - O5: La recepción provisoria se otorgará únicamente después de aprobado el SAT bajo carga y cerradas las no conformidades bloqueantes. 7.2 SAT bajo carga
  - O6: Para no comprometer la vida útil de las ruedas de la flota, el SAT se ejecutará con 3 pares montados reales provistos por el Comitente, identificados individualmente, aplicando únicamente pasadas de acabado de 0,5 mm de profundidad.
  - O7: Esta estrategia permite demostrar la precisión del perfil sin consumir material útil de rodadura.
  - O8: Se registrarán la corriente y potencia de los accionamientos, el régimen de los cabezales, el avance, la profundidad de pasada y las alarmas.
  - O9: 7.3 Mediciones Verificación Criterio Perfil de rueda
  - O10: Desviación ≤ 0,2 mm respecto del perfil teórico Diferencia de diámetros en un mismo eje ≤ 0,2 mm Rugosidad superficial
  - O11: Ra ≤ 6,3 μm; 3 trazas por rueda distribuidas a 120° Temperatura de rodamientos Registro automático con muestreo cada 30 s; estabilidad con 3 lecturas a intervalos de 5 min y variación ≤ 2 K Vibración de cabezales
  - O12: ISO 20816-3, Grupo 2, soporte rígido, zona A/B (≤ 1,4 mm/s RMS) 7.4 Supervisión y actas El SAT se ejecutará bajo supervisión conjunta del proveedor, Ingeniería/Infraestructura, Material Rodante, Operaciones y Calidad.
  - O13: Las mediciones críticas de perfil serán presenciadas por el responsable de Material Rodante, quien firmará el acta SAT como receptor técnico.

#### P4-02-A · NORM_02 4.15

Frase de la trampa: «diferencial general de 300 mA»

- **8B v1** (encontrada): frase en O11; citó O11, O12 → **sí**. NORM_02 4.15: Incumple (oraciones O11, O12) — La oferta utiliza un diferencial de 300 mA para tomas de mantenimiento, mientras que la norma exige un diferencial de 30 mA para esa protección.
- **8B elegida** (encontrada): frase en O11; citó O11, O12 → **sí**. NORM_02 4.15: Incumple (oraciones O11, O12) — La oferta utiliza un diferencial de 300 mA para tomas de mantenimiento, mientras que la norma exige un diferencial de 30 mA para esa protección.
  - O11: Las tomas de mantenimiento dentro de la fosa quedarán protegidas por el diferencial general de 300 mA del tablero seccional, evitando disparos por humedad que interrumpen las tareas de limpieza.
  - O12: Las tomas de uso general de la nave conservan su protección diferencial de 30 mA.

#### P4-05-M · NORM_05 4.8

Frase de la trampa: «separados 50 mm»

- **8B v1** (encontrada): frase en O17; citó O17, O18, O19 → **sí**. NORM_05 4.8: Incumple (oraciones O17, O18, O19) — La oferta no cumple con la separación mínima de 200 mm requerida para cables de potencia y señal en bandeja independiente.
- **8B elegida** (encontrada): frase en O17; citó O17, O18, O19 → **sí**. NORM_05 4.8: Incumple (oraciones O17, O18, O19) — La oferta menciona una separación de 50 mm entre cables de encoder y motor, mientras que el artículo exige una separación mínima de 200 mm cuando exista recorrido paralelo en bandeja independiente.
  - O17: Los cables de encoder y de motor compartirán bandeja, separados 50 mm mediante precintos, para simplificar el tendido y reducir el número de bandejas en la zona del torno.
  - O18: Las pantallas de los cables de encoder se terminarán con abrazadera de 360° en ambos extremos.
  - O19: El nuevo tendido de bandejas portacables se montará a 0,50 m del recorrido del carro del puente grúa, aprovechando el espacio disponible bajo la cubierta.

## «Otra causa» en 8B v1

3 trampas: el artículo llegó al verificador, la verificación dijo Incumple o Revisar y la clasificación no la descartó como CUMPLE/NO_APLICA, pero ninguna brecha cita la frase de la trampa con su artículo.

| Trampa | Artículo | Subcausa | Verificación | Clasificación | Cifras extraídas (si fue vetada por cálculo) | Cita de la brecha del par |
|---|---|---|---|---|---|---|
| P1-01-B | NORM_01 6.5 | cita otro artículo | NORM_01 6.5: Incumple (oraciones O7) — La oferta menciona banda hidroexpansiva, mientras que el artículo exige bandas hidrófilas, waterstops o sistemas equivalentes, lo cual no se cumple. | — | — | Las juntas llevarán banda hidroexpansiva y sellador poliuretánico. |
| P3-01-A | NORM_01 6.1 | vetada por cálculo | NORM_01 6.1: Incumple (oraciones O8, O9, O10) — La oferta no incluye sistema de contención lateral metálico calculado para excavación de 2,10 m de profundidad, lo cual incumple el artículo. | — | ofertado 2,10 / exigido 1,20 / límite MINIMO / objeto CUANTITATIVO_TECNICO / brecha relativa 0.0 | La excavación para el bloque de fundación (2,10 m de profundidad bajo NPT, planta de 5,2 × 4,6 m) se ejecutará con taludes naturales 1:0,5, dada la buena cohesión del suelo observada en el sitio y en… [descartada por cálculo] |
| P3-03-B | NORM_03 5.2 | cita otro artículo | NORM_03 5.2: Incumple (oraciones O8) — La oferta menciona la firma del Ingeniero Mecánico, pero no incluye la revisión por parte del Departamento de Higiene y Seguridad ni la presentación del expediente a la ART. | — | — | Las tres maniobras se clasifican como izaje crítico por tratarse de equipo de precisión de alto valor; el travesaño, además, supera 10 t y el 80 % de capacidad, y la bancada supera 10 t. El Plan de I… |

## «Otra causa» en 8B elegida

4 trampas: el artículo llegó al verificador, la verificación dijo Incumple o Revisar y la clasificación no la descartó como CUMPLE/NO_APLICA, pero ninguna brecha cita la frase de la trampa con su artículo.

| Trampa | Artículo | Subcausa | Verificación | Clasificación | Cifras extraídas (si fue vetada por cálculo) | Cita de la brecha del par |
|---|---|---|---|---|---|---|
| P1-01-B | NORM_01 6.5 | cita otro artículo | NORM_01 6.5: Incumple (oraciones O7) — La oferta menciona banda hidroexpansiva, mientras que el artículo exige bandas hidrófilas, waterstops o sistemas equivalentes, lo cual no se cumple. | — | — | Las juntas llevarán banda hidroexpansiva y sellador poliuretánico. |
| P3-01-A | NORM_01 6.1 | vetada por cálculo | NORM_01 6.1: Incumple (oraciones O8, O9, O10) — La oferta no incluye sistema de contención lateral metálico calculado para excavación de 2,10 m de profundidad, lo cual incumple el artículo. | — | ofertado 2,10 / exigido 1,20 / límite MINIMO / objeto CUANTITATIVO_TECNICO / brecha relativa 0.0 | La excavación para el bloque de fundación (2,10 m de profundidad bajo NPT, planta de 5,2 × 4,6 m) se ejecutará con taludes naturales 1:0,5, dada la buena cohesión del suelo observada en el sitio y en… [descartada por cálculo] |
| P3-03-M | NORM_03 5.5 | descartada por regla 2.5 | NORM_03 5.5: Incumple (oraciones O14, O15) — La oferta menciona la presencia del Responsable de Higiene y Seguridad y del Supervisor de Montaje, pero no garantiza la presencia física continua e ininterrumpida, ni la ubicación dentro del área operativa segura. | INFORMACION_FALTANTE (regla 2.5) — La oferta no garantiza la presencia física continua e ininterrumpida del Responsable de Higiene y Seguridad ni su ubicación dentro del área operativa segura, según el artículo NORM_03, Art. 5.5. [Art. 2.5: no es un ítem del Art. 2.6] | — | — |
| P3-03-B | NORM_03 5.2 | cita otro artículo | NORM_03 5.2: Incumple (oraciones O8) — La oferta menciona la firma del Ingeniero Mecánico, pero no incluye la revisión por parte del Departamento de Higiene y Seguridad ni la presentación del expediente a la ART. | — | — | Las tres maniobras se clasifican como izaje crítico por tratarse de equipo de precisión de alto valor; el travesaño, además, supera 10 t y el 80 % de capacidad, y la bancada supera 10 t. El Plan de I… |

## Trampa por trampa

| Trampa | Artículo | Pérdida en 8B v1 | Pérdida en 8B elegida | Frase en lo que citó el verificador (8B v1 → 8B elegida; solo si se perdió en verificación) | Veredicto del verificador (8B v1 → 8B elegida) | Explicación del verificador (donde cambia) |
|---|---|---|---|---|---|---|
| P1-01-A | NORM_01 4.2 | encontrada | encontrada |  |  |  |
| P1-01-M | NORM_01 6.3 | encontrada | encontrada |  |  |  |
| P1-01-B | NORM_01 6.5 | otra causa (cita otro artículo) | otra causa (cita otro artículo) |  |  |  |
| P1-02-A | NORM_02 5.4 | encontrada | encontrada |  |  |  |
| P1-02-M | NORM_02 4.5 | encontrada | encontrada |  |  |  |
| P1-02-B | NORM_02 5.16 | perdida en verificación | perdida en verificación | sí → sí |  |  |
| P1-03-A | NORM_03 2.2 | encontrada | encontrada |  |  |  |
| P1-03-M | NORM_03 2.6 | encontrada | encontrada |  |  |  |
| P1-03-B | NORM_03 5.1 | encontrada | encontrada |  |  |  |
| P1-04-A | NORM_04 2.3 | encontrada | encontrada |  |  |  |
| P1-04-M | NORM_04 3.8 | encontrada | encontrada |  |  |  |
| P1-04-B | NORM_04 2.5 | no recuperada | encontrada **(cambia)** |  | — → Incumple | **8B elegida:** NORM_04 2.5: Incumple (oraciones O12) — La oferta indica una separación de 1,0 m entre secciones, mientras que la norma exige una separación máxima de 0,50 m.<br>**8B v1:** no llegó al verificador |
| P1-05-A | NORM_05 3.4 | encontrada | encontrada |  |  |  |
| P1-05-M | NORM_05 2.1 | no recuperada | encontrada **(cambia)** |  | — → Incumple | **8B elegida:** NORM_05 2.1: Incumple (oraciones O4, O5) — La oferta indica una desviación mayor que la exigida por la norma.<br>**8B v1:** no llegó al verificador |
| P1-05-B | NORM_05 4.4 | perdida en verificación | perdida en verificación | sí → sí |  |  |
| P2-01-A | NORM_01 5.2 | encontrada | encontrada |  |  |  |
| P2-01-M | NORM_01 3.2 | no recuperada | encontrada **(cambia)** |  | — → Incumple | **8B elegida:** NORM_01 3.2: Incumple (oraciones O12, O13) — La oferta menciona un contenido de cemento de 330 kg/m³, que cumple con el mínimo de 300 kg/m³. Sin embargo, la relación agua/cemento de 0,52 supera el límite máximo de 0,48 establecido en la norma.<br>**8B v1:** no llegó al verificador |
| P2-01-B | NORM_01 3.7 | no recuperada | encontrada **(cambia)** |  | — → Incumple | **8B elegida:** NORM_01 3.7: Incumple (oraciones O17) — La oferta menciona el uso exclusivo del ensayo esclerométrico a los 28 días sin cumplir con la norma que exige la correlación con testigos extraídos o un procedimiento aprobado, y la interpretación por profesional competente.<br>**8B v1:** no llegó al verificador |
| P2-02-A | NORM_02 3.13 | encontrada | encontrada |  |  |  |
| P2-02-M | NORM_02 2.16 | perdida en verificación | perdida en verificación | sí → sí |  |  |
| P2-02-B | NORM_02 4.7 | encontrada | encontrada |  |  |  |
| P2-03-A | NORM_03 2.8 | encontrada | encontrada |  |  |  |
| P2-03-M | NORM_03 2.4 | encontrada | encontrada |  |  |  |
| P2-03-B | NORM_03 6.2 | perdida en verificación | perdida en verificación | sí → sí |  |  |
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
| P3-03-M | NORM_03 5.5 | perdida en verificación | otra causa (descartada por regla 2.5) **(cambia)** | sí → sí | Cumple → Incumple | **8B elegida:** NORM_03 5.5: Incumple (oraciones O14, O15) — La oferta menciona la presencia del Responsable de Higiene y Seguridad y del Supervisor de Montaje, pero no garantiza la presencia física continua e ininterrumpida, ni la ubicación dentro del área operativa segura.<br>**8B v1:** NORM_03 5.5: Cumple (oraciones O14, O15) — La oferta menciona la presencia física y continua del Responsable de Higiene y Seguridad y del Supervisor de Montaje, así como su permanencia en el área de maniobra, cumpliendo con los requisitos del artículo. |
| P3-03-B | NORM_03 5.2 | otra causa (cita otro artículo) | otra causa (cita otro artículo) |  |  |  |
| P3-04-A | NORM_04 3.6 | encontrada | encontrada |  |  |  |
| P3-04-M | NORM_04 1.6 | encontrada | encontrada |  |  |  |
| P3-04-B | NORM_04 3.10 | encontrada | encontrada |  |  |  |
| P3-05-A | NORM_05 4.3 | no recuperada | no recuperada |  |  |  |
| P3-05-M | NORM_05 2.9 | no recuperada | no recuperada |  |  |  |
| P3-05-B | NORM_05 2.3 | no recuperada | no recuperada |  |  |  |
| P4-01-A | NORM_01 3.1 | encontrada | encontrada |  |  |  |
| P4-01-M | NORM_01 3.5 | encontrada | encontrada |  |  |  |
| P4-01-B | NORM_01 4.1 | encontrada | encontrada |  |  |  |
| P4-02-A | NORM_02 4.15 | encontrada | encontrada |  |  |  |
| P4-02-M | NORM_02 1.10 | perdida en verificación | perdida en verificación | sí → sí |  |  |
| P4-02-B | NORM_02 4.10 | encontrada | encontrada |  |  |  |
| P4-03-A | NORM_03 3.4 | encontrada | encontrada |  |  |  |
| P4-03-M | NORM_03 4.2 | encontrada | encontrada |  |  |  |
| P4-03-B | NORM_03 3.6 | perdida en verificación | perdida en verificación | sí → sí |  |  |
| P4-04-A | NORM_04 1.10 | encontrada | encontrada |  |  |  |
| P4-04-M | NORM_04 3.20 | perdida en verificación | perdida en verificación | sí → sí |  |  |
| P4-04-B | NORM_04 3.12 | encontrada | encontrada |  |  |  |
| P4-05-A | NORM_05 3.9 | no recuperada | perdida en verificación **(cambia)** | sin citas → sí | — → No aplica | **8B elegida:** NORM_05 3.9: No aplica (oraciones O2, O3, O4, O8, O10) — La oferta no menciona el control de humedad ni métodos de medición requeridos por el artículo.<br>**8B v1:** no llegó al verificador |
| P4-05-M | NORM_05 4.8 | encontrada | encontrada |  |  |  |
| P4-05-B | NORM_05 4.5 | encontrada | encontrada |  |  |  |

