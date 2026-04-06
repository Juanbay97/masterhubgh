from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


_STUBBED_MODULE_NAMES = [
	"frappe",
	"frappe.model",
	"frappe.model.document",
	"frappe.utils",
	"frappe.utils.password",
	"hubgh.person_identity",
	"hubgh.hubgh.document_service",
	"hubgh.hubgh.onboarding_security",
]
_ORIGINAL_MODULES = {name: sys.modules.get(name) for name in _STUBBED_MODULE_NAMES}


def _install_frappe_stub():
	frappe_module = types.ModuleType("frappe")

	def _whitelist(*args, **kwargs):
		if args and callable(args[0]) and len(args) == 1 and not kwargs:
			return args[0]

		def _decorator(func):
			return func

		return _decorator

	frappe_module.db = SimpleNamespace(exists=lambda *args, **kwargs: False, get_value=lambda *args, **kwargs: None)
	frappe_module.get_doc = lambda *args, **kwargs: SimpleNamespace(roles=[])
	frappe_module.get_meta = lambda *args, **kwargs: None
	frappe_module.logger = lambda *args, **kwargs: SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None)
	frappe_module.whitelist = _whitelist

	utils_module = types.ModuleType("frappe.utils")
	utils_module.validate_email_address = lambda value, throw=False: True

	password_module = types.ModuleType("frappe.utils.password")
	password_module.update_password = lambda *args, **kwargs: None

	model_module = types.ModuleType("frappe.model")
	document_module = types.ModuleType("frappe.model.document")

	class Document:
		pass

	document_module.Document = Document
	model_module.document = document_module

	sys.modules["frappe"] = frappe_module
	sys.modules["frappe.utils"] = utils_module
	sys.modules["frappe.utils.password"] = password_module
	sys.modules["frappe.model"] = model_module
	sys.modules["frappe.model.document"] = document_module


def _install_support_stubs():
	person_identity_module = types.ModuleType("hubgh.person_identity")
	person_identity_module.reconcile_person_identity = lambda *args, **kwargs: SimpleNamespace(employee=None)
	sys.modules["hubgh.person_identity"] = person_identity_module

	document_service_module = types.ModuleType("hubgh.hubgh.document_service")
	document_service_module.ensure_candidate_required_documents = lambda *args, **kwargs: None
	document_service_module.set_candidate_status_from_progress = lambda *args, **kwargs: None
	sys.modules["hubgh.hubgh.document_service"] = document_service_module

	onboarding_security_module = types.ModuleType("hubgh.hubgh.onboarding_security")
	onboarding_security_module.mark_user_for_first_login_password_reset = lambda *args, **kwargs: None
	sys.modules["hubgh.hubgh.onboarding_security"] = onboarding_security_module


_install_frappe_stub()
_install_support_stubs()

candidate_states = importlib.import_module("hubgh.hubgh.candidate_states")
candidato_module = importlib.import_module("hubgh.hubgh.doctype.candidato.candidato")


def tearDownModule():
	for name, module in _ORIGINAL_MODULES.items():
		if module is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = module


class TestCandidateStatusCompatContract(TestCase):
	def test_resolve_candidate_status_prefers_canonical_when_allowed(self):
		resolved = candidate_states.resolve_candidate_status_for_storage(
			"",
			options=["En documentación", "En examen médico", "En afiliación"],
		)

		self.assertEqual(resolved, "En documentación")

	def test_resolve_candidate_status_falls_back_to_live_legacy_initial_option(self):
		resolved = candidate_states.resolve_candidate_status_for_storage(
			"",
			options=["En Proceso", "En examen médico", "En afiliación"],
		)

		self.assertEqual(resolved, "En Proceso")

	def test_resolve_candidate_status_does_not_downgrade_existing_legacy_value(self):
		resolved = candidate_states.resolve_candidate_status_for_storage(
			"Documentación Completa",
			options=["En Proceso", "Documentación Incompleta", "Documentación Completa", "En afiliación"],
		)

		self.assertEqual(resolved, "Documentación Completa")

	def test_candidato_validate_uses_storage_compatible_initial_status(self):
		doc = candidato_module.Candidato.__new__(candidato_module.Candidato)
		doc.estado_proceso = ""
		doc.primer_apellido = ""
		doc.segundo_apellido = ""
		doc.apellidos = "Compat"
		doc.numero_documento = "123"
		doc.email = "compat@example.com"
		doc.meta = SimpleNamespace(
			get_field=lambda fieldname: SimpleNamespace(options="En Proceso\nEn examen médico\nEn afiliación")
			if fieldname == "estado_proceso"
			else None
		)

		with patch.object(doc, "validate_unique_documento"), patch.object(doc, "validate_unique_email"), patch.object(
			doc,
			"autovincular_persona",
		), patch.object(doc, "validate_disponibilidad"):
			doc.validate()

		self.assertEqual(doc.estado_proceso, "En Proceso")
