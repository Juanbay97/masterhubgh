# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate

from hubgh.hubgh.people_ops_lifecycle import apply_retirement, reverse_retirement_if_clear


class CasoDisciplinario(Document):
	def validate(self):
		if (self.estado or "") != "Cerrado":
			return

		if not (self.decision_final or "").strip():
			frappe.throw("No se puede cerrar el caso sin una decisión final.")

		if not self.fecha_cierre:
			frappe.throw("No se puede cerrar el caso sin fecha de cierre.")

	def on_update(self):
		if (self.estado or "") == "Cerrado" and (self.decision_final or "").strip() == "Terminación":
			self._apply_rrll_retiro_if_required()
			return
		self._reverse_rrll_retiro_if_possible()

	def _apply_rrll_retiro_if_required(self):
		if not self.empleado:
			return
		apply_retirement(
			employee=self.empleado,
			source_doctype="Caso Disciplinario",
			source_name=self.name,
			retirement_date=self.fecha_cierre or self.fecha_incidente or nowdate(),
			reason=self.decision_final,
		)
		self._emit_retiro_trace_event()

	def _reverse_rrll_retiro_if_possible(self):
		if not self.empleado:
			return
		reverse_retirement_if_clear(
			employee=self.empleado,
			source_doctype="Caso Disciplinario",
			source_name=self.name,
		)

	def _emit_retiro_trace_event(self):
		if not frappe.db.exists("DocType", "GH Novedad"):
			return

		existing = frappe.db.exists(
			"GH Novedad",
			{
				"persona": self.empleado,
				"tipo": "Otro",
				"descripcion": ["like", f"%retiro controlado desde caso disciplinario {self.name}%"],
			},
		)
		if existing:
			return

		frappe.get_doc(
			{
				"doctype": "GH Novedad",
				"persona": self.empleado,
				"tipo": "Otro",
				"cola_origen": "GH-RRLL",
				"cola_destino": "GH-RRLL",
				"estado": "Cerrada",
				"fecha_inicio": self.fecha_incidente or nowdate(),
				"fecha_fin": self.fecha_cierre or nowdate(),
				"descripcion": f"Retiro controlado desde caso disciplinario {self.name}",
			}
		).insert(ignore_permissions=True)
