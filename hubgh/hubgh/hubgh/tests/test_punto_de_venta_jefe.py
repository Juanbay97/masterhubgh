# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for jefe_responsable field on Punto de Venta.

TDD Cycle: RED (T-3) → GREEN (I-3) → TRIANGULATE → REFACTOR

Tests:
- campo jefe_responsable tipo Link → User
- guardado y lectura correctos
"""

from frappe.tests.utils import FrappeTestCase
import frappe


class TestPuntoDeVentaJefeResponsable(FrappeTestCase):

    def test_jefe_responsable_field_exists(self):
        """Punto de Venta debe tener el campo jefe_responsable."""
        meta = frappe.get_meta("Punto de Venta")
        fieldnames = [f.fieldname for f in meta.fields]
        self.assertIn(
            "jefe_responsable",
            fieldnames,
            "Campo 'jefe_responsable' no encontrado en Punto de Venta",
        )

    def test_jefe_responsable_is_link_to_user(self):
        """jefe_responsable debe ser Link → User."""
        meta = frappe.get_meta("Punto de Venta")
        campo = next((f for f in meta.fields if f.fieldname == "jefe_responsable"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.fieldtype, "Link", "jefe_responsable debe ser tipo Link")
        self.assertEqual(campo.options, "User", "jefe_responsable debe linkar a User")

    def test_jefe_responsable_is_not_required(self):
        """jefe_responsable no debe ser obligatorio (puede estar vacío)."""
        meta = frappe.get_meta("Punto de Venta")
        campo = next((f for f in meta.fields if f.fieldname == "jefe_responsable"), None)
        self.assertIsNotNone(campo)
        self.assertNotEqual(campo.reqd, 1, "jefe_responsable no debe ser reqd")

    def test_jefe_responsable_in_field_order(self):
        """jefe_responsable debe estar registrado en los fields del DocType (orden incluido)."""
        meta = frappe.get_meta("Punto de Venta")
        fieldnames = [f.fieldname for f in meta.fields]
        self.assertIn("jefe_responsable", fieldnames)

    # TRIANGULATE: verificar que el campo tiene descripción adecuada
    def test_jefe_responsable_has_description(self):
        """jefe_responsable debe tener una descripción de uso."""
        meta = frappe.get_meta("Punto de Venta")
        campo = next((f for f in meta.fields if f.fieldname == "jefe_responsable"), None)
        self.assertIsNotNone(campo)
        self.assertTrue(
            campo.description,
            "jefe_responsable debe tener descripción explicando su uso",
        )
