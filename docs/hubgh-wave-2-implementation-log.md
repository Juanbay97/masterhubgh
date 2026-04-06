# HubGH Wave 2 Implementation Log

Status: Prefilled slice-by-slice execution checklist template for Sprint 2 candidate to employee handoff hardening.

Related design reference:

- [`HubGH Wave 2 Design`](./hubgh-wave-2-design.md)

## 1. Usage instructions

1. Execute slices in order.
2. For each slice, record exact artifacts touched, validation evidence, and rollback note.
3. Keep all changes backward-compatible with current endpoint signatures and existing flows.
4. Use additive behavior and preserve RRLL final authority at formal ingreso.

---

## 2. Slice register

| Slice | Objective | Planned status | Owner | Notes |
|---|---|---|---|---|
| S2-01 | Baseline and contract alignment | Not started | Unassigned | Confirm scope and non-regression baseline |
| S2-02 | Formal RRLL authority gate | Done | Roo | `submit_contract` now requires RRLL authority (`HR Labor Relations` / `System Manager` / `Administrator`) |
| S2-03 | Mandatory data gate | Done | Roo | Enforced in submit_contract pre-gate with deterministic missing-field blocking |
| S2-04 | Mandatory document gate | Done | Roo | Enforced in submit_contract via candidate required dossier completeness |
| S2-05 | Duplicate-prevention controls | Done | Roo | Existing employee with conflicting lineage is blocked deterministically |
| S2-06 | Candidate employee lineage persistence | Done | Roo | Existing employee lineage backfilled when missing; conflict-safe idempotent reuse |
| S2-07 | Event traceability contract | Done | Roo | `on_submit` now emits idempotent ingreso event in `GH Novedad` |
| S2-08 | Persona 360 and Punto 360 integration | Done | Roo | Persona timeline and Punto KPI ingest ingreso event without contract breaks |
| S2-09 | Documentary linkage integration | Not started | Unassigned | Candidate dossier continuity into employee context |
| S2-10 | Regression and release readiness | Not started | Unassigned | Final checks, evidence packaging, rollback readiness |

---

## 3. Slice execution checklist details

## S2-01 Baseline and contract alignment

- [ ] Confirm Sprint 2 scope matches [`HubGH Wave 2 Design`](./hubgh-wave-2-design.md)
- [ ] Confirm non-regression contract for selección afiliaciones contratación
- [ ] Confirm endpoint signature freeze list
- [ ] Record baseline affected artifacts inventory

Execution log:

- Date:
- Operator:
- Artifacts reviewed:
- Decisions:

Evidence required:

- Baseline contract checklist attached
- Signature freeze list attached

Rollback note:

- No runtime changes expected in this slice

---

## S2-02 Formal RRLL authority gate

- [x] Implement or configure formal RRLL final decision gate
- [x] Ensure non-RRLL roles cannot finalize ingreso
- [x] Record denial path behavior and reason codes

Execution log:

- Date: 2026-03-12
- Operator: Roo
- Artifacts touched:
  - `frappe-bench/apps/hubgh/hubgh/hubgh/contratacion_service.py`
  - `frappe-bench/apps/hubgh/hubgh/tests/test_phase8_role_permissions.py`
- Decision path summary:
  - New guard `validate_rrll_authority()` invoked in `submit_contract`
  - Allowed roles: `HR Labor Relations`, `System Manager`, `Administrator`
  - Denied roles now receive explicit RRLL authority message

Evidence required:

- Access matrix proof for RRLL-only finalization:
  - `test_validate_rrll_authority_allows_rrll_alias`
  - `test_validate_rrll_authority_denies_selection_role`
- Regression suite evidence:
  - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_phase8_role_permissions`
  - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments`

Rollback note:

- Revert `validate_rrll_authority` usage in `submit_contract`, then re-run role permission and phase9 suites

---

## S2-03 Mandatory data gate

