"""Stub temporal de permisos del módulo payroll legacy.

El sistema de permisos del módulo legacy se eliminó. Las funciones aquí
expuestas sólo sobreviven porque módulos no-payroll las importan
(`api/module_dashboards.py`, `page/persona_360`). Respuestas permisivas:
el control real vuelve con la fase G del rewrite.
"""

import frappe


def enforce_payroll_access(operation, user=None, context=None):
	return None


def can_user_view_employee_payroll(employee_id, user=None):
	return True


def can_user_access_nomina_module(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	roles = set(frappe.get_roles(user))
	allowed_roles = {"System Manager", "Nomina", "Nómina"}
	return bool(roles & allowed_roles)
