# Figura final de la curva de recuperación

- Datos: `evaluacion\diagnosticos\curva_recuperacion_2026-11-14.csv` (BGE-M3, solo denso, N=2, cupo 8, sin tope; 57 puntos, K de 1 a 410; 30 trampas de P1+P2).
- Figura: `figura_curva_final.png` (300 dpi). Panel A: recall contra pares verificados (log) con USD y horas en ejes secundarios; panel B: ganancia marginal contra K.
- Rótulos con el K de cada punto: 56 de 57 (los que no entran sin pisar otro texto quedan sin rótulo; todos los puntos están en el CSV de origen).

## Factores de costo

| Factor | Valor | Origen |
|---|---|---|
| USD por par | 0,00051 | «gpt-oss-120b esfuerzo bajo (elegida)», conjunto «P1–P4 total» (P1+P2+P3+P4): costo_usd 0,6843 / 1.334 pares |
| Segundos por par | 23,7 | «qwen3:8b local», conjunto «P1–P4 total» (P1+P2+P3+P4): tiempo_s 22.710 / 960 pares |

## Ajuste recall(p) = 1 − a·p^(−b)

Mínimos cuadrados sobre los 57 puntos de la serie: **a = 176,1406**, **b = 1,1161**, **R² = 0,9698** (sobre el recall). La banda del gráfico es el intervalo de Wilson al 95 % de cada punto (n = 30).

## Puntos de referencia

| Punto | K | Pares | Recall (Wilson 95 %) | USD (nube) | Horas (local) |
|---|---|---|---|---|---|
| regla marginal | 6 | 487 | 25/30 (83%; 66%–93%) | 0,25 | 3,2 |
| elegido | 10 | 677 | 27/30 (90%; 74%–97%) | 0,35 | 4,4 |
| codo (Kneedle) | 15 | 890 | 28/30 (93%; 79%–98%) | 0,46 | 5,8 |
| **configuración elegida** (constante) | 10 (cupo 15, tope 39) | 721 | 28/30 (93%; 79%–98%) | 0,37 | 4,7 |
| validación de la elegida en P3+P4 (constante) | — | 613 | 26/30 (87%; 70%–95%) | 0,31 | 4,0 |

Origen de las constantes: la elegida (28/30, 721 pares, K=10, cupo 15, tope 39) es la del commit 9e7a8ab y del informe de la curva; el 26/30 en P3+P4 es la validación de la elegida y dibuja en 613 pares («Qwen3-32B (elegida)», conjunto «P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1)»: 306 pares por oferta × 2).

## Verificación de los K de referencia

- Regla marginal calculada aquí: K = 6 (esperado 6).
- Codo de Kneedle calculado aquí: K = 15 (esperado 15).

## La cola de la curva: pares para las últimas trampas (solo denso, sin tope)

| Trampas | K (primer K medido) | Pares | Costo USD | Horas |
|---|---|---|---|---|
| 28/30 | 15 | 890 | 0,46 | 5,8 |
| 29/30 | 35 | 1.685 | 0,86 | 11,1 |
| 30/30 | 200 | 6.205 | 3,18 | 40,8 |
| 30/30 en el puesto exacto 175 (interpolado) | 175 | 5.662 | 2,90 | 37,2 |

- Razón pares para la última trampa ÷ pares para las primeras 28: **6,97** (con el primer K medido que llega a 30/30; 6,36 con el puesto exacto 175 interpolado).
- Los pares que hay que agregar para pasar de 28 a 30 trampas son 5,97 veces los pares de las primeras 28.
- Los valores «medidos» son los de la primera fila de la serie que llega al número de trampas: como la serie salta de K=150 a K=200, son una cota superior de los pares exactos.
- Control con el ajuste: llegar a 98,3 % de recall (punto medio entre 29/30 y 30/30) cuesta ≈4.030 pares; el ajuste no alcanza 100 % nunca.

## Frase para el tribunal

> Con BGE-M3 en modo solo denso, las primeras 28 de 30 trampas se recuperan verificando 890 pares; la trampa 29 exige 1.685 pares y la última, 6.205 pares (≈5.662 si se corta exactamente en el puesto 175 de su ranking, interpolado): 7,0 veces los pares de las primeras 28, para sumar 3,3 puntos de recall. Por eso la configuración elegida se detiene antes de esa cola de costo creciente.

