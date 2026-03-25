import frappe
from frappe.exceptions import DocumentLockedError

from hubgh.hubgh.role_matrix import canonicalize_roles, roles_have_any


ROLE_PROFILES = {
	"HubGH Operario": ["Empleado", "Employee", "LMS Student"],
	"HubGH Jefe PDV": ["Empleado", "Employee", "LMS Student", "Jefe_PDV"],
	"HubGH Coordinador Zona": ["Empleado", "Employee", "LMS Student", "Coordinador Zona"],
	"HubGH GH Seleccion": ["Empleado", "Employee", "Gestión Humana", "HR Selection", "GH - Bandeja General"],
	"HubGH GH SST": ["Empleado", "Employee", "Gestión Humana", "HR SST", "GH - SST"],
	"HubGH GH RRLL": ["Empleado", "Employee", "Gestión Humana", "HR Labor Relations", "GH - RRLL"],
	"HubGH GH Formacion y Bienestar": [
		"Empleado",
		"Employee",
		"Gestión Humana",
		"HR Training & Wellbeing",
	],
	"HubGH Nómina Operativa": ["Empleado", "Employee", "Gestión Humana", "Operativo Nómina"],
	"HubGH Nómina TP": ["Empleado", "Employee", "Gestión Humana", "TP Nómina"],
	"HubGH GH Gerente": [
		"Empleado",
		"Employee",
		"Gestión Humana",
		"GH - Bandeja General",
		"GH - SST",
		"GH - RRLL",
		"HR Selection",
		"HR SST",
		"HR Labor Relations",
		"HR Training & Wellbeing",
		"GH Gerente",
	],
	"HubGH Candidato": ["Candidato"],
	"HubGH Admin": ["System Manager"],
}


MODULE_PROFILES = {
	"HubGH Operario": [],
	"HubGH Jefe PDV": [],
	"HubGH Coordinador Zona": [],
	"HubGH GH": [],
	"HubGH Nómina": [],
	"HubGH Candidato": [],
	"HubGH Admin": [],
}


WORKSPACE_ROLE_MAP = {
	"Mi Perfil": ["Empleado", "Employee", "LMS Student", "Jefe_PDV", "Coordinador Zona", "Gestión Humana", "System Manager"],
	"Mi Postulación": ["Candidato"],
	"Mi Punto": ["Jefe_PDV", "Coordinador Zona", "System Manager"],
	"Operación": ["Jefe_PDV", "Coordinador Zona", "System Manager", "GH Gerente"],
	"Gestión Humana": ["Gestión Humana", "System Manager", "GH - Bandeja General", "GH - SST", "GH - RRLL", "GH Gerente"],
	"Selección": ["HR Selection", "Gestión Humana", "System Manager", "GH Gerente"],
	"Relaciones Laborales": ["HR Labor Relations", "Gestión Humana", "System Manager", "GH - RRLL", "GH Gerente"],
	"SST": ["HR SST", "Gestión Humana", "System Manager", "GH - SST", "GH Gerente"],
	"Capacitación": [
		"Empleado",
		"Employee",
		"LMS Student",
		"Jefe_PDV",
		"Coordinador Zona",
		"HR Training & Wellbeing",
		"Gestión Humana",
		"System Manager",
		"GH Gerente",
	],
	"Bienestar": [
		"HR Training & Wellbeing",
		"Gestión Humana",
		"System Manager",
		"GH Gerente",
	],
	"Nómina": [
		"Gestión Humana",
		"Operativo Nómina",
		"TP Nómina",
		"System Manager",
	],
	"HubGH Admin": ["System Manager"],
}


SEED_ROLES = {
	"Coordinador Zona",
	"GH Gerente",
	"Operación",
	"GH - Bandeja General",
	"GH - SST",
	"GH - RRLL",
	"HR Selection",
	"HR SST",
	"HR Labor Relations",
	"HR Training & Wellbeing",
	"Operativo Nómina",
	"TP Nómina",
	"Contabilidad",
	"RRLL",
	"SST",
}


def ensure_roles_and_profiles():
	for role_name in sorted(SEED_ROLES):
		_ensure_role(role_name)

	for profile_name, profile_roles in ROLE_PROFILES.items():
		_ensure_role_profile(profile_name, profile_roles)

	for module_profile_name, blocked_modules in MODULE_PROFILES.items():
		_ensure_module_profile(module_profile_name, blocked_modules)


def sync_all_user_access_profiles():
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ["not in", ["Guest"]]},
		pluck="name",
	)
	for user in users:
		sync_user_access_profile(user)


