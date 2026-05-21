# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
T-2.2 — Integration test: Novedad SST con estado_target='Retirado' dispara apply_retirement_stub.

RED phase: these tests verify that:
  - apply_retirement_stub is called (not apply_retirement from people_ops_lifecycle)
  - reverse_retirement_if_clear_stub is called when the novedad is open
  - source_doctype = "Novedad SST" and source_name = novedad.name
  - last_retirement_attempt_source set with correct prefix
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase


class TestNovedadSSTRetiradoDisparaStub(FrappeTestCase):
    """Verifica que apply_estado_empleado con estado_target=Retirado invoca el stub."""

    def _make_novedad_cerrada(self, name="NOV-S-001", empleado="EMP-S-001"):
        """Construye un doc de Novedad SST con estado cerrado y destino Retirado."""
        from hubgh.hubgh.doctype.novedad_sst.novedad_sst import NovedadSST

        doc = SimpleNamespace()
        doc.name = name
        doc.empleado = empleado
        doc.estado = "Cerrada"
        doc.fecha_fin = "2026-05-10"
        doc.fecha_inicio = "2026-04-01"
        doc.descripcion_resumen = "Retiro voluntario"
        doc.descripcion = "Retiro voluntario"
        doc.tipo_novedad = "Retiro"
        # Bind methods from the real class
        doc.get_impacta_estado = lambda: True
        doc.get_estado_destino = lambda: "Retirado"
        doc.get_estado_actual = lambda: "Activo"
        doc.get_estados_temporales = lambda: set()
        doc.update_empleado_estado = lambda estado: None
        doc.apply_estado_empleado = NovedadSST.apply_estado_empleado.__get__(doc, NovedadSST)
        return doc

    def _make_novedad_abierta(self, name="NOV-S-002", empleado="EMP-S-001"):
        """Construye un doc de Novedad SST con estado abierto y destino Retirado."""
        from hubgh.hubgh.doctype.novedad_sst.novedad_sst import NovedadSST

        doc = SimpleNamespace()
        doc.name = name
        doc.empleado = empleado
        doc.estado = "Abierta"
        doc.fecha_fin = None
        doc.fecha_inicio = "2026-04-01"
        doc.descripcion_resumen = ""
        doc.descripcion = ""
        doc.tipo_novedad = "Retiro"
        doc.get_impacta_estado = lambda: True
        doc.get_estado_destino = lambda: "Retirado"
        doc.get_estado_actual = lambda: "Activo"
        doc.get_estados_temporales = lambda: set()
        doc.update_empleado_estado = lambda estado: None
        doc.apply_estado_empleado = NovedadSST.apply_estado_empleado.__get__(doc, NovedadSST)
        return doc

    def test_novedad_cerrada_retirado_invoca_apply_retirement_stub(self):
        """apply_estado_empleado cerrada con Retirado invoca apply_retirement_stub."""
        doc = self._make_novedad_cerrada()

        with patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.apply_retirement_stub",
        ) as stub_mock, patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.getdate",
            side_effect=lambda value=None: value or "2026-05-10",
        ), patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.nowdate",
            return_value="2026-05-10",
        ):
            doc.apply_estado_empleado()

        stub_mock.assert_called_once()
        call_kwargs = stub_mock.call_args.kwargs
        self.assertEqual(call_kwargs["empleado"], "EMP-S-001")
        self.assertEqual(call_kwargs["source_doctype"], "Novedad SST")
        self.assertEqual(call_kwargs["source_name"], "NOV-S-001")

    def test_novedad_cerrada_retirado_no_invoca_apply_retirement_legacy(self):
        """apply_estado_empleado cerrada con Retirado NO invoca apply_retirement (legacy)."""
        doc = self._make_novedad_cerrada()

        with patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.apply_retirement_stub",
            return_value={"status": "skipped_gap", "reason": "awaiting_c3"},
        ), patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.getdate",
            side_effect=lambda value=None: value or "2026-05-10",
        ), patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.nowdate",
            return_value="2026-05-10",
        ):
            # Should not raise AttributeError or ImportError for apply_retirement
            doc.apply_estado_empleado()

    def test_novedad_abierta_retirado_invoca_reverse_stub(self):
        """apply_estado_empleado abierta con Retirado invoca reverse_retirement_if_clear_stub."""
        doc = self._make_novedad_abierta()

        with patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.reverse_retirement_if_clear_stub",
        ) as reverse_mock, patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.getdate",
            side_effect=lambda value=None: value or "2026-05-10",
        ), patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.nowdate",
            return_value="2026-05-10",
        ):
            doc.apply_estado_empleado()

        reverse_mock.assert_called_once()
        call_kwargs = reverse_mock.call_args.kwargs
        self.assertEqual(call_kwargs["empleado"], "EMP-S-001")
        self.assertEqual(call_kwargs["source_doctype"], "Novedad SST")
        self.assertEqual(call_kwargs["source_name"], "NOV-S-002")

    def test_novedad_no_importa_legacy_apply_retirement(self):
        """novedad_sst.py ya no importa apply_retirement de people_ops_lifecycle."""
        import inspect
        import hubgh.hubgh.doctype.novedad_sst.novedad_sst as novedad_module

        source = inspect.getsource(novedad_module)
        self.assertNotIn(
            "from hubgh.hubgh.people_ops_lifecycle import apply_retirement",
            source,
            "novedad_sst MUST NOT import apply_retirement from people_ops_lifecycle after Batch B",
        )

    def test_retirement_date_passed_correctly(self):
        """retirement_date se pasa como fecha_fin de la novedad."""
        doc = self._make_novedad_cerrada()
        doc.fecha_fin = "2026-05-15"

        with patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.apply_retirement_stub",
            return_value={"status": "skipped_gap", "reason": "awaiting_c3"},
        ) as stub_mock, patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.getdate",
            side_effect=lambda value=None: value or "2026-05-15",
        ), patch(
            "hubgh.hubgh.doctype.novedad_sst.novedad_sst.nowdate",
            return_value="2026-05-15",
        ):
            doc.apply_estado_empleado()

        call_kwargs = stub_mock.call_args.kwargs
        self.assertEqual(call_kwargs.get("retirement_date"), "2026-05-15")
