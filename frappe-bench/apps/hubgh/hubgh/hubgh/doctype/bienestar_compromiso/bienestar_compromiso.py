# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from hubgh.hubgh.bienestar_context import validate_compromiso_source_reference


class BienestarCompromiso(Document):
	def validate(self):
		if not self.punto_venta and self.ficha_empleado:
			self.punto_venta = frappe.db.get_value("Ficha Empleado", self.ficha_empleado, "pdv")

		validate_compromiso_source_reference(self, doctype_label="Bienestar Compromiso")

	def on_update(self):
		return
