"""Tests del enrichment del pipeline payroll.

Sin Frappe: usa un `EnrichmentContext` con resolvers en memoria. Cubre:
- Empleado no encontrado → calc_status='error'.
- Contrato no encontrado → calc_status='error'.
- Jornada no canonicalizable → calc_status='error'.
- Aplicabilidad: tipo TC-only sobre TP → 'skipped'.
- TC happy path: valor_hora_base = salario / horas_trabajadas_mes.
- TC fallback al global cuando horas_trabajadas_mes = 0.
- TP: valor_hora_base = hora_tp_fija (independiente del salario).
- compute_period_window: corte 16-15 para TC, 23-22 para TP.
"""

from __future__ import annotations

import unittest
from datetime import date

from hubgh.hubgh.payroll.adapters import NovedadCanonica
from hubgh.hubgh.payroll.enrichment import (
	ContractRecord,
	EmployeeRecord,
	EnrichmentContext,
	GlobalParams,
	compute_period_window,
	enrich,
)


def _make_ctx(
	*,
	employees: dict[str, EmployeeRecord] | None = None,
	contracts: dict[str, ContractRecord] | None = None,
	params: GlobalParams | None = None,
) -> EnrichmentContext:
	emps = employees or {}
	cons = contracts or {}

	def _resolve_employee(documento: str):
		return emps.get((documento or "").strip())

	def _resolve_contract(empleado: str, period_start: date, period_end: date):
		# Stubs: ignoran el periodo, devuelven el contrato del empleado tal cual.
		return cons.get(empleado)

	return EnrichmentContext(
		resolve_employee=_resolve_employee,
		resolve_contract=_resolve_contract,
		params=params or GlobalParams(),
	)


def _hd_novedad(documento: str = "1001", cantidad: float = 100.0) -> NovedadCanonica:
	return NovedadCanonica(
		documento_identidad=documento,
		tipo_novedad="HD",
		cantidad=cantidad,
		unidad="horas",
		raw_payload={},
	)


class EnrichmentErrorPaths(unittest.TestCase):
	def test_employee_not_found(self):
		ctx = _make_ctx()
		out = enrich(_hd_novedad("9999"), date(2026, 1, 16), date(2026, 2, 15), ctx)
		self.assertEqual(out.calc_status, "error")
		self.assertIn("Empleado no encontrado", out.calc_notes)

	def test_contract_not_found(self):
		ctx = _make_ctx(
			employees={"1001": EmployeeRecord(name="EMP-1", cedula="1001")},
		)
		out = enrich(_hd_novedad("1001"), date(2026, 1, 16), date(2026, 2, 15), ctx)
		self.assertEqual(out.calc_status, "error")
		self.assertEqual(out.empleado, "EMP-1")
		self.assertIn("Sin contrato activo", out.calc_notes)

	def test_jornada_not_canonicalizable(self):
		ctx = _make_ctx(
			employees={"1001": EmployeeRecord(name="EMP-1", cedula="1001")},
			contracts={
				"EMP-1": ContractRecord(
					name="C-1",
					empleado="EMP-1",
					tipo_jornada="Vendedor freelance",
					salario=2_000_000,
					horas_trabajadas_mes=220,
				)
			},
		)
		out = enrich(_hd_novedad("1001"), date(2026, 1, 16), date(2026, 2, 15), ctx)
		self.assertEqual(out.calc_status, "error")
		self.assertIn("no canonicaliza", out.calc_notes)


class EnrichmentApplicability(unittest.TestCase):
	def test_tc_happy_path_uses_contract_divisor(self):
		ctx = _make_ctx(
			employees={"1001": EmployeeRecord(name="EMP-1", cedula="1001")},
			contracts={
				"EMP-1": ContractRecord(
					name="C-1",
					empleado="EMP-1",
					tipo_jornada="Tiempo Completo",
					salario=1_400_000,
					horas_trabajadas_mes=220,  # ley 2101: jornada reducida
				)
			},
		)
		out = enrich(_hd_novedad("1001"), date(2026, 1, 16), date(2026, 2, 15), ctx)
		self.assertEqual(out.calc_status, "pending")
		self.assertEqual(out.tipo_jornada_snapshot, "Tiempo Completo")
		self.assertEqual(out.empleado, "EMP-1")
		self.assertEqual(out.contrato, "C-1")
		expected = 1_400_000 / 220
		self.assertAlmostEqual(out.valor_hora_base, expected, places=2)

	def test_tc_falls_back_to_global_when_contract_lacks_horas(self):
		ctx = _make_ctx(
			employees={"1002": EmployeeRecord(name="EMP-2", cedula="1002")},
			contracts={
				"EMP-2": ContractRecord(
					name="C-2",
					empleado="EMP-2",
					tipo_jornada="Tiempo Completo",
					salario=2_400_000,
					horas_trabajadas_mes=0,  # contrato viejo sin el campo
				)
			},
			params=GlobalParams(divisor_hora_tc=240),
		)
		out = enrich(_hd_novedad("1002"), date(2026, 1, 16), date(2026, 2, 15), ctx)
		self.assertEqual(out.calc_status, "pending")
		self.assertEqual(out.valor_hora_base, 2_400_000 / 240)

	def test_tp_uses_global_fixed_value(self):
		ctx = _make_ctx(
			employees={"1003": EmployeeRecord(name="EMP-3", cedula="1003")},
			contracts={
				"EMP-3": ContractRecord(
					name="C-3",
					empleado="EMP-3",
					tipo_jornada="Tiempo Parcial",
					salario=1_000_000,
					horas_trabajadas_mes=160,  # se ignora para TP
				)
			},
			params=GlobalParams(hora_tp_fija=9530),
		)
		out = enrich(_hd_novedad("1003"), date(2026, 1, 23), date(2026, 2, 22), ctx)
		self.assertEqual(out.calc_status, "pending")
		self.assertEqual(out.tipo_jornada_snapshot, "Tiempo Parcial")
		self.assertEqual(out.valor_hora_base, 9530)

	def test_aprendizaje_normalizes_to_tc_for_calc(self):
		# El usuario decidió que Aprendizaje paga como TC en v1.
		ctx = _make_ctx(
			employees={"1004": EmployeeRecord(name="EMP-4", cedula="1004")},
			contracts={
				"EMP-4": ContractRecord(
					name="C-4",
					empleado="EMP-4",
					tipo_jornada="Aprendizaje",
					salario=1_300_000,
					horas_trabajadas_mes=220,
				)
			},
		)
		out = enrich(_hd_novedad("1004"), date(2026, 1, 16), date(2026, 2, 15), ctx)
		self.assertEqual(out.calc_status, "pending")
		self.assertEqual(out.tipo_jornada_snapshot, "Tiempo Completo")


class PeriodWindow(unittest.TestCase):
	def test_tc_window_for_february_2026(self):
		start, end = compute_period_window(2026, 2, "Tiempo Completo")
		self.assertEqual(start, date(2026, 1, 16))
		self.assertEqual(end, date(2026, 2, 15))

	def test_tp_window_for_february_2026(self):
		start, end = compute_period_window(2026, 2, "Tiempo Parcial")
		self.assertEqual(start, date(2026, 1, 23))
		self.assertEqual(end, date(2026, 2, 22))

	def test_january_wraps_to_previous_year(self):
		start, end = compute_period_window(2026, 1, "Tiempo Completo")
		self.assertEqual(start, date(2025, 12, 16))
		self.assertEqual(end, date(2026, 1, 15))


if __name__ == "__main__":
	unittest.main()
