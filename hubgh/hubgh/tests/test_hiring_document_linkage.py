import sys
import types
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch


_ORIGINAL_MODULES = {name: sys.modules.get(name) for name in [
	"frappe",
	"frappe.utils",
	"frappe.utils.file_manager",
	"hubgh.hubgh.candidate_states",
	"hubgh.hubgh.doctype.document_type.document_type",
	"hubgh.hubgh.people_ops_handoffs",
	"hubgh.hubgh.people_ops_policy",
	"hubgh.hubgh.role_matrix",
	"hubgh.hubgh.selection_document_types",
]}


def _install_stubs():
	frappe_module = types.ModuleType("frappe")
	frappe_module.db = SimpleNamespace(exists=lambda *args, **kwargs: False, get_value=lambda *args, **kwargs: None, set_value=lambda *args, **kwargs: None)
	frappe_module.session = SimpleNamespace(user="rrll@example.com")
	frappe_module.get_doc = lambda *args, **kwargs: None
	frappe_module.get_all = lambda *args, **kwargs: []
	frappe_module.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))
	frappe_module._ = lambda value: value
	frappe_module.get_site_path = lambda *parts: "/tmp/" + "/".join(parts)
	frappe_module.generate_hash = lambda length=6: "ABC123"
	sys.modules["frappe"] = frappe_module

	frappe_utils = types.ModuleType("frappe.utils")
	frappe_utils.now = lambda: "2026-04-01 10:00:00"
	sys.modules["frappe.utils"] = frappe_utils

	frappe_file_manager = types.ModuleType("frappe.utils.file_manager")
	frappe_file_manager.save_file = lambda *args, **kwargs: SimpleNamespace(file_url="/private/files/test.zip")
	sys.modules["frappe.utils.file_manager"] = frappe_file_manager

	candidate_states = types.ModuleType("hubgh.hubgh.candidate_states")
	candidate_states.STATE_AFILIACION = "Afiliación"
	candidate_states.STATE_CONTRATADO = "Contratado"
	candidate_states.STATE_DOCUMENTACION = "Documentación"
	candidate_states.STATE_EXAMEN_MEDICO = "En Examen Médico"
	candidate_states.STATE_LISTO_CONTRATAR = "Listo para Contratar"
	candidate_states.get_candidate_status_options = lambda *args, **kwargs: []
	candidate_states.is_candidate_status = lambda current, *states: current in states
	candidate_states.resolve_candidate_status_for_storage = lambda value, **kwargs: value
	sys.modules["hubgh.hubgh.candidate_states"] = candidate_states

	doc_type_module = types.ModuleType("hubgh.hubgh.doctype.document_type.document_type")
	doc_type_module.get_effective_area_roles = lambda role: [role]
	sys.modules["hubgh.hubgh.doctype.document_type.document_type"] = doc_type_module

	handoffs_module = types.ModuleType("hubgh.hubgh.people_ops_handoffs")
	handoffs_module.validate_selection_to_rrll_gate = lambda payload: {"status": "ready", "errors": []}
	sys.modules["hubgh.hubgh.people_ops_handoffs"] = handoffs_module

	policy_module = types.ModuleType("hubgh.hubgh.people_ops_policy")
	policy_module.evaluate_dimension_access = lambda *args, **kwargs: True
	policy_module.resolve_document_dimension = lambda *args, **kwargs: "general"
	sys.modules["hubgh.hubgh.people_ops_policy"] = policy_module

	role_matrix_module = types.ModuleType("hubgh.hubgh.role_matrix")
	role_matrix_module.roles_have_any = lambda *args, **kwargs: False
	role_matrix_module.user_has_any_role = lambda *args, **kwargs: True
	sys.modules["hubgh.hubgh.role_matrix"] = role_matrix_module

	selection_module = types.ModuleType("hubgh.hubgh.selection_document_types")
	selection_module.canonicalize_selection_document_name = lambda value: value
	sys.modules["hubgh.hubgh.selection_document_types"] = selection_module


_install_stubs()

from hubgh.hubgh import document_service


def tearDownModule():
	sys.modules.pop("hubgh.hubgh.document_service", None)
	for name, original in _ORIGINAL_MODULES.items():
		if original is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = original


