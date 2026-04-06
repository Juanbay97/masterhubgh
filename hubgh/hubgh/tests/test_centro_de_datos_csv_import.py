from __future__ import annotations

import sys
import types
from types import SimpleNamespace
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
			commit=lambda *args, **kwargs: None,
		),
	)
	frappe_module.get_doc = getattr(
		frappe_module,
		"get_doc",
		lambda *args, **kwargs: SimpleNamespace(get_content=lambda: ""),
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

from hubgh.hubgh.page.centro_de_datos import centro_de_datos


class TestCentroDeDatosCsvImport(TestCase):
	def test_upload_data_normalizes_utf8_bom_header_for_punto_import(self):
		file_doc = SimpleNamespace(get_content=lambda: b"\xef\xbb\xbfnombre_pdv,codigo\nCentro Uno,PDV-1\n")

		with patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.get_doc", return_value=file_doc), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.create_punto"
		) as create_punto, patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.commit"), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.sql", create=True
		):
			res = centro_de_datos.upload_data("Punto de Venta", "/private/files/puntos.csv")

		self.assertEqual(res["success"], 1)
		self.assertEqual(res["committed"], 1)
		self.assertEqual(res["errors"], [])
		self.assertEqual(create_punto.call_args.args[0]["nombre_pdv"], "Centro Uno")

	def test_upload_data_accepts_semicolon_delimiter_for_punto_import(self):
		file_doc = SimpleNamespace(get_content=lambda: "nombre_pdv;codigo\nCentro Dos;PDV-2\n")

		with patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.get_doc", return_value=file_doc), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.create_punto"
		) as create_punto, patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.commit"), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.sql", create=True
		):
			res = centro_de_datos.upload_data("Punto de Venta", "/private/files/puntos.csv")

		self.assertEqual(res["success"], 1)
		self.assertEqual(res["committed"], 1)
		self.assertEqual(res["errors"], [])
		self.assertEqual(create_punto.call_args.args[0]["codigo"], "PDV-2")

	def test_upload_data_reports_missing_expected_columns(self):
		file_doc = SimpleNamespace(get_content=lambda: "codigo,zona\nPDV-1,Norte\n")

		with patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.get_doc", return_value=file_doc), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.commit"
		), patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.sql", create=True):
			res = centro_de_datos.upload_data("Punto de Venta", "/private/files/puntos.csv")

		self.assertEqual(res["success"], 0)
		self.assertEqual(res["committed"], 0)
		self.assertEqual(len(res["errors"]), 1)
		self.assertIn("nombre_pdv", res["errors"][0])
		self.assertIn("columnas", res["errors"][0].lower())

	def test_upload_data_rolls_back_all_rows_when_any_row_fails(self):
		file_doc = SimpleNamespace(get_content=lambda: "nombre_pdv,codigo\nCentro Uno,PDV-1\nCentro Dos,PDV-2\n")
		sql_calls = []

		def fake_create(row):
			if row["codigo"] == "PDV-2":
				raise Exception("codigo duplicado")

		with patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.get_doc", return_value=file_doc), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.create_punto",
			side_effect=fake_create,
		), patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.commit") as commit_mock, patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.sql",
			side_effect=lambda query: sql_calls.append(query),
			create=True,
		):
			res = centro_de_datos.upload_data("Punto de Venta", "/private/files/puntos.csv")

		self.assertEqual(res["success"], 0)
		self.assertEqual(res["committed"], 0)
		self.assertEqual(res["errors"][0]["row"], 3)
		self.assertEqual(res["errors"][0]["code"], "row_validation")
		commit_mock.assert_not_called()
		self.assertEqual(sql_calls, ["SAVEPOINT centro_de_datos_upload", "ROLLBACK TO SAVEPOINT centro_de_datos_upload"])
