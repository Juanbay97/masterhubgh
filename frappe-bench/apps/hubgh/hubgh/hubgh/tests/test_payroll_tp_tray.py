"""
Tests for Payroll TP Tray functionality and Prenomina export.

Tests TP workflow, employee consolidation, recargo calculations, and 
Prenomina Excel generation for Sprint 4 completion.
"""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, now_datetime, add_days, flt

from hubgh.hubgh.payroll_tp_tray import (
	PayrollTPTrayService,
	get_tp_consolidation,
	approve_tp_batch,
	approve_tp_employees,
	get_available_periods
)
from hubgh.hubgh.payroll_export_prenomina import (
	PrenominaExportService,
	generate_prenomina_export,
	get_prenomina_preview
)


class TestPayrollTPTray(FrappeTestCase):
	"""Test suite for TP tray functionality and prenomina export."""
	
	def setUp(self):
		"""Set up test data."""
		self.cleanup_test_data()
		self.create_test_data()
		
	def tearDown(self):
		"""Clean up after tests."""
		self.cleanup_test_data()
		
	def cleanup_test_data(self):
		"""Remove test data."""
		frappe.db.delete("Payroll Import Line", {"batch": ["like", "TEST-TP-%"]})
		frappe.db.delete("Payroll Import Batch", {"name": ["like", "TEST-TP-%"]})
		frappe.db.delete("People Ops Event", {"source_doctype": ["in", ["Payroll Import Line", "Payroll Import Batch"]]})
		frappe.db.commit()
		
	def create_test_data(self):
		"""Create test payroll data with TC-approved status."""
		
		# Create test employee if not exists
		if not frappe.db.exists("Employee", "EMP-TP-001"):
			emp_doc = frappe.new_doc("Employee")
			emp_doc.employee_name = "Juan Pérez TP Test"
			emp_doc.employee_id = "EMP-TP-001"
			emp_doc.personal_email = "12345678"  # Document number
			emp_doc.company = "HOME BURGERS"
			emp_doc.branch = "PDV Centro"
			emp_doc.employment_type = "Full-time"
			emp_doc.insert(ignore_permissions=True)
			
		if not frappe.db.exists("Employee", "EMP-TP-002"):
			emp_doc = frappe.new_doc("Employee")
			emp_doc.employee_name = "María García TP Test"
			emp_doc.employee_id = "EMP-TP-002"
			emp_doc.personal_email = "87654321"
			emp_doc.company = "HOME BURGERS"
			emp_doc.branch = "PDV Norte"
			emp_doc.employment_type = "Part-time"
			emp_doc.insert(ignore_permissions=True)
		
		# Create test batch
		batch_doc = frappe.new_doc("Payroll Import Batch")
		batch_doc.name = "TEST-TP-BATCH-001"
		batch_doc.source_type = "CLONK"
		batch_doc.source_file = "test_clonk_file.xlsx"
		batch_doc.nomina_period = "2026-03"
		batch_doc.status = "Procesado"
		batch_doc.insert(ignore_permissions=True)
		
		# Create test import lines with TC-approved status
		test_lines = [
			{
				"employee_id": "EMP-TP-001",
				"employee_name": "Juan Pérez TP Test",
				"matched_employee": "EMP-TP-001",
				"novedad_type": "HD",
				"quantity": 160,
				"amount": 2400000,  # 160 hours * 15000/hour
				"novedad_date": "2026-03-15"
			},
			{
				"employee_id": "EMP-TP-001", 
				"employee_name": "Juan Pérez TP Test",
				"matched_employee": "EMP-TP-001",
				"novedad_type": "HN",
				"quantity": 20,
				"amount": 375000,  # 20 hours * 15000 * 1.25
				"novedad_date": "2026-03-16"
			},
			{
				"employee_id": "EMP-TP-001",
				"employee_name": "Juan Pérez TP Test", 
				"matched_employee": "EMP-TP-001",
				"novedad_type": "AUX-TRANSPORTE",
				"quantity": 1,
				"amount": 140606,
				"novedad_date": "2026-03-01"
			},
			{
				"employee_id": "EMP-TP-001",
				"employee_name": "Juan Pérez TP Test",
				"matched_employee": "EMP-TP-001", 
				"novedad_type": "DESC-SANITAS",
				"quantity": 1,
				"amount": -85000,
				"novedad_date": "2026-03-01"
			},
			{
				"employee_id": "EMP-TP-002",
				"employee_name": "María García TP Test",
				"matched_employee": "EMP-TP-002",
				"novedad_type": "HD",
				"quantity": 80,
				"amount": 1200000,
				"novedad_date": "2026-03-15"
			},
			{
				"employee_id": "EMP-TP-002",
				"employee_name": "María García TP Test",
				"matched_employee": "EMP-TP-002",
				"novedad_type": "AUX-HOME12",
				"quantity": 1,
				"amount": 110000,
				"novedad_date": "2026-03-01"
			}
		]
		
		for i, line_data in enumerate(test_lines):
			line_doc = frappe.new_doc("Payroll Import Line")
			line_doc.batch = "TEST-TP-BATCH-001"
			line_doc.row_number = i + 1
			line_doc.status = "Válido"
			line_doc.tc_status = "Aprobado"  # Key: TC-approved for TP processing
			line_doc.tp_status = "Pendiente"
			
			for field, value in line_data.items():
				setattr(line_doc, field, value)
			
			line_doc.insert(ignore_permissions=True)
		
		frappe.db.commit()
		
		# Store for test reference
		self.test_batch = "TEST-TP-BATCH-001"
		self.test_employees = ["EMP-TP-001", "EMP-TP-002"]
		
	def test_tp_service_initialization(self):
		"""Test TP tray service initialization."""
		service = PayrollTPTrayService()
		
		self.assertEqual(service.supported_statuses, ["Pendiente", "Revisado", "Aprobado", "Rechazado"])
		self.assertEqual(service.valid_tc_statuses, ["Aprobado"])
		
	def test_consolidate_by_period(self):
		"""Test period consolidation functionality."""
		service = PayrollTPTrayService()
		
		result = service.consolidate_by_period(period_filter="2026-03")
		
		self.assertEqual(result["status"], "success")
		self.assertEqual(result["total_employees"], 2)
		self.assertEqual(len(result["employee_consolidation"]), 2)
		
		# Check employee data structure
		emp_data = result["employee_consolidation"][0]
		required_fields = [
			"employee_id", "employee_name", "total_devengado", 
			"total_deducciones", "neto_a_pagar", "novelty_breakdown",
			"hour_totals", "recargos", "overall_tp_status"
		]
		for field in required_fields:
			self.assertIn(field, emp_data)
		
	def test_consolidate_by_batch(self):
		"""Test batch-specific consolidation."""
		service = PayrollTPTrayService()
		
		result = service.consolidate_by_period(batch_filter=self.test_batch)
		
		self.assertEqual(result["status"], "success")
		self.assertEqual(result["total_employees"], 2)
		
		# Verify batch filter worked
		for emp in result["employee_consolidation"]:
			self.assertIn(self.test_batch, emp["batches"])
		
	def test_employee_consolidation_with_recargos(self):
		"""Test employee consolidation with recargo calculations."""
		service = PayrollTPTrayService()
		
		# Get test lines
		lines = frappe.get_all("Payroll Import Line",
			filters={"batch": self.test_batch, "tc_status": "Aprobado"},
			fields=["*"]
		)
		
		consolidation = service.consolidate_by_employee_with_recargos(lines)
		
		# Find employee 1 (Juan Pérez) 
		emp1 = next((emp for emp in consolidation if emp["employee_id"] == "EMP-TP-001"), None)
		self.assertIsNotNone(emp1)
		
		# Check hour totals
		self.assertEqual(emp1["hour_totals"]["HD"], 160)
		self.assertEqual(emp1["hour_totals"]["HN"], 20)
		
		# Check recargo calculations
		self.assertGreater(emp1["recargos"]["nocturnal_amount"], 0)
		
		# Check financial totals
		self.assertGreater(emp1["total_devengado"], 0)
		self.assertGreater(emp1["total_deducciones"], 0)
		self.assertGreater(emp1["neto_a_pagar"], 0)
		
		# Verify math: neto = devengado - deducciones
		expected_neto = emp1["total_devengado"] - emp1["total_deducciones"]
		self.assertAlmostEqual(emp1["neto_a_pagar"], expected_neto, places=0)
		
	def test_recargo_calculations(self):
		"""Test recargo calculation logic."""
		service = PayrollTPTrayService()
		
		# Test nocturnal hours
		recargos = service.calculate_recargos("HN", 8, {"novedad_date": "2026-03-16"})
		expected_nocturnal = 8 * 15000 * 0.25  # 8 hours * base_rate * 25%
		self.assertEqual(recargos["nocturnal"], expected_nocturnal)
		
		# Test extra hours
		recargos = service.calculate_recargos("HED", 4, {"novedad_date": "2026-03-17"}) 
		expected_extra = 4 * 15000 * 0.25  # 4 hours * base_rate * 25%
		self.assertEqual(recargos["extra_hours"], expected_extra)
		
		# Test nocturnal extra hours (both recargos)
		recargos = service.calculate_recargos("HEN", 2, {"novedad_date": "2026-03-18"})
		self.assertEqual(recargos["nocturnal"], 2 * 15000 * 0.25)
		self.assertEqual(recargos["extra_hours"], 2 * 15000 * 0.50)
		
	def test_executive_summary_calculation(self):
		"""Test executive summary calculations."""
		service = PayrollTPTrayService()
		
		result = service.consolidate_by_period(batch_filter=self.test_batch)
		summary = result["executive_summary"]
		
		# Check summary structure
		required_fields = [
			"total_employees", "employees_ready_for_approval", "total_payroll_amount",
			"average_per_employee", "approval_readiness", "novelty_summary"
		]
		for field in required_fields:
			self.assertIn(field, summary)
		
		# Check calculations
		self.assertEqual(summary["total_employees"], 2)
		self.assertGreater(summary["total_payroll_amount"], 0)
		
		if summary["total_employees"] > 0:
			expected_avg = summary["total_payroll_amount"] / summary["total_employees"]
			self.assertAlmostEqual(summary["average_per_employee"], expected_avg, places=0)
		
	def test_bulk_approve_tp_employees(self):
		"""Test bulk TP approval for specific employees."""
		service = PayrollTPTrayService()
		
		# Approve one employee
		result = service.bulk_approve_tp(
			employee_ids=["EMP-TP-001"],
			comments="Test TP approval"
		)
		
		self.assertEqual(result["status"], "success")
		self.assertGreater(result["success_count"], 0)
		
		# Verify status updated
		approved_lines = frappe.get_all("Payroll Import Line", 
			filters={
				"batch": self.test_batch,
				"matched_employee": "EMP-TP-001", 
				"tp_status": "Aprobado"
			}
		)
		self.assertGreater(len(approved_lines), 0)
		
		# Check if prenomina was generated
		self.assertIn("prenomina_results", result)
		
	def test_bulk_approve_tp_batch(self):
		"""Test bulk TP approval for entire batch."""
		service = PayrollTPTrayService()
		
		result = service.bulk_approve_tp(
			batch_filter=self.test_batch,
			comments="Test batch TP approval"
		)
		
		self.assertEqual(result["status"], "success")
		self.assertGreater(result["success_count"], 0)
		
		# Verify all lines in batch are approved
		pending_lines = frappe.get_all("Payroll Import Line",
			filters={
				"batch": self.test_batch,
				"tp_status": ["!=", "Aprobado"]
			}
		)
		self.assertEqual(len(pending_lines), 0)
		
		# Check batch approval metadata
		batch_doc = frappe.get_doc("Payroll Import Batch", self.test_batch)
		self.assertIsNotNone(batch_doc.aprobado_tc_por)  # Reusing field
		
	@patch('hubgh.hubgh.payroll_publishers.publish_tp_approval_event')
	@patch('hubgh.hubgh.payroll_publishers.publish_prenomina_generation_event')
	def test_tp_approval_events(self, mock_prenomina_event, mock_tp_event):
		"""Test that TP approval publishes correct events."""
		service = PayrollTPTrayService()
		
		service.bulk_approve_tp(
			employee_ids=["EMP-TP-001"],
			comments="Event test"
		)
		
		# Verify TP approval event was published
		mock_tp_event.assert_called()
		
		# Verify prenomina generation event was published
		mock_prenomina_event.assert_called()
		
	def test_api_endpoints(self):
		"""Test TP tray API endpoints."""
		
		# Test consolidation endpoint
		result = get_tp_consolidation(batch_filter=self.test_batch)
		self.assertEqual(result["status"], "success")
		
		# Test available periods endpoint
		result = get_available_periods()
		self.assertEqual(result["status"], "success")
		self.assertIn("periods", result)
		
		# Test employee approval endpoint  
		result = approve_tp_employees(
			employee_ids=json.dumps(["EMP-TP-002"]),
			comments="API test"
		)
		self.assertEqual(result["status"], "success")
		
		# Test batch approval endpoint
		# Create another batch for this test
		batch_doc = frappe.new_doc("Payroll Import Batch")
		batch_doc.name = "TEST-TP-BATCH-002"
		batch_doc.source_type = "CLONK"
		batch_doc.nomina_period = "2026-04"
		batch_doc.insert(ignore_permissions=True)
		
		line_doc = frappe.new_doc("Payroll Import Line")
		line_doc.batch = "TEST-TP-BATCH-002"
		line_doc.employee_id = "EMP-TP-001"
		line_doc.matched_employee = "EMP-TP-001"
		line_doc.status = "Válido"
		line_doc.tc_status = "Aprobado"
		line_doc.tp_status = "Pendiente"
		line_doc.novedad_type = "HD"
		line_doc.quantity = 40
		line_doc.amount = 600000
		line_doc.insert(ignore_permissions=True)
		
		result = approve_tp_batch("TEST-TP-BATCH-002", comments="Batch API test")
		self.assertEqual(result["status"], "success")
		
		# Cleanup
		frappe.delete_doc("Payroll Import Line", line_doc.name)
		frappe.delete_doc("Payroll Import Batch", "TEST-TP-BATCH-002")


