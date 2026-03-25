# HubGH Wave 8 Change Summary

Scope: Sprint 8 delivery for training assignment catalog, compliance/expiry indicators, LMS-ready integration contract, and closure regression.

## Modified artifacts

- [`punto_360.py`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py)
- [`test_flow_phase9_adjustments.py`](../frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py)

## Added artifacts

- [`hubgh-wave-8-implementation-log.md`](./hubgh-wave-8-implementation-log.md)
- [`hubgh-wave-8-verification.md`](./hubgh-wave-8-verification.md)
- [`hubgh-wave-8-change-summary.md`](./hubgh-wave-8-change-summary.md)

## Outcomes

1. Added additive endpoint `get_formacion_catalog_assignments` with assignment rules by cargo/rol/punto.
2. Added additive endpoint `get_formacion_compliance` with mandatory completion KPIs and pending alerts payload.
3. Added additive endpoint `get_lms_integration_contract` with active/degraded contract response and capability matrix.
4. Preserved prior endpoint signatures and behavior, extending payloads and routes additively.

## Regression

- `bench --site hubgh.test run-tests --module hubgh.tests.test_flow_phase9_adjustments`
- Result: 41 tests passed.
