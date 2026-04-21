# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for www/agendar_examen.py portal handler.

The portal module (hubgh.hubgh.www.agendar_examen) does NOT exist in Batch 2.
These tests import it lazily inside each test method — they will fail RED with
ImportError until Batch 3 (Group E) creates the file. That is the expected state.

REQ refs: REQ-16 (allow_guest), REQ-17 (slot calendar), REQ-18 (booked token),
          REQ-19 (409 concurrency).
"""

from unittest.mock import patch
from frappe.tests.utils import FrappeTestCase
import frappe


class TestPortalGetAgendar(FrappeTestCase):
	"""Portal handler tests — RED until Batch 3 creates www/agendar_examen.py."""

	def _get_portal(self):
		"""Import portal lazily — raises ImportError until Batch 3 (expected RED)."""
		from hubgh.hubgh.www import agendar_examen
		return agendar_examen

	def test_get_agendar_examen_valid_token_renders_calendar(self):
		"""REQ-16/REQ-17: GET con token válido → context con slots y mode='pending'."""
		portal = self._get_portal()  # raises ImportError — RED as expected
		context = {}
		with patch(
			"hubgh.hubgh.examen_medico.token_manager.validate_token",
			return_value={
				"name": "CEM-001",
				"estado": "Pendiente Agendamiento",
				"ips": "IPS-TEST",
				"candidato": "CAND-001",
			},
		), patch(
			"hubgh.hubgh.examen_medico.slot_engine.get_available_slots",
			return_value=[{"fecha": "2026-07-13", "hora": "09:00", "disponibles": 2}],
		):
			portal.get_context(context)
		self.assertEqual(context.get("mode"), "pending")
		self.assertIn("slots", context)

	def test_get_agendar_examen_invalid_token_returns_400(self):
		"""REQ-16: Token inválido → lanza excepción / HTTP 400."""
		portal = self._get_portal()
		context = {}
		with patch(
			"hubgh.hubgh.examen_medico.token_manager.validate_token",
			side_effect=frappe.ValidationError("Token inválido"),
		):
			with self.assertRaises(Exception):
				portal.get_context(context)

	def test_get_agendar_examen_expired_token_rejected(self):
		"""REQ-12: Token expirado → excepción en get_context."""
		portal = self._get_portal()
		context = {}
		with patch(
			"hubgh.hubgh.examen_medico.token_manager.validate_token",
			side_effect=frappe.ValidationError("Token expirado"),
		):
			with self.assertRaises(Exception):
				portal.get_context(context)

	def test_get_agendar_examen_already_booked_token_shows_current(self):
		"""REQ-18: Cita ya Agendada → mode='booked', incluye datos de la cita."""
		portal = self._get_portal()
		context = {}
		with patch(
			"hubgh.hubgh.examen_medico.token_manager.validate_token",
			return_value={
				"name": "CEM-002",
				"estado": "Agendada",
				"ips": "IPS-TEST",
				"candidato": "CAND-001",
				"fecha_cita": "2026-07-20",
				"hora_cita": "09:00:00",
			},
		):
			portal.get_context(context)
		self.assertEqual(context.get("mode"), "booked")
		self.assertIn("cita", context)

	def test_post_booking_valid_slot_returns_200(self):
		"""REQ-10/REQ-19: POST con slot disponible → Cita=Agendada, retorna status ok."""
		portal = self._get_portal()
		with patch(
			"hubgh.hubgh.examen_medico.token_manager.validate_token",
			return_value={"name": "CEM-003", "estado": "Pendiente Agendamiento",
			              "ips": "IPS-TEST", "cupos_por_slot": 3},
		), patch.object(frappe.db, "get_value", return_value=0), \
		   patch.object(frappe.db, "set_value"):
			result = portal.book_slot(
				token="a" * 32,
				fecha="2026-07-13",
				hora="09:00",
			)
		self.assertEqual(result.get("status"), "ok")

	def test_post_booking_no_longer_available_slot_returns_409(self):
		"""REQ-19: Slot lleno → lanza excepción / 409 'Cupo ocupado'."""
		portal = self._get_portal()
		with patch(
			"hubgh.hubgh.examen_medico.token_manager.validate_token",
			return_value={"name": "CEM-004", "estado": "Pendiente Agendamiento",
			              "ips": "IPS-TEST", "cupos_por_slot": 1},
		), patch.object(frappe.db, "get_value", return_value=1):  # booked count == cupos
			with self.assertRaises(Exception):
				portal.book_slot(
					token="b" * 32,
					fecha="2026-07-13",
					hora="09:00",
				)
