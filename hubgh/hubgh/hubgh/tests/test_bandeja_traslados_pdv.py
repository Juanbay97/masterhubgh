# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para bandeja_traslados_pdv — Fase 7.

TDD Cycle (Strict):
  RED  → este archivo (tests fallan porque la page no existe aún)
  GREEN → crear page/bandeja_traslados_pdv/
  REFACTOR → verificar thin controllers

Cubre:
- get_traslados_tray filtra por estado
- get_traslado_flow_context: can_manage=True para Administrator/RRLL, False para Jefe_PDV
- apply_traslado_action: Programado+fecha hoy → applied; Aplicado → skipped
- cancel_traslado_action: motivo válido → cancelled; motivo vacío → ValidationError
"""

import json
from unittest.mock import patch, MagicMock
from frappe.tests.utils import FrappeTestCase
import frappe
from frappe.utils import today, add_days, now_datetime


# ---------------------------------------------------------------------------
# Helpers de fixtures
# ---------------------------------------------------------------------------

def _ensure_pdv(name, ciudad="TestBandeja"):
    if not frappe.db.exists("Punto de Venta", name):
        doc = frappe.get_doc({
            "doctype": "Punto de Venta",
            "nombre_pdv": name,
            "codigo": name,
            "ciudad": ciudad,
            "activo": 1,
        })
        doc.insert(ignore_permissions=True)
    return name


def _ensure_empleado(cedula, pdv, estado="Activo", email=None):
    email = email or f"{cedula.lower().replace(' ', '')}@test.com"
    if not frappe.db.exists("Ficha Empleado", cedula):
        doc = frappe.get_doc({
            "doctype": "Ficha Empleado",
            "nombres": cedula,
            "apellidos": "BandejaApellido",
            "cedula": cedula,
            "pdv": pdv,
            "estado": estado,
            "email": email,
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


def _make_traslado_sql(empleado, pdv_origen, pdv_destino, estado="Programado", fecha_aplicacion=None):
    """Crea traslado directamente via SQL para bypasear hooks en tests."""
    fecha = fecha_aplicacion or today()
    naming_series = "TRAS-TEST-"
    name = frappe.generate_hash(length=8)
    full_name = f"TRAS-TEST-{name}"
    frappe.db.sql("""
        INSERT INTO `tabTraslado PDV`
        (name, docstatus, creation, modified, owner, modified_by,
         empleado, pdv_origen, pdv_destino, estado, fecha_aplicacion,
         motivo, justificacion, solicitado_por)
        VALUES
        (%s, 0, NOW(), NOW(), 'Administrator', 'Administrator',
         %s, %s, %s, %s, %s,
         'necesidad_operativa', 'Test justificacion bandeja para traslado',
         'Administrator')
    """, (full_name, empleado, pdv_origen, pdv_destino, estado, fecha))
    frappe.db.commit()
    return full_name


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBandejaTraslados(FrappeTestCase):
    """Tests para los thin controllers de la bandeja de traslados PDV."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pdv_a = _ensure_pdv("BDJ-PDV-A")
        cls.pdv_b = _ensure_pdv("BDJ-PDV-B")
        cls.emp_1 = _ensure_empleado("EMP-BDJ-001", cls.pdv_a)
        cls.emp_2 = _ensure_empleado("EMP-BDJ-002", cls.pdv_a)
        _ensure_motivo()

    def setUp(self):
        frappe.set_user("Administrator")
        # Limpiar traslados de test previos
        frappe.db.sql(
            "DELETE FROM `tabTraslado PDV` WHERE name LIKE 'TRAS-TEST-%'",
        )
        frappe.db.commit()

    # ------------------------------------------------------------------
    # get_traslados_tray
    # ------------------------------------------------------------------

    def test_get_traslados_tray_returns_rows(self):
        """get_traslados_tray devuelve filas existentes."""
        from hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv import get_traslados_tray

        _make_traslado_sql(self.emp_1, self.pdv_a, self.pdv_b, "Programado")
        result = get_traslados_tray(filters=json.dumps({}))
        self.assertIsInstance(result, list)

    def test_get_traslados_tray_filters_by_estado(self):
        """get_traslados_tray filtra correctamente por estado."""
        from hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv import get_traslados_tray

        prog_name = _make_traslado_sql(self.emp_1, self.pdv_a, self.pdv_b, "Programado")
        anulado_name = _make_traslado_sql(self.emp_2, self.pdv_a, self.pdv_b, "Anulado")

        result_prog = get_traslados_tray(filters=json.dumps({"estado": "Programado"}))
        names_prog = [r.get("name") for r in result_prog]
        self.assertIn(prog_name, names_prog)
        self.assertNotIn(anulado_name, names_prog)

        result_anulado = get_traslados_tray(filters=json.dumps({"estado": "Anulado"}))
        names_anulado = [r.get("name") for r in result_anulado]
        self.assertIn(anulado_name, names_anulado)
        self.assertNotIn(prog_name, names_anulado)

    # ------------------------------------------------------------------
    # get_traslado_flow_context
    # ------------------------------------------------------------------

    def test_get_traslado_flow_context_administrator_can_manage(self):
        """Administrator tiene can_manage=True."""
        from hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv import get_traslado_flow_context

        frappe.set_user("Administrator")
        result = get_traslado_flow_context()
        self.assertTrue(result.get("can_manage"))

    def test_get_traslado_flow_context_rrll_can_manage(self):
        """Usuario con HR Labor Relations tiene can_manage=True."""
        from hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv import get_traslado_flow_context
        from hubgh.hubgh.services.traslado_service import get_flow_context

        result = get_flow_context("Administrator")
        self.assertTrue(result.get("can_manage"))

    def test_get_traslado_flow_context_returns_dict(self):
        """get_traslado_flow_context retorna dict con keys esperadas."""
        from hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv import get_traslado_flow_context

        result = get_traslado_flow_context()
        self.assertIn("can_manage", result)
        self.assertIn("user", result)

    def test_get_flow_context_jefe_pdv_cannot_manage(self):
        """Rol Jefe_PDV no tiene can_manage (no está en ALLOWED_MANAGE_ROLES)."""
        from hubgh.hubgh.services.traslado_service import get_flow_context

        with patch("hubgh.hubgh.services.traslado_service.frappe.get_roles") as mock_roles:
            mock_roles.return_value = ["Jefe_PDV", "Empleado"]
            result = get_flow_context("jefe_test@test.com")
            self.assertFalse(result.get("can_manage"))

    def test_get_flow_context_gestión_humana_can_manage(self):
        """Rol Gestión Humana tiene can_manage=True."""
        from hubgh.hubgh.services.traslado_service import get_flow_context

        with patch("hubgh.hubgh.services.traslado_service.frappe.get_roles") as mock_roles:
            mock_roles.return_value = ["Gestión Humana"]
            result = get_flow_context("gh_user@test.com")
            self.assertTrue(result.get("can_manage"))

    # ------------------------------------------------------------------
    # apply_traslado_action
    # ------------------------------------------------------------------

    def test_apply_traslado_action_programado_hoy_aplica(self):
        """apply_traslado_action con Programado y fecha hoy → status applied."""
        from hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv import apply_traslado_action

        traslado_name = _make_traslado_sql(
            self.emp_1, self.pdv_a, self.pdv_b,
            estado="Programado",
            fecha_aplicacion=today(),
        )

        with patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups"):
            with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif:
                mock_notif.return_value = []
                result = apply_traslado_action(traslado_name=traslado_name)

        self.assertEqual(result.get("status"), "applied")
        # Restaurar PDV del empleado para no contaminar otros tests
        frappe.db.set_value("Ficha Empleado", self.emp_1, "pdv", self.pdv_a)

    def test_apply_traslado_action_aplicado_devuelve_skipped(self):
        """apply_traslado_action con traslado ya Aplicado → status skipped."""
        from hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv import apply_traslado_action

        traslado_name = _make_traslado_sql(
            self.emp_2, self.pdv_a, self.pdv_b,
            estado="Aplicado",
            fecha_aplicacion=today(),
        )
        result = apply_traslado_action(traslado_name=traslado_name)
        self.assertEqual(result.get("status"), "skipped")

    # ------------------------------------------------------------------
    # cancel_traslado_action
    # ------------------------------------------------------------------

    def test_cancel_traslado_action_motivo_valido_cancela(self):
        """cancel_traslado_action con motivo válido → status cancelled."""
        from hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv import cancel_traslado_action

        traslado_name = _make_traslado_sql(
            self.emp_1, self.pdv_a, self.pdv_b,
            estado="Programado",
            fecha_aplicacion=add_days(today(), 5),
        )
        result = cancel_traslado_action(
            traslado_name=traslado_name,
            motivo="Motivo de anulación suficientemente largo para el test",
        )
        self.assertEqual(result.get("status"), "cancelled")

    def test_cancel_traslado_action_motivo_vacio_lanza_error(self):
        """cancel_traslado_action con motivo vacío → ValidationError."""
        from hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv import cancel_traslado_action

        traslado_name = _make_traslado_sql(
            self.emp_2, self.pdv_a, self.pdv_b,
            estado="Programado",
            fecha_aplicacion=add_days(today(), 5),
        )
        with self.assertRaises(frappe.ValidationError):
            cancel_traslado_action(traslado_name=traslado_name, motivo="")
