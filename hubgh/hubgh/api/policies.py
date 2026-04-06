import frappe


@frappe.whitelist()
def search(query=None, filters=None):
	"""Busca políticas con filtros compactos para cards."""
	if not frappe.db.exists("DocType", "GH Policy"):
		return []

	parsed_filters = frappe.parse_json(filters) if filters else {}
	query = (query or "").strip()
	user_roles = set(frappe.get_roles(frappe.session.user) or [])

	db_filters = {}
	if parsed_filters.get("categoria"):
		db_filters["categoria"] = parsed_filters.get("categoria")
	if parsed_filters.get("vigente") in (0, 1, "0", "1"):
		db_filters["vigente"] = int(parsed_filters.get("vigente"))

	rows = frappe.get_all(
		"GH Policy",
		filters=db_filters,
		fields=["name", "titulo", "categoria", "version", "vigente", "tags", "archivo", "roles_permitidos", "fecha_vigencia"],
		order_by="fecha_vigencia desc, modified desc",
		limit=50,
	)

	results = []
	for row in rows:
		if query and not _matches_query(row, query):
			continue
		if not _allowed_for_user(row.get("roles_permitidos"), user_roles):
			continue
		results.append(
			{
				"name": row.get("name"),
				"titulo": row.get("titulo"),
				"categoria": row.get("categoria"),
				"version": row.get("version"),
				"vigente": row.get("vigente"),
				"archivo": row.get("archivo"),
				"tags": row.get("tags"),
				"fecha_vigencia": row.get("fecha_vigencia"),
			}
		)

	return results


def _matches_query(row, query):
	q = query.lower()
	blob = " ".join(
		[
			str(row.get("titulo") or ""),
			str(row.get("categoria") or ""),
			str(row.get("tags") or ""),
		]
	).lower()
	return q in blob


def _allowed_for_user(raw_roles, user_roles):
	if not raw_roles:
		return True

	allowed = set()
	for part in str(raw_roles).split("\n"):
		for role in part.split(","):
			role = role.strip()
			if role:
				allowed.add(role)
	if not allowed:
		return True
	return bool(user_roles.intersection(allowed)) or "System Manager" in user_roles
