# HubGH Payroll Sprint 1 Governance Design

## 1. Decision lock and compatibility contract

### 1.1 Locked strategy for Sprint 1

Sprint 1 is **read-through-first only**.

- Official writes remain on existing labor event sources:
  - [`frappe-bench/apps/hubgh/hubgh/hubgh/doctype/novedad_laboral/novedad_laboral.json`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/novedad_laboral/novedad_laboral.json)
  - [`frappe-bench/apps/hubgh/hubgh/hubgh/doctype/gh_novedad/gh_novedad.json`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/gh_novedad/gh_novedad.json)
- Payroll in Sprint 1 is governance and read-model framing, not write cutover.
- Any permission change for payroll context must be additive and reversible against:
  - [`frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py`](frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py)
  - [`frappe-bench/apps/hubgh/hubgh/hooks.py`](frappe-bench/apps/hubgh/hubgh/hooks.py)

### 1.2 Explicit compatibility contract

For Sprint 1, engineering cannot break these invariants:

1. No runtime behavior change in existing DocType writes for GH labor events.
2. No signature change in Persona or Punto 360 server APIs:
   - [`frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py)
   - [`frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py)
3. No route or UI contract change on current 360 pages:
   - [`frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.js`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.js)
   - [`frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.js`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.js)
4. No semantic break on active-state logic used by Punto 360 for headcount and open novelty aggregation.

### 1.3 Decision lock outcomes

- Decision status: **Approved and locked for Sprint 1**
- Change policy: **Additive only**
- Exception policy: Any non-additive proposal is deferred outside Sprint 1

## 2. Payroll-related entity ownership map

| Domain | Primary owner | Co-owner | Source of truth in Sprint 1 | Notes |
|---|---|---|---|---|
| Payroll event intake | Gestión Humana | Operación | GH Novedad and Novedad Laboral | Read-through governance only |
| Labor novelty operational state | SST and RRLL by novelty type | Gestión Humana | Novedad Laboral state taxonomy | State semantics unchanged |
| Point level operational effect | Operación | Gestión Humana | Punto 360 aggregations | Active headcount semantics immutable |
| Person level timeline consumption | Gestión Humana | SST and RRLL | Persona 360 timeline | API and response contract immutable |
| Payroll catalogs | Governance board | Functional area owners | Catalog registry in this document | Versioned and additive |
| RBAC dimensional access | Platform governance | Functional owners | Existing permission architecture | Business dimensions mapped to current matrix |

## 3. Reuse vs extension registry for existing artifacts

| Artifact | Current role | Sprint 1 decision | Constraint | Required evidence |
|---|---|---|---|---|
| [`GH Novedad`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/gh_novedad/gh_novedad.json) | Operational novelty intake and routing | Reuse as write source plus payroll read input | No write-path replacement | Contract checklist approved |
| [`Novedad Laboral`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/novedad_laboral/novedad_laboral.json) | Canonical novelty lifecycle and SST-sensitive fields | Reuse as write source plus payroll read input | No state option semantic change | State mapping documented |
| [`Persona 360 page backend`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py) | Employee timeline and KPI assembly | Reuse unchanged contract | No response key removals or renames | Non-regression checklist pass |
| [`Persona 360 page UI`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.js) | Persona route and display contract | Reuse unchanged route and action flow | No route break or incompatible UI contract | UI smoke pass |
| [`Punto 360 page backend`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py) | Point KPIs and aggregated novelty status | Reuse unchanged contract | Preserve active headcount and novelty semantics | KPI parity check |
| [`Punto 360 page UI`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.js) | Punto route and dashboard rendering | Reuse unchanged route and filters | No route or payload dependency break | UI smoke pass |
| [`Gestión Humana workspace`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/gestión_humana/gestión_humana.json) | GH navigation entrypoints | Reuse with additive payroll shortcuts only if needed | Existing shortcuts preserved | Workspace diff reviewed |
| [`Relaciones Laborales workspace`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/relaciones_laborales/relaciones_laborales.json) | RRLL operational navigation | Reuse with additive links only | Existing links preserved | Workspace diff reviewed |
| [`SST workspace`](frappe-bench/apps/hubgh/hubgh/hubgh/workspace/sst/sst.json) | SST operational navigation | Reuse with additive links only | Existing links preserved | Workspace diff reviewed |

## 4. Catalog governance model for Sprint 1

### 4.1 Governance roles

| Catalog family | Owner | Approver | Consumers | Lifecycle |
|---|---|---|---|---|
| Payroll novelty type taxonomy | Gestión Humana | Governance board | RRLL, SST, Payroll ops | Draft, Approved, Deprecated |
| Payroll concept catalog | Payroll ops lead | Governance board | Contabilidad, GH | Draft, Approved, Deprecated |
| Payroll period and cut parameters | Payroll ops lead | Contabilidad | Payroll and reporting | Draft, Approved, Deprecated |
| Data sensitivity labels | Security and governance | Governance board | Platform and app teams | Draft, Approved, Deprecated |

