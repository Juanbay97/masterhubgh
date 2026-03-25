# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from hubgh.hubgh.bienestar_automation import (
	calculate_followup_score,
	ensure_followup_questionnaire,
)


class BienestarSeguimientoIngreso(Document):
	def validate(self):
		if self.tipo_seguimiento == "30/45" and not self.momento_consolidacion:
			frappe.throw("El momento de consolidación es obligatorio para el seguimiento 30/45")

		if not self.fecha_ingreso and self.ficha_empleado:
			self.fecha_ingreso = frappe.db.get_value("Ficha Empleado", self.ficha_empleado, "fecha_ingreso")

		if not self.punto_venta and self.ficha_empleado:
			self.punto_venta = frappe.db.get_value("Ficha Empleado", self.ficha_empleado, "pdv")

		ensure_followup_questionnaire(self)
		self.score_global = calculate_followup_score(self.respuestas_escala)

	def on_update(self):
		return
