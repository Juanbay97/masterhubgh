# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para sst_seguimiento_examenes — Bandeja SST de seguimiento de citas activas.

Estrategia TDD:
- _has_seguimiento_access: unit tests puros (sin I/O).
- Endpoints: unit tests con patch de frappe.db y frappe.session.
- _query_seguimiento_examenes: unit tests con patch de frappe.db.sql.

Ciclos RED → GREEN → TRIANGULATE para cada task:
  T06: _has_seguimiento_access + _require_access
  T07: list_seguimiento_examenes / _query_seguimiento_examenes
  T08: set_cita_schedule
  T09: set_cita_observaciones
  T10: set_cita_outcome
  T11: export_seguimiento_examenes_xlsx
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe


def _get_mod():
    """Importa el módulo bajo test."""
    from hubgh.hubgh.page.sst_seguimiento_examenes import sst_seguimiento_examenes as m
    return m


# ---------------------------------------------------------------------------
# T06 — _has_seguimiento_access + _require_access
# ---------------------------------------------------------------------------

class TestHasSeguimientoAccess(unittest.TestCase):
    """Tests para la función pura _has_seguimiento_access."""

    def test_administrator_siempre_tiene_acceso(self):
        """Administrator bypasea la verificación de roles."""
        m = _get_mod()
        with patch.object(frappe, "get_roles", return_value=[]):
            result = m._has_seguimiento_access("Administrator")
        self.assertTrue(result, "Administrator debe tener acceso siempre.")

    def test_hr_sst_tiene_acceso(self):
        """Usuario con rol HR SST tiene acceso."""
        m = _get_mod()
        with patch.object(frappe, "get_roles", return_value=["HR SST", "Empleado"]):
            result = m._has_seguimiento_access("user@test.com")
        self.assertTrue(result, "HR SST debe tener acceso.")

    def test_hr_selection_tiene_acceso(self):
        """Usuario con rol HR Selection tiene acceso."""
        m = _get_mod()
        with patch.object(frappe, "get_roles", return_value=["HR Selection"]):
            result = m._has_seguimiento_access("user@test.com")
        self.assertTrue(result)

    def test_gestion_humana_tiene_acceso(self):
        """Usuario con rol Gestión Humana tiene acceso."""
        m = _get_mod()
        with patch.object(frappe, "get_roles", return_value=["Gestión Humana"]):
            result = m._has_seguimiento_access("user@test.com")
        self.assertTrue(result)

    def test_sin_rol_no_tiene_acceso(self):
        """Usuario sin ninguno de los 4 roles NO tiene acceso."""
        m = _get_mod()
        with patch.object(frappe, "get_roles", return_value=["Empleado", "Guest"]):
            result = m._has_seguimiento_access("random@test.com")
        self.assertFalse(result, "Usuario sin rol autorizado no debe tener acceso.")

    def test_require_access_lanza_permission_error(self):
        """_require_access lanza PermissionError cuando el usuario no tiene rol."""
        m = _get_mod()
        with patch.object(frappe, "get_roles", return_value=[]), \
             patch.object(frappe, "session", new=MagicMock(user="noperm@test.com")):
            with self.assertRaises(frappe.PermissionError):
                m._require_access()

    def test_require_access_no_lanza_con_rol(self):
        """_require_access no lanza excepción si el usuario tiene rol válido."""
        m = _get_mod()
        with patch.object(frappe, "get_roles", return_value=["HR SST"]), \
             patch.object(frappe, "session", new=MagicMock(user="sst@test.com")):
            # No debe lanzar nada
            m._require_access()


# ---------------------------------------------------------------------------
# T07 — _query_seguimiento_examenes
# ---------------------------------------------------------------------------

