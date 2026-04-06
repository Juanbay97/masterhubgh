from types import SimpleNamespace
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from hubgh.api import ops
from hubgh.lms import hardening, integration_hooks
from hubgh.seed_operational_enablement import ensure_lms_single_entrypoint


class TestLmsHardeningPhase7(FrappeTestCase):
	def test_ensure_lms_single_entrypoint_keeps_capacitacion_lms_only(self):
		class _WorkspaceStub:
			def __init__(self):
				self.links = [
					SimpleNamespace(label="Comentario Bienestar", link_to="Comentario Bienestar"),
					SimpleNamespace(label="Ir al LMS", link_to="/lms"),
				]
				self.shortcuts = [
					SimpleNamespace(label="Cursos", link_to="LMS Course"),
					SimpleNamespace(label="Bandeja Bienestar", link_to="bienestar_bandeja"),
				]
				self.content = ""
				self.saved = False

			def set(self, fieldname, value):
				setattr(self, fieldname, value)

			def append(self, fieldname, value):
				getattr(self, fieldname).append(SimpleNamespace(**value))

			def save(self, ignore_permissions=False):
				self.saved = True

		workspace = _WorkspaceStub()

		def _exists(doctype, name):
			if doctype != "Workspace":
				return False
			return name == "Capacitación"

		with patch("hubgh.seed_operational_enablement.frappe.db.exists", side_effect=_exists), patch(
			"hubgh.seed_operational_enablement.frappe.get_doc", return_value=workspace
		), patch("hubgh.seed_operational_enablement.frappe.delete_doc") as delete_doc:
			ensure_lms_single_entrypoint()

		delete_doc.assert_not_called()
		self.assertTrue(workspace.saved)
		self.assertTrue(all((row.link_to or "") != "Comentario Bienestar" for row in workspace.links))

		shortcut_links = {row.link_to for row in workspace.shortcuts}
		self.assertIn("LMS Course", shortcut_links)
		self.assertIn("LMS Enrollment", shortcut_links)
		self.assertIn("LMS Certificate", shortcut_links)
		self.assertNotIn("Bienestar Proceso Colaborador", shortcut_links)
		self.assertNotIn("Bienestar Seguimiento Ingreso", shortcut_links)
		self.assertNotIn("Bienestar Evaluacion Periodo Prueba", shortcut_links)
		self.assertNotIn("Bienestar Alerta", shortcut_links)
		self.assertNotIn("Bienestar Compromiso", shortcut_links)
		self.assertNotIn("Bienestar Levantamiento Punto", shortcut_links)
		self.assertNotIn("persona_360", shortcut_links)
		self.assertIn("Gestión de Cursos", workspace.content)
		self.assertNotIn("Bienestar Operativo", workspace.content)

	def test_ensure_lms_single_entrypoint_sets_bienestar_workspace_and_hides_legacy(self):
		class _WorkspaceStub:
			def __init__(self, shortcuts=None):
				self.links = []
				self.shortcuts = shortcuts or []
				self.content = ""
				self.saved = False
				self.is_hidden = 0
				self.public = 1

			def set(self, fieldname, value):
				setattr(self, fieldname, value)

			def append(self, fieldname, value):
				getattr(self, fieldname).append(SimpleNamespace(**value))

			def save(self, ignore_permissions=False):
				self.saved = True

		legacy_ws = _WorkspaceStub()
		cap_ws = _WorkspaceStub()
		bienestar_ws = _WorkspaceStub(shortcuts=[SimpleNamespace(label="Proceso Colaborador", link_to="Bienestar Proceso Colaborador")])

		def _exists(doctype, name):
			if doctype != "Workspace":
				return False
			return name in {"Capacitación", "Bienestar", "Formación y Bienestar"}

		def _get_doc(doctype, name):
			if doctype != "Workspace":
				raise AssertionError("unexpected doctype")
			if name == "Capacitación":
				return cap_ws
			if name == "Bienestar":
				return bienestar_ws
			if name == "Formación y Bienestar":
				return legacy_ws
			raise AssertionError(f"unexpected workspace {name}")

		with patch("hubgh.seed_operational_enablement.frappe.db.exists", side_effect=_exists), patch(
			"hubgh.seed_operational_enablement.frappe.get_doc", side_effect=_get_doc
		), patch("hubgh.seed_operational_enablement.frappe.delete_doc") as delete_doc:
			ensure_lms_single_entrypoint()

		delete_doc.assert_not_called()
		self.assertEqual(legacy_ws.is_hidden, 1)
		self.assertEqual(legacy_ws.public, 0)

		bienestar_links = {row.link_to for row in bienestar_ws.shortcuts}
		self.assertIn("bienestar_bandeja", bienestar_links)
		self.assertIn("Bienestar Evaluacion Periodo Prueba", bienestar_links)
		self.assertIn("Bienestar Seguimiento Ingreso", bienestar_links)
		self.assertIn("Bienestar Alerta", bienestar_links)
		self.assertIn("Bienestar Compromiso", bienestar_links)
		self.assertIn("Bienestar Levantamiento Punto", bienestar_links)
		self.assertIn("persona_360", bienestar_links)
		self.assertNotIn("Bienestar Proceso Colaborador", bienestar_links)

	def test_get_lms_course_name_prefers_site_config(self):
		with patch("hubgh.lms.hardening.frappe.conf", {"hubgh_lms_course_name": "curso-site"}), patch(
			"hubgh.lms.hardening._get_single_setting_value", return_value="curso-settings"
		):
			resolved = hardening.get_lms_course_name()

		self.assertEqual(resolved, "curso-site")

	def test_get_lms_course_name_uses_fallback_when_not_configured(self):
		with patch("hubgh.lms.hardening.frappe.conf", {}), patch(
			"hubgh.lms.hardening._get_single_setting_value", return_value=""
		), patch("hubgh.lms.hardening.log_lms_event") as log_event:
			resolved = hardening.get_lms_course_name()

		self.assertEqual(resolved, hardening.DEFAULT_LMS_COURSE_NAME)
		log_event.assert_called_once()

	def test_run_with_lms_retry_returns_default_after_bounded_attempts(self):
		calls = {"count": 0}

		def _always_fail():
			calls["count"] += 1
			raise RuntimeError("lms down")

		with patch("hubgh.lms.hardening.get_lms_retry_attempts", return_value=2), patch(
			"hubgh.lms.hardening.get_lms_retry_delay_seconds", return_value=0
		), patch("hubgh.lms.hardening.log_lms_event") as log_event:
			result = hardening.run_with_lms_retry("report.enrollment_lookup", _always_fail, default=None)

		self.assertIsNone(result)
		self.assertEqual(calls["count"], 2)
		statuses = [kwargs.get("status") for _, kwargs in log_event.call_args_list]
		self.assertIn("retry", statuses)
		self.assertIn("error", statuses)

	def test_integration_hook_uses_resolved_course_name(self):
		doc = SimpleNamespace(name="EMP-001", estado="Activo", email="persona@example.com")

		with patch("hubgh.lms.integration_hooks._lms_disponible", return_value=True), patch(
			"hubgh.lms.integration_hooks._resolver_usuario_empleado", return_value="persona@example.com"
		), patch("hubgh.lms.integration_hooks.get_lms_course_name", return_value="curso-dinamico"), patch(
			"hubgh.lms.integration_hooks._asignar_rol_lms_student"
		) as assign_role, patch("hubgh.lms.integration_hooks._crear_enrollment_si_no_existe") as create_enrollment:
			integration_hooks.enrolar_empleado_en_calidad(doc)

		assign_role.assert_called_once()
		create_enrollment.assert_called_once_with(
			"persona@example.com",
			"curso-dinamico",
			context={"empleado": "EMP-001", "user": "persona@example.com", "course": "curso-dinamico"},
		)

	def test_build_pdv_lms_report_degrades_when_lms_unavailable(self):
		personas = [{"name": "EMP-001", "nombres": "Ana", "apellidos": "P", "estado": "Activo", "email": "a@b.com"}]
		with patch("hubgh.api.ops.get_lms_course_name", return_value="curso-dinamico"), patch(
			"hubgh.api.ops._lms_tables_available", return_value=False
		):
			reporte, kpis = ops._build_pdv_lms_report("PDV-001", personas)

		self.assertEqual(len(reporte), 1)
		self.assertEqual(reporte[0].get("curso"), "curso-dinamico")
		self.assertEqual(reporte[0].get("estado"), "Pendiente LMS")
		self.assertEqual(kpis.get("cursos_calidad_sin_iniciar"), 1)

	def test_build_pdv_lms_report_handles_lms_lookup_errors_without_crash(self):
		personas = [{"name": "EMP-001", "nombres": "Ana", "apellidos": "P", "estado": "Activo", "email": "a@b.com"}]

		def _fake_retry(operation, func, **kwargs):
			if operation == "report.enrollment_lookup":
				return None
			return kwargs.get("default")

		with patch("hubgh.api.ops.get_lms_course_name", return_value="curso-dinamico"), patch(
			"hubgh.api.ops._lms_tables_available", return_value=True
		), patch("hubgh.api.ops._get_total_lecciones", return_value=10), patch(
			"hubgh.api.ops.frappe.db.exists", return_value=True
		), patch("hubgh.api.ops.run_with_lms_retry", side_effect=_fake_retry):
			reporte, _ = ops._build_pdv_lms_report("PDV-001", personas)

		self.assertEqual(reporte[0].get("estado"), "Sin iniciar")
		self.assertEqual(reporte[0].get("avance"), 0)

	def test_get_lms_integration_health_returns_lightweight_contract(self):
		with patch("hubgh.api.ops._lms_tables_available", return_value=False), patch(
			"hubgh.api.ops.get_lms_course_name", return_value="curso-dinamico"
		), patch("hubgh.api.ops.get_lms_metrics_snapshot", return_value={"report.person:success": 4}), patch(
			"hubgh.api.ops.get_lms_retry_attempts", return_value=3
		), patch("hubgh.api.ops.get_lms_retry_delay_seconds", return_value=0.25):
			payload = ops.get_lms_integration_health()

		self.assertEqual(payload.get("service"), "hubgh_lms_integration")
		self.assertEqual(payload.get("status"), "degraded")
		self.assertFalse(payload.get("available"))
		self.assertEqual(payload.get("course"), "curso-dinamico")
		self.assertEqual(payload.get("retry", {}).get("attempts"), 3)
		self.assertEqual(payload.get("metrics", {}).get("report.person:success"), 4)
