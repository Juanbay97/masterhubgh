# HubGH Wave 2 Change Summary

Scope: Sprint 2 candidate to employee handoff hardening.

References:

- [`HubGH Wave 2 Design`](./hubgh-wave-2-design.md)
- [`HubGH Wave 2 Implementation Log`](./hubgh-wave-2-implementation-log.md)
- [`HubGH Wave 2 Verification`](./hubgh-wave-2-verification.md)

## 1. Change control metadata

| Field | Value |
|---|---|
| Wave | 2 |
| Sprint focus | Candidate to employee handoff |
| Baseline tag or commit | Pending |
| Release tag or commit | Pending |
| Prepared by | Pending |
| Reviewed by | Pending |
| Status | Draft |

## 2. Add modify deprecate register

## 2.1 Added artifacts

| ID | Artifact | Type | Purpose | Backward compatibility impact | Status |
|---|---|---|---|---|---|
| A-01 | Pending | Contract or code | RRLL final authority gate support | Additive only | Planned |
| A-02 | Pending | Contract or code | Mandatory data and document gate support | Additive only | Planned |
| A-03 | Pending | Contract or code | Candidate employee lineage mapping | Additive only | Planned |
| A-04 | Pending | Contract or code | Handoff event envelope and emitters | Additive only | Planned |
| A-05 | `MANDATORY_INGRESO_FIELDS` + `_validate_mandatory_ingreso_gate` in `frappe-bench/apps/hubgh/hubgh/hubgh/contratacion_service.py` | Code | Enforce S2.1 pre-submit mandatory data/document gate | Additive guard in existing submit flow | Done |

## 2.2 Modified artifacts

| ID | Artifact | Type | Why modified | Expected behavior change | Signature impact | Status |
|---|---|---|---|---|---|---|
| M-01 | `frappe-bench/apps/hubgh/hubgh/hubgh/contratacion_service.py::submit_contract` | Existing service | Enforce mandatory ingreso gate before formal submit | Stricter preconditions only | None | Done |
| M-02 | Pending | Existing read model integration | Show ingreso traceability in 360 | Additive visibility | None allowed | Planned |
| M-03 | Pending | Existing documentary mapping | Preserve candidate dossier continuity | Additive linkage | None allowed | Planned |
| M-04 | `frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py` | Tests | Add regression coverage for mandatory data/document gate on contract submit | Explicit blocked outcomes for incomplete handoff | None | Done |
| M-05 | `frappe-bench/apps/hubgh/hubgh/hubgh/contratacion_service.py::submit_contract` | Existing service | Enforce RRLL final authority in formal ingreso action | Non-RRLL users denied at finalization step | None | Done |
| M-06 | `frappe-bench/apps/hubgh/hubgh/tests/test_phase8_role_permissions.py` | Tests | Add RRLL authority guard coverage (allow legacy RRLL alias, deny Selection) | Explicit role-based finalization checks | None | Done |
| M-07 | `frappe-bench/apps/hubgh/hubgh/hubgh/doctype/contrato/contrato.py::_ensure_employee` | Existing service | Enforce immutable lineage conflict guard and backfill missing candidate origin on existing employee reuse | Deterministic duplicate prevention with safe idempotent reuse | None | Done |
| M-08 | `frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py` | Tests | Add lineage backfill and lineage-conflict regression coverage | Guarantees S2.3 zero-or-one lineage behavior | None | Done |
| M-09 | `frappe-bench/apps/hubgh/hubgh/hubgh/doctype/contrato/contrato.py::on_submit/_publish_ingreso_event` | Existing service | Emit idempotent ingreso trace event into `GH Novedad` on formal submit | Additive event persistence for downstream 360 views | None | Done |
| M-10 | `frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py` | Existing read model integration | Surface ingreso event in timeline through additive `GH Novedad` mapping | Additive timeline item (`type=Ingreso`) | None | Done |
| M-11 | `frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py` | Existing read model integration | Add KPI `kpi_ingreso.ingresos_formalizados_30d` from ingreso event traces | Additive KPI block only | None | Done |
| M-12 | `frappe-bench/apps/hubgh/hubgh/tests/test_flow_phase9_adjustments.py` | Tests | Add event emission and Persona/Punto propagation regression coverage | Locks S2.4 propagation behavior | None | Done |

## 2.3 Deprecated artifacts

| ID | Artifact | Deprecation reason | Replacement | Compatibility window | Status |
|---|---|---|---|---|---|
| D-01 | None planned | Not applicable | Not applicable | Not applicable | Not started |

Rule: deprecation is not expected in Sprint 2. If introduced, include compatibility layer and explicit rollback path.

## 3. Non-regression declaration

Protected surfaces:

1. Selección flows and candidate progression actions
2. Afiliaciones bandeja behavior
3. Contratación approved candidate contract path
4. Existing endpoint names request keys and response envelopes

Declaration checklist:

- [ ] No breaking endpoint signature changes
- [ ] No workflow regressions in protected modules
- [ ] Additive defaults applied for new fields and statuses
- [ ] Existing integrations remain stable for Persona 360 Punto 360 and documentary paths

## 4. Risk and mitigation journal

| Risk ID | Risk | Trigger | Mitigation | Owner | Status |
|---|---|---|---|---|---|
| R-01 | Duplicate employee creation | Missing deterministic identity checks | Enforce duplicate gate with conflict routing | Pending | Open |
| R-02 | Unauthorized ingreso finalization | Role enforcement gap | RRLL-only final action gate with explicit authorization denial | Roo | Mitigated in S2.2 |
| R-03 | Documentary discontinuity | Weak candidate employee linkage | Gate pre-submit through `get_candidate_progress` completeness check | Roo | Mitigated in S2.1 |
| R-04 | 360 integration regression | Additive event surfacing done incorrectly | Contract verification plus regression gates | Roo | Mitigated in S2.4 |
| R-05 | Lineage inconsistency on employee reuse | Existing employee matched by cedula with different candidate origin | Block conflicting lineage and backfill only when origin is empty | Roo | Mitigated in S2.3 |

## 5. Rollback journal

## 5.1 Rollback strategy summary

1. Prefer feature toggles or compatibility switches for new gate logic.
2. Revert additive linkage and event emitters independently when possible.
3. Preserve audit artifacts generated during failed rollout attempts.
4. Keep endpoint signatures unchanged during rollback and forward paths.

## 5.2 Rollback entries

| Entry ID | Date | Change batch | Rollback trigger | Action taken | Data impact | Verification result | Owner |
|---|---|---|---|---|---|---|---|
| RB-01 |  | Pending |  |  |  |  |  |
| RB-02 | 2026-03-12 | S2.1 data/document mandatory gate | Unexpected block in valid contract submit path | Revert `_validate_mandatory_ingreso_gate` invocation in `submit_contract` and guard helper; rerun phase9 suite | None (logic-only) | `hubgh.tests.test_flow_phase9_adjustments` passes | Roo |

## 5.3 Rollback readiness checklist

- [ ] Rollback commands or steps documented
- [ ] Data repair or reconciliation steps documented
- [ ] Post-rollback verification checklist documented
- [ ] Stakeholder communication template prepared

## 6. Approval log

| Role | Name | Decision | Date | Notes |
|---|---|---|---|---|
| Technical owner | Pending | Pending |  |  |
| RRLL authority | Pending | Pending |  |  |
| Product owner | Pending | Pending |  |  |
