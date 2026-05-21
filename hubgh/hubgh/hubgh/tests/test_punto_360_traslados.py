# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para la integración Punto 360 + Traslados PDV — Fase 8.

TDD Cycle (Strict):
  RED  → este archivo (tests fallan hasta implementar get_traslados_activos)
  GREEN → extender punto_360.py
  REFACTOR → verificar count correcto origen + destino

Cubre:
- get_traslados_activos_count solo cuenta Programados
- Cuenta traslados donde PDV es origen O destino
- No cuenta Aplicados ni Anulados
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days


def _ensure_pdv(name):
    if not frappe.db.exists("Punto de Venta", name):
        doc = frappe.get_doc({
            "doctype": "Punto de Venta",
            "nombre_pdv": name,
            "codigo": name,
            "ciudad": "TestCityPunto360",
            "activo": 1,
        })
        doc.insert(ignore_permissions=True)
    return name


def _ensure_empleado(cedula, pdv, estado="Activo"):
    if not frappe.db.exists("Ficha Empleado", cedula):
        doc = frappe.get_doc({
            "doctype": "Ficha Empleado",
            "nombres": cedula,
            "apellidos": "Punto360Test",
            "cedula": cedula,
            "pdv": pdv,
            "estado": estado,
            "email": f"{cedula.lower().replace('-', '')}@punto360test.com",
        })
        doc.insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Ficha Empleado", cedula, "pdv", pdv)
    return cedula


def _ensure_motivo(codigo="necesidad_operativa"):
    if not frappe.db.exists("Motivo Traslado", codigo):
        doc = frappe.get_doc({
            "doctype": "Motivo Traslado",
            "codigo": codigo,
            "label": "Necesidad operativa",
            "requiere_cambio_cargo": 0,
            "activo": 1,
        })
        doc.insert(ignore_permissions=True)
    return codigo


def _make_traslado_sql(empleado, pdv_origen, pdv_destino, estado="Programado", fecha_aplicacion=None):
    """Inserta traslado directamente para tests."""
    fecha = fecha_aplicacion or today()
    name = f"TRAS-PT360-{frappe.generate_hash(length=8)}"
    frappe.db.sql("""
        INSERT INTO `tabTraslado PDV`
        (name, docstatus, creation, modified, owner, modified_by,
         empleado, pdv_origen, pdv_destino, estado, fecha_aplicacion,
         motivo, justificacion, solicitado_por)
        VALUES
        (%s, 0, NOW(), NOW(), 'Administrator', 'Administrator',
         %s, %s, %s, %s, %s,
         'necesidad_operativa', 'Justificacion suficientemente larga para el test',
         'Administrator')
    """, (name, empleado, pdv_origen, pdv_destino, estado, fecha))
    frappe.db.commit()
    return name


class TestPunto360Traslados(FrappeTestCase):
    """Tests para get_traslados_activos_count en punto_360.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pdv_x = _ensure_pdv("PT360-PDV-X")
        cls.pdv_y = _ensure_pdv("PT360-PDV-Y")
        cls.pdv_z = _ensure_pdv("PT360-PDV-Z")
        cls.emp_1 = _ensure_empleado("EMP-PT360-001", cls.pdv_x)
        cls.emp_2 = _ensure_empleado("EMP-PT360-002", cls.pdv_x)
        cls.emp_3 = _ensure_empleado("EMP-PT360-003", cls.pdv_y)
        _ensure_motivo()

    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.sql("DELETE FROM `tabTraslado PDV` WHERE name LIKE 'TRAS-PT360-%'")
        frappe.db.commit()

    def test_get_traslados_activos_count_returns_int(self):
        """get_traslados_activos_count retorna entero."""
        from hubgh.hubgh.page.punto_360.punto_360 import get_traslados_activos_count

        result = get_traslados_activos_count(self.pdv_x)
        self.assertIsInstance(result, int)

    def test_get_traslados_activos_count_counts_origen(self):
        """Cuenta traslados donde el PDV es el origen (salientes)."""
        from hubgh.hubgh.page.punto_360.punto_360 import get_traslados_activos_count

        _make_traslado_sql(self.emp_1, self.pdv_x, self.pdv_y, "Programado")
        _make_traslado_sql(self.emp_2, self.pdv_x, self.pdv_z, "Programado")

        count = get_traslados_activos_count(self.pdv_x)
        self.assertGreaterEqual(count, 2)

    def test_get_traslados_activos_count_counts_destino(self):
        """Cuenta traslados donde el PDV es el destino (entrantes)."""
        from hubgh.hubgh.page.punto_360.punto_360 import get_traslados_activos_count

        _make_traslado_sql(self.emp_3, self.pdv_y, self.pdv_x, "Programado")

        count = get_traslados_activos_count(self.pdv_x)
        self.assertGreaterEqual(count, 1)

    def test_get_traslados_activos_count_combined_origen_destino(self):
        """Cuenta traslados en ambas direcciones correctamente."""
        from hubgh.hubgh.page.punto_360.punto_360 import get_traslados_activos_count

        # 2 salientes + 1 entrante = 3 total para pdv_x
        _make_traslado_sql(self.emp_1, self.pdv_x, self.pdv_y, "Programado")
        _make_traslado_sql(self.emp_2, self.pdv_x, self.pdv_z, "Programado")
        _make_traslado_sql(self.emp_3, self.pdv_y, self.pdv_x, "Programado")

        count = get_traslados_activos_count(self.pdv_x)
        self.assertEqual(count, 3)

    def test_get_traslados_activos_count_ignores_aplicado(self):
        """No cuenta traslados con estado Aplicado."""
        from hubgh.hubgh.page.punto_360.punto_360 import get_traslados_activos_count

        _make_traslado_sql(self.emp_1, self.pdv_x, self.pdv_y, "Aplicado")

        count = get_traslados_activos_count(self.pdv_x)
        self.assertEqual(count, 0)

    def test_get_traslados_activos_count_ignores_anulado(self):
        """No cuenta traslados con estado Anulado."""
        from hubgh.hubgh.page.punto_360.punto_360 import get_traslados_activos_count

        _make_traslado_sql(self.emp_1, self.pdv_x, self.pdv_y, "Anulado")

        count = get_traslados_activos_count(self.pdv_x)
        self.assertEqual(count, 0)

    def test_get_traslados_activos_count_zero_for_unrelated_pdv(self):
        """PDV sin traslados devuelve 0."""
        from hubgh.hubgh.page.punto_360.punto_360 import get_traslados_activos_count

        # pdv_z nunca fue tocado en este test
        count = get_traslados_activos_count(self.pdv_z)
        self.assertEqual(count, 0)
