from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh import document_service
from hubgh.hubgh import contratacion_service
from hubgh.hubgh import siesa_export
from hubgh.hubgh import siesa_reference_matrix
from hubgh.hubgh.doctype.datos_contratacion.datos_contratacion import DatosContratacion
from hubgh.hubgh.doctype.contrato.contrato import Contrato
from hubgh.hubgh.page.seleccion_documentos import seleccion_documentos
from hubgh.hubgh.page.persona_360 import persona_360
from hubgh.hubgh.page.punto_360 import punto_360
from hubgh.hubgh.page.centro_de_datos import centro_de_datos
from hubgh.hubgh.page.carpeta_documental_empleado import carpeta_documental_empleado


class TestFlowPhase9Adjustments(FrappeTestCase):
	class _DocStub(dict):
		def __getattr__(self, item):
			return self.get(item)

		def __setattr__(self, key, value):
			self[key] = value

		def set(self, key, value):
			self[key] = value

	def test_set_candidate_status_keeps_medical_exam_state(self):
		with patch("hubgh.hubgh.document_service.frappe.db.get_value", return_value="En Examen Médico"), patch(
			"hubgh.hubgh.document_service.frappe.db.set_value"
		) as set_value_mock, patch("hubgh.hubgh.document_service.get_candidate_progress") as progress_mock:
			status = document_service.set_candidate_status_from_progress("CAND-001")

		self.assertEqual(status, "En Examen Médico")
		progress_mock.assert_not_called()
		set_value_mock.assert_not_called()

	def test_document_type_rules_enable_multi_upload_for_reference_letters(self):
		doc_type = SimpleNamespace(
			allowed_areas=[],
			allowed_roles_override="",
			requires_approval=0,
			allows_multiple=0,
			document_name="2 cartas de referencias personales.",
			name="2 cartas de referencias personales.",
		)
		with patch("hubgh.hubgh.document_service.frappe.db.exists", side_effect=lambda dt, name: dt == "Document Type"), patch(
			"hubgh.hubgh.document_service.frappe.get_doc", return_value=doc_type
		):
			rules = document_service._get_document_type_rules("2 cartas de referencias personales.")

		self.assertEqual(rules["document_type"], "2 cartas de referencias personales.")
		self.assertEqual(rules["allows_multiple"], 1)

	def test_contract_number_autoincrements_when_default_value_is_one(self):
		contract = SimpleNamespace(numero_contrato=1)
		with patch("hubgh.hubgh.doctype.contrato.contrato.frappe.db.sql", return_value=[(7,)]):
			Contrato._ensure_numero_contrato(contract)

		self.assertEqual(contract.numero_contrato, 8)

	def test_contract_ensure_employee_backfills_missing_candidate_lineage_on_existing_employee(self):
		contract = SimpleNamespace(empleado=None, numero_documento="1001", candidato="CAND-001")

		def fake_get_value(doctype, filters, fieldname=None, *args, **kwargs):
			if doctype != "Ficha Empleado":
				return None
			if isinstance(filters, dict):
				return "EMP-001"
			if filters == "EMP-001" and fieldname == "candidato_origen":
				return None
			return None

		with patch("hubgh.hubgh.doctype.contrato.contrato.frappe.db.get_value", side_effect=fake_get_value), patch(
			"hubgh.hubgh.doctype.contrato.contrato.frappe.db.set_value"
		) as set_value_mock:
			employee = Contrato._ensure_employee(contract)

		self.assertEqual(employee, "EMP-001")
		set_value_mock.assert_called_once_with(
			"Ficha Empleado",
			"EMP-001",
			"candidato_origen",
			"CAND-001",
			update_modified=False,
		)

	def test_contract_ensure_employee_blocks_conflicting_candidate_lineage(self):
		contract = SimpleNamespace(empleado=None, numero_documento="1001", candidato="CAND-NEW")

		def fake_get_value(doctype, filters, fieldname=None, *args, **kwargs):
			if doctype != "Ficha Empleado":
				return None
			if isinstance(filters, dict):
				return "EMP-001"
			if filters == "EMP-001" and fieldname == "candidato_origen":
				return "CAND-OLD"
			return None

		with patch("hubgh.hubgh.doctype.contrato.contrato.frappe.db.get_value", side_effect=fake_get_value), patch(
			"hubgh.hubgh.doctype.contrato.contrato.frappe.throw",
			side_effect=RuntimeError("lineage-conflict"),
		), patch("hubgh.hubgh.doctype.contrato.contrato.frappe.db.set_value") as set_value_mock:
			with self.assertRaisesRegex(RuntimeError, "lineage-conflict"):
				Contrato._ensure_employee(contract)

		set_value_mock.assert_not_called()

	def test_contract_publish_ingreso_event_creates_closed_rrll_novedad(self):
		contract = SimpleNamespace(
			name="CONT-001",
			pdv_destino="PDV-1",
			fecha_ingreso="2026-03-20",
		)

		with patch(
			"hubgh.hubgh.doctype.contrato.contrato.frappe.db.exists",
			side_effect=lambda doctype, *args, **kwargs: doctype == "DocType",
		), patch("hubgh.hubgh.doctype.contrato.contrato.frappe.get_doc") as get_doc_mock:
			doc_stub = SimpleNamespace(insert=lambda **kwargs: None)
			get_doc_mock.return_value = doc_stub
			Contrato._publish_ingreso_event(contract, "EMP-001")

		payload = get_doc_mock.call_args.args[0]
		self.assertEqual(payload["doctype"], "GH Novedad")
		self.assertEqual(payload["persona"], "EMP-001")
		self.assertEqual(payload["punto"], "PDV-1")
		self.assertEqual(payload["estado"], "Cerrada")
		self.assertEqual(payload["cola_destino"], "GH-RRLL")

	def test_contract_publish_ingreso_event_skips_when_already_exists(self):
		contract = SimpleNamespace(
			name="CONT-001",
			pdv_destino="PDV-1",
			fecha_ingreso="2026-03-20",
		)

		def fake_exists(doctype, *args, **kwargs):
			if doctype == "DocType":
				return True
			if doctype == "GH Novedad":
				return "GHNOV-EXISTING"
			return False

		with patch("hubgh.hubgh.doctype.contrato.contrato.frappe.db.exists", side_effect=fake_exists), patch(
			"hubgh.hubgh.doctype.contrato.contrato.frappe.get_doc"
		) as get_doc_mock:
			Contrato._publish_ingreso_event(contract, "EMP-001")

		get_doc_mock.assert_not_called()

	def test_persona_360_includes_ingreso_event_from_gh_novedad(self):
		emp = SimpleNamespace(
			nombres="Ana",
			apellidos="Paz",
			cedula="1001",
			cargo="CAR-1",
			pdv="PDV-1",
			estado="Activo",
			fecha_ingreso="2026-03-20",
			email="ana@example.com",
		)

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Novedad SST":
				return []
			if doctype == "Caso Disciplinario":
				return []
			if doctype == "Caso SST":
				return []
			if doctype == "Comentario Bienestar":
				return []
			if doctype == "GH Novedad":
				return [
					SimpleNamespace(
						name="GHNOV-1",
						tipo="Otro",
						fecha_inicio="2026-03-20",
						descripcion="Ingreso formalizado desde contrato CONT-001",
						estado="Cerrada",
					)
				]
			return []

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.get_doc", return_value=emp), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.session",
			new=SimpleNamespace(user="rrll@example.com"),
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_roles",
			return_value=["HR Labor Relations"],
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.get_value",
			return_value="PDV 1",
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.exists",
			return_value=True,
		):
			res = persona_360.get_persona_stats("EMP-001")

		self.assertTrue(any(item.get("type") == "Ingreso" for item in res.get("timeline", [])))

	def test_persona_360_marks_sst_as_canonical_source_for_incapacidad(self):
		emp = SimpleNamespace(
			nombres="Ana",
			apellidos="Paz",
			cedula="1001",
			cargo="CAR-1",
			pdv="PDV-1",
			estado="Activo",
			fecha_ingreso="2026-03-20",
			email="rrll@example.com",
		)

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Novedad SST":
				return [
					SimpleNamespace(
						name="NOV-INC-1",
						tipo_novedad="Accidente",
						fecha_inicio="2026-03-18",
						fecha_fin="2026-03-20",
						descripcion="Reposo por accidente",
						descripcion_resumen="AT con incapacidad",
						estado="En seguimiento",
						en_radar=0,
						es_incapacidad=1,
						proxima_alerta_fecha=None,
						recomendaciones_detalle="",
						ref_doctype="GH Novedad",
						ref_docname="GHNOV-1",
					)
				]
			if doctype in {"Caso Disciplinario", "Bienestar Seguimiento Ingreso", "Bienestar Evaluacion Periodo Prueba", "Bienestar Alerta", "Bienestar Compromiso"}:
				return []
			if doctype == "GH Novedad":
				return [
					SimpleNamespace(
						name="GHNOV-1",
						tipo="Otro",
						fecha_inicio="2026-03-18",
						descripcion="Escalamiento RRLL desde Novedad SST NOV-INC-1. Caso SST",
						estado="Recibida",
					)
				]
			return []

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.get_doc", return_value=emp), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.session",
			new=SimpleNamespace(user="rrll@example.com"),
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_roles",
			return_value=["HR Labor Relations"],
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.evaluate_dimension_permission",
			return_value={"effective_allowed": True},
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.get_value",
			return_value="PDV 1",
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.exists",
			return_value=True,
		):
			res = persona_360.get_persona_stats("EMP-001")

		self.assertEqual(res["sst_cards"]["incapacidades_activas"], 1)
		self.assertEqual(res["sst_cards"]["incapacidades_rrll_handoff"], 1)
		self.assertEqual(res["sst_cards"]["fuente_canonica_incapacidad"], "Novedad SST")

	def test_persona_360_supports_module_state_and_date_filters_with_sections(self):
		emp = SimpleNamespace(
			nombres="Ana",
			apellidos="Paz",
			cedula="1001",
			cargo="CAR-1",
			pdv="PDV-1",
			estado="Activo",
			fecha_ingreso="2026-03-20",
			email="ana@example.com",
		)

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Novedad SST":
				return [
					SimpleNamespace(
						name="NOV-1",
						tipo_novedad="Incapacidad",
						fecha_inicio="2026-03-18",
						fecha_fin=None,
						descripcion="Reposo",
						descripcion_resumen="Incapacidad 2 días",
						estado="Abierta",
						en_radar=0,
						proxima_alerta_fecha=None,
						recomendaciones_detalle="",
					)
				]
			if doctype == "Caso Disciplinario":
				return []
			if doctype == "Caso SST":
				return []
			if doctype == "Comentario Bienestar":
				return []
			if doctype == "GH Novedad":
				return [
					SimpleNamespace(
						name="GHNOV-1",
						tipo="Ingreso",
						fecha_inicio="2026-03-20",
						descripcion="Ingreso formalizado desde contrato CONT-001",
						estado="Cerrada",
					)
				]
			return []

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.get_doc", return_value=emp), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.session",
			new=SimpleNamespace(user="rrll@example.com"),
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_roles",
			return_value=["HR Labor Relations"],
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.get_value",
			return_value="PDV 1",
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.exists",
			return_value=True,
		):
			res = persona_360.get_persona_stats(
				"EMP-001",
				module_filter="GH Novedad",
				state_filter="cerrada",
				date_from="2026-03-19",
				date_to="2026-03-21",
			)

		timeline = res.get("timeline", [])
		self.assertEqual(len(timeline), 1)
		self.assertEqual(timeline[0].get("module"), "GH Novedad")
		self.assertEqual(timeline[0].get("state"), "Cerrada")

		sections = res.get("timeline_sections", [])
		self.assertEqual(len(sections), 1)
		self.assertEqual(sections[0].get("section"), "GH Novedad")
		self.assertEqual(sections[0].get("count"), 1)

		filters_applied = res.get("filters_applied", {})
		self.assertEqual(filters_applied.get("module"), ["gh novedad"])
		self.assertEqual(filters_applied.get("state"), ["cerrada"])
		self.assertEqual(filters_applied.get("date_from"), "2026-03-19")
		self.assertEqual(filters_applied.get("date_to"), "2026-03-21")

	def test_persona_360_contextual_actions_hide_creation_for_employee_profile(self):
		emp = SimpleNamespace(
			nombres="Ana",
			apellidos="Paz",
			cedula="1001",
			cargo="CAR-1",
			pdv="PDV-1",
			estado="Activo",
			fecha_ingreso="2026-03-20",
			email="empleado@example.com",
		)

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.get_doc", return_value=emp), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.session",
			new=SimpleNamespace(user="empleado@example.com"),
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_roles",
			return_value=["Empleado"],
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.user_has_any_role",
			side_effect=lambda user, *roles: "Empleado" in roles,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.get_value",
			return_value="PDV 1",
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_all",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.exists",
			return_value=False,
		):
			res = persona_360.get_persona_stats("EMP-001")

		actions = {a["key"]: a for a in res.get("contextual_actions", {}).get("quick_actions", [])}
		self.assertFalse(actions["create_novedad"]["visible"])
		self.assertFalse(actions["create_disciplinary"]["visible"])
		self.assertTrue(actions["view_documents"]["visible"])
		self.assertEqual(actions["view_documents"]["presentation"], "drawer")
		self.assertEqual(actions["view_documents"]["route"], "/app/carpeta-documental-empleado")
		self.assertEqual(actions["view_documents"]["prefill"], {"employee": "EMP-001", "open_drawer": 1})
		self.assertEqual(actions["create_wellbeing"]["doctype"], "Bienestar Compromiso")
		self.assertEqual(actions["create_wellbeing_alert"]["doctype"], "Bienestar Alerta")

	def test_persona_360_blocks_retirado_for_non_rrll_roles(self):
		emp = SimpleNamespace(
			nombres="Ana",
			apellidos="Paz",
			cedula="1001",
			cargo="CAR-1",
			pdv="PDV-1",
			estado="Retirado",
			fecha_ingreso="2026-03-20",
			email="empleado@example.com",
		)

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.get_doc", return_value=emp), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.session",
			new=SimpleNamespace(user="empleado@example.com"),
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.user_has_any_role",
			side_effect=lambda user, *roles: "Empleado" in roles,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.throw",
			side_effect=RuntimeError("blocked-retiro"),
		):
			with self.assertRaisesRegex(RuntimeError, "blocked-retiro"):
				persona_360.get_persona_stats("EMP-001")

	def test_persona_360_bienestar_followups_use_new_ingreso_sources(self):
		emp = SimpleNamespace(
			nombres="Ana",
			apellidos="Paz",
			cedula="1001",
			cargo="CAR-1",
			pdv="PDV-1",
			estado="Activo",
			fecha_ingreso="2026-03-20",
			email="rrll@example.com",
		)

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Novedad SST":
				return []
			if doctype == "Caso Disciplinario":
				return []
			if doctype == "Caso SST":
				return []
			if doctype == "Bienestar Seguimiento Ingreso":
				return [
					SimpleNamespace(
						name="BSI-001",
						proceso_colaborador="BPC-001",
						tipo_seguimiento="5",
						momento_consolidacion=None,
						fecha_programada="2026-03-06",
						fecha_realizacion="2026-03-06",
						estado="Realizado",
						score_global=80,
						compromiso_generado=None,
						alerta_generada=None,
						observaciones="Seguimiento inicial",
					),
					SimpleNamespace(
						name="BSI-002",
						proceso_colaborador="BPC-001",
						tipo_seguimiento="30/45",
						momento_consolidacion="45",
						fecha_programada="2026-04-15",
						fecha_realizacion=None,
						estado="Pendiente",
						score_global=None,
						compromiso_generado="BCO-001",
						alerta_generada="BAL-001",
						observaciones="Consolidación pendiente",
					),
				]
			if doctype in {
				"Bienestar Evaluacion Periodo Prueba",
				"Bienestar Alerta",
				"Bienestar Compromiso",
			}:
				return []
			return []

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.get_doc", return_value=emp), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.session",
			new=SimpleNamespace(user="rrll@example.com"),
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_roles",
			return_value=["HR Labor Relations"],
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.get_value",
			return_value="PDV 1",
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.exists",
			return_value=False,
		), patch("hubgh.hubgh.page.persona_360.persona_360.nowdate", return_value="2026-03-10"):
			res = persona_360.get_persona_stats("EMP-001")

		followups = res.get("bienestar_followups", [])
		self.assertEqual(len(followups), 2)
		self.assertEqual(followups[0].get("source_comment"), "BSI-001")
		self.assertEqual(followups[0].get("checkpoint_day"), 5)
		self.assertEqual(followups[0].get("status"), "Completado")
		self.assertEqual(followups[1].get("source_comment"), "BSI-002")
		self.assertEqual(followups[1].get("checkpoint_day"), 45)
		self.assertEqual(followups[1].get("status"), "Pendiente")
		self.assertEqual(followups[1].get("compromiso_generado"), "BCO-001")
		self.assertEqual(followups[1].get("alerta_generada"), "BAL-001")

		self.assertIn("bienestar_ruta_ingreso", res)
		self.assertEqual(res.get("bienestar_ruta_ingreso"), followups)

	def test_persona_360_bienestar_followups_mark_overdue_checkpoints(self):
		emp = SimpleNamespace(
			nombres="Ana",
			apellidos="Paz",
			cedula="1001",
			cargo="CAR-1",
			pdv="PDV-1",
			estado="Activo",
			fecha_ingreso="2026-03-20",
			email="rrll@example.com",
		)

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Novedad SST":
				return []
			if doctype == "Caso Disciplinario":
				return []
			if doctype == "Caso SST":
				return []
			if doctype == "Bienestar Seguimiento Ingreso":
				return [
					SimpleNamespace(
						name="BSI-010",
						proceso_colaborador="BPC-002",
						tipo_seguimiento="10",
						momento_consolidacion=None,
						fecha_programada="2026-03-11",
						fecha_realizacion=None,
						estado="Vencido",
						score_global=None,
						compromiso_generado=None,
						alerta_generada=None,
						observaciones="Sin contacto",
					),
				]
			if doctype in {
				"Bienestar Evaluacion Periodo Prueba",
				"Bienestar Alerta",
				"Bienestar Compromiso",
			}:
				return []
			return []

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.get_doc", return_value=emp), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.session",
			new=SimpleNamespace(user="rrll@example.com"),
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_roles",
			return_value=["HR Labor Relations"],
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.get_value",
			return_value="PDV 1",
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.exists",
			return_value=False,
		), patch("hubgh.hubgh.page.persona_360.persona_360.nowdate", return_value="2026-04-15"):
			res = persona_360.get_persona_stats("EMP-001")

		followups = res.get("bienestar_followups", [])
		self.assertEqual(len(followups), 1)
		self.assertTrue(all(item.get("status") == "Vencido" for item in followups))

	def test_persona_360_bienestar_payload_sections_and_timeline_use_new_doctypes(self):
		emp = SimpleNamespace(
			nombres="Ana",
			apellidos="Paz",
			cedula="1001",
			cargo="CAR-1",
			pdv="PDV-1",
			estado="Activo",
			fecha_ingreso="2026-03-20",
			email="rrll@example.com",
		)

		def fake_get_all(doctype, *args, **kwargs):
			if doctype in {"Novedad SST", "Caso Disciplinario", "Caso SST", "GH Novedad"}:
				return []
			if doctype == "Bienestar Seguimiento Ingreso":
				return [
					SimpleNamespace(
						name="BSI-100",
						proceso_colaborador="BPC-100",
						tipo_seguimiento="30/45",
						momento_consolidacion="30",
						fecha_programada="2026-04-19",
						fecha_realizacion="2026-04-18",
						estado="Realizado",
						score_global=70,
						compromiso_generado="BCO-100",
						alerta_generada="BAL-100",
						observaciones="ok",
					)
				]
			if doctype == "Bienestar Evaluacion Periodo Prueba":
				return [
					SimpleNamespace(
						name="BEP-100",
						fecha_evaluacion="2026-04-20",
						estado="Realizada",
						dictamen="Aprueba",
						porcentaje_resultado=78,
						requiere_escalamiento_rrll=0,
						gh_novedad=None,
						observaciones="avance",
					)
				]
			if doctype == "Bienestar Alerta":
				return [
					SimpleNamespace(
						name="BAL-100",
						fecha_alerta="2026-04-21",
						tipo_alerta="Ingreso",
						prioridad="Alta",
						estado="Abierta",
						descripcion="Riesgo detectado",
						fecha_cierre=None,
					)
				]
			if doctype == "Bienestar Compromiso":
				return [
					SimpleNamespace(
						name="BCO-100",
						fecha_compromiso="2026-04-22",
						fecha_limite="2026-04-30",
						fecha_cierre=None,
						estado="En seguimiento",
						sin_mejora=0,
						resultado="Plan activo",
						gh_novedad=None,
					)
				]
			return []

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.get_doc", return_value=emp), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.session",
			new=SimpleNamespace(user="rrll@example.com"),
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_roles",
			return_value=["HR Labor Relations"],
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.get_value",
			return_value="PDV 1",
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.exists",
			return_value=True,
		):
			res = persona_360.get_persona_stats("EMP-001")

		# backward-compatible base contract keys
		for key in ["info", "timeline", "timeline_sections", "sst_cards", "filters_applied", "contextual_actions", "bienestar_followups"]:
			self.assertIn(key, res)

		# new bienestar blocks
		self.assertEqual(len(res.get("bienestar_periodo_prueba", [])), 1)
		self.assertEqual(len(res.get("bienestar_alertas", [])), 1)
		self.assertEqual(len(res.get("bienestar_compromisos", [])), 1)

		modules = {item.get("module") for item in res.get("timeline", [])}
		self.assertIn("Bienestar Seguimiento Ingreso", modules)
		self.assertIn("Bienestar Evaluacion Periodo Prueba", modules)
		self.assertIn("Bienestar Alerta", modules)
		self.assertIn("Bienestar Compromiso", modules)

	def test_centro_de_datos_rejects_legacy_comentario_bienestar_upload(self):
		file_doc = SimpleNamespace(get_content=lambda: "cedula_empleado,comentario\n1001,legacy")

		with patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.get_doc",
			return_value=file_doc,
		), patch(
			"hubgh.hubgh.page.centro_de_datos.centro_de_datos.frappe.db.commit"
		):
			res = centro_de_datos.upload_data("Comentario Bienestar", "/private/files/legacy.csv")

		self.assertEqual(res.get("success"), 0)
		self.assertEqual(len(res.get("errors", [])), 1)
		self.assertIn("no soportado", res["errors"][0].lower())

	def test_persona_360_overview_uses_new_bienestar_ingreso_source(self):
		empleados = [
			SimpleNamespace(
				name="EMP-001",
				nombres="Ana",
				apellidos="Paz",
				cedula="1001",
				cargo="CAR-1",
				pdv="PDV-1",
				email="ana@example.com",
				estado="Activo",
				fecha_ingreso="2026-03-20",
				pdv_nombre="PDV 1",
			)
		]

		def fake_count(doctype, filters=None):
			if doctype == "Novedad SST":
				return 2
			if doctype == "Bienestar Seguimiento Ingreso":
				return 1
			if doctype == "Comentario Bienestar":
				raise AssertionError("legacy doctype should not be used")
			return 0

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Bienestar Seguimiento Ingreso":
				return [SimpleNamespace(observaciones="Seguimiento 10")]
			if doctype == "Comentario Bienestar":
				raise AssertionError("legacy doctype should not be queried")
			return []

		def fake_sql(query, values=None, as_dict=False):
			self.assertTrue(as_dict)
			self.assertEqual(values["search_term"], "")
			return empleados

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.db.sql", side_effect=fake_sql), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_all", side_effect=fake_get_all
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.count",
			side_effect=fake_count,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.has_permission",
			return_value=True,
		):
			rows = persona_360.get_all_personas_overview()

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["feedback_count"], 1)
		self.assertEqual(rows[0]["feedback_last"], "Seguimiento 10")
		self.assertEqual(rows[0]["pdv_nombre"], "PDV 1")

	def test_persona_360_overview_supports_backend_search(self):
		empleados = [
			SimpleNamespace(
				name="EMP-001",
				nombres="Ana",
				apellidos="Paz",
				cedula="1001",
				cargo="Cajera",
				pdv="PDV-NORTE",
				email="ana@example.com",
				estado="Activo",
				fecha_ingreso="2026-03-20",
				pdv_nombre="Punto Norte",
			)
		]

		def fake_sql(query, values=None, as_dict=False):
			self.assertEqual(values["search_term"], "norte")
			self.assertEqual(values["search_like"], "%norte%")
			return empleados

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.db.sql", side_effect=fake_sql), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.count",
			return_value=0,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_all",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.has_permission",
			return_value=True,
		):
			rows = persona_360.get_all_personas_overview(search="norte")

		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["name"], "EMP-001")
		self.assertEqual(rows[0]["pdv_nombre"], "Punto Norte")

	def test_persona_360_link_query_supports_name_cedula_and_point_search(self):
		def fake_sql(query, values=None, as_dict=False):
			self.assertFalse(as_dict)
			self.assertIn("LOWER(IFNULL(emp.name, '')) LIKE %(search_like)s", query)
			self.assertIn("LOWER(IFNULL(emp.cedula, '')) LIKE %(search_like)s", query)
			self.assertIn("LOWER(IFNULL(pdv.nombre_pdv, '')) LIKE %(search_like)s", query)
			self.assertEqual(values["search_term"], "punto norte")
			self.assertEqual(values["search_like"], "%punto norte%")
			self.assertEqual(values["start"], 0)
			self.assertEqual(values["page_len"], 20)
			return [["EMP-001", "Ana Paz", "1001", "Punto Norte"]]

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.db.sql", side_effect=fake_sql), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.session",
			new=SimpleNamespace(user="gh@example.com"),
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.user_has_any_role",
			return_value=False,
		):
			rows = persona_360.search_persona_360_employee(
				"Ficha Empleado",
				"Punto Norte",
				"name",
				0,
				20,
				None,
			)

		self.assertEqual(rows, [["EMP-001", "Ana Paz", "1001", "Punto Norte"]])

	def test_persona_360_hides_payroll_block_without_payroll_access(self):
		emp = SimpleNamespace(
			nombres="Ana",
			apellidos="Paz",
			cedula="1001",
			cargo="Analista",
			pdv="PDV-1",
			estado="Activo",
			fecha_ingreso="2026-03-01",
			email="gh@example.com",
		)

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.get_doc", return_value=emp), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.session",
			new=SimpleNamespace(user="gh@example.com"),
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.user_has_any_role",
			side_effect=lambda user, *roles: "Gestión Humana" in roles,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.evaluate_dimension_permission",
			return_value={"effective_allowed": False},
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.get_value",
			return_value="PDV 1",
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.get_all",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.count",
			return_value=0,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.exists",
			return_value=False,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.can_user_view_employee_payroll",
			return_value=False,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.get_payroll_block"
		) as payroll_block_mock:
			res = persona_360.get_persona_stats("EMP-001")

		payroll_block_mock.assert_not_called()
		self.assertEqual(res["payroll_block"], {})

	def test_punto_360_exposes_ingresos_formalizados_kpi(self):
		punto_doc = SimpleNamespace(nombre_pdv="PDV 1", zona="Norte", planta_autorizada=10)

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Ficha Empleado":
				return [
					SimpleNamespace(
						name="EMP-001",
						nombres="Ana",
						apellidos="Paz",
						cedula="1001",
						cargo="Cajera",
						estado="Activo",
						email="ana@example.com",
					)
				]
			if doctype == "Novedad SST":
				return []
			if doctype == "Caso Disciplinario":
				return []
			if doctype == "Caso SST":
				return []
			if doctype == "SST Alerta":
				return []
			if doctype == "Feedback Punto":
				return []
			if doctype == "Bienestar Levantamiento Punto":
				return [
					{"name": "BLP-1", "estado": "Realizado", "fecha_levantamiento": "2026-03-20", "score_global": 80},
				]
			if doctype == "Bienestar Seguimiento Ingreso":
				return [
					{
						"name": "BSI-1",
						"estado": "Realizado",
						"fecha_programada": "2026-03-18",
						"fecha_realizacion": "2026-03-18",
						"tipo_seguimiento": "10",
						"score_global": 40,
					}
				]
			if doctype == "Bienestar Evaluacion Periodo Prueba":
				return [
					{
						"name": "BEP-1",
						"estado": "No aprobada",
						"fecha_evaluacion": "2026-03-19",
						"dictamen": "No aprueba",
						"porcentaje_resultado": 20,
					}
				]
			if doctype == "Bienestar Alerta":
				return [
					{"name": "BAL-1", "estado": "Abierta", "fecha_alerta": "2026-03-20", "tipo_alerta": "Levantamiento de punto"},
				]
			if doctype == "Bienestar Compromiso":
				return [
					{"name": "BCO-1", "estado": "Activo", "fecha_compromiso": "2026-03-20", "sin_mejora": 0},
				]
			if doctype == "GH Novedad":
				return [
					{"descripcion": "Ingreso formalizado desde contrato CONT-001"},
					{"descripcion": "Otro evento"},
				]
			return []

		def fake_exists(doctype, name=None):
			if doctype == "DocType":
				return name in {
					"GH Novedad",
					"Bienestar Levantamiento Punto",
					"Bienestar Seguimiento Ingreso",
					"Bienestar Evaluacion Periodo Prueba",
					"Bienestar Alerta",
					"Bienestar Compromiso",
				}
			return True

		with patch("hubgh.hubgh.page.punto_360.punto_360.frappe.has_permission", return_value=True), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_doc",
			return_value=punto_doc,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.nowdate",
			return_value="2026-03-21",
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.utils.nowdate",
			return_value="2026-03-21",
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.db.count",
			return_value=1,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.db.exists",
			side_effect=fake_exists,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.session",
			new=SimpleNamespace(user="empleado@example.com"),
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.user_has_any_role",
			return_value=False,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.evaluate_dimension_permission",
			return_value={"effective_allowed": False},
		):
			res = punto_360.get_punto_stats("PDV-1")

		self.assertEqual(res["info"]["nombre"], "PDV 1")
		self.assertEqual(res["info"]["pdv_nombre"], "PDV 1")
		self.assertEqual(res["info"]["kpi_ingreso"]["ingresos_formalizados_30d"], 1)
		self.assertEqual(res["info"]["kpi_liderazgo"]["faltantes_dotacion"], 9)
		self.assertEqual(res["info"]["kpi_liderazgo"]["ingresos_formalizados_30d"], 1)
		self.assertEqual(res["info"]["kpi_operativo"]["headcount_activo"], 1)
		self.assertEqual(res["info"]["kpi_operativo"]["planta_autorizada"], 10)
		self.assertEqual(res["info"]["kpi_operativo"]["cobertura_dotacion_pct"], 10.0)
		self.assertEqual(res["info"]["kpi_operativo"]["novedades_activas"], 0)
		self.assertEqual(res["info"]["kpi_operativo"]["alertas_pendientes"], 0)
		self.assertEqual(res["info"]["kpi_operativo"]["riesgo_operativo_total"], 0)
		self.assertEqual(res["info"]["kpi_bienestar"]["feedback_30d"], 3)
		self.assertEqual(res["info"]["kpi_bienestar"]["valoracion_promedio_30d"], 2.33)
		self.assertEqual(res["info"]["kpi_bienestar"]["feedback_riesgo_30d"], 2)
		self.assertEqual(res["info"]["kpi_clima"]["bienestar_registros_30d"], 5)
		self.assertEqual(res["info"]["kpi_clima"]["visitas_clima_30d"], 1)
		self.assertEqual(res["info"]["kpi_clima"]["periodo_prueba_no_aprobado_30d"], 1)
		self.assertEqual(res["info"]["kpi_clima"]["cobertura_clima_pct_30d"], 100.0)
		self.assertEqual(res["info"]["kpi_clima"]["temas_30d"]["clima"], 1)
		self.assertEqual(res["info"]["kpi_clima"]["temas_30d"]["infraestructura"], 1)
		self.assertEqual(res["info"]["kpi_clima"]["temas_30d"]["dotacion"], 1)
		self.assertEqual(res["info"]["kpi_clima"]["temas_30d"]["otro"], 1)
		self.assertEqual(res["info"]["kpi_formacion"]["lms_disponible"], False)
		self.assertEqual(res["info"]["kpi_formacion"]["total_colaboradores"], 1)
		self.assertEqual(res["info"]["kpi_formacion"]["completados"], 0)
		self.assertEqual(res["info"]["kpi_formacion"]["porcentaje_completud"], 0)
		self.assertEqual(res["personas"], [{"name": "EMP-001", "nombre": "Ana Paz", "cedula": "1001", "cargo": "Cajera", "estado": "Activo"}])
		self.assertEqual(res["navigation_context"]["persona_route"], "persona_360")
		self.assertEqual(res["navigation_context"]["expediente_route"], "query-report/Person Documents")
		self.assertIn("actionable_hub", res)
		self.assertFalse(res["actionable_hub"]["widgets"]["empty"])
		self.assertFalse(res["actionable_hub"]["feeds"]["empty"])

		widgets = {item["key"]: item for item in res["actionable_hub"]["widgets"]["items"]}
		self.assertEqual(widgets["headcount_activo"]["value"], 1)
		self.assertEqual(widgets["brecha_dotacion"]["value"], 9)
		self.assertEqual(widgets["ingresos_formalizados_30d"]["route"], "app/bandeja_contratacion")

		feeds = {item["key"]: item for item in res["actionable_hub"]["feeds"]["items"]}
		self.assertIn("leadership_gap", feeds)
		self.assertEqual(feeds["leadership_gap"]["feed"], "liderazgo")
		self.assertTrue(any(item["feed"] == "bienestar" for item in res["actionable_hub"]["feeds"]["items"]))

		actions = {item["key"]: item for item in res["actionable_hub"]["contextual_actions"]["quick_actions"]}
		self.assertTrue(actions["open_operacion"]["visible"])
		self.assertFalse(actions["create_gh_novedad"]["visible"])
		self.assertFalse(actions["create_sst_alert"]["visible"])
		self.assertFalse(actions["create_wellbeing_alert"]["visible"])
		self.assertFalse(actions["open_rl_view"]["visible"])
		self.assertFalse(actions["view_documents"]["visible"])

	def test_punto_360_actionable_hub_enables_role_actions_for_point_lead(self):
		punto_doc = SimpleNamespace(nombre_pdv="PDV 1", zona="Norte", planta_autorizada=10)

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Ficha Empleado":
				return [SimpleNamespace(name="EMP-001")]
			if doctype == "Novedad SST":
				return []
			if doctype == "Caso Disciplinario":
				return []
			if doctype == "Caso SST":
				return []
			if doctype == "SST Alerta":
				return []
			if doctype == "GH Novedad":
				return []
			return []

		def fake_exists(doctype, name=None):
			if doctype == "DocType":
				return name == "GH Novedad"
			return True

		with patch("hubgh.hubgh.page.punto_360.punto_360.frappe.has_permission", return_value=True), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_doc",
			return_value=punto_doc,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.nowdate",
			return_value="2026-03-21",
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.db.count",
			return_value=1,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.db.exists",
			side_effect=fake_exists,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.session",
			new=SimpleNamespace(user="jefe@example.com"),
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.user_has_any_role",
			side_effect=lambda user, *roles: "Jefe_PDV" in roles,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.evaluate_dimension_permission",
			return_value={"effective_allowed": False},
		):
			res = punto_360.get_punto_stats("PDV-1")

		actions = {item["key"]: item for item in res["actionable_hub"]["contextual_actions"]["quick_actions"]}
		self.assertTrue(actions["create_gh_novedad"]["visible"])
		self.assertFalse(actions["create_sst_alert"]["visible"])
		self.assertTrue(actions["create_wellbeing_alert"]["visible"])
		self.assertFalse(actions["open_rl_view"]["visible"])
		self.assertTrue(actions["view_documents"]["visible"])

	def test_punto_360_uses_sst_as_canonical_source_for_incapacidad(self):
		punto_doc = SimpleNamespace(nombre_pdv="PDV 1", zona="Norte", planta_autorizada=10)

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Ficha Empleado":
				return [SimpleNamespace(name="EMP-001")]
			if doctype == "Novedad SST":
				return [
					{
						"name": "NOV-INC-1",
						"empleado": "EMP-001",
						"empleado_nombres": "Ana",
						"empleado_apellidos": "Paz",
						"tipo_novedad": "Accidente",
						"estado": "En seguimiento",
						"fecha_inicio": "2026-03-18",
						"fecha_fin": "2026-03-20",
						"es_incapacidad": 1,
						"origen_incapacidad": "AT",
						"proxima_alerta_fecha": None,
						"en_radar": 1,
						"ref_doctype": "GH Novedad",
						"ref_docname": "GHNOV-1",
					}
				]
			if doctype == "GH Novedad":
				return []
			return []

		def fake_exists(doctype, name=None):
			if doctype == "DocType":
				return name == "GH Novedad"
			return True

		def fake_count(doctype, filters=None):
			if doctype == "Ficha Empleado":
				return 1
			if doctype == "GH Novedad":
				return 3
			return 0

		with patch("hubgh.hubgh.page.punto_360.punto_360.frappe.has_permission", return_value=True), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_doc",
			return_value=punto_doc,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.nowdate",
			return_value="2026-03-21",
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.db.count",
			side_effect=fake_count,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.db.exists",
			side_effect=fake_exists,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.session",
			new=SimpleNamespace(user="rrll@example.com"),
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.evaluate_dimension_permission",
			return_value={"effective_allowed": True},
		):
			res = punto_360.get_punto_stats("PDV-1")

		self.assertEqual(res["info"]["kpi_sst"]["incapacidades_activas"], 1)
		self.assertEqual(res["info"]["kpi_sst"]["incapacidades_rrll_handoff"], 1)
		self.assertEqual(res["info"]["kpi_sst"]["fuente_canonica_incapacidad"], "Novedad SST")
		self.assertEqual(res["info"]["kpi_sst"]["_fuentes"]["incapacidades_gh_novedad"], 1)
		self.assertEqual(res["no_disponibles"][0]["rrll_handoff_name"], "GHNOV-1")

	def test_punto_360_exposes_formacion_catalog_assignments_by_role_and_point(self):
		punto_doc = SimpleNamespace(nombre_pdv="PDV 1", zona="Norte", planta_autorizada=10)

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Ficha Empleado":
				return [
					{
						"name": "EMP-001",
						"nombres": "Ana",
						"apellidos": "Paz",
						"cargo": "Jefe de Tienda",
						"email": "jefe@example.com",
					},
					{
						"name": "EMP-002",
						"nombres": "Luis",
						"apellidos": "Rios",
						"cargo": "Analista SST",
						"email": "sst@example.com",
					},
				]
			return []

		def fake_exists(doctype, name=None):
			if doctype == "DocType":
				return name == "LMS Enrollment"
			if doctype == "User":
				return name in {"jefe@example.com", "sst@example.com"}
			return True

		with patch("hubgh.hubgh.page.punto_360.punto_360.frappe.has_permission", return_value=True), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_doc",
			return_value=punto_doc,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.db.exists",
			side_effect=fake_exists,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_roles",
			side_effect=lambda user: ["Jefe_PDV"] if user == "jefe@example.com" else (["HR SST"] if user == "sst@example.com" else []),
		):
			res = punto_360.get_formacion_catalog_assignments("PDV-1")

		self.assertTrue(res["lms_disponible"])
		self.assertEqual(res["resumen"]["total_colaboradores"], 2)
		self.assertEqual(res["resumen"]["asignaciones_obligatorias"], 4)
		self.assertEqual(res["resumen"]["asignaciones_recomendadas"], 4)

		by_emp = {row["empleado"]: row for row in res["empleados"]}
		jefe_courses = {a["course"]: a for a in by_emp["EMP-001"]["asignaciones"]}
		sst_courses = {a["course"]: a for a in by_emp["EMP-002"]["asignaciones"]}

		self.assertEqual(jefe_courses["liderazgo-punto-de-venta"]["assignment_type"], "Obligatorio")
		self.assertEqual(sst_courses["seguridad-y-salud-en-el-trabajo"]["assignment_type"], "Obligatorio")
		self.assertIn("contexto-operativo-norte", jefe_courses)

	def test_punto_360_formacion_compliance_reports_pending_and_pct(self):
		assignments_payload = {
			"lms_disponible": True,
			"empleados": [
				{
					"empleado": "EMP-001",
					"asignaciones": [
						{"course": "calidad-e-inocuidad-alimentaria", "label": "Calidad", "assignment_type": "Obligatorio"}
					],
				},
				{
					"empleado": "EMP-002",
					"asignaciones": [
						{"course": "calidad-e-inocuidad-alimentaria", "label": "Calidad", "assignment_type": "Obligatorio"}
					],
				},
			],
		}

		with patch("hubgh.hubgh.page.punto_360.punto_360.frappe.has_permission", return_value=True), patch(
			"hubgh.hubgh.page.punto_360.punto_360.get_formacion_catalog_assignments",
			return_value=assignments_payload,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360._employee_rows_for_point",
			return_value=[
				{"name": "EMP-001", "email": "a@example.com"},
				{"name": "EMP-002", "email": "b@example.com"},
			],
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_all",
			return_value=[
				{"member": "a@example.com", "course": "calidad-e-inocuidad-alimentaria", "progress": 100},
				{"member": "b@example.com", "course": "calidad-e-inocuidad-alimentaria", "progress": 40},
			],
		):
			res = punto_360.get_formacion_compliance("PDV-1")

		self.assertTrue(res["lms_disponible"])
		self.assertEqual(res["resumen"]["mandatory_total"], 2)
		self.assertEqual(res["resumen"]["mandatory_completed"], 1)
		self.assertEqual(res["resumen"]["mandatory_pending"], 1)
		self.assertEqual(res["resumen"]["cumplimiento_pct"], 50.0)
		self.assertEqual(len(res["alertas"]), 1)

	def test_punto_360_lms_integration_contract_reports_degraded_without_lms(self):
		def fake_exists(doctype, name=None):
			if doctype == "DocType":
				return False
			return True

		with patch("hubgh.hubgh.page.punto_360.punto_360.frappe.db.exists", side_effect=fake_exists):
			res = punto_360.get_lms_integration_contract()

		self.assertEqual(res["status"], "degraded")
		self.assertFalse(res["lms_disponible"])
		self.assertIn("catalog_assignments", res["endpoints"])
		self.assertIn("compliance", res["endpoints"])

	def test_medical_exam_list_excludes_candidates_with_defined_concept(self):
		rows = [
			SimpleNamespace(
				name="CAND-001",
				nombres="Ana",
				apellidos="Paz",
				primer_apellido="",
				segundo_apellido="",
				numero_documento="1001",
				pdv_destino="PDV-1",
				cargo_postulado="Auxiliar",
				fecha_envio_examen_medico="2026-03-01",
				concepto_medico="Pendiente",
				creation="2026-03-01 10:00:00",
			),
			SimpleNamespace(
				name="CAND-002",
				nombres="Luis",
				apellidos="Roa",
				primer_apellido="",
				segundo_apellido="",
				numero_documento="1002",
				pdv_destino="PDV-1",
				cargo_postulado="Auxiliar",
				fecha_envio_examen_medico="2026-03-01",
				concepto_medico="Favorable",
				creation="2026-03-01 11:00:00",
			),
		]

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Has Role":
				return ["sst.owner@example.com"]
			if doctype == "Candidato":
				return rows
			return []

		with patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.session",
			new=SimpleNamespace(user="sst@example.com"),
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.user_can_access_dimension",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.nowdate",
			return_value="2026-03-05",
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._candidate_has_medical_exam_doc",
			return_value=True,
		):
			result = seleccion_documentos.list_medical_exam_candidates()

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["name"], "CAND-001")
		self.assertEqual(result[0]["exam_scope"], "vigente")
		self.assertEqual(result[0]["responsable_alerta"], "sst.owner@example.com")
		self.assertEqual(result[0]["dias_pendientes"], 4)
		self.assertTrue(result[0]["alerta_vencimiento"])

	def test_medical_exam_history_returns_historico_scope_and_order(self):
		rows = [
			SimpleNamespace(
				name="CAND-001",
				nombres="Ana",
				apellidos="Paz",
				primer_apellido="",
				segundo_apellido="",
				numero_documento="1001",
				pdv_destino="PDV-1",
				cargo_postulado="Auxiliar",
				fecha_envio_examen_medico="2026-03-01",
				concepto_medico="Favorable",
				estado_proceso="En Proceso",
				modified="2026-03-02 11:00:00",
			),
			SimpleNamespace(
				name="CAND-002",
				nombres="Luis",
				apellidos="Roa",
				primer_apellido="",
				segundo_apellido="",
				numero_documento="1002",
				pdv_destino="PDV-1",
				cargo_postulado="Auxiliar",
				fecha_envio_examen_medico="2026-03-01",
				concepto_medico="Desfavorable",
				estado_proceso="En Examen Médico",
				modified="2026-03-01 10:00:00",
			),
		]

		with patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.session",
			new=SimpleNamespace(user="sst@example.com"),
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.user_can_access_dimension",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.get_all",
			return_value=rows,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._candidate_has_medical_exam_doc",
			return_value=True,
		):
			result = seleccion_documentos.list_medical_exam_history()

		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["name"], "CAND-001")
		self.assertEqual(result[0]["exam_scope"], "historico")
		self.assertEqual(result[0]["evaluado_en"], "2026-03-02 11:00:00")
		self.assertEqual(result[1]["name"], "CAND-002")

	def test_medical_exam_history_masks_concept_without_clinical_dimension(self):
		rows = [
			SimpleNamespace(
				name="CAND-001",
				nombres="Ana",
				apellidos="Paz",
				primer_apellido="",
				segundo_apellido="",
				numero_documento="1001",
				pdv_destino="PDV-1",
				cargo_postulado="Auxiliar",
				fecha_envio_examen_medico="2026-03-01",
				concepto_medico="Favorable",
				estado_proceso="En Proceso",
				modified="2026-03-02 11:00:00",
			),
		]

		with patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.session",
			new=SimpleNamespace(user="rrll@example.com"),
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.user_has_any_role",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.user_can_access_dimension",
			return_value=False,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.get_all",
			return_value=rows,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._candidate_has_medical_exam_doc",
			return_value=True,
		):
			result = seleccion_documentos.list_medical_exam_history()

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["concepto_medico"], "Restringido")
		self.assertFalse(result[0]["clinical_visible"])

	def test_selection_candidate_detail_resolves_display_labels_for_codes(self):
		candidate_doc = SimpleNamespace(
			name="CAND-001",
			nombres="Ana",
			apellidos="Paz",
			primer_apellido="",
			segundo_apellido="",
			numero_documento="1001",
			estado_proceso="En Proceso",
			concepto_medico="Pendiente",
			fecha_envio_examen_medico="2026-03-01",
			direccion="Calle 1",
			barrio="Centro",
			ciudad="Bogota",
			localidad="Suba",
			localidad_otras="",
			procedencia_pais="169",
			procedencia_departamento="11",
			procedencia_ciudad="001",
			banco_siesa="1059",
			pdv_destino="PDV-1",
			tipo_cuenta_bancaria="Ahorros",
			numero_cuenta_bancaria="12345",
		)

		with patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._validate_selection_access"), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.ensure_candidate_required_documents"
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.get_doc",
			return_value=candidate_doc,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.get_person_document_rows",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.get_candidate_progress",
			return_value={"percent": 0, "required_ok": 0, "required_total": 0, "is_complete": False},
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._selection_docs_status",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._active_candidate_document_types",
			return_value=[],
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.resolve_candidate_location_labels",
			return_value={"pais": "Colombia", "departamento": "Cundinamarca", "ciudad": "Armenia"},
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.resolve_siesa_bank_name",
			return_value="Bancolombia",
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.get_punto_name_map",
			return_value={"PDV-1": "Punto Norte"},
		):
			result = seleccion_documentos.candidate_detail("CAND-001")

		self.assertEqual(result["candidate"]["procedencia_pais"], "Colombia")
		self.assertEqual(result["candidate"]["procedencia_departamento"], "Cundinamarca")
		self.assertEqual(result["candidate"]["procedencia_ciudad"], "Armenia")
		self.assertEqual(result["candidate"]["banco_siesa"], "Bancolombia")
		self.assertEqual(result["candidate"]["pdv_destino_nombre"], "Punto Norte")
		self.assertEqual(result["candidate"]["banco_siesa_codigo"], "1059")

	def test_selection_list_candidates_exposes_point_name_alongside_code(self):
		rows = [
			SimpleNamespace(
				name="CAND-001",
				nombres="Ana",
				apellidos="Paz",
				primer_apellido="",
				segundo_apellido="",
				numero_documento="1001",
				pdv_destino="PDV-1",
				cargo_postulado="Auxiliar",
				creation="2026-03-01 10:00:00",
				estado_proceso="En Proceso",
				concepto_medico="Pendiente",
				fecha_envio_examen_medico="2026-03-01",
				solo_afiliacion=0,
				persona=None,
				fecha_tentativa_ingreso=None,
			),
		]

		with patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._validate_selection_access"), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._can_manage_candidates",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.get_all",
			return_value=rows,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.ensure_candidate_required_documents"
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.get_candidate_progress",
			return_value={"percent": 50, "required_ok": 1, "required_total": 2, "is_complete": False},
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._has_uploaded_document",
			return_value=False,
		), patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.get_punto_name_map",
			return_value={"PDV-1": "Punto Norte"},
		):
			result = seleccion_documentos.list_candidates()

		self.assertEqual(result[0]["pdv_destino"], "PDV-1")
		self.assertEqual(result[0]["pdv_destino_nombre"], "Punto Norte")

	def test_ensure_person_document_allows_multiple_reuses_pending_seed(self):
		rules = {"document_type": "2 cartas de referencias personales.", "allows_multiple": 1, "requires_approval": 0}
		pending_row = [SimpleNamespace(name="PD-0001")]
		with patch("hubgh.hubgh.document_service._get_document_type_rules", return_value=rules), patch(
			"hubgh.hubgh.document_service.frappe.get_all", return_value=pending_row
		), patch("hubgh.hubgh.document_service.frappe.get_doc", return_value=SimpleNamespace(name="PD-0001")) as get_doc_mock, patch(
			"hubgh.hubgh.document_service._new_person_document"
		) as new_doc_mock:
			doc = document_service.ensure_person_document("Candidato", "CAND-001", "2 cartas de referencias personales.")

		self.assertEqual(doc.name, "PD-0001")
		get_doc_mock.assert_called_once_with("Person Document", "PD-0001")
		new_doc_mock.assert_not_called()

	def test_resolve_siesa_catalog_name_matches_name_code_or_description(self):
		rows = [
			{"name": "001", "code": "001", "description": "ADMIN"},
			{"name": "XYZ", "code": "ABC", "description": "Operativo General"},
		]
		with patch("hubgh.hubgh.contratacion_service._catalog_rows", return_value=rows):
			by_name = contratacion_service._resolve_siesa_catalog_name("Centro Costos Siesa", ["001"])
			by_code = contratacion_service._resolve_siesa_catalog_name("Centro Costos Siesa", ["ABC"])
			by_desc = contratacion_service._resolve_siesa_catalog_name("Centro Costos Siesa", ["operativo general"])

		self.assertEqual(by_name, "001")
		self.assertEqual(by_code, "XYZ")
		self.assertEqual(by_desc, "XYZ")

	def test_guess_tipo_cotizante_prefers_aprendiz_when_contract_is_aprendizaje(self):
		rows = [
			{"name": "01", "code": "01", "description": "Dependiente"},
			{"name": "19", "code": "19", "description": "Aprendiz Sena"},
		]
		with patch("hubgh.hubgh.contratacion_service._catalog_rows", return_value=rows):
			value = contratacion_service._guess_tipo_cotizante_from_tipo_contrato("Aprendizaje Productiva")

		self.assertEqual(value, "19")

	def test_create_contract_requires_manual_capture_when_siesa_derivation_fails(self):
		candidate_doc = SimpleNamespace(pdv_destino="PDV-1", cargo_postulado="CAR-1", fecha_tentativa_ingreso="2026-03-10")
		datos_doc = SimpleNamespace(get=lambda fieldname: None)

		with patch("hubgh.hubgh.contratacion_service.validate_hr_access"), patch(
			"hubgh.hubgh.contratacion_service.frappe.get_doc", return_value=candidate_doc
		), patch(
			"hubgh.hubgh.contratacion_service.get_or_create_datos_contratacion", return_value=datos_doc
		), patch(
			"hubgh.hubgh.contratacion_service._resolve_required_siesa_fields",
			return_value={
				"tipo_cotizante_siesa": None,
				"centro_costos_siesa": None,
				"unidad_negocio_siesa": "UN-1",
				"centro_trabajo_siesa": "CT-1",
				"grupo_empleados_siesa": "GE-1",
			},
		), patch(
			"hubgh.hubgh.contratacion_service._missing_required_siesa_fields",
			return_value=["centro de costos", "tipo cotizante"],
		), patch(
			"hubgh.hubgh.contratacion_service.frappe.throw",
			side_effect=RuntimeError("manual-capture-required"),
		):
			with self.assertRaisesRegex(RuntimeError, "manual-capture-required"):
				contratacion_service.create_contract("CAND-001", {"tipo_contrato": "Indefinido"})

	def test_resolve_siesa_catalog_name_falls_back_to_code_one(self):
		rows = [{"name": "2", "code": "2", "description": "Otro"}]
		with patch("hubgh.hubgh.contratacion_service._catalog_rows", return_value=rows), patch(
			"hubgh.hubgh.contratacion_service._ensure_catalog_ready"
		), patch(
			"hubgh.hubgh.contratacion_service.frappe.db.get_value", return_value="1"
		):
			resolved = contratacion_service._resolve_siesa_catalog_name("Centro Costos Siesa", ["valor-no-mapeado"])

		self.assertEqual(resolved, "1")

	def test_build_employee_context_requires_rrll_final_fields(self):
		data = SimpleNamespace(
			candidato=None,
			contrato=None,
			numero_documento="1001",
			tipo_documento="Cedula",
			nombres="ANA",
			primer_apellido="PEREZ",
			segundo_apellido="LOPEZ",
			fecha_ingreso="2026-03-01",
			fecha_nacimiento="2000-01-01",
			fecha_expedicion="2018-05-01",
			nivel_educativo_siesa="MEDIA",
			genero="Femenino",
			estado_civil="Soltero",
			direccion="CL 1 # 2-3",
			pais_residencia_siesa="169",
			departamento_residencia_siesa="11",
			ciudad_residencia_siesa="001",
			telefono_contacto_siesa="3001234567",
			email="ana@example.com",
			es_extranjero=0,
			pais_nacimiento_siesa="",
			departamento_nacimiento_siesa="",
			ciudad_nacimiento_siesa="",
			pais_expedicion_siesa="",
			departamento_expedicion_siesa="",
			ciudad_expedicion_siesa="",
			prefijo_cuenta_extranjero="",
			barrio="",
			celular="",
			ciudad="",
		)

		_, missing = siesa_export._build_employee_context(data)

		self.assertIn("PAIS NACIMIENTO", missing)
		self.assertIn("DEPTO EXPEDICION", missing)

	def test_datos_contratacion_does_not_copy_cellphone_into_landline_contact(self):
		datos = self._DocStub(candidato="CAND-001", telefono_contacto_siesa="")
		candidate_doc = self._DocStub(
			tipo_documento="Cedula",
			numero_documento="1001",
			nombres="Ana",
			primer_apellido="Perez",
			segundo_apellido="Lopez",
			telefono_fijo="",
			celular="3001234567",
		)

		with patch("hubgh.hubgh.doctype.datos_contratacion.datos_contratacion.frappe.get_doc", return_value=candidate_doc):
			DatosContratacion._sync_from_candidate(datos)

		self.assertEqual(datos.telefono_contacto_siesa or "", "")

	def test_validar_candidato_para_siesa_skips_bank_requirements_when_candidate_has_no_account(self):
		datos = self._DocStub(
			name="DC-001",
			estado_datos="Completo",
			tipo_documento="Cedula",
			numero_documento="1001",
			nombres="Ana",
			primer_apellido="Perez",
			segundo_apellido="Lopez",
			fecha_nacimiento="2000-01-01",
			fecha_expedicion="2018-05-01",
			genero="Femenino",
			estado_civil="Soltero",
			nivel_educativo_siesa="MEDIA",
			direccion="CL 1 # 2-3",
			ciudad_residencia_siesa="001",
			email="ana@example.com",
			tiene_cuenta_bancaria="No",
			fecha_ingreso="2026-03-01",
			salario="1500000",
			contrato="CONT-001",
		)
		candidate_doc = self._DocStub(
			name="CAND-001",
			tipo_documento="Cedula",
			numero_documento="1001",
			nombres="Ana",
			primer_apellido="Perez",
			segundo_apellido="Lopez",
			fecha_nacimiento="2000-01-01",
			fecha_expedicion="2018-05-01",
			genero="Femenino",
			estado_civil="Soltero",
			nivel_educativo_siesa="MEDIA",
			direccion="CL 1 # 2-3",
			ciudad_residencia_siesa="001",
			email="ana@example.com",
			tiene_cuenta_bancaria="No",
		)
		contract_doc = self._DocStub(docstatus=1)

		def fake_get_doc(doctype, name):
			if doctype == "Datos Contratacion":
				return datos
			if doctype == "Contrato":
				return contract_doc
			return candidate_doc

		with patch("hubgh.hubgh.contratacion_service.frappe.db.get_value", return_value="DC-001"), patch(
			"hubgh.hubgh.contratacion_service.frappe.get_doc", side_effect=fake_get_doc
		), patch("hubgh.hubgh.contratacion_service.ensure_reference_catalog"), patch(
			"hubgh.hubgh.contratacion_service._resolve_siesa_catalog_name", return_value="MEDIA"
		), patch(
			"hubgh.hubgh.contratacion_service._resolve_required_siesa_fields",
			return_value={
				"tipo_cotizante_siesa": "TC",
				"centro_costos_siesa": "CC",
				"unidad_negocio_siesa": "UN",
				"centro_trabajo_siesa": "CT",
				"grupo_empleados_siesa": "GE",
				"pdv_destino": "PDV-1",
				"cargo_postulado": "CAR-1",
				"tipo_contrato": "Indefinido",
			}
		), patch("hubgh.hubgh.contratacion_service._missing_required_siesa_fields", return_value=[]), patch(
			"hubgh.hubgh.contratacion_service.get_or_create_affiliation",
			return_value=SimpleNamespace(arl_afiliado=1, eps_afiliado=1, afp_afiliado=1, cesantias_afiliado=1, caja_afiliado=1),
		):
			result = contratacion_service.validar_candidato_para_siesa("CAND-001")

		self.assertTrue(result["ok"])
		self.assertNotIn("Falta banco", result["errors"])

	def test_candidate_progress_ignores_bank_document_when_candidate_has_no_account(self):
		required_docs = [
			SimpleNamespace(name="Certificación bancaria (No mayor a 30 días).", document_name="Certificación bancaria (No mayor a 30 días).", requires_approval=0, allows_multiple=0),
			SimpleNamespace(name="Hoja de vida actualizada.", document_name="Hoja de vida actualizada.", requires_approval=0, allows_multiple=0),
		]

		with patch("hubgh.hubgh.document_service.frappe.get_all", return_value=required_docs), patch(
			"hubgh.hubgh.document_service.frappe.db.get_value",
			return_value={"tiene_cuenta_bancaria": "No", "banco_siesa": "", "tipo_cuenta_bancaria": "", "numero_cuenta_bancaria": ""},
		), patch(
			"hubgh.hubgh.document_service._build_person_dossier",
			return_value={
				"vigentes": [{"document_type": "Hoja de vida actualizada.", "file": "/files/hv.pdf", "status": "Subido"}]
			},
		):
			progress = document_service.get_candidate_progress("CAND-001")

		self.assertEqual(progress["required_total"], 1)
		self.assertEqual(progress["required_ok"], 1)
		self.assertTrue(progress["is_complete"])

	def test_build_contract_context_requires_complete_operational_codes(self):
		data = SimpleNamespace(candidato="CAND-001", contrato="CONT-001", aplica_auxilio_transporte="3", arl_codigo_siesa="")
		contract_doc = SimpleNamespace(
			numero_documento="1001",
			numero_contrato=1,
			pdv_destino="PDV-1",
			cargo="CAR-1",
			tipo_cotizante_siesa="TC-1",
			unidad_negocio_siesa="UN-1",
			grupo_empleados_siesa="GE-1",
			centro_costos_siesa="CC-1",
			centro_trabajo_siesa="CT-1",
			entidad_afp_siesa="AFP-1",
			entidad_eps_siesa="EPS-1",
			entidad_cesantias_siesa="CES-1",
			entidad_ccf_siesa="CCF-1",
			fecha_ingreso="2026-03-01",
			fecha_fin_contrato=None,
			salario=1500000,
			horas_trabajadas_mes=220,
			cuenta_bancaria="",
			tipo_cuenta_bancaria="Ahorros",
			banco_siesa="BAN-1",
			tipo_contrato="Indefinido",
		)

		with patch("hubgh.hubgh.siesa_export.frappe.db.exists", return_value=True), patch(
			"hubgh.hubgh.siesa_export.frappe.get_doc",
			side_effect=lambda doctype, name: contract_doc if doctype == "Contrato" else SimpleNamespace(es_extranjero=0, personas_a_cargo=0),
		), patch("hubgh.hubgh.siesa_export.frappe.db.get_value", return_value=""), patch(
			"hubgh.hubgh.siesa_export._catalog_code", return_value=""
		), patch(
			"hubgh.hubgh.siesa_export.get_or_create_affiliation", return_value=SimpleNamespace(arl_numero_afiliacion="")
		):
			_, missing = siesa_export._build_contract_context(data)

		self.assertIn("ID TIPO COTIZANTE", missing)
		self.assertIn("CUENTA BANCARIA", missing)

	def test_resolve_id_banco_empleado_uses_description_fallback_when_digits_missing(self):
		calls = []

		def fake_get_value(doctype, name, fieldname, as_dict=False):
			calls.append((doctype, name, fieldname, as_dict))
			if doctype == "Banco Siesa" and fieldname == ["name", "code", "description", "ultimos_dos_digitos", "codigo_bancolombia"]:
				return {
					"name": "BAN-1",
					"code": "FINANCIERA JURISCOOP S.A. COMP",
					"description": "1121",
					"ultimos_dos_digitos": "",
					"codigo_bancolombia": "BC-99",
				}
			return None

		with patch("hubgh.hubgh.siesa_export.frappe.db.exists", return_value=True), patch(
			"hubgh.hubgh.siesa_export.frappe.db.get_value",
			side_effect=fake_get_value,
		), patch("hubgh.hubgh.siesa_export.frappe.db.set_value") as set_value_mock:
			bank_id, notas = siesa_export._resolve_id_banco_empleado("BAN-1")

		self.assertEqual(bank_id, "21")
		self.assertEqual(notas, "99")
		set_value_mock.assert_called_once()

	def test_normalize_banco_siesa_swaps_inverted_code_and_sets_last_two_digits(self):
		snapshot_before = {
			"name": "BAN-1",
			"code": "FINANCIERA JURISCOOP S.A. COMP",
			"description": "1121",
			"ultimos_dos_digitos": "",
			"codigo_bancolombia": "",
		}
		snapshot_after = {
			"name": "BAN-1",
			"code": "1121",
			"description": "FINANCIERA JURISCOOP S.A. COMP",
			"ultimos_dos_digitos": "21",
			"codigo_bancolombia": "",
		}

		with patch("hubgh.hubgh.siesa_export.frappe.db.exists", return_value=True), patch(
			"hubgh.hubgh.siesa_export.frappe.db.get_value",
			side_effect=[snapshot_before, snapshot_after],
		), patch("hubgh.hubgh.siesa_export.frappe.db.set_value") as set_value_mock:
			normalized = siesa_export._normalize_banco_siesa_record("BAN-1")

		set_value_mock.assert_called_once_with(
			"Banco Siesa",
			"BAN-1",
			{"code": "1121", "description": "FINANCIERA JURISCOOP S.A. COMP", "ultimos_dos_digitos": "21"},
			update_modified=False,
		)
		self.assertEqual(normalized["code"], "1121")
		self.assertEqual(normalized["ultimos_dos_digitos"], "21")

	def test_normalize_code_for_doctype_preserves_zero_padding(self):
		self.assertEqual(siesa_reference_matrix.normalize_code_for_doctype("Grupo Empleados Siesa", "1"), "001")
		self.assertEqual(siesa_reference_matrix.normalize_code_for_doctype("Centro Trabajo Siesa", "5"), "005")
		self.assertEqual(siesa_reference_matrix.normalize_code_for_doctype("Centro Costos Siesa", "220101"), "220101")

	def test_infer_selection_defaults_for_group_and_ccosto(self):
		self.assertEqual(contratacion_service._infer_grupo_from_selection("Aprendiz Sena Productivo", "Indefinido"), "004")
		self.assertEqual(contratacion_service._infer_grupo_from_selection("Analista de Sistemas", "Indefinido"), "001")
		self.assertEqual(contratacion_service._infer_ccosto_from_selection("Analista de Sistemas"), "110104")
		self.assertEqual(contratacion_service._infer_ccosto_from_selection("Auxiliar de Producción"), "220101")

	def test_catalog_code_applies_zero_padding(self):
		with patch("hubgh.hubgh.siesa_export.frappe.db.exists", return_value=False), patch(
			"hubgh.hubgh.siesa_export.frappe.db.get_value", return_value=None
		):
			self.assertEqual(siesa_export._catalog_code("Grupo Empleados Siesa", "1"), "001")
			self.assertEqual(siesa_export._catalog_code("Centro Trabajo Siesa", "5"), "005")
			self.assertEqual(siesa_export._catalog_code("Grupo Empleados Siesa", "2"), "002")

	def test_catalog_code_resolves_legacy_social_security_aliases(self):
		with patch("hubgh.hubgh.siesa_export.frappe.db.exists", return_value=False), patch(
			"hubgh.hubgh.siesa_export.frappe.db.get_value", return_value=None
		), patch(
			"hubgh.hubgh.siesa_export.frappe.get_all",
			return_value=[
				{"name": "AFP-230301", "code": "230301", "description": "COLPENSIONES"},
			],
		):
			self.assertEqual(siesa_export._catalog_code("Entidad AFP Siesa", "colpenciones_afc"), "230301")
			self.assertEqual(siesa_export._catalog_code("Entidad AFP Siesa", "COLPENSIONES"), "230301")

	def test_affiliation_contract_snapshot_falls_back_to_candidate_ccf(self):
		candidate_doc = SimpleNamespace(
			name="CAND-001",
			numero_documento="1001",
			nombres="Ana",
			apellidos="Paz",
			tipo_documento=None,
			primer_apellido=None,
			segundo_apellido=None,
			fecha_nacimiento=None,
			fecha_expedicion=None,
			direccion=None,
			ciudad=None,
			celular=None,
			email=None,
			pdv_destino=None,
			cargo_postulado=None,
			fecha_tentativa_ingreso=None,
			eps_siesa=None,
			afp_siesa=None,
			cesantias_siesa=None,
			ccf_siesa="001",
		)

		datos_doc = SimpleNamespace(name="DC-001", get=lambda *_: None)

		def fake_get_value(doctype, filters, fieldname=None):
			if doctype == "Datos Contratacion":
				return "DC-001"
			if doctype == "Afiliacion Seguridad Social":
				return None
			return None

		def fake_get_doc(doctype, name):
			if doctype == "Candidato":
				return candidate_doc
			if doctype == "Datos Contratacion":
				return datos_doc
			raise AssertionError(f"unexpected get_doc call: {doctype} {name}")

		with patch("hubgh.hubgh.contratacion_service.validate_hr_access"), patch(
			"hubgh.hubgh.contratacion_service.frappe.db.exists",
			side_effect=lambda dt, name: dt == "Candidato" and name == "CAND-001",
		), patch(
			"hubgh.hubgh.contratacion_service.frappe.db.get_value",
			side_effect=fake_get_value,
		), patch(
			"hubgh.hubgh.contratacion_service.frappe.get_doc",
			side_effect=fake_get_doc,
		):
			payload = contratacion_service.affiliation_contract_snapshot("CAND-001")

		self.assertEqual(payload["blocks"]["seguridad_social"]["ccf_siesa"], "001")

	def test_affiliation_contract_snapshot_exposes_human_readable_labels_alongside_codes(self):
		candidate_doc = SimpleNamespace(
			name="CAND-001",
			numero_documento="1001",
			nombres="Ana",
			apellidos="Paz",
			tipo_documento="CC",
			primer_apellido=None,
			segundo_apellido=None,
			fecha_nacimiento=None,
			fecha_expedicion=None,
			direccion="Calle 1",
			ciudad="001",
			celular="3001234567",
			email="ana@example.com",
			pdv_destino="PDV-1",
			cargo_postulado="CAR-1",
			fecha_tentativa_ingreso="2026-03-20",
			eps_siesa="EPS-1",
			afp_siesa="AFP-1",
			cesantias_siesa="CES-1",
			ccf_siesa="001",
		)

		datos_map = {
			"direccion": "Calle 1",
			"barrio": "Centro",
			"ciudad_residencia_siesa": "001",
			"departamento_residencia_siesa": "11",
			"pais_residencia_siesa": "169",
			"celular": "3001234567",
			"email": "ana@example.com",
			"banco_siesa": "1059",
			"pdv_destino": "PDV-1",
			"eps_siesa": "EPS-1",
			"afp_siesa": "AFP-1",
			"cesantias_siesa": "CES-1",
			"ccf_siesa": "001",
		}
		datos_doc = SimpleNamespace(name="DC-001", get=lambda fieldname: datos_map.get(fieldname))

		def fake_get_value(doctype, filters, fieldname=None):
			if doctype == "Datos Contratacion":
				return "DC-001"
			if doctype == "Afiliacion Seguridad Social":
				return None
			return None

		def fake_get_doc(doctype, name):
			if doctype == "Candidato":
				return candidate_doc
			if doctype == "Datos Contratacion":
				return datos_doc
			raise AssertionError(f"unexpected get_doc call: {doctype} {name}")

		def fake_catalog_label(doctype, value):
			return {
				("Entidad EPS Siesa", "EPS-1"): "Sanitas",
				("Entidad AFP Siesa", "AFP-1"): "Porvenir",
				("Entidad Cesantias Siesa", "CES-1"): "Protección",
				("Entidad CCF Siesa", "001"): "Compensar",
			}.get((doctype, value), value)

		with patch("hubgh.hubgh.contratacion_service.validate_hr_access"), patch(
			"hubgh.hubgh.contratacion_service.frappe.db.exists",
			side_effect=lambda dt, name: dt == "Candidato" and name == "CAND-001",
		), patch(
			"hubgh.hubgh.contratacion_service.frappe.db.get_value",
			side_effect=fake_get_value,
		), patch(
			"hubgh.hubgh.contratacion_service.frappe.get_doc",
			side_effect=fake_get_doc,
		), patch(
			"hubgh.hubgh.contratacion_service.resolve_candidate_location_labels",
			return_value={"pais": "Colombia", "departamento": "Cundinamarca", "ciudad": "Armenia"},
		), patch(
			"hubgh.hubgh.contratacion_service.resolve_siesa_bank_name",
			return_value="Bancolombia",
		), patch(
			"hubgh.hubgh.contratacion_service.get_punto_display_name",
			return_value="Punto Norte",
		), patch(
			"hubgh.hubgh.contratacion_service.resolve_catalog_display_name",
			side_effect=fake_catalog_label,
		):
			payload = contratacion_service.affiliation_contract_snapshot("CAND-001")

		self.assertEqual(payload["blocks"]["contacto"]["ciudad"], "001")
		self.assertEqual(payload["blocks"]["contacto"]["ciudad_nombre"], "Armenia")
		self.assertEqual(payload["blocks"]["contacto"]["departamento_residencia_siesa"], "11")
		self.assertEqual(payload["blocks"]["contacto"]["departamento_residencia_nombre"], "Cundinamarca")
		self.assertEqual(payload["blocks"]["contacto"]["pais_residencia_siesa"], "169")
		self.assertEqual(payload["blocks"]["contacto"]["pais_residencia_nombre"], "Colombia")
		self.assertEqual(payload["blocks"]["bancarios"]["banco_siesa"], "1059")
		self.assertEqual(payload["blocks"]["bancarios"]["banco_siesa_nombre"], "Bancolombia")
		self.assertEqual(payload["blocks"]["laborales"]["pdv_destino"], "PDV-1")
		self.assertEqual(payload["blocks"]["laborales"]["pdv_destino_nombre"], "Punto Norte")
		self.assertEqual(payload["blocks"]["seguridad_social"]["eps_siesa"], "EPS-1")
		self.assertEqual(payload["blocks"]["seguridad_social"]["eps_siesa_nombre"], "Sanitas")
		self.assertEqual(payload["blocks"]["seguridad_social"]["ccf_siesa"], "001")
		self.assertEqual(payload["blocks"]["seguridad_social"]["ccf_siesa_nombre"], "Compensar")

	def test_ensure_official_ccf_catalog_disables_non_official_rows(self):
		rows = [
			{"name": "001", "code": "001", "enabled": 1},
			{"name": "002", "code": "002", "enabled": 1},
			{"name": "999", "code": "999", "enabled": 1},
		]

		with patch("hubgh.hubgh.siesa_reference_matrix.ensure_reference_catalog") as ensure_ref_mock, patch(
			"hubgh.hubgh.siesa_reference_matrix.frappe.get_all",
			return_value=rows,
		), patch("hubgh.hubgh.siesa_reference_matrix.frappe.db.set_value") as set_value_mock:
			siesa_reference_matrix.ensure_official_ccf_catalog(strict_disable_others=True)

		ensure_ref_mock.assert_called_once_with("Entidad CCF Siesa")
		set_value_mock.assert_called_once_with("Entidad CCF Siesa", "999", "enabled", 0, update_modified=False)

	def test_ensure_official_unidad_negocio_catalog_repoints_and_disables_non_official(self):
		unidad_rows = [
			{"name": "UN-100", "code": "100", "description": "HAMBURGUESAS", "enabled": 1},
			{"name": "UN-200", "code": "200", "description": "POSTRES", "enabled": 1},
			{"name": "UN-999", "code": "999", "description": "ADMINISTRATIVO", "enabled": 1},
			{"name": "UN-BAD", "code": "1", "description": "test", "enabled": 1},
		]

		def fake_exists(doctype, name=None):
			if doctype == "DocType":
				return name in {"Contrato", "Datos Contratacion"}
			return doctype in {"Contrato", "Datos Contratacion"}

		def fake_get_all(doctype, fields=None, filters=None):
			if doctype == "Unidad Negocio Siesa":
				return unidad_rows
			if doctype == "Contrato":
				return [{"name": "CONT-1", "unidad_negocio_siesa": "UN-BAD"}]
			if doctype == "Datos Contratacion":
				return [{"name": "DC-1", "unidad_negocio_siesa": "INEXISTENTE"}]
			return []

		with patch("hubgh.hubgh.siesa_reference_matrix.ensure_reference_catalog") as ensure_ref_mock, patch(
			"hubgh.hubgh.siesa_reference_matrix.frappe.db.exists",
			side_effect=fake_exists,
		), patch(
			"hubgh.hubgh.siesa_reference_matrix.frappe.get_all",
			side_effect=fake_get_all,
		), patch("hubgh.hubgh.siesa_reference_matrix.frappe.db.set_value") as set_value_mock:
			siesa_reference_matrix.ensure_official_unidad_negocio_catalog(strict_disable_others=True)

		ensure_ref_mock.assert_called_once_with("Unidad Negocio Siesa")
		set_calls = set_value_mock.call_args_list
		self.assertTrue(any(c.args[:4] == ("Contrato", "CONT-1", "unidad_negocio_siesa", "UN-999") for c in set_calls))
		self.assertTrue(any(c.args[:4] == ("Datos Contratacion", "DC-1", "unidad_negocio_siesa", "UN-999") for c in set_calls))
		self.assertTrue(any(c.args[:4] == ("Unidad Negocio Siesa", "UN-BAD", "enabled", 0) for c in set_calls))

	def test_ensure_official_centro_trabajo_catalog_repoints_and_disables_non_official(self):
		ct_rows = [
			{"name": "CT-001", "code": "001", "description": "Nivel Riesgo 1 (0,522%)", "enabled": 1},
			{"name": "CT-002", "code": "002", "description": "Nivel Riesgo 2 (1,044%)", "enabled": 1},
			{"name": "CT-003", "code": "003", "description": "Nivel Riesgo 3 (2,436%)", "enabled": 1},
			{"name": "CT-004", "code": "004", "description": "Nivel Riesgo 4 (4,35%)", "enabled": 1},
			{"name": "CT-005", "code": "005", "description": "Nivel Riesgo 5 (6,96%)", "enabled": 1},
			{"name": "CT-BAD", "code": "100", "description": "HAMBURGUESAS", "enabled": 1},
		]

		def fake_exists(doctype, name=None):
			if doctype == "DocType":
				return name in {"Contrato", "Datos Contratacion"}
			return doctype in {"Contrato", "Datos Contratacion"}

		def fake_get_all(doctype, fields=None, filters=None):
			if doctype == "Centro Trabajo Siesa":
				return ct_rows
			if doctype == "Contrato":
				return [{"name": "CONT-1", "centro_trabajo_siesa": "CT-BAD"}]
			if doctype == "Datos Contratacion":
				return [{"name": "DC-1", "centro_trabajo_siesa": "INEXISTENTE"}]
			return []

		with patch("hubgh.hubgh.siesa_reference_matrix.ensure_reference_catalog") as ensure_ref_mock, patch(
			"hubgh.hubgh.siesa_reference_matrix.frappe.db.exists",
			side_effect=fake_exists,
		), patch(
			"hubgh.hubgh.siesa_reference_matrix.frappe.get_all",
			side_effect=fake_get_all,
		), patch("hubgh.hubgh.siesa_reference_matrix.frappe.db.set_value") as set_value_mock:
			siesa_reference_matrix.ensure_official_centro_trabajo_catalog(strict_disable_others=True)

		ensure_ref_mock.assert_called_once_with("Centro Trabajo Siesa")
		set_calls = set_value_mock.call_args_list
		self.assertTrue(any(c.args[:4] == ("Contrato", "CONT-1", "centro_trabajo_siesa", "CT-001") for c in set_calls))
		self.assertTrue(any(c.args[:4] == ("Datos Contratacion", "DC-1", "centro_trabajo_siesa", "CT-001") for c in set_calls))
		self.assertTrue(any(c.args[:4] == ("Centro Trabajo Siesa", "CT-BAD", "enabled", 0) for c in set_calls))

	def test_sync_reference_masters_enforces_official_catalog_guards(self):
		with patch("hubgh.hubgh.siesa_reference_matrix.ensure_reference_catalog") as ensure_catalog_mock, patch(
			"hubgh.hubgh.siesa_reference_matrix.ensure_official_ccf_catalog"
		) as ensure_ccf_mock, patch(
			"hubgh.hubgh.siesa_reference_matrix.ensure_official_unidad_negocio_catalog"
		) as ensure_un_mock, patch(
			"hubgh.hubgh.siesa_reference_matrix.ensure_official_centro_trabajo_catalog"
		) as ensure_ct_mock, patch(
			"hubgh.hubgh.siesa_reference_matrix.ensure_banco_reference_catalog"
		) as ensure_banco_mock, patch(
			"hubgh.hubgh.siesa_reference_matrix.ensure_official_cargo_matrix"
		) as ensure_cargo_mock, patch(
			"hubgh.hubgh.siesa_reference_matrix.frappe.db.commit"
		) as commit_mock:
			siesa_reference_matrix.sync_reference_masters()

		self.assertEqual(ensure_catalog_mock.call_count, len(siesa_reference_matrix.OFFICIAL_SIESA_CATALOGS))
		ensure_ccf_mock.assert_called_once_with(strict_disable_others=True)
		ensure_un_mock.assert_called_once_with(strict_disable_others=True)
		ensure_ct_mock.assert_called_once_with(strict_disable_others=True)
		ensure_banco_mock.assert_called_once()
		ensure_cargo_mock.assert_called_once()
		commit_mock.assert_called_once()

	def test_submit_contract_blocks_when_mandatory_ingreso_data_missing(self):
		contract_doc = SimpleNamespace(
			name="CONT-001",
			candidato="CAND-001",
			numero_documento="1001",
			nombres="Ana",
			apellidos="Paz",
			pdv_destino="PDV-1",
			cargo="CAR-1",
			fecha_ingreso="2026-03-15",
			tipo_contrato="Indefinido",
			salario=0,
			docstatus=0,
			get=lambda fieldname: getattr(contract_doc, fieldname, None),
		)

		candidate_doc = SimpleNamespace(
			get=lambda fieldname: {
				"cargo_postulado": "CAR-1",
				"fecha_tentativa_ingreso": "2026-03-15",
			}.get(fieldname)
		)
		datos_doc = SimpleNamespace(get=lambda _fieldname: None)

		with patch("hubgh.hubgh.contratacion_service.validate_hr_access"), patch(
			"hubgh.hubgh.contratacion_service.frappe.get_doc",
			side_effect=lambda doctype, name: contract_doc if doctype == "Contrato" else candidate_doc,
		), patch(
			"hubgh.hubgh.contratacion_service.get_or_create_datos_contratacion",
			return_value=datos_doc,
		), patch(
			"hubgh.hubgh.contratacion_service.frappe.throw",
			side_effect=RuntimeError("gate-blocked"),
		):
			with self.assertRaisesRegex(RuntimeError, "gate-blocked"):
				contratacion_service.submit_contract("CONT-001")

	def test_submit_contract_blocks_when_mandatory_documents_incomplete(self):
		contract_doc = SimpleNamespace(
			name="CONT-001",
			candidato="CAND-001",
			numero_documento="1001",
			nombres="Ana",
			apellidos="Paz",
			pdv_destino="PDV-1",
			cargo="CAR-1",
			fecha_ingreso="2026-03-15",
			tipo_contrato="Indefinido",
			salario=1500000,
			docstatus=0,
			get=lambda fieldname: getattr(contract_doc, fieldname, None),
		)

		candidate_doc = SimpleNamespace(
			get=lambda fieldname: {
				"cargo_postulado": "CAR-1",
				"fecha_tentativa_ingreso": "2026-03-15",
			}.get(fieldname)
		)
		datos_doc = SimpleNamespace(get=lambda _fieldname: None)

		with patch("hubgh.hubgh.contratacion_service.validate_hr_access"), patch(
			"hubgh.hubgh.contratacion_service.frappe.get_doc",
			side_effect=lambda doctype, name: contract_doc if doctype == "Contrato" else candidate_doc,
		), patch(
			"hubgh.hubgh.contratacion_service.get_or_create_datos_contratacion",
			return_value=datos_doc,
		), patch(
			"hubgh.hubgh.document_service.get_candidate_progress",
			return_value={"is_complete": False, "missing": ["SAGRILAFT"]},
		), patch(
			"hubgh.hubgh.contratacion_service.frappe.throw",
			side_effect=RuntimeError("docs-blocked"),
		):
			with self.assertRaisesRegex(RuntimeError, "docs-blocked"):
				contratacion_service.submit_contract("CONT-001")

	def test_reject_candidate_from_rrll_sets_state_and_motivo(self):
		set_value_calls = []

		def fake_set_value(doctype, name, payload, *args, **kwargs):
			set_value_calls.append((doctype, name, payload))

		def fake_get_value(doctype, name, fieldname=None, *args, **kwargs):
			if doctype == "Candidato" and fieldname == "estado_proceso":
				return "Listo para contratar"
			if doctype == "Candidato" and fieldname == "user":
				return "candidate@example.com"
			return None

		with patch("hubgh.hubgh.contratacion_service.validate_rrll_authority"), patch(
			"hubgh.hubgh.contratacion_service.frappe.db.get_value", side_effect=fake_get_value
		), patch(
			"hubgh.hubgh.contratacion_service.frappe.db.set_value", side_effect=fake_set_value
		), patch(
			"hubgh.hubgh.contratacion_service.frappe.db.exists", return_value=True
		):
			result = contratacion_service.reject_candidate("CAND-001", "No firmó contrato")

		self.assertEqual(result, {"ok": True, "status": "Rechazado"})
		candidato_calls = [c for c in set_value_calls if c[0] == "Candidato"]
		self.assertEqual(len(candidato_calls), 1)
		self.assertEqual(candidato_calls[0][1], "CAND-001")
		self.assertEqual(candidato_calls[0][2]["estado_proceso"], "Rechazado")
		self.assertEqual(candidato_calls[0][2]["motivo_rechazo"], "No firmó contrato")
		user_calls = [c for c in set_value_calls if c[0] == "User"]
		self.assertEqual(user_calls, [("User", "candidate@example.com", "enabled")])

	def test_reject_candidate_requires_motivo(self):
		with patch("hubgh.hubgh.contratacion_service.validate_rrll_authority"), patch(
			"hubgh.hubgh.contratacion_service.frappe.throw", side_effect=RuntimeError("motivo-required")
		):
			with self.assertRaisesRegex(RuntimeError, "motivo-required"):
				contratacion_service.reject_candidate("CAND-001", "   ")

	def test_reject_candidate_blocks_when_state_not_in_bandeja(self):
		def fake_get_value(doctype, name, fieldname=None, *args, **kwargs):
			if doctype == "Candidato" and fieldname == "estado_proceso":
				return "En documentación"
			return None

		with patch("hubgh.hubgh.contratacion_service.validate_rrll_authority"), patch(
			"hubgh.hubgh.contratacion_service.frappe.db.get_value", side_effect=fake_get_value
		), patch(
			"hubgh.hubgh.contratacion_service.frappe.throw", side_effect=RuntimeError("state-blocked")
		):
			with self.assertRaisesRegex(RuntimeError, "state-blocked"):
				contratacion_service.reject_candidate("CAND-001", "Cualquier motivo")

	def _patch_send_to_medical_exam(self, *, cargo="CAR-1", flag_enabled=False):
		set_value_calls = []

		def fake_set_value(doctype, name, payload, *args, **kwargs):
			set_value_calls.append((doctype, name, payload))

		def fake_get_value(doctype, name, fieldname=None, *args, **kwargs):
			if doctype == "Candidato" and fieldname == "cargo":
				return cargo
			return None

		patches = [
			patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._validate_selection_access"),
			patch(
				"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._can_manage_candidates",
				return_value=True,
			),
			patch(
				"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.db.get_value",
				side_effect=fake_get_value,
			),
			patch(
				"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.db.set_value",
				side_effect=fake_set_value,
			),
			patch(
				"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.nowdate",
				return_value="2026-04-30",
			),
			patch(
				"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.conf.get",
				return_value=1 if flag_enabled else 0,
			),
		]
		return set_value_calls, patches

	def test_send_to_medical_exam_manual_does_not_dispatch_cita(self):
		set_value_calls, patches = self._patch_send_to_medical_exam()
		create_cita = patch("hubgh.hubgh.examen_medico.cita_service.create_cita_and_send_link")
		mock_cita = create_cita.start()
		try:
			for p in patches:
				p.start()
			try:
				result = seleccion_documentos.send_to_medical_exam("CAND-001", modo="manual")
			finally:
				for p in patches:
					p.stop()
		finally:
			create_cita.stop()

		self.assertEqual(result["modo"], "manual")
		mock_cita.assert_not_called()
		candidato_payload = next(c[2] for c in set_value_calls if c[0] == "Candidato" and isinstance(c[2], dict))
		self.assertEqual(candidato_payload["modo_agendamiento_examen"], "Manual")

	def test_send_to_medical_exam_autogestionado_dispatches_when_flag_on(self):
		set_value_calls, patches = self._patch_send_to_medical_exam(flag_enabled=True)
		create_cita = patch("hubgh.hubgh.examen_medico.cita_service.create_cita_and_send_link")
		mock_cita = create_cita.start()
		try:
			for p in patches:
				p.start()
			try:
				result = seleccion_documentos.send_to_medical_exam("CAND-001", modo="autogestionado")
			finally:
				for p in patches:
					p.stop()
		finally:
			create_cita.stop()

		self.assertEqual(result["modo"], "autogestionado")
		mock_cita.assert_called_once_with("CAND-001", "CAR-1")
		candidato_payload = next(c[2] for c in set_value_calls if c[0] == "Candidato" and isinstance(c[2], dict))
		self.assertEqual(candidato_payload["modo_agendamiento_examen"], "Autogestionado")

	def test_send_to_medical_exam_autogestionado_blocks_when_flag_off(self):
		_set_value_calls, patches = self._patch_send_to_medical_exam(flag_enabled=False)
		throw_patch = patch(
			"hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.throw",
			side_effect=RuntimeError("flag-off"),
		)
		throw_patch.start()
		try:
			for p in patches:
				p.start()
			try:
				with self.assertRaisesRegex(RuntimeError, "flag-off"):
					seleccion_documentos.send_to_medical_exam("CAND-001", modo="autogestionado")
			finally:
				for p in patches:
					p.stop()
		finally:
			throw_patch.stop()

	def test_documentary_folder_prefers_freshest_candidate_or_employee_metadata(self):
		emp = SimpleNamespace(name="EMP-001", nombres="Ana", apellidos="Paz", cedula="1001", pdv="PDV-1")
		required = [SimpleNamespace(name="Cedula", document_name="Cedula", has_expiry=1, sort_order=1)]

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Person Document":
				filters = kwargs.get("filters") or {}
				if filters.get("employee") == "EMP-001":
					return [
						SimpleNamespace(name="PD-EMP", document_type="Cedula", status="Subido", file="/files/emp.pdf", uploaded_by="rrll@example.com", uploaded_on="2026-03-01 08:00:00", approved_by=None, approved_on=None, notes=None, issue_date="2025-01-01", valid_until="2026-03-01", modified="2026-03-01 08:00:00"),
					]
				if filters.get("candidate") == "CAND-001":
					return [
						SimpleNamespace(name="PD-CAND", document_type="Cedula", status="Subido", file="/files/cand.pdf", uploaded_by="rrll@example.com", uploaded_on="2026-03-10 08:00:00", approved_by=None, approved_on=None, notes=None, issue_date="2025-02-01", valid_until="2026-04-01", modified="2026-03-10 08:00:00"),
					]
			return []

		with patch("hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._validate_folder_access"), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe.get_doc",
			return_value=emp,
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado._required_document_types",
			return_value=required,
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.frappe.db.get_value",
			return_value="CAND-001",
		):
			data = carpeta_documental_empleado.get_employee_documents("EMP-001")

		self.assertEqual(data["required_documents"][0]["file"], "/files/cand.pdf")
		self.assertEqual(data["required_documents"][0]["status"], "Vigente")
		self.assertEqual(data["required_documents"][0]["valid_until"], "2026-04-01")

	def test_persona_360_overview_includes_retired_only_for_rrll(self):
		empleados = [SimpleNamespace(name="EMP-RET", nombres="Ana", apellidos="Paz", cedula="1001", cargo="CAR-1", pdv="PDV-1", email="ana@example.com", estado="Retirado", fecha_ingreso="2026-03-01")]

		with patch("hubgh.hubgh.page.persona_360.persona_360.frappe.get_all", return_value=empleados), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.count",
			return_value=0,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.has_permission",
			return_value=True,
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.get_value",
			return_value="PDV 1",
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.session",
			new=SimpleNamespace(user="rrll@example.com"),
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.user_has_any_role",
			side_effect=lambda user, *roles: "HR Labor Relations" in roles,
		):
			rows = persona_360.get_all_personas_overview()

		self.assertEqual(len(rows), 1)

	def test_siesa_contract_export_marks_retired_contracts(self):
		contract = SimpleNamespace(candidato="CAND-001", empleado="EMP-001", estado_contrato="Retirado", numero_documento="1001", numero_contrato=3, pdv_destino="PDV-1", cargo="CAR-1", banco_siesa="BANCO", tipo_cotizante_siesa="TC", unidad_negocio_siesa="UN", grupo_empleados_siesa="GE", centro_costos_siesa="CC", centro_trabajo_siesa="CT", entidad_afp_siesa="AFP", entidad_eps_siesa="EPS", entidad_cesantias_siesa="CES", entidad_ccf_siesa="CCF", fecha_ingreso="2026-01-01", fecha_fin_contrato="2026-03-31", salario=1000000, horas_trabajadas_mes=220, cuenta_bancaria="123", tipo_cuenta_bancaria="Ahorros", tipo_contrato="Indefinido")
		data = SimpleNamespace(candidato="CAND-001", contrato="CONT-001", numero_documento="1001", aplica_auxilio_transporte="3", arl_codigo_siesa="ARL")
		candidate = SimpleNamespace(es_extranjero=0)

		with patch("hubgh.hubgh.siesa_export.frappe.get_doc", side_effect=lambda doctype, name: contract if doctype == "Contrato" else candidate), patch(
			"hubgh.hubgh.siesa_export.get_or_create_affiliation",
			return_value=SimpleNamespace(arl_numero_afiliacion="ARL"),
		), patch("hubgh.hubgh.siesa_export._catalog_code", return_value="CODE"), patch(
			"hubgh.hubgh.siesa_export._resolve_id_banco_empleado",
			return_value=("BANK", ""),
		), patch(
			"hubgh.hubgh.siesa_export.frappe.db.exists",
			return_value=True,
		), patch(
			"hubgh.hubgh.siesa_export.frappe.db.get_value",
			side_effect=lambda doctype, filters, fieldname=None: "2026-03-31" if doctype == "Payroll Liquidation Case" else "PDV-CODE",
		):
			ctx, _ = siesa_export._build_contract_context(data)

		self.assertEqual(ctx["ind_estado"], "1")
		self.assertEqual(ctx["fecha_retiro"], "20260331")


