"""
Test that payroll seed functions work correctly.
This is primarily an integration test to ensure the seed data can be created.
"""

import frappe
import json
from frappe.tests.utils import FrappeTestCase


class TestPayrollSeedIntegration(FrappeTestCase):
	def setUp(self):
		"""Clean up any existing test data."""
		# Don't delete all data, just ensure we can test the seeding functions
		pass

	def test_seed_novedad_types_function(self):
		"""Test that seed_novedad_types creates expected novedad types."""
		from hubgh.hubgh.payroll_seed import seed_novedad_types
		
		# Get initial count
		initial_count = len(frappe.get_all("Payroll Novedad Type"))
		
		# Run seeding (should be idempotent)
		seed_novedad_types()
		
		# Verify key types exist
		essential_types = ["DESCANSO", "VACACIONES", "INC-EG", "INC-AT", "AUSENTISMO"]
		for code in essential_types:
			self.assertTrue(
				frappe.db.exists("Payroll Novedad Type", code),
				f"Essential novedad type {code} should exist after seeding"
			)

	def test_seed_source_catalog_function(self):
		"""Test that seed_source_catalog creates expected sources."""
		from hubgh.hubgh.payroll_seed import seed_source_catalog
		
		# Run seeding
		seed_source_catalog()
		
		# Verify key sources exist
		essential_sources = ["CLONK", "Payflow Resumen", "Fincomercio", "Fondo FONGIGA"]
		for source in essential_sources:
			self.assertTrue(
				frappe.db.exists("Payroll Source Catalog", source),
				f"Essential source {source} should exist after seeding"
			)

	def test_seed_rule_catalog_function(self):
		"""Test that seed_rule_catalog creates expected business rules."""
		from hubgh.hubgh.payroll_seed import seed_rule_catalog
		
		# Run seeding
		seed_rule_catalog()
		
		# Verify key rules exist
		essential_rules = ["HOME12-FIJO", "HOME12-PROP", "AUX-DOM-NOCHE", "TOPE-DESC-702K"]
		for rule_code in essential_rules:
			self.assertTrue(
				frappe.db.exists("Payroll Rule Catalog", rule_code),
				f"Essential rule {rule_code} should exist after seeding"
			)
			
			# Verify rule has valid JSON parameters
			rule = frappe.get_doc("Payroll Rule Catalog", rule_code)
			try:
				params = json.loads(rule.parametros)
				self.assertIsInstance(params, dict, f"Rule {rule_code} should have valid JSON parameters")
			except json.JSONDecodeError:
				self.fail(f"Rule {rule_code} has invalid JSON in parametros field")

	def test_seed_current_period_function(self):
		"""Test that seed_current_period creates a valid period."""
		from hubgh.hubgh.payroll_seed import seed_current_period
		
		# Run seeding
		seed_current_period()
		
		# Check that at least one active period exists
		active_periods = frappe.get_all(
			"Payroll Period Config", 
			filters={"status": "Active"},
			limit=1
		)
		
		self.assertTrue(
			len(active_periods) > 0,
			"At least one active payroll period should exist after seeding"
		)

	def test_complete_foundation_seeding(self):
		"""Test the complete foundation seeding process."""
		from hubgh.hubgh.payroll_seed import seed_payroll_foundation
		
		# Run complete seeding
		try:
			seed_payroll_foundation()
		except Exception as e:
			self.fail(f"Complete foundation seeding should not raise exception: {e}")
		
		# Verify all major components exist
		novedad_count = len(frappe.get_all("Payroll Novedad Type"))
		source_count = len(frappe.get_all("Payroll Source Catalog"))  
		rule_count = len(frappe.get_all("Payroll Rule Catalog"))
		period_count = len(frappe.get_all("Payroll Period Config"))
		
		self.assertGreaterEqual(novedad_count, 12, "Should have at least 12 novedad types")
		self.assertGreaterEqual(source_count, 6, "Should have at least 6 sources")
		self.assertGreaterEqual(rule_count, 4, "Should have at least 4 business rules")
		self.assertGreaterEqual(period_count, 1, "Should have at least 1 period config")