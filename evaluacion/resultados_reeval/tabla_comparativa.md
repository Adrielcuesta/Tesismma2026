# Comparación de configuraciones

## P1–P2 desarrollo

| Configuración | Recall estricto (IC 95 %) | Recall@artículo | Falsas alarmas sobre casos conformes | Brechas / oferta | Brechas (total) | Riesgos agrupados / oferta | Precisión humana | Extras etiquetados | Precisión juez estricta | Precisión juez amplia | Control del juez (casos conformes NO_VALIDA) | Kappa de clase | Recall de Críticos | Tiempo (h:mm:ss) | Costo USD | Tokens entrada | Tokens salida |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:8b local (elegida) | 23/30 (77%; 59%–88%) | 28/30 (93%) | 15/60 (25%; 16%–37%) | 86.5 | 173 | 14.0 | n/d (cobertura 0/132) | 0/132 | n/d | n/d | n/d | 0.54 | 8/9 | 3:40:02 | 0.00 | 2.723.753 | 301.027 |
| Qwen3-32B (elegida) | 23/30 (77%; 59%–88%) | 28/30 (93%) | 0/60 (0%; 0%–6%) | 63.0 | 126 | 26.0 | n/d (cobertura 0/101) | 0/101 | n/d | n/d | n/d | 0.25 | 8/9 | 0:13:53 | 0.26 | 2.408.839 | 247.902 |
| gpt-oss-120b esfuerzo bajo (elegida) | 24/30 (80%; 63%–90%) | 28/30 (93%) | 3/60 (5%; 2%–14%) | 55.0 | 110 | 21.0 | 41% | 80/80 | n/d | n/d | n/d | 0.29 | 7/9 | 1:18:31 | 0.37 | 3.653.408 | 1.379.643 |
| qwen3:8b local | 19/30 (63%; 46%–78%) | 24/30 (80%) | 13/60 (22%; 13%–34%) | 67.5 | 135 | 15.5 | n/d (cobertura 0/100) | 0/100 | n/d | n/d | 3/12 (25%) | 0.56 | 8/9 | 3:34:26 | 0.00 | 2.084.934 | 224.149 |
| Qwen3-32B | 20/30 (67%; 49%–81%) | 24/30 (80%) | 1/60 (2%; 0%–9%) | 44.0 | 88 | 23.0 | n/d (cobertura 0/66) | 0/66 | n/d | n/d | n/d | 0.14 | 7/9 | 0:28:17 | 0.19 | 1.804.051 | 180.535 |
| Qwen3-32B con razonamiento | 22/30 (73%; 56%–86%) | 24/30 (80%) | 5/60 (8%; 4%–18%) | 83.5 | 167 | 24.5 | n/d (cobertura 0/138) | 0/138 | n/d | n/d | n/d | 0.08 | 7/9 | 1:47:06 | 0.48 | 2.674.257 | 961.676 |

- Lectura, qwen3:8b local (elegida): precisión humana n/d: hay 0 de 132 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, Qwen3-32B (elegida): precisión humana n/d: hay 0 de 101 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, gpt-oss-120b esfuerzo bajo (elegida): precisión humana 41% = (24 trampas encontradas + 21 extras válidos) / 110 brechas; extras etiquetados 80/80.
- Lectura, qwen3:8b local: precisión humana n/d: hay 0 de 100 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, Qwen3-32B: precisión humana n/d: hay 0 de 66 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, Qwen3-32B con razonamiento: precisión humana n/d: hay 0 de 138 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).

## P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1)

