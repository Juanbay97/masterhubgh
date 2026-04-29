# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt
"""
Phase 2 TDD Tests — disciplinary_workflow_service.py

Tasks covered (test-first):
  T014 — render_document() and _save_as_private_file() with mocks
  T016 — open_case() creates Caso + Afectados
  T018 — Citacion Disciplinaria DocType schema + validations
  T020 — triage_programar_descargos() generates Citaciones
  T022 — triage_cerrar_recordatorio() and triage_cerrar_llamado_directo()
  T024 — sync_case_state_from_afectados() state-minimum rule
  T026 — marcar_citacion_entregada() transitions to Citado
"""

from __future__ import annotations

import types
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase


# =============================================================================
# T014 — render_document() — unit tests with mocked docxtpl
# =============================================================================


class TestRenderDocument(FrappeTestCase):
    """T014 — render_document() returns (filename, bytes) for each supported tipo."""

    def _make_context(self) -> dict:
        return {
            "ciudad_emision": "Bogotá D.C.",
            "fecha_citacion": "23 de abril de 2026",
            "fecha_iso": "2026-04-23",
            "empleado": {
                "nombre": "JUAN PEREZ",
                "cedula": "1001234567",
                "cargo": "Auxiliar de Cocina",
                "pdv": "Home Burgers Chapinero",
                "direccion_residencia": "Cra 15 #45-67",
            },
            "empresa": {
                "razon_social": "COMIDAS VARPEL S.A.S.",
                "nit": "900.123.456-7",
            },
            "fecha_programada_descargos": "5 de mayo de 2026",
            "hora_descargos": "10:00 AM",
            "lugar": "Oficina Administrativa Bogotá",
            "articulos": [{"numero": 42, "literales": "3, 4", "texto": "..."}],
            "hechos_narrados": "El día X el trabajador...",
            "firmante": {
                "nombre": "MÓNICA NUDELMAN",
                "cargo": "COORDINADORA AP",
            },
        }

    def _mock_docxtpl_render(self, tipo: str) -> tuple[str, bytes]:
        """Call render_document with fully mocked DocxTemplate and file system."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        fake_bytes = b"PK\x03\x04fake-docx-content"
        mock_tpl = MagicMock()

        def mock_save(buf):
            buf.write(fake_bytes)

        mock_tpl.save.side_effect = mock_save

        with patch("hubgh.hubgh.disciplinary_workflow_service.DocxTemplate", return_value=mock_tpl) as mock_cls, \
             patch("hubgh.hubgh.disciplinary_workflow_service.TEMPLATE_DIR") as mock_dir:
            # Simulate template file exists (Path object behavior)
            mock_template_path = MagicMock()
            mock_template_path.__str__ = MagicMock(return_value=f"/fake/path/{tipo}.docx")
            mock_dir.__truediv__ = MagicMock(return_value=mock_template_path)

            ctx = self._make_context()
            filename, content = svc.render_document(tipo, ctx)
        return filename, content

    def test_render_document_returns_tuple(self):
        """render_document should return (filename: str, content: bytes)."""
        filename, content = self._mock_docxtpl_render("citacion")
        self.assertIsInstance(filename, str)
        self.assertIsInstance(content, bytes)

    def test_render_document_filename_contains_cedula(self):
        """filename should contain employee cedula."""
        filename, _ = self._mock_docxtpl_render("citacion")
        self.assertIn("1001234567", filename)

    def test_render_document_filename_contains_tipo(self):
        """filename should contain document tipo."""
        filename, _ = self._mock_docxtpl_render("citacion")
        self.assertIn("citacion", filename)

    def test_render_document_returns_nonempty_bytes(self):
        """render_document should return non-empty bytes."""
        _, content = self._mock_docxtpl_render("citacion")
        self.assertGreater(len(content), 0)

    def test_render_document_all_tipos_accepted(self):
        """All 6 tipos should be accepted without ValueError."""
        tipos = [
            "citacion",
            "diligencia_descargos",
            "acta_cierre_sancion",
            "terminacion_justa_causa",
            "acta_cierre_llamado",
            "recordatorio_funciones",
        ]
        for tipo in tipos:
            with self.subTest(tipo=tipo):
                filename, content = self._mock_docxtpl_render(tipo)
                self.assertIsInstance(filename, str)
                self.assertIsInstance(content, bytes)

    def test_render_document_unknown_tipo_raises_value_error(self):
        """Unknown tipo should raise ValueError."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        with self.assertRaises(ValueError):
            svc.render_document("tipo_inexistente", {})

    def test_render_document_template_not_found_raises_frappe_error(self):
        """If template file does not exist, should raise frappe.ValidationError."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        with patch("hubgh.hubgh.disciplinary_workflow_service.DocxTemplate") as mock_cls:
            mock_cls.side_effect = FileNotFoundError("template not found")

            with self.assertRaises(frappe.ValidationError):
                svc.render_document("citacion", self._make_context())

    def test_save_as_private_file_calls_frappe_get_doc(self):
        """_save_as_private_file should create a File doc and return file_url."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        mock_file_doc = MagicMock()
        mock_file_doc.file_url = "/private/files/test.docx"
        mock_file_doc.insert.return_value = mock_file_doc

        with patch("frappe.get_doc", return_value=mock_file_doc):
            result = svc._save_as_private_file(
                filename="test.docx",
                content=b"fakecontent",
                attached_to_doctype="Caso Disciplinario",
                attached_to_name="CD-2026-00001",
            )

        self.assertEqual(result, "/private/files/test.docx")
        mock_file_doc.insert.assert_called_once()


# =============================================================================
# T016 — open_case() — unit tests
# =============================================================================


