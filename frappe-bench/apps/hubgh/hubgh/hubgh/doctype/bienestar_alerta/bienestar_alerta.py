# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from hubgh.hubgh.bienestar_context import (
	BIENESTAR_ALERT_SOURCE_FIELDS,
	expected_alert_source_field,
	validate_single_source_reference,
)


class BienestarAlerta(Document):
	def validate(self):
		if not self.punto_venta and self.ficha_empleado:
			self.punto_venta = frappe.db.get_value("Ficha Empleado", self.ficha_empleado, "pdv")

		validate_single_source_reference(
			self,
			BIENESTAR_ALERT_SOURCE_FIELDS,
			doctype_label="Bienestar Alerta",
			expected_field=expected_alert_source_field(self.tipo_alerta),
		)
