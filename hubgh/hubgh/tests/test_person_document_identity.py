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
	frappe_module.db = SimpleNamespace(
		exists=lambda *args, **kwargs: False,
		get_value=lambda *args, **kwargs: None,
		set_value=lambda *args, **kwargs: None,
	)
	frappe_module.session = SimpleNamespace(user="candidate@example.com")
	frappe_module.get_doc = lambda *args, **kwargs: None
	frappe_module.get_all = lambda *args, **kwargs: []
	frappe_module.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))
	frappe_module._ = lambda value: value
	sys.modules["frappe"] = frappe_module

	frappe_utils = types.ModuleType("frappe.utils")
	frappe_utils.now = lambda: "2026-04-01 10:00:00"
	sys.modules["frappe.utils"] = frappe_utils

	frappe_file_manager = types.ModuleType("frappe.utils.file_manager")
	frappe_file_manager.save_file = lambda *args, **kwargs: None
	sys.modules["frappe.utils.file_manager"] = frappe_file_manager

	candidate_states = types.ModuleType("hubgh.hubgh.candidate_states")
	candidate_states.STATE_AFILIACION = "Afiliación"
	candidate_states.STATE_CONTRATADO = "Contratado"
	candidate_states.STATE_DOCUMENTACION = "Documentación"
	candidate_states.STATE_EXAMEN_MEDICO = "Examen Médico"
	candidate_states.STATE_LISTO_CONTRATAR = "Listo para contratar"
	candidate_states.get_candidate_status_options = lambda *args, **kwargs: []
	candidate_states.is_candidate_status = lambda *args, **kwargs: False
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
	role_matrix_module.user_has_any_role = lambda *args, **kwargs: False
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


