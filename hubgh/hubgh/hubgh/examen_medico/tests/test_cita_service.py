# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for cita_service helpers.

Covers _resolve_active_ips_for_ciudad accent-tolerant lookup so that
candidates whose ciudad is stored without accents (legacy Select values)
still match IPS records whose ciudad is the accented Ciudad fixture name.
"""

from unittest.mock import patch

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
