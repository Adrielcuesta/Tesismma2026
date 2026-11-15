# Curva de recuperación (2026-11-14)

**Calibración OK: la configuración actual del pipeline (K 10, 5 + 5, tope 25, N=2, cupo 8) sobre P1+P2 da Recall@artículo 24/30 y 516 pares, igual que v1.**

- Ofertas: P1, P2. Filas: 30 trampas y 60 casos conformes.
- Base de conocimiento: 410 fragmentos, 393 artículos (norma, artículo), 5 normas.
- Proyecciones: 25.0 s por par en local, 0.00037 USD y 3.3 s por par en la nube. Umbral marginal: 0.5 trampas por cada 100 pares extra (3 pasos seguidos).

## Calibración

| Oferta | Pares con la configuración actual |
|---|---|
| P1 | 303 |
| P2 | 213 |

## Embeddings: tiempos y costo

| Embedding | Indexación (s, n) | Consultas (s, n) | Tokens reales / estimados | USD esta corrida | USD acumulado en caché |
|---|---|---|---|---|---|
| bge-m3 | 0.0, 0 | 57.5, 294 | 0 / 0 | 0.0000 | 0.0000 |
| deepinfra__Qwen-Qwen3-Embedding-8B | 35.0, 410 | 21.1, 294 | 143139 / 0 | 0.0000 | 0.0014 |
| gemini__gemini-embedding-2-3072 | 252.0, 410 | 180.0, 294 | 0 / 143103 | 0.0000 | 0.0286 |

## bge-m3

### solo denso (sin reranker)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | 10 | 677 pares, 4.7 h local, 0.25 USD nube | `(10, 10, 0, 1000000, 2, 8)` |
| K95 | 35 | 1685 pares, 11.7 h local, 0.62 USD nube | `(35, 35, 0, 1000000, 2, 8)` |
| K99 | 200 | 6205 pares, 43.1 h local, 2.30 USD nube | `(200, 200, 0, 1000000, 2, 8)` |
| K100 | 200 | 6205 pares, 43.1 h local, 2.30 USD nube | `(200, 200, 0, 1000000, 2, 8)` |

Recall de trampas en K = 10, 25 y 50: K=10: 27/30 (90%; 74%–97%) | K=25: 28/30 (93%; 79%–98%) | K=50: 29/30 (97%; 83%–99%)

Área bajo la curva (K en escala log, 0–1): 0.877

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: K=10, recall 27/30 (90%; 74%–97%), 677 pares, 4.7 h local, 0.25 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 10, "TOP_DENSA_SUBSECCION": 10, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 39, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- K95: K=35, recall 29/30 (97%; 83%–99%), 1685 pares, 11.7 h local, 0.62 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 35, "TOP_DENSA_SUBSECCION": 35, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 111, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- codo (Kneedle): K=15, recall 28/30 (93%; 79%–98%), 890 pares, 6.2 h local, 0.33 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 15, "TOP_DENSA_SUBSECCION": 15, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 56, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=6, recall 25/30 (83%; 66%–93%), 487 pares, 3.4 h local, 0.18 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 6, "TOP_DENSA_SUBSECCION": 6, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 23, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### denso + reranker (100 candidatos)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | 16 | 868 pares, 6.0 h local, 0.32 USD nube | `(100, 0, 16, 1000000, 2, 8)` |
| K95 | 23 | 1142 pares, 7.9 h local, 0.42 USD nube | `(100, 0, 23, 1000000, 2, 8)` |
| K99 | nunca | — | — |
| K100 | nunca | — | — |

Recall de trampas en K = 10, 25 y 50: K=10: 23/30 (77%; 59%–88%) | K=25: 29/30 (97%; 83%–99%) | K=50: 29/30 (97%; 83%–99%)

