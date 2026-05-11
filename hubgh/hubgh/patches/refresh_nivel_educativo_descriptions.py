import frappe

from hubgh.hubgh.siesa_reference_matrix import ensure_official_nivel_educativo_catalog


def execute():
	if not frappe.db.exists("DocType", "Nivel Educativo Siesa"):
		return
	ensure_official_nivel_educativo_catalog(strict_disable_others=True)
	frappe.db.commit()
