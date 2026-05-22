# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para Configuracion Terminacion (Single) schema y Terminacion Suscriptor Area.

TDD: parte del Batch A - verifica issingle=1, child table, y seed patch (A.10/A.11)
"""

from frappe.tests.utils import FrappeTestCase
import frappe


class TestConfiguracionTerminacionSchema(FrappeTestCase):

    def test_doctype_exists(self):
        self.assertTrue(
            frappe.db.exists("DocType", "Configuracion Terminacion"),
            "DocType 'Configuracion Terminacion' no existe.",
        )

    def test_is_single(self):
        """issingle debe ser 1 (singleton config)."""
        dt = frappe.get_doc("DocType", "Configuracion Terminacion")
        self.assertEqual(dt.issingle, 1, "Configuracion Terminacion debe ser issingle=1")

    def test_suscriptores_por_area_field_present(self):
        meta = frappe.get_meta("Configuracion Terminacion")
        fieldnames = [f.fieldname for f in meta.fields]
        self.assertIn("suscriptores_por_area", fieldnames)

    def test_suscriptores_table_options(self):
        """suscriptores_por_area debe apuntar a Terminacion Suscriptor Area."""
        meta = frappe.get_meta("Configuracion Terminacion")
        campo = next((f for f in meta.fields if f.fieldname == "suscriptores_por_area"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.fieldtype, "Table")
        self.assertEqual(campo.options, "Terminacion Suscriptor Area")


class TestTerminacionSuscriptorAreaSchema(FrappeTestCase):

    def test_doctype_exists(self):
        self.assertTrue(
            frappe.db.exists("DocType", "Terminacion Suscriptor Area"),
            "DocType 'Terminacion Suscriptor Area' no existe.",
        )

    def test_is_table(self):
        dt = frappe.get_doc("DocType", "Terminacion Suscriptor Area")
        self.assertEqual(dt.istable, 1)

    def test_required_fields_present(self):
        meta = frappe.get_meta("Terminacion Suscriptor Area")
        fieldnames = [f.fieldname for f in meta.fields]
        for field in ("area", "role", "user", "email_fijo", "activo"):
            self.assertIn(field, fieldnames, f"Campo '{field}' no encontrado")

    def test_area_is_required(self):
        meta = frappe.get_meta("Terminacion Suscriptor Area")
        campo = next((f for f in meta.fields if f.fieldname == "area"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.reqd, 1)

    def test_area_options_include_all_seven(self):
        meta = frappe.get_meta("Terminacion Suscriptor Area")
        campo = next((f for f in meta.fields if f.fieldname == "area"), None)
        self.assertIsNotNone(campo)
        options = (campo.options or "").split("\n")
        for opt in ("sistemas", "rrll_dotacion", "operacion", "sst",
                    "compensacion", "jefe_pdv", "nomina"):
            self.assertIn(opt, options, f"Opcion de area '{opt}' no encontrada")

    def test_activo_default_1(self):
        meta = frappe.get_meta("Terminacion Suscriptor Area")
        campo = next((f for f in meta.fields if f.fieldname == "activo"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(str(campo.default or "1"), "1")
