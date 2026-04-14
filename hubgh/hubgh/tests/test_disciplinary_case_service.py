from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh import disciplinary_case_service


class TestDisciplinaryCaseService(FrappeTestCase):
	def test_sync_disciplinary_case_effects_uses_retirement_service_for_termination(self):
		case_doc = SimpleNamespace(
			name="DIS-001",
			empleado="EMP-001",
			estado="Cerrado",
			decision_final="Terminación",
			fecha_cierre="2026-04-13",
			fecha_incidente="2026-04-10",
			resumen_cierre="Incumplimiento grave",
		)

		with patch(
			"hubgh.hubgh.disciplinary_case_service._clear_disciplinary_suspension_if_possible",
			return_value={"status": "noop"},
		), patch(
			"hubgh.hubgh.disciplinary_case_service.employee_retirement_service.submit_employee_retirement",
			return_value={"status": "retired"},
		) as retirement_mock:
			result = disciplinary_case_service.sync_disciplinary_case_effects(case_doc)

		self.assertEqual(result["status"], "retired")
		self.assertEqual(retirement_mock.call_args.kwargs["source_doctype"], "Caso Disciplinario")
		self.assertEqual(retirement_mock.call_args.kwargs["source_name"], "DIS-001")

	def test_sync_disciplinary_case_effects_applies_active_suspension_state(self):
		case_doc = SimpleNamespace(
			name="DIS-002",
			empleado="EMP-001",
			estado="Cerrado",
			decision_final="Suspensión",
			fecha_inicio_suspension="2026-04-10",
			fecha_fin_suspension="2026-04-20",
		)

		with patch("hubgh.hubgh.disciplinary_case_service.nowdate", return_value="2026-04-13"), patch(
			"hubgh.hubgh.disciplinary_case_service.reverse_retirement_if_clear",
		), patch(
			"hubgh.hubgh.disciplinary_case_service.frappe.db.get_value",
			return_value="Activo",
		), patch(
			"hubgh.hubgh.disciplinary_case_service.frappe.db.set_value",
		) as set_value_mock:
			result = disciplinary_case_service.sync_disciplinary_case_effects(case_doc)

		self.assertEqual(result["status"], "active")
		set_value_mock.assert_called_once_with("Ficha Empleado", "EMP-001", "estado", "Suspensión", update_modified=False)

	def test_close_disciplinary_case_persists_rrll_outcome_payload(self):
		case_doc = SimpleNamespace(
			name="DIS-003",
			save=lambda ignore_permissions=True: None,
		)

		with patch(
			"hubgh.hubgh.disciplinary_case_service.enforce_disciplinary_access",
			return_value={"can_manage": True},
		), patch(
			"hubgh.hubgh.disciplinary_case_service.frappe.get_doc",
			return_value=case_doc,
		), patch(
			"hubgh.hubgh.disciplinary_case_service.get_disciplinary_case_snapshot",
			return_value={"name": "DIS-003", "decision": "Suspensión"},
		):
			result = disciplinary_case_service.close_disciplinary_case(
				case_name="DIS-003",
				decision="Suspensión",
				closure_date="2026-04-13",
				closure_summary="Medida disciplinaria aplicada",
				suspension_start="2026-04-14",
				suspension_end="2026-04-16",
			)

		self.assertEqual(case_doc.estado, "Cerrado")
		self.assertEqual(case_doc.decision_final, "Suspensión")
		self.assertEqual(case_doc.fecha_inicio_suspension, "2026-04-14")
		self.assertEqual(result["decision"], "Suspensión")

	def test_get_disciplinary_tray_filters_by_pdv_from_employee_map(self):
		case_rows = [
			{
				"name": "DIS-001",
				"empleado": "EMP-001",
				"fecha_incidente": "2026-04-10",
				"tipo_falta": "Grave",
				"estado": "Abierto",
				"decision_final": "",
				"fecha_cierre": "",
				"resumen_cierre": "",
				"fecha_inicio_suspension": "",
				"fecha_fin_suspension": "",
			},
		]
		employee_rows = [
			{"name": "EMP-001", "nombres": "Ana", "apellidos": "Paz", "cedula": "1001", "pdv": "PDV-1", "estado": "Activo"},
		]

		with patch(
			"hubgh.hubgh.disciplinary_case_service.enforce_disciplinary_access",
			return_value={"can_manage": True},
		), patch(
			"hubgh.hubgh.disciplinary_case_service.frappe.get_all",
			side_effect=[case_rows, employee_rows],
		):
			result = disciplinary_case_service.get_disciplinary_tray(filters={"pdv": "PDV-1"})

		self.assertEqual(len(result["rows"]), 1)
		self.assertEqual(result["rows"][0]["pdv"], "PDV-1")
