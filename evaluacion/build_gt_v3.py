"""Construye evaluacion/ground_truth_v3.csv: las 60 trampas clasificadas con NORM_07 (versión del 7/11, criterio de Adriel).

Uso: python evaluacion/build_gt_v3.py  (escribe ground_truth_v3.csv en la misma carpeta)

La clase sale de reglas explícitas (misma lógica que usará reglas_norm07.py):
  1. condicion_critico a/b/c/d                    -> Crítico  (Art. 3.2)
  2. objeto DOCUMENTAL_PROCEDIMIENTO              -> Menor    (Art. 3.4.c)
  3. objeto RESERVA_ERGONOMIA_EFICIENCIA          -> Menor    (Art. 3.4.d)
  4. objeto VERIFICACION_RUTINA                   -> Menor    (Art. 3.4.b)
  5. objeto ENSAYO_ACEPTACION                     -> Mayor    (Art. 3.3.b)
  6. objeto ORDINAL                               -> Mayor    (Art. 3.3.d)
  7. objeto CUANTITATIVO_TECNICO: brecha >= 25 %  -> Mayor (3.3.a);
     < 25 % con riesgo para personas -> Mayor (3.3.e); < 25 % sin riesgo para personas -> Menor (3.4.a)
  8. objeto OTRO_TECNICO                          -> Mayor    (Art. 3.3.c)
Probabilidad por fuente (Art. 4.2), nivel por matriz (Art. 5.1) y consistencia (Art. 5.3).
"""
import csv

