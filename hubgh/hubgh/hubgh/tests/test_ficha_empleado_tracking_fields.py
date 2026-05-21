# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for Ficha Empleado tracking fields added in Phase 1 (Batch A).

TDD Batch A — T-1.4
Strict TDD: written BEFORE the JSON is edited.

Verifica que:
- last_retirement_attempt_at existe como Datetime read_only
- last_retirement_attempt_source existe como Data read_only
- Los campos legacy de retiro SIGUEN existiendo (no se borran hasta Fase 3)
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestFichaEmpleadoTrackingFields(FrappeTestCase):
    def setUp(self):
        frappe.clear_cache(doctype="Ficha Empleado")

    # -------------------------------------------------------------------------
    # T-1.4-a: last_retirement_attempt_at field exists
    # -------------------------------------------------------------------------
    def test_last_retirement_attempt_at_existe(self):
        """El campo last_retirement_attempt_at debe existir en Ficha Empleado."""
        field = frappe.get_meta("Ficha Empleado").get_field("last_retirement_attempt_at")
        self.assertIsNotNone(
            field,
            "last_retirement_attempt_at debe estar en Ficha Empleado",
        )

    def test_last_retirement_attempt_at_es_datetime(self):
        """last_retirement_attempt_at debe ser de tipo Datetime."""
        field = frappe.get_meta("Ficha Empleado").get_field("last_retirement_attempt_at")
        if field is None:
            self.skipTest("Campo ausente — revisar I-1.4")
        self.assertEqual(field.fieldtype, "Datetime")

    def test_last_retirement_attempt_at_es_read_only(self):
        """last_retirement_attempt_at debe ser read_only=1."""
        field = frappe.get_meta("Ficha Empleado").get_field("last_retirement_attempt_at")
        if field is None:
            self.skipTest("Campo ausente — revisar I-1.4")
        self.assertEqual(field.read_only, 1)

    # -------------------------------------------------------------------------
    # T-1.4-b: last_retirement_attempt_source field exists
    # -------------------------------------------------------------------------
    def test_last_retirement_attempt_source_existe(self):
        """El campo last_retirement_attempt_source debe existir en Ficha Empleado."""
        field = frappe.get_meta("Ficha Empleado").get_field("last_retirement_attempt_source")
        self.assertIsNotNone(
            field,
            "last_retirement_attempt_source debe estar en Ficha Empleado",
        )

    def test_last_retirement_attempt_source_es_data(self):
        """last_retirement_attempt_source debe ser de tipo Data."""
        field = frappe.get_meta("Ficha Empleado").get_field("last_retirement_attempt_source")
        if field is None:
            self.skipTest("Campo ausente — revisar I-1.4")
        self.assertEqual(field.fieldtype, "Data")

    def test_last_retirement_attempt_source_es_read_only(self):
        """last_retirement_attempt_source debe ser read_only=1."""
        field = frappe.get_meta("Ficha Empleado").get_field("last_retirement_attempt_source")
        if field is None:
            self.skipTest("Campo ausente — revisar I-1.4")
        self.assertEqual(field.read_only, 1)

    # -------------------------------------------------------------------------
    # T-1.4-c: Legacy fields REMOVED in Phase 3 (updated from Batch A guards)
    # Phase 1 guards said "STILL exist — Phase 3 removes them". Phase 3 is done.
    # -------------------------------------------------------------------------
    def test_legacy_estado_retiro_operacion_removido_en_fase3(self):
        """
        Phase 3 completada. estado_retiro_operacion debe estar AUSENTE del schema.
        """
        field = frappe.get_meta("Ficha Empleado").get_field("estado_retiro_operacion")
        self.assertIsNone(
            field,
            "estado_retiro_operacion fue removido en Fase 3 — no debe existir en el schema",
        )

    def test_legacy_motivo_retiro_removido_en_fase3(self):
        """Phase 3 completada. motivo_retiro debe estar AUSENTE del schema."""
        field = frappe.get_meta("Ficha Empleado").get_field("motivo_retiro")
        self.assertIsNone(
            field,
            "motivo_retiro fue removido en Fase 3 — no debe existir en el schema",
        )

    def test_legacy_fecha_ultimo_dia_laborado_removido_en_fase3(self):
        """Phase 3 completada. fecha_ultimo_dia_laborado debe estar AUSENTE del schema."""
        field = frappe.get_meta("Ficha Empleado").get_field("fecha_ultimo_dia_laborado")
        self.assertIsNone(
            field,
            "fecha_ultimo_dia_laborado fue removido en Fase 3 — no debe existir en el schema",
        )
