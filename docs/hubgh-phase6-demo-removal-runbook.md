# HubGH Fase 6 — Eliminación total de lógica demo

## Objetivo

Eliminar fallback/demo residual en APIs de experiencia interna HubGH y asegurar contratos estables con empty states explícitos.

## Alcance aplicado

- API perfil interno:
  - `hubgh.api.my_profile.get_summary`
  - `hubgh.api.my_profile.get_time_summary`
- API operación documental:
  - `hubgh.api.ops.export_docs_zip`
- Shell frontend mínimo (sin rediseño):
  - página `mi_perfil`
  - texto de empty en `operacion_punto_lite`
- Pruebas de regresión Fase 6 (API + contratos vacíos)

## Cambios implementados

### 1) API de perfil sin fallback demo

Se removió comportamiento demo/hardcodeado y se devolvió estado vacío explícito:

- Cuando no hay `Ficha Empleado`:
  - `empty: true`
  - `empty_state.code: employee_not_linked`
  - `profile` mantiene shape estable y campos string vacíos.
- Cuando sí existe ficha:
  - respuesta con datos reales + `empty: false`.

### 2) API de tiempo semanal sin KPI demo

- Se eliminó KPI estático demo.
- `get_time_summary` ahora:
  - usa datos reales de `Timesheet` si existe DocType y registros de semana actual,
  - o retorna empty explícito:
    - `timesheet_unavailable` si no hay fuente,
    - `no_timesheet_data` cuando no hay registros en la semana.

### 3) Export ZIP de operación con metadata empty state

`export_docs_zip` conserva contrato (`file_url`, `file_name`) y añade:

- `empty`
- `empty_state { empty, code, message }`

Casos:

- `mode=persona` sin categorías/documentos: `no_document_categories`
- `mode=punto_mes` sin novedades en rango: `no_novedades_in_month`

### 4) Ajustes frontend mínimos para consumir empty states

- `mi_perfil`:
  - se eliminan textos demo,
  - se retira lista mock de solicitudes,
  - se muestran mensajes explícitos de empty state (sobre mí / tiempo).
- `operacion_punto_lite`:
  - se cambia texto "placeholder" por empty-state productivo.

## Pruebas ejecutadas

### Nuevas

- `hubgh.tests.test_phase6_demo_removal`
  - cubre:
    - perfil sin ficha (empty explícito),
    - perfil con ficha (datos reales),
    - tiempo sin fuente / con datos,
    - export ZIP persona y punto_mes con empty state.

### Regresión existente

- `hubgh.tests.test_feed_api`
- `hubgh.tests.test_module_dashboards_api`
- `hubgh.tests.test_shell_api`

## Validación manual (checklist)

1. Ingresar a `Mi Perfil` con usuario sin `Ficha Empleado`.
2. Confirmar que NO aparecen textos demo y que la UI muestra estado vacío explícito.
3. Ingresar con usuario con `Ficha Empleado`; validar datos reales en cabecera/chips.
4. Ejecutar `export_docs_zip(mode="persona")` para persona sin categorías activas y validar `empty_state.code=no_document_categories`.
5. Ejecutar `export_docs_zip(mode="punto_mes")` para mes sin novedades y validar `empty_state.code=no_novedades_in_month`.
6. Confirmar descarga de ZIP en ambos casos (contrato estable + archivo generado).

## Resultado

Fase 6 implementada en alcance solicitado: sin respuestas demo hardcodeadas en endpoints intervenidos, contratos estables y empty states explícitos para frontend.
