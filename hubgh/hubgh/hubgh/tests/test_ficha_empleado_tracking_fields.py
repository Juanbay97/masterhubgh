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
    # T-1.4-c: Legacy fields STILL exist (Phase 3 removes them — not now)
    # -------------------------------------------------------------------------
    def test_legacy_estado_retiro_operacion_sigue_existiendo(self):
        """
        Phase 1 es ADITIVA. estado_retiro_operacion NO debe ser removido todavía.
        """
        field = frappe.get_meta("Ficha Empleado").get_field("estado_retiro_operacion")
        self.assertIsNotNone(
            field,
            "estado_retiro_operacion debe seguir existiendo en Fase 1 (se borra en Fase 3)",
        )

    def test_legacy_motivo_retiro_sigue_existiendo(self):
        """Phase 1 es ADITIVA. motivo_retiro NO debe ser removido todavía."""
        field = frappe.get_meta("Ficha Empleado").get_field("motivo_retiro")
        self.assertIsNotNone(
            field,
            "motivo_retiro debe seguir existiendo en Fase 1 (se borra en Fase 3)",
        )

    def test_legacy_fecha_ultimo_dia_laborado_sigue_existiendo(self):
        """Phase 1 es ADITIVA. fecha_ultimo_dia_laborado NO debe ser removido todavía."""
        field = frappe.get_meta("Ficha Empleado").get_field("fecha_ultimo_dia_laborado")
        self.assertIsNotNone(
            field,
            "fecha_ultimo_dia_laborado debe seguir existiendo en Fase 1",
        )
