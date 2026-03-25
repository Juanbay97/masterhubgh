import frappe

from hubgh.hubgh.role_matrix import canonicalize_roles, roles_have_any


PERM_DOCTYPES = {"Ficha Empleado", "LMS Enrollment", "Novedad SST", "Candidato"}


def _get_roles(user):
	return canonicalize_roles(frappe.get_roles(user) or [])


def _get_employee_name(user):
	return _get_employee_row(user).get("name")


def _get_employee_point(user):
	return _get_employee_row(user).get("pdv")


def _get_employee_row(user):
	if not user or user in {"Guest", "Administrator"}:
		return {}

	username = frappe.db.get_value("User", user, "username") if frappe.db.exists("User", user) else None

	if username:
		rows = frappe.get_all(
			"Ficha Empleado",
			filters={"cedula": username},
			fields=["name", "pdv", "email", "cedula"],
			limit=1,
		)
		if rows:
			return rows[0]

	rows = frappe.get_all(
		"Ficha Empleado",
		filters={"email": user},
		fields=["name", "pdv", "email", "cedula"],
		limit=1,
	)
	return rows[0] if rows else {}


def _get_user_allowed_points(user):
	rows = frappe.get_all(
		"User Permission",
		filters={
			"user": user,
			"allow": "Punto de Venta",
			"apply_to_all_doctypes": 1,
		},
		pluck="for_value",
	)
	return [r for r in rows if r]


def get_permission_query_conditions(user=None, doctype=None, **kwargs):
	# Backward compatibility for direct calls like get_permission_query_conditions("Ficha Empleado")
	if doctype is None and user in PERM_DOCTYPES:
		doctype, user = user, None

	user = user or frappe.session.user
	logger = frappe.logger("hubgh.permissions")
	logger.info(
		"permission_query_conditions_call",
		extra={"user": user, "doctype": doctype, "kwargs_keys": sorted((kwargs or {}).keys())},
	)

	if user in {"Guest", "Administrator"}:
		logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": None})
		return None

	roles = _get_roles(user)
	if "System Manager" in roles:
		return None

	if doctype == "Ficha Empleado":
		if roles_have_any(roles, {"Gestión Humana", "GH - Bandeja General", "GH - SST", "GH - RRLL"}):
			logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": None})
			return None
		if roles_have_any(roles, {"Coordinador Zona"}):
			points = _get_user_allowed_points(user)
			if points:
				escaped = ", ".join(frappe.db.escape(p) for p in points)
				result = f"`tabFicha Empleado`.pdv in ({escaped})"
				logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": result})
				return result
			logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": "1=0"})
			return "1=0"
		if roles_have_any(roles, {"Jefe_PDV"}):
			pdv = _get_employee_point(user)
			if pdv:
				result = f"`tabFicha Empleado`.pdv = {frappe.db.escape(pdv)}"
				logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": result})
				return result
			logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": "1=0"})
			return "1=0"

		emp = _get_employee_name(user)
		if emp:
			result = f"`tabFicha Empleado`.name = {frappe.db.escape(emp)}"
			logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": result})
			return result
		logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": "1=0"})
		return "1=0"

	if doctype == "LMS Enrollment":
		if roles_have_any(roles, {"Gestión Humana", "GH - Bandeja General", "GH - SST", "GH - RRLL"}):
			logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": None})
			return None
		result = f"`tabLMS Enrollment`.member = {frappe.db.escape(user)}"
		logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": result})
		return result

	if doctype == "Novedad SST":
		if roles_have_any(roles, {"Gestión Humana", "GH - Bandeja General", "GH - SST", "GH - RRLL"}):
			logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": None})
			return None
		if roles_have_any(roles, {"Coordinador Zona"}):
			points = _get_user_allowed_points(user)
			if points:
				escaped = ", ".join(frappe.db.escape(p) for p in points)
				result = f"`tabNovedad SST`.punto_venta in ({escaped})"
				logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": result})
				return result
			logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": "1=0"})
			return "1=0"
		if roles_have_any(roles, {"Jefe_PDV"}):
			pdv = _get_employee_point(user)
			if pdv:
				result = f"`tabNovedad SST`.punto_venta = {frappe.db.escape(pdv)}"
				logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": result})
				return result
			logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": "1=0"})
			return "1=0"

		emp = _get_employee_name(user)
		if emp:
			result = f"`tabNovedad SST`.empleado = {frappe.db.escape(emp)}"
			logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": result})
			return result
		logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": "1=0"})
		return "1=0"

	if doctype == "Candidato":
		if roles_have_any(roles, {"HR Selection", "HR Labor Relations", "Gestión Humana"}):
			logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": None})
			return None
		logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": "1=0"})
		return "1=0"

	logger.info("permission_query_conditions_result", extra={"user": user, "doctype": doctype, "result": None})
	return None


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if user in {"Administrator"}:
		return True

	roles = _get_roles(user)
	if "System Manager" in roles:
		return True

	if doc.doctype == "Ficha Empleado":
		if roles_have_any(roles, {"Gestión Humana", "GH - Bandeja General", "GH - SST", "GH - RRLL"}):
			return True
		if roles_have_any(roles, {"Coordinador Zona"}):
			return doc.get("pdv") in set(_get_user_allowed_points(user))
		if roles_have_any(roles, {"Jefe_PDV"}):
			user_pdv = _get_employee_point(user)
			return bool(user_pdv and doc.get("pdv") == user_pdv)
		return doc.name == _get_employee_name(user)

	if doc.doctype == "LMS Enrollment":
		if roles_have_any(roles, {"Gestión Humana", "GH - Bandeja General", "GH - SST", "GH - RRLL"}):
			return True
		return doc.get("member") == user

	if doc.doctype == "Candidato":
		return roles_have_any(roles, {"HR Selection", "HR Labor Relations", "Gestión Humana"})

	return True
