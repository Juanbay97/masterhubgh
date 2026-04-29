# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt
"""
test_persona_360_disciplinary_projection.py — Phase 6 tests (T055-T057)

Tests for 3-level disciplinary projection in persona_360.py:
  - Full (RRLL): all fields visible
  - Sensitive (can_view_sensitive, no RRLL): redacted fields
  - External (no sensitive): only {fecha_inicio_proceso, estado_caso, conclusion_publica}
  - Self-query returns []
  - Afectado Disciplinario is the canonical source (casos arg is unused)
  - CONCLUSION_PUBLICA_MAP mappings
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import frappe
from frappe.tests.utils import FrappeTestCase


RRLL_ROLES = {"HR Labor Relations", "GH - RRLL"}


def _make_caso_doc(name="CD-001", fecha="2026-01-01", estado="En Triage", decision=None,
                   tipo_falta="Grave", descripcion="Descripción larga", resumen=""):
	return SimpleNamespace(
		name=name, fecha_incidente=fecha, estado=estado, decision_final=decision,
		tipo_falta=tipo_falta, descripcion=descripcion, hechos_narrados="Hechos",
		resumen_cierre=resumen,
	)


def _make_afectado_ns(name="AFE-001", caso="CD-001", empleado="EMP-001",
                      estado="En Triage", decision=None, resumen=""):
	return SimpleNamespace(
		name=name, caso=caso, empleado=empleado, estado=estado,
		decision_final_afectado=decision, resumen_cierre_afectado=resumen,
	)


class TestPersona360DisciplinaryProjectionFull(FrappeTestCase):
	"""T055 — RRLL user sees all fields (via Afectado as canonical source)."""

	@patch("hubgh.hubgh.page.persona_360.persona_360.user_has_any_role")
	@patch("hubgh.hubgh.page.persona_360.persona_360.frappe")
	def test_rrll_sees_full_projection(self, mock_frappe, mock_roles):
		from hubgh.hubgh.page.persona_360.persona_360 import _get_disciplinary_projection

		mock_roles.side_effect = lambda user, *roles: bool(set(roles) & RRLL_ROLES)
		caso_doc = _make_caso_doc(descripcion="Descripción larga del caso")
		mock_frappe.get_doc = MagicMock(return_value=caso_doc)

		afectados = [_make_afectado_ns()]

		result = _get_disciplinary_projection(
			casos=[],
			afectados=afectados,
			requesting_user="monica@hubgh.com",
			employee_id="EMP-001",
		)
		self.assertTrue(len(result) > 0)
		row = result[0]
		# RRLL sees all fields
		self.assertIn("tipo_falta", row)
		self.assertIn("descripcion", row)
		self.assertIn("estado", row)
		self.assertIn("name", row)
		self.assertNotEqual(row.get("descripcion"), "REDACTED")

	@patch("hubgh.hubgh.page.persona_360.persona_360.user_has_any_role")
	@patch("hubgh.hubgh.page.persona_360.persona_360.frappe")
	def test_rrll_sees_name_not_redacted(self, mock_frappe, mock_roles):
		from hubgh.hubgh.page.persona_360.persona_360 import _get_disciplinary_projection

		mock_roles.side_effect = lambda user, *roles: bool(set(roles) & RRLL_ROLES)
		caso_doc = _make_caso_doc(name="CD-002", decision="Suspensión")
		mock_frappe.get_doc = MagicMock(return_value=caso_doc)

		afectados = [_make_afectado_ns(caso="CD-002", decision="Suspensión")]

		result = _get_disciplinary_projection(
			casos=[],
			afectados=afectados,
			requesting_user="monica@hubgh.com",
			employee_id="EMP-002",
		)
		self.assertEqual(result[0]["name"], "CD-002")


class TestPersona360DisciplinaryProjectionSensitive(FrappeTestCase):
	"""T055 — Sensitive user (can_view_sensitive, no RRLL) sees redacted fields."""

	@patch("hubgh.hubgh.page.persona_360.persona_360.user_has_any_role")
	@patch("hubgh.hubgh.page.persona_360.persona_360.frappe")
	def test_sensitive_user_sees_redacted_name_and_description(self, mock_frappe, mock_roles):
		from hubgh.hubgh.page.persona_360.persona_360 import _get_disciplinary_projection

		mock_roles.side_effect = lambda user, *roles: False
		caso_doc = _make_caso_doc(descripcion="Descripción extensa que será redactada")
		mock_frappe.get_doc = MagicMock(return_value=caso_doc)

		result = _get_disciplinary_projection(
			casos=[],
			afectados=[_make_afectado_ns()],
			requesting_user="gerente@hubgh.com",
			employee_id="EMP-001",
			can_view_sensitive=True,
		)
		self.assertTrue(len(result) > 0)
		row = result[0]
		# Sensitive: name is redacted (not the real case name)
		self.assertNotEqual(row.get("name"), "CD-001")
		self.assertEqual(row.get("descripcion"), "REDACTED")
		self.assertIn("fecha", row)
		self.assertIn("estado", row)
		self.assertIn("tipo_falta", row)

	@patch("hubgh.hubgh.page.persona_360.persona_360.user_has_any_role")
	@patch("hubgh.hubgh.page.persona_360.persona_360.frappe")
	def test_sensitive_user_does_not_see_hechos(self, mock_frappe, mock_roles):
		from hubgh.hubgh.page.persona_360.persona_360 import _get_disciplinary_projection

		mock_roles.side_effect = lambda user, *roles: False
		caso_doc = _make_caso_doc()
		mock_frappe.get_doc = MagicMock(return_value=caso_doc)

		result = _get_disciplinary_projection(
			casos=[],
			afectados=[_make_afectado_ns()],
			requesting_user="gerente@hubgh.com",
			employee_id="EMP-001",
			can_view_sensitive=True,
		)
		row = result[0]
		self.assertNotIn("hechos_narrados", row)


class TestPersona360DisciplinaryProjectionExternal(FrappeTestCase):
	"""T055 — External user sees only {fecha_inicio_proceso, estado_caso, conclusion_publica}."""

	@patch("hubgh.hubgh.page.persona_360.persona_360.user_has_any_role")
	@patch("hubgh.hubgh.page.persona_360.persona_360.frappe")
	def test_external_user_sees_only_3_fields(self, mock_frappe, mock_roles):
		from hubgh.hubgh.page.persona_360.persona_360 import _get_disciplinary_projection

		mock_roles.side_effect = lambda user, *roles: False
		caso_doc = _make_caso_doc(descripcion="No debe verse")
		mock_frappe.get_doc = MagicMock(return_value=caso_doc)

		result = _get_disciplinary_projection(
			casos=[],
			afectados=[_make_afectado_ns()],
			requesting_user="bienestar@hubgh.com",
			employee_id="EMP-001",
			can_view_sensitive=False,
		)
		self.assertTrue(len(result) > 0)
		row = result[0]

		self.assertIn("fecha_inicio_proceso", row)
		self.assertIn("estado_caso", row)
		self.assertIn("conclusion_publica", row)
		self.assertNotIn("tipo_falta", row)
		self.assertNotIn("descripcion", row)
		self.assertNotIn("hechos_narrados", row)
		self.assertNotIn("name", row)

	@patch("hubgh.hubgh.page.persona_360.persona_360.user_has_any_role")
	@patch("hubgh.hubgh.page.persona_360.persona_360.frappe")
	def test_external_conclusion_publica_maps_suspension(self, mock_frappe, mock_roles):
		from hubgh.hubgh.page.persona_360.persona_360 import _get_disciplinary_projection

		mock_roles.side_effect = lambda user, *roles: False
		caso_doc = _make_caso_doc(fecha="2026-02-01", estado="Cerrado", decision="Suspensión")
		mock_frappe.get_doc = MagicMock(return_value=caso_doc)

		result = _get_disciplinary_projection(
			casos=[],
			afectados=[_make_afectado_ns(estado="Cerrado", decision="Suspensión")],
			requesting_user="bienestar@hubgh.com",
			employee_id="EMP-001",
			can_view_sensitive=False,
		)
		self.assertEqual(result[0]["conclusion_publica"], "Sanción aplicada")


class TestPersona360SelfQuery(FrappeTestCase):
	"""REQ-10-02 — Employee cannot see their own disciplinary data."""

	@patch("hubgh.hubgh.page.persona_360.persona_360.user_has_any_role")
	@patch("hubgh.hubgh.page.persona_360.persona_360.frappe")
	def test_self_query_returns_empty(self, mock_frappe, mock_roles):
		from hubgh.hubgh.page.persona_360.persona_360 import get_disciplinary_data

		mock_frappe.session = SimpleNamespace(user="emp001@hubgh.com")
		mock_frappe.db = MagicMock()
		mock_frappe.db.get_value = MagicMock(return_value="emp001@hubgh.com")  # email matches
		mock_roles.return_value = False

		result = get_disciplinary_data(employee_id="EMP-001", requesting_user="emp001@hubgh.com")
		self.assertEqual(result, [])


class TestPersona360ConclusionPublicaMap(FrappeTestCase):
	"""T057 — CONCLUSION_PUBLICA_MAP covers all outcomes."""

	def test_map_archivo(self):
		from hubgh.hubgh.page.persona_360.persona_360 import CONCLUSION_PUBLICA_MAP
		self.assertEqual(CONCLUSION_PUBLICA_MAP["Archivo"], "Proceso archivado")

	def test_map_recordatorio_funciones(self):
		from hubgh.hubgh.page.persona_360.persona_360 import CONCLUSION_PUBLICA_MAP
		self.assertEqual(CONCLUSION_PUBLICA_MAP["Recordatorio de Funciones"], "Sin sanción")

	def test_map_llamado_atencion_directo(self):
		from hubgh.hubgh.page.persona_360.persona_360 import CONCLUSION_PUBLICA_MAP
		self.assertEqual(CONCLUSION_PUBLICA_MAP["Llamado de Atención Directo"], "Sanción aplicada")

	def test_map_llamado_atencion(self):
		from hubgh.hubgh.page.persona_360.persona_360 import CONCLUSION_PUBLICA_MAP
		self.assertEqual(CONCLUSION_PUBLICA_MAP["Llamado de Atención"], "Sanción aplicada")

	def test_map_suspension(self):
		from hubgh.hubgh.page.persona_360.persona_360 import CONCLUSION_PUBLICA_MAP
		self.assertEqual(CONCLUSION_PUBLICA_MAP["Suspensión"], "Sanción aplicada")

	def test_map_terminacion(self):
		from hubgh.hubgh.page.persona_360.persona_360 import CONCLUSION_PUBLICA_MAP
		# REQ-10-03: Terminación maps to "Sanción aplicada" (not "Terminación")
		self.assertEqual(CONCLUSION_PUBLICA_MAP["Terminación"], "Sanción aplicada")

	def test_open_case_conclusion_is_en_proceso(self):
		from hubgh.hubgh.page.persona_360.persona_360 import _map_conclusion_publica
		result = _map_conclusion_publica(None)
		self.assertEqual(result, "En proceso")

	def test_map_conclusion_suspension(self):
		from hubgh.hubgh.page.persona_360.persona_360 import _map_conclusion_publica
		result = _map_conclusion_publica("Suspensión")
		self.assertEqual(result, "Sanción aplicada")


class TestPersona360AfectadoSource(FrappeTestCase):
	"""T055 — projection uses Afectado Disciplinario as canonical source."""

	@patch("hubgh.hubgh.page.persona_360.persona_360.user_has_any_role")
	@patch("hubgh.hubgh.page.persona_360.persona_360.frappe")
	def test_afectado_source_returns_entries(self, mock_frappe, mock_roles):
		from hubgh.hubgh.page.persona_360.persona_360 import get_disciplinary_data

		mock_roles.side_effect = lambda user, *roles: bool(set(roles) & RRLL_ROLES)
		mock_frappe.session = SimpleNamespace(user="monica@hubgh.com")
		mock_frappe.db = MagicMock()
		mock_frappe.db.get_value = MagicMock(return_value="other@hubgh.com")

		afectado_caso = SimpleNamespace(
			name="CD-NEW", fecha_incidente="2026-01-01", estado="En Triage",
			decision_final=None, tipo_falta="Grave", descripcion="New desc",
			hechos_narrados="New hechos", resumen_cierre="",
		)

		def get_all_side(doctype, **kwargs):
			if doctype == "Afectado Disciplinario":
				return [SimpleNamespace(caso="CD-NEW", name="AFE-001", empleado="EMP-001",
				                        decision_final_afectado=None, estado="En Triage",
				                        resumen_cierre_afectado="")]
			return []

		mock_frappe.get_all = MagicMock(side_effect=get_all_side)
		mock_frappe.get_doc = MagicMock(return_value=afectado_caso)

		result = get_disciplinary_data(employee_id="EMP-001", requesting_user="monica@hubgh.com")
		self.assertGreaterEqual(len(result), 1)
		self.assertEqual(result[0]["name"], "CD-NEW")
