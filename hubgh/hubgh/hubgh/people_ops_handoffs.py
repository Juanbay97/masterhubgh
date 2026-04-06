import frappe

from hubgh.hubgh.role_matrix import canonicalize_roles, roles_have_any


HANDOFF_STATUSES = ("pending", "ready", "blocked", "completed")


HANDOFF_CONTRACTS = {
	"selection_to_rrll": {
		"from_area": "seleccion",
		"to_area": "rrll",
		"required_fields": ["contrato", "punto", "fecha_ingreso"],
		"required_documents": [],
		"required_permissions": ["HR Selection", "HR Labor Relations", "Gestión Humana", "System Manager"],
	},
	"wellbeing_to_rrll": {
		"from_area": "bienestar",
		"to_area": "rrll",
		"required_fields": ["persona", "source", "causal"],
		"required_documents": [],
		"required_permissions": ["HR Training & Wellbeing", "HR Labor Relations", "Gestión Humana", "System Manager"],
	},
	"sst_to_persona360": {
		"from_area": "sst",
		"to_area": "persona_360",
		"required_fields": ["persona", "source", "state"],
		"required_documents": [],
		"required_permissions": ["HR SST", "Gestión Humana", "System Manager"],
	},
}


def validate_selection_to_rrll_gate(payload):
	data = payload if isinstance(payload, dict) else {}
	target_data = data.get("target_data") or {}
	required_documents = data.get("required_documents") or {}
	medical_concept = str(data.get("medical_concept") or "").strip().lower()

	errors = []
	if medical_concept != "favorable":
		errors.append("medical_concept_not_favorable")
	if not bool(required_documents.get("SAGRILAFT")):
		errors.append("missing_document_sagrilaft")
	if not _has_value(target_data.get("pdv_destino")):
		errors.append("missing_pdv_destino")
	if not _has_value(target_data.get("fecha_tentativa_ingreso")):
		errors.append("missing_fecha_tentativa_ingreso")

	return {
		"status": "ready" if not errors else "blocked",
		"errors": errors,
		"required_documents": sorted(required_documents.keys()),
		"gate_version": "v1",
	}


def validate_handoff_contract(handoff_type, payload, user=None, actor_roles=None, lifecycle_state=None):
	handoff_key = str(handoff_type or "").strip().lower()
	contract = HANDOFF_CONTRACTS.get(handoff_key)
	if not contract:
		return {
			"handoff_type": handoff_key,
			"status": "blocked",
			"status_reason": "handoff_type_not_supported",
			"from_area": None,
			"to_area": None,
			"required_fields": [],
			"required_documents": [],
			"required_permissions": [],
			"errors": ["handoff_type_not_supported"],
			"missing_fields": [],
			"missing_documents": [],
			"missing_permissions": [],
			"supported_statuses": list(HANDOFF_STATUSES),
			"contract_version": "v1",
		}

	data = payload if isinstance(payload, dict) else {}
	roles = _resolve_roles(user=user, actor_roles=actor_roles)

	missing_fields = [field for field in contract["required_fields"] if not _has_value(data.get(field))]
	missing_documents = _missing_documents(data.get("documents"), contract["required_documents"])
	permissions_ok = _has_permissions(roles, contract["required_permissions"])
	missing_permissions = [] if permissions_ok else list(contract["required_permissions"])

	errors = []
	if missing_fields:
		errors.append("missing_fields")
	if missing_documents:
		errors.append("missing_documents")
	if missing_permissions:
		errors.append("missing_permissions")

	status, status_reason = _resolve_handoff_status(data, lifecycle_state=lifecycle_state, has_errors=bool(errors))
	return {
		"handoff_type": handoff_key,
		"from_area": contract["from_area"],
		"to_area": contract["to_area"],
		"status": status,
		"status_reason": status_reason,
		"required_fields": list(contract["required_fields"]),
		"required_documents": list(contract["required_documents"]),
		"required_permissions": list(contract["required_permissions"]),
		"missing_fields": missing_fields,
		"missing_documents": missing_documents,
		"missing_permissions": missing_permissions,
		"errors": errors,
		"supported_statuses": list(HANDOFF_STATUSES),
		"contract_version": "v1",
	}


def _resolve_handoff_status(payload, lifecycle_state=None, has_errors=False):
	if has_errors:
		return "blocked", "validation_failed"

	requested_status = _normalize_handoff_status(lifecycle_state)
	if requested_status is None:
		requested_status = _normalize_handoff_status((payload or {}).get("status"))

	if requested_status == "pending":
		return "pending", "handoff_pending"
	if requested_status == "completed":
		return "completed", "handoff_completed"

	return "ready", "validation_passed"


def _normalize_handoff_status(value):
	status = str(value or "").strip().lower()
	if status in {"pending", "completed"}:
		return status
	if status == "ready":
		return "ready"
	return None


def _resolve_roles(user=None, actor_roles=None):
	if actor_roles is not None:
		return canonicalize_roles(actor_roles)

	resolved_user = user or frappe.session.user
	if resolved_user == "Administrator":
		return {"System Manager"}

	return canonicalize_roles(frappe.get_roles(resolved_user) or [])


def _missing_documents(provided_documents, required_documents):
	provided = {
		str(item).strip().lower()
		for item in (provided_documents or [])
		if str(item).strip()
	}
	missing = []
	for doc in required_documents:
		doc_key = str(doc).strip().lower()
		if doc_key and doc_key not in provided:
			missing.append(doc)
	return missing


def _has_permissions(roles, required_permissions):
	return bool(roles_have_any(set(roles or []), set(required_permissions or [])))


def _has_value(value):
	if value is None:
		return False
	if isinstance(value, str):
		return bool(value.strip())
	return True
