import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


_ORIGINAL_MODULES = {
	name: sys.modules.get(name)
	for name in [
		"frappe",
		"frappe.utils",
		"frappe.utils.file_manager",
		"hubgh.hubgh.document_service",
		"hubgh.hubgh.role_matrix",
	]
}


def _install_stubs():
	frappe_module = types.ModuleType("frappe")
	frappe_module.whitelist = lambda *args, **kwargs: (lambda fn: fn)
	frappe_module.PermissionError = Exception
	frappe_module.session = SimpleNamespace(user="rrll@example.com")
	frappe_module.db = SimpleNamespace(get_value=lambda *args, **kwargs: None, count=lambda *args, **kwargs: 0)
	frappe_module.get_doc = lambda *args, **kwargs: None
	frappe_module.get_all = lambda *args, **kwargs: []
	frappe_module.throw = lambda msg, *args, **kwargs: (_ for _ in ()).throw(Exception(msg))
	frappe_module.get_site_path = lambda *parts: "/tmp/" + "/".join(parts)
	sys.modules["frappe"] = frappe_module

	frappe_utils = types.ModuleType("frappe.utils")
	frappe_utils.cint = lambda value=0: int(value or 0)
	frappe_utils.getdate = lambda value=None: value
	frappe_utils.now_datetime = lambda: "2026-04-06 10:00:00"
	sys.modules["frappe.utils"] = frappe_utils

	frappe_file_manager = types.ModuleType("frappe.utils.file_manager")
	frappe_file_manager.save_file = lambda *args, **kwargs: SimpleNamespace(file_url="/private/files/test.zip")
	sys.modules["frappe.utils.file_manager"] = frappe_file_manager

	document_service = types.ModuleType("hubgh.hubgh.document_service")
	document_service.build_employee_documents_zip = lambda employee: "/private/files/test.zip"
	sys.modules["hubgh.hubgh.document_service"] = document_service

	role_matrix = types.ModuleType("hubgh.hubgh.role_matrix")
	role_matrix.user_has_any_role = lambda *args, **kwargs: True
	sys.modules["hubgh.hubgh.role_matrix"] = role_matrix


_install_stubs()

from hubgh.hubgh.page.carpeta_documental_empleado import carpeta_documental_empleado


def tearDownModule():
	sys.modules.pop("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado", None)
	for name, original in _ORIGINAL_MODULES.items():
		if original is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = original


