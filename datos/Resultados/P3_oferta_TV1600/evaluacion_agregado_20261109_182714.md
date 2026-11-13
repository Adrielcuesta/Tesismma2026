# Evaluación P3+P4

## Recuperación

| Métrica | Valor |
|---|---|
| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | 26/30 (87%), IC 95 % 70%–95% |

## Detección

| Métrica | Valor |
|---|---|
| Recall solo riesgos (frase y artículo) | 22/30 (73%), IC 95 % 56%–86% |
| Recall riesgos + alertas (la alerta de contradicción cita la frase y el artículo) | 23/30 (77%), IC 95 % 59%–88% |
| Precisión | precisión pendiente de revisión |
| F1 | n/d |
| F2 | n/d |
| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | 1/30 (3%) |
| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | 1/30 (3%) |

## Clasificación (de las trampas encontradas)

| Métrica | Valor |
|---|---|
| Exactitud de clase | 11/22 (50%) |
| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | 0.18 |
| Responsable correcto | 22/22 (100%) |

Matriz de confusión de clase (filas: esperada; columnas: obtenida)

| esperada \ obtenida | Crítico | Mayor | Menor |
|---|---|---|---|
| Crítico | 2 | 2 | 0 |
| Mayor | 2 | 7 | 0 |
| Menor | 3 | 4 | 2 |

## Fidelidad

| Métrica | Valor |
|---|---|
| Brechas con alguna marca «valor no verificado» | 54/162 (33%) |

La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas.

## Recall por clase esperada

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Crítico | 7 | 4/7 (57%) | 5/7 (71%) |
| Mayor | 10 | 9/10 (90%) | 9/10 (90%) |
| Menor | 13 | 9/13 (69%) | 9/13 (69%) |

## Recall por nivel esperado

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Alto | 9 | 6/9 (67%) | 7/9 (78%) |
| Medio | 8 | 7/8 (88%) | 7/8 (88%) |
| Bajo | 13 | 9/13 (69%) | 9/13 (69%) |

## Falsas alarmas

| Métrica | Valor |
|---|---|
| Espejos marcados | 8/60 (13%), IC 95 % 7%–24% |

## Volumen

| Concepto | Cantidad |
|---|---|
| Brechas | 162 |
| Riesgos agrupados | 58 |
| Solicitudes | 58 |
| Alertas | 5 |

## Dónde se pierde cada trampa

| Etapa | Trampas |
|---|---|
| no recuperada | 4/30 (13%) |
| perdida en verificación | 1/30 (3%) |
| perdida en clasificación | 1/30 (3%) |
| otra causa | 2/30 (7%) |
| encontrada | 22/30 (73%) |

| Trampa no encontrada | Dónde se pierde | Artículo | Veredicto de verificación | Veredicto de clasificación |
|---|---|---|---|---|
| P3-01-A | otra causa | NORM_01 Art. 6.1 | Incumple | — |
| P3-01-M | perdida en clasificación | NORM_01 Art. 7.3 | Incumple | NO_APLICA |
| P3-02-A | no recuperada | NORM_02 Art. 5.14 | — | — |
| P3-04-B | otra causa | NORM_04 Art. 3.10 | Incumple | — |
| P3-05-A | no recuperada | NORM_05 Art. 4.3 | — | — |
| P3-05-B | no recuperada | NORM_05 Art. 2.3 | — | — |
| P4-01-B | perdida en verificación | NORM_01 Art. 4.1 | Cumple | — |
| P4-05-A | no recuperada | NORM_05 Art. 3.9 | — | — |

## Costo computacional

**P3**

| Concepto | Valor |
|---|---|
| Modelo | deepinfra:Qwen/Qwen3-32B |
| Hardware | n/d |
| Pares verificados | 278 |
| Llamadas totales (con comentario y reintentos) | 432 |
| Tiempo total | 3.935,1 s (1:05:35) |
| Segundos por par (mediana / p90) | 82.0 / 148.1 |
| Tokens de entrada (total / por par) | 1.369.647 / 4.927 |
| Tokens de salida (total / por par) | 515.775 / 1.855 |

**P4**

| Concepto | Valor |
|---|---|
| Modelo | deepinfra:Qwen/Qwen3-32B |
| Hardware | n/d |
| Pares verificados | 279 |
| Llamadas totales (con comentario y reintentos) | 430 |
| Tiempo total | 3.605,2 s (1:00:05) |
| Segundos por par (mediana / p90) | 82.7 / 146.8 |
| Tokens de entrada (total / por par) | 1.333.976 / 4.781 |
| Tokens de salida (total / por par) | 513.873 / 1.842 |

## Detalle por trampa

| Trampa | Encontrada | Artículo citado | Artículo verificado | Clase esperada | Clase obtenida | Responsable esperado | Responsable obtenido | Nivel esperado | Nivel obtenido |
|---|---|---|---|---|---|---|---|---|---|
| P3-01-A | otro artículo | NORM_01 Art. 6.3 | sí | Crítico | — | Gerencia de Infraestructura y Vías | — | Alto | — |
| P3-01-M | otro artículo | NORM_01 Art. 2.4 | sí | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P3-01-B | sí | — | sí | Menor | Crítico | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Bajo | Alto |
| P3-02-A | otro artículo | NORM_05 Art. 4.9 | no | Crítico | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Alto | — |
| P3-02-M | sí | — | sí | Mayor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Medio |
| P3-02-B | sí | — | sí | Menor | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Alto |
| P3-03-A | sí | — | sí | Crítico | Crítico | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Alto | Alto |
| P3-03-M | sí | — | sí | Mayor | Crítico | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Alto |
| P3-03-B | sí | — | sí | Menor | Menor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Bajo | Bajo |
| P3-04-A | sí | — | sí | Crítico | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Alto |
| P3-04-M | sí | — | sí | Mayor | Crítico | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Alto |
| P3-04-B | otro artículo | NORM_04 Art. 3.12 | sí | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P3-05-A | otro artículo | NORM_05 Art. 2.10 | no | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P3-05-M | sí | — | sí | Mayor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Medio | Alto |
| P3-05-B | no | — | no | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P4-01-A | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P4-01-M | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Medio |
| P4-01-B | no | — | sí | Menor | — | Gerencia de Infraestructura y Vías | — | Bajo | — |
| P4-02-A | sí | — | sí | Crítico | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P4-02-M | sí | — | sí | Menor | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Alto |
| P4-02-B | sí | — | sí | Menor | Menor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Bajo |
| P4-03-A | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Alto |
| P4-03-M | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Medio |
| P4-03-B | sí | — | sí | Menor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Bajo | Alto |
| P4-04-A | sí | — | sí | Crítico | Crítico | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P4-04-M | sí | — | sí | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Medio |
| P4-04-B | sí | — | sí | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Alto |
| P4-05-A | no | — | no | Crítico | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P4-05-M | sí | — | sí | Mayor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Medio | Alto |
| P4-05-B | sí | — | sí | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Medio |
