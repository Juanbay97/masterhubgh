# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PayrollNovedad(Document):
	def validate(self) -> None:
		if self.unidad == "cop" and self.valor is None:
			frappe.throw("Las novedades en COP requieren un valor.")
		if self.unidad in {"horas", "dias", "unidades"} and self.cantidad is None:
			frappe.throw("Las novedades en horas/días/unidades requieren una cantidad.")
		if self.manual_override and not (self.override_reason or "").strip():
			frappe.throw("El override manual requiere un motivo.")