### 4.2 Versioning policy

1. Version format: `major.minor.patch`.
2. Sprint 1 allows only additive change classes:
   - Add new code/value
   - Add descriptive metadata
   - Mark deprecated without deletion
3. Sprint 1 disallows:
   - Renaming existing code keys
   - Reusing a retired key with a different meaning
   - Deleting actively referenced key values

### 4.3 Change control policy

- Every catalog change requires:
  1. Owner proposal
  2. Impact check against 360 and permissions
  3. Governance approval
  4. Rollback entry in execution checklist

## 5. RBAC dimension matrix draft aligned to current architecture

This business matrix is mapped to existing technical enforcement in [`frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py`](frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py).

### 5.1 Business dimensions for Sprint 1

- Operativo Nómina
- RRLL Sensible
- SST Clínico
- SST Operativo
- Contabilidad Cierre
- Auditoría
- Administración

### 5.2 Alignment to current technical dimensions

| Business dimension | Current technical anchor | Mapping intent |
|---|---|---|
| Operativo Nómina | operational | Primary mapping |
| RRLL Sensible | sensitive | Primary mapping |
| SST Clínico | clinical | Primary mapping |
| SST Operativo | operational | Scoped by role and module |
| Contabilidad Cierre | operational | Scoped additive policy in Sprint 1 docs |
| Auditoría | operational plus sensitive read controls | Additive read-only governance intent |
| Administración | operational plus full admin role set | Uses existing admin permission behavior |

### 5.3 Draft role-to-dimension matrix

Legend: `M` manage, `R` read, `N` none.

| Role | Operativo Nómina | RRLL Sensible | SST Clínico | SST Operativo | Contabilidad Cierre | Auditoría | Administración |
|---|---|---|---|---|---|---|---|
| System Manager | M | M | M | M | M | M | M |
| Gestión Humana | M | R | N | R | R | R | N |
| HR Labor Relations | R | M | N | N | R | R | N |
| Relaciones Laborales | R | M | N | N | R | R | N |
| HR SST | R | N | M | M | N | R | N |
| SST | R | N | M | M | N | R | N |
| Jefe_PDV | R | R | N | R | N | N | N |
| Empleado | R own context | N | N | N | N | N | N |
| Contabilidad | R | N | N | N | M | R | N |

Note: `Contabilidad` is governance-defined for Sprint 1 and must be implemented additively only where compatible with current permission hooks in [`frappe-bench/apps/hubgh/hubgh/hooks.py`](frappe-bench/apps/hubgh/hubgh/hooks.py).

## 6. Explicit non-regression API and page contracts that cannot break

## 6.1 Server API contracts

The following whitelisted APIs are immutable for Sprint 1:

1. [`get_persona_stats`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py:155)
2. [`get_all_personas_overview`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.py:420)
3. [`get_punto_stats`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:117)
4. [`get_all_puntos_overview`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.py:403)

Sprint 1 cannot:

- Rename methods
- Remove output keys currently consumed by page JS
- Change semantics of active novelty and active headcount outputs

## 6.2 Page contracts

The following routes and page load hooks are immutable for Sprint 1:

1. [`frappe.pages['persona_360'].on_page_load`](frappe-bench/apps/hubgh/hubgh/hubgh/page/persona_360/persona_360.js:2)
2. [`frappe.pages['punto_360'].on_page_load`](frappe-bench/apps/hubgh/hubgh/hubgh/page/punto_360/punto_360.js:3)

Sprint 1 cannot:

- Break route entry from existing workspaces
- Remove existing core user actions
- Require new mandatory parameters for baseline views

## 6.3 Permission contracts

Permission hooks for existing payroll-relevant entities remain intact in Sprint 1:

- Query and object permission maps in [`frappe-bench/apps/hubgh/hubgh/hooks.py`](frappe-bench/apps/hubgh/hubgh/hooks.py)
- Dimension logic in [`frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py`](frappe-bench/apps/hubgh/hubgh/hubgh/permissions.py)

## 7. Sprint 1 acceptance criteria

Sprint 1 governance is accepted only when all are true:

1. Read-through-first contract documented and approved without write cutover scope.
2. Ownership map approved by GH, RRLL, SST, and payroll stakeholders.
3. Reuse versus extension registry approved for GH Novedad, Novedad Laboral, Persona 360, Punto 360, and workspaces.
4. Catalog governance model published with owner, lifecycle, and versioning rules.
5. RBAC draft published with explicit business dimensions and technical mapping.
6. Non-regression API and page contract list published with immutable constraints.
7. Execution checklist exists with entry criteria, exit criteria, and rollback notes.

## 8. Out of scope guardrail for this document

This design intentionally excludes Sprint 2 plus implementation details except Sprint 1 dependencies for governance decisions.