class TestOpenCase(FrappeTestCase):
    """T016 — open_case() creates a Caso Disciplinario and one or more Afectados."""

    def _make_payload(self, **overrides) -> dict:
        base = {
            "origen": "Apertura RRLL",
            "solicitante": None,
            "fecha_incidente": "2026-04-23",
            "tipo_falta": "Grave",
            "descripcion": "Descripción del hecho.",
            "hechos_detallados": "Hechos detallados del incidente.",
            "ciudad_emision": "Bogotá D.C.",
            "empresa": "COMIDAS VARPEL S.A.S.",
            "afectados": [{"empleado": "EMP-TEST-001"}],
            "articulos_rit": [{"articulo": 42, "literales_aplicables": "3, 4"}],
        }
        base.update(overrides)
        return base

    def test_open_case_requires_at_least_one_afectado(self):
        """open_case should raise ValidationError if afectados list is empty."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        with self.assertRaises(frappe.ValidationError):
            with patch("frappe.get_doc") as mock_gd, \
                 patch("frappe.db.exists", return_value=False):
                svc.open_case(self._make_payload(afectados=[]))

    def test_open_case_requires_hechos_detallados(self):
        """open_case should raise ValidationError if hechos_detallados is empty."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        with self.assertRaises(frappe.ValidationError):
            svc.open_case(self._make_payload(hechos_detallados=""))

    def test_open_case_requires_solicitante_when_origen_jefe_pdv(self):
        """open_case should raise ValidationError if origen=Solicitud Jefe PDV and no solicitante."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        with self.assertRaises(frappe.ValidationError):
            svc.open_case(
                self._make_payload(origen="Solicitud Jefe PDV", solicitante=None)
            )

    def test_open_case_creates_caso_doc(self):
        """open_case should call frappe.get_doc to create a Caso Disciplinario."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        mock_caso = MagicMock()
        mock_caso.name = "CD-2026-00001"
        mock_caso.insert.return_value = mock_caso
        mock_caso.transition_log = []
        mock_caso.append = MagicMock()
        mock_caso.save = MagicMock()

        mock_afectado = MagicMock()
        mock_afectado.name = "AFE-2026-00001"
        mock_afectado.insert.return_value = mock_afectado
        mock_afectado.transition_log = []
        mock_afectado.append = MagicMock()
        mock_afectado.save = MagicMock()

        call_count = [0]

        def fake_get_doc(data_or_doctype, name=None):
            call_count[0] += 1
            if isinstance(data_or_doctype, dict):
                if data_or_doctype.get("doctype") == "Caso Disciplinario":
                    return mock_caso
                return mock_afectado
            # Called as get_doc("Caso Disciplinario", "CD-...") by _append_transition_log
            return mock_caso if "CD" in (name or "") else mock_afectado

        with patch("frappe.get_doc", side_effect=fake_get_doc):
            result = svc.open_case(self._make_payload())

        # Should return the caso name
        self.assertEqual(result, "CD-2026-00001")
        # Should have called get_doc at least for caso + 1 afectado
        self.assertGreaterEqual(call_count[0], 2)

    def test_open_case_sets_estado_en_triage_for_rrll(self):
        """open_case with origen=Apertura RRLL should set estado=En Triage."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        created_docs = []

        mock_caso = MagicMock()
        mock_caso.name = "CD-2026-00001"
        mock_caso.insert.return_value = mock_caso
        mock_caso.transition_log = []
        mock_caso.append = MagicMock()
        mock_caso.save = MagicMock()

        mock_afectado = MagicMock()
        mock_afectado.name = "AFE-2026-00001"
        mock_afectado.insert.return_value = mock_afectado
        mock_afectado.transition_log = []
        mock_afectado.append = MagicMock()
        mock_afectado.save = MagicMock()

        def fake_get_doc(data_or_doctype, name=None):
            if isinstance(data_or_doctype, dict):
                created_docs.append(data_or_doctype)
                if data_or_doctype.get("doctype") == "Caso Disciplinario":
                    return mock_caso
                return mock_afectado
            return mock_caso if "CD" in (name or "") else mock_afectado

        with patch("frappe.get_doc", side_effect=fake_get_doc):
            svc.open_case(self._make_payload(origen="Apertura RRLL"))

        caso_data = next(
            (d for d in created_docs if d.get("doctype") == "Caso Disciplinario"), None
        )
        self.assertIsNotNone(caso_data)
        self.assertEqual(caso_data.get("estado"), "En Triage")

    def test_open_case_sets_estado_solicitado_for_jefe_pdv(self):
        """open_case with origen=Solicitud Jefe PDV should set estado=Solicitado."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        created_docs = []

        mock_caso = MagicMock()
        mock_caso.name = "CD-2026-00001"
        mock_caso.insert.return_value = mock_caso
        mock_caso.transition_log = []
        mock_caso.append = MagicMock()
        mock_caso.save = MagicMock()

        mock_afectado = MagicMock()
        mock_afectado.name = "AFE-2026-00001"
        mock_afectado.insert.return_value = mock_afectado
        mock_afectado.transition_log = []
        mock_afectado.append = MagicMock()
        mock_afectado.save = MagicMock()

        def fake_get_doc(data_or_doctype, name=None):
            if isinstance(data_or_doctype, dict):
                created_docs.append(data_or_doctype)
                if data_or_doctype.get("doctype") == "Caso Disciplinario":
                    return mock_caso
                return mock_afectado
            return mock_caso if "CD" in (name or "") else mock_afectado

        with patch("frappe.get_doc", side_effect=fake_get_doc):
            svc.open_case(
                self._make_payload(
                    origen="Solicitud Jefe PDV", solicitante="jefe@homeburgers.com"
                )
            )

        caso_data = next(
            (d for d in created_docs if d.get("doctype") == "Caso Disciplinario"), None
        )
        self.assertIsNotNone(caso_data)
        self.assertEqual(caso_data.get("estado"), "Solicitado")


# =============================================================================
# T018 — Citacion Disciplinaria DocType schema
# =============================================================================


class TestCitacionDisciplinariaDocType(FrappeTestCase):
    """T018 — DocType Citacion Disciplinaria schema tests."""

    def test_citacion_disciplinaria_doctype_exists(self):
        """El DocType Citacion Disciplinaria debe existir."""
        meta = frappe.get_meta("Citacion Disciplinaria")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.name, "Citacion Disciplinaria")

    def test_citacion_disciplinaria_naming_series(self):
        """El autoname debe contener 'CIT-'."""
        meta = frappe.get_meta("Citacion Disciplinaria")
        self.assertIn("CIT-", meta.autoname or "")

    def test_citacion_disciplinaria_has_required_fields(self):
        """Debe tener: afectado, numero_ronda, fecha_citacion, fecha_programada_descargos, hora_descargos, lugar, articulos_rit, hechos_narrados, estado."""
        meta = frappe.get_meta("Citacion Disciplinaria")
        fieldnames = {f.fieldname for f in meta.fields}
        required = {
            "afectado",
            "numero_ronda",
            "fecha_citacion",
            "fecha_programada_descargos",
            "hora_descargos",
            "lugar",
            "articulos_rit",
            "hechos_narrados",
            "estado",
        }
        self.assertTrue(
            required.issubset(fieldnames),
            f"Faltan campos en Citacion Disciplinaria: {required - fieldnames}",
        )

    def test_citacion_disciplinaria_afectado_links_to_afectado_disciplinario(self):
        """afectado debe ser Link a Afectado Disciplinario."""
        meta = frappe.get_meta("Citacion Disciplinaria")
        field = next((f for f in meta.fields if f.fieldname == "afectado"), None)
        self.assertIsNotNone(field)
        self.assertEqual(field.fieldtype, "Link")
        self.assertEqual(field.options, "Afectado Disciplinario")
        self.assertEqual(int(field.reqd or 0), 1)

    def test_citacion_disciplinaria_articulos_rit_is_table(self):
        """articulos_rit debe ser Table de Articulo RIT Caso."""
        meta = frappe.get_meta("Citacion Disciplinaria")
        field = next((f for f in meta.fields if f.fieldname == "articulos_rit"), None)
        self.assertIsNotNone(field)
        self.assertEqual(field.fieldtype, "Table")
        self.assertEqual(field.options, "Articulo RIT Caso")

    def test_citacion_disciplinaria_estado_options(self):
        """estado debe incluir: Borrador, Emitida, Entregada, Respondida, Sin Respuesta, Anulada."""
        meta = frappe.get_meta("Citacion Disciplinaria")
        field = next((f for f in meta.fields if f.fieldname == "estado"), None)
        self.assertIsNotNone(field)
        opciones = set((field.options or "").split("\n"))
        expected = {"Borrador", "Emitida", "Entregada", "Respondida", "Sin Respuesta", "Anulada"}
        self.assertTrue(
            expected.issubset(opciones),
            f"Faltan estados en Citacion Disciplinaria: {expected - opciones}",
        )

    def test_citacion_disciplinaria_estado_default_borrador(self):
        """El default del estado debe ser 'Borrador'."""
        meta = frappe.get_meta("Citacion Disciplinaria")
        field = next((f for f in meta.fields if f.fieldname == "estado"), None)
        self.assertIsNotNone(field)
        self.assertEqual((field.default or "").strip(), "Borrador")

    def test_citacion_disciplinaria_numero_ronda_default_1(self):
        """numero_ronda debe tener default=1."""
        meta = frappe.get_meta("Citacion Disciplinaria")
        field = next((f for f in meta.fields if f.fieldname == "numero_ronda"), None)
        self.assertIsNotNone(field)
        self.assertEqual(int(field.default or 0), 1)

    def test_citacion_disciplinaria_validation_min_5_business_days(self):
        """Debe rechazar fecha_programada_descargos < 5 días hábiles desde fecha_citacion."""
        from hubgh.hubgh.doctype.citacion_disciplinaria.citacion_disciplinaria import (
            CitacionDisciplinaria,
        )

        doc = SimpleNamespace(
            name="CIT-TEST-001",
            afectado="AFE-TEST-001",
            numero_ronda=1,
            estado="Borrador",
            fecha_citacion="2026-04-23",
            fecha_programada_descargos="2026-04-25",  # only 2 days — must fail
            hora_descargos="10:00:00",
            lugar="Oficina Bogotá",
            articulos_rit=[SimpleNamespace(articulo=42)],
            hechos_narrados="Los hechos...",
        )

        with self.assertRaises(frappe.ValidationError):
            CitacionDisciplinaria._validate_minimo_5_dias_habiles(doc)

    def test_citacion_disciplinaria_validation_passes_5_business_days(self):
        """Debe pasar si fecha_programada_descargos tiene ≥5 días hábiles."""
        from hubgh.hubgh.doctype.citacion_disciplinaria.citacion_disciplinaria import (
            CitacionDisciplinaria,
        )

        doc = SimpleNamespace(
            name="CIT-TEST-002",
            afectado="AFE-TEST-001",
            numero_ronda=1,
            estado="Borrador",
            fecha_citacion="2026-04-23",  # Thursday
            fecha_programada_descargos="2026-04-30",  # 7 calendar = 5 business
            hora_descargos="10:00:00",
            lugar="Oficina Bogotá",
            articulos_rit=[SimpleNamespace(articulo=42)],
            hechos_narrados="Los hechos...",
        )

        # Should not raise
        CitacionDisciplinaria._validate_minimo_5_dias_habiles(doc)

    def test_citacion_disciplinaria_validation_ronda_unica_activa(self):
        """No puede haber dos citaciones activas de la misma ronda para el mismo afectado."""
        from hubgh.hubgh.doctype.citacion_disciplinaria.citacion_disciplinaria import (
            CitacionDisciplinaria,
        )

        doc = SimpleNamespace(
            name="CIT-NEW-001",
            afectado="AFE-TEST-001",
            numero_ronda=1,
            estado="Borrador",
        )

        with patch("frappe.db.exists", return_value="CIT-EXISTING-001"):
            with self.assertRaises(frappe.ValidationError):
                CitacionDisciplinaria._validate_ronda_unica_activa(doc)