| Configuración | Recall estricto (IC 95 %) | Recall@artículo | Falsas alarmas sobre casos conformes | Brechas / oferta | Brechas (total) | Riesgos agrupados / oferta | Precisión humana | Extras etiquetados | Precisión juez estricta | Precisión juez amplia | Control del juez (casos conformes NO_VALIDA) | Kappa de clase | Recall de Críticos | Tiempo (h:mm:ss) | Costo USD | Tokens entrada | Tokens salida |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:8b local (elegida) | 19/30 (63%; 46%–78%) | 26/30 (87%) | 20/60 (33%; 23%–46%) | 84.5 | 169 | 14.0 | n/d (cobertura 0/129) | 0/129 | n/d | n/d | n/d | 0.24 | 4/7 | 3:29:05 | 0.00 | 2.543.522 | 284.197 |
| Qwen3-32B (elegida) | 19/30 (63%; 46%–78%) | 26/30 (87%) | 1/60 (2%; 0%–9%) | 56.5 | 113 | 26.0 | n/d (cobertura 0/93) | 0/93 | n/d | n/d | n/d | 0.44 | 3/7 | 0:11:18 | 0.23 | 2.090.327 | 211.154 |
| gpt-oss-120b esfuerzo bajo (elegida) | 23/30 (77%; 59%–88%) | 26/30 (87%) | 3/60 (5%; 2%–14%) | 38.0 | 76 | 23.0 | 42% | 50/50 | n/d | n/d | n/d | 0.28 | 6/7 | 1:03:38 | 0.31 | 3.017.238 | 1.193.817 |
| qwen3:8b local | 19/30 (63%; 46%–78%) | 25/30 (83%) | 20/60 (33%; 23%–46%) | 68.5 | 137 | 16.0 | n/d (cobertura 0/98) | 0/98 | n/d | n/d | 10/20 (50%) | 0.24 | 4/7 | 2:44:03 | 0.00 | 1.945.750 | 209.512 |
| Qwen3-32B | 21/30 (70%; 52%–83%) | 25/30 (83%) | 0/60 (0%; 0%–6%) | 40.0 | 80 | 23.5 | n/d (cobertura 0/59) | 0/59 | n/d | n/d | n/d | 0.31 | 4/7 | 0:20:57 | 0.16 | 1.514.612 | 150.839 |
| Qwen3-32B con razonamiento | 20/30 (67%; 49%–81%) | 25/30 (83%) | 8/60 (13%; 7%–24%) | 65.0 | 130 | 26.0 | n/d (cobertura 0/102) | 0/102 | n/d | n/d | n/d | 0.21 | 5/7 | 1:45:59 | 0.41 | 2.207.284 | 831.058 |

- Lectura, qwen3:8b local (elegida): precisión humana n/d: hay 0 de 129 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, Qwen3-32B (elegida): precisión humana n/d: hay 0 de 93 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, gpt-oss-120b esfuerzo bajo (elegida): precisión humana 42% = (23 trampas encontradas + 9 extras válidos) / 76 brechas; extras etiquetados 50/50.
- Lectura, qwen3:8b local: precisión humana n/d: hay 0 de 98 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, Qwen3-32B: precisión humana n/d: hay 0 de 59 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, Qwen3-32B con razonamiento: precisión humana n/d: hay 0 de 102 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).

## P1–P4 total

| Configuración | Recall estricto (IC 95 %) | Recall@artículo | Falsas alarmas sobre casos conformes | Brechas / oferta | Brechas (total) | Riesgos agrupados / oferta | Precisión humana | Extras etiquetados | Precisión juez estricta | Precisión juez amplia | Control del juez (casos conformes NO_VALIDA) | Kappa de clase | Recall de Críticos | Tiempo (h:mm:ss) | Costo USD | Tokens entrada | Tokens salida |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:8b local (elegida) | 42/60 (70%; 57%–80%) | 54/60 (90%) | 35/120 (29%; 22%–38%) | 85.5 | 342 | 14.0 | n/d (cobertura 0/261) | 0/261 | n/d | n/d | n/d | 0.39 | 12/16 | 7:09:08 | 0.00 | 5.267.275 | 585.224 |
| Qwen3-32B (elegida) | 42/60 (70%; 57%–80%) | 54/60 (90%) | 1/120 (1%; 0%–5%) | 59.8 | 239 | 26.0 | n/d (cobertura 0/194) | 0/194 | n/d | n/d | n/d | 0.36 | 11/16 | 0:25:11 | 0.49 | 4.499.166 | 459.056 |
| gpt-oss-120b esfuerzo bajo (elegida) | 47/60 (78%; 66%–87%) | 54/60 (90%) | 6/120 (5%; 2%–10%) | 46.5 | 186 | 22.0 | 41% | 130/130 | n/d | n/d | n/d | 0.27 | 13/16 | 2:22:10 | 0.68 | 6.670.646 | 2.573.460 |
| qwen3:8b local | 38/60 (63%; 51%–74%) | 49/60 (82%) | 33/120 (28%; 20%–36%) | 68.0 | 272 | 15.8 | n/d (cobertura 0/198) | 0/198 | n/d | n/d | 13/32 (41%) | 0.38 | 12/16 | 6:18:30 | 0.00 | 4.030.684 | 433.661 |
| Qwen3-32B | 41/60 (68%; 56%–79%) | 49/60 (82%) | 1/120 (1%; 0%–5%) | 42.0 | 168 | 23.2 | n/d (cobertura 0/125) | 0/125 | n/d | n/d | n/d | 0.26 | 11/16 | 0:49:14 | 0.36 | 3.318.663 | 331.374 |
| Qwen3-32B con razonamiento | 42/60 (70%; 57%–80%) | 49/60 (82%) | 13/120 (11%; 6%–18%) | 74.2 | 297 | 25.2 | n/d (cobertura 0/240) | 0/240 | n/d | n/d | n/d | 0.15 | 12/16 | 3:33:05 | 0.89 | 4.881.541 | 1.792.734 |