# id; oferta; seccion; fragmento_trampa; norma; articulo; responsable (NORM_06)
MAPA = """P1-01-A;P1;3.5 Optimización del plazo de la obra civil;posicionar el torno sobre sus apoyos a los 14 días;NORM_01;4.2;Gerencia de Infraestructura y Vías
P1-01-M;P1;3.6 Fosa: accesos, achique y estanqueidad;escalera portátil de aluminio;NORM_01;6.3;Gerencia de Infraestructura y Vías
P1-01-B;P1;3.6 Fosa: accesos, achique y estanqueidad;prueba de inundación de 24 h;NORM_01;6.5;Gerencia de Infraestructura y Vías
P1-02-A;P1;4.3 Puesta a tierra y compatibilidad electromagnética;jabalina dedicada exclusiva;NORM_02;5.4;Gerencia de Energía e Instalaciones Electromecánicas
P1-02-M;P1;4.2 Tableros seccionales;serán IP54;NORM_02;4.5;Gerencia de Energía e Instalaciones Electromecánicas
P1-02-B;P1;4.3 Puesta a tierra y compatibilidad electromagnética;marzo de 2025;NORM_02;5.16;Gerencia de Energía e Instalaciones Electromecánicas
P1-03-A;P1;5.1 Descripción de la maniobra principal;utilización resultante es del 87 %;NORM_03;2.2;Gerencia de Seguridad Operacional y Salud Ocupacional
P1-03-M;P1;5.2 Eslingado y accesorios;ángulo de 55°;NORM_03;2.6;Gerencia de Seguridad Operacional y Salud Ocupacional
P1-03-B;P1;5.4 Supervisión y documentación;48 horas de anticipación;NORM_03;5.1;Gerencia de Seguridad Operacional y Salud Ocupacional
P1-04-A;P1;6.3 Control geométrico de la vía de aproximación;ajustada a ± 3 mm;NORM_04;2.3;Gerencia de Infraestructura y Vías
P1-04-M;P1;7.2 SAT bajo carga;pasadas de acabado de 0,5 mm;NORM_04;3.8;Gerencia de Material Rodante y Equipamiento de Talleres
P1-04-B;P1;6.3 Control geométrico de la vía de aproximación;lecturas de trocha cada 1,0 m;NORM_04;2.5;Gerencia de Infraestructura y Vías
P1-05-A;P1;4.4 Sistema oleohidráulico;servoválvulas se conectarán directamente;NORM_05;3.4;Gerencia de Material Rodante y Equipamiento de Talleres
P1-05-M;P1;6.1 Nivelación de la bancada;se ajustará a 0,05 mm/m;NORM_05;2.1;Gerencia de Material Rodante y Equipamiento de Talleres
P1-05-B;P1;4.5 Bulonería, anclajes y grout;plan bienal de calibraciones;NORM_05;4.4;Gerencia de Material Rodante y Equipamiento de Talleres
P2-01-A;P2;2.2 Implantación sobre la losa existente;prensa anterior de 22 t;NORM_01;5.2;Gerencia de Infraestructura y Vías
P2-01-M;P2;3.2 Hormigón de bloques de anclaje y losa de vía;relación agua/cemento 0,52;NORM_01;3.2;Gerencia de Infraestructura y Vías
P2-01-B;P2;3.2 Hormigón de bloques de anclaje y losa de vía;ensayo esclerométrico a los 28 días;NORM_01;3.7;Gerencia de Infraestructura y Vías
P2-02-A;P2;4.2 Tablero de la prensa;será de 25 kA;NORM_02;3.13;Gerencia de Energía e Instalaciones Electromecánicas
P2-02-M;P2;4.1 Instalación eléctrica;es de 4,2 %, dentro del 5 % admisible;NORM_02;2.16;Gerencia de Energía e Instalaciones Electromecánicas
P2-02-B;P2;4.2 Tablero de la prensa;20 % de espacio libre en riel DIN;NORM_02;4.7;Gerencia de Energía e Instalaciones Electromecánicas
P2-03-A;P2;5.1 Maniobra del bastidor;tomando cada una 12 t;NORM_03;2.8;Gerencia de Seguridad Operacional y Salud Ocupacional
P2-03-M;P2;5.1 Maniobra del bastidor;peso de catálogo de la prensa: 24.000 kg;NORM_03;2.4;Gerencia de Seguridad Operacional y Salud Ocupacional
P2-03-B;P2;4.7 Ruido;a 3 m del equipo;NORM_03;6.2;Gerencia de Seguridad Operacional y Salud Ocupacional
P2-04-A;P2;7.2 Pruebas en sitio y recepción;prueba de funcionamiento en vacío en sitio;NORM_04;3.2;Gerencia de Material Rodante y Equipamiento de Talleres
P2-04-M;P2;3.4 Vía de alimentación de pares montados;desnivel longitudinal de hasta 1,5 mm/m;NORM_04;2.6;Gerencia de Infraestructura y Vías
P2-04-B;P2;3.4 Vía de alimentación de pares montados;levantamiento realizado antes del hormigonado;NORM_04;2.13;Gerencia de Infraestructura y Vías
P2-05-A;P2;5.2 Eslingado;eslingando desde las columnas guía rectificadas;NORM_05;1.8;Gerencia de Material Rodante y Equipamiento de Talleres
P2-05-M;P2;4.4 Sistema oleohidráulico;Re ≈ 2.300;NORM_05;3.5;Gerencia de Material Rodante y Equipamiento de Talleres
P2-05-B;P2;4.4 Sistema oleohidráulico;aceite se presente claro;NORM_05;3.8;Gerencia de Material Rodante y Equipamiento de Talleres
P3-01-A;P3;3.2 Excavación;taludes naturales 1:0,5;NORM_01;6.1;Gerencia de Infraestructura y Vías
P3-01-M;P3;3.3 Fundación;bloque de inercia de 45 t;NORM_01;7.3;Gerencia de Infraestructura y Vías
P3-01-B;P3;3.5 Inspección y liberaciones;conformidad verbal del jefe de obra;NORM_01;8.2;Gerencia de Infraestructura y Vías
P3-02-A;P3;4.3 Puesta a tierra;referenciará únicamente a la bancada metálica;NORM_02;5.14;Gerencia de Energía e Instalaciones Electromecánicas
P3-02-M;P3;4.3 Puesta a tierra;será de 10 mm² Cu;NORM_02;5.5;Gerencia de Energía e Instalaciones Electromecánicas
P3-02-B;P3;4.1 Alimentación eléctrica;cos φ 0,92;NORM_02;1.11;Gerencia de Energía e Instalaciones Electromecánicas
P3-03-A;P3;5.3 Apoyo de la autogrúa;contrachapado fenólico de 25 mm;NORM_03;4.7;Gerencia de Seguridad Operacional y Salud Ocupacional
P3-03-M;P3;5.4 Supervisión;permanecerá disponible por radio;NORM_03;5.5;Gerencia de Seguridad Operacional y Salud Ocupacional
P3-03-B;P3;5.2 Plan de Izaje Crítico;constancia de recepción del sistema se considerará conformidad;NORM_03;5.2;Gerencia de Seguridad Operacional y Salud Ocupacional
P3-04-A;P3;7.1 Unidades de prueba;serán discos patrón;NORM_04;3.6;Gerencia de Material Rodante y Equipamiento de Talleres
P3-04-M;P3;3.6 Vía de abastecimiento y pasarela;altura libre de 2,00 m;NORM_04;1.6;Gerencia de Infraestructura y Vías
P3-04-B;P3;7.3 Mediciones;Una traza por rueda;NORM_04;3.10;Gerencia de Material Rodante y Equipamiento de Talleres
P3-05-A;P3;4.6 Anclajes, bulonería y grout;se apretarán a 2.700 N·m;NORM_05;4.3;Gerencia de Material Rodante y Equipamiento de Talleres
P3-05-M;P3;4.6 Anclajes, bulonería y grout;mortero cementicio de nivelación de alta resistencia (60 MPa);NORM_05;2.9;Gerencia de Material Rodante y Equipamiento de Talleres
P3-05-B;P3;6. Montaje y nivelación;portón de la nave abierto;NORM_05;2.3;Gerencia de Material Rodante y Equipamiento de Talleres
P4-01-A;P4;3.2 Hormigón;hormigón elaborado H-25;NORM_01;3.1;Gerencia de Infraestructura y Vías
P4-01-M;P4;3.2 Hormigón;recubrimiento de 25 mm;NORM_01;3.5;Gerencia de Infraestructura y Vías
P4-01-B;P4;3.3 Curado;consignará la fecha de hormigonado;NORM_01;4.1;Gerencia de Infraestructura y Vías
P4-02-A;P4;4.2 Tablero seccional;diferencial general de 300 mA;NORM_02;4.15;Gerencia de Energía e Instalaciones Electromecánicas
P4-02-M;P4;4.1 Alimentación y capacidad del sistema;630 kVA cubre holgadamente;NORM_02;1.10;Gerencia de Energía e Instalaciones Electromecánicas
P4-02-B;P4;4.2 Tablero seccional;a 1,70 m de altura;NORM_02;4.10;Gerencia de Energía e Instalaciones Electromecánicas
P4-03-A;P4;5.2 Pruebas y habilitación;únicamente a su capacidad nominal (100 %);NORM_03;3.4;Gerencia de Seguridad Operacional y Salud Ocupacional
P4-03-M;P4;4.4 Canalizaciones y EMC;a 0,50 m del recorrido del carro;NORM_03;4.2;Gerencia de Seguridad Operacional y Salud Ocupacional
P4-03-B;P4;5.3 Mantenimiento;inspección especializada anual;NORM_03;3.6;Gerencia de Seguridad Operacional y Salud Ocupacional
P4-04-A;P4;6.2 Interferencia con la vía 4 electrificada;a 2,0 m de la catenaria;NORM_04;1.10;Gerencia de Infraestructura y Vías
P4-04-M;P4;8.2 Actas y recepción;firmada por el Jefe de Puesta en Marcha;NORM_04;3.20;Gerencia de Material Rodante y Equipamiento de Talleres
P4-04-B;P4;8.1 SAT bajo carga;manualmente cada 15 minutos;NORM_04;3.12;Gerencia de Material Rodante y Equipamiento de Talleres
P4-05-A;P4;4.5 Hidráulica;eliminarán por centrifugado;NORM_05;3.9;Gerencia de Material Rodante y Equipamiento de Talleres
P4-05-M;P4;4.4 Canalizaciones y EMC;separados 50 mm;NORM_05;4.8;Gerencia de Material Rodante y Equipamiento de Talleres
P4-05-B;P4;4.6 Bulonería y grout;dos pasadas (50 % y 100 %;NORM_05;4.5;Gerencia de Material Rodante y Equipamiento de Talleres"""

