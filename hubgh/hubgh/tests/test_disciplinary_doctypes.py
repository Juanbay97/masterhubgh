# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt
"""
T005, T007, T009, T011, T013 — Tests de los DocTypes disciplinarios Phase 1.
Cubre: Articulo RIT Caso (child), Disciplinary Transition Log (child),
Caso Disciplinario (refactor), Afectado Disciplinario, Evidencia Disciplinaria.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


# =============================================================================
# T005 — Articulo RIT Caso (Child Table)
# =============================================================================

class TestArticuloRitCaso(FrappeTestCase):
	"""T005 — Tests del DocType Child Table Articulo RIT Caso."""

	def test_articulo_rit_caso_doctype_exists(self):
		"""El DocType Articulo RIT Caso debe existir."""
		meta = frappe.get_meta("Articulo RIT Caso")
		self.assertIsNotNone(meta)
		self.assertEqual(meta.name, "Articulo RIT Caso")

	def test_articulo_rit_caso_is_child_table(self):
		"""Articulo RIT Caso debe ser istable=1 (Child Table)."""
		meta = frappe.get_meta("Articulo RIT Caso")
		self.assertEqual(int(meta.istable or 0), 1, "Articulo RIT Caso debe ser istable=1")

	def test_articulo_rit_caso_has_required_fields(self):
		"""Debe tener los campos: articulo, literales_aplicables."""
		meta = frappe.get_meta("Articulo RIT Caso")
		fieldnames = {f.fieldname for f in meta.fields}
		required = {"articulo", "literales_aplicables"}
		self.assertTrue(
			required.issubset(fieldnames),
			f"Faltan campos en Articulo RIT Caso: {required - fieldnames}",
		)

	def test_articulo_rit_caso_articulo_links_to_rit_articulo(self):
		"""El campo articulo debe ser Link a RIT Articulo."""
		meta = frappe.get_meta("Articulo RIT Caso")
		field = next((f for f in meta.fields if f.fieldname == "articulo"), None)
		self.assertIsNotNone(field, "Campo 'articulo' no encontrado")
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "RIT Articulo")

	def test_articulo_rit_caso_articulo_is_required(self):
		"""El campo articulo debe ser obligatorio."""
		meta = frappe.get_meta("Articulo RIT Caso")
		field = next((f for f in meta.fields if f.fieldname == "articulo"), None)
		self.assertIsNotNone(field, "Campo 'articulo' no encontrado")
		self.assertEqual(int(field.reqd or 0), 1, "El campo 'articulo' debe ser reqd=1")

	def test_articulo_rit_caso_literales_is_optional(self):
		"""El campo literales_aplicables debe ser opcional."""
		meta = frappe.get_meta("Articulo RIT Caso")
		field = next((f for f in meta.fields if f.fieldname == "literales_aplicables"), None)
		self.assertIsNotNone(field, "Campo 'literales_aplicables' no encontrado")
		self.assertEqual(int(field.reqd or 0), 0, "El campo 'literales_aplicables' debe ser opcional")


# =============================================================================
# T007 — Disciplinary Transition Log (Child Table)
# =============================================================================

class TestDisciplinaryTransitionLog(FrappeTestCase):
	"""T007 — Tests del DocType Child Table Disciplinary Transition Log."""

	def test_disciplinary_transition_log_doctype_exists(self):
		"""El DocType Disciplinary Transition Log debe existir."""
		meta = frappe.get_meta("Disciplinary Transition Log")
		self.assertIsNotNone(meta)
		self.assertEqual(meta.name, "Disciplinary Transition Log")

	def test_disciplinary_transition_log_is_child_table(self):
		"""Disciplinary Transition Log debe ser istable=1."""
		meta = frappe.get_meta("Disciplinary Transition Log")
		self.assertEqual(int(meta.istable or 0), 1)

	def test_disciplinary_transition_log_has_required_fields(self):
		"""Debe tener: transition_name, from_state, to_state, actor, timestamp, comment."""
		meta = frappe.get_meta("Disciplinary Transition Log")
		fieldnames = {f.fieldname for f in meta.fields}
		required = {"transition_name", "from_state", "to_state", "actor", "timestamp", "comment"}
		self.assertTrue(
			required.issubset(fieldnames),
			f"Faltan campos en Disciplinary Transition Log: {required - fieldnames}",
		)

	def test_transition_log_transition_name_is_required(self):
		"""El campo transition_name debe ser obligatorio."""
		meta = frappe.get_meta("Disciplinary Transition Log")
		field = next((f for f in meta.fields if f.fieldname == "transition_name"), None)
		self.assertIsNotNone(field)
		self.assertEqual(int(field.reqd or 0), 1)

	def test_transition_log_to_state_is_required(self):
		"""El campo to_state debe ser obligatorio."""
		meta = frappe.get_meta("Disciplinary Transition Log")
		field = next((f for f in meta.fields if f.fieldname == "to_state"), None)
		self.assertIsNotNone(field)
		self.assertEqual(int(field.reqd or 0), 1)

	def test_transition_log_actor_links_to_user(self):
		"""El campo actor debe ser Link a User."""
		meta = frappe.get_meta("Disciplinary Transition Log")
		field = next((f for f in meta.fields if f.fieldname == "actor"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "User")

	def test_transition_log_timestamp_is_required(self):
		"""El campo timestamp debe ser obligatorio."""
		meta = frappe.get_meta("Disciplinary Transition Log")
		field = next((f for f in meta.fields if f.fieldname == "timestamp"), None)
		self.assertIsNotNone(field)
		self.assertEqual(int(field.reqd or 0), 1)


# =============================================================================
# T009 — Caso Disciplinario (refactor — campos nuevos)
# =============================================================================

class TestCasoDisciplinarioRefactor(FrappeTestCase):
	"""T009 — Tests del refactor de Caso Disciplinario: campos nuevos y estado extendido."""

	def test_caso_disciplinario_has_new_fields(self):
		"""Caso Disciplinario debe tener los campos nuevos del refactor."""
		meta = frappe.get_meta("Caso Disciplinario")
		fieldnames = {f.fieldname for f in meta.fields}
		new_fields = {"origen", "solicitante", "hechos_detallados", "ciudad_emision", "empresa"}
		self.assertTrue(
			new_fields.issubset(fieldnames),
			f"Faltan campos nuevos en Caso Disciplinario: {new_fields - fieldnames}",
		)

	def test_caso_disciplinario_has_articulos_rit_table(self):
		"""Caso Disciplinario debe tener child table articulos_rit."""
		meta = frappe.get_meta("Caso Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "articulos_rit"), None)
		self.assertIsNotNone(field, "Campo 'articulos_rit' no encontrado en Caso Disciplinario")
		self.assertEqual(field.fieldtype, "Table")
		self.assertEqual(field.options, "Articulo RIT Caso")

	def test_caso_disciplinario_has_transition_log(self):
		"""Caso Disciplinario debe tener child table transition_log."""
		meta = frappe.get_meta("Caso Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "transition_log"), None)
		self.assertIsNotNone(field, "Campo 'transition_log' no encontrado en Caso Disciplinario")
		self.assertEqual(field.fieldtype, "Table")
		self.assertEqual(field.options, "Disciplinary Transition Log")

	def test_caso_disciplinario_estado_extendido_has_en_triage(self):
		"""Estado debe incluir 'En Triage'."""
		meta = frappe.get_meta("Caso Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "estado"), None)
		self.assertIsNotNone(field)
		opciones = (field.options or "").split("\n")
		self.assertIn("En Triage", opciones, "Estado debe incluir 'En Triage'")

	def test_caso_disciplinario_estado_extendido_has_descargos_programados(self):
		"""Estado debe incluir 'Descargos Programados'."""
		meta = frappe.get_meta("Caso Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "estado"), None)
		self.assertIsNotNone(field)
		opciones = (field.options or "").split("\n")
		self.assertIn("Descargos Programados", opciones)

	def test_caso_disciplinario_estado_extendido_has_citado(self):
		"""Estado debe incluir 'Citado'."""
		meta = frappe.get_meta("Caso Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "estado"), None)
		opciones = (field.options or "").split("\n")
		self.assertIn("Citado", opciones)

	def test_caso_disciplinario_estado_extendido_has_en_descargos(self):
		"""Estado debe incluir 'En Descargos'."""
		meta = frappe.get_meta("Caso Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "estado"), None)
		opciones = (field.options or "").split("\n")
		self.assertIn("En Descargos", opciones)

	def test_caso_disciplinario_estado_extendido_has_en_deliberacion(self):
		"""Estado debe incluir 'En Deliberación'."""
		meta = frappe.get_meta("Caso Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "estado"), None)
		opciones = (field.options or "").split("\n")
		self.assertIn("En Deliberación", opciones)

	def test_caso_disciplinario_estado_default_is_en_triage(self):
		"""El default del estado debe ser 'En Triage'."""
		meta = frappe.get_meta("Caso Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "estado"), None)
		self.assertIsNotNone(field)
		self.assertEqual((field.default or "").strip(), "En Triage")

	def test_caso_disciplinario_preserves_existing_fields(self):
		"""Los campos existentes deben preservarse: empleado, fecha_incidente, tipo_falta, etc."""
		meta = frappe.get_meta("Caso Disciplinario")
		fieldnames = {f.fieldname for f in meta.fields}
		existing = {"empleado", "fecha_incidente", "tipo_falta", "descripcion", "decision_final", "fecha_cierre"}
		self.assertTrue(
			existing.issubset(fieldnames),
			f"Campos existentes eliminados del Caso Disciplinario: {existing - fieldnames}",
		)


# =============================================================================
# T011 — Afectado Disciplinario
# =============================================================================

class TestAfectadoDisciplinario(FrappeTestCase):
	"""T011 — Tests del DocType Afectado Disciplinario: validaciones, lifecycle hook stub."""

	def test_afectado_disciplinario_doctype_exists(self):
		"""El DocType Afectado Disciplinario debe existir."""
		meta = frappe.get_meta("Afectado Disciplinario")
		self.assertIsNotNone(meta)
		self.assertEqual(meta.name, "Afectado Disciplinario")

	def test_afectado_disciplinario_has_required_fields(self):
		"""Debe tener los campos del design §1.2."""
		meta = frappe.get_meta("Afectado Disciplinario")
		fieldnames = {f.fieldname for f in meta.fields}
		required = {
			"caso", "empleado", "estado", "decision_final_afectado",
			"fecha_cierre_afectado", "resumen_cierre_afectado",
			"fecha_inicio_suspension", "fecha_fin_suspension",
		}
		self.assertTrue(
			required.issubset(fieldnames),
			f"Faltan campos en Afectado Disciplinario: {required - fieldnames}",
		)

	def test_afectado_disciplinario_has_transition_log(self):
		"""Afectado Disciplinario debe tener child table transition_log."""
		meta = frappe.get_meta("Afectado Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "transition_log"), None)
		self.assertIsNotNone(field, "Campo 'transition_log' no encontrado en Afectado Disciplinario")
		self.assertEqual(field.fieldtype, "Table")
		self.assertEqual(field.options, "Disciplinary Transition Log")

	def test_afectado_disciplinario_caso_links_to_caso_disciplinario(self):
		"""El campo caso debe ser Link a Caso Disciplinario."""
		meta = frappe.get_meta("Afectado Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "caso"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Caso Disciplinario")
		self.assertEqual(int(field.reqd or 0), 1)

	def test_afectado_disciplinario_empleado_links_to_ficha_empleado(self):
		"""El campo empleado debe ser Link a Ficha Empleado."""
		meta = frappe.get_meta("Afectado Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "empleado"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Ficha Empleado")
		self.assertEqual(int(field.reqd or 0), 1)

	def test_afectado_disciplinario_estado_has_correct_options(self):
		"""Estado debe tener: Pendiente Triage, Citado, En Descargos, En Deliberación, Cerrado."""
		meta = frappe.get_meta("Afectado Disciplinario")
		field = next((f for f in meta.fields if f.fieldname == "estado"), None)
		self.assertIsNotNone(field)
		opciones = set((field.options or "").split("\n"))
		expected = {"Pendiente Triage", "Citado", "En Descargos", "En Deliberación", "Cerrado"}
		self.assertTrue(
			expected.issubset(opciones),
			f"Faltan estados en Afectado Disciplinario: {expected - opciones}",
		)

	def test_afectado_disciplinario_naming_series(self):
		"""El autoname debe seguir el patrón AFE-.YYYY.-.####."""
		meta = frappe.get_meta("Afectado Disciplinario")
		self.assertIn("AFE-", meta.autoname or "")

	def test_afectado_disciplinario_suspension_validation(self):
		"""Debe validar que fecha_fin >= fecha_inicio en suspensión."""
		from hubgh.hubgh.doctype.afectado_disciplinario.afectado_disciplinario import (
			AfectadoDisciplinario,
		)
		from types import SimpleNamespace

		doc = SimpleNamespace(
			name="AFE-TEST-001",
			caso="DIS-TEST-001",
			empleado="EMP-001",
			estado="Cerrado",
			decision_final_afectado="Suspensión",
			fecha_cierre_afectado="2026-04-23",
			resumen_cierre_afectado="Resumen de prueba",
			fecha_inicio_suspension="2026-04-25",
			fecha_fin_suspension="2026-04-23",  # fin < inicio → debe fallar
		)

		with self.assertRaises(frappe.ValidationError):
			AfectadoDisciplinario._validate_suspension_dates(doc)

	def test_afectado_disciplinario_closure_requires_decision(self):
		"""Al cerrar, decision_final_afectado es obligatorio."""
		from hubgh.hubgh.doctype.afectado_disciplinario.afectado_disciplinario import (
			AfectadoDisciplinario,
		)
		from types import SimpleNamespace

		doc = SimpleNamespace(
			name="AFE-TEST-002",
			estado="Cerrado",
			decision_final_afectado=None,  # falta
			fecha_cierre_afectado=None,
			resumen_cierre_afectado=None,
			fecha_inicio_suspension=None,
			fecha_fin_suspension=None,
		)

		with self.assertRaises(frappe.ValidationError):
			AfectadoDisciplinario._validate_closure_requirements(doc)

	def test_afectado_no_se_duplica_en_caso(self):
		"""Un empleado no puede estar dos veces en el mismo caso."""
		from hubgh.hubgh.doctype.afectado_disciplinario.afectado_disciplinario import (
			AfectadoDisciplinario,
		)
		from types import SimpleNamespace
		from unittest.mock import patch

		doc = SimpleNamespace(
			name="AFE-NEW-001",
			caso="DIS-TEST-DUP",
			empleado="EMP-DUP-001",
		)

		# Simular que ya existe un registro con el mismo caso + empleado
		with patch("frappe.db.exists", return_value="AFE-EXISTING-001"):
			with self.assertRaises(frappe.ValidationError):
				AfectadoDisciplinario._validate_unique_empleado_per_caso(doc)

	def test_afectado_se_puede_agregar_diferente_empleado_mismo_caso(self):
		"""Agregar un empleado distinto al mismo caso no debe fallar."""
		from hubgh.hubgh.doctype.afectado_disciplinario.afectado_disciplinario import (
			AfectadoDisciplinario,
		)
		from types import SimpleNamespace
		from unittest.mock import patch

		doc = SimpleNamespace(
			name="AFE-NEW-002",
			caso="DIS-TEST-DUP",
			empleado="EMP-DIFERENTE-002",
		)

		# Simular que NO existe un registro previo con este empleado en el caso
		with patch("frappe.db.exists", return_value=None):
			# No debe lanzar excepción
			AfectadoDisciplinario._validate_unique_empleado_per_caso(doc)


