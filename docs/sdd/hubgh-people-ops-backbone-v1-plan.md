# HubGH People Ops Backbone v1 - Plan Consolidado SDD

## Que es este plan

Este documento consolida en un solo lugar el plan SDD ya aprobado para `hubgh-people-ops-backbone-v1`. Su objetivo es alinear a stakeholders tecnicos y no tecnicos sobre que se va a cambiar, que no se va a cambiar, como se controla el riesgo y como se ejecuta sin romper la operacion.

No es un rediseno big-bang ni una app nueva. Es una evolucion aditiva dentro de `frappe-bench/apps/hubgh`, con foco en continuidad funcional y mejora progresiva.

## Decisiones de base (no negociables en este plan)

- No app nueva: todo se implementa dentro del app actual `hubgh`.
- Funcionalidad y flujos preservados: las reglas de negocio y resultados operativos se mantienen.
- UI evolutiva permitida: se puede redisenar por etapas sin romper contratos funcionales.
- Backward compatibility funcional: wrappers/facades y versionado cuando aplique.
- Rollout por flags: `off -> warn -> enforce` por modulo, con rollback rapido.

## 1) Proposal consolidada

### Intent

Unificar People Ops en HubGH con un backbone canonico por persona que conecte RRLL, SST, Bienestar, Seleccion y Documental, preservando contratos y flujos existentes.

### Scope

**In scope**
- Historial/timeline canonico por persona con eventos multi-area.
- Policy layer reutilizable de sensibilidad/permisos para Persona 360 y Punto 360.
- Handoffs inter-area contract-first (Seleccion->RRLL, Bienestar->RRLL, SST->Persona/Punto).
- Evolucion progresiva UX/UI en bandejas sin regresiones funcionales.

**Out of scope**
- Crear una app nueva o migrar fuera de `frappe-bench/apps/hubgh`.
- Reescritura total en un solo release.
- Formacion/LMS en esta iteracion (queda como backlog futuro fuera de alcance actual).

### Principios de adopcion

- Functionality-first: primero preservar comportamiento de negocio.
- Additive-first y reversible: cambios activables/desactivables por flags.
- Strangler por endpoint/widget: convivir con legacy mientras se valida paridad.
- Promocion gradual: pasar de `warn` a `enforce` solo con evidencia.

### Riesgos principales y mitigacion

- Regresion funcional por UI nueva -> contract tests + datasets golden + rollout por flags.
- Drift de permisos/sensibilidad -> policy unica + pruebas cross-modulo de autorizacion.
- Divergencia legacy/nuevo en transicion -> matriz de paridad + telemetria de eventos.

## 2) Spec consolidada (requerimientos y escenarios)

### Requerimientos funcionales principales

1. Persona 360 Timeline canonico: eventos unificados por modulo, fecha y estado.
2. Persona 360 Creacion de novedades: alta controlada por rol, area y sensibilidad.
3. Punto 360 Tablero accionable: KPIs y acciones habilitadas por rol.
4. RRLL Lifecycle disciplinario: trazabilidad completa de evidencia, estados y cierre.
5. SST Salud y aforados: manejo de vencimientos y acceso restringido sensible.
6. Bienestar flujo contractual: seguimiento 5/15/30, periodo de prueba y handoff a RRLL.
7. Seleccion handoff estable: contratos compatibles para consumidores nuevos y legacy.
8. Flags, observabilidad y rollback: modos `off/warn/enforce` por modulo y vuelta segura.
9. NFR Paridad funcional y contratos: evidencia de equivalencia legacy vs backbone antes de `enforce`.
10. NFR Confiabilidad y operacion: degradacion parcial controlada sin romper contratos publicos.

### Escenarios principales (happy path + edge)

- Timeline consolidado: usuario autorizado ve eventos unificados y filtrables.
- Sensibilidad: usuario sin permiso ve redaccion/bloqueo con warning auditable.
- Creacion permitida/denegada: alta valida persiste; alta no autorizada se rechaza sin side effects.
- Punto 360 por rol: operativo con acciones; read-only solo visualiza metricas permitidas.
- Disciplinario auditado: cada transicion queda registrada y visible segun sensibilidad.
- Vencimientos SST: alertas y estado vigente/historico correctos.
- Handoff Bienestar/Seleccion: contratos trazables sin romper consumidores legacy.
- Drift contractual en `warn`: diferencia detectada bloquea promocion a `enforce` con evidencia auditable.
- Degradacion parcial: Persona/Punto responden con fallback declarado sin romper contratos.
- Rollback operativo: degradar de `enforce` a `warn/off` sin perdida de datos.

## 3) Design consolidado

### Enfoque tecnico

Se agrega un backbone aditivo de eventos canonicos y una capa central de policy de sensibilidad/permisos. Se preservan endpoints y respuestas existentes mediante compatibilidad funcional.

### Decisiones tecnicas clave

- Canonical event store aditivo (`People Ops Event`) en vez de derivar todo on-demand.
- Policy centralizada (`people_ops_policy.py`) en vez de checks dispersos.
- Rollout strangler por endpoint/widget en vez de reemplazo big-bang de UI.
- Contratos reutilizables para widgets/feeds/acciones en Punto 360.

### Componentes y contratos

