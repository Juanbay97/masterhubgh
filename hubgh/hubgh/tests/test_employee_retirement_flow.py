from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh import employee_retirement_service
from hubgh.hubgh.page.persona_360 import persona_360


class TestEmployeeRetirementFlow(FrappeTestCase):
	def test_submit_employee_retirement_schedules_future_offboarding(self):
		captured_updates = []
		row = {
			"name": "EMP-001",
			"nombres": "Ana",
			"apellidos": "Paz",
			"cedula": "1001",
			"cargo": "Analista",
			"pdv": "PDV-1",
			"estado": "Activo",
			"fecha_ingreso": "2026-01-10",
			"estado_retiro_operacion": "",
		}

		with patch("hubgh.hubgh.employee_retirement_service.frappe.session", new=SimpleNamespace(user="rrll@example.com")), patch(
			"hubgh.hubgh.employee_retirement_service.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.employee_retirement_service.nowdate",
			return_value="2026-04-13",
		), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.get_meta",
			return_value=SimpleNamespace(fields=[SimpleNamespace(fieldname=field) for field in employee_retirement_service.RETIREMENT_METADATA_FIELDS]),
		), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.db.get_value",
			return_value=row,
		), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.db.set_value",
			side_effect=lambda doctype, name, values, update_modified=False: captured_updates.append((doctype, name, values)),
		), patch("hubgh.hubgh.employee_retirement_service.apply_retirement") as retirement_mock:
			result = employee_retirement_service.submit_employee_retirement(
				employee="EMP-001",
				last_worked_date="2026-04-20",
				reason="Renuncia",
				closure_date="2026-04-13",
				closure_summary="Entrega de puesto validada",
			)

		self.assertEqual(result["status"], "scheduled")
		retirement_mock.assert_not_called()
		self.assertEqual(captured_updates[0][2]["estado_retiro_operacion"], "Programado")
		self.assertEqual(captured_updates[0][2]["fecha_retiro_efectiva"], "2026-04-20")

	def test_submit_employee_retirement_executes_immediately_when_due(self):
		captured_updates = []
		row = {
			"name": "EMP-001",
			"nombres": "Ana",
			"apellidos": "Paz",
			"cedula": "1001",
			"cargo": "Analista",
			"pdv": "PDV-1",
			"estado": "Activo",
			"fecha_ingreso": "2026-01-10",
			"estado_retiro_operacion": "",
		}

		with patch("hubgh.hubgh.employee_retirement_service.frappe.session", new=SimpleNamespace(user="rrll@example.com")), patch(
			"hubgh.hubgh.employee_retirement_service.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.employee_retirement_service.nowdate",
			return_value="2026-04-13",
		), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.get_meta",
			return_value=SimpleNamespace(fields=[SimpleNamespace(fieldname=field) for field in employee_retirement_service.RETIREMENT_METADATA_FIELDS]),
		), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.db.get_value",
			return_value=row,
		), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.db.set_value",
			side_effect=lambda doctype, name, values, update_modified=False: captured_updates.append((doctype, name, values)),
		), patch(
			"hubgh.hubgh.employee_retirement_service.apply_retirement",
			return_value={"employee": "EMP-001", "retirement_date": "2026-04-10"},
		) as retirement_mock:
			result = employee_retirement_service.submit_employee_retirement(
				employee="EMP-001",
				last_worked_date="2026-04-10",
				reason="Fin de contrato",
				closure_summary="Cierre administrativo completo",
			)

		self.assertEqual(result["status"], "retired")
		retirement_mock.assert_called_once()
		self.assertEqual(retirement_mock.call_args.kwargs["source_doctype"], "Ficha Empleado")
		self.assertEqual(captured_updates[0][2]["estado_retiro_operacion"], "Ejecutado")

	def test_submit_employee_retirement_respects_source_override(self):
		captured_updates = []
		row = {
			"name": "EMP-001",
			"nombres": "Ana",
			"apellidos": "Paz",
			"cedula": "1001",
			"cargo": "Analista",
			"pdv": "PDV-1",
			"estado": "Activo",
			"fecha_ingreso": "2026-01-10",
			"estado_retiro_operacion": "",
		}

		with patch("hubgh.hubgh.employee_retirement_service.nowdate", return_value="2026-04-13"), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.get_meta",
			return_value=SimpleNamespace(fields=[SimpleNamespace(fieldname=field) for field in employee_retirement_service.RETIREMENT_METADATA_FIELDS]),
		), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.db.get_value",
			return_value=row,
		), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.db.set_value",
			side_effect=lambda doctype, name, values, update_modified=False: captured_updates.append((doctype, name, values)),
		), patch(
			"hubgh.hubgh.employee_retirement_service.apply_retirement",
			return_value={"employee": "EMP-001", "retirement_date": "2026-04-10"},
		) as retirement_mock:
			employee_retirement_service.submit_employee_retirement(
				employee="EMP-001",
				last_worked_date="2026-04-10",
				reason="Terminación con justa causa",
				closure_summary="Cierre disciplinario",
				source_doctype="Caso Disciplinario",
				source_name="DIS-001",
				enforce_access=False,
			)

		self.assertEqual(retirement_mock.call_args.kwargs["source_doctype"], "Caso Disciplinario")
		self.assertEqual(retirement_mock.call_args.kwargs["source_name"], "DIS-001")
		self.assertEqual(captured_updates[0][2]["retiro_fuente_doctype"], "Caso Disciplinario")

	def test_process_pending_employee_retirements_executes_due_rows(self):
		captured_updates = []
		rows = [
			{
				"name": "EMP-001",
				"estado": "Activo",
				"motivo_retiro": "Renuncia",
				"detalle_retiro": "Entrega final aprobada",
				"fecha_retiro_efectiva": "2026-04-13",
				"retiro_fuente_doctype": "Ficha Empleado",
				"retiro_fuente_name": "EMP-001",
			}
		]

		with patch("hubgh.hubgh.employee_retirement_service.nowdate", return_value="2026-04-13"), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.get_all",
			return_value=rows,
		), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.get_meta",
			return_value=SimpleNamespace(fields=[SimpleNamespace(fieldname=field) for field in employee_retirement_service.RETIREMENT_METADATA_FIELDS]),
		), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.db.set_value",
			side_effect=lambda doctype, name, values, update_modified=False: captured_updates.append((doctype, name, values)),
		), patch(
			"hubgh.hubgh.employee_retirement_service.apply_retirement",
			return_value={"employee": "EMP-001", "retirement_date": "2026-04-13"},
		) as retirement_mock:
			result = employee_retirement_service.process_pending_employee_retirements()

		self.assertEqual(result["processed_count"], 1)
		retirement_mock.assert_called_once()
		self.assertEqual(captured_updates[0][2]["estado_retiro_operacion"], "Ejecutado")

	def test_get_retirement_tray_includes_legacy_retired_rows(self):
		rows = [
			{
				"name": "EMP-RET",
				"nombres": "Ana",
				"apellidos": "Paz",
				"cedula": "1001",
				"cargo": "Analista",
				"pdv": "PDV-1",
				"estado": "Retirado",
				"fecha_ingreso": "2026-01-10",
				"estado_retiro_operacion": "",
			}
		]

		with patch("hubgh.hubgh.employee_retirement_service.frappe.session", new=SimpleNamespace(user="rrll@example.com")), patch(
			"hubgh.hubgh.employee_retirement_service.user_has_any_role",
			return_value=True,
		), patch("hubgh.hubgh.employee_retirement_service.nowdate", return_value="2026-04-13"), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.get_meta",
			return_value=SimpleNamespace(fields=[SimpleNamespace(fieldname=field) for field in employee_retirement_service.RETIREMENT_METADATA_FIELDS]),
		), patch(
			"hubgh.hubgh.employee_retirement_service.frappe.get_all",
			return_value=rows,
		):
			result = employee_retirement_service.get_retirement_tray()

		self.assertEqual(result["summary"]["legacy_retired"], 1)
		self.assertEqual(result["rows"][0]["flow_status"], "Legado Retirado")

	def test_persona_360_contextual_actions_expose_retirement_route_for_rrll(self):
		with patch("hubgh.hubgh.page.persona_360.persona_360.user_has_any_role", side_effect=lambda user, *roles: "HR Labor Relations" in roles):
			actions = persona_360._build_contextual_actions(
				user="rrll@example.com",
				employee_id="EMP-001",
				is_gh=False,
				is_jefe=False,
				is_emp=False,
				can_view_sensitive=True,
			)

		retirement_actions = [row for row in actions["quick_actions"] if row["key"] == "manage_retirement" and row["visible"]]
		self.assertEqual(len(retirement_actions), 1)
		self.assertEqual(retirement_actions[0]["route"], "/app/bandeja-retiros-empleados")
