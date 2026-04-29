# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt
"""
test_disciplinary_bandeja.py — Phase 5 tests (T051, T054)

Tests for get_disciplinary_tray extended functionality:
  - Tray returns expected columns (afectados_summary, proxima_accion, citacion_vencida, pdv, outcome)
  - compute_proxima_accion for each caso state
  - detect_citacion_vencida with fixture
  - filters: estado (multi), outcome (multi), PDV, búsqueda libre
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestBandejaColumns(FrappeTestCase):
	"""T051 — get_disciplinary_tray returns expected columns."""

	def _make_caso(self, name="CD-001", estado="En Triage", outcome=None, empleado="EMP-001"):
		return SimpleNamespace(
			name=name,
			estado=estado,
			decision_final=outcome,
			fecha_incidente="2026-01-01",
			tipo_falta="Grave",
			fecha_cierre=None,
			resumen_cierre="",
			fecha_inicio_suspension=None,
			fecha_fin_suspension=None,
			modified="2026-04-01 10:00:00",
			empleado=empleado,
		)

	def _make_afectado(self, name="AFE-001", caso="CD-001", empleado="EMP-001", estado="En Triage", decision=None):
		return SimpleNamespace(
			name=name,
			caso=caso,
			empleado=empleado,
			estado=estado,
			decision_final_afectado=decision,
		)

	@patch("hubgh.hubgh.disciplinary_case_service.enforce_disciplinary_access")
	@patch("hubgh.hubgh.disciplinary_case_service.frappe")
	def test_tray_returns_expected_column_keys(self, mock_frappe, mock_auth):
		"""T051: tray rows include caso, estado, outcome, pdv, fecha_ultimo_movimiento,
		afectados_summary, proxima_accion, citacion_vencida."""
		from hubgh.hubgh.disciplinary_case_service import get_disciplinary_tray

		caso_row = {
			"name": "CD-001",
			"empleado": "EMP-001",
			"fecha_incidente": "2026-01-01",
			"tipo_falta": "Grave",
			"estado": "En Triage",
			"decision_final": None,
			"fecha_cierre": None,
			"resumen_cierre": "",
			"fecha_inicio_suspension": None,
			"fecha_fin_suspension": None,
			"modified": "2026-04-01 10:00:00",
		}
		afectado_row = {"name": "AFE-001", "caso": "CD-001", "empleado": "EMP-001", "estado": "En Triage", "decision_final_afectado": None}
		empleado_row = {"name": "EMP-001", "nombres": "Juan", "apellidos": "Pérez", "cedula": "123", "pdv": "PDV-001", "estado": "Activo"}

		mock_frappe.parse_json = frappe.parse_json
		mock_frappe.get_all = MagicMock(side_effect=self._make_get_all_stub([caso_row], [afectado_row], [empleado_row]))
		mock_frappe.db = MagicMock()
		mock_frappe.db.get_value = MagicMock(return_value=None)

		result = get_disciplinary_tray(filters={"limit": 50})
		self.assertIn("rows", result)
		self.assertTrue(len(result["rows"]) > 0)
		row = result["rows"][0]

		# Required columns
		self.assertIn("proxima_accion", row)
		self.assertIn("citacion_vencida", row)
		self.assertIn("afectados_summary", row)
		self.assertIn("pdv", row)
		self.assertIn("fecha_ultimo_movimiento", row)
		self.assertIn("outcome", row)

	def _make_get_all_stub(self, casos, afectados, empleados):
		def side_effect(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				return casos
			if doctype == "Afectado Disciplinario":
				return afectados
			if doctype == "Ficha Empleado":
				return empleados
			if doctype == "Citacion Disciplinaria":
				return []
			return []

		return side_effect


class TestComputeProximaAccion(FrappeTestCase):
	"""T051 — compute_proxima_accion for each state."""

	def _afectado(self, estado, nombre="Juan Pérez"):
		return {"estado": estado, "empleado": "EMP-001", "nombre": nombre, "decision_final_afectado": None}

	def _get_nombre_stub(self, emp):
		return "Juan Pérez"

	@patch("hubgh.hubgh.disciplinary_case_service._get_afectado_nombre")
	def test_compute_en_triage(self, mock_nombre):
		from hubgh.hubgh.disciplinary_case_service import compute_proxima_accion
		mock_nombre.return_value = "Juan Pérez"
		afectados = [self._afectado("En Triage")]
		result = compute_proxima_accion("En Triage", afectados, citacion_vencida=False)
		self.assertEqual(result, "Hacer triage")

	@patch("hubgh.hubgh.disciplinary_case_service._get_afectado_nombre")
	def test_compute_descargos_programados(self, mock_nombre):
		from hubgh.hubgh.disciplinary_case_service import compute_proxima_accion
		mock_nombre.return_value = "Juan Pérez"
		afectados = [self._afectado("Descargos Programados")]
		result = compute_proxima_accion("Descargos Programados", afectados, citacion_vencida=False)
		self.assertIn("Emitir citación para", result)
		self.assertIn("Juan Pérez", result)

	@patch("hubgh.hubgh.disciplinary_case_service._get_afectado_nombre")
	def test_compute_citado(self, mock_nombre):
		from hubgh.hubgh.disciplinary_case_service import compute_proxima_accion
		mock_nombre.return_value = "Juan Pérez"
		afectados = [self._afectado("Citado")]
		result = compute_proxima_accion("Citado", afectados, citacion_vencida=False)
		self.assertIn("Conducir descargos de", result)
		self.assertIn("Juan Pérez", result)

	@patch("hubgh.hubgh.disciplinary_case_service._get_afectado_nombre")
	def test_compute_en_descargos(self, mock_nombre):
		from hubgh.hubgh.disciplinary_case_service import compute_proxima_accion
		mock_nombre.return_value = "Juan Pérez"
		afectados = [self._afectado("En Descargos")]
		result = compute_proxima_accion("En Descargos", afectados, citacion_vencida=False)
		self.assertIn("Completar acta de", result)
		self.assertIn("Juan Pérez", result)

	@patch("hubgh.hubgh.disciplinary_case_service._get_afectado_nombre")
	def test_compute_en_deliberacion(self, mock_nombre):
		from hubgh.hubgh.disciplinary_case_service import compute_proxima_accion
		mock_nombre.return_value = "Juan Pérez"
		afectados = [self._afectado("En Deliberación")]
		result = compute_proxima_accion("En Deliberación", afectados, citacion_vencida=False)
		self.assertIn("Deliberar sobre", result)
		self.assertIn("Juan Pérez", result)

	def test_compute_cerrado(self):
		from hubgh.hubgh.disciplinary_case_service import compute_proxima_accion
		result = compute_proxima_accion("Cerrado", [], citacion_vencida=False)
		self.assertEqual(result, "")

	@patch("hubgh.hubgh.disciplinary_case_service._get_afectado_nombre")
	def test_compute_urgente_prefix_when_vencida(self, mock_nombre):
		from hubgh.hubgh.disciplinary_case_service import compute_proxima_accion
		mock_nombre.return_value = "Juan Pérez"
		afectados = [self._afectado("Citado")]
		result = compute_proxima_accion("Citado", afectados, citacion_vencida=True)
		self.assertIn("⚠ URGENTE:", result)


class TestDetectCitacionVencida(FrappeTestCase):
	"""T051 — detect_citacion_vencida with fixture."""

	@patch("hubgh.hubgh.disciplinary_case_service.frappe")
	def test_detect_vencida_returns_true_when_past_date_and_citado(self, mock_frappe):
		from hubgh.hubgh.disciplinary_case_service import detect_citacion_vencida
		from frappe.utils import add_days, nowdate

		# Citacion with past fecha_programada and afectado still in "Citado"
		citacion = SimpleNamespace(
			name="CIT-001",
			afectado="AFE-001",
			fecha_programada_descargos=add_days(nowdate(), -3),
			estado="Entregada",
		)
		afectado = SimpleNamespace(name="AFE-001", estado="Citado")

		mock_frappe.get_all = MagicMock(return_value=[citacion])
		mock_frappe.db = MagicMock()
		mock_frappe.db.get_value = MagicMock(return_value="Citado")
		mock_frappe.utils = frappe.utils

		result = detect_citacion_vencida("CD-001", ["AFE-001"])
		self.assertTrue(result)

	@patch("hubgh.hubgh.disciplinary_case_service.frappe")
	def test_detect_vencida_returns_false_when_no_citaciones(self, mock_frappe):
		from hubgh.hubgh.disciplinary_case_service import detect_citacion_vencida

		mock_frappe.get_all = MagicMock(return_value=[])
		mock_frappe.utils = frappe.utils

		result = detect_citacion_vencida("CD-001", [])
		self.assertFalse(result)

	@patch("hubgh.hubgh.disciplinary_case_service.frappe")
	def test_detect_vencida_returns_false_when_future_date(self, mock_frappe):
		from hubgh.hubgh.disciplinary_case_service import detect_citacion_vencida
		from frappe.utils import add_days, nowdate

		citacion = SimpleNamespace(
			name="CIT-001",
			afectado="AFE-001",
			fecha_programada_descargos=add_days(nowdate(), 5),
			estado="Entregada",
		)
		mock_frappe.get_all = MagicMock(return_value=[citacion])
		mock_frappe.db = MagicMock()
		mock_frappe.db.get_value = MagicMock(return_value="Citado")
		mock_frappe.utils = frappe.utils

		result = detect_citacion_vencida("CD-001", ["AFE-001"])
		self.assertFalse(result)


class TestBandejaFilters(FrappeTestCase):
	"""T054 — bandeja filters: estado, outcome, PDV, búsqueda libre."""

	def _caso_rows(self):
		return [
			{"name": "CD-001", "empleado": "EMP-001", "fecha_incidente": "2026-01-01", "tipo_falta": "Grave",
			 "estado": "En Triage", "decision_final": None, "fecha_cierre": None, "resumen_cierre": "",
			 "fecha_inicio_suspension": None, "fecha_fin_suspension": None, "modified": "2026-04-01 10:00:00"},
			{"name": "CD-002", "empleado": "EMP-002", "fecha_incidente": "2026-01-02", "tipo_falta": "Leve",
			 "estado": "Cerrado", "decision_final": "Archivo", "fecha_cierre": "2026-02-01", "resumen_cierre": "Archivado",
			 "fecha_inicio_suspension": None, "fecha_fin_suspension": None, "modified": "2026-04-02 10:00:00"},
		]

	def _empleado_rows(self):
		return [
			{"name": "EMP-001", "nombres": "Juan", "apellidos": "Pérez", "cedula": "111", "pdv": "PDV-A", "estado": "Activo"},
			{"name": "EMP-002", "nombres": "Ana", "apellidos": "López", "cedula": "222", "pdv": "PDV-B", "estado": "Activo"},
		]

	def _afectado_rows_for(self, caso_name):
		mapping = {
			"CD-001": [{"name": "AFE-001", "caso": "CD-001", "empleado": "EMP-001", "estado": "En Triage", "decision_final_afectado": None}],
			"CD-002": [{"name": "AFE-002", "caso": "CD-002", "empleado": "EMP-002", "estado": "Cerrado", "decision_final_afectado": "Archivo"}],
		}
		return mapping.get(caso_name, [])

	@patch("hubgh.hubgh.disciplinary_case_service.enforce_disciplinary_access")
	@patch("hubgh.hubgh.disciplinary_case_service.frappe")
	def test_filter_by_estado_single(self, mock_frappe, mock_auth):
		from hubgh.hubgh.disciplinary_case_service import get_disciplinary_tray
		mock_frappe.parse_json = frappe.parse_json
		mock_frappe.get_all = MagicMock(side_effect=self._build_get_all())
		mock_frappe.db = MagicMock()
		mock_frappe.db.get_value = MagicMock(return_value=None)

		result = get_disciplinary_tray(filters={"estado": "En Triage", "limit": 50})
		estados = [r["estado"] for r in result["rows"]]
		self.assertTrue(all(e == "En Triage" for e in estados))
		self.assertEqual(len(result["rows"]), 1)

	@patch("hubgh.hubgh.disciplinary_case_service.enforce_disciplinary_access")
	@patch("hubgh.hubgh.disciplinary_case_service.frappe")
	def test_filter_by_pdv(self, mock_frappe, mock_auth):
		from hubgh.hubgh.disciplinary_case_service import get_disciplinary_tray
		mock_frappe.parse_json = frappe.parse_json
		mock_frappe.get_all = MagicMock(side_effect=self._build_get_all())
		mock_frappe.db = MagicMock()
		mock_frappe.db.get_value = MagicMock(return_value=None)

		result = get_disciplinary_tray(filters={"pdv": "PDV-A", "limit": 50})
		pdvs = [r["pdv"] for r in result["rows"]]
		self.assertTrue(all(p == "PDV-A" for p in pdvs))
		self.assertEqual(len(result["rows"]), 1)

	@patch("hubgh.hubgh.disciplinary_case_service.enforce_disciplinary_access")
	@patch("hubgh.hubgh.disciplinary_case_service.frappe")
	def test_filter_by_outcome(self, mock_frappe, mock_auth):
		from hubgh.hubgh.disciplinary_case_service import get_disciplinary_tray
		mock_frappe.parse_json = frappe.parse_json
		mock_frappe.get_all = MagicMock(side_effect=self._build_get_all())
		mock_frappe.db = MagicMock()
		mock_frappe.db.get_value = MagicMock(return_value=None)

		result = get_disciplinary_tray(filters={"outcome": "Archivo", "limit": 50})
		self.assertEqual(len(result["rows"]), 1)
		self.assertEqual(result["rows"][0]["outcome"], "Archivo")

	@patch("hubgh.hubgh.disciplinary_case_service.enforce_disciplinary_access")
	@patch("hubgh.hubgh.disciplinary_case_service.frappe")
	def test_filter_free_search_by_name(self, mock_frappe, mock_auth):
		from hubgh.hubgh.disciplinary_case_service import get_disciplinary_tray
		mock_frappe.parse_json = frappe.parse_json
		mock_frappe.get_all = MagicMock(side_effect=self._build_get_all())
		mock_frappe.db = MagicMock()
		mock_frappe.db.get_value = MagicMock(return_value=None)

		result = get_disciplinary_tray(filters={"search": "CD-001", "limit": 50})
		self.assertEqual(len(result["rows"]), 1)
		self.assertEqual(result["rows"][0]["name"], "CD-001")

	def _build_get_all(self):
		caso_rows = self._caso_rows()
		empleado_rows = self._empleado_rows()
		all_afectados = [
			{"name": "AFE-001", "caso": "CD-001", "empleado": "EMP-001", "estado": "En Triage", "decision_final_afectado": None},
			{"name": "AFE-002", "caso": "CD-002", "empleado": "EMP-002", "estado": "Cerrado", "decision_final_afectado": "Archivo"},
		]

		def side_effect(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				return caso_rows
			if doctype == "Ficha Empleado":
				return empleado_rows
			if doctype == "Afectado Disciplinario":
				return all_afectados
			if doctype == "Citacion Disciplinaria":
				return []
			return []

		return side_effect


class TestBandejaVencidaBadge(FrappeTestCase):
	"""T051 — badge 'Vencida' appears when citacion_vencida=True."""

	@patch("hubgh.hubgh.disciplinary_case_service.enforce_disciplinary_access")
	@patch("hubgh.hubgh.disciplinary_case_service.frappe")
	def test_vencida_badge_present_in_row(self, mock_frappe, mock_auth):
		from hubgh.hubgh.disciplinary_case_service import get_disciplinary_tray
		from frappe.utils import add_days, nowdate

		caso_row = {
			"name": "CD-001", "empleado": "EMP-001", "fecha_incidente": "2026-01-01",
			"tipo_falta": "Grave", "estado": "Citado", "decision_final": None,
			"fecha_cierre": None, "resumen_cierre": "", "fecha_inicio_suspension": None,
			"fecha_fin_suspension": None, "modified": "2026-04-01 10:00:00",
		}
		afectado_row = {
			"name": "AFE-001", "caso": "CD-001", "empleado": "EMP-001",
			"estado": "Citado", "decision_final_afectado": None,
		}
		empleado_row = {"name": "EMP-001", "nombres": "Juan", "apellidos": "Pérez", "cedula": "111", "pdv": "PDV-A", "estado": "Activo"}
		citacion_row = SimpleNamespace(
			name="CIT-001",
			afectado="AFE-001",
			fecha_programada_descargos=add_days(nowdate(), -2),
			estado="Entregada",
		)

		def get_all_side(doctype, **kwargs):
			if doctype == "Caso Disciplinario":
				return [caso_row]
			if doctype == "Ficha Empleado":
				return [empleado_row]
			if doctype == "Afectado Disciplinario":
				return [afectado_row]
			if doctype == "Citacion Disciplinaria":
				return [citacion_row]
			return []

		mock_frappe.parse_json = frappe.parse_json
		mock_frappe.get_all = MagicMock(side_effect=get_all_side)
		mock_frappe.db = MagicMock()
		mock_frappe.db.get_value = MagicMock(return_value="Citado")
		mock_frappe.utils = frappe.utils

		result = get_disciplinary_tray(filters={"limit": 50})
		self.assertEqual(len(result["rows"]), 1)
		row = result["rows"][0]
		self.assertTrue(row["citacion_vencida"])
