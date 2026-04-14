# Copyright (c) 2026, Antigravity and Contributors
# See license.txt

from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase
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
		doc.resumen_cierre = "Sin mérito para sanción"

		doc.validate()

	def test_validate_blocks_close_without_summary(self):
		doc = frappe.get_doc({"doctype": "Caso Disciplinario"})
		doc.estado = "Cerrado"
		doc.decision_final = "Archivo"
		doc.fecha_cierre = "2026-03-12"
		doc.resumen_cierre = ""

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_validate_blocks_suspension_without_dates(self):
		doc = frappe.get_doc({"doctype": "Caso Disciplinario"})
		doc.estado = "Cerrado"
		doc.decision_final = "Suspensión"
		doc.fecha_cierre = "2026-03-12"
		doc.resumen_cierre = "Cierre RRLL"
		doc.fecha_inicio_suspension = None
		doc.fecha_fin_suspension = None

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_on_update_termination_routes_through_service(self):
		doc = frappe.get_doc({"doctype": "Caso Disciplinario"})
		doc.name = "DIS-001"
		doc.empleado = "EMP-001"
		doc.estado = "Cerrado"
		doc.decision_final = "Terminación"
		doc.fecha_incidente = "2026-03-10"
		doc.fecha_cierre = "2026-03-12"
		doc.resumen_cierre = "Validación RRLL final"

		with patch(
			"hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario.sync_disciplinary_case_effects"
		) as sync_mock:
			doc.on_update()

		sync_mock.assert_called_once_with(doc)

	def test_punto_360_quick_action_routes_to_rrll_disciplinary_tray(self):
		js_path = Path(__file__).resolve().parents[2] / "page" / "punto_360" / "punto_360.js"
		content = js_path.read_text(encoding="utf-8")

		self.assertIn("frappe.set_route('bandeja_casos_disciplinarios')", content)
		self.assertNotIn("frappe.new_doc('Caso Disciplinario', { pdv: pdvId });", content)

	def test_on_update_reopen_reverses_retirement_when_case_is_no_longer_termination(self):
		doc = frappe.get_doc({"doctype": "Caso Disciplinario"})
		doc.name = "DIS-002"
		doc.empleado = "EMP-001"
		doc.estado = "Abierto"
		doc.decision_final = "Archivo"

		with patch(
			"hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario.sync_disciplinary_case_effects"
		) as sync_mock:
			doc.on_update()

		sync_mock.assert_called_once_with(doc)
