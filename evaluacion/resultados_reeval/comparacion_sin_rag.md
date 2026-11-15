# Comparación con RAG (qwen3:8b local (elegida)) frente a sin RAG

## P1–P2 desarrollo

| Métrica | Con RAG | Sin RAG |
|---|---|---|
| Trampas encontradas | 23/30 (77%) (frase y artículo) | 10/30 (33%) por frase, sin validar |
| Falsas alarmas sobre casos conformes (por frase) | 15/60 (25%) | 17/60 (28%) |
| Riesgos / brechas | 173 | 89 |
| Riesgos agrupados | 28 | — |
| Solicitudes | 28 | — |
| Alertas | 16 | — |

Nota: la columna sin RAG usa «por frase», un criterio más laxo que el de la columna con RAG: la diferencia es una cota inferior del aporte del RAG.

Prueba exacta de McNemar (pareada por trampa): solo con RAG 16, solo sin RAG 3, p = 0.0044.

## P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1)

| Métrica | Con RAG | Sin RAG |
|---|---|---|
| Trampas encontradas | 19/30 (63%) (frase y artículo) | 13/30 (43%) por frase, sin validar |
| Falsas alarmas sobre casos conformes (por frase) | 20/60 (33%) | 18/60 (30%) |
| Riesgos / brechas | 169 | 79 |
| Riesgos agrupados | 28 | — |
| Solicitudes | 28 | — |
| Alertas | 21 | — |

Nota: la columna sin RAG usa «por frase», un criterio más laxo que el de la columna con RAG: la diferencia es una cota inferior del aporte del RAG.

Prueba exacta de McNemar (pareada por trampa): solo con RAG 11, solo sin RAG 5, p = 0.2101.

## P1–P4 total

| Métrica | Con RAG | Sin RAG |
|---|---|---|
| Trampas encontradas | 42/60 (70%) (frase y artículo) | 23/60 (38%) por frase, sin validar |
| Falsas alarmas sobre casos conformes (por frase) | 35/120 (29%) | 35/120 (29%) |
| Riesgos / brechas | 342 | 168 |
| Riesgos agrupados | 56 | — |
| Solicitudes | 56 | — |
| Alertas | 37 | — |

Nota: la columna sin RAG usa «por frase», un criterio más laxo que el de la columna con RAG: la diferencia es una cota inferior del aporte del RAG.

Prueba exacta de McNemar (pareada por trampa): solo con RAG 27, solo sin RAG 8, p = 0.0019.
