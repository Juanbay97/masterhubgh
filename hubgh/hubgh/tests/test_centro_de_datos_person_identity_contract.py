from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch


def _install_frappe_stub():
	frappe_module = sys.modules.get("frappe") or types.ModuleType("frappe")
	db = getattr(frappe_module, "db", types.SimpleNamespace())
	if not hasattr(db, "exists"):
		db.exists = lambda *args, **kwargs: False
	if not hasattr(db, "get_value"):
		db.get_value = lambda *args, **kwargs: None
	if not hasattr(db, "commit"):
		db.commit = lambda *args, **kwargs: None
	frappe_module.db = db
	frappe_module.new_doc = getattr(
		frappe_module,
		"new_doc",
		lambda *args, **kwargs: SimpleNamespace(insert=lambda *a, **k: None, add_roles=lambda *a, **k: None),
	)
	frappe_module.get_doc = getattr(
		frappe_module,
		"get_doc",
		lambda *args, **kwargs: SimpleNamespace(name=None, add_roles=lambda *a, **k: None),
	)
	frappe_module.logger = getattr(
		frappe_module,
		"logger",
		lambda *args, **kwargs: types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
	)
	frappe_module.throw = getattr(frappe_module, "throw", lambda message: (_ for _ in ()).throw(Exception(message)))
	frappe_module.whitelist = getattr(frappe_module, "whitelist", lambda *args, **kwargs: (lambda fn: fn))
	frappe_module._ = getattr(frappe_module, "_", lambda value: value)

	frappe_utils = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")
	frappe_utils.getdate = getattr(frappe_utils, "getdate", lambda value: value)
	frappe_utils.validate_email_address = getattr(
		frappe_utils,
		"validate_email_address",
		lambda value, throw=False: "@" in (value or ""),
	)

	sys.modules["frappe"] = frappe_module
	sys.modules["frappe.utils"] = frappe_utils


_install_frappe_stub()

from hubgh.person_identity import PersonIdentity
from hubgh.hubgh.page.centro_de_datos import centro_de_datos


