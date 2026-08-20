# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — Phase 1.1: permission-independent completeness computation.

get_candidate_progress must return identical is_complete/missing/
required_total for every HR-EXT role (HR Selection, Gestión Humana,
GH - Bandeja General, Gerente GH). Uses real per-role Users + real Has Role
rows + frappe.set_user() (not mocked roles) to exercise real Frappe perms.
"""

import uuid

import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch

from hubgh.hubgh.document_service import get_candidate_progress, get_candidates_progress_bulk


HR_EXT_ROLES = ["HR Selection", "Gestión Humana", "GH - Bandeja General", "Gerente GH"]
_SLUGS = {"HR Selection": "hrsel", "Gestión Humana": "gh", "GH - Bandeja General": "ghbg", "Gerente GH": "ggh"}


def _ensure_user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc({
			"doctype": "User", "email": email, "first_name": email.split("@")[0],
			"enabled": 1, "send_welcome_email": 0,
		}).insert(ignore_permissions=True)
	frappe.db.delete("Has Role", {"parent": email})
	for role in roles:
		if frappe.db.exists("Role", role):
			frappe.get_doc({
				"doctype": "Has Role", "parent": email, "parenttype": "User",
				"parentfield": "roles", "role": role,
			}).insert(ignore_permissions=True)
	frappe.db.commit()


def _seed_candidato():
	cedula = f"DTP{uuid.uuid4().hex[:8].upper()}"
	# Pre-create the linked User so Candidato.before_insert takes the
	# "existing user" fast path and skips the activation email (this site has
	# no outgoing Email Account configured).
	user_email = f"{cedula.lower()}@example.com"
	user_doc = frappe.get_doc({
		"doctype": "User", "email": user_email, "first_name": "PermTest",
		"enabled": 1, "send_welcome_email": 0, "user_type": "Website User",
		"roles": [{"role": "Candidato"}],
	})
	user_doc.insert(ignore_permissions=True)

	doc = frappe.new_doc("Candidato")
	doc.tipo_documento = "Cedula"
	doc.numero_documento = cedula
	doc.nombres = "PermTest"
	doc.primer_apellido = doc.apellidos = "Candidato"
	doc.email = user_email
	doc.user = user_doc.name
	doc.celular = "3000000000"
	doc.direccion = "Calle Falsa 123"
	doc.ciudad = "Barranquilla"
	doc.estado_proceso = "En Proceso"
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


class TestDocumentTypeReadPermissionParity(FrappeTestCase):

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for role in HR_EXT_ROLES:
			_ensure_user(f"dtp_{_SLUGS[role]}@example.com", [role])
		cls.candidate = _seed_candidato()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	def _progress_as(self, user):
		frappe.set_user(user)
		try:
			return get_candidate_progress(self.candidate)
		finally:
			frappe.set_user("Administrator")

	def test_hr_ext_roles_match_system_manager_baseline(self):
		baseline = self._progress_as("Administrator")
		for role in HR_EXT_ROLES:
			progress = self._progress_as(f"dtp_{_SLUGS[role]}@example.com")
			self.assertEqual(progress["is_complete"], baseline["is_complete"], f"{role!r} diverged on is_complete")
			self.assertEqual(sorted(progress["missing"]), sorted(baseline["missing"]), f"{role!r} diverged on missing[]")
			self.assertEqual(
				progress["required_total"], baseline["required_total"],
				f"{role!r} saw a different required_total (catalog filtered by DocPerm)",
			)


class TestEmptyRequiredCatalogLogsWarning(FrappeTestCase):
	"""An empty required Document Type catalog must log a warning."""

	def test_get_candidate_progress_logs_warning(self):
		with (
			patch("hubgh.hubgh.document_service.frappe.get_all", return_value=[]),
			patch("hubgh.hubgh.document_service.logger") as mock_logger,
		):
			progress = get_candidate_progress("CAND-EMPTY-CATALOG")
		self.assertTrue(progress["is_complete"])
		mock_logger.warning.assert_called_once()

	def test_get_candidates_progress_bulk_logs_warning(self):
		with (
			patch("hubgh.hubgh.document_service.frappe.get_all", return_value=[]),
			patch("hubgh.hubgh.document_service.logger") as mock_logger,
		):
			result = get_candidates_progress_bulk(["CAND-EMPTY-CATALOG"])
		self.assertTrue(result["CAND-EMPTY-CATALOG"]["is_complete"])
		mock_logger.warning.assert_called_once()
