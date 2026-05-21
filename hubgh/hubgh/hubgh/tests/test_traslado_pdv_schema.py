# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for Traslado PDV DocType schema.

TDD Cycle: RED (T-2) → GREEN (I-2) → TRIANGULATE → REFACTOR

Tests:
- Campos obligatorios presentes
- naming_series TRAS-.YYYY.-
- estado default Programado
- pdv_origen read_only
"""

from frappe.tests.utils import FrappeTestCase
import frappe


REQUIRED_FIELDS = [
    "naming_series",
    "empleado",
    "empleado_nombre",
    "estado",
    "fecha_aplicacion",
    "pdv_origen",
    "pdv_destino",
    "cargo_destino",
    "motivo",
    "justificacion",
    "aplicado_en",
    "aplicado_por",
    "anulado_en",
    "anulado_por",
    "motivo_anulacion",
    "payload_notificaciones",
]


class TestTrasladoPDVSchema(FrappeTestCase):

    def test_doctype_exists(self):
        """DocType Traslado PDV debe existir tras bench migrate."""
        self.assertTrue(
            frappe.db.exists("DocType", "Traslado PDV"),
            "DocType 'Traslado PDV' no existe. Ejecutar bench migrate.",
        )

    def test_required_fields_present(self):
        """Todos los campos definidos en el diseño deben estar presentes."""
        meta = frappe.get_meta("Traslado PDV")
        fieldnames = [f.fieldname for f in meta.fields]
        for field in REQUIRED_FIELDS:
            self.assertIn(field, fieldnames, f"Campo '{field}' no encontrado en Traslado PDV")

    def test_naming_series_options(self):
        """naming_series debe incluir TRAS-.YYYY.- como opción."""
        meta = frappe.get_meta("Traslado PDV")
        campo = next((f for f in meta.fields if f.fieldname == "naming_series"), None)
        self.assertIsNotNone(campo, "Campo naming_series no encontrado")
        self.assertIn("TRAS-.YYYY.-", campo.options or "")

    def test_estado_default_programado(self):
        """estado debe tener default 'Programado'."""
        meta = frappe.get_meta("Traslado PDV")
        campo = next((f for f in meta.fields if f.fieldname == "estado"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.default, "Programado")

    def test_estado_options(self):
        """estado debe tener opciones: Programado, Aplicado, Anulado."""
        meta = frappe.get_meta("Traslado PDV")
        campo = next((f for f in meta.fields if f.fieldname == "estado"), None)
        self.assertIsNotNone(campo)
        options = (campo.options or "").split("\n")
        for opt in ("Programado", "Aplicado", "Anulado"):
            self.assertIn(opt, options, f"Opción '{opt}' no encontrada en estado")

    def test_pdv_origen_is_read_only(self):
        """pdv_origen debe ser read_only=1 (snapshot inmutable)."""
        meta = frappe.get_meta("Traslado PDV")
        campo = next((f for f in meta.fields if f.fieldname == "pdv_origen"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.read_only, 1, "pdv_origen debe ser read_only=1")

    def test_pdv_origen_links_to_punto_de_venta(self):
        """pdv_origen y pdv_destino deben linkar a Punto de Venta."""
        meta = frappe.get_meta("Traslado PDV")
        for fieldname in ("pdv_origen", "pdv_destino"):
            campo = next((f for f in meta.fields if f.fieldname == fieldname), None)
            self.assertIsNotNone(campo, f"Campo '{fieldname}' no encontrado")
            self.assertEqual(campo.fieldtype, "Link")
            self.assertEqual(campo.options, "Punto de Venta")

    def test_empleado_links_to_ficha_empleado(self):
        """empleado debe linkar a Ficha Empleado."""
        meta = frappe.get_meta("Traslado PDV")
        campo = next((f for f in meta.fields if f.fieldname == "empleado"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.options, "Ficha Empleado")

    def test_motivo_links_to_motivo_traslado(self):
        """motivo debe linkar a Motivo Traslado."""
        meta = frappe.get_meta("Traslado PDV")
        campo = next((f for f in meta.fields if f.fieldname == "motivo"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.options, "Motivo Traslado")

    def test_payload_notificaciones_is_json(self):
        """payload_notificaciones debe ser tipo JSON."""
        meta = frappe.get_meta("Traslado PDV")
        campo = next((f for f in meta.fields if f.fieldname == "payload_notificaciones"), None)
        self.assertIsNotNone(campo)
        self.assertEqual(campo.fieldtype, "JSON")

    def test_empleado_nombre_fetch_from(self):
        """empleado_nombre debe hacer fetch_from de algún campo de nombres del empleado."""
        meta = frappe.get_meta("Traslado PDV")
        campo = next((f for f in meta.fields if f.fieldname == "empleado_nombre"), None)
        self.assertIsNotNone(campo)
        # Acepta fetch_from a nombres o nombre_completo (Ficha Empleado usa 'nombres')
        self.assertTrue(
            campo.fetch_from and campo.fetch_from.startswith("empleado."),
            f"empleado_nombre.fetch_from debe comenzar con 'empleado.', got: {campo.fetch_from}",
        )

    def test_track_changes_enabled(self):
        """track_changes debe estar habilitado (auditoría)."""
        dt = frappe.get_doc("DocType", "Traslado PDV")
        self.assertEqual(dt.track_changes, 1)

    # TRIANGULATE: verificar que autoname usa naming_series
    def test_autoname_uses_naming_series(self):
        """autoname debe estar configurado para usar Naming Series."""
        dt = frappe.get_doc("DocType", "Traslado PDV")
        # Frappe v15: naming_rule="Naming Series" y autoname="naming_series:"
        self.assertIn(
            dt.naming_rule,
            ("Naming Series", "By \"Naming Series\" field"),
            f"naming_rule inesperado: {dt.naming_rule}",
        )
