# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para Terminacion Validacion Item (child DocType) schema.

TDD: parte del Batch A - verifica istable=1 y campos del design §1.3
"""

from frappe.tests.utils import FrappeTestCase
import frappe


class TestTerminacionValidacionItemSchema(FrappeTestCase):

    def test_doctype_exists(self):
        self.assertTrue(
            frappe.db.exists("DocType", "Terminacion Validacion Item"),
            "DocType 'Terminacion Validacion Item' no existe.",
        )

    def test_is_table(self):
        """istable debe ser 1 (child table)."""
        dt = frappe.get_doc("DocType", "Terminacion Validacion Item")
        self.assertEqual(dt.istable, 1, "Terminacion Validacion Item debe ser istable=1")

    def test_required_fields_present(self):
        meta = frappe.get_meta("Terminacion Validacion Item")
        fieldnames = [f.fieldname for f in meta.fields]
        for field in ("codigo_validacion", "descripcion", "resultado",
                      "detalle", "override_por", "override_justificacion"):
            self.assertIn(field, fieldnames, f"Campo '{field}' no encontrado")

    def test_resultado_options(self):
        """resultado debe tener opciones: OK, Alerta, Bloqueante, No Aplica, Override."""
        meta = frappe.get_meta("Terminacion Validacion Item")
        campo = next((f for f in meta.fields if f.fieldname == "resultado"), None)
        self.assertIsNotNone(campo)
        options = (campo.options or "").split("\n")
        for opt in ("OK", "Alerta", "Bloqueante", "No Aplica", "Override"):
            self.assertIn(opt, options, f"Opcion '{opt}' no encontrada en resultado")

    def test_resultado_is_required(self):
        meta = frappe.get_meta("Terminacion Validacion Item")
        campo = next((f for f in meta.fields if f.fieldname == "resultado"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.reqd, 1)

    def test_codigo_validacion_is_required(self):
        meta = frappe.get_meta("Terminacion Validacion Item")
        campo = next((f for f in meta.fields if f.fieldname == "codigo_validacion"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.reqd, 1)
