import frappe


MULTI_UPLOAD_DOCUMENT_TYPES = [
	"2 cartas de referencias personales.",
	"Certificados de estudios y/o actas de grado Bachiller y posteriores.",
]


def execute():
	if not frappe.db.exists("DocType", "Document Type"):
		return

	if not frappe.db.has_column("Document Type", "allows_multiple"):
		return

	for name in MULTI_UPLOAD_DOCUMENT_TYPES:
		if frappe.db.exists("Document Type", name):
			frappe.db.set_value("Document Type", name, "allows_multiple", 1, update_modified=False)

	frappe.db.commit()
