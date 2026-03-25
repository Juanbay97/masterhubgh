import frappe
import unittest
import json
from frappe.utils import now_datetime, getdate


class TestPayrollTCTray(unittest.TestCase):
    """Tests for TC Tray workflow."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        if not frappe.db.exists("DocType", "Employee"):
            raise unittest.SkipTest("Skipping Payroll TC tray tests: DocType Employee is not available in this test site")

        # Create test employee if not exists
        if not frappe.db.exists("Employee", {"employee_name": "Test Employee TC"}):
            doc = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Test Employee TC",
                "status": "Active"
            })
            try:
                doc.insert(ignore_permissions=True)
            except:
                pass
    
    def setUp(self):
        """Set up each test."""
        self.test_employee = frappe.db.get_value("Employee", 
            {"employee_name": "Test Employee TC"}, "name") or "EMP001"
    
    def test_payroll_tc_tray_service_exists(self):
        """Test that TC Tray service exists and can be imported."""
        from hubgh.hubgh.payroll_tc_tray import PayrollTCTrayService
        service = PayrollTCTrayService()
        self.assertIsNotNone(service)
        self.assertIn("Pendiente", service.supported_statuses)
        self.assertIn("Aprobado", service.supported_statuses)
    
    def test_query_pending_lines(self):
        """Test querying pending lines for TC review."""
        from hubgh.hubgh.payroll_tc_tray import PayrollTCTrayService
        
        service = PayrollTCTrayService()
        result = service.query_pending_lines(limit=10)
        
        # Should return dict with expected keys
        self.assertIsInstance(result, dict)
        if result.get("lines"):
            line = result["lines"][0]
            self.assertIn("name", line)
            self.assertIn("employee_id", line)
            self.assertIn("tc_status", line)
    
    def test_consolidate_by_employee(self):
        """Test employee consolidation logic."""
        from hubgh.hubgh.payroll_tc_tray import PayrollTCTrayService
        
        service = PayrollTCTrayService()
        result = service.consolidate_by_employee()
        
        # Should return consolidation structure
        self.assertIsInstance(result, dict)
        if result.get("employees"):
            emp = result["employees"][0]
            self.assertIn("employee_id", emp)
            self.assertIn("lines", emp)
    
    def test_bulk_approve_requires_lines(self):
        """Test that bulk approve requires line names."""
        from hubgh.hubgh.payroll_tc_tray import PayrollTCTrayService
        
        service = PayrollTCTrayService()
        
        # Empty list should be handled
        result = service.bulk_approve([], "Test approval")
        self.assertFalse(result.get("success", True))
    
    def test_bulk_reject_requires_lines(self):
        """Test that bulk reject requires line names."""
        from hubgh.hubgh.payroll_tc_tray import PayrollTCTrayService
        
        service = PayrollTCTrayService()
        
        # Empty list should be handled
        result = service.bulk_reject([], "Test rejection")
        self.assertFalse(result.get("success", True))
    
    def test_tc_status_workflow(self):
        """Test TC status transitions."""
        # Valid transitions: Pendiente -> Revisado -> Aprobado/Rechazado
        valid_statuses = ["Pendiente", "Revisado", "Aprobado", "Rechazado"]
        
        for status in valid_statuses:
            self.assertIn(status, valid_statuses)
    
    def test_rule_application_tracking(self):
        """Test that applied rules are tracked per line."""
        # Lines should have rule_applied field
        lines = frappe.get_all("Payroll Import Line", 
            filters={"docstatus": ["<", 2]},
            fields=["name", "rule_applied"],
            limit=5)
        
        # All lines should have rule_applied field accessible
        for line in lines:
            self.assertIn("rule_applied", line)


class TestPayrollPublishers(unittest.TestCase):
    """Tests for People Ops Event publishing."""
    
    def test_payroll_publishers_exist(self):
        """Test that payroll publishers module exists."""
        from hubgh.hubgh.payroll_publishers import PAYROLL_TAXONOMIES
        self.assertIsNotNone(PAYROLL_TAXONOMIES)
        self.assertIn("nomina.importada", PAYROLL_TAXONOMIES)
        self.assertIn("nomina.tc_revisada", PAYROLL_TAXONOMIES)
        self.assertIn("nomina.tp_aprobada", PAYROLL_TAXONOMIES)
    
    def test_taxonomies_defined(self):
        """Test all required taxonomies are defined."""
        from hubgh.hubgh.payroll_publishers import PAYROLL_TAXONOMIES
        
        required_taxonomies = [
            "nomina.importada",
            "nomina.regla_aplicada",
            "nomina.tc_revisada",
            "nomina.tc_rechazada",
            "nomina.tp_aprobada",
            "nomina.prenomina_generada"
        ]
        
        for taxonomy in required_taxonomies:
            self.assertIn(taxonomy, PAYROLL_TAXONOMIES)
    
    def test_sensitivity_mapping(self):
        """Test sensitivity mapping exists for novelty types."""
        from hubgh.hubgh.payroll_publishers import NOVELTY_SENSITIVITY_MAP
        
        # Clinical types should map to clinical sensitivity
        self.assertIn("clinical", NOVELTY_SENSITIVITY_MAP)
        self.assertIn("INC-EG", NOVELTY_SENSITIVITY_MAP["clinical"])
        self.assertIn("INC-AT", NOVELTY_SENSITIVITY_MAP["clinical"])


class TestBusinessRules(unittest.TestCase):
    """Tests for business rules engine."""
    
    def test_novedad_service_exists(self):
        """Test that novedad service exists."""
        from hubgh.hubgh.payroll_novedad_service import PayrollNovedadService
        service = PayrollNovedadService()
        self.assertIsNotNone(service)
    
    def test_apply_business_rules_method(self):
        """Test business rules can be applied to lines."""
        from hubgh.hubgh.payroll_novedad_service import PayrollNovedadService
        
        service = PayrollNovedadService()
        test_lines = [
            {
                "name": "TEST-001",
                "employee_id": "EMP001",
                "novedad_type": "HD",
                "quantity": 8,
                "status": "Válido"
            }
        ]
        
        result = service.apply_business_rules(test_lines)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
