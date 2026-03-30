from __future__ import annotations

import sys
import types
from unittest import TestCase
from unittest.mock import MagicMock, patch


def _install_frappe_stub():
	frappe_module = sys.modules.get("frappe") or types.ModuleType("frappe")
	frappe_module.db = getattr(
		frappe_module,
		"db",
		types.SimpleNamespace(
			exists=lambda *args, **kwargs: False,
			get_value=lambda *args, **kwargs: None,
			set_value=lambda *args, **kwargs: None,
		),
	)
	frappe_module.get_all = getattr(frappe_module, "get_all", lambda *args, **kwargs: [])
	frappe_module.get_doc = getattr(frappe_module, "get_doc", lambda *args, **kwargs: None)
	frappe_module._dict = getattr(frappe_module, "_dict", lambda value: value)
	frappe_module._ = getattr(frappe_module, "_", lambda value: value)
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


class TestPersonIdentityContract(TestCase):
	def test_normalize_document_removes_formatting(self):
		self.assertEqual(person_identity.normalize_document(" 12.345-abc "), "12345ABC")
		self.assertEqual(person_identity.normalize_document("áéí 99.z"), "AEI99Z")

	def test_resolve_employee_for_user_prefers_explicit_employee_link(self):
		user_row = {"name": "user@example.com", "email": "user@example.com", "username": "123", "employee": "EMP-1"}
		with patch("hubgh.person_identity._coerce_user", return_value=user_row), patch(
			"hubgh.person_identity._get_unique_employee_by_name",
			return_value=({"name": "EMP-1"}, None),
		), patch(
			"hubgh.person_identity._get_unique_employee_by_document",
			return_value=({"name": "EMP-2"}, None),
		), patch(
			"hubgh.person_identity._get_unique_employee_by_email",
			return_value=({"name": "EMP-3"}, None),
		):
			identity = person_identity.resolve_employee_for_user("user@example.com")

		self.assertEqual(identity.employee, "EMP-1")
		self.assertEqual(identity.source, "employee_link")
		self.assertTrue(identity.conflict)
		self.assertEqual(identity.conflict_reason, "document_vs_employee_link_conflict")

	def test_resolve_employee_for_user_matches_normalized_document(self):
		user_row = {"name": "user@example.com", "email": "user@example.com", "username": "12.345-abc", "employee": None}
		with patch("hubgh.person_identity._coerce_user", return_value=user_row), patch(
			"hubgh.person_identity._get_unique_employee_by_name",
			return_value=(None, None),
		), patch(
			"hubgh.person_identity.frappe.get_all",
			side_effect=[[], [{"name": "EMP-1", "cedula": "12 345 ABC", "email": "empleado@example.com"}], []],
		):
			identity = person_identity.resolve_employee_for_user("user@example.com")

		self.assertEqual(identity.employee, "EMP-1")
		self.assertEqual(identity.document, "12345ABC")
		self.assertEqual(identity.source, "username")
		self.assertFalse(identity.conflict)

	def test_resolve_user_for_employee_warns_on_email_fallback(self):
		employee_row = {"name": "EMP-1", "cedula": "123", "email": "empleado@example.com"}
		logger = MagicMock()
		with patch("hubgh.person_identity._coerce_employee", return_value=employee_row), patch(
			"hubgh.person_identity._get_unique_user_by_employee",
			return_value=(None, None),
		), patch(
			"hubgh.person_identity._get_unique_user_by_document",
			return_value=(None, None),
		), patch(
			"hubgh.person_identity._get_unique_user_by_email",
			return_value=("empleado@example.com", None),
		), patch("hubgh.person_identity.frappe.logger", return_value=logger):
			identity = person_identity.resolve_user_for_employee("EMP-1")

		self.assertEqual(identity.user, "empleado@example.com")
		self.assertEqual(identity.source, "email_fallback")
		self.assertTrue(identity.fallback)
		logger.warning.assert_called_once()

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

	def test_reconcile_person_identity_refuses_to_create_user_without_valid_email(self):
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
