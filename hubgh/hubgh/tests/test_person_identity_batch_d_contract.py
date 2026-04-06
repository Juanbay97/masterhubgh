from __future__ import annotations

import importlib
import sys
import types
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


_STUBBED_MODULE_NAMES = [
	"frappe",
	"frappe.utils",
	"frappe.utils.password",
	"frappe.utils.file_manager",
	"frappe.utils.pdf",
	"frappe.model",
	"frappe.model.document",
	"hubgh.hubgh.document_service",
	"hubgh.hubgh.people_ops_policy",
	"hubgh.hubgh.bienestar_automation",
	"hubgh.hubgh.candidate_states",
	"hubgh.hubgh.onboarding_security",
]
_ORIGINAL_MODULES = {name: sys.modules.get(name) for name in _STUBBED_MODULE_NAMES}


def _install_frappe_stub():
	frappe_module = types.ModuleType("frappe")

	class _FrappeError(Exception):
		pass

	def _throw(message, exc=None):
		raise (exc or _FrappeError)(message)

	def _whitelist(*args, **kwargs):
		if args and callable(args[0]) and len(args) == 1 and not kwargs:
			return args[0]

		def _decorator(func):
			return func

		return _decorator

	frappe_module.ValidationError = _FrappeError
	frappe_module.PermissionError = _FrappeError
	frappe_module.DoesNotExistError = _FrappeError
	frappe_module.throw = _throw
	frappe_module.whitelist = _whitelist
	frappe_module._ = lambda value: value
	frappe_module._dict = lambda value: value
	frappe_module.session = SimpleNamespace(user="test@example.com")
	frappe_module.conf = {}
	frappe_module.defaults = SimpleNamespace(get_user_default=lambda key: None)
	frappe_module.db = SimpleNamespace(
		exists=lambda *args, **kwargs: False,
		get_value=lambda *args, **kwargs: None,
		set_value=lambda *args, **kwargs: None,
		count=lambda *args, **kwargs: 0,
		commit=lambda: None,
		escape=lambda value: repr(value),
		sql=lambda *args, **kwargs: [],
		get_single_value=lambda *args, **kwargs: "",
	)
	frappe_module.get_all = lambda *args, **kwargs: []
	frappe_module.get_roles = lambda *args, **kwargs: []
	frappe_module.get_doc = lambda *args, **kwargs: SimpleNamespace(
		insert=lambda **insert_kwargs: None,
		save=lambda **save_kwargs: None,
		append=lambda *append_args, **append_kwargs: None,
		set=lambda *set_args, **set_kwargs: None,
		roles=[],
	)
	frappe_module.logger = lambda *args, **kwargs: SimpleNamespace(
		info=lambda *a, **k: None,
		warning=lambda *a, **k: None,
		error=lambda *a, **k: None,
	)
	frappe_module.cache = lambda: SimpleNamespace(hincrby=lambda *args, **kwargs: None, hgetall=lambda *args, **kwargs: {})
	frappe_module.utils = SimpleNamespace(escape_html=lambda value: value)

	utils_module = types.ModuleType("frappe.utils")
	utils_module.add_days = lambda value, days: value + timedelta(days=days) if hasattr(value, "__add__") else value
	utils_module.add_months = lambda value, months: value
	utils_module.getdate = lambda value=None: value
	utils_module.nowdate = lambda: "2026-03-30"
	utils_module.now_datetime = lambda: datetime(2026, 3, 30, 12, 0, 0)
	utils_module.get_first_day = lambda value: value
	utils_module.get_last_day = lambda value: value
	utils_module.cstr = lambda value: "" if value is None else str(value)
	utils_module.validate_email_address = lambda value, throw=False: "@" in (value or "")

	password_module = types.ModuleType("frappe.utils.password")
	password_module.update_password = lambda *args, **kwargs: None

	file_manager_module = types.ModuleType("frappe.utils.file_manager")
	file_manager_module.save_file = lambda *args, **kwargs: SimpleNamespace(file_url="/files/test")

	pdf_module = types.ModuleType("frappe.utils.pdf")
	pdf_module.get_pdf = lambda html: html.encode("utf-8")

	model_module = types.ModuleType("frappe.model")
	document_module = types.ModuleType("frappe.model.document")

	class Document:
		pass

	document_module.Document = Document
	document_module.get_doc = lambda *args, **kwargs: SimpleNamespace()
	model_module.document = document_module
	frappe_module.model = model_module
	frappe_module.utils = utils_module

	sys.modules["frappe"] = frappe_module
	sys.modules["frappe.utils"] = utils_module
	sys.modules["frappe.utils.password"] = password_module
	sys.modules["frappe.utils.file_manager"] = file_manager_module
	sys.modules["frappe.utils.pdf"] = pdf_module
	sys.modules["frappe.model"] = model_module
	sys.modules["frappe.model.document"] = document_module


