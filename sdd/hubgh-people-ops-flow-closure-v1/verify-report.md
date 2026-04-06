## Verification Report

**Change**: `hubgh-people-ops-flow-closure-v1`
**Date**: 2026-03-31
**Recommendation**: GO CONDICIONADO

---

### Completeness

| Metric | Value |
|---|---:|
| Tasks total | 13 |
| Tasks complete | 11 |
| Tasks incomplete | 2 |

Open tasks:
- `1.2` Add site-flag / pending-hire backfill scaffold in `hubgh/hubgh/hooks.py` and `hubgh/hubgh/hubgh/patches/`
- `5.3` Commit full local E2E smoke coverage for onboarding, Persona 360, SST tray, and CSV import

---

### Real Environment Verification

- `/candidato`: page loads, guest catalogs respond `200`, explicit runtime submit via page transport created candidate `9770865232` and user `verify.70865232@example.com`; record stayed in candidate state (`estado_proceso=En Proceso`, `persona=null`) and no premature `Ficha Empleado` row was found.
- `/candidato` risk note: the page history also contained a prior `POST /api/method/hubgh.www.candidato.create_candidate -> 417` caused by invalid legacy initial status `En documentación`; current explicit submit succeeded, but this remains a release warning until the path that still emits that value is ruled out.
- `Persona 360`: `/app/persona_360` loads and `get_all_personas_overview` returns `200`; current site shows only active employees, so retired visibility could not be proven live.
- `SST Bandeja`: `/app/sst_bandeja` loads and `get_sst_bandeja` returns `200` with `status=ok`, `reason=ready`, and canonical incapacity source `Novedad SST`.
- `Centro de Datos`: `/app/centro_de_datos` loads, templates and identity tray context return `200`; import behavior was validated mainly through automated tests.

---

### Automated Tests

Executed in the running Docker/Frappe environment.

| Module | Result |
|---|---|
| `hubgh.tests.test_flow_phase9_adjustments` | 47 passed, 1 error |
| `hubgh.tests.test_sst_bandeja` | 2 passed |
| `hubgh.hubgh.doctype.novedad_sst.test_novedad_sst` | 9 passed |
| `hubgh.hubgh.doctype.caso_disciplinario.test_caso_disciplinario` | 5 passed |
| `hubgh.tests.test_document_phase4_unification` | 4 passed |
| `hubgh.tests.test_centro_de_datos_csv_import` | 4 passed |
| `hubgh.tests.test_centro_de_datos_person_identity_contract` | 7 passed |
| `hubgh.tests.test_onboarding_security_phase5` | 15 passed, 1 error |

**Totals**: 93 passed, 2 errors

Errors observed:
- `test_documentary_folder_prefers_freshest_candidate_or_employee_metadata`: test-time failure in `carpeta_documental_empleado._is_expired()` because mocked `get_system_settings` returned a `SimpleNamespace` without `.get`.
- `test_validate_candidate_duplicates_blocks_document_and_email`: hit onboarding rate-limit cache during test setup, producing `TooManyRequestsError`.

Build/type-check:
- Attempted `python -m build` in backend container.
- Skipped by environment: module `build` is not installed.

---

### Spec Compliance Snapshot

| Requirement | Scenario | Status | Evidence |
|---|---|---|---|
| Seleccion Handoff Estable | Contract activation creates real employee identity | COMPLIANT | runtime candidate submit + `test_person_identity_batch_d_contract` static seam + contract/lifecycle code |
| Seleccion Handoff Estable | Candidate stage must not activate employee access early | COMPLIANT | runtime candidate `9770865232` stayed without `persona`; no `Ficha Empleado` found |
| SST Salud y Aforados | Alert resync preserves attended state | COMPLIANT | `hubgh.hubgh.doctype.novedad_sst.test_novedad_sst` |
| SST Salud y Aforados | Critical wellbeing trigger emits one traceable escalation | COMPLIANT | `hubgh.tests.test_flow_phase9_adjustments` |
| RRLL Lifecycle Disciplinario | Reopen reverses unjustified retirement | COMPLIANT | `hubgh.hubgh.doctype.caso_disciplinario.test_caso_disciplinario` |
| RRLL Lifecycle Disciplinario | Permission contract is consistent | COMPLIANT | `hubgh.tests.test_flow_phase9_adjustments` + permission hooks in `hubgh/hubgh/hooks.py` |
| Retirement Synchronization | Retirement closes all downstream seams | PARTIAL | code and tests exist, but no live retired/contract/payroll data on site |
| Retirement Synchronization | Retired visibility is role-scoped | PARTIAL | automated tests cover it; live site has no retired employees to exercise |
| Employee Documentary Folder Validity and Imports | Folder shows validity and inherited records | PARTIAL | automated scenario exists but one test error blocked clean runtime proof |
| Employee Documentary Folder Validity and Imports | Bulk import fails atomically | COMPLIANT | `hubgh.tests.test_centro_de_datos_csv_import` |

---

### Coherence / Design Drift

- `people_ops_lifecycle.py` centralizes hire/retire orchestration as designed.
- Permission hooks for `Caso Disciplinario` are wired in `hubgh/hubgh/hooks.py`.
- Remaining drift: the rollout/backfill scaffold from task `1.2` is still absent, and the design's richer retirement snapshot helpers (`retirement_source` / `retirement_ref`) are not persisted.

---

### Verdict

**PASS WITH WARNINGS**

The release candidate is broadly functional for the audited People Ops closure, with live confirmation on `/candidato`, `SST Bandeja`, and `Centro de Datos` page readiness. Final release should stay conditioned on clearing the two noisy test errors and accepting that retirement / retired-visibility could not be fully proven live because the current site has no retired-contract fixtures.
