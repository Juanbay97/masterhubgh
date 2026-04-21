# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class IPS(Document):
	def validate(self):
		if self.requiere_orden_servicio and not self.template_orden_servicio:
			frappe.throw(
				_("Debe adjuntar el template de orden de servicio cuando 'Requiere Orden Servicio' está marcado."),
				frappe.ValidationError,
			)

		# Dedupe examenes_estandar by (cargo, codigo_examen)
		seen = set()
		for row in self.examenes_estandar or []:
			cargo = getattr(row, "cargo", None) or (row.get("cargo") if isinstance(row, dict) else None)
			codigo = getattr(row, "codigo_examen", None) or (row.get("codigo_examen") if isinstance(row, dict) else None)
			key = (cargo, codigo)
			if key in seen:
				frappe.throw(
					_("Examen duplicado por cargo: {0} / {1}").format(cargo, codigo),
					frappe.ValidationError,
				)
			seen.add(key)
