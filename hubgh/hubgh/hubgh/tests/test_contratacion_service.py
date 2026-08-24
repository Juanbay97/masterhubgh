# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — Batch C / Phase C1 + SCOPE EXTENSION Phase C7 (RED): `contract_candidates`
real-progress enrichment for the RRLL board.

Covers:
- C1.1/C7.1: `contract_candidates` (contratacion_service.py) must merge
  `missing`, `exempted` and `percent` from `get_candidates_progress_bulk`
  into every row it returns — N-independent (one bulk call, not one call per
  candidate).
- C7.1: the `validate_hr_access` gate must run BEFORE any read (no
  `frappe.get_all` / `get_candidates_progress_bulk` call happens for an
  unauthorized user), with a dedicated negative test for a non-RRLL/non-HR
  role.

`get_candidate_progress` (singular, not whitelisted) stays untouched by this
change — the RRLL board must route exclusively through
`get_candidates_progress_bulk`, per binding override #2 in tasks.md.
"""

from unittest.mock import patch, MagicMock

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.contratacion_service import contract_candidates


_CONT_MODULE = "hubgh.hubgh.contratacion_service"


def _make_row(name, **extra):
	row = MagicMock()
	row.name = name
	row.nombres = "Juan"
	row.apellidos = "Pérez"
	row.numero_documento = "12345678"
	row.pdv_destino = "PDV-01"
	row.cargo_postulado = "Asesor"
	row.fecha_tentativa_ingreso = "2026-07-01"
	for k, v in extra.items():
		setattr(row, k, v)
	return row


def _make_progress(missing=None, exempted=None, percent=100):
	return {
		"missing": missing or [],
		"exempted": exempted or [],
		"percent": percent,
		"required_ok": 5,
		"required_total": 5,
		"is_complete": percent == 100,
		"sagrilaft_ok": True,
	}


class TestContractCandidatesProgressEnrichment(FrappeTestCase):
	"""C1.1/C7.1/C7.2 — contract_candidates must expose real progress."""

	def test_contract_candidates_includes_missing_exempted_and_percent(self):
		row = _make_row("CAND-RRLL-1")
		progress_map = {
			"CAND-RRLL-1": _make_progress(
				missing=["SAGRILAFT"], exempted=["Cédula"], percent=60
			),
		}

		def _fake_get_all(doctype, **kwargs):
			if doctype == "Candidato":
				return [row]
			if doctype == "Datos Contratacion":
				return []
			raise AssertionError(f"unexpected frappe.get_all({doctype!r})")

		with (
			patch(f"{_CONT_MODULE}.validate_hr_access", return_value=None),
			patch(f"{_CONT_MODULE}.frappe.get_all", side_effect=_fake_get_all),
			patch(
				f"{_CONT_MODULE}.get_candidates_progress_bulk",
				return_value=progress_map,
			) as mock_bulk,
		):
			result = contract_candidates()

		self.assertEqual(len(result), 1)
		payload = result[0]
		self.assertEqual(payload["name"], "CAND-RRLL-1")
		self.assertEqual(payload["missing"], ["SAGRILAFT"])
		self.assertEqual(payload["exempted"], ["Cédula"])
		self.assertEqual(payload["percent"], 60)
		# N-independent: exactly one bulk call for the whole board, never per row.
		mock_bulk.assert_called_once()

	def test_contract_candidates_bulk_call_is_n_independent(self):
		rows = [_make_row(f"CAND-RRLL-{i}") for i in range(5)]
		progress_map = {r.name: _make_progress(percent=100) for r in rows}

		def _fake_get_all(doctype, **kwargs):
			if doctype == "Candidato":
				return rows
			if doctype == "Datos Contratacion":
				return []
			raise AssertionError(f"unexpected frappe.get_all({doctype!r})")

		with (
			patch(f"{_CONT_MODULE}.validate_hr_access", return_value=None),
			patch(f"{_CONT_MODULE}.frappe.get_all", side_effect=_fake_get_all),
			patch(
				f"{_CONT_MODULE}.get_candidates_progress_bulk",
				return_value=progress_map,
			) as mock_bulk,
		):
			result = contract_candidates()

		self.assertEqual(len(result), 5)
		mock_bulk.assert_called_once()
		self.assertEqual(sorted(mock_bulk.call_args[0][0]), sorted(r.name for r in rows))

	def test_missing_candidate_from_bulk_map_gets_safe_default(self):
		"""A candidate absent from the bulk map (edge case) must not KeyError."""
		row = _make_row("CAND-RRLL-NODATA")

		def _fake_get_all(doctype, **kwargs):
			if doctype == "Candidato":
				return [row]
			if doctype == "Datos Contratacion":
				return []
			raise AssertionError(f"unexpected frappe.get_all({doctype!r})")

		with (
			patch(f"{_CONT_MODULE}.validate_hr_access", return_value=None),
			patch(f"{_CONT_MODULE}.frappe.get_all", side_effect=_fake_get_all),
			patch(f"{_CONT_MODULE}.get_candidates_progress_bulk", return_value={}),
		):
			result = contract_candidates()

		self.assertEqual(result[0]["missing"], [])
		self.assertEqual(result[0]["exempted"], [])


class TestContractCandidatesAccessGate(FrappeTestCase):
	"""C7.1 — validate_hr_access must run BEFORE any read; negative test for
	a non-RRLL/non-HR role."""

	def test_gate_runs_before_any_read(self):
		"""Unauthorized user: validate_hr_access throws before the "Candidato"
		read or get_candidates_progress_bulk are ever invoked. frappe.throw's
		own internal "Translation" doctype lookup is not the production read
		under test and is excluded from the assertion."""
		with (
			patch(f"{_CONT_MODULE}._user_is_hr", return_value=False),
			patch(f"{_CONT_MODULE}.frappe.get_all") as mock_get_all,
			patch(
				f"{_CONT_MODULE}.get_candidates_progress_bulk"
			) as mock_bulk,
		):
			with self.assertRaises(frappe.exceptions.ValidationError):
				contract_candidates()

		candidato_calls = [
			c for c in mock_get_all.call_args_list if c.args and c.args[0] == "Candidato"
		]
		self.assertEqual(candidato_calls, [], "no Candidato read must happen before the gate")
		mock_bulk.assert_not_called()

	def test_non_rrll_role_rejected(self):
		"""A real user holding none of the HR/RRLL roles is rejected, and no
		read is attempted — mirrors test_board_visibility.py's role-parity
		pattern (patches role_matrix.frappe.get_roles + frappe.session)."""
		with (
			patch("hubgh.hubgh.role_matrix.frappe.get_roles", return_value=["Candidato"]),
			patch(f"{_CONT_MODULE}.frappe.session") as mock_session,
			patch(f"{_CONT_MODULE}.frappe.get_all") as mock_get_all,
			patch(f"{_CONT_MODULE}.get_candidates_progress_bulk") as mock_bulk,
		):
			mock_session.user = "non-rrll-role@example.com"
			with self.assertRaises(frappe.exceptions.ValidationError):
				contract_candidates()

		mock_get_all.assert_not_called()
		mock_bulk.assert_not_called()
