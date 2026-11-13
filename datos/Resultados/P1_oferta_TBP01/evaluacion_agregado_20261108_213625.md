# Evaluación P1+P2

## Recuperación

| Métrica | Valor |
|---|---|
| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | 24/30 (80%), IC 95 % 63%–90% |

## Detección

| Métrica | Valor |
|---|---|
| Recall solo riesgos (frase y artículo) | 19/30 (63%), IC 95 % 46%–78% |
| Recall riesgos + alertas (la alerta de contradicción cita la frase y el artículo) | 19/30 (63%), IC 95 % 46%–78% |
| Precisión | precisión pendiente de revisión |
| F1 | n/d |
| F2 | n/d |
| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | 4/30 (13%) |
| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | 0/30 (0%) |

## Clasificación (de las trampas encontradas)

| Métrica | Valor |
|---|---|
| Exactitud de clase | 12/19 (63%) |
| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | 0.56 |
| Responsable correcto | 19/19 (100%) |

Matriz de confusión de clase (filas: esperada; columnas: obtenida)

| esperada \ obtenida | Crítico | Mayor | Menor |
|---|---|---|---|
| Crítico | 5 | 3 | 0 |
| Mayor | 2 | 6 | 0 |
| Menor | 0 | 2 | 1 |

## Fidelidad

| Métrica | Valor |
|---|---|
| Brechas con alguna marca «valor no verificado» | 43/135 (32%) |

La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas.

## Recall por clase esperada

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Crítico | 9 | 8/9 (89%) | 8/9 (89%) |
| Mayor | 13 | 8/13 (62%) | 8/13 (62%) |
| Menor | 8 | 3/8 (38%) | 3/8 (38%) |

## Recall por nivel esperado

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Alto | 12 | 10/12 (83%) | 10/12 (83%) |
| Medio | 10 | 6/10 (60%) | 6/10 (60%) |
| Bajo | 8 | 3/8 (38%) | 3/8 (38%) |

## Falsas alarmas

| Métrica | Valor |
|---|---|
| Espejos marcados | 12/60 (20%), IC 95 % 12%–32% |

## Volumen

| Concepto | Cantidad |
|---|---|
| Brechas | 135 |
| Riesgos agrupados | 31 |
| Solicitudes | 31 |
| Alertas | 17 |

## Dónde se pierde cada trampa

| Etapa | Trampas |
|---|---|
| no recuperada | 6/30 (20%) |
| perdida en verificación | 4/30 (13%) |
| perdida en clasificación | 0/30 (0%) |
| otra causa | 1/30 (3%) |
| encontrada | 19/30 (63%) |

| Trampa no encontrada | Dónde se pierde | Artículo | Veredicto de verificación | Veredicto de clasificación |
|---|---|---|---|---|
| P1-01-B | otra causa | NORM_01 Art. 6.5 | Incumple | — |
| P1-02-B | perdida en verificación | NORM_02 Art. 5.16 | Cumple | — |
| P1-04-B | no recuperada | NORM_04 Art. 2.5 | — | — |
| P1-05-M | no recuperada | NORM_05 Art. 2.1 | — | — |
| P1-05-B | perdida en verificación | NORM_05 Art. 4.4 | Cumple | — |
| P2-01-M | no recuperada | NORM_01 Art. 3.2 | — | — |
| P2-01-B | no recuperada | NORM_01 Art. 3.7 | — | — |
| P2-02-M | perdida en verificación | NORM_02 Art. 2.16 | Cumple | — |
| P2-03-B | perdida en verificación | NORM_03 Art. 6.2 | Cumple | — |
| P2-04-B | no recuperada | NORM_04 Art. 2.13 | — | — |
| P2-05-A | no recuperada | NORM_05 Art. 1.8 | — | — |

## Costo computacional

**P1**

| Concepto | Valor |
|---|---|
| Modelo | qwen3:8b |
| Hardware | NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB |
| Pares verificados | 303 |
| Llamadas totales (con comentario y reintentos) | 423 |
| Tiempo total | 7.625,7 s (2:07:05) |
| Segundos por par (mediana / p90) | 15.2 / 45.4 |
| Tokens de entrada (total / por par) | 1.233.494 / 4.064 |
| Tokens de salida (total / por par) | 132.910 / 438 |

**P2**

| Concepto | Valor |
|---|---|
| Modelo | qwen3:8b |
| Hardware | NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB |
| Pares verificados | 213 |
| Llamadas totales (con comentario y reintentos) | 299 |
| Tiempo total | 5.240,6 s (1:27:20) |
| Segundos por par (mediana / p90) | 16.2 / 42.5 |
| Tokens de entrada (total / por par) | 851.440 / 3.990 |
| Tokens de salida (total / por par) | 91.239 / 428 |

## Detalle por trampa

| Trampa | Encontrada | Artículo citado | Artículo verificado | Clase esperada | Clase obtenida | Responsable esperado | Responsable obtenido | Nivel esperado | Nivel obtenido |
|---|---|---|---|---|---|---|---|---|---|
| P1-01-A | sí | — | sí | Crítico | Crítico | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P1-01-M | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Medio |
| P1-01-B | otro artículo | NORM_01 Art. 6.3 | sí | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P1-02-A | sí | — | sí | Crítico | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P1-02-M | sí | — | sí | Mayor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Medio | Medio |
| P1-02-B | no | — | sí | Menor | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Bajo | — |
| P1-03-A | sí | — | sí | Crítico | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Alto | Alto |
| P1-03-M | sí | — | sí | Mayor | Crítico | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Alto |
| P1-03-B | sí | — | sí | Menor | Menor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Bajo | Bajo |
| P1-04-A | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Medio |
| P1-04-M | sí | — | sí | Mayor | Crítico | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Alto |
| P1-04-B | otro artículo | NORM_05 Art. 5.3 | no | Menor | — | Gerencia de Infraestructura y Vías | — | Bajo | — |
| P1-05-A | sí | — | sí | Crítico | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Bajo |
| P1-05-M | otro artículo | NORM_05 Art. 5.3 | no | Mayor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P1-05-B | otro artículo | NORM_05 Art. 4.9 | sí | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P2-01-A | sí | — | sí | Crítico | Crítico | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P2-01-M | otro artículo | NORM_04 Art. 2.13 | no | Menor | — | Gerencia de Infraestructura y Vías | — | Bajo | — |
| P2-01-B | otro artículo | NORM_01 Art. 4.5 | no | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P2-02-A | sí | — | sí | Crítico | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P2-02-M | no | — | sí | Mayor | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Medio | — |
| P2-02-B | sí | — | sí | Menor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Medio |
| P2-03-A | sí | — | sí | Crítico | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Alto | Alto |
| P2-03-M | sí | — | sí | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Bajo |
| P2-03-B | otro artículo | NORM_05 Art. 3.4 | sí | Menor | — | Gerencia de Seguridad Operacional y Salud Ocupacional | — | Bajo | — |
| P2-04-A | sí | — | sí | Crítico | Crítico | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Alto |
| P2-04-M | sí | — | sí | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Alto |
| P2-04-B | no | — | no | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P2-05-A | otro artículo | NORM_03 Art. 2.6 | no | Crítico | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P2-05-M | sí | — | sí | Mayor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Medio | Medio |
| P2-05-B | sí | — | sí | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Medio |
