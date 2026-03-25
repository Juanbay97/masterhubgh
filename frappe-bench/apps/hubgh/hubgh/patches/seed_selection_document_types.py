import frappe


SELECTION_DOC_TYPES = [
	{"name": "Carta Oferta", "is_required_for_hiring": 0, "is_optional": 1},
	{"name": "SAGRILAFT", "is_required_for_hiring": 1, "is_optional": 0},
	{"name": "Autorización de Descuento", "is_required_for_hiring": 0, "is_optional": 1},
	{"name": "Autorización de Ingreso", "is_required_for_hiring": 0, "is_optional": 1},
]
def execute():
	if not frappe.db.exists("DocType", "Document Type"):
		return

	for row in SELECTION_DOC_TYPES:
		name = row["name"]
		if frappe.db.exists("Document Type", name):
			frappe.db.set_value(
				"Document Type",
				name,
				{
					"is_active": 1,
					"applies_to": "Candidato",
					"candidate_uploads": 0,
					"allowed_roles_override": "HR Selection",
					"is_required_for_hiring": row["is_required_for_hiring"],
					"is_optional": row["is_optional"],
				},
				update_modified=False,
			)
		else:
			frappe.get_doc({
				"doctype": "Document Type",
				"document_name": name,
				"is_active": 1,
				"applies_to": "Candidato",
				"candidate_uploads": 0,
				"allowed_roles_override": "HR Selection",
				"is_required_for_hiring": row["is_required_for_hiring"],
				"is_optional": row["is_optional"],
			}).insert(ignore_permissions=True)

	frappe.db.commit()
