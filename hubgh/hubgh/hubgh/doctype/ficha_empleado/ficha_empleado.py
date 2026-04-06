# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FichaEmpleado(Document):
	def validate(self):
		self.validate_unique_cedula()

	def after_insert(self):
		self._ensure_persona_document_folder()

	def validate_unique_cedula(self):
		if not getattr(self, "cedula", None):
			return
		if frappe.db.exists(
			"Ficha Empleado",
			{"cedula": self.cedula, "name": ["!=", self.name]},
		):
			frappe.throw("La cédula ya existe en otra persona.")

	def _ensure_persona_document_folder(self):
		if frappe.db.exists("Persona Documento", {"persona": self.name, "tipo_documento": "Carpeta"}):
			return
		frappe.get_doc({
			"doctype": "Persona Documento",
			"persona": self.name,
			"tipo_documento": "Carpeta",
			"estado_documento": "Pendiente",
		}).insert(ignore_permissions=True)
