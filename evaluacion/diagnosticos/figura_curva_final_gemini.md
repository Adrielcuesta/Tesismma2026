# Figura final de la curva de recuperación (gemini__gemini-embedding-2-3072)

- Datos: `evaluacion\diagnosticos\curva_recuperacion_2026-11-14.csv` (gemini__gemini-embedding-2-3072, solo denso, N=2, cupo 8, sin tope; 57 puntos, K de 1 a 410; 30 trampas de P1+P2).
- Figura: `figura_curva_final_gemini.png` (300 dpi). Panel A: recall contra pares verificados (log) con USD y horas en ejes secundarios; panel B: ganancia marginal contra K.
- La configuración elegida (28/30, 721 pares) y su validación en P3+P4 son de BGE-M3: no se dibujan con otro embedding, que no tiene perfil elegido.
- Rótulos con el K de cada punto: 56 de 57 (los que no entran sin pisar otro texto quedan sin rótulo; todos los puntos están en el CSV de origen).

## Factores de costo

| Factor | Valor | Origen |
|---|---|---|
| USD por par | 0,00051 | «gpt-oss-120b esfuerzo bajo (elegida)», conjunto «P1–P4 total» (P1+P2+P3+P4): costo_usd 0,6843 / 1.334 pares |
| Segundos por par | 18,0 | argumento --seg-por-par |

## Ajuste recall(p) = 1 − a·p^(−b)

Mínimos cuadrados sobre los 57 puntos de la serie: **a = 1.854,2283**, **b = 1,5723**, **R² = 0,9305** (sobre el recall). La banda del gráfico es el intervalo de Wilson al 95 % de cada punto (n = 30).

## Puntos de referencia

| Punto | K | Pares | Recall (Wilson 95 %) | USD (nube) | Horas (local) |
|---|---|---|---|---|---|
| regla marginal | 6 | 466 | 28/30 (93%; 79%–98%) | 0,24 | 2,3 |
| codo (Kneedle) | 16 | 852 | 29/30 (97%; 83%–99%) | 0,44 | 4,3 |

Los K de referencia son los que da la propia serie de gemini__gemini-embedding-2-3072: regla marginal K = 6, codo de Kneedle K = 16.

## La cola de la curva: pares para las últimas trampas (solo denso, sin tope)

| Trampas | K (primer K medido) | Pares | Costo USD | Horas |
|---|---|---|---|---|
| 28/30 | 6 | 466 | 0,24 | 2,3 |
| 29/30 | 16 | 852 | 0,44 | 4,3 |
| 30/30 | 100 | 3.498 | 1,79 | 17,5 |

- Razón pares para la última trampa ÷ pares para las primeras 28: **7,51** (con el primer K medido que llega a 30/30).
- Los pares que hay que agregar para pasar de 28 a 30 trampas son 6,51 veces los pares de las primeras 28.
- Los valores «medidos» son los de la primera fila de la serie que llega al número de trampas: como la serie salta de K=150 a K=200, son una cota superior de los pares exactos.
- Control con el ajuste: llegar a 98,3 % de recall (punto medio entre 29/30 y 30/30) cuesta ≈1.620 pares; el ajuste no alcanza 100 % nunca.

## Frase para el tribunal

> Con gemini__gemini-embedding-2-3072 en modo solo denso, las primeras 28 de 30 trampas se recuperan verificando 466 pares; la trampa 29 exige 852 pares y la última, 3.498 pares: 7,5 veces los pares de las primeras 28, para sumar 3,3 puntos de recall. Por eso la configuración elegida se detiene antes de esa cola de costo creciente.

