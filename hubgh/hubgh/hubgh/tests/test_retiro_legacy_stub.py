# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for hubgh.hubgh.services.retiro_legacy_stub

TDD Batch A — Phase 1 (PR-1)
Strict TDD: these tests were written BEFORE the production module exists.
"""

from unittest.mock import call, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.services.retiro_legacy_stub import (
    apply_retirement_stub,
    reverse_retirement_if_clear_stub,
)


class TestApplyRetirementStub(FrappeTestCase):
    # -------------------------------------------------------------------------
    # T-1.1-a: apply stub does NOT mutate User.enabled
    # -------------------------------------------------------------------------
    def test_apply_stub_no_muta_user_enabled(self):
        """
        User.enabled must NOT be written by the stub at all.
        Verifica que frappe.db.set_value nunca es llamado con 'User' como doctype.
        """
        with patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.exists",
            return_value=True,
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.set_value",
        ) as set_value_mock, patch(
            "hubgh.hubgh.services.retiro_legacy_stub.resolve_role_subscribers",
            return_value=["rrll@example.com"],
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.dispatch_email",
            return_value={"status": "ok"},
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.log_error",
        ):
            apply_retirement_stub(
                empleado="EMP-001",
                source_doctype="Novedad SST",
                source_name="NSST-2026-001",
            )

        # Ninguna llamada a set_value debe tener "User" como primer argumento
        for call_args in set_value_mock.call_args_list:
            args = call_args[0] if call_args[0] else []
            self.assertNotEqual(
                args[0] if args else None,
                "User",
                "stub NO debe mutar User.enabled",
            )

    # -------------------------------------------------------------------------
    # T-1.1-b: apply stub does NOT create Payroll Liquidation Case
    # -------------------------------------------------------------------------
    def test_apply_stub_no_crea_payroll_liquidation_case(self):
        """
        frappe.get_doc nunca debe ser llamado con 'Payroll Liquidation Case'.
        """
        with patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.exists",
            return_value=True,
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.set_value",
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.resolve_role_subscribers",
            return_value=["rrll@example.com"],
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.dispatch_email",
            return_value={"status": "ok"},
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.log_error",
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.get_doc",
        ) as get_doc_mock:
            apply_retirement_stub(
                empleado="EMP-001",
                source_doctype="Novedad SST",
                source_name="NSST-2026-001",
            )

        for call_args in get_doc_mock.call_args_list:
            args = call_args[0] if call_args[0] else []
            self.assertNotEqual(
                args[0] if args else None,
                "Payroll Liquidation Case",
                "stub NO debe crear Payroll Liquidation Case",
            )

    # -------------------------------------------------------------------------
    # T-1.1-c: apply stub sets tracking fields on Ficha Empleado
    # -------------------------------------------------------------------------
    def test_apply_stub_setea_tracking_fields(self):
        """
        frappe.db.set_value debe ser llamado con 'Ficha Empleado' + los 2 tracking fields.
        """
        with patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.exists",
            return_value=True,
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.set_value",
        ) as set_value_mock, patch(
            "hubgh.hubgh.services.retiro_legacy_stub.resolve_role_subscribers",
            return_value=["rrll@example.com"],
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.dispatch_email",
            return_value={"status": "ok"},
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.log_error",
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.now_datetime",
            return_value="2026-05-21 10:00:00",
        ):
            apply_retirement_stub(
                empleado="EMP-001",
                source_doctype="Novedad SST",
                source_name="NSST-2026-001",
            )

        # set_value debe haber sido llamado con Ficha Empleado + diccionario de campos
        set_value_mock.assert_called_once_with(
            "Ficha Empleado",
            "EMP-001",
            {
                "last_retirement_attempt_at": "2026-05-21 10:00:00",
                "last_retirement_attempt_source": "Novedad SST:NSST-2026-001",
            },
            update_modified=False,
        )

    # -------------------------------------------------------------------------
    # T-1.1-d: apply stub dispatches email to resolved role recipients
    # -------------------------------------------------------------------------
    def test_apply_stub_dispatch_email_a_rol(self):
        """
        dispatch_email debe ser invocado con los recipients del rol HR Labor Relations.
        """
        with patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.exists",
            return_value=True,
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.set_value",
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.resolve_role_subscribers",
            return_value=["rrll1@example.com", "rrll2@example.com"],
        ) as resolve_mock, patch(
            "hubgh.hubgh.services.retiro_legacy_stub.dispatch_email",
            return_value={"status": "ok"},
        ) as dispatch_mock, patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.log_error",
        ):
            apply_retirement_stub(
                empleado="EMP-001",
                source_doctype="Caso Disciplinario",
                source_name="DIS-001",
            )

        resolve_mock.assert_called_once_with("HR Labor Relations")
        dispatch_mock.assert_called_once()
        call_kwargs = dispatch_mock.call_args
        recipients_used = call_kwargs[0][1] if call_kwargs[0] else call_kwargs[1].get("recipients")
        self.assertIn("rrll1@example.com", recipients_used)
        self.assertIn("rrll2@example.com", recipients_used)

    # -------------------------------------------------------------------------
    # T-1.1-e: apply stub falls back to frappe.conf when role returns empty
    # -------------------------------------------------------------------------
    def test_apply_stub_fallback_a_site_config(self):
        """
        Cuando resolve_role_subscribers retorna [], se usan los emails de frappe.conf.
        Reemplaza _get_fallback_conf en el módulo para aislar la dependencia.
        """
        with patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.exists",
            return_value=True,
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.set_value",
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.resolve_role_subscribers",
            return_value=[],
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub._get_fallback_emails",
            return_value=["fallback@example.com"],
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.dispatch_email",
            return_value={"status": "ok"},
        ) as dispatch_mock, patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.log_error",
        ):
            result = apply_retirement_stub(
                empleado="EMP-001",
                source_doctype="Novedad SST",
                source_name="NSST-001",
            )

        dispatch_mock.assert_called_once()
        call_kwargs = dispatch_mock.call_args
        recipients_used = call_kwargs[0][1] if call_kwargs[0] else call_kwargs[1].get("recipients")
        self.assertIn("fallback@example.com", recipients_used)
        self.assertEqual(result["status"], "skipped_gap")

    # -------------------------------------------------------------------------
    # T-1.1-f: apply stub does not crash when no recipients at all
    # -------------------------------------------------------------------------
    def test_apply_stub_no_crashea_sin_destinatarios(self):
        """
        Con ambos vacíos (rol y site_config), stub retorna OK y llama log_error.
        """
        with patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.exists",
            return_value=True,
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.set_value",
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.resolve_role_subscribers",
            return_value=[],
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub._get_fallback_emails",
            return_value=[],
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.dispatch_email",
        ) as dispatch_mock, patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.log_error",
        ) as log_error_mock:
            result = apply_retirement_stub(
                empleado="EMP-001",
                source_doctype="Novedad SST",
                source_name="NSST-001",
            )

        dispatch_mock.assert_not_called()
        log_error_mock.assert_called()
        self.assertEqual(result["status"], "skipped_gap")

    # -------------------------------------------------------------------------
    # T-1.1-g: apply stub returns empleado_no_encontrado when Ficha doesn't exist
    # -------------------------------------------------------------------------
    def test_apply_stub_empleado_no_existe(self):
        """
        Cuando la Ficha Empleado no existe, retorna skipped_gap/empleado_no_encontrado.
        set_value no debe ser llamado.
        """
        with patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.exists",
            return_value=False,
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.set_value",
        ) as set_value_mock, patch(
            "hubgh.hubgh.services.retiro_legacy_stub.resolve_role_subscribers",
            return_value=["rrll@example.com"],
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.dispatch_email",
            return_value={"status": "ok"},
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.log_error",
        ):
            result = apply_retirement_stub(
                empleado="EMP-FANTASMA",
                source_doctype="Novedad SST",
                source_name="NSST-001",
            )

        self.assertEqual(result["status"], "skipped_gap")
        self.assertEqual(result["reason"], "empleado_no_encontrado")
        set_value_mock.assert_not_called()

    # -------------------------------------------------------------------------
    # T-1.1 return value contract
    # -------------------------------------------------------------------------
    def test_apply_stub_retorna_contrato_awaiting_c3(self):
        """Triangulation: retorna {"status": "skipped_gap", "reason": "awaiting_c3"}."""
        with patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.exists",
            return_value=True,
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.set_value",
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.resolve_role_subscribers",
            return_value=["rrll@example.com"],
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.dispatch_email",
            return_value={"status": "ok"},
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.log_error",
        ):
            result = apply_retirement_stub(
                empleado="EMP-001",
                source_doctype="Novedad SST",
                source_name="NSST-001",
            )

        self.assertEqual(result["status"], "skipped_gap")
        self.assertEqual(result["reason"], "awaiting_c3")


class TestReverseRetirementStub(FrappeTestCase):
    # -------------------------------------------------------------------------
    # T-1.1-h: reverse stub sets source with "reverse:" prefix
    # -------------------------------------------------------------------------
    def test_reverse_stub_setea_source_con_prefijo_reverse(self):
        """
        reverse stub setea last_retirement_attempt_source con "source_doctype:reverse:source_name".
        """
        with patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.exists",
            return_value=True,
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.set_value",
        ) as set_value_mock, patch(
            "hubgh.hubgh.services.retiro_legacy_stub.resolve_role_subscribers",
            return_value=["rrll@example.com"],
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.dispatch_email",
            return_value={"status": "ok"},
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.log_error",
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.now_datetime",
            return_value="2026-05-21 10:00:00",
        ):
            reverse_retirement_if_clear_stub(
                empleado="EMP-001",
                source_doctype="Novedad SST",
                source_name="NSST-2026-001",
            )

        set_value_mock.assert_called_once()
        call_args = set_value_mock.call_args[0]
        fields_dict = call_args[2]
        self.assertIn("reverse:", fields_dict.get("last_retirement_attempt_source", ""))

    # -------------------------------------------------------------------------
    # T-1.1-i: reverse stub dispatches email with is_reverse=True in context
    # -------------------------------------------------------------------------
    def test_reverse_stub_dispatch_con_is_reverse_true(self):
        """
        dispatch_email debe recibir context con is_reverse=True para reverse stub.
        """
        with patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.exists",
            return_value=True,
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.db.set_value",
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.resolve_role_subscribers",
            return_value=["rrll@example.com"],
        ), patch(
            "hubgh.hubgh.services.retiro_legacy_stub.dispatch_email",
            return_value={"status": "ok"},
        ) as dispatch_mock, patch(
            "hubgh.hubgh.services.retiro_legacy_stub.frappe.log_error",
        ):
            reverse_retirement_if_clear_stub(
                empleado="EMP-001",
                source_doctype="Novedad SST",
                source_name="NSST-2026-001",
            )

        dispatch_mock.assert_called_once()
        context_arg = dispatch_mock.call_args[0][2]
        self.assertTrue(context_arg.get("is_reverse"), "context debe tener is_reverse=True")


class TestEmailTemplateExistence(FrappeTestCase):
    # -------------------------------------------------------------------------
    # T-1.2: Email Template retiro_legacy_stub_alerta exists (post-patch)
    # -------------------------------------------------------------------------
    def test_email_template_retiro_legacy_stub_alerta_existe(self):
        """
        El Email Template 'retiro_legacy_stub_alerta' debe existir en DB.
        Requiere que el patch cleanup_retiro_legacy_v1 haya corrido.
        """
        exists = frappe.db.exists("Email Template", "retiro_legacy_stub_alerta")
        self.assertTrue(
            exists,
            "Email Template 'retiro_legacy_stub_alerta' debe existir post-patch",
        )

    def test_email_template_subject_contiene_gap_c3(self):
        """
        El subject del template debe contener '[GAP C3]'.
        """
        if not frappe.db.exists("Email Template", "retiro_legacy_stub_alerta"):
            self.skipTest("Template ausente — patch no ejecutado")

        template = frappe.get_doc("Email Template", "retiro_legacy_stub_alerta")
        self.assertIn("[GAP C3]", template.subject)

    def test_email_template_body_cambia_con_is_reverse(self):
        """
        El body renderizado debe contener texto diferente cuando is_reverse=True.
        Verifica que el template tiene lógica condicional para reversión.
        """
        if not frappe.db.exists("Email Template", "retiro_legacy_stub_alerta"):
            self.skipTest("Template ausente — patch no ejecutado")

        from frappe.utils.jinja import render_template

        template = frappe.get_doc("Email Template", "retiro_legacy_stub_alerta")
        body_source = template.response or template.message or ""

        context_retiro = {
            "empleado": "EMP-001",
            "empleado_nombre": "Juan García",
            "source_doctype": "Novedad SST",
            "source_name": "NSST-001",
            "action": "retiro",
            "is_reverse": False,
            "retirement_date": "",
            "reason": "",
            "site_url": "http://hubgh.local",
        }
        context_reverse = dict(context_retiro, is_reverse=True, action="reverse")

        body_retiro = render_template(body_source, context_retiro)
        body_reverse = render_template(body_source, context_reverse)

        # Los bodies deben ser distintos para demostrar la rama condicional
        self.assertNotEqual(
            body_retiro,
            body_reverse,
            "El body debe cambiar con is_reverse=True (template tiene lógica condicional)",
        )