# Clasificación de cada trampa con NORM_07:
# id: (fuente, condicion_critico, objeto, ofertado, exigido, tipo_limite, dimension, impacto, dudosa, nota)
D, E = "DESVIO", "EXCEPCION_NO_ACREDITADA"
CLAS = {
 "P1-01-A": (D, "c", "CUANTITATIVO_TECNICO", 14, 28, "MINIMO", "Integridad", 4, "", "14 días queda fuera incluso de la excepción (mín. 21 días con probetas y aprobación): Art. 3.2.c y Art. 2.3"),
 "P1-01-M": (D, None, "CUANTITATIVO_TECNICO", 1, 2, "CANTIDAD", "Seguridad", 3, "Adriel: Medio, solicitar modificación", "Hay 1 escalera fija de 2 exigidas: la protección existe parcialmente, no es ausencia total (3.2.a). Brecha 50 %"),
 "P1-01-B": (D, None, "ENSAYO_ACEPTACION", None, None, None, "Integridad", 3, "", "Sustituye IRAM 1554 por inundación y control visual: no mide la misma propiedad"),
 "P1-02-A": (D, "b", "OTRO_TECNICO", None, None, None, "Seguridad", 5, "", "Electrodo de tierra aislado de la malla: ejemplo literal del Art. 3.2.b"),
 "P1-02-M": (D, None, "ORDINAL", None, None, None, "Integridad", 3, "", "IP54 frente a IP55: un escalón ordinal"),
 "P1-02-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Cumplimiento legal", 2, "", "Protocolo de PAT con más de 12 meses de antigüedad: requisito de vigencia documental"),
 "P1-03-A": (D, "a", "OTRO_TECNICO", None, None, None, "Seguridad", 5, "", "Izaje de 26 t al 87 % tratado como rutinario: omite por completo la clasificación como izaje crítico (3.2.a)"),
 "P1-03-M": (E, None, "CUANTITATIVO_TECNICO", 55, 45, "MAXIMO", "Seguridad", 3, "Adriel: Medio, solicitar modificación", "Excepción (cálculo y autorización) no acreditada; clase del desvío (3.6.5): brecha 22 % con riesgo para personas → Mayor (3.3.e)"),
 "P1-03-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Plazo", 2, "", "Plazo de presentación (48 h frente a 5 días hábiles)"),
 "P1-04-A": (D, None, "CUANTITATIVO_TECNICO", 3, 1.5, "TOLERANCIA", "Integridad", 4, "", "±3 mm frente a ±1,5 mm: brecha 100 %"),
 "P1-04-M": (D, None, "ENSAYO_ACEPTACION", None, None, None, "Desempeño", 4, "", "El SAT bajo carga existe pero omite la verificación en máxima carga de corte"),
 "P1-04-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Desempeño", 2, "", "Cantidad de puntos o lecturas de un control que sí se realiza"),
 "P1-05-A": (D, "a", "OTRO_TECNICO", None, None, None, "Integridad", 4, "", "Omite por completo el flushing en sitio antes de conectar servoválvulas: integridad del sistema hidráulico (3.2.a)"),
 "P1-05-M": (D, None, "CUANTITATIVO_TECNICO", 0.05, 0.02, "MAXIMO", "Desempeño", 4, "", "0,05 frente a 0,02 mm/m: brecha 150 %"),
 "P1-05-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Desempeño", 2, "", "Frecuencia de calibración (24 frente a 12 meses)"),
 "P2-01-A": (E, "a", "OTRO_TECNICO", None, None, None, "Integridad", 4, "", "Losa existente sin informe de capacidad portante: falta por completo la verificación de integridad de la losa (3.2.a)"),
 "P2-01-M": (D, None, "CUANTITATIVO_TECNICO", 0.52, 0.48, "MAXIMO", "Integridad", 2, "", "a/c 0,52 frente a 0,48: brecha 8,3 % → Menor"),
 "P2-01-B": (D, None, "ENSAYO_ACEPTACION", None, None, None, "Integridad", 3, "", "Esclerometría como única prueba: no mide la resistencia característica"),
 "P2-02-A": (D, "d", "CUANTITATIVO_TECNICO", 25, 27.4, "MINIMO", "Seguridad", 4, "", "Poder de corte menor que la Icc: valor inviable (decisión del 7/11)"),
 "P2-02-M": (D, None, "CUANTITATIVO_TECNICO", 4.2, 3, "MAXIMO", "Desempeño", 3, "", "4,2 % frente a 3 % en el tramo terminal: brecha 40 %"),
 "P2-02-B": (D, None, "RESERVA_ERGONOMIA_EFICIENCIA", None, None, None, "Costo", 2, "", "Reserva física del tablero"),
 "P2-03-A": (D, "b", "OTRO_TECNICO", None, None, None, "Seguridad", 5, "", "Izaje con dos equipos sin cálculo de reparto: ejemplo literal del Art. 3.2.b"),
 "P2-03-M": (D, None, "OTRO_TECNICO", None, None, None, "Seguridad", 3, "Adriel: Medio, solicitar modificación", "Declara un peso (neto de catálogo) en lugar del bruto: la medida existe pero mal definida, no es ausencia total"),
 "P2-03-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Seguridad", 2, "", "Posición de medición de un ensayo que sí se realiza"),
 "P2-04-A": (D, "b", "OTRO_TECNICO", None, None, None, "Desempeño", 5, "", "Recepción con FAT y pruebas en vacío: ejemplo literal del Art. 3.2.b"),
 "P2-04-M": (D, None, "CUANTITATIVO_TECNICO", 1.5, 1.0, "MAXIMO", "Integridad", 3, "", "1,5 frente a 1,0 mm/m: brecha 50 %"),
 "P2-04-B": (D, None, "ENSAYO_ACEPTACION", None, None, None, "Desempeño", 3, "Adriel: Medio, nota aclaratoria", "Certifica con el levantamiento previo al hormigonado: omite la verificación de aceptación posterior"),
 "P2-05-A": (D, "b", "OTRO_TECNICO", None, None, None, "Integridad", 4, "", "Eslingado sobre superficies de precisión: ejemplo literal del Art. 3.2.b"),
 "P2-05-M": (D, None, "CUANTITATIVO_TECNICO", 2300, 4000, "MINIMO", "Integridad", 3, "", "Re 2.300 frente a ≥ 4.000: brecha 42,5 %"),
 "P2-05-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Integridad", 2, "", "Cantidad de muestras (1 frente a 3)"),
 "P3-01-A": (D, "a", "OTRO_TECNICO", None, None, None, "Seguridad", 5, "", "Excavación de 2,10 m sin ninguna contención: sepultamiento (3.2.a)"),
 "P3-01-M": (E, None, "CUANTITATIVO_TECNICO", 1.32, 2, "MINIMO", "Desempeño", 3, "", "Sin análisis dinámico (excepción no acreditada); relación 1,32 frente a mín. 2: brecha 34 %"),
 "P3-01-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Cumplimiento legal", 2, "", "Liberación verbal de puntos de espera: requisito de registro y firma"),
 "P3-02-A": (D, "b", "OTRO_TECNICO", None, None, None, "Seguridad", 5, "", "Elimina el PE y usa bancada y carriles como tierra: solución sustituta peligrosa"),
 "P3-02-M": (D, None, "CUANTITATIVO_TECNICO", 10, 16, "MINIMO", "Seguridad", 4, "", "PE de 10 frente a 16 mm²: brecha 37,5 % (el PE existe: no es ausencia total)"),
 "P3-02-B": (D, None, "RESERVA_ERGONOMIA_EFICIENCIA", None, None, None, "Costo", 2, "", "Factor de potencia: eficiencia sin efecto en la seguridad (además brecha 3 %)"),
 "P3-03-A": (D, "b", "OTRO_TECNICO", None, None, None, "Seguridad", 5, "", "Estabilizadores sobre contrachapado sin capacidad conocida: el apoyo propuesto crea el peligro de hundimiento"),
 "P3-03-M": (D, None, "OTRO_TECNICO", None, None, None, "Seguridad", 3, "Adriel: Medio, nota aclaratoria", "HyS solo al inicio y luego por radio: la supervisión existe parcialmente, no es ausencia total"),
 "P3-03-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Cumplimiento legal", 2, "", "Aprobación formal de la ART"),
 "P3-04-A": (D, "b", "OTRO_TECNICO", None, None, None, "Desempeño", 5, "", "SAT con discos patrón: sustituye la prueba con unidades reales (equivalente a la prueba en vacío del 3.2.b)"),
 "P3-04-M": (D, None, "CUANTITATIVO_TECNICO", 2.00, 2.10, "MINIMO", "Seguridad", 3, "Adriel: Medio, nota aclaratoria", "2,00 frente a 2,10 m: brecha 4,8 % con riesgo de golpe para personas → Mayor (3.3.e)"),
 "P3-04-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Desempeño", 2, "", "Cantidad de trazas (1 frente a 3)"),
 "P3-05-A": (D, None, "CUANTITATIVO_TECNICO", 2700, 2274, "MAXIMO", "Integridad", 2, "", "2.700 frente a 2.274 N·m: brecha 18,7 % → Menor (decisión del 7/11)"),
 "P3-05-M": (D, None, "OTRO_TECNICO", 60, 80, "MINIMO", "Integridad", 3, "", "Material distinto (cementicio en lugar de epóxico) y brecha de resistencia del 25 %"),
 "P3-05-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Desempeño", 2, "", "Condición de medición de un ensayo que sí se realiza"),
 "P4-01-A": (D, None, "ORDINAL", None, None, None, "Integridad", 4, "", "H-25 frente a H-35: escala ordinal → Mayor (decisión del 7/11)"),
 "P4-01-M": (D, None, "CUANTITATIVO_TECNICO", 25, 40, "MINIMO", "Integridad", 3, "", "25 frente a 40 mm: brecha 37,5 %"),
 "P4-01-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Cumplimiento legal", 2, "", "Registro de curado incompleto"),
 "P4-02-A": (D, "b", "CUANTITATIVO_TECNICO", 300, 30, "MAXIMO", "Seguridad", 5, "", "Diferencial de 300 mA en lugar de ≤ 30 mA en área húmeda: no protege a personas"),
 "P4-02-M": (D, None, "RESERVA_ERGONOMIA_EFICIENCIA", 16.7, 35, "MINIMO", "Costo", 2, "Adriel: Bajo (la capacidad ofertada supera la demanda)", "Reserva de potencia del 16,7 % frente a 35 %: el transformador (630 kVA) cubre la demanda (540 kVA), sin efecto en el desempeño inicial"),
 "P4-02-B": (D, None, "RESERVA_ERGONOMIA_EFICIENCIA", None, None, None, "Desempeño", 2, "", "Altura de mandos: ergonomía"),
 "P4-03-A": (E, None, "ENSAYO_ACEPTACION", None, None, None, "Seguridad", 3, "Adriel: Medio, nota aclaratoria", "Omite las pruebas al 110 % y 125 % del puente grúa sin acreditar la justificación del fabricante"),
 "P4-03-M": (D, None, "CUANTITATIVO_TECNICO", 0.50, 0.80, "MINIMO", "Integridad", 3, "", "0,50 frente a 0,80 m: brecha 37,5 %"),
 "P4-03-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Seguridad", 2, "", "Frecuencia de inspección (anual frente a trimestral)"),
 "P4-04-A": (D, "b", "OTRO_TECNICO", None, None, None, "Seguridad", 5, "", "Operar a 2,0 m de la catenaria energizada sin consignación: la práctica crea el peligro"),
 "P4-04-M": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Cumplimiento legal", 2, "", "Firma del acta"),
 "P4-04-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Desempeño", 2, "", "Frecuencia de registro (15 min frente a 60 s)"),
 "P4-05-A": (D, "b", "OTRO_TECNICO", None, None, None, "Integridad", 4, "", "Arrancar con condensado y eliminarlo en el rodaje: la práctica daña el sistema hidráulico"),
 "P4-05-M": (D, None, "CUANTITATIVO_TECNICO", 50, 200, "MINIMO", "Desempeño", 3, "", "50 frente a 200 mm: brecha 75 %"),
 "P4-05-B": (D, None, "DOCUMENTAL_PROCEDIMIENTO", None, None, None, "Integridad", 2, "", "Secuencia de procedimiento (2 frente a 3 pasadas)"),
}

