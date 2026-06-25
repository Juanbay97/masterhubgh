# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — T-01 (RED): Audit fields present on Datos Contratacion DocType.

Tests assert that the five audit fields required by the envio-incompleto-contratacion
change exist on the 'Datos Contratacion' DocType with the correct metadata.

RED until T-02 (schema update) lands.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

AUDIT_FIELDS = [
    "documentacion_incompleta",
    "motivo_doc_incompleta",
    "autorizado_por",
    "fecha_autorizacion",
    "docs_faltantes_snapshot",
]


class TestDatosContratacionSchema(FrappeTestCase):

    def _get_field(self, fieldname):
        meta = frappe.get_meta("Datos Contratacion")
        return next((f for f in meta.fields if f.fieldname == fieldname), None)

    def test_audit_fieldnames_exist(self):
        """All five audit fieldnames must be present on Datos Contratacion."""
        meta = frappe.get_meta("Datos Contratacion")
        present = [f.fieldname for f in meta.fields]
        for fieldname in AUDIT_FIELDS:
            self.assertIn(
                fieldname,
                present,
                f"Expected field '{fieldname}' to exist on Datos Contratacion",
            )

    def test_documentacion_incompleta_is_check_with_default_zero(self):
        """documentacion_incompleta must be a Check field with default '0'."""
        field = self._get_field("documentacion_incompleta")
        self.assertIsNotNone(field, "Field 'documentacion_incompleta' not found")
        self.assertEqual(field.fieldtype, "Check")
        self.assertEqual(str(field.default or "0"), "0")

    def test_motivo_doc_incompleta_is_small_text(self):
        """motivo_doc_incompleta must be a Small Text field."""
        field = self._get_field("motivo_doc_incompleta")
        self.assertIsNotNone(field, "Field 'motivo_doc_incompleta' not found")
        self.assertEqual(field.fieldtype, "Small Text")

    def test_motivo_doc_incompleta_has_mandatory_depends_on(self):
        """motivo_doc_incompleta must be mandatory when documentacion_incompleta == 1."""
        field = self._get_field("motivo_doc_incompleta")
        self.assertIsNotNone(field, "Field 'motivo_doc_incompleta' not found")
        self.assertIn(
            "documentacion_incompleta",
            field.mandatory_depends_on or "",
            "motivo_doc_incompleta must have mandatory_depends_on referencing documentacion_incompleta",
        )

    def test_autorizado_por_is_link_to_user(self):
        """autorizado_por must be a Link field pointing to User."""
        field = self._get_field("autorizado_por")
        self.assertIsNotNone(field, "Field 'autorizado_por' not found")
        self.assertEqual(field.fieldtype, "Link")
        self.assertEqual(field.options, "User")

    def test_fecha_autorizacion_is_datetime(self):
        """fecha_autorizacion must be a Datetime field."""
        field = self._get_field("fecha_autorizacion")
        self.assertIsNotNone(field, "Field 'fecha_autorizacion' not found")
        self.assertEqual(field.fieldtype, "Datetime")

    def test_docs_faltantes_snapshot_is_small_text(self):
        """docs_faltantes_snapshot must be a Small Text field."""
        field = self._get_field("docs_faltantes_snapshot")
        self.assertIsNotNone(field, "Field 'docs_faltantes_snapshot' not found")
        self.assertIn(field.fieldtype, ("Small Text", "Long Text", "Text"))

    def test_audit_fields_in_field_order(self):
        """All five audit fields must appear in the field_order of the DocType."""
        dt = frappe.get_doc("DocType", "Datos Contratacion")
        field_order = list(dt.field_order or [])
        for fieldname in AUDIT_FIELDS:
            self.assertIn(
                fieldname,
                field_order,
                f"Expected '{fieldname}' to appear in Datos Contratacion field_order",
            )

    def test_audit_fields_under_seccion_auditoria(self):
        """documentacion_incompleta must appear after seccion_auditoria in field order."""
        dt = frappe.get_doc("DocType", "Datos Contratacion")
        field_order = list(dt.field_order or [])
        self.assertIn("seccion_auditoria", field_order)
        audit_pos = field_order.index("seccion_auditoria")
        dc_pos = field_order.index("documentacion_incompleta")
        self.assertGreater(
            dc_pos,
            audit_pos,
            "documentacion_incompleta must appear after seccion_auditoria in field_order",
        )
