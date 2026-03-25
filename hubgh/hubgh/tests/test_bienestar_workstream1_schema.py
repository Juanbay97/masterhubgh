from types import SimpleNamespace
import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.doctype.bienestar_proceso_colaborador.bienestar_proceso_colaborador import (
	BienestarProcesoColaborador,
)
from hubgh.hubgh.doctype.bienestar_seguimiento_ingreso.bienestar_seguimiento_ingreso import (
	BienestarSeguimientoIngreso,
)
from hubgh.hubgh.bienestar_context import (
	BIENESTAR_ALERT_SOURCE_FIELDS,
	BIENESTAR_COMPROMISO_SOURCE_FIELDS,
	COMPROMISO_ORIGIN_MANUAL,
	expected_alert_source_field,
	validate_compromiso_source_reference,
	validate_single_source_reference,
)


class TestBienestarWorkstream1Schema(FrappeTestCase):
	def test_bienestar_doctypes_exist_and_have_base_states(self):
		head_doctypes = {
			"Bienestar Proceso Colaborador": {"estado"},
			"Bienestar Seguimiento Ingreso": {"estado", "tipo_seguimiento"},
			"Bienestar Evaluacion Periodo Prueba": {"estado", "dictamen"},
			"Bienestar Levantamiento Punto": {"estado"},
			"Bienestar Alerta": {"estado"},
			"Bienestar Compromiso": {"estado"},
		}

		for doctype, expected_fields in head_doctypes.items():
			meta = frappe.get_meta(doctype)
			self.assertIsNotNone(meta)
			fieldnames = {d.fieldname for d in meta.fields}
			self.assertTrue(expected_fields.issubset(fieldnames), f"Faltan campos en {doctype}")

	def test_operational_doctypes_hide_proceso_colaborador(self):
		base = Path(__file__).resolve().parents[1] / "hubgh" / "doctype"
		targets = {
			"bienestar_alerta": "Bienestar Alerta",
			"bienestar_compromiso": "Bienestar Compromiso",
		}
		for slug, label in targets.items():
			json_path = base / slug / f"{slug}.json"
			payload = json.loads(json_path.read_text(encoding="utf-8"))
			field = next((row for row in payload.get("fields", []) if row.get("fieldname") == "proceso_colaborador"), None)
			self.assertIsNotNone(field)
			self.assertEqual(int(field.get("hidden") or 0), 1, f"{label}.proceso_colaborador debe estar oculto")
			self.assertNotIn("proceso_colaborador", payload.get("field_order", []))

	def test_bienestar_alerta_y_compromiso_include_hidden_origin_context(self):
		base = Path(__file__).resolve().parents[1] / "hubgh" / "doctype"
		for slug, expected in {
			"bienestar_alerta": set(BIENESTAR_ALERT_SOURCE_FIELDS),
			"bienestar_compromiso": set(BIENESTAR_COMPROMISO_SOURCE_FIELDS),
		}.items():
			json_path = base / slug / f"{slug}.json"
			payload = json.loads(json_path.read_text(encoding="utf-8"))
			field = next((row for row in payload.get("fields", []) if row.get("fieldname") == "origen_contexto"), None)
			self.assertIsNotNone(field)
			self.assertEqual(field.get("fieldtype"), "Select")
			self.assertEqual(int(field.get("hidden") or 0), 1)
			self.assertEqual(int(field.get("read_only") or 0), 1)
			self.assertTrue(expected.issubset(set((field.get("options") or "").splitlines())))

	def test_bienestar_compromiso_exposes_legible_origin_selector(self):
		json_path = (
			Path(__file__).resolve().parents[1]
			/ "hubgh"
			/ "doctype"
			/ "bienestar_compromiso"
			/ "bienestar_compromiso.json"
		)
		payload = json.loads(json_path.read_text(encoding="utf-8"))
		field = next((row for row in payload.get("fields", []) if row.get("fieldname") == "tipo_origen_compromiso"), None)

		self.assertIsNotNone(field)
		self.assertEqual(field.get("fieldtype"), "Select")
		self.assertEqual(field.get("default"), COMPROMISO_ORIGIN_MANUAL)
		self.assertEqual(
			(field.get("options") or "").splitlines(),
			[
				"Manual",
				"Alerta",
				"Seguimiento ingreso",
				"Evaluacion periodo prueba",
				"Levantamiento",
				"GH Novedad",
			],
		)

	def test_alerta_accepts_handoff_trace_when_active_origin_is_consistent(self):
		doc = SimpleNamespace(
			tipo_alerta="Ingreso",
			origen_contexto="seguimiento_ingreso",
			seguimiento_ingreso="BSI-001",
			evaluacion_periodo_prueba=None,
			levantamiento_punto=None,
			gh_novedad="GHN-001",
		)

		fieldname, ref_name = validate_single_source_reference(
			doc,
			BIENESTAR_ALERT_SOURCE_FIELDS,
			doctype_label="Bienestar Alerta",
			expected_field=expected_alert_source_field(doc.tipo_alerta),
		)

		self.assertEqual(fieldname, "seguimiento_ingreso")
		self.assertEqual(ref_name, "BSI-001")
		self.assertEqual(doc.origen_contexto, "seguimiento_ingreso")

	def test_compromiso_requires_active_origin_reference_when_context_is_present(self):
		doc = SimpleNamespace(
			tipo_origen_compromiso="Alerta",
			origen_contexto="alerta",
			alerta=None,
			seguimiento_ingreso="BSI-001",
			evaluacion_periodo_prueba=None,
			levantamiento_punto=None,
			gh_novedad="GHN-001",
		)

		with self.assertRaises(Exception):
			validate_compromiso_source_reference(doc, doctype_label="Bienestar Compromiso")

	def test_compromiso_manual_accepts_zero_origins(self):
		doc = SimpleNamespace(
			tipo_origen_compromiso=COMPROMISO_ORIGIN_MANUAL,
			origen_contexto="alerta",
			alerta=None,
			seguimiento_ingreso=None,
			evaluacion_periodo_prueba=None,
			levantamiento_punto=None,
			gh_novedad=None,
		)

		fieldname, ref_name = validate_compromiso_source_reference(doc, doctype_label="Bienestar Compromiso")

		self.assertIsNone(fieldname)
		self.assertIsNone(ref_name)
		self.assertEqual(doc.origen_contexto, "")
		self.assertEqual(doc.tipo_origen_compromiso, COMPROMISO_ORIGIN_MANUAL)

	def test_compromiso_manual_rejects_any_origin_reference(self):
		doc = SimpleNamespace(
			tipo_origen_compromiso=COMPROMISO_ORIGIN_MANUAL,
			origen_contexto="",
			alerta="BAL-001",
			seguimiento_ingreso=None,
			evaluacion_periodo_prueba=None,
			levantamiento_punto=None,
			gh_novedad=None,
		)

		with self.assertRaises(Exception):
			validate_compromiso_source_reference(doc, doctype_label="Bienestar Compromiso")

	def test_compromiso_non_manual_requires_exactly_one_origin(self):
		doc = SimpleNamespace(
			tipo_origen_compromiso="Seguimiento ingreso",
			origen_contexto="seguimiento_ingreso",
			alerta=None,
			seguimiento_ingreso="BSI-001",
			evaluacion_periodo_prueba=None,
			levantamiento_punto=None,
			gh_novedad=None,
		)

		fieldname, ref_name = validate_compromiso_source_reference(doc, doctype_label="Bienestar Compromiso")

		self.assertEqual(fieldname, "seguimiento_ingreso")
		self.assertEqual(ref_name, "BSI-001")

	def test_compromiso_non_manual_rejects_multiple_origins_on_new_docs(self):
		doc = SimpleNamespace(
			tipo_origen_compromiso="Alerta",
			origen_contexto="alerta",
			alerta="BAL-001",
			seguimiento_ingreso="BSI-001",
			evaluacion_periodo_prueba=None,
			levantamiento_punto=None,
			gh_novedad=None,
		)

		with self.assertRaises(Exception):
			validate_compromiso_source_reference(doc, doctype_label="Bienestar Compromiso")

	def test_compromiso_keeps_legacy_traceability_on_existing_docs(self):
		doc = SimpleNamespace(
			name="BCO-2026-00001",
			tipo_origen_compromiso="Alerta",
			origen_contexto="alerta",
			alerta="BAL-001",
			seguimiento_ingreso="BSI-001",
			evaluacion_periodo_prueba=None,
			levantamiento_punto=None,
			gh_novedad=None,
		)

		fieldname, ref_name = validate_compromiso_source_reference(doc, doctype_label="Bienestar Compromiso")

		self.assertEqual(fieldname, "alerta")
		self.assertEqual(ref_name, "BAL-001")
		self.assertEqual(doc.origen_contexto, "alerta")

	def test_bienestar_child_tables_are_istable(self):
		for doctype in [
			"Bienestar Respuesta Escala",
			"Bienestar Respuesta Abierta",
			"Bienestar Participante Levantamiento",
			"Bienestar Bitacora Caso",
		]:
			meta = frappe.get_meta(doctype)
			self.assertEqual(int(meta.istable or 0), 1, f"{doctype} debe ser tabla hija")

	def test_bienestar_proceso_syncs_point_from_ficha(self):
		doc = SimpleNamespace(punto_venta=None, ficha_empleado="EMP-001")
		with patch(
			"hubgh.hubgh.doctype.bienestar_proceso_colaborador.bienestar_proceso_colaborador.frappe.db.get_value",
			return_value="PDV-001",
		):
			BienestarProcesoColaborador.validate(doc)

		self.assertEqual(doc.punto_venta, "PDV-001")

	def test_bienestar_seguimiento_requires_momento_for_30_45(self):
		doc = SimpleNamespace(tipo_seguimiento="30/45", momento_consolidacion=None, punto_venta="PDV-001", ficha_empleado=None)

		with self.assertRaises(Exception):
			BienestarSeguimientoIngreso.validate(doc)
