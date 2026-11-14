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
| deepinfra__Qwen-Qwen3-Embedding-4B | 30.4, 410 | 15.4, 294 | 143139 / 0 | 0.0000 | 0.0014 |

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

## deepinfra__Qwen-Qwen3-Embedding-4B

### solo denso (sin reranker)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | 100 | 2668 pares, 18.5 h local, 0.99 USD nube | `(100, 100, 0, 1000000, 2, 8)` |
| K95 | 150 | 3924 pares, 27.2 h local, 1.45 USD nube | `(150, 150, 0, 1000000, 2, 8)` |
| K99 | 300 | 7123 pares, 49.5 h local, 2.64 USD nube | `(300, 300, 0, 1000000, 2, 8)` |
| K100 | 300 | 7123 pares, 49.5 h local, 2.64 USD nube | `(300, 300, 0, 1000000, 2, 8)` |

Recall de trampas en K = 10, 25 y 50: K=10: 13/30 (43%; 27%–61%) | K=25: 19/30 (63%; 46%–78%) | K=50: 22/30 (73%; 56%–86%)

Área bajo la curva (K en escala log, 0–1): 0.589

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: K=100, recall 27/30 (90%; 74%–97%), 2668 pares, 18.5 h local, 0.99 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-4B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 100, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 158, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- K95: K=150, recall 29/30 (97%; 83%–99%), 3924 pares, 27.2 h local, 1.45 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-4B", "K_SUBSECCION": 150, "TOP_DENSA_SUBSECCION": 150, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 231, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- codo (Kneedle): K=100, recall 27/30 (90%; 74%–97%), 2668 pares, 18.5 h local, 0.99 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-4B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 100, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 158, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=5, recall 11/30 (37%; 22%–54%), 229 pares, 1.6 h local, 0.08 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-4B", "K_SUBSECCION": 5, "TOP_DENSA_SUBSECCION": 5, "TOP_N_SUBSECCION": 0, "VERIFICAR_TOPE": 16, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### denso + reranker (100 candidatos)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | 78 | 2314 pares, 16.1 h local, 0.86 USD nube | `(100, 0, 78, 1000000, 2, 8)` |
| K95 | nunca | — | — |
| K99 | nunca | — | — |
| K100 | nunca | — | — |

Recall de trampas en K = 10, 25 y 50: K=10: 14/30 (47%; 30%–64%) | K=25: 23/30 (77%; 59%–88%) | K=50: 26/30 (87%; 70%–95%)

Área bajo la curva (K en escala log, 0–1): 0.546

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: K=78, recall 27/30 (90%; 74%–97%), 2314 pares, 16.1 h local, 0.86 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-4B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 78, "VERIFICAR_TOPE": 142, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- K95: no se alcanza
- codo (Kneedle): K=36, recall 26/30 (87%; 70%–95%), 1289 pares, 9.0 h local, 0.48 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-4B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 36, "VERIFICAR_TOPE": 91, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=14, recall 19/30 (63%; 46%–78%), 639 pares, 4.4 h local, 0.24 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-4B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 0, "TOP_N_SUBSECCION": 14, "VERIFICAR_TOPE": 46, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### unión denso + reranker (100 candidatos)

Recall mínimo alcanzado por primera vez (K = K, o k en la unión; tupla = (K_SUBSECCION, TOP_DENSA, TOP_N, VERIFICAR_TOPE, ORACIONES_N, ORACIONES_CUPO)):

| Punto | K | Costo | Tupla del pipeline |
|---|---|---|---|
| K90 | nunca | — | — |
| K95 | nunca | — | — |
| K99 | nunca | — | — |
| K100 | nunca | — | — |

Recall de trampas en K = 10, 25 y 50: K=10: 17/30 (57%; 39%–73%) | K=25: 23/30 (77%; 59%–88%) | K=50: 26/30 (87%; 70%–95%)

Área bajo la curva (K en escala log, 0–1): 0.523

