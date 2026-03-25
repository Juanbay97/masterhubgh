# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from hubgh.hubgh.bienestar_automation import ensure_ingreso_followups_for_process


class BienestarProcesoColaborador(Document):
	def validate(self):
		if not self.punto_venta and self.ficha_empleado:
			self.punto_venta = frappe.db.get_value("Ficha Empleado", self.ficha_empleado, "pdv")

	def after_insert(self):
		ensure_ingreso_followups_for_process(self)

	def on_update(self):
		ensure_ingreso_followups_for_process(self)
