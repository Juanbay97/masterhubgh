# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para Email Templates de Traslado PDV — Fase 6.

TDD Cycle:
  T-11  RED  → estos tests (archivo)
  I-11a GREEN → patch create_traslado_email_templates.py
  I-11b GREEN → fixtures/email_template.json (4 templates agregados)

Verifica:
  - Los 4 templates existen en DB post-migrate (vía patch o fixture)
  - Cada template renderiza sin error con un contexto típico
  - Subject no está vacío
  - Body contiene las variables críticas
  - dispatch_email con template faltante loguea pero no aborta
"""

from unittest.mock import patch, MagicMock
from frappe.tests.utils import FrappeTestCase
import frappe
from frappe.utils import today


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TEMPLATES_TRASLADO = [
    "traslado_pdv_empleado_programado",
    "traslado_pdv_jefe_origen_programado",
    "traslado_pdv_jefe_destino_programado",
    "traslado_pdv_aplicado_confirmacion",
]

# Contexto típico para renderizar
SAMPLE_CONTEXT = {
    "traslado": {
        "name": "TRAS-2026-00001",
        "empleado": "TEST-EMP-001",
        "empleado_nombre": "Juan Pérez",
        "pdv_origen": "Home 06",
        "pdv_destino": "Home 07",
        "fecha_aplicacion": today(),
        "motivo_label": "Necesidad operativa",
        "justificacion": "Justificacion de ejemplo para el template de traslado",
        "cargo_destino": None,
    },
    "empleado": {
        "nombres": "Juan",
        "apellidos": "Pérez",
        "cedula": "12345678",
        "email": "juan.perez@test.com",
    },
    "jefe_origen": {
        "user": "jefe_origen@test.com",
        "full_name": "Carlos Gómez",
    },
    "jefe_destino": {
        "user": "jefe_destino@test.com",
        "full_name": "Ana López",
    },
    "aplicado_por": "rrll@test.com",
}


# ---------------------------------------------------------------------------
# Tests de existencia
# ---------------------------------------------------------------------------

class TestEmailTemplatesExistencia(FrappeTestCase):
    """Verifica que los 4 templates fueron creados (vía fixture o patch)."""

    def test_template_empleado_programado_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "traslado_pdv_empleado_programado"),
            "Template 'traslado_pdv_empleado_programado' debe existir en DB",
        )

    def test_template_jefe_origen_programado_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "traslado_pdv_jefe_origen_programado"),
            "Template 'traslado_pdv_jefe_origen_programado' debe existir en DB",
        )

    def test_template_jefe_destino_programado_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "traslado_pdv_jefe_destino_programado"),
            "Template 'traslado_pdv_jefe_destino_programado' debe existir en DB",
        )

    def test_template_aplicado_confirmacion_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "traslado_pdv_aplicado_confirmacion"),
            "Template 'traslado_pdv_aplicado_confirmacion' debe existir en DB",
        )


# ---------------------------------------------------------------------------
# Tests de renderización
# ---------------------------------------------------------------------------

class TestEmailTemplatesRenderizacion(FrappeTestCase):
    """Verifica que los templates renderizan sin error y tienen contenido mínimo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Asegurar que existen para poder testear renderizado
        # (si no existen por falta de fixture, los tests de existencia ya fallan)
        cls._ensure_templates()

    @classmethod
    def _ensure_templates(cls):
        """Crea templates mínimos en DB de test si no existen, para probar renderizado."""
        templates_defaults = {
            "traslado_pdv_empleado_programado": {
                "subject": "Tu traslado a {{ traslado.pdv_destino }} está programado — {{ traslado.fecha_aplicacion }}",
                "response": (
                    "<p>Hola {{ empleado.nombres }},</p>"
                    "<p>Tu traslado desde <strong>{{ traslado.pdv_origen }}</strong> "
                    "hacia <strong>{{ traslado.pdv_destino }}</strong> "
                    "está programado para el <strong>{{ traslado.fecha_aplicacion }}</strong>.</p>"
                    "<p>Motivo: {{ traslado.motivo_label }}</p>"
                    "<p><em>Equipo de Relaciones Laborales — HubGH</em></p>"
                ),
            },
            "traslado_pdv_jefe_origen_programado": {
                "subject": "Salida de {{ empleado.nombres }} {{ empleado.apellidos }} desde {{ traslado.pdv_origen }}",
                "response": (
                    "<p>Estimado/a {{ jefe_origen.full_name }},</p>"
                    "<p>Le informamos que <strong>{{ empleado.nombres }} {{ empleado.apellidos }}</strong> "
                    "será trasladado/a desde <strong>{{ traslado.pdv_origen }}</strong> "
                    "hacia {{ traslado.pdv_destino }} "
                    "con fecha de aplicación <strong>{{ traslado.fecha_aplicacion }}</strong>.</p>"
                    "<p>Por favor prepare la entrega de turno antes de esa fecha.</p>"
                    "<p><em>Equipo de Relaciones Laborales — HubGH</em></p>"
                ),
            },
            "traslado_pdv_jefe_destino_programado": {
                "subject": "Llegada de {{ empleado.nombres }} {{ empleado.apellidos }} a {{ traslado.pdv_destino }}",
                "response": (
                    "<p>Estimado/a {{ jefe_destino.full_name }},</p>"
                    "<p>Le informamos que <strong>{{ empleado.nombres }} {{ empleado.apellidos }}</strong> "
                    "se incorporará a <strong>{{ traslado.pdv_destino }}</strong> "
                    "el <strong>{{ traslado.fecha_aplicacion }}</strong>.</p>"
                    "{% if traslado.cargo_destino %}"
                    "<p>Cargo asignado: {{ traslado.cargo_destino }}</p>"
                    "{% endif %}"
                    "<p>Por favor prepare el puesto de trabajo con anticipación.</p>"
                    "<p><em>Equipo de Relaciones Laborales — HubGH</em></p>"
                ),
            },
            "traslado_pdv_aplicado_confirmacion": {
                "subject": "Traslado aplicado: {{ empleado.nombres }} {{ empleado.apellidos }} ahora en {{ traslado.pdv_destino }}",
                "response": (
                    "<p>El traslado de <strong>{{ empleado.nombres }} {{ empleado.apellidos }}</strong> "
                    "ha sido <strong>aplicado</strong> exitosamente.</p>"
                    "<ul>"
                    "<li><strong>PDV origen:</strong> {{ traslado.pdv_origen }}</li>"
                    "<li><strong>PDV destino:</strong> {{ traslado.pdv_destino }}</li>"
                    "<li><strong>Fecha aplicación:</strong> {{ traslado.fecha_aplicacion }}</li>"
                    "<li><strong>Aplicado por:</strong> {{ aplicado_por }}</li>"
                    "</ul>"
                    "<p><em>Equipo de Relaciones Laborales — HubGH</em></p>"
                ),
            },
        }
        for name, data in templates_defaults.items():
            if not frappe.db.exists("Email Template", name):
                frappe.get_doc({
                    "doctype": "Email Template",
                    "name": name,
                    "subject": data["subject"],
                    "response": data["response"],
                    "enabled": 1,
                    "use_html": 1,
                }).insert(ignore_permissions=True)

    def _render_template(self, template_name):
        """Renderiza subject y body del template con SAMPLE_CONTEXT."""
        from frappe.utils.jinja import render_template
        doc = frappe.get_doc("Email Template", template_name)
        subject = render_template(doc.subject or "", SAMPLE_CONTEXT)
        body = render_template(doc.response or doc.message or "", SAMPLE_CONTEXT)
        return subject, body

    def test_template_empleado_renderiza_sin_error(self):
        subject, body = self._render_template("traslado_pdv_empleado_programado")
        self.assertIsNotNone(subject)
        self.assertIsNotNone(body)

    def test_template_jefe_origen_renderiza_sin_error(self):
        subject, body = self._render_template("traslado_pdv_jefe_origen_programado")
        self.assertIsNotNone(subject)
        self.assertIsNotNone(body)

    def test_template_jefe_destino_renderiza_sin_error(self):
        subject, body = self._render_template("traslado_pdv_jefe_destino_programado")
        self.assertIsNotNone(subject)
        self.assertIsNotNone(body)

    def test_template_aplicado_renderiza_sin_error(self):
        subject, body = self._render_template("traslado_pdv_aplicado_confirmacion")
        self.assertIsNotNone(subject)
        self.assertIsNotNone(body)

    def test_subjects_no_vacios(self):
        for name in TEMPLATES_TRASLADO:
            subject, _ = self._render_template(name)
            self.assertTrue(
                subject.strip(),
                f"Subject del template '{name}' no debe estar vacío tras renderizar",
            )

    def test_bodies_no_vacios(self):
        for name in TEMPLATES_TRASLADO:
            _, body = self._render_template(name)
            self.assertTrue(
                body.strip(),
                f"Body del template '{name}' no debe estar vacío tras renderizar",
            )


