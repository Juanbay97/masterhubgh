from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.api.access import get_workspace_permission_query_conditions, workspace_has_permission
from hubgh.www_hooks import check_page_permissions


class TestWorkspaceVisibilityAndCandidateFlow(FrappeTestCase):
	def test_workspace_permission_query_conditions_filter_by_user_roles(self):
		with patch("hubgh.api.access.frappe.get_roles", return_value=["Candidato"]), patch(
			"hubgh.api.access.frappe.db.escape",
			side_effect=lambda value: f"'{value}'",
		):
			query = get_workspace_permission_query_conditions("candidate@example.com")

		self.assertIn("tabWorkspace", query)
		self.assertIn("tabHas Role", query)
		self.assertIn("'Candidato'", query)

	def test_workspace_has_permission_denies_non_matching_workspace_role(self):
		workspace = SimpleNamespace(name="Mi Perfil")
		with patch("hubgh.api.access.frappe.get_roles", return_value=["Candidato"]), patch(
			"hubgh.api.access.frappe.db.exists",
			return_value=True,
		), patch(
			"hubgh.api.access.frappe.get_all",
			return_value=["Empleado"],
		):
			allowed = workspace_has_permission(workspace, user="candidate@example.com")

		self.assertFalse(allowed)

	def test_candidate_only_generic_app_routes_redirect_to_candidate_home(self):
		frappe.local.response = {}
		with patch("hubgh.www_hooks.frappe.session", new=SimpleNamespace(user="candidate@example.com")), patch(
			"hubgh.www_hooks.frappe.request",
			new=SimpleNamespace(path="/app"),
		), patch(
			"hubgh.www_hooks.frappe.get_roles",
			return_value=["Candidato"],
		), patch(
			"hubgh.utils.frappe.get_roles",
			return_value=["Candidato"],
		):
			check_page_permissions()

		self.assertEqual(frappe.local.response.get("type"), "redirect")
		self.assertEqual(frappe.local.response.get("location"), "/app/mis_documentos_candidato")

	def test_candidate_only_allowed_page_remains_accessible(self):
		frappe.local.response = {}
		with patch("hubgh.www_hooks.frappe.session", new=SimpleNamespace(user="candidate@example.com")), patch(
			"hubgh.www_hooks.frappe.request",
			new=SimpleNamespace(path="/app/mis_documentos_candidato"),
		), patch(
			"hubgh.www_hooks.frappe.get_roles",
			return_value=["Candidato"],
		), patch(
			"hubgh.utils.frappe.get_roles",
			return_value=["Candidato"],
		):
			check_page_permissions()

		self.assertEqual(frappe.local.response, {})
