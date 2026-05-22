# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for examen_egreso_service.py — Batch B.5 (TDD RED → GREEN)

Covers:
  T-B.5a  crear_examen_egreso happy path — crea Cita Examen Egreso, retorna name
  T-B.5b  fecha_limite es today + 5 business days (lunes a viernes)
  T-B.5c  token único generado (not empty, distinto por llamada)
  T-B.5d  Email R4 invocado al crear examen
  T-B.5e  process_scheduled_recordatorios filtra correctamente
  T-B.5f  marcar_realizada cambia estado a Realizada
"""

from datetime import date, datetime
from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase
import frappe


# ---------------------------------------------------------------------------
# Module under test
# ---------------------------------------------------------------------------

from hubgh.hubgh.services.examen_egreso_service import (
    crear_examen_egreso,
    marcar_realizada,
    process_scheduled_recordatorios,
    _dias_habiles,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tc_doc(name="TC-2026-001", empleado="EMP-001"):
    doc = MagicMock()
    doc.name = name
    doc.empleado = empleado
    doc.causal = "justa_causa"
    doc.fecha_terminacion_efectiva = "2026-06-30"
    return doc


# ---------------------------------------------------------------------------
# T-B.5b — _dias_habiles helper
# ---------------------------------------------------------------------------

class TestDiasHabilesHelper(FrappeTestCase):

    def test_5_dias_habiles_desde_lunes(self):
        """5 días hábiles sumados desde lunes (exclusive start) → lunes siguiente."""
        # 2026-01-05 es lunes. day+1=Tue(1), Wed(2), Thu(3), Fri(4), Mon12(5)
        start = date(2026, 1, 5)
        result = _dias_habiles(start, 5)
        # Tue 6 (1), Wed 7 (2), Thu 8 (3), Fri 9 (4), Mon 12 (5)
        self.assertEqual(result, date(2026, 1, 12))

    def test_5_dias_habiles_saltando_fin_de_semana(self):
        """5 días hábiles desde jueves → siguiente jueves."""
        # 2026-01-08 es jueves. day+1=Fri(1), Mon12(2), Tue13(3), Wed14(4), Thu15(5)
        start = date(2026, 1, 8)
        result = _dias_habiles(start, 5)
        # Fri 9(1), Mon 12(2), Tue 13(3), Wed 14(4), Thu 15(5)
        self.assertEqual(result, date(2026, 1, 15))


# ---------------------------------------------------------------------------
# T-B.5a — crear_examen_egreso happy path
# ---------------------------------------------------------------------------

class TestCrearExamenEgresoHappyPath(FrappeTestCase):

    def test_crear_retorna_name(self):
        """crear_examen_egreso debe retornar el name de la Cita creada."""
        tc_doc = _make_tc_doc()
        mock_cita_doc = MagicMock()
        mock_cita_doc.name = "CXE-2026-001"

        def _get_doc_side_effect(payload):
            if isinstance(payload, dict) and payload.get("doctype") == "Cita Examen Egreso":
                return mock_cita_doc
            return MagicMock()

        mock_cita_doc.insert = MagicMock(return_value=mock_cita_doc)

        with patch("hubgh.hubgh.services.examen_egreso_service.frappe.get_doc", side_effect=_get_doc_side_effect), \
             patch("hubgh.hubgh.services.examen_egreso_service.frappe.generate_hash", return_value="abc123xyz456"), \
             patch("hubgh.hubgh.services.examen_egreso_service.today", return_value=date(2026, 5, 22)), \
             patch("hubgh.hubgh.services.examen_egreso_service.dispatch_email", return_value={"status": "ok"}), \
             patch("hubgh.hubgh.services.examen_egreso_service.resolve_employee_email", return_value="emp@test.com"):
            result = crear_examen_egreso(tc_doc)

        self.assertEqual(result, "CXE-2026-001")

    def test_crear_inserta_con_terminacion_origen(self):
        """Cita Examen Egreso debe linkear terminacion_origen=TC.name."""
        tc_doc = _make_tc_doc(name="TC-2026-999")
        captured_payload = {}
        mock_cita_doc = MagicMock()
        mock_cita_doc.name = "CXE-2026-001"
        mock_cita_doc.insert = MagicMock(return_value=mock_cita_doc)

        def _get_doc_side_effect(payload):
            if isinstance(payload, dict) and payload.get("doctype") == "Cita Examen Egreso":
                captured_payload.update(payload)
                return mock_cita_doc
            return MagicMock()

        with patch("hubgh.hubgh.services.examen_egreso_service.frappe.get_doc", side_effect=_get_doc_side_effect), \
             patch("hubgh.hubgh.services.examen_egreso_service.frappe.generate_hash", return_value="token123"), \
             patch("hubgh.hubgh.services.examen_egreso_service.today", return_value=date(2026, 5, 22)), \
             patch("hubgh.hubgh.services.examen_egreso_service.dispatch_email", return_value={"status": "ok"}), \
             patch("hubgh.hubgh.services.examen_egreso_service.resolve_employee_email", return_value="emp@test.com"):
            crear_examen_egreso(tc_doc)

        self.assertEqual(captured_payload.get("terminacion_origen"), "TC-2026-999")
        self.assertEqual(captured_payload.get("empleado"), "EMP-001")


# ---------------------------------------------------------------------------
# T-B.5b — fecha_limite = today + 5 business days
# ---------------------------------------------------------------------------

class TestFechaLimiteBusiness(FrappeTestCase):

    def test_fecha_limite_is_5_business_days(self):
        """fecha_limite en la Cita debe ser today + 5 días hábiles."""
        # 2026-05-22 es viernes → 5 días hábiles = lunes 25, mar 26, mié 27, jue 28, vie 29 = 2026-05-29
        tc_doc = _make_tc_doc()
        captured = {}
        mock_cita = MagicMock()
        mock_cita.name = "CXE-2026-001"
        mock_cita.insert = MagicMock(return_value=mock_cita)

        def _get_doc_se(payload):
            if isinstance(payload, dict) and payload.get("doctype") == "Cita Examen Egreso":
                captured.update(payload)
                return mock_cita
            return MagicMock()

        with patch("hubgh.hubgh.services.examen_egreso_service.frappe.get_doc", side_effect=_get_doc_se), \
             patch("hubgh.hubgh.services.examen_egreso_service.frappe.generate_hash", return_value="tok"), \
             patch("hubgh.hubgh.services.examen_egreso_service.today", return_value=date(2026, 5, 22)), \
             patch("hubgh.hubgh.services.examen_egreso_service.dispatch_email", return_value={"status": "ok"}), \
             patch("hubgh.hubgh.services.examen_egreso_service.resolve_employee_email", return_value="emp@test.com"):
            crear_examen_egreso(tc_doc)

        self.assertEqual(captured.get("fecha_limite"), date(2026, 5, 29))


# ---------------------------------------------------------------------------
# T-B.5c — token único
# ---------------------------------------------------------------------------

class TestTokenUnico(FrappeTestCase):

    def test_token_is_set(self):
        """La Cita debe incluir token no vacío."""
        tc_doc = _make_tc_doc()
        captured = {}
        mock_cita = MagicMock()
        mock_cita.name = "CXE-001"
        mock_cita.insert = MagicMock(return_value=mock_cita)

        def _get_doc_se(payload):
            if isinstance(payload, dict) and payload.get("doctype") == "Cita Examen Egreso":
                captured.update(payload)
                return mock_cita
            return MagicMock()

        with patch("hubgh.hubgh.services.examen_egreso_service.frappe.get_doc", side_effect=_get_doc_se), \
             patch("hubgh.hubgh.services.examen_egreso_service.frappe.generate_hash", return_value="uniquetoken24chars123456"), \
             patch("hubgh.hubgh.services.examen_egreso_service.today", return_value=date(2026, 5, 22)), \
             patch("hubgh.hubgh.services.examen_egreso_service.dispatch_email", return_value={"status": "ok"}), \
             patch("hubgh.hubgh.services.examen_egreso_service.resolve_employee_email", return_value="emp@test.com"):
            crear_examen_egreso(tc_doc)

        self.assertTrue(captured.get("token"))
        self.assertEqual(captured["token"], "uniquetoken24chars123456")


# ---------------------------------------------------------------------------
# T-B.5d — Email R4 invocado
# ---------------------------------------------------------------------------

class TestEmailR4Invocado(FrappeTestCase):

    def test_r4_email_dispatched(self):
        """dispatch_email con template R4 debe invocarse al crear examen."""
        tc_doc = _make_tc_doc()
        mock_cita = MagicMock()
        mock_cita.name = "CXE-001"
        mock_cita.insert = MagicMock(return_value=mock_cita)

        def _get_doc_se(payload):
            if isinstance(payload, dict) and payload.get("doctype") == "Cita Examen Egreso":
                return mock_cita
            return MagicMock()

        mock_dispatch = MagicMock(return_value={"status": "ok"})
        with patch("hubgh.hubgh.services.examen_egreso_service.frappe.get_doc", side_effect=_get_doc_se), \
             patch("hubgh.hubgh.services.examen_egreso_service.frappe.generate_hash", return_value="tok"), \
             patch("hubgh.hubgh.services.examen_egreso_service.today", return_value=date(2026, 5, 22)), \
             patch("hubgh.hubgh.services.examen_egreso_service.dispatch_email", mock_dispatch), \
             patch("hubgh.hubgh.services.examen_egreso_service.resolve_employee_email", return_value="emp@test.com"):
            crear_examen_egreso(tc_doc)

        mock_dispatch.assert_called_once()
        call_kwargs = mock_dispatch.call_args[1]
        self.assertEqual(call_kwargs.get("template_name"), "terminacion_iniciada_sst_empleado")


# ---------------------------------------------------------------------------
# T-B.5f — marcar_realizada cambia estado
# ---------------------------------------------------------------------------

class TestMarcarRealizada(FrappeTestCase):

    def test_marcar_realizada_cambia_estado(self):
        """marcar_realizada debe setear estado='Realizada' en la Cita."""
        mock_cita = MagicMock()
        mock_cita.name = "CXE-001"
        mock_cita.estado = "Pendiente Agendamiento"
        mock_cita.db_set = MagicMock()

        with patch("hubgh.hubgh.services.examen_egreso_service.frappe.get_doc", return_value=mock_cita):
            result = marcar_realizada("CXE-001")

        mock_cita.db_set.assert_any_call("estado", "Realizada")
        self.assertTrue(result["ok"])


# ---------------------------------------------------------------------------
# T-B.5e — process_scheduled_recordatorios filtra
# ---------------------------------------------------------------------------

class TestProcessScheduledRecordatorios(FrappeTestCase):

    def test_recordatorio_sent_when_within_2_days(self):
        """Citas con fecha_limite - today <= 2 y Pendiente → recordatorio enviado."""
        # Fecha hoy = 2026-05-22, fecha_limite = 2026-05-23 (1 día de diferencia)
        cita_row = MagicMock()
        cita_row.name = "CXE-001"

        mock_cita = MagicMock()
        mock_cita.nombre = "CXE-001"
        mock_cita.empleado = "EMP-001"
        mock_cita.fecha_limite = date(2026, 5, 23)
        mock_cita.estado = "Pendiente Agendamiento"
        mock_cita.token = "tok"
        mock_cita.db_set = MagicMock()

        mock_dispatch = MagicMock(return_value={"status": "ok"})

        with patch("hubgh.hubgh.services.examen_egreso_service.frappe.get_all", return_value=[cita_row]), \
             patch("hubgh.hubgh.services.examen_egreso_service.frappe.get_doc", return_value=mock_cita), \
             patch("hubgh.hubgh.services.examen_egreso_service.today", return_value=date(2026, 5, 22)), \
             patch("hubgh.hubgh.services.examen_egreso_service.dispatch_email", mock_dispatch), \
             patch("hubgh.hubgh.services.examen_egreso_service.resolve_employee_email", return_value="emp@test.com"):
            result = process_scheduled_recordatorios()

        self.assertGreater(result["sent"], 0)
