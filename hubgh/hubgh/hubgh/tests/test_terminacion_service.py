# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for terminacion_service.py — Batch B.9 (TDD RED → GREEN)

Covers:
  T-B.9a  iniciar_terminacion happy path → retorna TC.name
  T-B.9b  iniciar_terminacion con causal sin carta automática → carta no generada
  T-B.9c  iniciar_terminacion con validación bloqueante sin override → throw
  T-B.9d  iniciar_terminacion snapshot pdv_al_terminar / cargo_al_terminar
  T-B.9e  aplicar_subproceso primera vez → TC pasa a En Curso
  T-B.9f  aplicar_subproceso registra fecha_completado y evidencia
  T-B.9g  cerrar_terminacion con subprocesos incompletos → throw
  T-B.9h  cerrar_terminacion happy path → estado Cerrado
  T-B.9i  cancelar_terminacion desde Iniciado → estado Cancelado, restore acceso
  T-B.9j  cancelar_terminacion restaura User access
  T-B.9k  crear_terminacion_desde_caso_disciplinario
  T-B.9l  crear_terminacion_desde_novedad_sst
  T-B.9m  cancelar_terminacion_si_activa cancela TC activa
  T-B.9n  evaluar_checklist_validaciones retorna 9 items
  T-B.9o  before_insert_terminacion snapshot pdv/cargo
