# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class RITArticulo(Document):
	def validate(self):
		self._validate_numero()
		self._validate_texto_completo()

	def _validate_numero(self):
		if not self.numero:
			frappe.throw(_("El campo 'número' es obligatorio en RIT Articulo."))

	def _validate_texto_completo(self):
		if not (self.texto_completo or "").strip():
			frappe.throw(_("El campo 'texto_completo' es obligatorio en RIT Articulo."))