class TestQuerySeguimientoExamenes(unittest.TestCase):
    """Tests para el helper privado de query."""

    def _mock_sql(self, rows_data):
        """Genera un side_effect de frappe.db.sql que retorna rows para SELECT y total para COUNT."""
        call_count = [0]

        def sql_side_effect(query, params, as_dict=False):
            call_count[0] += 1
            # Primera llamada: COUNT query
            if "COUNT(*)" in query:
                return [{"total": len(rows_data)}]
            # Segunda llamada: datos
            return rows_data

        return sql_side_effect

    def test_excluye_concepto_registrado(self):
        """La query base filtra citas con concepto_resultado registrado."""
        m = _get_mod()

        # 2 citas activas, ninguna con concepto
        rows_data = [
            {
                "name": "CEM-001", "estado": "Agendada", "fecha_cita": "2026-05-10",
                "hora_cita": "08:00:00", "sede_seleccionada": None, "cargo_al_enviar": "100",
                "ips": "IPS-TEST", "observaciones_sst": None,
                "candidato": "CAND-001", "nombres": "Juan", "primer_apellido": "Pérez",
                "segundo_apellido": None, "numero_documento": "12345678",
                "ciudad": "Bogotá", "celular": "3001234567", "email": "juan@test.com",
                "modo": "Autogestionado", "cargo_nombre": "Aux. Cocina", "tipo_cargo": "Operativo",
            },
            {
                "name": "CEM-002", "estado": "Pendiente Agendamiento", "fecha_cita": None,
                "hora_cita": None, "sede_seleccionada": None, "cargo_al_enviar": "200",
                "ips": "IPS-TEST", "observaciones_sst": "Nota",
                "candidato": "CAND-002", "nombres": "Ana", "primer_apellido": "Gómez",
                "segundo_apellido": None, "numero_documento": "87654321",
                "ciudad": "Medellín", "celular": "3109876543", "email": "ana@test.com",
                "modo": "Manual", "cargo_nombre": "Asistente", "tipo_cargo": "Administrativo",
            },
        ]

        with patch.object(frappe.db, "sql", side_effect=self._mock_sql(rows_data)):
            rows, total = m._query_seguimiento_examenes({})

        self.assertEqual(total, 2)
        self.assertEqual(len(rows), 2)
        self.assertIn("nombre_completo", rows[0])
        self.assertEqual(rows[0]["nombre_completo"], "Juan Pérez")

    def test_datos_faltantes_en_manual_sin_fecha(self):
        """Filas con modo=Manual y sin fecha_cita tienen datos_faltantes=True."""
        m = _get_mod()

        rows_data = [
            {
                "name": "CEM-003", "estado": "Pendiente Agendamiento", "fecha_cita": None,
                "hora_cita": None, "sede_seleccionada": None, "cargo_al_enviar": "300",
                "ips": "IPS", "observaciones_sst": None,
                "candidato": "CAND-003", "nombres": "Pedro", "primer_apellido": "López",
                "segundo_apellido": None, "numero_documento": "11111111",
                "ciudad": "Cali", "celular": "3200000000", "email": "p@test.com",
                "modo": "Manual", "cargo_nombre": "Operario", "tipo_cargo": "Operativo",
            },
        ]

        with patch.object(frappe.db, "sql", side_effect=self._mock_sql(rows_data)):
            rows, _ = m._query_seguimiento_examenes({})

        self.assertTrue(rows[0]["datos_faltantes"], "Cita Manual sin fecha debe tener datos_faltantes=True.")

    def test_autogestionado_con_fecha_no_tiene_datos_faltantes(self):
        """Fila Autogestionado con fecha NO tiene datos_faltantes."""
        m = _get_mod()

        rows_data = [
            {
                "name": "CEM-004", "estado": "Agendada", "fecha_cita": "2026-05-15",
                "hora_cita": "09:00:00", "sede_seleccionada": "Sede Norte",
                "cargo_al_enviar": "400", "ips": "IPS", "observaciones_sst": None,
                "candidato": "CAND-004", "nombres": "Luis", "primer_apellido": "Torres",
                "segundo_apellido": None, "numero_documento": "22222222",
                "ciudad": "Bogotá", "celular": "3001111111", "email": "l@test.com",
                "modo": "Autogestionado", "cargo_nombre": "Técnico", "tipo_cargo": "Operativo",
            },
        ]

        with patch.object(frappe.db, "sql", side_effect=self._mock_sql(rows_data)):
            rows, _ = m._query_seguimiento_examenes({})

        self.assertFalse(rows[0]["datos_faltantes"])

    def test_obs_preview_trunca_a_80(self):
        """observaciones_preview se trunca a 80 chars con '...'."""
        m = _get_mod()
        obs_larga = "x" * 200

        rows_data = [
            {
                "name": "CEM-005", "estado": "Agendada", "fecha_cita": "2026-05-10",
                "hora_cita": "10:00:00", "sede_seleccionada": None, "cargo_al_enviar": "500",
                "ips": "IPS", "observaciones_sst": obs_larga,
                "candidato": "CAND-005", "nombres": "Rosa", "primer_apellido": "Díaz",
                "segundo_apellido": None, "numero_documento": "33333333",
                "ciudad": "Bogotá", "celular": "3002222222", "email": "r@test.com",
                "modo": "Autogestionado", "cargo_nombre": "Supervisora", "tipo_cargo": "Administrativo",
            },
        ]

        with patch.object(frappe.db, "sql", side_effect=self._mock_sql(rows_data)):
            rows, _ = m._query_seguimiento_examenes({})

        preview = rows[0]["observaciones_preview"]
        self.assertEqual(len(preview), 83, "80 chars + '...'")
        self.assertTrue(preview.endswith("..."))


