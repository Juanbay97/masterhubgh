import frappe

from hubgh.hubgh.siesa_reference_matrix import (
	ensure_official_centro_trabajo_catalog,
	ensure_official_unidad_negocio_catalog,
)


def execute():
	if frappe.db.exists("DocType", "Unidad Negocio Siesa"):
		ensure_official_unidad_negocio_catalog(strict_disable_others=True)
	if frappe.db.exists("DocType", "Centro Trabajo Siesa"):
		ensure_official_centro_trabajo_catalog(strict_disable_others=True)
	frappe.db.commit()

