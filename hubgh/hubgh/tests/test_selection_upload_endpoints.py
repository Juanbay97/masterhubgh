import sys
import types
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


_ORIGINAL_MODULES = {
	name: sys.modules.get(name)
	for name in [
		"frappe",
		"frappe.utils",
		"hubgh.hubgh.candidate_states",
		"hubgh.hubgh.document_service",
		"hubgh.hubgh.permissions",
		"hubgh.hubgh.selection_document_types",
	]
}


def _install_stubs():
	frappe_module = types.ModuleType("frappe")
	frappe_module.whitelist = lambda *args, **kwargs: (lambda fn: fn)
	frappe_module.session = SimpleNamespace(user="selection@example.com")
	frappe_module.local = SimpleNamespace(message_log=["stale warning"])
	frappe_module.db = SimpleNamespace(get_value=lambda *args, **kwargs: "666666", set_value=lambda *args, **kwargs: None, exists=lambda *args, **kwargs: True)
	frappe_module.get_doc = lambda *args, **kwargs: None
	frappe_module.get_all = lambda *args, **kwargs: []
	frappe_module.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))
	frappe_module.logger = lambda *args, **kwargs: SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None)
	sys.modules["frappe"] = frappe_module

	frappe_utils = types.ModuleType("frappe.utils")
	frappe_utils.getdate = lambda value=None: value
	frappe_utils.nowdate = lambda: "2026-04-01"
	sys.modules["frappe.utils"] = frappe_utils

	candidate_states = types.ModuleType("hubgh.hubgh.candidate_states")
	candidate_states.STATE_AFILIACION = "Afiliación"
	candidate_states.STATE_EXAMEN_MEDICO = "En Examen Médico"
	candidate_states.STATE_LISTO_CONTRATAR = "Listo para Contratar"
	candidate_states.STATE_DOCUMENTACION = "Documentación"
	candidate_states.is_candidate_status = lambda *args, **kwargs: False
	sys.modules["hubgh.hubgh.candidate_states"] = candidate_states

	dimension_permissions = types.ModuleType("hubgh.hubgh.dimension_permissions")
	dimension_permissions.user_can_access_dimension = lambda *args, **kwargs: True
	sys.modules["hubgh.hubgh.dimension_permissions"] = dimension_permissions

	document_service = types.ModuleType("hubgh.hubgh.document_service")
	document_service.ensure_candidate_required_documents = lambda *args, **kwargs: None
	document_service.build_candidate_documents_zip = lambda *args, **kwargs: None
	document_service.get_candidate_progress = lambda *args, **kwargs: {"percent": 0, "required_ok": 0, "required_total": 0, "is_complete": False}
	document_service.hire_candidate = lambda *args, **kwargs: None
	document_service.send_candidate_to_labor_relations = lambda *args, **kwargs: None
	document_service.upload_person_document = lambda *args, **kwargs: SimpleNamespace(name="PD-001", status="Subido")
	document_service.user_has_any_role = lambda *args, **kwargs: True
	sys.modules["hubgh.hubgh.document_service"] = document_service

	permissions = types.ModuleType("hubgh.hubgh.permissions")
	permissions.user_can_access_dimension = lambda *args, **kwargs: True
	sys.modules["hubgh.hubgh.permissions"] = permissions

	selection_document_types = types.ModuleType("hubgh.hubgh.selection_document_types")
	selection_document_types.SELECTION_OPERATIONAL_DOCS = []
	selection_document_types.canonicalize_selection_document_name = lambda value: value
	selection_document_types.get_selection_document_lookup_names = lambda value: [value] if value else []
	selection_document_types.get_selection_operational_document_names = lambda: []
	sys.modules["hubgh.hubgh.selection_document_types"] = selection_document_types

_install_stubs()

from hubgh.hubgh.page.seleccion_documentos import seleccion_documentos


def tearDownModule():
	sys.modules.pop("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos", None)
	for name, original in _ORIGINAL_MODULES.items():
		if original is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = original


class TestSelectionUploadEndpoints(TestCase):
	def test_validate_selection_access_allows_gestion_humana_actor(self):
		with patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.user_has_any_role",
			side_effect=lambda user, *roles: "Gestión Humana" in roles,
		):
			seleccion_documentos._validate_selection_access()

	def test_attach_contract_allows_relaciones_laborales_jefe(self):
		with patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.user_has_any_role",
			side_effect=lambda user, *roles: "Relaciones Laborales Jefe" in roles,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.upload_person_document",
			return_value=SimpleNamespace(name="PD-003"),
		):
			result = seleccion_documentos.attach_contract("666666", "/private/files/contract.pdf")

		self.assertEqual(result, "PD-003")

	def test_upload_candidate_document_clears_stale_message_log(self):
		frappe_module = sys.modules["frappe"]
		frappe_module.local.message_log = ["No se pudo encontrar Persona: 666666"]

		with patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._validate_selection_access"
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._validate_candidate_document_type"
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.upload_person_document",
			return_value=SimpleNamespace(name="PD-001", status="Subido"),
		):
			result = seleccion_documentos.upload_candidate_document("666666", "SAGRILAFT", "/private/files/test.pdf")

		self.assertEqual(result, {"name": "PD-001", "status": "Subido"})
		self.assertEqual(frappe_module.local.message_log, [])

	def test_upload_medical_exam_document_clears_stale_message_log(self):
		frappe_module = sys.modules["frappe"]
		frappe_module.local.message_log = ["No se pudo encontrar Persona: 666666"]

		with patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._resolve_medical_document_type",
			return_value="Examen Médico",
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.upload_person_document",
			return_value=SimpleNamespace(name="PD-002", status="Subido"),
		):
			result = seleccion_documentos.upload_medical_exam_document("666666", "/private/files/test.pdf")

		self.assertEqual(result, {"name": "PD-002", "status": "Subido", "document_type": "Examen Médico"})
		self.assertEqual(frappe_module.local.message_log, [])

	def test_set_medical_concept_favorable_does_not_advance_to_affiliations(self):
		captured = {}

		def _set_value(doctype, name, values, *args, **kwargs):
			captured["doctype"] = doctype
			captured["name"] = name
			captured["values"] = values

		with patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.db.set_value", side_effect=_set_value):
			result = seleccion_documentos.set_medical_concept("666666", "Favorable")

		self.assertEqual(captured["doctype"], "Candidato")
		self.assertEqual(captured["name"], "666666")
		self.assertEqual(captured["values"]["estado_proceso"], "En Examen Médico")
		self.assertEqual(result["estado_proceso"], "En Examen Médico")
		self.assertEqual(result["next_recommended"], "send_to_labor_relations")