- Lectura, qwen3:8b local (elegida): precisión humana n/d: hay 0 de 261 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, Qwen3-32B (elegida): precisión humana n/d: hay 0 de 194 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, gpt-oss-120b esfuerzo bajo (elegida): precisión humana 41% = (47 trampas encontradas + 30 extras válidos) / 186 brechas; extras etiquetados 130/130.
- Lectura, qwen3:8b local: precisión humana n/d: hay 0 de 198 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, Qwen3-32B: precisión humana n/d: hay 0 de 125 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).
- Lectura, Qwen3-32B con razonamiento: precisión humana n/d: hay 0 de 240 extras etiquetados; hay que etiquetar el resto (columna valido de los <json>_extras.csv).

Precisión humana: (trampas encontradas + extras con valido=sí) / brechas; solo se calcula si todos los extras del conjunto están etiquetados (sí/no), si no, n/d con la cobertura. Extras etiquetados: extras con valido sí/no / extras. Recall estricto: trampa encontrada con su frase y su artículo (o uno equivalente); IC de Wilson al 95 %. Precisión según el juez: (trampas encontradas + extras válidos) / brechas; estricta cuenta DUDOSA como no válida, amplia como válida; n/d si faltan veredictos. Control del juez: de las brechas que caen sobre casos conformes (falsos positivos conocidos), cuántas marcó NO_VALIDA (especificidad); n/d si no se corrió «juez --conformes». Falsas alarmas sobre casos conformes: casos conformes marcados como brecha / total de casos conformes. Costo USD: 0 en la corrida local. Kappa de clase: ponderado cuadrático, sobre las trampas encontradas.

## Recuperación elegida frente a v1

### P1–P2 desarrollo

| Configuración (elegida − v1) | Δ recall estricto (pp) | Δ trampas encontradas | Δ trampas no recuperadas (gris) | Δ Recall@artículo | Δ falsas alarmas sobre casos conformes | Δ brechas / oferta | Δ brechas (total) | Δ riesgos agrupados / oferta | Δ pares / oferta | Δ kappa de clase | Δ tiempo | Δ costo USD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:8b local (elegida) − qwen3:8b local | +13.3 | +4 | −4 | +4 | +2 | +19.0 | +38 | −1.5 | +102 | −0.02 | +336 s | 0 |
| Qwen3-32B (elegida) − Qwen3-32B | +10.0 | +3 | −4 | +4 | −1 | +19.0 | +38 | +3.0 | +102 | +0.11 | −864 s | +0.07 |

### P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1)

| Configuración (elegida − v1) | Δ recall estricto (pp) | Δ trampas encontradas | Δ trampas no recuperadas (gris) | Δ Recall@artículo | Δ falsas alarmas sobre casos conformes | Δ brechas / oferta | Δ brechas (total) | Δ riesgos agrupados / oferta | Δ pares / oferta | Δ kappa de clase | Δ tiempo | Δ costo USD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:8b local (elegida) − qwen3:8b local | 0 | 0 | −1 | +1 | 0 | +16.0 | +32 | −2.0 | +84 | −0.00 | +2702 s | 0 |
| Qwen3-32B (elegida) − Qwen3-32B | −6.7 | −2 | −1 | +1 | +1 | +16.5 | +33 | +2.5 | +84 | +0.13 | −579 s | +0.06 |

### P1–P4 total

