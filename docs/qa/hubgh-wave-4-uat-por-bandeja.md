# HubGH Wave 4 UAT por Bandeja

Objetivo: ejecutar UAT manual funcional por bandeja para OLA 4 sin depender de automatizacion E2E.

## 1. Precondiciones

1. Site de prueba con datos semilla (`hubgh.test` o equivalente).
2. Usuarios de prueba por rol: Bienestar, RRLL, SST, Nomina TC, Nomina TP, Jefe PDV, System Manager.
3. Navegacion Desk disponible.

## 2. UAT Bienestar (`/app/bienestar_bandeja`)

1. Verificar que cada bloque muestra columna `Semáforo`.
2. Tomar un item de cada tipo (seguimiento/evaluacion/alerta/compromiso) y abrir `Gestionar`.
3. Validar que `Nuevo estado` sea `Select` con opciones controladas.
4. Guardar gestion breve + cambio de estado.
5. Confirmar que:
   - no se genera auto-escalamiento RRLL por guardado,
   - se registra bitacora/observacion,
   - la fila actualiza estado y mantiene contexto.

## 3. UAT Nomina TC (`/app/payroll_tc_tray`)

1. Cargar vista consolidada con filtros y sin filtros.
2. Confirmar presencia de `contract_version` y `traceability` en payload (Network tab).
3. Validar conteos (`pending_count`, `ready_count`) y consistencia con lotes.

## 4. UAT Nomina TP (`/app/payroll_tp_tray`)

1. Abrir periodo con lineas TC aprobadas.
2. Confirmar por empleado:
   - `recobro_priority.score`,
   - `recobro_priority.level`,
   - `traceability.trace_id`.
3. Revisar resumen ejecutivo:
   - `recobro_weighted.high_priority|medium_priority|low_priority`,
   - `top_cases` ordenado por score desc.

## 5. UAT Reportes Iniciales (`get_initial_tray_reports`)

1. Ejecutar endpoint desde Desk/console.
2. Verificar `modules = [seleccion, rrll, sst, operacion, nomina]`.
3. Confirmar que `reports.nomina` trae `kpis`, `alerts`, `actions` con contrato comun.

## 6. UAT Decommission Capacitación (`/app/punto_360`)

1. Abrir Punto 360 y confirmar ausencia del bloque visual `Capacitación — Curso de Calidad`.
2. Validar que el resto de secciones operativas (novedades, casos, SST, feedback) siga estable.
3. Consumir `get_capacitacion_punto(punto)` y confirmar respuesta fallback:
   - `deprecated = true`,
   - `status = decommissioned`,
   - sin errores de servidor.

## 7. Criterio de aceptacion

UAT aprobado si todos los escenarios pasan sin errores bloqueantes y sin regresion visible en bandejas existentes.