Área bajo la curva (K en escala log, 0–1): 0.791

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: K=16, recall 27/30 (90%; 74%–97%), 868 pares, 6.0 h local, 0.32 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 16, "VERIFICAR_TOPE": 56, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- K95: K=23, recall 29/30 (97%; 83%–99%), 1142 pares, 7.9 h local, 0.42 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 23, "VERIFICAR_TOPE": 74, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- codo (Kneedle): K=23, recall 29/30 (97%; 83%–99%), 1142 pares, 7.9 h local, 0.42 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 23, "VERIFICAR_TOPE": 74, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=4, recall 22/30 (73%; 56%–86%), 367 pares, 2.5 h local, 0.14 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 4, "VERIFICAR_TOPE": 15, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### unión denso + reranker (100 candidatos)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | 10 | 884 pares, 6.1 h local, 0.33 USD nube | `(100, 10, 10, 1000000, 2, 8)` |
| K95 | 19 | 1399 pares, 9.7 h local, 0.52 USD nube | `(100, 19, 19, 1000000, 2, 8)` |
| K99 | nunca | — | — |
| K100 | nunca | — | — |

Recall de trampas en K = 10, 25 y 50: K=10: 28/30 (93%; 79%–98%) | K=25: 29/30 (97%; 83%–99%) | K=50: 29/30 (97%; 83%–99%)

Área bajo la curva (K en escala log, 0–1): 0.859

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: K=10, recall 28/30 (93%; 79%–98%), 884 pares, 6.1 h local, 0.33 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 10, "TOP_N_SUBSECCION": 10, "VERIFICAR_TOPE": 54, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- K95: K=19, recall 29/30 (97%; 83%–99%), 1399 pares, 9.7 h local, 0.52 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 19, "TOP_N_SUBSECCION": 19, "VERIFICAR_TOPE": 94, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- codo (Kneedle): K=10, recall 28/30 (93%; 79%–98%), 884 pares, 6.1 h local, 0.33 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 10, "TOP_N_SUBSECCION": 10, "VERIFICAR_TOPE": 54, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=6, recall 26/30 (87%; 70%–95%), 625 pares, 4.3 h local, 0.23 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "bge-m3", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 6, "TOP_N_SUBSECCION": 6, "VERIFICAR_TOPE": 32, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### Grilla de oraciones (ORACIONES_N × ORACIONES_CUPO), en el K de la configuración actual de cada variante

solo denso (sin reranker) (K=10); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 21/30 · 527 | — | — | — | — | — |
| N=1 | 21/30 · 527 | 25/30 · 599 | 27/30 · 625 | 27/30 · 627 | 27/30 · 627 | 27/30 · 627 |
| N=2 | 21/30 · 527 | 25/30 · 614 | 27/30 · 677 | 27/30 · 696 | 28/30 · 721 **←** | 28/30 · 725 |
| N=3 | 21/30 · 527 | 25/30 · 616 | 27/30 · 694 | 27/30 · 726 | 28/30 · 784 | 28/30 · 826 |
| N=5 | 21/30 · 527 | 25/30 · 618 | 27/30 · 703 | 27/30 · 745 | 28/30 · 836 | 28/30 · 1029 |

denso + reranker (100 candidatos) (K=5); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 12/30 · 247 | — | — | — | — | — |
| N=1 | 12/30 · 247 | 16/30 · 329 | 22/30 · 375 | 23/30 · 387 | 24/30 · 393 | 24/30 · 393 |
| N=2 | 12/30 · 247 | 16/30 · 336 | 22/30 · 412 | 23/30 · 442 | 26/30 · 496 | 26/30 · 533 |
| N=3 | 12/30 · 247 | 16/30 · 336 | 22/30 · 420 | 23/30 · 456 | 26/30 · 539 | 28/30 · 671 **←** |
| N=5 | 12/30 · 247 | 16/30 · 338 | 22/30 · 426 | 23/30 · 468 | 26/30 · 567 | 28/30 · 933 |