| Configuración (elegida − v1) | Δ recall estricto (pp) | Δ trampas encontradas | Δ trampas no recuperadas (gris) | Δ Recall@artículo | Δ falsas alarmas sobre casos conformes | Δ brechas / oferta | Δ brechas (total) | Δ riesgos agrupados / oferta | Δ pares / oferta | Δ kappa de clase | Δ tiempo | Δ costo USD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:8b local (elegida) − qwen3:8b local | +6.7 | +4 | −5 | +5 | +2 | +17.5 | +70 | −1.8 | +94 | +0.01 | +3038 s | 0 |
| Qwen3-32B (elegida) − Qwen3-32B | +1.7 | +1 | −5 | +5 | 0 | +17.8 | +71 | +2.8 | +94 | +0.10 | −1443 s | +0.13 |

Lectura: Δ trampas no recuperadas negativo = el gris bajó; Δ falsas alarmas, Δ brechas y Δ riesgos positivos = subió el ruido (el costo de bajar el gris). Δ tiempo en segundos, Δ costo en USD.

## Comparabilidad de la recuperación

Huella de los pares verificados (sha256 de sección, norma, artículo y parte; primeros 10 caracteres) y, entre paréntesis, los pares de cada oferta. Dos configuraciones con la misma huella verificaron exactamente los mismos pares.

| Configuración | Recuperación | P1 | P2 | P3 | P4 |
|---|---|---|---|---|---|
| qwen3:8b local (elegida) | embedding bge-m3, K_SUBSECCION=10, TOP_N=0, TOP_DENSA=10, tope=39 | `d1ab5ed8f2` (425) | `38512457c3` (296) | `a15855cf94` (301) | `7583f27531` (312) |
| Qwen3-32B (elegida) | embedding bge-m3, K_SUBSECCION=10, TOP_N=0, TOP_DENSA=10, tope=39 | `d1ab5ed8f2` (425) | `38512457c3` (296) | `a15855cf94` (301) | `7583f27531` (312) |
| Qwen3-32B con razonamiento (elegida) | n/d | — | — | — | — |
| gpt-oss-120b esfuerzo bajo (elegida) | embedding bge-m3, K_SUBSECCION=10, TOP_N=0, TOP_DENSA=10, tope=39 | `d1ab5ed8f2` (425) | `38512457c3` (296) | `a15855cf94` (301) | `7583f27531` (312) |
| qwen3:8b local | embedding bge-m3, K_SUBSECCION=10, TOP_N=5, TOP_DENSA=5, tope=25 | `525d95df70` (303) | `89f077d757` (213) | `f2fdde25f1` (219) | `8d7229b2aa` (225) |
| Qwen3-32B | embedding bge-m3, K_SUBSECCION=10, TOP_N=5, TOP_DENSA=5, tope=25 | `525d95df70` (303) | `89f077d757` (213) | `f2fdde25f1` (219) | `8d7229b2aa` (225) |
| Qwen3-32B con razonamiento | embedding bge-m3, K_SUBSECCION=10, TOP_N=5, TOP_DENSA=5, tope=25 | `525d95df70` (303) | `89f077d757` (213) | `f2fdde25f1` (219) | `8d7229b2aa` (225) |

Archivo de recuperación reusado (sha256, primeros 12 caracteres): qwen3:8b local (elegida): da9b87b60829, e879479cb6b0, e9dce61b88c0, ffc3cd0879b5; Qwen3-32B (elegida): da9b87b60829, e879479cb6b0, e9dce61b88c0, ffc3cd0879b5; gpt-oss-120b esfuerzo bajo (elegida): da9b87b60829, e879479cb6b0, e9dce61b88c0, ffc3cd0879b5

