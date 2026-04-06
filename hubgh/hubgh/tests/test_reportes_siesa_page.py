import sys
import types
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


_ORIGINAL_MODULES = {name: sys.modules.get(name) for name in ["frappe", "hubgh.hubgh.contratacion_service", "hubgh.hubgh.siesa_export"]}


def _install_stubs():
	frappe_module = types.ModuleType("frappe")
	frappe_module.whitelist = lambda *args, **kwargs: (lambda fn: fn)
	frappe_module.db = SimpleNamespace(get_value=lambda *args, **kwargs: None)
	sys.modules["frappe"] = frappe_module

	contratacion = types.ModuleType("hubgh.hubgh.contratacion_service")
	contratacion.siesa_candidates = lambda *args, **kwargs: []
	contratacion.get_or_create_datos_contratacion = lambda candidate, contract=None: SimpleNamespace(name=f"DC-{candidate}")
	sys.modules["hubgh.hubgh.contratacion_service"] = contratacion

	siesa_export = types.ModuleType("hubgh.hubgh.siesa_export")
	siesa_export.exportar_conector_contratos = lambda *args, **kwargs: None
	siesa_export.exportar_conector_empleados = lambda *args, **kwargs: None
	sys.modules["hubgh.hubgh.siesa_export"] = siesa_export


_install_stubs()

from hubgh.hubgh.page.reportes_siesa import reportes_siesa


def tearDownModule():
	sys.modules.pop("hubgh.hubgh.page.reportes_siesa.reportes_siesa", None)
	for name, original in _ORIGINAL_MODULES.items():
		if original is None:
			sys.modules.pop(name, None)
		else:
			sys.modules[name] = original


class TestReportesSiesaPage(TestCase):
	def test_get_datos_contratacion_for_candidate_creates_missing_record(self):
		with patch(
			"hubgh.hubgh.page.reportes_siesa.reportes_siesa.get_or_create_datos_contratacion",
			return_value=SimpleNamespace(name="DC-666666"),
		) as get_or_create_mock:
			result = reportes_siesa.get_datos_contratacion_for_candidate("666666")

		self.assertEqual(result, "DC-666666")
		get_or_create_mock.assert_called_once_with("666666")