unión denso + reranker (100 candidatos) (K=5); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 20/30 · 412 | — | — | — | — | — |
| N=1 | 20/30 · 412 | 23/30 · 483 | 25/30 · 513 | 25/30 · 516 | 26/30 · 517 | 26/30 · 517 |
| N=2 | 20/30 · 412 | 23/30 · 498 | 25/30 · 559 | 25/30 · 581 | 26/30 · 613 | 26/30 · 621 |
| N=3 | 20/30 · 412 | 23/30 · 501 | 25/30 · 578 | 25/30 · 608 | 28/30 · 672 **←** | 28/30 · 738 |
| N=5 | 20/30 · 412 | 23/30 · 502 | 25/30 · 588 | 25/30 · 630 | 28/30 · 721 | 28/30 · 965 |

### Referencia: recall usando solo la oración de la fila (no es una tupla del pipeline)

| N artículos de la oración | Trampas | Casos conformes | Total |
|---|---|---|---|
| 1 | 19/30 | 37/60 | 56/90 |
| 2 | 22/30 | 46/60 | 68/90 |
| 3 | 25/30 | 48/60 | 73/90 |
| 5 | 27/30 | 51/60 | 78/90 |

### Filas que no recupera el solo denso en K=50 (sin oraciones)

- P1-C14 (conforme, sección S7, NORM_02 4.15): puesto del artículo en el ranking completo: 55
- P1-C28 (conforme, sección S8, NORM_05 4.5): puesto del artículo en el ranking completo: 54
- P1-C32 (conforme, sección S8, NORM_05 4.8): puesto del artículo en el ranking completo: 194
- P2-04-M (trampa, sección S5, NORM_04 2.6): puesto del artículo en el ranking completo: 63
- P2-04-B (trampa, sección S5, NORM_04 2.13): puesto del artículo en el ranking completo: 175

## deepinfra__Qwen-Qwen3-Embedding-8B

### solo denso (sin reranker)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | 21 | 902 pares, 6.3 h local, 0.33 USD nube | `(21, 21, 0, 1000000, 2, 8)` |
| K95 | 60 | 2050 pares, 14.2 h local, 0.76 USD nube | `(60, 60, 0, 1000000, 2, 8)` |
| K99 | 200 | 5447 pares, 37.8 h local, 2.02 USD nube | `(200, 200, 0, 1000000, 2, 8)` |
| K100 | 200 | 5447 pares, 37.8 h local, 2.02 USD nube | `(200, 200, 0, 1000000, 2, 8)` |

Recall de trampas en K = 10, 25 y 50: K=10: 26/30 (87%; 70%–95%) | K=25: 28/30 (93%; 79%–98%) | K=50: 28/30 (93%; 79%–98%)

Área bajo la curva (K en escala log, 0–1): 0.839

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: K=21, recall 27/30 (90%; 74%–97%), 902 pares, 6.3 h local, 0.33 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-8B", "K_SUBSECCION": 21, "TOP_DENSA_SUBSECCION": 21, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 70, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- K95: K=60, recall 29/30 (97%; 83%–99%), 2050 pares, 14.2 h local, 0.76 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-8B", "K_SUBSECCION": 60, "TOP_DENSA_SUBSECCION": 60, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 147, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- codo (Kneedle): K=24, recall 28/30 (93%; 79%–98%), 1003 pares, 7.0 h local, 0.37 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-8B", "K_SUBSECCION": 24, "TOP_DENSA_SUBSECCION": 24, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 77, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=9, recall 26/30 (87%; 70%–95%), 520 pares, 3.6 h local, 0.19 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-8B", "K_SUBSECCION": 9, "TOP_DENSA_SUBSECCION": 9, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 36, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### denso + reranker (100 candidatos)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | 31 | 1255 pares, 8.7 h local, 0.46 USD nube | `(100, 0, 31, 1000000, 2, 8)` |
| K95 | 84 | 2766 pares, 19.2 h local, 1.02 USD nube | `(100, 0, 84, 1000000, 2, 8)` |
| K99 | nunca | — | — |
| K100 | nunca | — | — |

Recall de trampas en K = 10, 25 y 50: K=10: 24/30 (80%; 63%–90%) | K=25: 26/30 (87%; 70%–95%) | K=50: 28/30 (93%; 79%–98%)

