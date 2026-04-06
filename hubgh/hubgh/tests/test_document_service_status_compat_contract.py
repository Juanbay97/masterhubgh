from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


_STUBBED_MODULE_NAMES = [
	"frappe",
	"frappe.utils",
	"frappe.utils.file_manager",
	"hubgh.hubgh.doctype.document_type.document_type",
	"hubgh.hubgh.people_ops_handoffs",
	"hubgh.hubgh.people_ops_policy",
	"hubgh.hubgh.role_matrix",
]
_ORIGINAL_MODULES = {name: sys.modules.get(name) for name in _STUBBED_MODULE_NAMES}


def _install_frappe_stub():
	frappe_module = types.ModuleType("frappe")
	frappe_module._ = lambda value: value
	frappe_module.db = SimpleNamespace(get_value=lambda *args, **kwargs: None, set_value=lambda *args, **kwargs: None)
	frappe_module.get_meta = lambda *args, **kwargs: SimpleNamespace(get_field=lambda fieldname: None)

	utils_module = types.ModuleType("frappe.utils")
	utils_module.now = lambda: "2026-03-31 00:00:00"

	file_manager_module = types.ModuleType("frappe.utils.file_manager")
	file_manager_module.save_file = lambda *args, **kwargs: None

	sys.modules["frappe"] = frappe_module
	sys.modules["frappe.utils"] = utils_module
	sys.modules["frappe.utils.file_manager"] = file_manager_module


def _install_support_stubs():
	document_type_module = types.ModuleType("hubgh.hubgh.doctype.document_type.document_type")
	document_type_module.get_effective_area_roles = lambda *args, **kwargs: []
	sys.modules["hubgh.hubgh.doctype.document_type.document_type"] = document_type_module

	handoffs_module = types.ModuleType("hubgh.hubgh.people_ops_handoffs")
	handoffs_module.validate_selection_to_rrll_gate = lambda *args, **kwargs: {"status": "ready", "errors": []}
	sys.modules["hubgh.hubgh.people_ops_handoffs"] = handoffs_module

	policy_module = types.ModuleType("hubgh.hubgh.people_ops_policy")
	policy_module.evaluate_dimension_access = lambda *args, **kwargs: {}
	policy_module.resolve_document_dimension = lambda *args, **kwargs: {}
	sys.modules["hubgh.hubgh.people_ops_policy"] = policy_module

	role_matrix_module = types.ModuleType("hubgh.hubgh.role_matrix")
	role_matrix_module.roles_have_any = lambda *args, **kwargs: False
	role_matrix_module.user_has_any_role = lambda *args, **kwargs: False
	sys.modules["hubgh.hubgh.role_matrix"] = role_matrix_module


_install_frappe_stub()
_install_support_stubs()

document_service = importlib.import_module("hubgh.hubgh.document_service")


def tearDownModule():
	for name, module in _ORIGINAL_MODULES.items():
		if module is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = module


class TestDocumentServiceStatusCompatContract(TestCase):
	def test_set_candidate_status_keeps_medical_exam_state(self):
		with patch("hubgh.hubgh.document_service.frappe.db.get_value", return_value="En Examen Médico"), patch(
			"hubgh.hubgh.document_service.frappe.db.set_value"
		) as set_value_mock, patch("hubgh.hubgh.document_service.get_candidate_progress") as progress_mock:
			status = document_service.set_candidate_status_from_progress("CAND-001")

		self.assertEqual(status, "En Examen Médico")
		progress_mock.assert_not_called()
		set_value_mock.assert_not_called()

	def test_set_candidate_status_uses_legacy_initial_option_when_metadata_is_legacy_only(self):
		legacy_meta = SimpleNamespace(
			get_field=lambda fieldname: SimpleNamespace(
				options="En Proceso\nEn examen médico\nEn afiliación\nContratado\nRechazado"
			)
			if fieldname == "estado_proceso"
			else None
		)
		with patch("hubgh.hubgh.document_service.frappe.db.get_value", return_value=""), patch(
			"hubgh.hubgh.document_service.frappe.get_meta",
			return_value=legacy_meta,
		), patch("hubgh.hubgh.document_service.get_candidate_progress", return_value={"is_complete": False}), patch(
			"hubgh.hubgh.document_service.frappe.db.set_value"
		) as set_value_mock:
			status = document_service.set_candidate_status_from_progress("CAND-001")

		self.assertEqual(status, "En Proceso")
		set_value_mock.assert_called_once_with(
			"Candidato",
			"CAND-001",
			"estado_proceso",
			"En Proceso",
			update_modified=False,
		)
