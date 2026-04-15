import frappe

from hubgh.hubgh.role_matrix import canonicalize_roles, expand_roles_for_lookup


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


def get_workspace_permission_query_conditions(user=None):
	user = user or frappe.session.user
	roles = canonicalize_roles(set(frappe.get_roles(user) or [])) if user and user != "Guest" else set()
	expanded_roles = sorted(set(expand_roles_for_lookup(roles)))

	if "System Manager" in expanded_roles:
		return ""

	if not expanded_roles:
		return "not exists (select 1 from `tabHas Role` hr where hr.parenttype='Workspace' and hr.parent=`tabWorkspace`.name)"

	escaped_roles = ", ".join(frappe.db.escape(role) for role in expanded_roles)
	return (
		"(not exists (select 1 from `tabHas Role` hr where hr.parenttype='Workspace' and hr.parent=`tabWorkspace`.name) "
		f"or exists (select 1 from `tabHas Role` hr where hr.parenttype='Workspace' and hr.parent=`tabWorkspace`.name and hr.role in ({escaped_roles})))"
	)


def workspace_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	roles = canonicalize_roles(set(frappe.get_roles(user) or [])) if user and user != "Guest" else set()
	return has_doc_access("Workspace", getattr(doc, "name", None), roles)

