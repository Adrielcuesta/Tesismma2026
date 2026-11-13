# Comparación de configuraciones

## P1–P2 desarrollo

| Configuración | Recall estricto (IC 95 %) | Recall@artículo | Falsas alarmas | Brechas / oferta | Riesgos agrupados / oferta | Precisión juez estricta | Precisión juez amplia | Control del juez (espejos NO_VALIDA) | Kappa de clase | Recall de Críticos | Tiempo (h:mm:ss) | Costo USD | Tokens entrada | Tokens salida |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:8b local | 19/30 (63%; 46%–78%) | 24/30 (80%) | 12/60 (20%; 12%–32%) | 67.5 | 15.5 | n/d | n/d | 3/12 (25%) | 0.56 | 8/9 | 3:34:26 | 0.00 | 2.084.934 | 224.149 |
| Qwen3-32B | 20/30 (67%; 49%–81%) | 24/30 (80%) | 1/60 (2%; 0%–9%) | 44.0 | 23.0 | n/d | n/d | n/d | 0.14 | 7/9 | 0:28:17 | 0.19 | 1.804.051 | 180.535 |
| Qwen3-32B con razonamiento | 22/30 (73%; 56%–86%) | 24/30 (80%) | 5/60 (8%; 4%–18%) | 83.5 | 24.5 | n/d | n/d | n/d | 0.08 | 7/9 | 1:47:06 | 0.48 | 2.674.257 | 961.676 |
| 32B con razonamiento + recuperación amplia | 26/30 (87%; 70%–95%) | 26/30 (87%) | 5/60 (8%; 4%–18%) | 101.0 | 29.5 | n/d | n/d | n/d | 0.45 | 8/9 | 1:23:45 | 0.60 | 3.332.372 | 1.198.161 |

## P3–P4 prueba

| Configuración | Recall estricto (IC 95 %) | Recall@artículo | Falsas alarmas | Brechas / oferta | Riesgos agrupados / oferta | Precisión juez estricta | Precisión juez amplia | Control del juez (espejos NO_VALIDA) | Kappa de clase | Recall de Críticos | Tiempo (h:mm:ss) | Costo USD | Tokens entrada | Tokens salida |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:8b local | 19/30 (63%; 46%–78%) | 25/30 (83%) | 20/60 (33%; 23%–46%) | 68.5 | 16.0 | n/d | n/d | 10/20 (50%) | 0.24 | 4/7 | 2:44:03 | 0.00 | 1.945.750 | 209.512 |
| Qwen3-32B | 21/30 (70%; 52%–83%) | 25/30 (83%) | 0/60 (0%; 0%–6%) | 40.0 | 23.5 | n/d | n/d | n/d | 0.31 | 4/7 | 0:20:57 | 0.16 | 1.514.612 | 150.839 |
| Qwen3-32B con razonamiento | 20/30 (67%; 49%–81%) | 25/30 (83%) | 8/60 (13%; 7%–24%) | 65.0 | 26.0 | n/d | n/d | n/d | 0.21 | 5/7 | 1:45:59 | 0.41 | 2.207.284 | 831.058 |
| 32B con razonamiento + recuperación amplia | 22/30 (73%; 56%–86%) | 26/30 (87%) | 8/60 (13%; 7%–24%) | 81.0 | 29.0 | n/d | n/d | n/d | 0.18 | 4/7 | 2:05:40 | 0.50 | 2.703.623 | 1.029.648 |

## P1–P4 total

| Configuración | Recall estricto (IC 95 %) | Recall@artículo | Falsas alarmas | Brechas / oferta | Riesgos agrupados / oferta | Precisión juez estricta | Precisión juez amplia | Control del juez (espejos NO_VALIDA) | Kappa de clase | Recall de Críticos | Tiempo (h:mm:ss) | Costo USD | Tokens entrada | Tokens salida |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:8b local | 38/60 (63%; 51%–74%) | 49/60 (82%) | 32/120 (27%; 20%–35%) | 68.0 | 15.8 | n/d | n/d | 13/32 (41%) | 0.38 | 12/16 | 6:18:30 | 0.00 | 4.030.684 | 433.661 |
| Qwen3-32B | 41/60 (68%; 56%–79%) | 49/60 (82%) | 1/120 (1%; 0%–5%) | 42.0 | 23.2 | n/d | n/d | n/d | 0.26 | 11/16 | 0:49:14 | 0.36 | 3.318.663 | 331.374 |
| Qwen3-32B con razonamiento | 42/60 (70%; 57%–80%) | 49/60 (82%) | 13/120 (11%; 6%–18%) | 74.2 | 25.2 | n/d | n/d | n/d | 0.15 | 12/16 | 3:33:05 | 0.89 | 4.881.541 | 1.792.734 |
| 32B con razonamiento + recuperación amplia | 48/60 (80%; 68%–88%) | 52/60 (87%) | 13/120 (11%; 6%–18%) | 91.0 | 29.2 | n/d | n/d | n/d | 0.29 | 12/16 | 3:29:25 | 1.11 | 6.035.995 | 2.227.809 |

Recall estricto: trampa encontrada con su frase y su artículo (o uno equivalente); IC de Wilson al 95 %. Precisión según el juez: (trampas encontradas + extras válidos) / brechas; estricta cuenta DUDOSA como no válida, amplia como válida; n/d si faltan veredictos. Control del juez: de las brechas que caen sobre espejos conformes (falsos positivos conocidos), cuántas marcó NO_VALIDA (especificidad); n/d si no se corrió «juez --espejos». Costo USD: 0 en la corrida local. Kappa de clase: ponderado cuadrático, sobre las trampas encontradas.