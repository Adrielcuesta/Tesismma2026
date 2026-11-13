# Evaluación P1+P2

## Recuperación

| Métrica | Valor |
|---|---|
| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | 24/30 (80%), IC 95 % 63%–90% |

## Detección

| Métrica | Valor |
|---|---|
| Recall solo riesgos (frase y artículo) | 20/30 (67%), IC 95 % 49%–81% |
| Recall riesgos + alertas (la alerta de contradicción cita la frase y el artículo) | 20/30 (67%), IC 95 % 49%–81% |
| Precisión | precisión pendiente de revisión |
| F1 | n/d |
| F2 | n/d |
| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | 4/30 (13%) |
| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | 0/30 (0%) |

## Clasificación (de las trampas encontradas)

| Métrica | Valor |
|---|---|
| Exactitud de clase | 9/20 (45%) |
| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | 0.14 |
| Responsable correcto | 20/20 (100%) |

Matriz de confusión de clase (filas: esperada; columnas: obtenida)

| esperada \ obtenida | Crítico | Mayor | Menor |
|---|---|---|---|
| Crítico | 1 | 6 | 0 |
| Mayor | 0 | 8 | 0 |
| Menor | 0 | 5 | 0 |

## Fidelidad

| Métrica | Valor |
|---|---|
| Brechas con alguna marca «valor no verificado» | 29/88 (33%) |

La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas.

## Recall por clase esperada

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Crítico | 9 | 7/9 (78%) | 7/9 (78%) |
| Mayor | 13 | 8/13 (62%) | 8/13 (62%) |
| Menor | 8 | 5/8 (62%) | 5/8 (62%) |

## Recall por nivel esperado

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Alto | 12 | 9/12 (75%) | 9/12 (75%) |
| Medio | 10 | 6/10 (60%) | 6/10 (60%) |
| Bajo | 8 | 5/8 (62%) | 5/8 (62%) |

## Falsas alarmas

| Métrica | Valor |
|---|---|
| Espejos marcados | 1/60 (2%), IC 95 % 0%–9% |

## Volumen

| Concepto | Cantidad |
|---|---|
| Brechas | 88 |
| Riesgos agrupados | 46 |
| Solicitudes | 46 |
| Alertas | 13 |

## Dónde se pierde cada trampa

| Etapa | Trampas |
|---|---|
| no recuperada | 6/30 (20%) |
| perdida en verificación | 4/30 (13%) |
| perdida en clasificación | 0/30 (0%) |
| encontrada | 20/30 (67%) |

| Trampa no encontrada | Dónde se pierde | Artículo | Veredicto de verificación | Veredicto de clasificación |
|---|---|---|---|---|
| P1-01-B | perdida en verificación | NORM_01 Art. 6.5 | Cumple | — |
| P1-04-B | no recuperada | NORM_04 Art. 2.5 | — | — |
| P1-05-M | no recuperada | NORM_05 Art. 2.1 | — | — |
| P1-05-B | perdida en verificación | NORM_05 Art. 4.4 | Cumple | — |
| P2-01-M | no recuperada | NORM_01 Art. 3.2 | — | — |
| P2-01-B | no recuperada | NORM_01 Art. 3.7 | — | — |
| P2-02-M | perdida en verificación | NORM_02 Art. 2.16 | Cumple | — |
| P2-03-A | perdida en verificación | NORM_03 Art. 2.8 | Cumple | — |
| P2-04-B | no recuperada | NORM_04 Art. 2.13 | — | — |
| P2-05-A | no recuperada | NORM_05 Art. 1.8 | — | — |

## Costo computacional

**P1**

| Concepto | Valor |
|---|---|
| Modelo | deepinfra:Qwen/Qwen3-32B |
| Hardware | n/d |
| Pares verificados | 303 |
| Llamadas totales (con comentario y reintentos) | 392 |
| Tiempo total | 927,8 s (0:15:27) |
| Segundos por par (mediana / p90) | 12.5 / 34.3 |
| Tokens de entrada (total / por par) | 1.049.447 / 3.464 |
| Tokens de salida (total / por par) | 103.366 / 341 |

**P2**

| Concepto | Valor |
|---|---|
| Modelo | deepinfra:Qwen/Qwen3-32B |
| Hardware | n/d |
| Pares verificados | 213 |
| Llamadas totales (con comentario y reintentos) | 283 |
| Tiempo total | 769,3 s (0:12:49) |
| Segundos por par (mediana / p90) | 13.8 / 39.7 |
| Tokens de entrada (total / por par) | 754.604 / 3.543 |
| Tokens de salida (total / por par) | 77.169 / 362 |

## Detalle por trampa

| Trampa | Encontrada | Artículo citado | Artículo verificado | Clase esperada | Clase obtenida | Responsable esperado | Responsable obtenido | Nivel esperado | Nivel obtenido |
|---|---|---|---|---|---|---|---|---|---|
| P1-01-A | sí | — | sí | Crítico | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P1-01-M | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Medio |
| P1-01-B | no | — | sí | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P1-02-A | sí | — | sí | Crítico | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P1-02-M | sí | — | sí | Mayor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Medio | Medio |
| P1-02-B | sí | — | sí | Menor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Bajo |
| P1-03-A | sí | — | sí | Crítico | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Alto | Medio |
| P1-03-M | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Medio |
| P1-03-B | sí | — | sí | Menor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Bajo | Medio |
| P1-04-A | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Medio |
| P1-04-M | sí | — | sí | Mayor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Bajo |
| P1-04-B | otro artículo | NORM_04 Art. 2.4 | no | Menor | — | Gerencia de Infraestructura y Vías | — | Bajo | — |
| P1-05-A | sí | — | sí | Crítico | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Alto |
| P1-05-M | otro artículo | NORM_05 Art. 5.3 | no | Mayor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P1-05-B | otro artículo | NORM_01 Art. 4.3 | sí | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P2-01-A | sí | — | sí | Crítico | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P2-01-M | otro artículo | NORM_05 Art. 2.4 | no | Menor | — | Gerencia de Infraestructura y Vías | — | Bajo | — |
| P2-01-B | otro artículo | NORM_05 Art. 2.4 | no | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P2-02-A | sí | — | sí | Crítico | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P2-02-M | no | — | sí | Mayor | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Medio | — |
| P2-02-B | sí | — | sí | Menor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Medio |
| P2-03-A | no | — | sí | Crítico | — | Gerencia de Seguridad Operacional y Salud Ocupacional | — | Alto | — |
| P2-03-M | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Medio |
| P2-03-B | sí | — | sí | Menor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Bajo | Medio |
| P2-04-A | sí | — | sí | Crítico | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Medio |
| P2-04-M | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Medio |
| P2-04-B | otro artículo | NORM_05 Art. 2.6 | no | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P2-05-A | otro artículo | NORM_05 Art. 5.2 | no | Crítico | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P2-05-M | sí | — | sí | Mayor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Medio | Medio |
| P2-05-B | sí | — | sí | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Medio |
