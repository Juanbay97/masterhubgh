from types import SimpleNamespace
from unittest.mock import Mock, patch

from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate

from hubgh import tasks
from hubgh.hubgh import bienestar_automation
from hubgh.hubgh.doctype.bienestar_compromiso.bienestar_compromiso import BienestarCompromiso
from hubgh.hubgh.doctype.bienestar_evaluacion_periodo_prueba.bienestar_evaluacion_periodo_prueba import (
	BienestarEvaluacionPeriodoPrueba,
)
from hubgh.hubgh.doctype.bienestar_levantamiento_punto.bienestar_levantamiento_punto import BienestarLevantamientoPunto
from hubgh.hubgh.doctype.bienestar_seguimiento_ingreso.bienestar_seguimiento_ingreso import BienestarSeguimientoIngreso
from hubgh import lifecycle


class TestBienestarWorkstream2Automation(FrappeTestCase):
	def test_ensure_ingreso_followups_creates_5_10_30_45(self):
		process = SimpleNamespace(
			name="BPC-0001",
			ficha_empleado="EMP-001",
			punto_venta="PDV-001",
			fecha_ingreso="2026-03-01",
			responsable_bienestar="bienestar@example.com",
		)

		inserted_payloads = []

		def fake_get_doc(payload):
			doc = SimpleNamespace(name=f"BSI-{len(inserted_payloads) + 1}")

			def _insert(ignore_permissions=True):
				inserted_payloads.append(payload)

			doc.insert = _insert
			return doc

		with patch(
			"hubgh.hubgh.bienestar_automation.frappe.db.exists",
			return_value=False,
		), patch("hubgh.hubgh.bienestar_automation.frappe.get_doc", side_effect=fake_get_doc):
			created = bienestar_automation.ensure_ingreso_followups_for_process(process)

		self.assertEqual(created, 4)
		self.assertEqual(len(inserted_payloads), 4)

		tipos = [p["tipo_seguimiento"] for p in inserted_payloads]
		self.assertEqual(tipos, ["5", "10", "30/45", "30/45"])

		momentos = [p.get("momento_consolidacion") for p in inserted_payloads]
		self.assertEqual(momentos, [None, None, "30", "45"])

		expected_dates = [
			add_days(getdate(process.fecha_ingreso), 5),
			add_days(getdate(process.fecha_ingreso), 10),
			add_days(getdate(process.fecha_ingreso), 30),
			add_days(getdate(process.fecha_ingreso), 45),
		]
		self.assertEqual([p["fecha_programada"] for p in inserted_payloads], expected_dates)

	def test_ensure_ingreso_followups_is_deterministic_when_existing(self):
		process = SimpleNamespace(
			name="BPC-0002",
			ficha_empleado="EMP-002",
			fecha_ingreso="2026-03-01",
		)

		with patch(
			"hubgh.hubgh.bienestar_automation.frappe.db.exists",
			return_value=True,
		), patch("hubgh.hubgh.bienestar_automation.frappe.get_doc") as get_doc_mock:
			created = bienestar_automation.ensure_ingreso_followups_for_process(process)

		self.assertEqual(created, 0)
		get_doc_mock.assert_not_called()

	def test_calculate_probation_metrics_sets_dictamen_by_threshold(self):
		metrics_ok = bienestar_automation.calculate_probation_metrics(
			[
				SimpleNamespace(puntaje="3", tipo_respuesta="1-3"),
				SimpleNamespace(puntaje="2", tipo_respuesta="1-3"),
				SimpleNamespace(puntaje="2", tipo_respuesta="1-3"),
			]
		)
		self.assertEqual(metrics_ok["total_score"], 7)
		self.assertEqual(metrics_ok["max_score"], 9)
		self.assertGreaterEqual(metrics_ok["percentage"], 70)
		self.assertEqual(metrics_ok["dictamen"], "APRUEBA")

		metrics_ko = bienestar_automation.calculate_probation_metrics(
			[
				SimpleNamespace(puntaje="3", tipo_respuesta="1-3"),
				SimpleNamespace(puntaje="2", tipo_respuesta="1-3"),
				SimpleNamespace(puntaje="1", tipo_respuesta="1-3"),
			]
		)
		self.assertEqual(metrics_ko["total_score"], 6)
		self.assertEqual(metrics_ko["max_score"], 9)
		self.assertLess(metrics_ko["percentage"], 70)
		self.assertEqual(metrics_ko["dictamen"], "NO APRUEBA")

	def test_calculate_followup_score_supports_mixed_scales(self):
		score = bienestar_automation.calculate_followup_score(
			[
				SimpleNamespace(puntaje="8", tipo_respuesta="1-10", peso=1),
				SimpleNamespace(puntaje="1", tipo_respuesta="Booleano", peso=1),
				SimpleNamespace(puntaje="2", tipo_respuesta="1-3", peso=1),
			]
		)
		self.assertEqual(score, 82.22)

	def test_mark_overdue_only_changes_pending_or_in_progress(self):
		rows = [
			{"name": "BSI-1", "estado": "Pendiente"},
			{"name": "BSI-2", "estado": "En gestión"},
			{"name": "BSI-3", "estado": "Realizado"},
		]

		with patch("hubgh.hubgh.bienestar_automation.frappe.get_all", return_value=rows), patch(
			"hubgh.hubgh.bienestar_automation.frappe.db.set_value"
		) as set_value_mock:
			updated = bienestar_automation.mark_bienestar_followups_overdue("2026-03-16")

		self.assertEqual(updated, 2)
		self.assertEqual(set_value_mock.call_count, 2)
		updated_names = [call.args[1] for call in set_value_mock.call_args_list]
		self.assertEqual(updated_names, ["BSI-1", "BSI-2"])

	def test_create_rrll_escalation_includes_source_traceability(self):
		source = SimpleNamespace(
			doctype="Bienestar Evaluacion Periodo Prueba",
			name="BEP-0001",
			ficha_empleado="EMP-001",
			punto_venta="PDV-001",
			gh_novedad=None,
		)
		captured = {}

		def fake_get_doc(payload):
			captured.update(payload)
			doc = SimpleNamespace(name="GHNOV-0001")
			doc.insert = lambda ignore_permissions=True: None
			return doc

		with patch("hubgh.hubgh.bienestar_automation.frappe.db.exists", return_value=True), patch(
			"hubgh.hubgh.bienestar_automation.frappe.db.get_value",
			return_value=None,
		), patch("hubgh.hubgh.bienestar_automation.frappe.get_doc", side_effect=fake_get_doc):
			novedad = bienestar_automation.create_rrll_escalation_if_needed(
				source,
				should_escalate=True,
				reason="Escalamiento RRLL por evaluación no aprobada",
				fecha_base="2026-03-15",
			)

		self.assertEqual(novedad, "GHNOV-0001")
		self.assertEqual(source.gh_novedad, "GHNOV-0001")
		self.assertEqual(captured["doctype"], "GH Novedad")
		self.assertEqual(captured["cola_destino"], "GH-RRLL")
		self.assertIn("Fuente: Bienestar Evaluacion Periodo Prueba BEP-0001.", captured["descripcion"])

	def test_bienestar_evaluacion_validate_computes_percentage_and_dictamen(self):
		doc = SimpleNamespace(
			fecha_ingreso=None,
			punto_venta=None,
			ficha_empleado="EMP-010",
			dictamen="Pendiente",
			estado="Pendiente",
			respuestas_escala=[
				SimpleNamespace(puntaje="3", tipo_respuesta="1-3"),
				SimpleNamespace(puntaje="2", tipo_respuesta="1-3"),
				SimpleNamespace(puntaje="2", tipo_respuesta="1-3"),
			],
			respuestas_abiertas=[],
			porcentaje_resultado=0,
			requiere_escalamiento_rrll=0,
		)

		with patch(
			"hubgh.hubgh.doctype.bienestar_evaluacion_periodo_prueba.bienestar_evaluacion_periodo_prueba.frappe.db.get_value",
			return_value="PDV-010",
		):
			BienestarEvaluacionPeriodoPrueba.validate(doc)

		self.assertEqual(doc.punto_venta, "PDV-010")
		self.assertGreaterEqual(doc.porcentaje_resultado, 70)
		self.assertEqual(doc.dictamen, "APRUEBA")
		self.assertEqual(doc.requiere_escalamiento_rrll, 0)

	def test_lifecycle_creates_bienestar_followups_for_active_employee_ingreso(self):
		doc = SimpleNamespace(name="EMP-001", estado="Activo", fecha_ingreso="2026-03-15", pdv="PDV-001")

		with patch("hubgh.lifecycle.enrolar_empleado_en_calidad"), patch(
			"hubgh.lifecycle.sync_user_groups_on_employee_change"
		), patch("hubgh.lifecycle.ensure_bienestar_process_for_employee") as ensure_mock:
			lifecycle.on_ficha_empleado_insert(doc)

		ensure_mock.assert_called_once()

	def test_bienestar_followup_validate_autoloads_questionnaire_and_score(self):
		rows_escala = []
		rows_abiertas = []

		doc = SimpleNamespace(
			tipo_seguimiento="10",
			momento_consolidacion=None,
			fecha_ingreso=None,
			punto_venta=None,
			ficha_empleado="EMP-001",
			respuestas_escala=rows_escala,
			respuestas_abiertas=rows_abiertas,
			score_global=0,
		)

		def _append(fieldname, row):
			if fieldname == "respuestas_escala":
				rows_escala.append(SimpleNamespace(**row))
			else:
				rows_abiertas.append(SimpleNamespace(**row))

		doc.append = _append

		with patch(
			"hubgh.hubgh.doctype.bienestar_seguimiento_ingreso.bienestar_seguimiento_ingreso.frappe.db.get_value",
			return_value="PDV-001",
		):
			BienestarSeguimientoIngreso.validate(doc)

		self.assertEqual(doc.punto_venta, "PDV-001")
		self.assertGreater(len(rows_escala), 0)
		self.assertGreater(len(rows_abiertas), 0)
		self.assertEqual(doc.score_global, 0)

	def test_bienestar_levantamiento_validate_restricts_participants_by_point(self):
		doc = SimpleNamespace(
			punto_venta="PDV-001",
			participantes=[
				SimpleNamespace(ficha_empleado="EMP-OK", asistencia=1, puntaje_global="8"),
				SimpleNamespace(ficha_empleado="EMP-BAD", asistencia=1, puntaje_global="9"),
			],
			score_global=0,
			cobertura_participacion=0,
		)

		def fake_get_value(doctype, name, fieldname):
			if doctype == "Ficha Empleado" and name == "EMP-OK":
				return "PDV-001"
			if doctype == "Ficha Empleado" and name == "EMP-BAD":
				return "PDV-999"
			return None

		with patch(
			"hubgh.hubgh.doctype.bienestar_levantamiento_punto.bienestar_levantamiento_punto.frappe.db.get_value",
			side_effect=fake_get_value,
		):
			with self.assertRaises(Exception):
				BienestarLevantamientoPunto.validate(doc)

	def test_bienestar_evaluacion_on_update_is_manual_no_auto_escalation(self):
		doc = SimpleNamespace(dictamen="NO APRUEBA", fecha_evaluacion="2026-03-15")

		res = BienestarEvaluacionPeriodoPrueba.on_update(doc)

		self.assertIsNone(res)

	def test_bienestar_compromiso_on_update_is_manual_no_auto_state_change(self):
		db_set_mock = Mock()
		doc = SimpleNamespace(
			sin_mejora=1,
			fecha_compromiso="2026-03-15",
			estado="En seguimiento",
			db_set=db_set_mock,
		)

		res = BienestarCompromiso.on_update(doc)

		self.assertIsNone(res)
		db_set_mock.assert_not_called()

	def test_daily_task_wrappers_delegate_to_automation(self):
		with patch(
			"hubgh.tasks.generate_ingreso_followups_for_active_employees",
			return_value=4,
		), patch("hubgh.tasks.mark_bienestar_followups_overdue", return_value=2):
			self.assertEqual(tasks.bienestar_generar_seguimientos_ingreso_diarios(), 4)
			self.assertEqual(tasks.bienestar_marcar_vencidos_diario(), 2)

	def test_ensure_followup_questionnaire_for_type_5_loads_expected_questions(self):
		rows_escala = []
		rows_abiertas = []
		doc = SimpleNamespace(
			tipo_seguimiento="5",
			momento_consolidacion=None,
			respuestas_escala=rows_escala,
			respuestas_abiertas=rows_abiertas,
		)
		doc.append = lambda fieldname, row: (
			rows_escala.append(SimpleNamespace(**row)) if fieldname == "respuestas_escala" else rows_abiertas.append(SimpleNamespace(**row))
		)

		bienestar_automation.ensure_followup_questionnaire(doc)

		self.assertEqual(len(rows_escala), 10)  # Q1..Q9 + eNPS
		self.assertGreaterEqual(len(rows_abiertas), 2)
		dims = {r.dimension for r in rows_escala}
		self.assertIn("q3_motivacion", dims)
		self.assertIn("q4_relacion_lider", dims)
		self.assertIn("enps", dims)

	def test_probation_questionnaire_uses_fixed_criteria(self):
		rows_escala = []
		doc = SimpleNamespace(respuestas_escala=rows_escala, respuestas_abiertas=[])
		doc.append = lambda fieldname, row: rows_escala.append(SimpleNamespace(**row)) if fieldname == "respuestas_escala" else None

		bienestar_automation.ensure_probation_questionnaire(doc)

		dims = {r.dimension for r in rows_escala}
		for expected in {
			"conocimiento_del_puesto",
			"cumplimiento_procedimientos",
			"calidad_trabajo",
			"velocidad_aprendizaje",
			"trabajo_equipo",
			"actitud_servicio",
			"responsabilidad",
			"adaptacion_cultura",
		}:
			self.assertIn(expected, dims)

	def test_followups_created_without_proceso_colaborador_dependency(self):
		employee = SimpleNamespace(name="EMP-001", estado="Activo", fecha_ingreso="2026-03-01", pdv="PDV-001", owner="x")
		inserted_payloads = []

		def fake_get_doc(payload):
			doc = SimpleNamespace(name=f"BSI-{len(inserted_payloads) + 1}")
			doc.insert = lambda ignore_permissions=True: inserted_payloads.append(payload)
			return doc

		with patch("hubgh.hubgh.bienestar_automation.frappe.db.exists", return_value=False), patch(
			"hubgh.hubgh.bienestar_automation.frappe.get_doc", side_effect=fake_get_doc
		):
			created = bienestar_automation.ensure_ingreso_followups_for_employee(employee)

		self.assertEqual(created, 4)
		self.assertTrue(all("proceso_colaborador" not in row for row in inserted_payloads))

	def test_followup_questionnaire_template_for_new_ui_preload(self):
		template = bienestar_automation.get_followup_questionnaire_template("30/45", "45")

		self.assertEqual(template["key"], "30/45-45")
		self.assertGreater(len(template["escala"]), 0)
		self.assertGreater(len(template["abiertas"]), 0)
		dims = {row["dimension"] for row in template["escala"]}
		self.assertIn("autonomia", dims)
		self.assertIn("riesgos_criticos", dims)

	def test_probation_questionnaire_template_for_new_ui_preload(self):
		template = bienestar_automation.get_probation_questionnaire_template()

		self.assertGreaterEqual(len(template["escala"]), 8)
		self.assertGreaterEqual(len(template["abiertas"]), 3)
		dims = {row["dimension"] for row in template["escala"]}
		self.assertIn("conocimiento_del_puesto", dims)
		self.assertIn("adaptacion_cultura", dims)