Área bajo la curva (K en escala log, 0–1): 0.706

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: K=31, recall 27/30 (90%; 74%–97%), 1255 pares, 8.7 h local, 0.46 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-8B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 31, "VERIFICAR_TOPE": 91, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- K95: K=84, recall 29/30 (97%; 83%–99%), 2766 pares, 19.2 h local, 1.02 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-8B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 84, "VERIFICAR_TOPE": 189, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- codo (Kneedle): K=11, recall 25/30 (83%; 66%–93%), 593 pares, 4.1 h local, 0.22 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-8B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 11, "VERIFICAR_TOPE": 38, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=11, recall 25/30 (83%; 66%–93%), 593 pares, 4.1 h local, 0.22 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-8B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 11, "VERIFICAR_TOPE": 38, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### unión denso + reranker (100 candidatos)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | 21 | 1251 pares, 8.7 h local, 0.46 USD nube | `(100, 21, 21, 1000000, 2, 8)` |
| K95 | nunca | — | — |
| K99 | nunca | — | — |
| K100 | nunca | — | — |

Recall de trampas en K = 10, 25 y 50: K=10: 26/30 (87%; 70%–95%) | K=25: 28/30 (93%; 79%–98%) | K=50: 28/30 (93%; 79%–98%)

Área bajo la curva (K en escala log, 0–1): 0.774

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: K=21, recall 28/30 (93%; 79%–98%), 1251 pares, 8.7 h local, 0.46 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-8B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 21, "TOP_N_SUBSECCION": 21, "VERIFICAR_TOPE": 91, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- K95: no se alcanza
- codo (Kneedle): K=9, recall 26/30 (87%; 70%–95%), 690 pares, 4.8 h local, 0.26 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-8B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 9, "TOP_N_SUBSECCION": 9, "VERIFICAR_TOPE": 43, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=9, recall 26/30 (87%; 70%–95%), 690 pares, 4.8 h local, 0.26 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-8B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 9, "TOP_N_SUBSECCION": 9, "VERIFICAR_TOPE": 43, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### Grilla de oraciones (ORACIONES_N × ORACIONES_CUPO), en el K de la configuración actual de cada variante

solo denso (sin reranker) (K=10); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 22/30 · 454 | — | — | — | — | — |
| N=1 | 22/30 · 454 | 25/30 · 498 | 25/30 · 502 | 25/30 · 502 | 25/30 · 502 | 25/30 · 502 |
| N=2 | 22/30 · 454 | 25/30 · 523 | 26/30 · 552 | 26/30 · 555 | 26/30 · 560 | 26/30 · 561 |
| N=3 | 22/30 · 454 | 25/30 · 533 | 26/30 · 589 | 26/30 · 604 | 28/30 · 618 | 28/30 · 625 |
| N=5 | 22/30 · 454 | 25/30 · 539 | 26/30 · 611 | 26/30 · 641 | 29/30 · 700 **←** | 29/30 · 749 |

denso + reranker (100 candidatos) (K=5); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 9/30 · 226 | — | — | — | — | — |
| N=1 | 9/30 · 226 | 11/30 · 301 | 16/30 · 333 | 16/30 · 338 | 16/30 · 339 | 16/30 · 339 |
| N=2 | 9/30 · 226 | 11/30 · 314 | 18/30 · 381 | 20/30 · 405 | 21/30 · 431 | 21/30 · 437 |
| N=3 | 9/30 · 226 | 11/30 · 316 | 18/30 · 391 | 20/30 · 426 | 22/30 · 493 | 26/30 · 533 |
| N=5 | 9/30 · 226 | 11/30 · 318 | 18/30 · 406 | 20/30 · 445 | 22/30 · 535 | 27/30 · 735 **←** |

