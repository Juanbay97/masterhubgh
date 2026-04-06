# HubGH Wave 4 Change Summary

Scope: OLA 4 endurecimiento final (Bienestar manual, Nomina recobros ponderados, UAT/MCP docs, retiro operativo legacy de Capacitacion, cierre de riesgo residual).

## 1. Control metadata

| Field | Value |
|---|---|
| Wave | 4 |
| Focus | Endurecimiento final transversal |
| Prepared by | OpenCode |
| Status | Executed (validacion final bench pendiente de ambiente) |

## 2. Registro de cambios

### 2.1 Funcionales

| ID | Area | Cambio | Tipo |
|---|---|---|---|
| W4-F01 | Bienestar | Se elimino auto-escalamiento en updates de seguimiento/evaluacion/compromiso | Hardening aditivo |
| W4-F02 | Bienestar | Se agrego semaforo visible por score y gestion manual con estados controlados | UX/operativo |
| W4-F03 | Nomina | Se agrego `recobro_priority` ponderado en consolidacion TP | Hardening operativo |
| W4-F04 | Nomina | Se agrego `traceability` en TC/TP para contrato canónico | Trazabilidad |
| W4-F05 | Dashboards | Se agrego modulo `nomina` en `get_initial_tray_reports()` | Cobertura de bandejas |
| W4-F06 | Punto 360 | Se retiro render operativo legacy de Capacitacion | Decommission no destructivo |
| W4-F07 | Punto 360 | `get_capacitacion_punto()` queda deprecated/fallback, con continuidad LMS-ready | Backward compatibility |

### 2.2 Documentales

| ID | Artefacto | Objetivo |
|---|---|---|
| W4-D01 | `docs/qa/hubgh-wave-4-uat-por-bandeja.md` | UAT manual por bandeja |
| W4-D02 | `docs/qa/hubgh-wave-4-chrome-devtools-mcp-suite.md` | Suite detallada para Chrome DevTools MCP |
| W4-D03 | `docs/hubgh-wave-4-implementation-log.md` | Registro consolidado de implementacion |
| W4-D04 | `docs/hubgh-wave-4-verification.md` | Protocolo de verificacion final |

## 3. Compatibilidad y no-regresion

- `get_punto_stats()` mantiene contrato base (cambios aditivos, sin romper claves legacy).
- Endpoints de nomina TC/TP conservan respuesta previa y agregan metadata (`contract_version`, `traceability`).
- `get_capacitacion_punto()` no se elimina; se mantiene como fallback pasivo.

## 4. Riesgo residual

| Riesgo | Estado | Mitigacion |
|---|---|---|
| Falta corrida bench-site completa | Abierto (ambiental) | Ejecutar protocolo de `hubgh-wave-4-verification.md` en entorno con bench operativo |
| Drift entre semaforo visual y score origen | Bajo | Test de contrato en `test_bienestar_bandeja.py` |
| Priorizacion recobro requiere tuning de pesos | Medio | Ajuste controlado por revision funcional sin romper schema |

## 5. Rollback

Rollback por archivo, aditivo y reversible:

1. Revertir `bienestar_bandeja.py/js` (bloques `semaforo_*` + select de estados).
2. Revertir metadata/ponderacion en `payroll_tp_tray.py` y wrappers TC/TP.
3. Revertir modulo `nomina` en `module_dashboards.py`.
4. Reponer bloque legacy de capacitacion en `punto_360.js` si negocio lo solicita.
