# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt
"""
ArticuloRITCaso — child table of Citacion Disciplinaria.

REQ-09-04: texto_completo is snapshotted from the linked RIT Articulo on insert,
making it immutable once the citacion row is created.
"""

import frappe
from frappe.model.document import Document


class ArticuloRITCaso(Document):
	def before_insert(self):
		"""Snapshot texto_completo from the linked RIT Articulo (REQ-09-04)."""
		if self.articulo and not self.texto_completo:
			texto = frappe.db.get_value("RIT Articulo", self.articulo, "texto_completo")
			if texto:
				self.texto_completo = texto
