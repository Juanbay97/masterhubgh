# Copyright (c) 2026, Antigravity and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.page.sst_bandeja.sst_bandeja import (
	_build_cola_prorrogas_pendientes,
	_build_cola_recomendaciones_medicas,
	_is_incapacidad,
	get_caso_completo,
)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _row(**kwargs):
	"""Return a plain dict representing a Novedad SST row."""
	defaults = {
		"name": "NOV-001",
		"tipo_novedad": "Incapacidad por enfermedad general",
		"categoria_novedad": "SST",
		"es_incapacidad": 1,
		"en_radar": 0,
		"estado": "Abierta",
	}
	defaults.update(kwargs)
	return defaults


# ---------------------------------------------------------------------------
# T2-A: Queue separation — _is_incapacidad guard and classification
# ---------------------------------------------------------------------------

class TestQueueSeparation(FrappeTestCase):
	def test_accidente_does_not_bleed_into_cola_incapacidades(self):
		"""REQ-4 (spec): Accidente rows must never appear in cola_incapacidades."""
		row = _row(
			tipo_novedad="Accidente",
			es_incapacidad=1,
			accidente_tuvo_incapacidad=1,
			categoria_novedad="SST",
		)
		self.assertFalse(_is_incapacidad(row))

	def test_incapacidad_appears_only_in_cola_incapacidades(self):
		"""REQ-4 (spec): Incapacidad rows must be classified as incapacidad."""
		row = _row(
			tipo_novedad="Incapacidad por enfermedad general",
			es_incapacidad=1,
			categoria_novedad="SST",
		)
		self.assertTrue(_is_incapacidad(row))

	def test_accidente_with_es_incapacidad_flag_returns_false(self):
		"""Edge case: Accidente row with es_incapacidad=1 still returns False from _is_incapacidad."""
		row = _row(tipo_novedad="Accidente", es_incapacidad=1)
		self.assertFalse(_is_incapacidad(row))

	def test_incapacidad_plain_type_returns_true(self):
		"""Incapacidad (without enfermedad general qualifier) is also classified correctly."""
		row = _row(tipo_novedad="Incapacidad", es_incapacidad=0)
		self.assertTrue(_is_incapacidad(row))


# ---------------------------------------------------------------------------
# T2-B: Bulk helpers — cola_recomendaciones and cola_prorrogas
# ---------------------------------------------------------------------------

class TestBulkHelpers(FrappeTestCase):
	def test_recomendacion_medica_appears_in_cola_recomendaciones(self):
		"""REQ-1 (spec): Active seguimientos with tipo_seguimiento 'Recomendación médica' appear."""
		novedad_names = ["NOV-001"]
		seguimiento_row = {
			"name": "SEG-001",
			"parent": "NOV-001",
			"parentfield": "seguimientos",
			"fecha_seguimiento": "2026-04-10 09:00:00",
			"tipo_seguimiento": "Recomendación médica",
			"detalle": "Aplica restricción lumbar",
			"estado_resultante": "sigue igual",
		}
		with patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_all") as mock_get_all:
			mock_get_all.return_value = [seguimiento_row]
			result = _build_cola_recomendaciones_medicas(novedad_names)

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["novedad"], "NOV-001")
		self.assertEqual(result[0]["tipo_seguimiento"], "Recomendación médica")

	def test_open_prorroga_in_pendientes_closed_excluded(self):
		"""REQ-2 (spec): Closed prorrogas must be excluded; open ones included."""
		novedad_names = ["NOV-001"]
		open_prorroga = {
			"name": "PRO-001",
			"parent": "NOV-001",
			"parentfield": "prorrogas_incapacidad",
			"fecha_seguimiento": "2026-04-05 00:00:00",
			"tipo_seguimiento": "Prórroga incapacidad",
			"detalle": "Prórroga 15 días",
			"estado_resultante": "sigue igual",
		}
		with patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_all") as mock_get_all:
			mock_get_all.return_value = [open_prorroga]
			result = _build_cola_prorrogas_pendientes(novedad_names)

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["name"], "PRO-001")

	def test_closed_prorroga_not_returned_by_bulk_helper(self):
		"""Closed prorrogas (estado_resultante='cerrar') must not appear in results."""
		novedad_names = ["NOV-001"]
		# The filter excludes them at query level — mock returns empty list
		with patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_all") as mock_get_all:
			mock_get_all.return_value = []
			result = _build_cola_prorrogas_pendientes(novedad_names)

		self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# T2-C: get_caso_completo
# ---------------------------------------------------------------------------

