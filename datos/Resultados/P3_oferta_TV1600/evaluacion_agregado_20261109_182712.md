# Evaluación P3+P4

## Recuperación

| Métrica | Valor |
|---|---|
| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | 25/30 (83%), IC 95 % 66%–93% |

## Detección

| Métrica | Valor |
|---|---|
| Recall solo riesgos (frase y artículo) | 21/30 (70%), IC 95 % 52%–83% |
| Recall riesgos + alertas (la alerta de contradicción cita la frase y el artículo) | 22/30 (73%), IC 95 % 56%–86% |
| Precisión | precisión pendiente de revisión |
| F1 | n/d |
| F2 | n/d |
| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | 1/30 (3%) |
| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | 0/30 (0%) |

## Clasificación (de las trampas encontradas)

| Métrica | Valor |
|---|---|
| Exactitud de clase | 10/21 (48%) |
| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | 0.31 |
| Responsable correcto | 21/21 (100%) |

Matriz de confusión de clase (filas: esperada; columnas: obtenida)

| esperada \ obtenida | Crítico | Mayor | Menor |
|---|---|---|---|
| Crítico | 1 | 3 | 0 |
| Mayor | 0 | 7 | 2 |
| Menor | 0 | 6 | 2 |

## Fidelidad

| Métrica | Valor |
|---|---|
| Brechas con alguna marca «valor no verificado» | 20/80 (25%) |

La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas.

## Recall por clase esperada

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Crítico | 7 | 4/7 (57%) | 5/7 (71%) |
| Mayor | 10 | 9/10 (90%) | 9/10 (90%) |
| Menor | 13 | 8/13 (62%) | 8/13 (62%) |

## Recall por nivel esperado

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Alto | 9 | 6/9 (67%) | 7/9 (78%) |
| Medio | 8 | 7/8 (88%) | 7/8 (88%) |
| Bajo | 13 | 8/13 (62%) | 8/13 (62%) |

## Falsas alarmas

| Métrica | Valor |
|---|---|
| Espejos marcados | 0/60 (0%), IC 95 % 0%–6% |

## Volumen

| Concepto | Cantidad |
|---|---|
| Brechas | 80 |
| Riesgos agrupados | 47 |
| Solicitudes | 47 |
| Alertas | 14 |

## Dónde se pierde cada trampa

| Etapa | Trampas |
|---|---|
| no recuperada | 5/30 (17%) |
| perdida en verificación | 1/30 (3%) |
| perdida en clasificación | 0/30 (0%) |
| otra causa | 3/30 (10%) |
| encontrada | 21/30 (70%) |

| Trampa no encontrada | Dónde se pierde | Artículo | Veredicto de verificación | Veredicto de clasificación |
|---|---|---|---|---|
| P3-01-A | otra causa | NORM_01 Art. 6.1 | Incumple | — |
| P3-02-A | no recuperada | NORM_02 Art. 5.14 | — | — |
| P3-04-B | otra causa | NORM_04 Art. 3.10 | Incumple | — |
| P3-05-A | no recuperada | NORM_05 Art. 4.3 | — | — |
| P3-05-M | no recuperada | NORM_05 Art. 2.9 | — | — |
| P3-05-B | no recuperada | NORM_05 Art. 2.3 | — | — |
| P4-01-B | perdida en verificación | NORM_01 Art. 4.1 | Cumple | — |
| P4-03-B | otra causa | NORM_03 Art. 3.6 | Incumple | INFORMACION_FALTANTE |
| P4-05-A | no recuperada | NORM_05 Art. 3.9 | — | — |

## Costo computacional

**P3**

| Concepto | Valor |
|---|---|
| Modelo | deepinfra:Qwen/Qwen3-32B |
| Hardware | n/d |
| Pares verificados | 219 |
| Llamadas totales (con comentario y reintentos) | 289 |
| Tiempo total | 597,7 s (0:09:57) |
| Segundos por par (mediana / p90) | 11.3 / 33.2 |
| Tokens de entrada (total / por par) | 781.413 / 3.568 |
| Tokens de salida (total / por par) | 77.050 / 352 |

**P4**

| Concepto | Valor |
|---|---|
| Modelo | deepinfra:Qwen/Qwen3-32B |
| Hardware | n/d |
| Pares verificados | 225 |
| Llamadas totales (con comentario y reintentos) | 288 |
| Tiempo total | 659,3 s (0:10:59) |
| Segundos por par (mediana / p90) | 11.6 / 32.8 |
| Tokens de entrada (total / por par) | 733.199 / 3.259 |
| Tokens de salida (total / por par) | 73.789 / 328 |

## Detalle por trampa

| Trampa | Encontrada | Artículo citado | Artículo verificado | Clase esperada | Clase obtenida | Responsable esperado | Responsable obtenido | Nivel esperado | Nivel obtenido |
|---|---|---|---|---|---|---|---|---|---|
| P3-01-A | otro artículo | NORM_01 Art. 6.3 | sí | Crítico | — | Gerencia de Infraestructura y Vías | — | Alto | — |
| P3-01-M | sí | — | sí | Mayor | Menor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Bajo |
| P3-01-B | sí | — | sí | Menor | Menor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Bajo | Bajo |
| P3-02-A | otro artículo | NORM_05 Art. 4.9 | no | Crítico | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Alto | — |
| P3-02-M | sí | — | sí | Mayor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P3-02-B | sí | — | sí | Menor | Menor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Bajo |
| P3-03-A | sí | — | sí | Crítico | Crítico | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Alto | Alto |
| P3-03-M | sí | — | sí | Mayor | Menor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Bajo |
| P3-03-B | sí | — | sí | Menor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Bajo | Bajo |
| P3-04-A | sí | — | sí | Crítico | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Alto |
| P3-04-M | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Medio |
| P3-04-B | otro artículo | NORM_03 Art. 6.4 | sí | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P3-05-A | otro artículo | NORM_01 Art. 4.3 | no | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P3-05-M | otro artículo | NORM_01 Art. 4.3 | no | Mayor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Medio | — |
| P3-05-B | no | — | no | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P4-01-A | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P4-01-M | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Medio |
| P4-01-B | no | — | sí | Menor | — | Gerencia de Infraestructura y Vías | — | Bajo | — |
| P4-02-A | sí | — | sí | Crítico | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Medio |
| P4-02-M | sí | — | sí | Menor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Alto |
| P4-02-B | sí | — | sí | Menor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Medio |
| P4-03-A | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Medio |
| P4-03-M | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Alto |
| P4-03-B | no | — | sí | Menor | — | Gerencia de Seguridad Operacional y Salud Ocupacional | — | Bajo | — |
| P4-04-A | sí | — | sí | Crítico | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P4-04-M | sí | — | sí | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Bajo |
| P4-04-B | sí | — | sí | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Medio |
| P4-05-A | no | — | no | Crítico | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P4-05-M | sí | — | sí | Mayor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Medio | Medio |
| P4-05-B | sí | — | sí | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Medio |
