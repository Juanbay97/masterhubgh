# HubGH Wave 1 Verification

## 1. Objective

Define explicit Sprint 1 validation gates with pass or fail criteria to ensure governance deliverables are complete and backward-compatible with current HubGH architecture.

References:

- [`Wave 1 Design`](./hubgh-wave-1-design.md)
- [`Wave 1 Implementation Log`](./hubgh-wave-1-implementation-log.md)
- [`HubGH Orchestrated Plan v1`](../plans/hubgh-8-sprint-orchestrated-plan-v1.md)

## 2. Verification operating model

1. Gates are executed in order
2. Each gate must have evidence artifacts
3. Any failed gate blocks Sprint 1 closeout
4. Regression-sensitive gates are mandatory even for documentation-only increments

## 3. Validation gates and pass fail criteria

### Gate G1 Scope and architecture alignment

Purpose: confirm Sprint 1 outputs remain within governance-only scope and preserve current architecture.

Checks:

- Sprint 1 files exist and are versioned
- Scope explicitly excludes runtime code and config mutations
- Architecture statement preserves DocType to Page to Workspace compatibility

Pass criteria:

- All required Sprint 1 docs exist
- No implementation instruction requires breaking architectural change

Fail criteria:

- Missing required Sprint 1 artifact
- Any statement introduces hard break to current architecture contract

Evidence:

- Document links and revision snapshot

### Gate G2 Entity governance completeness

Purpose: validate entity master map coverage and ownership clarity.

Checks:

- Candidate, hiring, employee, point, documentary, novedades, SST, RRLL, wellbeing domains are represented
- Owner area and lifecycle stage are defined for each core domain
- Coupling to pages and workspaces is documented

Pass criteria:

- No core domain missing
- No entity marked without owner

Fail criteria:

- Missing domain coverage
- Ambiguous ownership that prevents operating decisions

Evidence:

- Completed entity map table in design document

### Gate G3 Permission matrix governance viability

Purpose: ensure role by information-dimension governance is explicit and operationally safe.

Checks:

- Matrix includes canonical operational and GH roles
- Sensitive dimensions include at least disciplinary and SST confidentiality controls
- Candidate, employee, and operational roles remain bounded

Pass criteria:

- Matrix includes all required roles and dimensions
- Sensitive data boundaries are explicitly constrained

Fail criteria:

- Missing required role coverage
- Sensitive dimensions not separated by role responsibility

Evidence:

- Permission matrix and compatibility notes from design doc

### Gate G4 Shared catalog governance readiness

Purpose: validate catalog control rules are enforceable and backward-compatible.

Checks:

- Catalog families are enumerated
- Single owner and additive-change rule are defined
- Key stability and deprecation policy are explicit
- Bandeja status semantics compatibility is acknowledged

Pass criteria:

- Governance rules are complete and conflict-free

Fail criteria:

- Catalog changes allowed without owner or deprecation control

Evidence:

- Catalog governance section and approval notes

### Gate G5 DocType strategy non-disruptive decisioning

Purpose: verify reuse vs extend vs create decisions are complete and non-disruptive.

Checks:

- Decision table covers core impacted DocTypes
- Each row has rationale and guardrail
- New DocType creation is restricted to truly missing governance gaps

Pass criteria:

- Decision table complete with backward-compatibility guardrails

Fail criteria:

- Impacted domain without decision entry
- Decision requires destructive replacement in Sprint 1

Evidence:

- DocType decision table and reviewer approval record

### Gate G6 Non-regression constraints completeness

Purpose: guarantee explicit protection of critical current flows.

Checks:

- Constraints exist for onboarding
- Constraints exist for Persona 360
- Constraints exist for Punto 360
- Constraints exist for bandejas and endpoint contracts

Pass criteria:

- All four non-regression sections present and actionable

Fail criteria:

- Any critical flow missing guardrails

Evidence:

- Non-regression section in design doc

### Gate G7 Implementation log traceability

Purpose: ensure Sprint 1 can be executed incrementally with reversible control.

Checks:

- Slice template includes scope, change map, verification, rollback, approvals
- Prefilled Sprint 1 slice backlog is present
- Sprint closure checklist references non-regression gates

Pass criteria:

- Implementation log can support slice-by-slice controlled execution

Fail criteria:

- Missing rollback or verification sections

Evidence:

- Implementation log template and prefilled slices

### Gate G8 Change summary initialization integrity

Purpose: validate readiness for ongoing adds modifies deprecations and rollback tracking.

Checks:

- Change summary document initialized
- Sections include additions, modifications, deprecations, and rollback notes
- Entries can be linked to slice IDs

Pass criteria:

- Change summary structure supports traceable incremental updates

Fail criteria:

- Missing key change tracking dimensions

Evidence:

- Wave 1 change summary template

## 4. Gate result register

| Gate ID | Status | Evidence reference | Reviewer | Date | Notes |
|---|---|---|---|---|---|
| G1 | Pending | TBD | TBD | TBD |  |
| G2 | Pending | TBD | TBD | TBD |  |
| G3 | Pending | TBD | TBD | TBD |  |
| G4 | Pending | TBD | TBD | TBD |  |
| G5 | Pending | TBD | TBD | TBD |  |
| G6 | Pending | TBD | TBD | TBD |  |
| G7 | Pending | TBD | TBD | TBD |  |
| G8 | Pending | TBD | TBD | TBD |  |

## 5. Sprint 1 final pass rule

Sprint 1 verification is considered passed only when all gates G1 through G8 are marked Pass and no open blocker remains in the implementation log or change summary.

## 6. Slice execution record: W1-S1A

| Check ID | Command | Status | Notes |
|---|---|---|---|
| W1-S1A-R1 | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_wave1_slice_a_baseline_registry` | Pass | 5 tests passed |
| W1-S1A-R2 | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_onboarding_security_phase5 --test test_ensure_user_link_generates_non_document_password_and_marks_reset` | Pass | Regression fixed with security hotfix |
| W1-S1A-R3 | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_onboarding_security_phase5` | Pass | 12 tests passed |
| W1-S1A-R4 | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_wave1_slice_a_baseline_registry` | Pass | 5 tests passed (smoke re-check) |

## 6.1 Slice execution record: W1-S2

| Check ID | Command | Status | Notes |
|---|---|---|---|
| W1-S2-R1 | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_phase8_role_permissions` | Pass | 14 tests passed; includes new dimension matrix checks and alias compatibility assertions |

## 6.2 Slice execution record: W1-S3

| Check ID | Command | Status | Notes |
|---|---|---|---|
| W1-S3-R1 | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments` | Pass | 21 tests passed; includes catalog repoint/disable assertions and sync guard coverage |

## 6.3 Slice execution record: W1-S4

| Check ID | Command | Status | Notes |
|---|---|---|---|
| W1-S4-R1 | `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_wave1_slice_a_baseline_registry` | Pass | 6 tests passed; includes DocType decision registry completeness validator |

## 7. Hotfix trace: onboarding security regression

- Affected test: `hubgh.tests.test_onboarding_security_phase5::test_ensure_user_link_generates_non_document_password_and_marks_reset`
- Root cause: initial onboarding password was set equal to `numero_documento` inside candidate user linking path.
- Minimal fix: generate a random temporary password (`secrets.token_urlsafe(24)`) and keep forced-reset semantics unchanged.
- Safety note: no endpoint contract changes, no schema changes, no runtime routing changes.

W1-S1A compatibility statement: Slice changes are additive and declarative only (new registry package, static baseline registry, and validation tests). No endpoint signatures, page routes, workspace visibility semantics, permission query code, schema, or runtime hooks were modified.
