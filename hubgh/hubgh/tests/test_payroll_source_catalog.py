import frappe
from frappe.tests.utils import FrappeTestCase


class TestPayrollSourceCatalog(FrappeTestCase):
	def tearDown(self):
		frappe.delete_doc_if_exists("Payroll Source Catalog", "TEST-CLONK", force=True)
		frappe.delete_doc_if_exists("Payroll Source Catalog", "TEST-PAYFLOW", force=True)

	def test_payroll_source_catalog_crud(self):
		"""Create, save, and delete a Payroll Source Catalog."""
		doc = frappe.get_doc({
			"doctype": "Payroll Source Catalog",
			"nombre_fuente": "TEST-CLONK",
			"tipo_fuente": "clonk",
			"hoja_principal": "Resumen horas",
			"periodicidad": "Quincenal",
			"status": "Active",
			"notas": "Fuente de prueba para CLONK",
		})
		doc.insert()
		self.assertTrue(frappe.db.exists("Payroll Source Catalog", "TEST-CLONK"))
		self.assertEqual(doc.tipo_fuente, "clonk")
		self.assertEqual(doc.nombre_fuente, "TEST-CLONK")

	def test_payroll_source_catalog_tipo_fuente_required(self):
		"""tipo_fuente is required in schema, verify insertion works with it."""
		doc = frappe.get_doc({
			"doctype": "Payroll Source Catalog",
			"nombre_fuente": "TEST-PAYFLOW",
			"tipo_fuente": "payflow",
			"periodicidad": "Quincenal",
			"status": "Active",
		})
		doc.insert()
		self.assertTrue(frappe.db.exists("Payroll Source Catalog", "TEST-PAYFLOW"))
		self.assertEqual(doc.tipo_fuente, "payflow")
