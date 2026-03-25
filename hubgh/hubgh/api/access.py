import frappe

from hubgh.hubgh.role_matrix import expand_roles_for_lookup


def has_doc_access(doctype, name, user_roles):
	if not name or not frappe.db.exists(doctype, name):
		return False

	user_roles = set(user_roles or [])
	expanded_user_roles = set(expand_roles_for_lookup(user_roles))

	if "System Manager" in expanded_user_roles:
		return True

	allowed_roles = set(
		frappe.get_all(
			"Has Role",
			filters={"parenttype": doctype, "parent": name},
			pluck="role",
		)
	)
	if not allowed_roles:
		return True

	return bool(user_roles.intersection(allowed_roles) or expanded_user_roles.intersection(allowed_roles))

