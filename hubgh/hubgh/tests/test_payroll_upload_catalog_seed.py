import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.payroll_seed import PAYROLL_UPLOAD_SOURCE_ROWS, seed_payroll_upload_catalogs


class TestPayrollUploadCatalogSeed(FrappeTestCase):
	def tearDown(self):
		for source_row in PAYROLL_UPLOAD_SOURCE_ROWS:
			frappe.delete_doc_if_exists("Payroll Source Catalog", source_row["nombre_fuente"], force=True)
		frappe.db.delete(
			"Payroll Period Config",
			{
				"nombre_periodo": "Marzo 2026 - Quincena 2",
				"observaciones": "Periodo operativo generado para habilitar el uploader de nomina.",
			},
		)

	def test_seed_payroll_upload_catalogs_creates_active_sources_and_period(self):
		seed_payroll_upload_catalogs(reference_date="2026-03-19")

		active_sources = frappe.get_all(
			"Payroll Source Catalog",
			filters={"status": "Active"},
			fields=["name"],
		)
		self.assertGreaterEqual(len(active_sources), 1)
		self.assertTrue(frappe.db.exists("Payroll Source Catalog", "CLONK"))

		periods = frappe.get_all(
			"Payroll Period Config",
			filters={
				"nombre_periodo": "Marzo 2026 - Quincena 2",
				"status": "Active",
			},
			fields=["name", "fecha_corte_inicio", "fecha_corte_fin"],
		)
		self.assertEqual(len(periods), 1)
		self.assertEqual(str(periods[0].fecha_corte_inicio), "2026-03-16")
		self.assertEqual(str(periods[0].fecha_corte_fin), "2026-03-31")

	def test_seed_payroll_upload_catalogs_is_idempotent_for_same_period(self):
		seed_payroll_upload_catalogs(reference_date="2026-03-19")
		seed_payroll_upload_catalogs(reference_date="2026-03-19")

		periods = frappe.get_all(
			"Payroll Period Config",
			filters={
				"nombre_periodo": "Marzo 2026 - Quincena 2",
				"status": "Active",
			},
			fields=["name"],
		)
		self.assertEqual(len(periods), 1)