# Artículos alternativos válidos, declarados al generar las ofertas
EQUIV = {"P1-03-A": "NORM_05 1.6", "P3-02-A": "NORM_02 5.12", "P2-04-A": "NORM_04 3.22; NORM_04 3.25"}

def brecha(of, ex, tipo):
    if of is None or ex is None:
        return None
    if tipo == "MINIMO":
        return max(0.0, (ex - of) / ex)
    if tipo in ("MAXIMO", "TOLERANCIA"):
        return max(0.0, (of - ex) / ex)
    if tipo == "CANTIDAD":
        return max(0.0, (ex - of) / ex)
    return None

def clase(cond, objeto, b, dim):
    if cond in ("a", "b", "c", "d"):
        return "Crítico", f"3.2.{cond}"
    regla = {"DOCUMENTAL_PROCEDIMIENTO": ("Menor", "3.4.c"), "RESERVA_ERGONOMIA_EFICIENCIA": ("Menor", "3.4.d"),
             "VERIFICACION_RUTINA": ("Menor", "3.4.b"), "ENSAYO_ACEPTACION": ("Mayor", "3.3.b"),
             "ORDINAL": ("Mayor", "3.3.d"), "OTRO_TECNICO": ("Mayor", "3.3.c")}
    if objeto in regla:
        return regla[objeto]
    if objeto == "CUANTITATIVO_TECNICO":
        if b is not None and b >= 0.25:
            return "Mayor", "3.3.a"
        if dim == "Seguridad":          # brecha < 25 % con riesgo para personas
            return "Mayor", "3.3.e"
        return "Menor", "3.4.a"
    raise ValueError(objeto)

