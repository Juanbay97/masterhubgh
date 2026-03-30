from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


class _FrappeError(Exception):
	pass


class _FakeCache:
	def __init__(self):
		self.values = {}

	def get_value(self, key):
		return self.values.get(key)

	def set_value(self, key, value, expires_in_sec=None):
		self.values[key] = value

	def delete_value(self, key):
		self.values.pop(key, None)


def _install_frappe_stub():
	frappe_module = sys.modules.get("frappe") or types.ModuleType("frappe")
	frappe_module.db = getattr(
		frappe_module,
		"db",
		types.SimpleNamespace(
			set_value=lambda *args, **kwargs: None,
			commit=lambda *args, **kwargs: None,
		),
	)
	frappe_module.whitelist = getattr(frappe_module, "whitelist", lambda *args, **kwargs: (lambda fn: fn))
	frappe_module.parse_json = getattr(frappe_module, "parse_json", lambda value: {"limit": 10} if value else {})
	frappe_module.throw = getattr(
		frappe_module,
		"throw",
		lambda message, exc=None: (_ for _ in ()).throw((exc or _FrappeError)(message)),
	)
	frappe_module.PermissionError = getattr(frappe_module, "PermissionError", _FrappeError)
	frappe_module.get_roles = getattr(frappe_module, "get_roles", lambda *args, **kwargs: [])
	frappe_module.get_site_config = getattr(frappe_module, "get_site_config", lambda: {})
	frappe_module.session = getattr(frappe_module, "session", SimpleNamespace(user="runner@example.com"))
	cache = getattr(frappe_module, "_cache", None) or _FakeCache()
	frappe_module._cache = cache
	frappe_module.cache = getattr(frappe_module, "cache", lambda: cache)
	frappe_module._dict = getattr(frappe_module, "_dict", lambda value: value)
	frappe_module.get_all = getattr(frappe_module, "get_all", lambda *args, **kwargs: [])
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

from hubgh import utils
from hubgh.hubgh.page.operational_person_identity_tray import operational_person_identity_tray


