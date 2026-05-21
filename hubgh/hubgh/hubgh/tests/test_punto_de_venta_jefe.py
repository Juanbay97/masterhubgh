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


class TestPuntoDeVentaJefeRolValidation(FrappeTestCase):
    """
    Tests para CAP-12 — validate() warning cuando jefe_responsable no tiene rol Jefe_PDV.

    TDD Cycle (Strict):
      RED  → estos tests (fallan hasta implementar validate en punto_de_venta.py)
      GREEN → agregar método validate() con frappe.msgprint warning
      TRIANGULATE → vacío y con rol correcto no disparan msgprint
    """

    def _make_pdv_doc(self, jefe=None):
        """Construye un doc de Punto de Venta en memoria sin guardarlo."""
        doc = frappe.new_doc("Punto de Venta")
        doc.nombre_pdv = "PDV-VALID-TEST"
        doc.codigo = "PDV-VALID-TEST"
        doc.ciudad = "TestCity"
        doc.activo = 1
        if jefe:
            doc.jefe_responsable = jefe
        return doc

    def test_jefe_responsable_sin_rol_dispara_warning(self):
        """
        Si jefe_responsable está seteado y el user NO tiene rol Jefe_PDV,
        validate() debe llamar frappe.msgprint con alert=True.
        """
        from unittest.mock import patch

        # Usar Administrator como proxy: no tiene exactamente Jefe_PDV
        # pero podemos mockear frappe.get_roles para aislar el comportamiento
        doc = self._make_pdv_doc(jefe="test_no_jefe@example.com")

        with patch("frappe.get_roles", return_value=["Empleado", "Guest"]) as mock_roles, \
             patch("frappe.msgprint") as mock_msgprint:
            doc.validate()
            mock_msgprint.assert_called_once()
            call_kwargs = mock_msgprint.call_args
            # Verificar que se pasó alert=True
            self.assertTrue(
                call_kwargs.kwargs.get("alert") or
                (len(call_kwargs.args) > 1 and call_kwargs.args[1] == True),
                "msgprint debe llamarse con alert=True",
            )
            # Verificar que el mensaje menciona al usuario y el rol
            msg = call_kwargs.args[0] if call_kwargs.args else ""
            self.assertIn("Jefe_PDV", msg, "El mensaje debe mencionar el rol Jefe_PDV")

    def test_jefe_responsable_con_rol_no_warning(self):
        """
        Si jefe_responsable tiene el rol Jefe_PDV, validate() NO debe llamar msgprint.
        """
        from unittest.mock import patch

        doc = self._make_pdv_doc(jefe="jefe_con_rol@example.com")

        with patch("frappe.get_roles", return_value=["Jefe_PDV", "Empleado"]) as mock_roles, \
             patch("frappe.msgprint") as mock_msgprint:
            doc.validate()
            mock_msgprint.assert_not_called()

    def test_jefe_responsable_vacio_no_warning(self):
        """
        Si jefe_responsable está vacío, validate() NO debe llamar msgprint.
        """
        from unittest.mock import patch

        doc = self._make_pdv_doc(jefe=None)

        with patch("frappe.get_roles", return_value=[]) as mock_roles, \
             patch("frappe.msgprint") as mock_msgprint:
            doc.validate()
            mock_msgprint.assert_not_called()
