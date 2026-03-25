import frappe

from hubgh.hubgh.siesa_reference_matrix import ensure_official_ccf_catalog


def execute():
	if not frappe.db.exists("DocType", "Entidad CCF Siesa"):
		return
	ensure_official_ccf_catalog(strict_disable_others=True)
	frappe.db.commit()
