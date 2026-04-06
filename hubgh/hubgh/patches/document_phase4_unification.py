import frappe

from hubgh.hubgh.document_service import ensure_candidate_required_documents, ensure_person_document


STATUS_MAP = {
	"Pendiente": "Pendiente",
	"En Revision": "Subido",
	"Aprobado": "Aprobado",
	"Rechazado": "Rechazado",
}


def execute():
	if not frappe.db.exists("DocType", "Document Type") or not frappe.db.exists("DocType", "Person Document"):
		return

	_seed_missing_document_types_from_legacy()
	_migrate_candidate_child_documents_to_person_document()


def _seed_missing_document_types_from_legacy():
	if not frappe.db.exists("DocType", "Documento Requerido"):
		return

	legacy_rows = frappe.get_all(
		"Documento Requerido",
		filters={"activo": 1},
		fields=["name", "nombre", "requerido"],
	)

	for row in legacy_rows:
		document_name = (row.nombre or "").strip()
		if not document_name:
			continue

		name = frappe.db.get_value("Document Type", {"document_name": document_name}, "name")
		if name:
			doc_type = frappe.get_doc("Document Type", name)
		else:
			doc_type = frappe.get_doc({
				"doctype": "Document Type",
				"document_name": document_name,
				"is_active": 1,
				"is_required_for_hiring": int(row.requerido or 0),
				"is_optional": 0,
				"applies_to": "Candidato",
				"requires_approval": 0,
				"allowed_areas": [
					{"area_role": "HR Selection"},
					{"area_role": "HR Labor Relations"},
				],
			})

		doc_type.is_active = 1
		doc_type.is_required_for_hiring = int(row.requerido or 0)
		doc_type.applies_to = doc_type.applies_to or "Candidato"
		if not doc_type.legacy_documento_requerido:
			doc_type.legacy_documento_requerido = row.name

		if doc_type.is_new():
			doc_type.insert(ignore_permissions=True)
		else:
			doc_type.save(ignore_permissions=True)


def _migrate_candidate_child_documents_to_person_document():
	if not frappe.db.exists("DocType", "Candidato") or not frappe.db.exists("DocType", "Candidato Documento"):
		return

	candidates = frappe.get_all("Candidato", fields=["name"])
	for row in candidates:
		candidate = row.name
		ensure_candidate_required_documents(candidate)

		legacy_rows = frappe.get_all(
			"Candidato Documento",
			filters={"parent": candidate, "parenttype": "Candidato", "parentfield": "documentos"},
			fields=["tipo_documento", "archivo", "estado_documento", "motivo_rechazo", "revisado_por", "fecha_ultima_revision"],
		)

		for old in legacy_rows:
			document_type = _resolve_document_type_from_legacy(old.tipo_documento)
			if not document_type:
				continue

			new_doc = ensure_person_document("Candidato", candidate, document_type)
			_maybe_merge_legacy_into_person_document(new_doc, old)


def _resolve_document_type_from_legacy(legacy_documento_requerido_name):
	if not legacy_documento_requerido_name:
		return None

	by_legacy = frappe.db.get_value(
		"Document Type",
		{"legacy_documento_requerido": legacy_documento_requerido_name},
		"name",
	)
	if by_legacy:
		return by_legacy

	document_name = frappe.db.get_value("Documento Requerido", legacy_documento_requerido_name, "nombre")
	if not document_name:
		return None

	return frappe.db.get_value("Document Type", {"document_name": document_name}, "name")


def _maybe_merge_legacy_into_person_document(new_doc, old):
	legacy_status = STATUS_MAP.get(old.estado_documento or "Pendiente", "Pendiente")

	if old.archivo and not new_doc.file:
		new_doc.file = old.archivo

	if new_doc.status in (None, "", "Pendiente") and legacy_status != "Pendiente":
		new_doc.status = legacy_status

	if old.motivo_rechazo and not new_doc.notes:
		new_doc.notes = old.motivo_rechazo

	if old.revisado_por and not new_doc.approved_by and legacy_status == "Aprobado":
		new_doc.approved_by = old.revisado_por

	if old.fecha_ultima_revision and not new_doc.approved_on and legacy_status == "Aprobado":
		new_doc.approved_on = old.fecha_ultima_revision

	new_doc.save(ignore_permissions=True)
