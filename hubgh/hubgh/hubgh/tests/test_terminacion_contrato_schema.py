# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para Terminacion Contrato DocType schema.

TDD Cycle: RED (A.1) -> GREEN (A.2) -> TRIANGULATE -> REFACTOR

Tests:
- DocType existe
- Campos obligatorios presentes
- naming_series TC-.YYYY.-
- title_field = empleado
- track_changes = 1
- estado options y default Iniciado
- child tables: checklist_validaciones + subprocesos
- read_only snapshots: pdv_al_terminar, cargo_al_terminar, iniciado_por, iniciado_en
"""

from frappe.tests.utils import FrappeTestCase
import frappe


REQUIRED_FIELDS = [
    "naming_series",
    "empleado",
    "causal",
    "fecha_ultimo_dia",
    "fecha_terminacion_efectiva",
    "estado",
    "iniciado_por",
    "iniciado_en",
    "justificacion",
    "pdv_al_terminar",
    "cargo_al_terminar",
    "checklist_validaciones",
    "subprocesos",
    "carta_terminacion",
    "resumen_cierre",
    "cancelado_motivo",
    "override_role_block",
]


class TestTerminacionContratoSchema(FrappeTestCase):

    def test_doctype_exists(self):
        """DocType Terminacion Contrato debe existir tras bench migrate."""
        self.assertTrue(
            frappe.db.exists("DocType", "Terminacion Contrato"),
            "DocType 'Terminacion Contrato' no existe. Ejecutar bench migrate.",
        )

    def test_required_fields_present(self):
        """Todos los campos del design deben estar presentes."""
        meta = frappe.get_meta("Terminacion Contrato")
        fieldnames = [f.fieldname for f in meta.fields]
        for field in REQUIRED_FIELDS:
            self.assertIn(field, fieldnames, f"Campo '{field}' no encontrado en Terminacion Contrato")

    def test_naming_series_options(self):
        """naming_series debe incluir TC-.YYYY.- como opcion."""
        meta = frappe.get_meta("Terminacion Contrato")
        campo = next((f for f in meta.fields if f.fieldname == "naming_series"), None)
        self.assertIsNotNone(campo, "Campo naming_series no encontrado")
        self.assertIn("TC-.YYYY.-", campo.options or "")

    def test_autoname_uses_naming_series(self):
        """autoname debe usar Naming Series."""
        dt = frappe.get_doc("DocType", "Terminacion Contrato")
        self.assertIn(
            dt.naming_rule,
            ('Naming Series', 'By "Naming Series" field'),
            f"naming_rule inesperado: {dt.naming_rule}",
        )

    def test_track_changes_enabled(self):
        """track_changes debe estar habilitado."""
        dt = frappe.get_doc("DocType", "Terminacion Contrato")
        self.assertEqual(dt.track_changes, 1)

    def test_title_field(self):
        """title_field debe ser empleado."""
        dt = frappe.get_doc("DocType", "Terminacion Contrato")
        self.assertEqual(dt.title_field, "empleado")

    def test_estado_default_iniciado(self):
        """estado debe tener default 'Iniciado'."""
        meta = frappe.get_meta("Terminacion Contrato")
        campo = next((f for f in meta.fields if f.fieldname == "estado"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.default, "Iniciado")

    def test_estado_options(self):
        """estado debe tener opciones: Iniciado, En Curso, Cerrado, Cancelado."""
        meta = frappe.get_meta("Terminacion Contrato")
        campo = next((f for f in meta.fields if f.fieldname == "estado"), None)
        self.assertIsNotNone(campo)
        options = (campo.options or "").split("\n")
        for opt in ("Iniciado", "En Curso", "Cerrado", "Cancelado"):
            self.assertIn(opt, options, f"Opcion '{opt}' no encontrada en estado")

    def test_empleado_links_to_ficha_empleado(self):
        """empleado debe linkar a Ficha Empleado."""
        meta = frappe.get_meta("Terminacion Contrato")
        campo = next((f for f in meta.fields if f.fieldname == "empleado"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.options, "Ficha Empleado")
        self.assertEqual(campo.reqd, 1)

    def test_causal_links_to_causal_terminacion(self):
        """causal debe linkar a Causal Terminacion."""
        meta = frappe.get_meta("Terminacion Contrato")
        campo = next((f for f in meta.fields if f.fieldname == "causal"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.options, "Causal Terminacion")
        self.assertEqual(campo.reqd, 1)

    def test_checklist_validaciones_is_table(self):
        """checklist_validaciones debe ser Table de Terminacion Validacion Item."""
        meta = frappe.get_meta("Terminacion Contrato")
        campo = next((f for f in meta.fields if f.fieldname == "checklist_validaciones"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.fieldtype, "Table")
        self.assertEqual(campo.options, "Terminacion Validacion Item")

    def test_subprocesos_is_table(self):
        """subprocesos debe ser Table de Terminacion Subproceso."""
        meta = frappe.get_meta("Terminacion Contrato")
        campo = next((f for f in meta.fields if f.fieldname == "subprocesos"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.fieldtype, "Table")
        self.assertEqual(campo.options, "Terminacion Subproceso")

    def test_pdv_al_terminar_is_read_only(self):
        """pdv_al_terminar debe ser read_only=1 (snapshot)."""
        meta = frappe.get_meta("Terminacion Contrato")
        campo = next((f for f in meta.fields if f.fieldname == "pdv_al_terminar"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.read_only, 1)

    def test_cargo_al_terminar_is_read_only(self):
        """cargo_al_terminar debe ser read_only=1 (snapshot)."""
        meta = frappe.get_meta("Terminacion Contrato")
        campo = next((f for f in meta.fields if f.fieldname == "cargo_al_terminar"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.read_only, 1)

    def test_iniciado_por_is_read_only(self):
        """iniciado_por debe ser read_only=1."""
        meta = frappe.get_meta("Terminacion Contrato")
        campo = next((f for f in meta.fields if f.fieldname == "iniciado_por"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.read_only, 1)

    def test_override_role_block_is_check(self):
        """override_role_block debe ser tipo Check con default 0."""
        meta = frappe.get_meta("Terminacion Contrato")
        campo = next((f for f in meta.fields if f.fieldname == "override_role_block"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.fieldtype, "Check")
        self.assertIn(str(campo.default or "0"), ("0", ""))
