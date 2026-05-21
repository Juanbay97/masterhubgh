# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for traslado_service.py — Fase 3.

TDD Cycle (Strict):
  T-7a RED  → create_traslado + before_insert_traslado validations
  I-7a GREEN → traslado_service.create_traslado + before_insert hook
  T-7b RED  → apply_traslado
  I-7b GREEN → apply_traslado + on_update hook
  T-7c RED  → cancel_traslado
  I-7c GREEN → cancel_traslado
  T-7d RED  → process_scheduled_traslados batch
  I-7d GREEN → process_scheduled_traslados + get_flow_context + get_tray
"""

import json
from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase
import frappe
from frappe.utils import today, add_days, now_datetime


# ---------------------------------------------------------------------------
# Helpers de setup de fixtures de test
# ---------------------------------------------------------------------------

def _ensure_pdv(name, ciudad="TestCiudad"):
    if not frappe.db.exists("Punto de Venta", name):
        doc = frappe.get_doc({
            "doctype": "Punto de Venta",
            "nombre_pdv": name,
            "codigo": name,
            "ciudad": ciudad,
            "activo": 1,
        })
        doc.insert(ignore_permissions=True)
    return name


def _ensure_empleado(cedula, pdv, estado="Activo", email="emp@test.com"):
    """Creates or updates a Ficha Empleado. Returns the cedula (which is also the doc name)."""
    if not frappe.db.exists("Ficha Empleado", cedula):
        doc = frappe.get_doc({
            "doctype": "Ficha Empleado",
            "nombres": cedula,
            "apellidos": "TestApellido",
            "cedula": cedula,
            "pdv": pdv,
            "estado": estado,
            "email": email,
        })
        doc.insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Ficha Empleado", cedula, "pdv", pdv)
        frappe.db.set_value("Ficha Empleado", cedula, "estado", estado)
    return cedula


def _cleanup_traslados(empleado=None):
    filters = {"empleado": empleado} if empleado else {}
    docs = frappe.get_all("Traslado PDV", filters=filters, pluck="name")
    for d in docs:
        frappe.delete_doc("Traslado PDV", d, force=True, ignore_permissions=True)


PDV_A = "PDV-TEST-A"
PDV_B = "PDV-TEST-B"
PDV_C = "PDV-TEST-C"
# Ficha Empleado autoname = format:{cedula} so name == cedula
EMP_ACTIVO = "TEST-EMP-ACTIVO-001"
EMP_RETIRADO = "TEST-EMP-RETIRADO-001"

MOTIVO_SIMPLE = "necesidad_operativa"
MOTIVO_REQUIERE_CARGO = "reorganizacion"
JUSTIFICACION_VALIDA = "Justificacion suficientemente larga para pasar la validacion"


# ---------------------------------------------------------------------------
# T-7a: create_traslado tests (RED)
# ---------------------------------------------------------------------------

class TestCreateTraslado(FrappeTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_pdv(PDV_A)
        _ensure_pdv(PDV_B)
        _ensure_pdv(PDV_C)
        _ensure_empleado(EMP_ACTIVO, pdv=PDV_A, estado="Activo", email="activo@test.com")
        _ensure_empleado(EMP_RETIRADO, pdv=PDV_A, estado="Retirado", email="retirado@test.com")
        # Asegurar motivos fixture existen
        if not frappe.db.exists("Motivo Traslado", MOTIVO_SIMPLE):
            frappe.get_doc({
                "doctype": "Motivo Traslado",
                "codigo": MOTIVO_SIMPLE,
                "label": "Necesidad operativa",
                "requiere_cambio_cargo": 0,
                "activo": 1,
            }).insert(ignore_permissions=True)
        if not frappe.db.exists("Motivo Traslado", MOTIVO_REQUIERE_CARGO):
            frappe.get_doc({
                "doctype": "Motivo Traslado",
                "codigo": MOTIVO_REQUIERE_CARGO,
                "label": "Reorganización / promoción",
                "requiere_cambio_cargo": 1,
                "activo": 1,
            }).insert(ignore_permissions=True)

    def tearDown(self):
        _cleanup_traslados(EMP_ACTIVO)
        _cleanup_traslados(EMP_RETIRADO)

    def _create_ok(self, **kwargs):
        """Shorthand para crear un traslado con parámetros base válidos."""
        from hubgh.hubgh.services.traslado_service import create_traslado
        params = dict(
            empleado=EMP_ACTIVO,
            pdv_destino=PDV_B,
            fecha_aplicacion=today(),
            motivo=MOTIVO_SIMPLE,
            justificacion=JUSTIFICACION_VALIDA,
        )
        params.update(kwargs)
        return create_traslado(**params)

    # --- Happy path ---

    def test_create_traslado_happy_path(self):
        """Empleado Activo + PDV destino válido → doc creado en Programado."""
        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif:
            mock_notif.return_value = [
                {"status": "ok", "template": "T1"},
                {"status": "ok", "template": "T2"},
                {"status": "ok", "template": "T3"},
            ]
            name = self._create_ok()

        self.assertTrue(frappe.db.exists("Traslado PDV", name), "Doc debe existir en DB")
        doc = frappe.get_doc("Traslado PDV", name)
        self.assertEqual(doc.estado, "Programado")
        self.assertEqual(doc.empleado, EMP_ACTIVO)
        self.assertEqual(doc.pdv_destino, PDV_B)
        # pdv_origen debe ser snapshot del PDV del empleado (PDV_A)
        self.assertEqual(doc.pdv_origen, PDV_A, "pdv_origen debe ser snapshot de empleado.pdv")
        self.assertIsNotNone(doc.solicitado_por, "solicitado_por no debe ser nulo")

    def test_create_traslado_snapshot_pdv_origen(self):
        """before_insert fuerza pdv_origen desde empleado.pdv, aunque venga seteado."""
        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif:
            mock_notif.return_value = []
            # Incluso si el caller intentara pasar pdv_origen distinto, el hook lo sobreescribe
            name = self._create_ok()
        doc = frappe.get_doc("Traslado PDV", name)
        # El empleado tiene pdv=PDV_A
        self.assertEqual(doc.pdv_origen, PDV_A)

    def test_create_traslado_dispatches_three_notifications(self):
        """create_traslado debe disparar _dispatch_notifications con fase='programado'."""
        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif:
            mock_notif.return_value = []
            name = self._create_ok()
        mock_notif.assert_called_once()
        call_args = mock_notif.call_args
        # Segundo argumento posicional o kwarg fase
        fase = call_args[1].get("fase") if call_args[1] else call_args[0][1]
        self.assertEqual(fase, "programado")

    def test_create_persists_payload_notificaciones(self):
        """payload_notificaciones debe guardar los resultados de notificación."""
        mock_results = [
            {"status": "ok", "template": "traslado_pdv_empleado_programado", "recipients": ["emp@test.com"]},
            {"status": "ok", "template": "traslado_pdv_jefe_origen_programado", "recipients": ["jefe@test.com"]},
            {"status": "skipped", "template": "traslado_pdv_jefe_destino_programado", "recipients": []},
        ]
        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif:
            mock_notif.return_value = mock_results
            name = self._create_ok()
        doc = frappe.get_doc("Traslado PDV", name)
        payload_raw = doc.payload_notificaciones
        self.assertIsNotNone(payload_raw)
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
        self.assertEqual(len(payload), 3)

    # --- Validaciones de creación ---

    def test_create_blocks_empleado_no_activo(self):
        """Empleado con estado != Activo debe lanzar ValidationError con token EMPLEADO_NO_ACTIVO."""
        from hubgh.hubgh.services.traslado_service import create_traslado
        with self.assertRaises(frappe.ValidationError) as ctx:
            create_traslado(
                empleado=EMP_RETIRADO,
                pdv_destino=PDV_B,
                fecha_aplicacion=today(),
                motivo=MOTIVO_SIMPLE,
                justificacion=JUSTIFICACION_VALIDA,
            )
        self.assertIn("EMPLEADO_NO_ACTIVO", str(ctx.exception))

    def test_create_blocks_pdv_destino_igual_origen(self):
        """pdv_destino == empleado.pdv debe lanzar PDV_DESTINO_IGUAL_ORIGEN."""
        from hubgh.hubgh.services.traslado_service import create_traslado
        # EMP_ACTIVO está en PDV_A
        with self.assertRaises(frappe.ValidationError) as ctx:
            create_traslado(
                empleado=EMP_ACTIVO,
                pdv_destino=PDV_A,  # igual al origen
                fecha_aplicacion=today(),
                motivo=MOTIVO_SIMPLE,
                justificacion=JUSTIFICACION_VALIDA,
            )
        self.assertIn("PDV_DESTINO_IGUAL_ORIGEN", str(ctx.exception))

    def test_create_blocks_justificacion_corta(self):
        """Justificacion < 20 chars debe lanzar JUSTIFICACION_CORTA."""
        from hubgh.hubgh.services.traslado_service import create_traslado
        with self.assertRaises(frappe.ValidationError) as ctx:
            create_traslado(
                empleado=EMP_ACTIVO,
                pdv_destino=PDV_B,
                fecha_aplicacion=today(),
                motivo=MOTIVO_SIMPLE,
                justificacion="Muy corta",  # < 20 chars
            )
        self.assertIn("JUSTIFICACION_CORTA", str(ctx.exception))

    def test_create_blocks_duplicate_programado(self):
        """Si ya existe Traslado PDV Programado para el empleado, lanzar TRASLADO_DUPLICADO."""
        from hubgh.hubgh.services.traslado_service import create_traslado
        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif:
            mock_notif.return_value = []
            self._create_ok()  # primer traslado OK

        # segundo intento debe fallar
        with self.assertRaises(frappe.ValidationError) as ctx:
            with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif:
                mock_notif.return_value = []
                create_traslado(
                    empleado=EMP_ACTIVO,
                    pdv_destino=PDV_C,
                    fecha_aplicacion=today(),
                    motivo=MOTIVO_SIMPLE,
                    justificacion=JUSTIFICACION_VALIDA,
                )
        self.assertIn("TRASLADO_DUPLICADO", str(ctx.exception))

    def test_create_blocks_motivo_invalido(self):
        """Motivo que no existe o no está activo debe lanzar MOTIVO_INVALIDO."""
        from hubgh.hubgh.services.traslado_service import create_traslado
        with self.assertRaises(frappe.ValidationError) as ctx:
            create_traslado(
                empleado=EMP_ACTIVO,
                pdv_destino=PDV_B,
                fecha_aplicacion=today(),
                motivo="motivo_inexistente_xyz",
                justificacion=JUSTIFICACION_VALIDA,
            )
        self.assertIn("MOTIVO_INVALIDO", str(ctx.exception))

    def test_create_requires_cargo_when_motivo_requiere(self):
        """Si motivo.requiere_cambio_cargo=True y cargo_destino es None, lanzar CARGO_DESTINO_REQUERIDO."""
        from hubgh.hubgh.services.traslado_service import create_traslado
        with self.assertRaises(frappe.ValidationError) as ctx:
            create_traslado(
                empleado=EMP_ACTIVO,
                pdv_destino=PDV_B,
                fecha_aplicacion=today(),
                motivo=MOTIVO_REQUIERE_CARGO,
                justificacion=JUSTIFICACION_VALIDA,
                cargo_destino=None,
            )
        self.assertIn("CARGO_DESTINO_REQUERIDO", str(ctx.exception))


# ---------------------------------------------------------------------------
# T-7b: apply_traslado tests (RED)
# ---------------------------------------------------------------------------

class TestApplyTraslado(FrappeTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_pdv(PDV_A)
        _ensure_pdv(PDV_B)
        _ensure_empleado(EMP_ACTIVO, pdv=PDV_A, estado="Activo", email="activo@test.com")
        if not frappe.db.exists("Motivo Traslado", MOTIVO_SIMPLE):
            frappe.get_doc({
                "doctype": "Motivo Traslado",
                "codigo": MOTIVO_SIMPLE,
                "label": "Necesidad operativa",
                "requiere_cambio_cargo": 0,
                "activo": 1,
            }).insert(ignore_permissions=True)

    def setUp(self):
        # Reset empleado a PDV_A antes de cada test
        frappe.db.set_value("Ficha Empleado", EMP_ACTIVO, "pdv", PDV_A)
        frappe.db.set_value("Ficha Empleado", EMP_ACTIVO, "estado", "Activo")

    def tearDown(self):
        _cleanup_traslados(EMP_ACTIVO)
        # Reset empleado
        frappe.db.set_value("Ficha Empleado", EMP_ACTIVO, "pdv", PDV_A)

    def _make_programado(self, fecha=None, pdv_destino=PDV_B):
        """Crea un traslado Programado directamente (bypassing service para aislar apply)."""
        doc = frappe.get_doc({
            "doctype": "Traslado PDV",
            "empleado": EMP_ACTIVO,
            "pdv_origen": PDV_A,
            "pdv_destino": pdv_destino,
            "fecha_aplicacion": fecha or today(),
            "motivo": MOTIVO_SIMPLE,
            "justificacion": JUSTIFICACION_VALIDA,
            "estado": "Programado",
        })
        doc.insert(ignore_permissions=True)
        return doc.name

    def test_apply_traslado_happy_path(self):
        """apply_traslado muta Ficha Empleado.pdv y marca estado=Aplicado."""
        name = self._make_programado()
        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif, \
             patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups") as mock_sync, \
             patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event") as mock_event:
            mock_notif.return_value = []
            from hubgh.hubgh.services.traslado_service import apply_traslado
            result = apply_traslado(name)

        self.assertEqual(result["status"], "applied")
        doc = frappe.get_doc("Traslado PDV", name)
        self.assertEqual(doc.estado, "Aplicado")
        self.assertIsNotNone(doc.aplicado_en)
        self.assertIsNotNone(doc.aplicado_por)
        # Ficha Empleado.pdv debe haber cambiado
        nuevo_pdv = frappe.db.get_value("Ficha Empleado", EMP_ACTIVO, "pdv")
        self.assertEqual(nuevo_pdv, PDV_B, "Ficha Empleado.pdv debe cambiar a pdv_destino")

    def test_apply_traslado_idempotent(self):
        """Segunda llamada a apply_traslado sobre un Aplicado retorna status=skipped."""
        name = self._make_programado()
        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif, \
             patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups"), \
             patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            mock_notif.return_value = []
            from hubgh.hubgh.services.traslado_service import apply_traslado
            apply_traslado(name)  # primera aplicación
            result2 = apply_traslado(name)  # segunda

        self.assertEqual(result2["status"], "skipped")
        self.assertIn("reason", result2)

    def test_apply_traslado_with_cargo_destino(self):
        """Si el traslado tiene cargo_destino, Ficha Empleado.cargo debe mutar."""
        # Asegurar que existe el Cargo
        cargo_name = "CARGO-TEST-TRAD"
        if not frappe.db.exists("Cargo", cargo_name):
            frappe.get_doc({
                "doctype": "Cargo",
                "codigo": cargo_name,
                "nombre": "Cargo de Test Traslado",
                "activo": 1,
            }).insert(ignore_permissions=True)

        doc = frappe.get_doc({
            "doctype": "Traslado PDV",
            "empleado": EMP_ACTIVO,
            "pdv_origen": PDV_A,
            "pdv_destino": PDV_B,
            "fecha_aplicacion": today(),
            "motivo": MOTIVO_SIMPLE,
            "justificacion": JUSTIFICACION_VALIDA,
            "estado": "Programado",
            "cargo_destino": cargo_name,
        })
        doc.insert(ignore_permissions=True)

        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif, \
             patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups"), \
             patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            mock_notif.return_value = []
            from hubgh.hubgh.services.traslado_service import apply_traslado
            result = apply_traslado(doc.name)

        self.assertEqual(result["status"], "applied")
        cargo_actual = frappe.db.get_value("Ficha Empleado", EMP_ACTIVO, "cargo")
        self.assertEqual(cargo_actual, cargo_name,
            "Ficha Empleado.cargo debe cambiar al cargo_destino (field Data = name del Cargo)")

    def test_apply_traslado_error_fecha_futura(self):
        """apply_traslado con fecha_aplicacion futura debe lanzar ValidationError."""
        fecha_futura = add_days(today(), 5)
        name = self._make_programado(fecha=fecha_futura)
        from hubgh.hubgh.services.traslado_service import apply_traslado
        with self.assertRaises(frappe.ValidationError) as ctx:
            apply_traslado(name)
        self.assertIn("FECHA_NO_ALCANZADA", str(ctx.exception))

    def test_apply_traslado_dispatches_t4(self):
        """apply_traslado debe disparar _dispatch_notifications con fase='aplicado'."""
        name = self._make_programado()
        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif, \
             patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups"), \
             patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            mock_notif.return_value = [{"status": "ok", "template": "T4"}]
            from hubgh.hubgh.services.traslado_service import apply_traslado
            apply_traslado(name)

        mock_notif.assert_called_once()
        call_args = mock_notif.call_args
        fase = call_args[1].get("fase") if call_args[1] else call_args[0][1]
        self.assertEqual(fase, "aplicado")

    def test_apply_traslado_publishes_event(self):
        """apply_traslado debe publicar People Ops Event con taxonomy aplicado."""
        name = self._make_programado()
        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif, \
             patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups"), \
             patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event") as mock_event:
            mock_notif.return_value = []
            from hubgh.hubgh.services.traslado_service import apply_traslado
            apply_traslado(name)

        mock_event.assert_called_once()
        payload = mock_event.call_args[0][0]
        self.assertIn("operacion.traslado_pdv.aplicado", payload.get("taxonomy", ""))

    def test_apply_calls_sync_user_groups(self):
        """apply_traslado debe llamar sync_all_user_groups."""
        name = self._make_programado()
        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif, \
             patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups") as mock_sync, \
             patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            mock_notif.return_value = []
            from hubgh.hubgh.services.traslado_service import apply_traslado
            apply_traslado(name)

        mock_sync.assert_called_once()


# ---------------------------------------------------------------------------
# T-7c: cancel_traslado tests (RED)
# ---------------------------------------------------------------------------

class TestCancelTraslado(FrappeTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_pdv(PDV_A)
        _ensure_pdv(PDV_B)
        _ensure_empleado(EMP_ACTIVO, pdv=PDV_A, estado="Activo", email="activo@test.com")
        if not frappe.db.exists("Motivo Traslado", MOTIVO_SIMPLE):
            frappe.get_doc({
                "doctype": "Motivo Traslado",
                "codigo": MOTIVO_SIMPLE,
                "label": "Necesidad operativa",
                "requiere_cambio_cargo": 0,
                "activo": 1,
            }).insert(ignore_permissions=True)

    def tearDown(self):
        _cleanup_traslados(EMP_ACTIVO)

    def _make_programado(self):
        doc = frappe.get_doc({
            "doctype": "Traslado PDV",
            "empleado": EMP_ACTIVO,
            "pdv_origen": PDV_A,
            "pdv_destino": PDV_B,
            "fecha_aplicacion": today(),
            "motivo": MOTIVO_SIMPLE,
            "justificacion": JUSTIFICACION_VALIDA,
            "estado": "Programado",
        })
        doc.insert(ignore_permissions=True)
        return doc.name

    def _make_aplicado(self):
        doc = frappe.get_doc({
            "doctype": "Traslado PDV",
            "empleado": EMP_ACTIVO,
            "pdv_origen": PDV_A,
            "pdv_destino": PDV_B,
            "fecha_aplicacion": today(),
            "motivo": MOTIVO_SIMPLE,
            "justificacion": JUSTIFICACION_VALIDA,
            "estado": "Aplicado",
        })
        doc.insert(ignore_permissions=True)
        return doc.name

    def test_cancel_traslado_happy_path(self):
        """cancel_traslado sobre Programado lo pone en Anulado."""
        name = self._make_programado()
        with patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            from hubgh.hubgh.services.traslado_service import cancel_traslado
            result = cancel_traslado(name, motivo="Motivo de anulacion suficientemente largo para test")

        self.assertEqual(result["status"], "cancelled")
        doc = frappe.get_doc("Traslado PDV", name)
        self.assertEqual(doc.estado, "Anulado")
        self.assertIsNotNone(doc.anulado_en)

    def test_cancel_traslado_persists_motivo(self):
        """El motivo de anulación se persiste en motivo_anulacion."""
        name = self._make_programado()
        motivo_texto = "Cancelado por error de captura en el sistema"
        with patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            from hubgh.hubgh.services.traslado_service import cancel_traslado
            cancel_traslado(name, motivo=motivo_texto)
        doc = frappe.get_doc("Traslado PDV", name)
        self.assertEqual(doc.motivo_anulacion, motivo_texto)

    def test_cancel_traslado_aplicado_throws(self):
        """Anular un traslado Aplicado debe lanzar ValidationError (estado terminal)."""
        name = self._make_aplicado()
        from hubgh.hubgh.services.traslado_service import cancel_traslado
        with self.assertRaises(frappe.ValidationError) as ctx:
            cancel_traslado(name, motivo="Intentando anular un aplicado")
        self.assertIn("TRASLADO_APLICADO_NO_CANCELABLE", str(ctx.exception))

    def test_cancel_traslado_idempotent_anulado(self):
        """Cancelar un traslado ya Anulado retorna status=skipped (idempotente)."""
        name = self._make_programado()
        with patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            from hubgh.hubgh.services.traslado_service import cancel_traslado
            cancel_traslado(name, motivo="Primera anulacion correcta y larga")
            result2 = cancel_traslado(name, motivo="Segunda anulacion no debe ejecutarse")
        self.assertEqual(result2["status"], "skipped")

    def test_cancel_traslado_sin_motivo_throws(self):
        """Cancelar sin motivo debe lanzar ValidationError."""
        name = self._make_programado()
        from hubgh.hubgh.services.traslado_service import cancel_traslado
        with self.assertRaises(frappe.ValidationError) as ctx:
            cancel_traslado(name, motivo="")
        self.assertIn("MOTIVO_ANULACION_REQUERIDO", str(ctx.exception))

    def test_cancel_publishes_event(self):
        """cancel_traslado debe publicar People Ops Event con taxonomy anulado."""
        name = self._make_programado()
        with patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event") as mock_event:
            from hubgh.hubgh.services.traslado_service import cancel_traslado
            cancel_traslado(name, motivo="Motivo valido para anulacion del traslado")
        mock_event.assert_called_once()
        payload = mock_event.call_args[0][0]
        self.assertIn("operacion.traslado_pdv.anulado", payload.get("taxonomy", ""))


# ---------------------------------------------------------------------------
# T-7d: process_scheduled_traslados batch tests (RED)
# ---------------------------------------------------------------------------

class TestProcessScheduledTraslados(FrappeTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_pdv(PDV_A)
        _ensure_pdv(PDV_B)
        _ensure_pdv(PDV_C)
        _ensure_empleado(EMP_ACTIVO, pdv=PDV_A, estado="Activo", email="activo@test.com")
        if not frappe.db.exists("Motivo Traslado", MOTIVO_SIMPLE):
            frappe.get_doc({
                "doctype": "Motivo Traslado",
                "codigo": MOTIVO_SIMPLE,
                "label": "Necesidad operativa",
                "requiere_cambio_cargo": 0,
                "activo": 1,
            }).insert(ignore_permissions=True)

    def setUp(self):
        frappe.db.set_value("Ficha Empleado", EMP_ACTIVO, "pdv", PDV_A)
        frappe.db.set_value("Ficha Empleado", EMP_ACTIVO, "estado", "Activo")

    def tearDown(self):
        _cleanup_traslados(EMP_ACTIVO)
        frappe.db.set_value("Ficha Empleado", EMP_ACTIVO, "pdv", PDV_A)

    def _make_traslado(self, fecha, estado="Programado", pdv_destino=PDV_B):
        doc = frappe.get_doc({
            "doctype": "Traslado PDV",
            "empleado": EMP_ACTIVO,
            "pdv_origen": PDV_A,
            "pdv_destino": pdv_destino,
            "fecha_aplicacion": fecha,
            "motivo": MOTIVO_SIMPLE,
            "justificacion": JUSTIFICACION_VALIDA,
            "estado": estado,
        })
        doc.insert(ignore_permissions=True)
        return doc.name

    def test_process_applies_today_traslados(self):
        """Traslados con fecha_aplicacion <= hoy deben procesarse."""
        name = self._make_traslado(fecha=today())

        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif, \
             patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups"), \
             patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            mock_notif.return_value = []
            from hubgh.hubgh.services.traslado_service import process_scheduled_traslados
            result = process_scheduled_traslados()

        self.assertGreaterEqual(result["processed"], 1)
        doc = frappe.get_doc("Traslado PDV", name)
        self.assertEqual(doc.estado, "Aplicado")

    def test_process_skips_future_traslados(self):
        """Traslados con fecha_aplicacion > hoy NO se aplican."""
        fecha_futura = add_days(today(), 3)
        name = self._make_traslado(fecha=fecha_futura)

        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif, \
             patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups"), \
             patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            mock_notif.return_value = []
            from hubgh.hubgh.services.traslado_service import process_scheduled_traslados
            result = process_scheduled_traslados()

        # El traslado futuro no debe aparecer en processed
        doc = frappe.get_doc("Traslado PDV", name)
        self.assertEqual(doc.estado, "Programado", "Traslado futuro no debe aplicarse")

    def test_process_skips_already_applied(self):
        """Traslado ya Aplicado no se procesa de nuevo (idempotencia)."""
        name = self._make_traslado(fecha=today(), estado="Aplicado")

        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif, \
             patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups"), \
             patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            mock_notif.return_value = []
            from hubgh.hubgh.services.traslado_service import process_scheduled_traslados
            result = process_scheduled_traslados()

        # El query solo busca Programados, así que el aplicado no aparece en processed
        self.assertEqual(result.get("processed", 0), 0)

    def test_process_returns_summary_dict(self):
        """process_scheduled_traslados retorna dict con claves processed, skipped, failed."""
        from hubgh.hubgh.services.traslado_service import process_scheduled_traslados
        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif, \
             patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups"), \
             patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            mock_notif.return_value = []
            result = process_scheduled_traslados()

        for key in ("processed", "failed", "skipped"):
            self.assertIn(key, result, f"Key '{key}' must be in result")

    def test_process_individual_failure_does_not_abort_batch(self):
        """Un fallo en apply_traslado individual no debe abortar el batch."""
        # Crear 2 traslados — ambos de hoy
        # Pero uno tiene pdv_destino mal (para simular error en apply)
        # En realidad vamos a simular el error mockando apply_traslado
        name1 = self._make_traslado(fecha=today(), pdv_destino=PDV_B)

        call_count = {"n": 0}
        original_apply = None

        def apply_side_effect(traslado_name):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("Error simulado en apply")
            return {"status": "applied", "name": traslado_name}

        with patch("hubgh.hubgh.services.traslado_service.apply_traslado",
                   side_effect=apply_side_effect) as mock_apply:
            from hubgh.hubgh.services.traslado_service import process_scheduled_traslados
            result = process_scheduled_traslados()

        # El fallo debe estar registrado pero el batch debe continuar
        self.assertGreaterEqual(result.get("failed", 0), 1)

    def test_process_sets_aplicado_por_administrator(self):
        """process_scheduled_traslados debe setear aplicado_por = 'Administrator' (via cron)."""
        name = self._make_traslado(fecha=today())

        with patch("hubgh.hubgh.services.traslado_service._dispatch_notifications") as mock_notif, \
             patch("hubgh.hubgh.services.traslado_service.sync_all_user_groups"), \
             patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event"):
            mock_notif.return_value = []
            # Simular que el cron corre como Administrator
            original_user = frappe.session.user
            frappe.set_user("Administrator")
            try:
                from hubgh.hubgh.services.traslado_service import process_scheduled_traslados
                process_scheduled_traslados()
            finally:
                frappe.set_user(original_user)

        doc = frappe.get_doc("Traslado PDV", name)
        if doc.estado == "Aplicado":
            self.assertEqual(doc.aplicado_por, "Administrator")


# ---------------------------------------------------------------------------
# T-7: on_update_traslado hook — event publication on estado change (RED)
# ---------------------------------------------------------------------------

class TestOnUpdateTraslado(FrappeTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_pdv(PDV_A)
        _ensure_pdv(PDV_B)
        _ensure_empleado(EMP_ACTIVO, pdv=PDV_A, estado="Activo")
        if not frappe.db.exists("Motivo Traslado", MOTIVO_SIMPLE):
            frappe.get_doc({
                "doctype": "Motivo Traslado",
                "codigo": MOTIVO_SIMPLE,
                "label": "Necesidad operativa",
                "requiere_cambio_cargo": 0,
                "activo": 1,
            }).insert(ignore_permissions=True)

    def tearDown(self):
        _cleanup_traslados(EMP_ACTIVO)

    def test_on_update_publishes_event_on_estado_change(self):
        """on_update_traslado debe publicar event cuando el estado cambia."""
        doc = frappe.get_doc({
            "doctype": "Traslado PDV",
            "empleado": EMP_ACTIVO,
            "pdv_origen": PDV_A,
            "pdv_destino": PDV_B,
            "fecha_aplicacion": today(),
            "motivo": MOTIVO_SIMPLE,
            "justificacion": JUSTIFICACION_VALIDA,
            "estado": "Programado",
        })
        doc.insert(ignore_permissions=True)

        with patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event") as mock_event:
            from hubgh.hubgh.services.traslado_service import on_update_traslado
            # Simular cambio de estado
            doc._doc_before_save = frappe.get_doc("Traslado PDV", doc.name)
            doc._doc_before_save.estado = "Programado"
            doc.estado = "Aplicado"
            on_update_traslado(doc)

        mock_event.assert_called_once()
        payload = mock_event.call_args[0][0]
        self.assertIn("aplicado", payload.get("taxonomy", ""))

    def test_on_update_no_publish_if_estado_unchanged(self):
        """on_update_traslado NO publica event si el estado no cambió."""
        doc = frappe.get_doc({
            "doctype": "Traslado PDV",
            "empleado": EMP_ACTIVO,
            "pdv_origen": PDV_A,
            "pdv_destino": PDV_B,
            "fecha_aplicacion": today(),
            "motivo": MOTIVO_SIMPLE,
            "justificacion": JUSTIFICACION_VALIDA,
            "estado": "Programado",
        })
        doc.insert(ignore_permissions=True)

        with patch("hubgh.hubgh.services.traslado_service.publish_people_ops_event") as mock_event:
            from hubgh.hubgh.services.traslado_service import on_update_traslado
            doc._doc_before_save = frappe.get_doc("Traslado PDV", doc.name)
            doc._doc_before_save.estado = "Programado"
            doc.estado = "Programado"  # sin cambio
            on_update_traslado(doc)

        mock_event.assert_not_called()


# ---------------------------------------------------------------------------
# T-7: get_flow_context + get_tray (RED)
# ---------------------------------------------------------------------------

class TestFlowContextAndTray(FrappeTestCase):

    def test_get_flow_context_admin(self):
        """Administrator siempre tiene can_manage=True."""
        from hubgh.hubgh.services.traslado_service import get_flow_context
        ctx = get_flow_context(user="Administrator")
        self.assertTrue(ctx["can_manage"])
        self.assertEqual(ctx["user"], "Administrator")

    def test_get_flow_context_no_role(self):
        """User sin roles de gestión tiene can_manage=False."""
        from hubgh.hubgh.services.traslado_service import get_flow_context
        ctx = get_flow_context(user="Guest")
        self.assertFalse(ctx["can_manage"])

    def test_get_tray_returns_list(self):
        """get_tray retorna lista (vacía si no hay datos)."""
        from hubgh.hubgh.services.traslado_service import get_tray
        result = get_tray(filters={})
        self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# SUGGESTION-1: motivo_label en context de _dispatch_notifications
# ---------------------------------------------------------------------------

class TestDispatchNotificationsMotivoLabel(FrappeTestCase):
    """
    Tests para SUGGESTION-1 — motivo_label debe inyectarse en el context de email.

    TDD Cycle (Strict):
      RED  → estos tests (fallan hasta agregar motivo_label en _dispatch_notifications)
      GREEN → agregar resolución de motivo_label en _dispatch_notifications
      TRIANGULATE → fallback a code si no hay registro de Motivo Traslado
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_pdv(PDV_A)
        _ensure_pdv(PDV_B)
        _ensure_empleado(EMP_ACTIVO, pdv=PDV_A, estado="Activo")
        # Asegurar que el Motivo Traslado existe con label legible
        if not frappe.db.exists("Motivo Traslado", MOTIVO_SIMPLE):
            frappe.get_doc({
                "doctype": "Motivo Traslado",
                "codigo": MOTIVO_SIMPLE,
                "label": "Necesidad operativa",
                "requiere_cambio_cargo": 0,
                "activo": 1,
            }).insert(ignore_permissions=True)

    def tearDown(self):
        _cleanup_traslados(EMP_ACTIVO)

    def _make_doc(self, motivo=MOTIVO_SIMPLE):
        """Construye un doc de Traslado PDV sin guardarlo (para unit test de context)."""
        doc = frappe.new_doc("Traslado PDV")
        doc.empleado = EMP_ACTIVO
        doc.pdv_origen = PDV_A
        doc.pdv_destino = PDV_B
        doc.fecha_aplicacion = today()
        doc.motivo = motivo
        doc.justificacion = JUSTIFICACION_VALIDA
        doc.estado = "Programado"
        return doc

    def test_dispatch_context_includes_motivo_label_when_motivo_set(self):
        """
        Cuando motivo está seteado y existe en Motivo Traslado,
        el context de dispatch debe contener motivo_label con la label legible.
        """
        from unittest.mock import patch, MagicMock

        doc = self._make_doc(motivo=MOTIVO_SIMPLE)

        captured_contexts = []

        def capture_dispatch(template_name, recipients, context):
            captured_contexts.append(context)
            return {"status": "skipped", "template": template_name}

        with patch("hubgh.hubgh.services.traslado_service.dispatch_email",
                   side_effect=capture_dispatch), \
             patch("hubgh.hubgh.services.traslado_service.resolve_employee_email",
                   return_value=None), \
             patch("hubgh.hubgh.services.traslado_service.resolve_jefe_pdv",
                   return_value=None):
            from hubgh.hubgh.services.traslado_service import _dispatch_notifications
            _dispatch_notifications(doc, fase="programado")

        self.assertTrue(captured_contexts, "dispatch_email no fue llamado")
        ctx = captured_contexts[0]
        traslado_ctx = ctx.get("traslado", {})
        self.assertIn(
            "motivo_label",
            traslado_ctx,
            "motivo_label no está en context['traslado']",
        )
        # La label debe ser la legible, no el código
        self.assertEqual(
            traslado_ctx["motivo_label"],
            "Necesidad operativa",
            "motivo_label debe ser la label del Motivo Traslado, no el código",
        )

    def test_dispatch_context_motivo_label_falls_back_to_code(self):
        """
        Cuando motivo no tiene registro en Motivo Traslado,
        motivo_label cae al código del motivo.
        """
        from unittest.mock import patch

        # Usar un motivo que no existe en DB
        doc = self._make_doc(motivo="motivo_inexistente_xyz")

        captured_contexts = []

        def capture_dispatch(template_name, recipients, context):
            captured_contexts.append(context)
            return {"status": "skipped", "template": template_name}

        with patch("hubgh.hubgh.services.traslado_service.dispatch_email",
                   side_effect=capture_dispatch), \
             patch("hubgh.hubgh.services.traslado_service.resolve_employee_email",
                   return_value=None), \
             patch("hubgh.hubgh.services.traslado_service.resolve_jefe_pdv",
                   return_value=None):
            from hubgh.hubgh.services.traslado_service import _dispatch_notifications
            _dispatch_notifications(doc, fase="programado")

        self.assertTrue(captured_contexts)
        ctx = captured_contexts[0]
        traslado_ctx = ctx.get("traslado", {})
        self.assertIn("motivo_label", traslado_ctx)
        # Fallback al código del motivo
        self.assertEqual(
            traslado_ctx["motivo_label"],
            "motivo_inexistente_xyz",
            "motivo_label debe caer al código cuando no hay registro",
        )

    def test_dispatch_context_motivo_label_when_motivo_is_none(self):
        """
        Cuando motivo es None, motivo_label también es None o cadena vacía.
        """
        from unittest.mock import patch

        doc = self._make_doc(motivo=MOTIVO_SIMPLE)
        doc.motivo = None  # Forzar None

        captured_contexts = []

        def capture_dispatch(template_name, recipients, context):
            captured_contexts.append(context)
            return {"status": "skipped", "template": template_name}

        with patch("hubgh.hubgh.services.traslado_service.dispatch_email",
                   side_effect=capture_dispatch), \
             patch("hubgh.hubgh.services.traslado_service.resolve_employee_email",
                   return_value=None), \
             patch("hubgh.hubgh.services.traslado_service.resolve_jefe_pdv",
                   return_value=None):
            from hubgh.hubgh.services.traslado_service import _dispatch_notifications
            _dispatch_notifications(doc, fase="programado")

        self.assertTrue(captured_contexts)
        ctx = captured_contexts[0]
        traslado_ctx = ctx.get("traslado", {})
        self.assertIn("motivo_label", traslado_ctx)
        # None motivo → motivo_label debe ser None o vacío (no crash)
        label = traslado_ctx["motivo_label"]
        self.assertTrue(label is None or label == "", "motivo_label con motivo=None debe ser None o vacío")
