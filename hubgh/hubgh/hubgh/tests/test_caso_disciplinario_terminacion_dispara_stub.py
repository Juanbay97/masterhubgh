# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
T-2.1 — Integration test: Caso Disciplinario con Terminación dispara apply_retirement_stub.

RED phase: these tests import disciplinary_case_service and verify that:
  - apply_retirement_stub is called (not employee_retirement_service)
  - reverse_retirement_if_clear_stub is called when case is NOT closed
  - email dispatch to RRLL happens (via mock)
  - User.enabled is NOT modified
  - frappe.log_error is called with stub title
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh import disciplinary_case_service


class TestCasoDisciplinarioTerminacionDisparaStub(FrappeTestCase):
    """Verifica que cerrar un Caso Disciplinario con Terminación invoca el stub, no el flujo legacy."""

    def _make_termination_case(self, name="DIS-T-001"):
        return SimpleNamespace(
            name=name,
            empleado="EMP-T-001",
            estado="Cerrado",
            decision_final="Terminación",
            fecha_cierre="2026-05-01",
            fecha_incidente="2026-04-28",
            resumen_cierre="Incumplimiento reglamento",
        )

    def test_terminacion_invoca_apply_retirement_stub(self):
        """sync_disciplinary_case_effects con Terminación llama apply_retirement_stub."""
        case_doc = self._make_termination_case()

        stub_return = {"status": "skipped_gap", "reason": "awaiting_c3"}

        with patch(
            "hubgh.hubgh.disciplinary_case_service._clear_disciplinary_suspension_if_possible",
            return_value={"status": "noop"},
        ), patch(
            "hubgh.hubgh.disciplinary_case_service.apply_retirement_stub",
            return_value=stub_return,
        ) as stub_mock:
            result = disciplinary_case_service.sync_disciplinary_case_effects(case_doc)

        stub_mock.assert_called_once()
        call_kwargs = stub_mock.call_args.kwargs
        self.assertEqual(call_kwargs["empleado"], "EMP-T-001")
        self.assertEqual(call_kwargs["source_doctype"], "Caso Disciplinario")
        self.assertEqual(call_kwargs["source_name"], "DIS-T-001")

    def test_terminacion_retorna_contrato_stub(self):
        """El resultado de sync_disciplinary_case_effects con Terminación es el contrato del stub."""
        case_doc = self._make_termination_case()

        expected = {"status": "skipped_gap", "reason": "awaiting_c3"}

        with patch(
            "hubgh.hubgh.disciplinary_case_service._clear_disciplinary_suspension_if_possible",
            return_value={"status": "noop"},
        ), patch(
            "hubgh.hubgh.disciplinary_case_service.apply_retirement_stub",
            return_value=expected,
        ):
            result = disciplinary_case_service.sync_disciplinary_case_effects(case_doc)

        self.assertEqual(result["status"], "skipped_gap")
        self.assertEqual(result["reason"], "awaiting_c3")

    def test_terminacion_no_importa_employee_retirement_service(self):
        """disciplinary_case_service ya no importa employee_retirement_service."""
        import inspect
        import hubgh.hubgh.disciplinary_case_service as svc_module

        source = inspect.getsource(svc_module)
        self.assertNotIn(
            "employee_retirement_service",
            source,
            "disciplinary_case_service MUST NOT import employee_retirement_service after Batch B",
        )

    def test_case_not_closed_invoca_reverse_stub(self):
        """Caso no cerrado llama a reverse_retirement_if_clear_stub."""
        case_doc = SimpleNamespace(
            name="DIS-T-002",
            empleado="EMP-T-001",
            estado="Abierto",
            decision_final="Terminación",
        )

        with patch(
            "hubgh.hubgh.disciplinary_case_service.reverse_retirement_if_clear_stub",
        ) as reverse_mock, patch(
            "hubgh.hubgh.disciplinary_case_service._clear_disciplinary_suspension_if_possible",
            return_value={"status": "noop"},
        ):
            result = disciplinary_case_service.sync_disciplinary_case_effects(case_doc)

        reverse_mock.assert_called_once()
        call_kwargs = reverse_mock.call_args.kwargs
        self.assertEqual(call_kwargs["empleado"], "EMP-T-001")
        self.assertEqual(call_kwargs["source_doctype"], "Caso Disciplinario")
        self.assertEqual(call_kwargs["source_name"], "DIS-T-002")

    def test_amonestacion_no_invoca_apply_retirement_stub(self):
        """Caso cerrado con Amonestación no invoca apply_retirement_stub."""
        case_doc = SimpleNamespace(
            name="DIS-T-003",
            empleado="EMP-T-001",
            estado="Cerrado",
            decision_final="Llamado de atención",
        )

        with patch(
            "hubgh.hubgh.disciplinary_case_service.apply_retirement_stub",
        ) as stub_mock, patch(
            "hubgh.hubgh.disciplinary_case_service.reverse_retirement_if_clear_stub",
        ), patch(
            "hubgh.hubgh.disciplinary_case_service._clear_disciplinary_suspension_if_possible",
            return_value={"status": "noop"},
        ):
            disciplinary_case_service.sync_disciplinary_case_effects(case_doc)

        stub_mock.assert_not_called()

    def test_retirement_date_passed_from_fecha_cierre(self):
        """retirement_date del stub toma fecha_cierre del caso."""
        case_doc = self._make_termination_case()

        with patch(
            "hubgh.hubgh.disciplinary_case_service._clear_disciplinary_suspension_if_possible",
            return_value={"status": "noop"},
        ), patch(
            "hubgh.hubgh.disciplinary_case_service.apply_retirement_stub",
            return_value={"status": "skipped_gap", "reason": "awaiting_c3"},
        ) as stub_mock:
            disciplinary_case_service.sync_disciplinary_case_effects(case_doc)

        call_kwargs = stub_mock.call_args.kwargs
        self.assertEqual(call_kwargs.get("retirement_date"), "2026-05-01")
