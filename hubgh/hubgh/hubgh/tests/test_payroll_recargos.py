"""
Tests for Payroll Recargos (Hourly Calculation) functionality.

Sprint 5: Tests for TP hourly calculation rules with employee-specific base rates,
nocturnal, dominical, and extra hours recargos, plus HOME12 prorated subsidy.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, now_datetime, add_days, flt
from unittest.mock import patch, MagicMock

from hubgh.hubgh.payroll_tp_tray import PayrollTPTrayService


class TestPayrollRecargos(FrappeTestCase):
	"""Test suite for payroll recargo calculations."""
	
	def setUp(self):
		"""Set up test data for recargo calculations."""
		self.cleanup_test_data()
		self.create_test_data()
		self.service = PayrollTPTrayService()
		
	def tearDown(self):
		"""Clean up after tests."""
		self.cleanup_test_data()
		
	def cleanup_test_data(self):
		"""Remove test data."""
		frappe.db.delete("Payroll Import Line", {"batch": ["like", "TEST-RECARGO-%"]})
		frappe.db.delete("Payroll Import Batch", {"name": ["like", "TEST-RECARGO-%"]})
		frappe.db.delete("Employee", {"employee_id": ["like", "EMP-RECARGO-%"]})
		frappe.db.commit()
		
	def create_test_data(self):
		"""Create test employees with different salary levels."""
		
		# Create test employee 1: Standard rate
		emp1_doc = frappe.new_doc("Employee")
		emp1_doc.employee_name = "Pedro Recargo Standard"
		emp1_doc.employee_id = "EMP-RECARGO-001"
		emp1_doc.personal_email = "11111111"
		emp1_doc.company = "HOME BURGERS"
		emp1_doc.branch = "PDV Centro"
		emp1_doc.ctc = 3600000  # 15,000/hour (3.6M / 240 hours)
		emp1_doc.insert(ignore_permissions=True)
		
		# Create test employee 2: HOME12 higher rate
		emp2_doc = frappe.new_doc("Employee")
		emp2_doc.employee_name = "Ana Recargo HOME12"
		emp2_doc.employee_id = "EMP-RECARGO-002"
		emp2_doc.personal_email = "22222222"
		emp2_doc.company = "HOME BURGERS" 
		emp2_doc.branch = "HOME12 PDV Norte"
		emp2_doc.ctc = 4320000  # 18,000/hour
		emp2_doc.insert(ignore_permissions=True)
		
		frappe.db.commit()
		
		# Store for test reference
		self.test_employees = ["EMP-RECARGO-001", "EMP-RECARGO-002"]
		
	def test_nocturnal_recargo_25_percent(self):
		"""Test nocturnal recargo calculation: base_rate × 1.25 (9PM-6AM)."""
		
		# Standard employee with known base rate (15,000/hour)
		line_data = {
			"matched_employee": "EMP-RECARGO-001",
			"employee_id": "EMP-RECARGO-001",
			"novedad_date": "2026-03-15"
		}
		
		# Test nocturnal hours calculation
		recargos = self.service.calculate_recargos("HN", 8.0, line_data)
		
		# Expected: 8 hours × 15,000 × 0.25 = 30,000
		expected_nocturnal = 8.0 * 15000 * 0.25
		self.assertEqual(recargos["nocturnal"], expected_nocturnal)
		self.assertEqual(recargos["dominical"], 0)
		self.assertEqual(recargos["extra_hours"], 0)
		
	def test_dominical_recargo_100_percent(self):
		"""Test dominical recargo: base_rate × 2.0 (Sunday/festive)."""
		
		# Sunday date for dominical calculation
		sunday_date = "2026-03-16"  # This should be a Sunday
		line_data = {
			"matched_employee": "EMP-RECARGO-001",
			"employee_id": "EMP-RECARGO-001",
			"novedad_date": sunday_date,
			"quantity": 8.0
		}
		
		# Mock the dominical work detection
		with patch.object(self.service, '_is_dominical_work', return_value=True):
			with patch.object(self.service, '_extract_dominical_hours', return_value=8.0):
				recargos = self.service.calculate_recargos("HD", 8.0, line_data)
		
		# Expected: 8 hours × 15,000 × 1.0 = 120,000 (100% additional)
		expected_dominical = 8.0 * 15000 * 1.0
		self.assertEqual(recargos["dominical"], expected_dominical)
		
	def test_extra_diurna_25_percent(self):
		"""Test extra hours diurnas: base_rate × 1.25 (first 2h extra)."""
		
		line_data = {
			"matched_employee": "EMP-RECARGO-001",
			"employee_id": "EMP-RECARGO-001",
			"novedad_date": "2026-03-15"
		}
		
		# Test extra diurnal hours
		recargos = self.service.calculate_recargos("HED", 2.0, line_data)
		
		# Expected: 2 hours × 15,000 × 0.25 = 7,500
		expected_extra = 2.0 * 15000 * 0.25
		self.assertEqual(recargos["extra_hours"], expected_extra)
		self.assertEqual(recargos["nocturnal"], 0)
		self.assertEqual(recargos["dominical"], 0)
		
	def test_extra_nocturna_75_percent(self):
		"""Test extra hours nocturnas: base_rate × 1.75 (25% night + 50% extra)."""
		
		line_data = {
			"matched_employee": "EMP-RECARGO-001", 
			"employee_id": "EMP-RECARGO-001",
			"novedad_date": "2026-03-15"
		}
		
		# Test nocturnal extra hours (HEN)
		recargos = self.service.calculate_recargos("HEN", 3.0, line_data)
		
		# Expected: 3 hours × 15,000 × 0.25 = 11,250 (nocturnal part)
		# Expected: 3 hours × 15,000 × 0.50 = 22,500 (extra part)
		expected_nocturnal = 3.0 * 15000 * 0.25
		expected_extra = 3.0 * 15000 * 0.50
		
		self.assertEqual(recargos["nocturnal"], expected_nocturnal)
		self.assertEqual(recargos["extra_hours"], expected_extra)
		self.assertEqual(recargos["dominical"], 0)
		
	def test_employee_specific_base_rates(self):
		"""Test that base rates are calculated from employee salary data."""
		
		# Test standard employee (15,000/hour)
		line_data_1 = {
			"matched_employee": "EMP-RECARGO-001",
			"employee_id": "EMP-RECARGO-001",
			"novedad_date": "2026-03-15"
		}
		
		base_rate_1 = self.service._get_employee_base_rate(line_data_1)
		self.assertEqual(base_rate_1, 15000)
		
		# Test HOME12 employee (18,000/hour)
		line_data_2 = {
			"matched_employee": "EMP-RECARGO-002",
			"employee_id": "EMP-RECARGO-002", 
			"novedad_date": "2026-03-15"
		}
		
		base_rate_2 = self.service._get_employee_base_rate(line_data_2)
		self.assertEqual(base_rate_2, 18000)
		
		# Test nocturnal with different base rates
		recargos_1 = self.service.calculate_recargos("HN", 4.0, line_data_1)
		recargos_2 = self.service.calculate_recargos("HN", 4.0, line_data_2)
		
		# Standard: 4 × 15,000 × 0.25 = 15,000
		# HOME12: 4 × 18,000 × 0.25 = 18,000
		self.assertEqual(recargos_1["nocturnal"], 15000)
		self.assertEqual(recargos_2["nocturnal"], 18000)
		
	def test_HOME12_full_subsidy(self):
		"""Test HOME12 FIJO: $110,000/month if employee in HOME12 PDV with >= 6 PDVs."""
		
		# Create employee data for HOME12 employee without incapacidad
		emp_data = {
			"employee_id": "EMP-RECARGO-002",
			"employee_name": "Ana Recargo HOME12",
			"home12_subsidy": 0,
			"auxilios_total": 0,
			"has_incapacidad_or_licencia": False,
			"novelty_breakdown": {}
		}
		
		# Apply HOME12 proration
		updated_emp_data = self.service._apply_home12_proration(emp_data)
		
		# Should receive full subsidy
		self.assertEqual(updated_emp_data["home12_subsidy"], 110000)
		self.assertEqual(updated_emp_data["auxilios_total"], 110000)
		self.assertIn("FIJO", updated_emp_data["home12_proration_note"])
		
	def test_HOME12_prorated_with_incapacidad(self):
		"""Test HOME12 PROP: Prorated if employee had Incapacidad/Licencia during period."""
		
		# Create employee data with incapacidad (5 days out of 30)
		emp_data = {
			"employee_id": "EMP-RECARGO-002",
			"employee_name": "Ana Recargo HOME12",
			"home12_subsidy": 0,
			"auxilios_total": 0,
			"has_incapacidad_or_licencia": True,
			"batches": ["TEST-BATCH"],
			"novelty_breakdown": {
				"INC-EG": {
					"quantity": 5,  # 5 days of incapacidad
					"amount": 0
				}
			}
		}
		
		# Apply HOME12 proration
		updated_emp_data = self.service._apply_home12_proration(emp_data)
		
		# Expected: (30 - 5) / 30 * 110,000 = 0.833 * 110,000 = 91,666.67
		expected_prorated = 110000 * (25 / 30)
		self.assertAlmostEqual(updated_emp_data["home12_subsidy"], expected_prorated, places=0)
		self.assertAlmostEqual(updated_emp_data["auxilios_total"], expected_prorated, places=0)
		self.assertIn("Prorrateado", updated_emp_data["home12_proration_note"])
		
	def test_is_home12_employee_detection(self):
		"""Test detection of HOME12 employees."""
		
		# Test HOME12 employee
		is_home12_1 = self.service._is_home12_employee("EMP-RECARGO-002")
		self.assertTrue(is_home12_1)
		
		# Test non-HOME12 employee
		is_home12_2 = self.service._is_home12_employee("EMP-RECARGO-001")
		self.assertFalse(is_home12_2)
		
	def test_proration_factor_calculation(self):
		"""Test calculation of proration factor for HOME12 subsidy."""
		
		# Test case: 5 days incapacidad out of 30
		emp_data = {
			"batches": ["TEST-BATCH"],
			"novelty_breakdown": {
				"INC-EG": {"quantity": 3},
				"LICENCIA": {"quantity": 2}
			}
		}
		
		factor = self.service._calculate_home12_proration_factor(emp_data)
		expected_factor = (30 - 5) / 30  # 25/30 = 0.833...
		self.assertAlmostEqual(factor, expected_factor, places=3)
		
		# Test case: No incapacidad
		emp_data_no_inc = {
			"batches": ["TEST-BATCH"],
			"novelty_breakdown": {"HD": {"quantity": 160}}
		}
		
		factor_no_inc = self.service._calculate_home12_proration_factor(emp_data_no_inc)
		self.assertEqual(factor_no_inc, 1.0)
		
		# Test edge case: More incapacidad than days in period
		emp_data_over = {
			"batches": ["TEST-BATCH"], 
			"novelty_breakdown": {
				"INC-EG": {"quantity": 35}  # More than 30 days
			}
		}
		
		factor_over = self.service._calculate_home12_proration_factor(emp_data_over)
		self.assertEqual(factor_over, 0.0)  # Should not be negative
		
	def test_combined_recargos_calculation(self):
		"""Test combined scenarios with multiple recargos."""
		
		# Create comprehensive test data
		lines = [
			{
				"matched_employee": "EMP-RECARGO-001",
				"employee_id": "EMP-RECARGO-001",
				"novedad_type": "HD",
				"quantity": 160,
				"amount": 2400000,
				"novedad_date": "2026-03-15"
			},
			{
				"matched_employee": "EMP-RECARGO-001",
				"employee_id": "EMP-RECARGO-001",
				"novedad_type": "HN",
				"quantity": 12,
				"amount": 225000,
				"novedad_date": "2026-03-15"
			},
			{
				"matched_employee": "EMP-RECARGO-001",
				"employee_id": "EMP-RECARGO-001",
				"novedad_type": "HED",
				"quantity": 6,
				"amount": 112500,
				"novedad_date": "2026-03-15"
			},
			{
				"matched_employee": "EMP-RECARGO-001",
				"employee_id": "EMP-RECARGO-001",
				"novedad_type": "HEN",
				"quantity": 4,
				"amount": 105000,
				"novedad_date": "2026-03-15"
			}
		]
		
		# Test consolidation with all recargo types
		consolidation = self.service.consolidate_by_employee_with_recargos(lines)
		
		self.assertEqual(len(consolidation), 1)
		emp_data = consolidation[0]
		
		# Verify hour totals
		self.assertEqual(emp_data["hour_totals"]["HD"], 160)
		self.assertEqual(emp_data["hour_totals"]["HN"], 12)
		self.assertEqual(emp_data["hour_totals"]["HED"], 6)
		self.assertEqual(emp_data["hour_totals"]["HEN"], 4)
		
		# Verify recargo calculations
		# HN: 12 × 15,000 × 0.25 = 45,000
		# HED: 6 × 15,000 × 0.25 = 22,500
		# HEN nocturnal: 4 × 15,000 × 0.25 = 15,000
		# HEN extra: 4 × 15,000 × 0.50 = 30,000
		expected_nocturnal = (12 * 15000 * 0.25) + (4 * 15000 * 0.25)
		expected_extra = (6 * 15000 * 0.25) + (4 * 15000 * 0.50)
		
		self.assertEqual(emp_data["recargos"]["nocturnal_amount"], expected_nocturnal)
		self.assertEqual(emp_data["recargos"]["extra_hours_amount"], expected_extra)
		
		# Verify total calculations include recargos
		total_recargos = sum(emp_data["recargos"].values())
		self.assertGreater(total_recargos, 0)
		self.assertIn(total_recargos, emp_data["total_devengado"])
		
	def test_weekend_dominical_detection(self):
		"""Test dominical work detection for weekends."""
		
		# Test Sunday detection
		sunday_line = {
			"matched_employee": "EMP-RECARGO-001",
			"novedad_date": "2026-03-22"  # Should be a Sunday
		}
		
		# Mock date to ensure Sunday
		with patch('hubgh.hubgh.payroll_tp_tray.getdate') as mock_getdate:
			mock_date = MagicMock()
			mock_date.weekday.return_value = 6  # Sunday
			mock_getdate.return_value = mock_date
			
			is_dominical = self.service._is_dominical_work(sunday_line)
			self.assertTrue(is_dominical)
		
		# Test regular weekday
		weekday_line = {
			"matched_employee": "EMP-RECARGO-001",
			"novedad_date": "2026-03-18"  # Weekday
		}
		
		with patch('hubgh.hubgh.payroll_tp_tray.getdate') as mock_getdate:
			mock_date = MagicMock()
			mock_date.weekday.return_value = 2  # Wednesday
			mock_getdate.return_value = mock_date
			
			is_dominical = self.service._is_dominical_work(weekday_line)
			self.assertFalse(is_dominical)
			
	def test_error_handling_in_recargos(self):
		"""Test error handling in recargo calculations."""
		
		# Test with invalid employee data
		invalid_line = {
			"matched_employee": None,
			"employee_id": None,
			"novedad_date": "2026-03-15"
		}
		
		recargos = self.service.calculate_recargos("HN", 8.0, invalid_line)
		
		# Should return default rate calculation without crashing
		self.assertIsInstance(recargos, dict)
		self.assertIn("nocturnal", recargos)
		self.assertIn("dominical", recargos)
		self.assertIn("extra_hours", recargos)
		
		# Test with invalid novelty type
		valid_line = {
			"matched_employee": "EMP-RECARGO-001",
			"employee_id": "EMP-RECARGO-001",
			"novedad_date": "2026-03-15"
		}
		
		recargos = self.service.calculate_recargos("INVALID_TYPE", 8.0, valid_line)
		
		# Should return zeros for unknown types
		self.assertEqual(recargos["nocturnal"], 0)
		self.assertEqual(recargos["dominical"], 0)
		self.assertEqual(recargos["extra_hours"], 0)


class TestRecargosIntegration(FrappeTestCase):
	"""Integration tests for recargos in full TP workflow."""
	
	def setUp(self):
		"""Set up integration test data."""
		self.cleanup_test_data()
		self.create_integration_test_data()
		
	def tearDown(self):
		"""Clean up after tests."""
		self.cleanup_test_data()
		
	def cleanup_test_data(self):
		"""Remove test data."""
		frappe.db.delete("Payroll Import Line", {"batch": ["like", "TEST-RECARGO-INT-%"]})
		frappe.db.delete("Payroll Import Batch", {"name": ["like", "TEST-RECARGO-INT-%"]})
		frappe.db.delete("Employee", {"employee_id": ["like", "EMP-RECARGO-INT-%"]})
		frappe.db.commit()
		
	def create_integration_test_data(self):
		"""Create integration test scenario with real batch and lines."""
		
		# Create test employee
		emp_doc = frappe.new_doc("Employee")
		emp_doc.employee_name = "Integration Test Recargos"
		emp_doc.employee_id = "EMP-RECARGO-INT-001"
		emp_doc.personal_email = "33333333"
		emp_doc.company = "HOME BURGERS"
		emp_doc.branch = "HOME12 PDV Centro"
		emp_doc.ctc = 4320000  # 18,000/hour
		emp_doc.insert(ignore_permissions=True)
		
		# Create test batch
		batch_doc = frappe.new_doc("Payroll Import Batch")
		batch_doc.name = "TEST-RECARGO-INT-001"
		batch_doc.source_type = "CLONK"
		batch_doc.nomina_period = "2026-03"
		batch_doc.insert(ignore_permissions=True)
		
		# Create comprehensive test lines
		test_lines = [
			{
				"novedad_type": "HD",
				"quantity": 120,
				"amount": 2160000  # 120 × 18,000
			},
			{
				"novedad_type": "HN",
				"quantity": 16,
				"amount": 360000  # 16 × 18,000 × 1.25
			},
			{
				"novedad_type": "HED",
				"quantity": 8,
				"amount": 180000  # 8 × 18,000 × 1.25
			},
			{
				"novedad_type": "HEN",
				"quantity": 4,
				"amount": 126000  # 4 × 18,000 × 1.75
			},
			{
				"novedad_type": "AUX-HOME12",
				"quantity": 1,
				"amount": 110000
			},
			{
				"novedad_type": "INC-EG",
				"quantity": 3,  # 3 days incapacidad for proration
				"amount": 0
			}
		]
		
		for i, line_data in enumerate(test_lines):
			line_doc = frappe.new_doc("Payroll Import Line")
			line_doc.batch = "TEST-RECARGO-INT-001"
			line_doc.row_number = i + 1
			line_doc.employee_id = "EMP-RECARGO-INT-001"
			line_doc.employee_name = "Integration Test Recargos"
			line_doc.matched_employee = "EMP-RECARGO-INT-001"
			line_doc.status = "Válido"
			line_doc.tc_status = "Aprobado"
			line_doc.tp_status = "Pendiente"
			line_doc.novedad_date = "2026-03-15"
			
			for field, value in line_data.items():
				setattr(line_doc, field, value)
			
			line_doc.insert(ignore_permissions=True)
		
		frappe.db.commit()
		self.integration_batch = "TEST-RECARGO-INT-001"
		
	def test_full_tp_consolidation_with_recargos(self):
		"""Test complete TP consolidation including all recargo types and HOME12 proration."""
		
		service = PayrollTPTrayService()
		
		# Test consolidation
		result = service.consolidate_by_period(batch_filter=self.integration_batch)
		
		self.assertEqual(result["status"], "success")
		self.assertEqual(result["total_employees"], 1)
		
		emp_data = result["employee_consolidation"][0]
		
		# Verify hour consolidation
		self.assertEqual(emp_data["hour_totals"]["HD"], 120)
		self.assertEqual(emp_data["hour_totals"]["HN"], 16)
		self.assertEqual(emp_data["hour_totals"]["HED"], 8)
		self.assertEqual(emp_data["hour_totals"]["HEN"], 4)
		
		# Verify recargo calculations with employee-specific rate (18,000/hour)
		expected_nocturnal = (16 * 18000 * 0.25) + (4 * 18000 * 0.25)  # HN + HEN nocturnal
		expected_extra = (8 * 18000 * 0.25) + (4 * 18000 * 0.50)  # HED + HEN extra
		
		self.assertEqual(emp_data["recargos"]["nocturnal_amount"], expected_nocturnal)
		self.assertEqual(emp_data["recargos"]["extra_hours_amount"], expected_extra)
		
		# Verify HOME12 proration (3 days out of 30)
		expected_home12_prorated = 110000 * (27 / 30)  # 99,000
		self.assertAlmostEqual(emp_data["home12_subsidy"], expected_home12_prorated, places=0)
		self.assertIn("Prorrateado", emp_data["home12_proration_note"])
		
		# Verify total calculations
		total_recargos = sum(emp_data["recargos"].values())
		self.assertGreater(total_recargos, 0)
		
		# HOME12 should be included in auxilios
		self.assertIn(emp_data["home12_subsidy"], emp_data["auxilios_total"])
		
		# Total devengado should include recargos and subsidies
		expected_devengado = (
			emp_data["devengo_total"] +  # Base amounts
			emp_data["auxilios_total"] +  # Including HOME12
			total_recargos  # All recargos
		)
		self.assertAlmostEqual(emp_data["total_devengado"], expected_devengado, places=0)
		
		# Net pay calculation
		expected_neto = emp_data["total_devengado"] - emp_data["total_deducciones"]
		self.assertAlmostEqual(emp_data["neto_a_pagar"], expected_neto, places=0)
		
	def test_executive_summary_with_enhanced_amounts(self):
		"""Test executive summary includes enhanced recargo calculations."""
		
		service = PayrollTPTrayService()
		result = service.consolidate_by_period(batch_filter=self.integration_batch)
		
		summary = result["executive_summary"]
		
		# Total payroll amount should include all enhancements
		self.assertGreater(summary["total_payroll_amount"], 2500000)  # Base + recargos + subsidies
		
		# Average per employee should reflect enhanced calculations
		expected_avg = summary["total_payroll_amount"] / summary["total_employees"]
		self.assertEqual(summary["average_per_employee"], expected_avg)
		
		# Top cost employees should show enhanced totals
		top_employees = summary["top_cost_employees"]
		self.assertGreater(len(top_employees), 0)
		self.assertGreater(top_employees[0]["neto_a_pagar"], 2000000)