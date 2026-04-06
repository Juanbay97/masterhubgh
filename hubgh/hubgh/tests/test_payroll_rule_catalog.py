import frappe
import json
from frappe.tests.utils import FrappeTestCase


class TestPayrollRuleCatalog(FrappeTestCase):
	def tearDown(self):
		frappe.delete_doc_if_exists("Payroll Rule Catalog", "HOME-12-001", force=True)

	def test_payroll_rule_catalog_crud(self):
		"""Create, save, and delete a Payroll Rule Catalog."""
		doc = frappe.get_doc({
			"doctype": "Payroll Rule Catalog",
			"codigo_regla": "HOME-12-001",
			"nombre_regla": "HOME 12 Fijo",
			"descripcion_regla": "Auxilio fijo $110K para HOME 12 con 6 PDV",
			"tipo_regla": "home12_fijo",
			"parametros": '{"amount": 110000, "pdv_count": 6, "applies_to": "empleado"}',
			"aplica_a": "empleado",
			"activa": 1,
		})
		doc.insert()
		self.assertTrue(frappe.db.exists("Payroll Rule Catalog", "HOME-12-001"))
		self.assertEqual(doc.tipo_regla, "home12_fijo")
		self.assertEqual(doc.activa, 1)

	def test_payroll_rule_catalog_json_config(self):
		"""Rule with JSON config for HOME 12 should parse parameters correctly."""
		doc = frappe.get_doc({
			"doctype": "Payroll Rule Catalog",
			"codigo_regla": "HOME-12-001",
			"nombre_regla": "HOME 12 Proporcional",
			"descripcion_regla": "Auxilio proporcional para HOME 12 con incapacidad",
			"tipo_regla": "home12_proporcional",
			"parametros": json.dumps({
				"amount": 110000,
				"pdv_count": 6,
				"applies_to": "empleado",
				"proportional_on": "incapacidad",
			}),
			"aplica_a": "empleado",
			"activa": 1,
		})
		doc.insert()
		params = json.loads(doc.parametros)
		self.assertEqual(params["amount"], 110000)
		self.assertEqual(params["proportional_on"], "incapacidad")
