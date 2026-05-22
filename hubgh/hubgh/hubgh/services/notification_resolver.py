# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
notification_resolver — Resolución de destinatarios para notificaciones de traslado PDV.

Provee tres helpers sin acoplamiento de dominio:
- resolve_jefe_pdv(pdv_name)      → User del jefe responsable del PDV
- resolve_employee_email(employee) → email del empleado
- resolve_role_subscribers(role)   → emails de todos los usuarios con un rol
"""

from __future__ import annotations

import frappe

from hubgh.person_identity import resolve_user_for_employee


def resolve_jefe_pdv(pdv_name: str) -> str | None:
	"""
	Resuelve el User del jefe responsable de un PDV.

	Estrategia de resolución (orden de prioridad):
	1. Punto de Venta.jefe_responsable (Link → User) — fuente determinística.
	   Valida que el User exista en la base de datos.
	2. Fallback: intersección de rol 'Jefe_PDV' × empleados con ficha en el PDV.
	   Si hay más de un candidato, retorna el más recientemente modificado.
	3. None si ninguna estrategia encuentra candidato.

	Args:
		pdv_name: Nombre del Punto de Venta.

	Returns:
		User name (que es el email en Frappe) o None.
	"""
	if not pdv_name:
		return None

	# Estrategia 1: campo directo jefe_responsable
	jefe = frappe.db.get_value("Punto de Venta", pdv_name, "jefe_responsable")
	if jefe and frappe.db.exists("User", jefe):
		return jefe

	# Estrategia 2: fallback — intersección rol Jefe_PDV × empleados del PDV activos
	# Ficha Empleado no tiene campo usuario directo; se resuelve vía email matching.
	# Obtenemos todos los Users con rol Jefe_PDV activos...
	jefe_users = frappe.db.sql(
		"""
		SELECT DISTINCT u.name AS user, u.email, u.modified
		FROM `tabUser` u
		JOIN `tabHas Role` hr ON hr.parent = u.name AND hr.role = 'Jefe_PDV'
		WHERE u.enabled = 1
		ORDER BY u.modified DESC
		""",
		as_dict=True,
	)
	if not jefe_users:
		return None

	# ...y entre ellos, filtramos los que tienen una Ficha Empleado en este PDV.
	# Match por email (convención del sistema: user.email == ficha_empleado.email).
	jefe_emails = [r["email"] for r in jefe_users if r.get("email")]
	if not jefe_emails:
		return None

	placeholders = ", ".join(["%s"] * len(jefe_emails))
	match = frappe.db.sql(
		f"""
		SELECT fe.email AS email
		FROM `tabFicha Empleado` fe
		WHERE fe.pdv = %s
		  AND fe.estado = 'Activo'
		  AND fe.email IN ({placeholders})
		LIMIT 1
		""",
		[pdv_name] + jefe_emails,
		as_dict=True,
	)
	if not match:
		return None

	matched_email = match[0]["email"]
	# Retornar el user name que corresponde a ese email
	for r in jefe_users:
		if r.get("email") == matched_email:
			return r["user"]
	return None


def resolve_employee_email(employee: str) -> str | None:
	"""
	Resuelve el email de contacto de un empleado.

	Estrategia:
	1. Lee Ficha Empleado.email directamente (confirmado campo existe).
	2. Fallback: User vinculado vía resolve_user_for_employee.
	   Si User.email está vacío, retorna el user name (que es el login/email en Frappe).
	3. None si no hay identidad posible.

	Args:
		employee: Nombre de la Ficha Empleado.

	Returns:
		Email string o None.
	"""
	if not employee:
		return None

	# Estrategia 1: campo directo en Ficha Empleado
	email = frappe.db.get_value("Ficha Empleado", employee, "email")
	if email:
		return email

	# Estrategia 2: User vinculado
	identity = resolve_user_for_employee(employee)
	if identity and identity.user:
		user_email = frappe.db.get_value("User", identity.user, "email")
		# Frappe: si email está vacío, el user name es el login (generalmente el email)
		return user_email or identity.user

	return None


def resolve_area_subscribers(area: str) -> list[str]:
	"""
	Retorna lista deduplicada de emails de suscriptores configurados para un área
	de terminación.

	Lee `Configuracion Terminacion.suscriptores_por_area` (Single DocType) y
	filtra por `area` + `activo=1`.

	Resolución por tipo de suscriptor (un row puede tener uno de los tres):
	  - user    → frappe.db.get_value("User", user, "email")
	  - role    → resolve_role_subscribers(role) para expandir a todos los emails
	  - email_fijo → agrega el literal directamente

	Args:
		area: Código del área (ej. "sistemas", "rrll_dotacion", "sst", etc.)

	Returns:
		Lista ordenada y deduplicada de emails. Lista vacía si no hay config o
		suscriptores activos para el área.
	"""
	try:
		config = frappe.get_single("Configuracion Terminacion")
	except Exception:
		return []

	emails: set[str] = set()
	rows = getattr(config, "suscriptores_por_area", []) or []

	for row in rows:
		row_area = getattr(row, "area", None)
		activo = getattr(row, "activo", 1)
		if row_area != area:
			continue
		if not activo:
			continue

		user = getattr(row, "user", None)
		role = getattr(row, "role", None)
		email_fijo = getattr(row, "email_fijo", None)

		if user:
			user_email = frappe.db.get_value("User", user, "email")
			if user_email:
				emails.add(user_email)

		if role:
			role_emails = resolve_role_subscribers(role)
			emails.update(role_emails)

		if email_fijo:
			emails.add(email_fijo)

	return sorted(emails)


def resolve_role_subscribers(role: str) -> list[str]:
	"""
	Retorna lista ordenada y deduplicada de emails de todos los Users activos con un rol dado.

	Uso típico: notificar a todo un área (ej. 'Gestión Humana') como fallback C3.
	Para uso futuro en Cambio 3 (Terminación).

	Args:
		role: Nombre del rol Frappe.

	Returns:
		Lista de emails únicos, ordenada.
	"""
	rows = frappe.db.sql(
		"""
		SELECT u.email
		FROM `tabUser` u
		JOIN `tabHas Role` hr ON hr.parent = u.name
		WHERE hr.role = %s
		  AND u.enabled = 1
		  AND u.email IS NOT NULL
		  AND u.email != ''
		""",
		role,
		as_dict=True,
	)
	return sorted({r["email"] for r in rows})
