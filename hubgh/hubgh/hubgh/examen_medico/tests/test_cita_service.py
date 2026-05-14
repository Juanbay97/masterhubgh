# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for cita_service helpers.

Covers _resolve_active_ips_for_ciudad accent-tolerant lookup so that
candidates whose ciudad is stored without accents (legacy Select values)
still match IPS records whose ciudad is the accented Ciudad fixture name.
"""

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.examen_medico import cita_service


class TestResolveIpsForCiudad(FrappeTestCase):
	def test_normalize_city_key_strips_accents_and_case(self):
		self.assertEqual(cita_service._normalize_city_key("Bogotá"), "bogota")
		self.assertEqual(cita_service._normalize_city_key("Bogota"), "bogota")
		self.assertEqual(cita_service._normalize_city_key("MEDELLÍN"), "medellin")
		self.assertEqual(cita_service._normalize_city_key("  Cartagena  "), "cartagena")
		self.assertEqual(cita_service._normalize_city_key(""), "")
		self.assertEqual(cita_service._normalize_city_key(None), "")

	def test_resolve_returns_none_for_empty_ciudad(self):
		self.assertIsNone(cita_service._resolve_active_ips_for_ciudad(""))
		self.assertIsNone(cita_service._resolve_active_ips_for_ciudad(None))

	def test_resolve_uses_exact_match_when_available(self):
		with patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.db.get_value",
			return_value="IPS-EXACT",
		) as get_value, patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.get_all"
		) as get_all:
			result = cita_service._resolve_active_ips_for_ciudad("Bogotá")

		self.assertEqual(result, "IPS-EXACT")
		get_value.assert_called_once()
		get_all.assert_not_called()

	def test_resolve_falls_back_to_accent_normalized_match(self):
		with patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.db.get_value",
			return_value=None,
		), patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.get_all",
			return_value=[
				type("Row", (), {"name": "Zonamedica", "ciudad": "Bogotá"})(),
				type("Row", (), {"name": "OtraIPS", "ciudad": "Medellín"})(),
			],
		):
			result = cita_service._resolve_active_ips_for_ciudad("Bogota")

		self.assertEqual(result, "Zonamedica")

	def test_resolve_returns_none_when_no_active_ips_matches(self):
		with patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.db.get_value",
			return_value=None,
		), patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.get_all",
			return_value=[
				type("Row", (), {"name": "Zonamedica", "ciudad": "Cartagena"})(),
			],
		):
			result = cita_service._resolve_active_ips_for_ciudad("Bogota")

		self.assertIsNone(result)


class TestGetSedesForCiudadEmailCascade(FrappeTestCase):
	"""Cascada de resolución del email destinatario para la sede:

	  1. sede.email_notificacion (más específico)
	  2. IPS.emails_por_ciudad matched por ciudad de la sede (accent-tolerant)
	  3. IPS.email_notificacion (legacy fallback)

	Bug histórico: la IPS Zonamedica MR SAS tenía emails_por_ciudad para
	Medellín/Cartagena pero las sedes en esas ciudades quedaban con
	email_notificacion vacío, así que el código caía directo a
	IPS.email_notificacion (recepcion@...) ignorando el override por ciudad.
	"""

	def _ips(self, sedes, emails_por_ciudad=None, ips_email="legacy@ips.com"):
		return {
			"name": "IPS-TEST",
			"email_notificacion": ips_email,
			"emails_por_ciudad": emails_por_ciudad or [],
			"sedes": sedes,
			"direccion": "",
			"telefono": "",
			"ciudad": "",
			"requiere_orden_servicio": 0,
		}

	def test_sede_email_wins_when_present(self):
		ips = self._ips(
			sedes=[{"activa": 1, "ciudad": "Medellín", "nombre_sede": "S1", "email_notificacion": "sede@x.com"}],
			emails_por_ciudad=[{"ciudad": "Medellín", "email": "porciudad@x.com"}],
		)
		out = cita_service._get_sedes_for_ciudad(ips, "Medellín")
		self.assertEqual(len(out), 1)
		self.assertEqual(out[0]["email"], "sede@x.com")

	def test_emails_por_ciudad_wins_when_sede_email_empty(self):
		ips = self._ips(
			sedes=[{"activa": 1, "ciudad": "Medellín", "nombre_sede": "S1", "email_notificacion": ""}],
			emails_por_ciudad=[{"ciudad": "Medellín", "email": "porciudad@x.com"}],
		)
		out = cita_service._get_sedes_for_ciudad(ips, "Medellín")
		self.assertEqual(out[0]["email"], "porciudad@x.com")

	def test_ips_email_used_when_no_sede_email_and_no_ciudad_match(self):
		ips = self._ips(
			sedes=[{"activa": 1, "ciudad": "Bogotá", "nombre_sede": "S1", "email_notificacion": ""}],
			emails_por_ciudad=[{"ciudad": "Medellín", "email": "porciudad@x.com"}],
			ips_email="legacy@ips.com",
		)
		out = cita_service._get_sedes_for_ciudad(ips, "Bogotá")
		self.assertEqual(out[0]["email"], "legacy@ips.com")

	def test_emails_por_ciudad_match_is_accent_tolerant(self):
		# Candidato.ciudad sin acentos vs emails_por_ciudad con acentos
		ips = self._ips(
			sedes=[{"activa": 1, "ciudad": "Medellin", "nombre_sede": "S1", "email_notificacion": ""}],
			emails_por_ciudad=[{"ciudad": "Medellín", "email": "porciudad@x.com"}],
		)
		out = cita_service._get_sedes_for_ciudad(ips, "Medellin")
		self.assertEqual(out[0]["email"], "porciudad@x.com")

	def test_empty_emails_por_ciudad_falls_back_to_ips_email(self):
		ips = self._ips(
			sedes=[{"activa": 1, "ciudad": "Medellín", "nombre_sede": "S1", "email_notificacion": ""}],
			emails_por_ciudad=[],
			ips_email="legacy@ips.com",
		)
		out = cita_service._get_sedes_for_ciudad(ips, "Medellín")
		self.assertEqual(out[0]["email"], "legacy@ips.com")


class TestSetExamOutcomeCandidato(FrappeTestCase):
	"""set_exam_outcome debe actualizar Candidato según el resultado para
	cerrar el ciclo del candidato sin requerir intervención manual de Selección.

	Reglas:
	  - Cancelada → Candidato vuelve a STATE_DOCUMENTACION, concepto_medico vacío.
	  - Realizada + Favorable → solo Candidato.concepto_medico="Favorable"; estado_proceso no se mueve.
	  - Realizada + Desfavorable → Candidato.concepto_medico="Desfavorable",
	    estado_proceso=STATE_RECHAZADO, motivo_rechazo poblado.
	  - Realizada + Aplazado → la cita se persiste como Aplazada (no Realizada);
	    Candidato.concepto_medico="Aplazado"; estado_proceso permanece en examen.
	"""

	def _capture_set_value(self):
		calls = []

		def fake(doctype, name, fieldname_or_dict, value=None, **kwargs):
			calls.append((doctype, name, fieldname_or_dict, value))

		return calls, fake

	def _mock_cita(self, candidato="CAND-001"):
		cita = MagicMock()
		cita.candidato = candidato
		cita.name = "CEM-2026-9999"
		return cita

	def _written(self, calls, doctype, name):
		"""Aplana set_value calls en un dict de field -> value, filtrado por doctype y name."""
		out = {}
		for dt, dname, fod, val in calls:
			if dt != doctype or dname != name:
				continue
			if isinstance(fod, dict):
				out.update(fod)
			else:
				out[fod] = val
		return out

	def test_cancelada_devuelve_candidato_a_documentacion(self):
		calls, fake = self._capture_set_value()
		with patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.get_doc",
			return_value=self._mock_cita(),
		), patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.db.set_value",
			side_effect=fake,
		):
			cita_service.set_exam_outcome("CEM-2026-9999", "Cancelada", motivo="Candidato no quiere")

		cita_writes = self._written(calls, "Cita Examen Medico", "CEM-2026-9999")
		self.assertEqual(cita_writes.get("estado"), "Cancelada")
		self.assertEqual(cita_writes.get("motivo_aplazamiento"), "Candidato no quiere")

		cand_writes = self._written(calls, "Candidato", "CAND-001")
		self.assertEqual(cand_writes.get("estado_proceso"), "En documentación")
		self.assertEqual(cand_writes.get("concepto_medico"), "Pendiente")
		self.assertIn("fecha_envio_examen_medico", cand_writes)
		self.assertIsNone(cand_writes["fecha_envio_examen_medico"])

	def test_realizada_favorable_solo_actualiza_concepto_medico(self):
		"""Favorable NO debe avanzar estado_proceso — Selección decide RRLL con gate SAGRILAFT."""
		calls, fake = self._capture_set_value()
		with patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.get_doc",
			return_value=self._mock_cita(),
		), patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.db.set_value",
			side_effect=fake,
		):
			cita_service.set_exam_outcome("CEM-2026-9999", "Realizada", concepto="Favorable")

		cand_writes = self._written(calls, "Candidato", "CAND-001")
		self.assertEqual(cand_writes.get("concepto_medico"), "Favorable")
		self.assertNotIn("estado_proceso", cand_writes,
			"Favorable no debe modificar estado_proceso del candidato.")

	def test_realizada_desfavorable_rechaza_candidato(self):
		calls, fake = self._capture_set_value()
		with patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.get_doc",
			return_value=self._mock_cita(),
		), patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.db.set_value",
			side_effect=fake,
		):
			cita_service.set_exam_outcome("CEM-2026-9999", "Realizada", concepto="Desfavorable")

		cand_writes = self._written(calls, "Candidato", "CAND-001")
		self.assertEqual(cand_writes.get("concepto_medico"), "Desfavorable")
		self.assertEqual(cand_writes.get("estado_proceso"), "Rechazado")
		self.assertTrue(
			(cand_writes.get("motivo_rechazo") or "").strip(),
			"motivo_rechazo debe poblarse para Desfavorable.",
		)

	def test_realizada_aplazado_marca_cita_aplazada(self):
		"""Concepto=Aplazado mapea a estado=Aplazada (no Realizada) — la cita
		queda visible en bandeja para que GH/SST la reagende."""
		calls, fake = self._capture_set_value()
		with patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.get_doc",
			return_value=self._mock_cita(),
		), patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.db.set_value",
			side_effect=fake,
		):
			cita_service.set_exam_outcome("CEM-2026-9999", "Realizada", concepto="Aplazado", motivo="Tensión alta")

		cita_writes = self._written(calls, "Cita Examen Medico", "CEM-2026-9999")
		self.assertEqual(cita_writes.get("estado"), "Aplazada",
			"Concepto Aplazado debe persistir la cita como Aplazada para que siga en bandeja.")
		# concepto_resultado NO debe escribirse — la cita aún no se considera Realizada.
		self.assertNotIn("concepto_resultado", cita_writes)

		cand_writes = self._written(calls, "Candidato", "CAND-001")
		# Candidato no se mueve de estado_proceso.
		self.assertNotIn("estado_proceso", cand_writes)


class TestReagendarCita(FrappeTestCase):
	"""reagendar_cita crea una cita nueva ligada por cita_anterior y reproduce
	el flujo según el modo del candidato (Manual queda Pendiente, Autogestionado
	dispara link nuevo)."""

	def test_reagendar_manual_crea_cita_pendiente_con_link_anterior(self):
		"""Modo Manual → create_cita_manual con cita_anterior + sin envío de link."""
		from hubgh.hubgh.examen_medico import cita_service as svc

		cita_prev = MagicMock()
		cita_prev.candidato = "CAND-001"
		cita_prev.cargo_al_enviar = "416"
		cita_prev.name = "CEM-2026-0001"

		create_calls = {}

		def fake_create_manual(candidato_name, cargo=None, sede=None, fecha_cita=None, hora_cita=None, cita_anterior=None):
			create_calls["candidato"] = candidato_name
			create_calls["cargo"] = cargo
			create_calls["cita_anterior"] = cita_anterior
			return "CEM-2026-9999"

		with patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.get_doc",
			return_value=cita_prev,
		), patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.db.get_value",
			return_value="Manual",  # Candidato.modo_agendamiento_examen
		), patch.object(svc, "create_cita_manual", side_effect=fake_create_manual):
			new_name = svc.reagendar_cita("CEM-2026-0001")

		self.assertEqual(new_name, "CEM-2026-9999")
		self.assertEqual(create_calls.get("cita_anterior"), "CEM-2026-0001")
		self.assertEqual(create_calls.get("candidato"), "CAND-001")

	def test_reagendar_autogestionado_envia_link_nuevo(self):
		"""Modo Autogestionado → create_cita_and_send_link con cita_anterior."""
		from hubgh.hubgh.examen_medico import cita_service as svc

		cita_prev = MagicMock()
		cita_prev.candidato = "CAND-002"
		cita_prev.cargo_al_enviar = "416"
		cita_prev.name = "CEM-2026-0002"

		create_calls = {}

		def fake_create_link(candidato_name, cargo=None, fecha_limite=None, cita_anterior=None):
			create_calls["candidato"] = candidato_name
			create_calls["cita_anterior"] = cita_anterior
			return "CEM-2026-9998"

		with patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.get_doc",
			return_value=cita_prev,
		), patch(
			"hubgh.hubgh.examen_medico.cita_service.frappe.db.get_value",
			return_value="Autogestionado",
		), patch.object(svc, "create_cita_and_send_link", side_effect=fake_create_link):
			new_name = svc.reagendar_cita("CEM-2026-0002")

		self.assertEqual(new_name, "CEM-2026-9998")
		self.assertEqual(create_calls.get("cita_anterior"), "CEM-2026-0002")
		self.assertEqual(create_calls.get("candidato"), "CAND-002")
