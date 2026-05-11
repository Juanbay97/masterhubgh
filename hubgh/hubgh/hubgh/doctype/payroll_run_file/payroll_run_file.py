# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PayrollRunFile(Document):
	def validate(self) -> None:
		if self.detected_period_month is not None:
			month = int(self.detected_period_month or 0)
			if month and (month < 1 or month > 12):
				frappe.throw("Mes detectado fuera de rango (1-12).")
		if self.detected_period_year is not None:
			year = int(self.detected_period_year or 0)
			if year and (year < 2020 or year > 2099):
				frappe.throw("Año detectado fuera de rango razonable.")
