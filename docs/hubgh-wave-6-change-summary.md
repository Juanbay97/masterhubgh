# HubGH Wave 6 Change Summary

Scope: Sprint 6 SST updates for exam lifecycle, alerts, and clinical confidentiality.

## Modified artifacts

- [`seleccion_documentos.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/seleccion_documentos/seleccion_documentos.py)
- [`test_flow_phase9_adjustments.py`](../frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py)
- [`test_novedad_laboral.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/novedad_laboral/test_novedad_laboral.py)

## Outcomes

1. Medical exam queue now explicitly marks `exam_scope=vigente`; history uses `exam_scope=historico` and `evaluado_en`.
2. Added aging/expiration metadata with responsible assignee for pending medical exams.
3. Added clinical masking path for non-clinical viewers while preserving endpoint contract shape.

## Regression

- `bench --site hubgh.test run-tests --module hubgh.hubgh.doctype.novedad_laboral.test_novedad_laboral`
- `bench --site hubgh.test run-tests --module hubgh.tests.test_flow_phase9_adjustments`
- Result: 33 tests passed.

