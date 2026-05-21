"""
T-3.2 — RED schema tests for Ficha Empleado legacy field cleanup.

These tests verify that the 9 legacy retirement fields have been REMOVED
from ficha_empleado.json and that the 2 tracking fields added in Batch A are preserved.

Expected behavior BEFORE cleanup: tests asserting legacy fields are absent will FAIL (RED).
Expected behavior AFTER cleanup: all tests GREEN.
"""
import json
import os

from frappe.tests.utils import FrappeTestCase


def _load_ficha_json():
    """Load ficha_empleado.json directly from the filesystem."""
    base = os.path.dirname(__file__)
    # hubgh/hubgh/tests/ → go up to hubgh/hubgh/hubgh/doctype/ficha_empleado/
    json_path = os.path.join(
        base, "..", "hubgh", "doctype", "ficha_empleado", "ficha_empleado.json"
    )
    json_path = os.path.normpath(json_path)
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


LEGACY_FIELDS = [
    "retirement_section",
    "estado_retiro_operacion",
    "motivo_retiro",
    "fecha_ultimo_dia_laborado",
    "fecha_retiro_efectiva",
    "fecha_cierre_retiro",
    "detalle_retiro",
    "retiro_fuente_doctype",
    "retiro_fuente_name",
]

TRACKING_FIELDS = [
    "last_retirement_attempt_at",
    "last_retirement_attempt_source",
]


class TestFichaEmpleadoLegacyFieldsRemoved(FrappeTestCase):
    """Assert legacy retirement fields are absent from ficha_empleado.json."""

    def setUp(self):
        self.data = _load_ficha_json()
        self.fieldnames_in_fields = {f["fieldname"] for f in self.data.get("fields", [])}
        self.field_order = self.data.get("field_order", [])

    def test_retirement_section_removed_from_fields(self):
        self.assertNotIn("retirement_section", self.fieldnames_in_fields)

    def test_retirement_section_removed_from_field_order(self):
        self.assertNotIn("retirement_section", self.field_order)

    def test_estado_retiro_operacion_removed_from_fields(self):
        self.assertNotIn("estado_retiro_operacion", self.fieldnames_in_fields)

    def test_estado_retiro_operacion_removed_from_field_order(self):
        self.assertNotIn("estado_retiro_operacion", self.field_order)

    def test_motivo_retiro_removed_from_fields(self):
        self.assertNotIn("motivo_retiro", self.fieldnames_in_fields)

    def test_motivo_retiro_removed_from_field_order(self):
        self.assertNotIn("motivo_retiro", self.field_order)

    def test_fecha_ultimo_dia_laborado_removed_from_fields(self):
        self.assertNotIn("fecha_ultimo_dia_laborado", self.fieldnames_in_fields)

    def test_fecha_ultimo_dia_laborado_removed_from_field_order(self):
        self.assertNotIn("fecha_ultimo_dia_laborado", self.field_order)

    def test_fecha_retiro_efectiva_removed_from_fields(self):
        self.assertNotIn("fecha_retiro_efectiva", self.fieldnames_in_fields)

    def test_fecha_retiro_efectiva_removed_from_field_order(self):
        self.assertNotIn("fecha_retiro_efectiva", self.field_order)

    def test_fecha_cierre_retiro_removed_from_fields(self):
        self.assertNotIn("fecha_cierre_retiro", self.fieldnames_in_fields)

    def test_fecha_cierre_retiro_removed_from_field_order(self):
        self.assertNotIn("fecha_cierre_retiro", self.field_order)

    def test_detalle_retiro_removed_from_fields(self):
        self.assertNotIn("detalle_retiro", self.fieldnames_in_fields)

    def test_detalle_retiro_removed_from_field_order(self):
        self.assertNotIn("detalle_retiro", self.field_order)

    def test_retiro_fuente_doctype_removed_from_fields(self):
        self.assertNotIn("retiro_fuente_doctype", self.fieldnames_in_fields)

    def test_retiro_fuente_doctype_removed_from_field_order(self):
        self.assertNotIn("retiro_fuente_doctype", self.field_order)

    def test_retiro_fuente_name_removed_from_fields(self):
        self.assertNotIn("retiro_fuente_name", self.fieldnames_in_fields)

    def test_retiro_fuente_name_removed_from_field_order(self):
        self.assertNotIn("retiro_fuente_name", self.field_order)

    def test_no_search_fields_contain_legacy_names(self):
        """If search_fields exists, it must not contain any legacy retirement field."""
        search_fields = self.data.get("search_fields", "")
        if isinstance(search_fields, list):
            for field in LEGACY_FIELDS:
                self.assertNotIn(field, search_fields, f"{field} found in search_fields list")
        elif isinstance(search_fields, str):
            for field in LEGACY_FIELDS:
                self.assertNotIn(field, search_fields, f"{field} found in search_fields string")


class TestFichaEmpleadoTrackingFieldsPreserved(FrappeTestCase):
    """Assert the 2 tracking fields added in Batch A are preserved."""

    def setUp(self):
        self.data = _load_ficha_json()
        self.fields_by_name = {f["fieldname"]: f for f in self.data.get("fields", [])}
        self.field_order = self.data.get("field_order", [])

    def test_last_retirement_attempt_at_present_in_fields(self):
        self.assertIn("last_retirement_attempt_at", self.fields_by_name)

    def test_last_retirement_attempt_at_is_datetime(self):
        field = self.fields_by_name.get("last_retirement_attempt_at", {})
        self.assertEqual(field.get("fieldtype"), "Datetime")

    def test_last_retirement_attempt_at_is_read_only(self):
        field = self.fields_by_name.get("last_retirement_attempt_at", {})
        self.assertEqual(field.get("read_only"), 1)

    def test_last_retirement_attempt_at_in_field_order(self):
        self.assertIn("last_retirement_attempt_at", self.field_order)

    def test_last_retirement_attempt_source_present_in_fields(self):
        self.assertIn("last_retirement_attempt_source", self.fields_by_name)

    def test_last_retirement_attempt_source_is_data(self):
        field = self.fields_by_name.get("last_retirement_attempt_source", {})
        self.assertEqual(field.get("fieldtype"), "Data")

    def test_last_retirement_attempt_source_is_read_only(self):
        field = self.fields_by_name.get("last_retirement_attempt_source", {})
        self.assertEqual(field.get("read_only"), 1)

    def test_last_retirement_attempt_source_in_field_order(self):
        self.assertIn("last_retirement_attempt_source", self.field_order)

    def test_trazabilidad_section_present(self):
        """The Auditoría section break added in Batch A must still be present."""
        fields_by_name = {f["fieldname"]: f for f in self.data.get("fields", [])}
        self.assertIn("trazabilidad_section", fields_by_name)
