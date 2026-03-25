# HubGH Wave 2 Verification

Scope: Sprint 2 candidate to employee handoff hardening verification with explicit gates, pass fail criteria, and required evidence.

Reference artifacts:

- [`HubGH Wave 2 Design`](./hubgh-wave-2-design.md)
- [`HubGH Wave 2 Implementation Log`](./hubgh-wave-2-implementation-log.md)
- [`HubGH Orchestrated Plan v1`](../plans/hubgh-8-sprint-orchestrated-plan-v1.md)

## 1. Verification protocol

1. Evaluate gates in sequence.
2. Any gate with fail status blocks release readiness.
3. Evidence must be attached per gate and traceable to a run id or execution record.
4. Non-regression gates are mandatory even when no direct code touch is expected.

## 2. Sprint 2 gates

| Gate ID | Gate name | Objective | Status |
|---|---|---|---|
| G2-01 | RRLL authority gate | Confirm RRLL is final authority for ingreso | Pass |
| G2-02 | Mandatory data gate | Confirm required data blocks or allows handoff correctly | Pass |
| G2-03 | Mandatory document gate | Confirm required dossier blocks or allows handoff correctly | Pass |
| G2-04 | Duplicate prevention gate | Confirm no duplicate employee creation and deterministic conflict behavior | Pass |
| G2-05 | Candidate employee lineage gate | Confirm immutable lineage mapping and idempotent link behavior | Pass |
| G2-06 | Event traceability gate | Confirm required handoff events and normalized envelope | Pass |
| G2-07 | Persona 360 integration gate | Confirm ingreso trace appears with no contract break | Pass |
| G2-08 | Punto 360 integration gate | Confirm post-handoff context with stable KPI semantics | Pass |
| G2-09 | Documentary continuity gate | Confirm candidate dossier continuity into employee context | Pending |
| G2-10 | Non-regression gate | Confirm selección afiliaciones contratación and signatures remain stable | Pending |

## 3. Detailed pass fail criteria and required evidence

## G2-01 RRLL authority gate

Pass criteria:

1. Final ingreso action can only be executed by RRLL-authorized role.
2. Non-RRLL attempt is denied with explicit authorization outcome.
3. Approval and rejection both create auditable decision traces.

Fail criteria:

1. Any non-RRLL role can finalize ingreso.
2. Decision path lacks auditable actor role or decision result.

Required evidence:

1. Access test matrix by role.
2. Decision audit records for approved and rejected flows.
3. Trace showing actor role at decision point.

## G2-02 Mandatory data gate

Pass criteria:

1. Handoff proceeds when all minimum fields are present and valid.
2. Handoff is blocked when any required field is missing.
3. Error outcome is explicit and deterministic.

Fail criteria:

1. Missing required data still permits handoff.
2. Validation errors are ambiguous or inconsistent for same input.

Required evidence:

1. Positive test payload and outcome.
2. Negative test payload missing fields and blocked outcome.
3. Validation result logs or screenshots.

## G2-03 Mandatory document gate

Pass criteria:

1. Required dossier completeness is enforced before RRLL finalization.
2. Incomplete dossier blocks handoff with reason code.
3. Existing candidate document upload and retrieval path remains operational.

Fail criteria:

1. Incomplete required documents still allow handoff.
2. Existing document journey breaks.

Required evidence:

1. Complete dossier pass case.
2. Incomplete dossier fail case.
3. Candidate document upload retrieval smoke evidence.

## G2-04 Duplicate prevention gate

Pass criteria:

1. Exact identity match prevents duplicate employee creation.
2. Existing employee match yields linkage outcome.
3. Ambiguous conflicts block automatic conversion and route to RRLL resolution.

Fail criteria:

1. Duplicate employee record is created for matching identity.
2. Conflict scenarios produce nondeterministic outcomes.

Required evidence:

1. No-match create or link case.
2. Existing-match link case.
3. Ambiguous conflict blocked case with reason code.

## G2-05 Candidate employee lineage gate

Pass criteria:

1. Approved handoff stores immutable candidate to employee lineage.
2. Candidate maps to zero or one canonical employee within Sprint 2 scope.
3. Retry on same operation is idempotent.

Fail criteria:

1. Employee record lacks candidate origin trace.
2. Duplicate lineage links are created on retry.

Required evidence:

1. Candidate and employee linked records.
2. Retry execution proof showing no duplication.
3. Query proof from both candidate and employee context.

## G2-06 Event traceability gate

Pass criteria:

1. Required handoff events are emitted and persisted.
2. Event envelope includes actor role, decision, reason code, timestamp, correlation id.
3. Event sequence supports end to end reconstruction.

Fail criteria:

1. Missing required event types for key decision points.
2. Event envelope missing mandatory metadata fields.

Required evidence:

1. Event samples for pass and fail paths.
2. Correlation chain from validation to final handoff outcome.
3. Event schema snapshot.

## G2-07 Persona 360 integration gate

Pass criteria:

1. Ingreso appears in Persona 360 timeline for authorized roles.
2. Candidate origin trace is visible in authorized context.
3. Existing route and response contract remain unchanged.

Fail criteria:

1. Ingreso event does not appear after successful handoff.
2. Existing Persona 360 load behavior or response contract is broken.

Required evidence:

1. Persona 360 timeline capture with ingreso event.
2. Contract compatibility check output.
3. Role-based visibility proof.

## G2-08 Punto 360 integration gate

Pass criteria:

1. Post-handoff employee linkage context appears in Punto 360 dependent views.
2. Active headcount semantics remain unchanged.
3. Existing filters and route behavior remain stable.

Fail criteria:

1. Handoff breaks existing Punto 360 view behavior.
2. Active headcount logic changes unexpectedly.

Required evidence:

1. Before and after Punto 360 comparison for affected records.
2. Headcount consistency check output.
3. Filter and route compatibility smoke results.

## G2-09 Documentary continuity gate

Pass criteria:

1. Candidate dossier remains linked and traceable from employee context.
2. Historical evidence remains queryable.
3. Existing candidate document paths remain operational.

Fail criteria:

1. Candidate to employee document continuity is lost.
2. Any existing retrieval path is broken.

Required evidence:

1. Candidate dossier continuity example.
2. Historical retrieval proof.
3. Candidate document flow smoke results.

## G2-10 Non-regression gate

Pass criteria:

1. Selección behavior remains unchanged.
2. Afiliaciones behavior remains unchanged.
3. Contratación behavior remains unchanged.
4. Endpoint names, request keys, and response envelopes remain backward-compatible.

Fail criteria:

1. Any of the protected modules show behavior regressions.
2. Any endpoint signature break is detected.

Required evidence:

1. Regression checklist execution report.
2. Endpoint compatibility matrix.
3. Error-free smoke run summary for protected modules.

## 4. Gate execution tracker

| Gate ID | Executed by | Execution date | Result | Evidence reference | Notes |
|---|---|---|---|---|---|
| G2-01 | Roo | 2026-03-12 | Pass | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_phase8_role_permissions` | Covered by `test_validate_rrll_authority_allows_rrll_alias` and `test_validate_rrll_authority_denies_selection_role` |
| G2-02 | Roo | 2026-03-12 | Pass | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments` | Covered by `test_submit_contract_blocks_when_mandatory_ingreso_data_missing` |
| G2-03 | Roo | 2026-03-12 | Pass | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments` | Covered by `test_submit_contract_blocks_when_mandatory_documents_incomplete` |
| G2-04 | Roo | 2026-03-12 | Pass | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments` | Covered by `test_contract_ensure_employee_blocks_conflicting_candidate_lineage` |
| G2-05 | Roo | 2026-03-12 | Pass | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments` | Covered by `test_contract_ensure_employee_backfills_missing_candidate_lineage_on_existing_employee` |
| G2-06 | Roo | 2026-03-12 | Pass | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments` | Covered by `test_contract_publish_ingreso_event_creates_closed_rrll_novedad` and idempotency skip test |
| G2-07 | Roo | 2026-03-12 | Pass | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments` | Covered by `test_persona_360_includes_ingreso_event_from_gh_novedad` |
| G2-08 | Roo | 2026-03-12 | Pass | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments` | Covered by `test_punto_360_exposes_ingresos_formalizados_kpi` |
| G2-09 |  |  |  |  |  |
| G2-10 |  |  |  |  |  |

## 5. Release decision

- [ ] All gates passed
- [ ] Evidence package complete
- [ ] Rollback package validated
- [ ] Change summary updated

Decision record:

- Decision: Pending
- Date:
- Approved by:
- Notes:
