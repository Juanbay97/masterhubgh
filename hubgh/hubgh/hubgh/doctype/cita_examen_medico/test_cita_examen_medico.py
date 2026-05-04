# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for Cita Examen Medico lifecycle: state transitions, booking, outcomes.

Strategy for RED state (Batch 2):
- cita_service module does NOT exist yet — all tests that call it will fail
  RED with ImportError. That is the expected state until Batch 3.
- Uses FrappeTestCase + patch.object(frappe.db, ...) for Frappe v15 safety.

REQ refs: REQ-8, REQ-9, REQ-10, REQ-11, REQ-13, REQ-14, REQ-15.
"""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import frappe
from frappe.tests.utils import FrappeTestCase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cita(**overrides):
	defaults = {
		"name": "CEM-2026-0001",
		"candidato": "CAND-001",
		"ips": "IPS-TEST",
		"estado": "Pendiente Agendamiento",
		"token": None,
		"token_expira": None,
		"token_usado": 0,
		"fecha_cita": None,
		"hora_cita": None,
		"concepto_resultado": None,
		"motivo_aplazamiento": None,
		"instrucciones_reagendamiento": None,
		"enviado_confirmacion": 0,
		"enviado_recordatorio": 0,
		"enviado_ips": 0,
		"cita_anterior": None,
		"cargo_al_enviar": None,
	}
	from types import SimpleNamespace
	defaults.update(overrides)
	return SimpleNamespace(**defaults)


def _get_cita_service():
	"""Import lazily — raises ImportError until Batch 3 (expected RED)."""
	from hubgh.hubgh.examen_medico import cita_service
	return cita_service


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCitaExamenMedico(FrappeTestCase):

	def test_send_to_exam_creates_cita_pendiente_agendamiento_with_token(self):
		"""REQ-8: send_to_medical_exam crea Cita con Pendiente Agendamiento y token 32-char hex."""
		svc = _get_cita_service()  # raises ImportError — RED expected

		with patch.object(frappe.db, "get_value", return_value="IPS-MEDELLIN"), \
		     patch.object(frappe, "get_doc", return_value=_make_cita(
		         candidato="CAND-001", ciudad="Medellin", cargo_postulado="Auxiliar"
		     )), \
		     patch.object(frappe, "new_doc", return_value=MagicMock(
		         name=None, insert=lambda: None
		     )), \
		     patch("hubgh.hubgh.examen_medico.token_manager.create_token",
		           return_value="a" * 32):
			cita = svc.create_cita_and_send_link("CAND-001")

		self.assertIsNotNone(cita)

	def test_cargo_captured_at_send_to_exam_written_to_candidato(self):
		"""REQ-9: cargo_postulado del candidato se copia a Cita.cargo_al_enviar al crear."""
		svc = _get_cita_service()

		from types import SimpleNamespace
		candidato = SimpleNamespace(
			name="CAND-001",
			nombre="Ana",
			email="ana@test.com",
			ciudad="Medellin",
			cargo_postulado="Auxiliar Logístico",
		)
		new_cita = MagicMock()
		new_cita.name = None

		with patch.object(frappe, "get_doc", return_value=candidato), \
		     patch.object(frappe.db, "get_value", return_value="IPS-TEST"), \
		     patch.object(frappe, "new_doc", return_value=new_cita), \
		     patch("hubgh.hubgh.examen_medico.token_manager.create_token",
		           return_value="b" * 32):
			svc.create_cita_and_send_link("CAND-001")

		# Verify cargo_al_enviar was set on the new cita document
		self.assertEqual(new_cita.cargo_al_enviar, "Auxiliar Logístico")

	def test_book_slot_with_cupos_available_succeeds(self):
		"""REQ-10: book_slot con cupo disponible → Cita=Agendada, token_usado=1."""
		svc = _get_cita_service()

		future = datetime.now() + timedelta(days=10)
		with patch("hubgh.hubgh.examen_medico.token_manager.validate_token",
		           return_value={"name": "CEM-001", "estado": "Pendiente Agendamiento",
		                         "ips": "IPS-TEST", "token_expira": future,
		                         "token_usado": 0, "cupos_por_slot": 3}), \
		     patch.object(frappe.db, "get_value", return_value=0), \
		     patch.object(frappe.db, "set_value"):
			result = svc.book_slot("c" * 32, "2026-08-10", "09:00")

		self.assertIsNotNone(result)

	def test_book_slot_when_cupos_exceeded_fails(self):
		"""REQ-11: Cupos excedidos → ValidationError 'Cupo ocupado'."""
		svc = _get_cita_service()

		future = datetime.now() + timedelta(days=10)
		with patch("hubgh.hubgh.examen_medico.token_manager.validate_token",
		           return_value={"name": "CEM-002", "estado": "Pendiente Agendamiento",
		                         "ips": "IPS-TEST", "cupos_por_slot": 1,
		                         "token_expira": future, "token_usado": 0}), \
		     patch.object(frappe.db, "get_value", return_value=1):  # count == cupos
			with self.assertRaises(Exception, msg="Cupo lleno debe lanzar excepción"):
				svc.book_slot("d" * 32, "2026-08-10", "09:00")

	def test_sst_realizada_favorable_writes_concepto_medico(self):
		"""REQ-13: SST Realizada + Favorable → Candidato.concepto_medico=Favorable."""
		svc = _get_cita_service()

		set_calls = {}

		def capture_set_value(doctype, name, field_or_dict, val=None, **kw):
			set_calls.setdefault(doctype, {}).update(
				field_or_dict if isinstance(field_or_dict, dict) else {field_or_dict: val}
			)

		with patch.object(frappe, "get_doc", return_value=_make_cita(
		         name="CEM-003", estado="Agendada", candidato="CAND-001"
		     )), \
		     patch.object(frappe.db, "set_value", side_effect=capture_set_value):
			svc.set_exam_outcome("CEM-003", "Realizada", concepto="Favorable")

		concepto = (
			set_calls.get("Candidato", {}).get("concepto_medico")
			or set_calls.get("Cita Examen Medico", {}).get("concepto_resultado")
		)
		self.assertEqual(concepto, "Favorable")

	def test_sst_aplazada_creates_new_token_sends_email(self):
		"""REQ-14: SST Aplazada → nuevo token generado, email enviado al candidato."""
		svc = _get_cita_service()

		tokens_created = []
		emails_sent = []

		with patch.object(frappe, "get_doc", return_value=_make_cita(
		         name="CEM-004", estado="Agendada", candidato="CAND-001"
		     )), \
		     patch("hubgh.hubgh.examen_medico.token_manager.create_token",
		           side_effect=lambda name, **kw: tokens_created.append(name) or "e" * 32), \
		     patch("hubgh.hubgh.examen_medico.email_service.send_exam_email",
		           side_effect=lambda *a, **kw: emails_sent.append(True)), \
		     patch.object(frappe.db, "set_value"):
			svc.set_exam_outcome(
				"CEM-004",
				"Aplazada",
				motivo="Requiere exámenes adicionales",
				instrucciones="Reprogramar en 15 días",
			)

		self.assertGreater(len(tokens_created), 0, "Debe crear un nuevo token")
		self.assertGreater(len(emails_sent), 0, "Debe enviar email con nuevo link")

	def test_sst_no_asistio_rebook_creates_new_cita_cancels_old(self):
		"""REQ-15: No Asistió + rebook → cita vieja=Cancelada, nueva cita creada."""
		svc = _get_cita_service()

		set_calls = {}
		new_docs = []

		def capture_set(doctype, name, field_or_dict, val=None, **kw):
			set_calls.setdefault(name, {}).update(
				field_or_dict if isinstance(field_or_dict, dict) else {field_or_dict: val}
			)

		with patch.object(frappe, "get_doc", return_value=_make_cita(
		         name="CEM-005", estado="Agendada", candidato="CAND-001", ips="IPS-TEST"
		     )), \
		     patch.object(frappe.db, "set_value", side_effect=capture_set), \
		     patch.object(frappe, "new_doc",
		                  side_effect=lambda dt: new_docs.append(dt) or MagicMock(insert=lambda: None)), \
		     patch("hubgh.hubgh.examen_medico.token_manager.create_token", return_value="f" * 32), \
		     patch("hubgh.hubgh.examen_medico.email_service.send_exam_email"):
			svc.set_exam_outcome("CEM-005", "No Asistió", action="rebook")

		old_estado = set_calls.get("CEM-005", {}).get("estado")
		self.assertEqual(old_estado, "Cancelada")
		self.assertGreater(len(new_docs), 0, "Nueva cita debe ser creada")

	def test_sst_no_asistio_close_cancels_cita(self):
		"""REQ-15: No Asistió + close → cita=Cancelada, sin nueva cita."""
		svc = _get_cita_service()

		set_calls = {}
		new_docs = []

		def capture_set(doctype, name, field_or_dict, val=None, **kw):
			set_calls.setdefault(name, {}).update(
				field_or_dict if isinstance(field_or_dict, dict) else {field_or_dict: val}
			)

		with patch.object(frappe, "get_doc", return_value=_make_cita(
		         name="CEM-006", estado="Agendada", candidato="CAND-001", ips="IPS-TEST"
		     )), \
		     patch.object(frappe.db, "set_value", side_effect=capture_set), \
		     patch.object(frappe, "new_doc",
		                  side_effect=lambda dt: new_docs.append(dt)):
			svc.set_exam_outcome("CEM-006", "No Asistió", action="close")

		old_estado = set_calls.get("CEM-006", {}).get("estado")
		self.assertEqual(old_estado, "Cancelada")
		self.assertEqual(len(new_docs), 0, "No debe crear nueva cita con action=close")
