# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import json
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase


class TestRitArticuloFixture(FrappeTestCase):
	"""T003 — Tests del DocType RIT Articulo: validaciones de campos required,
	unicidad del campo numero, campo activo con default 1, y seed fixtures."""

	# -------------------------------------------------------------------------
	# Schema / Meta tests
	# -------------------------------------------------------------------------

	def test_rit_articulo_doctype_exists(self):
		"""El DocType RIT Articulo debe existir en Frappe."""
		meta = frappe.get_meta("RIT Articulo")
		self.assertIsNotNone(meta)
		self.assertEqual(meta.name, "RIT Articulo")

	def test_rit_articulo_has_required_fields(self):
		"""Debe tener los campos: numero, capitulo, literal_clave, texto_completo, activo."""
		meta = frappe.get_meta("RIT Articulo")
		fieldnames = {f.fieldname for f in meta.fields}
		required = {"numero", "capitulo", "literal_clave", "texto_completo", "activo"}
		self.assertTrue(
			required.issubset(fieldnames),
			f"Faltan campos en RIT Articulo: {required - fieldnames}",
		)

	def test_rit_articulo_numero_is_required(self):
		"""El campo numero debe ser obligatorio (reqd=1)."""
		meta = frappe.get_meta("RIT Articulo")
		numero_field = next((f for f in meta.fields if f.fieldname == "numero"), None)
		self.assertIsNotNone(numero_field, "Campo 'numero' no encontrado")
		self.assertEqual(int(numero_field.reqd or 0), 1, "El campo 'numero' debe ser reqd=1")

	def test_rit_articulo_texto_completo_is_required(self):
		"""El campo texto_completo debe ser obligatorio."""
		meta = frappe.get_meta("RIT Articulo")
		field = next((f for f in meta.fields if f.fieldname == "texto_completo"), None)
		self.assertIsNotNone(field, "Campo 'texto_completo' no encontrado")
		self.assertEqual(int(field.reqd or 0), 1, "El campo 'texto_completo' debe ser reqd=1")

	def test_rit_articulo_activo_default_is_1(self):
		"""El campo activo debe tener default=1."""
		meta = frappe.get_meta("RIT Articulo")
		field = next((f for f in meta.fields if f.fieldname == "activo"), None)
		self.assertIsNotNone(field, "Campo 'activo' no encontrado")
		self.assertEqual(str(field.default or "").strip(), "1", "El campo 'activo' debe tener default=1")

	def test_rit_articulo_numero_is_unique(self):
		"""El campo numero debe tener unique=1 en el meta."""
		meta = frappe.get_meta("RIT Articulo")
		field = next((f for f in meta.fields if f.fieldname == "numero"), None)
		self.assertIsNotNone(field, "Campo 'numero' no encontrado")
		self.assertEqual(int(field.unique or 0), 1, "El campo 'numero' debe ser unique=1")

	# -------------------------------------------------------------------------
	# Fixture content tests
	# -------------------------------------------------------------------------

	def test_fixture_file_exists(self):
		"""El archivo fixtures/rit_articulo.json debe existir."""
		base = Path(__file__).resolve().parents[1]
		fixture_path = base / "hubgh" / "fixtures" / "rit_articulo.json"
		self.assertTrue(fixture_path.exists(), f"Fixture no encontrado en {fixture_path}")

	def test_fixture_contains_articulo_42(self):
		"""El fixture debe contener el Artículo 42."""
		base = Path(__file__).resolve().parents[1]
		fixture_path = base / "hubgh" / "fixtures" / "rit_articulo.json"
		if not fixture_path.exists():
			self.skipTest("Fixture no existe aun")
		data = json.loads(fixture_path.read_text(encoding="utf-8"))
		numeros = [int(item.get("numero", 0)) for item in data]
		self.assertIn(42, numeros, "El fixture debe contener el Artículo 42")

	def test_fixture_contains_articulo_45(self):
		"""El fixture debe contener el Artículo 45."""
		base = Path(__file__).resolve().parents[1]
		fixture_path = base / "hubgh" / "fixtures" / "rit_articulo.json"
		if not fixture_path.exists():
			self.skipTest("Fixture no existe aun")
		data = json.loads(fixture_path.read_text(encoding="utf-8"))
		numeros = [int(item.get("numero", 0)) for item in data]
		self.assertIn(45, numeros, "El fixture debe contener el Artículo 45")

	def test_fixture_all_items_have_texto_completo(self):
		"""Todos los artículos del fixture deben tener texto_completo no vacío."""
		base = Path(__file__).resolve().parents[1]
		fixture_path = base / "hubgh" / "fixtures" / "rit_articulo.json"
		if not fixture_path.exists():
			self.skipTest("Fixture no existe aun")
		data = json.loads(fixture_path.read_text(encoding="utf-8"))
		for item in data:
			self.assertTrue(
				bool((item.get("texto_completo") or "").strip()),
				f"El artículo {item.get('numero')} no tiene texto_completo",
			)

	def test_fixture_no_duplicate_numeros(self):
		"""Los numeros de artículo en el fixture deben ser únicos."""
		base = Path(__file__).resolve().parents[1]
		fixture_path = base / "hubgh" / "fixtures" / "rit_articulo.json"
		if not fixture_path.exists():
			self.skipTest("Fixture no existe aun")
		data = json.loads(fixture_path.read_text(encoding="utf-8"))
		numeros = [int(item.get("numero", 0)) for item in data]
		self.assertEqual(len(numeros), len(set(numeros)), "Hay numeros duplicados en el fixture")

	# -------------------------------------------------------------------------
	# Validation tests (via controller)
	# -------------------------------------------------------------------------

	def test_rit_articulo_validation_requires_numero(self):
		"""Debe fallar si numero está vacío."""
		doc = frappe.new_doc("RIT Articulo")
		doc.texto_completo = "Texto de prueba"
		doc.activo = 1
		with self.assertRaises(frappe.exceptions.ValidationError):
			doc.save(ignore_permissions=True)

	def test_rit_articulo_validation_requires_texto_completo(self):
		"""Debe fallar si texto_completo está vacío."""
		doc = frappe.new_doc("RIT Articulo")
		doc.numero = 999
		doc.activo = 1
		with self.assertRaises((frappe.exceptions.ValidationError, frappe.exceptions.MandatoryError)):
			doc.save(ignore_permissions=True)

	def test_rit_articulo_activo_defaults_to_1_on_new(self):
		"""Al crear un nuevo documento, activo debe ser 1 por defecto."""
		doc = frappe.new_doc("RIT Articulo")
		# El default se aplica al crear con new_doc
		self.assertEqual(int(doc.activo or 0), 1)

	def test_rit_articulo_uniqueness_enforced_on_duplicate_numero(self):
		"""Intentar crear dos artículos con el mismo numero debe lanzar error."""
		# Usar numero muy alto para evitar colision con fixtures reales
		test_numero = 9900
		# Limpiar si existe de un test anterior
		if frappe.db.exists("RIT Articulo", {"numero": test_numero}):
			frappe.db.delete("RIT Articulo", {"numero": test_numero})
			frappe.db.commit()

		doc1 = frappe.new_doc("RIT Articulo")
		doc1.numero = test_numero
		doc1.texto_completo = "Texto artículo de prueba unicidad"
		doc1.activo = 1
		doc1.save(ignore_permissions=True)
		frappe.db.commit()

		try:
			doc2 = frappe.new_doc("RIT Articulo")
			doc2.numero = test_numero
			doc2.texto_completo = "Otro texto"
			doc2.activo = 1
			with self.assertRaises(Exception):
				doc2.save(ignore_permissions=True)
		finally:
			# Limpiar
			frappe.db.delete("RIT Articulo", {"numero": test_numero})
			frappe.db.commit()
