# HubGH Wave 5 Change Summary

Scope: Sprint 5 changes for documentary single-source, disciplinary MVP closure enforcement, and controlled retiro consistency.

## Modified artifacts

- [`document_service.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/document_service.py)
- [`caso_disciplinario.json`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/caso_disciplinario/caso_disciplinario.json)
- [`caso_disciplinario.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/caso_disciplinario/caso_disciplinario.py)
- [`novedad_laboral.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/novedad_laboral/novedad_laboral.py)
- [`test_document_phase4_unification.py`](../frappe-bench/apps/hubgh/hubgh/tests/test_document_phase4_unification.py)
- [`test_caso_disciplinario.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/caso_disciplinario/test_caso_disciplinario.py)
- [`test_novedad_laboral.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/doctype/novedad_laboral/test_novedad_laboral.py)

## Key outcomes

1. Canonical person dossier (vigente/histórico/versioned) now sourced only from `Person Document`.
2. Disciplinary case closure requires explicit final decision and close date.
3. Retiro finalization requires closed novelty state and emits a traceability event in `GH Novedad`.

## Regression declaration

- Protected test command passed with 31 tests:
  - `bench --site hubgh.test run-tests --module hubgh.hubgh.doctype.novedad_laboral.test_novedad_laboral --module hubgh.hubgh.doctype.caso_disciplinario.test_caso_disciplinario --module hubgh.tests.test_document_phase4_unification --module hubgh.tests.test_flow_phase9_adjustments`