# ---------------------------------------------------------------------------
# Tests de contenido — variables críticas en body
# ---------------------------------------------------------------------------

class TestEmailTemplatesContenido(TestEmailTemplatesRenderizacion):
    """Verifica que los placeholders críticos están en el body renderizado."""

    def test_template_empleado_contiene_pdv_destino(self):
        _, body = self._render_template("traslado_pdv_empleado_programado")
        self.assertIn("Home 07", body, "Body T1 debe contener pdv_destino renderizado")

    def test_template_empleado_contiene_fecha_aplicacion(self):
        _, body = self._render_template("traslado_pdv_empleado_programado")
        self.assertIn(today(), body, "Body T1 debe contener fecha_aplicacion renderizada")

    def test_template_empleado_contiene_nombre_empleado(self):
        _, body = self._render_template("traslado_pdv_empleado_programado")
        self.assertIn("Juan", body, "Body T1 debe contener el nombre del empleado")

    def test_template_jefe_origen_contiene_pdv_origen(self):
        _, body = self._render_template("traslado_pdv_jefe_origen_programado")
        self.assertIn("Home 06", body, "Body T2 debe contener pdv_origen renderizado")

    def test_template_jefe_origen_contiene_empleado(self):
        _, body = self._render_template("traslado_pdv_jefe_origen_programado")
        self.assertIn("Pérez", body, "Body T2 debe contener apellido del empleado")

    def test_template_jefe_destino_contiene_pdv_destino(self):
        _, body = self._render_template("traslado_pdv_jefe_destino_programado")
        self.assertIn("Home 07", body, "Body T3 debe contener pdv_destino renderizado")

    def test_template_jefe_destino_contiene_fecha(self):
        _, body = self._render_template("traslado_pdv_jefe_destino_programado")
        self.assertIn(today(), body, "Body T3 debe contener fecha_aplicacion renderizada")

    def test_template_aplicado_contiene_empleado(self):
        _, body = self._render_template("traslado_pdv_aplicado_confirmacion")
        self.assertIn("Juan", body, "Body T4 debe contener el nombre del empleado")

    def test_template_aplicado_contiene_pdv_destino(self):
        _, body = self._render_template("traslado_pdv_aplicado_confirmacion")
        self.assertIn("Home 07", body, "Body T4 debe contener pdv_destino renderizado")

    def test_template_aplicado_contiene_aplicado_por(self):
        _, body = self._render_template("traslado_pdv_aplicado_confirmacion")
        self.assertIn("rrll@test.com", body, "Body T4 debe contener aplicado_por renderizado")

    def test_subject_t1_contiene_pdv_destino(self):
        subject, _ = self._render_template("traslado_pdv_empleado_programado")
        self.assertIn("Home 07", subject, "Subject T1 debe contener pdv_destino")

    def test_subject_t4_contiene_empleado_nombre(self):
        subject, _ = self._render_template("traslado_pdv_aplicado_confirmacion")
        # Subject contiene apellido o nombre del empleado
        self.assertTrue(
            "Juan" in subject or "Pérez" in subject,
            f"Subject T4 debe contener el nombre del empleado. Got: {subject}",
        )


