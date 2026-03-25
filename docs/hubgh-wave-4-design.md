# HubGH Wave 4 Design

## Objetivo

Implementar OLA 4 de endurecimiento final con cambios aditivos y reversibles:

1. Bienestar sin auto-escalamientos (operacion 100% manual con semaforo + accion).
2. Nomina con recobro ponderado y trazabilidad TC/TP/reportes.
3. Preparar UAT por bandeja y suite Chrome DevTools MCP (solo docs).
4. Retirar entrypoints legacy operativos de Capacitación sin romper historial/fallback.

## Estrategia tecnica

1. **Bienestar**
   - desactivar side-effects automaticos en hooks de update;
   - reforzar UX de gestion manual en bandeja con estados controlados.
2. **Nomina**
   - incorporar scoring ponderado explicable por empleado;
   - exponer metadata de trazabilidad sin romper contrato existente.
3. **Dashboards**
   - incluir `nomina` en contrato comun de reportes iniciales.
4. **Decommission Capacitación**
   - retirar render operativo en Punto 360;
   - mantener endpoint fallback (`deprecated`) para compatibilidad no destructiva.

## Guardrails no-regresion

- No eliminar endpoints existentes.
- No romper shape de payload legacy (solo agregar campos).
- Mantener rollback por archivo (sin migraciones destructivas).
