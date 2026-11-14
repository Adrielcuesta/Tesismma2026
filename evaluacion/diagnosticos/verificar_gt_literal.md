# Verificación del ground truth contra el texto de las ofertas

Niveles: **literal** (la frase tal cual está en el texto extraído de la oferta), **normalizada** (sin mayúsculas ni acentos, «|» y saltos de línea como espacios), **alfanumérica** (solo letras y números; el criterio de la curva). **evaluar.py** dice si `evaluar.norm` (que no quita «|» ni puntuación) encuentra la frase en las oraciones de alguna sección unidas con espacios, como queda la cita de una brecha; en los casos conformes solo cuentan los primeros 60 caracteres. **Curva**: la frase alfanumérica está en una sección que se verifica.

## Resumen por oferta

| Oferta | Tipo | Total | Literal | Normalizada | Alfanumérica | No encontrada | evaluar.py no la ve | la curva no la ubica |
|---|---|---|---|---|---|---|---|---|
| P1 | trampa | 15 | 14 | 1 | 0 | 0 | 0 | 0 |
| P1 | conforme | 32 | 12 | 20 | 0 | 0 | 2 | 0 |
| P2 | trampa | 15 | 10 | 5 | 0 | 0 | 0 | 0 |
| P2 | conforme | 28 | 8 | 20 | 0 | 0 | 0 | 0 |
| P3 | trampa | 15 | 10 | 5 | 0 | 0 | 0 | 0 |
| P3 | conforme | 28 | 19 | 9 | 0 | 0 | 0 | 0 |
| P4 | trampa | 15 | 13 | 2 | 0 | 0 | 0 | 0 |
| P4 | conforme | 32 | 13 | 19 | 0 | 0 | 0 | 0 |

## No encontradas en forma literal (81 de 180)

