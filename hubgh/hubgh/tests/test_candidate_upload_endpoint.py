import sys
import types
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


_ORIGINAL_MODULES = {
	name: sys.modules.get(name)
	for name in [
		"frappe",
		"hubgh.hubgh.document_service",
		"hubgh.hubgh.siesa_reference_matrix",
	]
}


def _install_stubs():
	frappe_module = types.ModuleType("frappe")
	frappe_module.whitelist = lambda *args, **kwargs: (lambda fn: fn)
	frappe_module.session = SimpleNamespace(user="candidate@example.com")
	frappe_module.local = SimpleNamespace(message_log=["stale warning"])
	frappe_module.db = SimpleNamespace(get_value=lambda *args, **kwargs: "333333", has_column=lambda *args, **kwargs: False)
	frappe_module.get_doc = lambda *args, **kwargs: None
	frappe_module.get_all = lambda *args, **kwargs: []
	frappe_module.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))
	sys.modules["frappe"] = frappe_module

	document_service_module = types.ModuleType("hubgh.hubgh.document_service")
	document_service_module.ensure_person_document = lambda *args, **kwargs: None
	document_service_module.upload_person_document = lambda *args, **kwargs: SimpleNamespace(name="PD-001", status="Subido")
	sys.modules["hubgh.hubgh.document_service"] = document_service_module

	siesa_module = types.ModuleType("hubgh.hubgh.siesa_reference_matrix")
	siesa_module.ensure_social_security_reference_catalogs = lambda: None
	sys.modules["hubgh.hubgh.siesa_reference_matrix"] = siesa_module


_install_stubs()

from hubgh.hubgh.page.mis_documentos_candidato import mis_documentos_candidato


def tearDownModule():
	sys.modules.pop("hubgh.hubgh.page.mis_documentos_candidato.mis_documentos_candidato", None)
	for name, original in _ORIGINAL_MODULES.items():
		if original is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = original


class TestCandidateUploadEndpoint(TestCase):
	def test_upload_my_document_clears_stale_message_log_after_success(self):
		frappe_module = sys.modules["frappe"]
		frappe_module.local.message_log = ["No se pudo encontrar Persona: 333333"]

		with patch(
			"hubgh.hubgh.page.mis_documentos_candidato.mis_documentos_candidato._get_my_candidate_name",
			return_value="333333",
		), patch(
			"hubgh.hubgh.page.mis_documentos_candidato.mis_documentos_candidato.upload_person_document",
			return_value=SimpleNamespace(name="PD-001", status="Subido"),
		):
			result = mis_documentos_candidato.upload_my_document(
				"2 cartas de referencias personales.",
				"/private/files/test.pdf",
			)

		self.assertEqual(result, {"name": "PD-001", "status": "Subido"})
		self.assertEqual(frappe_module.local.message_log, [])
