from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.page.sst_bandeja.sst_bandeja import get_sst_bandeja


class _Row(dict):
	def __getattr__(self, item):
		return self.get(item)


class TestSstBandeja(FrappeTestCase):
	def test_get_sst_bandeja_returns_legible_labels(self):
		def _get_all(doctype, filters=None, fields=None, order_by=None, limit_page_length=None):
			if doctype == "SST Alerta":
				return [
					_Row(
						name="SSTA-1",
						novedad="NOV-1",
						novedad_titulo_resumen="Control incapacidad por lumbalgia",
						novedad_tipo_novedad="Incapacidad",
						empleado="EMP-1",
						empleado_nombres="Juana",
						empleado_apellidos="Diaz",
						punto_venta="PDV-1",
						punto_venta_nombre="Portal Norte",
						fecha_programada="2026-03-12",
						estado="Pendiente",
						tipo_alerta="Control medico",
						asignado_a="sst.responsable@example.com",
						mensaje="Llamar a Juana para confirmar evolucion y soporte medico.",
					),
				]
			if doctype == "Novedad SST":
				return [
					_Row(
						name="NOV-1",
						owner="owner@example.com",
						empleado="EMP-1",
						empleado_nombres="Juana",
						empleado_apellidos="Diaz",
						punto_venta="PDV-1",
						punto_venta_nombre="Portal Norte",
						tipo_novedad="Incapacidad",
						estado="En seguimiento",
						prioridad="Alta",
						titulo_resumen="Control incapacidad por lumbalgia",
						descripcion_resumen="Seguimiento por incapacidad extendida",
						proxima_alerta_fecha="2026-03-15",
						en_radar=1,
						categoria_seguimiento="Condicion medica",
						tiene_recomendaciones=1,
						es_incapacidad=1,
						ref_doctype="GH Novedad",
						ref_docname="GHN-1",
					),
				]
			if doctype == "User":
				return [
					{"name": "sst.responsable@example.com", "full_name": "Paula SST"},
					{"name": "owner@example.com", "full_name": "Carlos Prevencion"},
				]
			if doctype == "GH Novedad":
				return [{"name": "GHN-1", "tipo": "Descargos", "estado": "Abierta"}]
			return []

		with patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.nowdate", return_value="2026-03-12"), patch(
			"hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_all",
			side_effect=_get_all,
		):
			payload = get_sst_bandeja(punto_venta="PDV-1", responsable="sst.responsable@example.com")

		self.assertIn("cola_alertas", payload)
		self.assertIn("cola_novedades", payload)
		self.assertEqual(payload["kpis"]["total_alertas"], 1)
		self.assertEqual(payload["kpis"]["novedades_abiertas"], 1)

		alerta = payload["cola_alertas"][0]
		self.assertEqual(alerta["empleado_label"], "Juana Diaz")
		self.assertEqual(alerta["punto_venta_label"], "Portal Norte")
		self.assertEqual(alerta["responsable_label"], "Paula SST")
		self.assertEqual(alerta["tipo_resumen"], "Control medico · Pendiente")
		self.assertEqual(alerta["novedad_label"], "Control incapacidad por lumbalgia")

		novedad = payload["cola_novedades"][0]
		self.assertEqual(novedad["empleado_label"], "Juana Diaz")
		self.assertEqual(novedad["punto_venta_label"], "Portal Norte")
		self.assertEqual(novedad["responsable_label"], "Carlos Prevencion")
		self.assertEqual(novedad["tipo_resumen"], "Control incapacidad por lumbalgia")
		self.assertEqual(novedad["rrll_handoff_label"], "Traslado RRLL: Descargos")
		self.assertEqual(novedad["rrll_handoff_name"], "GHN-1")
		self.assertEqual(payload["alertas_hoy"][0]["responsable_label"], "Paula SST")

	def test_get_sst_bandeja_reports_degraded_exam_contract_on_upstream_failure(self):
		def _get_all(doctype, filters=None, fields=None, order_by=None, limit_page_length=None):
			if doctype == "SST Alerta":
				return []
			if doctype == "Novedad SST":
				return []
			if doctype == "User":
				return []
			if doctype == "GH Novedad":
				return []
			return []

		with patch("hubgh.hubgh.page.sst_bandeja.sst_bandeja.nowdate", return_value="2026-03-12"), patch(
			"hubgh.hubgh.page.sst_bandeja.sst_bandeja.frappe.get_all",
			side_effect=_get_all,
		), patch(
			"hubgh.hubgh.page.sst_examenes_medicos.sst_examenes_medicos.list_medical_exam_candidates",
			side_effect=RuntimeError("database unavailable"),
		):
			payload = get_sst_bandeja(punto_venta="PDV-1")

		self.assertEqual(payload["resumen_examenes"]["status"], "degraded")
		self.assertEqual(payload["resumen_examenes"]["reason"], "infrastructure_unavailable")