class TestCentroDeDatosPersonIdentityContract(TestCase):
	def test_centro_de_datos_js_gates_identity_tray_cta_by_view_context(self):
		js_path = Path(__file__).resolve().parents[1] / "hubgh" / "page" / "centro_de_datos" / "centro_de_datos.js"
		content = js_path.read_text(encoding="utf-8")

		self.assertIn("get_tray_context", content)
		self.assertIn("if (!context.can_view)", content)
		self.assertIn("operational_person_identity_tray", content)

	def test_operational_person_identity_tray_assets_expose_basic_page_contract(self):
		base = Path(__file__).resolve().parents[1] / "hubgh" / "page" / "operational_person_identity_tray"
		centro_base = Path(__file__).resolve().parents[1] / "hubgh" / "page" / "centro_de_datos"
		json_payload = json.loads((base / "operational_person_identity_tray.json").read_text(encoding="utf-8"))
		centro_payload = json.loads((centro_base / "centro_de_datos.json").read_text(encoding="utf-8"))
		js_content = (base / "operational_person_identity_tray.js").read_text(encoding="utf-8")

		self.assertEqual(json_payload["doctype"], "Page")
		self.assertEqual(json_payload["page_name"], "operational_person_identity_tray")
		self.assertEqual(
			[row["role"] for row in json_payload["roles"]],
			[row["role"] for row in centro_payload["roles"]],
		)
		self.assertIn("get_snapshot", js_content)
		self.assertIn("generated_at", js_content)
		self.assertIn("run_manual_reconciliation", js_content)
		self.assertIn("manual_run_mode", js_content)

	def test_operational_person_identity_backend_contract_keeps_view_and_execute_separate(self):
		page_py = (
			Path(__file__).resolve().parents[1]
			/ "hubgh"
			/ "page"
			/ "operational_person_identity_tray"
			/ "operational_person_identity_tray.py"
		).read_text(encoding="utf-8")

		self.assertIn('TRAY_VIEW_ROLES = {"System Manager", "Gestión Humana"}', page_py)
		self.assertIn('MANUAL_RECONCILIATION_EXECUTE_ROLES = {"System Manager"}', page_py)
		self.assertIn('resolve_operational_person_identity_manual_run_enabled', page_py)

	def test_create_empleado_logs_pending_identity_state(self):
		employee_doc = SimpleNamespace(
			name="EMP-1",
			doctype="Ficha Empleado",
			nombres="Ana",
			apellidos="Paz",
			cedula="123",
			email="correo-invalido",
			insert=MagicMock(),
		)
		identity = PersonIdentity(
			"EMP-1",
			None,
			"123",
			"correo-invalido",
			"unresolved",
			pending=True,
			conflict_reason="invalid_or_missing_email",
			warnings=("missing_valid_email",),
		)
		logger = MagicMock()

		with patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.exists", return_value=False), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.get_value",
			return_value="PDV-1",
		), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.new_doc",
			return_value=employee_doc,
		), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.reconcile_person_identity",
			return_value=identity,
		) as reconcile, patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.logger", return_value=logger):
			centro_de_datos.create_empleado(
				{
					"cedula": "123",
					"nombres": "Ana",
					"apellidos": "Paz",
					"email": "correo-invalido",
					"cargo": "Auxiliar",
					"tipo_jornada": "Diurna",
					"estado": "Activo",
					"pdv": "Centro",
				}
			)

		reconcile.assert_called_once()
		logger.warning.assert_called_once()

	def test_create_user_infers_document_from_employee_before_creation(self):
		lookup_identity = PersonIdentity("EMP-1", None, None, "user@example.com", "email_fallback")
		created_identity = PersonIdentity("EMP-1", "user@example.com", "123", "user@example.com", "employee_link")
		user_doc = SimpleNamespace(name="user@example.com", add_roles=MagicMock())

		with patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.reconcile_person_identity",
			side_effect=[lookup_identity, created_identity],
		) as reconcile, patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos._get_employee_identity_seed",
			return_value=("123", "user@example.com"),
		), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.get_doc",
			return_value=user_doc,
		), patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.logger", return_value=MagicMock()), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.new_doc"
		) as new_doc:
			centro_de_datos.create_user({"email": "user@example.com", "first_name": "Ana", "last_name": "Paz"})

		self.assertEqual(reconcile.call_args_list[1].kwargs["employee"], "EMP-1")
		self.assertEqual(reconcile.call_args_list[1].kwargs["document"], "123")
		self.assertTrue(reconcile.call_args_list[1].kwargs["allow_create_user"])
		new_doc.assert_not_called()

	def test_create_user_raises_explicit_pending_for_invalid_email(self):
		lookup_identity = PersonIdentity("EMP-1", None, None, "correo-invalido", "unresolved")
		pending_identity = PersonIdentity(
			"EMP-1",
			None,
			"123",
			"correo-invalido",
			"unresolved",
			pending=True,
			conflict_reason="invalid_or_missing_email",
			warnings=("missing_valid_email",),
		)

		with patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.reconcile_person_identity",
			side_effect=[lookup_identity, pending_identity],
		), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos._get_employee_identity_seed",
			return_value=("123", "correo-invalido"),
		), patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.logger", return_value=MagicMock()), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.new_doc"
		) as new_doc:
			with self.assertRaisesRegex(Exception, "invalid_or_missing_email"):
				centro_de_datos.create_user({"email": "correo-invalido"})

		new_doc.assert_not_called()

	def test_create_user_rejects_non_canonical_raw_creation_without_valid_email(self):
		identity = PersonIdentity(None, None, None, "correo-invalido", "unresolved")
		logger = MagicMock()

		with patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.reconcile_person_identity",
			return_value=identity,
		), patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.logger", return_value=logger), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.new_doc"
		) as new_doc:
			with self.assertRaisesRegex(Exception, "email válido"):
				centro_de_datos.create_user({"email": "correo-invalido"})

		new_doc.assert_not_called()
		logger.warning.assert_called_once()
