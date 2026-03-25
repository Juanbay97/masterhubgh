"""Wave 1 Sprint 1 governance baseline registry.

Slice W1-S1A is intentionally declarative and non-executing at runtime.
"""

SLICE_ID = "W1-S1A"
SLICE_NAME = "Governance baseline codification with zero runtime behavior change"

RUNTIME_IMPACT_CONTRACT = {
	"schema_changes": False,
	"doctype_field_changes": False,
	"permission_runtime_changes": False,
	"endpoint_signature_changes": False,
	"workspace_route_changes": False,
	"client_js_flow_changes": False,
}

PROTECTED_NON_REGRESSION_SURFACES = (
	"Onboarding candidate creation and candidate document flow remain unchanged",
	"Persona 360 route and response contract remain unchanged",
	"Punto 360 route, filters, and active headcount semantics remain unchanged",
	"Bandejas selection, afiliaciones, and contratación action signatures remain unchanged",
)

ENTITY_OWNERSHIP_BASELINE = {
	"candidate_intake": {
		"anchor_artifacts": ["Candidato", "Candidato Documento", "Candidato Disponibilidad"],
		"owner_area": "HR Selection",
		"lifecycle_stage": "Prospect to approved or rejected",
	},
	"hiring_packet": {
		"anchor_artifacts": ["Datos Contratacion", "Contrato", "Afiliacion Seguridad Social"],
		"owner_area": "HR Labor Relations",
		"lifecycle_stage": "Approved candidate to linked employee",
	},
	"employee_master": {
		"anchor_artifacts": ["Ficha Empleado"],
		"owner_area": "Gestión Humana",
		"lifecycle_stage": "Active workforce lifecycle",
	},
	"point_master": {
		"anchor_artifacts": ["Punto de Venta"],
		"owner_area": "Operación with GH governance",
		"lifecycle_stage": "Operational assignment lifecycle",
	},
	"document_domain": {
		"anchor_artifacts": [
			"Document Type",
			"Document Type Area",
			"Person Document",
			"Persona Documento",
			"Operacion Tipo Documento",
		],
		"owner_area": "Shared GH governance",
		"lifecycle_stage": "Versioned by person and area",
	},
	"labor_events": {
		"anchor_artifacts": ["Novedad SST", "GH Novedad"],
		"owner_area": "GH and Operación",
		"lifecycle_stage": "Time-bound state events",
	},
	"sst_domain": {
		"anchor_artifacts": ["Caso SST", "SST Alerta", "SST Seguimiento"],
		"owner_area": "HR SST",
		"lifecycle_stage": "Occupational health lifecycle",
	},
	"rrll_domain": {
		"anchor_artifacts": ["Caso Disciplinario"],
		"owner_area": "HR Labor Relations",
		"lifecycle_stage": "Case intake to formal decision",
	},
	"wellbeing_signals": {
		"anchor_artifacts": [
			"Feedback Punto",
			"Bienestar Seguimiento Ingreso",
			"Bienestar Evaluacion Periodo Prueba",
			"Bienestar Alerta",
			"Bienestar Compromiso",
		],
		"owner_area": "HR Training and Wellbeing",
		"lifecycle_stage": "Follow-up cycles",
	},
}

ROLE_DIMENSIONS = ("D1", "D2", "D3", "D4", "D5", "D6", "D7")

ROLE_DIMENSION_MATRIX_BASELINE = {
	"Gestión Humana": {
		"aliases": ["Gestion Humana", "GH_Central", "GH Central"],
		"dimensions": {"D1": "M", "D2": "M", "D3": "M", "D4": "R", "D5": "R", "D6": "R", "D7": "M"},
	},
	"HR Selection": {
		"aliases": ["Selección", "Seleccion"],
		"dimensions": {"D1": "M", "D2": "R", "D3": "M", "D4": "N", "D5": "N", "D6": "R", "D7": "N"},
	},
	"HR Labor Relations": {
		"aliases": ["Relaciones Laborales", "Relaciones_Laborales", "Relaciones Laborales GH"],
		"dimensions": {"D1": "R", "D2": "M", "D3": "M", "D4": "M", "D5": "R", "D6": "R", "D7": "N"},
	},
	"HR SST": {
		"aliases": ["SST"],
		"dimensions": {"D1": "R", "D2": "R", "D3": "R", "D4": "N", "D5": "M", "D6": "R", "D7": "N"},
	},
	"HR Training & Wellbeing": {
		"aliases": ["Formación y Bienestar", "Formacion y Bienestar"],
		"dimensions": {"D1": "R", "D2": "N", "D3": "R", "D4": "N", "D5": "R", "D6": "M", "D7": "M"},
	},
	"GH - Bandeja General": {
		"aliases": [],
		"dimensions": {"D1": "R", "D2": "R", "D3": "R", "D4": "N", "D5": "N", "D6": "R", "D7": "N"},
	},
	"GH - RRLL": {
		"aliases": [],
		"dimensions": {"D1": "R", "D2": "R", "D3": "R", "D4": "M", "D5": "N", "D6": "R", "D7": "N"},
	},
	"GH - SST": {
		"aliases": [],
		"dimensions": {"D1": "R", "D2": "N", "D3": "R", "D4": "N", "D5": "R", "D6": "R", "D7": "N"},
	},
	"Jefe_PDV": {
		"aliases": ["Jefe de tienda", "Jefe de Punto"],
		"dimensions": {"D1": "R", "D2": "N", "D3": "R", "D4": "N", "D5": "R", "D6": "M", "D7": "N"},
	},
	"Empleado": {
		"aliases": [],
		"dimensions": {"D1": "R", "D2": "N", "D3": "R", "D4": "N", "D5": "R", "D6": "R", "D7": "R"},
	},
	"Candidato": {
		"aliases": [],
		"dimensions": {"D1": "R", "D2": "N", "D3": "M", "D4": "N", "D5": "N", "D6": "N", "D7": "N"},
	},
	"System Manager": {
		"aliases": [],
		"dimensions": {"D1": "M", "D2": "M", "D3": "M", "D4": "M", "D5": "M", "D6": "M", "D7": "M"},
	},
}

