# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt
"""
Acta Descargos — controller

Design reference: obs #863 §1.6
Naming: ACT-.YYYY.-.#####
Validaciones:
  - derechos_informados=1 obligatorio.
  - Si firma_empleado=0 → testigo_1 y testigo_2 required.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class ActaDescargos(Document):
	def validate(self):
		self._validate_derechos_informados()
		self._validate_testigos_si_no_firma()

	def _validate_derechos_informados(self):
		"""Derechos del trabajador (Art. 29 CN) deben haber sido informados antes de guardar."""
		if not self.derechos_informados:
			frappe.throw(
				_(
					"Debe confirmar que se informaron los derechos al trabajador (Art. 29 CN) "
					"antes de guardar el acta."
				),
				frappe.ValidationError,
			)

	def _validate_testigos_si_no_firma(self):
		"""Si el empleado no firma, se requieren 2 testigos (dec. LOCKED #11)."""
		if not self.firma_empleado:
			if not self.testigo_1 or not self.testigo_2:
				frappe.throw(
					_(
						"Si el empleado no firma el acta, se requieren dos testigos "
						"(testigo_1 y testigo_2) para dar validez al documento."
					),
					frappe.ValidationError,
				)
