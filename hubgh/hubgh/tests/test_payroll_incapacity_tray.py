from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.payroll_incapacity_tray import PayrollIncapacityTrayService


class TestPayrollIncapacityTray(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self.service = PayrollIncapacityTrayService()

	def test_prefers_main_evidence_field_for_download(self):
		row = {
			"name": "NOV-INC-0001",
			"empleado": "EMP-0001",
			"nombres": "Ana",
			"apellidos": "Pérez",
			"cedula": "123",
			"fecha_inicio": "2026-04-01",
			"fecha_fin": "2026-04-03",
			"dias_incapacidad": 3,
			"evidencia_incapacidad": "/private/files/incapacidad-principal.pdf",
		}

		item = self.service._serialize_row(row)

		self.assertEqual(item["persona"], "Ana Pérez")
		self.assertEqual(item["dias_incapacidad"], 3)
		self.assertEqual(item["evidence_url"], "/private/files/incapacidad-principal.pdf")
		self.assertEqual(item["evidence_source"], "Novedad SST.evidencia_incapacidad")

	@patch("hubgh.hubgh.payroll_incapacity_tray.frappe.get_all")
	@patch("hubgh.hubgh.payroll_incapacity_tray.frappe.db.sql")
	def test_falls_back_to_prorroga_attachment_when_main_evidence_is_missing(self, mock_sql, mock_get_all):
		mock_sql.return_value = [{"adjunto": "/private/files/prorroga-1.pdf", "fecha_seguimiento": "2026-04-08 10:00:00"}]
		mock_get_all.return_value = []

		item = self.service._serialize_row({
			"name": "NOV-INC-0002",
			"empleado": "EMP-0002",
			"nombres": "Luis",
			"apellidos": "Gómez",
			"cedula": "456",
			"fecha_inicio": "2026-04-01",
			"fecha_fin": "2026-04-10",
			"dias_incapacidad": 0,
			"evidencia_incapacidad": None,
		})

		self.assertEqual(item["dias_incapacidad"], 10)
		self.assertEqual(item["evidence_url"], "/private/files/prorroga-1.pdf")
		self.assertEqual(item["evidence_source"], "Novedad SST.prorrogas_incapacidad[].adjunto")

	@patch.object(PayrollIncapacityTrayService, "_query_rows")
	@patch.object(PayrollIncapacityTrayService, "_resolve_evidence")
	def test_get_tray_data_builds_summary_and_attachment_policy(self, mock_resolve_evidence, mock_query_rows):
		mock_query_rows.return_value = [
			{
				"name": "NOV-1",
				"empleado": "EMP-1",
				"nombres": "Ana",
				"apellidos": "Pérez",
				"cedula": "123",
				"fecha_inicio": "2026-04-01",
				"fecha_fin": "2026-04-03",
				"dias_incapacidad": 3,
			},
			{
				"name": "NOV-2",
				"empleado": "EMP-2",
				"nombres": "Lina",
				"apellidos": "Suárez",
				"cedula": "456",
				"fecha_inicio": "2026-04-02",
				"fecha_fin": "2026-04-06",
				"dias_incapacidad": 5,
			},
		]
		mock_resolve_evidence.side_effect = [
			{"file_url": "/private/files/a.pdf", "label": "a.pdf", "source": "Novedad SST.evidencia_incapacidad"},
			{"file_url": None, "label": None, "source": None},
		]

		result = self.service.get_tray_data(search="123", status="Abierta", limit=50)

		self.assertEqual(result["status"], "success")
		self.assertEqual(result["summary"]["total"], 2)
		self.assertEqual(result["summary"]["with_evidence"], 1)
		self.assertEqual(result["summary"]["without_evidence"], 1)
		self.assertEqual(result["attachment_policy"]["canonical_source"], "Novedad SST.evidencia_incapacidad")