SHARED_CATALOG_BASELINE = {
	"identity_and_civil_data": {
		"owner": "Gestión Humana",
		"backup_owner": "HR Selection",
		"change_policy": "additive_default",
		"stable_keys_required": True,
	},
	"contracting_and_social_security": {
		"owner": "HR Labor Relations",
		"backup_owner": "Gestión Humana",
		"change_policy": "additive_default",
		"stable_keys_required": True,
	},
	"documentary_type_catalogs": {
		"owner": "Shared GH governance",
		"backup_owner": "HR Selection",
		"change_policy": "additive_default",
		"stable_keys_required": True,
	},
	"novedad_and_state_taxonomy": {
		"owner": "GH and Operación",
		"backup_owner": "HR Labor Relations",
		"change_policy": "additive_default",
		"stable_keys_required": True,
	},
	"sst_and_compliance_status": {
		"owner": "HR SST",
		"backup_owner": "Gestión Humana",
		"change_policy": "additive_default",
		"stable_keys_required": True,
	},
	"operational_classification": {
		"owner": "Operación with GH governance",
		"backup_owner": "Gestión Humana",
		"change_policy": "additive_default",
		"stable_keys_required": True,
	},
}

DOCTYPE_STRATEGY_BASELINE = {
	"candidate_intake_and_documents": {
		"artifacts": ["Candidato", "Candidato Documento", "Candidato Disponibilidad"],
		"decision": "reuse_and_extend_additive_only",
		"guardrail": "Keep create_candidate response and onboarding flow stable",
	},
	"hiring_handoff_packet": {
		"artifacts": ["Datos Contratacion", "Contrato", "Afiliacion Seguridad Social"],
		"decision": "reuse_and_extend",
		"guardrail": "Preserve current bandeja contracting and affiliation actions",
	},
	"employee_canonical_record": {
		"artifacts": ["Ficha Empleado"],
		"decision": "reuse",
		"guardrail": "Do not alter key semantics consumed by Persona 360 and Punto 360",
	},
	"point_operational_context": {
		"artifacts": ["Punto de Venta"],
		"decision": "reuse",
		"guardrail": "Keep active headcount criteria unchanged",
	},
	"documentary_governance": {
		"artifacts": ["Document Type", "Document Type Area", "Person Document", "Persona Documento", "Operacion Tipo Documento"],
		"decision": "reuse_with_unification_policy",
		"guardrail": "Maintain existing retrieval endpoints and page consumers",
	},
	"labor_state_events": {
		"artifacts": ["Novedad SST", "GH Novedad"],
		"decision": "reuse_with_taxonomy_harmonization",
		"guardrail": "Keep temporary versus definitive state behavior unchanged",
	},
	"rrll_case_flow": {
		"artifacts": ["Caso Disciplinario"],
		"decision": "reuse_and_extend_workflow_metadata",
		"guardrail": "No closure without explicit decision metadata",
	},
	"sst_longitudinal_flow": {
		"artifacts": ["Caso SST", "SST Alerta", "SST Seguimiento"],
		"decision": "reuse",
		"guardrail": "Preserve confidentiality partitioning",
	},
	"wellbeing_follow_up": {
		"artifacts": [
			"Feedback Punto",
			"Bienestar Seguimiento Ingreso",
			"Bienestar Evaluacion Periodo Prueba",
			"Bienestar Alerta",
			"Bienestar Compromiso",
		],
		"decision": "reuse_and_extend_additive",
		"guardrail": "Operate wellbeing follow-up via WS1-WS4 artifacts in Persona and Punto views",
	},
}


DOCTYPE_DECISION_OPTIONS = {"reuse", "extend", "create", "reuse_with_bridge"}

