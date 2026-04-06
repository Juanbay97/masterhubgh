import frappe


def execute():
	if not frappe.db.exists("DocType", "Document Type"):
		return

	if not frappe.db.has_column("Document Type", "candidate_uploads"):
		return

	doc_names = [
		"Hoja de vida actualizada.",
		"Fotocopia del documento de identidad al 150%.",
		"Certificación bancaria (No mayor a 30 días).",
		"Carnet manipulación de alimentos.",
		"Certificado de EPS (Salud).",
		"Certificado de fondo de pensiones.",
		"Certificado de fondo de cesantías.",
		"Certificados de estudios y/o actas de grado Bachiller y posteriores.",
		"2 cartas de referencias personales.",
	]

	frappe.db.sql("update `tabDocument Type` set candidate_uploads=0")

	for name in doc_names:
		if frappe.db.exists("Document Type", name):
			frappe.db.set_value("Document Type", name, "candidate_uploads", 1, update_modified=False)

	frappe.db.commit()
