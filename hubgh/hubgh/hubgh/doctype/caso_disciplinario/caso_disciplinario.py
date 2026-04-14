# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from hubgh.hubgh.disciplinary_case_service import sync_disciplinary_case_effects


class CasoDisciplinario(Document):
	def validate(self):
		self._normalize_decision_final()
		if (self.estado or "") != "Cerrado":
			return

		if not (self.decision_final or "").strip():
			frappe.throw("No se puede cerrar el caso sin una decisión final.")

		if not self.fecha_cierre:
			frappe.throw("No se puede cerrar el caso sin fecha de cierre.")

		if not (self.resumen_cierre or "").strip():
			frappe.throw("No se puede cerrar el caso sin resumen de cierre.")

		if (self.decision_final or "") == "Suspensión":
			if not self.fecha_inicio_suspension or not self.fecha_fin_suspension:
				frappe.throw("La suspensión requiere fecha inicio y fecha fin.")
			if self.fecha_fin_suspension < self.fecha_inicio_suspension:
				frappe.throw("La fecha fin de suspensión no puede ser menor a la fecha inicio.")
			return

		self.fecha_inicio_suspension = None
		self.fecha_fin_suspension = None

	def on_update(self):
		sync_disciplinary_case_effects(self)

	def _normalize_decision_final(self):
		if (self.decision_final or "").strip() == "Llamado de Atención":
			self.decision_final = "Llamado de atención"
