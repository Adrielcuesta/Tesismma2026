# Evaluación P1+P2+P3+P4

## Recuperación

| Métrica | Valor |
|---|---|
| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | 49/60 (82%), IC 95 % 70%–89% |

## Detección

| Métrica | Valor |
|---|---|
| Recall solo riesgos (frase y artículo) | 41/60 (68%), IC 95 % 56%–79% |
| Recall riesgos + alertas (la alerta de contradicción cita la frase y el artículo) | 42/60 (70%), IC 95 % 57%–80% |
| Precisión | precisión pendiente de revisión |
| F1 | n/d |
| F2 | n/d |
| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | 5/60 (8%) |
| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | 0/60 (0%) |

## Clasificación (de las trampas encontradas)

| Métrica | Valor |
|---|---|
| Exactitud de clase | 19/41 (46%) |
| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | 0.26 |
| Responsable correcto | 41/41 (100%) |

Matriz de confusión de clase (filas: esperada; columnas: obtenida)

| esperada \ obtenida | Crítico | Mayor | Menor |
|---|---|---|---|
| Crítico | 2 | 9 | 0 |
| Mayor | 0 | 15 | 2 |
| Menor | 0 | 11 | 2 |

## Fidelidad

| Métrica | Valor |
|---|---|
| Brechas con alguna marca «valor no verificado» | 49/168 (29%) |

La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas.

## Recall por clase esperada

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Crítico | 16 | 11/16 (69%) | 12/16 (75%) |
| Mayor | 23 | 17/23 (74%) | 17/23 (74%) |
| Menor | 21 | 13/21 (62%) | 13/21 (62%) |

## Recall por nivel esperado

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Alto | 21 | 15/21 (71%) | 16/21 (76%) |
| Medio | 18 | 13/18 (72%) | 13/18 (72%) |
| Bajo | 21 | 13/21 (62%) | 13/21 (62%) |

## Falsas alarmas

| Métrica | Valor |
|---|---|
| Espejos marcados | 1/120 (1%), IC 95 % 0%–5% |

## Volumen

| Concepto | Cantidad |
|---|---|
| Brechas | 168 |
| Riesgos agrupados | 93 |
| Solicitudes | 93 |
| Alertas | 27 |

## Dónde se pierde cada trampa

| Etapa | Trampas |
|---|---|
| no recuperada | 11/60 (18%) |
| perdida en verificación | 5/60 (8%) |
| perdida en clasificación | 0/60 (0%) |
| otra causa | 3/60 (5%) |
| encontrada | 41/60 (68%) |

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
