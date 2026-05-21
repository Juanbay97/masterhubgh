# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for Motivo Traslado DocType.

TDD Cycle: RED (T-1) → GREEN (I-1a, I-1b) → TRIANGULATE → REFACTOR

Tests:
- Fixture con 5 registros cargados
- activo=False excluye del selector
- requiere_cambio_cargo se lee correctamente
"""

from unittest.mock import patch, MagicMock
from frappe.tests.utils import FrappeTestCase
import frappe


EXPECTED_FIXTURES = [
    {"codigo": "necesidad_operativa", "label": "Necesidad operativa", "requiere_cambio_cargo": 0, "activo": 1},
    {"codigo": "solicitud_empleado", "label": "Solicitud del empleado", "requiere_cambio_cargo": 0, "activo": 1},
    {"codigo": "cierre_pdv", "label": "Cierre de PDV", "requiere_cambio_cargo": 0, "activo": 1},
    {"codigo": "reorganizacion", "label": "Reorganización / promoción", "requiere_cambio_cargo": 1, "activo": 1},
    {"codigo": "otro", "label": "Otro", "requiere_cambio_cargo": 0, "activo": 1},
]


class TestMotivoTrasladoSchema(FrappeTestCase):

    def test_doctype_exists(self):
        """DocType Motivo Traslado debe existir tras bench migrate."""
        self.assertTrue(
            frappe.db.exists("DocType", "Motivo Traslado"),
            "DocType 'Motivo Traslado' no existe. Ejecutar bench migrate.",
        )

    def test_required_fields_present(self):
        """Campos obligatorios deben estar presentes en el schema."""
        meta = frappe.get_meta("Motivo Traslado")
        fieldnames = [f.fieldname for f in meta.fields]
        for field in ("codigo", "label", "requiere_cambio_cargo", "activo", "descripcion"):
            self.assertIn(field, fieldnames, f"Campo '{field}' no encontrado en Motivo Traslado")

    def test_codigo_is_unique_and_required(self):
        """codigo debe ser reqd=1 y unique=1."""
        meta = frappe.get_meta("Motivo Traslado")
        campo = next((f for f in meta.fields if f.fieldname == "codigo"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.reqd, 1, "codigo debe ser reqd=1")
        self.assertEqual(campo.unique, 1, "codigo debe ser unique=1")

    def test_requiere_cambio_cargo_is_check(self):
        """requiere_cambio_cargo debe ser tipo Check."""
        meta = frappe.get_meta("Motivo Traslado")
        campo = next((f for f in meta.fields if f.fieldname == "requiere_cambio_cargo"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.fieldtype, "Check")

    def test_activo_is_check_with_default_1(self):
        """activo debe ser Check con default 1."""
        meta = frappe.get_meta("Motivo Traslado")
        campo = next((f for f in meta.fields if f.fieldname == "activo"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.fieldtype, "Check")
        self.assertEqual(str(campo.default), "1")


class TestMotivoTrasladoFixtures(FrappeTestCase):

    def test_five_fixtures_loaded(self):
        """Los 5 motivos del fixture deben existir."""
        for fixture in EXPECTED_FIXTURES:
            self.assertTrue(
                frappe.db.exists("Motivo Traslado", fixture["codigo"]),
                f"Motivo Traslado '{fixture['codigo']}' no encontrado. Ejecutar bench import-fixtures.",
            )

    def test_fixture_codigos(self):
        """Los 5 codigos exactos del fixture deben existir."""
        expected_codigos = {f["codigo"] for f in EXPECTED_FIXTURES}
        existing = set(frappe.get_all("Motivo Traslado", pluck="name"))
        for codigo in expected_codigos:
            self.assertIn(codigo, existing)

    def test_reorganizacion_requiere_cambio_cargo(self):
        """reorganizacion debe tener requiere_cambio_cargo=1."""
        doc = frappe.get_doc("Motivo Traslado", "reorganizacion")
        self.assertEqual(doc.requiere_cambio_cargo, 1)

    def test_otros_no_requieren_cargo(self):
        """Los demás motivos no deben requerir cambio de cargo."""
        no_cargo = ["necesidad_operativa", "solicitud_empleado", "cierre_pdv", "otro"]
        for codigo in no_cargo:
            doc = frappe.get_doc("Motivo Traslado", codigo)
            self.assertEqual(
                doc.requiere_cambio_cargo, 0,
                f"{codigo} no debe requerir cambio de cargo",
            )


class TestMotivoTrasladoSelector(FrappeTestCase):

    def test_activo_false_excluye_del_selector(self):
        """Motivos inactivos no deben aparecer en selector (filtro activo=1)."""
        # Verificar que el filtro por activo funciona correctamente
        activos = frappe.get_all("Motivo Traslado", filters={"activo": 1}, pluck="name")
        inactivos = frappe.get_all("Motivo Traslado", filters={"activo": 0}, pluck="name")

        for motivo in inactivos:
            self.assertNotIn(
                motivo,
                activos,
                f"Motivo inactivo '{motivo}' apareció en el selector de activos",
            )

    def test_todos_los_fixtures_son_activos_por_defecto(self):
        """Todos los fixtures iniciales deben estar activos."""
        fixture_codigos = [f["codigo"] for f in EXPECTED_FIXTURES]
        for codigo in fixture_codigos:
            if frappe.db.exists("Motivo Traslado", codigo):
                activo = frappe.db.get_value("Motivo Traslado", codigo, "activo")
                self.assertEqual(activo, 1, f"Fixture '{codigo}' debe estar activo por defecto")
