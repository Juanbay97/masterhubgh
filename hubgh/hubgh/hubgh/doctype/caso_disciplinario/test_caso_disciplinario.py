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

	def test_on_update_termination_routes_through_lifecycle(self):
		doc = frappe.get_doc({"doctype": "Caso Disciplinario"})
		doc.name = "DIS-001"
		doc.empleado = "EMP-001"
		doc.estado = "Cerrado"
		doc.decision_final = "Terminación"
		doc.fecha_incidente = "2026-03-10"
		doc.fecha_cierre = "2026-03-12"

		with patch(
			"hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario.apply_retirement"
		) as retirement_mock, patch(
			"hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario.frappe.db.exists",
			side_effect=lambda doctype, filters=None: doctype == "DocType",
		), patch(
			"hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario.frappe.get_doc",
			return_value=SimpleNamespace(insert=lambda **insert_kwargs: None),
		):
			doc.on_update()

		retirement_mock.assert_called_once()

	def test_on_update_reopen_reverses_retirement_when_case_is_no_longer_termination(self):
		doc = frappe.get_doc({"doctype": "Caso Disciplinario"})
		doc.name = "DIS-002"
		doc.empleado = "EMP-001"
		doc.estado = "Abierto"
		doc.decision_final = "Archivo"

		with patch(
			"hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario.reverse_retirement_if_clear"
		) as reverse_mock:
			doc.on_update()

		reverse_mock.assert_called_once_with(employee="EMP-001", source_doctype="Caso Disciplinario", source_name="DIS-002")
