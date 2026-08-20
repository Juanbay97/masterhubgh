# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — Batch PR2, Phase 2.1: seleccion_cruce_service column contract + row builder.

Tests cover:
  2.1.1  RED  → CRUCE_COLUMNS golden 49-label order
  2.1.3  RED  → one-hot drift guards (estado_civil, nivel_educativo_siesa)
  2.1.4  RED  → build_cruce_row field resolution (Candidato-only fields, blank rules)
  2.1.5  RED  → compute_edad calendar arithmetic (leap year, birthday boundary)
  2.1.7  RED  → _has_cruce_read_access denies before any DB read
  2.1.9  RED  → talla_pantalon free-text blank-on-non-match

All tests are RED until the corresponding GREEN task lands (see tasks.md Phase 2.1).
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.seleccion_cruce_service import (
	CRUCE_COLUMNS,
	CRUCE_ROLES,
	ESTADO_CIVIL_ONEHOT,
	NIVEL_EDUCATIVO_ONEHOT,
	_has_cruce_read_access,
	_nivel_educativo_onehot,
	_normalize_match_text,
	build_cruce_row,
	compute_edad,
	validate_hr_or_selection_read_access,
)


EXPECTED_LABELS = [
	"T.D", "NOMBRE", "EDAD", "CC", "FECHA Y LUGAR DE NACIMIENTO", "DIRECCION",
	"CIUDAD Y BARRIO", "TELEFONO FIJO", "NUMERO CELULAR", "CORREO ELECTRONICO", "RH",
	"SOLTERO", "CASADO", "ULIBRE", "VIUDO", "DIVORCIADO", "EPS",
	"PRIMARIA", "BACHILLER CLASICO", "BACHILLER TECNICO", "TECNICO", "TECNOLOGO",
	"UNIVERSITARIO", "POSTGRADO",
	"AFP", "EMERGENCIA", "CELULAR", "ALERGICO",
	"XS", "S", "M", "L", "XL",
	"XS", "S", "M", "L", "XL",
	"ZAPATOS",
	"XS", "S", "M", "L", "XL",
	"CIUDAD DE EXPEDICION", "CESANTIAS", "BANCO", "NUMERO DE CUENTA", "CIUDAD",
]


class TestCruceColumnContract(FrappeTestCase):
	"""2.1.1 — golden 49-column header contract."""

	def test_column_count_is_49(self):
		self.assertEqual(len(CRUCE_COLUMNS), 49)

	def test_column_labels_match_exact_order(self):
		self.assertEqual([c.label for c in CRUCE_COLUMNS], EXPECTED_LABELS)

	def test_column_keys_are_unique_even_with_duplicate_labels(self):
		keys = [c.key for c in CRUCE_COLUMNS]
		self.assertEqual(len(keys), len(set(keys)), "ColumnSpec.key values must all be unique")


class TestEstadoCivilDriftGuard(FrappeTestCase):
	"""2.1.3 — one-hot drift guard: ESTADO_CIVIL_ONEHOT vs live Candidato.estado_civil options."""

	def test_frozen_map_covers_every_live_select_option(self):
		meta = frappe.get_meta("Candidato")
		field = next(f for f in meta.fields if f.fieldname == "estado_civil")
		options = [o for o in (field.options or "").split("\n") if o.strip()]
		mapped_normalized = {kw for kw, _ in ESTADO_CIVIL_ONEHOT}
		for option in options:
			self.assertIn(
				_normalize_match_text(option),
				mapped_normalized,
				f"Live estado_civil option '{option}' has no ESTADO_CIVIL_ONEHOT mapping — drift detected",
			)

	def test_frozen_map_has_exactly_five_buckets_in_column_order(self):
		self.assertEqual(
			[key for _, key in ESTADO_CIVIL_ONEHOT],
			[
				"estado_civil__soltero",
				"estado_civil__casado",
				"estado_civil__ulibre",
				"estado_civil__viudo",
				"estado_civil__divorciado",
			],
		)


