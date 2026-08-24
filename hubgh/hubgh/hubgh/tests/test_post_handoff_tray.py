# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — Batch PR3, Phase 3.4: post-handoff opt-in tab + page-role parity fix.

Tests cover:
  3.4.1  RED  → includes En afiliación/Listo para contratar/Contratado candidates whose
               permission-independent progress is NOT complete, regardless of solo_afiliacion
  3.4.2  RED  → Rechazado excluded
  3.4.3  RED (security) → gate runs before any DB read, negative for a non-authorized role
  3.4.6  REFACTOR → ignore_permissions widening (PR1) does not change which candidates
               any caller sees (parity guard)
  3.4.7  RED+GREEN → page-role parity: seleccion_documentos.json roles[] must cover every
               role authorized by _has_selection_access

All tests are RED until the corresponding GREEN task lands (see tasks.md Phase 3.4).
"""

import json
import os
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.page.seleccion_documentos.seleccion_documentos import (
	_has_selection_access,
	list_post_handoff_candidates,
)


_SEL_MODULE = "hubgh.hubgh.page.seleccion_documentos.seleccion_documentos"


def _make_row(name, estado, solo_afiliacion=0, **extra):
	row = MagicMock()
	row.name = name
	row.nombres = "Juan"
	row.apellidos = "Pérez"
	row.primer_apellido = "Pérez"
	row.segundo_apellido = ""
	row.numero_documento = "12345678"
	row.pdv_destino = "PDV-01"
	row.cargo_postulado = "Asesor"
	row.creation = "2026-06-25 10:00:00"
	row.estado_proceso = estado
	row.concepto_medico = "Favorable"
	row.fecha_envio_examen_medico = None
	row.solo_afiliacion = solo_afiliacion
	row.persona = None
	row.fecha_tentativa_ingreso = "2026-07-01"
	for k, v in extra.items():
		setattr(row, k, v)
	return row


def _progress(is_complete, missing=None):
	return {
		"is_complete": is_complete,
		"missing": missing or [],
		"percent": 100 if is_complete else 40,
		"required_ok": 5 if is_complete else 2,
		"required_total": 5,
		"sagrilaft_ok": True,
	}


# ---------------------------------------------------------------------------
# 3.4.3 — security gate before any DB read
# ---------------------------------------------------------------------------


class TestListPostHandoffCandidatesGate(FrappeTestCase):
	def test_denies_non_authorized_role_before_db_read(self):
		with (
			patch(f"{_SEL_MODULE}.user_has_any_role", return_value=False),
			patch(f"{_SEL_MODULE}.frappe.session") as mock_session,
			patch(f"{_SEL_MODULE}.frappe.get_all") as mock_get_all,
		):
			mock_session.user = "hr.sst@homeburgers.com"
			with self.assertRaises(frappe.exceptions.ValidationError):
				list_post_handoff_candidates()
		for call in mock_get_all.call_args_list:
			doctype = call.args[0] if call.args else call.kwargs.get("doctype")
			self.assertNotEqual(doctype, "Candidato", f"Unexpected Candidato read before gate: {call}")


# ---------------------------------------------------------------------------
# 3.4.1/3.4.2 — inclusion/exclusion rules
# ---------------------------------------------------------------------------


class TestListPostHandoffCandidatesInclusion(FrappeTestCase):
	def test_incomplete_en_afiliacion_included_regardless_of_solo_afiliacion(self):
		"""solo_afiliacion=0 must NOT hide a candidate from this tab (orchestrator correction)."""
		row = _make_row("CAND-1", "En afiliación", solo_afiliacion=0)
		with (
			patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
			patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[row]),
			patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
			patch(
				f"{_SEL_MODULE}.get_candidates_progress_bulk",
				return_value={"CAND-1": _progress(False, ["Cédula"])},
			),
		):
			result = list_post_handoff_candidates()
		names = [r["name"] for r in result]
		self.assertIn("CAND-1", names)

	def test_incomplete_listo_para_contratar_included(self):
		row = _make_row("CAND-2", "Listo para contratar", solo_afiliacion=0)
		with (
			patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
			patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[row]),
			patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
			patch(
				f"{_SEL_MODULE}.get_candidates_progress_bulk",
				return_value={"CAND-2": _progress(False, ["SAGRILAFT"])},
			),
		):
			result = list_post_handoff_candidates()
		self.assertIn("CAND-2", [r["name"] for r in result])

	def test_incomplete_contratado_included(self):
		row = _make_row("CAND-3", "Contratado", solo_afiliacion=0)
		with (
			patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
			patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[row]),
			patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
			patch(
				f"{_SEL_MODULE}.get_candidates_progress_bulk",
				return_value={"CAND-3": _progress(False, ["Cédula"])},
			),
		):
			result = list_post_handoff_candidates()
		self.assertIn("CAND-3", [r["name"] for r in result])

	def test_complete_candidate_excluded(self):
		"""Progress is_complete=True must NOT appear in the pending tab."""
		row = _make_row("CAND-4", "En afiliación", solo_afiliacion=0)
		with (
			patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
			patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[row]),
			patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
			patch(f"{_SEL_MODULE}.get_candidates_progress_bulk", return_value={"CAND-4": _progress(True)}),
		):
			result = list_post_handoff_candidates()
		self.assertNotIn("CAND-4", [r["name"] for r in result])

	def test_rechazado_excluded_even_if_incomplete(self):
		row = _make_row("CAND-5", "Rechazado", solo_afiliacion=0)
		with (
			patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
			patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[row]),
			patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
			patch(
				f"{_SEL_MODULE}.get_candidates_progress_bulk",
				return_value={"CAND-5": _progress(False, ["Cédula"])},
			),
		):
			result = list_post_handoff_candidates()
		self.assertNotIn("CAND-5", [r["name"] for r in result])

	def test_documentacion_state_excluded_not_a_post_handoff_state(self):
		"""En documentación (pre-handoff) must not appear — only post-handoff states qualify."""
		row = _make_row("CAND-6", "En documentación", solo_afiliacion=0)
		with (
			patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
			patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[row]),
			patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
			patch(
				f"{_SEL_MODULE}.get_candidates_progress_bulk",
				return_value={"CAND-6": _progress(False, ["Cédula"])},
			),
		):
			result = list_post_handoff_candidates()
		self.assertEqual(result, [])

	def test_rows_carry_can_manage_false(self):
		row = _make_row("CAND-7", "En afiliación", solo_afiliacion=1)
		with (
			patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
			patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[row]),
			patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
			patch(
				f"{_SEL_MODULE}.get_candidates_progress_bulk",
				return_value={"CAND-7": _progress(False, ["Cédula"])},
			),
		):
			result = list_post_handoff_candidates()
		self.assertEqual(result[0]["can_manage"], False)

	def test_empty_result_returns_empty_payload_no_error(self):
		with (
			patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
			patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[]),
		):
			result = list_post_handoff_candidates()
		self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# 3.4.6 — parity guard: ignore_permissions widening must not change visibility
# ---------------------------------------------------------------------------


class TestIgnorePermissionsParityGuard(FrappeTestCase):
	"""frappe.get_all already ignores permissions unconditionally (framework behavior,
	confirmed in PR1 apply-progress): the PR1 widening note only concerns which
	Document Type rows the *progress computation* counts as required, never which
	candidates list_candidates/list_post_handoff_candidates return. This test pins
	that the candidate-visibility set is identical across two different acting roles
	when the underlying progress result is held fixed."""

	def test_same_candidate_set_visible_regardless_of_caller_role(self):
		row = _make_row("CAND-PARITY", "En afiliación", solo_afiliacion=0)
		fixed_progress = {"CAND-PARITY": _progress(False, ["Cédula"])}

		def _run_as(role):
			with (
				patch(f"{_SEL_MODULE}.user_has_any_role", side_effect=lambda user, *roles: role in roles),
				patch(f"{_SEL_MODULE}.frappe.session") as mock_session,
				patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[row]),
				patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
				patch(f"{_SEL_MODULE}.get_candidates_progress_bulk", return_value=fixed_progress),
			):
				mock_session.user = f"{role.lower().replace(' ', '.')}@homeburgers.com"
				return [r["name"] for r in list_post_handoff_candidates()]

		self.assertEqual(_run_as("Gestión Humana"), _run_as("Gerente GH"))
		self.assertEqual(_run_as("Gestión Humana"), ["CAND-PARITY"])


# ---------------------------------------------------------------------------
# Batch C (Phase C3.4/C4) — "exempted" key propagation.
#
# _project_candidate_row (shared by list_candidates and this tab) never
# copied progress["exempted"] into its row payload, even though PR B's
# _compute_candidate_progress has produced that key since Batch B. Without
# it, seleccion_documentos.js has no data to render the "Exonerado" pill on
# this tab's rows.
# ---------------------------------------------------------------------------


class TestListPostHandoffCandidatesExemptedField(FrappeTestCase):
	def test_row_carries_exempted_list_from_progress(self):
		row = _make_row("CAND-EXEMPT", "En afiliación", solo_afiliacion=0)
		with (
			patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
			patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[row]),
			patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
			patch(
				f"{_SEL_MODULE}.get_candidates_progress_bulk",
				return_value={
					"CAND-EXEMPT": {
						"is_complete": False,
						"missing": ["SAGRILAFT"],
						"exempted": ["Cédula"],
						"percent": 60,
						"required_ok": 3,
						"required_total": 5,
						"sagrilaft_ok": False,
					}
				},
			),
		):
			result = list_post_handoff_candidates()
		self.assertEqual(result[0]["exempted"], ["Cédula"])

	def test_row_defaults_exempted_to_empty_list_when_absent(self):
		row = _make_row("CAND-NOEXEMPT", "En afiliación", solo_afiliacion=0)
		with (
			patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
			patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[row]),
			patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
			patch(f"{_SEL_MODULE}.get_candidates_progress_bulk", return_value={"CAND-NOEXEMPT": _progress(False, ["Cédula"])}),
		):
			result = list_post_handoff_candidates()
		self.assertEqual(result[0]["exempted"], [])


# ---------------------------------------------------------------------------
# 3.4.7 — page-role parity with _has_selection_access
# ---------------------------------------------------------------------------


class TestSeleccionDocumentosPageRoleParity(FrappeTestCase):
	REQUIRED_ROLES = ("HR Selection", "Gestión Humana", "GH - Bandeja General", "Gerente GH")

	def test_has_selection_access_authorizes_every_required_role(self):
		"""Drift guard: pins the exact role set _has_selection_access authorizes,
		so a future change to that gate is caught alongside the json parity check below."""
		for role in self.REQUIRED_ROLES:
			with patch(
				f"{_SEL_MODULE}.user_has_any_role",
				side_effect=lambda user, *roles, _role=role: _role in roles,
			):
				self.assertTrue(
					_has_selection_access(user="probe@homeburgers.com"),
					f"{role} must be authorized by _has_selection_access",
				)

	def test_page_json_roles_cover_every_has_selection_access_role(self):
		"""Real navigation bug found during PR1: backend authorized Gestión Humana,
		GH - Bandeja General and Gerente GH via _has_selection_access, but the Desk
		page denied navigation because its roles[] list was missing them."""
		json_path = os.path.join(
			frappe.get_app_path("hubgh"), "hubgh", "page", "seleccion_documentos", "seleccion_documentos.json"
		)
		with open(json_path, encoding="utf-8") as f:
			page_def = json.load(f)
		page_roles = {entry["role"] for entry in page_def.get("roles", [])}

		missing = set(self.REQUIRED_ROLES) - page_roles
		self.assertEqual(
			missing, set(),
			f"seleccion_documentos.json roles[] is missing roles authorized by _has_selection_access: {missing}",
		)
