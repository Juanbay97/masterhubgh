# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for token_manager: create_token, validate_token, consume_token.

Strategy (Batch 3 — GREEN):
- Functions are fully implemented.
- patch.object(frappe.db, "method") used throughout (Frappe v15 safe, no AsyncMock).
- Tests verify actual behavior: token format, expiry, used-flag logic.

REQ refs: REQ-8 (token 32-char hex, expiry 14d), REQ-10 (single-use),
          REQ-12 (expiry rejection).
"""

from datetime import datetime, timedelta
from unittest.mock import patch, call
from frappe.tests.utils import FrappeTestCase
import frappe


class TestTokenManager(FrappeTestCase):

	def _import_module(self):
		from hubgh.hubgh.examen_medico import token_manager
		return token_manager

	def test_create_token_returns_32_char_hex(self):
		"""REQ-8: create_token genera secrets.token_hex(16) → 32 chars hexadecimales."""
		token_manager = self._import_module()
		captured = {}

		def fake_set_value(doctype, name, field_or_dict, value=None, **kw):
			if isinstance(field_or_dict, dict):
				captured.update(field_or_dict)
			else:
				captured[field_or_dict] = value

		with patch.object(frappe.db, "set_value", side_effect=fake_set_value):
			result = token_manager.create_token("CEM-2026-0001", expiry_days=14)

		self.assertEqual(len(result), 32, "Token debe ser de 32 caracteres")
		self.assertTrue(all(c in "0123456789abcdef" for c in result), "Token debe ser hexadecimal")

	def test_create_token_sets_expiry_14_days_from_now(self):
		"""REQ-8: token_expira debe estar entre now+13d y now+15d."""
		token_manager = self._import_module()
		captured = {}

		def fake_set_value(doctype, name, field_or_dict, value=None, **kw):
			if isinstance(field_or_dict, dict):
				captured.update(field_or_dict)
			else:
				captured[field_or_dict] = value

		with patch.object(frappe.db, "set_value", side_effect=fake_set_value):
			token_manager.create_token("CEM-2026-0002", expiry_days=14)

		expiry = captured.get("token_expira")
		self.assertIsNotNone(expiry, "token_expira debe ser seteado")
		now = datetime.now()
		self.assertGreater(expiry, now + timedelta(days=13))
		self.assertLess(expiry, now + timedelta(days=15))

	def test_validate_expired_token_raises_validation_error(self):
		"""REQ-12: Token con token_expira en el pasado lanza ValidationError."""
		token_manager = self._import_module()
		past_expiry = datetime.now() - timedelta(days=1)

		with patch.object(frappe.db, "get_value", return_value={
			"name": "CEM-2026-0003",
			"token": "abc123abc123abc123abc123abc12312",
			"token_expira": past_expiry,
			"token_usado": 0,
		}):
			with self.assertRaises(frappe.ValidationError):
				token_manager.validate_token("abc123abc123abc123abc123abc12312")

	def test_validate_used_token_raises_validation_error(self):
		"""REQ-10: Token con token_usado=1 lanza ValidationError (single-use)."""
		token_manager = self._import_module()
		future_expiry = datetime.now() + timedelta(days=10)

		with patch.object(frappe.db, "get_value", return_value={
			"name": "CEM-2026-0004",
			"token": "def456def456def456def456def45645",
			"token_expira": future_expiry,
			"token_usado": 1,
		}):
			with self.assertRaises(frappe.ValidationError):
				token_manager.validate_token("def456def456def456def456def45645")

	def test_validate_fresh_unused_token_returns_dict(self):
		"""REQ-8: Token válido (no expirado, no usado) retorna dict de la Cita."""
		token_manager = self._import_module()
		future_expiry = datetime.now() + timedelta(days=10)
		expected = {
			"name": "CEM-2026-0005",
			"token": "ghi789ghi789ghi789ghi789ghi78978",
			"token_expira": future_expiry,
			"token_usado": 0,
		}

		with patch.object(frappe.db, "get_value", return_value=expected):
			result = token_manager.validate_token("ghi789ghi789ghi789ghi789ghi78978")

		self.assertEqual(result["name"], "CEM-2026-0005")

	def test_mark_used_flips_flag(self):
		"""REQ-10: consume_token llama frappe.db.set_value con token_usado=1."""
		token_manager = self._import_module()
		captured = {}

		def fake_set_value(doctype, name, field_or_dict, value=None, **kw):
			if isinstance(field_or_dict, dict):
				captured.update(field_or_dict)
			else:
				captured[field_or_dict] = value

		with patch.object(frappe.db, "set_value", side_effect=fake_set_value):
			token_manager.consume_token("CEM-2026-0006")

		self.assertEqual(captured.get("token_usado"), 1, "token_usado debe ser 1")
