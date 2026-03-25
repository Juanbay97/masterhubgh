import frappe

from hubgh.hubgh.document_service import ensure_candidate_required_documents


ROLE_MAP = [
	"HR Selection",
	"HR Labor Relations",
	"HR Training & Wellbeing",
	"HR SST",
]


def execute():
	_ensure_roles()
	_seed_document_types()
	_migrate_candidate_documents_to_person_document()


def _ensure_roles():
	for role in ROLE_MAP:
		if frappe.db.exists("Role", role):
			continue
		frappe.get_doc({
			"doctype": "Role",
			"role_name": role,
			"desk_access": 1,
			"read_only": 0,
		}).insert(ignore_permissions=True)


def _seed_document_types():
	legacy = frappe.get_all(
		"Documento Requerido",
		fields=["name", "nombre", "requerido", "activo"],
	)

	for row in legacy:
		if frappe.db.exists("Document Type", row.nombre):
			doc_type = frappe.get_doc("Document Type", row.nombre)
		else:
			doc_type = frappe.get_doc({
				"doctype": "Document Type",
				"document_name": row.nombre,
			})

		doc_type.is_active = int(row.activo or 0)
		doc_type.is_required_for_hiring = int(row.requerido or 0)
		doc_type.is_optional = 0
		doc_type.applies_to = "Candidato"
		doc_type.requires_approval = 0
		doc_type.legacy_documento_requerido = row.name
		doc_type.allowed_areas = []
		doc_type.append("allowed_areas", {"area_role": "HR Selection"})
		doc_type.append("allowed_areas", {"area_role": "HR Labor Relations"})

		if doc_type.is_new():
			doc_type.insert(ignore_permissions=True)
		else:
			doc_type.save(ignore_permissions=True)

	for default_name in [
		"Concepto médico",
		"Documento autorización de ingreso",
		"SAGRILAFT",
		"Autorización de descuento",
		"Carta oferta",
		"Contrato",
	]:
		if frappe.db.exists("Document Type", default_name):
			continue

		is_optional = 1 if default_name == "Carta oferta" else 0
		is_required = 0 if default_name == "Carta oferta" else 1
		applies_to = "Candidato" if default_name != "Contrato" else "Ambos"

		doc = frappe.get_doc({
			"doctype": "Document Type",
			"document_name": default_name,
			"is_active": 1,
			"is_required_for_hiring": is_required,
			"is_optional": is_optional,
			"applies_to": applies_to,
			"requires_approval": 0,
			"allowed_areas": [
				{"area_role": "HR Selection"},
				{"area_role": "HR Labor Relations"},
			],
		})
		doc.insert(ignore_permissions=True)


def _migrate_candidate_documents_to_person_document():
	candidates = frappe.get_all("Candidato", fields=["name"])
	for row in candidates:
		candidate = row.name
		ensure_candidate_required_documents(candidate)

		cand = frappe.get_doc("Candidato", candidate)
		for old in cand.documentos or []:
			doc_type = _resolve_document_type(old.tipo_documento)
			if not doc_type:
				continue

			name = frappe.db.get_value(
				"Person Document",
				{"person_type": "Candidato", "person": candidate, "document_type": doc_type},
			)
			if not name:
				continue

			new_doc = frappe.get_doc("Person Document", name)
			status = _map_status(old.estado_documento)
			new_doc.status = status
			new_doc.file = old.archivo
			new_doc.notes = old.motivo_rechazo
			new_doc.save(ignore_permissions=True)


def _resolve_document_type(legacy_name):
	by_legacy = frappe.db.get_value("Document Type", {"legacy_documento_requerido": legacy_name}, "name")
	if by_legacy:
		return by_legacy

	doc_req_name = frappe.db.get_value("Documento Requerido", legacy_name, "nombre")
	if doc_req_name and frappe.db.exists("Document Type", doc_req_name):
		return doc_req_name
	return None


def _map_status(old_status):
	mapping = {
		"Pendiente": "Pendiente",
		"En Revision": "Subido",
		"Aprobado": "Aprobado",
		"Rechazado": "Rechazado",
	}
	return mapping.get(old_status or "Pendiente", "Pendiente")

