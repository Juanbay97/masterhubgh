from __future__ import annotations

import io
import sys
import types
import zipfile
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


def _install_frappe_stub():
	frappe_module = sys.modules.get("frappe") or types.ModuleType("frappe")
	db = getattr(frappe_module, "db", types.SimpleNamespace())
	db.exists = getattr(db, "exists", lambda *args, **kwargs: False)
	db.get_value = getattr(db, "get_value", lambda *args, **kwargs: None)
	db.commit = getattr(db, "commit", lambda *args, **kwargs: None)
	frappe_module.db = db
	frappe_module.get_doc = getattr(
		frappe_module,
		"get_doc",
		lambda *args, **kwargs: SimpleNamespace(get_content=lambda: ""),
	)
	frappe_module.get_all = getattr(frappe_module, "get_all", lambda *args, **kwargs: [])
	frappe_module.enqueue = getattr(frappe_module, "enqueue", lambda *args, **kwargs: None)
	frappe_module.cache = getattr(
		frappe_module,
		"cache",
		lambda: SimpleNamespace(get_value=lambda *a, **k: None, set_value=lambda *a, **k: None),
	)
	frappe_module.throw = getattr(frappe_module, "throw", lambda message: (_ for _ in ()).throw(Exception(message)))
	frappe_module.whitelist = getattr(frappe_module, "whitelist", lambda *args, **kwargs: (lambda fn: fn))
	frappe_module._ = getattr(frappe_module, "_", lambda value: value)
	frappe_module.session = getattr(frappe_module, "session", SimpleNamespace(user="rrll.jefe@example.com"))

	frappe_utils = sys.modules.get("frappe.utils") or types.ModuleType("frappe.utils")
	frappe_utils.getdate = getattr(frappe_utils, "getdate", lambda value: value)
	frappe_utils.validate_email_address = getattr(
		frappe_utils,
		"validate_email_address",
		lambda value, throw=False: "@" in (value or ""),
	)

	frappe_file_manager = sys.modules.get("frappe.utils.file_manager") or types.ModuleType("frappe.utils.file_manager")
	frappe_file_manager.save_file = getattr(
		frappe_file_manager,
		"save_file",
		lambda file_name, content, doctype, docname, is_private=1: SimpleNamespace(file_url=f"/private/files/{file_name}"),
	)

	document_service = sys.modules.get("hubgh.hubgh.document_service") or types.ModuleType("hubgh.hubgh.document_service")
	document_service.upload_person_document = getattr(
		document_service,
		"upload_person_document",
		lambda **kwargs: SimpleNamespace(name="PD-TEST", issue_date=None, valid_until=None, save=lambda **k: None),
	)

	role_matrix = sys.modules.get("hubgh.hubgh.role_matrix") or types.ModuleType("hubgh.hubgh.role_matrix")
	role_matrix.user_has_any_role = getattr(
		role_matrix,
		"user_has_any_role",
		lambda user, *roles: "Relaciones Laborales Jefe" in roles,
	)

	sys.modules["frappe"] = frappe_module
	sys.modules["frappe.utils"] = frappe_utils
	sys.modules["frappe.utils.file_manager"] = frappe_file_manager
	sys.modules["hubgh.hubgh.document_service"] = document_service
	sys.modules["hubgh.hubgh.role_matrix"] = role_matrix


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

	def test_start_upload_data_enqueues_background_job_and_persists_status(self):
		file_doc = SimpleNamespace(get_content=lambda: "nombre_pdv,codigo\nCentro Uno,PDV-1\n")
		cache_values = {}

		cache = SimpleNamespace(
			get_value=lambda key: cache_values.get(key),
			set_value=lambda key, value, expires_in_sec=None: cache_values.__setitem__(key, value),
		)

		with patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.get_doc", return_value=file_doc), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.cache",
			return_value=cache,
		), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.enqueue"
		) as enqueue:
			result = centro_de_datos.start_upload_data("Punto de Venta", "/private/files/puntos.csv", chunk_size=25)

		enqueue.assert_called_once()
		self.assertEqual(result["status"], "queued")
		self.assertEqual(result["total_rows"], 1)
		self.assertEqual(result["chunk_size"], 25)

	def test_upload_data_accepts_document_zip_manifest(self):
		buffer = io.BytesIO()
		with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
			archive.writestr(
				"documentos.csv",
				"cedula,document_type,archivo,issue_date,valid_until,notes\n123,Hoja de vida,documentos/hv.pdf,2026-04-01,,Carga inicial\n",
			)
			archive.writestr("documentos/hv.pdf", b"fake-pdf")
		file_doc = SimpleNamespace(get_content=lambda: buffer.getvalue())

		with patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.get_doc", return_value=file_doc), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.bulk_upload_employee_documents",
			return_value={"action": "created", "document": "PD-1"},
		) as bulk_upload, patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.commit"), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.sql",
			create=True,
		):
			res = centro_de_datos.upload_data("Documentos Empleado", "/private/files/documentos.zip")

		self.assertEqual(res["success"], 1)
		self.assertEqual(res["committed"], 1)
		self.assertEqual(res["errors"], [])
		self.assertEqual(bulk_upload.call_args.args[0]["archivo"], "documentos/hv.pdf")
		self.assertEqual(bulk_upload.call_args.args[0]["__attachment_filename"], "hv.pdf")

	def test_documental_mass_upload_requires_relaciones_laborales_jefe(self):
		with patch("hubgh.hubgh.page.centro_de_datos.centro_de_datos.user_has_any_role", return_value=False), self.assertRaisesRegex(Exception, "Jefe RRLL"):
			centro_de_datos.upload_data("Documentos Empleado", "/private/files/documentos.zip")
