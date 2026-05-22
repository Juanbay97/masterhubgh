# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para Email Templates de Terminacion Contrato.

TDD Cycle: RED (A.8) -> GREEN (A.9 patch) -> TRIANGULATE -> REFACTOR

Verifica:
- Los 11 templates existen en DB post-migrate/patch
- Cada template renderiza sin error con un contexto tipico
- Subject no esta vacio
- Body contiene las variables criticas
- Patch idempotente (doble ejecucion sin error ni duplicados)
"""

from frappe.tests.utils import FrappeTestCase
import frappe
from frappe.utils import today


# ---------------------------------------------------------------------------
# Templates esperados: R1-R9 + 2 cartas
# ---------------------------------------------------------------------------

TEMPLATES_TERMINACION = [
    "terminacion_iniciada_sistemas",           # R1
    "terminacion_iniciada_rrll_dotacion",      # R2
    "terminacion_iniciada_operacion",          # R3
    "terminacion_examen_egreso_empleado",      # R4
    "terminacion_iniciada_compensacion",       # R5
    "terminacion_iniciada_jefe_pdv",           # R6
    "terminacion_carta_empleado",              # R7
    "terminacion_cerrada_rrll",                # R8
    "terminacion_recordatorio_subproceso",     # R9
    "carta_terminacion_justa_causa",           # carta plantilla
    "carta_terminacion_periodo_prueba",        # carta plantilla
]

# Contexto tipico de terminacion
SAMPLE_CONTEXT = {
    "empleado": {
        "name": "TEST-EMP-001",
        "nombres": "Maria",
        "apellidos": "Rodriguez",
        "cedula": "98765432",
        "email": "maria.rodriguez@test.com",
        "cargo": "Cajera",
    },
    "terminacion": {
        "name": "TC-2026-00001",
        "causal_nombre": "Terminacion con justa causa",
        "fecha_ultimo_dia": today(),
        "fecha_terminacion_efectiva": today(),
        "pdv_al_terminar": "Home 06",
        "cargo_al_terminar": "Cajera",
        "resumen_cierre": "Proceso completado satisfactoriamente.",
        "link_tc": "/app/terminacion-contrato/TC-2026-00001",
    },
    "fecha_limite": today(),
    "link_agendamiento": "https://hubgh.local/exam?token=abc123",
    "link_tc": "/app/terminacion-contrato/TC-2026-00001",
    "causal_descripcion": "Incumplimiento reiterado del reglamento interno.",
    "justificacion": "El empleado incumplio el reglamento interno en multiples ocasiones.",
    "contrato_fecha_inicio": "2024-01-15",
    "subprocesos_resumen": "sistemas: Completado, RRLL: Completado",
    "area": "sistemas",
    "area_nombre": "Sistemas",
    "fecha_limite_subproceso": today(),
    "carta_terminacion_url": None,
}


# ---------------------------------------------------------------------------
# Tests de existencia
# ---------------------------------------------------------------------------

class TestTerminacionEmailTemplatesExistencia(FrappeTestCase):
    """Verifica que los 11 templates existen en DB."""

    def test_r1_sistemas_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "terminacion_iniciada_sistemas"),
            "Template R1 'terminacion_iniciada_sistemas' no existe.",
        )

    def test_r2_rrll_dotacion_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "terminacion_iniciada_rrll_dotacion"),
            "Template R2 'terminacion_iniciada_rrll_dotacion' no existe.",
        )

    def test_r3_operacion_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "terminacion_iniciada_operacion"),
            "Template R3 'terminacion_iniciada_operacion' no existe.",
        )

    def test_r4_examen_egreso_empleado_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "terminacion_examen_egreso_empleado"),
            "Template R4 'terminacion_examen_egreso_empleado' no existe.",
        )

    def test_r5_compensacion_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "terminacion_iniciada_compensacion"),
            "Template R5 'terminacion_iniciada_compensacion' no existe.",
        )

    def test_r6_jefe_pdv_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "terminacion_iniciada_jefe_pdv"),
            "Template R6 'terminacion_iniciada_jefe_pdv' no existe.",
        )

    def test_r7_carta_empleado_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "terminacion_carta_empleado"),
            "Template R7 'terminacion_carta_empleado' no existe.",
        )

    def test_r8_cerrada_rrll_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "terminacion_cerrada_rrll"),
            "Template R8 'terminacion_cerrada_rrll' no existe.",
        )

    def test_r9_recordatorio_subproceso_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "terminacion_recordatorio_subproceso"),
            "Template R9 'terminacion_recordatorio_subproceso' no existe.",
        )

    def test_carta_justa_causa_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "carta_terminacion_justa_causa"),
            "Template carta 'carta_terminacion_justa_causa' no existe.",
        )

    def test_carta_periodo_prueba_existe(self):
        self.assertTrue(
            frappe.db.exists("Email Template", "carta_terminacion_periodo_prueba"),
            "Template carta 'carta_terminacion_periodo_prueba' no existe.",
        )


# ---------------------------------------------------------------------------
# Tests de renderizacion
# ---------------------------------------------------------------------------

class TestTerminacionEmailTemplatesRenderizacion(FrappeTestCase):
    """Verifica que todos los templates renderizan sin error."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._ensure_templates()

    @classmethod
    def _ensure_templates(cls):
        """Crea templates minimos en DB de test si no existen (para probar renderizado)."""
        defaults = {
            "terminacion_iniciada_sistemas": {
                "subject": "Terminacion iniciada - Bloqueo credenciales: {{ empleado.nombres }} {{ empleado.apellidos }}",
                "response": "<p>Area sistemas: {{ empleado.nombres }} en PDV {{ terminacion.pdv_al_terminar }}. Link: {{ terminacion.link_tc }}</p>",
            },
            "terminacion_iniciada_rrll_dotacion": {
                "subject": "Terminacion iniciada - Devolucion dotacion: {{ empleado.nombres }} {{ empleado.apellidos }}",
                "response": "<p>RRLL Dotacion: {{ empleado.nombres }}. PDV: {{ terminacion.pdv_al_terminar }}. Link: {{ terminacion.link_tc }}</p>",
            },
            "terminacion_iniciada_operacion": {
                "subject": "Terminacion iniciada - Desactivar Clonk: {{ empleado.nombres }} {{ empleado.apellidos }}",
                "response": "<p>Operacion: {{ empleado.nombres }}, Cedula: {{ empleado.cedula }}. Link: {{ terminacion.link_tc }}</p>",
            },
            "terminacion_examen_egreso_empleado": {
                "subject": "Examen medico de egreso - {{ empleado.nombres }} {{ empleado.apellidos }}",
                "response": "<p>{{ empleado.nombres }}: fecha limite {{ fecha_limite }}. Agendar: {{ link_agendamiento }}</p>",
            },
            "terminacion_iniciada_compensacion": {
                "subject": "Terminacion iniciada - Liquidacion pendiente: {{ empleado.nombres }} {{ empleado.apellidos }}",
                "response": "<p>Compensacion: {{ empleado.nombres }}, ultimo dia {{ terminacion.fecha_ultimo_dia }}. Link: {{ terminacion.link_tc }}</p>",
            },
            "terminacion_iniciada_jefe_pdv": {
                "subject": "Terminacion en tu PDV - {{ empleado.nombres }} {{ empleado.apellidos }}",
                "response": "<p>Jefe PDV: {{ empleado.nombres }}, ultimo dia {{ terminacion.fecha_ultimo_dia }}. Link: {{ terminacion.link_tc }}</p>",
            },
            "terminacion_carta_empleado": {
                "subject": "Comunicacion oficial de terminacion - {{ empleado.nombres }} {{ empleado.apellidos }}",
                "response": "<p>{{ empleado.nombres }}: causal {{ terminacion.causal_nombre }}. {% if carta_terminacion_url %}<a href='{{ carta_terminacion_url }}'>Ver carta</a>{% endif %}</p>",
            },
            "terminacion_cerrada_rrll": {
                "subject": "Terminacion cerrada - {{ empleado.nombres }} {{ empleado.apellidos }}",
                "response": "<p>Cerrado: {{ empleado.nombres }}, causal {{ terminacion.causal_nombre }}. Resumen: {{ terminacion.resumen_cierre }}</p>",
            },
            "terminacion_recordatorio_subproceso": {
                "subject": "Recordatorio: subproceso pendiente {{ area_nombre }} - {{ empleado.nombres }} {{ empleado.apellidos }}",
                "response": "<p>{{ area_nombre }}: pendiente para {{ empleado.nombres }}. Fecha limite: {{ fecha_limite_subproceso }}</p>",
            },
            "carta_terminacion_justa_causa": {
                "subject": "Carta de terminacion con justa causa",
                "response": "<p>{{ empleado.nombres }} {{ empleado.apellidos }}, Cedula {{ empleado.cedula }}: {{ causal_descripcion }}. Fecha efectiva: {{ terminacion.fecha_terminacion_efectiva }}.</p>",
            },
            "carta_terminacion_periodo_prueba": {
                "subject": "Carta de terminacion en periodo de prueba",
                "response": "<p>{{ empleado.nombres }} {{ empleado.apellidos }}: contrato iniciado {{ contrato_fecha_inicio }}. Fecha efectiva: {{ terminacion.fecha_terminacion_efectiva }}.</p>",
            },
        }
        for name, data in defaults.items():
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
        from frappe.utils.jinja import render_template
        doc = frappe.get_doc("Email Template", template_name)
        subject = render_template(doc.subject or "", SAMPLE_CONTEXT)
        body = render_template(doc.response or doc.message or "", SAMPLE_CONTEXT)
        return subject, body

    def test_r1_sistemas_renderiza(self):
        subject, body = self._render_template("terminacion_iniciada_sistemas")
        self.assertTrue(subject.strip())
        self.assertTrue(body.strip())

    def test_r2_rrll_dotacion_renderiza(self):
        subject, body = self._render_template("terminacion_iniciada_rrll_dotacion")
        self.assertTrue(subject.strip())
        self.assertTrue(body.strip())

    def test_r3_operacion_renderiza(self):
        subject, body = self._render_template("terminacion_iniciada_operacion")
        self.assertTrue(subject.strip())
        self.assertTrue(body.strip())

    def test_r4_examen_egreso_renderiza(self):
        subject, body = self._render_template("terminacion_examen_egreso_empleado")
        self.assertTrue(subject.strip())
        self.assertTrue(body.strip())
        self.assertIn(today(), body)

    def test_r5_compensacion_renderiza(self):
        subject, body = self._render_template("terminacion_iniciada_compensacion")
        self.assertTrue(subject.strip())
        self.assertTrue(body.strip())

    def test_r6_jefe_pdv_renderiza(self):
        subject, body = self._render_template("terminacion_iniciada_jefe_pdv")
        self.assertTrue(subject.strip())
        self.assertTrue(body.strip())

    def test_r7_carta_empleado_renderiza_sin_carta(self):
        """R7 con carta_terminacion_url=None no debe crashear."""
        subject, body = self._render_template("terminacion_carta_empleado")
        self.assertTrue(subject.strip())
        self.assertTrue(body.strip())

    def test_r7_carta_empleado_renderiza_con_carta(self):
        """R7 con carta_terminacion_url presente debe incluir el link."""
        ctx = dict(SAMPLE_CONTEXT)
        ctx["carta_terminacion_url"] = "https://hubgh.local/carta.pdf"
        from frappe.utils.jinja import render_template
        doc = frappe.get_doc("Email Template", "terminacion_carta_empleado")
        body = render_template(doc.response or doc.message or "", ctx)
        self.assertIn("carta.pdf", body)

    def test_r8_cerrada_rrll_renderiza(self):
        subject, body = self._render_template("terminacion_cerrada_rrll")
        self.assertTrue(subject.strip())
        self.assertTrue(body.strip())

    def test_r9_recordatorio_renderiza(self):
        subject, body = self._render_template("terminacion_recordatorio_subproceso")
        self.assertTrue(subject.strip())
        self.assertTrue(body.strip())

    def test_carta_justa_causa_renderiza(self):
        subject, body = self._render_template("carta_terminacion_justa_causa")
        self.assertTrue(subject.strip())
        self.assertTrue(body.strip())
        self.assertIn("Maria", body)

    def test_carta_periodo_prueba_renderiza(self):
        subject, body = self._render_template("carta_terminacion_periodo_prueba")
        self.assertTrue(subject.strip())
        self.assertTrue(body.strip())


# ---------------------------------------------------------------------------
# Test idempotencia del patch
# ---------------------------------------------------------------------------

class TestTerminacionEmailTemplatesPatchIdempotente(FrappeTestCase):

    def test_patch_ejecuta_sin_error(self):
        from hubgh.patches.create_terminacion_email_templates import execute
        try:
            execute()
            execute()
        except Exception as exc:
            self.fail(f"Patch no debe lanzar excepcion en segunda ejecucion: {exc}")

    def test_patch_no_duplica_templates(self):
        from hubgh.patches.create_terminacion_email_templates import execute
        execute()
        for name in TEMPLATES_TERMINACION:
            count = frappe.db.count("Email Template", {"name": name})
            self.assertEqual(count, 1, f"Debe haber exactamente 1 template '{name}', hay {count}")