class TestCarpetaDocumentalEmpleado(TestCase):
	def test_folder_access_requires_rrll_scope_for_full_rrll_access(self):
		with patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.user_has_any_role",
			return_value=False,
		), self.assertRaisesRegex(Exception, "No autorizado"):
			carpeta_documental_empleado._validate_folder_access("EMP-001")

	def test_folder_access_allows_hr_labor_relations(self):
		with patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.user_has_any_role",
			side_effect=lambda user, *roles: "HR Labor Relations" in roles,
		):
			carpeta_documental_empleado._validate_folder_access("EMP-001")

	def test_employee_rows_supports_retired_filter(self):
		captured = {}

		def fake_get_all(doctype, **kwargs):
			captured.update(kwargs)
			return []

		with patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe.get_all",
			side_effect=fake_get_all,
		):
			carpeta_documental_empleado._employee_rows(employment_status="retired")

		self.assertEqual(captured["filters"]["estado"], "Retirado")

	def test_persona_documento_legacy_placeholder_is_excluded(self):
		rows = [
			SimpleNamespace(name="LEG-IGNORE", tipo_documento="Carpeta", archivo="/files/folder.pdf", estado_documento="Vigente", modified="2026-04-01 08:00:00", owner="legacy@example.com"),
			SimpleNamespace(name="LEG-KEEP", tipo_documento="Hoja de vida", archivo="/files/hv.pdf", estado_documento="Vigente", modified="2026-04-01 09:00:00", owner="legacy@example.com"),
		]

		with patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe.get_all",
			return_value=rows,
		):
			items = carpeta_documental_empleado._persona_documento_documents("EMP-001")

		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["document_type"], "Hoja de vida")

	def test_dedupes_duplicate_file_between_person_document_and_legacy_sources(self):
		emp = SimpleNamespace(name="EMP-001", nombres="Ana", apellidos="Paz", cedula="1001", pdv="PDV-1")
		person_doc = SimpleNamespace(
			name="PD-001",
			document_type="Hoja de vida",
			status="Subido",
			file="/files/shared.pdf",
			uploaded_by="rrll@example.com",
			uploaded_on="2026-04-05 09:00:00",
			approved_by=None,
			approved_on=None,
			notes=None,
			issue_date=None,
			valid_until=None,
			modified="2026-04-05 09:00:00",
		)
		legacy_doc = carpeta_documental_empleado._mk_folder_item(
			"selection_rrll_documents",
			"Hoja de vida",
			file_url="/files/shared.pdf",
			uploaded_on="2026-04-04 09:00:00",
			uploaded_by="legacy@example.com",
			source_doctype="Persona Documento",
			source_name="LEG-001",
		)

		with patch("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._validate_folder_access"), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe.get_doc",
			return_value=emp,
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._required_document_types",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._collect_employee_and_candidate_person_docs",
			return_value=[person_doc],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._persona_documento_documents",
			return_value=[legacy_doc],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._contract_documents",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._sst_documents",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._disciplinary_documents",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._employee_required_summary",
			return_value={"total_required": 0, "uploaded_count": 0, "uploaded_any_count": 1, "missing_count": 0, "expired_count": 0, "progress_percent": 100},
		):
			data = carpeta_documental_empleado.get_employee_documents("EMP-001")

		self.assertEqual(len(data["selection_rrll_documents"]), 1)
		self.assertEqual(data["selection_rrll_documents"][0]["source_doctype"], "Person Document")
		self.assertEqual(data["selection_rrll_documents"][0]["file"], "/files/shared.pdf")

	def test_examen_medico_is_classified_once_in_sst_and_not_editable(self):
		emp = SimpleNamespace(name="EMP-001", nombres="Ana", apellidos="Paz", cedula="1001", pdv="PDV-1")
		exam_doc = SimpleNamespace(
			name="PD-EXAM",
			document_type="Examen Médico",
			status="Subido",
			file="/files/exam.pdf",
			uploaded_by="sst@example.com",
			uploaded_on="2026-04-05 10:00:00",
			approved_by=None,
			approved_on=None,
			notes=None,
			issue_date=None,
			valid_until=None,
			modified="2026-04-05 10:00:00",
		)
		process_exam = carpeta_documental_empleado._mk_folder_item(
			"sst_documents",
			"Examen Médico",
			file_url="/files/exam.pdf",
			uploaded_on="2026-04-04 10:00:00",
			uploaded_by="sst@example.com",
			source_doctype="Novedad SST",
			source_name="SST-001",
		)

		with patch("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._validate_folder_access"), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe.get_doc",
			return_value=emp,
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._required_document_types",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._collect_employee_and_candidate_person_docs",
			return_value=[exam_doc],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._persona_documento_documents",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._contract_documents",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._sst_documents",
			return_value=[process_exam],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._disciplinary_documents",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._employee_required_summary",
			return_value={"total_required": 0, "uploaded_count": 0, "uploaded_any_count": 1, "missing_count": 0, "expired_count": 0, "progress_percent": 100},
		):
			data = carpeta_documental_empleado.get_employee_documents("EMP-001")

		self.assertEqual(data["selection_rrll_documents"], [])
		self.assertEqual(len(data["sst_documents"]), 1)
		self.assertEqual(data["sst_documents"][0]["source_doctype"], "Person Document")
		self.assertFalse(data["sst_documents"][0]["is_editable"])

	def test_upload_document_blocks_process_derived_document_types(self):
		with patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._validate_folder_access"
		), self.assertRaisesRegex(Exception, "proceso origen"):
			carpeta_documental_empleado.upload_document("EMP-001", "Examen Médico", "/files/exam.pdf")

	def test_folder_js_exposes_bulk_documental_and_sst_batch_actions(self):
		js_path = Path(__file__).resolve().parents[1] / "hubgh" / "page" / "carpeta_documental_empleado" / "carpeta_documental_empleado.js"
		content = js_path.read_text(encoding="utf-8")

		self.assertIn("subir documentos masivos", content)
		self.assertIn("Documentos Empleado", content)
		self.assertIn("Estado SST Empleado", content)
		self.assertIn("template_documentos_masivos_manifest.csv", content)
		self.assertIn("template_estados_sst_opciones.csv", content)
		self.assertIn("Retirados", content)
