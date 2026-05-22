# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for evaluar_checklist_validaciones — Batch B.12 (TDD RED → GREEN)

Verifica cada uno de los 9 códigos de validación individualmente.
"""

from unittest.mock import patch, MagicMock
from frappe.tests.utils import FrappeTestCase
import frappe


from hubgh.hubgh.services.terminacion_service import evaluar_checklist_validaciones


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_item(result, codigo):
    return next((i for i in result if i["codigo_validacion"] == codigo), None)


def _base_mocks():
    """Mocks base: sin DocTypes problemáticos, sin novedades activas."""
    return {
        "hubgh.hubgh.services.terminacion_service.frappe.db.exists": MagicMock(return_value=True),
        "hubgh.hubgh.services.terminacion_service.frappe.db.count": MagicMock(return_value=0),
        "hubgh.hubgh.services.terminacion_service.frappe.get_all": MagicMock(return_value=[]),
        "hubgh.hubgh.services.terminacion_service.frappe.db.get_value": MagicMock(return_value=1),
    }


class TestEvaluarChecklistTodosOK(FrappeTestCase):

    def test_all_9_codes_present_when_all_ok(self):
        """Cuando no hay condiciones activas, los 9 códigos deben estar presentes."""
        with patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", return_value=True), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.count", return_value=0), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.get_value", return_value=1):
            result = evaluar_checklist_validaciones("EMP-001")

        codigos = {i["codigo_validacion"] for i in result}
        expected = {
            "incapacidad_abierta", "caso_disciplinario_abierto", "traslado_pendiente",
            "contrato_activo_otro", "dotacion_pendiente", "prestamos_libranzas",
            "clonk_marcas_recientes", "examen_egreso_programado", "bloqueo_acceso",
        }
        self.assertEqual(codigos, expected)


class TestIncapacidadAbierta(FrappeTestCase):

    def test_incapacidad_abierta_bloqueante(self):
        """incapacidad_abierta con count>0 → Bloqueante."""
        def _count(doctype, filters):
            if doctype == "Novedad SST":
                return 1
            return 0

        with patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", return_value=True), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.count", side_effect=_count), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.get_value", return_value=1):
            result = evaluar_checklist_validaciones("EMP-001")

        item = _get_item(result, "incapacidad_abierta")
        self.assertEqual(item["resultado"], "Bloqueante")

    def test_incapacidad_abierta_ok_cuando_none(self):
        """incapacidad_abierta con count=0 → OK."""
        with patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", return_value=True), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.count", return_value=0), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.get_value", return_value=1):
            result = evaluar_checklist_validaciones("EMP-001")

        item = _get_item(result, "incapacidad_abierta")
        self.assertEqual(item["resultado"], "OK")


class TestCasoDisciplinarioAbierto(FrappeTestCase):

    def test_caso_disciplinario_bloqueante(self):
        """caso_disciplinario_abierto con count>0 → Bloqueante."""
        call_count = {"n": 0}
        def _count(doctype, filters):
            if doctype == "Caso Disciplinario":
                return 1
            return 0

        with patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", return_value=True), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.count", side_effect=_count), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.get_value", return_value=1):
            result = evaluar_checklist_validaciones("EMP-001")

        item = _get_item(result, "caso_disciplinario_abierto")
        self.assertEqual(item["resultado"], "Bloqueante")


class TestTrasladoPendiente(FrappeTestCase):

    def test_traslado_pendiente_bloqueante(self):
        """traslado_pendiente con count>0 → Bloqueante."""
        def _count(doctype, filters):
            if doctype == "Traslado PDV":
                return 1
            return 0

        with patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", return_value=True), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.count", side_effect=_count), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.get_value", return_value=1):
            result = evaluar_checklist_validaciones("EMP-001")

        item = _get_item(result, "traslado_pendiente")
        self.assertEqual(item["resultado"], "Bloqueante")


class TestContratoActivoOtro(FrappeTestCase):

    def test_contrato_activo_otro_bloqueante(self):
        """contrato_activo_otro con count>0 → Bloqueante."""
        def _count(doctype, filters):
            if doctype == "Contrato":
                return 1
            return 0

        with patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", return_value=True), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.count", side_effect=_count), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.get_value", return_value=1):
            result = evaluar_checklist_validaciones("EMP-001")

        item = _get_item(result, "contrato_activo_otro")
        self.assertEqual(item["resultado"], "Bloqueante")


class TestNoAplicaWhenDoctypeMissing(FrappeTestCase):

    def test_no_aplica_when_doctype_absent(self):
        """Si un DocType fuente no existe → resultado=No Aplica."""
        def _exists(doctype_or_dt, name=None):
            # Si chequeamos DocType, retornar False para el DocType fuente
            if doctype_or_dt == "DocType":
                return False
            return True

        with patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", side_effect=_exists), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.count", return_value=0), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.get_value", return_value=1):
            result = evaluar_checklist_validaciones("EMP-001")

        # Al menos los bloqueantes basados en DocType deben ser No Aplica
        for codigo in ["incapacidad_abierta", "caso_disciplinario_abierto", "traslado_pendiente"]:
            item = _get_item(result, codigo)
            self.assertEqual(item["resultado"], "No Aplica", f"{codigo} debería ser No Aplica")


class TestBloqueoPorDefecto(FrappeTestCase):

    def test_informativas_son_no_aplica_por_defecto(self):
        """dotacion_pendiente, prestamos_libranzas, clonk_marcas_recientes siempre No Aplica."""
        with patch("hubgh.hubgh.services.terminacion_service.frappe.db.exists", return_value=True), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.count", return_value=0), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.get_all", return_value=[]), \
             patch("hubgh.hubgh.services.terminacion_service.frappe.db.get_value", return_value=1):
            result = evaluar_checklist_validaciones("EMP-001")

        for codigo in ["dotacion_pendiente", "prestamos_libranzas", "clonk_marcas_recientes"]:
            item = _get_item(result, codigo)
            self.assertEqual(item["resultado"], "No Aplica", f"{codigo} debe ser siempre No Aplica")
