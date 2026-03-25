# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class CasoDisciplinario(Document):
	def validate(self):
		if (self.estado or "") != "Cerrado":
			return

		if not (self.decision_final or "").strip():
			frappe.throw("No se puede cerrar el caso sin una decisión final.")

		if not self.fecha_cierre:
			frappe.throw("No se puede cerrar el caso sin fecha de cierre.")

	def on_update(self):
		if (self.estado or "") != "Cerrado":
			return
		self._apply_rrll_retiro_if_required()

	def _apply_rrll_retiro_if_required(self):
		if (self.decision_final or "").strip() != "Terminación":
			return
		if not self.empleado:
			return

		frappe.db.set_value("Ficha Empleado", self.empleado, "estado", "Retirado", update_modified=False)
		self._disable_employee_user()
		self._emit_retiro_trace_event()

	def _disable_employee_user(self):
		persona = frappe.get_doc("Ficha Empleado", self.empleado)
		cedula = (getattr(persona, "cedula", None) or "").strip()
		user_name = None

		if cedula:
			user_name = frappe.db.get_value("User", {"username": cedula}, "name")
			if not user_name and frappe.db.exists("User", cedula):
				user_name = cedula

		if not user_name and getattr(persona, "email", None):
			user_name = frappe.db.get_value("User", {"email": persona.email}, "name")

		if user_name:
			frappe.db.set_value("User", user_name, "enabled", 0, update_modified=False)

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
