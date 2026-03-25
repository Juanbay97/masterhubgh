# HubGH Wave 1 Slice A Implementation Spec

## 1. Slice identity and intent

- Slice ID: **W1-S1A**
- Slice name: **Governance baseline codification with zero runtime behavior change**
- Sprint: **Wave 1 Sprint 1**
- Primary objective: codify Sprint 1 governance contracts in executable, testable artifacts without changing active business flows.

This is the safest first implementation slice because it is **additive and read-only at runtime**: no endpoint signatures, no DocType schema, no workspace routes, no page contracts, and no existing permission query behavior are altered.

---

## 2. Backward-compatibility contract

Protected modules must remain unchanged after this slice:

1. Onboarding candidate creation and candidate document flow
2. Persona 360 route and response contract
3. Punto 360 route, filters, and active headcount semantics
4. Bandejas selection, afiliaciones, contratación action signatures

Compatibility strategy in Slice A:

- Add only governance registry code and validation tests
- Do not hook registry into request-time permission code
- Do not run migrations or patch scripts
- Do not modify client JS for onboarding, 360 pages, or bandejas

---

## 3. Exact file-level implementation plan

## 3.1 Files to create

| File | Action | Exact content scope | Runtime impact |
|---|---|---|---|
| `frappe-bench/apps/hubgh/hubgh/hubgh/governance/__init__.py` | Create | Package marker for governance registry modules | None |
| `frappe-bench/apps/hubgh/hubgh/hubgh/governance/wave1_baseline_registry.py` | Create | Static dictionaries for entity ownership baseline, role-dimension matrix baseline, shared catalog baseline, and DocType strategy baseline aligned to Wave 1 design | None unless imported explicitly |
| `frappe-bench/apps/hubgh/hubgh/tests/test_wave1_slice_a_baseline_registry.py` | Create | Unit tests that validate coverage and invariants of registry content against canonical role aliases and protected non-regression rules | Test-only |

## 3.2 Files to modify

| File | Action | Exact modification | Rationale |
|---|---|---|---|
| `docs/hubgh-wave-1-implementation-log.md` | Modify | Add executed entry for `W1-S1A` with evidence, non-regression declaration, and rollback note | Keep Sprint 1 traceability current |
| `docs/hubgh-wave-1-change-summary.md` | Modify | Add one `ADD` change record for governance registry code + tests | Maintain ledger and rollback mapping |

## 3.3 Files explicitly not touched in Slice A

- No changes to `hooks.py`
- No changes to page controllers under `hubgh/hubgh/hubgh/page/*`
- No changes to onboarding handlers under `hubgh/www/*`
- No changes to runtime permission functions under `hubgh/hubgh/permissions.py`
- No changes to DocType JSON schema under `hubgh/hubgh/hubgh/doctype/*/*.json`

---

## 4. Exact data model, permission, and catalog changes

## 4.1 Data model changes

- **Database schema changes: NONE**
- **DocType field changes: NONE**
- **Child table changes: NONE**

## 4.2 Permission changes

- **Runtime RBAC grant/revoke changes: NONE**
- **Permission query condition changes: NONE**
- **Page role assignment changes: NONE**

Declarative governance artifact added (non-executing baseline only):

- Role-by-dimension baseline matrix (`D1..D7`) captured in `wave1_baseline_registry.py`
- Canonical roles plus transitional aliases referenced from existing role normalization model

## 4.3 Shared catalog changes

- **Catalog rows added/updated/deprecated in DB: NONE**
- **Operational select options modified in existing forms: NONE**

Declarative governance artifact added (non-executing baseline only):

- Catalog family ownership and rules baseline codified for:
  1. Identity and civil data catalogs
  2. Contracting and social security catalogs
  3. Documentary type catalogs
  4. Novedad and state taxonomy catalogs
  5. SST and compliance status catalogs
  6. Operational classification catalogs

---

## 5. Migration and patch requirements

- `patches.txt` update: **NOT REQUIRED**
- New patch module: **NOT REQUIRED**
- `bench migrate`: **NOT REQUIRED**

Reason: Slice A introduces only static governance registry code and tests, with no schema mutation and no data backfill.

---

## 6. Regression checks to run immediately after Slice A

Run in this order:

1. New slice validation test
   - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_wave1_slice_a_baseline_registry`

2. Existing onboarding security regression
   - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_onboarding_security_phase5`

3. Existing role alias and permission regression
   - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_phase8_role_permissions`

4. Existing flow-level guard checks touching selección/contratación/document interactions
   - `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_flow_phase9_adjustments`

Pass criteria:

- All four test modules pass
- No route, signature, or permission behavior changes detected in logs
- No new migration requirement appears

---

## 7. Rollback steps

Because Slice A has no schema changes, rollback is code-only and immediate.

1. Revert the Slice A commit containing:
   - `hubgh/hubgh/hubgh/governance/__init__.py`
   - `hubgh/hubgh/hubgh/governance/wave1_baseline_registry.py`
   - `hubgh/hubgh/tests/test_wave1_slice_a_baseline_registry.py`
   - updates in `docs/hubgh-wave-1-implementation-log.md`
   - updates in `docs/hubgh-wave-1-change-summary.md`

2. Clear Python cache and restart workers/web as per standard deploy routine.

3. Re-run regression checks:
   - `test_onboarding_security_phase5`
   - `test_phase8_role_permissions`

4. Confirm protected surfaces remain stable:
   - onboarding create candidate
   - Persona 360 load
   - Punto 360 load
   - bandeja contratación and afiliaciones actions

---

## 8. Why this is the smallest safe first slice

1. It transforms approved Sprint 1 governance into executable assets without touching live flow logic.
2. It introduces no schema or endpoint risk.
3. It strengthens traceability and auditability before any operational RBAC/catalog enforcement.
4. It provides a clean rollback path with no data repair work.

This creates a low-risk foundation for the next Sprint 1 slices that will operationalize permissions and catalog controls incrementally.
