# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for user_access_control.py — Batch B.1 (TDD RED → GREEN)

Covers:
  T-B.1a  block happy path — User.enabled=0, sessions cleared, blocked=True
  T-B.1b  restore happy path — User.enabled=1
  T-B.1c  Empleado sin User → {blocked: False, reason: no_user_account}
  T-B.1d  Administrator → throw
  T-B.1e  System Manager sin override_role_block → throw
  T-B.1f  System Manager con override_role_block=True → OK
  T-B.1g  clear_sessions llamado con force=True
  T-B.1h  People Ops Event publicado en block
  T-B.1i  Idempotencia — User ya disabled → already_blocked
  T-B.1j  restore sin User → no_user_account graceful
"""

from datetime import datetime
from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase
import frappe


# ---------------------------------------------------------------------------
# Module under test
# ---------------------------------------------------------------------------

from hubgh.hubgh.services.user_access_control import (
    block_user_access,
    restore_user_access,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_identity(user=None):
    identity = MagicMock()
    identity.user = user
    return identity


_BLOCK_KWARGS = dict(
    reason="terminacion_iniciada",
    source_doctype="Terminacion Contrato",
    source_name="TC-2026-001",
)

_RESTORE_KWARGS = dict(
    reason="terminacion_cancelada",
    source_doctype="Terminacion Contrato",
    source_name="TC-2026-001",
)

_FIXED_NOW = datetime(2026, 5, 22, 10, 0, 0)

# Context manager helper: patches common callsites for happy-path block
def _block_patches(user="emp@test.com", roles=None, enabled=1):
    """Returns a list of patch context managers for a standard block_user_access test."""
    from contextlib import ExitStack
    stack = ExitStack()
    identity = _make_identity(user)
    stack.enter_context(patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity))
    stack.enter_context(patch("hubgh.hubgh.services.user_access_control.frappe.get_roles", return_value=roles or []))
    stack.enter_context(patch("hubgh.hubgh.services.user_access_control.frappe.db.get_value", return_value=enabled))
    stack.enter_context(patch("hubgh.hubgh.services.user_access_control.frappe.db.set_value"))
    stack.enter_context(patch("hubgh.hubgh.services.user_access_control.clear_sessions"))
    stack.enter_context(patch("hubgh.hubgh.services.user_access_control.now_datetime", return_value=_FIXED_NOW))
    stack.enter_context(patch("hubgh.hubgh.services.user_access_control.publish_people_ops_event", return_value="POE-1"))
    return stack


# ---------------------------------------------------------------------------
# B.1a — block happy path
# ---------------------------------------------------------------------------

class TestBlockUserAccessHappyPath(FrappeTestCase):

    def test_block_sets_enabled_zero(self):
        """block_user_access debe setear User.enabled=0."""
        identity = _make_identity("emp@test.com")
        mock_set = MagicMock()
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity), \
             patch("hubgh.hubgh.services.user_access_control.frappe.get_roles", return_value=[]), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.get_value", return_value=1), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.set_value", mock_set), \
             patch("hubgh.hubgh.services.user_access_control.clear_sessions"), \
             patch("hubgh.hubgh.services.user_access_control.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.user_access_control.publish_people_ops_event", return_value="POE-1"):
            result = block_user_access("EMP-001", **_BLOCK_KWARGS)

        mock_set.assert_any_call("User", "emp@test.com", "enabled", 0)
        self.assertTrue(result["blocked"])

    def test_block_returns_user_in_result(self):
        """Resultado debe incluir user con el user name resuelto."""
        identity = _make_identity("emp@test.com")
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity), \
             patch("hubgh.hubgh.services.user_access_control.frappe.get_roles", return_value=[]), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.get_value", return_value=1), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.set_value"), \
             patch("hubgh.hubgh.services.user_access_control.clear_sessions"), \
             patch("hubgh.hubgh.services.user_access_control.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.user_access_control.publish_people_ops_event", return_value="POE-1"):
            result = block_user_access("EMP-001", **_BLOCK_KWARGS)

        self.assertEqual(result["user"], "emp@test.com")


# ---------------------------------------------------------------------------
# B.1c — Empleado sin User
# ---------------------------------------------------------------------------

class TestBlockUserNoUserAccount(FrappeTestCase):

    def test_no_user_account_returns_no_user(self):
        """Cuando el empleado no tiene User, retorna blocked=False reason=no_user_account."""
        identity = _make_identity(user=None)
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity):
            result = block_user_access("EMP-SIN-USER", **_BLOCK_KWARGS)

        self.assertFalse(result["blocked"])
        self.assertEqual(result["reason"], "no_user_account")

    def test_none_identity_returns_no_user(self):
        """resolve_user_for_employee retorna None → no_user_account."""
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=None):
            result = block_user_access("EMP-NO-IDENTITY", **_BLOCK_KWARGS)

        self.assertFalse(result["blocked"])
        self.assertEqual(result["reason"], "no_user_account")


# ---------------------------------------------------------------------------
# B.1d — Administrator throw
# ---------------------------------------------------------------------------

class TestBlockAdministratorThrow(FrappeTestCase):

    def test_administrator_throws(self):
        """Intentar bloquear Administrator debe lanzar ValidationError."""
        identity = _make_identity("Administrator")
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity):
            with self.assertRaises(frappe.exceptions.ValidationError):
                block_user_access("EMP-ADMIN", **_BLOCK_KWARGS)


# ---------------------------------------------------------------------------
# B.1e — System Manager sin override
# ---------------------------------------------------------------------------

class TestBlockSystemManagerNoOverride(FrappeTestCase):

    def test_system_manager_without_override_throws(self):
        """System Manager sin override_role_block→throw."""
        identity = _make_identity("sysmanager@test.com")
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity), \
             patch("hubgh.hubgh.services.user_access_control.frappe.get_roles", return_value=["System Manager"]):
            with self.assertRaises(frappe.exceptions.ValidationError):
                block_user_access("EMP-SYSMANAGER", **_BLOCK_KWARGS, override_role_block=False)


# ---------------------------------------------------------------------------
# B.1f — System Manager con override
# ---------------------------------------------------------------------------

class TestBlockSystemManagerWithOverride(FrappeTestCase):

    def test_system_manager_with_override_ok(self):
        """System Manager con override_role_block=True → procede sin error."""
        identity = _make_identity("sysmanager@test.com")
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity), \
             patch("hubgh.hubgh.services.user_access_control.frappe.get_roles", return_value=["System Manager"]), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.get_value", return_value=1), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.set_value"), \
             patch("hubgh.hubgh.services.user_access_control.clear_sessions"), \
             patch("hubgh.hubgh.services.user_access_control.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.user_access_control.publish_people_ops_event", return_value="POE-1"):
            result = block_user_access("EMP-SYSMANAGER", **_BLOCK_KWARGS, override_role_block=True)

        self.assertTrue(result["blocked"])


# ---------------------------------------------------------------------------
# B.1g — clear_sessions called
# ---------------------------------------------------------------------------

class TestBlockSessionsDeleted(FrappeTestCase):

    def test_clear_sessions_called_with_force(self):
        """clear_sessions(user, force=True) debe invocarse."""
        identity = _make_identity("emp@test.com")
        mock_clear = MagicMock()
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity), \
             patch("hubgh.hubgh.services.user_access_control.frappe.get_roles", return_value=[]), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.get_value", return_value=1), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.set_value"), \
             patch("hubgh.hubgh.services.user_access_control.clear_sessions", mock_clear), \
             patch("hubgh.hubgh.services.user_access_control.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.user_access_control.publish_people_ops_event", return_value="POE-1"):
            block_user_access("EMP-001", **_BLOCK_KWARGS)

        mock_clear.assert_called_once_with("emp@test.com", force=True)


# ---------------------------------------------------------------------------
# B.1h — People Ops Event published
# ---------------------------------------------------------------------------

class TestBlockPeopleOpsEvent(FrappeTestCase):

    def test_people_ops_event_published_taxonomy(self):
        """People Ops Event con taxonomy rrll.acceso.bloqueado debe publicarse."""
        identity = _make_identity("emp@test.com")
        mock_publish = MagicMock(return_value="POE-1")
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity), \
             patch("hubgh.hubgh.services.user_access_control.frappe.get_roles", return_value=[]), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.get_value", return_value=1), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.set_value"), \
             patch("hubgh.hubgh.services.user_access_control.clear_sessions"), \
             patch("hubgh.hubgh.services.user_access_control.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.user_access_control.publish_people_ops_event", mock_publish):
            block_user_access("EMP-001", **_BLOCK_KWARGS)

        mock_publish.assert_called_once()
        payload = mock_publish.call_args[0][0]
        self.assertIn("rrll.acceso.bloqueado", payload["taxonomy"])


# ---------------------------------------------------------------------------
# B.1i — Idempotence (second block)
# ---------------------------------------------------------------------------

class TestBlockIdempotence(FrappeTestCase):

    def test_already_blocked_returns_already_blocked(self):
        """Si User.enabled=0, segundo block retorna already_blocked sin re-bloquear."""
        identity = _make_identity("emp@test.com")
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity), \
             patch("hubgh.hubgh.services.user_access_control.frappe.get_roles", return_value=[]), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.get_value", return_value=0):
            result = block_user_access("EMP-001", **_BLOCK_KWARGS)

        self.assertFalse(result["blocked"])
        self.assertEqual(result["reason"], "already_blocked")


# ---------------------------------------------------------------------------
# B.1b — restore happy path
# ---------------------------------------------------------------------------

class TestRestoreUserAccessHappyPath(FrappeTestCase):

    def test_restore_sets_enabled_one(self):
        """restore_user_access debe setear User.enabled=1."""
        identity = _make_identity("emp@test.com")
        mock_set = MagicMock()
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity), \
             patch("hubgh.hubgh.services.user_access_control.frappe.db.set_value", mock_set), \
             patch("hubgh.hubgh.services.user_access_control.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.user_access_control.publish_people_ops_event", return_value="POE-2"):
            result = restore_user_access("EMP-001", **_RESTORE_KWARGS)

        mock_set.assert_any_call("User", "emp@test.com", "enabled", 1)
        self.assertTrue(result["restored"])


# ---------------------------------------------------------------------------
# B.1j — restore sin User
# ---------------------------------------------------------------------------

class TestRestoreNoUser(FrappeTestCase):

    def test_restore_no_user_account_graceful(self):
        """Restore sin User retorna restored=False, reason=no_user_account."""
        identity = _make_identity(user=None)
        with patch("hubgh.hubgh.services.user_access_control.resolve_user_for_employee", return_value=identity):
            result = restore_user_access("EMP-SIN-USER", **_RESTORE_KWARGS)

        self.assertFalse(result["restored"])
        self.assertEqual(result["reason"], "no_user_account")
