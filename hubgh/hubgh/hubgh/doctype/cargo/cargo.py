# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from hubgh.hubgh.siesa_reference_matrix import normalize_code_for_doctype


class Cargo(Document):
	def validate(self):
		self.codigo = normalize_code_for_doctype("Cargo", self.codigo)
		self.nombre = str(self.nombre or "").strip()
		if not self.codigo:
			frappe.throw("El código SIESA del cargo es obligatorio.")
		if not self.nombre:
			frappe.throw("El nombre del cargo es obligatorio.")
