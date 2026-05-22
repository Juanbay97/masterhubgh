# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para seed de Configuracion Terminacion (Single).

TDD Cycle: RED (A.10) -> GREEN (A.11 patch) -> TRIANGULATE -> REFACTOR

Tests:
- El Single existe tras el patch
- Tiene 7 areas seed (incluye nomina aunque activo=0)
- Las 6 areas activas son: sistemas, rrll_dotacion, operacion, sst, compensacion, jefe_pdv
- nomina existe con activo=0 (fuera del MVP)
- Patch idempotente (sin duplicados, sin error en re-run)
"""

from frappe.tests.utils import FrappeTestCase
import frappe


EXPECTED_AREAS = [
    {"area": "sistemas", "activo": 1},
    {"area": "rrll_dotacion", "activo": 1},
    {"area": "operacion", "activo": 1},
    {"area": "sst", "activo": 1},
    {"area": "compensacion", "activo": 1},
    {"area": "jefe_pdv", "activo": 1},
    {"area": "nomina", "activo": 0},  # fuera del MVP
]


class TestConfiguracionTerminacionSeed(FrappeTestCase):

    def test_single_accesible(self):
        """Configuracion Terminacion Single debe ser accesible vía frappe.get_single."""
        try:
            doc = frappe.get_single("Configuracion Terminacion")
            self.assertIsNotNone(doc)
        except Exception as exc:
            self.fail(f"No se pudo acceder al Single Configuracion Terminacion: {exc}")

    def test_tiene_siete_areas(self):
        """Debe tener exactamente 7 areas seed."""
        doc = frappe.get_single("Configuracion Terminacion")
        self.assertEqual(
            len(doc.suscriptores_por_area), 7,
            f"Se esperaban 7 areas, hay {len(doc.suscriptores_por_area)}"
        )

    def test_seis_areas_activas(self):
        """6 areas deben estar activas (nomina=0 por ser MVP-out)."""
        doc = frappe.get_single("Configuracion Terminacion")
        activas = [r for r in doc.suscriptores_por_area if r.activo == 1]
        self.assertEqual(
            len(activas), 6,
            f"Se esperaban 6 areas activas, hay {len(activas)}"
        )

    def test_nomina_existe_y_esta_inactiva(self):
        """nomina debe existir pero con activo=0."""
        doc = frappe.get_single("Configuracion Terminacion")
        nomina_rows = [r for r in doc.suscriptores_por_area if r.area == "nomina"]
        self.assertEqual(len(nomina_rows), 1, "Debe haber exactamente 1 row para nomina")
        self.assertEqual(nomina_rows[0].activo, 0, "nomina debe estar inactiva (activo=0)")

    def test_todas_las_areas_esperadas_presentes(self):
        """Todas las areas del design deben estar presentes."""
        doc = frappe.get_single("Configuracion Terminacion")
        areas_presentes = {r.area for r in doc.suscriptores_por_area}
        for expected in EXPECTED_AREAS:
            self.assertIn(
                expected["area"], areas_presentes,
                f"Area '{expected['area']}' no encontrada en suscriptores_por_area"
            )

    def test_patch_idempotente(self):
        """El patch no debe generar duplicados ni errores en segunda ejecucion."""
        from hubgh.patches.seed_terminacion_config import execute
        try:
            execute()
            execute()
        except Exception as exc:
            self.fail(f"Patch seed_terminacion_config no debe lanzar excepcion: {exc}")

        # Verificar que sigue habiendo 7 areas (sin duplicados)
        doc = frappe.get_single("Configuracion Terminacion")
        self.assertEqual(len(doc.suscriptores_por_area), 7,
                         "Despues del patch doble, deben seguir siendo 7 areas")
