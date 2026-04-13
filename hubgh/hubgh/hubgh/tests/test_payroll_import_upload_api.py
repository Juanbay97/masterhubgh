import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hubgh.hubgh import payroll_import_upload_api as upload_api


class TestPayrollImportUploadAPI(unittest.TestCase):
	"""Best-effort unit coverage for grouped upload API orchestration."""

	@patch("hubgh.hubgh.payroll_import_upload_api.enforce_payroll_access")
	@patch("hubgh.hubgh.payroll_import_upload_api._validate_source_and_period")
	@patch("hubgh.hubgh.payroll_import_upload_api._make_run_id")
	@patch("hubgh.hubgh.payroll_import_upload_api.frappe.get_doc")
	def test_create_import_run_creates_one_run_with_many_batches(
		self, mock_get_doc, mock_make_run_id, mock_validate, mock_enforce
	):
		period_doc = SimpleNamespace(name="PER-2026-03", nombre_periodo="Marzo 2026")
		period_doc.as_dict = lambda: {"name": "PER-2026-03", "nombre_periodo": "Marzo 2026"}
		mock_validate.return_value = period_doc
		mock_make_run_id.return_value = "RUN-TEST-001"

		created_batches = []

		def _build_batch(payload):
			batch = SimpleNamespace(**payload)
			batch.name = f"BATCH-{len(created_batches) + 1:03d}"
			batch.insert = MagicMock()
			created_batches.append(batch)
			return batch

		mock_get_doc.side_effect = _build_batch

		result = upload_api.create_import_run(
			'["/files/a.xlsx", "/files/b.xlsx"]',
			"CLONK",
			"PER-2026-03",
		)

		self.assertEqual(result["run_id"], "RUN-TEST-001")
		self.assertEqual(result["source_count"], 2)
		self.assertEqual(len(result["batches"]), 2)
		self.assertEqual({batch.run_id for batch in created_batches}, {"RUN-TEST-001"})
		self.assertEqual({batch.run_source_count for batch in created_batches}, {2})
		self.assertEqual({batch.nomina_period for batch in created_batches}, {"Marzo 2026"})

	@patch("hubgh.hubgh.payroll_import_upload_api.enforce_payroll_access")
	@patch("hubgh.hubgh.payroll_import_upload_api._get_run_batches")
	@patch("hubgh.hubgh.payroll_import_upload_api.frappe.db.set_value")
	def test_confirm_import_run_updates_all_batches(self, mock_set_value, mock_get_run_batches, mock_enforce):
		mock_get_run_batches.return_value = [
			{"name": "BATCH-001", "status": "Completado"},
			{"name": "BATCH-002", "status": "Completado con duplicados"},
		]

		result = upload_api.confirm_import_run("RUN-TEST-001")

		self.assertEqual(result, {"run_id": "RUN-TEST-001", "status": "Confirmado", "batch_count": 2})
		self.assertEqual(mock_set_value.call_count, 2)

	@patch("hubgh.hubgh.payroll_import_upload_api.enforce_payroll_access")
	@patch("hubgh.hubgh.payroll_import_upload_api._get_run_batches")
	@patch("hubgh.hubgh.payroll_import_upload_api.frappe.throw", side_effect=RuntimeError("blocked"))
	def test_confirm_import_run_rejects_failed_batches(self, mock_throw, mock_get_run_batches, mock_enforce):
		mock_get_run_batches.return_value = [{"name": "BATCH-001", "status": "Fuente no soportada"}]

		with self.assertRaisesRegex(RuntimeError, "blocked"):
			upload_api.confirm_import_run("RUN-TEST-001")

		mock_throw.assert_called_once()

	@patch("hubgh.hubgh.payroll_import_upload_api.enforce_payroll_access")
	@patch("hubgh.hubgh.payroll_import_upload_api.frappe.get_all")
	def test_get_import_preview_lines_supports_run_scope(self, mock_get_all, mock_enforce):
		mock_get_all.return_value = [{"run_id": "RUN-TEST-001", "batch": "BATCH-001", "row_number": 1}]

		result = upload_api.get_import_preview_lines(run_id="RUN-TEST-001", limit_page_length=50)

		self.assertEqual(result[0]["run_id"], "RUN-TEST-001")
		self.assertEqual(mock_get_all.call_args.kwargs["filters"], {"run_id": "RUN-TEST-001"})

	@patch("hubgh.hubgh.payroll_import_upload_api.enforce_payroll_access")
	@patch("hubgh.hubgh.payroll_import_upload_api._get_run_batches")
	@patch("hubgh.hubgh.payroll_import_upload_api.frappe.delete_doc")
	def test_delete_import_run_cancels_every_batch(self, mock_delete_doc, mock_get_run_batches, mock_enforce):
		mock_get_run_batches.return_value = [
			{"name": "BATCH-001", "status": "Pendiente"},
			{"name": "BATCH-002", "status": "Completado"},
		]

		result = upload_api.delete_import_run("RUN-TEST-001")

		self.assertEqual(result, {"run_id": "RUN-TEST-001", "deleted": True, "batch_count": 2})
		self.assertEqual(mock_delete_doc.call_count, 2)


if __name__ == "__main__":
	unittest.main()
