# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt
"""
test_punto_360_disciplinary.py — Phase 7 tests (T060-T061)

Tests that disciplinarios_abiertos_count in Punto 360 also counts cases where
the employee is an Afectado Disciplinario (not just Caso.empleado == emp).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPunto360DisciplinaryAfectadoCount(FrappeTestCase):
	"""T060 — disciplinarios_abiertos_count includes afectado-based cases."""

	@patch("hubgh.hubgh.page.punto_360.punto_360.frappe")
	@patch("hubgh.hubgh.page.punto_360.punto_360.evaluate_dimension_permission")
	def test_count_includes_afectados(self, mock_policy, mock_frappe):
		from hubgh.hubgh.page.punto_360.punto_360 import _count_disciplinarios_abiertos_for_pdv

		mock_policy.return_value = {"effective_allowed": True}

		# Direct Caso Disciplinario employees
		legacy_caso = SimpleNamespace(name="CD-001", tipo_falta="Grave", fecha_incidente="2026-01-01")
		# Afectado Disciplinario employees in the same PDV
		afectado_caso = SimpleNamespace(name="CD-002", tipo_falta="Leve", fecha_incidente="2026-02-01")

		empleados_pdv = ["EMP-001", "EMP-002"]

		def get_all_side(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				# Legacy query by empleado IN PDV
				return [legacy_caso]
			if doctype == "Afectado Disciplinario":
				# New query: afectados whose empleado is in PDV
				return [SimpleNamespace(name="AFE-001", caso="CD-002", empleado="EMP-002", estado="En Triage")]
			return []

		mock_frappe.get_all = MagicMock(side_effect=get_all_side)
		mock_frappe.db = MagicMock()

		count = _count_disciplinarios_abiertos_for_pdv(empleados_pdv=empleados_pdv)
		# Should count both sources: 1 legacy + 1 afectado = 2
		self.assertGreaterEqual(count, 2)

	@patch("hubgh.hubgh.page.punto_360.punto_360.frappe")
	@patch("hubgh.hubgh.page.punto_360.punto_360.evaluate_dimension_permission")
	def test_count_no_duplicates_when_same_case_both_sources(self, mock_policy, mock_frappe):
		from hubgh.hubgh.page.punto_360.punto_360 import _count_disciplinarios_abiertos_for_pdv

		mock_policy.return_value = {"effective_allowed": True}

		empleados_pdv = ["EMP-001"]

		# Same case appears both as legacy and via afectado
		caso = SimpleNamespace(name="CD-001", tipo_falta="Grave", fecha_incidente="2026-01-01")
		afectado = SimpleNamespace(name="AFE-001", caso="CD-001", empleado="EMP-001", estado="En Triage")

		def get_all_side(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				return [caso]
			if doctype == "Afectado Disciplinario":
				return [afectado]
			return []

		mock_frappe.get_all = MagicMock(side_effect=get_all_side)
		mock_frappe.db = MagicMock()

		count = _count_disciplinarios_abiertos_for_pdv(empleados_pdv=empleados_pdv)
		# Should deduplicate — same case only counted once
		self.assertEqual(count, 1)

	@patch("hubgh.hubgh.page.punto_360.punto_360.frappe")
	@patch("hubgh.hubgh.page.punto_360.punto_360.evaluate_dimension_permission")
	def test_count_zero_when_no_employees(self, mock_policy, mock_frappe):
		from hubgh.hubgh.page.punto_360.punto_360 import _count_disciplinarios_abiertos_for_pdv

		mock_policy.return_value = {"effective_allowed": True}
		mock_frappe.get_all = MagicMock(return_value=[])
		mock_frappe.db = MagicMock()

		count = _count_disciplinarios_abiertos_for_pdv(empleados_pdv=[])
		self.assertEqual(count, 0)


class TestPunto360BandejaDisciplinariaAction(FrappeTestCase):
	"""D.3 — Punto 360 must include 'Bandeja disciplinaria' quick action for RRLL users."""

	@patch("hubgh.hubgh.page.punto_360.punto_360.user_has_any_role")
	@patch("hubgh.hubgh.page.punto_360.punto_360.build_dashboard_actions")
	def test_bandeja_disciplinaria_action_present_for_rrll(self, mock_build, mock_roles):
		from hubgh.hubgh.page.punto_360.punto_360 import _build_point_contextual_actions

		def roles_side(user, *roles):
			return "HR Labor Relations" in roles or "GH - RRLL" in roles

		mock_roles.side_effect = roles_side
		mock_build.side_effect = lambda actions: actions

		sensitive_policy = {"effective_allowed": True}
		result = _build_point_contextual_actions("PDV-001", "rrll@hubgh.com", sensitive_policy)

		actions = result.get("quick_actions") or []
		keys = [a.get("key") for a in actions if isinstance(a, dict)]
		self.assertIn(
			"open_bandeja_disciplinaria", keys,
			"Punto 360 must expose 'open_bandeja_disciplinaria' quick action for RRLL"
		)

	@patch("hubgh.hubgh.page.punto_360.punto_360.user_has_any_role")
	@patch("hubgh.hubgh.page.punto_360.punto_360.build_dashboard_actions")
	def test_bandeja_disciplinaria_action_has_pdv_prefill(self, mock_build, mock_roles):
		from hubgh.hubgh.page.punto_360.punto_360 import _build_point_contextual_actions

		mock_roles.side_effect = lambda user, *roles: "HR Labor Relations" in roles or "GH - RRLL" in roles
		mock_build.side_effect = lambda actions: actions

		sensitive_policy = {"effective_allowed": True}
		result = _build_point_contextual_actions("PDV-TEST", "rrll@hubgh.com", sensitive_policy)

		actions = result.get("quick_actions") or []
		disc_action = next((a for a in actions if isinstance(a, dict) and a.get("key") == "open_bandeja_disciplinaria"), None)
		self.assertIsNotNone(disc_action, "Bandeja disciplinaria action missing")
		prefill = disc_action.get("prefill") or {}
		self.assertEqual(prefill.get("pdv"), "PDV-TEST", "Bandeja action must prefill pdv")
