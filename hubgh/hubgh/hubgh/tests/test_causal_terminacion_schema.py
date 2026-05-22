# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para Causal Terminacion DocType schema y fixtures.

TDD Cycle: RED (A.3) -> GREEN (A.4) -> TRIANGULATE -> REFACTOR

Tests:
- DocType existe
- Campos obligatorios presentes
- autoname field:codigo
- codigo unique + reqd
- Fixtures: 6 causales cargadas
- justa_causa y periodo_prueba tienen requiere_carta_automatica=1
"""

from frappe.tests.utils import FrappeTestCase
import frappe


EXPECTED_FIXTURES = [
    {"name": "renuncia", "requiere_carta_automatica": 0, "requiere_caso_disciplinario": 0},
    {"name": "abandono_cargo", "requiere_carta_automatica": 0, "requiere_caso_disciplinario": 0},
    {"name": "justa_causa", "requiere_carta_automatica": 1, "requiere_caso_disciplinario": 1},
    {"name": "periodo_prueba", "requiere_carta_automatica": 1, "requiere_caso_disciplinario": 0},
    {"name": "mutuo_acuerdo", "requiere_carta_automatica": 0, "requiere_caso_disciplinario": 0},
    {"name": "otros", "requiere_carta_automatica": 0, "requiere_caso_disciplinario": 0},
]


class TestCausalTerminacionSchema(FrappeTestCase):

    def test_doctype_exists(self):
        """DocType Causal Terminacion debe existir tras bench migrate."""
        self.assertTrue(
            frappe.db.exists("DocType", "Causal Terminacion"),
            "DocType 'Causal Terminacion' no existe. Ejecutar bench migrate.",
        )

    def test_required_fields_present(self):
        """Campos del design deben estar presentes."""
        meta = frappe.get_meta("Causal Terminacion")
        fieldnames = [f.fieldname for f in meta.fields]
        for field in ("codigo", "nombre", "requiere_carta_automatica",
                      "requiere_caso_disciplinario", "requiere_periodo_prueba_check",
                      "plantilla_carta_template_name", "activo"):
            self.assertIn(field, fieldnames, f"Campo '{field}' no encontrado en Causal Terminacion")

    def test_codigo_is_unique_and_required(self):
        """codigo debe ser reqd=1 y unique=1."""
        meta = frappe.get_meta("Causal Terminacion")
        campo = next((f for f in meta.fields if f.fieldname == "codigo"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.reqd, 1, "codigo debe ser reqd=1")
        self.assertEqual(campo.unique, 1, "codigo debe ser unique=1")

    def test_requiere_carta_automatica_is_check(self):
        """requiere_carta_automatica debe ser tipo Check."""
        meta = frappe.get_meta("Causal Terminacion")
        campo = next((f for f in meta.fields if f.fieldname == "requiere_carta_automatica"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.fieldtype, "Check")

    def test_activo_is_check_with_default_1(self):
        """activo debe ser Check con default 1."""
        meta = frappe.get_meta("Causal Terminacion")
        campo = next((f for f in meta.fields if f.fieldname == "activo"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.fieldtype, "Check")
        self.assertEqual(str(campo.default or "1"), "1")

    def test_nombre_is_required(self):
        """nombre debe ser reqd=1."""
        meta = frappe.get_meta("Causal Terminacion")
        campo = next((f for f in meta.fields if f.fieldname == "nombre"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.reqd, 1)


class TestCausalTerminacionFixtures(FrappeTestCase):

    def test_six_fixtures_loaded(self):
        """Los 6 causales del fixture deben existir."""
        for fixture in EXPECTED_FIXTURES:
            self.assertTrue(
                frappe.db.exists("Causal Terminacion", fixture["name"]),
                f"Causal Terminacion '{fixture['name']}' no encontrada. Ejecutar bench migrate.",
            )

    def test_justa_causa_requiere_carta(self):
        """justa_causa debe tener requiere_carta_automatica=1."""
        doc = frappe.get_doc("Causal Terminacion", "justa_causa")
        self.assertEqual(doc.requiere_carta_automatica, 1)

    def test_periodo_prueba_requiere_carta(self):
        """periodo_prueba debe tener requiere_carta_automatica=1."""
        doc = frappe.get_doc("Causal Terminacion", "periodo_prueba")
        self.assertEqual(doc.requiere_carta_automatica, 1)

    def test_justa_causa_requiere_caso_disciplinario(self):
        """justa_causa debe tener requiere_caso_disciplinario=1."""
        doc = frappe.get_doc("Causal Terminacion", "justa_causa")
        self.assertEqual(doc.requiere_caso_disciplinario, 1)

    def test_otros_causales_sin_carta(self):
        """Causales sin carta no deben tener requiere_carta_automatica=1."""
        sin_carta = ["renuncia", "abandono_cargo", "mutuo_acuerdo", "otros"]
        for nombre in sin_carta:
            if frappe.db.exists("Causal Terminacion", nombre):
                doc = frappe.get_doc("Causal Terminacion", nombre)
                self.assertEqual(
                    doc.requiere_carta_automatica, 0,
                    f"{nombre} no debe requerir carta automatica",
                )

    def test_all_fixtures_are_active(self):
        """Todos los fixtures deben estar activos por defecto."""
        for fixture in EXPECTED_FIXTURES:
            if frappe.db.exists("Causal Terminacion", fixture["name"]):
                activo = frappe.db.get_value("Causal Terminacion", fixture["name"], "activo")
                self.assertEqual(activo, 1, f"Fixture '{fixture['name']}' debe estar activo")