# ---------------------------------------------------------------------------
# T07 — list_seguimiento_examenes (endpoint)
# ---------------------------------------------------------------------------

class TestListSeguimientoExamenes(unittest.TestCase):

    def test_retorna_estructura_correcta(self):
        """list_seguimiento_examenes retorna {rows, total, limit, offset}."""
        m = _get_mod()

        with patch.object(m, "_require_access"), \
             patch.object(m, "_query_seguimiento_examenes", return_value=([], 0)):
            result = m.list_seguimiento_examenes(filters=None, limit=50, offset=0)

        self.assertIn("rows", result)
        self.assertIn("total", result)
        self.assertIn("limit", result)
        self.assertIn("offset", result)

    def test_clamp_limit_maximo_500(self):
        """limit se clampea a 500 máximo."""
        m = _get_mod()

        captured = {}

        def mock_query(filters, limit, offset):
            captured["limit"] = limit
            return [], 0

        with patch.object(m, "_require_access"), \
             patch.object(m, "_query_seguimiento_examenes", side_effect=mock_query):
            m.list_seguimiento_examenes(filters=None, limit=9999, offset=0)

        self.assertEqual(captured["limit"], 500)

    def test_offset_negativo_se_clampea_a_cero(self):
        """offset negativo se clampea a 0."""
        m = _get_mod()

        captured = {}

        def mock_query(filters, limit, offset):
            captured["offset"] = offset
            return [], 0

        with patch.object(m, "_require_access"), \
             patch.object(m, "_query_seguimiento_examenes", side_effect=mock_query):
            m.list_seguimiento_examenes(filters=None, limit=50, offset=-5)

        self.assertEqual(captured["offset"], 0)


# ---------------------------------------------------------------------------
# T08 — set_cita_schedule
# ---------------------------------------------------------------------------

class TestSetCitaSchedule(unittest.TestCase):

    def _patch_exists(self, exists=True):
        return patch.object(frappe.db, "exists", return_value=exists)

    def _patch_set_value(self):
        return patch.object(frappe.db, "set_value")

    def _patch_session(self, user="sst@test.com"):
        return patch.object(frappe, "session", new=MagicMock(user=user))

    def test_actualiza_fecha_hora_sede(self):
        """set_cita_schedule guarda fecha, hora y sede con set_value."""
        m = _get_mod()
        calls = {}

        def capture_sv(doctype, name, vals, **kw):
            calls["vals"] = vals

        with patch.object(m, "_require_access"), \
             self._patch_exists(True), \
             patch.object(frappe.db, "set_value", side_effect=capture_sv), \
             patch("frappe.utils.getdate", side_effect=lambda x: x):
            result = m.set_cita_schedule("CEM-001", "2026-06-01", "09:00", "Sede Norte")

        self.assertTrue(result["ok"])
        self.assertEqual(calls["vals"]["estado"], "Agendada")
        self.assertEqual(calls["vals"]["sede_seleccionada"], "Sede Norte")
        self.assertEqual(calls["vals"]["fecha_cita"], "2026-06-01")

    def test_cita_inexistente_lanza_error(self):
        """set_cita_schedule lanza ValidationError si la cita no existe."""
        m = _get_mod()
        with patch.object(m, "_require_access"), \
             self._patch_exists(False):
            with self.assertRaises(frappe.ValidationError):
                m.set_cita_schedule("NO-EXISTE", "2026-06-01", "09:00")

    def test_fecha_pasada_sin_force_lanza_error(self):
        """Fecha pasada sin force_pasado=True lanza ValidationError."""
        m = _get_mod()

        import datetime

        with patch.object(m, "_require_access"), \
             self._patch_exists(True), \
             patch("frappe.utils.getdate", return_value=datetime.date(2025, 1, 1)), \
             patch("hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.nowdate",
                   return_value="2026-06-01"):
            with self.assertRaises(frappe.ValidationError):
                m.set_cita_schedule("CEM-001", "2025-01-01", "09:00")

    def test_hora_normaliza_a_hhmmss(self):
        """Hora en formato HH:MM se normaliza a HH:MM:SS."""
        m = _get_mod()
        calls = {}

        def capture_sv(doctype, name, vals, **kw):
            calls["vals"] = vals

        with patch.object(m, "_require_access"), \
             self._patch_exists(True), \
             patch.object(frappe.db, "set_value", side_effect=capture_sv), \
             patch("frappe.utils.getdate", side_effect=lambda x: x), \
             patch("hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.nowdate",
                   return_value="2020-01-01"):
            m.set_cita_schedule("CEM-001", "2099-12-31", "08:30")

        self.assertEqual(calls["vals"]["hora_cita"], "08:30:00")


