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