PROB = {"DESVIO": 4, "EXCEPCION_NO_ACREDITADA": 3, "INFORMACION_FALTANTE": 2}
MATRIZ = {5: "BMMAA", 4: "BBMAA", 3: "BBMAA", 2: "BBBMA", 1: "BBBMM"}
NIV = {"B": "Bajo", "M": "Medio", "A": "Alto"}
RANGO = {"Crítico": (4, 5), "Mayor": (3, 4), "Menor": (1, 2)}

filas = []
for linea in MAPA.splitlines():
    tid, of, sec, frag, norma, art, resp = linea.split(";")
    fuente, cond, objeto, vo, ve, tipo, dim, imp, dudosa, nota = CLAS[tid]
    b = brecha(vo, ve, tipo)
    cl, regla = clase(cond, objeto, b, dim)
    lo, hi = RANGO[cl]
    assert lo <= imp <= hi, (tid, cl, imp)
    p = PROB[fuente]
    nivel = NIV[MATRIZ[p][imp - 1]]
    if cl == "Crítico" and nivel != "Alto": nivel = "Alto"      # Art. 5.3
    if cl == "Menor" and nivel != "Bajo": nivel = "Bajo"        # Art. 5.3
    filas.append({
        "id": tid, "oferta": of, "seccion": sec, "fragmento_trampa": frag,
        "norma": norma, "articulo": art, "articulos_equivalentes": EQUIV.get(tid, ""),
        "fuente": fuente, "condicion_critico": cond or "", "objeto_requisito": objeto,
        "valor_ofertado": "" if vo is None else vo, "valor_exigido": "" if ve is None else ve,
        "tipo_limite": tipo or "", "brecha_relativa": "" if b is None else round(b, 3),
        "clase": cl, "regla_norm07": regla, "probabilidad": p, "dimension_impacto": dim,
        "impacto": imp, "nivel": nivel, "responsable": resp,
        "decision_adriel": dudosa, "nota": nota,
    })

import os
SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ground_truth_v3.csv")
with open(SALIDA, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(filas[0].keys()), delimiter=";")
    w.writeheader(); w.writerows(filas)

from collections import Counter
print("Clases:", Counter(r["clase"] for r in filas))
print("Niveles:", Counter(r["nivel"] for r in filas))
for of in ("P1", "P2", "P3", "P4"):
    print(of, Counter(r["clase"] for r in filas if r["oferta"] == of))
print("Decididas por Adriel:", [r["id"] for r in filas if r["decision_adriel"]])
