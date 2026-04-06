import unittest
import frappe
from unittest.mock import patch
from hubgh.hubgh.payroll_permissions import (
	validate_payroll_access,
	get_user_payroll_permissions,
	can_user_access_tc_tray,
	can_user_access_tp_tray,
	can_user_access_import_batches,
	can_user_access_liquidation_cases,
	can_user_view_employee_payroll,
	PAYROLL_ROLE_MATRIX
)


class TestPayrollPermissions(unittest.TestCase):
	"""Test payroll permissions and access control."""

	def setUp(self):
		"""Set up test environment."""
		self.test_users = {
			"nomina_user": "test.nomina@example.com",
			"rrll_user": "test.rrll@example.com",
			"sst_user": "test.sst@example.com",
			"contabilidad_user": "test.contabilidad@example.com",
			"admin_user": "Administrator",
			"regular_user": "test.regular@example.com"
		}

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('frappe.get_roles')
	def test_operativo_nomina_permissions(self, mock_get_roles, mock_feature_flag):
		"""Test that Operativo Nómina users have full TC/TP access."""
		mock_feature_flag.return_value = True
		mock_get_roles.return_value = ["Operativo Nómina", "Gestión Humana"]
		
		user = self.test_users["nomina_user"]
		permissions = get_user_payroll_permissions(user)
		
		# Should have full access to TC/TP operations
		self.assertEqual(permissions.get("tc_tray"), "full")
		self.assertEqual(permissions.get("tp_tray"), "full")
		self.assertEqual(permissions.get("import_batches"), "full")
		self.assertEqual(permissions.get("employee_payroll_data"), "read")

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('frappe.get_roles')
	def test_sensible_rrll_permissions(self, mock_get_roles, mock_feature_flag):
		"""Test that RRLL users have absence validation access only."""
		mock_feature_flag.return_value = True
		mock_get_roles.return_value = ["RRLL", "Relaciones Laborales"]
		
		user = self.test_users["rrll_user"]
		permissions = get_user_payroll_permissions(user)
		
		# Should have access to absence validation and disciplinary review
		self.assertEqual(permissions.get("absence_validation"), "full")
		self.assertEqual(permissions.get("disciplinary_review"), "full")
		self.assertEqual(permissions.get("liquidation_cases"), "validate")
		self.assertEqual(permissions.get("employee_payroll_data"), "sensitive_only")

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('frappe.get_roles')
	def test_clinico_sst_permissions(self, mock_get_roles, mock_feature_flag):
		"""Test that SST users have incapacity support access only."""
		mock_feature_flag.return_value = True
		mock_get_roles.return_value = ["SST", "Salud y Seguridad"]
		
		user = self.test_users["sst_user"]
		permissions = get_user_payroll_permissions(user)
		
		# Should have medical/incapacity related access
		self.assertEqual(permissions.get("incapacity_support"), "full")
		self.assertEqual(permissions.get("medical_documents"), "full")
		self.assertEqual(permissions.get("absence_validation"), "medical_only")
		self.assertEqual(permissions.get("employee_payroll_data"), "medical_only")

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('frappe.get_roles')
	def test_validacion_contabilidad_permissions(self, mock_get_roles, mock_feature_flag):
		"""Test that Contabilidad users have liquidation validation access."""
		mock_feature_flag.return_value = True
		mock_get_roles.return_value = ["Contabilidad", "Contador"]
		
		user = self.test_users["contabilidad_user"]
		permissions = get_user_payroll_permissions(user)
		
		# Should have financial validation access
		self.assertEqual(permissions.get("liquidation_cases"), "validate")
		self.assertEqual(permissions.get("financial_review"), "full")
		self.assertEqual(permissions.get("payroll_exports"), "read")
		self.assertEqual(permissions.get("employee_payroll_data"), "financial_only")

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	def test_administrator_permissions(self, mock_feature_flag):
		"""Test that Administrator has full access to everything."""
		mock_feature_flag.return_value = True
		
		user = self.test_users["admin_user"]
		permissions = get_user_payroll_permissions(user)
		
		# Administrator should have full access to everything
		self.assertEqual(permissions.get("all_operations"), "full")
		self.assertEqual(permissions.get("payroll_configuration"), "full")
		self.assertEqual(permissions.get("user_management"), "full")
		self.assertEqual(permissions.get("system_flags"), "full")

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('frappe.get_roles')
	def test_feature_flag_disabled(self, mock_get_roles, mock_feature_flag):
		"""Test that all access is blocked when feature flag is disabled."""
		mock_feature_flag.return_value = False
		mock_get_roles.return_value = ["Operativo Nómina", "Gestión Humana"]
		
		user = self.test_users["nomina_user"]
		
		# All operations should be denied when feature flag is off
		tc_result = validate_payroll_access("tc_tray", user=user)
		tp_result = validate_payroll_access("tp_tray", user=user)
		import_result = validate_payroll_access("import_batches", user=user)
		
		self.assertFalse(tc_result["allowed"])
		self.assertFalse(tp_result["allowed"])
		self.assertFalse(import_result["allowed"])
		self.assertEqual(tc_result["reason"], "Payroll module is disabled")

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('frappe.get_roles')
	def test_no_permissions_for_regular_user(self, mock_get_roles, mock_feature_flag):
		"""Test that regular users without payroll roles have no access."""
		mock_feature_flag.return_value = True
		mock_get_roles.return_value = ["Empleado"]  # Regular employee role only
		
		user = self.test_users["regular_user"]
		
		# Regular user should have no payroll access
		tc_result = validate_payroll_access("tc_tray", user=user)
		tp_result = validate_payroll_access("tp_tray", user=user)
		import_result = validate_payroll_access("import_batches", user=user)
		
		self.assertFalse(tc_result["allowed"])
		self.assertFalse(tp_result["allowed"])
		self.assertFalse(import_result["allowed"])

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('frappe.get_roles')
	def test_tc_tray_access(self, mock_get_roles, mock_feature_flag):
		"""Test TC tray access function."""
		mock_feature_flag.return_value = True
		
		# Test with nomina user
		mock_get_roles.return_value = ["Operativo Nómina"]
		self.assertTrue(can_user_access_tc_tray(self.test_users["nomina_user"]))
		
		# Test with regular user
		mock_get_roles.return_value = ["Empleado"]
		self.assertFalse(can_user_access_tc_tray(self.test_users["regular_user"]))

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('frappe.get_roles')
	def test_tp_tray_access(self, mock_get_roles, mock_feature_flag):
		"""Test TP tray access function."""
		mock_feature_flag.return_value = True
		
		# Test with nomina user
		mock_get_roles.return_value = ["Gestión Humana"]
		self.assertTrue(can_user_access_tp_tray(self.test_users["nomina_user"]))
		
		# Test with regular user
		mock_get_roles.return_value = ["Empleado"]
		self.assertFalse(can_user_access_tp_tray(self.test_users["regular_user"]))

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('frappe.get_roles')
	def test_import_batches_access(self, mock_get_roles, mock_feature_flag):
		"""Test import batches access function."""
		mock_feature_flag.return_value = True
		
		# Test with nomina user
		mock_get_roles.return_value = ["Operativo Nómina"]
		self.assertTrue(can_user_access_import_batches(self.test_users["nomina_user"]))
		
		# Test with SST user (should not have import access)
		mock_get_roles.return_value = ["SST"]
		self.assertFalse(can_user_access_import_batches(self.test_users["sst_user"]))

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('frappe.get_roles')
	def test_liquidation_cases_access(self, mock_get_roles, mock_feature_flag):
		"""Test liquidation cases access function."""
		mock_feature_flag.return_value = True
		
		# Test with contabilidad user
		mock_get_roles.return_value = ["Contabilidad"]
		self.assertTrue(can_user_access_liquidation_cases(self.test_users["contabilidad_user"]))
		
		# Test with RRLL user
		mock_get_roles.return_value = ["RRLL"]
		self.assertTrue(can_user_access_liquidation_cases(self.test_users["rrll_user"]))
		
		# Test with regular user
		mock_get_roles.return_value = ["Empleado"]
		self.assertFalse(can_user_access_liquidation_cases(self.test_users["regular_user"]))

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('hubgh.hubgh.role_matrix.user_has_any_role')
	def test_employee_payroll_view_contextual_access(self, mock_user_has_role, mock_feature_flag):
		"""Test contextual access to employee payroll data."""
		mock_feature_flag.return_value = True
		
		employee_id = "EMP-001"
		
		# Test RRLL user with sensitive access
		mock_user_has_role.return_value = True  # Has RRLL role
		result = can_user_view_employee_payroll(employee_id, self.test_users["rrll_user"])
		self.assertTrue(result)
		
		# Test regular user without context
		mock_user_has_role.return_value = False
		result = can_user_view_employee_payroll(employee_id, self.test_users["regular_user"])
		self.assertFalse(result)

	def test_role_matrix_completeness(self):
		"""Test that all required roles are defined in the matrix."""
		required_dimensions = [
			"operativo_nomina", "sensible_rrll", "clinico_sst", 
			"validacion_contabilidad", "administracion"
		]
		
		for dimension in required_dimensions:
			self.assertIn(dimension, PAYROLL_ROLE_MATRIX)
			self.assertIn("roles", PAYROLL_ROLE_MATRIX[dimension])
			self.assertIn("access", PAYROLL_ROLE_MATRIX[dimension])
			self.assertIn("description", PAYROLL_ROLE_MATRIX[dimension])

	@patch('hubgh.hubgh.payroll_permissions._check_payroll_feature_flag')
	@patch('frappe.get_roles')
	def test_access_level_hierarchy(self, mock_get_roles, mock_feature_flag):
		"""Test that access levels work correctly (full > validate > read)."""
		mock_feature_flag.return_value = True
		
		# Test full access (nomina user)
		mock_get_roles.return_value = ["Operativo Nómina"]
		result = validate_payroll_access("tc_tray", user=self.test_users["nomina_user"])
		self.assertTrue(result["allowed"])
		self.assertEqual(result["level"], "full")
		
		# Test validate access (contabilidad user for liquidations)
		mock_get_roles.return_value = ["Contabilidad"]
		result = validate_payroll_access("liquidation_cases", user=self.test_users["contabilidad_user"])
		self.assertTrue(result["allowed"])
		self.assertEqual(result["level"], "validate")


if __name__ == '__main__':
	unittest.main()