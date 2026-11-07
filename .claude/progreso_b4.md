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