| Oferta | Tipo | Id | Nivel | evaluar.py | Curva | Sección | Conocido | Frase |
|---|---|---|---|---|---|---|---|---|
| P1 | trampa | P1-04-M | normalizada | sí | sí | S13 |  | pasadas de acabado de 0,5 mm |
| P1 | conforme | P1-C01 | normalizada | sí | sí | S4 |  | hormigón H-35 elaborado en planta, con contenido de cemento Portland de 340 kg/m³, relación agua/cemento 0,45 |
| P1 | conforme | P1-C02 | normalizada | sí | sí | S4 |  | El recubrimiento de armaduras principales será de 40 mm |
| P1 | conforme | P1-C03 | normalizada | sí | sí | S4 |  | se ejecutará contención lateral mediante tablestacado metálico calculado |
| P1 | conforme | P1-C04 | normalizada | sí | sí | S5 |  | relación masa de fundación / masa de máquina de 2,5 |
| P1 | conforme | P1-C05 | normalizada | sí | sí | S4 |  | con registro diario de temperatura ambiente y del hormigón, inicio y fin de cada método de curado |
| P1 | conforme | P1-C07 | normalizada | sí | sí | S7 |  | Poder de corte del interruptor de cabecera ofertado (Icu a 400 V) / 36 kA |
| P1 | conforme | P1-C08 | normalizada | **no** | sí | S7 | sí | Caída de tensión en el tramo terminal / 2,1 % |
| P1 | conforme | P1-C09 | normalizada | **no** | sí | S7 | sí | Conductor de protección PE de la máquina / 25 mm² Cu |
| P1 | conforme | P1-C11 | normalizada | sí | sí | S7 |  | cos φ ≥ 0,96 mediante el banco automático escalonado existente |
| P1 | conforme | P1-C12 | normalizada | sí | sí | S7 |  | 40 % de reserva física en rieles y barras |
| P1 | conforme | P1-C13 | normalizada | sí | sí | S7 |  | Los mandos de uso habitual se ubican entre 0,90 m y 1,45 m sobre el NPT |
| P1 | conforme | P1-C16 | normalizada | sí | sí | S10 |  | Durante toda la maniobra estarán presentes en forma continua el Responsable de Higiene y Seguridad |
| P1 | conforme | P1-C18 | normalizada | sí | sí | S9 |  | no superior a 82 dB(A), medido a 1,00 m de la envolvente y a 1,50 m sobre el piso |
| P1 | conforme | P1-C19 | normalizada | sí | sí | S10 |  | Los ramales se tomarán exclusivamente de los cuatro puntos de izaje indicados por el fabricante |
| P1 | conforme | P1-C21 | normalizada | sí | sí | S12 |  | El levantamiento completo de trocha y nivelación se repetirá después del endurecimiento del hormigón |
| P1 | conforme | P1-C22 | normalizada | sí | sí | S12 |  | Las pasarelas de acceso al pupitre tienen una altura libre de 2,20 m |
| P1 | conforme | P1-C23 | normalizada | sí | sí | S13 |  | La recepción provisoria se otorgará únicamente después de aprobado el SAT bajo carga |
| P1 | conforme | P1-C24 | normalizada | sí | sí | S13 |  | con 3 pares montados reales provistos por el Comitente |
| P1 | conforme | P1-C28 | normalizada | sí | sí | S8 |  | aplicado en tres pasadas (30 %, 60 % y 100 %) en secuencia cruzada |
| P1 | conforme | P1-C31 | normalizada | sí | sí | S12 |  | portones cerrados y registro de temperatura al inicio y al cierre de cada serie, con variación inferior a 1,0 °C |
| P2 | trampa | P2-01-M | normalizada | sí | sí | S4 |  | relación agua/cemento 0,52 |
| P2 | trampa | P2-02-M | normalizada | sí | sí | S6 |  | es de 4,2 %, dentro del 5 % admisible |
| P2 | trampa | P2-02-B | normalizada | sí | sí | S6 |  | 20 % de espacio libre en riel DIN |
| P2 | trampa | P2-04-A | normalizada | sí | sí | S10 |  | prueba de funcionamiento en vacío en sitio |
| P2 | trampa | P2-05-B | normalizada | sí | sí | S7 |  | aceite se presente claro |
| P2 | conforme | P2-C01 | normalizada | sí | sí | S4 |  | hormigón H-35 con contenido de cemento de 330 kg/m³ |
| P2 | conforme | P2-C02 | normalizada | sí | sí | S4 |  | El recubrimiento de armaduras será de 40 mm en todas las caras expuestas a derrames de aceite hidráulico |
| P2 | conforme | P2-C03 | normalizada | sí | sí | S4 |  | durante 28 días corridos antes de posicionar la prensa y aplicar el torque definitivo de anclajes |
| P2 | conforme | P2-C04 | normalizada | sí | sí | S4 |  | Se llevará registro de temperatura ambiente y del hormigón, inicio y fin de cada método de curado e interrupciones |
| P2 | conforme | P2-C05 | normalizada | sí | sí | S5 |  | se ubican a 1,80 m del eje de vía |
| P2 | conforme | P2-C07 | normalizada | sí | sí | S5 |  | en secciones cada 0,50 m (11 secciones) con tres lecturas independientes por sección |
| P2 | conforme | P2-C08 | normalizada | sí | sí | S6 |  | mantiene una reserva de potencia del 41 % |
| P2 | conforme | P2-C09 | normalizada | sí | sí | S6 |  | la tensión en bornes durante el arranque es de 0,88·Un |
| P2 | conforme | P2-C12 | normalizada | sí | sí | S6 |  | Las tomas de mantenimiento estarán protegidas con diferencial de 30 mA |
| P2 | conforme | P2-C13 | normalizada | sí | sí | S6 |  | conductor PE de cobre de 16 mm² |
| P2 | conforme | P2-C14 | normalizada | sí | sí | S6 |  | con el protocolo de la Resolución SRT 900/2015 |
| P2 | conforme | P2-C15 | normalizada | sí | sí | S7 |  | serán sometidas a flushing por circulación forzada antes de conectar el bloque de válvulas proporcionales |
| P2 | conforme | P2-C16 | normalizada | sí | sí | S7 |  | filtro de relación β5(c) ≥ 200 |
| P2 | conforme | P2-C18 | normalizada | sí | sí | S7 |  | calibradas según ISO 6789-2 en los últimos 12 meses |
| P2 | conforme | P2-C19 | normalizada | sí | sí | S7 |  | torque de referencia de 661 N·m aplicado en tres pasadas (30 %, 60 % y 100 %) |
| P2 | conforme | P2-C20 | normalizada | sí | sí | S7 |  | grout epóxico sin contracción de 85 MPa |
| P2 | conforme | P2-C22 | normalizada | sí | sí | S9 |  | hasta una desviación máxima de 0,02 mm/m |
| P2 | conforme | P2-C24 | normalizada | sí | sí | S8 |  | con ángulo de 30° respecto de la vertical |
| P2 | conforme | P2-C25 | normalizada | sí | sí | S8 |  | presentado con 7 días hábiles de anticipación |
| P2 | conforme | P2-C27 | normalizada | sí | sí | S8 |  | estarán presentes de manera continua el Responsable de Higiene y Seguridad y el Supervisor de Montaje |
| P3 | trampa | P3-01-B | normalizada | sí | sí | S4 |  | conformidad verbal del jefe de obra |
| P3 | trampa | P3-03-M | normalizada | sí | sí | S8 |  | permanecerá disponible por radio |
| P3 | trampa | P3-04-M | normalizada | sí | sí | S5 |  | altura libre de 2,00 m |
| P3 | trampa | P3-05-A | normalizada | sí | sí | S7 |  | se apretarán a 2.700 N·m |
| P3 | trampa | P3-05-M | normalizada | sí | sí | S7 |  | mortero cementicio de nivelación de alta resistencia (60 MPa) |
| P3 | conforme | P3-C02 | normalizada | sí | sí | S4 |  | El recubrimiento de armaduras será de 40 mm en caras expuestas a refrigerante |
| P3 | conforme | P3-C03 | normalizada | sí | sí | S4 |  | El curado se extenderá 28 días corridos antes de posicionar la máquina |
| P3 | conforme | P3-C06 | normalizada | sí | sí | S5 |  | con tolerancia de ± 1,5 mm (998,5 a 1.001,5 mm) |
| P3 | conforme | P3-C09 | normalizada | sí | sí | S6 |  | interruptor de cabecera con Icu de 36 kA a 400 V |
| P3 | conforme | P3-C13 | normalizada | sí | sí | S6 |  | 45 % de reserva física |
| P3 | conforme | P3-C14 | normalizada | sí | sí | S6 |  | tomas de mantenimiento con diferencial de 30 mA |
| P3 | conforme | P3-C16 | normalizada | sí | sí | S7 |  | régimen turbulento Re ≥ 4.000 en cada ramal |
| P3 | conforme | P3-C17 | normalizada | sí | sí | S7 |  | tres muestras consecutivas conformes a ISO 4406 17/15/12, separadas 15 minutos |
| P3 | conforme | P3-C26 | normalizada | sí | sí | S10 |  | el acta será firmada por el responsable de Material Rodante como receptor técnico |
| P4 | trampa | P4-02-A | normalizada | sí | sí | S6 |  | diferencial general de 300 mA |
| P4 | trampa | P4-04-A | normalizada | sí | sí | S9 |  | a 2,0 m de la catenaria |
| P4 | conforme | P4-C03 | normalizada | sí | sí | S4 |  | durante 28 días corridos antes del posicionamiento del torno |
| P4 | conforme | P4-C05 | normalizada | sí | sí | S4 |  | ensayo de penetración de agua según IRAM 1554 sobre probetas, con criterio de aceptación ≤ 30 mm |
| P4 | conforme | P4-C06 | normalizada | sí | sí | S5 |  | se liberarán mediante acta firmada por la Inspección del Comitente |
| P4 | conforme | P4-C07 | normalizada | sí | sí | S5 |  | con tolerancia de ± 1,5 mm (1.674,5 a 1.677,5 mm), medida en 11 secciones cada 0,50 m, con tres lecturas por sección |
| P4 | conforme | P4-C08 | normalizada | sí | sí | S5 |  | Se repetirá el levantamiento completo tras el endurecimiento del hormigón |
| P4 | conforme | P4-C09 | normalizada | sí | sí | S5 |  | la altura libre de los pasos peatonales es de 2,15 m |
| P4 | conforme | P4-C10 | normalizada | sí | sí | S6 |  | interruptor de cabecera con Icu de 36 kA a 400 V |
| P4 | conforme | P4-C13 | normalizada | sí | sí | S6 |  | el PE del torno será de cobre de 16 mm² |
| P4 | conforme | P4-C14 | normalizada | sí | sí | S6 |  | tras el montaje se emitirá un nuevo protocolo según la Resolución SRT 900/2015 |
| P4 | conforme | P4-C18 | normalizada | sí | sí | S9 |  | firmado por Ingeniero Mecánico matriculado y presentado con 5 días hábiles de anticipación, con conformidad escrita de la ART |
| P4 | conforme | P4-C20 | normalizada | sí | sí | S9 |  | Los estabilizadores apoyarán sobre planchones metálicos certificados |
| P4 | conforme | P4-C21 | normalizada | sí | sí | S9 |  | Estarán presentes de forma continua el Responsable de Higiene y Seguridad y el Supervisor de Montaje |
| P4 | conforme | P4-C22 | normalizada | sí | sí | S7 |  | se lavarán por circulación forzada antes de conectar las válvulas proporcionales, con Re ≥ 4.000 en cada ramal |
| P4 | conforme | P4-C23 | normalizada | sí | sí | S7 |  | aceptación con tres muestras consecutivas ISO 4406 17/15/12 separadas 10 minutos |
| P4 | conforme | P4-C24 | normalizada | sí | sí | S7 |  | con llave dinamométrica calibrada en los últimos 12 meses |
| P4 | conforme | P4-C25 | normalizada | sí | sí | S7 |  | El grout bajo placas base será epóxico sin contracción de 90 MPa |
| P4 | conforme | P4-C27 | normalizada | sí | sí | S10 |  | portones cerrados y variación de temperatura ≤ 1,0 °C |
| P4 | conforme | P4-C30 | normalizada | sí | sí | S11 |  | La rugosidad se medirá con tres trazas por pieza distribuidas a 120° |
| P4 | conforme | P4-C31 | normalizada | sí | sí | S11 |  | La recepción provisoria se otorgará una vez aprobado el SAT bajo carga |

## Lectura

- Trampas que `evaluar.py` no puede reconocer aunque el sistema cite la oración correcta (la frase, con `evaluar.norm`, no está en las oraciones unidas de ninguna sección): 0.
- Casos conformes que `evaluar.py` no puede reconocer (nunca contarían como falsa alarma): 2.
- Frases que la curva no ubica en ninguna sección que se verifica: 0.

