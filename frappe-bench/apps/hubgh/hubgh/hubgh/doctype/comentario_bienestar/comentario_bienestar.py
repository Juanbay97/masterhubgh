# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ComentarioBienestar(Document):
	def after_insert(self):
		self.create_novedad_bienestar()
		self.create_probation_escalation_if_needed()

	def create_novedad_bienestar(self):
		if not self.empleado:
			return

		frappe.get_doc({
			"doctype": "Novedad SST",
			"empleado": self.empleado,
			"categoria_novedad": "Bienestar",
			"tipo_novedad": "Otro",
			"fecha_inicio": self.fecha,
			"descripcion": self.comentario,
			"estado": "Abierto",
			"impacta_estado": 0,
			"ref_doctype": "Comentario Bienestar",
			"ref_docname": self.name,
		}).insert(ignore_permissions=True)

	def create_probation_escalation_if_needed(self):
		"""S7.2: Escalate non-approved probation outcomes to RRLL queue."""
		if not self.empleado:
			return
		if (self.tipo or "") != "Periodo de prueba - No aprobado":
			return
		if not frappe.db.exists("DocType", "GH Novedad"):
			return

		frappe.get_doc(
			{
				"doctype": "GH Novedad",
				"persona": self.empleado,
				"tipo": "Llamado de atención",
				"fecha_inicio": self.fecha,
				"descripcion": f"Escalamiento RRLL por periodo de prueba no aprobado. Fuente: Comentario Bienestar {self.name}.",
				"estado": "Recibida",
				"cola_origen": "GH-Bandeja General",
				"cola_sugerida": "GH-RRLL",
				"cola_destino": "GH-RRLL",
			}
		).insert(ignore_permissions=True)
