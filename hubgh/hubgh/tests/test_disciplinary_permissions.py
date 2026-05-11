# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt
"""
T050 — Integration tests for disciplinary permissions and hooks.

Import convention (Frappe bench Python path):
  hubgh.hubgh.<module>        → apps/hubgh/hubgh/hubgh/<module>.py
  hubgh.hubgh.permissions     → apps/hubgh/hubgh/hubgh/permissions.py
  hubgh.hubgh.disciplinary_workflow_service → apps/hubgh/hubgh/hubgh/disciplinary_workflow_service.py
  hubgh.hubgh.hooks           → apps/hubgh/hubgh/hubgh/hooks.py   ← but hooks is in hubgh/hubgh/hooks.py
  hubgh.hooks                 → apps/hubgh/hubgh/hooks.py
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


DISCIPLINARY_DOCTYPES = [
	"Afectado Disciplinario",
	"Citacion Disciplinaria",
	"Acta Descargos",
	"Comunicado Sancion",
	"Evidencia Disciplinaria",
]

PRIVILEGED_ROLES = {"System Manager", "HR Labor Relations", "GH - RRLL", "Relaciones Laborales Jefe", "Gerente GH"}

# ---------------------------------------------------------------------------
# Helper — build a minimal fake doc
# ---------------------------------------------------------------------------


def _make_doc(doctype, name="DOC-001"):
	doc = SimpleNamespace()
	doc.doctype = doctype
	doc.name = name
	return doc


# =============================================================================
# T050-A — Permission query functions: privileged user gets "" or None
# =============================================================================


class TestDisciplinaryPermissionQueryPrivileged(FrappeTestCase):
	"""Privileged user (RRLL role) gets unrestricted query for all disciplinary DocTypes."""

	def _check_query_fn(self, fn_name, user="rrll@example.com"):
		with patch("frappe.get_roles", return_value=list(PRIVILEGED_ROLES)):
			with patch("hubgh.hubgh.permissions.user_has_any_role", return_value=True):
				mod = importlib.import_module("hubgh.hubgh.permissions")
				fn = getattr(mod, fn_name)
				result = fn(user=user)
				self.assertIn(result, ("", None), f"{fn_name} should return '' or None for privileged user, got {result!r}")

	def test_afectado_disciplinario_privileged(self):
		self._check_query_fn("get_afectado_disciplinario_permission_query")

	def test_citacion_disciplinaria_privileged(self):
		self._check_query_fn("get_citacion_disciplinaria_permission_query")

	def test_acta_descargos_privileged(self):
		self._check_query_fn("get_acta_descargos_permission_query")

	def test_comunicado_sancion_privileged(self):
		self._check_query_fn("get_comunicado_sancion_permission_query")

	def test_evidencia_disciplinaria_privileged(self):
		self._check_query_fn("get_evidencia_disciplinaria_permission_query")


# =============================================================================
# T050-B — Permission query functions: external user gets "1=0"
# =============================================================================


class TestDisciplinaryPermissionQueryExternal(FrappeTestCase):
	"""User with only Employee role gets '1=0' for all disciplinary DocTypes."""

	def _check_query_fn_blocked(self, fn_name, user="external@example.com"):
		with patch("frappe.get_roles", return_value=["Empleado", "Guest"]):
			with patch("hubgh.hubgh.permissions.user_has_any_role", return_value=False):
				mod = importlib.import_module("hubgh.hubgh.permissions")
				fn = getattr(mod, fn_name)
				result = fn(user=user)
				self.assertEqual(result, "1=0", f"{fn_name} should return '1=0' for external user, got {result!r}")

	def test_afectado_disciplinario_blocked(self):
		self._check_query_fn_blocked("get_afectado_disciplinario_permission_query")

	def test_citacion_disciplinaria_blocked(self):
		self._check_query_fn_blocked("get_citacion_disciplinaria_permission_query")

	def test_acta_descargos_blocked(self):
		self._check_query_fn_blocked("get_acta_descargos_permission_query")

	def test_comunicado_sancion_blocked(self):
		self._check_query_fn_blocked("get_comunicado_sancion_permission_query")

	def test_evidencia_disciplinaria_blocked(self):
		self._check_query_fn_blocked("get_evidencia_disciplinaria_permission_query")


# =============================================================================
# T050-C — has_permission functions: privileged and external
# =============================================================================


class TestDisciplinaryHasPermissionPrivileged(FrappeTestCase):
	"""has_permission returns True for privileged users."""

	def _check_has_perm(self, fn_name, doctype, user="rrll@example.com"):
		with patch("frappe.get_roles", return_value=list(PRIVILEGED_ROLES)):
			with patch("hubgh.hubgh.permissions.user_has_any_role", return_value=True):
				mod = importlib.import_module("hubgh.hubgh.permissions")
				fn = getattr(mod, fn_name)
				doc = _make_doc(doctype)
				result = fn(doc, user=user)
				self.assertTrue(result, f"{fn_name} should return True for privileged user")

	def test_afectado_disciplinario_has_permission(self):
		self._check_has_perm("afectado_disciplinario_has_permission", "Afectado Disciplinario")

	def test_citacion_disciplinaria_has_permission(self):
		self._check_has_perm("citacion_disciplinaria_has_permission", "Citacion Disciplinaria")

	def test_acta_descargos_has_permission(self):
		self._check_has_perm("acta_descargos_has_permission", "Acta Descargos")

	def test_comunicado_sancion_has_permission(self):
		self._check_has_perm("comunicado_sancion_has_permission", "Comunicado Sancion")

	def test_evidencia_disciplinaria_has_permission(self):
		self._check_has_perm("evidencia_disciplinaria_has_permission", "Evidencia Disciplinaria")


class TestDisciplinaryHasPermissionExternal(FrappeTestCase):
	"""has_permission returns False for external users."""

	def _check_has_perm_blocked(self, fn_name, doctype, user="external@example.com"):
		with patch("frappe.get_roles", return_value=["Empleado"]):
			with patch("hubgh.hubgh.permissions.user_has_any_role", return_value=False):
				mod = importlib.import_module("hubgh.hubgh.permissions")
				fn = getattr(mod, fn_name)
				doc = _make_doc(doctype)
				result = fn(doc, user=user)
				self.assertFalse(result, f"{fn_name} should return False for external user")

	def test_afectado_disciplinario_blocked(self):
		self._check_has_perm_blocked("afectado_disciplinario_has_permission", "Afectado Disciplinario")

	def test_citacion_disciplinaria_blocked(self):
		self._check_has_perm_blocked("citacion_disciplinaria_has_permission", "Citacion Disciplinaria")

	def test_acta_descargos_blocked(self):
		self._check_has_perm_blocked("acta_descargos_has_permission", "Acta Descargos")

	def test_comunicado_sancion_blocked(self):
		self._check_has_perm_blocked("comunicado_sancion_has_permission", "Comunicado Sancion")

	def test_evidencia_disciplinaria_blocked(self):
		self._check_has_perm_blocked("evidencia_disciplinaria_has_permission", "Evidencia Disciplinaria")


# =============================================================================
# T050-D — hooks.py registration (hubgh/hubgh/hooks.py)
# =============================================================================


class TestHooksRegistration(FrappeTestCase):
	"""hooks.py has required entries for all new DocTypes."""

	def _load_hooks(self):
		# hubgh/hubgh/hooks.py is the app-level hooks file
		return importlib.import_module("hubgh.hooks")

	def test_doc_events_afectado(self):
		hooks = self._load_hooks()
		doc_events = getattr(hooks, "doc_events", {})
		self.assertIn("Afectado Disciplinario", doc_events, "hooks.doc_events missing 'Afectado Disciplinario'")
		self.assertIn("on_update", doc_events["Afectado Disciplinario"])

	def test_doc_events_citacion(self):
		hooks = self._load_hooks()
		doc_events = getattr(hooks, "doc_events", {})
		self.assertIn("Citacion Disciplinaria", doc_events, "hooks.doc_events missing 'Citacion Disciplinaria'")
		self.assertIn("on_update", doc_events["Citacion Disciplinaria"])

	def test_doc_events_acta(self):
		hooks = self._load_hooks()
		doc_events = getattr(hooks, "doc_events", {})
		self.assertIn("Acta Descargos", doc_events, "hooks.doc_events missing 'Acta Descargos'")
		self.assertIn("on_update", doc_events["Acta Descargos"])

	def test_doc_events_comunicado(self):
		hooks = self._load_hooks()
		doc_events = getattr(hooks, "doc_events", {})
		self.assertIn("Comunicado Sancion", doc_events, "hooks.doc_events missing 'Comunicado Sancion'")
		self.assertIn("on_update", doc_events["Comunicado Sancion"])

	def test_permission_query_conditions_afectado(self):
		hooks = self._load_hooks()
		pqc = getattr(hooks, "permission_query_conditions", {})
		self.assertIn("Afectado Disciplinario", pqc)

	def test_permission_query_conditions_citacion(self):
		hooks = self._load_hooks()
		pqc = getattr(hooks, "permission_query_conditions", {})
		self.assertIn("Citacion Disciplinaria", pqc)

	def test_permission_query_conditions_acta(self):
		hooks = self._load_hooks()
		pqc = getattr(hooks, "permission_query_conditions", {})
		self.assertIn("Acta Descargos", pqc)

	def test_permission_query_conditions_comunicado(self):
		hooks = self._load_hooks()
		pqc = getattr(hooks, "permission_query_conditions", {})
		self.assertIn("Comunicado Sancion", pqc)

	def test_permission_query_conditions_evidencia(self):
		hooks = self._load_hooks()
		pqc = getattr(hooks, "permission_query_conditions", {})
		self.assertIn("Evidencia Disciplinaria", pqc)

	def test_has_permission_afectado(self):
		hooks = self._load_hooks()
		hp = getattr(hooks, "has_permission", {})
		self.assertIn("Afectado Disciplinario", hp)

	def test_has_permission_citacion(self):
		hooks = self._load_hooks()
		hp = getattr(hooks, "has_permission", {})
		self.assertIn("Citacion Disciplinaria", hp)

	def test_has_permission_acta(self):
		hooks = self._load_hooks()
		hp = getattr(hooks, "has_permission", {})
		self.assertIn("Acta Descargos", hp)

	def test_has_permission_comunicado(self):
		hooks = self._load_hooks()
		hp = getattr(hooks, "has_permission", {})
		self.assertIn("Comunicado Sancion", hp)

	def test_has_permission_evidencia(self):
		hooks = self._load_hooks()
		hp = getattr(hooks, "has_permission", {})
		self.assertIn("Evidencia Disciplinaria", hp)

	def test_scheduler_alertar_citaciones_daily(self):
		hooks = self._load_hooks()
		daily = getattr(hooks, "scheduler_events", {}).get("daily", [])
		self.assertTrue(
			any("scheduler_alertar_citaciones_vencidas" in e for e in daily),
			"scheduler_events.daily missing scheduler_alertar_citaciones_vencidas",
		)

	def test_scheduler_enviar_resumen_daily(self):
		hooks = self._load_hooks()
		daily = getattr(hooks, "scheduler_events", {}).get("daily", [])
		self.assertTrue(
			any("scheduler_enviar_resumen_rrll" in e for e in daily),
			"scheduler_events.daily missing scheduler_enviar_resumen_rrll",
		)


# =============================================================================
# T044 — scheduler_alertar_citaciones_vencidas
# =============================================================================


class TestSchedulerAlertarCitacionesVencidas(FrappeTestCase):
	"""T044 — scheduler_alertar_citaciones_vencidas() finds vencidas and logs alerts."""

	def test_returns_zero_when_no_citaciones(self):
		with patch("frappe.get_all", return_value=[]):
			from hubgh.hubgh import disciplinary_workflow_service as svc
			result = svc.scheduler_alertar_citaciones_vencidas()
			self.assertEqual(result, 0)

	def test_returns_count_of_alerts_raised(self):
		citacion = SimpleNamespace(
			name="CIT-2026-00001",
			afectado="AFE-2026-00001",
			fecha_programada_descargos="2026-01-01",
		)
		afectado_doc = MagicMock()
		afectado_doc.estado = "Citado"
		afectado_doc.transition_log = []
		afectado_doc.name = "AFE-2026-00001"

		with patch("frappe.get_all", return_value=[citacion]):
			with patch("frappe.get_doc", return_value=afectado_doc):
				with patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today", return_value="2026-04-23"):
					from hubgh.hubgh import disciplinary_workflow_service as svc
					result = svc.scheduler_alertar_citaciones_vencidas()
					self.assertEqual(result, 1)

	def test_skips_afectado_past_citado_state(self):
		"""Afectados already in 'En Descargos' or later are skipped."""
		citacion = SimpleNamespace(
			name="CIT-2026-00002",
			afectado="AFE-2026-00002",
			fecha_programada_descargos="2026-01-01",
		)
		afectado_doc = MagicMock()
		afectado_doc.estado = "En Descargos"  # already moved on
		afectado_doc.name = "AFE-2026-00002"

		with patch("frappe.get_all", return_value=[citacion]):
			with patch("frappe.get_doc", return_value=afectado_doc):
				with patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today", return_value="2026-04-23"):
					from hubgh.hubgh import disciplinary_workflow_service as svc
					result = svc.scheduler_alertar_citaciones_vencidas()
					self.assertEqual(result, 0)

	def test_appends_log_entry_to_afectado(self):
		"""A log row of type 'Alerta Citacion Vencida' is appended and doc saved."""
		citacion = SimpleNamespace(
			name="CIT-2026-00003",
			afectado="AFE-2026-00003",
			fecha_programada_descargos="2026-01-01",
		)
		afectado_doc = MagicMock()
		afectado_doc.estado = "Citado"
		afectado_doc.name = "AFE-2026-00003"
		afectado_doc.transition_log = []

		with patch("frappe.get_all", return_value=[citacion]):
			with patch("frappe.get_doc", return_value=afectado_doc):
				with patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today", return_value="2026-04-23"):
					from hubgh.hubgh import disciplinary_workflow_service as svc
					svc.scheduler_alertar_citaciones_vencidas()
					afectado_doc.append.assert_called()
					afectado_doc.save.assert_called()


# =============================================================================
# T045 — scheduler_enviar_resumen_rrll
# =============================================================================


class TestSchedulerEnviarResumenRrll(FrappeTestCase):
	"""T045 — scheduler_enviar_resumen_rrll() sends email to RRLL users."""

	# A fake pending caso to ensure total_pending > 0 in all tests
	_pending_caso = SimpleNamespace(name="CD-2026-00001", creation="2026-04-20")

	def test_falls_back_to_bienestar_email_when_no_rrll_users(self):
		"""When no RRLL users found, falls back to bienestar@homeburgers.com."""
		def mock_get_all(doctype, *args, **kwargs):
			if doctype == "Caso Disciplinario":
				return [self._pending_caso]
			return []

		with patch("frappe.get_all", side_effect=mock_get_all):
			with patch("frappe.sendmail") as mock_mail:
				with patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today", return_value="2026-04-23"):
					from hubgh.hubgh import disciplinary_workflow_service as svc
					result = svc.scheduler_enviar_resumen_rrll()
					mock_mail.assert_called_once()
					self.assertEqual(result, 1)

	def test_sends_email_to_rrll_users(self):
		rrll_user = SimpleNamespace(name="rrll@example.com")

		def mock_get_all(doctype, *args, **kwargs):
			if doctype == "Has Role":
				return [rrll_user]
			if doctype == "Caso Disciplinario":
				return [self._pending_caso]
			return []

		with patch("frappe.get_all", side_effect=mock_get_all):
			with patch("frappe.sendmail") as mock_mail:
				with patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today", return_value="2026-04-23"):
					from hubgh.hubgh import disciplinary_workflow_service as svc
					result = svc.scheduler_enviar_resumen_rrll()
					mock_mail.assert_called_once()
					self.assertGreater(result, 0)

	def test_sendmail_called_with_non_empty_subject(self):
		"""Email contains a recognizable subject."""
		rrll_user = SimpleNamespace(name="rrll@example.com")

		def mock_get_all(doctype, *args, **kwargs):
			if doctype == "Has Role":
				return [rrll_user]
			if doctype == "Caso Disciplinario":
				return [self._pending_caso]
			return []

		with patch("frappe.get_all", side_effect=mock_get_all):
			with patch("frappe.sendmail") as mock_mail:
				with patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today", return_value="2026-04-23"):
					from hubgh.hubgh import disciplinary_workflow_service as svc
					svc.scheduler_enviar_resumen_rrll()
					call_kwargs = mock_mail.call_args[1] if mock_mail.call_args else {}
					subject = call_kwargs.get("subject", "") or ""
					self.assertGreater(len(subject), 0, "Email subject should not be empty")


# =============================================================================
# T048-T049 — people_ops_policy.py — sensitivity dimensions
# =============================================================================


class TestPeopleOpsPolicySensitivity(FrappeTestCase):
	"""T048-T049 — Disciplinary DocTypes appear in DOCUMENT_SENSITIVITY_DIMENSIONS['sensitive']."""

	def _get_sensitive_set(self):
		from hubgh.hubgh.people_ops_policy import DOCUMENT_SENSITIVITY_DIMENSIONS
		return DOCUMENT_SENSITIVITY_DIMENSIONS.get("sensitive", set())

	def test_afectado_disciplinario_in_sensitive(self):
		self.assertIn("afectado disciplinario", self._get_sensitive_set())

	def test_citacion_disciplinaria_in_sensitive(self):
		self.assertIn("citacion disciplinaria", self._get_sensitive_set())

	def test_acta_descargos_in_sensitive(self):
		self.assertIn("acta descargos", self._get_sensitive_set())

	def test_comunicado_sancion_in_sensitive(self):
		self.assertIn("comunicado sancion", self._get_sensitive_set())

	def test_evidencia_disciplinaria_in_sensitive(self):
		self.assertIn("evidencia disciplinaria", self._get_sensitive_set())

	def test_recordatorio_de_funciones_in_sensitive(self):
		self.assertIn("recordatorio de funciones", self._get_sensitive_set())

	def test_existing_sensitive_docs_preserved(self):
		"""Existing entries must not be removed."""
		sensitive = self._get_sensitive_set()
		self.assertIn("caso disciplinario", sensitive)
		self.assertIn("descargo disciplinario", sensitive)
