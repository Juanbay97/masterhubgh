# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for services/email_dispatcher.py and backward-compat shim in email_service.py

TDD Cycle: RED (T-4) → GREEN (I-4) → TRIANGULATE → RED (T-5) → GREEN (I-5)

Tests:
- T-4: dispatch_email ok, skipped (empty recipients), error no relanza, log_error invocado en fallo
- T-5: send_exam_email sigue siendo void, frappe.sendmail se invoca, firma idéntica

Note: frappe se importa DENTRO de dispatch_email, así que usamos patch.object(frappe, ...)
      igual que el resto de los tests de examen médico.
"""

import inspect
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase
import frappe


def _make_template(subject="Asunto {{ var }}", response="Hola {{ var }}"):
    t = MagicMock()
    t.subject = subject
    t.response = response
    t.message = response
    return t


# ---------------------------------------------------------------------------
# T-4: dispatch_email
# ---------------------------------------------------------------------------

class TestDispatchEmail(FrappeTestCase):

    def test_dispatch_email_ok(self):
        """dispatch_email retorna status='ok' cuando sendmail no lanza."""
        from hubgh.hubgh.services.email_dispatcher import dispatch_email

        sendmail_calls = []

        with patch.object(frappe, "get_doc", return_value=_make_template()), \
             patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)), \
             patch.object(frappe, "log_error"):
            result = dispatch_email(
                template_name="traslado_pdv_empleado_programado",
                recipients=["empleado@test.com"],
                context={"var": "test"},
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["template"], "traslado_pdv_empleado_programado")
        self.assertIn("empleado@test.com", result["recipients"])
        self.assertIsNone(result["error"])
        self.assertEqual(len(sendmail_calls), 1)

    def test_dispatch_email_skipped_empty_recipients(self):
        """dispatch_email retorna status='skipped' cuando recipients está vacío."""
        from hubgh.hubgh.services.email_dispatcher import dispatch_email

        sendmail_mock = MagicMock()

        with patch.object(frappe, "sendmail", sendmail_mock):
            result_empty = dispatch_email("tmpl", [], {})
            result_none = dispatch_email("tmpl", None, {})

        self.assertEqual(result_empty["status"], "skipped")
        self.assertEqual(result_none["status"], "skipped")
        sendmail_mock.assert_not_called()

    def test_dispatch_email_skipped_filters_empty_strings(self):
        """dispatch_email filtra strings vacíos y None de recipients antes de evaluar."""
        from hubgh.hubgh.services.email_dispatcher import dispatch_email

        sendmail_mock = MagicMock()

        with patch.object(frappe, "sendmail", sendmail_mock):
            result = dispatch_email("tmpl", ["", None, ""], {})

        self.assertEqual(result["status"], "skipped")
        sendmail_mock.assert_not_called()

    def test_dispatch_email_error_does_not_raise(self):
        """Cuando frappe.sendmail lanza, dispatch_email NO relanza — retorna status='error'."""
        from hubgh.hubgh.services.email_dispatcher import dispatch_email

        with patch.object(frappe, "get_doc", return_value=_make_template()), \
             patch.object(frappe, "sendmail", side_effect=Exception("SMTP failure")), \
             patch.object(frappe, "log_error"):
            # NO debe lanzar
            result = dispatch_email("tmpl", ["empleado@test.com"], {})

        self.assertEqual(result["status"], "error")
        self.assertIsNotNone(result["error"])
        self.assertIn("SMTP failure", result["error"])

    def test_dispatch_email_error_calls_log_error(self):
        """Cuando frappe.sendmail lanza, frappe.log_error debe ser invocado."""
        from hubgh.hubgh.services.email_dispatcher import dispatch_email

        log_calls = []

        with patch.object(frappe, "get_doc", return_value=_make_template()), \
             patch.object(frappe, "sendmail", side_effect=RuntimeError("SMTP down")), \
             patch.object(frappe, "log_error", side_effect=lambda **kw: log_calls.append(kw)):
            dispatch_email("some_template", ["x@test.com"], {})

        self.assertEqual(len(log_calls), 1)
        title = log_calls[0].get("title", "")
        self.assertIn("some_template", title)

    def test_dispatch_email_passes_cc(self):
        """cc debe ser pasado a frappe.sendmail."""
        from hubgh.hubgh.services.email_dispatcher import dispatch_email

        sendmail_calls = []

        with patch.object(frappe, "get_doc", return_value=_make_template()), \
             patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)), \
             patch.object(frappe, "log_error"):
            dispatch_email("tmpl", ["to@test.com"], {}, cc=["cc@test.com"])

        self.assertEqual(sendmail_calls[0]["cc"], ["cc@test.com"])

    # TRIANGULATE: template con response vs message
    def test_dispatch_uses_response_field_if_present(self):
        """dispatch_email usa template.response cuando message está vacío."""
        from hubgh.hubgh.services.email_dispatcher import dispatch_email

        template = MagicMock()
        template.subject = "Test"
        template.response = "<p>Response body</p>"
        template.message = ""

        sendmail_calls = []

        with patch.object(frappe, "get_doc", return_value=template), \
             patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)), \
             patch.object(frappe, "log_error"):
            dispatch_email("tmpl", ["x@t.com"], {})

        # render_template devuelve el template crudo en este contexto
        self.assertIn("Response body", sendmail_calls[0]["message"])

    # TRIANGULATE: attachments pasados correctamente
    def test_dispatch_email_passes_attachments(self):
        """attachments debe ser pasado a frappe.sendmail."""
        from hubgh.hubgh.services.email_dispatcher import dispatch_email

        sendmail_calls = []
        attachment = {"fname": "test.xlsx", "fcontent": b"data"}

        with patch.object(frappe, "get_doc", return_value=_make_template()), \
             patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)), \
             patch.object(frappe, "log_error"):
            dispatch_email("tmpl", ["x@t.com"], {}, attachments=[attachment])

        self.assertIn(attachment, sendmail_calls[0].get("attachments", []))


# ---------------------------------------------------------------------------
# T-5: backward-compat shim en examen_medico/email_service.py
# ---------------------------------------------------------------------------

class TestEmailServiceBackwardCompat(FrappeTestCase):

    def test_send_exam_email_returns_none(self):
        """send_exam_email debe ser void (retornar None)."""
        from hubgh.hubgh.examen_medico.email_service import send_exam_email

        with patch.object(frappe, "get_doc", return_value=_make_template()), \
             patch.object(frappe, "sendmail"), \
             patch.object(frappe, "log_error"):
            result = send_exam_email(
                template_name="examen_medico_link_agendar",
                recipients=["candidato@test.com"],
                context={"candidato": {"nombre": "Ana"}},
            )

        self.assertIsNone(result, "send_exam_email debe retornar None (contrato void)")

    def test_send_exam_email_calls_sendmail(self):
        """send_exam_email debe invocar frappe.sendmail (vía dispatch_email)."""
        from hubgh.hubgh.examen_medico.email_service import send_exam_email

        sendmail_mock = MagicMock()

        with patch.object(frappe, "get_doc", return_value=_make_template()), \
             patch.object(frappe, "sendmail", sendmail_mock), \
             patch.object(frappe, "log_error"):
            send_exam_email(
                template_name="examen_medico_link_agendar",
                recipients=["candidato@test.com"],
                context={"candidato": {"nombre": "Ana"}},
            )

        sendmail_mock.assert_called_once()

    def test_send_exam_email_signature_unchanged(self):
        """send_exam_email debe aceptar exactamente los mismos argumentos que antes."""
        from hubgh.hubgh.examen_medico.email_service import send_exam_email

        sig = inspect.signature(send_exam_email)
        params = list(sig.parameters.keys())
        self.assertEqual(
            params,
            ["template_name", "recipients", "context", "attachments", "cc"],
            f"Firma de send_exam_email cambió: {params}",
        )

    def test_send_exam_email_passes_attachments(self):
        """send_exam_email debe pasar attachments a frappe.sendmail."""
        from hubgh.hubgh.examen_medico.email_service import send_exam_email

        sendmail_calls = []
        attachment = {"fname": "FRSN-02.xlsx", "fcontent": b"PK..."}

        with patch.object(frappe, "get_doc", return_value=_make_template()), \
             patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)), \
             patch.object(frappe, "log_error"):
            send_exam_email(
                template_name="examen_medico_ips_notificacion",
                recipients=["ips@test.com"],
                context={},
                attachments=[attachment],
            )

        self.assertIn(attachment, sendmail_calls[0].get("attachments", []))

    # TRIANGULATE: verificar que existentes tests de examen médico siguen pasando
    def test_get_ips_email_unchanged(self):
        """get_ips_email no debe ser modificado — sigue siendo función independiente."""
        from hubgh.hubgh.examen_medico.email_service import get_ips_email

        ips = {
            "email_notificacion": "default@ips.com",
            "emails_por_ciudad": [{"ciudad": "Bogotá", "email": "bog@ips.com"}],
        }
        self.assertEqual(get_ips_email(ips, "Bogotá"), "bog@ips.com")
        self.assertEqual(get_ips_email(ips, "Medellín"), "default@ips.com")
