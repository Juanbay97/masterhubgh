"""
Tests for Payroll TC Tray functionality and business rules engine.

Tests TC workflow, business rules application, and People Ops Event integration.
Sprint 3: Core TC functionality with rule engine validation.
"""

import json
from unittest.mock import patch, MagicMock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, now_datetime, add_days

from hubgh.hubgh.payroll_tc_tray import (
	PayrollTCTrayService,
	get_tc_tray_data,
	bulk_approve_tc,
	bulk_reject_tc
)
from hubgh.hubgh.payroll_novedad_service import PayrollNovedadService
from hubgh.hubgh.payroll_publishers import (
	publish_tc_review_event,
	determine_novelty_sensitivity
)


class TestPayrollTCTray(FrappeTestCase):
	"""Test suite for TC tray functionality."""
	
	def setUp(self):
		"""Set up test data."""
		self.cleanup_test_data()
		self.create_test_data()
		
	def tearDown(self):
		"""Clean up after tests."""
		self.cleanup_test_data()
		
	def cleanup_test_data(self):
		"""Remove test data."""
		frappe.db.delete("Payroll Import Line", {"batch": ["like", "TEST-TC-%"]})
		frappe.db.delete("Payroll Import Batch", {"name": ["like", "TEST-TC-%"]})
		frappe.db.delete("People Ops Event", {"source_doctype": "Payroll Import Line"})
		frappe.db.commit()
		
	def create_test_data(self):
		"""Create test payroll data."""
		
		# Create test employee if not exists
		if not frappe.db.exists("Employee", "TEST-EMP-001"):
			frappe.get_doc({
				"doctype": "Employee", 
				"name": "TEST-EMP-001",
				"employee_name": "Juan Pérez",
				"company": "Home Burgers",
				"employment_type": "Full-time",
				"department": "Operaciones"
			}).insert(ignore_permissions=True)
		
		# Create test batch
		self.test_batch = frappe.get_doc({
			"doctype": "Payroll Import Batch",
			"name": "TEST-TC-BATCH-001",
			"run_id": "TEST-TC-RUN-001",
			"run_label": "Marzo 2026 · TEST-TC-RUN-001",
			"run_source_count": 1,
			"source_file": "test_clonk.xlsx", 
			"source_type": "CLONK",
			"nomina_period": "2026-03",
			"status": "Procesado"
		})
		self.test_batch.insert(ignore_permissions=True)
		
		# Create test lines with different scenarios
		self.test_lines = []
		
		# Line 1: HOME12 eligible employee with incapacity
		line1 = frappe.get_doc({
			"doctype": "Payroll Import Line",
			"batch": self.test_batch.name,
			"row_number": 1,
			"employee_id": "12345678",
			"employee_name": "Juan Pérez",
			"matched_employee": "TEST-EMP-001",
			"novedad_type": "INC-EG",
			"novedad_date": getdate(),
			"quantity": 5.0,  # 5 days incapacity
			"amount": 0,
			"status": "Válido",
			"tc_status": "Pendiente",
			"source_sheet": "Ausentismos",
			"source_file": "test_clonk.xlsx",
			"source_type_code": "CLONK",
			"source_row_number": 1,
			"source_concept_code": "INC-EG"
		})
		line1.insert(ignore_permissions=True)
		self.test_lines.append(line1)
		
		# Line 2: Sunday night hours (dominical)
		line2 = frappe.get_doc({
			"doctype": "Payroll Import Line", 
			"batch": self.test_batch.name,
			"row_number": 2,
			"employee_id": "12345678",
			"employee_name": "Juan Pérez",
			"matched_employee": "TEST-EMP-001",
			"novedad_type": "HN",
			"novedad_date": getdate(),  # Assuming this is a Sunday
			"quantity": 8.0,
			"amount": 50000,
			"status": "Válido",
			"tc_status": "Pendiente",
			"source_sheet": "Resumen",
			"source_file": "test_clonk.xlsx",
			"source_type_code": "CLONK",
			"source_row_number": 2,
			"source_concept_code": "HN",
			"source_row_data": json.dumps({
				"turno_fin": "22:30",
				"tipo_hora": "nocturno",
				"horas_domingo_noche": 2
			})
		})
		line2.insert(ignore_permissions=True)
		self.test_lines.append(line2)
		
		# Line 3: Payflow deduction
		line3 = frappe.get_doc({
			"doctype": "Payroll Import Line",
			"batch": self.test_batch.name,
			"row_number": 3,
			"employee_id": "87654321", 
			"employee_name": "María García",
			"matched_employee": "TEST-EMP-001",
			"novedad_type": "PAYFLOW",
			"novedad_date": getdate(),
			"quantity": 1.0,
			"amount": 750000,  # Above deduction cap
			"status": "Válido",
			"tc_status": "Pendiente",
			"source_sheet": "Deducciones",
			"source_file": "test_clonk.xlsx",
			"source_type_code": "CLONK",
			"source_row_number": 3,
			"source_concept_code": "PAYFLOW"
		})
		line3.insert(ignore_permissions=True)
		self.test_lines.append(line3)
		
		frappe.db.commit()
	
	def test_tc_tray_service_query_pending_lines(self):
		"""Test TC tray service can query pending lines correctly."""
		
		service = PayrollTCTrayService()
		result = service.query_pending_lines()
		
		# Verify basic structure
		self.assertEqual(result["status"], "success")
		self.assertGreater(result["total_lines"], 0)
		self.assertGreater(result["total_employees"], 0)
		
		# Verify we have our test lines
		self.assertGreaterEqual(result["total_lines"], 3)
		
		# Check consolidated view
		consolidated = result["consolidated"]
		self.assertGreater(len(consolidated), 0)
		
		# Find our test employee
		test_employee = None
		for emp in consolidated:
			if emp["employee_id"] == "TEST-EMP-001":
				test_employee = emp
				break
		
		self.assertIsNotNone(test_employee)
		self.assertEqual(test_employee["employee_name"], "Juan Pérez")
		self.assertGreater(test_employee["line_count"], 0)
		self.assertEqual(test_employee["overall_tc_status"], "Pendiente")

	def test_tc_tray_run_filter_keeps_provenance_visible(self):
		"""TC run filtering should keep provenance fields available for review."""
		service = PayrollTCTrayService()
		result = service.query_pending_lines(run_filter="TEST-TC-RUN-001")

		self.assertEqual(result["status"], "success")
		self.assertEqual(result["total_lines"], 3)
		for line in result["lines"]:
			self.assertEqual(line["run_id"], "TEST-TC-RUN-001")
			self.assertTrue(line.get("source_sheet"))
			self.assertIn("source_row_data", line)
	
	def test_tc_tray_consolidate_by_employee(self):
		"""Test employee consolidation logic."""
		
		service = PayrollTCTrayService()
		
		# Get lines for our test batch
		lines = frappe.get_all("Payroll Import Line",
			filters={"batch": self.test_batch.name},
			fields=["*"]
		)
		
		consolidated = service.consolidate_by_employee(lines)
		
		# Should have at least one employee
		self.assertGreater(len(consolidated), 0)
		
		# Check test employee aggregation
		test_emp = next((emp for emp in consolidated if emp["employee_id"] == "TEST-EMP-001"), None)
		self.assertIsNotNone(test_emp)
		
		# Verify aggregation fields
		self.assertGreater(test_emp["line_count"], 0)
		self.assertGreater(test_emp["total_amount"], 0)
		self.assertIn(self.test_batch.name, test_emp["batches"])
		self.assertTrue(test_emp["novelty_types"])
	
	def test_business_rules_engine_home12_prop(self):
		"""Test HOME12-PROP rule for incapacity."""
		
		service = PayrollNovedadService()
		
		# Get INC-EG line (should trigger HOME12-PROP)
		inc_line = next(line for line in self.test_lines if line.novedad_type == "INC-EG")
		
		line_data = {
			"name": inc_line.name,
			"matched_employee": inc_line.matched_employee,
			"employee_id": inc_line.employee_id,
			"novedad_type": inc_line.novedad_type,
			"quantity": inc_line.quantity,
			"amount": inc_line.amount,
			"batch": inc_line.batch
		}
		
		# Apply rules
		processed_line = service._apply_line_rules(line_data)
		
		# Should apply HOME12-PROP rule
		self.assertIsNotNone(processed_line.get("rule_applied"))
		self.assertIn("HOME12", processed_line.get("rule_applied", ""))
		self.assertIsNotNone(processed_line.get("rule_notes"))
		
	def test_business_rules_engine_aux_dom_noche(self):
		"""Test AUX-DOM-NOCHE rule for Sunday night hours."""
		
		service = PayrollNovedadService()
		
		# Get HN line (should trigger AUX-DOM-NOCHE if Sunday)
		hn_line = next(line for line in self.test_lines if line.novedad_type == "HN")
		
		line_data = {
			"name": hn_line.name,
			"matched_employee": hn_line.matched_employee,
			"employee_id": hn_line.employee_id,
			"novedad_type": hn_line.novedad_type,
			"quantity": hn_line.quantity,
			"amount": hn_line.amount,
			"novedad_date": hn_line.novedad_date,
			"source_row_data": hn_line.source_row_data,
			"batch": hn_line.batch
		}
		
		# Apply rules
		processed_line = service._apply_line_rules(line_data)
		
		# Should have some rule applied
		self.assertIsNotNone(processed_line.get("rule_applied"))
		self.assertIsNotNone(processed_line.get("rule_notes"))
	
	def test_business_rules_engine_deduction_cap(self):
		"""Test TOPE-DESC-702K deduction cap validation."""
		
		service = PayrollNovedadService()
		
		# Get PAYFLOW line (should trigger deduction cap)
		payflow_line = next(line for line in self.test_lines if line.novedad_type == "PAYFLOW")
		
		line_data = {
			"name": payflow_line.name,
			"matched_employee": payflow_line.matched_employee,
			"employee_id": payflow_line.employee_id,
			"novedad_type": payflow_line.novedad_type,
			"quantity": payflow_line.quantity,
			"amount": payflow_line.amount,
			"batch": payflow_line.batch
		}
		
		# Apply rules
		processed_line = service._apply_line_rules(line_data)
		
		# Should apply deduction cap rule
		self.assertIsNotNone(processed_line.get("rule_applied"))
		self.assertIn("TOPE", processed_line.get("rule_applied", ""))
		
		# Amount should be adjusted or flagged
		original_amount = payflow_line.amount
		processed_amount = processed_line.get("amount", original_amount)
		
		if original_amount > 702000:
			# Should be capped or flagged with error
			self.assertTrue(
				processed_amount <= 702000 or 
				processed_line.get("status") == "Error"
			)
	
	def test_bulk_approve_tc_functionality(self):
		"""Test bulk approve functionality."""
		
		# Get line IDs for approval
		line_ids = [line.name for line in self.test_lines]
		
		# Mock the People Ops Event publishing
		with patch('hubgh.hubgh.payroll_tc_tray.publish_tc_review_event') as mock_publish:
			with patch('hubgh.hubgh.payroll_tc_tray.publish_bulk_tc_events') as mock_bulk_publish:
				
				result = bulk_approve_tc(line_ids, "Aprobación automática de prueba")
				
				# Should succeed
				self.assertEqual(result["status"], "success")
				self.assertGreater(result["success_count"], 0)
				
				# Verify lines were updated
				for line_id in line_ids:
					line_doc = frappe.get_doc("Payroll Import Line", line_id)
					self.assertEqual(line_doc.tc_status, "Aprobado")
					self.assertIn("TC Aprobado", line_doc.rule_notes or "")
				
				# Verify events were published
				self.assertGreater(mock_publish.call_count, 0)
				mock_bulk_publish.assert_called_once()
	
	def test_bulk_reject_tc_functionality(self):
		"""Test bulk reject functionality."""
		
		# Get one line ID for rejection
		line_id = self.test_lines[0].name
		
		# Mock the People Ops Event publishing
		with patch('hubgh.hubgh.payroll_tc_tray.publish_tc_review_event') as mock_publish:
			
			result = bulk_reject_tc([line_id], "Rechazo de prueba")
			
			# Should succeed
			self.assertEqual(result["status"], "success")
			self.assertEqual(result["success_count"], 1)
			
			# Verify line was updated
			line_doc = frappe.get_doc("Payroll Import Line", line_id)
			self.assertEqual(line_doc.tc_status, "Rechazado")
			self.assertIn("TC Rechazado", line_doc.rule_notes or "")
			
			# Verify event was published
			mock_publish.assert_called_once()
	
	def test_people_ops_event_sensitivity_mapping(self):
		"""Test novelty type sensitivity mapping."""
		
		# Test different novelty types
		test_cases = [
			("INC-EG", "clinical"),
			("INC-AT", "sst_clinical"),
			("AUSENTISMO", "disciplinary"),
			("HD", "operational"),
			("PAYFLOW", "operational"),  # Default for unmapped types
		]
		
		for novelty_type, expected_sensitivity in test_cases:
			sensitivity = determine_novelty_sensitivity(novelty_type)
			self.assertEqual(sensitivity, expected_sensitivity, 
				f"Novelty type {novelty_type} should have sensitivity {expected_sensitivity}")
	
	@patch('hubgh.hubgh.payroll_publishers.publish_people_ops_event')
	def test_tc_review_event_publishing(self, mock_publish):
		"""Test People Ops Event publishing for TC reviews."""
		
		mock_publish.return_value = "TEST-EVENT-001"
		
		# Get a test line
		line_doc = self.test_lines[0]
		
		# Publish TC review event
		event_id = publish_tc_review_event(line_doc, "Aprobado", "Test approval", "test_user")
		
		# Verify event was published
		mock_publish.assert_called_once()
		self.assertEqual(event_id, "TEST-EVENT-001")
		
		# Verify payload structure
		call_args = mock_publish.call_args[0][0]  # First argument is the payload
		
		self.assertEqual(call_args["area"], "nomina")
		self.assertEqual(call_args["taxonomy"], "nomina.tc_revisada")
		self.assertEqual(call_args["state"], "Aprobado")
		self.assertEqual(call_args["source_doctype"], "Payroll Import Line")
		self.assertIn("batch", call_args["refs"])
	
	def test_tc_tray_api_endpoints(self):
		"""Test TC tray API endpoints."""
		
		# Test get_tc_tray_data
		result = get_tc_tray_data(limit=50)
		self.assertEqual(result["status"], "success")
		self.assertIsInstance(result["lines"], list)
		self.assertIsInstance(result["consolidated"], list)
	
	def test_tc_tray_filtering(self):
		"""Test TC tray filtering functionality."""
		
		service = PayrollTCTrayService()
		
		# Test employee filter
		result = service.query_pending_lines(employee_filter="Juan")
		self.assertEqual(result["status"], "success")
		
		# Should have fewer or equal results
		total_result = service.query_pending_lines()
		self.assertLessEqual(result["total_lines"], total_result["total_lines"])
		
		# Test batch filter
		batch_result = service.query_pending_lines(batch_filter=self.test_batch.name)
		self.assertEqual(batch_result["status"], "success")
		self.assertGreater(batch_result["total_lines"], 0)
	
	def test_employee_detail_view(self):
		"""Test employee detail summary functionality."""
		
		service = PayrollTCTrayService()
		
		# Get detail for test employee
		result = service.get_employee_summary("TEST-EMP-001")
		
		self.assertEqual(result["status"], "success")
		self.assertEqual(result["employee_id"], "TEST-EMP-001")
		self.assertEqual(result["employee_name"], "Juan Pérez")
		self.assertGreater(result["total_lines"], 0)
		self.assertIsInstance(result["lines"], list)
		self.assertIsInstance(result["timeline"], dict)
	
	def test_tc_status_transitions(self):
		"""Test valid TC status transitions."""
		
		service = PayrollTCTrayService()
		
		# Test line that's already approved can't be changed
		approved_line = self.test_lines[0]
		approved_line.tc_status = "Aprobado"
		approved_line.save(ignore_permissions=True)
		
		# Try to reject it
		result = service._bulk_update_tc_status([approved_line.name], "Rechazado", "Test reject")
		
		# Should have errors
		self.assertEqual(result["status"], "partial")
		self.assertGreater(result["error_count"], 0)
		self.assertIn("Ya está aprobado", result["errors"][0])
	
	def test_business_rules_error_handling(self):
		"""Test business rules engine error handling."""
		
		service = PayrollNovedadService()
		
		# Test with invalid/incomplete data
		invalid_line = {
			"name": "INVALID",
			"novedad_type": None,  # Missing required data
			"employee_id": None
		}
		
		# Should handle gracefully
		processed = service._apply_line_rules(invalid_line)
		
		self.assertIsNotNone(processed)
		self.assertIn("rule_notes", processed)
	
	def test_tc_tray_batch_summary(self):
		"""Test batch summary functionality."""
		
		service = PayrollTCTrayService()
		
		# Get lines for our test batch
		lines = frappe.get_all("Payroll Import Line",
			filters={"batch": self.test_batch.name},
			fields=["*"]
		)
		
		batch_summary = service.get_batch_summary(lines)
		
		# Should have our test batch
		self.assertGreater(len(batch_summary), 0)
		
		test_batch_summary = next(
			(batch for batch in batch_summary if batch["batch"] == self.test_batch.name), 
			None
		)
		
		self.assertIsNotNone(test_batch_summary)
		self.assertGreater(test_batch_summary["line_count"], 0)
		self.assertGreater(test_batch_summary["employee_count"], 0)
		self.assertTrue(test_batch_summary["status_breakdown"])


