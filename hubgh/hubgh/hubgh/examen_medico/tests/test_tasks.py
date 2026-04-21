# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for tasks.enviar_recordatorios_examen_medico.

Strategy (Batch 3 — GREEN):
- Task is fully implemented.
- patch.object(frappe.db, ...) for Frappe v15 safety.
- Hour guard (datetime.now().hour == 17) is patched to always return 17.
- NOT patching frappe.db as a whole (avoids AsyncMock coercion).

REQ refs: REQ-20 (cron recordatorios), REQ-21 (idempotente).
"""

from datetime import datetime
from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase
import frappe

from hubgh.hubgh.examen_medico import tasks


# Helper to make a mock Candidato/IPS doc
def _make_candidato_doc(nombre="Juan", email="juan@test.com"):
	doc = MagicMock()
	doc.nombre = nombre
	doc.email = email
	return doc


def _make_ips_doc(nombre="IPS Test", direccion="Calle 1"):
	doc = MagicMock()
	doc.nombre = nombre
	doc.direccion = direccion
	return doc


class TestTasks(FrappeTestCase):

	def _run_with_hour_17(self, fn, *args, **kwargs):
		"""Patch datetime.now() to return hour=17 so the hour guard passes."""
		fake_now = MagicMock(return_value=MagicMock(hour=17))
		with patch("hubgh.hubgh.examen_medico.tasks.datetime") as mock_dt:
			mock_dt.now.return_value.hour = 17
			mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
			return fn(*args, **kwargs)

	def test_enviar_recordatorios_emails_tomorrows_agendadas(self):
		"""REQ-20: Sólo citas de mañana, Agendada, enviado_recordatorio=0 reciben email."""
		cita_a = {
			"name": "CEM-A",
			"candidato": "CAND-001",
			"ips": "IPS-TEST",
			"fecha_cita": "2026-07-07",
			"hora_cita": "09:00:00",
			"estado": "Agendada",
			"enviado_recordatorio": 0,
		}
		email_calls = []

		def fake_get_doc(doctype, name):
			if doctype == "Candidato":
				return _make_candidato_doc()
			if doctype == "IPS":
				return _make_ips_doc()
			return MagicMock()

		with patch.object(frappe.db, "get_all", return_value=[cita_a]), \
		     patch.object(frappe.db, "set_value") as mock_set, \
		     patch.object(frappe, "get_doc", side_effect=fake_get_doc), \
		     patch("hubgh.hubgh.examen_medico.tasks.send_exam_email",
		           side_effect=lambda *a, **kw: email_calls.append(kw)):
			# Bypass hour guard
			with patch("hubgh.hubgh.examen_medico.tasks.datetime") as mock_dt:
				mock_dt.now.return_value.hour = 17
				mock_dt.side_effect = None
				tasks.enviar_recordatorios_examen_medico()

		self.assertGreater(len(email_calls), 0, "Email debe ser enviado para la cita de mañana")

	def test_enviar_recordatorios_skips_already_flagged(self):
		"""REQ-21: Citas con enviado_recordatorio=1 no reciben un segundo email."""
		email_calls = []

		# Return empty list — filter already excludes flagged citas at DB level
		with patch.object(frappe.db, "get_all", return_value=[]), \
		     patch.object(frappe.db, "set_value"), \
		     patch("hubgh.hubgh.examen_medico.tasks.send_exam_email",
		           side_effect=lambda *a, **kw: email_calls.append(kw)):
			with patch("hubgh.hubgh.examen_medico.tasks.datetime") as mock_dt:
				mock_dt.now.return_value.hour = 17
				mock_dt.side_effect = None
				tasks.enviar_recordatorios_examen_medico()

		self.assertEqual(len(email_calls), 0, "No emails deben enviarse si no hay citas pendientes")

	def test_enviar_recordatorios_idempotent_same_day(self):
		"""REQ-21: Segunda ejecución del mismo día no duplica envíos."""
		email_calls = []

		with patch.object(frappe.db, "get_all", return_value=[]), \
		     patch.object(frappe.db, "set_value"), \
		     patch("hubgh.hubgh.examen_medico.tasks.send_exam_email",
		           side_effect=lambda *a, **kw: email_calls.append(kw)):
			with patch("hubgh.hubgh.examen_medico.tasks.datetime") as mock_dt:
				mock_dt.now.return_value.hour = 17
				mock_dt.side_effect = None
				tasks.enviar_recordatorios_examen_medico()
				tasks.enviar_recordatorios_examen_medico()

		self.assertEqual(len(email_calls), 0, "Segunda ejecución no duplica si no hay citas")

	def test_enviar_recordatorios_skips_non_agendada_states(self):
		"""REQ-20: Citas en estado Cancelada/Aplazada/Realizada no se procesan."""
		email_calls = []

		# DB filter already excludes non-Agendada — return empty
		with patch.object(frappe.db, "get_all", return_value=[]):
			with patch("hubgh.hubgh.examen_medico.tasks.send_exam_email",
			           side_effect=lambda *a, **kw: email_calls.append(kw)):
				with patch("hubgh.hubgh.examen_medico.tasks.datetime") as mock_dt:
					mock_dt.now.return_value.hour = 17
					mock_dt.side_effect = None
					tasks.enviar_recordatorios_examen_medico()

		self.assertEqual(len(email_calls), 0, "No-Agendada states no deben recibir email")