**AVISO (P1–P2 desarrollo, P1):** las configuraciones comparan recuperaciones distintas: `d1ab5ed8f2`: qwen3:8b local (elegida), Qwen3-32B (elegida), gpt-oss-120b esfuerzo bajo (elegida) | `525d95df70`: qwen3:8b local, Qwen3-32B, Qwen3-32B con razonamiento
**AVISO (P1–P2 desarrollo, P2):** las configuraciones comparan recuperaciones distintas: `38512457c3`: qwen3:8b local (elegida), Qwen3-32B (elegida), gpt-oss-120b esfuerzo bajo (elegida) | `89f077d757`: qwen3:8b local, Qwen3-32B, Qwen3-32B con razonamiento
**AVISO (P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1), P3):** las configuraciones comparan recuperaciones distintas: `a15855cf94`: qwen3:8b local (elegida), Qwen3-32B (elegida), gpt-oss-120b esfuerzo bajo (elegida) | `f2fdde25f1`: qwen3:8b local, Qwen3-32B, Qwen3-32B con razonamiento
**AVISO (P3–P4 prueba (segunda evaluación: el conjunto ya fue visto en v1), P4):** las configuraciones comparan recuperaciones distintas: `7583f27531`: qwen3:8b local (elegida), Qwen3-32B (elegida), gpt-oss-120b esfuerzo bajo (elegida) | `8d7229b2aa`: qwen3:8b local, Qwen3-32B, Qwen3-32B con razonamiento
**AVISO (P1–P4 total, P1):** las configuraciones comparan recuperaciones distintas: `d1ab5ed8f2`: qwen3:8b local (elegida), Qwen3-32B (elegida), gpt-oss-120b esfuerzo bajo (elegida) | `525d95df70`: qwen3:8b local, Qwen3-32B, Qwen3-32B con razonamiento
**AVISO (P1–P4 total, P2):** las configuraciones comparan recuperaciones distintas: `38512457c3`: qwen3:8b local (elegida), Qwen3-32B (elegida), gpt-oss-120b esfuerzo bajo (elegida) | `89f077d757`: qwen3:8b local, Qwen3-32B, Qwen3-32B con razonamiento
**AVISO (P1–P4 total, P3):** las configuraciones comparan recuperaciones distintas: `a15855cf94`: qwen3:8b local (elegida), Qwen3-32B (elegida), gpt-oss-120b esfuerzo bajo (elegida) | `f2fdde25f1`: qwen3:8b local, Qwen3-32B, Qwen3-32B con razonamiento
**AVISO (P1–P4 total, P4):** las configuraciones comparan recuperaciones distintas: `7583f27531`: qwen3:8b local (elegida), Qwen3-32B (elegida), gpt-oss-120b esfuerzo bajo (elegida) | `8d7229b2aa`: qwen3:8b local, Qwen3-32B, Qwen3-32B con razonamiento

## Intervalos de confianza (Wilson 95 %) y recall por oferta

| Configuración | Conjunto total | Recall total | Recall P3+P4 | Falsas alarmas | Precisión humana | Recall por oferta (rango) |
|---|---|---|---|---|---|---|
| qwen3:8b local (elegida) | P1+P2+P3+P4 | 70 % [57–80] | 63 % [46–78] | 29 % [22–38] | n/d | P1 12/15, P2 11/15, P3 8/15, P4 11/15 (rango 53–80 %) |
| Qwen3-32B (elegida) | P1+P2+P3+P4 | 70 % [57–80] | 63 % [46–78] | 1 % [0–5] | n/d | P1 12/15, P2 11/15, P3 9/15, P4 10/15 (rango 60–80 %) |
| gpt-oss-120b esfuerzo bajo (elegida) | P1+P2+P3+P4 | 78 % [66–87] | 77 % [59–88] | 5 % [2–10] | 41 % [35–49] | P1 13/15, P2 11/15, P3 10/15, P4 13/15 (rango 67–87 %) |
| qwen3:8b local | P1+P2+P3+P4 | 63 % [51–74] | 63 % [46–78] | 28 % [20–36] | n/d | P1 10/15, P2 9/15, P3 8/15, P4 11/15 (rango 53–73 %) |
| Qwen3-32B | P1+P2+P3+P4 | 68 % [56–79] | 70 % [52–83] | 1 % [0–5] | n/d | P1 11/15, P2 9/15, P3 9/15, P4 12/15 (rango 60–80 %) |
| Qwen3-32B con razonamiento | P1+P2+P3+P4 | 70 % [57–80] | 67 % [49–81] | 11 % [6–18] | n/d | P1 13/15, P2 9/15, P3 9/15, P4 11/15 (rango 60–87 %) |

Formato: valor [IC 95 % de Wilson], en puntos. Recall total, falsas alarmas, precisión humana y recall por oferta salen del conjunto total de cada configuración (columna «Conjunto total»); Recall P3+P4, del conjunto P3+P4. El rango es el recall mínimo y máximo entre ofertas. Precisión humana n/d si faltan extras por etiquetar.
