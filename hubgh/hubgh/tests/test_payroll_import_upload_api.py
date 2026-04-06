from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.payroll_import_upload_api import create_import_batch, get_upload_form_options


class TestPayrollImportUploadApi(FrappeTestCase):
	def setUp(self):
		self.created_batches = []
		self.created_periods = []
		self.created_sources = []

	def tearDown(self):
		for batch_name in self.created_batches:
			frappe.delete_doc_if_exists("Payroll Import Batch", batch_name, force=True)
		for period_name in self.created_periods:
			frappe.delete_doc_if_exists("Payroll Period Config", period_name, force=True)
		for source_name in self.created_sources:
			frappe.delete_doc_if_exists("Payroll Source Catalog", source_name, force=True)

	def _make_source(self, suffix, status):
		doc = frappe.get_doc({
			"doctype": "Payroll Source Catalog",
			"nombre_fuente": f"TEST-UPLOAD-SOURCE-{suffix}",
			"tipo_fuente": "clonk",
			"status": status,
		})
		doc.insert(ignore_permissions=True)
		self.created_sources.append(doc.name)
		return doc

	def _make_period(self, suffix, status):
		doc = frappe.get_doc({
			"doctype": "Payroll Period Config",
			"nombre_periodo": f"Periodo Upload {suffix}",
			"ano": 2026,
			"mes": 3,
			"fecha_corte_inicio": "2026-03-01",
			"fecha_corte_fin": "2026-03-15",
			"status": status,
		})
		doc.insert(ignore_permissions=True)
		self.created_periods.append(doc.name)
		return doc

	@patch("hubgh.hubgh.payroll_import_upload_api.enforce_payroll_access")
	def test_get_upload_form_options_returns_active_catalogs(self, _mock_access):
		active_source = self._make_source("ACTIVE", "Active")
		self._make_source("INACTIVE", "Deprecated")
		active_period = self._make_period("ACTIVE", "Active")
		self._make_period("DRAFT", "Draft")

		result = get_upload_form_options()

		self.assertEqual([row["value"] for row in result["sources"]], [active_source.name])
		self.assertEqual([row["value"] for row in result["periods"]], [active_period.name])
		self.assertEqual(result["periods"][0]["label"], active_period.nombre_periodo)
		self.assertFalse(result["empty_states"]["sources"])
		self.assertFalse(result["empty_states"]["periods"])

	@patch("hubgh.hubgh.payroll_import_upload_api.enforce_payroll_access")
	def test_create_import_batch_uses_nombre_periodo(self, _mock_access):
		source = self._make_source("BATCH", "Active")
		period = self._make_period("BATCH", "Active")

		result = create_import_batch("/private/files/test-upload.xlsx", source.name, period.name)
		self.created_batches.append(result["name"])

		batch = frappe.get_doc("Payroll Import Batch", result["name"])
		self.assertEqual(batch.source_type, source.name)
		self.assertEqual(batch.period, period.name)
		self.assertEqual(batch.nomina_period, period.nombre_periodo)
