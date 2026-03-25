# HubGH Wave 4 Implementation Log

Status: OLA 4 (endurecimiento final) implementada en codigo, con validacion local parcial y corrida bench pendiente por entorno.

## Alcance ejecutado

1. Bienestar
   - Se removio auto-escalamiento en hooks de actualizacion para seguimiento, evaluacion y compromiso.
   - Se mantuvo gestion manual en `bienestar_bandeja` con dialogo de accion y estados controlados.
   - Se agrego semaforo visible por score (`Verde/Amarillo/Rojo/Sin score`) en todas las tablas de la bandeja.

2. Nomina
   - Se agrego prioridad de recobro ponderado por empleado en consolidacion TP (`recobro_priority`).
   - Se agrego trazabilidad operativa (`traceability`) en endpoints y consolidaciones TC/TP.
   - Se incluyo modulo `nomina` en `get_initial_tray_reports()` con KPIs y alertas del contrato comun.

3. UAT y Chrome DevTools MCP
   - Se dejaron runbooks listos para ejecucion manual en:
     - `docs/qa/hubgh-wave-4-uat-por-bandeja.md`
     - `docs/qa/hubgh-wave-4-chrome-devtools-mcp-suite.md`

4. Retiro final de entrypoints legacy de Capacitacion
   - Se retiro el bloque visual operativo de Capacitacion en `punto_360.js`.
   - `get_capacitacion_punto()` quedo en modo compatibilidad pasiva/decommissioned (fallback no destructivo), redirigiendo a endpoints LMS-ready.

## Archivos modificados (OLA 4)

- `frappe-bench/apps/hubgh/hubgh/hubgh/doctype/bienestar_seguimiento_ingreso/bienestar_seguimiento_ingreso.py`
- `frappe-bench/apps/hubgh/hubgh/hubgh/doctype/bienestar_evaluacion_periodo_prueba/bienestar_evaluacion_periodo_prueba.py`
- `frappe-bench/apps/hubgh/hubgh/hubgh/doctype/bienestar_compromiso/bienestar_compromiso.py`
- `frappe-bench/apps/hubgh/hubgh/hubgh/page/bienestar_bandeja/bienestar_bandeja.py`
- `frappe-bench/apps/hubgh/hubgh/hubgh/page/bienestar_bandeja/bienestar_bandeja.js`
- `frappe-bench/apps/hubgh/hubgh/hubgh/payroll_tp_tray.py`
- `frappe-bench/apps/hubgh/hubgh/hubgh/page/payroll_tp_tray/payroll_tp_tray.py`
- `frappe-bench/apps/hubgh/hubgh/hubgh/page/payroll_tc_tray/payroll_tc_tray.py`
- `frappe-bench/apps/hubgh/hubgh/api/module_dashboards.py`
- `frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py`
- `frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.js`
- `frappe-bench/apps/hubgh/hubgh/tests/test_bienestar_workstream2_automation.py`
- `frappe-bench/apps/hubgh/hubgh/tests/test_bienestar_bandeja.py`
- `frappe-bench/apps/hubgh/hubgh/tests/test_module_dashboards_api.py`

## Validacion ejecutada

- Python syntax: pendiente de registrar en `hubgh-wave-4-verification.md` (corrida local planificada)
- JS syntax: pendiente de registrar en `hubgh-wave-4-verification.md` (corrida local planificada)
- Bench scoped tests: bloqueado por entorno cuando `bench/frappe` no estan disponibles

## Rollback aditivo

1. Revertir semaforo en `bienestar_bandeja.py/js` (bloque `semaforo_*`).
2. Revertir `recobro_priority`/`traceability` en TC/TP.
3. Revertir modulo `nomina` en `module_dashboards.py`.
4. Rehabilitar render legacy de capacitacion en `punto_360.js` si negocio lo requiere.

Todo rollback es acotado por archivo y sin migraciones destructivas.
