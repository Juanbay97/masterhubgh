# HubGH Payroll Sprint 1 Execution Checklist

## 1. Scope lock

- Sprint scope is limited to governance package for read-through-first compatibility.
- No Python, JS, or JSON runtime code changes are allowed in this checklist execution.
- No Sprint 2 plus implementation planning is included, except dependencies required to finalize Sprint 1 decisions.

## 2. Entry criteria

All items must be true before execution starts:

- [ ] Approved parent plan exists at [`plans/hubgh-payroll-orchestrated-sprint-plan-v2.md`](plans/hubgh-payroll-orchestrated-sprint-plan-v2.md)
- [ ] Baseline labor event artifacts are confirmed:
  - [ ] [`GH Novedad`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/gh_novedad/gh_novedad.json)
  - [ ] [`Novedad Laboral`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/novedad_laboral/novedad_laboral.json)
- [ ] Baseline 360 contracts are confirmed:
  - [ ] [`Persona 360 backend`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py)
  - [ ] [`Persona 360 UI`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.js)
  - [ ] [`Punto 360 backend`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py)
  - [ ] [`Punto 360 UI`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.js)
- [ ] Baseline permission architecture is confirmed:
  - [ ] [`permissions.py`](frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py)
  - [ ] [`hooks.py`](frappe-bench/apps/hubgh/hubgh/hooks.py)

## 3. Work checklist

### 3.1 Governance design artifact

- [ ] Publish Sprint 1 decision lock with read-through-first compatibility contract
- [ ] Publish payroll-related entity ownership map
- [ ] Publish reuse versus extension registry for GH Novedad, Novedad Laboral, Persona 360, Punto 360, and target workspaces
- [ ] Publish catalog governance model with owner, lifecycle, and versioning policy
- [ ] Publish RBAC draft using explicit business dimensions:
  - [ ] Operativo Nómina
  - [ ] RRLL Sensible
  - [ ] SST Clínico
  - [ ] SST Operativo
  - [ ] Contabilidad Cierre
  - [ ] Auditoría
  - [ ] Administración
- [ ] Publish explicit non-regression API and page contracts

Reference deliverable:

- [`docs/hubgh-payroll-sprint-1-governance-design.md`](docs/hubgh-payroll-sprint-1-governance-design.md)

### 3.2 Sprint execution controls artifact

- [ ] Publish entry criteria, execution checklist, and exit criteria
- [ ] Publish rollback notes for each governance decision class
- [ ] Include constraints that preserve additive and backward-compatible behavior

Reference deliverable:

- [`docs/hubgh-payroll-sprint-1-execution-checklist.md`](docs/hubgh-payroll-sprint-1-execution-checklist.md)

## 4. Non-regression acceptance checks

All items must pass:

- [ ] No runtime code files changed outside governance docs
- [ ] No API signature modifications for:
  - [ ] [`get_persona_stats`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py:155)
  - [ ] [`get_all_personas_overview`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py:420)
  - [ ] [`get_punto_stats`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:117)
  - [ ] [`get_all_puntos_overview`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:403)
- [ ] No route contract modifications for:
  - [ ] [`frappe.pages['persona_360'].on_page_load`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.js:2)
  - [ ] [`frappe.pages['punto_360'].on_page_load`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.js:3)
- [ ] No semantic change to novelty operational states in:
  - [ ] [`Novedad Laboral estado`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/novedad_laboral/novedad_laboral.json)
  - [ ] [`GH Novedad estado`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/gh_novedad/gh_novedad.json)
- [ ] Workspace navigation remains additive only in:
  - [ ] [`Gestión Humana workspace`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/gestión_humana/gestión_humana.json)
  - [ ] [`Relaciones Laborales workspace`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/relaciones_laborales/relaciones_laborales.json)
  - [ ] [`SST workspace`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/sst/sst.json)

## 5. Exit criteria

Sprint 1 governance package is complete when all are true:

- [ ] Governance design document exists and is implementation-ready
- [ ] Execution checklist exists with explicit entry, exit, and rollback controls
- [ ] Decision lock states read-through-first and additive-only policy
- [ ] Non-regression contract list is explicit and testable
- [ ] No out-of-scope Sprint 2 plus implementation detail is included

## 6. Rollback notes

If any acceptance check fails, use this rollback policy:

1. Revert affected governance document section to previous approved version.
2. Preserve all baseline contracts in runtime artifacts:
   - [`frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py)
   - [`frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py)
   - [`frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py`](frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py)
3. Re-run checklist section 4 before re-approval.
4. Document rollback reason and correction in the sprint governance decision log.

## 7. Dependencies allowed for Sprint 1 decisions

Only decision dependencies are allowed:

- Baseline contract inventory
- Functional owner assignment by domain
- RBAC business dimension naming and mapping to current permission architecture

No implementation dependency for write cutover is included in Sprint 1.