DOCTYPE_DECISION_REGISTRY = {
	"Candidato": {
		"domain": "candidate_intake",
		"decision": "extend",
		"justification": "Public onboarding and candidate lifecycle are already canonical and must stay stable.",
		"risk_level": "low",
		"rollback_strategy": "Revert additive field/controller changes and re-run onboarding security and candidate flow tests.",
	},
	"Datos Contratacion": {
		"domain": "hiring_packet",
		"decision": "extend",
		"justification": "Current handoff packet is active and should evolve without replacing current routes.",
		"risk_level": "medium",
		"rollback_strategy": "Revert handoff logic additions and validate contracting snapshot end-to-end.",
	},
	"Contrato": {
		"domain": "hiring_packet",
		"decision": "extend",
		"justification": "Contract generation is in production and must preserve numbering and submit flow contracts.",
		"risk_level": "medium",
		"rollback_strategy": "Revert contract mutation and export adjustments and rerun contratación + export tests.",
	},
	"Afiliacion Seguridad Social": {
		"domain": "hiring_packet",
		"decision": "extend",
		"justification": "Affiliation status is already coupled to hiring progress and should remain additive.",
		"risk_level": "medium",
		"rollback_strategy": "Revert affiliation logic deltas and verify affiliation snapshot and completion flow.",
	},
	"Ficha Empleado": {
		"domain": "employee_master",
		"decision": "reuse",
		"justification": "Canonical employee master consumed by Persona/Punto 360 should remain structurally stable.",
		"risk_level": "high",
		"rollback_strategy": "Rollback to previous employee model behavior and validate read permissions + 360 pages.",
	},
	"Punto de Venta": {
		"domain": "point_master",
		"decision": "reuse",
		"justification": "Operational KPIs and allocation logic depend on stable point keys.",
		"risk_level": "high",
		"rollback_strategy": "Revert any point coupling changes and validate Punto 360 aggregation outcomes.",
	},
	"Person Document": {
		"domain": "document_domain",
		"decision": "reuse_with_bridge",
		"justification": "Unified documentary governance requires bridge semantics while preserving current retrieval flows.",
		"risk_level": "medium",
		"rollback_strategy": "Disable bridge behavior and keep legacy retrieval path active.",
	},
	"Novedad SST": {
		"domain": "labor_events",
		"decision": "reuse",
		"justification": "Legacy novelty records remain a source for active operational states.",
		"risk_level": "high",
		"rollback_strategy": "Rollback event harmonization and verify active state semantics across 360 pages.",
	},
	"GH Novedad": {
		"domain": "labor_events",
		"decision": "extend",
		"justification": "Needed for cross-module operational visibility while retaining backward compatibility.",
		"risk_level": "medium",
		"rollback_strategy": "Revert GH novelty extensions and ensure legacy novelty queries still operate.",
	},
	"Caso SST": {
		"domain": "sst_domain",
		"decision": "reuse",
		"justification": "SST case continuity requires stable confidentiality boundaries.",
		"risk_level": "high",
		"rollback_strategy": "Rollback SST case evolution and re-run confidentiality and alert checks.",
	},
	"Caso Disciplinario": {
		"domain": "rrll_domain",
		"decision": "extend",
		"justification": "RRLL decisions need additive metadata without replacing current workflow.",
		"risk_level": "medium",
		"rollback_strategy": "Revert disciplinary metadata changes and ensure closure rules are intact.",
	},
	"Bienestar Seguimiento Ingreso": {
		"domain": "wellbeing_signals",
		"decision": "extend",
		"justification": "Operational follow-up is governed by the new ingreso follow-up flow while preserving additive behavior.",
		"risk_level": "low",
		"rollback_strategy": "Revert additive follow-up changes and validate Persona/Punto wellbeing aggregates.",
	},
}


def validate_doctype_decision_registry():
	"""Return validation diagnostics for S1.4 DocType decision registry completeness."""
	required_fields = {"domain", "decision", "justification", "risk_level", "rollback_strategy"}
	allowed_risks = {"low", "medium", "high"}

	issues = []
	for doctype, payload in (DOCTYPE_DECISION_REGISTRY or {}).items():
		missing = sorted(required_fields - set(payload.keys()))
		if missing:
			issues.append({"doctype": doctype, "issue": f"missing_fields:{','.join(missing)}"})
			continue

		if payload.get("decision") not in DOCTYPE_DECISION_OPTIONS:
			issues.append({"doctype": doctype, "issue": "invalid_decision"})

		if str(payload.get("risk_level") or "").strip().lower() not in allowed_risks:
			issues.append({"doctype": doctype, "issue": "invalid_risk_level"})

		if not str(payload.get("justification") or "").strip():
			issues.append({"doctype": doctype, "issue": "empty_justification"})

		if not str(payload.get("rollback_strategy") or "").strip():
			issues.append({"doctype": doctype, "issue": "empty_rollback_strategy"})

	return {"valid": len(issues) == 0, "issues": issues, "total": len(DOCTYPE_DECISION_REGISTRY)}
