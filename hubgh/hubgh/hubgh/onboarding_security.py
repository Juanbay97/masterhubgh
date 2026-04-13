import re

import frappe
from frappe import _
from frappe.integrations.utils import make_post_request
from frappe.utils import cint

from hubgh.public_url import build_public_url, override_public_base_url_for_frappe


_FORCE_PASSWORD_RESET_CACHE_KEY = "hubgh:onboarding:force_password_reset"


def get_onboarding_security_config():
	conf = frappe.conf or {}
	return {
		"rate_limit_enabled": cint(conf.get("hubgh_onboarding_rate_limit_enabled", 1)),
		"rate_limit_limit": max(cint(conf.get("hubgh_onboarding_rate_limit_limit", 10)), 1),
		"rate_limit_window_seconds": max(cint(conf.get("hubgh_onboarding_rate_limit_window_seconds", 60)), 1),
		"captcha_enabled": cint(conf.get("hubgh_onboarding_captcha_enabled", 0)),
		"captcha_secret_key": (conf.get("hubgh_onboarding_captcha_secret_key") or "").strip(),
		"captcha_verify_url": (
			conf.get("hubgh_onboarding_captcha_verify_url")
			or "https://www.google.com/recaptcha/api/siteverify"
		),
	}


def normalize_candidate_identifier(value):
	if not value:
		return ""
	return re.sub(r"[^A-Za-z0-9._@+-]", "", str(value).strip().lower())


def get_request_ip_address():
	request_ip = getattr(frappe.local, "request_ip", None)
	if request_ip:
		return str(request_ip)

	request = getattr(frappe.local, "request", None)
	if not request:
		return "unknown"

	forwarded_for = request.headers.get("X-Forwarded-For", "") if request.headers else ""
	if forwarded_for:
		return forwarded_for.split(",")[0].strip() or "unknown"

	return "unknown"


def _increment_rate_limit_counter(cache_key, window_seconds):
	cache = frappe.cache
	if cache.get(cache_key) is None:
		cache.setex(cache_key, window_seconds, 0)

	return cint(cache.incrby(cache_key, 1))


def enforce_onboarding_rate_limit(identifier=None):
	config = get_onboarding_security_config()
	if not config["rate_limit_enabled"]:
		return

	limit = config["rate_limit_limit"]
	window_seconds = config["rate_limit_window_seconds"]

	identities = [("ip", get_request_ip_address())]
	normalized_identifier = normalize_candidate_identifier(identifier)
	if normalized_identifier:
		identities.append(("identifier", normalized_identifier))

	for scope, value in identities:
		cache_key = frappe.cache.make_key(f"hubgh:onboarding:rl:{scope}:{value}")
		counter = _increment_rate_limit_counter(cache_key, window_seconds)
		if counter > limit:
			frappe.throw(
				_("Has excedido el límite de intentos de onboarding. Intenta nuevamente en unos minutos."),
				frappe.TooManyRequestsError,
			)


def validate_onboarding_captcha(payload):
	config = get_onboarding_security_config()
	if not config["captcha_enabled"]:
		return

	captcha_token = (
		(payload or {}).get("captcha_token")
		or (payload or {}).get("recaptcha_token")
		or (payload or {}).get("g-recaptcha-response")
	)
	if not captcha_token:
		frappe.throw(_("Captcha requerido."), frappe.ValidationError)

	secret_key = config["captcha_secret_key"]
	if not secret_key:
		frappe.throw(_("Captcha habilitado sin secret configurado."), frappe.ValidationError)

	verification = make_post_request(
		config["captcha_verify_url"],
		data={
			"secret": secret_key,
			"response": captcha_token,
			"remoteip": get_request_ip_address(),
		},
	)

	if not isinstance(verification, dict) or not verification.get("success"):
		frappe.throw(_("Captcha inválido."), frappe.ValidationError)


def validate_candidate_duplicates(numero_documento=None, email=None):
	numero_documento = (numero_documento or "").strip()
	if numero_documento and frappe.db.exists("Candidato", {"numero_documento": numero_documento}):
		frappe.throw(_("Ya existe un candidato con ese número de documento."), frappe.DuplicateEntryError)
	if numero_documento and (
		frappe.db.exists("User", numero_documento)
		or frappe.db.exists("User", {"username": numero_documento})
	):
		frappe.throw(
			_("Ya existe una cuenta asociada a este documento. Inicia sesión o recupera tu contraseña."),
			frappe.ValidationError,
		)

	normalized_email = (email or "").strip().lower()
	if not normalized_email:
		return

	existing_email = frappe.db.sql(
		"""
		SELECT name
		FROM `tabCandidato`
		WHERE LOWER(email) = %s
		LIMIT 1
		""",
		(normalized_email,),
	)
	if existing_email:
		frappe.throw(_("Ya existe un candidato con ese correo electrónico."), frappe.DuplicateEntryError)

	existing_user_email = frappe.db.sql(
		"""
		SELECT name
		FROM `tabUser`
		WHERE LOWER(email) = %s OR LOWER(name) = %s
		LIMIT 1
		""",
		(normalized_email, normalized_email),
	)
	if existing_user_email:
		frappe.throw(
			_("Ya existe una cuenta asociada a este correo. Inicia sesión o recupera tu contraseña."),
			frappe.ValidationError,
		)


def mark_user_for_first_login_password_reset(user_id):
	if not user_id:
		return
	frappe.cache.hset(_FORCE_PASSWORD_RESET_CACHE_KEY, user_id, 1)


def should_force_password_reset(user_id):
	if not user_id:
		return False
	return bool(frappe.cache.hget(_FORCE_PASSWORD_RESET_CACHE_KEY, user_id))


def clear_force_password_reset_flag(user_id):
	if not user_id:
		return
	frappe.cache.hdel(_FORCE_PASSWORD_RESET_CACHE_KEY, user_id)


def send_user_activation_email(user_id):
	if not user_id:
		return None

	user_doc = frappe.get_doc("User", user_id)
	with override_public_base_url_for_frappe():
		reset_url = user_doc.reset_password(send_email=True)

	return build_public_url(reset_url)


def enforce_password_reset_on_login(login_manager=None):
	user_id = getattr(login_manager, "user", None) if login_manager else None
	user_id = user_id or frappe.session.user

	if not user_id or user_id == "Guest":
		return

	if not should_force_password_reset(user_id):
		return

	last_password_reset_date = frappe.db.get_value("User", user_id, "last_password_reset_date")
	if last_password_reset_date:
		clear_force_password_reset_flag(user_id)
		return

	user_doc = frappe.get_doc("User", user_id)
	frappe.local.response["redirect_to"] = user_doc.reset_password(send_email=False, password_expired=True)
	frappe.local.response["message"] = "Password Reset"