# ---------------------------------------------------------------------------
# Tests de dispatch_email con template faltante — no aborta
# ---------------------------------------------------------------------------

class TestDispatchEmailTemplFaltante(FrappeTestCase):
    """Verifica que dispatch_email loguea pero no relanza si el template no existe."""

    def test_dispatch_email_template_faltante_devuelve_error_sin_raise(self):
        from hubgh.hubgh.services.email_dispatcher import dispatch_email
        with patch("frappe.log_error") as mock_log:
            result = dispatch_email(
                template_name="template_que_no_existe_xyz_abc",
                recipients=["alguien@test.com"],
                context=SAMPLE_CONTEXT,
            )
        self.assertEqual(result["status"], "error")
        self.assertIsNotNone(result["error"])
        mock_log.assert_called_once()

    def test_dispatch_email_recipients_vacios_devuelve_skipped(self):
        from hubgh.hubgh.services.email_dispatcher import dispatch_email
        result = dispatch_email(
            template_name="traslado_pdv_empleado_programado",
            recipients=[],
            context=SAMPLE_CONTEXT,
        )
        self.assertEqual(result["status"], "skipped")


# ---------------------------------------------------------------------------
# Test idempotencia del patch
# ---------------------------------------------------------------------------

class TestPatchIdempotente(FrappeTestCase):
    """Verifica que el patch de carga de email templates es idempotente."""

    def test_patch_ejecuta_sin_error_multiple_veces(self):
        """Correr el patch dos veces no genera excepción ni duplicados."""
        from hubgh.patches.create_traslado_email_templates import execute
        try:
            execute()
            execute()  # segunda vez — idempotente
        except Exception as exc:
            self.fail(f"El patch no debe lanzar excepción en segunda ejecución: {exc}")

    def test_patch_no_duplica_templates(self):
        """Después de ejecutar el patch dos veces, debe haber exactamente 1 de cada template."""
        from hubgh.patches.create_traslado_email_templates import execute
        execute()
        for name in TEMPLATES_TRASLADO:
            count = frappe.db.count("Email Template", {"name": name})
            self.assertEqual(count, 1, f"Debe haber exactamente 1 template '{name}', hay {count}")