def sync_user_access_profile(user):
	if not user or user == "Guest" or not frappe.db.exists("User", user):
		return

	user_roles = set(frappe.get_roles(user) or [])
	canonical_roles = canonicalize_roles(user_roles)

	if "System Manager" in canonical_roles:
		_target_role_profile = "HubGH Admin"
		_target_module_profile = "HubGH Admin"
	elif "Candidato" in canonical_roles:
		_target_role_profile = "HubGH Candidato"
		_target_module_profile = "HubGH Candidato"
	elif roles_have_any(canonical_roles, {"TP Nómina"}):
		_target_role_profile = "HubGH Nómina TP"
		_target_module_profile = "HubGH Nómina"
	elif roles_have_any(canonical_roles, {"Operativo Nómina"}):
		_target_role_profile = "HubGH Nómina Operativa"
		_target_module_profile = "HubGH Nómina"
	elif "GH Gerente" in canonical_roles:
		_target_role_profile = "HubGH GH Gerente"
		_target_module_profile = "HubGH GH"
	elif roles_have_any(canonical_roles, {"HR Training & Wellbeing"}):
		_target_role_profile = "HubGH GH Formacion y Bienestar"
		_target_module_profile = "HubGH GH"
	elif roles_have_any(canonical_roles, {"HR Labor Relations", "GH - RRLL"}):
		_target_role_profile = "HubGH GH RRLL"
		_target_module_profile = "HubGH GH"
	elif roles_have_any(canonical_roles, {"HR SST", "GH - SST"}):
		_target_role_profile = "HubGH GH SST"
		_target_module_profile = "HubGH GH"
	elif roles_have_any(canonical_roles, {"HR Selection", "GH - Bandeja General", "Gestión Humana"}):
		_target_role_profile = "HubGH GH Seleccion"
		_target_module_profile = "HubGH GH"
	elif "Coordinador Zona" in canonical_roles:
		_target_role_profile = "HubGH Coordinador Zona"
		_target_module_profile = "HubGH Coordinador Zona"
	elif roles_have_any(canonical_roles, {"Jefe_PDV"}):
		_target_role_profile = "HubGH Jefe PDV"
		_target_module_profile = "HubGH Jefe PDV"
	else:
		_target_role_profile = "HubGH Operario"
		_target_module_profile = "HubGH Operario"

	frappe.db.set_value("User", user, "role_profile_name", _target_role_profile, update_modified=False)
	frappe.db.set_value("User", user, "module_profile", _target_module_profile, update_modified=False)


def apply_workspace_role_matrix():
	logger = frappe.logger("hubgh.access_profiles")
	for workspace_name, roles in WORKSPACE_ROLE_MAP.items():
		if not frappe.db.exists("Workspace", workspace_name):
			continue

		workspace = frappe.get_doc("Workspace", workspace_name)
		existing = {row.role for row in (workspace.roles or []) if row.role}
		desired = set(roles)

		if existing == desired:
			continue

		workspace.set("roles", [])
		for role in sorted(desired):
			workspace.append("roles", {"role": role})
		try:
			workspace.save(ignore_permissions=True)
		except Exception:
			logger.warning(
				"apply_workspace_role_matrix:skip_workspace_on_save_error",
				extra={"workspace": workspace_name, "error": frappe.get_traceback()},
			)


def after_migrate_sync():
	ensure_roles_and_profiles()
	_deprecate_bienestar_workspace()
	apply_workspace_role_matrix()
	sync_all_user_access_profiles()
	frappe.db.commit()


def _deprecate_bienestar_workspace():
	for legacy_name in ("Formación y Bienestar",):
		if frappe.db.exists("Workspace", legacy_name):
			doc = frappe.get_doc("Workspace", legacy_name)
			doc.is_hidden = 1
			doc.public = 0
			doc.save(ignore_permissions=True)

	frappe.db.sql(
		"""
		update `tabUser`
		set default_workspace='Bienestar'
		where ifnull(default_workspace,'') in ('Formación y Bienestar')
		"""
	)


def _ensure_role(role_name):
	if frappe.db.exists("Role", role_name):
		return

	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": role_name,
			"desk_access": 1,
			"read_only": 0,
		}
	).insert(ignore_permissions=True)


def _ensure_role_profile(profile_name, roles):
	for role in set(roles or []):
		_ensure_role(role)

	doc = frappe.get_doc("Role Profile", profile_name) if frappe.db.exists("Role Profile", profile_name) else frappe.get_doc(
		{"doctype": "Role Profile", "role_profile": profile_name}
	)

	existing = {row.role for row in (doc.roles or []) if row.role}
	desired = set(roles or [])
	if existing == desired and not doc.is_new():
		return

	doc.set("roles", [])
	for role in sorted(desired):
		doc.append("roles", {"role": role})

	if doc.is_new():
		try:
			doc.insert(ignore_permissions=True)
		except DocumentLockedError:
			frappe.logger("hubgh.access_profiles").warning(
				"ensure_role_profile:locked_skip",
				extra={"profile_name": profile_name},
			)
	else:
		try:
			doc.save(ignore_permissions=True)
		except DocumentLockedError:
			frappe.logger("hubgh.access_profiles").warning(
				"ensure_role_profile:locked_skip",
				extra={"profile_name": profile_name},
			)


def _ensure_module_profile(profile_name, blocked_modules):
	doc = (
		frappe.get_doc("Module Profile", profile_name)
		if frappe.db.exists("Module Profile", profile_name)
		else frappe.get_doc({"doctype": "Module Profile", "module_profile_name": profile_name})
	)

	existing = {row.module for row in (doc.block_modules or []) if row.module}
	desired = set(blocked_modules or [])
	if existing == desired and not doc.is_new():
		return

	doc.set("block_modules", [])
	for module in sorted(desired):
		doc.append("block_modules", {"module": module})

	if doc.is_new():
		try:
			doc.insert(ignore_permissions=True)
		except DocumentLockedError:
			frappe.logger("hubgh.access_profiles").warning(
				"ensure_module_profile:locked_skip",
				extra={"profile_name": profile_name},
			)
	else:
		try:
			doc.save(ignore_permissions=True)
		except DocumentLockedError:
			frappe.logger("hubgh.access_profiles").warning(
				"ensure_module_profile:locked_skip",
				extra={"profile_name": profile_name},
			)
