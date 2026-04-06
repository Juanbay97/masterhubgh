import frappe

from hubgh.hubgh.role_matrix import ROLE_MIGRATION_CANONICAL_MAP


def execute():
	if not frappe.db.exists("DocType", "Role") or not frappe.db.exists("DocType", "Has Role"):
		return

	for legacy_role, canonical_role in ROLE_MIGRATION_CANONICAL_MAP.items():
		_ensure_role(canonical_role)
		_migrate_user_role_assignments(legacy_role, canonical_role)

	frappe.db.commit()


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


def _migrate_user_role_assignments(legacy_role, canonical_role):
	if legacy_role == canonical_role:
		return
	if not frappe.db.exists("Role", legacy_role):
		return

	users = frappe.get_all("Has Role", filters={"role": legacy_role}, pluck="parent")
	for user in users:
		if not user or user in {"Administrator", "Guest"}:
			continue
		if not frappe.db.exists("User", user):
			continue

		already_has_canonical = frappe.db.exists(
			"Has Role", {"parenttype": "User", "parent": user, "role": canonical_role}
		)
		if not already_has_canonical:
			frappe.get_doc({
				"doctype": "Has Role",
				"parenttype": "User",
				"parentfield": "roles",
				"parent": user,
				"role": canonical_role,
			}).insert(ignore_permissions=True)

