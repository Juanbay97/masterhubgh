import sys
import types
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


_ORIGINAL_FRAPPE = sys.modules.get("frappe")


def _install_frappe_stub():
	frappe_module = types.ModuleType("frappe")
	frappe_module.db = SimpleNamespace(get_value=lambda *args, **kwargs: None)
	frappe_module.get_doc = lambda *args, **kwargs: None
	sys.modules["frappe"] = frappe_module


_install_frappe_stub()

from hubgh.hubgh.siesa_reference_matrix import ensure_social_security_reference_catalogs


def tearDownModule():
	sys.modules.pop("hubgh.hubgh.siesa_reference_matrix", None)
	if _ORIGINAL_FRAPPE is None:
		sys.modules.pop("frappe", None)
	else:
		sys.modules["frappe"] = _ORIGINAL_FRAPPE


class TestSocialSecurityCatalogSeed(TestCase):
	def test_ensure_social_security_reference_catalogs_seeds_all_fallback_rows(self):
		inserted = []

		class _Doc:
			def __init__(self, payload):
				self.payload = payload
				self.name = payload.get("code")

			def insert(self, ignore_permissions=False):
				inserted.append((self.payload, ignore_permissions))

		with patch("hubgh.hubgh.siesa_reference_matrix.frappe.db.get_value", return_value=None), patch(
			"hubgh.hubgh.siesa_reference_matrix.frappe.get_doc", side_effect=lambda payload: _Doc(payload)
		):
			ensure_social_security_reference_catalogs()

		doctypes = {payload["doctype"] for payload, _ in inserted}
		self.assertEqual(doctypes, {"Entidad EPS Siesa", "Entidad AFP Siesa", "Entidad Cesantias Siesa"})
		self.assertTrue(any(payload["description"] == "EPS SURA" for payload, _ in inserted))
		self.assertTrue(any(payload["description"] == "COLPENSIONES" for payload, _ in inserted))
		self.assertTrue(any(payload["description"] == "FONDO NACIONAL DEL AHORRO" for payload, _ in inserted))
		self.assertTrue(all(str(payload["code"]).isdigit() for payload, _ in inserted))
		self.assertTrue(any(payload["code"] == "230301" and payload["description"] == "COLPENSIONES" for payload, _ in inserted))
