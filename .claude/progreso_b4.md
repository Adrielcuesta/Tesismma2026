# Progreso B4

## Etapa 1 — Carpetas y configuración (hecha, sin commit)
- config: DIRECTORIO_NORMATIVA / DIRECTORIO_LINEAMIENTOS; NORMA_COMPLETA retirada; THINKING_VERIFICACION=False; MAX_CHARS_PROYECTO marcado legacy.
- Todos los lectores de la KB usan DIRECTORIO_NORMATIVA (main, vector_db_manager, evaluate_rag, diagnostico_recuperacion).
- document_utils: `cargar_norma_completa` -> `texto_limpio_de_archivo`.
- Nuevo `scripts/lineamientos.py` + `tests/test_lineamientos.py`.
- Pendiente de confirmar: nombres de claves de `criterios_empresa.json` (supuestos en lineamientos.py).
- Pendiente para Etapa 3: la cadena de redacción sigue usando `{norma_completa}` (ahora vacío); se reemplaza entera.
- Tests: 87 pasan.

## Correcciones a la Etapa 1
- lineamientos.py ajustado al esquema real (documento_criterios en la raíz; texto_para_el_modelo = capitulos + articulos); corte de artículos solo en encabezados `Art. X.Y. TÍTULO` (mayúsculas). Fixture en tests/fixtures/criterios_empresa.json.

## Etapa 2 — motor_riesgos (hecha, sin commit)
- scripts/motor_riesgos.py + tests/test_motor_riesgos.py. Ground truth: 60/60 filas coinciden en clase, regla y responsable.
- Art. 5.4: bloque decision_aceptabilidad en el JSON (clases y niveles sobre el mismo riesgo). 6.2 solo Menores. Brecha nunca negativa; clase() devuelve (clase, regla, marcas).

## Etapa 3 — Clasificación (hecha, sin commit)
- schemas.ClasificacionRiesgo; RiskReport con registro_brechas, riesgos, solicitudes, alertas, resumen_ejecutivo, lineamientos (riesgos_identificados opcional).
- rag_components.PROMPT_CLASIFICACION_STR + crear_cadena_clasificacion; retirados PROMPT_REDACCION_STR, PROMPT_RESUMEN_STR y sus cadenas.
- scripts/clasificacion.py (validación pasos 2-7 + cálculo con motor_riesgos); main._verificar_seccion devuelve (brechas, alertas, registro); sin llamada de resumen.
- motor_riesgos.solicitudes y resumen_ejecutivo. tests/test_clasificacion.py. 173 tests pasan.
- Pendiente de confirmar: nombres de las 6 dimensiones del Art. 4.3 (schemas.DimensionImpacto; solo "Seguridad de personas" viene del prompt).
- Correcciones Etapa 3: DimensionImpacto con nombres completos del Art. 4.3 y validación por primera palabra; solicitudes agrupadas = una línea por brecha, tipo/plazo del componente de mayor clase; prompt del modo lista con RAG sin el espacio de NORM_06; test de identidad con docs/prompts/prompt_B4_clasificacion_NORM07.md. 189 tests pasan.

## Etapa 4 — Dashboard (hecha, sin commit)
- scripts/dashboard_generator.py reescrito: modo verificación (4 secciones) y modo lista (leyenda + lista simple). tests/test_dashboard.py.
- Ejemplo: tests/fixtures/resultado_ejemplo.json -> tests/salida/dashboard_ejemplo.html (tests/salida/ en .gitignore).
- Ajuste Etapa 4: registro dividido por nivel (Altos/Medios/Bajos, borde rojo/ámbar/verde), RBS en el detalle; top 5 eliminado (dashboard, resumen_ejecutivo, motor_riesgos.top5 y sus tests). 194 tests pasan.
- Ajuste Etapa 4 (diseño): una sola familia tipográfica en --fuente, sin emojis, títulos en mayúsculas y negrita, etiquetas rectangulares; barra de color en las secciones por nivel. Resumen del informe: comentario general (LLM con validación + plantilla, scripts/comentario.py) y acciones antes de la adjudicación (código). Prompt del comentario en docs/prompts y test de igualdad extendido.

## Etapa 5 — evaluar.py (hecha)
- evaluacion/evaluar.py + tests/test_evaluar.py (modo brechas, modo lista, --revision, --comparar; ground truth como salida = 100 %, vacía = 0 %). 215 tests pasan.
