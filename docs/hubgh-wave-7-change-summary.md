# HubGH Wave 7 Change Summary

Scope: Sprint 7 updates for bienestar follow-up cadence, probation escalation, and climate aggregates.

## Modified artifacts

- [`persona_360.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py)
- [`comentario_bienestar.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/comentario_bienestar/comentario_bienestar.py)
- [`comentario_bienestar.json`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/comentario_bienestar/comentario_bienestar.json)
- [`punto_360.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py)
- [`test_flow_phase9_adjustments.py`](../frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py)

## Outcomes

1. Persona 360 now exposes additive follow-up history `bienestar_followups` for checkpoints 5/15/30 with deterministic status values.
2. `Comentario Bienestar` now supports probation outcome types and routes non-approved outcomes to `GH-RRLL` through additive `GH Novedad` creation.
3. Punto 360 now exposes additive climate KPIs in `kpi_clima`, including probation outcome counters and topic rollups.

## Regression

- `bench --site hubgh.test run-tests --module hubgh.tests.test_flow_phase9_adjustments`
- Result: 38 tests passed.