class TestPrenominaExport(FrappeTestCase):
	"""Test suite for Prenomina Excel export functionality."""
	
	def setUp(self):
		"""Set up test data for export."""
		self.cleanup_test_data()
		self.create_export_test_data()
		
	def tearDown(self):
		"""Clean up after tests."""
		self.cleanup_test_data()
		
	def cleanup_test_data(self):
		"""Remove test data."""
		frappe.db.delete("Payroll Import Line", {"batch": ["like", "TEST-EXPORT-%"]})
		frappe.db.delete("Payroll Import Batch", {"name": ["like", "TEST-EXPORT-%"]})
		frappe.db.commit()
		
	def create_export_test_data(self):
		"""Create TP-approved test data for export."""
		
		# Create test employee
		if not frappe.db.exists("Employee", "EMP-EXPORT-001"):
			emp_doc = frappe.new_doc("Employee")
			emp_doc.employee_name = "Ana Rodríguez Export Test"
			emp_doc.employee_id = "EMP-EXPORT-001"
			emp_doc.personal_email = "11223344"
			emp_doc.company = "HOME BURGERS"
			emp_doc.branch = "PDV Sur"
			emp_doc.insert(ignore_permissions=True)
		
		# Create test batch
		batch_doc = frappe.new_doc("Payroll Import Batch")
		batch_doc.name = "TEST-EXPORT-BATCH-001"
		batch_doc.source_type = "CLONK"
		batch_doc.nomina_period = "2026-03"
		batch_doc.aprobado_tc_por = "Administrator"
		batch_doc.aprobado_tc_fecha = now_datetime()
		batch_doc.insert(ignore_permissions=True)
		
		# Create comprehensive test lines (all TP-approved)
		test_lines = [
			{
				"novedad_type": "HD",
				"quantity": 160,
				"amount": 2400000
			},
			{
				"novedad_type": "HN", 
				"quantity": 12,
				"amount": 225000
			},
			{
				"novedad_type": "HED",
				"quantity": 8,
				"amount": 150000
			},
			{
				"novedad_type": "AUX-TRANSPORTE",
				"quantity": 1,
				"amount": 140606
			},
			{
				"novedad_type": "AUX-HOME12",
				"quantity": 1,
				"amount": 110000
			},
			{
				"novedad_type": "BONIFICACION",
				"quantity": 1,
				"amount": 50000
			},
			{
				"novedad_type": "DESC-SANITAS",
				"quantity": 1,
				"amount": -85000
			},
			{
				"novedad_type": "DESC-LIBRANZAS",
				"quantity": 1,
				"amount": -100000
			}
		]
		
		for i, line_data in enumerate(test_lines):
			line_doc = frappe.new_doc("Payroll Import Line")
			line_doc.batch = "TEST-EXPORT-BATCH-001"
			line_doc.row_number = i + 1
			line_doc.employee_id = "EMP-EXPORT-001"
			line_doc.employee_name = "Ana Rodríguez Export Test"
			line_doc.matched_employee = "EMP-EXPORT-001"
			line_doc.status = "Válido"
			line_doc.tc_status = "Aprobado"
			line_doc.tp_status = "Aprobado"  # Key: TP-approved for export
			line_doc.novedad_date = "2026-03-15"
			
			for field, value in line_data.items():
				setattr(line_doc, field, value)
			
			line_doc.insert(ignore_permissions=True)
		
		frappe.db.commit()
		self.test_export_batch = "TEST-EXPORT-BATCH-001"
		
	def test_prenomina_service_initialization(self):
		"""Test Prenomina export service initialization."""
		try:
			service = PrenominaExportService()
			self.assertIsNotNone(service)
			self.assertIsNotNone(service.default_values)
		except ImportError:
			self.skipTest("openpyxl not available - skipping export tests")
		
	def test_get_tp_approved_lines(self):
		"""Test retrieval of TP-approved lines."""
		try:
			service = PrenominaExportService()
			lines = service._get_tp_approved_lines(self.test_export_batch)
			
			self.assertGreater(len(lines), 0)
			
			# Verify all lines are TP-approved
			for line in lines:
				self.assertEqual(line.get("tc_status"), "Aprobado")
				self.assertEqual(line.get("tp_status"), "Aprobado")
				
		except ImportError:
			self.skipTest("openpyxl not available")
		
	def test_employee_data_consolidation(self):
		"""Test consolidation of employee data for export."""
		try:
			service = PrenominaExportService()
			lines = service._get_tp_approved_lines(self.test_export_batch)
			employee_data = service._consolidate_employee_data(lines)
			
			self.assertEqual(len(employee_data), 1)
			
			emp_record = employee_data[0]
			
			# Check required Prenomina fields
			required_fields = [
				"document_number", "employee_name", "horas_diurnas", "horas_nocturnas",
				"aux_transporte", "subsidio_home12", "total_devengado", 
				"total_deducciones", "neto_a_pagar"
			]
			for field in required_fields:
				self.assertIn(field, emp_record)
			
			# Verify hour consolidation
			self.assertEqual(emp_record["horas_diurnas"], 160)
			self.assertEqual(emp_record["horas_nocturnas"], 12)
			self.assertEqual(emp_record["horas_extras_diurnas"], 8)
			
			# Verify financial consolidation
			self.assertEqual(emp_record["aux_transporte"], 140606 + 140606)  # Default + line amount
			self.assertEqual(emp_record["subsidio_home12"], 110000)
			self.assertEqual(emp_record["desc_sanitas"], 85000)
			self.assertEqual(emp_record["desc_libranzas"], 100000)
			
			# Verify total calculations
			self.assertGreater(emp_record["total_devengado"], 0)
			self.assertGreater(emp_record["total_deducciones"], 0)
			self.assertGreater(emp_record["neto_a_pagar"], 0)
			
		except ImportError:
			self.skipTest("openpyxl not available")
		
	def test_excel_file_generation(self):
		"""Test Excel file creation."""
		try:
			service = PrenominaExportService()
			
			# Create temporary directory for test
			with tempfile.TemporaryDirectory() as temp_dir:
				result = service.generate_prenomina_export(
					self.test_export_batch,
					output_dir=temp_dir
				)
				
				self.assertEqual(result["status"], "success")
				self.assertIn("file_path", result)
				self.assertTrue(os.path.exists(result["file_path"]))
				
				# Verify file is actually an Excel file
				self.assertTrue(result["file_path"].endswith(".xlsx"))
				
				# Check summary data
				self.assertEqual(result["employee_count"], 1)
				self.assertIn("summary", result)
				
		except ImportError:
			self.skipTest("openpyxl not available")
		
	def test_prenomina_preview(self):
		"""Test Prenomina preview functionality."""
		try:
			service = PrenominaExportService()
			lines = service._get_tp_approved_lines(self.test_export_batch)
			employee_data = service._consolidate_employee_data(lines)
			
			# Test preview data structure
			self.assertGreater(len(employee_data), 0)
			
			preview_data = employee_data[:5]  # Preview limit
			self.assertEqual(len(preview_data), 1)  # Only one employee in test data
			
		except ImportError:
			self.skipTest("openpyxl not available")
		
	def test_export_api_endpoints(self):
		"""Test export API endpoints."""
		
		# Test preview endpoint
		result = get_prenomina_preview(self.test_export_batch, limit=5)
		if result.get("status") == "error" and "openpyxl" in result.get("message", ""):
			self.skipTest("openpyxl not available")
		
		self.assertEqual(result["status"], "success")
		self.assertIn("preview_data", result)
		self.assertIn("columns", result)
		
		# Test export endpoint
		result = generate_prenomina_export(self.test_export_batch)
		if result.get("status") == "error" and "openpyxl" in result.get("message", ""):
			self.skipTest("openpyxl not available")
			
		self.assertEqual(result["status"], "success")
		
	def test_column_mapping(self):
		"""Test Prenomina column mapping accuracy."""
		try:
			from hubgh.hubgh.payroll_export_prenomina import PRENOMINA_COLUMNS
			
			# Verify all expected columns are present
			expected_columns = [
				"Documento", "Nombre Empleado", "HD", "HN", "HED", "HEN",
				"Auxilio Transporte", "HOME 12", "Total Devengado", 
				"Total Deducciones", "Neto a Pagar"
			]
			
			for col in expected_columns:
				self.assertIn(col, PRENOMINA_COLUMNS)
				
		except ImportError:
			self.skipTest("openpyxl not available")