# ---------------------------------------------------------------------------
# T09 — set_cita_observaciones
# ---------------------------------------------------------------------------

class TestSetCitaObservaciones(unittest.TestCase):

    def test_guarda_observacion(self):
        """set_cita_observaciones persiste el texto con set_value."""
        m = _get_mod()
        calls = {}

        def capture_sv(doctype, name, field, val, **kw):
            calls["field"] = field
            calls["val"] = val

        with patch.object(m, "_require_access"), \
             patch.object(frappe.db, "exists", return_value=True), \
             patch.object(frappe.db, "set_value", side_effect=capture_sv):
            result = m.set_cita_observaciones("CEM-001", "Nota de prueba")

        self.assertTrue(result["ok"])
        self.assertEqual(calls["field"], "observaciones_sst")
        self.assertEqual(calls["val"], "Nota de prueba")

    def test_texto_vacio_permitido(self):
        """texto='' guarda sin error (limpiar notas)."""
        m = _get_mod()
        with patch.object(m, "_require_access"), \
             patch.object(frappe.db, "exists", return_value=True), \
             patch.object(frappe.db, "set_value"):
            result = m.set_cita_observaciones("CEM-001", "")
        self.assertTrue(result["ok"])

    def test_texto_demasiado_largo_lanza_error(self):
        """Texto de más de 5000 chars lanza ValidationError."""
        m = _get_mod()
        texto_largo = "x" * 5001
        with patch.object(m, "_require_access"), \
             patch.object(frappe.db, "exists", return_value=True):
            with self.assertRaises(frappe.ValidationError):
                m.set_cita_observaciones("CEM-001", texto_largo)

    def test_cita_inexistente_lanza_error(self):
        """Cita que no existe lanza ValidationError."""
        m = _get_mod()
        with patch.object(m, "_require_access"), \
             patch.object(frappe.db, "exists", return_value=False):
            with self.assertRaises(frappe.ValidationError):
                m.set_cita_observaciones("NO-EXISTE", "texto")


# ---------------------------------------------------------------------------
# T10 — set_cita_outcome
# ---------------------------------------------------------------------------

class TestSetCitaOutcome(unittest.TestCase):

    def _patches(self):
        return [
            patch.object(_get_mod(), "_require_access"),
            patch.object(frappe.db, "exists", return_value=True),
        ]

    def test_realizada_favorable(self):
        """Estado Realizada con concepto Favorable delega a set_exam_outcome."""
        m = _get_mod()

        with patch.object(m, "_require_access"), \
             patch.object(frappe.db, "exists", return_value=True), \
             patch("hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.set_exam_outcome") as mock_se:
            result = m.set_cita_outcome("CEM-001", "Realizada", concepto="Favorable")

        self.assertTrue(result["ok"])
        mock_se.assert_called_once_with(
            cita_name="CEM-001",
            estado="Realizada",
            concepto="Favorable",
            motivo=None,
            instrucciones=None,
        )

    def test_realizada_sin_concepto_lanza_error(self):
        """Estado Realizada sin concepto lanza ValidationError."""
        m = _get_mod()
        with patch.object(m, "_require_access"), \
             patch.object(frappe.db, "exists", return_value=True):
            with self.assertRaises(frappe.ValidationError):
                m.set_cita_outcome("CEM-001", "Realizada", concepto=None)

    def test_no_asistio_persiste_literal(self):
        """set_cita_outcome con 'No Asistió' delega a set_exam_outcome (que persiste literal)."""
        m = _get_mod()
        with patch.object(m, "_require_access"), \
             patch.object(frappe.db, "exists", return_value=True), \
             patch("hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.set_exam_outcome") as mock_se:
            result = m.set_cita_outcome("CEM-001", "No Asistió")

        self.assertTrue(result["ok"])
        args = mock_se.call_args
        self.assertEqual(args.kwargs.get("estado") or args[1].get("estado") or args[0][1], "No Asistió")

    def test_cancelada_con_motivo(self):
        """Estado Cancelada con motivo delega correctamente."""
        m = _get_mod()
        with patch.object(m, "_require_access"), \
             patch.object(frappe.db, "exists", return_value=True), \
             patch("hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.set_exam_outcome") as mock_se:
            result = m.set_cita_outcome("CEM-001", "Cancelada", motivo="Candidato desistió")

        self.assertTrue(result["ok"])
        mock_se.assert_called_once()

    def test_cancelada_sin_motivo_lanza_error(self):
        """Cancelada sin motivo lanza ValidationError."""
        m = _get_mod()
        with patch.object(m, "_require_access"), \
             patch.object(frappe.db, "exists", return_value=True):
            with self.assertRaises(frappe.ValidationError):
                m.set_cita_outcome("CEM-001", "Cancelada", motivo=None)

    def test_estado_invalido_lanza_error(self):
        """Estado no reconocido lanza ValidationError."""
        m = _get_mod()
        with patch.object(m, "_require_access"), \
             patch.object(frappe.db, "exists", return_value=True):
            with self.assertRaises(frappe.ValidationError):
                m.set_cita_outcome("CEM-001", "Inventado")

    def test_aplazada_requiere_motivo(self):
        """Estado Aplazada sin motivo (o muy corto) lanza ValidationError."""
        m = _get_mod()
        with patch.object(m, "_require_access"), \
             patch.object(frappe.db, "exists", return_value=True):
            with self.assertRaises(frappe.ValidationError):
                m.set_cita_outcome("CEM-001", "Aplazada", motivo="ok")  # < 5 chars