# =============================================================================
# T020 — triage_programar_descargos()
# =============================================================================


class TestTriageProgramarDescargos(FrappeTestCase):
    """T020 — triage_programar_descargos() generates citaciones and advances case state."""

    def test_triage_programar_descargos_requires_at_least_5_business_days(self):
        """Should raise ValidationError if fecha_descargos is < 5 business days from today."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        with patch("frappe.utils.today", return_value="2026-04-23"), \
             patch("frappe.get_doc") as mock_gd, \
             patch("frappe.db.get_all", return_value=[]):
            mock_caso = MagicMock()
            mock_caso.estado = "En Triage"
            mock_gd.return_value = mock_caso

            with self.assertRaises(frappe.ValidationError):
                svc.triage_programar_descargos(
                    caso_name="CD-2026-00001",
                    afectados=["AFE-2026-00001"],
                    fecha_descargos="2026-04-24",  # next day — not 5 business days
                    hora="10:00",
                    articulos_rit=[42],
                )

    def test_triage_programar_descargos_requires_at_least_one_articulo(self):
        """Should raise ValidationError if articulos_rit is empty."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        with patch("frappe.utils.today", return_value="2026-04-23"), \
             patch("frappe.get_doc") as mock_gd:
            mock_caso = MagicMock()
            mock_caso.estado = "En Triage"
            mock_gd.return_value = mock_caso

            with self.assertRaises(frappe.ValidationError):
                svc.triage_programar_descargos(
                    caso_name="CD-2026-00001",
                    afectados=["AFE-2026-00001"],
                    fecha_descargos="2026-05-05",
                    hora="10:00",
                    articulos_rit=[],  # empty — must fail
                )

    def test_triage_programar_descargos_requires_at_least_one_afectado(self):
        """Should raise ValidationError if afectados list is empty."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        with patch("frappe.utils.today", return_value="2026-04-23"), \
             patch("frappe.get_doc") as mock_gd:
            mock_caso = MagicMock()
            mock_caso.estado = "En Triage"
            mock_gd.return_value = mock_caso

            with self.assertRaises(frappe.ValidationError):
                svc.triage_programar_descargos(
                    caso_name="CD-2026-00001",
                    afectados=[],  # empty
                    fecha_descargos="2026-05-05",
                    hora="10:00",
                    articulos_rit=[42],
                )

    def test_triage_programar_descargos_returns_list_of_citacion_names(self):
        """Should return a list with one citacion name per afectado."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        mock_caso = MagicMock()
        mock_caso.name = "CD-2026-00001"
        mock_caso.estado = "En Triage"
        mock_caso.save = MagicMock()

        mock_citacion = MagicMock()
        mock_citacion.name = "CIT-2026-00001"
        mock_citacion.insert = MagicMock(return_value=mock_citacion)
        mock_citacion.save = MagicMock()

        mock_afectado = MagicMock()
        mock_afectado.name = "AFE-2026-00001"
        mock_afectado.caso = "CD-2026-00001"

        call_returns = {
            "CD-2026-00001": mock_caso,
            "AFE-2026-00001": mock_afectado,
        }

        def fake_get_doc(doctype_or_dict, name=None):
            if isinstance(doctype_or_dict, dict):
                if doctype_or_dict.get("doctype") == "Citacion Disciplinaria":
                    return mock_citacion
                return MagicMock()
            # get_doc("DocType", name)
            return call_returns.get(name, MagicMock())

        with patch("frappe.get_doc", side_effect=fake_get_doc), \
             patch("frappe.utils.today", return_value="2026-04-23"), \
             patch("hubgh.hubgh.disciplinary_workflow_service.render_document",
                   return_value=("cit.docx", b"bytes")), \
             patch("hubgh.hubgh.disciplinary_workflow_service._save_as_private_file",
                   return_value="/private/files/cit.docx"):
            result = svc.triage_programar_descargos(
                caso_name="CD-2026-00001",
                afectados=["AFE-2026-00001"],
                fecha_descargos="2026-05-05",
                hora="10:00",
                articulos_rit=[42],
            )

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_triage_programar_descargos_advances_caso_state(self):
        """Should set caso.estado = 'Descargos Programados'."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        mock_caso = MagicMock()
        mock_caso.name = "CD-2026-00001"
        mock_caso.estado = "En Triage"
        mock_caso.save = MagicMock()

        mock_citacion = MagicMock()
        mock_citacion.name = "CIT-2026-00001"
        mock_citacion.insert = MagicMock(return_value=mock_citacion)
        mock_citacion.save = MagicMock()

        mock_afectado = MagicMock()
        mock_afectado.name = "AFE-2026-00001"
        mock_afectado.caso = "CD-2026-00001"

        def fake_get_doc(doctype_or_dict, name=None):
            if isinstance(doctype_or_dict, dict):
                if doctype_or_dict.get("doctype") == "Citacion Disciplinaria":
                    return mock_citacion
                return MagicMock()
            if name == "CD-2026-00001":
                return mock_caso
            return mock_afectado

        with patch("frappe.get_doc", side_effect=fake_get_doc), \
             patch("frappe.utils.today", return_value="2026-04-23"), \
             patch("hubgh.hubgh.disciplinary_workflow_service.render_document",
                   return_value=("cit.docx", b"bytes")), \
             patch("hubgh.hubgh.disciplinary_workflow_service._save_as_private_file",
                   return_value="/private/files/cit.docx"):
            svc.triage_programar_descargos(
                caso_name="CD-2026-00001",
                afectados=["AFE-2026-00001"],
                fecha_descargos="2026-05-05",
                hora="10:00",
                articulos_rit=[42],
            )

        self.assertEqual(mock_caso.estado, "Descargos Programados")
        mock_caso.save.assert_called()


# =============================================================================
# T022 — triage_cerrar_recordatorio() and triage_cerrar_llamado_directo()
# =============================================================================


class TestTriageCerrarDirecto(FrappeTestCase):
    """T022 — triage_cerrar_recordatorio() and triage_cerrar_llamado_directo() unit tests."""

    def _make_mocks(self):
        mock_caso = MagicMock()
        mock_caso.name = "CD-2026-00001"
        mock_caso.estado = "En Triage"
        mock_caso.save = MagicMock()

        mock_afectado = MagicMock()
        mock_afectado.name = "AFE-2026-00001"
        mock_afectado.caso = "CD-2026-00001"
        mock_afectado.empleado = "EMP-TEST-001"
        mock_afectado.estado = "Pendiente Triage"
        mock_afectado.save = MagicMock()

        mock_comunicado = MagicMock()
        mock_comunicado.name = "COM-2026-00001"
        mock_comunicado.insert = MagicMock(return_value=mock_comunicado)

        return mock_caso, mock_afectado, mock_comunicado

    def _run_cerrar(self, fn_name: str):
        from hubgh.hubgh import disciplinary_workflow_service as svc

        mock_caso, mock_afectado, mock_comunicado = self._make_mocks()

        def fake_get_doc(doctype_or_dict, name=None):
            if isinstance(doctype_or_dict, dict):
                if doctype_or_dict.get("doctype") == "Comunicado Sancion":
                    return mock_comunicado
                return MagicMock()
            if name == "CD-2026-00001":
                return mock_caso
            return mock_afectado

        with patch("frappe.get_doc", side_effect=fake_get_doc), \
             patch("frappe.get_all", return_value=[{"name": "AFE-2026-00001", "estado": "Cerrado"}]), \
             patch("hubgh.hubgh.disciplinary_workflow_service.render_document",
                   return_value=("doc.docx", b"bytes")), \
             patch("hubgh.hubgh.disciplinary_workflow_service._save_as_private_file",
                   return_value="/private/files/doc.docx"):
            fn = getattr(svc, fn_name)
            result = fn(
                caso_name="CD-2026-00001",
                afectado_name="AFE-2026-00001",
                fundamentos="Fundamentos del cierre.",
            )
        return result, mock_caso, mock_afectado, mock_comunicado

    def test_triage_cerrar_recordatorio_returns_comunicado_name(self):
        """triage_cerrar_recordatorio should return comunicado name."""
        result, _, _, mock_comunicado = self._run_cerrar("triage_cerrar_recordatorio")
        self.assertIsNotNone(result)

    def test_triage_cerrar_recordatorio_sets_afectado_cerrado(self):
        """triage_cerrar_recordatorio should set afectado.estado = Cerrado."""
        _, _, mock_afectado, _ = self._run_cerrar("triage_cerrar_recordatorio")
        self.assertEqual(mock_afectado.estado, "Cerrado")

    def test_triage_cerrar_recordatorio_sets_decision_recordatorio(self):
        """triage_cerrar_recordatorio should set decision_final_afectado = Recordatorio de Funciones."""
        _, _, mock_afectado, _ = self._run_cerrar("triage_cerrar_recordatorio")
        self.assertEqual(
            mock_afectado.decision_final_afectado, "Recordatorio de Funciones"
        )

    def test_triage_cerrar_llamado_directo_returns_comunicado_name(self):
        """triage_cerrar_llamado_directo should return comunicado name."""
        result, _, _, _ = self._run_cerrar("triage_cerrar_llamado_directo")
        self.assertIsNotNone(result)

    def test_triage_cerrar_llamado_directo_sets_decision(self):
        """triage_cerrar_llamado_directo should set decision_final_afectado = Llamado de Atención Directo."""
        _, _, mock_afectado, _ = self._run_cerrar("triage_cerrar_llamado_directo")
        self.assertEqual(
            mock_afectado.decision_final_afectado, "Llamado de Atención Directo"
        )

    def test_triage_cerrar_recordatorio_creates_comunicado(self):
        """triage_cerrar_recordatorio should create a Comunicado Sancion doc."""
        _, _, _, mock_comunicado = self._run_cerrar("triage_cerrar_recordatorio")
        mock_comunicado.insert.assert_called_once()


# =============================================================================
# T024 — sync_case_state_from_afectados()
# =============================================================================


class TestSyncCaseStateFromAfectados(FrappeTestCase):
    """T024 — sync_case_state_from_afectados() correctly computes caso state from afectados."""

    def _run_sync(self, afectados_states: list[str], expected_caso_state: str):
        from hubgh.hubgh import disciplinary_workflow_service as svc

        mock_caso = MagicMock()
        mock_caso.name = "CD-2026-00001"
        mock_caso.origen = "Apertura RRLL"
        mock_caso.estado = "En Triage"
        mock_caso.save = MagicMock()

        afectados_rows = [{"estado": s} for s in afectados_states]

        with patch("frappe.get_doc", return_value=mock_caso), \
             patch("frappe.get_all", return_value=afectados_rows):
            svc.sync_case_state_from_afectados("CD-2026-00001")

        return mock_caso

    def test_sync_all_cerrado_sets_caso_cerrado(self):
        """All Cerrado → caso = Cerrado."""
        mock_caso = self._run_sync(["Cerrado", "Cerrado"], "Cerrado")
        self.assertEqual(mock_caso.estado, "Cerrado")

    def test_sync_one_en_deliberacion_sets_caso_en_deliberacion(self):
        """At least one En Deliberación and none behind → caso = En Deliberación."""
        mock_caso = self._run_sync(["En Deliberación", "En Deliberación"], "En Deliberación")
        self.assertEqual(mock_caso.estado, "En Deliberación")

    def test_sync_one_behind_citado_stays_citado(self):
        """One En Descargos + one Citado → minimum is Citado → caso = Citado (minimum rule)."""
        mock_caso = self._run_sync(["En Descargos", "Citado"], "Citado")
        self.assertEqual(mock_caso.estado, "Citado")

    def test_sync_all_citado_sets_caso_citado(self):
        """All Citado or Cerrado → caso = Citado."""
        mock_caso = self._run_sync(["Citado", "Citado"], "Citado")
        self.assertEqual(mock_caso.estado, "Citado")

    def test_sync_mixed_deliberacion_and_descargos_sets_en_descargos(self):
        """Mixed En Deliberación and En Descargos → minimum is En Descargos."""
        mock_caso = self._run_sync(["En Deliberación", "En Descargos"], "En Descargos")
        self.assertEqual(mock_caso.estado, "En Descargos")

    def test_sync_saves_caso(self):
        """sync_case_state_from_afectados should call caso.save()."""
        mock_caso = self._run_sync(["Cerrado"], "Cerrado")
        mock_caso.save.assert_called()

    def test_sync_no_afectados_does_not_crash(self):
        """If no afectados, should not raise — caso stays at current state."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        mock_caso = MagicMock()
        mock_caso.name = "CD-2026-00001"
        mock_caso.origen = "Apertura RRLL"
        mock_caso.estado = "En Triage"
        mock_caso.save = MagicMock()

        with patch("frappe.get_doc", return_value=mock_caso), \
             patch("frappe.get_all", return_value=[]):
            # Should not raise
            svc.sync_case_state_from_afectados("CD-2026-00001")


