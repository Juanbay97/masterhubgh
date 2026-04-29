from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate as _frappe_getdate

from hubgh.api import module_dashboards


class TestHubghModuleDashboardsApi(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self._original_user = frappe.session.user
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user(self._original_user)
		super().tearDown()

	def _assert_contract(self, payload, module_key):
		self.assertIn("module", payload)
		self.assertEqual(payload["module"].get("key"), module_key)
		self.assertIn("meta", payload)
		self.assertIn("generated_at", payload["meta"])

		self.assertIn("kpis", payload)
		self.assertIn("items", payload["kpis"])
		self.assertIn("alerts", payload)
		self.assertIn("items", payload["alerts"])
		self.assertIn("actions", payload)
		self.assertIsInstance(payload["actions"], list)

	def test_dashboard_contract_seleccion(self):
		payload = module_dashboards.get_module_dashboard("seleccion")
		self._assert_contract(payload, "seleccion")

	def test_dashboard_contract_relaciones_laborales(self):
		payload = module_dashboards.get_module_dashboard("relaciones_laborales")
		self._assert_contract(payload, "relaciones_laborales")

	def test_dashboard_contract_rrll_alias(self):
		payload = module_dashboards.get_module_dashboard("rrll")
		self._assert_contract(payload, "rrll")

	def test_dashboard_contract_sst(self):
		payload = module_dashboards.get_module_dashboard("sst")
		self._assert_contract(payload, "sst")

	def test_dashboard_contract_operacion(self):
		payload = module_dashboards.get_module_dashboard("operacion")
		self._assert_contract(payload, "operacion")

	def test_dashboard_contract_nomina(self):
		payload = module_dashboards.get_module_dashboard("nomina")
		self._assert_contract(payload, "nomina")
		routes = {item.get("route") for item in payload.get("actions", [])}
		self.assertIn("app/payroll_workspace", routes)

	def test_dashboard_nomina_returns_empty_during_rewrite(self):
		# El módulo de novedades de nómina está en reescritura: el dashboard
		# devuelve un empty payload con un único action al futuro workspace.
		payload = module_dashboards.get_module_dashboard("nomina")
		self.assertTrue(payload.get("empty"))
		self.assertEqual(payload["module"]["key"], "nomina")
		self.assertEqual(len(payload["actions"]), 1)
		self.assertEqual(payload["actions"][0]["route"], "app/payroll_workspace")

	def test_dashboard_empty_state_seleccion_when_doctype_is_missing(self):
		with patch("hubgh.api.module_dashboards._doctype_exists", return_value=False):
			payload = module_dashboards.get_module_dashboard("seleccion")

		self.assertTrue(payload["empty"])
		self.assertTrue(payload["kpis"]["empty"])
		self.assertTrue(payload["alerts"]["empty"])

	def test_dashboard_empty_state_rl_when_doctypes_are_missing(self):
		with patch("hubgh.api.module_dashboards._doctype_exists", return_value=False):
			payload = module_dashboards.get_module_dashboard("relaciones_laborales")

		self.assertTrue(payload["empty"])
		self.assertTrue(payload["kpis"]["empty"])
		self.assertTrue(payload["alerts"]["empty"])

	def test_dashboard_empty_state_sst_when_doctypes_are_missing(self):
		with patch("hubgh.api.module_dashboards._doctype_exists", return_value=False):
			payload = module_dashboards.get_module_dashboard("sst")

		self.assertTrue(payload["empty"])
		self.assertTrue(payload["kpis"]["empty"])
		self.assertTrue(payload["alerts"]["empty"])

	def test_dashboard_empty_state_operacion_when_user_has_no_point(self):
		with patch("hubgh.api.ops.get_punto_lite", side_effect=frappe.PermissionError):
			payload = module_dashboards.get_module_dashboard("operacion")

		self.assertTrue(payload["empty"])
		self.assertTrue(payload["kpis"]["empty"])
		self.assertTrue(payload["alerts"]["empty"])

	def test_get_initial_tray_reports_uses_common_contract(self):
		payload = module_dashboards.get_initial_tray_reports()

		self.assertEqual(payload["modules"], ["seleccion", "rrll", "sst", "operacion", "nomina"])
		self.assertEqual(set(payload["reports"].keys()), {"seleccion", "rrll", "sst", "operacion", "nomina"})
		for module_key in payload["modules"]:
			self._assert_contract(payload["reports"][module_key], module_key)

	def test_dashboard_contract_nomina_returns_empty_when_user_has_no_payroll_access(self):
		with patch("hubgh.api.module_dashboards.can_user_access_nomina_module", return_value=False):
			payload = module_dashboards.get_module_dashboard("nomina")

		self.assertTrue(payload["empty"])
		self.assertEqual(payload["module"]["key"], "nomina")
		self.assertFalse(payload["policy"]["effective_allowed"])

	def test_get_initial_tray_reports_omits_nomina_without_payroll_access(self):
		with patch("hubgh.api.module_dashboards.can_user_access_nomina_module", return_value=False):
			payload = module_dashboards.get_initial_tray_reports()

		self.assertEqual(payload["modules"], ["seleccion", "rrll", "sst", "operacion"])
		self.assertEqual(set(payload["reports"].keys()), {"seleccion", "rrll", "sst", "operacion"})
