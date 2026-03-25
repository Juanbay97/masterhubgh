# HubGH Wave 1 Change Summary

## 1. Purpose

Track Sprint 1 governance changes in a controlled ledger for adds, modifies, deprecations, and rollback readiness.

References:

- [`Wave 1 Design`](./hubgh-wave-1-design.md)
- [`Wave 1 Implementation Log`](./hubgh-wave-1-implementation-log.md)
- [`Wave 1 Verification`](./hubgh-wave-1-verification.md)

## 2. Change policy

1. Every entry maps to a slice ID from the implementation log
2. Every modify or deprecate entry must include non-regression impact notes
3. Every entry includes rollback notes
4. Additive change strategy is default for Sprint 1

## 3. Additions log

| Change ID | Slice ID | Artifact type | Artifact | Description | Compatibility impact | Verification gate refs | Rollback note |
|---|---|---|---|---|---|---|---|
| W1-ADD-001 | W1-S1 | Documentation | `docs/hubgh-wave-1-design.md` | Governance baseline with entity map, permissions, catalogs, and DocType decisions | None expected | G1, G2, G3, G4, G5, G6 | Revert document commit |
| W1-ADD-002 | W1-S2 | Documentation | `docs/hubgh-wave-1-implementation-log.md` | Prefilled incremental slice checklist template | None expected | G1, G7 | Revert document commit |
| W1-ADD-003 | W1-S3 | Documentation | `docs/hubgh-wave-1-verification.md` | Explicit validation gates and pass fail criteria | None expected | G1, G6, G7, G8 | Revert document commit |
| W1-ADD-004 | W1-S4 | Documentation | `docs/hubgh-wave-1-change-summary.md` | Change ledger initialization for Sprint 1 traceability | None expected | G1, G8 | Revert document commit |
| W1-ADD-005 | W1-S1A | Code and tests | `frappe-bench/apps/hubgh/hubgh/hubgh/governance/wave1_baseline_registry.py`, `frappe-bench/apps/hubgh/hubgh/hubgh/governance/__init__.py`, `frappe-bench/apps/hubgh/hubgh/tests/test_wave1_slice_a_baseline_registry.py` | Added declarative Wave 1 governance baseline registry and invariant tests with no runtime wiring | None expected (additive, non-executing) | W1-S1A-R1, W1-S1A-R2, W1-S1A-R3, W1-S1A-R4 | Revert W1-S1A commit; clear cache/restart workers; re-run onboarding and role-permission regressions |

## 4. Modifications log

| Change ID | Slice ID | Artifact type | Artifact | What changed | Reason | Compatibility impact | Verification gate refs | Rollback note |
|---|---|---|---|---|---|---|---|---|
| W1-MOD-001 | W1-S1A-HOTFIX-ONBOARDING | Code | `frappe-bench/apps/hubgh/hubgh/hubgh/doctype/candidato/candidato.py` | Replaced deterministic onboarding initial password (`numero_documento`) with random temporary password generation and added non-secret audit log | Fix mandatory onboarding security regression (`test_ensure_user_link_generates_non_document_password_and_marks_reset`) | Backward compatible: preserved user-link flow, forced reset flag, endpoint response contract, Persona 360/Punto 360/bandejas behavior | W1-S1A-R2, W1-S1A-R3, W1-S1A-R4 | Revert this file hunk to previous commit, restart workers/web, re-run onboarding security and slice A smoke tests |
| W1-MOD-002 | W1-S2 | Code | `frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py` | Added dimension access matrix (`operational`, `sensitive`, `clinical`) and helper APIs `get_user_dimension_access` + `user_can_access_dimension` with canonical-role alias support | Operationalize Sprint 1 role × dimension model without changing current endpoint contracts | Backward compatible: additive helper layer only; existing permission query entrypoints preserved | W1-S2-R1 | Revert `permissions.py`, clear cache/restart workers, re-run role-permission suite |
| W1-MOD-003 | W1-S2 | Code | `frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py` | Switched Persona 360 sensitive/clinical visibility checks to dimension helpers while keeping API contract unchanged | Enforce dimension-based visibility in a critical read API as first enforcement point | Backward compatible: no route/signature/schema changes; visibility remains role-bounded | W1-S2-R1 | Revert `persona_360.py`, clear cache/restart workers, validate Persona 360 role scenarios |
| W1-MOD-004 | W1-S2 | Tests | `frappe-bench/apps/hubgh/hubgh/tests/test_phase8_role_permissions.py` | Added tests for dimension access matrix behavior and alias compatibility for `Jefe de tienda` and `Relaciones Laborales` | Validate no-regression and alias-safe enforcement before progressing to next slices | Positive safety impact: codifies backward compatibility for legacy role names | W1-S2-R1 | Revert test additions only if needed and re-run suite to confirm baseline |
| W1-MOD-005 | W1-S3 | Tests | `frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py` | Added sync orchestration guard test for `sync_reference_masters` to enforce strict official catalog normalization sequence and commit behavior | Lock transversal catalog governance behavior against regressions before Sprint 1 closeout | Backward compatible: test-only hardening, no runtime contract changes | W1-S3-R1 | Revert this test hunk if required and re-run phase9 adjustments suite |
| W1-MOD-006 | W1-S4 | Code | `frappe-bench/apps/hubgh/hubgh/hubgh/governance/wave1_baseline_registry.py` | Added `DOCTYPE_DECISION_REGISTRY`, allowed decision options, and `validate_doctype_decision_registry()` validator with explicit risk/rollback metadata | Close Sprint 1 DocType strategy governance with a machine-checkable registry | Backward compatible: governance-only module, no runtime hooks/endpoints/schema changes | W1-S4-R1 | Revert S1.4 registry block and re-run baseline registry tests |
| W1-MOD-007 | W1-S4 | Tests | `frappe-bench/apps/hubgh/hubgh/tests/test_wave1_slice_a_baseline_registry.py` | Added assertions validating registry completeness and validator diagnostics | Enforce non-regression and completeness for S1.4 decision governance | Backward compatible: test-only hardening | W1-S4-R1 | Revert test hunk and re-run baseline suite |

## 5. Deprecations log

| Change ID | Slice ID | Artifact or key | Deprecation status | Replacement | Effective rule | Compatibility impact | Rollback note |
|---|---|---|---|---|---|---|---|
| None yet | TBD | TBD | Not started | TBD | TBD | TBD | TBD |

## 6. Rollback journal

| Rollback ID | Trigger condition | Affected change IDs | Execution notes | Validation after rollback | Owner | Date |
|---|---|---|---|---|---|---|
| RB-W1-001 | Governance artifact inconsistency detected during verification | W1-ADD-001 to W1-ADD-004 | Revert latest documentation batch and restore approved baseline | Re-run gates G1 and G8 | TBD | TBD |

## 7. Sprint 1 running totals

- Adds: 5
- Modifies: 7
- Deprecations: 0
- Open rollback risks: 0 critical

## 8. Slice W1-S1A execution note

- Regression check result summary for W1-S1A:
  - W1-S1A-R2: PASS (`test_onboarding_security_phase5::test_ensure_user_link_generates_non_document_password_and_marks_reset`)
  - W1-S1A-R3: PASS (`test_onboarding_security_phase5`)
  - W1-S1A-R4: PASS (`test_wave1_slice_a_baseline_registry`)
- Impact note: Hotfix is minimal and contract-safe; no endpoint/page route/schema changes.