class TestNivelEducativoDriftGuard(FrappeTestCase):
	"""2.1.3 — one-hot drift guard: NIVEL_EDUCATIVO_ONEHOT frozen 7-tuple vs live catalog."""

	def test_frozen_tuple_has_exactly_seven_buckets_in_column_order(self):
		self.assertEqual(
			[label for label, _, _ in NIVEL_EDUCATIVO_ONEHOT],
			[
				"PRIMARIA", "BACHILLER CLASICO", "BACHILLER TECNICO",
				"TECNICO", "TECNOLOGO", "UNIVERSITARIO", "POSTGRADO",
			],
		)

	def test_live_catalog_descriptions_normalize_into_a_known_bucket_or_are_documented_gaps(self):
		"""Skips gracefully when the Nivel Educativo Siesa catalog is empty on a fresh
		dev site — the seed patch `refresh_nivel_educativo_descriptions` populates it,
		but that patch may not have run yet on this bench. Documented known gaps
		(PREESCOLAR / SIN DEFINIR / OTROS) intentionally have no cruce column."""
		rows = frappe.get_all("Nivel Educativo Siesa", filters={"enabled": 1}, fields=["code", "description"])
		if not rows:
			self.skipTest(
				"Nivel Educativo Siesa catalog is empty on this site — the reference "
				"seed patch has not run here. Drift guard cannot compare against live "
				"catalog rows; the frozen 7-tuple is still asserted independently above."
			)

		# TÉCNICO LABORAL is an intentional, user-approved gap (binding decision): it is
		# NOT an explicit "bachiller técnico" designation, so it does not map to
		# BACHILLER TECNICO — pinned explicitly in TestNivelEducativoOnehotMapping below.
		known_unmapped = {"PREESCOLAR", "SIN DEFINIR", "OTROS", "TÉCNICO LABORAL"}
		unexpected = []
		for row in rows:
			normalized = _normalize_match_text(row["description"])
			matched = any(
				any(keyword in normalized for keyword in keywords)
				for _, _, keywords in NIVEL_EDUCATIVO_ONEHOT
			)
			if not matched and row["description"].strip().upper() not in known_unmapped:
				unexpected.append(row["description"])

		self.assertEqual(unexpected, [], f"Unexpected unmapped Nivel Educativo Siesa rows: {unexpected}")


class TestNivelEducativoOnehotMapping(FrappeTestCase):
	"""Pinned mapping outcomes per the user-approved bachiller rule (binding decision):

	"todo bachiller" -> BACHILLER CLASICO by default; BACHILLER TECNICO stays empty
	unless the catalog explicitly says "bachiller técnico". "TÉCNICO LABORAL" is NOT
	an explicit bachiller-técnico designation and must NOT map to BACHILLER TECNICO.
	"""

	def _mapped_key(self, description):
		with patch(
			"hubgh.hubgh.seleccion_cruce_service.resolve_catalog_display_name",
			return_value=description,
		):
			row = _nivel_educativo_onehot("ANY-CODE")
		marked = [key for key, value in row.items() if value == "X"]
		self.assertLessEqual(len(marked), 1, f"more than one column marked for '{description}': {marked}")
		return marked[0] if marked else None

	def test_bachillerato_maps_to_bachiller_clasico(self):
		self.assertEqual(self._mapped_key("BACHILLERATO"), "nivel_educativo__bachiller_clasico")

	def test_basica_secundaria_maps_to_bachiller_clasico(self):
		self.assertEqual(
			self._mapped_key("BÁSICA SECUNDARIA (6° - 9°)"), "nivel_educativo__bachiller_clasico"
		)

	def test_explicit_bachiller_tecnico_maps_to_bachiller_tecnico_column(self):
		self.assertEqual(
			self._mapped_key("BACHILLER TÉCNICO"), "nivel_educativo__bachiller_tecnico"
		)

	def test_tecnico_laboral_does_not_map_to_bachiller_tecnico(self):
		"""Pinned outcome: 'TÉCNICO LABORAL' matches none of the 7 frozen buckets
		(not an explicit bachiller-técnico designation, and not 'tecnica/tecnico
		profesional' either) — the whole nivel-educativo group stays blank."""
		mapped = self._mapped_key("TÉCNICO LABORAL")
		self.assertIsNone(mapped, "TÉCNICO LABORAL must not resolve to any nivel_educativo column")


class TestComputeEdad(FrappeTestCase):
	"""2.1.5/2.1.6 — true calendar-year arithmetic, not date_diff // 365."""

	def test_leap_year_birthday_already_occurred(self):
		self.assertEqual(compute_edad("2000-02-29", as_of="2024-03-01"), 24)

	def test_leap_year_birthday_not_yet_occurred_this_year(self):
		"""2024-02-28 is the day before Feb 29 exists that year — birthday not yet occurred."""
		self.assertEqual(compute_edad("2000-02-29", as_of="2024-02-28"), 23)

	def test_exact_birthday_counts_as_already_occurred(self):
		self.assertEqual(compute_edad("1990-06-15", as_of="2026-06-15"), 36)

	def test_day_before_birthday_not_yet_occurred(self):
		self.assertEqual(compute_edad("1990-06-15", as_of="2026-06-14"), 35)

	def test_blank_fecha_nacimiento_returns_none(self):
		self.assertIsNone(compute_edad(None))


class TestHasCruceReadAccess(FrappeTestCase):
	"""2.1.7 — security gate denies a role outside the 6-role set before any DB read."""

	def test_denies_role_outside_allowed_set_before_db_read(self):
		# `user_has_any_role` is fully mocked, so the gate never reaches a real role
		# lookup or any candidate/document data read — it denies purely on the
		# (mocked) role decision before any DB read of application data happens.
		with (
			patch("hubgh.hubgh.seleccion_cruce_service.user_has_any_role", return_value=False) as mock_role_check,
			patch("hubgh.hubgh.seleccion_cruce_service.frappe.session") as mock_session,
		):
			mock_session.user = "unrelated.role@homeburgers.com"
			with self.assertRaises(frappe.exceptions.ValidationError):
				validate_hr_or_selection_read_access()
		mock_role_check.assert_called_once()

	def test_allows_administrator_shortcut(self):
		with patch("hubgh.hubgh.seleccion_cruce_service.user_has_any_role", return_value=False):
			self.assertTrue(_has_cruce_read_access(user="Administrator"))

	def test_allows_every_role_in_cruce_roles(self):
		for role in CRUCE_ROLES:
			with patch(
				"hubgh.hubgh.seleccion_cruce_service.user_has_any_role",
				side_effect=lambda user, *roles: role in roles,
			):
				self.assertTrue(_has_cruce_read_access(user="someone@homeburgers.com"))


