# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for email_service: send_exam_email, get_ips_email.

Strategy (Batch 3 — GREEN):
- Functions are fully implemented.
- patch.object(frappe.db, ...) for Frappe v15 safety.
- NOT patching frappe.db as a whole (avoids AsyncMock coercion).

REQ refs: REQ-22 (email types), REQ-24 (IPS routing), REQ-5 (email_por_ciudad).
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase
import frappe

from hubgh.hubgh.examen_medico import email_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ips(ciudad_overrides=None, email_notificacion="default@ips.com"):
	return {
		"name": "IPS-TEST",
		"email_notificacion": email_notificacion,
		"emails_por_ciudad": ciudad_overrides or [],
	}


def _make_template(subject="Asunto", response="Mensaje"):
	t = MagicMock()
	t.subject = subject
	t.response = response
	t.message = response
	return t


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEmailService(FrappeTestCase):

	def test_sends_email_via_frappe_sendmail(self):
		"""REQ-22: send_exam_email llama frappe.sendmail al menos una vez."""
		sendmail_calls = []

		with patch.object(frappe, "get_doc", return_value=_make_template()), \
		     patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)):
			email_service.send_exam_email(
				template_name="examen_medico_link_agendar",
				recipients=["candidato@example.com"],
				context={"candidato": {"nombre": "Ana"}},
			)

		self.assertGreater(len(sendmail_calls), 0, "frappe.sendmail debe ser llamado")
		recipients = sendmail_calls[0].get("recipients", [])
		self.assertIn("candidato@example.com", recipients)

	def test_attaches_file_when_file_path_provided(self):
		"""REQ-23: Cuando se pasa attachments, frappe.sendmail recibe el attachment."""
		sendmail_calls = []
		attachment = {"fname": "FRSN-02.xlsx", "fcontent": b"PK..."}

		with patch.object(frappe, "get_doc", return_value=_make_template()), \
		     patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)):
			email_service.send_exam_email(
				template_name="examen_medico_ips_notificacion",
				recipients=["ips@example.com"],
				context={},
				attachments=[attachment],
			)

		self.assertGreater(len(sendmail_calls), 0)
		attachments_sent = sendmail_calls[0].get("attachments", [])
		self.assertIn(attachment, attachments_sent)

	def test_per_ips_template_override(self):
		"""REQ-24: send_exam_email acepta template_name personalizado por IPS."""
		get_doc_calls = []

		def fake_get_doc(doctype, name):
			get_doc_calls.append((doctype, name))
			return _make_template()

		with patch.object(frappe, "get_doc", side_effect=fake_get_doc), \
		     patch.object(frappe, "sendmail"):
			email_service.send_exam_email(
				template_name="ips_custom_template",
				recipients=["ips@custom.com"],
				context={},
			)

		fetched_templates = [name for dt, name in get_doc_calls if dt == "Email Template"]
		self.assertIn("ips_custom_template", fetched_templates)

	def test_routes_to_email_por_ciudad_when_match(self):
		"""REQ-5/REQ-24: get_ips_email retorna email_override cuando ciudad coincide."""
		ips = _make_ips(
			ciudad_overrides=[
				{"ciudad": "Cartagena", "email": "ips-ctg@example.com"},
			],
			email_notificacion="default@ips.com",
		)
		result = email_service.get_ips_email(ips, "Cartagena")
		self.assertEqual(result, "ips-ctg@example.com")

	def test_routes_to_default_email_when_no_ciudad_match(self):
		"""REQ-24: get_ips_email retorna email_notificacion cuando ciudad no coincide."""
		ips = _make_ips(
			ciudad_overrides=[
				{"ciudad": "Cartagena", "email": "ips-ctg@example.com"},
			],
			email_notificacion="default@ips.com",
		)
		result = email_service.get_ips_email(ips, "Bogota")
		self.assertEqual(result, "default@ips.com")
