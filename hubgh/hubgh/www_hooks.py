import frappe

from hubgh.hubgh.role_matrix import canonicalize_roles, roles_have_any


def check_page_permissions():
	"""Redirect users to /sin_acceso when attempting restricted routes without role access."""
	if frappe.session.user == "Guest":
		return

	current_path = (getattr(frappe.request, "path", "") or "").rstrip("/") or "/"
	if current_path == "/sin_acceso":
		return

	restricted_pages = {
		"/app/punto-360": {"Jefe_PDV", "Gestión Humana", "System Manager"},
		"/app/candidato": {"HR Selection", "Gestión Humana", "System Manager"},
		"/app/reportes-siesa": {"Gestión Humana", "System Manager"},
		"/app/archivo-empleados": {"Gestión Humana", "Jefe_PDV", "System Manager"},
	}

	roles = canonicalize_roles(frappe.get_roles(frappe.session.user) or [])
	is_candidate_only = "Candidato" in roles and not roles_have_any(roles, {"System Manager", "HR Selection", "Gestión Humana"})
	if is_candidate_only:
		allowed_app_prefixes = (
			"/app/mis_documentos_candidato",
			"/app/mi-postulacion",
			"/app/logout",
		)
		blocked_prefixes = (
			"/app/workspace",
			"/app/module-def",
			"/app/user-permission",
			"/app/lms",
			"/lms",
		)

		is_allowed_app = any(current_path == prefix or current_path.startswith(f"{prefix}/") for prefix in allowed_app_prefixes)
		is_blocked = any(current_path == prefix or current_path.startswith(f"{prefix}/") for prefix in blocked_prefixes)
		if is_blocked:
			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/sin_acceso"
			return

		if current_path == "/app" or current_path.startswith("/app/"):
			if not is_allowed_app:
				frappe.local.response["type"] = "redirect"
				frappe.local.response["location"] = "/sin_acceso"
				return

		if current_path.startswith("/lms"):
			frappe.local.response["type"] = "redirect"
			frappe.local.response["location"] = "/sin_acceso"
			return

	for page, required_roles in restricted_pages.items():
		if current_path.startswith(page):
			if not roles_have_any(roles, required_roles):
				frappe.local.response["type"] = "redirect"
				frappe.local.response["location"] = "/sin_acceso"
				return
