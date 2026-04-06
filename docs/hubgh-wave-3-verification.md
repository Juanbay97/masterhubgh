# HubGH Wave 3 Verification

Scope: Sprint 3 Persona 360 v2 verification for event envelope, filters/sections, and contextual action permissions.

Reference artifacts:

- [`HubGH Wave 3 Design`](./hubgh-wave-3-design.md)
- [`HubGH Wave 3 Implementation Log`](./hubgh-wave-3-implementation-log.md)
- [`HubGH Orchestrated Plan v1`](../plans/hubgh-8-sprint-orchestrated-plan-v1.md)

## 1. Verification protocol

1. Execute gates in order.
2. Any fail blocks Sprint 3 readiness.
3. Evidence must include test case pointers and command output references.
4. Non-regression against Wave 2 Persona/Punto integrations is mandatory.

## 2. Sprint 3 gates

| Gate ID | Gate name | Objective | Status |
|---|---|---|---|
| G3-01 | Unified envelope gate | Validate single event structure across timeline sources | Pass |
| G3-02 | Filter and section gate | Validate operational filters and grouped sections behavior | Pass |
| G3-03 | Contextual actions permission gate | Validate quick action visibility by permission context | Pass |
| G3-04 | Non-regression gate | Validate Wave 2 ingreso propagation and timeline compatibility | Pass |

## 3. Detailed pass/fail criteria and required evidence

## G3-01 Unified envelope gate

Pass criteria:

1. Timeline items from all sources expose unified metadata keys.
2. Legacy keys expected by existing frontend remain present.
3. Ingreso event remains visible in Persona timeline.

Fail criteria:

1. Any timeline source omits required envelope keys.
2. Existing frontend key contract (`type`, `title`, `date`, `desc`, `ref`, `color`) breaks.

Required evidence:

1. Code path using [`_event_entry()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py:10).
2. Regression test [`test_persona_360_includes_ingreso_event_from_gh_novedad()`](../frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py:141).

## G3-02 Filter and section gate

Pass criteria:

1. Optional filters by module/state/severity/date are applied deterministically.
2. No-filter behavior returns full timeline as before.
3. Grouped sections are returned additively without replacing `timeline`.

Fail criteria:

1. Filter mismatch returns unexpected events.
2. Existing consumer path relying on `timeline` is broken.

Required evidence:

1. Regression test [`test_persona_360_supports_module_state_and_date_filters_with_sections()`](../frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py:197).
2. Response keys from [`get_persona_stats()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py:80): `timeline`, `timeline_sections`, `filters_applied`.

## G3-03 Contextual actions permission gate

Pass criteria:

1. Backend publishes quick actions with explicit visibility flags.
2. Frontend renders only visible actions.
3. Employee self-profile cannot see create actions reserved for GH/Jefe contexts.

Fail criteria:

1. Unauthorized roles can see/create restricted actions.
2. Frontend ignores backend visibility flags.

Required evidence:

1. Regression test [`test_persona_360_contextual_actions_hide_creation_for_employee_profile()`](../frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py:291).
2. Frontend rendering branch in [`render_contextual_action_buttons()`](../frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.js:252).

## G3-04 Non-regression gate

Pass criteria:

1. Sprint 2 ingreso propagation remains operational.
2. Persona timeline load path remains stable.
3. No endpoint-breaking changes introduced.

Fail criteria:

1. Existing Sprint 2 timeline integration breaks.
2. Existing module regression detected in test suite.

Required evidence:

1. Command output:
   - `bench --site hubgh.test run-tests --module hubgh.tests.test_flow_phase9_adjustments`
2. Suite status: 31 tests, all pass.

## 4. Gate execution tracker

| Date | Gate ID | Executor | Evidence reference | Result |
|---|---|---|---|---|
| 2026-03-12 | G3-01 | Roo | `test_persona_360_includes_ingreso_event_from_gh_novedad` + module run | Pass |
| 2026-03-12 | G3-02 | Roo | `test_persona_360_supports_module_state_and_date_filters_with_sections` + module run | Pass |
| 2026-03-12 | G3-03 | Roo | `test_persona_360_contextual_actions_hide_creation_for_employee_profile` + module run | Pass |
| 2026-03-12 | G3-04 | Roo | `bench --site hubgh.test run-tests --module hubgh.tests.test_flow_phase9_adjustments` | Pass |

## 5. Release decision

Wave 3 / Sprint 3 gates are satisfied for implemented slices S3.1-S3.3 with additive contracts and no detected regressions in the protected phase9 suite.