# =============================================================================
# T026 — marcar_citacion_entregada()
# =============================================================================


class TestMarcarCitacionEntregada(FrappeTestCase):
    """T026 — marcar_citacion_entregada() transitions citacion → Entregada, afectado → Citado."""

    def test_marcar_citacion_entregada_sets_citacion_estado_entregada(self):
        """Should set citacion.estado = Entregada."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        mock_cit = MagicMock()
        mock_cit.name = "CIT-2026-00001"
        mock_cit.afectado = "AFE-2026-00001"
        mock_cit.estado = "Emitida"
        mock_cit.save = MagicMock()

        mock_afectado = MagicMock()
        mock_afectado.name = "AFE-2026-00001"
        mock_afectado.caso = "CD-2026-00001"
        mock_afectado.estado = "Pendiente Triage"
        mock_afectado.save = MagicMock()

        mock_caso = MagicMock()
        mock_caso.name = "CD-2026-00001"
        mock_caso.estado = "Descargos Programados"
        mock_caso.origen = "Apertura RRLL"
        mock_caso.save = MagicMock()

        def fake_get_doc(doctype_or_dict, name=None):
            if name == "CIT-2026-00001":
                return mock_cit
            if name == "AFE-2026-00001":
                return mock_afectado
            if name == "CD-2026-00001":
                return mock_caso
            return MagicMock()

        # All citaciones for the afectado's case are Entregadas
        with patch("frappe.get_doc", side_effect=fake_get_doc), \
             patch("frappe.get_all", side_effect=[
                 # citaciones of afectado
                 [{"name": "CIT-2026-00001", "estado": "Entregada"}],
                 # all afectados of case
                 [{"estado": "Citado"}],
             ]):
            svc.marcar_citacion_entregada("CIT-2026-00001", "2026-04-24")

        self.assertEqual(mock_cit.estado, "Entregada")
        mock_cit.save.assert_called()

    def test_marcar_citacion_entregada_only_updates_citacion_not_afectado(self):
        """REQ-03-05 (W-3): marcar_citacion_entregada only records delivery date on the citacion.
        The afectado already transitioned to 'Citado' at emission time (triage_programar_descargos).
        This function must NOT change afectado.estado again."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        mock_cit = MagicMock()
        mock_cit.name = "CIT-2026-00001"
        mock_cit.afectado = "AFE-2026-00001"
        mock_cit.estado = "Emitida"
        mock_cit.save = MagicMock()

        # Afectado already in Citado (set by triage_programar_descargos earlier)
        mock_afectado = MagicMock()
        mock_afectado.name = "AFE-2026-00001"
        mock_afectado.caso = "CD-2026-00001"
        mock_afectado.estado = "Citado"
        mock_afectado.save = MagicMock()

        mock_caso = MagicMock()
        mock_caso.name = "CD-2026-00001"
        mock_caso.estado = "Citado"
        mock_caso.origen = "Apertura RRLL"
        mock_caso.save = MagicMock()

        def fake_get_doc(doctype_or_dict, name=None):
            if name == "CIT-2026-00001":
                return mock_cit
            if name == "AFE-2026-00001":
                return mock_afectado
            if name == "CD-2026-00001":
                return mock_caso
            return MagicMock()

        with patch("frappe.get_doc", side_effect=fake_get_doc):
            svc.marcar_citacion_entregada("CIT-2026-00001", "2026-04-24")

        # Citacion must advance to Entregada
        self.assertEqual(mock_cit.estado, "Entregada")
        mock_cit.save.assert_called()
        # Afectado estado must remain unchanged (not modified by this function)
        self.assertEqual(mock_afectado.estado, "Citado",
                         "marcar_citacion_entregada must not change afectado.estado — that was done at emission")

    def test_marcar_citacion_entregada_does_not_advance_if_some_not_entregadas(self):
        """If not all citaciones are Entregadas, afectado should stay at Pendiente Triage."""
        from hubgh.hubgh import disciplinary_workflow_service as svc

        mock_cit = MagicMock()
        mock_cit.name = "CIT-2026-00001"
        mock_cit.afectado = "AFE-2026-00001"
        mock_cit.estado = "Emitida"
        mock_cit.save = MagicMock()

        mock_afectado = MagicMock()
        mock_afectado.name = "AFE-2026-00001"
        mock_afectado.caso = "CD-2026-00001"
        mock_afectado.estado = "Pendiente Triage"
        mock_afectado.save = MagicMock()

        mock_caso = MagicMock()
        mock_caso.name = "CD-2026-00001"
        mock_caso.estado = "Descargos Programados"
        mock_caso.origen = "Apertura RRLL"
        mock_caso.save = MagicMock()

        def fake_get_doc(doctype_or_dict, name=None):
            if name == "CIT-2026-00001":
                return mock_cit
            if name == "AFE-2026-00001":
                return mock_afectado
            if name == "CD-2026-00001":
                return mock_caso
            return MagicMock()

        with patch("frappe.get_doc", side_effect=fake_get_doc), \
             patch("frappe.get_all", side_effect=[
                 # citaciones — one still Emitida (not delivered)
                 [
                     {"name": "CIT-2026-00001", "estado": "Entregada"},
                     {"name": "CIT-2026-00002", "estado": "Emitida"},
                 ],
             ]):
            svc.marcar_citacion_entregada("CIT-2026-00001", "2026-04-24")

        # afectado should NOT have been moved to Citado
        self.assertNotEqual(mock_afectado.estado, "Citado")


