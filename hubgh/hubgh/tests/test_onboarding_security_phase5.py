import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.password import check_password

from hubgh.hubgh.onboarding_security import (
	clear_force_password_reset_flag,
	enforce_onboarding_rate_limit,
	enforce_password_reset_on_login,
	mark_user_for_first_login_password_reset,
	should_force_password_reset,
	validate_candidate_duplicates,
	validate_onboarding_captcha,
)
from hubgh.www.candidato import create_candidate, get_procedencia_siesa_catalog


class TestOnboardingSecurityPhase5(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self._created_candidates = []
		self._created_users = []

	def tearDown(self):
		for candidate_name in self._created_candidates:
			if frappe.db.exists("Candidato", candidate_name):
				frappe.delete_doc("Candidato", candidate_name, force=1, ignore_permissions=True)

		for user_name in self._created_users:
			if frappe.db.exists("User", user_name):
				frappe.delete_doc("User", user_name, force=1, ignore_permissions=True)

		super().tearDown()

	def _payload(self, suffix=None):
		suffix = suffix or uuid4().hex[:8]
		return {
			"tipo_documento": "Cedula",
			"numero_documento": f"9{suffix}",
			"nombres": "Candidato",
			"apellidos": "Seguridad",
			"email": f"candidato.{suffix}@example.com",
			"ciudad": "Bogota",
			"direccion": "Calle 123 #45-67",
		}

	def _create_candidate_for_tests(self, suffix=None):
		payload = self._payload(suffix=suffix)
		result = create_candidate(json.dumps(payload))
		self._created_candidates.append(result["name"])
		if result.get("user"):
			self._created_users.append(result["user"])
		return payload, result

	def test_create_candidate_rejects_rate_limit_abuse(self):
		payload = self._payload()
		with patch(
			"hubgh.www.candidato.enforce_onboarding_rate_limit",
			side_effect=frappe.TooManyRequestsError,
		):
			with self.assertRaises(frappe.TooManyRequestsError):
				create_candidate(json.dumps(payload))

	def test_validate_onboarding_captcha_enabled_and_invalid(self):
		with patch.dict(
			frappe.conf,
			{
				"hubgh_onboarding_captcha_enabled": 1,
				"hubgh_onboarding_captcha_secret_key": "secret-test",
			},
			clear=False,
		), patch(
			"hubgh.hubgh.onboarding_security.make_post_request",
			return_value={"success": False},
		):
			with self.assertRaises(frappe.ValidationError):
				validate_onboarding_captcha({"captcha_token": "invalid"})

	def test_rate_limit_enforced_by_identifier(self):
		identifier = f"id-{uuid4().hex[:8]}"
		with patch.dict(
			frappe.conf,
			{
				"hubgh_onboarding_rate_limit_enabled": 1,
				"hubgh_onboarding_rate_limit_limit": 2,
				"hubgh_onboarding_rate_limit_window_seconds": 60,
			},
			clear=False,
		), patch("hubgh.hubgh.onboarding_security.get_request_ip_address", return_value="10.10.10.10"):
			enforce_onboarding_rate_limit(identifier=identifier)
			enforce_onboarding_rate_limit(identifier=identifier)
			with self.assertRaises(frappe.TooManyRequestsError):
				enforce_onboarding_rate_limit(identifier=identifier)

	def test_validate_candidate_duplicates_blocks_document_and_email(self):
		payload, _ = self._create_candidate_for_tests()

		with self.assertRaises(frappe.DuplicateEntryError):
			validate_candidate_duplicates(numero_documento=payload["numero_documento"], email="other@example.com")

		with self.assertRaises(frappe.DuplicateEntryError):
			validate_candidate_duplicates(numero_documento=f"x-{uuid4().hex[:8]}", email=payload["email"].upper())

	def test_validate_candidate_duplicates_blocks_existing_user_by_document_or_email(self):
		suffix = uuid4().hex[:8]
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"existing.{suffix}@example.com",
				"username": f"3{suffix}",
				"first_name": "Existing",
				"last_name": "User",
				"enabled": 1,
				"send_welcome_email": 0,
				"user_type": "Website User",
			}
		).insert(ignore_permissions=True)
		self._created_users.append(user.name)

		with self.assertRaises(frappe.ValidationError):
			validate_candidate_duplicates(numero_documento=f"3{suffix}", email="other@example.com")

		with self.assertRaises(frappe.ValidationError):
			validate_candidate_duplicates(numero_documento=f"4{suffix}", email=f"EXISTING.{suffix}@EXAMPLE.COM")

	def test_ensure_user_link_generates_non_document_password_and_marks_reset(self):
		payload, result = self._create_candidate_for_tests()
		user = result["user"]

		with self.assertRaises(frappe.AuthenticationError):
			check_password(user, payload["numero_documento"])

		self.assertTrue(should_force_password_reset(user))

	def test_create_candidate_disables_welcome_email_for_new_user(self):
		_, result = self._create_candidate_for_tests()
		user = frappe.get_doc("User", result["user"])
		self.assertEqual(int(user.send_welcome_email or 0), 0)

	def test_create_candidate_uses_workflow_compatible_initial_status(self):
		meta = frappe.get_meta("Candidato")
		estado_field = meta.get_field("estado_proceso")
		allowed = [line.strip() for line in (estado_field.options or "").splitlines() if line.strip()]
		_, result = self._create_candidate_for_tests()
		candidate = frappe.get_doc("Candidato", result["name"])
		expected = "En documentación" if "En documentación" in allowed else "En Proceso"
		self.assertEqual(candidate.estado_proceso, expected)

	def test_create_candidate_falls_back_to_live_legacy_initial_status(self):
		meta = frappe.get_meta("Candidato")
		estado_field = meta.get_field("estado_proceso")
		original_options = estado_field.options
		estado_field.options = "En Proceso\nEn examen médico\nEn afiliación\nListo para contratar\nContratado\nRechazado"
		try:
			_, result = self._create_candidate_for_tests()
		finally:
			estado_field.options = original_options

		candidate = frappe.get_doc("Candidato", result["name"])
		self.assertEqual(candidate.estado_proceso, "En Proceso")

	def test_enforce_password_reset_on_login_sets_redirect(self):
		_, result = self._create_candidate_for_tests()
		user = result["user"]

		frappe.local.response = {}
		login_manager = SimpleNamespace(user=user)
		enforce_password_reset_on_login(login_manager=login_manager)

		self.assertIn("redirect_to", frappe.local.response)
		self.assertEqual(frappe.local.response.get("message"), "Password Reset")

		clear_force_password_reset_flag(user)

	def test_create_candidate_persists_procedencia_and_allows_optional_second_last_name(self):
		suffix = uuid4().hex[:8]
		payload = {
			"tipo_documento": "Cedula",
			"numero_documento": f"8{suffix}",
			"nombres": "Camila",
			"apellidos": "Rojas",
			"email": f"camila.{suffix}@example.com",
			"ciudad": "Bogota",
			"direccion": "Cra 10 # 20-30",
			"procedencia_pais": "169",
			"procedencia_departamento": "25",
			"procedencia_ciudad": "001",
		}
		meta = frappe.get_meta("Candidato")
		segundo_ap_field = meta.get_field("segundo_apellido")
		original_reqd = int(segundo_ap_field.reqd or 0)
		segundo_ap_field.reqd = 0
		try:
			result = create_candidate(json.dumps(payload))
		finally:
			segundo_ap_field.reqd = original_reqd
		self._created_candidates.append(result["name"])
		if result.get("user"):
			self._created_users.append(result["user"])

		created = frappe.get_doc("Candidato", result["name"])
		self.assertEqual(created.primer_apellido, "Rojas")
		self.assertEqual(created.segundo_apellido or "", "")
		self.assertEqual(created.procedencia_pais, "169")
		self.assertEqual(created.procedencia_departamento, "25")
		self.assertEqual(created.procedencia_ciudad, "001")
		self.assertEqual(int(created.es_extranjero or 0), 0)
		self.assertEqual((created.prefijo_cuenta_extranjero or "").upper(), "NO APLICA")
		self.assertEqual(created.pais_residencia_siesa, "169")
		self.assertEqual(created.departamento_residencia_siesa, "25")
		self.assertEqual(created.ciudad_residencia_siesa, "001")

	def test_create_candidate_accepts_procedencia_labels_and_normalizes_to_codes(self):
		suffix = uuid4().hex[:8]
		payload = {
			"tipo_documento": "Cedula",
			"numero_documento": f"7{suffix}",
			"nombres": "Laura",
			"apellidos": "Mora",
			"email": f"laura.{suffix}@example.com",
			"ciudad": "Bogota",
			"direccion": "Cra 7 # 45-10",
			"procedencia_pais": "Colombia",
			"procedencia_departamento": "Cundinamarca",
			"procedencia_ciudad": "Armenia",
		}
		result = create_candidate(json.dumps(payload))
		self._created_candidates.append(result["name"])
		if result.get("user"):
			self._created_users.append(result["user"])

		created = frappe.get_doc("Candidato", result["name"])
		self.assertEqual(created.procedencia_pais, "169")
		self.assertEqual(created.procedencia_departamento, "25")
		self.assertEqual(created.procedencia_ciudad, "001")

	def test_create_candidate_requires_prefix_for_foreign_country(self):
		suffix = uuid4().hex[:8]
		payload = {
			"tipo_documento": "Cedula",
			"numero_documento": f"6{suffix}",
			"nombres": "Nina",
			"apellidos": "Ruiz",
			"email": f"nina.{suffix}@example.com",
			"ciudad": "Bogota",
			"direccion": "Cra 50 # 20-10",
			"procedencia_pais": "850",
			"procedencia_departamento": "",
			"procedencia_ciudad": "",
			"prefijo_cuenta_extranjero": "",
		}

		with self.assertRaises(frappe.ValidationError):
			create_candidate(json.dumps(payload))

	def test_create_candidate_sets_foreign_flags_when_country_not_169(self):
		suffix = uuid4().hex[:8]
		payload = {
			"tipo_documento": "Cedula",
			"numero_documento": f"5{suffix}",
			"nombres": "Sofia",
			"apellidos": "Luna",
			"email": f"sofia.{suffix}@example.com",
			"ciudad": "Bogota",
			"direccion": "Cra 60 # 30-10",
			"procedencia_pais": "850",
			"procedencia_departamento": "",
			"procedencia_ciudad": "",
			"prefijo_cuenta_extranjero": "600",
		}

		result = create_candidate(json.dumps(payload))
		self._created_candidates.append(result["name"])
		if result.get("user"):
			self._created_users.append(result["user"])

		created = frappe.get_doc("Candidato", result["name"])
		self.assertEqual(created.procedencia_pais, "850")
		self.assertEqual(created.procedencia_departamento or "", "")
		self.assertEqual(created.procedencia_ciudad or "", "")
		self.assertEqual(int(created.es_extranjero or 0), 1)
		self.assertEqual(created.prefijo_cuenta_extranjero, "600")
		self.assertEqual(created.pais_residencia_siesa, "850")

	def test_get_procedencia_catalog_keeps_only_colombia_and_venezuela(self):
		catalog = get_procedencia_siesa_catalog()
		paises = catalog.get("paises") or []
		codes = {str(row.get("code") or "") for row in paises}
		self.assertEqual(codes, {"169", "850"})
		# Debe traer un set amplio de ciudades (no solo muestra corta)
		self.assertGreaterEqual(len(catalog.get("ciudades") or []), 1000)

	def test_create_candidate_accepts_colombia_five_digit_city_code(self):
		suffix = uuid4().hex[:8]
		payload = {
			"tipo_documento": "Cedula",
			"numero_documento": f"4{suffix}",
			"nombres": "Valeria",
			"apellidos": "Pardo",
			"email": f"valeria.{suffix}@example.com",
			"ciudad": "Bogota",
			"direccion": "Cra 100 # 10-20",
			"procedencia_pais": "169",
			"procedencia_departamento": "11",
			"procedencia_ciudad": "11001",
		}

		result = create_candidate(json.dumps(payload))
		self._created_candidates.append(result["name"])
		if result.get("user"):
			self._created_users.append(result["user"])

		created = frappe.get_doc("Candidato", result["name"])
		self.assertEqual(created.procedencia_pais, "169")
		self.assertEqual(created.procedencia_departamento, "11")
		self.assertEqual(created.procedencia_ciudad, "001")
		self.assertEqual(int(created.es_extranjero or 0), 0)
		self.assertEqual((created.prefijo_cuenta_extranjero or "").upper(), "NO APLICA")

	def test_create_candidate_persists_banking_and_location_fields(self):
		suffix = uuid4().hex[:8]
		payload = {
			"tipo_documento": "Cedula",
			"numero_documento": f"3{suffix}",
			"nombres": "Sara",
			"apellidos": "Campos",
			"email": f"sara.{suffix}@example.com",
			"ciudad": "Bogota",
			"localidad": "Suba",
			"direccion": "Cra 50 # 20-10",
			"barrio": "Niza",
			"procedencia_pais": "169",
			"procedencia_departamento": "11",
			"procedencia_ciudad": "001",
			"banco_siesa": "1059",
			"tipo_cuenta_bancaria": "Ahorros",
			"numero_cuenta_bancaria": "1234567890",
		}

		result = create_candidate(json.dumps(payload))
		self._created_candidates.append(result["name"])
		if result.get("user"):
			self._created_users.append(result["user"])

		created = frappe.get_doc("Candidato", result["name"])
		self.assertEqual(created.barrio, "Niza")
		self.assertEqual(created.localidad, "Suba")
		self.assertEqual(created.procedencia_pais, "169")
		self.assertEqual(created.procedencia_departamento, "11")
		self.assertEqual(created.procedencia_ciudad, "001")
		self.assertEqual(created.banco_siesa, "1059")
		self.assertEqual(created.tipo_cuenta_bancaria, "Ahorros")
		self.assertEqual(created.numero_cuenta_bancaria, "1234567890")
