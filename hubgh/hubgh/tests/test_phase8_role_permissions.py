from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.api.access import has_doc_access
from hubgh.hubgh import permissions
from hubgh.hubgh.contratacion_service import _user_is_hr, validate_rrll_authority
from hubgh.hubgh.people_ops_policy import resolve_document_dimension
from hubgh.hubgh.doctype.document_type.document_type import get_effective_area_roles
from hubgh.patches import phase8_role_normalization
from hubgh.hubgh.role_matrix import (
	ROLE_MIGRATION_CANONICAL_MAP,
	canonicalize_role,
	canonicalize_roles,
	expand_role_aliases,
	roles_have_any,
)


class TestHubghPhase8RolePermissions(FrappeTestCase):
	def test_role_catalog_has_expected_legacy_aliases(self):
		self.assertEqual(canonicalize_role("Gestion Humana"), "Gestión Humana")
		self.assertEqual(canonicalize_role("GH Gerente"), "Gerente GH")
		self.assertEqual(canonicalize_role("Selección"), "HR Selection")
		self.assertEqual(canonicalize_role("Seleccion"), "HR Selection")
		self.assertEqual(canonicalize_role("Relaciones Laborales"), "HR Labor Relations")
		self.assertEqual(canonicalize_role("SST"), "HR SST")
		self.assertEqual(canonicalize_role("Jefe de tienda"), "Jefe_PDV")

	def test_role_alias_matrix_covers_area_roles_for_document_access(self):
		selection_effective = get_effective_area_roles("HR Selection")
		rl_effective = get_effective_area_roles("HR Labor Relations")
		sst_effective = get_effective_area_roles("HR SST")

		self.assertIn("Selección", selection_effective)
		self.assertIn("HR Selection", selection_effective)
		self.assertIn("Relaciones Laborales", rl_effective)
		self.assertIn("Relaciones Laborales Jefe", rl_effective)
		self.assertIn("SST", sst_effective)

	def test_roles_have_any_supports_aliases_for_selection_rl_and_ops(self):
		self.assertTrue(roles_have_any({"Selección"}, {"HR Selection"}))
		self.assertTrue(roles_have_any({"Relaciones Laborales"}, {"HR Labor Relations"}))
		self.assertTrue(roles_have_any({"Jefe de tienda"}, {"Jefe_PDV"}))
		self.assertFalse(roles_have_any({"Empleado"}, {"HR Selection"}))

	def test_shell_access_uses_role_aliases_to_resolve_workspace_access(self):
		with patch("hubgh.api.access.frappe.db.exists", return_value=True), patch(
			"hubgh.api.access.frappe.get_all",
			return_value=["Jefe_PDV"],
		):
			allowed = has_doc_access("Page", "mi_perfil", {"Jefe de tienda"})
		self.assertTrue(allowed)

	def test_contratacion_service_hr_check_accepts_legacy_rl_role(self):
		with patch(
			"hubgh.hubgh.contratacion_service.frappe.session",
			new=SimpleNamespace(user="legacy.rl@example.com"),
		), patch("hubgh.hubgh.role_matrix.frappe.get_roles", return_value=["Relaciones Laborales"]):
			self.assertTrue(_user_is_hr())

	def test_validate_rrll_authority_allows_rrll_alias(self):
		with patch(
			"hubgh.hubgh.contratacion_service.frappe.session",
			new=SimpleNamespace(user="legacy.rl@example.com"),
		), patch("hubgh.hubgh.role_matrix.frappe.get_roles", return_value=["Relaciones Laborales"]):
			validate_rrll_authority()

	def test_validate_rrll_authority_denies_selection_role(self):
		with patch(
			"hubgh.hubgh.contratacion_service.frappe.session",
			new=SimpleNamespace(user="selection@example.com"),
		), patch("hubgh.hubgh.role_matrix.frappe.get_roles", return_value=["HR Selection"]), patch(
			"hubgh.hubgh.contratacion_service.frappe.throw",
			side_effect=RuntimeError("unauthorized-rrll"),
		):
			with self.assertRaisesRegex(RuntimeError, "unauthorized-rrll"):
				validate_rrll_authority()

	def test_permissions_rl_access_query_allows_legacy_alias(self):
		with patch("hubgh.hubgh.role_matrix.frappe.get_roles", return_value=["Relaciones Laborales"]):
			query = permissions.get_affiliation_permission_query("legacy.rl@example.com")

		self.assertEqual(query, "")

	def test_person_document_query_limits_rrll_to_candidate_records_without_dossier_role(self):
		with patch("hubgh.hubgh.role_matrix.frappe.get_roles", return_value=["HR Labor Relations"]):
			query = permissions.get_person_document_permission_query("rrll@example.com")

		self.assertEqual(query, "`tabPerson Document`.person_type = 'Candidato'")

	def test_person_document_query_grants_full_access_to_relaciones_laborales_jefe(self):
		with patch("hubgh.hubgh.role_matrix.frappe.get_roles", return_value=["Relaciones Laborales Jefe"]), patch(
			"hubgh.hubgh.permissions.frappe.db.escape",
			side_effect=lambda value: f"'{value}'",
		):
			query = permissions.get_person_document_permission_query("rrll.jefe@example.com")

		self.assertIn("`tabPerson Document`.person_type = 'Empleado'", query)
		self.assertIn("cand.estado_proceso in", query)

	def test_permissions_selection_query_allows_legacy_selection_alias(self):
		with patch("hubgh.hubgh.role_matrix.frappe.get_roles", return_value=["Selección"]):
			query = permissions.get_candidato_permission_query("legacy.selection@example.com")

		self.assertEqual(query, "")

	def test_permissions_ops_query_maps_store_manager_alias(self):
		emp = {"name": "EMP-0001", "pdv": "PDV-001"}
		with patch("hubgh.hubgh.permissions.frappe.get_roles", return_value=["Jefe de tienda"]), patch(
			"hubgh.hubgh.permissions._get_employee_by_user",
			return_value=emp,
		), patch("hubgh.hubgh.permissions.frappe.db.escape", side_effect=lambda x: f"'{x}'"):
			query = permissions.get_gh_novedad_permission_query("jefe.alias@example.com")

		self.assertEqual(query, "`tabGH Novedad`.punto = 'PDV-001'")

	def test_permissions_ops_query_employee_alias_scope_is_persona(self):
		emp = {"name": "EMP-0009", "pdv": "PDV-009"}
		with patch("hubgh.hubgh.permissions.frappe.get_roles", return_value=["Empleado"]), patch(
			"hubgh.hubgh.permissions._get_employee_by_user",
			return_value=emp,
		), patch("hubgh.hubgh.permissions.frappe.db.escape", side_effect=lambda x: f"'{x}'"):
			query = permissions.get_gh_novedad_permission_query("empleado@example.com")

		self.assertEqual(query, "`tabGH Novedad`.persona = 'EMP-0009'")

	def test_dimension_access_matrix_supports_clinical_sensitive_and_operational(self):
		with patch("hubgh.hubgh.permissions.frappe.get_roles", return_value=["HR SST"]):
			access = permissions.get_user_dimension_access("sst@example.com")

		self.assertTrue(access["clinical"])
		self.assertFalse(access["sensitive"])
		self.assertTrue(access["operational"])

		with patch("hubgh.hubgh.permissions.frappe.get_roles", return_value=["Relaciones Laborales"]):
			access = permissions.get_user_dimension_access("rrll.alias@example.com")

		self.assertTrue(access["clinical"])
		self.assertTrue(access["sensitive"])
		self.assertTrue(access["operational"])

	def test_dimension_access_resolves_role_aliases_and_unknown_dimension(self):
		with patch("hubgh.hubgh.permissions.frappe.get_roles", return_value=["Jefe de tienda"]):
			self.assertTrue(permissions.user_can_access_dimension("operational", "jefe.alias@example.com"))
			self.assertTrue(permissions.user_can_access_dimension("sensitive", "jefe.alias@example.com"))
			self.assertFalse(permissions.user_can_access_dimension("clinical", "jefe.alias@example.com"))

		with patch("hubgh.hubgh.permissions.frappe.get_roles", return_value=["Empleado"]):
			self.assertFalse(permissions.user_can_access_dimension("no-existe", "empleado@example.com"))

	def test_document_dimension_matrix_classifies_clinical_sensitive_and_operational(self):
		self.assertEqual(resolve_document_dimension("Historia Clínica"), "clinical")
		self.assertEqual(resolve_document_dimension("Acta de Retiro"), "sensitive")
		self.assertEqual(resolve_document_dimension("Carta Oferta"), "operational")

	def test_migration_map_is_idempotent_source_of_truth(self):
		self.assertEqual(ROLE_MIGRATION_CANONICAL_MAP["GH_Central"], "Gestión Humana")
		self.assertEqual(ROLE_MIGRATION_CANONICAL_MAP["GH Gerente"], "Gerente GH")
		self.assertEqual(ROLE_MIGRATION_CANONICAL_MAP["Seleccion"], "HR Selection")
		self.assertEqual(ROLE_MIGRATION_CANONICAL_MAP["Relaciones Laborales"], "HR Labor Relations")
		self.assertEqual(ROLE_MIGRATION_CANONICAL_MAP["SST"], "HR SST")

	def test_expand_role_aliases_contains_canonical_and_legacy_values(self):
		aliases = expand_role_aliases("Gestión Humana")
		self.assertIn("Gestión Humana", aliases)
		self.assertIn("GH_Central", aliases)

		manager_aliases = expand_role_aliases("Gerente GH")
		self.assertIn("Gerente GH", manager_aliases)
		self.assertIn("GH Gerente", manager_aliases)

		canonical = canonicalize_roles({"GH_Central", "Selección", "Jefe de tienda"})
		self.assertIn("Gestión Humana", canonical)
		self.assertIn("HR Selection", canonical)
		self.assertIn("Jefe_PDV", canonical)

	def test_role_migration_patch_is_idempotent_for_user_assignments(self):
		existing_assignments = set()
		inserted = []

		def _exists(doctype, name_or_filters=None):
			if doctype == "Role":
				return True
			if doctype == "User":
				return name_or_filters in {"legacy.user@example.com", "Guest", "Administrator"}
			if doctype == "Has Role" and isinstance(name_or_filters, dict):
				key = (name_or_filters.get("parent"), name_or_filters.get("role"))
				return key in existing_assignments
			return False

		class _DummyDoc:
			def __init__(self, payload):
				self.payload = payload

			def insert(self, ignore_permissions=False):
				key = (self.payload["parent"], self.payload["role"])
				existing_assignments.add(key)
				inserted.append(key)

		with patch("hubgh.patches.phase8_role_normalization.frappe.db.exists", side_effect=_exists), patch(
			"hubgh.patches.phase8_role_normalization.frappe.get_all",
			return_value=["legacy.user@example.com", "Guest", "Administrator"],
		), patch(
			"hubgh.patches.phase8_role_normalization.frappe.get_doc",
			side_effect=lambda payload: _DummyDoc(payload),
		):
			phase8_role_normalization._migrate_user_role_assignments("GH_Central", "Gestión Humana")
			phase8_role_normalization._migrate_user_role_assignments("GH_Central", "Gestión Humana")

		self.assertEqual(inserted, [("legacy.user@example.com", "Gestión Humana")])