# =============================================================================
# T036 — iniciar_descargos()
# =============================================================================


class TestIniciarDescargos(FrappeTestCase):
	"""T036 — iniciar_descargos() creates Acta Descargos borrador and transitions Afectado."""

	def _make_mocks(self):
		mock_afectado = MagicMock()
		mock_afectado.name = "AFE-2026-00001"
		mock_afectado.caso = "CD-2026-00001"
		mock_afectado.empleado = "EMP-TEST-001"
		mock_afectado.estado = "Citado"
		mock_afectado.save = MagicMock()

		mock_citacion = MagicMock()
		mock_citacion.name = "CIT-2026-00001"
		mock_citacion.afectado = "AFE-2026-00001"
		mock_citacion.numero_ronda = 1
		mock_citacion.estado = "Entregada"

		mock_acta = MagicMock()
		mock_acta.name = "ACT-2026-00001"
		mock_acta.insert = MagicMock(return_value=mock_acta)

		mock_caso = MagicMock()
		mock_caso.name = "CD-2026-00001"
		mock_caso.estado = "Citado"
		mock_caso.save = MagicMock()

		return mock_afectado, mock_citacion, mock_acta, mock_caso

	def test_iniciar_descargos_returns_acta_name(self):
		"""iniciar_descargos should return the name of the new Acta Descargos."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_afectado, mock_citacion, mock_acta, mock_caso = self._make_mocks()

		def fake_get_doc(doctype_or_dict, name=None):
			if isinstance(doctype_or_dict, dict):
				if doctype_or_dict.get("doctype") == "Acta Descargos":
					return mock_acta
				return MagicMock()
			if name == "AFE-2026-00001":
				return mock_afectado
			if name == "CIT-2026-00001":
				return mock_citacion
			if name == "CD-2026-00001":
				return mock_caso
			return MagicMock()

		with patch("frappe.get_doc", side_effect=fake_get_doc), \
			 patch("frappe.get_all", return_value=[{"estado": "En Descargos"}]):
			result = svc.iniciar_descargos("AFE-2026-00001", "CIT-2026-00001")

		self.assertIsNotNone(result)
		self.assertEqual(result, "ACT-2026-00001")

	def test_iniciar_descargos_sets_afectado_en_descargos(self):
		"""iniciar_descargos should transition afectado to En Descargos."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_afectado, mock_citacion, mock_acta, mock_caso = self._make_mocks()

		def fake_get_doc(doctype_or_dict, name=None):
			if isinstance(doctype_or_dict, dict):
				if doctype_or_dict.get("doctype") == "Acta Descargos":
					return mock_acta
				return MagicMock()
			if name == "AFE-2026-00001":
				return mock_afectado
			if name == "CIT-2026-00001":
				return mock_citacion
			if name == "CD-2026-00001":
				return mock_caso
			return MagicMock()

		with patch("frappe.get_doc", side_effect=fake_get_doc), \
			 patch("frappe.get_all", return_value=[{"estado": "En Descargos"}]):
			svc.iniciar_descargos("AFE-2026-00001", "CIT-2026-00001")

		self.assertEqual(mock_afectado.estado, "En Descargos")
		mock_afectado.save.assert_called()

	def test_iniciar_descargos_creates_acta_borrador(self):
		"""iniciar_descargos should create Acta Descargos with a dict that sets afectado and citacion."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_afectado, mock_citacion, mock_acta, mock_caso = self._make_mocks()
		created_docs = []

		def fake_get_doc(doctype_or_dict, name=None):
			if isinstance(doctype_or_dict, dict):
				created_docs.append(doctype_or_dict)
				if doctype_or_dict.get("doctype") == "Acta Descargos":
					return mock_acta
				return MagicMock()
			if name == "AFE-2026-00001":
				return mock_afectado
			if name == "CIT-2026-00001":
				return mock_citacion
			if name == "CD-2026-00001":
				return mock_caso
			return MagicMock()

		with patch("frappe.get_doc", side_effect=fake_get_doc), \
			 patch("frappe.get_all", return_value=[{"estado": "En Descargos"}]):
			svc.iniciar_descargos("AFE-2026-00001", "CIT-2026-00001")

		acta_data = next(
			(d for d in created_docs if d.get("doctype") == "Acta Descargos"), None
		)
		self.assertIsNotNone(acta_data)
		self.assertEqual(acta_data.get("afectado"), "AFE-2026-00001")
		self.assertEqual(acta_data.get("citacion"), "CIT-2026-00001")

	def test_iniciar_descargos_raises_if_afectado_not_citado(self):
		"""iniciar_descargos should raise ValidationError if afectado is not Citado."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_afectado = MagicMock()
		mock_afectado.name = "AFE-2026-00001"
		mock_afectado.caso = "CD-2026-00001"
		mock_afectado.estado = "Pendiente Triage"  # NOT Citado

		mock_citacion = MagicMock()
		mock_citacion.name = "CIT-2026-00001"
		mock_citacion.afectado = "AFE-2026-00001"
		mock_citacion.estado = "Entregada"

		def fake_get_doc(doctype_or_dict, name=None):
			if name == "AFE-2026-00001":
				return mock_afectado
			if name == "CIT-2026-00001":
				return mock_citacion
			return MagicMock()

		with patch("frappe.get_doc", side_effect=fake_get_doc):
			with self.assertRaises(frappe.ValidationError):
				svc.iniciar_descargos("AFE-2026-00001", "CIT-2026-00001")


