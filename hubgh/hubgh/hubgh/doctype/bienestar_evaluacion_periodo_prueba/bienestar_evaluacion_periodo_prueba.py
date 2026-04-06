# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from hubgh.hubgh.bienestar_automation import (
	calculate_probation_metrics,
	ensure_probation_questionnaire,
)


class BienestarEvaluacionPeriodoPrueba(Document):
	def validate(self):
		if not self.fecha_ingreso and self.ficha_empleado:
			self.fecha_ingreso = frappe.db.get_value("Ficha Empleado", self.ficha_empleado, "fecha_ingreso")

		if not self.punto_venta and self.ficha_empleado:
			self.punto_venta = frappe.db.get_value("Ficha Empleado", self.ficha_empleado, "pdv")

		ensure_probation_questionnaire(self)
		metrics = calculate_probation_metrics(self.respuestas_escala)
		self.puntaje_total = metrics["total_score"]
		self.puntaje_maximo = metrics["max_score"]
		self.porcentaje_resultado = metrics["percentage"]
		self.score_global = metrics["percentage"]
		self.dictamen = metrics["dictamen"]
		self.requiere_escalamiento_rrll = 1 if self.dictamen == "NO APRUEBA" else 0

		if self.dictamen == "NO APRUEBA" and self.estado in {"Pendiente", "En gestión", "Realizada"}:
			self.estado = "No aprobada"

	def on_update(self):
		return
