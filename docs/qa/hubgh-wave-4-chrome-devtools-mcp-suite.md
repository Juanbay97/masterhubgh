# HubGH Wave 4 Chrome DevTools MCP Suite

Objetivo: guion detallado para validacion manual asistida por Chrome DevTools MCP (sin ejecucion automatica en esta ola).

## 1. Setup MCP

1. Abrir navegador con session activa en site de prueba.
2. Habilitar captura de Network + Console.
3. Limpiar logs antes de cada escenario.

## 2. Escenarios

### E1 - Bienestar semaforo y gestion manual

- Ruta: `/app/bienestar_bandeja`
- Pasos:
  1. Confirmar render de columna `Semáforo`.
  2. Abrir `Gestionar` en item `seguimiento`.
  3. Guardar nuevo estado + gestion breve.
- Validar en Network:
  - request a `gestionar_bienestar_item` con `tipo`, `item_name`, `nuevo_estado`.
  - response `ok=true`.
- Validar en Console: sin errores JS.

### E2 - Nomina TC trazabilidad

- Ruta: `/app/payroll_tc_tray`
- Pasos:
  1. Aplicar filtro por periodo.
  2. Abrir detalle consolidado.
- Validar en Network response JSON:
  - `contract_version = nomina-operativa-v2`
  - `traceability.stage = tc_review`

### E3 - Nomina TP recobro ponderado

- Ruta: `/app/payroll_tp_tray`
- Pasos:
  1. Refrescar periodo con lineas aprobadas TC.
  2. Revisar payload consolidado.
- Validar:
  - `employee_consolidation[*].recobro_priority.score`
  - `executive_summary.recobro_weighted.top_cases`
  - `traceability.stage = tp_refresh|tp_page_load`

### E4 - Reporte inicial de bandejas

- Endpoint: `hubgh.api.module_dashboards.get_initial_tray_reports`
- Validar:
  - inclusion modulo `nomina`
  - contrato comun por reporte (`kpis`, `alerts`, `actions`).

### E5 - Decommission Capacitación en Punto 360

- Ruta: `/app/punto_360`
- Pasos:
  1. Cargar un PDV activo.
  2. Confirmar que no renderiza tarjeta operativa legacy de capacitacion.
  3. Ejecutar llamada manual a `get_capacitacion_punto`.
- Validar response fallback:
  - `deprecated=true`
  - `status=decommissioned`
  - `next_step` orientando a endpoints LMS-ready.

## 3. Evidencia requerida

Por escenario:

1. Captura de pantalla.
2. Export HAR o captura de payload clave.
3. Nota corta de resultado (`Pass/Fail`) y observaciones.

## 4. Criterio de salida de suite

Suite aprobada si E1-E5 pasan y no hay errores severos en Console/Network.
