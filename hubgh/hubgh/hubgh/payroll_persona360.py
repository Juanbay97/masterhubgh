"""Stub temporal del bloque payroll para Persona 360.

El módulo legacy se borró durante la reescritura del proceso de novedades de
nómina. Este archivo queda en pie únicamente para que `page/persona_360`
siga funcionando hasta que la fase G del rewrite reconecte el bloque al
nuevo modelo `hubgh.payroll`.
"""

import frappe


def _(text):
	try:
		from frappe import _ as frappe_translate

		return frappe_translate(text)
	except Exception:
		return text


def get_payroll_block(employee_id):
	return {
		"payroll_ready": False,
		"items": [],
		"message": _("Bloque de nómina deshabilitado durante la reescritura."),
	}


@frappe.whitelist()
def get_employee_payroll_data(employee_id):
	return get_payroll_block(employee_id)
