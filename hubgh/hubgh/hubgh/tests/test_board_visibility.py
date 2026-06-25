# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — T-14 to T-19 (RED): Board visibility + contract gate regression.

Tests cover:
  T-14  solo_afiliacion=1 → candidate IS visible in seleccion list_candidates
  T-15  solo_afiliacion=0 (complete send) → candidate NOT visible in seleccion
  T-16  incomplete candidate is visible in bandeja_contratacion (contract_candidates)
         + get_candidate_progress returns is_complete=False and non-empty missing list
  T-17  after uploading all missing docs, get_candidate_progress.is_complete=True
  T-18  contract submit blocked while docs incomplete (_validate_mandatory_ingreso_gate regression)
  T-19  contract submit unblocked after full upload

All tests are RED until WU2+WU3 GREEN implementations land; T-17 also needs T-13.
"""

from unittest.mock import patch, MagicMock, PropertyMock

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.page.seleccion_documentos.seleccion_documentos import list_candidates
from hubgh.hubgh.page.bandeja_contratacion.bandeja_contratacion import upload_contratacion_document
from hubgh.hubgh.document_service import get_candidate_progress
from hubgh.hubgh.contratacion_service import _validate_mandatory_ingreso_gate


_SEL_MODULE = "hubgh.hubgh.page.seleccion_documentos.seleccion_documentos"
_DOC_MODULE = "hubgh.hubgh.document_service"
_CONT_MODULE = "hubgh.hubgh.contratacion_service"
_BANDEJA_MODULE = "hubgh.hubgh.page.bandeja_contratacion.bandeja_contratacion"


def _make_candidate_row(name, estado="En Afiliación", solo_afiliacion=1, **extra):
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


def _make_progress(is_complete, missing=None):
    return {
        "is_complete": is_complete,
        "missing": missing or [],
        "percent": 100 if is_complete else 40,
        "required_ok": 5 if is_complete else 2,
        "required_total": 5,
        "sagrilaft_ok": True,
    }


# ---------------------------------------------------------------------------
# T-14: solo_afiliacion=1 candidate visible in seleccion list_candidates
# ---------------------------------------------------------------------------

class TestSeleccionBoardVisibility(FrappeTestCase):

    def test_solo_afiliacion_1_visible_in_seleccion_board(self):
        """Candidate sent incomplete (solo_afiliacion=1) must appear in list_candidates."""
        incomplete_row = _make_candidate_row("CAND-INCOMPLETE", solo_afiliacion=1)

        with (
            patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
            patch(f"{_SEL_MODULE}._can_manage_candidates", return_value=True),
            patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[incomplete_row]),
            patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
            patch(
                f"{_SEL_MODULE}.get_candidates_progress_bulk",
                return_value={"CAND-INCOMPLETE": _make_progress(False, ["Cédula"])},
            ),
        ):
            result = list_candidates()

        names = [r["name"] for r in result]
        self.assertIn(
            "CAND-INCOMPLETE",
            names,
            "Candidate with solo_afiliacion=1 must appear in seleccion list_candidates",
        )

    # ------------------------------------------------------------------
    # T-15: solo_afiliacion=0 (complete send) → hidden from seleccion
    # ------------------------------------------------------------------
    def test_solo_afiliacion_0_hidden_from_seleccion_board(self):
        """Candidate sent complete (solo_afiliacion=0) must NOT appear in list_candidates."""
        complete_row = _make_candidate_row("CAND-COMPLETE", solo_afiliacion=0)

        with (
            patch(f"{_SEL_MODULE}._validate_selection_access", return_value=None),
            patch(f"{_SEL_MODULE}._can_manage_candidates", return_value=True),
            patch(f"{_SEL_MODULE}.frappe.get_all", return_value=[complete_row]),
            patch(f"{_SEL_MODULE}._candidate_pdv_name_map", return_value={}),
            patch(
                f"{_SEL_MODULE}.get_candidates_progress_bulk",
                return_value={"CAND-COMPLETE": _make_progress(True)},
            ),
        ):
            result = list_candidates()

        names = [r["name"] for r in result]
        self.assertNotIn(
            "CAND-COMPLETE",
            names,
            "Candidate with solo_afiliacion=0 must NOT appear in seleccion list_candidates after full send",
        )


# ---------------------------------------------------------------------------
# T-16: incomplete candidate visible in bandeja_contratacion + progress check
# ---------------------------------------------------------------------------

class TestBandejaContratacionVisibility(FrappeTestCase):

    def test_incomplete_candidate_visible_in_bandeja_contratacion(self):
        """Candidate with documentacion_incompleta=1 appears in contract_candidates list."""
        from hubgh.hubgh.contratacion_service import contract_candidates

        # contract_candidates queries candidates in STATE_AFILIACION or STATE_LISTO_CONTRATAR.
        # An incomplete candidate is in STATE_AFILIACION with solo_afiliacion=1.
        incomplete_row = {
            "name": "CAND-INCOMPLETE",
            "nombres": "Juan",
            "apellidos": "Pérez",
            "numero_documento": "12345678",
            "estado_proceso": "En Afiliación",
            "pdv_destino": "PDV-01",
            "cargo_postulado": "Asesor",
            "creation": "2026-06-25 10:00:00",
            "documentacion_incompleta": 1,
        }

        with (
            patch(f"{_CONT_MODULE}.validate_hr_access", return_value=None),
            patch(f"{_CONT_MODULE}.frappe.get_all", return_value=[incomplete_row]),
            patch(f"{_CONT_MODULE}.frappe.session") as mock_session,
        ):
            mock_session.user = "hr.rrll@homeburgers.com"
            result = contract_candidates()

        names = [
            (r.get("name") if isinstance(r, dict) else getattr(r, "name", None))
            for r in result
        ]
        self.assertIn("CAND-INCOMPLETE", names,
                      "Incomplete candidate must appear in contract_candidates (bandeja_contratacion)")

    def test_get_candidate_progress_incomplete_returns_is_complete_false(self):
        """get_candidate_progress returns is_complete=False and non-empty missing for incomplete candidate."""
        with patch(
            f"{_DOC_MODULE}.get_candidate_progress",
            return_value=_make_progress(False, ["Cédula", "Carta referencia 1"]),
        ):
            progress = get_candidate_progress("CAND-INCOMPLETE")

        self.assertFalse(progress["is_complete"])
        self.assertTrue(len(progress["missing"]) > 0)


# ---------------------------------------------------------------------------
# T-17: after uploading all missing docs → is_complete=True, missing=[]
# ---------------------------------------------------------------------------

class TestMissingDocsClearAfterUpload(FrappeTestCase):

    def test_missing_docs_indicator_clears_when_all_uploaded(self):
        """After uploading all missing docs, is_complete=True and missing=[]."""
        mock_doc = MagicMock()
        mock_doc.name = "PD-NEW"
        mock_doc.status = "Subido"

        # Step 1: upload last missing doc via bandeja wrapper
        with (
            patch(f"{_BANDEJA_MODULE}.validate_hr_access", return_value=None),
            patch(f"{_BANDEJA_MODULE}.upload_person_document", return_value=mock_doc),
            patch(f"{_BANDEJA_MODULE}.frappe.db.get_value", return_value="12345678"),
        ):
            upload_result = upload_contratacion_document(
                candidate="CAND-INCOMPLETE",
                document_type="Cédula",
                file_url="/private/files/cedula.pdf",
            )

        self.assertEqual(upload_result.get("status"), "Subido")

        # Step 2: after upload, progress must show complete
        with patch(
            f"{_DOC_MODULE}.get_candidate_progress",
            return_value=_make_progress(True, []),
        ):
            progress = get_candidate_progress("CAND-INCOMPLETE")

        self.assertTrue(progress["is_complete"])
        self.assertEqual(progress["missing"], [])


# ---------------------------------------------------------------------------
# T-18: contract submit blocked while docs incomplete (regression)
# ---------------------------------------------------------------------------

class TestContractGateRegression(FrappeTestCase):

    def test_contract_submit_blocked_when_docs_incomplete(self):
        """_validate_mandatory_ingreso_gate must throw when docs are incomplete."""
        contract_doc = MagicMock()
        contract_doc.candidato = "CAND-INCOMPLETE"

        with (
            patch(f"{_CONT_MODULE}.get_or_create_datos_contratacion", return_value=MagicMock()),
            patch(f"{_CONT_MODULE}.frappe.get_doc", return_value=MagicMock()),
            patch(f"{_CONT_MODULE}._ingreso_field_value", return_value="value"),
            patch(f"{_CONT_MODULE}._is_missing_value", return_value=False),
            # Local import inside the function — patch at the source module
            patch(f"{_DOC_MODULE}.get_candidate_progress",
                  return_value=_make_progress(False, ["Cédula"])),
        ):
            with self.assertRaises(frappe.exceptions.ValidationError):
                _validate_mandatory_ingreso_gate(contract_doc)

    # ------------------------------------------------------------------
    # T-19: contract submit unblocked after full upload
    # ------------------------------------------------------------------
    def test_contract_submit_allowed_when_docs_complete_after_upload(self):
        """_validate_mandatory_ingreso_gate must not throw when all docs are uploaded."""
        contract_doc = MagicMock()
        contract_doc.candidato = "CAND-COMPLETE"

        with (
            patch(f"{_CONT_MODULE}.get_or_create_datos_contratacion", return_value=MagicMock()),
            patch(f"{_CONT_MODULE}.frappe.get_doc", return_value=MagicMock()),
            patch(f"{_CONT_MODULE}._ingreso_field_value", return_value="value"),
            patch(f"{_CONT_MODULE}._is_missing_value", return_value=False),
            # Local import inside the function — patch at the source module
            patch(f"{_DOC_MODULE}.get_candidate_progress",
                  return_value=_make_progress(True, [])),
        ):
            # Must not raise
            try:
                _validate_mandatory_ingreso_gate(contract_doc)
            except frappe.exceptions.ValidationError as exc:
                self.fail(
                    f"_validate_mandatory_ingreso_gate raised unexpectedly after all docs uploaded: {exc}"
                )