def _install_support_stubs():
	document_service_module = types.ModuleType("hubgh.hubgh.document_service")
	document_service_module.can_user_read_person_document = lambda *args, **kwargs: True
	document_service_module.move_file_to_employee_subfolder = lambda file_url, *args, **kwargs: file_url
	document_service_module.ensure_candidate_required_documents = lambda *args, **kwargs: None
	document_service_module.set_candidate_status_from_progress = lambda *args, **kwargs: None
	sys.modules["hubgh.hubgh.document_service"] = document_service_module

	people_ops_policy_module = types.ModuleType("hubgh.hubgh.people_ops_policy")
	people_ops_policy_module.DIMENSION_ROLE_MATRIX = {}
	people_ops_policy_module.evaluate_dimension_access = lambda *args, **kwargs: {"effective_allowed": True}
	people_ops_policy_module.get_user_dimension_access = lambda *args, **kwargs: {}
	people_ops_policy_module.user_can_access_dimension = lambda *args, **kwargs: True
	sys.modules["hubgh.hubgh.people_ops_policy"] = people_ops_policy_module

	bienestar_module = types.ModuleType("hubgh.hubgh.bienestar_automation")
	bienestar_module.ensure_ingreso_followups_for_employee = lambda *args, **kwargs: None
	sys.modules["hubgh.hubgh.bienestar_automation"] = bienestar_module

	candidate_states_module = types.ModuleType("hubgh.hubgh.candidate_states")
	candidate_states_module.STATE_AFILIACION = "Afiliacion"
	candidate_states_module.STATE_DOCUMENTACION = "Documentacion"
	candidate_states_module.is_candidate_status = lambda current, expected: current == expected
	candidate_states_module.normalize_candidate_status = lambda status, default=None: status or default
	sys.modules["hubgh.hubgh.candidate_states"] = candidate_states_module

	onboarding_security_module = types.ModuleType("hubgh.hubgh.onboarding_security")
	onboarding_security_module.mark_user_for_first_login_password_reset = lambda *args, **kwargs: None
	sys.modules["hubgh.hubgh.onboarding_security"] = onboarding_security_module


_install_frappe_stub()
_install_support_stubs()


def tearDownModule():
	for name, module in _ORIGINAL_MODULES.items():
		if module is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = module

from hubgh import person_identity
from hubgh.api import feed, my_profile, ops

permissions = importlib.import_module("hubgh.permissions")
user_groups = importlib.import_module("hubgh.user_groups")

integration_hooks = importlib.import_module("hubgh.lms.integration_hooks")
nested_permissions = importlib.import_module("hubgh.hubgh.permissions")
candidato_module = importlib.import_module("hubgh.hubgh.doctype.candidato.candidato")
contrato_module = importlib.import_module("hubgh.hubgh.doctype.contrato.contrato")
novedad_sst_module = importlib.import_module("hubgh.hubgh.doctype.novedad_sst.novedad_sst")
caso_disciplinario_module = importlib.import_module("hubgh.hubgh.doctype.caso_disciplinario.caso_disciplinario")


