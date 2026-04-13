# Copyright (c) 2026, Antigravity and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.doctype.novedad_sst.novedad_sst import NovedadSST


class TestNovedadSST(FrappeTestCase):
	def test_validate_blocks_rrll_types_in_novedad_sst(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		doc.tipo_novedad = "Suspensión"
		doc.fecha_inicio = "2026-03-10"

		with self.assertRaises(frappe.ValidationError):
			doc.validate_sst_taxonomy()

	def test_validate_accidente_requires_yes_no_incapacidad(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		doc.tipo_novedad = "Accidente"
		doc.causa_evento = "Acto inseguro"

		with self.assertRaises(frappe.ValidationError):
			doc.validate_accidente_payload()

	def test_validate_incapacidad_requires_payload(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		doc.tipo_novedad = "Incapacidad por enfermedad general"

		with self.assertRaises(frappe.ValidationError):
			doc.validate_incapacidad_payload()

	def test_normalize_prorrogas_moves_legacy_rows_out_of_seguimientos(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		doc.tipo_novedad = "Incapacidad por enfermedad general"
		doc.append(
			"seguimientos",
			{
				"fecha_seguimiento": "2026-03-10 08:00:00",
				"tipo_seguimiento": "Prórroga incapacidad",
				"detalle": "Extensión por control médico",
			},
		)
		doc.append(
			"seguimientos",
			{
				"fecha_seguimiento": "2026-03-11 08:00:00",
				"tipo_seguimiento": "Llamada",
				"detalle": "Confirmación con empleado",
			},
		)

		doc.normalize_prorroga_rows()

		self.assertEqual(len(doc.prorrogas_incapacidad), 1)
		self.assertEqual(doc.prorrogas_incapacidad[0].tipo_seguimiento, "Prórroga incapacidad")
		self.assertEqual(len(doc.seguimientos), 1)
		self.assertEqual(doc.seguimientos[0].tipo_seguimiento, "Llamada")

	def test_normalize_prorrogas_forces_prorroga_type_on_child_rows(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		doc.tipo_novedad = "Incapacidad por enfermedad general"
		doc.append(
			"prorrogas_incapacidad",
			{
				"fecha_seguimiento": "2026-03-10 08:00:00",
				"tipo_seguimiento": "Llamada",
				"detalle": "Se cargó desde UI antigua",
			},
		)

		doc.normalize_prorroga_rows()

		self.assertEqual(doc.prorrogas_incapacidad[0].tipo_seguimiento, "Prórroga incapacidad")

	def test_prorrogas_only_allowed_for_incapacidad_cases(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		doc.tipo_novedad = "Aforado"
		doc.append(
			"prorrogas_incapacidad",
			{
				"fecha_seguimiento": "2026-03-10 08:00:00",
				"tipo_seguimiento": "Prórroga incapacidad",
			},
		)

		with self.assertRaises(frappe.ValidationError):
			doc.ensure_prorroga_consistency()

	def test_alert_assignee_prefers_hr_sst(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		with patch("hubgh.hubgh.doctype.novedad_sst.novedad_sst.frappe.get_all") as get_all_mock:
			get_all_mock.side_effect = [
				["hr.sst@example.com"],
			]
			self.assertEqual(doc.get_alert_assignee(), "hr.sst@example.com")

	def test_validate_blocks_retiro_when_not_closed(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		doc.tipo_novedad = "Retiro"
		doc.impacta_estado = 1
		doc.estado = "Abierta"
		doc.estado_destino = "Retirado"

		with self.assertRaises(frappe.ValidationError):
			doc.ensure_retiro_consistency()

	def test_validate_allows_retiro_when_closed(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		doc.tipo_novedad = "Retiro"
		doc.impacta_estado = 1
		doc.estado = "Cerrada"
		doc.estado_destino = "Retirado"

		doc.ensure_retiro_consistency()

	def test_retiro_traceability_event_emits_once(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		doc.name = "NOV-RET-001"
		doc.empleado = "EMP-001"
		doc.punto_venta = "PDV-001"
		doc.fecha_inicio = "2026-03-10"
		doc.fecha_fin = "2026-03-12"
		doc.tipo_novedad = "Retiro"
		doc.estado = "Cerrada"
		doc.estado_destino = "Retirado"

		def fake_exists(doctype, filters=None, *args, **kwargs):
			if doctype == "DocType":
				return filters == "GH Novedad"
			if doctype == "GH Novedad":
				return False
			return False

		with patch("hubgh.hubgh.doctype.novedad_sst.novedad_sst.frappe.db.exists", side_effect=fake_exists), patch(
			"hubgh.hubgh.doctype.novedad_sst.novedad_sst.frappe.get_doc"
		) as get_doc_mock:
			get_doc_mock.return_value = SimpleNamespace(insert=lambda **kwargs: None)
			doc.ensure_retiro_traceability_event()

		payload = get_doc_mock.call_args.args[0]
		self.assertEqual(payload["doctype"], "GH Novedad")
		self.assertEqual(payload["persona"], "EMP-001")
		self.assertIn("Retiro controlado", payload["descripcion"])

	def test_apply_estado_empleado_sets_retirado_only_when_closed(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		doc.empleado = "EMP-001"
		doc.estado = "Cerrada"
		doc.estado_destino = "Retirado"
		doc.impacta_estado = 1
		real_get_value = frappe.db.get_value

		def scoped_get_value(doctype, filters=None, fieldname="name", *args, **kwargs):
			if doctype == "Ficha Empleado" and filters == "EMP-001" and fieldname == "estado":
				return "Activo"
			return real_get_value(doctype, filters, fieldname, *args, **kwargs)

		with patch(
			"hubgh.hubgh.doctype.novedad_sst.novedad_sst.frappe.db.get_value",
			side_effect=scoped_get_value,
		), patch("hubgh.hubgh.doctype.novedad_sst.novedad_sst.apply_retirement") as retirement_mock:
			doc.apply_estado_empleado()

		retirement_mock.assert_called_once()

	def test_ensure_sst_alerta_record_preserves_operator_state_and_todo(self):
		doc = frappe.get_doc({"doctype": "Novedad SST"})
		doc.name = "NOV-001"
		doc.empleado = "EMP-001"
		doc.punto_venta = "PDV-001"
		doc.proxima_alerta_fecha = "2026-03-20"
		doc.tipo_alerta = "Seguimiento"
		doc.alerta_activa = 1
		doc.crear_alerta = 1
		doc.get_alert_assignee = lambda: "sst@example.com"
		doc.get_alert_message = lambda: "Mensaje refrescado"

		with patch(
			"hubgh.hubgh.doctype.novedad_sst.novedad_sst.frappe.db.get_value",
			side_effect=lambda doctype, name, fieldname=None, as_dict=False: {
				"estado": "Atendida",
				"referencia_todo": "TODO-001",
				"atendida_en": "2026-03-18 10:00:00",
				"ultima_notificacion": "2026-03-18",
			} if doctype == "SST Alerta" and as_dict else "ALERTA-001",
		), patch("hubgh.hubgh.doctype.novedad_sst.novedad_sst.frappe.db.set_value") as set_value_mock:
			doc.ensure_sst_alerta_record()

		self.assertTrue(any(call.args[:3] == ("SST Alerta", "ALERTA-001", {"empleado": "EMP-001", "punto_venta": "PDV-001", "fecha_programada": "2026-03-20", "tipo_alerta": "Seguimiento", "asignado_a": "sst@example.com", "mensaje": "Mensaje refrescado", "canal": "In-app", "estado": "Atendida"}) for call in set_value_mock.call_args_list))
		self.assertTrue(any(call.args[:3] == ("SST Alerta", "ALERTA-001", "referencia_todo") for call in set_value_mock.call_args_list))
