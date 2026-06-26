# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""set_candidate_status_from_progress must not regress advanced candidates.

Uploading a document for a candidate already in afiliación / listo-para-contratar
/ contratado / examen médico must NOT pull them back to "En documentación"
(which would drop them out of the RRLL contratación board before the contract
is created).
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.candidate_states import (
    STATE_AFILIACION,
    STATE_CONTRATADO,
    STATE_DOCUMENTACION,
    STATE_EXAMEN_MEDICO,
    STATE_LISTO_CONTRATAR,
)
from hubgh.hubgh.document_service import set_candidate_status_from_progress


class TestStatusNoRegress(FrappeTestCase):
    def _assert_preserved(self, current):
        with (
            patch(
                "hubgh.hubgh.document_service.frappe.db.get_value",
                return_value=current,
            ),
            patch("hubgh.hubgh.document_service.frappe.db.set_value") as set_value,
            patch("hubgh.hubgh.document_service.get_candidate_progress"),
        ):
            result = set_candidate_status_from_progress("CAND-X")
            self.assertEqual(result, current)
            set_value.assert_not_called()

    def test_afiliacion_not_regressed(self):
        self._assert_preserved(STATE_AFILIACION)

    def test_listo_contratar_not_regressed(self):
        self._assert_preserved(STATE_LISTO_CONTRATAR)

    def test_contratado_not_regressed(self):
        self._assert_preserved(STATE_CONTRATADO)

    def test_examen_medico_not_regressed(self):
        self._assert_preserved(STATE_EXAMEN_MEDICO)

    def test_documentacion_still_updates(self):
        """A candidate still in the documentation phase is updated as before."""
        with (
            patch(
                "hubgh.hubgh.document_service.frappe.db.get_value",
                return_value=STATE_DOCUMENTACION,
            ),
            patch("hubgh.hubgh.document_service.frappe.db.set_value") as set_value,
            patch("hubgh.hubgh.document_service.get_candidate_progress"),
        ):
            set_candidate_status_from_progress("CAND-X")
            set_value.assert_called_once()
