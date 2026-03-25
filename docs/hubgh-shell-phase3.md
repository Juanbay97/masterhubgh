# HubGH Shell – Fase 3 (Dashboards por módulo)

## Resumen de implementación

Se implementó la capa de dashboards-resumen por módulo dentro del App Shell existente, manteniendo compatibilidad con Fase 1/Fase 2 y sin fallback demo.

Módulos cubiertos:

- Selección
- RL / Contratación
- SST
- Operación

Cada dashboard ahora expone:

- KPIs reales (según fuentes del módulo).
- Alertas dinámicas (sin datos hardcodeados demo).
- Empty-state explícito cuando no hay datos/fuente.
- Botones de navegación hacia rutas funcionales existentes.

## Backend (API)

Nuevo endpoint:

- `hubgh.api.module_dashboards.get_module_dashboard(module_key)`

Contrato retornado por módulo:

- `module`: `key`, `label`
- `kpis`: `items[]`, `empty`
- `alerts`: `items[]`, `empty`, `message`
- `actions[]`: botones/rutas
- `empty`, `empty_state`
- `meta`: `source`, `generated_at`

Fuentes por módulo:

- **Selección**: `Candidato` (estados del proceso).
- **RL / Contratación**: `Candidato` + `Datos Contratacion`.
- **SST**: `SST Alerta` + `Novedad Laboral`.
- **Operación**: reutiliza `hubgh.api.ops.get_punto_lite()`.

## Frontend (Shell)

Cambios principales:

- Se agrega sección visual `hubgh-module-dashboard` en el shell.
- Al activar módulo (`seleccion`, `relaciones_laborales`, `sst`, `operacion`) se consulta el endpoint de Fase 3.
- Se renderizan:
  - header del dashboard,
  - grilla de KPIs,
  - cards de alertas,
  - acciones principales.
- Para módulos sin dashboard Fase 3 (ej. `home`), el comportamiento anterior del Home Feed permanece.

Además, `get_shell_bootstrap` publica contrato Fase 3 en `contracts.module_dashboard`.

## Validación manual breve

1. Ingresar a `/app/hubgh_shell`.
2. Cambiar entre módulos **Selección**, **Relaciones Laborales**, **SST** y **Operación** desde sidebar/cards.
3. Verificar en cada módulo:
   - visualización de KPIs,
   - cards de alerta,
   - botones que navegan a rutas existentes.
4. Verificar casos vacíos:
   - usuario sin datos operativos (sin ficha/PDV) en Operación,
   - entorno sin datos en módulo (debe verse empty-state explícito, sin demo).
5. Confirmar que **Home Feed** sigue funcionando en módulo `home` (compatibilidad Fase 2).

## Pruebas básicas ejecutadas

- `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_module_dashboards_api`
- Resultado: **OK** (8 pruebas)
  - contrato/shape por módulo,
  - casos vacíos explícitos por módulo (incluido Operación con PermissionError).

