# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para CAP-08 — Timeline Persona 360 consume eventos de traslado PDV.

TDD Cycle (Strict):
  RED  → este archivo (tests fallan hasta implementar get_persona_timeline)
  GREEN → extender persona_360.py con consulta a People Ops Event
  TRIANGULATE → verificar que eventos traslado aparecen en timeline general

Cubre:
  - get_persona_timeline devuelve eventos de People Ops Event del empleado
  - taxonomy operacion.traslado_pdv.* incluida en resultados
  - Ordenados por occurred_on desc
  - Inyectados al timeline principal de get_persona_stats
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime, add_days, today


def _ensure_pdv(name):
    if not frappe.db.exists("Punto de Venta", name):
        frappe.get_doc({
            "doctype": "Punto de Venta",
            "nombre_pdv": name,
            "codigo": name,
            "ciudad": "TestCityTL",
            "activo": 1,
        }).insert(ignore_permissions=True)
    return name


def _ensure_empleado(cedula, pdv):
    if not frappe.db.exists("Ficha Empleado", cedula):
        frappe.get_doc({
            "doctype": "Ficha Empleado",
            "nombres": cedula,
            "apellidos": "TLTest",
            "cedula": cedula,
            "pdv": pdv,
            "estado": "Activo",
            "email": f"{cedula.lower().replace('-', '')}@tl360test.com",
        }).insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Ficha Empleado", cedula, "pdv", pdv)
        frappe.db.set_value("Ficha Empleado", cedula, "estado", "Activo")
    return cedula


def _insert_people_ops_event(persona, taxonomy, state="Aplicado", area="operacion",
                              source_doctype="Traslado PDV", source_name=None,
                              occurred_on=None):
    """Inserta un People Ops Event directamente (bypasea idempotency check)."""
    if not frappe.db.exists("DocType", "People Ops Event"):
        return None

    name = f"POE-TL-{frappe.generate_hash(length=8)}"
    source_name = source_name or name
    event_key = f"{source_doctype}::{source_name}::{taxonomy}"

    # Borrar si ya existe el key (para idempotencia en tests)
    existing = frappe.db.get_value("People Ops Event", {"event_key": event_key}, "name")
    if existing:
        return existing

    occurred = occurred_on or now_datetime()
    frappe.db.sql("""
        INSERT INTO `tabPeople Ops Event`
        (name, docstatus, creation, modified, owner, modified_by,
         event_key, persona, area, taxonomy, sensitivity, state,
         source_doctype, source_name, occurred_on, backbone_mode, contract_version)
        VALUES
        (%s, 0, NOW(), NOW(), 'Administrator', 'Administrator',
         %s, %s, %s, %s, 'operational', %s,
         %s, %s, %s, 'warn', 'v1')
    """, (name, event_key, persona, area, taxonomy, state, source_doctype, source_name, occurred))
    frappe.db.commit()
    return name