Puntos destacados (con el bloque listo para pegar en `PERFILES_RECUPERACION`; VERIFICAR_TOPE = el mayor tamaño de base de una sección en ese punto, para que el pipeline reproduzca la medición):

- K90: no se alcanza
- K95: no se alcanza
- codo (Kneedle): K=14, recall 20/30 (67%; 49%–81%), 753 pares, 5.2 h local, 0.28 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-4B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 14, "TOP_N_SUBSECCION": 14, "VERIFICAR_TOPE": 55, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```
- umbral marginal < 0.5: K=14, recall 20/30 (67%; 49%–81%), 753 pares, 5.2 h local, 0.28 USD nube
  ```
  "elegido": {"EMBEDDING_BACKEND": "deepinfra__Qwen-Qwen3-Embedding-4B", "K_SUBSECCION": 100, "TOP_DENSA_SUBSECCION": 14, "TOP_N_SUBSECCION": 14, "VERIFICAR_TOPE": 55, "ORACIONES_CIFRAS": True, "ORACIONES_N": 2, "ORACIONES_CUPO": 8}
  ```

### Grilla de oraciones (ORACIONES_N × ORACIONES_CUPO), en el K de la configuración actual de cada variante

solo denso (sin reranker) (K=10); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 11/30 · 271 | — | — | — | — | — |
| N=1 | 11/30 · 271 | 12/30 · 287 | 12/30 · 290 | 12/30 · 290 | 12/30 · 290 | 12/30 · 290 |
| N=2 | 11/30 · 271 | 12/30 · 313 | 13/30 · 320 | 13/30 · 320 | 13/30 · 320 | 13/30 · 320 |
| N=3 | 11/30 · 271 | 13/30 · 330 | 15/30 · 345 **←** | 15/30 · 345 | 15/30 · 345 | 15/30 · 345 |
| N=5 | 11/30 · 271 | 13/30 · 350 | 15/30 · 400 | 15/30 · 409 | 15/30 · 419 | 15/30 · 420 |

denso + reranker (100 candidatos) (K=5); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 7/30 · 215 | — | — | — | — | — |
| N=1 | 7/30 · 215 | 8/30 · 280 | 9/30 · 292 | 9/30 · 292 | 9/30 · 292 | 9/30 · 292 |
| N=2 | 7/30 · 215 | 8/30 · 300 | 10/30 · 346 | 10/30 · 356 | 11/30 · 361 | 11/30 · 361 |
| N=3 | 7/30 · 215 | 8/30 · 306 | 10/30 · 372 | 11/30 · 397 | 13/30 · 414 | 13/30 · 414 |
| N=5 | 7/30 · 215 | 8/30 · 307 | 10/30 · 390 | 11/30 · 426 | 14/30 · 492 **←** | 14/30 · 510 |

unión denso + reranker (100 candidatos) (K=5); celdas «trampas · pares», **←** = mejor (más trampas, a igual cantidad menos pares):

|  | cupo 0 | cupo 4 | cupo 8 | cupo 10 | cupo 15 | sin tope |
|---|---|---|---|---|---|---|
| N=0 | 10/30 · 305 | — | — | — | — | — |
| N=1 | 10/30 · 305 | 11/30 · 332 | 11/30 · 335 | 11/30 · 335 | 11/30 · 335 | 11/30 · 335 |
| N=2 | 10/30 · 305 | 11/30 · 368 | 12/30 · 381 | 12/30 · 383 | 12/30 · 383 | 12/30 · 383 |
| N=3 | 10/30 · 305 | 11/30 · 383 | 13/30 · 420 | 14/30 · 426 **←** | 14/30 · 426 | 14/30 · 426 |
| N=5 | 10/30 · 305 | 11/30 · 395 | 13/30 · 465 | 14/30 · 489 | 14/30 · 510 | 14/30 · 515 |

### Referencia: recall usando solo la oración de la fila (no es una tupla del pipeline)

| N artículos de la oración | Trampas | Casos conformes | Total |
|---|---|---|---|
| 1 | 4/30 | 11/60 | 15/90 |
| 2 | 6/30 | 15/60 | 21/90 |
| 3 | 8/30 | 17/60 | 25/90 |
| 5 | 10/30 | 22/60 | 32/90 |

### Filas que no recupera el solo denso en K=50 (sin oraciones)

- P1-01-B (trampa, sección S6, NORM_01 6.5): puesto del artículo en el ranking completo: 126
- P1-03-M (trampa, sección S10, NORM_03 2.6): puesto del artículo en el ranking completo: 83
- P1-C10 (conforme, sección S7, NORM_02 1.10): puesto del artículo en el ranking completo: 51
- P1-C11 (conforme, sección S7, NORM_02 1.11): puesto del artículo en el ranking completo: 111
- P1-C12 (conforme, sección S7, NORM_02 4.7): puesto del artículo en el ranking completo: 71
- P1-C13 (conforme, sección S7, NORM_02 4.10): puesto del artículo en el ranking completo: 87
- P1-C14 (conforme, sección S7, NORM_02 4.15): puesto del artículo en el ranking completo: 85
- P1-C15 (conforme, sección S10, NORM_03 4.7): puesto del artículo en el ranking completo: 87
- P1-C21 (conforme, sección S12, NORM_04 2.13): puesto del artículo en el ranking completo: 63
- P1-C28 (conforme, sección S8, NORM_05 4.5): puesto del artículo en el ranking completo: 126
- P1-C29 (conforme, sección S8, NORM_05 4.3): puesto del artículo en el ranking completo: 121
- P1-C30 (conforme, sección S8, NORM_05 2.9): puesto del artículo en el ranking completo: 92
- P1-C31 (conforme, sección S12, NORM_05 2.3): puesto del artículo en el ranking completo: 51
- P1-C32 (conforme, sección S8, NORM_05 4.8): puesto del artículo en el ranking completo: 56
- P2-01-M (trampa, sección S4, NORM_01 3.2): puesto del artículo en el ranking completo: 142
- P2-01-B (trampa, sección S4, NORM_01 3.7): puesto del artículo en el ranking completo: 65
- P2-02-A (trampa, sección S6, NORM_02 3.13): puesto del artículo en el ranking completo: 89
- P2-02-B (trampa, sección S6, NORM_02 4.7): puesto del artículo en el ranking completo: 62
- P2-04-M (trampa, sección S5, NORM_04 2.6): puesto del artículo en el ranking completo: 69
- P2-04-B (trampa, sección S5, NORM_04 2.13): puesto del artículo en el ranking completo: 246
- P2-C02 (conforme, sección S4, NORM_01 3.5): puesto del artículo en el ranking completo: 66
- P2-C07 (conforme, sección S5, NORM_04 2.5): puesto del artículo en el ranking completo: 52
- P2-C11 (conforme, sección S6, NORM_02 4.10): puesto del artículo en el ranking completo: 117
- P2-C12 (conforme, sección S6, NORM_02 4.15): puesto del artículo en el ranking completo: 84
- P2-C19 (conforme, sección S7, NORM_05 4.3; NORM_05 4.5): puesto del artículo en el ranking completo: 67
- P2-C20 (conforme, sección S7, NORM_05 2.9): puesto del artículo en el ranking completo: 123
- P2-C24 (conforme, sección S8, NORM_03 2.6): puesto del artículo en el ranking completo: 124
- P2-C25 (conforme, sección S8, NORM_03 5.1): puesto del artículo en el ranking completo: 52
- P2-C28 (conforme, sección S8, NORM_03 4.7): puesto del artículo en el ranking completo: 113

## Comparación a igual costo (oraciones N=2, cupo 8; punto más cercano en pares)

| Pares objetivo | Embedding | Variante | K | Pares reales | Recall de trampas (IC 95 %) | Tupla |
|---|---|---|---|---|---|---|
| ~400 | bge-m3 | solo denso (sin reranker) | 4 | 387 | 23/30 (77%; 59%–88%) | `(4, 4, 0, 1000000, 2, 8)` |
| ~400 | bge-m3 | denso + reranker (100 candidatos) | 5 | 412 | 22/30 (73%; 56%–86%) | `(100, 0, 5, 1000000, 2, 8)` |
| ~400 | bge-m3 | unión denso + reranker (100 candidatos) | 3 | 426 | 25/30 (83%; 66%–93%) | `(100, 3, 3, 1000000, 2, 8)` |
| ~400 | deepinfra__Qwen-Qwen3-Embedding-4B | solo denso (sin reranker) | 14 | 406 | 15/30 (50%; 33%–67%) | `(14, 14, 0, 1000000, 2, 8)` |
| ~400 | deepinfra__Qwen-Qwen3-Embedding-4B | denso + reranker (100 candidatos) | 6 | 386 | 13/30 (43%; 27%–61%) | `(100, 0, 6, 1000000, 2, 8)` |
| ~400 | deepinfra__Qwen-Qwen3-Embedding-4B | unión denso + reranker (100 candidatos) | 5 | 381 | 12/30 (40%; 25%–58%) | `(100, 5, 5, 1000000, 2, 8)` |
| ~516 | bge-m3 | solo denso (sin reranker) | 7 | 533 | 25/30 (83%; 66%–93%) | `(7, 7, 0, 1000000, 2, 8)` |
| ~516 | bge-m3 | denso + reranker (100 candidatos) | 8 | 532 | 22/30 (73%; 56%–86%) | `(100, 0, 8, 1000000, 2, 8)` |
| ~516 | bge-m3 | unión denso + reranker (100 candidatos) | 4 | 494 | 25/30 (83%; 66%–93%) | `(100, 4, 4, 1000000, 2, 8)` |
| ~516 | deepinfra__Qwen-Qwen3-Embedding-4B | solo denso (sin reranker) | 18 | 522 | 17/30 (57%; 39%–73%) | `(18, 18, 0, 1000000, 2, 8)` |
| ~516 | deepinfra__Qwen-Qwen3-Embedding-4B | denso + reranker (100 candidatos) | 10 | 516 | 14/30 (47%; 30%–64%) | `(100, 0, 10, 1000000, 2, 8)` |
| ~516 | deepinfra__Qwen-Qwen3-Embedding-4B | unión denso + reranker (100 candidatos) | 8 | 506 | 15/30 (50%; 33%–67%) | `(100, 8, 8, 1000000, 2, 8)` |
| ~700 | bge-m3 | solo denso (sin reranker) | 10 | 677 | 27/30 (90%; 74%–97%) | `(10, 10, 0, 1000000, 2, 8)` |
| ~700 | bge-m3 | denso + reranker (100 candidatos) | 12 | 696 | 24/30 (80%; 63%–90%) | `(100, 0, 12, 1000000, 2, 8)` |
| ~700 | bge-m3 | unión denso + reranker (100 candidatos) | 7 | 694 | 26/30 (87%; 70%–95%) | `(100, 7, 7, 1000000, 2, 8)` |
| ~700 | deepinfra__Qwen-Qwen3-Embedding-4B | solo denso (sin reranker) | 24 | 695 | 19/30 (63%; 46%–78%) | `(24, 24, 0, 1000000, 2, 8)` |
| ~700 | deepinfra__Qwen-Qwen3-Embedding-4B | denso + reranker (100 candidatos) | 16 | 703 | 19/30 (63%; 46%–78%) | `(100, 0, 16, 1000000, 2, 8)` |
| ~700 | deepinfra__Qwen-Qwen3-Embedding-4B | unión denso + reranker (100 candidatos) | 13 | 714 | 18/30 (60%; 42%–75%) | `(100, 13, 13, 1000000, 2, 8)` |

## Costo real gastado en API

| Embedding | USD esta corrida | USD acumulado |
|---|---|---|
| bge-m3 | 0.0000 | 0.0000 |
| deepinfra__Qwen-Qwen3-Embedding-4B | 0.0000 | 0.0014 |

Los embeddings de Gemini se estiman (la API no informa tokens).