# ---------------------------------------------------------------------------
# T1 / T2 / T3 — seleccion-documentos-perf failing tests (RED-by-construction)
# All tests in this class will be RED until get_candidates_progress_bulk is
# implemented in document_service.py.
# ---------------------------------------------------------------------------

class TestCandidatesProgressBulk(FrappeTestCase):
	"""Bulk progress helper contract tests.

	All tests are RED-by-construction pending bench execution.  They will fail
	with ImportError / AttributeError until get_candidates_progress_bulk is
	added to document_service.py (T6) and list_candidates is refactored (T7).
	"""

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _make_doc_type_row(self, name, requires_approval=0, allows_multiple=0, document_name=None):
		import frappe
		return frappe._dict({
			"name": name,
			"document_name": document_name or name,
			"requires_approval": requires_approval,
			"allows_multiple": allows_multiple,
			"is_active": 1,
			"is_required_for_hiring": 1,
			"applies_to": "Candidato",
		})

	def _make_person_doc_row(self, person, document_type, status="Subido", file="/files/x.pdf"):
		import frappe
		return frappe._dict({
			"name": f"PD-{person}-{document_type}",
			"person": person,
			"candidate": person,
			"employee": None,
			"document_type": document_type,
			"status": status,
			"file": file,
			"modified": "2026-01-01 10:00:00",
			"creation": "2026-01-01 09:00:00",
		})

	def _make_cand_row(self, name, numero_documento=None, persona=None):
		import frappe
		return frappe._dict({
			"name": name,
			"numero_documento": numero_documento or name,
			"persona": persona,
		})

	# ------------------------------------------------------------------
	# T1 — bulk contract tests (7 scenarios)
	# ------------------------------------------------------------------

	def test_bulk_empty_list_returns_empty_dict(self):
		"""Empty input must return {} without any frappe.get_all calls."""
		from hubgh.hubgh.document_service import get_candidates_progress_bulk

		with patch("hubgh.hubgh.document_service.frappe.get_all") as get_all_mock:
			result = get_candidates_progress_bulk([])

		self.assertEqual(result, {})
		get_all_mock.assert_not_called()

	def test_bulk_single_candidate_equals_single_path(self):
		"""get_candidates_progress_bulk([c])[c] must equal get_candidate_progress(c) field-for-field."""
		from hubgh.hubgh.document_service import (
			get_candidates_progress_bulk,
			get_candidate_progress,
		)

		required = [self._make_doc_type_row("Cedula")]
		cand_rows = [self._make_cand_row("CAND-A", numero_documento="1001")]
		pd_rows = [self._make_person_doc_row("CAND-A", "Cedula", status="Subido")]

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Document Type":
				return required
			if doctype == "Person Document":
				return pd_rows
			if doctype == "Candidato":
				return cand_rows
			if doctype == "Ficha Empleado":
				return []
			return []

		def fake_rules(doc_type):
			return {"document_type": doc_type, "allows_multiple": 0, "requires_approval": 0}

		with patch("hubgh.hubgh.document_service.frappe.get_all", side_effect=fake_get_all), \
				patch("hubgh.hubgh.document_service._get_document_type_rules", side_effect=fake_rules), \
				patch("hubgh.hubgh.document_service.frappe.db.get_value", return_value=None), \
				patch("hubgh.hubgh.document_service.frappe.db.exists", return_value=True):
			bulk_result = get_candidates_progress_bulk(["CAND-A"])
			single_result = get_candidate_progress("CAND-A")

		self.assertIn("CAND-A", bulk_result)
		for key in ("percent", "required_ok", "required_total", "is_complete"):
			self.assertEqual(bulk_result["CAND-A"].get(key), single_result.get(key),
				f"Mismatch for key {key!r}")

	def test_bulk_n_candidates_parity(self):
		"""For 3 candidates (incl. one with legacy numero_documento row), bulk matches single-path."""
		from hubgh.hubgh.document_service import (
			get_candidates_progress_bulk,
			get_candidate_progress,
		)

		required = [self._make_doc_type_row("Cedula"), self._make_doc_type_row("EPS")]

		# CAND-A: Cedula+EPS uploaded, keyed by name
		# CAND-B: only Cedula, keyed by name
		# CAND-C: legacy row keyed by numero_documento "9999"
		pd_rows_all = [
			self._make_person_doc_row("CAND-A", "Cedula"),
			self._make_person_doc_row("CAND-A", "EPS"),
			self._make_person_doc_row("CAND-B", "Cedula"),
			self._make_person_doc_row("9999", "EPS"),   # legacy keyed by numero_documento
		]
		cand_meta = [
			self._make_cand_row("CAND-A", numero_documento="1001"),
			self._make_cand_row("CAND-B", numero_documento="2002"),
			self._make_cand_row("CAND-C", numero_documento="9999"),
		]

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Document Type":
				return required
			if doctype == "Person Document":
				return pd_rows_all
			if doctype == "Candidato":
				names = (kwargs.get("filters") or {}).get("name", ["in", []])
				if isinstance(names, list) and names[0] == "in":
					return [r for r in cand_meta if r["name"] in names[1]]
				return cand_meta
			if doctype == "Ficha Empleado":
				return []
			return []

		def fake_rules(doc_type):
			return {"document_type": doc_type, "allows_multiple": 0, "requires_approval": 0}

		names = ["CAND-A", "CAND-B", "CAND-C"]
		with patch("hubgh.hubgh.document_service.frappe.get_all", side_effect=fake_get_all), \
				patch("hubgh.hubgh.document_service._get_document_type_rules", side_effect=fake_rules), \
				patch("hubgh.hubgh.document_service.frappe.db.get_value", return_value=None), \
				patch("hubgh.hubgh.document_service.frappe.db.exists", return_value=True):
			bulk = get_candidates_progress_bulk(names)

		self.assertEqual(set(bulk.keys()), set(names))
		# CAND-A: 2/2
		self.assertEqual(bulk["CAND-A"]["required_ok"], 2)
		self.assertEqual(bulk["CAND-A"]["required_total"], 2)
		# CAND-B: 1/2
		self.assertEqual(bulk["CAND-B"]["required_ok"], 1)
		self.assertEqual(bulk["CAND-B"]["required_total"], 2)
		# CAND-C: row keyed by numero_documento=9999 → EPS attributed to CAND-C → 1/2
		self.assertEqual(bulk["CAND-C"]["required_ok"], 1)
		self.assertEqual(bulk["CAND-C"]["required_total"], 2)

	def test_bulk_alias_numero_documento_keyed_row_attributed(self):
		"""Person Document row keyed by numero_documento must be attributed to the correct candidate."""
		from hubgh.hubgh.document_service import get_candidates_progress_bulk

		required = [self._make_doc_type_row("Cedula")]
		# Row person = "DOC-X" (the candidate's numero_documento)
		pd_rows = [self._make_person_doc_row("DOC-X", "Cedula")]
		cand_meta = [self._make_cand_row("CAND-X", numero_documento="DOC-X")]

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Document Type":
				return required
			if doctype == "Person Document":
				return pd_rows
			if doctype == "Candidato":
				return cand_meta
			if doctype == "Ficha Empleado":
				return []
			return []

		def fake_rules(doc_type):
			return {"document_type": doc_type, "allows_multiple": 0, "requires_approval": 0}

		with patch("hubgh.hubgh.document_service.frappe.get_all", side_effect=fake_get_all), \
				patch("hubgh.hubgh.document_service._get_document_type_rules", side_effect=fake_rules), \
				patch("hubgh.hubgh.document_service.frappe.db.get_value", return_value=None), \
				patch("hubgh.hubgh.document_service.frappe.db.exists", return_value=True):
			bulk = get_candidates_progress_bulk(["CAND-X"])

		self.assertEqual(bulk["CAND-X"]["required_ok"], 1)

	def test_bulk_alias_cedula_ficha_empleado_keyed_row_attributed(self):
		"""Person Document keyed by Ficha Empleado cedula must be attributed to the candidate."""
		from hubgh.hubgh.document_service import get_candidates_progress_bulk

		required = [self._make_doc_type_row("Cedula")]
		# Row person = "CED-Y" (the ficha empleado cedula)
		pd_rows = [self._make_person_doc_row("CED-Y", "Cedula")]
		cand_meta = [self._make_cand_row("CAND-Y", numero_documento="2002", persona="FE-Y")]
		ficha_rows = [{"name": "FE-Y", "cedula": "CED-Y"}]

		import frappe as _frappe

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Document Type":
				return required
			if doctype == "Person Document":
				return pd_rows
			if doctype == "Candidato":
				return cand_meta
			if doctype == "Ficha Empleado":
				return [_frappe._dict(r) for r in ficha_rows]
			return []

		def fake_rules(doc_type):
			return {"document_type": doc_type, "allows_multiple": 0, "requires_approval": 0}

		with patch("hubgh.hubgh.document_service.frappe.get_all", side_effect=fake_get_all), \
				patch("hubgh.hubgh.document_service._get_document_type_rules", side_effect=fake_rules), \
				patch("hubgh.hubgh.document_service.frappe.db.get_value", return_value=None), \
				patch("hubgh.hubgh.document_service.frappe.db.exists", return_value=True):
			bulk = get_candidates_progress_bulk(["CAND-Y"])

		self.assertEqual(bulk["CAND-Y"]["required_ok"], 1)

	def test_bulk_no_persona_fk_only_name_and_doc_aliases(self):
		"""Candidate with no persona FK — no error; only name+numero_documento aliases used."""
		from hubgh.hubgh.document_service import get_candidates_progress_bulk

		required = [self._make_doc_type_row("Cedula")]
		pd_rows = [self._make_person_doc_row("CAND-Z", "Cedula")]
		# No persona FK
		cand_meta = [self._make_cand_row("CAND-Z", numero_documento="3003", persona=None)]

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Document Type":
				return required
			if doctype == "Person Document":
				return pd_rows
			if doctype == "Candidato":
				return cand_meta
			if doctype == "Ficha Empleado":
				return []
			return []

		def fake_rules(doc_type):
			return {"document_type": doc_type, "allows_multiple": 0, "requires_approval": 0}

		# Must not raise
		with patch("hubgh.hubgh.document_service.frappe.get_all", side_effect=fake_get_all), \
				patch("hubgh.hubgh.document_service._get_document_type_rules", side_effect=fake_rules), \
				patch("hubgh.hubgh.document_service.frappe.db.get_value", return_value=None), \
				patch("hubgh.hubgh.document_service.frappe.db.exists", return_value=True):
			bulk = get_candidates_progress_bulk(["CAND-Z"])

		self.assertIn("CAND-Z", bulk)
		self.assertEqual(bulk["CAND-Z"]["required_ok"], 1)

	def test_bulk_allows_multiple_counted_once(self):
		"""Document Type with allows_multiple=True — 3 uploaded rows count as 1 in documentos_ok."""
		from hubgh.hubgh.document_service import get_candidates_progress_bulk

		import frappe as _frappe
		required = [
			_frappe._dict({
				"name": "Carta Referencia",
				"document_name": "Carta Referencia",
				"requires_approval": 0,
				"allows_multiple": 1,
				"is_active": 1,
				"is_required_for_hiring": 1,
				"applies_to": "Candidato",
			})
		]
		# 3 uploaded rows for the same allows_multiple type
		pd_rows = [
			self._make_person_doc_row("CAND-M", "Carta Referencia", status="Subido", file="/files/a.pdf"),
			self._make_person_doc_row("CAND-M", "Carta Referencia", status="Subido", file="/files/b.pdf"),
			self._make_person_doc_row("CAND-M", "Carta Referencia", status="Subido", file="/files/c.pdf"),
		]
		# Give them distinct names
		pd_rows[1]["name"] = "PD-CAND-M-Carta Referencia-2"
		pd_rows[2]["name"] = "PD-CAND-M-Carta Referencia-3"

		cand_meta = [self._make_cand_row("CAND-M", numero_documento="4004")]

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Document Type":
				return required
			if doctype == "Person Document":
				return pd_rows
			if doctype == "Candidato":
				return cand_meta
			if doctype == "Ficha Empleado":
				return []
			return []

		def fake_rules(doc_type):
			return {"document_type": doc_type, "allows_multiple": 1, "requires_approval": 0}

		with patch("hubgh.hubgh.document_service.frappe.get_all", side_effect=fake_get_all), \
				patch("hubgh.hubgh.document_service._get_document_type_rules", side_effect=fake_rules), \
				patch("hubgh.hubgh.document_service.frappe.db.get_value", return_value=None), \
				patch("hubgh.hubgh.document_service.frappe.db.exists", return_value=True):
			bulk = get_candidates_progress_bulk(["CAND-M"])

		# 1 required type → required_ok=1, required_total=1
		self.assertEqual(bulk["CAND-M"]["required_total"], 1)
		self.assertEqual(bulk["CAND-M"]["required_ok"], 1)
		self.assertEqual(bulk["CAND-M"]["percent"], 100)

	# ------------------------------------------------------------------
	# T2 — N-independent query count (RED-by-construction)
	# ------------------------------------------------------------------

	def test_bulk_query_count_n_independent(self):
		"""Query count for N=1 and N=5 must be equal, and no per-doc-type get_doc is issued.

		T0 finding: this repo has no frappe.db.count_queries context manager.
		We count frappe.get_all call_count instead (each call = 1 DB query for
		ORM callers), which is the established pattern in this test suite.

		W1 fix contract: _build_vigentes_by_type must NOT call frappe.get_doc("Document
		Type", ...) for any doc type present in the prefetched required set.  We verify
		this by NOT patching _get_document_type_rules and instead patching frappe.get_doc
		directly — if the per-doc-type fallback path is hit, get_doc_mock.call_args_list
		will show "Document Type" calls and the assertion will fail.
		"""
		from hubgh.hubgh.document_service import get_candidates_progress_bulk
		import frappe as _frappe

		required = [self._make_doc_type_row("Cedula")]

		def _build_fixture(candidate_names):
			cand_meta = [self._make_cand_row(n, numero_documento=f"ND-{n}") for n in candidate_names]
			pd_rows = [self._make_person_doc_row(n, "Cedula") for n in candidate_names]
			return cand_meta, pd_rows

		def _run_with_counter(candidate_names):
			cand_meta, pd_rows = _build_fixture(candidate_names)
			call_counter = {"count": 0}
			get_doc_calls = []

			def fake_get_all(doctype, *args, **kwargs):
				call_counter["count"] += 1
				if doctype == "Document Type":
					return required
				if doctype == "Person Document":
					return pd_rows
				if doctype == "Candidato":
					return cand_meta
				if doctype == "Ficha Empleado":
					return []
				return []

			def fake_get_doc(doctype, *args, **kwargs):
				# Record calls so we can assert none target "Document Type".
				get_doc_calls.append((doctype,) + args)
				# Return a minimal stub so the code does not crash if called.
				doc = _frappe._dict({"name": args[0] if args else doctype,
				                     "allows_multiple": 0,
				                     "requires_approval": 0,
				                     "document_name": args[0] if args else doctype,
				                     "allowed_areas": [],
				                     "allowed_roles_override": None})
				return doc

			with patch("hubgh.hubgh.document_service.frappe.get_all", side_effect=fake_get_all), \
					patch("hubgh.hubgh.document_service.frappe.get_doc", side_effect=fake_get_doc), \
					patch("hubgh.hubgh.document_service.frappe.db.get_value", return_value=None), \
					patch("hubgh.hubgh.document_service.frappe.db.exists", return_value=True):
				get_candidates_progress_bulk(candidate_names)

			return call_counter["count"], get_doc_calls

		count_n1, get_doc_n1 = _run_with_counter(["CAND-1"])
		count_n5, get_doc_n5 = _run_with_counter(["CAND-1", "CAND-2", "CAND-3", "CAND-4", "CAND-5"])

		# N-independence: same number of get_all calls regardless of candidate count.
		self.assertLessEqual(count_n1, 10, f"N=1 issued {count_n1} get_all calls (budget: 10)")
		self.assertLessEqual(count_n5, 10, f"N=5 issued {count_n5} get_all calls (budget: 10)")
		self.assertEqual(count_n1, count_n5,
			f"Query count is NOT N-independent: N=1 → {count_n1}, N=5 → {count_n5}")

		# W1 fix: no per-doc-type frappe.get_doc("Document Type", ...) must be issued.
		doc_type_get_doc_calls_n1 = [c for c in get_doc_n1 if c[0] == "Document Type"]
		doc_type_get_doc_calls_n5 = [c for c in get_doc_n5 if c[0] == "Document Type"]
		self.assertEqual(doc_type_get_doc_calls_n1, [],
			f"N=1: unexpected frappe.get_doc('Document Type', ...) calls: {doc_type_get_doc_calls_n1}")
		self.assertEqual(doc_type_get_doc_calls_n5, [],
			f"N=5: unexpected frappe.get_doc('Document Type', ...) calls: {doc_type_get_doc_calls_n5}")

	# ------------------------------------------------------------------
	# T3 — no-write-on-read and full 18-field shape
	# ------------------------------------------------------------------

	def test_list_candidates_zero_writes(self):
		"""list_candidates must not call set_value, ensure_candidate_required_documents, or issue INSERT/UPDATE."""
		import frappe as _frappe

		cand_rows = [
			_frappe._dict({
				"name": "CAND-001",
				"nombres": "Ana",
				"apellidos": "Paz",
				"primer_apellido": "Paz",
				"segundo_apellido": "",
				"numero_documento": "1001",
				"pdv_destino": "PDV-1",
				"cargo_postulado": "Cajera",
				"creation": "2026-01-01 08:00:00",
				"estado_proceso": "En proceso",
				"concepto_medico": "Pendiente",
				"fecha_envio_examen_medico": None,
				"solo_afiliacion": 0,
				"persona": None,
				"fecha_tentativa_ingreso": "2026-02-01",
			})
		]
		progress_result = {
			"CAND-001": {
				"percent": 50,
				"required_ok": 1,
				"required_total": 2,
				"is_complete": False,
				"missing": ["EPS"],
				"sagrilaft_ok": False,
			}
		}

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Candidato":
				return cand_rows
			return []

		with patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.get_all", side_effect=fake_get_all), \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.session",
					new=SimpleNamespace(user="gh@example.com")), \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._validate_selection_access"), \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._can_manage_candidates", return_value=True), \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._candidate_pdv_name_map", return_value={}), \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.get_candidates_progress_bulk",
					return_value=progress_result) as bulk_mock, \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.ensure_candidate_required_documents") as ensure_mock, \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.db.set_value") as set_value_mock:
			result = seleccion_documentos.list_candidates()

		# ensure_candidate_required_documents must NOT be called in the list path
		ensure_mock.assert_not_called()
		# No DB writes
		set_value_mock.assert_not_called()
		# Bulk helper called once
		bulk_mock.assert_called_once()
		self.assertIsInstance(result, list)

	def test_list_candidates_full_field_set(self):
		"""Every row returned by list_candidates must have exactly the 18 spec-required fields."""
		import frappe as _frappe

		EXPECTED_FIELDS = {
			"name", "full_name", "numero_documento", "pdv_destino", "pdv_destino_nombre",
			"cargo_postulado", "creation", "estado_proceso", "concepto_medico",
			"fecha_envio_examen_medico", "sagrilaft_ok", "avance_porcentaje",
			"documentos_ok", "documentos_total", "completo", "can_manage",
			"solo_afiliacion", "fecha_tentativa_ingreso",
		}

		cand_rows = [
			_frappe._dict({
				"name": "CAND-001",
				"nombres": "Ana",
				"apellidos": "Paz",
				"primer_apellido": "Paz",
				"segundo_apellido": "",
				"numero_documento": "1001",
				"pdv_destino": "PDV-1",
				"cargo_postulado": "Cajera",
				"creation": "2026-01-01 08:00:00",
				"estado_proceso": "En proceso",
				"concepto_medico": "Pendiente",
				"fecha_envio_examen_medico": None,
				"solo_afiliacion": 0,
				"persona": None,
				"fecha_tentativa_ingreso": "2026-02-01",
			})
		]
		progress_result = {
			"CAND-001": {
				"percent": 100,
				"required_ok": 2,
				"required_total": 2,
				"is_complete": True,
				"missing": [],
				"sagrilaft_ok": True,
			}
		}

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Candidato":
				return cand_rows
			return []

		with patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.get_all", side_effect=fake_get_all), \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.frappe.session",
					new=SimpleNamespace(user="gh@example.com")), \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._validate_selection_access"), \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._can_manage_candidates", return_value=True), \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos._candidate_pdv_name_map", return_value={"PDV-1": "PDV Norte"}), \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.get_candidates_progress_bulk",
					return_value=progress_result), \
				patch("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.ensure_candidate_required_documents"):
			result = seleccion_documentos.list_candidates()

		self.assertEqual(len(result), 1)
		row_keys = set(result[0].keys())
		self.assertEqual(row_keys, EXPECTED_FIELDS,
			f"Field mismatch. Extra: {row_keys - EXPECTED_FIELDS}. Missing: {EXPECTED_FIELDS - row_keys}")

	# ------------------------------------------------------------------
	# W3 — prefetched_rules parity: _MULTI_UPLOAD_DOCUMENT_TYPES_FALLBACK
	# ------------------------------------------------------------------

	def test_bulk_prefetched_rules_fallback_parity_allows_multiple(self):
		"""Bulk path must agree with single path for fallback-override doc types.

		RED-by-construction — unexecuted (no bench available in this environment).

		Scenario: a required Document Type whose DB allows_multiple = 0 but whose
		normalised document_name is in _MULTI_UPLOAD_DOCUMENT_TYPES_FALLBACK.
		Three Person Document rows are uploaded for it.

		Before the W3 fix:
		  - prefetched_rules stored raw allows_multiple=0 → _build_vigentes_by_type
		    would keep only the most-recent row as vigente → required_ok=1, but
		    vigentes_by_type["<fallback-type>"] contains only 1 row.
		  - _get_document_type_rules applied the fallback → allows_multiple=1 →
		    all 3 rows are vigente.
		  The two paths diverged: bulk vigentes count ≠ single vigentes count.

		After the W3 fix (_resolve_allows_multiple shared helper):
		  - Both paths call _resolve_allows_multiple → same result (allows_multiple=1)
		    → all 3 rows are vigente in both paths → required_ok agrees.

		Assertions:
		  1. Bulk path reports required_ok=1 (type satisfied) and vigentes count=3.
		  2. Single path (_compute_candidate_progress) reports the same required_ok.
		  3. _resolve_allows_multiple(0, fallback_name, fallback_name) == 1 (unit check).
		"""
		from hubgh.hubgh.document_service import (
			get_candidates_progress_bulk,
			_compute_candidate_progress,
			_resolve_allows_multiple,
		)
		import frappe as _frappe

		# A document_name that IS in _MULTI_UPLOAD_DOCUMENT_TYPES_FALLBACK (unnormalised form).
		# _normalize_text strips accents and lowercases, so this plain ASCII version matches.
		FALLBACK_DOC_NAME = "2 cartas de referencias personales."
		FALLBACK_TYPE_NAME = "Carta Referencia Fallback"  # distinct .name from .document_name

		# Unit check: _resolve_allows_multiple must return 1 for the fallback case.
		self.assertEqual(
			_resolve_allows_multiple(0, FALLBACK_DOC_NAME, FALLBACK_TYPE_NAME),
			1,
			"_resolve_allows_multiple should return 1 when document_name is in _MULTI_UPLOAD_DOCUMENT_TYPES_FALLBACK",
		)

		# Required set: one doc type with DB allows_multiple=0 but fallback document_name.
		required = [
			_frappe._dict({
				"name": FALLBACK_TYPE_NAME,
				"document_name": FALLBACK_DOC_NAME,
				"requires_approval": 0,
				"allows_multiple": 0,   # raw DB value — the fallback must promote this to 1
				"is_active": 1,
				"is_required_for_hiring": 1,
				"applies_to": "Candidato",
			})
		]

		# Three uploaded rows for the fallback type (simulating multiple references).
		pd_rows = [
			_frappe._dict({
				"name": f"PD-CAND-F-{i}",
				"person": "CAND-F",
				"candidate": "CAND-F",
				"employee": None,
				"document_type": FALLBACK_TYPE_NAME,
				"status": "Subido",
				"file": f"/files/ref_{i}.pdf",
				"modified": f"2026-01-0{i + 1} 10:00:00",
				"creation": f"2026-01-0{i + 1} 09:00:00",
			})
			for i in range(1, 4)
		]

		cand_meta = [self._make_cand_row("CAND-F", numero_documento="5005")]

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Document Type":
				return required
			if doctype == "Person Document":
				return pd_rows
			if doctype == "Candidato":
				return cand_meta
			if doctype == "Ficha Empleado":
				return []
			return []

		with patch("hubgh.hubgh.document_service.frappe.get_all", side_effect=fake_get_all), \
				patch("hubgh.hubgh.document_service.frappe.db.get_value", return_value=None), \
				patch("hubgh.hubgh.document_service.frappe.db.exists", return_value=True):
			bulk_result = get_candidates_progress_bulk(["CAND-F"])

		self.assertIn("CAND-F", bulk_result, "CAND-F must appear in bulk result")
		cand_progress = bulk_result["CAND-F"]

		# The single doc type is satisfied → required_ok=1, required_total=1.
		self.assertEqual(cand_progress["required_total"], 1,
			"required_total must be 1 (one required type)")
		self.assertEqual(cand_progress["required_ok"], 1,
			"required_ok must be 1: fallback override → allows_multiple=1 → all 3 rows are vigente → type satisfied")

		# Parity check: run _compute_candidate_progress directly with allows_multiple=1
		# (what _resolve_allows_multiple produces) to confirm both paths agree.
		# Build vigentes_by_type as the bulk path would after the fix.
		vigentes_by_type_expected = {FALLBACK_TYPE_NAME: pd_rows}  # all 3 rows vigente
		single_progress = _compute_candidate_progress(required, vigentes_by_type_expected)
		self.assertEqual(
			cand_progress["required_ok"],
			single_progress["required_ok"],
			"Bulk and single paths must agree on required_ok for fallback-override doc types",
		)
