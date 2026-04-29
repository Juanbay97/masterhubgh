import unicodedata

import frappe

from hubgh.hubgh.people_ops_flags import resolve_policy_mode
from hubgh.hubgh.role_matrix import canonicalize_roles, roles_have_any


DIMENSION_ROLE_MATRIX = {
	"operational": {
		"System Manager",
		"Gestión Humana",
		"Gerente GH",
		"HR Selection",
		"HR Labor Relations",
		"Relaciones Laborales Jefe",
		"HR Training & Wellbeing",
		"HR SST",
		"GH - Bandeja General",
		"GH - RRLL",
		"GH - SST",
		"Coordinador Zona",
		"Jefe_PDV",
		"Empleado",
	},
	"sensitive": {
		"System Manager",
		"Gestión Humana",
		"HR Labor Relations",
		"Relaciones Laborales Jefe",
		"GH - RRLL",
		"Jefe_PDV",
	},
	"clinical": {
		"System Manager",
		"HR SST",
		"HR Labor Relations",
		"Relaciones Laborales Jefe",
		"GH - RRLL",
	},
	"payroll_operational": {
		"System Manager",
		"Gestión Humana",
		"HR Labor Relations",
		"Relaciones Laborales Jefe",
		"GH - RRLL",
		"Operativo Nómina",
	},
	"payroll_sensible": {
		"System Manager",
		"Gestión Humana",
		"HR Labor Relations",
		"Relaciones Laborales Jefe",
		"GH - RRLL",
		"Sensible RRLL",
	},
	"payroll_clinical": {
		"System Manager",
		"HR SST",
		"Clínico SST",
	},
	"payroll_validacion": {
		"System Manager",
		"Validación Contabilidad",
		"Gestión Humana",
	},
}


DOCUMENT_SENSITIVITY_DIMENSIONS = {
	"clinical": {
		"historia clinica",
		"examen medico",
		"examenes medicos",
		"concepto medico",
		"incapacidad",
	},
	"sensitive": {
		"caso disciplinario",
		"descargo disciplinario",
		"llamado de atencion",
		"acta de retiro",
		# T048-T049: disciplinary flow sub-documents
		"afectado disciplinario",
		"citacion disciplinaria",
		"acta descargos",
		"comunicado sancion",
		"evidencia disciplinaria",
		"recordatorio de funciones",
	},
}


def resolve_document_dimension(document_type):
	label = _normalize_dimension_label(document_type)
	if not label:
		return "operational"

	for dimension, known_labels in DOCUMENT_SENSITIVITY_DIMENSIONS.items():
		if label in known_labels:
			return dimension

	if "medic" in label or "clin" in label or "incapac" in label:
		return "clinical"
	if "disciplin" in label or "retiro" in label:
		return "sensitive"

	return "operational"


def get_user_dimension_access(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return {dimension: True for dimension in DIMENSION_ROLE_MATRIX}

	roles = canonicalize_roles(frappe.get_roles(user) or [])
	return {
		dimension: roles_have_any(roles, allowed_roles)
		for dimension, allowed_roles in DIMENSION_ROLE_MATRIX.items()
	}


def user_can_access_dimension(dimension, user=None):
	dim = str(dimension or "").strip().lower()
	access = get_user_dimension_access(user=user)
	return bool(access.get(dim))


def evaluate_dimension_access(dimension, user=None, surface=None, context=None):
	dim = str(dimension or "").strip().lower()
	known_dimension = dim in DIMENSION_ROLE_MATRIX
	base_allowed = user_can_access_dimension(dim, user=user) if known_dimension else False
	mode = resolve_policy_mode(surface=surface)

	effective_allowed = False
	if known_dimension:
		if mode == "off":
			effective_allowed = True
		elif mode == "warn":
			effective_allowed = True
		else:
			effective_allowed = base_allowed

	violated = bool(known_dimension and not base_allowed and mode in {"warn", "enforce"})
	decision = {
		"dimension": dim,
		"mode": mode,
		"allowed_by_role": bool(base_allowed),
		"effective_allowed": bool(effective_allowed),
		"violated": violated,
		"known_dimension": known_dimension,
		"surface": str(surface or "generic").strip() or "generic",
	}

	if violated:
		_audit_policy_violation(decision, user=user, context=context)

	return decision


def _audit_policy_violation(decision, user=None, context=None):
	logger = frappe.logger("hubgh.people_ops_policy")
	logger.info(
		"policy_dimension_violation",
		extra={
			"user": user or frappe.session.user,
			"dimension": decision.get("dimension"),
			"mode": decision.get("mode"),
			"surface": decision.get("surface"),
			"context": context or {},
		},
	)


def _normalize_dimension_label(value):
	text = str(value or "").strip().lower()
	if not text:
		return ""
	return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
