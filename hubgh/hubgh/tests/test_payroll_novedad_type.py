import frappe
from frappe.tests.utils import FrappeTestCase


class TestPayrollNovedadType(FrappeTestCase):
	def tearDown(self):
		frappe.delete_doc_if_exists("Payroll Novedad Type", "TEST-AUS-001", force=True)
		frappe.delete_doc_if_exists("Payroll Novedad Type", "TEST-AUS-002", force=True)

	def test_payroll_novedad_type_crud(self):
		"""Create, save, and delete a Payroll Novedad Type."""
		doc = frappe.get_doc({
			"doctype": "Payroll Novedad Type",
			"codigo": "TEST-AUS-001",
			"novedad_type": "Test Ausentismo",
			"descripcion": "Tipo de prueba para ausentismo",
			"requiere_soporte": 1,
			"sensitivity": "operational",
			"status": "Active",
		})
		doc.insert()
		self.assertTrue(frappe.db.exists("Payroll Novedad Type", "TEST-AUS-001"))
		self.assertEqual(doc.novedad_type, "Test Ausentismo")
		self.assertEqual(doc.codigo, "TEST-AUS-001")

	def test_payroll_novedad_type_code_uniqueness(self):
		"""Creating two types with same codigo should raise DuplicateEntryError."""
		frappe.get_doc({
			"doctype": "Payroll Novedad Type",
			"codigo": "TEST-AUS-002",
			"novedad_type": "First Type",
			"sensitivity": "operational",
			"status": "Active",
		}).insert()
		self.assertRaises(
			frappe.DuplicateEntryError,
			lambda: frappe.get_doc({
				"doctype": "Payroll Novedad Type",
				"codigo": "TEST-AUS-002",  # duplicate codigo
				"novedad_type": "Duplicate Type",
				"sensitivity": "operational",
				"status": "Active",
			}).insert(),
		)