unión denso + reranker (100 candidatos) (K=5); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 16/30 · 372 | — | — | — | — | — |
| N=1 | 16/30 · 372 | 19/30 · 423 | 20/30 · 432 | 20/30 · 432 | 20/30 · 432 | 20/30 · 432 |
| N=2 | 16/30 · 372 | 19/30 · 446 | 23/30 · 487 | 23/30 · 495 | 23/30 · 502 | 23/30 · 502 |
| N=3 | 16/30 · 372 | 19/30 · 455 | 23/30 · 519 | 24/30 · 543 | 25/30 · 573 | 26/30 · 582 |
| N=5 | 16/30 · 372 | 19/30 · 462 | 23/30 · 541 | 24/30 · 575 | 26/30 · 650 | 27/30 · 752 **←** |

### Referencia: recall usando solo la oración de la fila (no es una tupla del pipeline)

| N artículos de la oración | Trampas | Casos conformes | Total |
|---|---|---|---|
| 1 | 16/30 | 38/60 | 54/90 |
| 2 | 20/30 | 45/60 | 65/90 |
| 3 | 24/30 | 50/60 | 74/90 |
| 5 | 25/30 | 53/60 | 78/90 |

### Filas que no recupera el solo denso en K=50 (sin oraciones)

- P1-C11 (conforme, sección S7, NORM_02 1.11): puesto del artículo en el ranking completo: 60
- P2-04-M (trampa, sección S5, NORM_04 2.6): puesto del artículo en el ranking completo: 51
- P2-04-B (trampa, sección S5, NORM_04 2.13): puesto del artículo en el ranking completo: 153
- P2-C11 (conforme, sección S6, NORM_02 4.10): puesto del artículo en el ranking completo: 68

## gemini__gemini-embedding-2-3072

### solo denso (sin reranker)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | 5 | 422 pares, 2.9 h local, 0.16 USD nube | `(5, 5, 0, 1000000, 2, 8)` |
| K95 | 16 | 852 pares, 5.9 h local, 0.32 USD nube | `(16, 16, 0, 1000000, 2, 8)` |
| K99 | 100 | 3498 pares, 24.3 h local, 1.29 USD nube | `(100, 100, 0, 1000000, 2, 8)` |
| K100 | 100 | 3498 pares, 24.3 h local, 1.29 USD nube | `(100, 100, 0, 1000000, 2, 8)` |

Recall de trampas en K = 10, 25 y 50: K=10: 28/30 (93%; 79%–98%) | K=25: 29/30 (97%; 83%–99%) | K=50: 29/30 (97%; 83%–99%)

Área bajo la curva (K en escala log, 0–1): 0.910

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: K=5, recall 27/30 (90%; 74%–97%), 422 pares, 2.9 h local, 0.16 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 5, "TOP_DENSA_SUBSECCION": 5, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 20, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- K95: K=16, recall 29/30 (97%; 83%–99%), 852 pares, 5.9 h local, 0.32 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 16, "TOP_DENSA_SUBSECCION": 16, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 58, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- codo (Kneedle): K=16, recall 29/30 (97%; 83%–99%), 852 pares, 5.9 h local, 0.32 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 16, "TOP_DENSA_SUBSECCION": 16, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 58, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=6, recall 28/30 (93%; 79%–98%), 466 pares, 3.2 h local, 0.17 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 6, "TOP_DENSA_SUBSECCION": 6, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 24, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### denso + reranker (100 candidatos)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | 14 | 763 pares, 5.3 h local, 0.28 USD nube | `(100, 0, 14, 1000000, 2, 8)` |
| K95 | 22 | 1077 pares, 7.5 h local, 0.40 USD nube | `(100, 0, 22, 1000000, 2, 8)` |
| K99 | 72 | 2745 pares, 19.1 h local, 1.02 USD nube | `(100, 0, 72, 1000000, 2, 8)` |
| K100 | 72 | 2745 pares, 19.1 h local, 1.02 USD nube | `(100, 0, 72, 1000000, 2, 8)` |

Recall de trampas en K = 10, 25 y 50: K=10: 25/30 (83%; 66%–93%) | K=25: 29/30 (97%; 83%–99%) | K=50: 29/30 (97%; 83%–99%)