"""

from datetime import datetime
from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase
import frappe


# ---------------------------------------------------------------------------
# Module under test
# ---------------------------------------------------------------------------

from hubgh.hubgh.services.terminacion_service import (
    iniciar_terminacion,
    aplicar_subproceso,
    cerrar_terminacion,
    cancelar_terminacion,
    cancelar_terminacion_si_activa,
    crear_terminacion_desde_caso_disciplinario,
    crear_terminacion_desde_novedad_sst,
    evaluar_checklist_validaciones,
    before_insert_terminacion,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_FIXED_NOW = datetime(2026, 5, 22, 10, 0, 0)

_INIT_KWARGS = dict(
    empleado="EMP-001",
    causal="justa_causa",
    fecha_ultimo_dia="2026-06-30",
    fecha_terminacion_efectiva="2026-07-15",
    justificacion="Incumplimiento reiterado de normas laborales vigentes.",
)


def _make_causal_doc(requiere_carta=1):
    doc = MagicMock()
    doc.requiere_carta_automatica = requiere_carta
    doc.nombre = "Justa Causa"
    doc.codigo = "justa_causa"
    return doc


def _make_tc_doc(name="TC-2026-001", estado="Iniciado", empleado="EMP-001"):
    doc = MagicMock()
    doc.name = name
    doc.estado = estado
    doc.empleado = empleado
    doc.causal = "justa_causa"
    doc.resumen_cierre = ""
    doc.cancelado_motivo = ""
    doc.subprocesos = []
    doc.checklist_validaciones = []
    doc.pdv_al_terminar = "PDV-001"
    doc.examen_egreso = None
    doc.carta_terminacion = None
    doc.save = MagicMock()
    doc.insert = MagicMock(return_value=doc)
    doc.db_set = MagicMock()
    doc.append = MagicMock()
    return doc


def _make_emp_doc(pdv="PDV-001", cargo="Asesor Comercial", estado="Activo"):
    doc = MagicMock()
    doc.pdv = pdv
    doc.cargo = cargo
    doc.estado = estado
    doc.email = "emp@test.com"
    return doc


def _make_subproceso_row(area="sistemas", estado="Pendiente"):
    row = MagicMock()
    row.area = area
    row.estado = estado
    row.fecha_completado = None
    row.evidencia = None
    row.notas = None
    return row


# ---------------------------------------------------------------------------
# T-B.9a — iniciar_terminacion happy path
# ---------------------------------------------------------------------------

class TestIniciarTerminacionHappyPath(FrappeTestCase):

    def test_iniciar_retorna_tc_name(self):
        """iniciar_terminacion debe retornar el name del TC creado."""
        tc_doc = _make_tc_doc()
        emp_doc = _make_emp_doc()
        causal_doc = _make_causal_doc()

        def _get_doc_se(payload_or_doctype, name=None):
            if isinstance(payload_or_doctype, dict):
                dt = payload_or_doctype.get("doctype")
                if dt == "Terminacion Contrato":
                    return tc_doc
                return MagicMock()
            if payload_or_doctype == "Ficha Empleado":
                return emp_doc
            if payload_or_doctype == "Causal Terminacion":
                return causal_doc
            return MagicMock()

        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_doc", side_effect=_get_doc_se), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", return_value=False), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.session", MagicMock(user="admin@test.com")), \
             patch("hubgh.hubgh.services.terminacion_service.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.terminacion_service.today", return_value="2026-05-22"), \
             patch("hubgh.hubgh.services.terminacion_service.evaluar_checklist_validaciones", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.block_user_access", return_value={"blocked": True, "user": "emp@test.com", "reason": "ok"}), \
             patch("hubgh.hubgh.services.terminacion_service.generar_carta", return_value=None), \
             patch("hubgh.hubgh.services.terminacion_service.crear_examen_egreso", return_value="CXE-001"), \
             patch("hubgh.hubgh.services.terminacion_service._dispatch_notifications_iniciar"), \
             patch("hubgh.hubgh.services.terminacion_service.publish_people_ops_event", return_value="POE-1"):
            result = iniciar_terminacion(**_INIT_KWARGS)

        self.assertEqual(result, "TC-2026-001")


# ---------------------------------------------------------------------------
# T-B.9b — causal sin carta automática → carta no generada
# ---------------------------------------------------------------------------

class TestIniciarSinCarta(FrappeTestCase):

    def test_no_carta_when_causal_no_requiere(self):
        """Si causal.requiere_carta_automatica=0, generar_carta no se invoca."""
        tc_doc = _make_tc_doc()
        emp_doc = _make_emp_doc()
        causal_doc = _make_causal_doc(requiere_carta=0)

        def _get_doc_se(payload_or_doctype, name=None):
            if isinstance(payload_or_doctype, dict):
                dt = payload_or_doctype.get("doctype")
                if dt == "Terminacion Contrato":
                    return tc_doc
                return MagicMock()
            if payload_or_doctype == "Ficha Empleado":
                return emp_doc
            if payload_or_doctype == "Causal Terminacion":
                return causal_doc
            return MagicMock()

        mock_carta = MagicMock(return_value=None)
        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_doc", side_effect=_get_doc_se), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", return_value=False), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.session", MagicMock(user="admin@test.com")), \
             patch("hubgh.hubgh.services.terminacion_service.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.terminacion_service.today", return_value="2026-05-22"), \
             patch("hubgh.hubgh.services.terminacion_service.evaluar_checklist_validaciones", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.block_user_access", return_value={"blocked": True, "user": "emp@test.com", "reason": "ok"}), \
             patch("hubgh.hubgh.services.terminacion_service.generar_carta", mock_carta), \
             patch("hubgh.hubgh.services.terminacion_service.crear_examen_egreso", return_value="CXE-001"), \
             patch("hubgh.hubgh.services.terminacion_service._dispatch_notifications_iniciar"), \
             patch("hubgh.hubgh.services.terminacion_service.publish_people_ops_event", return_value="POE-1"):
            iniciar_terminacion(**_INIT_KWARGS)

        mock_carta.assert_not_called()


# ---------------------------------------------------------------------------
# T-B.9c — validación bloqueante sin override → throw
# ---------------------------------------------------------------------------

class TestIniciarBloqueante(FrappeTestCase):

    def test_blocking_validation_throws(self):
        """Si evaluar_checklist_validaciones tiene Bloqueante, iniciar lanza ValidationError."""
        blocking_item = {
            "codigo_validacion": "incapacidad_abierta",
            "resultado": "Bloqueante",
            "detalle": "Incapacidad INC-001 abierta",
        }

        with patch("hubgh.hubgh.services.terminacion_service.evaluar_checklist_validaciones", return_value=[blocking_item]):
            with self.assertRaises(frappe.exceptions.ValidationError):
                iniciar_terminacion(**_INIT_KWARGS)


# ---------------------------------------------------------------------------
# T-B.9d — snapshot pdv/cargo en before_insert
# ---------------------------------------------------------------------------

class TestBeforeInsertSnapshot(FrappeTestCase):

    def test_before_insert_sets_snapshot_fields(self):
        """before_insert_terminacion debe asignar pdv_al_terminar y cargo_al_terminar."""
        doc = _make_tc_doc()
        doc.pdv_al_terminar = None
        doc.cargo_al_terminar = None
        doc.iniciado_por = None
        doc.iniciado_en = None

        emp = MagicMock()
        emp.pdv = "PDV-SNAPSHOT"
        emp.cargo = "Cargo Test"
        emp.estado = "Activo"

        with patch("hubgh.hubgh.services.terminacion_service.frappe.db.get_value",
                   return_value=["PDV-SNAPSHOT", "Cargo Test", "Activo"]), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.session",
                   MagicMock(user="admin@test.com")), \
             patch("hubgh.hubgh.services.terminacion_service.now_datetime",
                   return_value=_FIXED_NOW):
            before_insert_terminacion(doc)

        # pdv_al_terminar y cargo_al_terminar seteados desde el tuple
        self.assertIsNotNone(doc.pdv_al_terminar)


# ---------------------------------------------------------------------------
# T-B.9e — aplicar_subproceso primera vez → En Curso
# ---------------------------------------------------------------------------

class TestAplicarSubprocesoPrimeraVez(FrappeTestCase):

    def test_first_subproceso_transitions_to_en_curso(self):
        """Primer aplicar_subproceso cambia TC de Iniciado a En Curso."""
        row = _make_subproceso_row(area="sistemas", estado="Pendiente")
        tc_doc = _make_tc_doc(estado="Iniciado")
        tc_doc.subprocesos = [row]

        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_doc", return_value=tc_doc), \
             patch("hubgh.hubgh.services.terminacion_service.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.terminacion_service.publish_people_ops_event", return_value="POE-1"):
            result = aplicar_subproceso("TC-2026-001", "sistemas")

        self.assertEqual(tc_doc.estado, "En Curso")

    def test_aplicar_subproceso_marks_area_completado(self):
        """aplicar_subproceso debe marcar el área como Completado."""
        row = _make_subproceso_row(area="sst", estado="Pendiente")
        tc_doc = _make_tc_doc(estado="Iniciado")
        tc_doc.subprocesos = [row]

        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_doc", return_value=tc_doc), \
             patch("hubgh.hubgh.services.terminacion_service.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.terminacion_service.publish_people_ops_event", return_value="POE-1"):
            aplicar_subproceso("TC-2026-001", "sst")

        self.assertEqual(row.estado, "Completado")


# ---------------------------------------------------------------------------
# T-B.9g — cerrar_terminacion con subprocesos incompletos → throw
# ---------------------------------------------------------------------------

class TestCerrarTerminacionIncompleto(FrappeTestCase):

    def test_close_throws_if_subprocess_incomplete(self):
        """cerrar_terminacion lanza si hay subprocesos Pendientes."""
        row = _make_subproceso_row(area="sistemas", estado="Pendiente")
        tc_doc = _make_tc_doc(estado="En Curso")
        tc_doc.subprocesos = [row]
        tc_doc.resumen_cierre = "Proceso de terminación completado satisfactoriamente en todos los aspectos."

        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_doc", return_value=tc_doc), \
             patch("hubgh.hubgh.services.terminacion_service.now_datetime", return_value=_FIXED_NOW):
            with self.assertRaises(frappe.exceptions.ValidationError):
                cerrar_terminacion("TC-2026-001", tc_doc.resumen_cierre)


# ---------------------------------------------------------------------------
# T-B.9h — cerrar_terminacion happy path
# ---------------------------------------------------------------------------

class TestCerrarTerminacionHappyPath(FrappeTestCase):

    def test_close_sets_cerrado(self):
        """cerrar_terminacion happy path → estado=Cerrado."""
        row_ok = _make_subproceso_row(area="sistemas", estado="Completado")
        tc_doc = _make_tc_doc(estado="En Curso")
        tc_doc.subprocesos = [row_ok]
        tc_doc.resumen_cierre = ""

        resumen = "Todos los subprocesos completados. Empleado desvinculado formalmente del sistema y procesos."

        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_doc", return_value=tc_doc), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.set_value"), \
             patch("hubgh.hubgh.services.terminacion_service.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.terminacion_service._dispatch_notifications_cerrar"), \
             patch("hubgh.hubgh.services.terminacion_service.publish_people_ops_event", return_value="POE-1"):
            result = cerrar_terminacion("TC-2026-001", resumen)

        self.assertEqual(tc_doc.estado, "Cerrado")
        self.assertTrue(result.get("ok"))


class TestCerrarResumenCorto(FrappeTestCase):

    def test_close_throws_if_resumen_too_short(self):
        """cerrar_terminacion lanza si resumen_cierre < 30 chars."""
        row_ok = _make_subproceso_row(area="sistemas", estado="Completado")
        tc_doc = _make_tc_doc(estado="En Curso")
        tc_doc.subprocesos = [row_ok]

        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_doc", return_value=tc_doc), \
             patch("hubgh.hubgh.services.terminacion_service.now_datetime", return_value=_FIXED_NOW):
            with self.assertRaises(frappe.exceptions.ValidationError):
                cerrar_terminacion("TC-2026-001", "Corto")


# ---------------------------------------------------------------------------
# T-B.9i — cancelar desde Iniciado
# ---------------------------------------------------------------------------

class TestCancelarTerminacion(FrappeTestCase):

    def test_cancel_sets_cancelado(self):
        """cancelar_terminacion desde Iniciado → estado=Cancelado."""
        tc_doc = _make_tc_doc(estado="Iniciado")
        tc_doc.subprocesos = []

        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_doc", return_value=tc_doc), \
             patch("hubgh.hubgh.services.terminacion_service.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.terminacion_service.restore_user_access",
                   return_value={"restored": True, "user": "emp@test.com", "reason": "ok"}), \
             patch("hubgh.hubgh.services.terminacion_service.cancelar_si_pendiente", return_value={"ok": True}), \
             patch("hubgh.hubgh.services.terminacion_service.publish_people_ops_event", return_value="POE-1"):
            result = cancelar_terminacion("TC-2026-001", "Error de proceso en creación de TC.")

        self.assertEqual(tc_doc.estado, "Cancelado")
        self.assertTrue(result.get("ok"))

    def test_cancel_from_cerrado_throws(self):
        """cancelar desde Cerrado lanza ValidationError."""
        tc_doc = _make_tc_doc(estado="Cerrado")

        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_doc", return_value=tc_doc):
            with self.assertRaises(frappe.exceptions.ValidationError):
                cancelar_terminacion("TC-2026-001", "Motivo de cancelación")

    def test_cancel_requires_motivo(self):
        """cancelar sin motivo lanza ValidationError."""
        tc_doc = _make_tc_doc(estado="Iniciado")

        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_doc", return_value=tc_doc):
            with self.assertRaises(frappe.exceptions.ValidationError):
                cancelar_terminacion("TC-2026-001", "")


# ---------------------------------------------------------------------------
# T-B.9j — cancelar restaura User access
# ---------------------------------------------------------------------------

class TestCancelarRestauraAcceso(FrappeTestCase):

    def test_cancel_calls_restore_user_access(self):
        """cancelar_terminacion invoca restore_user_access para el empleado."""
        tc_doc = _make_tc_doc(estado="Iniciado")
        tc_doc.subprocesos = []

        mock_restore = MagicMock(return_value={"restored": True, "user": "emp@test.com", "reason": "ok"})
        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_doc", return_value=tc_doc), \
             patch("hubgh.hubgh.services.terminacion_service.now_datetime", return_value=_FIXED_NOW), \
             patch("hubgh.hubgh.services.terminacion_service.restore_user_access", mock_restore), \
             patch("hubgh.hubgh.services.terminacion_service.cancelar_si_pendiente", return_value={"ok": True}), \
             patch("hubgh.hubgh.services.terminacion_service.publish_people_ops_event", return_value="POE-1"):
            cancelar_terminacion("TC-2026-001", "Motivo de cancelación con detalle suficiente para la validación.")

        mock_restore.assert_called_once()
        call_kwargs = mock_restore.call_args
        self.assertEqual(call_kwargs[0][0], "EMP-001")


# ---------------------------------------------------------------------------
# T-B.9k — crear desde caso disciplinario
# ---------------------------------------------------------------------------

class TestCrearDesdeCasoDisciplinario(FrappeTestCase):

    def test_crear_desde_caso_invokes_iniciar(self):
        """crear_terminacion_desde_caso_disciplinario invoca iniciar con justa_causa."""
        case_doc = MagicMock()
        case_doc.name = "CD-001"
        case_doc.empleado = "EMP-001"
        case_doc.fecha_cierre = "2026-06-30"
        case_doc.descripcion_final = "Incumplimiento reiterado de normas de convivencia laboral."

        mock_iniciar = MagicMock(return_value="TC-2026-002")
        with patch("hubgh.hubgh.services.terminacion_service.iniciar_terminacion", mock_iniciar):
            result = crear_terminacion_desde_caso_disciplinario(case_doc)

        mock_iniciar.assert_called_once()
        call_kwargs = mock_iniciar.call_args[1]
        self.assertEqual(call_kwargs.get("causal"), "justa_causa")
        self.assertEqual(call_kwargs.get("caso_disciplinario_origen"), "CD-001")
        self.assertEqual(result, "TC-2026-002")


# ---------------------------------------------------------------------------
# T-B.9l — crear desde novedad SST
# ---------------------------------------------------------------------------

class TestCrearDesdeNovedadSST(FrappeTestCase):

    def test_crear_desde_novedad_sst_invokes_iniciar(self):
        """crear_terminacion_desde_novedad_sst invoca iniciar con causal=otros."""
        novedad_doc = MagicMock()
        novedad_doc.name = "NSST-001"
        novedad_doc.empleado = "EMP-001"
        novedad_doc.fecha_inicio = "2026-06-30"
        novedad_doc.descripcion = "Retiro voluntario del empleado por condición de salud irreversible."

        mock_iniciar = MagicMock(return_value="TC-2026-003")
        with patch("hubgh.hubgh.services.terminacion_service.iniciar_terminacion", mock_iniciar):
            result = crear_terminacion_desde_novedad_sst(novedad_doc)

        mock_iniciar.assert_called_once()
        call_kwargs = mock_iniciar.call_args[1]
        self.assertEqual(call_kwargs.get("causal"), "otros")
        self.assertEqual(call_kwargs.get("novedad_sst_origen"), "NSST-001")


# ---------------------------------------------------------------------------
# T-B.9m — cancelar_terminacion_si_activa
# ---------------------------------------------------------------------------

class TestCancelarSiActiva(FrappeTestCase):

    def test_cancela_tc_activa(self):
        """cancelar_terminacion_si_activa cancela si hay TC activa para el empleado."""
        tc_row = MagicMock()
        tc_row.name = "TC-2026-001"

        mock_cancelar = MagicMock(return_value={"ok": True})
        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[tc_row]), \
             patch("hubgh.hubgh.services.terminacion_service.cancelar_terminacion", mock_cancelar):
            result = cancelar_terminacion_si_activa("EMP-001", source_name="CD:CD-001")

        mock_cancelar.assert_called_once()
        args = mock_cancelar.call_args[0]
        self.assertEqual(args[0], "TC-2026-001")
        self.assertIn("CD:CD-001", args[1])

    def test_no_tc_activa_returns_none(self):
        """Si no hay TC activa, retorna None sin error."""
        with patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[]):
            result = cancelar_terminacion_si_activa("EMP-001", source_name="CD:CD-001")

        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# T-B.9n — evaluar_checklist_validaciones
# ---------------------------------------------------------------------------

class TestEvaluarChecklistValidaciones(FrappeTestCase):

    def test_returns_9_items(self):
        """evaluar_checklist_validaciones retorna exactamente 9 items."""
        with patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", return_value=False), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.count", return_value=0), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.get_value", return_value=None):
            result = evaluar_checklist_validaciones("EMP-001")

        self.assertEqual(len(result), 9)

    def test_all_items_have_required_keys(self):
        """Cada item debe tener codigo_validacion, resultado, descripcion, detalle."""
        with patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", return_value=False), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.count", return_value=0), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.get_value", return_value=None):
            result = evaluar_checklist_validaciones("EMP-001")

        for item in result:
            self.assertIn("codigo_validacion", item)
            self.assertIn("resultado", item)
            self.assertIn("descripcion", item)
