from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh import people_ops_lifecycle


class TestPeopleOpsLifecycle(FrappeTestCase):
	def test_reverse_retirement_if_clear_updates_metadata_without_typeerror(self):
		meta = type("Meta", (), {"fields": [type("Field", (), {"fieldname": "estado_retiro_operacion"})()]})()

		with patch(
			"hubgh.hubgh.people_ops_lifecycle._has_other_active_retirement_sources",
			return_value=False,
		), patch(
			"hubgh.hubgh.people_ops_lifecycle.frappe.get_meta",
			return_value=meta,
		), patch(
			"hubgh.hubgh.people_ops_lifecycle.frappe.db.set_value",
		) as set_value_mock, patch(
			"hubgh.hubgh.people_ops_lifecycle.resolve_user_for_employee",
			return_value=None,
		), patch(
			"hubgh.hubgh.people_ops_lifecycle._reactivate_tarjeta_empleado_if_exists",
		), patch(
			"hubgh.hubgh.people_ops_lifecycle._sync_contract_retirement",
		), patch(
			"hubgh.hubgh.people_ops_lifecycle._emit_trace_event",
		), patch(
			"hubgh.hubgh.people_ops_lifecycle.nowdate",
			return_value="2026-04-15",
		):
			result = people_ops_lifecycle.reverse_retirement_if_clear(
				employee="EMP-001",
				source_doctype="Caso Disciplinario",
				source_name="DIS-001",
			)

		self.assertTrue(result["reversed"])
		set_value_mock.assert_any_call("Ficha Empleado", "EMP-001", "estado", "Activo", update_modified=False)
		set_value_mock.assert_any_call(
			"Ficha Empleado",
			"EMP-001",
			{"estado_retiro_operacion": "Revertido"},
			update_modified=False,
		)

	def test_apply_retirement_updates_metadata_without_typeerror(self):
		meta = type(
			"Meta",
			(),
			{
				"fields": [
					type("Field", (), {"fieldname": "estado_retiro_operacion"})(),
					type("Field", (), {"fieldname": "motivo_retiro"})(),
				]
			},
		)()

		with patch(
			"hubgh.hubgh.people_ops_lifecycle.frappe.get_meta",
			return_value=meta,
		), patch(
			"hubgh.hubgh.people_ops_lifecycle.frappe.db.set_value",
		) as set_value_mock, patch(
			"hubgh.hubgh.people_ops_lifecycle.resolve_user_for_employee",
			return_value=None,
		), patch(
			"hubgh.hubgh.people_ops_lifecycle._deactivate_tarjeta_empleado_if_exists",
		), patch(
			"hubgh.hubgh.people_ops_lifecycle._sync_contract_retirement",
		), patch(
			"hubgh.hubgh.people_ops_lifecycle._ensure_payroll_liquidation_case",
			return_value=None,
		), patch(
			"hubgh.hubgh.people_ops_lifecycle._emit_trace_event",
		):
			result = people_ops_lifecycle.apply_retirement(
				employee="EMP-001",
				source_doctype="Caso Disciplinario",
				source_name="DIS-001",
				retirement_date="2026-04-15",
				reason="Terminación con justa causa. Validado RRLL",
			)

		self.assertEqual(result["employee"], "EMP-001")
		set_value_mock.assert_any_call("Ficha Empleado", "EMP-001", "estado", "Retirado", update_modified=False)
		set_value_mock.assert_any_call(
			"Ficha Empleado",
			"EMP-001",
			{
				"estado_retiro_operacion": "Ejecutado",
				"motivo_retiro": "Terminación con justa causa",
			},
			update_modified=False,
		)
