# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para Cita Examen Egreso DocType schema.

TDD: Batch A.7 - verifica naming_series CXE-.YYYY.-, campos del design §1.7,
     independencia de Cita Examen Medico (ADR-3).
"""

from frappe.tests.utils import FrappeTestCase
import frappe


class TestCitaExamenEgresoSchema(FrappeTestCase):

    def test_doctype_exists(self):
        self.assertTrue(
            frappe.db.exists("DocType", "Cita Examen Egreso"),
            "DocType 'Cita Examen Egreso' no existe. Ejecutar bench migrate.",
        )

    def test_required_fields_present(self):
        meta = frappe.get_meta("Cita Examen Egreso")
        fieldnames = [f.fieldname for f in meta.fields]
        for field in ("naming_series", "empleado", "terminacion_origen",
                      "fecha_limite", "fecha_agendada", "estado", "ips", "token"):
            self.assertIn(field, fieldnames, f"Campo '{field}' no encontrado en Cita Examen Egreso")

    def test_naming_series_cxe(self):
        """naming_series debe incluir CXE-.YYYY.-"""
        meta = frappe.get_meta("Cita Examen Egreso")
        campo = next((f for f in meta.fields if f.fieldname == "naming_series"), None)
        self.assertIsNotNone(campo)
        self.assertIn("CXE-.YYYY.-", campo.options or "")

    def test_autoname_uses_naming_series(self):
        dt = frappe.get_doc("DocType", "Cita Examen Egreso")
        self.assertIn(
            dt.naming_rule,
            ('Naming Series', 'By "Naming Series" field'),
            f"naming_rule inesperado: {dt.naming_rule}",
        )

    def test_empleado_links_to_ficha_empleado(self):
        meta = frappe.get_meta("Cita Examen Egreso")
        campo = next((f for f in meta.fields if f.fieldname == "empleado"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.options, "Ficha Empleado")
        self.assertEqual(campo.reqd, 1)

    def test_terminacion_origen_links_to_terminacion_contrato(self):
        """terminacion_origen debe linkar a Terminacion Contrato (no a Cita Examen Medico)."""
        meta = frappe.get_meta("Cita Examen Egreso")
        campo = next((f for f in meta.fields if f.fieldname == "terminacion_origen"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.options, "Terminacion Contrato")
        self.assertEqual(campo.reqd, 1)

    def test_fecha_limite_is_required(self):
        meta = frappe.get_meta("Cita Examen Egreso")
        campo = next((f for f in meta.fields if f.fieldname == "fecha_limite"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.reqd, 1)

    def test_token_is_read_only(self):
        """token debe ser read_only=1 (generado en before_insert)."""
        meta = frappe.get_meta("Cita Examen Egreso")
        campo = next((f for f in meta.fields if f.fieldname == "token"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.read_only, 1)

    def test_estado_options(self):
        """estado debe incluir Pendiente Agendamiento como opcion y default."""
        meta = frappe.get_meta("Cita Examen Egreso")
        campo = next((f for f in meta.fields if f.fieldname == "estado"), None)
        self.assertIsNotNone(campo)
        options = (campo.options or "").split("\n")
        for opt in ("Pendiente Agendamiento", "Agendada", "Realizada", "No Realizada", "Cancelada"):
            self.assertIn(opt, options, f"Opcion '{opt}' no encontrada en estado")

    def test_not_extends_cita_examen_medico(self):
        """Verificar que Cita Examen Egreso no tiene link a Candidato (ADR-3)."""
        meta = frappe.get_meta("Cita Examen Egreso")
        fieldnames = [f.fieldname for f in meta.fields]
        self.assertNotIn("candidato", fieldnames,
                         "Cita Examen Egreso no debe tener campo candidato (seria extension de medico)")
