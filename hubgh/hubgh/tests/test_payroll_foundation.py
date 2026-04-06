import frappe
from frappe.tests.utils import FrappeTestCase


class TestPayrollFoundation(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		"""Set up test data once for the entire test class."""
		super().setUpClass()
		# Ensure foundation data exists
		cls._ensure_foundation_data()

	@classmethod
	def _ensure_foundation_data(cls):
		"""Ensure basic foundation data exists for tests."""
		# Create a test novedad type if it doesn't exist
		if not frappe.db.exists("Payroll Novedad Type", "TEST-FOUNDATION"):
			frappe.get_doc({
				"doctype": "Payroll Novedad Type",
				"codigo": "TEST-FOUNDATION",
				"novedad_type": "Test Foundation Type",
				"sensitivity": "operational",
				"status": "Active",
			}).insert(ignore_permissions=True)

		# Create test period if it doesn't exist
		if not frappe.db.exists("Payroll Period Config", {"nombre_periodo": "Test Period Foundation"}):
			frappe.get_doc({
				"doctype": "Payroll Period Config",
				"nombre_periodo": "Test Period Foundation",
				"ano": 2026,
				"mes": 3,
				"fecha_corte_inicio": "2026-03-01",
				"fecha_corte_fin": "2026-03-15",
				"status": "Draft",
				"total_dias": 15,
			}).insert(ignore_permissions=True)

	def tearDown(self):
		"""Clean up after each test."""
		frappe.delete_doc_if_exists("Payroll Novedad Type", "TEST-FOUNDATION", force=True)
		frappe.delete_doc_if_exists("Payroll Period Config", "Test Period Foundation", force=True)

	def test_novedad_type_code_mapping(self):
		"""Test that novedad type codes map correctly to CLONK codes."""
		# Test that essential CLONK codes exist
		essential_codes = ["DESCANSO", "VACACIONES", "INC-EG", "INC-AT", "AUSENTISMO"]
		
		for code in essential_codes:
			exists = frappe.db.exists("Payroll Novedad Type", code)
			self.assertTrue(
				exists, 
				f"Essential novedad type {code} should exist in catalog"
			)
			
			if exists:
				doc = frappe.get_doc("Payroll Novedad Type", code)
				self.assertEqual(doc.status, "Active", f"Novedad type {code} should be Active")
				self.assertIsNotNone(doc.sensitivity, f"Novedad type {code} should have sensitivity set")

	def test_requires_support_flag(self):
		"""Test that support-requiring novedad types are properly flagged."""
		# Test types that should require support
		support_required = ["INC-EG", "INC-AT", "MATERNIDAD", "CALAMIDAD", "LUTO"]
		
		for code in support_required:
			if frappe.db.exists("Payroll Novedad Type", code):
				doc = frappe.get_doc("Payroll Novedad Type", code)
				self.assertTrue(
					doc.requiere_soporte,
					f"Novedad type {code} should require support documentation"
				)

		# Test types that should NOT require support
		no_support_required = ["DESCANSO", "CUMPLEANOS", "DIA-FAMILIA"]
		
		for code in no_support_required:
			if frappe.db.exists("Payroll Novedad Type", code):
				doc = frappe.get_doc("Payroll Novedad Type", code)
				self.assertFalse(
					doc.requiere_soporte,
					f"Novedad type {code} should not require support documentation"
				)

	def test_sensitivity_mapping(self):
		"""Test that sensitivity levels are properly assigned."""
		sensitivity_map = {
			"clinical": ["INC-EG", "ENF-GENERAL", "MATERNIDAD"],
			"sst_clinical": ["INC-AT"],
			"disciplinary": ["AUSENTISMO", "NNR", "DNR", "BONIF-PERD"],
			"operational": ["DESCANSO", "VACACIONES", "HD", "HN", "AUX-HOME12"]
		}
		
		for sensitivity, codes in sensitivity_map.items():
			for code in codes:
				if frappe.db.exists("Payroll Novedad Type", code):
					doc = frappe.get_doc("Payroll Novedad Type", code)
					self.assertEqual(
						doc.sensitivity, 
						sensitivity,
						f"Novedad type {code} should have sensitivity '{sensitivity}'"
					)

	def test_source_catalog_completeness(self):
		"""Test that all required sources are in catalog."""
		required_sources = ["CLONK", "Payflow Resumen", "Fincomercio", "Fondo FONGIGA"]
		
		for source in required_sources:
			exists = frappe.db.exists("Payroll Source Catalog", source)
			self.assertTrue(
				exists,
				f"Required source {source} should exist in catalog"
			)
			
			if exists:
				doc = frappe.get_doc("Payroll Source Catalog", source)
				self.assertEqual(doc.status, "Active", f"Source {source} should be Active")

	def test_business_rules_existence(self):
		"""Test that essential business rules exist."""
		essential_rules = ["HOME12-FIJO", "HOME12-PROP", "AUX-DOM-NOCHE", "TOPE-DESC-702K"]
		
		for rule_code in essential_rules:
			exists = frappe.db.exists("Payroll Rule Catalog", rule_code)
			self.assertTrue(
				exists,
				f"Essential business rule {rule_code} should exist in catalog"
			)
			
			if exists:
				doc = frappe.get_doc("Payroll Rule Catalog", rule_code)
				self.assertTrue(doc.activa, f"Business rule {rule_code} should be active")
				self.assertIsNotNone(doc.parametros, f"Business rule {rule_code} should have parameters")

	def test_home12_rule_parameters(self):
		"""Test HOME12 rules have correct parameters."""
		if frappe.db.exists("Payroll Rule Catalog", "HOME12-FIJO"):
			import json
			doc = frappe.get_doc("Payroll Rule Catalog", "HOME12-FIJO")
			params = json.loads(doc.parametros)
			
			self.assertEqual(params.get("amount"), 110000, "HOME12-FIJO should have amount 110000")
			self.assertEqual(params.get("pdv_count"), 6, "HOME12-FIJO should require 6 PDV")
			self.assertEqual(params.get("currency"), "COP", "HOME12-FIJO should be in COP")

		if frappe.db.exists("Payroll Rule Catalog", "AUX-DOM-NOCHE"):
			import json
			doc = frappe.get_doc("Payroll Rule Catalog", "AUX-DOM-NOCHE")
			params = json.loads(doc.parametros)
			
			self.assertEqual(params.get("amount"), 7000, "AUX-DOM-NOCHE should have amount 7000")
			self.assertEqual(params.get("after_time"), "21:55", "AUX-DOM-NOCHE should apply after 21:55")

	def test_payroll_period_structure(self):
		"""Test payroll period configuration."""
		# Test that at least one period exists
		periods = frappe.get_all("Payroll Period Config", limit=1)
		self.assertTrue(len(periods) > 0, "At least one payroll period should exist")
		
		# Test period field completeness
		if periods:
			period_name = periods[0].name
			doc = frappe.get_doc("Payroll Period Config", period_name)
			
			self.assertIsNotNone(doc.ano, "Period should have year set")
			self.assertIsNotNone(doc.mes, "Period should have month set")
			self.assertIsNotNone(doc.fecha_corte_inicio, "Period should have start date")
			self.assertIsNotNone(doc.fecha_corte_fin, "Period should have end date")
			self.assertIn(doc.status, ["Draft", "Active", "Closed"], "Period should have valid status")