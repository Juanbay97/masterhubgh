# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from hubgh.hubgh.bienestar_automation import calculate_point_lifting_score


class BienestarLevantamientoPunto(Document):
	def validate(self):
		participant_count = len(self.participantes or [])
		for row in self.participantes or []:
			if not getattr(row, "ficha_empleado", None):
				continue

			emp_pdv = frappe.db.get_value("Ficha Empleado", row.ficha_empleado, "pdv")
			if self.punto_venta and emp_pdv and emp_pdv != self.punto_venta:
				frappe.throw(
					f"El colaborador {row.ficha_empleado} no pertenece al punto seleccionado {self.punto_venta}."
				)

		score_global, cobertura = calculate_point_lifting_score(self.participantes)
		self.score_global = score_global
		if participant_count:
			self.cobertura_participacion = cobertura