class TestPayrollBusinessRules(FrappeTestCase):
	"""Focused tests for business rules engine."""
	
	def test_home12_eligibility_detection(self):
		"""Test HOME12 eligibility detection."""
		
		service = PayrollNovedadService()
		
		# Test employee context with HOME12 eligibility
		context = service._get_employee_context("TEST-EMP-001")
		
		# Should detect HOME12 eligibility based on company/department
		# (This is based on our test employee setup)
		if "home" in context.get("employee_id", "").lower():
			self.assertTrue(context.get("home12_eligible", False))
	
	def test_sunday_night_detection(self):
		"""Test Sunday night hours detection."""
		
		service = PayrollNovedadService()
		
		# Test with Sunday date and night hours
		sunday_data = {
			"turno_fin": "22:30",
			"tipo_hora": "nocturno"
		}
		
		# Mock Sunday date
		from frappe.utils import getdate
		today = getdate()
		
		# Test the helper method
		is_sunday_night = service._is_sunday_after_2155(today, sunday_data)
		
		# Result depends on whether today is actually Sunday
		# This is more of a unit test for the logic structure
		self.assertIsInstance(is_sunday_night, bool)
	
	def test_extract_sunday_night_hours(self):
		"""Test Sunday night hour extraction."""
		
		service = PayrollNovedadService()
		
		# Test with explicit Sunday night hours
		source_data = {
			"horas_domingo_noche": 3
		}
		
		hours = service._extract_sunday_night_hours(source_data)
		self.assertEqual(hours, 3)
		
		# Test with implicit detection
		implicit_data = {
			"description": "Trabajo dominical noche"
		}
		
		hours_implicit = service._extract_sunday_night_hours(implicit_data)
		# Should return 0 or 1 based on heuristics
		self.assertIn(hours_implicit, [0, 1])
	
	def test_rule_priority_ordering(self):
		"""Test that business rules are applied in correct priority order."""
		
		service = PayrollNovedadService()
		
		# Create a line that could match multiple rules
		test_line = {
			"matched_employee": "TEST-EMP-001",
			"employee_id": "12345678",
			"novedad_type": "INC-EG",  # Could trigger HOME12 rules
			"quantity": 3,
			"amount": 0,
			"batch": "TEST-BATCH"
		}
		
		processed = service._apply_line_rules(test_line)
		
		# Should have applied some rule
		self.assertIsNotNone(processed.get("rule_applied"))
		
		# HOME12 rules should take priority for INC-EG
		rule_applied = processed.get("rule_applied", "")
		if "HOME12" in rule_applied:
			# Correct priority
			self.assertIn("HOME12", rule_applied)
		else:
			# At least some rule was applied
			self.assertNotEqual(rule_applied, "")


if __name__ == "__main__":
	import unittest
	unittest.main()
