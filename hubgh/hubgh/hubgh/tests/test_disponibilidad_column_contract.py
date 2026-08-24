# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — hubgh-disponibilidad-bandeja-v1, Slice 1 (Phase 1): column contract,
day mapping, hour formatting, pure row builder. No DB writes; no endpoints.

Tests cover:
  1.1  RED  -> DISPONIBILIDAD_COLUMNS golden 13-label order
  1.2  RED  -> day drift guard (live Candidato Disponibilidad.dia Select options)
  1.3  RED  -> _format_hora accepts timedelta/time/str, blanks None/garbage
  1.4  RED  -> build_disponibilidad_row: single/double range, zero rows, key set, accented days

All tests are RED until the corresponding GREEN task (1.5) lands.
"""

import datetime

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.disponibilidad_service import (
	_DAY_LOOKUP,
	DAY_COLUMNS,
	DISPONIBILIDAD_COLUMNS,
	_build_dias_resumen,
	_format_hora,
	_normalize_day,
	build_disponibilidad_row,
)

EXPECTED_LABELS = [
	"NOMBRE", "CÉDULA", "PUNTO DE VENTA", "VINCULACIÓN", "ESTADO", "FECHA DE INGRESO",
	"LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO",
]

EXPECTED_DAY_KEYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
EXPECTED_DAY_LABELS = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
EXPECTED_DAY_DIA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


class TestDisponibilidadColumnContract(FrappeTestCase):
	"""1.1 — golden 13-column header contract."""

	def test_column_count_is_13(self):
		self.assertEqual(len(DISPONIBILIDAD_COLUMNS), 13)

	def test_column_labels_match_exact_order(self):
		self.assertEqual([c.label for c in DISPONIBILIDAD_COLUMNS], EXPECTED_LABELS)

	def test_column_keys_are_unique(self):
		keys = [c.key for c in DISPONIBILIDAD_COLUMNS]
		self.assertEqual(len(keys), len(set(keys)), "ColumnSpec.key values must all be unique")

	def test_day_columns_frozen_seven_tuple_in_order(self):
		self.assertEqual(len(DAY_COLUMNS), 7)
		self.assertEqual([d.key for d in DAY_COLUMNS], EXPECTED_DAY_KEYS)
		self.assertEqual([d.label for d in DAY_COLUMNS], EXPECTED_DAY_LABELS)
		self.assertEqual([d.dia for d in DAY_COLUMNS], EXPECTED_DAY_DIA)


class TestDayDriftGuard(FrappeTestCase):
	"""1.2 — every live Candidato Disponibilidad.dia Select option maps to exactly
	one of the 7 frozen keys (AC-7), including defensively-checked accented/
	unaccented spellings."""

	def test_live_dia_options_map_to_exactly_one_frozen_key(self):
		meta = frappe.get_meta("Candidato Disponibilidad")
		field = next(f for f in meta.fields if f.fieldname == "dia")
		options = [o for o in (field.options or "").split("\n") if o.strip()]
		self.assertTrue(options, "Candidato Disponibilidad.dia has no live Select options")
		for option in options:
			key = _DAY_LOOKUP.get(_normalize_day(option))
			self.assertIsNotNone(key, f"Live dia option '{option}' has no DAY_COLUMNS mapping — drift detected")
			self.assertIn(key, EXPECTED_DAY_KEYS)

	def test_accented_and_unaccented_spellings_both_resolve(self):
		self.assertEqual(_DAY_LOOKUP[_normalize_day("Miércoles")], "miercoles")
		self.assertEqual(_DAY_LOOKUP[_normalize_day("Miercoles")], "miercoles")
		self.assertEqual(_DAY_LOOKUP[_normalize_day("Sábado")], "sabado")
		self.assertEqual(_DAY_LOOKUP[_normalize_day("Sabado")], "sabado")


class TestFormatHora(FrappeTestCase):
	"""1.3 — _format_hora accepts timedelta (the real frappe.get_all return type,
	confirmed live), datetime.time, and str; blanks None/garbage (AC-4)."""

	def test_timedelta_whole_hour(self):
		self.assertEqual(_format_hora(datetime.timedelta(hours=8)), "08:00")

	def test_timedelta_with_minutes(self):
		self.assertEqual(_format_hora(datetime.timedelta(hours=17, minutes=30)), "17:30")

	def test_timedelta_negative_is_blank(self):
		self.assertEqual(_format_hora(datetime.timedelta(hours=-1)), "")

	def test_datetime_time_object(self):
		self.assertEqual(_format_hora(datetime.time(8, 0)), "08:00")
		self.assertEqual(_format_hora(datetime.time(17, 30)), "17:30")

	def test_string_hh_mm_ss(self):
		self.assertEqual(_format_hora("08:00:00"), "08:00")
		self.assertEqual(_format_hora("17:30:00"), "17:30")

	def test_none_is_blank(self):
		self.assertEqual(_format_hora(None), "")

	def test_garbage_string_is_blank(self):
		self.assertEqual(_format_hora("not-a-time"), "")
		self.assertEqual(_format_hora(""), "")


class TestBuildDisponibilidadRow(FrappeTestCase):
	"""1.4 — pure row builder: person dict + availability rows -> dict keyed by
	ColumnSpec.key. Person fields are assumed already-resolved by the caller
	(readers land in slice 2); this slice only formats/joins day availability."""

	def _person(self, **overrides):
		base = {
			"nombre": "Ana Gomez",
			"cedula": "1001",
			"punto_de_venta": "PDV 07",
			"vinculacion": "Contratado",
			"estado": "Activo",
			"fecha_ingreso": "2026-03-10",
		}
		base.update(overrides)
		return base

	def test_row_keys_match_column_contract_exactly(self):
		row = build_disponibilidad_row(self._person(), [])
		self.assertEqual(set(row.keys()), {c.key for c in DISPONIBILIDAD_COLUMNS})

	def test_non_day_fields_pass_through(self):
		row = build_disponibilidad_row(self._person(), [])
		self.assertEqual(row["nombre"], "Ana Gomez")
		self.assertEqual(row["cedula"], "1001")
		self.assertEqual(row["punto_de_venta"], "PDV 07")
		self.assertEqual(row["vinculacion"], "Contratado")
		self.assertEqual(row["estado"], "Activo")
		self.assertEqual(row["fecha_ingreso"], "2026-03-10")

	def test_single_range_formats_hh_mm_dash_hh_mm(self):
		rows = [{"dia": "Lunes", "hora_inicio": datetime.timedelta(hours=8),
				"hora_fin": datetime.timedelta(hours=17), "idx": 1}]
		row = build_disponibilidad_row(self._person(), rows)
		self.assertEqual(row["lunes"], "08:00 - 17:00")

	def test_single_range_works_with_time_and_string_forms_too(self):
		rows_time = [{"dia": "Lunes", "hora_inicio": datetime.time(8, 0),
					"hora_fin": datetime.time(17, 0), "idx": 1}]
		self.assertEqual(build_disponibilidad_row(self._person(), rows_time)["lunes"], "08:00 - 17:00")

		rows_str = [{"dia": "Lunes", "hora_inicio": "08:00:00", "hora_fin": "17:00:00", "idx": 1}]
		self.assertEqual(build_disponibilidad_row(self._person(), rows_str)["lunes"], "08:00 - 17:00")

	def test_two_ranges_same_day_joined_by_slash_in_idx_order(self):
		rows = [
			{"dia": "Lunes", "hora_inicio": datetime.timedelta(hours=6),
				"hora_fin": datetime.timedelta(hours=10), "idx": 1},
			{"dia": "Lunes", "hora_inicio": datetime.timedelta(hours=18),
				"hora_fin": datetime.timedelta(hours=22), "idx": 2},
		]
		row = build_disponibilidad_row(self._person(), rows)
		self.assertEqual(row["lunes"], "06:00 - 10:00 / 18:00 - 22:00")

	def test_two_ranges_same_day_join_order_follows_idx_even_if_input_reversed(self):
		rows = [
			{"dia": "Lunes", "hora_inicio": datetime.timedelta(hours=18),
				"hora_fin": datetime.timedelta(hours=22), "idx": 2},
			{"dia": "Lunes", "hora_inicio": datetime.timedelta(hours=6),
				"hora_fin": datetime.timedelta(hours=10), "idx": 1},
		]
		row = build_disponibilidad_row(self._person(), rows)
		self.assertEqual(row["lunes"], "06:00 - 10:00 / 18:00 - 22:00")

	def test_zero_rows_all_days_blank_never_no_disponible(self):
		row = build_disponibilidad_row(self._person(), [])
		for spec in DAY_COLUMNS:
			self.assertEqual(row[spec.key], "")
		self.assertNotIn("No disponible", row.values())

	def test_accented_day_value_lands_in_correct_column(self):
		rows = [
			{"dia": "Miércoles", "hora_inicio": datetime.timedelta(hours=8),
				"hora_fin": datetime.timedelta(hours=17), "idx": 1},
			{"dia": "Sábado", "hora_inicio": datetime.timedelta(hours=9),
				"hora_fin": datetime.timedelta(hours=13), "idx": 1},
		]
		row = build_disponibilidad_row(self._person(), rows)
		self.assertEqual(row["miercoles"], "08:00 - 17:00")
		self.assertEqual(row["sabado"], "09:00 - 13:00")

	def test_unaccented_day_value_still_resolves(self):
		rows = [{"dia": "Miercoles", "hora_inicio": datetime.timedelta(hours=8),
				"hora_fin": datetime.timedelta(hours=17), "idx": 1}]
		row = build_disponibilidad_row(self._person(), rows)
		self.assertEqual(row["miercoles"], "08:00 - 17:00")


class TestDiasResumen(FrappeTestCase):
	"""2.7/ADR-7/AC-14 — compact tray summary, derived strictly from the same
	`build_disponibilidad_row()` output dict (anti-drift rule): never a second
	traversal of the raw child rows. Full ranges stay Excel-only."""

	def _person(self, **overrides):
		base = {
			"nombre": "Ana Gomez", "cedula": "1001", "punto_de_venta": "PDV 07",
			"vinculacion": "Contratado", "estado": "Activo", "fecha_ingreso": "2026-03-10",
		}
		base.update(overrides)
		return base

	def test_zero_availability_is_empty_string_never_no_disponible(self):
		row = build_disponibilidad_row(self._person(), [])
		self.assertEqual(_build_dias_resumen(row), "")

	def test_five_of_seven_days_reports_initials_and_count(self):
		"""AC-14: available Monday, Thursday, Friday, Saturday, Sunday -> 5/7."""
		disp = [
			{"dia": d, "hora_inicio": datetime.timedelta(hours=8), "hora_fin": datetime.timedelta(hours=17), "idx": 1}
			for d in ("Lunes", "Jueves", "Viernes", "Sábado", "Domingo")
		]
		row = build_disponibilidad_row(self._person(), disp)
		self.assertEqual(_build_dias_resumen(row), "L J V S D · 5/7")

	def test_initials_correspond_one_to_one_to_non_blank_day_keys(self):
		disp = [
			{"dia": "Martes", "hora_inicio": datetime.timedelta(hours=8), "hora_fin": datetime.timedelta(hours=17), "idx": 1},
			{"dia": "Miércoles", "hora_inicio": datetime.timedelta(hours=8), "hora_fin": datetime.timedelta(hours=17), "idx": 1},
		]
		row = build_disponibilidad_row(self._person(), disp)
		non_blank_keys = {spec.key for spec in DAY_COLUMNS if row[spec.key]}
		self.assertEqual(non_blank_keys, {"martes", "miercoles"})
		self.assertEqual(_build_dias_resumen(row), "M X · 2/7")

	def test_all_seven_days_available(self):
		disp = [
			{"dia": d.dia, "hora_inicio": datetime.timedelta(hours=8), "hora_fin": datetime.timedelta(hours=17), "idx": 1}
			for d in DAY_COLUMNS
		]
		row = build_disponibilidad_row(self._person(), disp)
		self.assertEqual(_build_dias_resumen(row), "L M X J V S D · 7/7")
