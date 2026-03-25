from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.api import ops
from hubgh.hubgh.page.persona_360 import persona_360
from hubgh.hubgh.page.punto_360 import punto_360
from hubgh.hubgh import contratacion_service
from hubgh.hubgh import people_ops_event_publishers
from hubgh.hubgh import people_ops_handoffs
from hubgh.hubgh import people_ops_policy


FIXED_NOW = datetime(2026, 3, 21, 9, 0, 0)


class _FakeInsertableDoc:
	def __init__(self, name, payload=None, collector=None):
		self.name = name
		self.payload = payload
		self.collector = collector

	def insert(self, **kwargs):
		if self.collector is not None:
			self.collector.append(self.payload)


class TestPeopleOpsBackbone(FrappeTestCase):
	def test_persona_360_baseline_contract_keys(self):
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
			return_value=[],
		), patch(
			"hubgh.hubgh.page.persona_360.persona_360.frappe.db.exists",
			return_value=False,
		):
			payload = persona_360.get_persona_stats("EMP-001")

		for key in [
			"info",
			"timeline",
			"timeline_sections",
			"sst_cards",
			"filters_applied",
			"contextual_actions",
			"bienestar_followups",
		]:
			self.assertIn(key, payload)

	def test_punto_360_baseline_contract_keys(self):
		punto_doc = SimpleNamespace(nombre_pdv="PDV 1", zona="Norte", planta_autorizada=10)

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

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Ficha Empleado":
				return [SimpleNamespace(name="EMP-001")]
			if doctype == "GH Novedad":
				return [{"descripcion": "Ingreso formalizado desde contrato CONT-001"}]
			return []

		with patch("hubgh.hubgh.page.punto_360.punto_360.frappe.has_permission", return_value=True), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_doc",
			return_value=punto_doc,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.db.count",
			return_value=1,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.get_all",
			side_effect=fake_get_all,
		), patch(
			"hubgh.hubgh.page.punto_360.punto_360.frappe.db.exists",
			side_effect=fake_exists,
		), patch("hubgh.hubgh.page.punto_360.punto_360.nowdate", return_value="2026-03-21"):
			payload = punto_360.get_punto_stats("PDV-1")

		self.assertIn("info", payload)
		self.assertIn("kpi_operativo", payload["info"])
		self.assertIn("kpi_sst", payload["info"])
		self.assertIn("kpi_ingreso", payload["info"])
		self.assertIn("kpi_liderazgo", payload["info"])
		self.assertIn("kpi_bienestar", payload["info"])
		self.assertIn("kpi_clima", payload["info"])
		self.assertIn("kpi_formacion", payload["info"])
		self.assertIn("actionable_hub", payload)
		self.assertIn("widgets", payload["actionable_hub"])
		self.assertIn("feeds", payload["actionable_hub"])
		self.assertIn("contextual_actions", payload["actionable_hub"])
		self.assertIn("tray_reports", payload["actionable_hub"])

	def test_operacion_punto_lite_uses_sst_as_canonical_source_for_incapacidad(self):
		personas = [{"name": "EMP-001", "nombres": "Ana", "apellidos": "Paz", "estado": "Activo", "email": "ana@example.com"}]

		def fake_count(doctype, filters=None):
			if doctype == "Ficha Empleado":
				return 1
			if doctype == "Novedad SST":
				self.assertEqual(filters["punto_venta"], "PDV-1")
				self.assertEqual(filters["es_incapacidad"], 1)
				return 2
			if doctype == "GH Novedad":
				return 7
			return 0

		with patch("hubgh.api.ops._get_session_employee", return_value={"pdv": "PDV-1"}), patch(
			"hubgh.api.ops.frappe.db.get_value",
			return_value="PDV 1",
		), patch(
			"hubgh.api.ops.frappe.get_all",
			return_value=personas,
		), patch(
			"hubgh.api.ops._build_pdv_lms_report",
			return_value=([], {}),
		), patch(
			"hubgh.api.ops.frappe.db.count",
			side_effect=fake_count,
		), patch(
			"hubgh.api.ops.nowdate",
			return_value="2026-03-21",
		):
			payload = ops.get_punto_lite()

		self.assertEqual(payload["kpis"]["incapacidades_abiertas"], 2)

	def test_people_ops_event_publish_is_idempotent(self):
		inserted_docs = []
		original_get_doc = frappe.get_doc

		def fake_exists(doctype, filters=None):
			if doctype == "DocType":
				return True
			if doctype == "People Ops Event" and isinstance(filters, dict):
				return "POE-00001" if inserted_docs else None
			return None

		def fake_get_doc(payload):
			if not isinstance(payload, dict) or payload.get("doctype") != "People Ops Event":
				return original_get_doc(payload)
			return _FakeInsertableDoc(name="POE-00001", payload=payload, collector=inserted_docs)

		with patch("hubgh.hubgh.people_ops_event_publishers.frappe.get_site_config", return_value={}), patch(
			"hubgh.hubgh.people_ops_event_publishers.frappe.db.exists",
			side_effect=fake_exists,
		), patch(
			"hubgh.hubgh.people_ops_event_publishers.frappe.get_doc",
			side_effect=fake_get_doc,
		), patch(
			"hubgh.hubgh.people_ops_event_publishers.now_datetime",
			return_value=FIXED_NOW,
		):
			payload = {
				"persona": "EMP-001",
				"area": "sst",
				"taxonomy": "sst.novedad.accidente",
				"sensitivity": "clinical",
				"state": "Abierta",
				"severity": "Accidente",
				"source_doctype": "Novedad SST",
				"source_name": "NOV-001",
			}
			first = people_ops_event_publishers.publish_people_ops_event(payload)
			second = people_ops_event_publishers.publish_people_ops_event(payload)

		self.assertEqual(first, "POE-00001")
		self.assertEqual(second, "POE-00001")
		self.assertEqual(len(inserted_docs), 1)

	def test_people_ops_event_publishers_exclude_lms_area(self):
		self.assertNotIn("lms", people_ops_event_publishers.SUPPORTED_AREAS)
		self.assertNotIn("formacion", people_ops_event_publishers.SUPPORTED_AREAS)

	def test_people_ops_event_publish_supports_nomina_and_normalizes_taxonomy(self):
		captured = {}
		original_get_doc = frappe.get_doc

		def fake_get_doc(payload):
			if not isinstance(payload, dict) or payload.get("doctype") != "People Ops Event":
				return original_get_doc(payload)
			captured.update(payload)
			return _FakeInsertableDoc(name="POE-900")

		with patch("hubgh.hubgh.people_ops_event_publishers.frappe.db.exists", side_effect=lambda doctype, filters=None: doctype == "DocType"), patch(
			"hubgh.hubgh.people_ops_event_publishers.resolve_backbone_mode",
			return_value="warn",
		), patch(
			"hubgh.hubgh.people_ops_event_publishers.frappe.get_doc",
			side_effect=fake_get_doc,
		), patch(
			"hubgh.hubgh.people_ops_event_publishers.now_datetime",
			return_value=FIXED_NOW,
		):
			res = people_ops_event_publishers.publish_people_ops_event(
				{
					"persona": "EMP-001",
					"area": "nomina",
					"taxonomy": "tc_revisada",
					"sensitivity": "sst_clinical",
					"source_doctype": "Payroll Import Line",
					"source_name": "PIL-001",
				}
			)

		self.assertEqual(res, "POE-900")
		self.assertEqual(captured["area"], "nomina")
		self.assertEqual(captured["taxonomy"], "nomina.tc_revisada")
		self.assertEqual(captured["sensitivity"], "clinical")

	def test_people_ops_event_enforce_rejects_unsupported_area(self):
		with patch("hubgh.hubgh.people_ops_event_publishers.resolve_backbone_mode", return_value="enforce"):
			res = people_ops_event_publishers.publish_people_ops_event(
				{
					"persona": "EMP-001",
					"area": "invalid-area",
					"taxonomy": "invalid.event",
					"source_doctype": "GH Novedad",
					"source_name": "NOV-001",
				}
			)

		self.assertIsNone(res)

	def test_people_ops_policy_warn_mode_audits_without_blocking(self):
		with patch("hubgh.hubgh.people_ops_policy.frappe.get_site_config", return_value={"hubgh_people_ops_policy_mode": "warn"}), patch(
			"hubgh.hubgh.people_ops_policy.frappe.get_roles",
			return_value=["Empleado"],
		):
			decision = people_ops_policy.evaluate_dimension_access("clinical", user="empleado@example.com", surface="persona_360")

		self.assertEqual(decision["mode"], "warn")
		self.assertFalse(decision["allowed_by_role"])
		self.assertTrue(decision["effective_allowed"])
		self.assertTrue(decision["violated"])

	def test_people_ops_policy_enforce_blocks_without_permission(self):
		with patch("hubgh.hubgh.people_ops_policy.frappe.get_site_config", return_value={"hubgh_people_ops_policy_mode": "enforce"}), patch(
			"hubgh.hubgh.people_ops_policy.frappe.get_roles",
			return_value=["Empleado"],
		):
			decision = people_ops_policy.evaluate_dimension_access("clinical", user="empleado@example.com", surface="persona_360")

		self.assertEqual(decision["mode"], "enforce")
		self.assertFalse(decision["allowed_by_role"])
		self.assertFalse(decision["effective_allowed"])
		self.assertTrue(decision["violated"])

	def test_people_ops_handoff_contract_validates_selection_to_rrll(self):
		ready = people_ops_handoffs.validate_handoff_contract(
			"selection_to_rrll",
			{
				"contrato": "CONT-001",
				"punto": "PDV-1",
				"fecha_ingreso": "2026-03-20",
			},
			actor_roles={"HR Selection"},
		)
		blocked = people_ops_handoffs.validate_handoff_contract(
			"selection_to_rrll",
			{
				"contrato": "CONT-001",
				"fecha_ingreso": "2026-03-20",
			},
			actor_roles={"Empleado"},
		)

		self.assertEqual(ready["status"], "ready")
		self.assertEqual(blocked["status"], "blocked")
		self.assertIn("punto", blocked["missing_fields"])
		self.assertIn("missing_permissions", blocked["errors"])

	def test_people_ops_handoff_contract_supports_pending_and_completed_states(self):
		pending = people_ops_handoffs.validate_handoff_contract(
			"wellbeing_to_rrll",
			{
				"persona": "EMP-001",
				"source": "BEP-001",
				"causal": "Periodo de prueba - No aprobado",
				"status": "pending",
			},
			actor_roles={"HR Training & Wellbeing"},
		)
		completed = people_ops_handoffs.validate_handoff_contract(
			"sst_to_persona360",
			{
				"persona": "EMP-001",
				"source": "NOV-001",
				"state": "Cerrada",
				"status": "completed",
			},
			actor_roles={"HR SST"},
		)

		self.assertEqual(pending["status"], "pending")
		self.assertEqual(pending["status_reason"], "handoff_pending")
		self.assertEqual(completed["status"], "completed")
		self.assertEqual(completed["status_reason"], "handoff_completed")

	def test_selection_to_rrll_minimum_gate_requires_core_docs_and_target_data(self):
		ready = people_ops_handoffs.validate_selection_to_rrll_gate(
			{
				"medical_concept": "Favorable",
				"required_documents": {"SAGRILAFT": True},
				"target_data": {"pdv_destino": "PDV-1", "fecha_tentativa_ingreso": "2026-03-20"},
			}
		)
		blocked = people_ops_handoffs.validate_selection_to_rrll_gate(
			{
				"medical_concept": "Pendiente",
				"required_documents": {"SAGRILAFT": False},
				"target_data": {"pdv_destino": "", "fecha_tentativa_ingreso": ""},
			}
		)

		self.assertEqual(ready["status"], "ready")
		self.assertEqual(blocked["status"], "blocked")
		self.assertIn("medical_concept_not_favorable", blocked["errors"])
		self.assertIn("missing_document_sagrilaft", blocked["errors"])
		self.assertIn("missing_pdv_destino", blocked["errors"])
		self.assertIn("missing_fecha_tentativa_ingreso", blocked["errors"])

	def test_people_ops_handoff_contract_defaults_invalid_status_to_ready(self):
		result = people_ops_handoffs.validate_handoff_contract(
			"sst_to_persona360",
			{
				"persona": "EMP-001",
				"source": "NOV-001",
				"state": "Abierta",
				"status": "legacy-state",
			},
			actor_roles={"HR SST"},
		)

		self.assertEqual(result["status"], "ready")
		self.assertEqual(result["status_reason"], "validation_passed")

	def test_submit_contract_returns_selection_to_rrll_handoff_contract(self):
		doc = SimpleNamespace(
			name="CONT-001",
			empleado="EMP-001",
			candidato="CAND-001",
			pdv_destino="PDV-1",
			fecha_ingreso="2026-03-20",
			docstatus=1,
		)
		doc.get = lambda fieldname, default=None: getattr(doc, fieldname, default)

		with patch("hubgh.hubgh.contratacion_service.validate_rrll_authority"), patch(
			"hubgh.hubgh.contratacion_service.frappe.get_doc",
			return_value=doc,
		), patch("hubgh.hubgh.contratacion_service._validate_mandatory_ingreso_gate"), patch(
			"hubgh.hubgh.contratacion_service.get_or_create_datos_contratacion"
		), patch(
			"hubgh.hubgh.contratacion_service.validate_handoff_contract",
			return_value={"handoff_type": "selection_to_rrll", "status": "completed"},
		) as handoff_mock:
			res = contratacion_service.submit_contract("CONT-001")

		handoff_mock.assert_called_once()
		self.assertEqual(handoff_mock.call_args.kwargs["lifecycle_state"], "completed")
		self.assertEqual(res["handoff_contract"]["handoff_type"], "selection_to_rrll")
		self.assertEqual(res["handoff_contract"]["status"], "completed")

	def test_publish_from_gh_novedad_adds_candidate_employee_lineage_refs_for_ingreso(self):
		captured = {}
		doc = SimpleNamespace(
			persona="EMP-001",
			tipo="Otro",
			descripcion="Ingreso formalizado desde contrato CONT-001",
			name="NOV-001",
		)

		def fake_publish(payload):
			captured.update(payload)
			return "POE-1"

		with patch("hubgh.hubgh.people_ops_event_publishers.publish_people_ops_event", side_effect=fake_publish), patch(
			"hubgh.hubgh.people_ops_event_publishers.frappe.db.exists",
			return_value=True,
		), patch(
			"hubgh.hubgh.people_ops_event_publishers.frappe.db.get_value",
			return_value="CAND-001",
		):
			result = people_ops_event_publishers.publish_from_gh_novedad(doc)

		self.assertEqual(result, "POE-1")
		self.assertEqual(captured["taxonomy"], "rrll.ingreso_formalizado")
		self.assertEqual(captured["refs"]["candidate"], "CAND-001")
		self.assertEqual(captured["refs"]["lineage"]["employee"], "EMP-001")
		self.assertEqual(captured["refs"]["lineage"]["candidate"], "CAND-001")
		self.assertEqual(captured["refs"]["contrato"], "CONT-001")

	def test_publish_from_caso_disciplinario_uses_closure_taxonomy_with_audit_refs(self):
		captured = {}
		doc = SimpleNamespace(
			empleado="EMP-001",
			estado="Cerrado",
			tipo_falta="Grave",
			decision_final="Terminación",
			fecha_cierre="2026-03-20",
			fecha_incidente="2026-03-19",
			name="DIS-001",
		)

		def fake_publish(payload):
			captured.update(payload)
			return "POE-77"

		with patch("hubgh.hubgh.people_ops_event_publishers.publish_people_ops_event", side_effect=fake_publish):
			result = people_ops_event_publishers.publish_from_caso_disciplinario(doc)

		self.assertEqual(result, "POE-77")
		self.assertEqual(captured["taxonomy"], "rrll.disciplinario.cierre")
		self.assertEqual(captured["refs"]["decision_final"], "Terminación")
		self.assertEqual(captured["refs"]["fecha_cierre"], "2026-03-20")
		self.assertTrue(captured["refs"]["closure_auditable"])
