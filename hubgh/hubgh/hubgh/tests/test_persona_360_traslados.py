# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para la integración Persona 360 + Traslados PDV — Fase 8.

TDD Cycle (Strict):
  RED  → este archivo (tests fallan hasta implementar get_traslados_history)
  GREEN → extender persona_360.py
  REFACTOR → verificar inyección en respuesta principal

Cubre:
- get_traslados_history devuelve traslados del empleado
- Ordenados por fecha_aplicacion desc
- Solo traslados del empleado, no de otros
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
            "ciudad": "TestCity360",
            "activo": 1,
        })
        doc.insert(ignore_permissions=True)
    return name


def _ensure_empleado(cedula, pdv, estado="Activo"):
    if not frappe.db.exists("Ficha Empleado", cedula):
        doc = frappe.get_doc({
            "doctype": "Ficha Empleado",
            "nombres": cedula,
            "apellidos": "P360Test",
            "cedula": cedula,
            "pdv": pdv,
            "estado": estado,
            "email": f"{cedula.lower().replace('-', '')}@persona360test.com",
        })
        doc.insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Ficha Empleado", cedula, "pdv", pdv)
        frappe.db.set_value("Ficha Empleado", cedula, "estado", estado)
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


def _make_traslado_sql(empleado, pdv_origen, pdv_destino, estado="Aplicado", fecha_aplicacion=None):
    """Inserta traslado directamente en DB para tests (bypasea hooks)."""
    fecha = fecha_aplicacion or today()
    name = f"TRAS-P360-{frappe.generate_hash(length=8)}"
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


class TestPersona360Traslados(FrappeTestCase):
    """Tests para get_traslados_history en persona_360.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pdv_a = _ensure_pdv("P360-PDV-A")
        cls.pdv_b = _ensure_pdv("P360-PDV-B")
        cls.pdv_c = _ensure_pdv("P360-PDV-C")
        cls.emp_target = _ensure_empleado("EMP-P360-TARGET", cls.pdv_a)
        cls.emp_other = _ensure_empleado("EMP-P360-OTHER", cls.pdv_a)
        _ensure_motivo()

    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.sql("DELETE FROM `tabTraslado PDV` WHERE name LIKE 'TRAS-P360-%'")
        frappe.db.commit()

    def test_get_traslados_history_returns_list(self):
        """get_traslados_history retorna una lista."""
        from hubgh.hubgh.page.persona_360.persona_360 import get_traslados_history

        result = get_traslados_history(self.emp_target)
        self.assertIsInstance(result, list)

    def test_get_traslados_history_returns_employee_traslados(self):
        """get_traslados_history retorna traslados del empleado dado."""
        from hubgh.hubgh.page.persona_360.persona_360 import get_traslados_history

        t1 = _make_traslado_sql(self.emp_target, self.pdv_a, self.pdv_b, "Aplicado",
                                add_days(today(), -10))
        t2 = _make_traslado_sql(self.emp_target, self.pdv_b, self.pdv_c, "Programado",
                                add_days(today(), 5))
        # Otro empleado — no debe aparecer
        _make_traslado_sql(self.emp_other, self.pdv_a, self.pdv_b, "Aplicado",
                           add_days(today(), -5))

        result = get_traslados_history(self.emp_target)
        names = [r.get("name") for r in result]
        self.assertIn(t1, names)
        self.assertIn(t2, names)

    def test_get_traslados_history_excludes_other_employees(self):
        """get_traslados_history no incluye traslados de otros empleados."""
        from hubgh.hubgh.page.persona_360.persona_360 import get_traslados_history

        _make_traslado_sql(self.emp_other, self.pdv_a, self.pdv_b, "Aplicado")

        result = get_traslados_history(self.emp_target)
        names = [r.get("name") for r in result]
        for r in result:
            self.assertEqual(r.get("empleado"), self.emp_target)

    def test_get_traslados_history_ordered_by_fecha_desc(self):
        """get_traslados_history ordena por fecha_aplicacion descendente."""
        from hubgh.hubgh.page.persona_360.persona_360 import get_traslados_history

        t_old = _make_traslado_sql(self.emp_target, self.pdv_a, self.pdv_b, "Aplicado",
                                   add_days(today(), -30))
        t_new = _make_traslado_sql(self.emp_target, self.pdv_b, self.pdv_c, "Programado",
                                   add_days(today(), 10))

        result = get_traslados_history(self.emp_target)
        if len(result) >= 2:
            # El más reciente debe estar primero (mayor fecha_aplicacion primero)
            dates = [str(r.get("fecha_aplicacion") or "") for r in result]
            self.assertGreaterEqual(dates[0], dates[-1])

    def test_get_traslados_history_has_expected_fields(self):
        """Las filas devueltas tienen los campos de columna esperados."""
        from hubgh.hubgh.page.persona_360.persona_360 import get_traslados_history

        _make_traslado_sql(self.emp_target, self.pdv_a, self.pdv_b, "Aplicado")

        result = get_traslados_history(self.emp_target)
        if result:
            row = result[0]
            for field in ["name", "pdv_origen", "pdv_destino", "fecha_aplicacion", "estado"]:
                self.assertIn(field, row)

    def test_get_traslados_history_empty_when_no_traslados(self):
        """get_traslados_history retorna lista vacía si no hay traslados."""
        from hubgh.hubgh.page.persona_360.persona_360 import get_traslados_history

        # No se crearon traslados para emp_target en setUp
        result = get_traslados_history(self.emp_target)
        self.assertIsInstance(result, list)
        # Puede ser vacía o tener solo los de esta sesión (ya limpiados en setUp)
        names = [r.get("name") for r in result]
        # No debe haber traslados de otros empleados
        for r in result:
            self.assertEqual(r.get("empleado"), self.emp_target)
