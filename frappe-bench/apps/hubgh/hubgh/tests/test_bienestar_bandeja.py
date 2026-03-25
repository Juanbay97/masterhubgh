from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.page.bienestar_bandeja.bienestar_bandeja import (
	get_bienestar_bandeja,
	gestionar_bienestar_item,
)


class _FakeDoc(dict):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.__dict__.update(kwargs)
		if "bitacora" not in kwargs:
			self.bitacora = []

	def append(self, fieldname, row):
		if fieldname == "bitacora":
			self.bitacora.append(row)

	def get(self, key, default=None):
		return getattr(self, key, default)

	def save(self, ignore_permissions=True):
		return None


class TestBienestarBandeja(FrappeTestCase):
	def test_get_bienestar_bandeja_contract_and_kpis(self):
		def _get_all(doctype, fields=None, order_by=None):
			if doctype == "Bienestar Seguimiento Ingreso":
				return [
					{
						"name": "BSI-1",
						"ficha_empleado": "EMP-1",
						"empleado_nombres": "Ana",
						"empleado_apellidos": "Gomez",
						"punto_venta": "PDV-1",
						"punto_venta_nombre": "Portal Norte",
						"tipo_seguimiento": "5",
						"fecha_programada": "2026-03-10",
						"estado": "Pendiente",
						"responsable_bienestar": "bienestar@example.com",
						"responsable_bienestar_nombre": "Marta Bienestar",
					},
					{
						"name": "BSI-2",
						"ficha_empleado": "EMP-2",
						"empleado_nombres": "Luis",
						"empleado_apellidos": "Perez",
						"punto_venta": "PDV-1",
						"punto_venta_nombre": "Portal Norte",
						"tipo_seguimiento": "10",
						"fecha_programada": "2026-03-12",
						"estado": "Pendiente",
						"responsable_bienestar": "bienestar@example.com",
						"responsable_bienestar_nombre": "Marta Bienestar",
					},
					{
						"name": "BSI-3",
						"ficha_empleado": "EMP-3",
						"empleado_nombres": "Sara",
						"empleado_apellidos": "Lopez",
						"punto_venta": "PDV-1",
						"punto_venta_nombre": "Portal Norte",
						"tipo_seguimiento": "30/45",
						"fecha_programada": "2026-03-20",
						"estado": "En gestión",
						"responsable_bienestar": "bienestar@example.com",
						"responsable_bienestar_nombre": "Marta Bienestar",
					},
				]
			if doctype == "Bienestar Evaluacion Periodo Prueba":
				return [
					{
						"name": "BEP-1",
						"ficha_empleado": "EMP-1",
						"empleado_nombres": "Ana",
						"empleado_apellidos": "Gomez",
						"punto_venta": "PDV-1",
						"punto_venta_nombre": "Portal Norte",
						"fecha_evaluacion": "2026-03-10",
						"estado": "Pendiente",
						"dictamen": "Pendiente",
						"responsable_bienestar": "bienestar@example.com",
						"responsable_bienestar_nombre": "Marta Bienestar",
					},
					{
						"name": "BEP-2",
						"ficha_empleado": "EMP-2",
						"empleado_nombres": "Luis",
						"empleado_apellidos": "Perez",
						"punto_venta": "PDV-1",
						"punto_venta_nombre": "Portal Norte",
						"fecha_evaluacion": "2026-03-12",
						"estado": "Pendiente",
						"dictamen": "Pendiente",
						"responsable_bienestar": "bienestar@example.com",
						"responsable_bienestar_nombre": "Marta Bienestar",
					},
					{
						"name": "BEP-3",
						"ficha_empleado": "EMP-3",
						"empleado_nombres": "Sara",
						"empleado_apellidos": "Lopez",
						"punto_venta": "PDV-1",
						"punto_venta_nombre": "Portal Norte",
						"fecha_evaluacion": "2026-03-20",
						"estado": "No aprobada",
						"dictamen": "No aprueba",
						"responsable_bienestar": "bienestar@example.com",
						"responsable_bienestar_nombre": "Marta Bienestar",
					},
				]
			if doctype == "Bienestar Alerta":
				return [
					{
						"name": "BAL-1",
						"ficha_empleado": "EMP-1",
						"empleado_nombres": "Ana",
						"empleado_apellidos": "Gomez",
						"punto_venta": "PDV-1",
						"punto_venta_nombre": "Portal Norte",
						"estado": "Abierta",
						"responsable_bienestar": "bienestar@example.com",
						"responsable_bienestar_nombre": "Marta Bienestar",
						"origen_contexto": "seguimiento_ingreso",
						"seguimiento_ingreso": "BSI-1",
						"seguimiento_ingreso_tipo_seguimiento": "5",
						"seguimiento_ingreso_fecha_programada": "2026-03-10",
						"gh_novedad": "GHN-9",
						"gh_novedad_tipo": "Proceso disciplinario",
					},
					{
						"name": "BAL-2",
						"punto_venta": "PDV-1",
						"estado": "En seguimiento",
						"responsable_bienestar": "bienestar@example.com",
					},
					{"name": "BAL-3", "punto_venta": "PDV-1", "estado": "Escalada", "responsable_bienestar": "bienestar@example.com"},
				]
			if doctype == "Bienestar Compromiso":
				return [
					{
						"name": "BCO-1",
						"ficha_empleado": "EMP-2",
						"empleado_nombres": "Luis",
						"empleado_apellidos": "Perez",
						"punto_venta": "PDV-1",
						"punto_venta_nombre": "Portal Norte",
						"origen_contexto": "alerta",
						"alerta": "BAL-1",
						"alerta_tipo_alerta": "Ausentismo recurrente",
						"alerta_prioridad": "Alta",
						"estado": "Activo",
						"sin_mejora": 1,
						"responsable_bienestar": "bienestar@example.com",
						"responsable_bienestar_nombre": "Marta Bienestar",
						"gh_novedad": "GHN-5",
						"gh_novedad_tipo": "Descargos",
					},
					{
						"name": "BCO-2",
						"ficha_empleado": "EMP-3",
						"empleado_nombres": "Sara",
						"empleado_apellidos": "Lopez",
						"punto_venta": "PDV-1",
						"punto_venta_nombre": "Portal Norte",
						"estado": "Escalado RRLL",
						"sin_mejora": 0,
						"responsable_bienestar": "bienestar@example.com",
						"responsable_bienestar_nombre": "Marta Bienestar",
					},
				]
			return []

		with patch("hubgh.hubgh.page.bienestar_bandeja.bienestar_bandeja.frappe.get_roles", return_value=["HR Training & Wellbeing"]), patch(
			"hubgh.hubgh.page.bienestar_bandeja.bienestar_bandeja.nowdate",
			return_value="2026-03-12",
		), patch("hubgh.hubgh.page.bienestar_bandeja.bienestar_bandeja.frappe.get_all", side_effect=_get_all):
			payload = get_bienestar_bandeja(punto_venta="PDV-1", responsable="bienestar@example.com")

		self.assertIn("kpis", payload)
		self.assertIn("colas", payload)
		self.assertIn("meta", payload)
		self.assertIn("seguimientos", payload["colas"])
		self.assertIn("evaluaciones", payload["colas"])
		self.assertIn("alertas", payload["colas"])
		self.assertIn("compromisos", payload["colas"])

		self.assertEqual(payload["kpis"]["seguimientos_vencidos"], 1)
		self.assertEqual(payload["kpis"]["seguimientos_hoy"], 1)
		self.assertEqual(payload["kpis"]["seguimientos_proximos"], 1)
		self.assertEqual(payload["kpis"]["evaluaciones_vencidas"], 1)
		self.assertEqual(payload["kpis"]["evaluaciones_pendientes"], 1)
		self.assertEqual(payload["kpis"]["evaluaciones_no_aprobadas"], 1)
		self.assertEqual(payload["kpis"]["alertas_abiertas"], 1)
		self.assertEqual(payload["kpis"]["alertas_en_seguimiento"], 1)
		self.assertEqual(payload["kpis"]["alertas_escaladas"], 1)
		self.assertEqual(payload["kpis"]["compromisos_activos"], 1)
		self.assertEqual(payload["kpis"]["compromisos_sin_mejora"], 1)
		self.assertEqual(payload["kpis"]["compromisos_escalados_rrll"], 1)
		self.assertEqual(payload["kpis"]["total_vencimientos"], 2)

		seguimiento_vencido = payload["colas"]["seguimientos"]["vencidos"][0]
		self.assertEqual(seguimiento_vencido["empleado_label"], "Ana Gomez")
		self.assertEqual(seguimiento_vencido["punto_venta_label"], "Portal Norte")
		self.assertEqual(seguimiento_vencido["responsable_label"], "Marta Bienestar")
		self.assertEqual(seguimiento_vencido["tipo_resumen"], "Seguimiento 5")
		self.assertEqual(seguimiento_vencido["semaforo_label"], "Sin score")
		self.assertEqual(seguimiento_vencido["semaforo_tone"], "neutral")

		alerta_abierta = payload["colas"]["alertas"]["abiertas"][0]
		self.assertEqual(alerta_abierta["origen_contexto_display"], "Seguimiento ingreso | 5 | 2026-03-10")
		self.assertEqual(alerta_abierta["origen_contexto_secondary"], "BSI-1")
		self.assertEqual(alerta_abierta["rrll_handoff_label"], "Handoff RRLL: Proceso disciplinario")

		compromiso_activo = payload["colas"]["compromisos"]["activos"][0]
		self.assertEqual(compromiso_activo["origen_contexto_display"], "Ausentismo recurrente | Alta")
		self.assertEqual(compromiso_activo["rrll_handoff_label"], "Handoff RRLL: Descargos")

	def test_get_bienestar_bandeja_supports_tipo_filter(self):
		with patch("hubgh.hubgh.page.bienestar_bandeja.bienestar_bandeja.frappe.get_roles", return_value=["HR Training & Wellbeing"]), patch(
			"hubgh.hubgh.page.bienestar_bandeja.bienestar_bandeja.frappe.get_all",
			return_value=[],
		) as get_all_mock:
			payload = get_bienestar_bandeja(tipo="alerta")

		requested = [c.args[0] for c in get_all_mock.call_args_list]
		self.assertEqual(requested, ["Bienestar Alerta"])
		self.assertEqual(payload["kpis"]["total_operativo"], 0)

	def test_gestionar_bienestar_item_updates_state_and_reprograms(self):
		doc = _FakeDoc(name="BSI-9", estado="Pendiente", fecha_programada="2026-03-12")

		with patch("hubgh.hubgh.page.bienestar_bandeja.bienestar_bandeja.frappe.get_roles", return_value=["HR Training & Wellbeing"]), patch(
			"hubgh.hubgh.page.bienestar_bandeja.bienestar_bandeja.frappe.get_doc",
			return_value=doc,
		), patch(
			"hubgh.hubgh.page.bienestar_bandeja.bienestar_bandeja.frappe.session",
			new=SimpleNamespace(user="bienestar@example.com"),
		):
			res = gestionar_bienestar_item(
				tipo="seguimiento",
				item_name="BSI-9",
				nuevo_estado="En gestión",
				gestion_breve="Contacto inicial y reagendamiento",
				reprogramar_fecha="2026-03-18",
			)

		self.assertTrue(res["ok"])
		self.assertEqual(doc.estado, "En gestión")
		self.assertEqual(doc.fecha_programada, "2026-03-18")
		self.assertEqual(len(doc.bitacora), 1)
		self.assertEqual(doc.bitacora[0]["estado_resultante"], "En gestión")
