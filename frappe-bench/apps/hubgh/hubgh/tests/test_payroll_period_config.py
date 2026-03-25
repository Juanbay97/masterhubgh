import frappe
from frappe.tests.utils import FrappeTestCase


class TestPayrollPeriodConfig(FrappeTestCase):
	def tearDown(self):
		frappe.delete_doc_if_exists("Payroll Period Config", "FEB-2026-Q1", force=True)
		frappe.delete_doc_if_exists("Payroll Period Config", "FEB-2026-Q2", force=True)
		frappe.delete_doc_if_exists("Payroll Period Config", "MAR-2026-Q1", force=True)

	def test_payroll_period_config_crud(self):
		"""Create, save, and delete a Payroll Period Config."""
		doc = frappe.get_doc({
			"doctype": "Payroll Period Config",
			"nombre_periodo": "FEB-2026-Q1",
			"ano": 2026,
			"mes": 2,
			"fecha_corte_inicio": "2026-02-01",
			"fecha_corte_fin": "2026-02-15",
			"status": "Active",
			"total_dias": 15,
			"dias_laborales": 11,
		})
		doc.insert()
		# doctype has no autoname, so name is auto-generated
		self.assertTrue(doc.name is not None)
		self.assertEqual(doc.mes, 2)
		self.assertEqual(doc.ano, 2026)
		self.assertEqual(doc.total_dias, 15)
		# cleanup
		frappe.delete_doc("Payroll Period Config", doc.name, force=True)