class TestTPTrayIntegration(FrappeTestCase):
	"""Integration tests for complete TP workflow."""
	
	def setUp(self):
		"""Set up integration test data."""
		self.cleanup_test_data()
		self.create_integration_test_data()
		
	def tearDown(self):
		"""Clean up after tests."""
		self.cleanup_test_data()
		
	def cleanup_test_data(self):
		"""Remove test data."""
		frappe.db.delete("Payroll Import Line", {"batch": ["like", "TEST-INTEGRATION-%"]})
		frappe.db.delete("Payroll Import Batch", {"name": ["like", "TEST-INTEGRATION-%"]})
		frappe.db.delete("People Ops Event", {"refs": ["like", "%TEST-INTEGRATION%"]})
		frappe.db.commit()
		
	def create_integration_test_data(self):
		"""Create complete test scenario."""
		
		# Create test employee
		if not frappe.db.exists("Employee", "EMP-INT-001"):
			emp_doc = frappe.new_doc("Employee")
			emp_doc.employee_name = "Carlos López Integration"
			emp_doc.employee_id = "EMP-INT-001"
			emp_doc.personal_email = "99887766"
			emp_doc.company = "HOME BURGERS" 
			emp_doc.branch = "PDV Oeste"
			emp_doc.employment_type = "Full-time"
			emp_doc.insert(ignore_permissions=True)
		
		# Create batch
		batch_doc = frappe.new_doc("Payroll Import Batch")
		batch_doc.name = "TEST-INTEGRATION-001"
		batch_doc.source_type = "CLONK"
		batch_doc.nomina_period = "2026-04"
		batch_doc.insert(ignore_permissions=True)
		
		# Create lines with TC-approved status
		line_doc = frappe.new_doc("Payroll Import Line")
		line_doc.batch = "TEST-INTEGRATION-001"
		line_doc.employee_id = "EMP-INT-001"
		line_doc.employee_name = "Carlos López Integration"
		line_doc.matched_employee = "EMP-INT-001"
		line_doc.status = "Válido"
		line_doc.tc_status = "Aprobado"
		line_doc.tp_status = "Pendiente"
		line_doc.novedad_type = "HD"
		line_doc.quantity = 100
		line_doc.amount = 1500000
		line_doc.novedad_date = "2026-04-15"
		line_doc.insert(ignore_permissions=True)
		
		frappe.db.commit()
		self.integration_batch = "TEST-INTEGRATION-001"
		
	@patch('hubgh.hubgh.payroll_publishers.publish_tp_approval_event')
	@patch('hubgh.hubgh.payroll_publishers.publish_prenomina_generation_event')
	def test_end_to_end_tp_workflow(self, mock_prenomina_event, mock_tp_event):
		"""Test complete TC → TP → Prenomina workflow."""
		
		try:
			service = PayrollTPTrayService()
			
			# Step 1: Consolidate data
			consolidation = service.consolidate_by_period(batch_filter=self.integration_batch)
			self.assertEqual(consolidation["status"], "success")
			self.assertEqual(consolidation["total_employees"], 1)
			
			# Step 2: Approve TP
			approval_result = service.bulk_approve_tp(
				batch_filter=self.integration_batch,
				comments="Integration test approval"
			)
			self.assertEqual(approval_result["status"], "success")
			
			# Step 3: Verify events published
			mock_tp_event.assert_called()
			mock_prenomina_event.assert_called()
			
			# Step 4: Verify prenomina generation
			self.assertIn("prenomina_results", approval_result)
			prenomina_results = approval_result["prenomina_results"]
			self.assertGreater(len(prenomina_results), 0)
			
			# Step 5: Verify line status updated
			updated_lines = frappe.get_all("Payroll Import Line",
				filters={
					"batch": self.integration_batch,
					"tp_status": "Aprobado"
				}
			)
			self.assertGreater(len(updated_lines), 0)
			
			# Step 6: Verify batch approval metadata
			batch_doc = frappe.get_doc("Payroll Import Batch", self.integration_batch)
			self.assertIsNotNone(batch_doc.aprobado_tc_por)
			
		except ImportError:
			self.skipTest("openpyxl not available for prenomina generation")
		
	def test_tp_filter_behavior(self):
		"""Test that only TC-approved lines are visible in TP tray."""
		service = PayrollTPTrayService()
		
		# Add a non-TC-approved line
		line_doc = frappe.new_doc("Payroll Import Line")
		line_doc.batch = self.integration_batch
		line_doc.employee_id = "EMP-INT-001"
		line_doc.matched_employee = "EMP-INT-001"
		line_doc.status = "Válido"
		line_doc.tc_status = "Pendiente"  # NOT approved
		line_doc.tp_status = "Pendiente"
		line_doc.novedad_type = "HN"
		line_doc.quantity = 10
		line_doc.amount = 150000
		line_doc.insert(ignore_permissions=True)
		
		# Query TP consolidation
		result = service.consolidate_by_period(batch_filter=self.integration_batch)
		
		# Should only show TC-approved lines
		self.assertEqual(result["status"], "success")
		emp_data = result["employee_consolidation"][0]
		
		# Should NOT include the HN line (not TC-approved)
		self.assertNotIn("HN", emp_data["novelty_breakdown"])
		
		# Cleanup
		frappe.delete_doc("Payroll Import Line", line_doc.name)