- [x] Define minimum required data fields for handoff readiness
- [x] Enforce blocking behavior when required data is missing
- [x] Keep request and response payload contracts backward-compatible

Execution log:

- Date: 2026-03-12
- Operator: Roo
- Artifacts touched:
  - `frappe-bench/apps/hubgh/hubgh/hubgh/contratacion_service.py`
  - `frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py`
- Validation rules added:
  - Mandatory ingreso fields (`numero_documento`, `nombres`, `apellidos`, `pdv_destino`, `cargo`, `fecha_ingreso`, `tipo_contrato`)
  - Salary gate (`salario > 0`)
  - Deterministic blocking message path before formal contract submit

Evidence required:

- Failing case with missing mandatory data and explicit message: `test_submit_contract_blocks_when_mandatory_ingreso_data_missing`
- Regression suite evidence:
  - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments`

Rollback note:

- Revert `_validate_mandatory_ingreso_gate` branch in `submit_contract` and rerun phase9 adjustment tests

---

## S2-04 Mandatory document gate

- [x] Define required documents for ingreso eligibility
- [x] Enforce block when dossier is incomplete
- [x] Preserve existing upload and retrieval paths

Execution log:

- Date: 2026-03-12
- Operator: Roo
- Artifacts touched:
  - `frappe-bench/apps/hubgh/hubgh/hubgh/contratacion_service.py`
  - `frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py`
- Required documents matrix:
  - Existing candidate required-hiring matrix resolved via `get_candidate_progress`

Evidence required:

- Incomplete dossier case fails gate with reason code: `test_submit_contract_blocks_when_mandatory_documents_incomplete`
- Regression suite evidence:
  - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments`

Rollback note:

- Revert document completeness branch in `_validate_mandatory_ingreso_gate` and rerun protected module tests

---

## S2-05 Duplicate-prevention controls

- [x] Implement deterministic identifier match checks
- [x] Prevent parallel handoff races via lock or idempotency key
- [x] Route ambiguous conflicts to RRLL resolution path

Execution log:

- Date: 2026-03-12
- Operator: Roo
- Artifacts touched:
  - `frappe-bench/apps/hubgh/hubgh/hubgh/doctype/contrato/contrato.py`
  - `frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py`
- Duplicate logic outcomes:
  - Existing employee by `cedula` is reused.
  - If existing employee already has different `candidato_origen`, conversion is blocked with deterministic conflict error.

Evidence required:

- Existing employee scenario links without duplicate creation:
  - `test_contract_ensure_employee_backfills_missing_candidate_lineage_on_existing_employee`
- Ambiguous scenario blocks and routes to RRLL review:
  - `test_contract_ensure_employee_blocks_conflicting_candidate_lineage`
- Regression suite evidence:
  - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments`

Rollback note:

- Revert `_ensure_employee` conflict/backfill branch and rerun phase9 suite

---

## S2-06 Candidate employee lineage persistence

- [x] Persist immutable candidate origin to employee linkage
- [x] Ensure zero-or-one candidate to employee mapping in Sprint 2 scope
- [x] Validate idempotent behavior under retry

Execution log:

- Date: 2026-03-12
- Operator: Roo
- Artifacts touched:
  - `frappe-bench/apps/hubgh/hubgh/hubgh/doctype/contrato/contrato.py`
  - `frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py`
- Lineage mapping details:
  - For reused employee records, `candidato_origen` is backfilled only when empty.
  - When lineage exists with a different candidate, operation is rejected to preserve immutability.

Evidence required:

- Link record visible and queryable from candidate and employee context:
  - `test_contract_ensure_employee_backfills_missing_candidate_lineage_on_existing_employee`
- Retry/idempotency safety via deterministic reuse and conflict guard:
  - `test_contract_ensure_employee_blocks_conflicting_candidate_lineage`
- Regression suite evidence:
  - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments`

Rollback note:

- Revert `_ensure_employee` lineage guard/backfill branch and rerun protected tests

---

## S2-07 Event traceability contract

- [x] Emit required handoff events with normalized envelope
- [x] Persist actor role decision result reason and correlation metadata
- [x] Keep event publishing additive and non-breaking

Execution log:

- Date: 2026-03-12
- Operator: Roo
- Artifacts touched:
  - `frappe-bench/apps/hubgh/hubgh/hubgh/doctype/contrato/contrato.py`
  - `frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py`
- Event contract notes:
  - On contract submit, `Contrato._publish_ingreso_event` creates `GH Novedad` with idempotency check.
  - Event payload includes persona, punto, fecha, estado cerrado y descripción con referencia de contrato.

Evidence required:

- Event emission evidence:
  - `test_contract_publish_ingreso_event_creates_closed_rrll_novedad`
  - `test_contract_publish_ingreso_event_skips_when_already_exists`
- Regression suite evidence:
  - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments`

Rollback note:

- Revert `_publish_ingreso_event` invocation and helper in `Contrato` controller; rerun phase9 suite

---

## S2-08 Persona 360 and Punto 360 integration

- [x] Surface ingreso event in Persona 360 timeline
- [x] Ensure Punto 360 receives post-handoff employee linkage context
- [x] Keep page routes filters and endpoint signatures unchanged

Execution log:

- Date: 2026-03-12
- Operator: Roo
- Artifacts touched:
  - `frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py`
  - `frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py`
  - `frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py`
- Integration notes:
  - Persona 360 adds additive timeline entries for `GH Novedad` ingreso events.
  - Punto 360 adds additive KPI block `kpi_ingreso.ingresos_formalizados_30d`.

Evidence required:

- Persona 360 timeline evidence showing ingreso event:
  - `test_persona_360_includes_ingreso_event_from_gh_novedad`
- Punto 360 evidence with stable headcount behavior:
  - `test_punto_360_exposes_ingresos_formalizados_kpi`
- Regression suite evidence:
  - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments`

Rollback note:

- Revert additive Persona/Punto blocks and rerun phase9 + role permission suites

---

## S2-09 Documentary linkage integration

- [ ] Link candidate dossier continuity into employee documentary context
- [ ] Preserve historical and latest valid evidence semantics
- [ ] Avoid breaking current candidate document journeys

Execution log:

- Date:
- Operator:
- Artifacts touched:
- Documentary mapping notes:

Evidence required:

- Candidate to employee documentary lineage example
- Existing candidate upload retrieval smoke checks

Rollback note:

- Revert documentary bridge mapping and maintain original references

---

## S2-10 Regression and release readiness

- [ ] Execute Sprint 2 verification gates from [`HubGH Wave 2 Verification`](./hubgh-wave-2-verification.md)
- [ ] Confirm non-regression in selección afiliaciones contratación and endpoint signatures
- [ ] Complete change summary and rollback journal updates

Execution log:

- Date:
- Operator:
- Artifacts touched:
- Final readiness decision:

Evidence required:

- Verification gate report complete
- Change summary updated and approved

Rollback note:

- Release rollback package validated and stored

---

## 4. Cross-slice non-regression tracker

| Guardrail | Checkpoint | Status | Evidence link |
|---|---|---|---|
| Selección behavior unchanged | Candidate progression actions | Pending | |
| Afiliaciones behavior unchanged | Existing bandeja actions | Pending | |
| Contratación behavior unchanged | Contract path for approved candidates | Pending | |
| Endpoint signatures unchanged | Request response compatibility matrix | Pending | |
| Bandeja visual consistency preserved | Tokens classes indicator semantics | Pending | |

## 5. Final sign-off

- [ ] Technical owner sign-off
- [ ] RRLL authority sign-off
- [ ] Product owner sign-off
- [ ] Orchestrator packet updated

Sign-off record:

- Date:
- Sprint:
- Approved by:
- Notes:
