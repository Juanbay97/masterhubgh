import frappe
from frappe.utils import getdate, now_datetime, nowdate

from hubgh.person_identity import resolve_employee_for_user


@frappe.whitelist()
def get_posts(limit=10, area=None):
	"""Lista posts vigentes/publicados de GH Post."""
	limit = cint_safe(limit, 10)
	limit = 10 if limit <= 0 else min(limit, 50)

	if not frappe.db.exists("DocType", "GH Post"):
		return []

	filters = {"publicado": 1}
	if area:
		filters["area"] = area

	posts = frappe.get_all(
		"GH Post",
		filters=filters,
		fields=["name", "titulo", "cuerpo_corto", "area", "fecha_publicacion", "vigencia_hasta", "audiencia_roles", "adjunto"],
		order_by="fecha_publicacion desc, modified desc",
		limit=limit,
	)

	today = nowdate()
	user_roles = set(frappe.get_roles(frappe.session.user) or [])

	visible = []
	for p in posts:
		if p.get("vigencia_hasta") and str(p.get("vigencia_hasta")) < today:
			continue
		if not _is_allowed_by_roles(p.get("audiencia_roles"), user_roles):
			continue
		visible.append(_serialize_post(p))

	return visible[:limit]


@frappe.whitelist()
def get_home_feed(limit=10, area=None):
	"""Contrato integral Home/Feed para shell Fase 2."""
	posts = get_posts(limit=limit, area=area)
	widgets = {
		"alerts": _get_personal_alerts(),
		"birthdays": _get_upcoming_birthdays(limit=5, window_days=30),
		"lms_pending": _get_lms_pending_courses(limit=5),
		"profile_completion": _get_profile_completion(),
	}

	return {
		"feed": {
			"posts": posts,
			"count": len(posts),
			"empty": len(posts) == 0,
		},
		"widgets": widgets,
		"meta": {
			"generated_at": now_datetime().isoformat(),
			"source": "hubgh.api.feed.get_home_feed",
		},
	}


def _is_allowed_by_roles(raw_roles, user_roles):
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


def _serialize_post(post):
	return {
		"name": post.get("name"),
		"titulo": post.get("titulo") or "",
		"cuerpo_corto": post.get("cuerpo_corto") or "",
		"area": post.get("area") or "",
		"fecha_publicacion": str(post.get("fecha_publicacion") or ""),
		"vigencia_hasta": str(post.get("vigencia_hasta") or "") if post.get("vigencia_hasta") else None,
		"adjunto": post.get("adjunto"),
	}


def _get_personal_alerts():
	"""Retorna alertas personales desde fuente configurada, o empty-state explícito."""
	return {
		"items": [],
		"empty": True,
		"source": "not_configured",
		"message": "No hay fuente de alertas personales configurada.",
	}


def _get_upcoming_birthdays(limit=5, window_days=30):
	if not frappe.db.exists("DocType", "Datos Contratacion"):
		return {
			"items": [],
			"count": 0,
			"empty": True,
			"source": "Datos Contratacion",
		}

	rows = frappe.db.sql(
		"""
		SELECT
			name,
			nombres,
			primer_apellido,
			segundo_apellido,
			fecha_nacimiento,
			ficha_empleado,
			pdv_destino,
			CASE
				WHEN DATE_FORMAT(fecha_nacimiento, '2000-%%m-%%d') >= DATE_FORMAT(CURDATE(), '2000-%%m-%%d')
				THEN DATEDIFF(
					STR_TO_DATE(CONCAT(YEAR(CURDATE()), '-', DATE_FORMAT(fecha_nacimiento, '%%m-%%d')), '%%Y-%%m-%%d'),
					CURDATE()
				)
				ELSE DATEDIFF(
					STR_TO_DATE(CONCAT(YEAR(CURDATE()) + 1, '-', DATE_FORMAT(fecha_nacimiento, '%%m-%%d')), '%%Y-%%m-%%d'),
					CURDATE()
				)
			END AS days_until
		FROM `tabDatos Contratacion`
		WHERE fecha_nacimiento IS NOT NULL
		HAVING days_until BETWEEN 0 AND %(window_days)s
		ORDER BY days_until ASC, fecha_nacimiento ASC
		LIMIT %(limit)s
		""",
		{"window_days": cint_safe(window_days, 30), "limit": cint_safe(limit, 5)},
		as_dict=True,
	)

	items = []
	for row in rows:
		birthday = getdate(row.get("fecha_nacimiento")) if row.get("fecha_nacimiento") else None
		full_name = " ".join(
			[p for p in [row.get("nombres"), row.get("primer_apellido"), row.get("segundo_apellido")] if p]
		).strip()
		items.append(
			{
				"name": row.get("name"),
				"full_name": full_name or row.get("ficha_empleado") or row.get("name"),
				"birth_date": str(row.get("fecha_nacimiento")),
				"day_month": birthday.strftime("%d/%m") if birthday else "",
				"days_until": cint_safe(row.get("days_until"), 0),
				"ficha_empleado": row.get("ficha_empleado"),
				"pdv": row.get("pdv_destino"),
			}
		)

	return {
		"items": items,
		"count": len(items),
		"empty": len(items) == 0,
		"source": "Datos Contratacion",
	}


