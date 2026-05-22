# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para Terminacion Subproceso (child DocType) schema.

TDD: parte del Batch A - verifica istable=1 y campos del design §1.4
"""

from frappe.tests.utils import FrappeTestCase
import frappe


AREA_OPTIONS = ["sistemas", "rrll_dotacion", "operacion", "sst", "compensacion", "jefe_pdv", "nomina"]
ESTADO_OPTIONS = ["Pendiente", "En Proceso", "Completado", "No Aplica", "Bloqueado"]


class TestTerminacionSubprocesoSchema(FrappeTestCase):

    def test_doctype_exists(self):
        self.assertTrue(
            frappe.db.exists("DocType", "Terminacion Subproceso"),
            "DocType 'Terminacion Subproceso' no existe.",
        )

    def test_is_table(self):
        """istable debe ser 1."""
        dt = frappe.get_doc("DocType", "Terminacion Subproceso")
        self.assertEqual(dt.istable, 1)

    def test_required_fields_present(self):
        meta = frappe.get_meta("Terminacion Subproceso")
        fieldnames = [f.fieldname for f in meta.fields]
        for field in ("area", "responsable_rol", "responsable_usuario",
                      "tarea_descripcion", "estado", "fecha_notificacion",
                      "fecha_completado", "evidencia", "notas"):
            self.assertIn(field, fieldnames, f"Campo '{field}' no encontrado")

    def test_area_options(self):
        """area debe tener las 7 opciones del design."""
        meta = frappe.get_meta("Terminacion Subproceso")
        campo = next((f for f in meta.fields if f.fieldname == "area"), None)
        self.assertIsNotNone(campo)
        options = (campo.options or "").split("\n")
        for opt in AREA_OPTIONS:
            self.assertIn(opt, options, f"Opcion de area '{opt}' no encontrada")

    def test_area_is_required(self):
        meta = frappe.get_meta("Terminacion Subproceso")
        campo = next((f for f in meta.fields if f.fieldname == "area"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.reqd, 1)

    def test_estado_options(self):
        """estado debe tener las 5 opciones del design."""
        meta = frappe.get_meta("Terminacion Subproceso")
        campo = next((f for f in meta.fields if f.fieldname == "estado"), None)
        self.assertIsNotNone(campo)
        options = (campo.options or "").split("\n")
        for opt in ESTADO_OPTIONS:
            self.assertIn(opt, options, f"Opcion de estado '{opt}' no encontrada")

    def test_estado_default_pendiente(self):
        """estado debe tener default 'Pendiente'."""
        meta = frappe.get_meta("Terminacion Subproceso")
        campo = next((f for f in meta.fields if f.fieldname == "estado"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.default, "Pendiente")
