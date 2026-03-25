# HubGH Wave 5 Implementation Log

Status: Sprint 5 execution record (documental único, disciplinario MVP, retiro controlado).

Reference:

- [`HubGH Plan Operativo S1-S8`](../plans/hubgh-plan-operativo-slices-s1-s8.md)

## Slice register

| Slice | Objective | Status | Owner |
|---|---|---|---|
| S5-01 | Expediente documental único | Done | Roo |
| S5-02 | Flujo disciplinario MVP | Done | Roo |
| S5-03 | Retiro controlado | Done | Roo |

## S5-01 Expediente documental único

Artifacts:

- [`document_service.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/document_service.py)
- [`test_document_phase4_unification.py`](../frappe-bench/apps/hubgh/hubgh/tests/test_document_phase4_unification.py)

Implemented:

- Canonical dossier builder with vigente/histórico/versionado using `Person Document` as single source.
- Candidate progress and ZIP generation now consume canonical dossier views.

## S5-02 Flujo disciplinario MVP

Artifacts:

- [`caso_disciplinario.json`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/caso_disciplinario/caso_disciplinario.json)
- [`caso_disciplinario.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/caso_disciplinario/caso_disciplinario.py)
- [`test_caso_disciplinario.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/caso_disciplinario/test_caso_disciplinario.py)

Implemented:

- Added closure fields `decision_final`, `fecha_cierre`.
- Enforced rule: cannot close disciplinary case without final decision and close date.

## S5-03 Retiro controlado

Artifacts:

- [`novedad_laboral.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/novedad_laboral/novedad_laboral.py)
- [`test_novedad_laboral.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/novedad_laboral/test_novedad_laboral.py)

Implemented:

- Enforced retiro consistency: retiro finalization requires closed novelty state.
- Added traceability event emission to `GH Novedad` for controlled retiro closure.

## Regression evidence

Command executed:

- `bench --site hubgh.test run-tests --module hubgh.hubgh.doctype.novedad_laboral.test_novedad_laboral --module hubgh.hubgh.doctype.caso_disciplinario.test_caso_disciplinario --module hubgh.tests.test_document_phase4_unification --module hubgh.tests.test_flow_phase9_adjustments`

Result:

- 31 tests passed.

