from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch


def _install_frappe_stub():
	frappe_module = sys.modules.get("frappe") or types.ModuleType("frappe")
	db = getattr(
		frappe_module,
		"db",
		types.SimpleNamespace(),
	)
	if not hasattr(db, "exists"):
		db.exists = lambda *args, **kwargs: False
	if not hasattr(db, "get_value"):
		db.get_value = lambda *args, **kwargs: None
	if not hasattr(db, "set_value"):
		db.set_value = lambda *args, **kwargs: None
	if not hasattr(db, "commit"):
		db.commit = lambda *args, **kwargs: None
	frappe_module.db = db
	frappe_module.flags = getattr(frappe_module, "flags", SimpleNamespace())
	frappe_module.get_all = getattr(frappe_module, "get_all", lambda *args, **kwargs: [])
	frappe_module.get_doc = getattr(frappe_module, "get_doc", lambda *args, **kwargs: None)
	frappe_module.get_roles = getattr(frappe_module, "get_roles", lambda *args, **kwargs: [])
	frappe_module.session = getattr(frappe_module, "session", SimpleNamespace(user="tester@example.com"))
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

from hubgh import person_identity, utils
from hubgh.patches import backfill_canonical_person_identity_by_document


class TestBackfillPersonIdentityContract(TestCase):
	def test_run_backfill_reports_conflicts_without_writing(self):
		employee = {"name": "EMP-1", "cedula": "123", "email": "empleado@example.com", "nombres": "Ana", "apellidos": "Paz"}
		conflict = person_identity.PersonIdentity(
			"EMP-1",
			"user@example.com",
			"123",
			"empleado@example.com",
			"username",
			conflict=True,
			conflict_reason="document_vs_email_conflict",
		)

		with patch("hubgh.utils.frappe.get_all", return_value=[employee]), patch(
			"hubgh.utils.resolve_user_for_employee",
			return_value=conflict,
		), patch("hubgh.utils.reconcile_person_identity") as reconcile, patch(
			"hubgh.utils.frappe.db.commit"
		), patch("hubgh.utils.frappe.logger", return_value=MagicMock()):
			report = utils.run_canonical_person_identity_backfill()

		reconcile.assert_not_called()
		self.assertEqual(report["employees_scanned"], 1)
		self.assertEqual(len(report["conflicts"]), 1)
		self.assertEqual(report["conflicts"][0]["reason"], "document_vs_email_conflict")

	def test_run_backfill_completes_unique_fallback_link(self):
		employee = {"name": "EMP-1", "cedula": "123", "email": "empleado@example.com", "nombres": "Ana", "apellidos": "Paz"}
		before = person_identity.PersonIdentity(
			"EMP-1",
			"user@example.com",
			"123",
			"empleado@example.com",
			"email_fallback",
			fallback=True,
			warnings=("email_fallback",),
		)
		reverse = person_identity.PersonIdentity(
			"EMP-1",
			"user@example.com",
			"123",
			"empleado@example.com",
			"email_fallback",
			fallback=True,
		)
		after = person_identity.PersonIdentity(
			"EMP-1",
			"user@example.com",
			"123",
			"empleado@example.com",
			"employee_link",
		)

		with patch("hubgh.utils.frappe.get_all", return_value=[employee]), patch(
			"hubgh.utils.resolve_user_for_employee",
			return_value=before,
		), patch(
			"hubgh.utils.resolve_employee_for_user",
			return_value=reverse,
		), patch(
			"hubgh.utils.reconcile_person_identity",
			return_value=after,
		) as reconcile, patch("hubgh.utils.frappe.db.commit"), patch(
			"hubgh.utils.frappe.logger",
			return_value=MagicMock(),
		):
			report = utils.run_canonical_person_identity_backfill()

		reconcile.assert_called_once()
		self.assertEqual(report["users_created"], 0)
		self.assertEqual(report["links_completed"], 1)
		self.assertEqual(report["fallback_only"], [])

	def test_run_backfill_reports_missing_document_as_pending(self):
		employee = {"name": "EMP-2", "cedula": "   ", "email": "empleado@example.com", "nombres": "Ana", "apellidos": "Paz"}
		before = person_identity.PersonIdentity("EMP-2", None, None, "empleado@example.com", "unresolved")

		with patch("hubgh.utils.frappe.get_all", return_value=[employee]), patch(
			"hubgh.utils.resolve_user_for_employee",
			return_value=before,
		), patch("hubgh.utils.reconcile_person_identity") as reconcile, patch(
			"hubgh.utils.frappe.db.commit"
		), patch("hubgh.utils.frappe.logger", return_value=MagicMock()):
			report = utils.run_canonical_person_identity_backfill()

		reconcile.assert_not_called()
		self.assertEqual(len(report["pending"]), 1)
		self.assertEqual(report["pending"][0]["reason"], "missing_normalized_document")

	def test_patch_execute_uses_shared_backfill_helper(self):
		report = {"employees_scanned": 1}
		with patch(
			"hubgh.patches.backfill_canonical_person_identity_by_document.run_canonical_person_identity_backfill",
			return_value=report,
		) as run_backfill, patch(
			"hubgh.patches.backfill_canonical_person_identity_by_document.frappe.logger",
			return_value=MagicMock(),
		):
			result = backfill_canonical_person_identity_by_document.execute()

		run_backfill.assert_called_once_with(commit=True)
		self.assertEqual(result, report)

	def test_manual_wrapper_returns_normalized_shape_and_traceability(self):
		raw_report = {
			"employees_scanned": 5,
			"users_created": 1,
			"links_completed": 2,
			"already_canonical": 1,
			"conflicts": [{"employee": "EMP-1", "reason": "document_conflict", "warnings": []}],
			"pending": [{"employee": "EMP-2", "reason": "missing_email", "warnings": ["missing_valid_email"]}],
			"fallback_only": [{"employee": "EMP-3", "reason": "fallback_not_one_to_one", "warnings": []}],
		}

		with patch(
			"hubgh.utils.run_canonical_person_identity_backfill",
			return_value=raw_report,
		) as run_backfill:
			result = utils.run_manual_person_identity_reconciliation(
				snapshot_id="snapshot-123",
				operator={"user": "runner@example.com", "roles": ["System Manager"]},
			)

		run_backfill.assert_called_once_with(default_password="Empleado123*", commit=True)
		self.assertEqual(result["status"], "completed")
		self.assertEqual(result["mode"], "apply")
		self.assertEqual(result["snapshot_id"], "snapshot-123")
		self.assertEqual(result["operator"]["user"], "runner@example.com")
		self.assertEqual(result["counts"]["skipped_rows"], 3)
		self.assertEqual(result["counts"]["mutations_applied"], 3)
		self.assertEqual(len(result["skipped_rows"]), 3)
		self.assertEqual(result["skipped_rows"][0]["category"], "conflict")
		self.assertEqual(result["traceability"]["write_path"], "hubgh.utils.run_manual_person_identity_reconciliation")
		self.assertEqual(result["traceability"]["canonical_helper"], "hubgh.utils.run_canonical_person_identity_backfill")
		self.assertTrue(result["traceability"]["commit"])
		self.assertFalse(result["traceability"]["preview_safe"])