def _get_lms_pending_courses(limit=5):
	if not _lms_tables_available():
		return {
			"items": [],
			"count": 0,
			"empty": True,
			"available": False,
			"reason": "lms_unavailable",
		}

	user_email = frappe.session.user
	enrollments = frappe.get_all(
		"LMS Enrollment",
		filters={"member": user_email},
		fields=["name", "course", "progress", "modified"],
		order_by="modified desc",
		limit=cint_safe(limit, 5) * 3,
	)

	pending = []
	for row in enrollments:
		progress = cint_safe(row.get("progress"), 0)
		if progress >= 100:
			continue
		pending.append(
			{
				"enrollment": row.get("name"),
				"course": row.get("course"),
				"progress": progress,
				"status": "En progreso" if progress > 0 else "Sin iniciar",
			}
		)
		if len(pending) >= cint_safe(limit, 5):
			break

	return {
		"items": pending,
		"count": len(pending),
		"empty": len(pending) == 0,
		"available": True,
		"reason": "no_pending_courses" if not pending else None,
	}


def _get_profile_completion():
	user = frappe.session.user
	employee = _get_employee_from_user(user)
	if not employee:
		return {
			"available": False,
			"completion_percent": 0,
			"completed_fields": 0,
			"total_fields": 9,
			"missing_fields": [
				"nombres",
				"apellidos",
				"email",
				"pdv",
				"cargo",
				"fecha_nacimiento",
				"numero_documento",
				"direccion",
				"celular",
			],
			"status": "pending_employee_record",
		}

	contract = _get_contract_data(employee)
	tracked = {
		"nombres": employee.get("nombres"),
		"apellidos": employee.get("apellidos"),
		"email": employee.get("email"),
		"pdv": employee.get("pdv"),
		"cargo": employee.get("cargo"),
		"fecha_nacimiento": contract.get("fecha_nacimiento") if contract else None,
		"numero_documento": contract.get("numero_documento") if contract else None,
		"direccion": contract.get("direccion") if contract else None,
		"celular": contract.get("celular") if contract else None,
	}

	total = len(tracked)
	completed = len([1 for _, value in tracked.items() if str(value or "").strip()])
	completion = int((completed / total) * 100) if total else 0

	status = "low"
	if completion >= 80:
		status = "high"
	elif completion >= 50:
		status = "medium"

	return {
		"available": True,
		"completion_percent": completion,
		"completed_fields": completed,
		"total_fields": total,
		"missing_fields": [key for key, value in tracked.items() if not str(value or "").strip()],
		"status": status,
		"ficha_empleado": employee.get("name"),
	}


def _get_employee_from_user(user_email):
	if not user_email or user_email == "Guest" or not frappe.db.exists("DocType", "Ficha Empleado"):
		return None

	identity = resolve_employee_for_user(user_email)
	if not identity.employee:
		return None

	return frappe.db.get_value(
		"Ficha Empleado",
		identity.employee,
		["name", "nombres", "apellidos", "cargo", "pdv", "estado", "email"],
		as_dict=True,
	)


def _get_contract_data(employee):
	if not employee or not frappe.db.exists("DocType", "Datos Contratacion"):
		return None

	ficha_empleado = employee.get("name")
	email = employee.get("email")
	filters = {}
	if ficha_empleado:
		filters["ficha_empleado"] = ficha_empleado
	elif email:
		filters["email"] = email
	else:
		return None

	rows = frappe.get_all(
		"Datos Contratacion",
		filters=filters,
		fields=["name", "fecha_nacimiento", "numero_documento", "direccion", "celular"],
		order_by="modified desc",
		limit=1,
	)
	return rows[0] if rows else None


def _lms_tables_available():
	return all(
		frappe.db.exists("DocType", dt)
		for dt in ["LMS Enrollment", "LMS Course", "LMS Course Progress"]
	)


def cint_safe(value, default=0):
	try:
		return int(value)
	except Exception:
		return default
