# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — T-11, T-12 (RED): upload_contratacion_document wrapper in bandeja_contratacion.

Tests cover:
  T-11  HR Labor Relations / Gestión Humana role → upload succeeds (delegates to upload_person_document)
  T-12  Non-HR role → validate_hr_access raises ValidationError

RED until T-13 (bandeja_contratacion.py implementation) lands.
"""

from unittest.mock import patch, MagicMock

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.page.bandeja_contratacion import bandeja_contratacion


_MODULE = "hubgh.hubgh.page.bandeja_contratacion.bandeja_contratacion"


class TestBandejaUploadWrapper(FrappeTestCase):
    """Unit tests for the upload_contratacion_document whitelisted wrapper."""

    # ------------------------------------------------------------------
    # T-11: HR Labor Relations role is accepted
    # ------------------------------------------------------------------
    def test_upload_contratacion_document_hr_role_accepted(self):
        """A user with HR Labor Relations role can upload without permission error."""
        mock_doc = MagicMock()
        mock_doc.name = "PD-001"
        mock_doc.status = "Subido"

        with (
            patch(f"{_MODULE}.validate_hr_access", return_value=None),
            patch(f"{_MODULE}.upload_person_document", return_value=mock_doc),
            patch(f"{_MODULE}.frappe.db.get_value", return_value="12345678"),
        ):
            result = bandeja_contratacion.upload_contratacion_document(
                candidate="CAND-001",
                document_type="Cédula",
                file_url="/private/files/cedula.pdf",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.get("status"), "Subido")
        self.assertEqual(result.get("name"), "PD-001")

    # ------------------------------------------------------------------
    # T-12: Non-HR role is rejected
    # ------------------------------------------------------------------
    def test_upload_contratacion_document_non_hr_role_rejected(self):
        """A user without HR Labor Relations / Gestión Humana role must be rejected."""
        with patch(
            f"{_MODULE}.validate_hr_access",
            side_effect=frappe.exceptions.ValidationError("No autorizado"),
        ):
            with self.assertRaises(frappe.exceptions.ValidationError):
                bandeja_contratacion.upload_contratacion_document(
                    candidate="CAND-001",
                    document_type="Cédula",
                    file_url="/private/files/cedula.pdf",
                )