class TestOperationalPersonIdentityTray(TestCase):
	def setUp(self):
		sys.modules["frappe"]._cache = _FakeCache()
		sys.modules["frappe"].cache = lambda: sys.modules["frappe"]._cache
		sys.modules["frappe"].session = SimpleNamespace(user="runner@example.com")

	def test_get_snapshot_returns_snapshot_contract_without_writes(self):
		expected = {
			"generated_at": "2026-03-30T00:00:00+00:00",
			"filters": {"category": None, "search": None, "limit": 10, "offset": 0},
			"kpis": {"employees_without_user": 0},
			"rows_by_category": {},
		}

		with patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.get_operational_person_identity_snapshot",
			return_value=expected,
		) as get_snapshot, patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.frappe.get_roles",
			return_value=["Gestión Humana"],
		), patch("hubgh.utils.run_canonical_person_identity_backfill") as backfill, patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.frappe.db.set_value",
			create=True,
		) as set_value, patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.frappe.db.commit",
			create=True,
		) as commit:
			result = operational_person_identity_tray.get_snapshot('{"limit": 10}')

		get_snapshot.assert_called_once_with(filters={"limit": 10})
		backfill.assert_not_called()
		set_value.assert_not_called()
		commit.assert_not_called()
		self.assertEqual(result, expected)

	def test_get_snapshot_denies_unauthorized_view_without_disclosing_data(self):
		with patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.frappe.get_roles",
			return_value=["Empleado"],
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.get_operational_person_identity_snapshot"
		) as get_snapshot:
			with self.assertRaises(_FrappeError):
				operational_person_identity_tray.get_snapshot('{"limit": 10}')

		get_snapshot.assert_not_called()

	def test_get_tray_context_returns_permission_flags_only(self):
		with patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.frappe.get_roles",
			return_value=["Gestión Humana"],
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.resolve_operational_person_identity_manual_run_enabled",
			return_value=False,
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.get_operational_person_identity_snapshot"
		) as get_snapshot:
			result = operational_person_identity_tray.get_tray_context()

		self.assertEqual(
			result,
			{
				"page_name": "operational_person_identity_tray",
				"can_view": True,
				"can_execute": False,
				"manual_run_mode": "disabled",
				"manual_confirmation_template": "MANUAL:{snapshot_id}",
			},
		)
		get_snapshot.assert_not_called()

	def test_get_tray_context_enables_run_only_when_role_and_flag_match(self):
		with patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.frappe.get_roles",
			return_value=["System Manager"],
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.resolve_operational_person_identity_manual_run_enabled",
			return_value=True,
		):
			result = operational_person_identity_tray.get_tray_context()

		self.assertTrue(result["can_view"])
		self.assertTrue(result["can_execute"])
		self.assertEqual(result["manual_run_mode"], "enabled")

	def test_get_tray_context_keeps_administrator_visible_but_respects_manual_flag(self):
		sys.modules["frappe"].session = SimpleNamespace(user="Administrator")

		with patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.resolve_operational_person_identity_manual_run_enabled",
			return_value=True,
		):
			result = operational_person_identity_tray.get_tray_context()

		self.assertEqual(result["page_name"], "operational_person_identity_tray")
		self.assertTrue(result["can_view"])
		self.assertTrue(result["can_execute"])
		self.assertEqual(result["manual_run_mode"], "enabled")

	def test_run_manual_reconciliation_denies_user_without_execute_permission(self):
		with patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.frappe.get_roles",
			return_value=["Gestión Humana"],
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.run_manual_person_identity_reconciliation"
		) as run_manual:
			with self.assertRaises(_FrappeError):
				operational_person_identity_tray.run_manual_reconciliation(
					"snapshot-123",
					"MANUAL:snapshot-123",
				)

		run_manual.assert_not_called()

	def test_run_manual_reconciliation_requires_explicit_confirmation(self):
		with patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.frappe.get_roles",
			return_value=["System Manager"],
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.resolve_operational_person_identity_manual_run_enabled",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.run_manual_person_identity_reconciliation"
		) as run_manual:
			with self.assertRaises(_FrappeError):
				operational_person_identity_tray.run_manual_reconciliation("snapshot-123", "confirm")

		run_manual.assert_not_called()

	def test_run_manual_reconciliation_denies_even_system_manager_when_feature_flag_is_off(self):
		with patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.frappe.get_roles",
			return_value=["System Manager"],
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.resolve_operational_person_identity_manual_run_enabled",
			return_value=False,
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.run_manual_person_identity_reconciliation"
		) as run_manual:
			with self.assertRaisesRegex(_FrappeError, "feature flag"):
				operational_person_identity_tray.run_manual_reconciliation(
					"snapshot-123",
					"MANUAL:snapshot-123",
				)

		run_manual.assert_not_called()

	def test_run_manual_reconciliation_rejects_double_submit_when_lock_exists(self):
		cache = sys.modules["frappe"]._cache
		cache.set_value(
			operational_person_identity_tray.MANUAL_RECONCILIATION_LOCK_KEY,
			{"snapshot_id": "snapshot-active", "started_by": "other@example.com"},
		)

		with patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.frappe.get_roles",
			return_value=["System Manager"],
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.resolve_operational_person_identity_manual_run_enabled",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.run_manual_person_identity_reconciliation"
		) as run_manual:
			result = operational_person_identity_tray.run_manual_reconciliation(
				"snapshot-123",
				"MANUAL:snapshot-123",
			)

		run_manual.assert_not_called()
		self.assertEqual(result["status"], "rejected_active_run")
		self.assertEqual(result["active_run"]["snapshot_id"], "snapshot-active")

	def test_run_manual_reconciliation_uses_apply_wrapper_without_preview_calls(self):
		report = {
			"status": "completed",
			"started_at": "2026-03-30T00:00:00+00:00",
			"finished_at": "2026-03-30T00:00:01+00:00",
			"counts": {"users_created": 1},
		}

		with patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.frappe.get_roles",
			return_value=["System Manager"],
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.resolve_operational_person_identity_manual_run_enabled",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.run_manual_person_identity_reconciliation",
			return_value=report,
		) as run_manual, patch(
			"hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.get_operational_person_identity_snapshot"
		) as get_snapshot, patch("hubgh.utils.run_canonical_person_identity_backfill") as backfill:
			result = operational_person_identity_tray.run_manual_reconciliation(
				"snapshot-123",
				"MANUAL:snapshot-123",
			)

		run_manual.assert_called_once_with(
			snapshot_id="snapshot-123",
			operator={"user": "runner@example.com", "roles": ["System Manager"]},
		)
		get_snapshot.assert_not_called()
		backfill.assert_not_called()
		self.assertEqual(result["status"], "completed")
		self.assertEqual(result["report"], report)
		self.assertIsNone(sys.modules["frappe"]._cache.get_value(operational_person_identity_tray.MANUAL_RECONCILIATION_LOCK_KEY))
