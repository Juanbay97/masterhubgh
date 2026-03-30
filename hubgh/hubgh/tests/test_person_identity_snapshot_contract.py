from __future__ import annotations

import sys
import types
from unittest import TestCase
from unittest.mock import patch


def _install_frappe_stub():
	frappe_module = sys.modules.get("frappe") or types.ModuleType("frappe")
	frappe_module.db = getattr(
		frappe_module,
		"db",
		types.SimpleNamespace(
			exists=lambda *args, **kwargs: False,
			get_value=lambda *args, **kwargs: None,
			set_value=lambda *args, **kwargs: None,
			commit=lambda *args, **kwargs: None,
		),
	)
	frappe_module.get_all = getattr(frappe_module, "get_all", lambda *args, **kwargs: [])
	frappe_module.get_doc = getattr(frappe_module, "get_doc", lambda *args, **kwargs: None)
	frappe_module._dict = getattr(frappe_module, "_dict", lambda value: value)
	frappe_module.logger = getattr(
		frappe_module,
		"logger",
		lambda *args, **kwargs: types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
	)

	frappe_utils = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")
	frappe_utils.validate_email_address = getattr(
		frappe_utils,
		"validate_email_address",
		lambda value, throw=False: "@" in (value or ""),
	)

	sys.modules["frappe"] = frappe_module
	sys.modules["frappe.utils"] = frappe_utils


_install_frappe_stub()

from hubgh import person_identity