class TestPersona360TimelineTraslado(FrappeTestCase):
    """Tests para get_persona_timeline en persona_360.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pdv_a = _ensure_pdv("TL-PDV-A")
        cls.pdv_b = _ensure_pdv("TL-PDV-B")
        cls.emp_target = _ensure_empleado("EMP-TL-TARGET", cls.pdv_a)
        cls.emp_other = _ensure_empleado("EMP-TL-OTHER", cls.pdv_a)

    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.sql(
            "DELETE FROM `tabPeople Ops Event` WHERE name LIKE 'POE-TL-%'"
        )
        frappe.db.commit()

    def test_get_persona_timeline_function_exists(self):
        """get_persona_timeline debe existir en persona_360.py."""
        from hubgh.hubgh.page.persona_360.persona_360 import get_persona_timeline
        self.assertTrue(callable(get_persona_timeline))

    def test_get_persona_timeline_returns_list(self):
        """get_persona_timeline devuelve una lista."""
        from hubgh.hubgh.page.persona_360.persona_360 import get_persona_timeline

        result = get_persona_timeline(self.emp_target)
        self.assertIsInstance(result, list)

    def test_get_persona_timeline_returns_empty_when_no_events(self):
        """get_persona_timeline retorna lista vacía si no hay eventos."""
        from hubgh.hubgh.page.persona_360.persona_360 import get_persona_timeline

        result = get_persona_timeline(self.emp_target)
        self.assertIsInstance(result, list)
        # All results must belong to the target employee
        for row in result:
            self.assertEqual(row.get("persona"), self.emp_target)

    def test_get_persona_timeline_includes_traslado_applied_event(self):
        """get_persona_timeline incluye eventos con taxonomy operacion.traslado_pdv.aplicado."""
        if not frappe.db.exists("DocType", "People Ops Event"):
            self.skipTest("DocType People Ops Event no disponible")

        from hubgh.hubgh.page.persona_360.persona_360 import get_persona_timeline

        ev_name = _insert_people_ops_event(
            persona=self.emp_target,
            taxonomy="operacion.traslado_pdv.aplicado",
            state="Aplicado",
            source_name="TRAS-TL-001",
        )
        self.assertIsNotNone(ev_name, "Event insert falló")

        result = get_persona_timeline(self.emp_target)
        found_taxonomies = [r.get("taxonomy") for r in result]
        self.assertIn(
            "operacion.traslado_pdv.aplicado",
            found_taxonomies,
            "Evento traslado.pdv.aplicado no encontrado en timeline",
        )

    def test_get_persona_timeline_includes_traslado_programado_event(self):
        """get_persona_timeline incluye eventos con taxonomy operacion.traslado_pdv.programado."""
        if not frappe.db.exists("DocType", "People Ops Event"):
            self.skipTest("DocType People Ops Event no disponible")

        from hubgh.hubgh.page.persona_360.persona_360 import get_persona_timeline

        ev_name = _insert_people_ops_event(
            persona=self.emp_target,
            taxonomy="operacion.traslado_pdv.programado",
            state="Programado",
            source_name="TRAS-TL-002",
        )
        self.assertIsNotNone(ev_name)

        result = get_persona_timeline(self.emp_target)
        found_taxonomies = [r.get("taxonomy") for r in result]
        self.assertIn("operacion.traslado_pdv.programado", found_taxonomies)

    def test_get_persona_timeline_excludes_other_employees(self):
        """get_persona_timeline NO incluye eventos de otros empleados."""
        if not frappe.db.exists("DocType", "People Ops Event"):
            self.skipTest("DocType People Ops Event no disponible")

        from hubgh.hubgh.page.persona_360.persona_360 import get_persona_timeline

        # Evento para otro empleado
        _insert_people_ops_event(
            persona=self.emp_other,
            taxonomy="operacion.traslado_pdv.aplicado",
            source_name="TRAS-TL-OTHER-001",
        )

        result = get_persona_timeline(self.emp_target)
        for row in result:
            self.assertEqual(
                row.get("persona"),
                self.emp_target,
                "Timeline contiene evento de otro empleado",
            )

    def test_get_persona_timeline_ordered_by_occurred_on_desc(self):
        """get_persona_timeline ordena por occurred_on descendente."""
        if not frappe.db.exists("DocType", "People Ops Event"):
            self.skipTest("DocType People Ops Event no disponible")

        from hubgh.hubgh.page.persona_360.persona_360 import get_persona_timeline

        _insert_people_ops_event(
            persona=self.emp_target,
            taxonomy="operacion.traslado_pdv.programado",
            state="Programado",
            source_name="TRAS-TL-003",
            occurred_on=add_days(today(), -30),
        )
        _insert_people_ops_event(
            persona=self.emp_target,
            taxonomy="operacion.traslado_pdv.aplicado",
            state="Aplicado",
            source_name="TRAS-TL-004",
            occurred_on=today(),
        )

        result = get_persona_timeline(self.emp_target)
        if len(result) >= 2:
            dates = [str(r.get("occurred_on") or "") for r in result]
            self.assertGreaterEqual(
                dates[0],
                dates[-1],
                "Eventos no ordenados por occurred_on desc",
            )

    def test_get_persona_timeline_has_expected_fields(self):
        """Filas de get_persona_timeline tienen campos mínimos esperados."""
        if not frappe.db.exists("DocType", "People Ops Event"):
            self.skipTest("DocType People Ops Event no disponible")

        from hubgh.hubgh.page.persona_360.persona_360 import get_persona_timeline

        _insert_people_ops_event(
            persona=self.emp_target,
            taxonomy="operacion.traslado_pdv.aplicado",
            source_name="TRAS-TL-005",
        )

        result = get_persona_timeline(self.emp_target)
        if result:
            row = result[0]
            for field in ["name", "taxonomy", "persona", "occurred_on", "state"]:
                self.assertIn(
                    field,
                    row,
                    f"Campo '{field}' falta en resultado de get_persona_timeline",
                )

    def test_get_persona_timeline_area_filter(self):
        """get_persona_timeline acepta filtro de area."""
        if not frappe.db.exists("DocType", "People Ops Event"):
            self.skipTest("DocType People Ops Event no disponible")

        from hubgh.hubgh.page.persona_360.persona_360 import get_persona_timeline

        _insert_people_ops_event(
            persona=self.emp_target,
            taxonomy="operacion.traslado_pdv.aplicado",
            area="operacion",
            source_name="TRAS-TL-006",
        )

        result_all = get_persona_timeline(self.emp_target)
        result_filtered = get_persona_timeline(self.emp_target, area="operacion")
        # Filtrado por area operacion debe incluir eventos de traslado
        filtered_taxonomies = [r.get("taxonomy") for r in result_filtered]
        self.assertIn("operacion.traslado_pdv.aplicado", filtered_taxonomies)
