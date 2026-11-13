# Evaluación P3+P4

## Recuperación

| Métrica | Valor |
|---|---|
| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | 25/30 (83%), IC 95 % 66%–93% |

## Detección

| Métrica | Valor |
|---|---|
| Recall solo riesgos (frase y artículo) | 19/30 (63%), IC 95 % 46%–78% |
| Recall riesgos + alertas (la alerta de contradicción cita la frase y el artículo) | 20/30 (67%), IC 95 % 49%–81% |
| Precisión | precisión pendiente de revisión |
| F1 | n/d |
| F2 | n/d |
| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | 4/30 (13%) |
| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | 0/30 (0%) |

## Clasificación (de las trampas encontradas)

| Métrica | Valor |
|---|---|
| Exactitud de clase | 8/19 (42%) |
| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | 0.24 |
| Responsable correcto | 19/19 (100%) |

Matriz de confusión de clase (filas: esperada; columnas: obtenida)

| esperada \ obtenida | Crítico | Mayor | Menor |
|---|---|---|---|
| Crítico | 2 | 2 | 0 |
| Mayor | 3 | 4 | 1 |
| Menor | 2 | 3 | 2 |

## Fidelidad

| Métrica | Valor |
|---|---|
| Brechas con alguna marca «valor no verificado» | 47/137 (34%) |

La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas.

## Recall por clase esperada

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Crítico | 7 | 4/7 (57%) | 5/7 (71%) |
| Mayor | 10 | 8/10 (80%) | 8/10 (80%) |
| Menor | 13 | 7/13 (54%) | 7/13 (54%) |

## Recall por nivel esperado

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Alto | 9 | 6/9 (67%) | 7/9 (78%) |
| Medio | 8 | 6/8 (75%) | 6/8 (75%) |
| Bajo | 13 | 7/13 (54%) | 7/13 (54%) |

## Falsas alarmas

| Métrica | Valor |
|---|---|
| Espejos marcados | 20/60 (33%), IC 95 % 23%–46% |

## Volumen

| Concepto | Cantidad |
|---|---|
| Brechas | 137 |
| Riesgos agrupados | 32 |
| Solicitudes | 32 |
| Alertas | 13 |

## Dónde se pierde cada trampa

| Etapa | Trampas |
|---|---|
| no recuperada | 5/30 (17%) |
| perdida en verificación | 4/30 (13%) |
| perdida en clasificación | 0/30 (0%) |
| otra causa | 2/30 (7%) |
| encontrada | 19/30 (63%) |

| Trampa no encontrada | Dónde se pierde | Artículo | Veredicto de verificación | Veredicto de clasificación |
|---|---|---|---|---|
| P3-01-A | otra causa | NORM_01 Art. 6.1 | Incumple | — |
| P3-02-A | no recuperada | NORM_02 Art. 5.14 | — | — |
| P3-03-M | perdida en verificación | NORM_03 Art. 5.5 | Cumple | — |
| P3-03-B | otra causa | NORM_03 Art. 5.2 | Incumple | — |
| P3-05-A | no recuperada | NORM_05 Art. 4.3 | — | — |
| P3-05-M | no recuperada | NORM_05 Art. 2.9 | — | — |
| P3-05-B | no recuperada | NORM_05 Art. 2.3 | — | — |
| P4-02-M | perdida en verificación | NORM_02 Art. 1.10 | Cumple | — |
| P4-03-B | perdida en verificación | NORM_03 Art. 3.6 | Cumple | — |
| P4-04-M | perdida en verificación | NORM_04 Art. 3.20 | No aplica | — |
| P4-05-A | no recuperada | NORM_05 Art. 3.9 | — | — |

## Costo computacional

**P3**

| Concepto | Valor |
|---|---|
| Modelo | qwen3:8b |
| Hardware | NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB |
| Pares verificados | 219 |
| Llamadas totales (con comentario y reintentos) | 323 |
| Tiempo total | 4.909,0 s (1:21:49) |
| Segundos por par (mediana / p90) | 20.9 / 37.5 |
| Tokens de entrada (total / por par) | 984.915 / 4.490 |
| Tokens de salida (total / por par) | 103.306 / 471 |

