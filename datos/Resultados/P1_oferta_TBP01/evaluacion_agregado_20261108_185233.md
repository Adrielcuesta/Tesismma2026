# Evaluación P1+P2

## Recuperación

| Métrica | Valor |
|---|---|
| Recall@artículo (el artículo de la trampa o un equivalente se verificó en su sección) | 1/30 (3%), IC 95 % 1%–17% |

## Detección

| Métrica | Valor |
|---|---|
| Recall (frase y artículo) | 19/30 (63%), IC 95 % 46%–78% |
| Precisión | precisión pendiente de revisión |
| F1 | n/d |
| F2 | n/d |
| Pereza de verificación (el artículo llegó a la sección y la verificación dio Cumple o No aplica) | 0/30 (0%) |
| Pereza de clasificación (la verificación dio Incumple o Revisar y la clasificación lo pasó a NO_APLICA o CUMPLE) | 0/30 (0%) |

## Clasificación (de las trampas encontradas)

| Métrica | Valor |
|---|---|
| Exactitud de clase | 12/19 (63%) |
| Kappa ponderado cuadrático (Crítico > Mayor > Menor) | 0.39 |
| Responsable correcto | 19/19 (100%) |

Matriz de confusión de clase (filas: esperada; columnas: obtenida)

| esperada \ obtenida | Crítico | Mayor | Menor |
|---|---|---|---|
| Crítico | 5 | 3 | 0 |
| Mayor | 2 | 6 | 0 |
| Menor | 1 | 1 | 1 |

## Fidelidad

| Métrica | Valor |
|---|---|
| Brechas con alguna marca «valor no verificado» | 46/151 (30%) |

La fidelidad de la cita es del 100 % por diseño: la cita la arma el código a partir de las oraciones numeradas.

## Falsas alarmas

| Métrica | Valor |
|---|---|
| Espejos marcados | 16/60 (27%), IC 95 % 17%–39% |

## Volumen

| Concepto | Cantidad |
|---|---|
| Brechas | 151 |
| Riesgos agrupados | 36 |
| Solicitudes | 36 |
| Alertas | 1 |

## Dónde se pierde cada trampa

| Etapa | Trampas |
|---|---|
| no recuperada | 11/30 (37%) |
| perdida en verificación | 0/30 (0%) |
| perdida en clasificación | 0/30 (0%) |
| encontrada | 19/30 (63%) |

| Trampa no encontrada | Dónde se pierde | Artículo | Veredicto de verificación | Veredicto de clasificación |
|---|---|---|---|---|
| P1-01-B | no recuperada | NORM_01 Art. 6.5 | — | — |
| P1-02-B | no recuperada | NORM_02 Art. 5.16 | — | — |
| P1-04-B | no recuperada | NORM_04 Art. 2.5 | — | — |
| P1-05-M | no recuperada | NORM_05 Art. 2.1 | — | — |
| P1-05-B | no recuperada | NORM_05 Art. 4.4 | — | — |
| P2-01-M | no recuperada | NORM_01 Art. 3.2 | — | — |
| P2-01-B | no recuperada | NORM_01 Art. 3.7 | — | — |
| P2-02-M | no recuperada | NORM_02 Art. 2.16 | — | — |
| P2-03-B | no recuperada | NORM_03 Art. 6.2 | — | — |
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
| P1-01-A | sí | — | no | Crítico | Crítico | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P1-01-M | sí | — | no | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Medio |
| P1-01-B | otro artículo | NORM_01 Art. 6.3 | no | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P1-02-A | sí | — | no | Crítico | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P1-02-M | sí | — | no | Mayor | Mayor | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Medio | Medio |
| P1-02-B | otro artículo | NORM_02 Art. 5.8 | no | Menor | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Bajo | — |
| P1-03-A | sí | — | no | Crítico | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Alto | Alto |
| P1-03-M | sí | — | no | Mayor | Crítico | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Alto |
| P1-03-B | sí | — | sí | Menor | Menor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Bajo | Bajo |
| P1-04-A | sí | — | no | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Medio |
| P1-04-M | sí | — | no | Mayor | Crítico | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Alto |
| P1-04-B | otro artículo | NORM_05 Art. 5.3 | no | Menor | — | Gerencia de Infraestructura y Vías | — | Bajo | — |
| P1-05-A | sí | — | no | Crítico | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Bajo |
| P1-05-M | otro artículo | NORM_05 Art. 5.3 | no | Mayor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P1-05-B | otro artículo | NORM_05 Art. 4.9 | no | Menor | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Bajo | — |
| P2-01-A | sí | — | no | Crítico | Crítico | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Alto | Alto |
| P2-01-M | otro artículo | NORM_04 Art. 2.13 | no | Menor | — | Gerencia de Infraestructura y Vías | — | Bajo | — |
| P2-01-B | otro artículo | NORM_01 Art. 4.5 | no | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P2-02-A | sí | — | no | Crítico | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Alto | Alto |
| P2-02-M | no | — | no | Mayor | — | Gerencia de Energía e Instalaciones Electromecánicas | — | Medio | — |
| P2-02-B | sí | — | no | Menor | Crítico | Gerencia de Energía e Instalaciones Electromecánicas | Gerencia de Energía e Instalaciones Electromecánicas | Bajo | Alto |
| P2-03-A | sí | — | no | Crítico | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Alto | Alto |
| P2-03-M | sí | — | no | Mayor | Mayor | Gerencia de Seguridad Operacional y Salud Ocupacional | Gerencia de Seguridad Operacional y Salud Ocupacional | Medio | Bajo |
| P2-03-B | otro artículo | NORM_05 Art. 3.4 | no | Menor | — | Gerencia de Seguridad Operacional y Salud Ocupacional | — | Bajo | — |
| P2-04-A | sí | — | no | Crítico | Crítico | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Alto | Alto |
| P2-04-M | sí | — | no | Mayor | Mayor | Gerencia de Infraestructura y Vías | Gerencia de Infraestructura y Vías | Medio | Alto |
| P2-04-B | no | — | no | Mayor | — | Gerencia de Infraestructura y Vías | — | Medio | — |
| P2-05-A | otro artículo | NORM_03 Art. 2.6 | no | Crítico | — | Gerencia de Material Rodante y Equipamiento de Talleres | — | Alto | — |
| P2-05-M | sí | — | no | Mayor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Medio | Medio |
| P2-05-B | sí | — | no | Menor | Mayor | Gerencia de Material Rodante y Equipamiento de Talleres | Gerencia de Material Rodante y Equipamiento de Talleres | Bajo | Medio |
