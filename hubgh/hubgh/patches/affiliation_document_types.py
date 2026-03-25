import frappe

from hubgh.hubgh.doctype.afiliacion_seguridad_social.afiliacion_seguridad_social import (
	ensure_affiliation_document_types,
)


def execute():
	if not frappe.db.exists("DocType", "Document Type"):
		return

	ensure_affiliation_document_types()

