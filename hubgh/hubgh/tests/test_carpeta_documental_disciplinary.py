# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt
"""
test_carpeta_documental_disciplinary.py — Phase 7 tests (T058)

Tests that _disciplinary_documents() includes all new DocType sources:
  - Caso Disciplinario (legacy, existing)
  - Afectado Disciplinario (empleado==employee) attachments
  - Citacion Disciplinaria (archivo_citacion)
  - Acta Descargos (archivo_acta)
  - Comunicado Sancion (archivo_comunicado)
  - Evidencia Disciplinaria (afectado.empleado == employee OR caso has afectado with that employee)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import frappe
from frappe.tests.utils import FrappeTestCase


class TestCarpetaDocumentalDisciplinaryLegacy(FrappeTestCase):
	"""Existing legacy source (Caso Disciplinario) still works."""

	@patch("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe")
	def test_legacy_caso_documents_still_included(self, mock_frappe):
		from hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado import _disciplinary_documents

		caso = SimpleNamespace(name="CD-001")
		file_row = SimpleNamespace(name="FILE-001", attached_to_name="CD-001", file_url="/private/files/doc.pdf", modified="2026-01-01", owner="admin")

		def get_all_side(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				return [caso]
			if doctype == "File":
				filters = kwargs.get("filters", {})
				if isinstance(filters, dict) and filters.get("attached_to_doctype") == "Caso Disciplinario":
					return [file_row]
				return []
			if doctype == "Afectado Disciplinario":
				return []
			if doctype == "Citacion Disciplinaria":
				return []
			if doctype == "Acta Descargos":
				return []
			if doctype == "Comunicado Sancion":
				return []
			if doctype == "Evidencia Disciplinaria":
				return []
			return []

		mock_frappe.get_all = MagicMock(side_effect=get_all_side)
		mock_frappe.utils = frappe.utils

		items = _disciplinary_documents("EMP-001")
		self.assertTrue(len(items) >= 1)
		urls = [i["file"] for i in items]
		self.assertIn("/private/files/doc.pdf", urls)


class TestCarpetaDocumentalAfectadoDocuments(FrappeTestCase):
	"""Attachments from Afectado Disciplinario are included."""

	@patch("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe")
	def test_afectado_files_included(self, mock_frappe):
		from hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado import _disciplinary_documents

		afectado = SimpleNamespace(name="AFE-001", empleado="EMP-001")
		file_row = SimpleNamespace(name="FILE-002", attached_to_name="AFE-001", file_url="/private/files/afe.pdf", modified="2026-02-01", owner="admin")

		def get_all_side(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				return []
			if doctype == "Afectado Disciplinario":
				return [afectado]
			if doctype == "File":
				filters = kwargs.get("filters", {})
				if isinstance(filters, dict) and filters.get("attached_to_doctype") == "Afectado Disciplinario":
					return [file_row]
				return []
			if doctype == "Citacion Disciplinaria":
				return []
			if doctype == "Acta Descargos":
				return []
			if doctype == "Comunicado Sancion":
				return []
			if doctype == "Evidencia Disciplinaria":
				return []
			return []

		mock_frappe.get_all = MagicMock(side_effect=get_all_side)

		items = _disciplinary_documents("EMP-001")
		urls = [i["file"] for i in items]
		self.assertIn("/private/files/afe.pdf", urls)


class TestCarpetaDocumentalCitacionDocuments(FrappeTestCase):
	"""Citacion Disciplinaria archivo_citacion is included."""

	@patch("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe")
	def test_citacion_archivo_included(self, mock_frappe):
		from hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado import _disciplinary_documents

		afectado = SimpleNamespace(name="AFE-001", empleado="EMP-001")
		citacion = SimpleNamespace(
			name="CIT-001",
			afectado="AFE-001",
			archivo_citacion="/private/files/citacion.pdf",
			modified="2026-03-01",
			owner="admin",
		)

		def get_all_side(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				return []
			if doctype == "Afectado Disciplinario":
				return [afectado]
			if doctype == "File":
				return []
			if doctype == "Citacion Disciplinaria":
				return [citacion]
			if doctype == "Acta Descargos":
				return []
			if doctype == "Comunicado Sancion":
				return []
			if doctype == "Evidencia Disciplinaria":
				return []
			return []

		mock_frappe.get_all = MagicMock(side_effect=get_all_side)

		items = _disciplinary_documents("EMP-001")
		urls = [i["file"] for i in items]
		self.assertIn("/private/files/citacion.pdf", urls)


class TestCarpetaDocumentalActaDocuments(FrappeTestCase):
	"""Acta Descargos archivo_acta is included."""

	@patch("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe")
	def test_acta_archivo_included(self, mock_frappe):
		from hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado import _disciplinary_documents

		afectado = SimpleNamespace(name="AFE-001", empleado="EMP-001")
		acta = SimpleNamespace(
			name="ACT-001",
			afectado="AFE-001",
			archivo_acta="/private/files/acta.pdf",
			modified="2026-04-01",
			owner="admin",
		)

		def get_all_side(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				return []
			if doctype == "Afectado Disciplinario":
				return [afectado]
			if doctype == "File":
				return []
			if doctype == "Citacion Disciplinaria":
				return []
			if doctype == "Acta Descargos":
				return [acta]
			if doctype == "Comunicado Sancion":
				return []
			if doctype == "Evidencia Disciplinaria":
				return []
			return []

		mock_frappe.get_all = MagicMock(side_effect=get_all_side)

		items = _disciplinary_documents("EMP-001")
		urls = [i["file"] for i in items]
		self.assertIn("/private/files/acta.pdf", urls)


class TestCarpetaDocumentalComunicadoDocuments(FrappeTestCase):
	"""Comunicado Sancion archivo_comunicado is included."""

	@patch("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe")
	def test_comunicado_archivo_included(self, mock_frappe):
		from hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado import _disciplinary_documents

		afectado = SimpleNamespace(name="AFE-001", empleado="EMP-001")
		comunicado = SimpleNamespace(
			name="COM-001",
			afectado="AFE-001",
			archivo_comunicado="/private/files/comunicado.pdf",
			modified="2026-04-15",
			owner="admin",
		)

		def get_all_side(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				return []
			if doctype == "Afectado Disciplinario":
				return [afectado]
			if doctype == "File":
				return []
			if doctype == "Citacion Disciplinaria":
				return []
			if doctype == "Acta Descargos":
				return []
			if doctype == "Comunicado Sancion":
				return [comunicado]
			if doctype == "Evidencia Disciplinaria":
				return []
			return []

		mock_frappe.get_all = MagicMock(side_effect=get_all_side)

		items = _disciplinary_documents("EMP-001")
		urls = [i["file"] for i in items]
		self.assertIn("/private/files/comunicado.pdf", urls)


class TestCarpetaDocumentalEvidenciaDocuments(FrappeTestCase):
	"""Evidencia Disciplinaria where afectado.empleado==employee is included."""

	@patch("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe")
	def test_evidencia_included(self, mock_frappe):
		from hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado import _disciplinary_documents

		afectado = SimpleNamespace(name="AFE-001", empleado="EMP-001")
		evidencia = SimpleNamespace(
			name="EVI-001",
			afectado="AFE-001",
			archivo="/private/files/evidencia.pdf",
			modified="2026-04-20",
			owner="admin",
		)

		def get_all_side(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				return []
			if doctype == "Afectado Disciplinario":
				return [afectado]
			if doctype == "File":
				return []
			if doctype == "Citacion Disciplinaria":
				return []
			if doctype == "Acta Descargos":
				return []
			if doctype == "Comunicado Sancion":
				return []
			if doctype == "Evidencia Disciplinaria":
				return [evidencia]
			return []

		mock_frappe.get_all = MagicMock(side_effect=get_all_side)

		items = _disciplinary_documents("EMP-001")
		urls = [i["file"] for i in items]
		self.assertIn("/private/files/evidencia.pdf", urls)


class TestCarpetaDocumentalEmptyEmployee(FrappeTestCase):
	"""Employee with no cases returns [] without error."""

	@patch("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe")
	def test_no_cases_returns_empty(self, mock_frappe):
		from hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado import _disciplinary_documents

		mock_frappe.get_all = MagicMock(return_value=[])

		items = _disciplinary_documents("EMP-NOCASE")
		self.assertEqual(items, [])


class TestCarpetaDocumentalSectionKey(FrappeTestCase):
	"""All disciplinary documents use section key '05_disciplinarios' or 'disciplinary_documents'."""

	@patch("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe")
	def test_section_key_is_disciplinary_documents(self, mock_frappe):
		from hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado import _disciplinary_documents

		caso = SimpleNamespace(name="CD-001")
		file_row = SimpleNamespace(name="FILE-001", attached_to_name="CD-001", file_url="/private/files/doc.pdf", modified="2026-01-01", owner="admin")

		def get_all_side(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				return [caso]
			if doctype == "File":
				filters = kwargs.get("filters", {})
				if isinstance(filters, dict) and filters.get("attached_to_doctype") == "Caso Disciplinario":
					return [file_row]
				return []
			if doctype in ("Afectado Disciplinario", "Citacion Disciplinaria", "Acta Descargos", "Comunicado Sancion", "Evidencia Disciplinaria"):
				return []
			return []

		mock_frappe.get_all = MagicMock(side_effect=get_all_side)

		items = _disciplinary_documents("EMP-001")
		for item in items:
			self.assertEqual(item["section_key"], "disciplinary_documents")