class TestPersonIdentitySnapshotContract(TestCase):
	def test_snapshot_scans_both_directions_and_dedupes(self):
		employees = [
			{"name": "EMP-1", "cedula": "123", "email": "emp1@example.com", "estado": "Activo"},
			{"name": "EMP-2", "cedula": "456", "email": "emp2@example.com", "estado": "Activo"},
		]
		users = [
			{"name": "user1@example.com", "email": "user1@example.com", "username": "123", "employee": "EMP-1", "enabled": 1, "user_type": "System User"},
			{"name": "orphan@example.com", "email": "orphan@example.com", "username": "999", "employee": None, "enabled": 1, "user_type": "System User"},
		]

		def fake_get_all(doctype, **kwargs):
			if doctype == "Ficha Empleado":
				return employees
			if doctype == "User":
				return users
			return []

		with patch("hubgh.person_identity.frappe.get_all", side_effect=fake_get_all), patch(
			"hubgh.person_identity.resolve_user_for_employee",
			side_effect=[
				person_identity.PersonIdentity("EMP-1", "user1@example.com", "123", "user1@example.com", "employee_link"),
				person_identity.PersonIdentity("EMP-2", None, "456", "emp2@example.com", "unresolved"),
			],
		), patch(
			"hubgh.person_identity.resolve_employee_for_user",
			side_effect=[
				person_identity.PersonIdentity("EMP-1", "user1@example.com", "123", "user1@example.com", "employee_link"),
				person_identity.PersonIdentity(None, "orphan@example.com", "999", "orphan@example.com", "unresolved"),
			],
		):
			snapshot = person_identity.get_operational_person_identity_snapshot()

		self.assertEqual(snapshot["kpis"]["already_canonical"], 1)
		self.assertEqual(snapshot["kpis"]["employees_without_user"], 1)
		self.assertEqual(snapshot["kpis"]["users_without_employee"], 1)
		self.assertEqual(snapshot["rows_by_category"]["already_canonical"]["rows"][0]["scan_sources"], ["employee", "user"])

	def test_snapshot_omits_employee_column_when_user_schema_does_not_expose_it(self):
		requested_user_fields = []

		class _UserMeta:
			def get_valid_columns(self):
				return ["name", "email", "username", "enabled", "first_name", "last_name", "user_type"]

		def fake_get_all(doctype, **kwargs):
			if doctype == "Ficha Empleado":
				return []
			if doctype == "User":
				requested_user_fields.append(list(kwargs.get("fields") or []))
				return [{"name": "ops@example.com", "email": "ops@example.com", "username": "333", "enabled": 1, "user_type": "System User"}]
			return []

		with patch("hubgh.person_identity.frappe.get_meta", return_value=_UserMeta(), create=True), patch(
			"hubgh.person_identity.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.person_identity.resolve_employee_for_user",
			return_value=person_identity.PersonIdentity(None, "ops@example.com", "333", "ops@example.com", "unresolved"),
		):
			snapshot = person_identity.get_operational_person_identity_snapshot()

		self.assertEqual(requested_user_fields, [["name", "email", "username", "enabled", "first_name", "last_name", "user_type"]])
		self.assertEqual(snapshot["kpis"]["users_without_employee"], 1)

	def test_snapshot_excludes_non_operational_accounts(self):
		users = [
			{"name": "Guest", "email": "", "username": "", "employee": None, "enabled": 1, "user_type": "System User"},
			{"name": "Administrator", "email": "", "username": "", "employee": None, "enabled": 1, "user_type": "System User"},
			{"name": "disabled@example.com", "email": "disabled@example.com", "username": "111", "employee": None, "enabled": 0, "user_type": "System User"},
			{"name": "portal@example.com", "email": "portal@example.com", "username": "222", "employee": None, "enabled": 1, "user_type": "Website User"},
			{"name": "ops@example.com", "email": "ops@example.com", "username": "333", "employee": None, "enabled": 1, "user_type": "System User"},
		]

		def fake_get_all(doctype, **kwargs):
			if doctype == "Ficha Empleado":
				return []
			if doctype == "User":
				return users
			return []

		with patch("hubgh.person_identity.frappe.get_all", side_effect=fake_get_all), patch(
			"hubgh.person_identity.resolve_employee_for_user",
			return_value=person_identity.PersonIdentity(None, "ops@example.com", "333", "ops@example.com", "unresolved"),
		) as resolve_employee:
			snapshot = person_identity.get_operational_person_identity_snapshot()

		resolve_employee.assert_called_once()
		self.assertEqual(snapshot["traceability"]["excluded_users"], ["Guest", "Administrator", "disabled@example.com", "portal@example.com"])
		self.assertEqual(snapshot["kpis"]["users_without_employee"], 1)

	def test_snapshot_surfaces_conflicts_pending_and_fallback(self):
		employees = [
			{"name": "EMP-C", "cedula": "999", "email": "conflict@example.com", "estado": "Activo"},
			{"name": "EMP-P", "cedula": " ", "email": "correo-invalido", "estado": "Activo"},
			{"name": "EMP-F", "cedula": "444", "email": "emp4@example.com", "estado": "Activo"},
		]

		with patch("hubgh.person_identity.frappe.get_all", side_effect=lambda doctype, **kwargs: employees if doctype == "Ficha Empleado" else []), patch(
			"hubgh.person_identity.resolve_user_for_employee",
			side_effect=[
				person_identity.PersonIdentity("EMP-C", "wrong@example.com", "999", "conflict@example.com", "username", conflict=True, conflict_reason="document_vs_email_conflict"),
				person_identity.PersonIdentity("EMP-P", None, None, "correo-invalido", "unresolved"),
				person_identity.PersonIdentity("EMP-F", "fallback@example.com", "444", "fallback@example.com", "email_fallback", fallback=True, warnings=("email_fallback",)),
			],
		):
			snapshot = person_identity.get_operational_person_identity_snapshot()

		self.assertEqual(snapshot["kpis"]["conflicts"], 1)
		self.assertEqual(snapshot["kpis"]["pending"], 1)
		self.assertEqual(snapshot["kpis"]["fallback_only"], 1)
		self.assertEqual(snapshot["rows_by_category"]["conflicts"]["rows"][0]["reason"], "document_vs_email_conflict")
		self.assertEqual(snapshot["rows_by_category"]["pending"]["rows"][0]["reason"], "missing_normalized_document")

	def test_snapshot_is_read_only(self):
		employee = {"name": "EMP-5", "cedula": "555", "email": "emp5@example.com", "estado": "Activo"}
		with patch("hubgh.person_identity.frappe.get_all", side_effect=lambda doctype, **kwargs: [employee] if doctype == "Ficha Empleado" else []), patch(
			"hubgh.person_identity.resolve_user_for_employee",
			return_value=person_identity.PersonIdentity("EMP-5", None, "555", "emp5@example.com", "unresolved"),
		), patch("hubgh.person_identity.reconcile_person_identity") as reconcile, patch(
			"hubgh.person_identity.frappe.db.set_value",
			create=True,
		) as set_value, patch("hubgh.person_identity.frappe.db.commit", create=True) as commit:
			snapshot = person_identity.get_operational_person_identity_snapshot()

		reconcile.assert_not_called()
		set_value.assert_not_called()
		commit.assert_not_called()
		self.assertEqual(snapshot["kpis"]["employees_without_user"], 1)
