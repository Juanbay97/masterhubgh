import frappe
from frappe.utils import add_days, getdate, nowdate

from hubgh.person_identity import resolve_employee_for_user


DEFAULT_TIME_SUMMARY = {
	"programadas": 0,
	"trabajadas": 0,
	"extra": 0,
	"nocturnas": 0,
	"llegadas_tarde": 0,
	"ausencias": 0,
}


@frappe.whitelist()
def get_summary():
	"""Devuelve resumen del perfil actual con empty-state explícito cuando no existe ficha."""
	user = frappe.session.user
	full_name = frappe.get_cached_value("User", user, "full_name") or user
	user_roles = [r for r in frappe.get_roles(user) if r not in ("All", "Guest")]

	emp = _get_employee_from_user(user)
	if emp:
		nombre = f"{(emp.get('nombres') or '').strip()} {(emp.get('apellidos') or '').strip()}".strip() or full_name
		punto = ""
		if emp.get("pdv"):
			punto = frappe.db.get_value("Punto de Venta", emp.get("pdv"), "nombre_pdv") or emp.get("pdv")

		profile = {
			"nombre": nombre,
			"cargo": emp.get("cargo") or "Colaborador",
			"punto": punto or "Punto sin asignar",
			"estado": emp.get("estado") or "Activo",
			"sobre_mi": "Perfil sincronizado desde Ficha Empleado.",
		}
		empty_state = {
			"empty": False,
			"code": None,
			"message": "",
		}
	else:
		profile = {
			"nombre": full_name,
			"cargo": "",
			"punto": "",
			"estado": "",
			"sobre_mi": "",
		}
		empty_state = {
			"empty": True,
			"code": "employee_not_linked",
			"message": "No hay Ficha Empleado asociada al usuario actual.",
		}

	chips = []
	if profile.get("estado"):
		chips.append({"label": f"Estado: {profile.get('estado')}", "color": "#0ea5e9"})
	if empty_state.get("empty"):
		chips.append({"label": "Perfil incompleto", "color": "#f59e0b"})
	else:
		chips.append({"label": "Perfil interno", "color": "#22c55e"})
	if any(role in user_roles for role in ("Empleado", "Jefe_PDV", "Gestión Humana")):
		chips.append({"label": "Acceso autorizado", "color": "#6366f1"})

	quick_links = [
		{"label": "Mi carpeta documental", "url": "/app/carpeta_documental_empleado", "icon": "📁"},
		{"label": "Novedad SST", "url": "/app/novedad-sst", "icon": "📢"},
		{"label": "Capacitación LMS", "url": "/lms", "icon": "🎓"},
	]

	return {
		"profile": profile,
		"chips": chips,
		"quick_links": quick_links,
		"empty": empty_state.get("empty"),
		"empty_state": empty_state,
	}


@frappe.whitelist()
def get_time_summary(week=None):
	"""Retorna KPIs semanales reales cuando existen, o empty-state explícito cuando no."""
	_ = week
	summary = dict(DEFAULT_TIME_SUMMARY)

	if not frappe.db.exists("DocType", "Timesheet"):
		return {
			**summary,
			"empty": True,
			"empty_state": {
				"empty": True,
				"code": "timesheet_unavailable",
				"message": "No hay fuente de horas configurada para este usuario.",
			},
		}

	week_start, week_end = _current_week_range()
	timesheets = frappe.get_all(
		"Timesheet",
		filters={
			"owner": frappe.session.user,
			"start_date": ["<=", week_end],
			"end_date": [">=", week_start],
		},
		fields=["name", "total_hours"],
	)

	worked_hours = sum(float(ts.get("total_hours") or 0) for ts in timesheets)
	summary["programadas"] = worked_hours
	summary["trabajadas"] = worked_hours

	empty = worked_hours <= 0
	return {
		**summary,
		"empty": empty,
		"empty_state": {
			"empty": empty,
			"code": "no_timesheet_data" if empty else None,
			"message": "Sin registros de tiempo para la semana actual." if empty else "",
		},
	}


def _current_week_range():
	today = getdate(nowdate())
	week_start = add_days(today, -today.weekday())
	week_end = add_days(week_start, 6)
	return week_start, week_end


def _get_employee_from_user(user_email):
	if not user_email or user_email == "Guest":
		return None

	if not frappe.db.exists("DocType", "Ficha Empleado"):
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