- `People Ops Event`: contrato canonico por evento con `event_key`, `area`, `taxonomy`, `sensitivity`, `state`, `refs`, `occurred_on`.
- `HandoffContract`: contrato de traspaso inter-area con campos requeridos, permisos y estado (`pending/ready/blocked/completed`).
- `people_ops_event_publishers.py`: publica eventos desde fuentes actuales (GH/SST/RRLL/Bienestar/Documental).
- `people_ops_policy.py` + `people_ops_flags.py`: decision de acceso por sensibilidad y modo (`off/warn/enforce`).
- `persona_360.py` y `punto_360.py`: consumen feed/policy sin romper response shape vigente.

### Rollout tecnico

1. `off`: backbone desactivado, flujo legacy intacto.
2. `warn`: dual write/read con comparacion, telemetria y auditoria.
3. `enforce`: backbone/policy autoritativos por modulo cuando hay paridad estable.

Rollback: bajar modulo a `warn` o `off`, manteniendo endpoints legacy activos.

## 4) Tasks consolidadas (fases 1.1 a 8.1)

| Fase | Objetivo | Modulos/archivos foco | Done criteria | Rollback |
|---|---|---|---|---|
| 1.1 | Congelar baseline de paridad funcional legacy+contracts | `hubgh/tests/test_people_ops_backbone.py`, `hubgh/tests/test_flow_phase9_adjustments.py`, fixtures golden | Matriz de paridad definida y tests RED iniciales en CI bench | Ejecutar solo suite legacy |
| 2.1 | Crear backbone canonico aditivo e idempotente | `hubgh/hubgh/doctype/people_ops_event/*`, `hubgh/hubgh/people_ops_event_publishers.py`, `hubgh/hooks.py` | Dual-write en `warn` sin romper fuentes actuales | Flag `off` + detener publish jobs |
| 3.1 | Centralizar policy de sensibilidad/permisos (`warn->enforce`) | `hubgh/hubgh/people_ops_policy.py`, `hubgh/hubgh/people_ops_flags.py`, `hubgh/hubgh/permissions.py` | Persona/Punto consumen policy y emiten warnings auditables | Volver modulo a `warn/off` |
| 4.1 | Formalizar handoffs contract-first inter-area | `hubgh/hubgh/people_ops_handoffs.py`, `hubgh/hubgh/contratacion_service.py` | Validadores y estados `pending/ready/blocked/completed` con contract tests | Facade legacy por endpoint |
| 5.1 | Montar Punto 360 hub accionable sin romper shape actual | `hubgh/hubgh/page/punto_360/punto_360.py`, `hubgh/api/module_dashboards.py` | KPIs + acciones por rol con paridad contractual | Apagar widgets nuevos por flag |
| 6.1 | Robustecer documental (vigente/historico/versionado) con sensibilidad | `hubgh/hubgh/document_service.py`, `hubgh/hubgh/permissions.py` | Escenarios de spec y auditoria documental aprobados | Ruta documental legacy + policy `warn` |
| 7.1 | Pipeline aditivo de clima laboral (Excel) | `hubgh/hubgh/climate_normalizer.py`, jobs en `hubgh/hooks.py`, widgets Persona/Punto | Errores reportables y fallback semantico estable | Desactivar job y mantener carga manual |
| 8.1 | Ejecutar rollout por modulo con observabilidad y rollback probado | suites bench site-scoped, logging/auditoria en hooks/servicios | Umbrales de paridad + runbook rollback < 30 min | Degradar modulo a `warn/off` y reactivar wrappers legacy |

### Backlog fuera de esta iteracion

- Formacion/LMS: evaluar contratos internos locales en un cambio futuro dedicado, sin integracion LMS externa, sin publishers LMS y sin handoffs `training_*` en este ciclo.

## Como ejecutar sin romper funcionalidades

Aplicar estas reglas operativas en cada fase:

1. No romper contratos actuales: preservar payload keys, semantica de estados y permisos observables.
2. Desplegar por modulo, no por sistema completo: activar flags graduales (`off`, `warn`, `enforce`).
3. Exigir evidencia antes de promover: contract tests + smoke funcional + telemetria estable.
4. Mantener wrappers/facades durante transicion: consumidores legacy siguen operativos.
5. Evitar migraciones destructivas: solo cambios aditivos y reversibles.
6. Auditar sensibilidad siempre: todo bloqueo/redaccion debe dejar rastro verificable.
7. Definir rollback antes de cada activacion: quien, como, y en cuanto tiempo se revierte.
8. Controlar paridad con datasets golden: comparar legacy vs nuevo en escenarios clave.
9. No mezclar rediseno visual con cambio semantico sin cobertura: UI puede evolucionar, contratos no se rompen.
10. Cerrar cada fase con criterio de done explicito y registro de riesgos remanentes.

---

### Trazabilidad de fuente de verdad

Este plan consolida los artefactos SDD ya cerrados en Engram:

- Proposal: `sdd/hubgh-people-ops-backbone-v1/proposal` (obs #106)
- Spec: `sdd/hubgh-people-ops-backbone-v1/spec` (obs #109)
- Design: `sdd/hubgh-people-ops-backbone-v1/design` (obs #110)
- Tasks: `sdd/hubgh-people-ops-backbone-v1/tasks` (obs #114)
- Decision: `sdd/hubgh-people-ops-backbone-v1/decision-exclude-lms-v1` (obs #118)
