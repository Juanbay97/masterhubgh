# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt
"""
T028 — Acta Descargos DocType schema tests.
T032 — Comunicado Sancion schema verification.

Tests run BEFORE implementation (TDD RED → GREEN).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


# =============================================================================
# T028 — DocType Acta Descargos schema
# =============================================================================


class TestActaDescargosDocType(FrappeTestCase):
	"""T028 — DocType Acta Descargos: schema, naming, validaciones."""

	def test_acta_descargos_doctype_exists(self):
		"""El DocType Acta Descargos debe existir."""
		meta = frappe.get_meta("Acta Descargos")
		self.assertIsNotNone(meta)
		self.assertEqual(meta.name, "Acta Descargos")

	def test_acta_descargos_naming_series(self):
		"""El autoname debe contener 'ACT-'."""
		meta = frappe.get_meta("Acta Descargos")
		self.assertIn("ACT-", meta.autoname or "")

	def test_acta_descargos_has_required_fields(self):
		"""Debe tener todos los campos del design §1.6."""
		meta = frappe.get_meta("Acta Descargos")
		fieldnames = {f.fieldname for f in meta.fields}
		required = {
			"afectado",
			"citacion",
			"numero_ronda",
			"fecha_sesion",
			"lugar_sesion",
			"participantes_empresa",
			"testigos_trabajador",
			"autorizacion_grabacion",
			"derechos_informados",
			"fecha_ingreso_empleado",
			"cargo_actual",
			"jefe_inmediato",
			"hechos_leidos",
			"preguntas_respuestas",
			"firma_empleado",
			"testigo_1",
			"testigo_2",
			"archivo_acta",
		}
		self.assertTrue(
			required.issubset(fieldnames),
			f"Faltan campos en Acta Descargos: {required - fieldnames}",
		)

	def test_acta_descargos_afectado_links_to_afectado_disciplinario(self):
		"""afectado debe ser Link a Afectado Disciplinario y requerido."""
		meta = frappe.get_meta("Acta Descargos")
		field = next((f for f in meta.fields if f.fieldname == "afectado"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Afectado Disciplinario")
		self.assertEqual(int(field.reqd or 0), 1)

	def test_acta_descargos_citacion_links_to_citacion_disciplinaria(self):
		"""citacion debe ser Link a Citacion Disciplinaria y requerido."""
		meta = frappe.get_meta("Acta Descargos")
		field = next((f for f in meta.fields if f.fieldname == "citacion"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Citacion Disciplinaria")
		self.assertEqual(int(field.reqd or 0), 1)

	def test_acta_descargos_fecha_sesion_is_datetime(self):
		"""fecha_sesion debe ser Datetime y requerido."""
		meta = frappe.get_meta("Acta Descargos")
		field = next((f for f in meta.fields if f.fieldname == "fecha_sesion"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Datetime")
		self.assertEqual(int(field.reqd or 0), 1)

	def test_acta_descargos_derechos_informados_is_check(self):
		"""derechos_informados debe ser Check."""
		meta = frappe.get_meta("Acta Descargos")
		field = next((f for f in meta.fields if f.fieldname == "derechos_informados"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Check")

	def test_acta_descargos_firma_empleado_is_check(self):
		"""firma_empleado debe ser Check."""
		meta = frappe.get_meta("Acta Descargos")
		field = next((f for f in meta.fields if f.fieldname == "firma_empleado"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Check")

	def test_acta_descargos_participantes_empresa_is_table(self):
		"""participantes_empresa debe ser Table de Participante Acta."""
		meta = frappe.get_meta("Acta Descargos")
		field = next((f for f in meta.fields if f.fieldname == "participantes_empresa"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Table")
		self.assertEqual(field.options, "Participante Acta")

	def test_acta_descargos_preguntas_respuestas_is_table(self):
		"""preguntas_respuestas debe ser Table de Pregunta Respuesta Descargos."""
		meta = frappe.get_meta("Acta Descargos")
		field = next((f for f in meta.fields if f.fieldname == "preguntas_respuestas"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Table")
		self.assertEqual(field.options, "Pregunta Respuesta Descargos")

	def test_acta_descargos_archivo_acta_is_attach_readonly(self):
		"""archivo_acta debe ser Attach y readonly."""
		meta = frappe.get_meta("Acta Descargos")
		field = next((f for f in meta.fields if f.fieldname == "archivo_acta"), None)
		self.assertIsNotNone(field)
		self.assertIn(field.fieldtype, ("Attach", "Link"))
		self.assertEqual(int(field.read_only or 0), 1)

	def test_acta_descargos_testigo_1_links_ficha_empleado(self):
		"""testigo_1 y testigo_2 deben ser Link a Ficha Empleado."""
		meta = frappe.get_meta("Acta Descargos")
		for fname in ("testigo_1", "testigo_2"):
			field = next((f for f in meta.fields if f.fieldname == fname), None)
			self.assertIsNotNone(field, f"Campo {fname} no encontrado")
			self.assertEqual(field.fieldtype, "Link")
			self.assertEqual(field.options, "Ficha Empleado")

	# -----------------------------------------------------------------------
	# Controller validations — unit tests with SimpleNamespace
	# -----------------------------------------------------------------------

	def test_validate_derechos_informados_raises_if_zero(self):
		"""Si derechos_informados=0, debe lanzar ValidationError."""
		from hubgh.hubgh.doctype.acta_descargos.acta_descargos import ActaDescargos

		doc = SimpleNamespace(
			name="ACT-TEST-001",
			derechos_informados=0,
			firma_empleado=1,
			testigo_1=None,
			testigo_2=None,
			preguntas_respuestas=[SimpleNamespace(pregunta="P", respuesta="R")],
		)

		with self.assertRaises(frappe.ValidationError):
			ActaDescargos._validate_derechos_informados(doc)

	def test_validate_derechos_informados_passes_if_one(self):
		"""Si derechos_informados=1, no debe lanzar error."""
		from hubgh.hubgh.doctype.acta_descargos.acta_descargos import ActaDescargos

		doc = SimpleNamespace(
			name="ACT-TEST-001",
			derechos_informados=1,
			firma_empleado=1,
			testigo_1=None,
			testigo_2=None,
			preguntas_respuestas=[SimpleNamespace(pregunta="P", respuesta="R")],
		)

		# Should not raise
		ActaDescargos._validate_derechos_informados(doc)

	def test_validate_testigos_raises_if_no_firma_and_no_testigos(self):
		"""Si firma_empleado=0 y faltan testigos → ValidationError."""
		from hubgh.hubgh.doctype.acta_descargos.acta_descargos import ActaDescargos

		doc = SimpleNamespace(
			name="ACT-TEST-001",
			firma_empleado=0,
			testigo_1=None,
			testigo_2=None,
		)

		with self.assertRaises(frappe.ValidationError):
			ActaDescargos._validate_testigos_si_no_firma(doc)

	def test_validate_testigos_raises_if_only_one_testigo(self):
		"""Si firma_empleado=0 y solo 1 testigo → ValidationError."""
		from hubgh.hubgh.doctype.acta_descargos.acta_descargos import ActaDescargos

		doc = SimpleNamespace(
			name="ACT-TEST-001",
			firma_empleado=0,
			testigo_1="EMP-001",
			testigo_2=None,
		)

		with self.assertRaises(frappe.ValidationError):
			ActaDescargos._validate_testigos_si_no_firma(doc)

	def test_validate_testigos_passes_if_firma(self):
		"""Si firma_empleado=1, no se requieren testigos."""
		from hubgh.hubgh.doctype.acta_descargos.acta_descargos import ActaDescargos

		doc = SimpleNamespace(
			name="ACT-TEST-001",
			firma_empleado=1,
			testigo_1=None,
			testigo_2=None,
		)

		# Should not raise
		ActaDescargos._validate_testigos_si_no_firma(doc)

	def test_validate_testigos_passes_if_no_firma_but_both_testigos(self):
		"""Si firma_empleado=0 y hay 2 testigos → sin error."""
		from hubgh.hubgh.doctype.acta_descargos.acta_descargos import ActaDescargos

		doc = SimpleNamespace(
			name="ACT-TEST-001",
			firma_empleado=0,
			testigo_1="EMP-001",
			testigo_2="EMP-002",
		)

		# Should not raise
		ActaDescargos._validate_testigos_si_no_firma(doc)


# =============================================================================
# T032 — Comunicado Sancion schema verification (already created in Phase 2)
# =============================================================================


class TestComunicadoSancionSchema(FrappeTestCase):
	"""T032 — Verify ComunicadoSancion schema matches design §1.7."""

	def test_comunicado_sancion_doctype_exists(self):
		"""El DocType Comunicado Sancion debe existir."""
		meta = frappe.get_meta("Comunicado Sancion")
		self.assertIsNotNone(meta)
		self.assertEqual(meta.name, "Comunicado Sancion")

	def test_comunicado_sancion_naming_series(self):
		"""El autoname debe contener 'COM-'."""
		meta = frappe.get_meta("Comunicado Sancion")
		self.assertIn("COM-", meta.autoname or "")

	def test_comunicado_sancion_has_required_fields(self):
		"""Debe tener: afectado, tipo_comunicado, fecha_emision, fundamentos, articulos_rit_citados, archivo_comunicado."""
		meta = frappe.get_meta("Comunicado Sancion")
		fieldnames = {f.fieldname for f in meta.fields}
		required = {
			"afectado",
			"tipo_comunicado",
			"fecha_emision",
			"fundamentos",
			"articulos_rit_citados",
			"archivo_comunicado",
		}
		self.assertTrue(
			required.issubset(fieldnames),
			f"Faltan campos en Comunicado Sancion: {required - fieldnames}",
		)

	def test_comunicado_sancion_tipo_options(self):
		"""tipo_comunicado debe incluir los 5 tipos del design."""
		meta = frappe.get_meta("Comunicado Sancion")
		field = next((f for f in meta.fields if f.fieldname == "tipo_comunicado"), None)
		self.assertIsNotNone(field)
		opciones = set((field.options or "").split("\n"))
		expected = {
			"Llamado de Atención Directo",
			"Llamado de Atención",
			"Suspensión",
			"Terminación",
			"Recordatorio de Funciones",
		}
		self.assertTrue(
			expected.issubset(opciones),
			f"Faltan tipos en Comunicado Sancion: {expected - opciones}",
		)

	def test_comunicado_sancion_articulos_rit_is_table(self):
		"""articulos_rit_citados debe ser Table de Articulo RIT Caso."""
		meta = frappe.get_meta("Comunicado Sancion")
		field = next((f for f in meta.fields if f.fieldname == "articulos_rit_citados"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Table")
		self.assertEqual(field.options, "Articulo RIT Caso")

	def test_comunicado_sancion_validates_articulos_required_for_sancion(self):
		"""Comunicado de tipo Suspensión sin artículos → ValidationError."""
		from hubgh.hubgh.doctype.comunicado_sancion.comunicado_sancion import ComunicadoSancion

		doc = SimpleNamespace(
			name="COM-TEST-001",
			tipo_comunicado="Suspensión",
			articulos_rit_citados=[],
			fundamentos="Fundamentos",
		)

		with self.assertRaises(frappe.ValidationError):
			ComunicadoSancion._validate_articulos_rit_required(doc)

	def test_comunicado_sancion_no_articulos_required_for_recordatorio(self):
		"""Comunicado de tipo Recordatorio de Funciones sin artículos → sin error."""
		from hubgh.hubgh.doctype.comunicado_sancion.comunicado_sancion import ComunicadoSancion

		doc = SimpleNamespace(
			name="COM-TEST-002",
			tipo_comunicado="Recordatorio de Funciones",
			articulos_rit_citados=[],
			fundamentos="Recordatorio",
		)

		# Should not raise
		ComunicadoSancion._validate_articulos_rit_required(doc)


# =============================================================================
# Child Tables schema
# =============================================================================


class TestParticipanteActaDocType(FrappeTestCase):
	"""Verify child table Participante Acta exists and has expected fields."""

	def test_participante_acta_is_child_table(self):
		"""Participante Acta debe ser una Child Table."""
		meta = frappe.get_meta("Participante Acta")
		self.assertIsNotNone(meta)
		self.assertEqual(int(meta.istable or 0), 1)

	def test_participante_acta_has_empleado_and_rol(self):
		"""Debe tener campos empleado y rol."""
		meta = frappe.get_meta("Participante Acta")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("empleado", fieldnames)
		self.assertIn("rol", fieldnames)


class TestPreguntaRespuestaDescargosDocType(FrappeTestCase):
	"""Verify child table Pregunta Respuesta Descargos exists and has expected fields."""

	def test_pregunta_respuesta_is_child_table(self):
		"""Pregunta Respuesta Descargos debe ser una Child Table."""
		meta = frappe.get_meta("Pregunta Respuesta Descargos")
		self.assertIsNotNone(meta)
		self.assertEqual(int(meta.istable or 0), 1)

	def test_pregunta_respuesta_has_pregunta_respuesta(self):
		"""Debe tener campos pregunta y respuesta."""
		meta = frappe.get_meta("Pregunta Respuesta Descargos")
		fieldnames = {f.fieldname for f in meta.fields}
		self.assertIn("pregunta", fieldnames)
		self.assertIn("respuesta", fieldnames)
