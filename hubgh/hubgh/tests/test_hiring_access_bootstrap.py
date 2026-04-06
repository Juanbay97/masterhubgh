import sys
import types
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch


_ORIGINAL_MODULES = {name: sys.modules.get(name) for name in [
	"frappe",
	"frappe.utils",
	"hubgh.access_profiles",
	"hubgh.person_identity",
	"hubgh.user_groups",
	"hubgh.hubgh.bienestar_automation",
]}


def _install_stubs():
	frappe_module = types.ModuleType("frappe")
	frappe_module.db = SimpleNamespace(get_value=lambda *args, **kwargs: None, set_value=lambda *args, **kwargs: None, exists=lambda *args, **kwargs: True)
	frappe_module.get_doc = lambda *args, **kwargs: None
	frappe_module.get_all = lambda *args, **kwargs: []
	frappe_module.throw = lambda msg: (_ for _ in ()).throw(Exception(msg))
	sys.modules["frappe"] = frappe_module

	frappe_utils = types.ModuleType("frappe.utils")
	frappe_utils.cstr = lambda value=None: "" if value is None else str(value)
	frappe_utils.getdate = lambda value=None: value
	frappe_utils.nowdate = lambda: "2026-04-01"
	sys.modules["frappe.utils"] = frappe_utils

	access_profiles = types.ModuleType("hubgh.access_profiles")
	access_profiles.ensure_roles_and_profiles = lambda: None
	sys.modules["hubgh.access_profiles"] = access_profiles

	person_identity = types.ModuleType("hubgh.person_identity")
	person_identity.reconcile_person_identity = lambda *args, **kwargs: SimpleNamespace(user="candidate@example.com")
	person_identity.resolve_user_for_employee = lambda *args, **kwargs: SimpleNamespace(user="candidate@example.com")
	sys.modules["hubgh.person_identity"] = person_identity

	user_groups = types.ModuleType("hubgh.user_groups")
	user_groups.ensure_contextual_groups = lambda *args, **kwargs: None
	user_groups.sync_all_user_groups = lambda *args, **kwargs: None
	sys.modules["hubgh.user_groups"] = user_groups

	bienestar = types.ModuleType("hubgh.hubgh.bienestar_automation")
	bienestar.ensure_ingreso_followups_for_employee = lambda *args, **kwargs: None
	sys.modules["hubgh.hubgh.bienestar_automation"] = bienestar


_install_stubs()

from hubgh.hubgh import people_ops_lifecycle


def tearDownModule():
	sys.modules.pop("hubgh.hubgh.people_ops_lifecycle", None)
	for name, original in _ORIGINAL_MODULES.items():
		if original is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = original


class _Contract(SimpleNamespace):
	def db_set(self, fieldname, value):
		setattr(self, fieldname, value)


class _Employee(SimpleNamespace):
	def save(self, ignore_permissions=False):
		self._saved = ignore_permissions


class TestHiringAccessBootstrap(TestCase):
	def test_finalize_hiring_bootstraps_profiles_and_context_groups(self):
		contract = _Contract(
			candidato="CAND-001",
			numero_documento="1001",
			email="candidate@example.com",
			nombres="Ana",
			apellidos="Paz",
			pdv_destino="202",
			cargo="Cargo",
			fecha_ingreso="2026-04-15",
			name="CONT-001",
		)
		contract._ensure_employee = Mock(return_value="EMP-001")
		employee = _Employee(name="EMP-001", estado="Inactivo", pdv="", cargo="", email="")

		with patch("hubgh.hubgh.people_ops_lifecycle.ensure_roles_and_profiles") as ensure_profiles_mock, patch(
			"hubgh.hubgh.people_ops_lifecycle.ensure_contextual_groups"
		) as ensure_groups_mock, patch("hubgh.hubgh.people_ops_lifecycle.sync_all_user_groups") as sync_groups_mock, patch(
			"hubgh.hubgh.people_ops_lifecycle.reconcile_person_identity",
			return_value=SimpleNamespace(user="candidate@example.com"),
		), patch("hubgh.hubgh.people_ops_lifecycle._promote_user_to_employee"), patch(
			"hubgh.hubgh.people_ops_lifecycle.frappe.get_doc",
			return_value=employee,
		), patch("hubgh.hubgh.people_ops_lifecycle.frappe.db.get_value", side_effect=[None, "Bogota", "Bogota"]), patch(
			"hubgh.hubgh.people_ops_lifecycle.frappe.db.set_value"
		), patch("hubgh.hubgh.people_ops_lifecycle._ensure_employee_document_folder"), patch(
			"hubgh.hubgh.people_ops_lifecycle.ensure_ingreso_followups_for_employee"
		):
			result = people_ops_lifecycle.finalize_hiring(contract)

		self.assertEqual(result["employee"], "EMP-001")
		ensure_profiles_mock.assert_called()
		ensure_groups_mock.assert_any_call(pdv_name="202", city="Bogota")
		sync_groups_mock.assert_called()