class TestPersonDocumentIdentity(TestCase):
	def test_can_user_read_person_document_grants_full_employee_access_only_to_rrll_jefe(self):
		doc = SimpleNamespace(person_type="Empleado", document_access=[], document_type="Contrato", person="EMP-001")
		with patch("hubgh.hubgh.document_service.user_has_any_role", side_effect=lambda user, *roles: "Relaciones Laborales Jefe" in roles), patch(
			"hubgh.hubgh.document_service.frappe.get_roles",
			return_value=[],
		), patch(
			"hubgh.hubgh.document_service._get_document_type_rules",
			return_value={"allowed_roles": []},
		), patch(
			"hubgh.hubgh.document_service.resolve_document_dimension",
			return_value="operational",
		), patch(
			"hubgh.hubgh.document_service.evaluate_dimension_access",
			return_value={"effective_allowed": False},
		):
			self.assertTrue(document_service.can_user_read_person_document(doc, user="rrll.jefe@example.com"))

	def test_can_user_read_person_document_does_not_bypass_employee_access_for_plain_rrll(self):
		doc = SimpleNamespace(person_type="Empleado", document_access=[], document_type="Contrato", person="EMP-001")
		with patch("hubgh.hubgh.document_service.user_has_any_role", return_value=False), patch(
			"hubgh.hubgh.document_service.frappe.get_roles",
			return_value=[],
		), patch(
			"hubgh.hubgh.document_service._get_document_type_rules",
			return_value={"allowed_roles": []},
		), patch(
			"hubgh.hubgh.document_service.resolve_document_dimension",
			return_value="operational",
		), patch(
			"hubgh.hubgh.document_service.evaluate_dimension_access",
			return_value={"effective_allowed": False},
		):
			self.assertFalse(document_service.can_user_read_person_document(doc, user="rrll@example.com"))

	def test_new_person_document_sets_candidate_identity_fields(self):
		captured = {}

		class _Doc:
			def insert(self, ignore_permissions=False):
				captured["insert_ignore_permissions"] = ignore_permissions

		def _get_doc(payload):
			captured["payload"] = payload
			return _Doc()

		with patch("hubgh.hubgh.document_service.frappe.get_doc", side_effect=_get_doc):
			document_service._new_person_document("Candidato", "333333", "SAGRILAFT")

		self.assertEqual(captured["payload"]["person_type"], "Candidato")
		self.assertEqual(captured["payload"]["person_doctype"], "Candidato")
		self.assertEqual(captured["payload"]["person"], "333333")
		self.assertEqual(captured["payload"]["candidate"], "333333")
		self.assertTrue(captured["insert_ignore_permissions"])

	def test_upload_person_document_repairs_candidate_identity_before_save(self):
		rules = {"document_type": "SAGRILAFT", "allows_multiple": 0, "requires_approval": 0}
		doc = SimpleNamespace(
			person_type="Candidato",
			person_doctype="Ficha Empleado",
			person="OLD-EMP",
			candidate=None,
			employee="EMP-001",
			notes=None,
			uploaded_by=None,
			uploaded_on=None,
			file=None,
			status="Pendiente",
			approved_by=None,
			approved_on=None,
		)
		doc.save = Mock()

		with patch("hubgh.hubgh.document_service._get_document_type_rules", return_value=rules), patch(
			"hubgh.hubgh.document_service.ensure_person_document", return_value=doc
		), patch("hubgh.hubgh.document_service.rename_uploaded_candidate_file", return_value="/private/files/test.pdf"), patch(
			"hubgh.hubgh.document_service.set_candidate_status_from_progress"
		), patch("hubgh.hubgh.document_service.now", return_value="2026-04-01 10:00:00"), patch(
			"hubgh.hubgh.document_service.user_has_any_role", return_value=False
		):
			result = document_service.upload_person_document(
				"Candidato",
				"333333",
				"SAGRILAFT",
				"/private/files/upload.pdf",
			)

		self.assertIs(result, doc)
		self.assertEqual(doc.person_type, "Candidato")
		self.assertEqual(doc.person_doctype, "Candidato")
		self.assertEqual(doc.person, "333333")
		self.assertEqual(doc.candidate, "333333")
		self.assertIsNone(doc.employee)
		doc.save.assert_called_once_with(ignore_permissions=True)

	def test_resolve_person_name_falls_back_to_candidate_document_number(self):
		def _exists(doctype, name=None, *args, **kwargs):
			if doctype == "Candidato" and name == "333333":
				return False
			return False

		def _get_value(doctype, filters=None, fieldname=None, *args, **kwargs):
			if doctype == "Candidato" and filters == {"numero_documento": "333333"}:
				return "CAND-0001"
			return None

		with patch("hubgh.hubgh.document_service.frappe.db.exists", side_effect=_exists), patch(
			"hubgh.hubgh.document_service.frappe.db.get_value", side_effect=_get_value
		):
			resolved = document_service._resolve_person_name("Candidato", "333333")

		self.assertEqual(resolved, "CAND-0001")

	def test_repair_person_document_links_backfills_candidate_identity(self):
		rows = [
			{
				"name": "PD-001",
				"person_type": "Candidato",
				"person": "444444",
				"person_doctype": "Ficha Empleado",
				"candidate": "CAND-0002",
				"employee": None,
			}
		]
		updates = []

		def _exists(doctype, name=None, *args, **kwargs):
			if doctype == "DocType" and name == "Person Document":
				return True
			if doctype == "Candidato" and name == "CAND-0002":
				return True
			return False

		with patch("hubgh.hubgh.document_service.frappe.db.exists", side_effect=_exists), patch(
			"hubgh.hubgh.document_service.frappe.get_all", return_value=rows
		), patch("hubgh.hubgh.document_service.frappe.db.set_value", side_effect=lambda *args, **kwargs: updates.append((args, kwargs))):
			updated = document_service.repair_person_document_links(person_type="Candidato", person="444444")

		self.assertEqual(updated, 1)
		self.assertEqual(updates[0][0][0], "Person Document")
		self.assertEqual(updates[0][0][1], "PD-001")
		self.assertEqual(
			updates[0][0][2],
			{"person": "CAND-0002", "person_doctype": "Candidato"},
		)

	def test_ensure_person_document_reuses_legacy_pending_multi_upload_row_by_document_number(self):
		rules = {
			"document_type": "2 cartas de referencias personales.",
			"allows_multiple": 1,
			"requires_approval": 0,
		}
		pending_rows = [
			{
				"name": "PD-LEGACY",
				"person": "333333",
				"candidate": "",
				"employee": "",
				"file": None,
			}
		]

		def _exists(doctype, name=None, *args, **kwargs):
			if doctype == "Candidato" and name == "CAND-0001":
				return True
			return False

		def _get_value(doctype, filters=None, fieldname=None, *args, **kwargs):
			if doctype == "Candidato" and filters == {"numero_documento": "333333"}:
				return "CAND-0001"
			if doctype == "Candidato" and filters == "CAND-0001" and fieldname == "numero_documento":
				return "333333"
			return None

		with patch("hubgh.hubgh.document_service._get_document_type_rules", return_value=rules), patch(
			"hubgh.hubgh.document_service.frappe.db.exists", side_effect=_exists
		), patch(
			"hubgh.hubgh.document_service.frappe.db.get_value", side_effect=_get_value
		), patch(
			"hubgh.hubgh.document_service.frappe.get_all", return_value=pending_rows
		), patch(
			"hubgh.hubgh.document_service.frappe.get_doc", return_value=SimpleNamespace(name="PD-LEGACY")) as get_doc_mock, patch(
			"hubgh.hubgh.document_service._new_person_document"
		) as new_doc_mock:
			doc = document_service.ensure_person_document("Candidato", "CAND-0001", "2 cartas de referencias personales.")

		self.assertEqual(doc.name, "PD-LEGACY")
		get_doc_mock.assert_called_once_with("Person Document", "PD-LEGACY")
		new_doc_mock.assert_not_called()
