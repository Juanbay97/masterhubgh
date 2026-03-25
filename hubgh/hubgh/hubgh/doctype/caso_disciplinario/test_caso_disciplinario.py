# Copyright (c) 2026, Antigravity and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from types import SimpleNamespace
from unittest.mock import patch

from hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario import CasoDisciplinario


class TestCasoDisciplinario(FrappeTestCase):
	def test_validate_blocks_close_without_decision(self):
		doc = frappe.get_doc({"doctype": "Caso Disciplinario"})
		doc.estado = "Cerrado"
		doc.decision_final = ""
		doc.fecha_cierre = "2026-03-12"

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_validate_blocks_close_without_fecha_cierre(self):
		doc = frappe.get_doc({"doctype": "Caso Disciplinario"})
		doc.estado = "Cerrado"
		doc.decision_final = "Suspensión"
		doc.fecha_cierre = None

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_validate_allows_close_with_decision_and_fecha(self):
		doc = frappe.get_doc({"doctype": "Caso Disciplinario"})
		doc.estado = "Cerrado"
		doc.decision_final = "Archivo"
		doc.fecha_cierre = "2026-03-12"

		doc.validate()

	def test_on_update_termination_marks_employee_as_retirado_and_disables_user(self):
		doc = frappe.get_doc({"doctype": "Caso Disciplinario"})
		doc.name = "DIS-001"
		doc.empleado = "EMP-001"
		doc.estado = "Cerrado"
		doc.decision_final = "Terminación"
		doc.fecha_incidente = "2026-03-10"
		doc.fecha_cierre = "2026-03-12"

		def fake_get_doc(*args, **kwargs):
			if args and args[0] == "Ficha Empleado":
				return SimpleNamespace(name="EMP-001", cedula="1001", email="emp@example.com")
			return SimpleNamespace(insert=lambda **insert_kwargs: None)

		with patch(
			"hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario.frappe.get_doc",
			side_effect=fake_get_doc,
		), patch(
			"hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario.frappe.db.get_value",
			side_effect=lambda doctype, filters, fieldname=None: "user@example.com" if doctype == "User" else None,
		), patch(
			"hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario.frappe.db.exists",
			side_effect=lambda doctype, filters=None: doctype == "DocType",
		), patch(
			"hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario.frappe.db.set_value"
		) as set_value_mock:
			doc.on_update()

		self.assertTrue(any(call.args[:3] == ("Ficha Empleado", "EMP-001", "estado") for call in set_value_mock.call_args_list))
		self.assertTrue(any(call.args[:3] == ("User", "user@example.com", "enabled") for call in set_value_mock.call_args_list))