**P4**

| Concepto | Valor |
|---|---|
| Modelo | qwen3:8b |
| Hardware | NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB |
| Pares verificados | 225 |
| Llamadas totales (con comentario y reintentos) | 326 |
| Tiempo total | 4.934,7 s (1:22:14) |
| Segundos por par (mediana / p90) | 15.5 / 37.5 |
| Tokens de entrada (total / por par) | 960.835 / 4.263 |
| Tokens de salida (total / por par) | 106.206 / 471 |

## Detalle por trampa

| Trampa | Encontrada | Artículo citado | Artículo verificado | Clase esperada | Clase obtenida | Responsable esperado | Responsable obtenido | Nivel esperado | Nivel obtenido |
|---|---|---|---|---|---|---|---|---|---|
| P3-01-A | otro artículo | NORM_01 Art. 5.1 | sí | Crítico | — | Gerencia de Infraestructura y Vías | — | Alto | — |
| P3-01-M | sí | — | sí | Mayor | Menor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Bajo |
| P3-01-B | sí | — | sí | Menor | Menor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Bajo | Bajo |
| P3-02-A | otro artículo | NORM_02 Art. 6.10 | no | Crítico | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Alto | — |
| P3-02-M | sí | — | sí | Mayor | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P3-02-B | sí | — | sí | Menor | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Alto |
| P3-03-A | sí | — | sí | Crítico | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Alto | Medio |
| P3-03-M | otro artículo | NORM_03 Art. 2.1 | sí | Mayor | — | Gerencia de Seguridad Operacional y Salud Ocupacional | — | Medio | — |
| P3-03-B | otro artículo | NORM_03 Art. 2.1 | sí | Menor | — | Gerencia de Seguridad Operacional y Salud Ocupacional | — | Bajo | — |
| P3-04-A | sí | — | sí | Crítico | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Medio |
| P3-04-M | sí | — | sí | Mayor | Crítico | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Alto |
| P3-04-B | sí | — | sí | Menor | Menor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Bajo |
| P3-05-A | otro artículo | NORM_05 Art. 5.5 | no | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P3-05-M | otro artículo | NORM_05 Art. 2.10 | no | Mayor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Medio | — |
| P3-05-B | otro artículo | NORM_05 Art. 2.6 | no | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P4-01-A | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Medio |
| P4-01-M | sí | — | sí | Mayor | Crítico | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Alto |
| P4-01-B | sí | — | sí | Menor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Bajo | Bajo |
| P4-02-A | sí | — | sí | Crítico | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P4-02-M | no | — | sí | Menor | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Bajo | — |
| P4-02-B | sí | — | sí | Menor | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Alto |
| P4-03-A | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Bajo |
| P4-03-M | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Medio |
| P4-03-B | otro artículo | NORM_03 Art. 3.4 | sí | Menor | — | Gerencia de Seguridad Operacional y Salud Ocupacional | — | Bajo | — |
| P4-04-A | sí | — | sí | Crítico | Crítico | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P4-04-M | otro artículo | NORM_04 Art. 3.8 | sí | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P4-04-B | sí | — | sí | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Medio |
| P4-05-A | otro artículo | NORM_05 Art. 3.4 | no | Crítico | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P4-05-M | sí | — | sí | Mayor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Medio | Medio |
| P4-05-B | sí | — | sí | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Medio |

## Comparación con la línea de base sin RAG

| Métrica | Con RAG | Sin RAG |
|---|---|---|
| Trampas encontradas | 19/30 (63%) (frase y artículo) | 13/30 (43%) por frase, sin validar |
| Falsas alarmas (por frase del espejo) | 20/60 (33%) | 18/60 (30%) |
| Riesgos / brechas | 137 | 79 |
| Riesgos agrupados | 32 | — |
| Solicitudes | 32 | — |
| Alertas | 13 | — |

Nota: la columna sin RAG usa «por frase», un criterio más laxo que el de la columna con RAG: la diferencia es una cota inferior del aporte del RAG.

Prueba exacta de McNemar (pareada por trampa): solo con RAG 11, solo sin RAG 5, p = 0.2101.
