import frappe

from hubgh.access_profiles import ensure_roles_and_profiles


def execute():
	if not frappe.db.exists("DocType", "Role") or not frappe.db.exists("DocType", "Has Role"):
		return

	ensure_roles_and_profiles()
	_grant_role_to_existing_users("Gerente GH", {"GH Gerente"})
	_grant_role_to_existing_users("Relaciones Laborales Jefe", {"HR Labor Relations", "GH - RRLL"})
	frappe.db.commit()


def _grant_role_to_existing_users(target_role, source_roles):
	_ensure_role(target_role)
	for source_role in sorted(set(source_roles or [])):
		if not source_role or not frappe.db.exists("Role", source_role):
			continue
		users = frappe.get_all("Has Role", filters={"role": source_role}, pluck="parent")
		for user in users:
			if not user or user in {"Administrator", "Guest"}:
				continue
			if not frappe.db.exists("User", user):
				continue
			if frappe.db.exists("Has Role", {"parenttype": "User", "parent": user, "role": target_role}):
				continue
			frappe.get_doc({
				"doctype": "Has Role",
				"parenttype": "User",
				"parentfield": "roles",
				"parent": user,
				"role": target_role,
			}).insert(ignore_permissions=True)


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
