# Evaluación P1+P2+P3+P4

## Recuperación

| Métrica | Valor |
|---|---|
| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | 49/60 (82%), IC 95 % 70%–89% |

## Detección

| Métrica | Valor |
|---|---|
| Recall solo riesgos (frase y artículo) | 42/60 (70%), IC 95 % 57%–80% |
| Recall riesgos + alertas (la alerta de contradicción cita la frase y el artículo) | 43/60 (72%), IC 95 % 59%–81% |
| Precisión | precisión pendiente de revisión |
| F1 | n/d |
| F2 | n/d |
| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | 1/60 (2%) |
| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | 4/60 (7%) |

## Clasificación (de las trampas encontradas)

| Métrica | Valor |
|---|---|
| Exactitud de clase | 21/42 (50%) |
| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | 0.15 |
| Responsable correcto | 42/42 (100%) |

Matriz de confusión de clase (filas: esperada; columnas: obtenida)

| esperada \ obtenida | Crítico | Mayor | Menor |
|---|---|---|---|
| Crítico | 5 | 6 | 1 |
| Mayor | 2 | 13 | 1 |
| Menor | 4 | 7 | 3 |

## Fidelidad

| Métrica | Valor |
|---|---|
| Brechas con alguna marca «valor no verificado» | 102/297 (34%) |

La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas.

## Recall por clase esperada

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Crítico | 16 | 12/16 (75%) | 13/16 (81%) |
| Mayor | 23 | 16/23 (70%) | 16/23 (70%) |
| Menor | 21 | 14/21 (67%) | 14/21 (67%) |

## Recall por nivel esperado

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Alto | 21 | 16/21 (76%) | 17/21 (81%) |
| Medio | 18 | 12/18 (67%) | 12/18 (67%) |
| Bajo | 21 | 14/21 (67%) | 14/21 (67%) |

## Falsas alarmas

| Métrica | Valor |
|---|---|
| Espejos marcados | 13/120 (11%), IC 95 % 6%–18% |

## Volumen

| Concepto | Cantidad |
|---|---|
| Brechas | 297 |
| Riesgos agrupados | 101 |
| Solicitudes | 101 |
| Alertas | 10 |

## Dónde se pierde cada trampa

| Etapa | Trampas |
|---|---|
| no recuperada | 11/60 (18%) |
| perdida en verificación | 1/60 (2%) |
| perdida en clasificación | 4/60 (7%) |
| otra causa | 2/60 (3%) |
| encontrada | 42/60 (70%) |

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