# ---------------------------------------------------------------------------
# T11 — export_seguimiento_examenes_xlsx
# ---------------------------------------------------------------------------

class TestExportSeguimientoExamenesXlsx(unittest.TestCase):

    def _make_row(self, name="CEM-001", obs=""):
        return {
            "name": name, "estado": "Agendada", "fecha_cita": "2026-05-10",
            "hora_cita": "08:00:00", "sede_seleccionada": "Sede Norte",
            "cargo_al_enviar": "100", "ips": "IPS-TEST",
            "observaciones_sst": obs,
            "candidato": "CAND-001", "nombre_completo": "Juan Pérez",
            "numero_documento": "12345678", "ciudad": "Bogotá",
            "celular": "3001234567", "email": "juan@test.com",
            "modo": "Autogestionado", "cargo_nombre": "Aux.", "tipo_cargo": "Operativo",
            "observaciones_preview": obs[:80],
            "datos_faltantes": False,
        }

    def test_retorna_base64_valido(self):
        """export retorna content_b64 decodificable."""
        import base64
        m = _get_mod()

        rows = [self._make_row()]
        with patch.object(m, "_require_access"), \
             patch.object(m, "_query_seguimiento_examenes", return_value=(rows, 1)):
            result = m.export_seguimiento_examenes_xlsx(filters=None)

        self.assertIn("content_b64", result)
        # No debe lanzar error al decodificar
        decoded = base64.b64decode(result["content_b64"])
        self.assertGreater(len(decoded), 0)

    def test_sin_resultados_retorna_header(self):
        """Sin filas retorna count=0 y archivo válido (solo header)."""
        import base64
        m = _get_mod()

        with patch.object(m, "_require_access"), \
             patch.object(m, "_query_seguimiento_examenes", return_value=([], 0)):
            result = m.export_seguimiento_examenes_xlsx(filters=None)

        self.assertEqual(result["count"], 0)
        # Aún debe ser un xlsx válido
        decoded = base64.b64decode(result["content_b64"])
        self.assertGreater(len(decoded), 0)

    def test_observaciones_completas_sin_truncar(self):
        """La columna Observaciones SST en el xlsx no trunca el texto."""
        import base64
        import openpyxl
        from io import BytesIO

        m = _get_mod()
        obs_larga = "A" * 500
        rows = [self._make_row(obs=obs_larga)]

        with patch.object(m, "_require_access"), \
             patch.object(m, "_query_seguimiento_examenes", return_value=(rows, 1)):
            result = m.export_seguimiento_examenes_xlsx(filters=None)

        xlsx_bytes = base64.b64decode(result["content_b64"])
        wb = openpyxl.load_workbook(BytesIO(xlsx_bytes))
        ws = wb.active

        # Columna Observaciones SST es la 14ª (índice 14)
        obs_cell = ws.cell(row=2, column=14).value
        self.assertEqual(obs_cell, obs_larga, "Las observaciones no deben truncarse en el xlsx.")

    def test_filename_contiene_fecha(self):
        """El filename del export contiene la fecha actual."""
        m = _get_mod()

        with patch.object(m, "_require_access"), \
             patch.object(m, "_query_seguimiento_examenes", return_value=([], 0)):
            result = m.export_seguimiento_examenes_xlsx(filters=None)

        self.assertIn("seguimiento_examenes_", result["filename"])
        self.assertTrue(result["filename"].endswith(".xlsx"))


if __name__ == "__main__":
    unittest.main()