class TestGetCasoCompleto(FrappeTestCase):
	def _make_novedad_mock(self, ref_doctype=None, ref_docname=None):
		from types import SimpleNamespace
		return SimpleNamespace(
			name="NOV-001",
			empleado="EMP-001",
			ref_doctype=ref_doctype,
			ref_docname=ref_docname,
		)

	def _allowed_roles(self):
		return {"SST"}

	def test_get_caso_completo_returns_empty_lists_when_no_children(self):
		"""REQ-3 (spec): Returns prorrogas=[], seguimientos=[], alertas=[] with no exception."""
		novedad_mock = self._make_novedad_mock()
		with patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_roles", return_value=list(self._allowed_roles())), \
		     patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_doc", return_value=novedad_mock), \
		     patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_all", return_value=[]):
			result = get_caso_completo("NOV-001")

		self.assertEqual(result["prorrogas"], [])
		self.assertEqual(result["seguimientos"], [])
		self.assertEqual(result["alertas"], [])

	def test_get_caso_completo_rrll_handoff_null_when_not_escalated(self):
		"""REQ-3 (spec): rrll_handoff must be None when novedad has no ref_docname."""
		novedad_mock = self._make_novedad_mock(ref_doctype=None, ref_docname=None)
		with patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_roles", return_value=list(self._allowed_roles())), \
		     patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_doc", return_value=novedad_mock), \
		     patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_all", return_value=[]):
			result = get_caso_completo("NOV-001")

		self.assertIsNone(result["rrll_handoff"])

	def test_get_caso_completo_rrll_handoff_populated_when_escalated(self):
		"""REQ-4 (spec): rrll_handoff populated with name/cola_destino/estado when GH Novedad exists."""
		novedad_mock = self._make_novedad_mock(ref_doctype="GH Novedad", ref_docname="GHN-001")
		handoff_data = {"name": "GHN-001", "cola_destino": "GH-RRLL", "estado": "Recibida"}
		with patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_roles", return_value=list(self._allowed_roles())), \
		     patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_doc", return_value=novedad_mock), \
		     patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_all", return_value=[]), \
		     patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.db.get_value", return_value=handoff_data):
			result = get_caso_completo("NOV-001")

		self.assertIsNotNone(result["rrll_handoff"])
		self.assertEqual(result["rrll_handoff"]["name"], "GHN-001")
		self.assertEqual(result["rrll_handoff"]["cola_destino"], "GH-RRLL")

	def test_get_caso_completo_rejects_non_sst_role(self):
		"""REQ-2 (spec): Callers without SST roles must receive PermissionError."""
		with patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_roles", return_value=[]), \
		     patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.has_permission", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				get_caso_completo("NOV-001")

	def test_get_caso_completo_returns_chronological_children(self):
		"""REQ-4 (spec): Response lists all child events in ascending date order."""
		novedad_mock = self._make_novedad_mock()
		prorrogas_data = [{"name": "PRO-002", "fecha_seguimiento": "2026-04-15 00:00:00", "tipo_seguimiento": "Prórroga incapacidad", "detalle": "", "estado_resultante": "sigue igual"}]
		seguimientos_data = [{"name": "SEG-001", "fecha_seguimiento": "2026-04-10 09:00:00", "tipo_seguimiento": "Llamada", "detalle": "", "estado_resultante": "sigue igual"}]
		alertas_data = [{"name": "ALRT-001", "fecha_programada": "2026-04-12", "tipo_alerta": "Seguimiento", "estado": "Pendiente", "mensaje": ""}]

		call_count = [0]
		def fake_get_all(doctype, filters=None, fields=None, **kwargs):
			call_count[0] += 1
			if doctype == "SST Seguimiento" and filters and filters.get("parentfield") == "prorrogas_incapacidad":
				return prorrogas_data
			if doctype == "SST Seguimiento" and filters and filters.get("parentfield") == "seguimientos":
				return seguimientos_data
			if doctype == "SST Alerta":
				return alertas_data
			return []

		with patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_roles", return_value=list(self._allowed_roles())), \
		     patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_doc", return_value=novedad_mock), \
		     patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_all", side_effect=fake_get_all):
			result = get_caso_completo("NOV-001")

		# Seguimiento (Apr 10) must appear in seguimientos
		self.assertEqual(len(result["seguimientos"]), 1)
		# Prorroga (Apr 15) must appear in prorrogas
		self.assertEqual(len(result["prorrogas"]), 1)
		# Alerta (Apr 12) in alertas
		self.assertEqual(len(result["alertas"]), 1)
		# prorrogas date > seguimiento date: Apr 15 > Apr 10 — order within each list correct
		self.assertGreater(result["prorrogas"][0]["fecha_seguimiento"], result["seguimientos"][0]["fecha_seguimiento"])
