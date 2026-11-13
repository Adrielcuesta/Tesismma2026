# Evaluación P1+P2+P3+P4

## Recuperación

| Métrica | Valor |
|---|---|
| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | 49/60 (82%), IC 95 % 70%–89% |

## Detección

| Métrica | Valor |
|---|---|
| Recall solo riesgos (frase y artículo) | 38/60 (63%), IC 95 % 51%–74% |
| Recall riesgos + alertas (la alerta de contradicción cita la frase y el artículo) | 39/60 (65%), IC 95 % 52%–76% |
| Precisión | precisión pendiente de revisión |
| F1 | n/d |
| F2 | n/d |
| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | 8/60 (13%) |
| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | 0/60 (0%) |

## Clasificación (de las trampas encontradas)

| Métrica | Valor |
|---|---|
| Exactitud de clase | 20/38 (53%) |
| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | 0.38 |
| Responsable correcto | 38/38 (100%) |

Matriz de confusión de clase (filas: esperada; columnas: obtenida)

| esperada \ obtenida | Crítico | Mayor | Menor |
|---|---|---|---|
| Crítico | 7 | 5 | 0 |
| Mayor | 5 | 10 | 1 |
| Menor | 2 | 5 | 3 |

## Fidelidad

| Métrica | Valor |
|---|---|
| Brechas con alguna marca «valor no verificado» | 90/272 (33%) |

La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas.

## Recall por clase esperada

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Crítico | 16 | 12/16 (75%) | 13/16 (81%) |
| Mayor | 23 | 16/23 (70%) | 16/23 (70%) |
| Menor | 21 | 10/21 (48%) | 10/21 (48%) |

## Recall por nivel esperado

| Esperada | Trampas | Solo riesgos | Riesgos + alertas |
|---|---|---|---|
| Alto | 21 | 16/21 (76%) | 17/21 (81%) |
| Medio | 18 | 12/18 (67%) | 12/18 (67%) |
| Bajo | 21 | 10/21 (48%) | 10/21 (48%) |

## Falsas alarmas

| Métrica | Valor |
|---|---|
| Espejos marcados | 32/120 (27%), IC 95 % 20%–35% |

## Volumen

| Concepto | Cantidad |
|---|---|
| Brechas | 272 |
| Riesgos agrupados | 63 |
| Solicitudes | 63 |
| Alertas | 30 |

## Dónde se pierde cada trampa

| Etapa | Trampas |
|---|---|
| no recuperada | 11/60 (18%) |
| perdida en verificación | 8/60 (13%) |
| perdida en clasificación | 0/60 (0%) |
| otra causa | 3/60 (5%) |
| encontrada | 38/60 (63%) |

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
| Trampas encontradas | 38/60 (63%) (frase y artículo) | 23/60 (38%) por frase, sin validar |
| Falsas alarmas (por frase del espejo) | 32/120 (27%) | 35/120 (29%) |
| Riesgos / brechas | 272 | 168 |
| Riesgos agrupados | 63 | — |
| Solicitudes | 63 | — |
| Alertas | 30 | — |

Nota: la columna sin RAG usa «por frase», un criterio más laxo que el de la columna con RAG: la diferencia es una cota inferior del aporte del RAG.

Prueba exacta de McNemar (pareada por trampa): solo con RAG 25, solo sin RAG 10, p = 0.0167.