# =============================================================================
# T030 — guardar_acta_descargos()
# =============================================================================


class TestGuardarActaDescargos(FrappeTestCase):
	"""T030 — guardar_acta_descargos() validates, generates DOCX, transitions afectado."""

	def _make_mocks(self):
		mock_acta = MagicMock()
		mock_acta.name = "ACT-2026-00001"
		mock_acta.afectado = "AFE-2026-00001"
		mock_acta.citacion = "CIT-2026-00001"
		mock_acta.derechos_informados = 1
		mock_acta.firma_empleado = 1
		mock_acta.testigo_1 = None
		mock_acta.testigo_2 = None
		mock_acta.save = MagicMock()

		mock_afectado = MagicMock()
		mock_afectado.name = "AFE-2026-00001"
		mock_afectado.caso = "CD-2026-00001"
		mock_afectado.empleado = "EMP-TEST-001"
		mock_afectado.estado = "En Descargos"
		mock_afectado.save = MagicMock()

		mock_caso = MagicMock()
		mock_caso.name = "CD-2026-00001"
		mock_caso.estado = "En Descargos"
		mock_caso.save = MagicMock()

		return mock_acta, mock_afectado, mock_caso

	def test_guardar_acta_descargos_sets_afectado_en_deliberacion(self):
		"""guardar_acta_descargos should transition afectado to En Deliberación."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_acta, mock_afectado, mock_caso = self._make_mocks()

		def fake_get_doc(doctype_or_dict, name=None):
			if name == "ACT-2026-00001":
				return mock_acta
			if name == "AFE-2026-00001":
				return mock_afectado
			if name == "CD-2026-00001":
				return mock_caso
			return MagicMock()

		datos = {
			"derechos_informados": 1,
			"firma_empleado": 1,
			"hechos_leidos": "Hechos leídos al empleado.",
			"preguntas_respuestas": [{"pregunta": "¿Qué pasó?", "respuesta": "Nada."}],
		}

		with patch("frappe.get_doc", side_effect=fake_get_doc), \
			 patch("frappe.get_all", return_value=[{"estado": "En Deliberación"}]), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today",
				   return_value="2026-04-23"), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.render_document",
				   return_value=("acta.docx", b"bytes")), \
			 patch("hubgh.hubgh.disciplinary_workflow_service._save_as_private_file",
				   return_value="/private/files/acta.docx"):
			svc.guardar_acta_descargos("ACT-2026-00001", datos)

		self.assertEqual(mock_afectado.estado, "En Deliberación")
		mock_afectado.save.assert_called()

	def test_guardar_acta_descargos_raises_if_no_derechos_informados(self):
		"""guardar_acta_descargos should raise if derechos_informados=0."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_acta, mock_afectado, mock_caso = self._make_mocks()
		mock_acta.derechos_informados = 0

		def fake_get_doc(doctype_or_dict, name=None):
			if name == "ACT-2026-00001":
				return mock_acta
			return MagicMock()

		datos = {"derechos_informados": 0, "firma_empleado": 1}

		with patch("frappe.get_doc", side_effect=fake_get_doc):
			with self.assertRaises(frappe.ValidationError):
				svc.guardar_acta_descargos("ACT-2026-00001", datos)

	def test_guardar_acta_descargos_raises_if_no_firma_and_no_testigos(self):
		"""guardar_acta_descargos should raise if firma_empleado=0 and no testigos."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_acta, mock_afectado, mock_caso = self._make_mocks()
		mock_acta.derechos_informados = 1
		mock_acta.firma_empleado = 0
		mock_acta.testigo_1 = None
		mock_acta.testigo_2 = None

		def fake_get_doc(doctype_or_dict, name=None):
			if name == "ACT-2026-00001":
				return mock_acta
			return MagicMock()

		datos = {"derechos_informados": 1, "firma_empleado": 0, "testigo_1": None, "testigo_2": None}

		with patch("frappe.get_doc", side_effect=fake_get_doc):
			with self.assertRaises(frappe.ValidationError):
				svc.guardar_acta_descargos("ACT-2026-00001", datos)

	def test_guardar_acta_descargos_passes_with_testigos_and_no_firma(self):
		"""guardar_acta_descargos should succeed if firma_empleado=0 but 2 testigos provided."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_acta, mock_afectado, mock_caso = self._make_mocks()
		mock_acta.firma_empleado = 0
		mock_acta.testigo_1 = "EMP-TESTIGO-001"
		mock_acta.testigo_2 = "EMP-TESTIGO-002"

		def fake_get_doc(doctype_or_dict, name=None):
			if name == "ACT-2026-00001":
				return mock_acta
			if name == "AFE-2026-00001":
				return mock_afectado
			if name == "CD-2026-00001":
				return mock_caso
			return MagicMock()

		datos = {
			"derechos_informados": 1,
			"firma_empleado": 0,
			"testigo_1": "EMP-TESTIGO-001",
			"testigo_2": "EMP-TESTIGO-002",
			"hechos_leidos": "Hechos.",
			"preguntas_respuestas": [{"pregunta": "P?", "respuesta": "R."}],
		}

		with patch("frappe.get_doc", side_effect=fake_get_doc), \
			 patch("frappe.get_all", return_value=[{"estado": "En Deliberación"}]), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today",
				   return_value="2026-04-23"), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.render_document",
				   return_value=("acta.docx", b"bytes")), \
			 patch("hubgh.hubgh.disciplinary_workflow_service._save_as_private_file",
				   return_value="/private/files/acta.docx"):
			# Should not raise
			svc.guardar_acta_descargos("ACT-2026-00001", datos)

	def test_guardar_acta_descargos_continues_if_no_template(self):
		"""guardar_acta_descargos should continue without DOCX if template missing."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_acta, mock_afectado, mock_caso = self._make_mocks()

		def fake_get_doc(doctype_or_dict, name=None):
			if name == "ACT-2026-00001":
				return mock_acta
			if name == "AFE-2026-00001":
				return mock_afectado
			if name == "CD-2026-00001":
				return mock_caso
			return MagicMock()

		datos = {
			"derechos_informados": 1,
			"firma_empleado": 1,
			"hechos_leidos": "Hechos.",
			"preguntas_respuestas": [{"pregunta": "P?", "respuesta": "R."}],
		}

		with patch("frappe.get_doc", side_effect=fake_get_doc), \
			 patch("frappe.get_all", return_value=[{"estado": "En Deliberación"}]), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today",
				   return_value="2026-04-23"), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.render_document",
				   side_effect=frappe.ValidationError("Plantilla no encontrada")):
			# Should not raise — fallback swallow
			svc.guardar_acta_descargos("ACT-2026-00001", datos)

		# afectado still transitioned
		self.assertEqual(mock_afectado.estado, "En Deliberación")


# =============================================================================
# T034 — cerrar_afectado_con_sancion()
# =============================================================================


class TestCerrarAfectadoConSancion(FrappeTestCase):
	"""T034 — cerrar_afectado_con_sancion() handles all outcomes."""

	def _make_mocks(self):
		mock_afectado = MagicMock()
		mock_afectado.name = "AFE-2026-00001"
		mock_afectado.caso = "CD-2026-00001"
		mock_afectado.empleado = "EMP-TEST-001"
		mock_afectado.estado = "En Deliberación"
		mock_afectado.save = MagicMock()

		mock_caso = MagicMock()
		mock_caso.name = "CD-2026-00001"
		mock_caso.estado = "En Deliberación"
		mock_caso.save = MagicMock()

		mock_comunicado = MagicMock()
		mock_comunicado.name = "COM-2026-00001"
		mock_comunicado.insert = MagicMock(return_value=mock_comunicado)
		mock_comunicado.save = MagicMock()

		return mock_afectado, mock_caso, mock_comunicado

	def _run_cerrar(self, outcome: str, datos: dict):
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_afectado, mock_caso, mock_comunicado = self._make_mocks()

		def fake_get_doc(doctype_or_dict, name=None):
			if isinstance(doctype_or_dict, dict):
				if doctype_or_dict.get("doctype") == "Comunicado Sancion":
					return mock_comunicado
				return MagicMock()
			if name == "AFE-2026-00001":
				return mock_afectado
			if name == "CD-2026-00001":
				return mock_caso
			return MagicMock()

		with patch("frappe.get_doc", side_effect=fake_get_doc), \
			 patch("frappe.get_all", return_value=[{"estado": "Cerrado"}]), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today",
				   return_value="2026-04-23"), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.render_document",
				   return_value=("com.docx", b"bytes")), \
			 patch("hubgh.hubgh.disciplinary_workflow_service._save_as_private_file",
				   return_value="/private/files/com.docx"), \
			 patch("hubgh.hubgh.disciplinary_case_service.sync_disciplinary_case_effects",
				   return_value={"status": "ok"}):
			result = svc.cerrar_afectado_con_sancion("AFE-2026-00001", outcome, datos)

		return result, mock_afectado, mock_caso, mock_comunicado

	def test_cerrar_con_llamado_sets_afectado_cerrado(self):
		"""outcome=Llamado de Atención → afectado.estado=Cerrado."""
		datos = {
			"resumen_cierre": "Se aplica llamado.",
			"fundamentos": "El empleado incurrió en falta.",
			"articulos": [42],
		}
		_, mock_afectado, _, _ = self._run_cerrar("Llamado de Atención", datos)
		self.assertEqual(mock_afectado.estado, "Cerrado")
		self.assertEqual(mock_afectado.decision_final_afectado, "Llamado de Atención")

	def test_cerrar_con_llamado_crea_comunicado(self):
		"""outcome=Llamado de Atención → debe crear Comunicado Sancion."""
		datos = {
			"resumen_cierre": "Se aplica llamado.",
			"fundamentos": "El empleado incurrió en falta.",
			"articulos": [42],
		}
		_, _, _, mock_comunicado = self._run_cerrar("Llamado de Atención", datos)
		mock_comunicado.insert.assert_called_once()

	def test_cerrar_con_suspension_sets_fechas(self):
		"""outcome=Suspensión → debe setear fecha_inicio/fin_suspension en afectado."""
		datos = {
			"resumen_cierre": "Suspensión aplicada.",
			"fundamentos": "Falta grave.",
			"articulos": [42, 45],
			"fecha_inicio_suspension": "2026-05-10",
			"fecha_fin_suspension": "2026-05-12",
		}
		_, mock_afectado, _, _ = self._run_cerrar("Suspensión", datos)
		self.assertEqual(mock_afectado.estado, "Cerrado")
		self.assertEqual(mock_afectado.decision_final_afectado, "Suspensión")
		self.assertEqual(mock_afectado.fecha_inicio_suspension, "2026-05-10")
		self.assertEqual(mock_afectado.fecha_fin_suspension, "2026-05-12")

	def test_cerrar_con_suspension_raises_if_no_fechas(self):
		"""outcome=Suspensión sin fechas → ValidationError."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		datos = {
			"resumen_cierre": "Suspensión aplicada.",
			"fundamentos": "Falta grave.",
			"articulos": [42],
			# No fechas de suspension
		}

		mock_afectado = MagicMock()
		mock_afectado.name = "AFE-2026-00001"
		mock_afectado.caso = "CD-2026-00001"
		mock_afectado.estado = "En Deliberación"

		def fake_get_doc(doctype_or_dict, name=None):
			if name == "AFE-2026-00001":
				return mock_afectado
			return MagicMock()

		# ValidationError raised before any frappe_today() call (during Suspensión date validation)
		with patch("frappe.get_doc", side_effect=fake_get_doc), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today", return_value="2026-04-23"):
			with self.assertRaises(frappe.ValidationError):
				svc.cerrar_afectado_con_sancion("AFE-2026-00001", "Suspensión", datos)

	def test_cerrar_con_archivo_no_crea_comunicado(self):
		"""outcome=Archivo → no debe crear Comunicado Sancion."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_afectado, mock_caso, mock_comunicado = self._make_mocks()
		created_docs = []

		def fake_get_doc(doctype_or_dict, name=None):
			if isinstance(doctype_or_dict, dict):
				created_docs.append(doctype_or_dict)
				if doctype_or_dict.get("doctype") == "Comunicado Sancion":
					return mock_comunicado
				return MagicMock()
			if name == "AFE-2026-00001":
				return mock_afectado
			if name == "CD-2026-00001":
				return mock_caso
			return MagicMock()

		datos = {"resumen_cierre": "Caso archivado."}

		with patch("frappe.get_doc", side_effect=fake_get_doc), \
			 patch("frappe.get_all", return_value=[{"estado": "Cerrado"}]), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today",
				   return_value="2026-04-23"), \
			 patch("hubgh.hubgh.disciplinary_case_service.sync_disciplinary_case_effects",
				   return_value={"status": "ok"}):
			result = svc.cerrar_afectado_con_sancion("AFE-2026-00001", "Archivo", datos)

		comunicado_creates = [d for d in created_docs if d.get("doctype") == "Comunicado Sancion"]
		self.assertEqual(len(comunicado_creates), 0)
		self.assertEqual(result, "")  # empty string for Archivo

	def test_cerrar_con_terminacion_dispara_retirement(self):
		"""outcome=Terminación → debe llamar employee_retirement_service."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		mock_afectado, mock_caso, mock_comunicado = self._make_mocks()

		def fake_get_doc(doctype_or_dict, name=None):
			if isinstance(doctype_or_dict, dict):
				if doctype_or_dict.get("doctype") == "Comunicado Sancion":
					return mock_comunicado
				return MagicMock()
			if name == "AFE-2026-00001":
				return mock_afectado
			if name == "CD-2026-00001":
				return mock_caso
			return MagicMock()

		datos = {
			"resumen_cierre": "Terminación justa causa.",
			"fundamentos": "Falta gravísima.",
			"articulos": [47],
			"fecha_ultimo_dia": "2026-05-10",
		}

		with patch("frappe.get_doc", side_effect=fake_get_doc), \
			 patch("frappe.get_all", return_value=[{"estado": "Cerrado"}]), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.frappe_today",
				   return_value="2026-04-23"), \
			 patch("hubgh.hubgh.disciplinary_workflow_service.render_document",
				   return_value=("term.docx", b"bytes")), \
			 patch("hubgh.hubgh.disciplinary_workflow_service._save_as_private_file",
				   return_value="/private/files/term.docx"), \
			 patch("hubgh.hubgh.disciplinary_case_service.sync_disciplinary_case_effects",
				   return_value={"status": "ok"}) as mock_effects:
			svc.cerrar_afectado_con_sancion("AFE-2026-00001", "Terminación", datos)

		mock_effects.assert_called_once()
		# Check the afectado was closed
		self.assertEqual(mock_afectado.estado, "Cerrado")
		self.assertEqual(mock_afectado.decision_final_afectado, "Terminación")

	def test_cerrar_invalid_outcome_raises(self):
		"""Unknown outcome → ValidationError."""
		from hubgh.hubgh import disciplinary_workflow_service as svc

		# ValidationError is raised before get_doc so no need to mock it
		with self.assertRaises(frappe.ValidationError):
			svc.cerrar_afectado_con_sancion(
				"AFE-2026-00001", "OutcomeInvalido", {"resumen_cierre": "x"}
			)


