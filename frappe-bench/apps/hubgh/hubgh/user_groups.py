import frappe


COMPANY_GROUP = "HubGH - Toda la Empresa"
OPERATIONS_GROUP = "HubGH - Operación"
ADMINISTRATIVE_GROUP = "HubGH - Administrativos"
PRODUCTION_GROUP = "HubGH - Centros de Producción"


def sync_user_groups_after_migrate():
	sync_all_user_groups()


def sync_user_groups_on_employee_change(doc=None, method=None):
	sync_all_user_groups()


def sync_user_groups_on_user_change(doc=None, method=None):
	sync_all_user_groups()


def sync_all_user_groups():
	logger = frappe.logger("hubgh.user_groups")
	_ensure_base_groups()
	active_users = _get_active_users()
	logger.info(
		"sync_all_user_groups:start",
		extra={
			"active_users_count": len(active_users or []),
			"session_user": frappe.session.user,
		},
	)
	roles_by_user = {user: set(frappe.get_roles(user) or []) for user in active_users}
	employees = frappe.get_all(
		"Ficha Empleado",
		fields=["name", "email", "cedula", "pdv", "cargo"],
	)

	user_to_employee = {}
	for row in employees:
		user = _resolve_user_from_employee_row(row)
		if user and user in active_users:
			user_to_employee[user] = row

	# 1) grupo global
	_sync_group(COMPANY_GROUP, active_users)

	# 2) grupos generales por área de negocio
	operations_users = {
		u
		for u in active_users
		if _has_any_role(roles_by_user.get(u, set()), {"Jefe_PDV", "Coordinador Zona", "Operación"})
		or bool((user_to_employee.get(u) or {}).get("pdv"))
	}
	_sync_group(OPERATIONS_GROUP, operations_users)

	administrative_users = {
		u
		for u, emp in user_to_employee.items()
		if _looks_administrative(emp.get("pdv"), emp.get("cargo"))
		or _has_any_role(roles_by_user.get(u, set()), {"Gestión Humana", "System Manager"})
	}
	_sync_group(ADMINISTRATIVE_GROUP, administrative_users)

	production_users = {
		u for u, emp in user_to_employee.items() if _looks_production_center(emp.get("pdv"), emp.get("cargo"))
	}
	_sync_group(PRODUCTION_GROUP, production_users)

	# 3) grupos por punto de venta
	users_by_point = {}
	for user, emp in user_to_employee.items():
		pdv = (emp.get("pdv") or "").strip()
		if not pdv:
			continue
		users_by_point.setdefault(pdv, set()).add(user)

	for pdv_name in frappe.get_all("Punto de Venta", pluck="name"):
		group_name = _pdv_group_name(pdv_name)
		_sync_group(group_name, users_by_point.get(pdv_name, set()))

	# 4) grupos por ciudad
	points = frappe.get_all("Punto de Venta", fields=["name", "ciudad"])
	city_points = {}
	for row in points:
		city = (row.get("ciudad") or "").strip()
		if not city:
			continue
		city_points.setdefault(city, set()).add(row.get("name"))

	for city, city_pdv_names in city_points.items():
		users = set()
		for pdv_name in city_pdv_names:
			users.update(users_by_point.get(pdv_name, set()))
		_sync_group(_city_group_name(city), users)

	frappe.db.commit()


def _ensure_base_groups():
	for group_name in (COMPANY_GROUP, OPERATIONS_GROUP, ADMINISTRATIVE_GROUP, PRODUCTION_GROUP):
		if frappe.db.exists("User Group", group_name):
			continue
		frappe.get_doc({"doctype": "User Group", "name": group_name}).insert(
			ignore_permissions=True,
			ignore_mandatory=True,
		)


def _resolve_user_from_employee_row(employee_row):
	cedula = (employee_row.get("cedula") or "").strip()
	email = (employee_row.get("email") or "").strip().lower()

	if cedula:
		by_username = frappe.db.get_value("User", {"username": cedula}, "name")
		if by_username:
			return by_username
		if frappe.db.exists("User", cedula):
			return cedula

	if email and frappe.db.exists("User", email):
		return email

	return None


def _get_active_users():
	return set(
		frappe.get_all(
			"User",
			filters={"enabled": 1, "name": ["not in", ["Guest"]]},
			pluck="name",
		)
	)


def _pdv_group_name(pdv_name):
	return f"HubGH - PDV - {pdv_name}"


def _city_group_name(city):
	return f"HubGH - Ciudad - {city}"


def _sync_group(group_name, users):
	logger = frappe.logger("hubgh.user_groups")
	users = sorted({u for u in (users or []) if u and u != "Guest" and frappe.db.exists("User", u)})

	if frappe.db.exists("User Group", group_name):
		doc = frappe.get_doc("User Group", group_name)
	else:
		logger.info(
			"sync_group:create_missing_group",
			extra={
				"group_name": group_name,
				"session_user": frappe.session.user,
				"users_count": len(users),
			},
		)
		doc = frappe.get_doc({"doctype": "User Group", "name": group_name})

	existing = sorted({row.user for row in (doc.user_group_members or []) if row.user})
	if existing == users and not doc.is_new():
		return

	doc.set("user_group_members", [])
	for user in users:
		doc.append("user_group_members", {"user": user})

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		logger.info(
			"sync_group:save_existing_group",
			extra={
				"group_name": group_name,
				"session_user": frappe.session.user,
				"users_count": len(users),
			},
		)
		try:
			doc.save(ignore_permissions=True)
		except frappe.DoesNotExistError:
			logger.warning(
				"sync_group:group_missing_during_save_recreate",
				extra={
					"group_name": group_name,
					"session_user": frappe.session.user,
					"users_count": len(users),
				},
			)
			doc = frappe.get_doc({"doctype": "User Group", "name": group_name})
			doc.set("user_group_members", [])
			for user in users:
				doc.append("user_group_members", {"user": user})
			doc.insert(ignore_permissions=True)


def _has_any_role(user_roles, expected_roles):
	roles = set(user_roles or [])
	for role in expected_roles:
		if role in roles:
			return True
	return False


def _looks_administrative(pdv, cargo):
	text = f"{pdv or ''} {cargo or ''}".lower()
	return any(token in text for token in ["admin", "administrativ", "oficina", "corporativ"])


def _looks_production_center(pdv, cargo):
	text = f"{pdv or ''} {cargo or ''}".lower()
	return any(token in text for token in ["produccion", "producción", "planta", "centro de producción", "centro de produccion"])
