import frappe

from hubgh.hubgh.page.seleccion_documentos import seleccion_documentos


@frappe.whitelist()
def get_data():
	return seleccion_documentos.labor_relations_candidates()
