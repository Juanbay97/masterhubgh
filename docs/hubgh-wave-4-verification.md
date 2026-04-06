# HubGH Wave 4 Verification

Scope: verificacion de OLA 4 endurecimiento final (Bienestar, Nomina, decommission Capacitación, docs UAT/MCP).

## 1. Validaciones locales ejecutables

1. Python syntax
   - `python -m py_compile` sobre archivos Python modificados.
2. JS syntax
   - `node --check` sobre `bienestar_bandeja.js` y `punto_360.js`.
3. JSON/docs
   - Validacion de markdown y consistencia de referencias internas.

## 2. Bench-scoped (protocolo canónico)

Ejecutar en entorno bench operativo (`frappe-bench` con `bench` + `frappe` instalados):

1. Bienestar + backbone
   - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_bienestar_workstream2_automation --module hubgh.tests.test_bienestar_bandeja --module hubgh.tests.test_people_ops_backbone`
2. Dashboards/Nómina
   - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_module_dashboards_api --module hubgh.tests.test_payroll_tc_tray`
3. Regresion transversal
   - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments`

## 3. Resultado esperado por gate

| Gate | Criterio | Esperado |
|---|---|---|
| G4-BIE-01 | Sin auto-escalamiento en update hooks Bienestar | Pass |
| G4-BIE-02 | Semaforo visible en bandeja + gestion manual | Pass |
| G4-NOM-01 | Recobro ponderado y trazabilidad en TC/TP | Pass |
| G4-NOM-02 | `get_initial_tray_reports()` incluye `nomina` | Pass |
| G4-DEC-01 | Sin bloque operativo legacy de Capacitacion en Punto 360 | Pass |
| G4-DEC-02 | Fallback no destructivo en `get_capacitacion_punto()` | Pass |
| G4-DOC-01 | Runbooks UAT + Chrome DevTools MCP listos | Pass |

## 4. Bloqueos ambientales conocidos

- Si `bench` no existe en PATH o no hay entorno Frappe instalado, la corrida bench no puede ejecutarse localmente.
- Ese bloqueo NO invalida la implementacion; deja pendiente solo la verificacion de infraestructura.

## 5. Cierre

Con codigo y docs actuales, OLA 4 queda lista para UAT funcional y ejecucion de test bench final en ambiente habilitado.
