# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PuntodeVenta(Document):
	def validate(self):
		"""
		CAP-12: Si jefe_responsable está seteado y el User no tiene el rol Jefe_PDV,
		emite un warning visible (no bloqueante) para alertar al operador.
		"""
		jefe = self.get("jefe_responsable")
		if not jefe:
			return

		roles = set(frappe.get_roles(jefe) or [])
		if "Jefe_PDV" not in roles:
			frappe.msgprint(
				f"El usuario {jefe} no tiene rol Jefe_PDV. Asignaselo o elegí otro usuario.",
				alert=True,
			)
