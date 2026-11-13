# Evaluación P1+P2

## Recuperación

| Métrica | Valor |
|---|---|
| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | 24/30 (80%), IC 95 % 63%–90% |

## Detección

| Métrica | Valor |
|---|---|
| Recall solo riesgos (frase y artículo) | 22/30 (73%), IC 95 % 56%–86% |
| Recall riesgos + alertas (la alerta de contradicción cita la frase y el artículo) | 23/30 (77%), IC 95 % 59%–88% |
| Precisión | precisión pendiente de revisión |
| F1 | n/d |
| F2 | n/d |
| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | 0/30 (0%) |
| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | 1/30 (3%) |

## Clasificación (de las trampas encontradas)

| Métrica | Valor |
|---|---|
| Exactitud de clase | 12/22 (55%) |
| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | 0.08 |
| Responsable correcto | 22/22 (100%) |

Matriz de confusión de clase (filas: esperada; columnas: obtenida)

| esperada \ obtenida | Crítico | Mayor | Menor |
|---|---|---|---|
| Crítico | 3 | 3 | 1 |
| Mayor | 1 | 8 | 0 |
| Menor | 2 | 3 | 1 |

## Fidelidad

| Métrica | Valor |
|---|---|
| Brechas con alguna marca «valor no verificado» | 58/167 (35%) |

La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas.

## Recall por clase esperada

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Crítico | 9 | 7/9 (78%) | 8/9 (89%) |
| Mayor | 13 | 9/13 (69%) | 9/13 (69%) |
| Menor | 8 | 6/8 (75%) | 6/8 (75%) |

## Recall por nivel esperado

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Alto | 12 | 9/12 (75%) | 10/12 (83%) |
| Medio | 10 | 7/10 (70%) | 7/10 (70%) |
| Bajo | 8 | 6/8 (75%) | 6/8 (75%) |

## Falsas alarmas

| Métrica | Valor |
|---|---|
| Espejos marcados | 5/60 (8%), IC 95 % 4%–18% |

## Volumen

| Concepto | Cantidad |
|---|---|
| Brechas | 167 |
| Riesgos agrupados | 49 |
| Solicitudes | 49 |
| Alertas | 7 |

## Dónde se pierde cada trampa

| Etapa | Trampas |
|---|---|
| no recuperada | 6/30 (20%) |
| perdida en verificación | 0/30 (0%) |
| perdida en clasificación | 1/30 (3%) |
| otra causa | 1/30 (3%) |
| encontrada | 22/30 (73%) |

| Trampa no encontrada | Dónde se pierde | Artículo | Veredicto de verificación | Veredicto de clasificación |
|---|---|---|---|---|
| P1-04-B | no recuperada | NORM_04 Art. 2.5 | — | — |
| P1-05-M | no recuperada | NORM_05 Art. 2.1 | — | — |
| P2-01-M | no recuperada | NORM_01 Art. 3.2 | — | — |
| P2-01-B | no recuperada | NORM_01 Art. 3.7 | — | — |
| P2-02-A | otra causa | NORM_02 Art. 3.13 | Incumple | — |
| P2-02-M | perdida en clasificación | NORM_02 Art. 2.16 | Revisar | CUMPLE |
| P2-04-B | no recuperada | NORM_04 Art. 2.13 | — | — |
| P2-05-A | no recuperada | NORM_05 Art. 1.8 | — | — |

## Costo computacional

**P1**

| Concepto | Valor |
|---|---|
| Modelo | deepinfra:Qwen/Qwen3-32B |
| Hardware | n/d |
| Pares verificados | 303 |
| Llamadas totales (con comentario y reintentos) | 484 |
| Tiempo total | 3.860,2 s (1:04:20) |
| Segundos por par (mediana / p90) | 71.9 / 129.1 |
| Tokens de entrada (total / por par) | 1.592.647 / 5.256 |
| Tokens de salida (total / por par) | 567.945 / 1.874 |

**P2**

| Concepto | Valor |
|---|---|
| Modelo | deepinfra:Qwen/Qwen3-32B |
| Hardware | n/d |
| Pares verificados | 213 |
| Llamadas totales (con comentario y reintentos) | 339 |
| Tiempo total | 2.565,9 s (0:42:45) |
| Segundos por par (mediana / p90) | 78.2 / 145.4 |
| Tokens de entrada (total / por par) | 1.081.610 / 5.078 |
| Tokens de salida (total / por par) | 393.731 / 1.848 |

## Detalle por trampa

| Trampa | Encontrada | Artículo citado | Artículo verificado | Clase esperada | Clase obtenida | Responsable esperado | Responsable obtenido | Nivel esperado | Nivel obtenido |
|---|---|---|---|---|---|---|---|---|---|
| P1-01-A | sí | — | sí | Crítico | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P1-01-M | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Alto |
| P1-01-B | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Medio |
| P1-02-A | sí | — | sí | Crítico | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P1-02-M | sí | — | sí | Mayor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Medio | Alto |
| P1-02-B | sí | — | sí | Menor | Menor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Bajo |
| P1-03-A | sí | — | sí | Crítico | Menor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Alto | Bajo |
| P1-03-M | sí | — | sí | Mayor | Crítico | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Alto |
| P1-03-B | sí | — | sí | Menor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Bajo | Medio |
| P1-04-A | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P1-04-M | sí | — | sí | Mayor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Bajo |
| P1-04-B | otro artículo | NORM_04 Art. 2.11 | no | Menor | — | Gerencia de Infraestructura y Vías | — | Bajo | — |
| P1-05-A | sí | — | sí | Crítico | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Bajo |
| P1-05-M | otro artículo | NORM_05 Art. 5.3 | no | Mayor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P1-05-B | sí | — | sí | Menor | Crítico | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Alto |
| P2-01-A | sí | — | sí | Crítico | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P2-01-M | otro artículo | NORM_05 Art. 2.4 | no | Menor | — | Gerencia de Infraestructura y Vías | — | Bajo | — |
| P2-01-B | otro artículo | NORM_05 Art. 2.4 | no | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P2-02-A | otro artículo | NORM_02 Art. 4.2 | sí | Crítico | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Alto | — |
| P2-02-M | no | — | sí | Mayor | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Medio | — |
| P2-02-B | sí | — | sí | Menor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Medio |
| P2-03-A | sí | — | sí | Crítico | Crítico | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Alto | Alto |
| P2-03-M | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Medio |
| P2-03-B | sí | — | sí | Menor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Bajo | Medio |
| P2-04-A | sí | — | sí | Crítico | Crítico | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Alto |
| P2-04-M | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Alto |
| P2-04-B | no | — | no | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P2-05-A | otro artículo | NORM_02 Art. 5.13 | no | Crítico | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P2-05-M | sí | — | sí | Mayor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Medio | Medio |
| P2-05-B | sí | — | sí | Menor | Crítico | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Alto |
