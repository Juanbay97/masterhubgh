# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests for carta_terminacion_generator.py — Batch B.3 (TDD RED → GREEN)

Covers:
  T-B.3a  Causal sin carta automática → returns None
  T-B.3b  Causal justa_causa → genera PDF + setea carta_terminacion field
  T-B.3c  Causal periodo_prueba → genera PDF
  T-B.3d  Plantilla no encontrada → log_error, returns None (no crash)
  T-B.3e  PDF tiene contenido (bytes no vacíos)
"""

from unittest.mock import patch, MagicMock, call
from frappe.tests.utils import FrappeTestCase
import frappe


# ---------------------------------------------------------------------------
# Module under test
# ---------------------------------------------------------------------------

from hubgh.hubgh.services.carta_terminacion_generator import generar_carta


# ---------------------------------------------------------------------------
# Helpers — TC doc mock
# ---------------------------------------------------------------------------

def _make_tc_doc(causal="justa_causa", name="TC-2026-001", empleado="EMP-001"):
    doc = MagicMock()
    doc.name = name
    doc.causal = causal
    doc.empleado = empleado
    doc.fecha_terminacion_efectiva = "2026-06-30"
    doc.justificacion = "Incumplimiento grave de obligaciones contractuales."
    doc.cargo_al_terminar = "Asesor Comercial"
    doc.db_set = MagicMock()
    return doc


def _make_causal(requiere_carta=1, plantilla="carta_terminacion_justa_causa"):
    causal = MagicMock()
    causal.requiere_carta_automatica = requiere_carta
    causal.plantilla_carta_template_name = plantilla
    return causal


def _make_template(response_html="<html><body>Carta</body></html>"):
    tpl = MagicMock()
    tpl.response = response_html
    return tpl


def _make_file_doc(file_url="/files/carta_TC-2026-001.pdf"):
    file_doc = MagicMock()
    file_doc.file_url = file_url
    file_doc.insert = MagicMock(return_value=file_doc)
    return file_doc


# ---------------------------------------------------------------------------
# T-B.3a — causal sin carta automática → None
# ---------------------------------------------------------------------------

class TestCartaNoRequerida(FrappeTestCase):

    def test_causal_sin_carta_returns_none(self):
        """Si causal.requiere_carta_automatica==0, generar_carta retorna None."""
        tc_doc = _make_tc_doc(causal="renuncia")
        causal = _make_causal(requiere_carta=0)

        with patch("hubgh.hubgh.services.carta_terminacion_generator.frappe.get_doc", return_value=causal):
            result = generar_carta(tc_doc)

        self.assertIsNone(result)
        tc_doc.db_set.assert_not_called()


# ---------------------------------------------------------------------------
# T-B.3b — causal justa_causa → genera PDF y setea field
# ---------------------------------------------------------------------------

class TestCartaJustaCausa(FrappeTestCase):

    def test_justa_causa_generates_pdf_and_sets_field(self):
        """justa_causa genera PDF y setea terminacion_doc.carta_terminacion."""
        tc_doc = _make_tc_doc(causal="justa_causa")
        causal = _make_causal(requiere_carta=1, plantilla="carta_terminacion_justa_causa")
        template = _make_template("<html>Carta justa causa {{ empleado }}</html>")
        file_doc = _make_file_doc("/files/carta_TC-2026-001.pdf")

        def _get_doc_side_effect(doctype, name=None):
            if doctype == "Causal Terminacion":
                return causal
            if doctype == "Email Template":
                return template
            if isinstance(doctype, dict) and doctype.get("doctype") == "File":
                return file_doc
            return MagicMock()

        with patch("hubgh.hubgh.services.carta_terminacion_generator.frappe.get_doc", side_effect=_get_doc_side_effect), \
             patch("hubgh.hubgh.services.carta_terminacion_generator.render_template", return_value="<html>Carta</html>"), \
             patch("hubgh.hubgh.services.carta_terminacion_generator.get_pdf", return_value=b"%PDF-1.4 test content"):
            result = generar_carta(tc_doc)

        self.assertEqual(result, "/files/carta_TC-2026-001.pdf")
        tc_doc.db_set.assert_called_once_with("carta_terminacion", "/files/carta_TC-2026-001.pdf")


# ---------------------------------------------------------------------------
# T-B.3c — periodo_prueba → genera PDF
# ---------------------------------------------------------------------------

class TestCartaPeriodoPrueba(FrappeTestCase):

    def test_periodo_prueba_generates_pdf(self):
        """periodo_prueba con carta automática también genera PDF."""
        tc_doc = _make_tc_doc(causal="periodo_prueba")
        causal = _make_causal(requiere_carta=1, plantilla="carta_terminacion_periodo_prueba")
        template = _make_template("<html>Carta periodo prueba {{ empleado }}</html>")
        file_doc = _make_file_doc("/files/carta_TC-2026-001.pdf")

        def _get_doc_side_effect(doctype, name=None):
            if doctype == "Causal Terminacion":
                return causal
            if doctype == "Email Template":
                return template
            if isinstance(doctype, dict) and doctype.get("doctype") == "File":
                return file_doc
            return MagicMock()

        with patch("hubgh.hubgh.services.carta_terminacion_generator.frappe.get_doc", side_effect=_get_doc_side_effect), \
             patch("hubgh.hubgh.services.carta_terminacion_generator.render_template", return_value="<html>Carta PP</html>"), \
             patch("hubgh.hubgh.services.carta_terminacion_generator.get_pdf", return_value=b"%PDF-1.4 pp content"):
            result = generar_carta(tc_doc)

        self.assertIsNotNone(result)
        self.assertIn("/files/", result)


# ---------------------------------------------------------------------------
# T-B.3d — Plantilla no encontrada → log_error, None
# ---------------------------------------------------------------------------

class TestCartaPlantillaNoEncontrada(FrappeTestCase):

    def test_missing_template_logs_error_and_returns_none(self):
        """Si frappe.get_doc(Email Template) lanza DoesNotExistError → log_error, retorna None."""
        tc_doc = _make_tc_doc(causal="justa_causa")
        causal = _make_causal(requiere_carta=1, plantilla="plantilla_inexistente")

        def _get_doc_side_effect(doctype, name=None):
            if doctype == "Causal Terminacion":
                return causal
            if doctype == "Email Template":
                raise frappe.DoesNotExistError(f"Email Template {name} not found")
            return MagicMock()

        with patch("hubgh.hubgh.services.carta_terminacion_generator.frappe.get_doc", side_effect=_get_doc_side_effect), \
             patch("hubgh.hubgh.services.carta_terminacion_generator.frappe.log_error") as mock_log:
            result = generar_carta(tc_doc)

        self.assertIsNone(result)
        mock_log.assert_called_once()


# ---------------------------------------------------------------------------
# T-B.3e — PDF bytes non-empty
# ---------------------------------------------------------------------------

class TestCartaPDFContent(FrappeTestCase):

    def test_pdf_bytes_passed_to_file_doc(self):
        """Los bytes del PDF generados deben pasarse al File DocType (no vacíos)."""
        tc_doc = _make_tc_doc(causal="justa_causa")
        causal = _make_causal(requiere_carta=1, plantilla="carta_terminacion_justa_causa")
        template = _make_template("<html>PDF content</html>")

        captured_file_payload = {}

        def _get_doc_side_effect(doctype, name=None):
            if doctype == "Causal Terminacion":
                return causal
            if doctype == "Email Template":
                return template
            if isinstance(doctype, dict) and doctype.get("doctype") == "File":
                captured_file_payload.update(doctype)
                file_doc = MagicMock()
                file_doc.file_url = "/files/carta.pdf"
                file_doc.insert = MagicMock(return_value=file_doc)
                return file_doc
            return MagicMock()

        pdf_bytes = b"%PDF-1.4 real content here"
        with patch("hubgh.hubgh.services.carta_terminacion_generator.frappe.get_doc", side_effect=_get_doc_side_effect), \
             patch("hubgh.hubgh.services.carta_terminacion_generator.render_template", return_value="<html>PDF</html>"), \
             patch("hubgh.hubgh.services.carta_terminacion_generator.get_pdf", return_value=pdf_bytes):
            generar_carta(tc_doc)

        self.assertIn("content", captured_file_payload)
        self.assertEqual(captured_file_payload["content"], pdf_bytes)
        self.assertTrue(len(captured_file_payload["content"]) > 0)