Área bajo la curva (K en escala log, 0–1): 0.765

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: K=14, recall 27/30 (90%; 74%–97%), 763 pares, 5.3 h local, 0.28 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 14, "VERIFICAR_TOPE": 49, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- K95: K=22, recall 29/30 (97%; 83%–99%), 1077 pares, 7.5 h local, 0.40 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 22, "VERIFICAR_TOPE": 74, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- codo (Kneedle): K=22, recall 29/30 (97%; 83%–99%), 1077 pares, 7.5 h local, 0.40 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 22, "VERIFICAR_TOPE": 74, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=4, recall 20/30 (67%; 49%–81%), 355 pares, 2.5 h local, 0.13 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 4, "VERIFICAR_TOPE": 15, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### unión denso + reranker (100 candidatos)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | 5 | 546 pares, 3.8 h local, 0.20 USD nube | `(100, 5, 5, 1000000, 2, 8)` |
| K95 | 12 | 941 pares, 6.5 h local, 0.35 USD nube | `(100, 12, 12, 1000000, 2, 8)` |
| K99 | nunca | — | — |
| K100 | nunca | — | — |

Recall de trampas en K = 10, 25 y 50: K=10: 28/30 (93%; 79%–98%) | K=25: 29/30 (97%; 83%–99%) | K=50: 29/30 (97%; 83%–99%)

Área bajo la curva (K en escala log, 0–1): 0.873

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: K=5, recall 28/30 (93%; 79%–98%), 546 pares, 3.8 h local, 0.20 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 5, "TOP_N_SUBSECCION": 5, "VERIFICAR_TOPE": 28, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- K95: K=12, recall 29/30 (97%; 83%–99%), 941 pares, 6.5 h local, 0.35 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 12, "TOP_N_SUBSECCION": 12, "VERIFICAR_TOPE": 61, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- codo (Kneedle): K=5, recall 28/30 (93%; 79%–98%), 546 pares, 3.8 h local, 0.20 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 5, "TOP_N_SUBSECCION": 5, "VERIFICAR_TOPE": 28, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=5, recall 28/30 (93%; 79%–98%), 546 pares, 3.8 h local, 0.20 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "gemini__gemini-embedding-2-3072", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 5, "TOP_N_SUBSECCION": 5, "VERIFICAR_TOPE": 28, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### Grilla de oraciones (ORACIONES_N × ORACIONES_CUPO), en el K de la configuración actual de cada variante

solo denso (sin reranker) (K=10); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 25/30 · 498 | — | — | — | — | — |
| N=1 | 25/30 · 498 | 27/30 · 563 | 27/30 · 578 | 27/30 · 580 | 27/30 · 581 | 27/30 · 581 |
| N=2 | 25/30 · 498 | 27/30 · 580 | 28/30 · 629 | 29/30 · 642 **←** | 29/30 · 655 | 29/30 · 661 |
| N=3 | 25/30 · 498 | 27/30 · 584 | 28/30 · 656 | 29/30 · 683 | 29/30 · 729 | 29/30 · 751 |
| N=5 | 25/30 · 498 | 27/30 · 586 | 28/30 · 671 | 29/30 · 711 | 29/30 · 799 | 29/30 · 942 |

denso + reranker (100 candidatos) (K=5); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 10/30 · 226 | — | — | — | — | — |
| N=1 | 10/30 · 226 | 13/30 · 308 | 20/30 · 361 | 22/30 · 372 | 22/30 · 379 | 22/30 · 379 |
| N=2 | 10/30 · 226 | 13/30 · 314 | 20/30 · 390 | 23/30 · 422 | 25/30 · 480 | 25/30 · 515 |
| N=3 | 10/30 · 226 | 13/30 · 316 | 20/30 · 399 | 23/30 · 438 | 26/30 · 522 | 29/30 · 650 **←** |
| N=5 | 10/30 · 226 | 13/30 · 318 | 20/30 · 406 | 23/30 · 449 | 26/30 · 549 | 29/30 · 891 |

