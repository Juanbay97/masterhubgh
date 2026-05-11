# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PayrollParametrosGlobales(Document):
	def validate(self) -> None:
		if (self.divisor_hora_tc or 0) <= 0:
			frappe.throw("Divisor hora TC debe ser mayor a 0.")
		if (self.valor_hora_tp_fija or 0) <= 0:
			frappe.throw("Valor hora TP debe ser mayor a 0.")
		if (self.jornada_induccion_tp_horas or 0) <= 0:
			frappe.throw("Jornada inducción TP debe ser mayor a 0 horas.")
		if (self.salario_minimo_mensual or 0) <= 0:
			frappe.throw("Salario mínimo mensual debe ser mayor a 0.")
