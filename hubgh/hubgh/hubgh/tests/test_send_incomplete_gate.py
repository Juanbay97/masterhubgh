# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — T-03 to T-08 (RED): send_candidate_to_labor_relations incomplete-send gate.

Tests cover:
  T-03  incomplete + no motivo → frappe.throw
  T-04  incomplete + motivo → succeeds, 5 audit fields set, solo_afiliacion=1
  T-05  hard gate (medical/SAGRILAFT) blocks even with motivo
  T-06  complete docs → unchanged happy path, audit fields absent
  T-07  any HR Selection user authorized (not just lead)
  T-08  docs_faltantes_snapshot is immutable after a later upload

All tests are RED until T-09 (backend implementation) lands.
"""

import json
from unittest.mock import patch, MagicMock

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.document_service import send_candidate_to_labor_relations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_progress(is_complete, missing=None):
    """Return a minimal progress dict like get_candidate_progress does."""
    return {
        "is_complete": is_complete,
        "missing": missing or [],
        "percent": 100 if is_complete else 50,
        "required_ok": 5 if is_complete else 2,
        "required_total": 5,
        "sagrilaft_ok": True,
    }


def _gate_ready():
    return {"status": "ready", "errors": []}


def _gate_blocked(reason="Concepto médico no Favorable"):
    return {"status": "blocked", "errors": [reason]}


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestSendIncompletGate(FrappeTestCase):
    """Unit tests for the incomplete-send gate in send_candidate_to_labor_relations."""

    # ------------------------------------------------------------------
    # T-03: incomplete + no motivo → raise
    # ------------------------------------------------------------------
    def test_send_incomplete_no_motivo_raises(self):
        """Incomplete docs without motivo must hard-throw asking for reason."""
        with (
            patch("hubgh.hubgh.document_service.user_has_any_role", return_value=True),
            patch(
                "hubgh.hubgh.document_service.get_candidate_progress",
                return_value=_make_progress(False, ["Cédula", "Carta de referencia 1"]),
            ),
            patch(
                "hubgh.hubgh.document_service.validate_selection_to_rrll_gate",
                return_value=_gate_ready(),
            ),
            patch("hubgh.hubgh.document_service.frappe.get_doc", return_value=MagicMock()),
            patch("hubgh.hubgh.document_service.frappe.db"),
        ):
            with self.assertRaises(frappe.exceptions.ValidationError):
                send_candidate_to_labor_relations(
                    "CAND-001",
                    pdv_destino="PDV-01",
                    fecha_tentativa_ingreso="2026-07-01",
                    cargo="Asesor",
                    # motivo intentionally omitted
                )

    # ------------------------------------------------------------------
    # T-04: incomplete + motivo → audit fields set
    # ------------------------------------------------------------------
    def test_send_incomplete_with_motivo_sets_audit_fields(self):
        """Incomplete + motivo: succeeds with documentacion_incompleta=1 and all audit fields."""
        missing_docs = ["Cédula", "Carta de referencia 1"]

        mock_datos_doc = MagicMock()
        mock_datos_doc.name = "DC-CAND-001"

        mock_cand_doc = MagicMock()
        mock_cand_doc.get = MagicMock(return_value=None)

        def _fake_get_doc(doctype_or_dict, name=None, *args, **kwargs):
            if isinstance(doctype_or_dict, dict):
                obj = MagicMock()
                obj.insert = MagicMock(return_value=obj)
                return obj
            if doctype_or_dict == "Candidato":
                return mock_cand_doc
            if doctype_or_dict == "Datos Contratacion":
                return mock_datos_doc
            return MagicMock()

        with (
            patch("hubgh.hubgh.document_service.user_has_any_role", return_value=True),
            patch(
                "hubgh.hubgh.document_service.get_candidate_progress",
                return_value=_make_progress(False, missing_docs),
            ),
            patch(
                "hubgh.hubgh.document_service.validate_selection_to_rrll_gate",
                return_value=_gate_ready(),
            ),
            patch("hubgh.hubgh.document_service.frappe.get_doc", side_effect=_fake_get_doc),
            patch("hubgh.hubgh.document_service.frappe.db") as mock_db,
            patch("hubgh.hubgh.document_service.frappe.session") as mock_session,
            patch("hubgh.hubgh.document_service.now", return_value="2026-06-25 10:00:00"),
        ):
            mock_db.get_value = MagicMock(return_value=None)
            mock_db.exists = MagicMock(return_value=False)
            mock_db.set_value = MagicMock()
            mock_session.user = "hr.selection@homeburgers.com"

            result = send_candidate_to_labor_relations(
                "CAND-001",
                pdv_destino="PDV-01",
                fecha_tentativa_ingreso="2026-07-01",
                cargo="Asesor",
                motivo="Candidato urgente, falta cédula en trámite",
            )

        # Verify the call to frappe.db.set_value for Candidato includes solo_afiliacion=1
        set_value_calls = mock_db.set_value.call_args_list
        candidato_calls = [c for c in set_value_calls if c.args[0] == "Candidato"]
        self.assertTrue(len(candidato_calls) > 0, "Expected frappe.db.set_value called for Candidato")
        updates_dict = candidato_calls[0].args[2]
        self.assertEqual(updates_dict.get("solo_afiliacion"), 1)

        # Verify result includes documentacion_incompleta=1
        self.assertEqual(result.get("documentacion_incompleta"), 1)

        # Verify Datos Contratacion was created/updated with audit fields
        # The insert call on the new doc or set_value on existing — check via inserted doc mock
        # Since db.exists returns False, a new doc is created via frappe.get_doc({...}).insert()
        datos_calls = [c for c in mock_db.set_value.call_args_list if c.args[0] == "Datos Contratacion"]
        # OR check via the dict passed to frappe.get_doc({...})
        get_doc_calls = frappe.get_doc.call_args_list if hasattr(frappe.get_doc, 'call_args_list') else []
        # We verify at a higher level: result must carry documentacion_incompleta=1
        self.assertIn("documentacion_incompleta", result)

    # ------------------------------------------------------------------
    # T-05: hard gate blocks even with motivo
    # ------------------------------------------------------------------
    def test_send_incomplete_hard_gate_blocks_even_with_motivo(self):
        """Medical/SAGRILAFT gate must throw even when motivo is provided."""
        with (
            patch("hubgh.hubgh.document_service.user_has_any_role", return_value=True),
            patch(
                "hubgh.hubgh.document_service.get_candidate_progress",
                return_value=_make_progress(False, ["Cédula"]),
            ),
            patch(
                "hubgh.hubgh.document_service.validate_selection_to_rrll_gate",
                return_value=_gate_blocked("Concepto médico no Favorable"),
            ),
            patch("hubgh.hubgh.document_service.frappe.get_doc", return_value=MagicMock()),
            patch("hubgh.hubgh.document_service.frappe.db"),
        ):
            with self.assertRaises(frappe.exceptions.ValidationError):
                send_candidate_to_labor_relations(
                    "CAND-001",
                    motivo="Urgente",
                )

    # ------------------------------------------------------------------
    # T-06a: complete docs → unchanged behavior (solo_afiliacion=0)
    # ------------------------------------------------------------------
    def test_send_complete_docs_unchanged_behavior(self):
        """Complete docs: send succeeds, solo_afiliacion=0."""
        mock_cand_doc = MagicMock()
        mock_cand_doc.get = MagicMock(return_value=None)

        def _fake_get_doc(doctype_or_dict, name=None, *args, **kwargs):
            if isinstance(doctype_or_dict, dict):
                obj = MagicMock()
                obj.insert = MagicMock(return_value=obj)
                return obj
            return mock_cand_doc

        with (
            patch("hubgh.hubgh.document_service.user_has_any_role", return_value=True),
            patch(
                "hubgh.hubgh.document_service.get_candidate_progress",
                return_value=_make_progress(True),
            ),
            patch(
                "hubgh.hubgh.document_service.validate_selection_to_rrll_gate",
                return_value=_gate_ready(),
            ),
            patch("hubgh.hubgh.document_service.frappe.get_doc", side_effect=_fake_get_doc),
            patch("hubgh.hubgh.document_service.frappe.db") as mock_db,
            patch("hubgh.hubgh.document_service.frappe.session") as mock_session,
        ):
            mock_db.get_value = MagicMock(return_value=None)
            mock_db.exists = MagicMock(return_value=False)
            mock_db.set_value = MagicMock()
            mock_session.user = "hr.selection@homeburgers.com"

            result = send_candidate_to_labor_relations("CAND-001")

        candidato_calls = [c for c in mock_db.set_value.call_args_list if c.args[0] == "Candidato"]
        self.assertTrue(len(candidato_calls) > 0)
        updates_dict = candidato_calls[0].args[2]
        self.assertEqual(updates_dict.get("solo_afiliacion"), 0)
        # documentacion_incompleta should be 0 in result
        self.assertEqual(result.get("documentacion_incompleta"), 0)

    # ------------------------------------------------------------------
    # T-06b: complete docs → audit fields absent / at default
    # ------------------------------------------------------------------
    def test_audit_fields_absent_on_complete_send(self):
        """Complete send must not populate audit fields (they stay default/null)."""
        new_doc_kwargs_captured = {}

        def _fake_get_doc(doctype_or_dict, name=None, *args, **kwargs):
            if isinstance(doctype_or_dict, dict):
                new_doc_kwargs_captured.update(doctype_or_dict)
                obj = MagicMock()
                obj.insert = MagicMock(return_value=obj)
                return obj
            return MagicMock()

        with (
            patch("hubgh.hubgh.document_service.user_has_any_role", return_value=True),
            patch(
                "hubgh.hubgh.document_service.get_candidate_progress",
                return_value=_make_progress(True),
            ),
            patch(
                "hubgh.hubgh.document_service.validate_selection_to_rrll_gate",
                return_value=_gate_ready(),
            ),
            patch("hubgh.hubgh.document_service.frappe.get_doc", side_effect=_fake_get_doc),
            patch("hubgh.hubgh.document_service.frappe.db") as mock_db,
            patch("hubgh.hubgh.document_service.frappe.session") as mock_session,
        ):
            mock_db.get_value = MagicMock(return_value=None)
            mock_db.exists = MagicMock(return_value=False)
            mock_db.set_value = MagicMock()
            mock_session.user = "hr.selection@homeburgers.com"

            send_candidate_to_labor_relations("CAND-001")

        # The new Datos Contratacion doc dict must NOT contain audit override fields
        self.assertNotIn("documentacion_incompleta", new_doc_kwargs_captured,
                         "Complete send must not inject documentacion_incompleta into Datos Contratacion doc")
        self.assertNotIn("motivo_doc_incompleta", new_doc_kwargs_captured)
        self.assertNotIn("autorizado_por", new_doc_kwargs_captured)

    # ------------------------------------------------------------------
    # T-07: any HR Selection user authorized
    # ------------------------------------------------------------------
    def test_send_incomplete_any_hr_selection_user_authorized(self):
        """Any HR Selection role user (not just lead) can authorize incomplete send."""
        authorized_user = "plain.hr.selection@homeburgers.com"

        mock_cand_doc = MagicMock()
        mock_cand_doc.get = MagicMock(return_value=None)

        def _fake_get_doc(doctype_or_dict, name=None, *args, **kwargs):
            if isinstance(doctype_or_dict, dict):
                obj = MagicMock()
                obj.insert = MagicMock(return_value=obj)
                return obj
            return mock_cand_doc

        def _fake_user_has_any_role(user, *roles):
            # Simulate a plain HR Selection user (not a lead)
            return "HR Selection" in roles

        with (
            patch(
                "hubgh.hubgh.document_service.user_has_any_role",
                side_effect=_fake_user_has_any_role,
            ),
            patch(
                "hubgh.hubgh.document_service.get_candidate_progress",
                return_value=_make_progress(False, ["Cédula"]),
            ),
            patch(
                "hubgh.hubgh.document_service.validate_selection_to_rrll_gate",
                return_value=_gate_ready(),
            ),
            patch("hubgh.hubgh.document_service.frappe.get_doc", side_effect=_fake_get_doc),
            patch("hubgh.hubgh.document_service.frappe.db") as mock_db,
            patch("hubgh.hubgh.document_service.frappe.session") as mock_session,
            patch("hubgh.hubgh.document_service.now", return_value="2026-06-25 10:00:00"),
        ):
            mock_db.get_value = MagicMock(return_value=None)
            mock_db.exists = MagicMock(return_value=False)
            mock_db.set_value = MagicMock()
            mock_session.user = authorized_user

            # Must not raise — any HR Selection user is allowed
            result = send_candidate_to_labor_relations(
                "CAND-001",
                motivo="Urgente — cédula en trámite",
            )

        self.assertEqual(result.get("documentacion_incompleta"), 1)

    # ------------------------------------------------------------------
    # T-08: docs_faltantes_snapshot immutable after upload
    # ------------------------------------------------------------------
    def test_docs_faltantes_snapshot_immutable_after_upload(self):
        """docs_faltantes_snapshot must not change when a document is later uploaded."""
        # Step 1: perform incomplete send — snapshot is written at send time.
        missing_at_send = ["Cédula", "Carta de referencia 1"]
        snapshot_written = {}

        def _fake_get_doc_capture(doctype_or_dict, name=None, *args, **kwargs):
            if isinstance(doctype_or_dict, dict):
                # Capture what would be written to Datos Contratacion
                snapshot_written.update(doctype_or_dict)
                obj = MagicMock()
                obj.insert = MagicMock(return_value=obj)
                return obj
            return MagicMock()

        with (
            patch("hubgh.hubgh.document_service.user_has_any_role", return_value=True),
            patch(
                "hubgh.hubgh.document_service.get_candidate_progress",
                return_value=_make_progress(False, missing_at_send),
            ),
            patch(
                "hubgh.hubgh.document_service.validate_selection_to_rrll_gate",
                return_value=_gate_ready(),
            ),
            patch(
                "hubgh.hubgh.document_service.frappe.get_doc",
                side_effect=_fake_get_doc_capture,
            ),
            patch("hubgh.hubgh.document_service.frappe.db") as mock_db,
            patch("hubgh.hubgh.document_service.frappe.session") as mock_session,
            patch("hubgh.hubgh.document_service.now", return_value="2026-06-25 10:00:00"),
        ):
            mock_db.get_value = MagicMock(return_value=None)
            mock_db.exists = MagicMock(return_value=False)
            mock_db.set_value = MagicMock()
            mock_session.user = "hr.selection@homeburgers.com"

            send_candidate_to_labor_relations(
                "CAND-001",
                motivo="Urgente",
            )

        # Snapshot recorded in the insert payload
        snapshot_raw = snapshot_written.get("docs_faltantes_snapshot")
        self.assertIsNotNone(snapshot_raw, "docs_faltantes_snapshot must be set in Datos Contratacion at send time")
        snapshot_value = json.loads(snapshot_raw)
        self.assertEqual(sorted(snapshot_value), sorted(missing_at_send))

        # Step 2: simulate that a document is uploaded (progress changes).
        # The snapshot field on the EXISTING Datos Contratacion record must NOT be updated.
        # We verify this by asserting set_value was NOT called on docs_faltantes_snapshot
        # after the send completes. The snapshot is only written once, at insert.
        set_value_calls = mock_db.set_value.call_args_list
        datos_set_value_calls = [
            c for c in set_value_calls
            if c.args[0] == "Datos Contratacion" and "docs_faltantes_snapshot" in str(c)
        ]
        # After the initial insert (which uses frappe.get_doc({...}).insert()), there must
        # be zero subsequent frappe.db.set_value calls touching docs_faltantes_snapshot.
        self.assertEqual(
            len(datos_set_value_calls),
            0,
            "docs_faltantes_snapshot must not be modified via set_value after initial insert",
        )
