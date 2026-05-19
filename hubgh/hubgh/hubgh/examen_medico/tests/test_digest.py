# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for digest.enviar_digest_diario_examenes.

Cubre:
- Skip cuando no hay agendados ni pendientes.
- Envío único cuando hay agendados (sin pendientes).
- Envío único cuando hay pendientes (sin agendados).
- Envío único cuando hay ambos.
- Recipients del Single doctype vs fallback hardcoded.
- Guardia horaria (solo envía a las 17:00).
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.examen_medico import digest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_template():
	t = MagicMock()
	t.subject = "Resumen — {{ fecha }}"
	t.response = "<p>{{ total_agendados }} agendados, {{ total_pendientes }} pendientes</p>"
	t.message = t.response
	return t


def _fake_candidato(name="CAND-001"):
	c = SimpleNamespace()
	c.nombres = "Ana"
	c.primer_apellido = "Pérez"
	c.segundo_apellido = "García"
	c.numero_documento = "1234567890"
	return c


def _fake_ips(name="IPS-001"):
	return SimpleNamespace(nombre="IPS Bogotá Centro")


def _mock_seventeen_hours():
	"""Devuelve un mock de `digest.datetime` cuya .now() retorna las 17:30."""
	mock_dt = MagicMock()
	mock_dt.now.return_value = datetime(2026, 5, 19, 17, 30, 0)
	# fromisoformat sigue funcionando con la implementación real
	mock_dt.fromisoformat.side_effect = datetime.fromisoformat
	return mock_dt


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDigest(FrappeTestCase):

	def test_skip_si_no_hay_agendados_ni_pendientes(self):
		"""Si las dos queries devuelven listas vacías, NO se llama a sendmail."""
		sendmail_calls = []

		with patch.object(digest, "datetime", _mock_seventeen_hours()), \
		     patch.object(digest, "_query_agendados_hoy", return_value=[]), \
		     patch.object(digest, "_query_pendientes", return_value=[]), \
		     patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)):
			digest.enviar_digest_diario_examenes()

		self.assertEqual(len(sendmail_calls), 0, "No debe enviar digest vacío")

	def test_solo_agendados(self):
		"""Con N agendados y 0 pendientes → 1 sendmail."""
		sendmail_calls = []
		agendados = [
			{"name": "CEM-001", "candidato": "CAND-001", "ips": "IPS-001",
			 "fecha_cita": "2026-05-20", "hora_cita": "08:00",
			 "sede_seleccionada": "Sede 1", "cargo_al_enviar": "AUX COCINA"},
			{"name": "CEM-002", "candidato": "CAND-002", "ips": "IPS-001",
			 "fecha_cita": "2026-05-20", "hora_cita": "09:00",
			 "sede_seleccionada": "Sede 1", "cargo_al_enviar": "AUX COCINA"},
		]

		with patch.object(digest, "datetime", _mock_seventeen_hours()), \
		     patch.object(digest, "_query_agendados_hoy", return_value=agendados), \
		     patch.object(digest, "_query_pendientes", return_value=[]), \
		     patch.object(digest, "_load_digest_recipients", return_value=["sst@x.com"]), \
		     patch.object(frappe, "get_cached_doc",
		                  side_effect=lambda dt, name: _fake_candidato() if dt == "Candidato" else _fake_ips()), \
		     patch.object(frappe, "get_doc", return_value=_make_template()), \
		     patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)):
			digest.enviar_digest_diario_examenes()

		self.assertEqual(len(sendmail_calls), 1, "Debe enviar exactamente UN correo")
		self.assertEqual(sendmail_calls[0]["recipients"], ["sst@x.com"])
		# No debe haber CC ni BCC — el digest va en 'recipients' nada más
		self.assertFalse(sendmail_calls[0].get("cc"))
		self.assertFalse(sendmail_calls[0].get("bcc"))

	def test_solo_pendientes(self):
		"""Con 0 agendados y N pendientes → 1 sendmail."""
		sendmail_calls = []
		pendientes = [
			{"name": "CEM-003", "candidato": "CAND-003", "ips": "IPS-001",
			 "creation": "2026-05-15 10:00:00", "cargo_al_enviar": "ADMIN"},
		]

		with patch.object(digest, "datetime", _mock_seventeen_hours()), \
		     patch.object(digest, "_query_agendados_hoy", return_value=[]), \
		     patch.object(digest, "_query_pendientes", return_value=pendientes), \
		     patch.object(digest, "_load_digest_recipients", return_value=["sst@x.com"]), \
		     patch.object(frappe, "get_cached_doc",
		                  side_effect=lambda dt, name: _fake_candidato() if dt == "Candidato" else _fake_ips()), \
		     patch.object(frappe, "get_doc", return_value=_make_template()), \
		     patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)):
			digest.enviar_digest_diario_examenes()

		self.assertEqual(len(sendmail_calls), 1)

	def test_ambos_agendados_y_pendientes(self):
		"""Con agendados y pendientes → 1 sendmail (no 2)."""
		sendmail_calls = []
		agendados = [{"name": "CEM-001", "candidato": "CAND-001", "ips": "IPS-001",
		              "fecha_cita": "2026-05-20", "hora_cita": "08:00",
		              "sede_seleccionada": None, "cargo_al_enviar": "AUX"}]
		pendientes = [{"name": "CEM-003", "candidato": "CAND-003", "ips": "IPS-001",
		               "creation": "2026-05-15 10:00:00", "cargo_al_enviar": "AUX"}]

		with patch.object(digest, "datetime", _mock_seventeen_hours()), \
		     patch.object(digest, "_query_agendados_hoy", return_value=agendados), \
		     patch.object(digest, "_query_pendientes", return_value=pendientes), \
		     patch.object(digest, "_load_digest_recipients", return_value=["sst@x.com"]), \
		     patch.object(frappe, "get_cached_doc",
		                  side_effect=lambda dt, name: _fake_candidato() if dt == "Candidato" else _fake_ips()), \
		     patch.object(frappe, "get_doc", return_value=_make_template()), \
		     patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)):
			digest.enviar_digest_diario_examenes()

		self.assertEqual(len(sendmail_calls), 1, "Un único correo combinando ambas secciones")

	def test_recipients_desde_config_doctype(self):
		"""Cuando el Single tiene rows activas, _load_digest_recipients las devuelve."""
		fake_config = MagicMock()
		fake_config.get.return_value = [
			SimpleNamespace(activo=1, email="custom1@x.com"),
			SimpleNamespace(activo=1, email="custom2@x.com"),
			SimpleNamespace(activo=0, email="inactivo@x.com"),
		]
		with patch.object(frappe, "get_cached_doc", return_value=fake_config):
			emails = digest._load_digest_recipients()

		self.assertEqual(emails, ["custom1@x.com", "custom2@x.com"])

	def test_recipients_fallback_si_config_vacia(self):
		"""Si el doctype no existe o está vacío → fallback hardcoded."""
		with patch.object(frappe, "get_cached_doc", side_effect=Exception("no existe")):
			emails = digest._load_digest_recipients()

		self.assertEqual(emails, digest.DIGEST_RECIPIENTS_FALLBACK)

	def test_guardia_horaria_skip_fuera_de_las_17(self):
		"""Si la hora no es 17, no debe ejecutar nada (ni siquiera querys)."""
		sendmail_calls = []
		query_calls = []

		mock_dt = MagicMock()
		mock_dt.now.return_value = datetime(2026, 5, 19, 10, 0, 0)

		with patch.object(digest, "datetime", mock_dt), \
		     patch.object(digest, "_query_agendados_hoy",
		                  side_effect=lambda: query_calls.append("agendados") or []), \
		     patch.object(digest, "_query_pendientes",
		                  side_effect=lambda: query_calls.append("pendientes") or []), \
		     patch.object(frappe, "sendmail", side_effect=lambda **kw: sendmail_calls.append(kw)):
			digest.enviar_digest_diario_examenes()

		self.assertEqual(len(sendmail_calls), 0)
		self.assertEqual(len(query_calls), 0, "Ni siquiera debe consultar la DB fuera de las 17h")