class _Doc(SimpleNamespace):
	def get(self, fieldname, default=None):
		return getattr(self, fieldname, default)


class TestHiringDocumentLinkage(TestCase):
	def test_hire_candidate_sets_employee_origin_and_syncs_banking_fields(self):
		candidate = _Doc(
			name="CAND-001",
			estado_proceso="Listo para Contratar",
			persona="EMP-001",
			nombres="Ana",
			apellidos="Paz",
			numero_documento="1001",
			pdv_destino="PDV-1",
			cargo_postulado="Cargo",
			fecha_tentativa_ingreso="2026-04-01",
			email="ana@example.com",
			banco_siesa="1059",
			tipo_cuenta_bancaria="Ahorros",
			numero_cuenta_bancaria="123456",
			eps_siesa="EPS-1",
			afp_siesa="AFP-1",
			cesantias_siesa="CES-1",
			ccf_siesa="CCF-1",
		)
		employee = _Doc(name="EMP-001", email="", banco_siesa="", tipo_cuenta_bancaria="", numero_cuenta_bancaria="", eps_siesa="", afp_siesa="", cesantias_siesa="", ccf_siesa="", candidato_origen="")
		employee.save = Mock()
		datos = _Doc(name="DC-001", ficha_empleado=None, contrato=None)
		datos.save = Mock()
		person_doc = _Doc(name="PD-001", employee=None)
		person_doc.save = Mock()

		def _get_doc(doctype, name=None):
			if doctype == "Candidato":
				return candidate
			if doctype == "Ficha Empleado":
				return employee
			if doctype == "Datos Contratacion":
				return datos
			if doctype == "Person Document":
				return person_doc
			raise AssertionError((doctype, name))

		def _get_value(doctype, filters, fieldname=None, order_by=None):
			if doctype == "Datos Contratacion":
				return "DC-001"
			if doctype == "Contrato":
				return "CONT-001"
			return None

		with patch("hubgh.hubgh.document_service.frappe.get_doc", side_effect=_get_doc), patch(
			"hubgh.hubgh.document_service.frappe.db.exists", return_value=True
		), patch("hubgh.hubgh.document_service.frappe.db.get_value", side_effect=_get_value), patch(
			"hubgh.hubgh.document_service.frappe.get_all", return_value=[SimpleNamespace(name="PD-001")]
		), patch("hubgh.hubgh.document_service.frappe.db.set_value") as set_value_mock:
			result = document_service.hire_candidate("CAND-001")

		self.assertEqual(result, {"ok": True, "employee": "EMP-001"})
		self.assertEqual(employee.candidato_origen, "CAND-001")
		self.assertEqual(employee.banco_siesa, "1059")
		self.assertEqual(employee.numero_cuenta_bancaria, "123456")
		employee.save.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(datos.ficha_empleado, "EMP-001")
		self.assertEqual(datos.contrato, "CONT-001")
		datos.save.assert_called_once_with(ignore_permissions=True)
		person_doc.save.assert_called_once_with(ignore_permissions=True)
		set_value_mock.assert_any_call("Candidato", "CAND-001", "persona", "EMP-001")

	def test_build_employee_documents_zip_falls_back_to_candidate_by_persona(self):
		employee = _Doc(name="EMP-001", candidato_origen=None)

		with patch("hubgh.hubgh.document_service.frappe.get_doc", return_value=employee), patch(
			"hubgh.hubgh.document_service.frappe.db.get_value", return_value="CAND-001"
		), patch("hubgh.hubgh.document_service.frappe.get_all", return_value=[]), patch(
			"hubgh.hubgh.document_service._build_person_dossier",
			return_value={"vigentes": [{"document_type": "HV", "file": "/private/files/hv.pdf", "version": 1, "is_vigente": True}], "historico": []},
		) as dossier_mock, patch("hubgh.hubgh.document_service.os.path.exists", return_value=False), patch(
			"hubgh.hubgh.document_service.save_file",
			return_value=SimpleNamespace(file_url="/private/files/zip.zip"),
		):
			result = document_service.build_employee_documents_zip("EMP-001")

		self.assertEqual(result, "/private/files/zip.zip")
		dossier_mock.assert_called_once_with("Candidato", "CAND-001")
