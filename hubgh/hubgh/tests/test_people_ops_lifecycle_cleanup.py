"""
T-3.1 — RED tests for people_ops_lifecycle cleanup.

These tests verify that the legacy retirement functions have been REMOVED
from people_ops_lifecycle.py and that the hiring functions still work.

Expected behavior BEFORE cleanup: tests that assert functions are ABSENT will FAIL (RED).
Expected behavior AFTER cleanup: all tests GREEN.
"""
import importlib
import types
from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase


class TestPeopleOpsLifecycleLegacyFunctionsRemoved(FrappeTestCase):
    """Assert that the 9 legacy retirement functions are gone."""

    def _get_module(self):
        import hubgh.hubgh.people_ops_lifecycle as mod
        importlib.reload(mod)
        return mod

    def test_apply_retirement_not_exported(self):
        """apply_retirement MUST NOT exist in people_ops_lifecycle after cleanup."""
        mod = self._get_module()
        self.assertFalse(
            hasattr(mod, "apply_retirement"),
            "apply_retirement should have been removed from people_ops_lifecycle",
        )

    def test_reverse_retirement_if_clear_not_exported(self):
        """reverse_retirement_if_clear MUST NOT exist in people_ops_lifecycle after cleanup."""
        mod = self._get_module()
        self.assertFalse(
            hasattr(mod, "reverse_retirement_if_clear"),
            "reverse_retirement_if_clear should have been removed from people_ops_lifecycle",
        )

    def test_sync_ficha_retirement_metadata_not_exported(self):
        """_sync_ficha_retirement_metadata MUST NOT exist."""
        mod = self._get_module()
        self.assertFalse(
            hasattr(mod, "_sync_ficha_retirement_metadata"),
            "_sync_ficha_retirement_metadata should have been removed",
        )

    def test_deactivate_tarjeta_not_exported(self):
        """_deactivate_tarjeta_empleado_if_exists MUST NOT exist."""
        mod = self._get_module()
        self.assertFalse(
            hasattr(mod, "_deactivate_tarjeta_empleado_if_exists"),
            "_deactivate_tarjeta_empleado_if_exists should have been removed",
        )

    def test_reactivate_tarjeta_not_exported(self):
        """_reactivate_tarjeta_empleado_if_exists MUST NOT exist."""
        mod = self._get_module()
        self.assertFalse(
            hasattr(mod, "_reactivate_tarjeta_empleado_if_exists"),
            "_reactivate_tarjeta_empleado_if_exists should have been removed",
        )

    def test_has_other_active_retirement_sources_not_exported(self):
        """_has_other_active_retirement_sources MUST NOT exist."""
        mod = self._get_module()
        self.assertFalse(
            hasattr(mod, "_has_other_active_retirement_sources"),
            "_has_other_active_retirement_sources should have been removed",
        )

    def test_ensure_payroll_liquidation_case_not_exported(self):
        """_ensure_payroll_liquidation_case MUST NOT exist."""
        mod = self._get_module()
        self.assertFalse(
            hasattr(mod, "_ensure_payroll_liquidation_case"),
            "_ensure_payroll_liquidation_case should have been removed",
        )

    def test_emit_trace_event_not_exported(self):
        """_emit_trace_event MUST NOT exist."""
        mod = self._get_module()
        self.assertFalse(
            hasattr(mod, "_emit_trace_event"),
            "_emit_trace_event should have been removed",
        )

    def test_build_trace_description_not_exported(self):
        """_build_trace_description MUST NOT exist."""
        mod = self._get_module()
        self.assertFalse(
            hasattr(mod, "_build_trace_description"),
            "_build_trace_description should have been removed",
        )

    def test_rrll_retirement_roles_constant_removed(self):
        """RRLL_RETIREMENT_ROLES constant MUST NOT exist after cleanup."""
        mod = self._get_module()
        self.assertFalse(
            hasattr(mod, "RRLL_RETIREMENT_ROLES"),
            "RRLL_RETIREMENT_ROLES constant should have been removed",
        )

    def test_cstr_not_imported_at_module_level(self):
        """cstr should no longer be imported (orphan import after retirement functions removed)."""
        mod = self._get_module()
        import inspect
        src = inspect.getsource(mod)
        self.assertNotIn(
            "from frappe.utils import cstr",
            src,
            "cstr is an orphan import that should be removed with the retirement functions",
        )


class TestPeopleOpsLifecycleHiringFunctionsPreserved(FrappeTestCase):
    """Assert that the 4 hiring/contract functions are still present and callable."""

    def _get_module(self):
        import hubgh.hubgh.people_ops_lifecycle as mod
        importlib.reload(mod)
        return mod

    def test_finalize_hiring_still_exists(self):
        """finalize_hiring MUST still be present."""
        mod = self._get_module()
        self.assertTrue(
            hasattr(mod, "finalize_hiring"),
            "finalize_hiring must not be removed",
        )
        self.assertTrue(callable(mod.finalize_hiring))

    def test_promote_user_to_employee_still_exists(self):
        """_promote_user_to_employee MUST still be present."""
        mod = self._get_module()
        self.assertTrue(
            hasattr(mod, "_promote_user_to_employee"),
            "_promote_user_to_employee must not be removed",
        )

    def test_ensure_employee_document_folder_still_exists(self):
        """_ensure_employee_document_folder MUST still be present."""
        mod = self._get_module()
        self.assertTrue(
            hasattr(mod, "_ensure_employee_document_folder"),
            "_ensure_employee_document_folder must not be removed",
        )

    def test_sync_contract_retirement_still_exists(self):
        """_sync_contract_retirement MUST still be present."""
        mod = self._get_module()
        self.assertTrue(
            hasattr(mod, "_sync_contract_retirement"),
            "_sync_contract_retirement must not be removed",
        )


class TestPeopleOpsLifecycleFinalizeHiringWorks(FrappeTestCase):
    """Smoke test: finalize_hiring still executes its contract."""

    def test_finalize_hiring_throws_on_no_employee(self):
        """finalize_hiring should frappe.throw when employee cannot be resolved."""
        from hubgh.hubgh.people_ops_lifecycle import finalize_hiring

        contract = MagicMock()
        contract.candidato = None
        contract.pdv_destino = None
        # _ensure_employee returns None and contract has no 'empleado' attr
        del contract._ensure_employee
        contract.empleado = None

        with patch("hubgh.hubgh.people_ops_lifecycle.frappe.throw") as mock_throw, \
             patch("hubgh.hubgh.people_ops_lifecycle.ensure_roles_and_profiles"), \
             patch("hubgh.hubgh.people_ops_lifecycle.ensure_contextual_groups"), \
             patch("hubgh.hubgh.people_ops_lifecycle.sync_all_user_groups"):
            mock_throw.side_effect = Exception("thrown")
            with self.assertRaises(Exception):
                finalize_hiring(contract)
            mock_throw.assert_called_once()
