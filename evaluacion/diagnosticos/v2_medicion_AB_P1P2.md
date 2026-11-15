# Medición de A y B como postproceso (P1+P2)

| Variante | Trampas encontradas | Brechas | Extras (válidos / no válidos / sin etiquetar) | Precisión humana | Cota (inferior–superior) | Δ vs base (pts) | Trampas perdidas vs base |
|---|---|---|---|---|---|---|---|
| base | 24/30 | 110 | 80 (21 / 59 / 0) | 40.9% (45/110) | 40.9%–40.9% | — | ninguna |
| A | 24/30 | 107 | 77 (20 / 57 / 0) | 41.1% (44/107) | 41.1%–41.1% | +0.2 | ninguna |
| B | 24/30 | 108 | 78 (20 / 58 / 0) | 40.7% (44/108) | 40.7%–40.7% | -0.2 | ninguna |
| A+B | 24/30 | 105 | 75 (19 / 56 / 0) | 41.0% (43/105) | 41.0%–41.0% | +0.0 | ninguna |

La precisión es (trampas encontradas + extras válidos) / brechas que generan riesgo; «n/d» si faltan etiquetas de algún extra (la cota inferior cuenta los sin etiquetar como no válidos y la superior como válidos).

## Qué elimina cada variante respecto de la base (extras por etiqueta)

| Variante | Válidos eliminados | No válidos eliminados | Sin etiqueta eliminados |
|---|---|---|---|
| A | 1 | 2 | 0 |
| B | 1 | 1 | 0 |
| A+B | 2 | 3 | 0 |

## Cobertura de B (etapa_requisito informada por fuente)

| Fuente | Brechas | Con etapa_requisito | Con POSTERIOR |
|---|---|---|---|
| DESVIO | 60 | 20 | 2 |
| EXCEPCION_NO_ACREDITADA | 3 | 2 | 0 |
| INFORMACION_FALTANTE | 47 | 47 | 0 |

B solo puede descartar donde el modelo informó la etapa; el prompt la pide únicamente para INFORMACION_FALTANTE.

## Artículos eliminados por A en estas ofertas (2)

- NORM_01 1.1 «OBJETO Y CARÁCTER»
- NORM_03 7.4 «Orden de prevalencia»

## Criterio de decisión (fijado antes de validar)

- La precisión sube al menos 10 puntos con A+B: +0.0 pts → no cumple
- No se pierde ninguna trampa detectada: cumple
- Conclusión: no se adopta.