unión denso + reranker (100 candidatos) (K=5); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 22/30 · 399 | — | — | — | — | — |
| N=1 | 22/30 · 399 | 25/30 · 474 | 27/30 · 496 | 27/30 · 500 | 27/30 · 501 | 27/30 · 501 |
| N=2 | 22/30 · 399 | 25/30 · 484 | 28/30 · 546 | 28/30 · 569 | 29/30 · 594 **←** | 29/30 · 603 |
| N=3 | 22/30 · 399 | 25/30 · 486 | 28/30 · 564 | 28/30 · 597 | 29/30 · 661 | 29/30 · 709 |
| N=5 | 22/30 · 399 | 25/30 · 488 | 28/30 · 574 | 28/30 · 614 | 29/30 · 713 | 29/30 · 921 |

### Referencia: recall usando solo la oración de la fila (no es una tupla del pipeline)

| N artículos de la oración | Trampas | Casos conformes | Total |
|---|---|---|---|
| 1 | 19/30 | 38/60 | 57/90 |
| 2 | 28/30 | 47/60 | 75/90 |
| 3 | 29/30 | 52/60 | 81/90 |
| 5 | 30/30 | 56/60 | 86/90 |

### Filas que no recupera el solo denso en K=50 (sin oraciones)

- P1-C08 (conforme, sección S7, NORM_02 2.16): puesto del artículo en el ranking completo: 53
- P2-04-B (trampa, sección S5, NORM_04 2.13): puesto del artículo en el ranking completo: 99

## Comparación a igual costo (oraciones N=2, cupo 8; punto más cercano en pares)