class TestBuildCruceRow(FrappeTestCase):
	"""2.1.4/2.1.9 — build_cruce_row field resolution and blank-cell rules."""

	def _candidato(self, **overrides):
		base = {
			"tipo_documento": "Cedula",
			"numero_documento": "123456",
			"nombres": "Ana",
			"apellidos": "",
			"primer_apellido": "Gomez",
			"segundo_apellido": "Diaz",
			"fecha_nacimiento": "1995-05-20",
			"direccion": "Calle 1 # 2-3",
			"barrio": "Centro",
			"ciudad": "BOG",
			"celular": "3000000000",
			"email": "ana@test.com",
			"telefono_fijo": "6011234567",
			"grupo_sanguineo": "O+",
			"contacto_emergencia_nombre": "Luis",
			"contacto_emergencia_telefono": "3001111111",
			"tiene_alergias": 0,
			"descripcion_alergias": "",
			"talla_camisa": "M",
			"talla_pantalon": "32",
			"numero_zapatos": "38",
			"talla_delantal": "L",
			"estado_civil": "Soltero",
			"nivel_educativo_siesa": None,
			"eps_siesa": "EPS1",
			"afp_siesa": "AFP1",
			"cesantias_siesa": "CES1",
			"banco_siesa": "BANCO1",
			"numero_cuenta_bancaria": "0001",
		}
		base.update(overrides)
		return frappe._dict(base)

	def test_row_keys_match_column_contract_exactly(self):
		row = build_cruce_row(self._candidato())
		self.assertEqual(set(row.keys()), {c.key for c in CRUCE_COLUMNS})

	def test_candidato_only_fields_populate_without_datos_contratacion(self):
		row = build_cruce_row(self._candidato())
		self.assertEqual(row["telefono_fijo"], "6011234567")
		self.assertEqual(row["rh"], "O+")
		self.assertEqual(row["emergencia"], "Luis")
		self.assertEqual(row["celular_emergencia"], "3001111111")
		self.assertEqual(row["zapatos"], "38")
		self.assertEqual(row["alergico"], "NO")

	def test_alergico_shows_description_when_present(self):
		row = build_cruce_row(self._candidato(tiene_alergias=1, descripcion_alergias="Polen"))
		self.assertEqual(row["alergico"], "Polen")

	def test_alergico_shows_si_when_flagged_without_description(self):
		row = build_cruce_row(self._candidato(tiene_alergias=1, descripcion_alergias=""))
		self.assertEqual(row["alergico"], "SI")

	def test_blank_rule_ciudad_expedicion_without_datos_contratacion(self):
		"""ciudad_expedicion_siesa lives ONLY on Datos Contratacion — no candidato fallback."""
		row = build_cruce_row(self._candidato())
		self.assertEqual(row["ciudad_expedicion"], "")

	def test_estado_civil_onehot_marks_single_column(self):
		row = build_cruce_row(self._candidato(estado_civil="Unión Libre"))
		self.assertEqual(row["estado_civil__ulibre"], "X")
		for key in ("estado_civil__soltero", "estado_civil__casado", "estado_civil__viudo", "estado_civil__divorciado"):
			self.assertEqual(row[key], "")

	def test_estado_civil_unmapped_leaves_whole_group_blank(self):
		row = build_cruce_row(self._candidato(estado_civil="Desconocido"))
		for key in (
			"estado_civil__soltero", "estado_civil__casado", "estado_civil__ulibre",
			"estado_civil__viudo", "estado_civil__divorciado",
		):
			self.assertEqual(row[key], "")

	def test_talla_pantalon_free_text_non_match_blanks_whole_group(self):
		"""2.1.9 — talla_pantalon is free-text Data; non-matching values blank the group."""
		row = build_cruce_row(self._candidato(talla_pantalon="TALLA RARA"))
		for size in ("xs", "s", "m", "l", "xl"):
			self.assertEqual(row[f"talla_pantalon__{size}"], "")

	def test_talla_pantalon_free_text_matches_normalized(self):
		row = build_cruce_row(self._candidato(talla_pantalon=" m "))
		self.assertEqual(row["talla_pantalon__m"], "X")
		for size in ("xs", "s", "l", "xl"):
			self.assertEqual(row[f"talla_pantalon__{size}"], "")

	def test_talla_camisa_select_xxl_blanks_whole_group(self):
		"""talla_camisa Select includes XXL, which has no cruce column — group stays blank."""
		row = build_cruce_row(self._candidato(talla_camisa="XXL"))
		for size in ("xs", "s", "m", "l", "xl"):
			self.assertEqual(row[f"talla_camisa__{size}"], "")
