# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for notification_resolver.resolve_area_subscribers — Batch B.7 (TDD RED → GREEN)

Covers:
  T-B.7a  Area con suscriptores de tipo 'user' → retorna email del user
  T-B.7b  Area con suscriptores de tipo 'role' → expande rol a múltiples users
  T-B.7c  Area con suscriptores de tipo 'email_fijo' → agrega email literal
  T-B.7d  Area inexistente → lista vacía
  T-B.7e  Suscriptores con activo=0 → excluidos de la lista
"""

from unittest.mock import patch, MagicMock
from frappe.tests.utils import FrappeTestCase
import frappe


# ---------------------------------------------------------------------------
# Module under test
# ---------------------------------------------------------------------------

from hubgh.hubgh.services.notification_resolver import resolve_area_subscribers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_subscriber(area="sistemas", user=None, role=None, email_fijo=None, activo=1):
    row = MagicMock()
    row.area = area
    row.user = user
    row.role = role
    row.email_fijo = email_fijo
    row.activo = activo
    return row


def _make_config_doc(subscribers):
    doc = MagicMock()
    doc.suscriptores_por_area = subscribers
    return doc


# ---------------------------------------------------------------------------
# T-B.7a — area con suscriptores de tipo 'user'
# ---------------------------------------------------------------------------

class TestResolveAreaSubscribersUser(FrappeTestCase):

    def test_user_subscriber_returns_email(self):
        """Suscriptor tipo user → retorna email del User."""
        sub = _make_subscriber(area="sistemas", user="admin@hubgh.com")
        config = _make_config_doc([sub])

        def _get_doc_side(doctype, name=None):
            if doctype == "Configuracion Terminacion":
                return config
            return MagicMock()

        with patch("hubgh.hubgh.services.notification_resolver.frappe.get_single", return_value=config), \
             patch("hubgh.hubgh.services.notification_resolver.frappe.db.get_value", return_value="admin@hubgh.com"):
            result = resolve_area_subscribers("sistemas")

        self.assertIn("admin@hubgh.com", result)

    def test_user_subscriber_deduped(self):
        """Suscriptores duplicados deben retornar una sola entrada."""
        sub1 = _make_subscriber(area="sistemas", user="user@hubgh.com")
        sub2 = _make_subscriber(area="sistemas", user="user@hubgh.com")
        config = _make_config_doc([sub1, sub2])

        with patch("hubgh.hubgh.services.notification_resolver.frappe.get_single", return_value=config), \
             patch("hubgh.hubgh.services.notification_resolver.frappe.db.get_value", return_value="user@hubgh.com"):
            result = resolve_area_subscribers("sistemas")

        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# T-B.7b — area con suscriptores de tipo 'role'
# ---------------------------------------------------------------------------

class TestResolveAreaSubscribersRole(FrappeTestCase):

    def test_role_subscriber_expands_to_user_emails(self):
        """Suscriptor tipo role → expande a emails de todos los users con ese rol."""
        sub = _make_subscriber(area="rrll_dotacion", role="GH-RRLL")
        config = _make_config_doc([sub])

        # resolve_role_subscribers retorna lista de emails
        with patch("hubgh.hubgh.services.notification_resolver.frappe.get_single", return_value=config), \
             patch("hubgh.hubgh.services.notification_resolver.resolve_role_subscribers",
                   return_value=["rrll1@hubgh.com", "rrll2@hubgh.com"]):
            result = resolve_area_subscribers("rrll_dotacion")

        self.assertIn("rrll1@hubgh.com", result)
        self.assertIn("rrll2@hubgh.com", result)
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# T-B.7c — area con email_fijo
# ---------------------------------------------------------------------------

class TestResolveAreaSubscribersEmailFijo(FrappeTestCase):

    def test_email_fijo_added_directly(self):
        """Suscriptor tipo email_fijo → agrega el email literal sin lookup."""
        sub = _make_subscriber(area="compensacion", email_fijo="liquidacion@empresa.com")
        config = _make_config_doc([sub])

        with patch("hubgh.hubgh.services.notification_resolver.frappe.get_single", return_value=config):
            result = resolve_area_subscribers("compensacion")

        self.assertIn("liquidacion@empresa.com", result)


# ---------------------------------------------------------------------------
# T-B.7d — area inexistente → lista vacía
# ---------------------------------------------------------------------------

class TestResolveAreaSubscribersNoArea(FrappeTestCase):

    def test_unknown_area_returns_empty(self):
        """Area sin suscriptores configurados retorna lista vacía."""
        sub = _make_subscriber(area="sistemas", user="admin@test.com")
        config = _make_config_doc([sub])

        with patch("hubgh.hubgh.services.notification_resolver.frappe.get_single", return_value=config), \
             patch("hubgh.hubgh.services.notification_resolver.frappe.db.get_value", return_value="admin@test.com"):
            result = resolve_area_subscribers("area_inexistente")

        self.assertEqual(result, [])

    def test_config_not_found_returns_empty(self):
        """Si Configuracion Terminacion lanza DoesNotExist → retorna lista vacía."""
        with patch("hubgh.hubgh.services.notification_resolver.frappe.get_single",
                   side_effect=frappe.DoesNotExistError("Configuracion Terminacion")):
            result = resolve_area_subscribers("sistemas")

        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# T-B.7e — activo=0 excluido
# ---------------------------------------------------------------------------

class TestResolveAreaSubscribersInactivo(FrappeTestCase):

    def test_inactive_subscriber_excluded(self):
        """Suscriptor con activo=0 no aparece en resultado."""
        sub_activo = _make_subscriber(area="sst", user="sst@hubgh.com", activo=1)
        sub_inactivo = _make_subscriber(area="sst", user="old@hubgh.com", activo=0)
        config = _make_config_doc([sub_activo, sub_inactivo])

        def _get_value_side(doctype, name, field):
            if name == "sst@hubgh.com":
                return "sst@hubgh.com"
            if name == "old@hubgh.com":
                return "old@hubgh.com"
            return None

        with patch("hubgh.hubgh.services.notification_resolver.frappe.get_single", return_value=config), \
             patch("hubgh.hubgh.services.notification_resolver.frappe.db.get_value", side_effect=_get_value_side):
            result = resolve_area_subscribers("sst")

        self.assertIn("sst@hubgh.com", result)
        self.assertNotIn("old@hubgh.com", result)
