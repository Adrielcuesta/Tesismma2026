# Evaluación P3+P4

## Recuperación

| Métrica | Valor |
|---|---|
| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | 25/30 (83%), IC 95 % 66%–93% |

## Detección

| Métrica | Valor |
|---|---|
| Recall solo riesgos (frase y artículo) | 20/30 (67%), IC 95 % 49%–81% |
| Recall riesgos + alertas (la alerta de contradicción cita la frase y el artículo) | 20/30 (67%), IC 95 % 49%–81% |
| Precisión | precisión pendiente de revisión |
| F1 | n/d |
| F2 | n/d |
| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | 1/30 (3%) |
| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | 3/30 (10%) |

## Clasificación (de las trampas encontradas)

| Métrica | Valor |
|---|---|
| Exactitud de clase | 9/20 (45%) |
| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | 0.21 |
| Responsable correcto | 20/20 (100%) |

Matriz de confusión de clase (filas: esperada; columnas: obtenida)

| esperada \ obtenida | Crítico | Mayor | Menor |
|---|---|---|---|
| Crítico | 2 | 3 | 0 |
| Mayor | 1 | 5 | 1 |
| Menor | 2 | 4 | 2 |

## Fidelidad

| Métrica | Valor |
|---|---|
| Brechas con alguna marca «valor no verificado» | 44/130 (34%) |

La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas.

## Recall por clase esperada

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Crítico | 7 | 5/7 (71%) | 5/7 (71%) |
| Mayor | 10 | 7/10 (70%) | 7/10 (70%) |
| Menor | 13 | 8/13 (62%) | 8/13 (62%) |

## Recall por nivel esperado

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Alto | 9 | 7/9 (78%) | 7/9 (78%) |
| Medio | 8 | 5/8 (62%) | 5/8 (62%) |
| Bajo | 13 | 8/13 (62%) | 8/13 (62%) |

## Falsas alarmas

| Métrica | Valor |
|---|---|
| Espejos marcados | 8/60 (13%), IC 95 % 7%–24% |

## Volumen

| Concepto | Cantidad |
|---|---|
| Brechas | 130 |
| Riesgos agrupados | 52 |
| Solicitudes | 52 |
| Alertas | 3 |

## Dónde se pierde cada trampa

| Etapa | Trampas |
|---|---|
| no recuperada | 5/30 (17%) |
| perdida en verificación | 1/30 (3%) |
| perdida en clasificación | 3/30 (10%) |
| otra causa | 1/30 (3%) |
| encontrada | 20/30 (67%) |

| Trampa no encontrada | Dónde se pierde | Artículo | Veredicto de verificación | Veredicto de clasificación |
|---|---|---|---|---|
| P3-02-A | no recuperada | NORM_02 Art. 5.14 | — | — |
| P3-04-M | perdida en clasificación | NORM_04 Art. 1.6 | Incumple | CUMPLE |
| P3-04-B | otra causa | NORM_04 Art. 3.10 | Incumple | — |
| P3-05-A | no recuperada | NORM_05 Art. 4.3 | — | — |
| P3-05-M | no recuperada | NORM_05 Art. 2.9 | — | — |
| P3-05-B | no recuperada | NORM_05 Art. 2.3 | — | — |
| P4-01-M | perdida en verificación | NORM_01 Art. 3.5 | Cumple | — |
| P4-01-B | perdida en clasificación | NORM_01 Art. 4.1 | Incumple | CUMPLE |
| P4-05-A | no recuperada | NORM_05 Art. 3.9 | — | — |
| P4-05-B | perdida en clasificación | NORM_05 Art. 4.5 | Incumple | NO_APLICA |

## Costo computacional

**P3**

| Concepto | Valor |
|---|---|
| Modelo | deepinfra:Qwen/Qwen3-32B |
| Hardware | n/d |
| Pares verificados | 219 |
| Llamadas totales (con comentario y reintentos) | 350 |
| Tiempo total | 3.405,7 s (0:56:45) |
| Segundos por par (mediana / p90) | 85.7 / 148.1 |
| Tokens de entrada (total / por par) | 1.135.483 / 5.185 |
| Tokens de salida (total / por par) | 427.419 / 1.952 |

**P4**

| Concepto | Valor |
|---|---|
| Modelo | deepinfra:Qwen/Qwen3-32B |
| Hardware | n/d |
| Pares verificados | 225 |
| Llamadas totales (con comentario y reintentos) | 346 |
| Tiempo total | 2.953,5 s (0:49:13) |
| Segundos por par (mediana / p90) | 74.4 / 133.9 |
| Tokens de entrada (total / por par) | 1.071.801 / 4.764 |
| Tokens de salida (total / por par) | 403.639 / 1.794 |

## Detalle por trampa

| Trampa | Encontrada | Artículo citado | Artículo verificado | Clase esperada | Clase obtenida | Responsable esperado | Responsable obtenido | Nivel esperado | Nivel obtenido |
|---|---|---|---|---|---|---|---|---|---|
| P3-01-A | sí | — | sí | Crítico | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Medio |
| P3-01-M | sí | — | sí | Mayor | Menor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Bajo |
| P3-01-B | sí | — | sí | Menor | Menor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Bajo | Bajo |
| P3-02-A | otro artículo | NORM_05 Art. 4.9 | no | Crítico | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Alto | — |
| P3-02-M | sí | — | sí | Mayor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P3-02-B | sí | — | sí | Menor | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Alto |
| P3-03-A | sí | — | sí | Crítico | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Alto | Alto |
| P3-03-M | sí | — | sí | Mayor | Crítico | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Alto |
| P3-03-B | sí | — | sí | Menor | Crítico | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Bajo | Alto |
| P3-04-A | sí | — | sí | Crítico | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Alto |
| P3-04-M | no | — | sí | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P3-04-B | otro artículo | NORM_04 Art. 3.12 | sí | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P3-05-A | otro artículo | NORM_05 Art. 5.5 | no | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P3-05-M | no | — | no | Mayor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Medio | — |
| P3-05-B | no | — | no | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P4-01-A | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P4-01-M | no | — | sí | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P4-01-B | no | — | sí | Menor | — | Gerencia de Infraestructura y Vías | — | Bajo | — |
| P4-02-A | sí | — | sí | Crítico | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P4-02-M | sí | — | sí | Menor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Alto |
| P4-02-B | sí | — | sí | Menor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Medio |
| P4-03-A | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Alto |
| P4-03-M | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Alto |
| P4-03-B | sí | — | sí | Menor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Bajo | Medio |
| P4-04-A | sí | — | sí | Crítico | Crítico | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P4-04-M | sí | — | sí | Menor | Menor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Bajo |
| P4-04-B | sí | — | sí | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Medio |
| P4-05-A | no | — | no | Crítico | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P4-05-M | sí | — | sí | Mayor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Medio | Alto |
| P4-05-B | otro artículo | NORM_05 Art. 5.5 | sí | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
