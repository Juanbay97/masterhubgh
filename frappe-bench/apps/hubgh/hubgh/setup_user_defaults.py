import frappe

from hubgh.access_profiles import sync_user_access_profile
from hubgh.hubgh.role_matrix import canonicalize_roles, roles_have_any
from hubgh.utils import get_website_user_home_page


def _resolve_home_workspace(user_roles: set[str]) -> str:
	canonical_roles = canonicalize_roles(user_roles)

	if "Candidato" in canonical_roles:
		return "app/mis_documentos_candidato"

	if "System Manager" in canonical_roles:
		return "HubGH Admin"

	if roles_have_any(canonical_roles, {"Operativo Nómina", "TP Nómina"}):
		return "Nómina"

	if roles_have_any(canonical_roles, {"Gestión Humana", "GH - Bandeja General", "GH - SST", "GH - RRLL"}):
		return "Gestión Humana"

	if roles_have_any(canonical_roles, {"Jefe_PDV"}):
		return "Mi Punto"

	if roles_have_any(canonical_roles, {"HR Training & Wellbeing", "Formación y Bienestar", "Formacion y Bienestar"}):
		return "Bienestar"

	if roles_have_any(canonical_roles, {"GH Gerente"}):
		return "Gestión Humana"

	if roles_have_any(canonical_roles, {"Empleado", "LMS Student", "Employee"}):
		return "Mi Perfil"

	return "Mi Perfil"


def setup_user_home_page(doc=None, method=None, user_email=None):
	"""Set default workspace for user on create/update keeping role aliases compatibility."""
	user_email = user_email or (doc.name if doc else None) or frappe.session.user
	if not user_email or user_email in {"Guest", "Administrator"}:
		return

	if not frappe.db.exists("User", user_email):
		return

	roles = set(frappe.get_roles(user_email) or [])
	workspace = _resolve_home_workspace(roles)

	if frappe.db.exists("Workspace", workspace):
		frappe.db.set_value("User", user_email, "default_workspace", workspace, update_modified=False)

	sync_user_access_profile(user_email)


def on_user_create(doc, method=None):
	setup_user_home_page(doc=doc, method=method)


def setup_all_users():
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ["not in", ["Guest", "Administrator"]]},
		pluck="name",
	)

	for user_email in users:
		setup_user_home_page(user_email=user_email)

	frappe.db.commit()


def apply_login_home_page_redirect(login_manager=None):
	user = getattr(login_manager, "user", None) if login_manager else None
	user = user or frappe.session.user
	if not user or user in {"Guest"}:
		return

	# Respect hard redirects set by other hooks (e.g. password reset)
	if getattr(frappe.local, "response", None) and frappe.local.response.get("redirect_to"):
		return

	home_page = get_website_user_home_page(user)
	if not home_page:
		return

	# Forzar redirección inmediata en login para Candidato.
	# `home_page` a veces solo impacta la UI del desk y no el primer landing.
	if home_page and home_page.startswith("app/"):
		frappe.local.response["redirect_to"] = f"/{home_page}"

	frappe.local.response["home_page"] = home_page