# =============================================================================
# T038 — disciplinary_case_service extended for Afectado Disciplinario
# =============================================================================


class TestSyncDisciplinaryCaseEffectsWithAfectado(FrappeTestCase):
	"""T038 — sync_disciplinary_case_effects accepts Afectado Disciplinario as source."""

	def test_sync_effects_with_afectado_suspension_calls_sync_suspension(self):
		"""If source is AfectadoDisciplinario with decision=Suspensión, should sync suspension."""
		from hubgh.hubgh import disciplinary_case_service as svc

		mock_afectado = MagicMock()
		mock_afectado.doctype = "Afectado Disciplinario"
		mock_afectado.name = "AFE-2026-00001"
		mock_afectado.empleado = "EMP-TEST-001"
		mock_afectado.estado = "Cerrado"
		mock_afectado.decision_final_afectado = "Suspensión"
		mock_afectado.fecha_inicio_suspension = "2026-05-10"
		mock_afectado.fecha_fin_suspension = "2026-05-12"
		mock_afectado.fecha_cierre_afectado = "2026-05-10"
		mock_afectado.resumen_cierre_afectado = "Suspensión aplicada."

		with patch("hubgh.hubgh.disciplinary_case_service._sync_case_suspension",
				   return_value={"status": "active"}) as mock_sync, \
			 patch("hubgh.hubgh.disciplinary_case_service.reverse_retirement_if_clear"):
			result = svc.sync_disciplinary_case_effects(mock_afectado)

		mock_sync.assert_called_once_with(mock_afectado)

	def test_sync_effects_with_afectado_terminacion_calls_retirement(self):
		"""If source is AfectadoDisciplinario with decision=Terminación, should call retirement."""
		from hubgh.hubgh import disciplinary_case_service as svc

		mock_afectado = MagicMock()
		mock_afectado.doctype = "Afectado Disciplinario"
		mock_afectado.name = "AFE-2026-00001"
		mock_afectado.empleado = "EMP-TEST-001"
		mock_afectado.estado = "Cerrado"
		mock_afectado.decision_final_afectado = "Terminación"
		mock_afectado.fecha_cierre_afectado = "2026-05-10"
		mock_afectado.resumen_cierre_afectado = "Terminación justa causa."

		with patch("hubgh.hubgh.employee_retirement_service.submit_employee_retirement",
				   return_value={"status": "ok"}) as mock_ret, \
			 patch("hubgh.hubgh.disciplinary_case_service._clear_disciplinary_suspension_if_possible",
				   return_value={"status": "noop"}), \
			 patch("hubgh.hubgh.people_ops_lifecycle.reverse_retirement_if_clear"):
			result = svc.sync_disciplinary_case_effects(mock_afectado)

		mock_ret.assert_called_once()
		call_kwargs = mock_ret.call_args[1]
		self.assertEqual(call_kwargs["employee"], "EMP-TEST-001")
		self.assertEqual(call_kwargs["source_doctype"], "Afectado Disciplinario")

	def test_sync_effects_with_caso_legacy_still_works(self):
		"""Legacy path: Caso Disciplinario with empleado field should still work."""
		from hubgh.hubgh import disciplinary_case_service as svc

		mock_caso = MagicMock()
		mock_caso.doctype = "Caso Disciplinario"
		mock_caso.name = "CD-2026-00001"
		mock_caso.empleado = "EMP-TEST-001"
		mock_caso.estado = "Cerrado"
		mock_caso.decision_final = "Suspensión"
		mock_caso.fecha_inicio_suspension = "2026-05-10"
		mock_caso.fecha_fin_suspension = "2026-05-12"
		mock_caso.fecha_cierre = "2026-05-10"
		mock_caso.resumen_cierre = "Suspensión."

		with patch("hubgh.hubgh.disciplinary_case_service._sync_case_suspension",
				   return_value={"status": "active"}) as mock_sync, \
			 patch("hubgh.hubgh.disciplinary_case_service.reverse_retirement_if_clear"):
			result = svc.sync_disciplinary_case_effects(mock_caso)

		mock_sync.assert_called_once_with(mock_caso)

	def test_sync_suspension_with_afectado_reads_fechas_from_afectado(self):
		"""_sync_case_suspension should read fechas from Afectado when source is AfectadoDisciplinario."""
		from hubgh.hubgh import disciplinary_case_service as svc

		mock_afectado = MagicMock()
		mock_afectado.doctype = "Afectado Disciplinario"
		mock_afectado.name = "AFE-2026-00001"
		mock_afectado.empleado = "EMP-TEST-001"
		mock_afectado.fecha_inicio_suspension = "2020-01-01"
		mock_afectado.fecha_fin_suspension = "2020-01-03"

		with patch("frappe.utils.getdate") as mock_getdate, \
			 patch("frappe.utils.nowdate", return_value="2020-01-02"), \
			 patch("frappe.db.get_value", return_value="Activo"), \
			 patch("frappe.db.set_value"):
			from frappe.utils import getdate as real_getdate
			mock_getdate.side_effect = real_getdate
			result = svc._sync_case_suspension(mock_afectado)

		# Should have processed suspension (active during range)
		self.assertIn(result["status"], ("active", "scheduled", "expired"))

	def test_process_closed_disciplinary_cases_includes_afectados(self):
		"""process_closed_disciplinary_cases should also process closed Afectados with Suspensión."""
		from hubgh.hubgh import disciplinary_case_service as svc

		mock_afectado_row = MagicMock()
		mock_afectado_row.name = "AFE-2026-00001"

		mock_afectado_doc = MagicMock()
		mock_afectado_doc.name = "AFE-2026-00001"
		mock_afectado_doc.doctype = "Afectado Disciplinario"
		mock_afectado_doc.empleado = "EMP-TEST-001"
		mock_afectado_doc.estado = "Cerrado"
		mock_afectado_doc.decision_final_afectado = "Suspensión"

		mock_caso_row = MagicMock()
		mock_caso_row.name = "CD-2026-00001"

		mock_caso_doc = MagicMock()
		mock_caso_doc.name = "CD-2026-00001"
		mock_caso_doc.doctype = "Caso Disciplinario"
		mock_caso_doc.empleado = "EMP-TEST-002"
		mock_caso_doc.estado = "Cerrado"
		mock_caso_doc.decision_final = "Suspensión"

		def fake_get_all(doctype, *args, **kwargs):
			if doctype == "Caso Disciplinario":
				return [mock_caso_row]
			if doctype == "Afectado Disciplinario":
				return [mock_afectado_row]
			return []

		def fake_get_doc(doctype, name):
			if name == "AFE-2026-00001":
				return mock_afectado_doc
			if name == "CD-2026-00001":
				return mock_caso_doc
			return MagicMock()

		with patch("frappe.get_all", side_effect=fake_get_all), \
			 patch("frappe.get_doc", side_effect=fake_get_doc), \
			 patch("hubgh.hubgh.disciplinary_case_service.sync_disciplinary_case_effects",
				   return_value={"status": "ok"}) as mock_sync:
			result = svc.process_closed_disciplinary_cases()

		# Should have been called for both caso and afectado
		self.assertGreaterEqual(mock_sync.call_count, 2)
		self.assertEqual(result["status"], "ok")


# =============================================================================
# GROUP CLEANUP — Legacy Frappe Workflow must not exist
# =============================================================================


class TestLegacyWorkflowDeleted(FrappeTestCase):
	"""Post-cleanup: The Frappe Workflow 'HubGH - Caso Disciplinario' must not exist."""

	def test_legacy_frappe_workflow_does_not_exist(self):
		"""frappe.db.exists('Workflow', 'HubGH - Caso Disciplinario') must return None."""
		result = frappe.db.exists("Workflow", "HubGH - Caso Disciplinario")
		self.assertIsNone(result, "Legacy Frappe Workflow must be deleted — it blocks the new state machine")