# =============================================================================
# T013 — Evidencia Disciplinaria
# =============================================================================

class TestEvidenciaDisciplinaria(FrappeTestCase):
	"""T013 — Tests del DocType Evidencia Disciplinaria: validaciones y campos."""

	def test_evidencia_disciplinaria_doctype_exists(self):
		"""El DocType Evidencia Disciplinaria debe existir."""
		meta = frappe.get_meta("Evidencia Disciplinaria")
		self.assertIsNotNone(meta)
		self.assertEqual(meta.name, "Evidencia Disciplinaria")

	def test_evidencia_disciplinaria_has_required_fields(self):
		"""Debe tener los campos del design §1.8."""
		meta = frappe.get_meta("Evidencia Disciplinaria")
		fieldnames = {f.fieldname for f in meta.fields}
		required = {
			"caso", "afectado", "tipo_documento", "archivo",
			"cargado_por", "fecha_carga", "descripcion",
		}
		self.assertTrue(
			required.issubset(fieldnames),
			f"Faltan campos en Evidencia Disciplinaria: {required - fieldnames}",
		)

	def test_evidencia_disciplinaria_tipo_documento_has_6_options(self):
		"""tipo_documento debe tener exactamente 6 opciones."""
		meta = frappe.get_meta("Evidencia Disciplinaria")
		field = next((f for f in meta.fields if f.fieldname == "tipo_documento"), None)
		self.assertIsNotNone(field)
		opciones = [o for o in (field.options or "").split("\n") if o.strip()]
		self.assertEqual(len(opciones), 6, f"Debe tener 6 opciones, tiene {len(opciones)}: {opciones}")

	def test_evidencia_disciplinaria_naming_series(self):
		"""El autoname debe seguir el patrón EVD-.YYYY.-.####."""
		meta = frappe.get_meta("Evidencia Disciplinaria")
		self.assertIn("EVD-", meta.autoname or "")

	def test_evidencia_disciplinaria_requires_caso_or_afectado(self):
		"""Debe fallar si ni caso ni afectado están llenos."""
		from hubgh.hubgh.doctype.evidencia_disciplinaria.evidencia_disciplinaria import (
			EvidenciaDisciplinaria,
		)
		from types import SimpleNamespace

		doc = SimpleNamespace(
			caso=None,
			afectado=None,
			archivo="some_file_url",
			tipo_documento="Evidencia Hechos",
			cargado_por=None,
			fecha_carga=None,
		)

		with self.assertRaises(frappe.ValidationError):
			EvidenciaDisciplinaria._validate_caso_or_afectado(doc)

	def test_evidencia_disciplinaria_passes_if_caso_filled(self):
		"""Debe pasar si caso está lleno (aunque afectado esté vacío)."""
		from hubgh.hubgh.doctype.evidencia_disciplinaria.evidencia_disciplinaria import (
			EvidenciaDisciplinaria,
		)
		from types import SimpleNamespace

		doc = SimpleNamespace(
			caso="DIS-2026-00001",
			afectado=None,
			archivo="some_file_url",
			tipo_documento="Evidencia Hechos",
			cargado_por=None,
			fecha_carga=None,
		)

		# No debe lanzar excepción
		EvidenciaDisciplinaria._validate_caso_or_afectado(doc)

	def test_evidencia_disciplinaria_passes_if_afectado_filled(self):
		"""Debe pasar si afectado está lleno (aunque caso esté vacío)."""
		from hubgh.hubgh.doctype.evidencia_disciplinaria.evidencia_disciplinaria import (
			EvidenciaDisciplinaria,
		)
		from types import SimpleNamespace

		doc = SimpleNamespace(
			caso=None,
			afectado="AFE-2026-00001",
			archivo="some_file_url",
			tipo_documento="Evidencia Hechos",
			cargado_por=None,
			fecha_carga=None,
		)

		# No debe lanzar excepción
		EvidenciaDisciplinaria._validate_caso_or_afectado(doc)
