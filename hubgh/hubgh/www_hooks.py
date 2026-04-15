import frappe

from hubgh.hubgh.role_matrix import canonicalize_roles, roles_have_any
from hubgh.utils import get_user_app_home_path, is_candidate_allowed_path, is_candidate_only_user


def check_page_permissions():
	"""Redirect users to /sin_acceso when attempting restricted routes without role access."""
	if frappe.session.user == "Guest":
		return

	current_path = (getattr(frappe.request, "path", "") or "").rstrip("/") or "/"
	if current_path == "/sin_acceso":
		return

	redirect_home = lambda: _redirect(get_user_app_home_path(frappe.session.user))

	restricted_pages = {
		"/app/punto-360": {"Jefe_PDV", "Gestión Humana", "System Manager"},
		"/app/candidato": {"HR Selection", "Gestión Humana", "System Manager"},
		"/app/reportes-siesa": {"Gestión Humana", "System Manager"},
		"/app/archivo-empleados": {"Gestión Humana", "Jefe_PDV", "System Manager"},
	}

	roles = canonicalize_roles(frappe.get_roles(frappe.session.user) or [])
	if is_candidate_only_user(frappe.session.user):
		if current_path.startswith("/lms"):
			return _redirect("/sin_acceso")

		if current_path == "/app" or current_path.startswith("/app/"):
			if not is_candidate_allowed_path(current_path):
				return redirect_home()

	for page, required_roles in restricted_pages.items():
		if current_path.startswith(page):
			if not roles_have_any(roles, required_roles):
				return _redirect("/sin_acceso")


def _redirect(location):
	if not getattr(frappe.local, "response", None):
		frappe.local.response = {}
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = location
