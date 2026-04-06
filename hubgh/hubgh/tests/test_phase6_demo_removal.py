from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from hubgh.api import my_profile, ops


class TestHubghPhase6DemoRemoval(FrappeTestCase):
	def test_my_profile_summary_returns_explicit_empty_state_without_employee(self):
		with patch("hubgh.api.my_profile._get_employee_from_user", return_value=None):
			payload = my_profile.get_summary()

		self.assertTrue(payload.get("empty"))
		self.assertEqual(payload.get("empty_state", {}).get("code"), "employee_not_linked")
		self.assertEqual(payload.get("profile", {}).get("cargo"), "")
		self.assertEqual(payload.get("profile", {}).get("punto"), "")
		self.assertNotIn("demo", str(payload).lower())

	def test_my_profile_summary_returns_real_shape_with_employee(self):
		emp = {
			"nombres": "Ana",
			"apellidos": "López",
			"cargo": "Auxiliar",
			"pdv": None,
			"estado": "Activo",
		}
		with patch("hubgh.api.my_profile._get_employee_from_user", return_value=emp):
			payload = my_profile.get_summary()

		self.assertFalse(payload.get("empty"))
		self.assertEqual(payload.get("profile", {}).get("nombre"), "Ana López")
		self.assertEqual(payload.get("profile", {}).get("cargo"), "Auxiliar")
		self.assertEqual(payload.get("empty_state", {}).get("code"), None)

	def test_my_profile_time_summary_returns_empty_state_when_timesheet_is_unavailable(self):
		with patch("hubgh.api.my_profile.frappe.db.exists", return_value=False):
			payload = my_profile.get_time_summary()

		self.assertTrue(payload.get("empty"))
		self.assertEqual(payload.get("empty_state", {}).get("code"), "timesheet_unavailable")
		self.assertEqual(payload.get("programadas"), 0)

	def test_my_profile_time_summary_returns_non_empty_with_timesheet_data(self):
		with patch("hubgh.api.my_profile.frappe.db.exists", return_value=True), patch(
			"hubgh.api.my_profile.frappe.get_all",
			return_value=[{"name": "TS-001", "total_hours": 8}],
		):
			payload = my_profile.get_time_summary()

		self.assertFalse(payload.get("empty"))
		self.assertEqual(payload.get("empty_state", {}).get("code"), None)
		self.assertEqual(payload.get("programadas"), 8.0)
		self.assertEqual(payload.get("trabajadas"), 8.0)

	def test_export_docs_zip_persona_returns_explicit_empty_state(self):
		saved = SimpleNamespace(file_url="/private/files/fase6_persona.zip")
		with patch("hubgh.api.ops._get_session_point", return_value=("PDV-001", "Punto 1")), patch(
			"hubgh.api.ops.get_person_docs",
			return_value={"persona": "EMP-001", "items": []},
		), patch("hubgh.api.ops.save_file", return_value=saved):
			payload = ops.export_docs_zip(mode="persona", persona="EMP-001")

		self.assertTrue(payload.get("empty"))
		self.assertEqual(payload.get("empty_state", {}).get("code"), "no_document_categories")
		self.assertIn("file_url", payload)

	def test_export_docs_zip_month_returns_explicit_empty_state(self):
		saved = SimpleNamespace(file_url="/private/files/fase6_punto_mes.zip")
		with patch("hubgh.api.ops._get_session_point", return_value=("PDV-001", "Punto 1")), patch(
			"hubgh.api.ops.frappe.get_all",
			return_value=[],
		), patch("hubgh.api.ops.save_file", return_value=saved):
			payload = ops.export_docs_zip(mode="punto_mes", month="2026-01")

		self.assertTrue(payload.get("empty"))
		self.assertEqual(payload.get("empty_state", {}).get("code"), "no_novedades_in_month")
		self.assertIn("file_name", payload)

