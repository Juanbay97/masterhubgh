# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for services/notification_resolver.py

TDD Cycle: RED (T-6) → GREEN (I-6) → TRIANGULATE → REFACTOR

Tests:
- resolve_jefe_pdv: campo directo, fallback rol+pdv, None cuando ambos fallan
- resolve_employee_email: happy path (Ficha Empleado.email), fallback User
- resolve_role_subscribers: retorna lista de emails por rol
"""

from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase
import frappe


MODULE = "hubgh.hubgh.services.notification_resolver"


class TestResolveJefePDV(FrappeTestCase):

    def test_uses_jefe_responsable_field_when_set(self):
        """Debe retornar el valor de Punto de Venta.jefe_responsable cuando existe."""
        from hubgh.hubgh.services.notification_resolver import resolve_jefe_pdv

        with patch(f"{MODULE}.frappe.db.get_value", return_value="jefe@test.com"), \
             patch(f"{MODULE}.frappe.db.exists", return_value=True):
            result = resolve_jefe_pdv("PDV-TEST-001")

        self.assertEqual(result, "jefe@test.com")

    def test_falls_back_to_role_intersection_when_field_empty(self):
        """Cuando jefe_responsable es None, debe hacer fallback al query SQL."""
        from hubgh.hubgh.services.notification_resolver import resolve_jefe_pdv

        def fake_get_value(doctype, name, fieldname):
            if fieldname == "jefe_responsable":
                return None  # campo vacío
            return None

        # Primera llamada: usuarios con Jefe_PDV; segunda: Ficha Empleado en PDV
        sql_responses = [
            [{"user": "jefe_fallback@test.com", "email": "jefe_fallback@test.com", "modified": "2026-01-01"}],
            [{"email": "jefe_fallback@test.com"}],
        ]
        sql_call_count = {"n": 0}

        def fake_sql(query, *args, **kwargs):
            idx = sql_call_count["n"]
            sql_call_count["n"] += 1
            return sql_responses[idx] if idx < len(sql_responses) else []

        with patch(f"{MODULE}.frappe.db.get_value", side_effect=fake_get_value), \
             patch(f"{MODULE}.frappe.db.sql", side_effect=fake_sql):
            result = resolve_jefe_pdv("PDV-TEST-001")

        self.assertEqual(result, "jefe_fallback@test.com")

    def test_returns_none_when_both_strategies_fail(self):
        """Retorna None cuando ni campo directo ni fallback encuentran jefe."""
        from hubgh.hubgh.services.notification_resolver import resolve_jefe_pdv

        def fake_get_value(doctype, name, fieldname):
            return None

        # Primera SQL devuelve lista vacía de jefes → no hay candidatos
        sql_mock = MagicMock(return_value=[])

        with patch(f"{MODULE}.frappe.db.get_value", side_effect=fake_get_value), \
             patch(f"{MODULE}.frappe.db.sql", sql_mock):
            result = resolve_jefe_pdv("PDV-EMPTY")

        self.assertIsNone(result)

    def test_returns_none_for_empty_pdv_name(self):
        """Retorna None inmediatamente si pdv_name es None o vacío."""
        from hubgh.hubgh.services.notification_resolver import resolve_jefe_pdv

        with patch(f"{MODULE}.frappe.db.get_value") as get_val_mock:
            self.assertIsNone(resolve_jefe_pdv(None))
            self.assertIsNone(resolve_jefe_pdv(""))
            get_val_mock.assert_not_called()

    def test_validates_user_exists_before_returning(self):
        """Si jefe_responsable tiene valor pero el User no existe, hace fallback."""
        from hubgh.hubgh.services.notification_resolver import resolve_jefe_pdv

        def fake_get_value(doctype, name, fieldname):
            return "jefe_fantasma@test.com"  # User no existe

        def fake_exists(doctype, name):
            return False  # User no encontrado

        # Fallback retorna un candidato válido
        sql_responses = [
            [{"user": "jefe_fallback@test.com", "email": "jefe_fallback@test.com", "modified": "2026-01-01"}],
            [{"email": "jefe_fallback@test.com"}],
        ]
        sql_call_count = {"n": 0}

        def fake_sql(query, *args, **kwargs):
            idx = sql_call_count["n"]
            sql_call_count["n"] += 1
            return sql_responses[idx] if idx < len(sql_responses) else []

        with patch(f"{MODULE}.frappe.db.get_value", side_effect=fake_get_value), \
             patch(f"{MODULE}.frappe.db.exists", side_effect=fake_exists), \
             patch(f"{MODULE}.frappe.db.sql", side_effect=fake_sql):
            result = resolve_jefe_pdv("PDV-TEST-001")

        # Debe hacer fallback porque el User no existe
        self.assertEqual(result, "jefe_fallback@test.com")


class TestResolveEmployeeEmail(FrappeTestCase):

    def test_returns_ficha_empleado_email_when_set(self):
        """Debe retornar Ficha Empleado.email cuando el campo tiene valor."""
        from hubgh.hubgh.services.notification_resolver import resolve_employee_email

        with patch(f"{MODULE}.frappe.db.get_value", return_value="empleado@test.com"):
            result = resolve_employee_email("EMP-001")

        self.assertEqual(result, "empleado@test.com")

    def test_fallback_to_user_when_ficha_email_empty(self):
        """Cuando Ficha Empleado.email está vacío, usa User.email vía resolve_user_for_employee."""
        from hubgh.hubgh.services.notification_resolver import resolve_employee_email

        identity_mock = MagicMock()
        identity_mock.user = "user@test.com"

        def fake_get_value(doctype, name, fieldname):
            if doctype == "Ficha Empleado":
                return None
            if doctype == "User":
                return "user@test.com"
            return None

        with patch(f"{MODULE}.frappe.db.get_value", side_effect=fake_get_value), \
             patch(f"{MODULE}.resolve_user_for_employee", return_value=identity_mock):
            result = resolve_employee_email("EMP-001")

        self.assertEqual(result, "user@test.com")

    def test_returns_none_for_empty_employee(self):
        """Retorna None si employee es None o vacío."""
        from hubgh.hubgh.services.notification_resolver import resolve_employee_email

        with patch(f"{MODULE}.frappe.db.get_value") as gv_mock:
            self.assertIsNone(resolve_employee_email(None))
            self.assertIsNone(resolve_employee_email(""))
            gv_mock.assert_not_called()

    def test_returns_none_when_both_sources_fail(self):
        """Retorna None cuando ni Ficha Empleado.email ni User tienen email."""
        from hubgh.hubgh.services.notification_resolver import resolve_employee_email

        with patch(f"{MODULE}.frappe.db.get_value", return_value=None), \
             patch(f"{MODULE}.resolve_user_for_employee", return_value=None):
            result = resolve_employee_email("EMP-999")

        self.assertIsNone(result)

    # TRIANGULATE: fallback retorna user name si User.email también está vacío
    def test_fallback_returns_user_name_if_email_blank(self):
        """Si User.email está vacío, retorna el user name (que es el email en Frappe)."""
        from hubgh.hubgh.services.notification_resolver import resolve_employee_email

        identity_mock = MagicMock()
        identity_mock.user = "username_as_email@domain.com"

        def fake_get_value(doctype, name, fieldname):
            if doctype == "Ficha Empleado":
                return None
            if doctype == "User":
                return ""  # email vacío
            return None

        with patch(f"{MODULE}.frappe.db.get_value", side_effect=fake_get_value), \
             patch(f"{MODULE}.resolve_user_for_employee", return_value=identity_mock):
            result = resolve_employee_email("EMP-001")

        # Debe retornar el user name cuando email está vacío
        self.assertEqual(result, "username_as_email@domain.com")


class TestResolveRoleSubscribers(FrappeTestCase):

    def test_returns_emails_for_role(self):
        """resolve_role_subscribers retorna lista de emails para el rol dado."""
        from hubgh.hubgh.services.notification_resolver import resolve_role_subscribers

        rows = [{"email": "a@test.com"}, {"email": "b@test.com"}]
        sql_mock = MagicMock(return_value=rows)

        with patch(f"{MODULE}.frappe.db.sql", sql_mock):
            result = resolve_role_subscribers("Gestión Humana")

        self.assertIn("a@test.com", result)
        self.assertIn("b@test.com", result)
        sql_mock.assert_called_once()

    def test_returns_empty_list_for_role_with_no_users(self):
        """Retorna lista vacía cuando no hay usuarios con ese rol."""
        from hubgh.hubgh.services.notification_resolver import resolve_role_subscribers

        with patch(f"{MODULE}.frappe.db.sql", MagicMock(return_value=[])):
            result = resolve_role_subscribers("Rol Inexistente")

        self.assertEqual(result, [])

    def test_deduplicates_emails(self):
        """Deduplica emails si hay duplicados en el resultado SQL."""
        from hubgh.hubgh.services.notification_resolver import resolve_role_subscribers

        rows = [{"email": "a@test.com"}, {"email": "a@test.com"}, {"email": "b@test.com"}]
        sql_mock = MagicMock(return_value=rows)

        with patch(f"{MODULE}.frappe.db.sql", sql_mock):
            result = resolve_role_subscribers("SomeRole")

        self.assertEqual(len(result), len(set(result)), "No debe haber emails duplicados")
