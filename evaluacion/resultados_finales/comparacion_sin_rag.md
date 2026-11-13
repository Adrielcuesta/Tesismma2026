# Comparación con RAG (qwen3:8b local) frente a sin RAG

## P1–P2 desarrollo

| Métrica | Con RAG | Sin RAG |
|---|---|---|
| Trampas encontradas | 19/30 (63%) (frase y artículo) | 10/30 (33%) por frase, sin validar |
| Falsas alarmas (por frase del espejo) | 12/60 (20%) | 17/60 (28%) |
| Riesgos / brechas | 135 | 89 |
| Riesgos agrupados | 31 | — |
| Solicitudes | 31 | — |
| Alertas | 17 | — |

Nota: la columna sin RAG usa «por frase», un criterio más laxo que el de la columna con RAG: la diferencia es una cota inferior del aporte del RAG.

Prueba exacta de McNemar (pareada por trampa): solo con RAG 14, solo sin RAG 5, p = 0.0636.

## P3–P4 prueba

| Métrica | Con RAG | Sin RAG |
|---|---|---|
| Trampas encontradas | 19/30 (63%) (frase y artículo) | 13/30 (43%) por frase, sin validar |
| Falsas alarmas (por frase del espejo) | 20/60 (33%) | 18/60 (30%) |
| Riesgos / brechas | 137 | 79 |
| Riesgos agrupados | 32 | — |
| Solicitudes | 32 | — |
| Alertas | 13 | — |

Nota: la columna sin RAG usa «por frase», un criterio más laxo que el de la columna con RAG: la diferencia es una cota inferior del aporte del RAG.

Prueba exacta de McNemar (pareada por trampa): solo con RAG 11, solo sin RAG 5, p = 0.2101.

## P1–P4 total

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