class TestPersonIdentityBatchDContract(TestCase):
	def test_my_profile_resolves_employee_via_canonical_helper(self):
		identity = person_identity.PersonIdentity("EMP-1", "USR-1", "123", "user@example.com", "employee_link")
		with patch("hubgh.api.my_profile.frappe.db.exists", return_value=True), patch(
			"hubgh.api.my_profile.resolve_employee_for_user",
			return_value=identity,
		), patch(
			"hubgh.api.my_profile.frappe.db.get_value",
			return_value={"name": "EMP-1", "cargo": "Auxiliar"},
		):
			row = my_profile._get_employee_from_user("legacy@example.com")

		self.assertEqual(row["name"], "EMP-1")

	def test_feed_resolves_employee_via_canonical_helper(self):
		identity = person_identity.PersonIdentity("EMP-2", "USR-2", "456", "user@example.com", "username")
		with patch("hubgh.api.feed.frappe.db.exists", return_value=True), patch(
			"hubgh.api.feed.resolve_employee_for_user",
			return_value=identity,
		), patch(
			"hubgh.api.feed.frappe.db.get_value",
			return_value={"name": "EMP-2", "cargo": "Supervisor"},
		):
			row = feed._get_employee_from_user("legacy@example.com")

		self.assertEqual(row["name"], "EMP-2")

	def test_ops_session_employee_uses_canonical_employee_resolution(self):
		identity = person_identity.PersonIdentity("EMP-3", "USR-3", "789", "boss@example.com", "employee_link")
		with patch("hubgh.api.ops.frappe.session", new=SimpleNamespace(user="legacy@example.com")), patch(
			"hubgh.api.ops.resolve_employee_for_user",
			return_value=identity,
		), patch(
			"hubgh.api.ops.frappe.db.get_value",
			return_value={"name": "EMP-3", "pdv": "PDV-1"},
		):
			row = ops._get_session_employee()

		self.assertEqual(row["name"], "EMP-3")

	def test_ops_lms_report_queries_enrollment_with_resolved_user(self):
		identity = person_identity.PersonIdentity("EMP-4", "USR-4", "999", "legacy@example.com", "username")
		captured_members = []

		def _fake_get_value(doctype, filters=None, fieldname=None, as_dict=False):
			if doctype == "LMS Enrollment":
				captured_members.append(filters.get("member"))
				return {"name": "ENR-1", "progress": 50}
			if doctype == "LMS Certificate":
				captured_members.append(filters.get("member"))
				return None
			return None

		with patch("hubgh.api.ops.get_lms_course_name", return_value="curso-calidad"), patch(
			"hubgh.api.ops._lms_tables_available",
			return_value=True,
		), patch("hubgh.api.ops._get_total_lecciones", return_value=10), patch(
			"hubgh.api.ops.resolve_user_for_employee",
			return_value=identity,
		), patch("hubgh.api.ops.frappe.db.exists", return_value=True), patch(
			"hubgh.api.ops.frappe.db.get_value",
			side_effect=_fake_get_value,
		), patch("hubgh.api.ops.frappe.db.count", return_value=5), patch(
			"hubgh.api.ops.run_with_lms_retry",
			side_effect=lambda operation, func, **kwargs: func(),
		), patch("hubgh.api.ops.log_lms_event"), patch("hubgh.api.ops.increment_lms_metric"):
			reporte, _ = ops._build_pdv_lms_report(
				"PDV-1",
				[{"name": "EMP-4", "nombres": "Ana", "apellidos": "Paz", "estado": "Activo", "email": "legacy@example.com"}],
			)

		self.assertEqual(captured_members, ["USR-4", "USR-4"])
		self.assertEqual(reporte[0]["estado"], "En progreso")

	def test_permissions_module_uses_canonical_employee_resolution(self):
		identity = person_identity.PersonIdentity("EMP-5", "USR-5", "123", "user@example.com", "employee_link")
		with patch("hubgh.permissions.resolve_employee_for_user", return_value=identity), patch(
			"hubgh.permissions.frappe.db.get_value",
			return_value={"name": "EMP-5", "pdv": "PDV-9"},
		):
			row = permissions._get_employee_row("legacy@example.com")

		self.assertEqual(row["name"], "EMP-5")

	def test_nested_permissions_module_uses_canonical_employee_resolution(self):
		identity = person_identity.PersonIdentity("EMP-6", "USR-6", "456", "user@example.com", "employee_link")
		with patch("hubgh.hubgh.permissions.resolve_employee_for_user", return_value=identity), patch(
			"hubgh.hubgh.permissions.frappe.db.get_value",
			return_value={"name": "EMP-6", "pdv": "PDV-10"},
		):
			row = nested_permissions._get_employee_by_user("legacy@example.com")

		self.assertEqual(row["name"], "EMP-6")

	def test_user_groups_resolves_user_from_employee_via_helper(self):
		identity = person_identity.PersonIdentity("EMP-7", "USR-7", "888", "user@example.com", "username")
		with patch("hubgh.user_groups.resolve_user_for_employee", return_value=identity):
			user = user_groups._resolve_user_from_employee_row({"name": "EMP-7", "cedula": "888"})

		self.assertEqual(user, "USR-7")

	def test_lms_integration_hook_resolves_user_via_helper(self):
		identity = person_identity.PersonIdentity("EMP-8", "USR-8", "777", "user@example.com", "employee_link")
		with patch("hubgh.lms.integration_hooks.resolve_user_for_employee", return_value=identity):
			user = integration_hooks._resolver_usuario_empleado(SimpleNamespace(name="EMP-8"))

		self.assertEqual(user, "USR-8")

	def test_candidate_autovincular_persona_uses_reconcile_helper(self):
		doc = candidato_module.Candidato.__new__(candidato_module.Candidato)
		doc.numero_documento = "1001"
		doc.email = "cand@example.com"
		doc.persona = None
		identity = person_identity.PersonIdentity("EMP-9", None, "1001", "cand@example.com", "username")

		with patch("hubgh.hubgh.doctype.candidato.candidato.reconcile_person_identity", return_value=identity):
			doc.autovincular_persona()

		self.assertEqual(doc.persona, "EMP-9")

	def test_contrato_on_submit_reconciles_identity_canonically(self):
		doc = contrato_module.Contrato.__new__(contrato_module.Contrato)
		doc.name = "CONT-1"
		doc.candidato = "CAND-1"
		doc._sync_contrato_to_datos_contratacion = lambda: None

		with patch(
			"hubgh.hubgh.doctype.contrato.contrato.finalize_hiring",
			return_value={"employee": "EMP-10", "user": "USR-10", "status": "hired"},
		) as finalize_mock:
			doc.on_submit()

		finalize_mock.assert_called_once_with(doc)

	def test_novedad_sst_retiro_uses_canonical_user_resolution(self):
		doc = novedad_sst_module.NovedadSST.__new__(novedad_sst_module.NovedadSST)
		doc.empleado = "EMP-11"
		doc.name = "NOV-001"
		doc.estado = "Cerrada"
		doc.estado_destino = "Retirado"
		doc.impacta_estado = 1
		doc.fecha_inicio = "2026-03-01"
		doc.fecha_fin = "2026-03-03"
		doc.descripcion_resumen = "Retiro SST"
		doc.descripcion = "Retiro SST"
		doc.get_impacta_estado = lambda: True
		doc.get_estado_destino = lambda: "Retirado"
		doc.get_estado_actual = lambda: "Activo"

		with patch("hubgh.hubgh.doctype.novedad_sst.novedad_sst.apply_retirement") as retirement_mock, patch(
			"hubgh.hubgh.doctype.novedad_sst.novedad_sst.getdate",
			side_effect=lambda value=None: value or "2026-03-03",
		), patch("hubgh.hubgh.doctype.novedad_sst.novedad_sst.nowdate", return_value="2026-03-03"):
			doc.apply_estado_empleado()

		retirement_mock.assert_called_once_with(
			employee="EMP-11",
			source_doctype="Novedad SST",
			source_name="NOV-001",
			retirement_date="2026-03-03",
			reason="Retiro SST",
		)

	def test_caso_disciplinario_retiro_uses_canonical_user_resolution(self):
		with patch("hubgh.hubgh.permissions.frappe.get_roles", return_value=["HR Labor Relations"]):
			self.assertEqual(nested_permissions.get_caso_disciplinario_permission_query("rrll@example.com"), "")

		with patch("hubgh.hubgh.permissions.frappe.get_roles", return_value=["Empleado"]):
			self.assertEqual(nested_permissions.get_caso_disciplinario_permission_query("empleado@example.com"), "1=0")

	def test_caso_disciplinario_has_permission_denies_non_rrll_entrypoint(self):
		doc = SimpleNamespace(empleado="EMP-12")

		with patch("hubgh.hubgh.permissions.frappe.get_roles", return_value=["HR Labor Relations"]):
			self.assertTrue(nested_permissions.caso_disciplinario_has_permission(doc, user="rrll@example.com"))

		with patch("hubgh.hubgh.permissions.frappe.get_roles", return_value=["Empleado"]):
			self.assertFalse(nested_permissions.caso_disciplinario_has_permission(doc, user="empleado@example.com"))