| Pares objetivo | Embedding | Variante | K | Pares reales | Recall de trampas (IC 95 %) | Tupla |
|---|---|---|---|---|---|---|
| ~400 | bge-m3 | solo denso (sin reranker) | 4 | 387 | 23/30 (77%; 59%–88%) | `(4, 4, 0, 1000000, 2, 8)` |
| ~400 | bge-m3 | denso + reranker (100 candidatos) | 5 | 412 | 22/30 (73%; 56%–86%) | `(100, 0, 5, 1000000, 2, 8)` |
| ~400 | bge-m3 | unión denso + reranker (100 candidatos) | 3 | 426 | 25/30 (83%; 66%–93%) | `(100, 3, 3, 1000000, 2, 8)` |
| ~400 | deepinfra__Qwen-Qwen3-Embedding-8B | solo denso (sin reranker) | 6 | 409 | 22/30 (73%; 56%–86%) | `(6, 6, 0, 1000000, 2, 8)` |
| ~400 | deepinfra__Qwen-Qwen3-Embedding-8B | denso + reranker (100 candidatos) | 5 | 381 | 18/30 (60%; 42%–75%) | `(100, 0, 5, 1000000, 2, 8)` |
| ~400 | deepinfra__Qwen-Qwen3-Embedding-8B | unión denso + reranker (100 candidatos) | 3 | 377 | 22/30 (73%; 56%–86%) | `(100, 3, 3, 1000000, 2, 8)` |
| ~400 | gemini__gemini-embedding-2-3072 | solo denso (sin reranker) | 5 | 422 | 27/30 (90%; 74%–97%) | `(5, 5, 0, 1000000, 2, 8)` |
| ~400 | gemini__gemini-embedding-2-3072 | denso + reranker (100 candidatos) | 5 | 390 | 20/30 (67%; 49%–81%) | `(100, 0, 5, 1000000, 2, 8)` |
| ~400 | gemini__gemini-embedding-2-3072 | unión denso + reranker (100 candidatos) | 3 | 408 | 25/30 (83%; 66%–93%) | `(100, 3, 3, 1000000, 2, 8)` |
| ~516 | bge-m3 | solo denso (sin reranker) | 7 | 533 | 25/30 (83%; 66%–93%) | `(7, 7, 0, 1000000, 2, 8)` |
| ~516 | bge-m3 | denso + reranker (100 candidatos) | 8 | 532 | 22/30 (73%; 56%–86%) | `(100, 0, 8, 1000000, 2, 8)` |
| ~516 | bge-m3 | unión denso + reranker (100 candidatos) | 4 | 494 | 25/30 (83%; 66%–93%) | `(100, 4, 4, 1000000, 2, 8)` |
| ~516 | deepinfra__Qwen-Qwen3-Embedding-8B | solo denso (sin reranker) | 9 | 520 | 26/30 (87%; 70%–95%) | `(9, 9, 0, 1000000, 2, 8)` |
| ~516 | deepinfra__Qwen-Qwen3-Embedding-8B | denso + reranker (100 candidatos) | 9 | 531 | 22/30 (73%; 56%–86%) | `(100, 0, 9, 1000000, 2, 8)` |
| ~516 | deepinfra__Qwen-Qwen3-Embedding-8B | unión denso + reranker (100 candidatos) | 6 | 543 | 23/30 (77%; 59%–88%) | `(100, 6, 6, 1000000, 2, 8)` |
| ~516 | gemini__gemini-embedding-2-3072 | solo denso (sin reranker) | 7 | 510 | 28/30 (93%; 79%–98%) | `(7, 7, 0, 1000000, 2, 8)` |
| ~516 | gemini__gemini-embedding-2-3072 | denso + reranker (100 candidatos) | 8 | 509 | 22/30 (73%; 56%–86%) | `(100, 0, 8, 1000000, 2, 8)` |
| ~516 | gemini__gemini-embedding-2-3072 | unión denso + reranker (100 candidatos) | 5 | 546 | 28/30 (93%; 79%–98%) | `(100, 5, 5, 1000000, 2, 8)` |
| ~700 | bge-m3 | solo denso (sin reranker) | 10 | 677 | 27/30 (90%; 74%–97%) | `(10, 10, 0, 1000000, 2, 8)` |
| ~700 | bge-m3 | denso + reranker (100 candidatos) | 12 | 696 | 24/30 (80%; 63%–90%) | `(100, 0, 12, 1000000, 2, 8)` |
| ~700 | bge-m3 | unión denso + reranker (100 candidatos) | 7 | 694 | 26/30 (87%; 70%–95%) | `(100, 7, 7, 1000000, 2, 8)` |
| ~700 | deepinfra__Qwen-Qwen3-Embedding-8B | solo denso (sin reranker) | 15 | 710 | 26/30 (87%; 70%–95%) | `(15, 15, 0, 1000000, 2, 8)` |
| ~700 | deepinfra__Qwen-Qwen3-Embedding-8B | denso + reranker (100 candidatos) | 14 | 701 | 25/30 (83%; 66%–93%) | `(100, 0, 14, 1000000, 2, 8)` |
| ~700 | deepinfra__Qwen-Qwen3-Embedding-8B | unión denso + reranker (100 candidatos) | 9 | 690 | 26/30 (87%; 70%–95%) | `(100, 9, 9, 1000000, 2, 8)` |
| ~700 | gemini__gemini-embedding-2-3072 | solo denso (sin reranker) | 12 | 704 | 28/30 (93%; 79%–98%) | `(12, 12, 0, 1000000, 2, 8)` |
| ~700 | gemini__gemini-embedding-2-3072 | denso + reranker (100 candidatos) | 13 | 718 | 26/30 (87%; 70%–95%) | `(100, 0, 13, 1000000, 2, 8)` |
| ~700 | gemini__gemini-embedding-2-3072 | unión denso + reranker (100 candidatos) | 8 | 715 | 28/30 (93%; 79%–98%) | `(100, 8, 8, 1000000, 2, 8)` |

## Costo real gastado en API

| Embedding | USD esta corrida | USD acumulado |
|---|---|---|
| bge-m3 | 0.0000 | 0.0000 |
| deepinfra__Qwen-Qwen3-Embedding-8B | 0.0000 | 0.0014 |
| gemini__gemini-embedding-2-3072 | 0.0000 | 0.0286 |

Los embeddings de Gemini se estiman (la API no informa tokens).