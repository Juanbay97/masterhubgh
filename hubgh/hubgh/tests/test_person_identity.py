from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hubgh import permissions, person_identity, user_groups
from hubgh.api import my_profile, ops
from hubgh.lms import integration_hooks
from hubgh.patches import backfill_canonical_person_identity_by_document


class TestPersonIdentity(TestCase):
	def test_normalize_document_keeps_ascii_alnum_only(self):
		self.assertEqual(person_identity.normalize_document(" 12.345-abc "), "12345ABC")
		self.assertEqual(person_identity.normalize_document("áéí 99.z"), "AEI99Z")

	def test_resolve_employee_for_user_matches_formatted_document(self):
		user_row = {"name": "user@example.com", "email": "user@example.com", "username": "12.345-abc", "employee": None}
		exact_scan = [{"name": "EMP-1", "cedula": "12 345 ABC", "email": "empleado@example.com"}]
		with patch("hubgh.person_identity._coerce_user", return_value=user_row), patch(
			"hubgh.person_identity._get_unique_employee_by_name",
			return_value=(None, None),
		), patch(
			"hubgh.person_identity.frappe.get_all",
			side_effect=[[], exact_scan, []],
		):
			identity = person_identity.resolve_employee_for_user("user@example.com")

		self.assertEqual(identity.employee, "EMP-1")
		self.assertEqual(identity.document, "12345ABC")
		self.assertEqual(identity.source, "username")
		self.assertFalse(identity.conflict)

	def test_resolve_employee_for_user_prefers_employee_link(self):
		with patch("hubgh.person_identity._coerce_user", return_value={"name": "user@example.com", "email": "user@example.com", "username": "123", "employee": "EMP-1"}), patch(
			"hubgh.person_identity._get_unique_employee_by_name",
			return_value=({"name": "EMP-1"}, None),
		), patch(
			"hubgh.person_identity._get_unique_employee_by_document",
			return_value=({"name": "EMP-1"}, None),
		), patch(
			"hubgh.person_identity._get_unique_employee_by_email",
			return_value=({"name": "EMP-1"}, None),
		):
			identity = person_identity.resolve_employee_for_user("user@example.com")

		self.assertEqual(identity.employee, "EMP-1")
		self.assertEqual(identity.source, "employee_link")
		self.assertFalse(identity.conflict)

	def test_resolve_employee_for_user_surfaces_document_vs_email_conflict(self):
		with patch("hubgh.person_identity._coerce_user", return_value={"name": "user@example.com", "email": "user@example.com", "username": "123", "employee": None}), patch(
			"hubgh.person_identity._get_unique_employee_by_name",
			return_value=(None, None),
		), patch(
			"hubgh.person_identity._get_unique_employee_by_document",
			return_value=({"name": "EMP-DOC"}, None),
		), patch(
			"hubgh.person_identity._get_unique_employee_by_email",
			return_value=({"name": "EMP-MAIL"}, None),
		), patch("hubgh.person_identity.frappe.logger"):
			identity = person_identity.resolve_employee_for_user("user@example.com")

		self.assertEqual(identity.employee, "EMP-DOC")
		self.assertEqual(identity.source, "username")
		self.assertTrue(identity.conflict)
		self.assertEqual(identity.conflict_reason, "document_vs_email_conflict")

	def test_resolve_user_for_employee_marks_email_fallback_and_logs(self):
		employee_row = {"name": "EMP-1", "cedula": "123", "email": "empleado@example.com"}
		logger = SimpleNamespace(warning=lambda *args, **kwargs: None, info=lambda *args, **kwargs: None)
		with patch("hubgh.person_identity._coerce_employee", return_value=employee_row), patch(
			"hubgh.person_identity._get_unique_user_by_employee",
			return_value=(None, None),
		), patch(
			"hubgh.person_identity._get_unique_user_by_document",
			return_value=(None, None),
		), patch(
			"hubgh.person_identity._get_unique_user_by_email",
			return_value=("empleado@example.com", None),
		), patch("hubgh.person_identity.frappe.logger", return_value=logger) as logger_factory:
			identity = person_identity.resolve_user_for_employee("EMP-1")

		self.assertEqual(identity.user, "empleado@example.com")
		self.assertEqual(identity.source, "email_fallback")
		self.assertTrue(identity.fallback)
		self.assertIn("email_fallback", identity.warnings)
		logger_factory.assert_called_with("hubgh.person_identity")

	def test_reconcile_person_identity_leaves_pending_when_email_is_invalid(self):
		employee_row = {"name": "EMP-1", "cedula": "123", "email": "correo-invalido", "nombres": "Ana", "apellidos": "Paz"}
		with patch("hubgh.person_identity._coerce_employee", return_value=employee_row), patch(
			"hubgh.person_identity._coerce_user",
			return_value=None,
		), patch(
			"hubgh.person_identity.resolve_user_for_employee",
			return_value=person_identity.PersonIdentity("EMP-1", None, "123", None, "unresolved"),
		), patch(
			"hubgh.person_identity._get_unique_user_by_document",
			return_value=(None, None),
		), patch("hubgh.person_identity.frappe.logger"):
			identity = person_identity.reconcile_person_identity(
				employee="EMP-1",
				document="123",
				email="correo-invalido",
				allow_create_user=True,
			)

		self.assertTrue(identity.pending)
		self.assertIsNone(identity.user)
		self.assertEqual(identity.conflict_reason, "invalid_or_missing_email")

	def test_reconcile_person_identity_blocks_duplicate_document_matches(self):
		employee_row = {"name": "EMP-1", "cedula": "123", "email": "empleado@example.com"}
		with patch("hubgh.person_identity._coerce_employee", return_value=employee_row), patch(
			"hubgh.person_identity._coerce_user",
			return_value=None,
		), patch(
			"hubgh.person_identity.resolve_user_for_employee",
			return_value=person_identity.PersonIdentity("EMP-1", None, "123", "empleado@example.com", "unresolved"),
		), patch(
			"hubgh.person_identity._get_unique_user_by_document",
			return_value=(None, "user_duplicate_document"),
		), patch("hubgh.person_identity.frappe.logger"):
			identity = person_identity.reconcile_person_identity(employee="EMP-1", document="123")

		self.assertTrue(identity.conflict)
		self.assertEqual(identity.conflict_reason, "user_duplicate_document")

	def test_ensure_user_roles_inserts_has_role_without_saving_user(self):
		user_doc = SimpleNamespace(roles=[], save=MagicMock())
		inserted = []

		def fake_get_doc(*args, **kwargs):
			if args == ("User", "empleado@example.com"):
				return user_doc
			payload = args[0] if args else kwargs
			insert = MagicMock(side_effect=lambda ignore_permissions=True: inserted.append(payload))
			return SimpleNamespace(insert=insert)

		with patch("hubgh.person_identity.frappe.get_doc", side_effect=fake_get_doc), patch(
			"hubgh.person_identity.frappe.db.exists",
			return_value=True,
		):
			person_identity._ensure_user_roles("empleado@example.com", ["Empleado"])

		user_doc.save.assert_not_called()
		self.assertEqual(inserted, [{"doctype": "Has Role", "parenttype": "User", "parentfield": "roles", "parent": "empleado@example.com", "role": "Empleado"}])

	def test_ensure_user_roles_creates_missing_role_before_assignment(self):
		user_doc = SimpleNamespace(roles=[])
		inserted = []

		def fake_get_doc(*args, **kwargs):
			if args == ("User", "empleado@example.com"):
				return user_doc
			payload = args[0] if args else kwargs
			insert = MagicMock(side_effect=lambda ignore_permissions=True: inserted.append(payload))
			return SimpleNamespace(insert=insert)

		def fake_exists(doctype, name):
			return not (doctype == "Role" and name == "Empleado")

		with patch("hubgh.person_identity.frappe.get_doc", side_effect=fake_get_doc), patch(
			"hubgh.person_identity.frappe.db.exists",
			side_effect=fake_exists,
		):
			person_identity._ensure_user_roles("empleado@example.com", ["Empleado"])

		self.assertEqual(
			inserted,
			[
				{"doctype": "Role", "role_name": "Empleado", "desk_access": 1, "read_only": 0},
				{"doctype": "Has Role", "parenttype": "User", "parentfield": "roles", "parent": "empleado@example.com", "role": "Empleado"},
			],
		)

	def test_my_profile_employee_lookup_uses_canonical_resolver(self):
		identity = person_identity.PersonIdentity("EMP-1", "user@example.com", "123", "user@example.com", "employee_link")
		with patch("hubgh.api.my_profile.frappe.db.exists", return_value=True), patch(
			"hubgh.api.my_profile.resolve_employee_for_user",
			return_value=identity,
		), patch(
			"hubgh.api.my_profile.frappe.db.get_value",
			return_value={"name": "EMP-1", "cargo": "Auxiliar"},
		):
			row = my_profile._get_employee_from_user("user@example.com")

		self.assertEqual(row["name"], "EMP-1")

	def test_ops_session_employee_uses_canonical_resolver(self):
		identity = person_identity.PersonIdentity("EMP-1", "jefe@example.com", "123", "jefe@example.com", "employee_link")
		with patch("hubgh.api.ops.frappe.session", new=SimpleNamespace(user="jefe@example.com")), patch(
			"hubgh.api.ops.resolve_employee_for_user",
			return_value=identity,
		), patch(
			"hubgh.api.ops.frappe.db.get_value",
			return_value={"name": "EMP-1", "pdv": "PDV-1"},
		):
			row = ops._get_session_employee()

		self.assertEqual(row["name"], "EMP-1")

	def test_permissions_employee_row_uses_canonical_resolver(self):
		identity = person_identity.PersonIdentity("EMP-1", "empleado@example.com", "123", "empleado@example.com", "employee_link")
		with patch("hubgh.permissions.resolve_employee_for_user", return_value=identity), patch(
			"hubgh.permissions.frappe.db.get_value",
			return_value={"name": "EMP-1", "pdv": "PDV-1", "email": "empleado@example.com", "cedula": "123"},
		):
			row = permissions._get_employee_row("empleado@example.com")

		self.assertEqual(row["name"], "EMP-1")

	def test_user_groups_resolve_user_from_employee_row_uses_canonical_resolver(self):
		identity = person_identity.PersonIdentity("EMP-1", "empleado@example.com", "123", "empleado@example.com", "username")
		with patch("hubgh.user_groups.resolve_user_for_employee", return_value=identity):
			user = user_groups._resolve_user_from_employee_row({"name": "EMP-1", "cedula": "123", "email": "empleado@example.com"})

		self.assertEqual(user, "empleado@example.com")

	def test_lms_hook_resolves_employee_user_canonically(self):
		identity = person_identity.PersonIdentity("EMP-1", "empleado@example.com", "123", "empleado@example.com", "employee_link")
		with patch("hubgh.lms.integration_hooks.resolve_user_for_employee", return_value=identity):
			user = integration_hooks._resolver_usuario_empleado(SimpleNamespace(name="EMP-1", cedula="123"))

		self.assertEqual(user, "empleado@example.com")

	def test_backfill_patch_reports_created_users_without_conflicts(self):
		before = person_identity.PersonIdentity("EMP-1", None, "123", "empleado@example.com", "unresolved")
		after = person_identity.PersonIdentity("EMP-1", "empleado@example.com", "123", "empleado@example.com", "employee_link")
		with patch(
			"hubgh.patches.backfill_canonical_person_identity_by_document.ensure_roles_and_profiles"
		), patch(
			"hubgh.patches.backfill_canonical_person_identity_by_document.run_canonical_person_identity_backfill",
			return_value={
				"employees_scanned": 1,
				"users_created": 1,
				"links_completed": 0,
				"conflicts": [],
				"before": before,
				"after": after,
			},
		), patch("hubgh.patches.backfill_canonical_person_identity_by_document.frappe.db.commit"), patch(
			"hubgh.patches.backfill_canonical_person_identity_by_document.frappe.logger"
		):
			report = backfill_canonical_person_identity_by_document.execute()

		self.assertEqual(report["employees_scanned"], 1)
		self.assertEqual(report["users_created"], 1)
		self.assertEqual(report["links_completed"], 0)
		self.assertEqual(report["conflicts"], [])

	def test_operational_snapshot_scans_both_directions_and_dedupes(self):
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
		canonical_rows = snapshot["rows_by_category"]["already_canonical"]["rows"]
		self.assertEqual(len(canonical_rows), 1)
		self.assertEqual(canonical_rows[0]["stable_key"], "employee:EMP-1")
		self.assertEqual(canonical_rows[0]["scan_sources"], ["employee", "user"])

	def test_operational_snapshot_excludes_non_operational_accounts(self):
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

	def test_operational_snapshot_surfaces_conflicts(self):
		employee = {"name": "EMP-9", "cedula": "999", "email": "conflict@example.com", "estado": "Activo"}
		with patch("hubgh.person_identity.frappe.get_all", side_effect=lambda doctype, **kwargs: [employee] if doctype == "Ficha Empleado" else []), patch(
			"hubgh.person_identity.resolve_user_for_employee",
			return_value=person_identity.PersonIdentity(
				"EMP-9",
				"wrong@example.com",
				"999",
				"conflict@example.com",
				"username",
				conflict=True,
				conflict_reason="document_vs_email_conflict",
			),
		):
			snapshot = person_identity.get_operational_person_identity_snapshot()

		self.assertEqual(snapshot["kpis"]["conflicts"], 1)
		self.assertEqual(
			snapshot["rows_by_category"]["conflicts"]["rows"][0]["reason"],
			"document_vs_email_conflict",
		)

	def test_operational_snapshot_marks_pending_rows(self):
		employee = {"name": "EMP-3", "cedula": "   ", "email": "correo-invalido", "estado": "Activo"}
		with patch("hubgh.person_identity.frappe.get_all", side_effect=lambda doctype, **kwargs: [employee] if doctype == "Ficha Empleado" else []), patch(
			"hubgh.person_identity.resolve_user_for_employee",
			return_value=person_identity.PersonIdentity("EMP-3", None, None, "correo-invalido", "unresolved"),
		):
			snapshot = person_identity.get_operational_person_identity_snapshot()

		self.assertEqual(snapshot["kpis"]["pending"], 1)
		self.assertEqual(snapshot["rows_by_category"]["pending"]["rows"][0]["reason"], "missing_normalized_document")

	def test_operational_snapshot_keeps_fallback_only_rows(self):
		employee = {"name": "EMP-4", "cedula": "444", "email": "emp4@example.com", "estado": "Activo"}
		with patch("hubgh.person_identity.frappe.get_all", side_effect=lambda doctype, **kwargs: [employee] if doctype == "Ficha Empleado" else []), patch(
			"hubgh.person_identity.resolve_user_for_employee",
			return_value=person_identity.PersonIdentity(
				"EMP-4",
				"fallback@example.com",
				"444",
				"fallback@example.com",
				"email_fallback",
				fallback=True,
				warnings=("email_fallback",),
			),
		):
			snapshot = person_identity.get_operational_person_identity_snapshot()

		self.assertEqual(snapshot["kpis"]["fallback_only"], 1)
		self.assertEqual(snapshot["rows_by_category"]["fallback_only"]["rows"][0]["source"], "email_fallback")

	def test_operational_snapshot_is_strictly_read_only(self):
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
