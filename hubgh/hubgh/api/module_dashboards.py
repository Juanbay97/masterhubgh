import frappe
from frappe.utils import now_datetime

from hubgh.hubgh.candidate_states import STATE_AFILIACION, STATE_DOCUMENTACION, STATE_LISTO_CONTRATAR, candidate_status_filter_values
from hubgh.hubgh.people_ops_policy import evaluate_dimension_access


MODULE_LABELS = {
	"seleccion": "Selección",
	"rrll": "RL / Contratación",
	"relaciones_laborales": "RL / Contratación",
	"sst": "SST",
	"operacion": "Operación",
	"nomina": "Nómina",
}


def build_dashboard_kpi(key, label, value, **extra):
	item = {
		"key": key,
		"label": label,
		"value": _normalize_metric_value(value),
	}
	item.update(extra)
	return item


def build_dashboard_kpis(items=None):
	rows = list(items or [])
	return {
		"items": rows,
		"empty": len(rows) == 0,
	}


def build_dashboard_alert(title, detail, severity="info", route=None, **extra):
	item = {
		"title": title,
		"detail": detail,
		"severity": severity,
	}
	if route:
		item["route"] = route
	item.update(extra)
	return item


def build_dashboard_alerts(items=None, empty_message=""):
	rows = list(items or [])
	return {
		"items": rows,
		"empty": len(rows) == 0,
		"message": empty_message if not rows else "",
	}


def build_dashboard_actions(actions=None):
	rows = []
	for action in actions or []:
		entry = dict(action or {})
		entry.setdefault("style", "secondary")
		entry.setdefault("visible", True)
		rows.append(entry)
	return rows


@frappe.whitelist()
def get_module_dashboard(module_key):
	if frappe.session.user == "Guest":
		raise frappe.PermissionError

	key = (module_key or "").strip()
	builders = {
		"seleccion": _build_seleccion_dashboard,
		"rrll": _build_rl_dashboard,
		"relaciones_laborales": _build_rl_dashboard,
		"sst": _build_sst_dashboard,
		"operacion": _build_operacion_dashboard,
		"nomina": _build_nomina_dashboard,
	}

	if key not in builders:
		frappe.throw("Módulo no soportado para dashboard de resumen.", frappe.ValidationError)

	dimension_map = {
		"seleccion": "operational",
		"rrll": "sensitive",
		"relaciones_laborales": "sensitive",
		"sst": "clinical",
		"operacion": "operational",
		"nomina": "payroll_operational",
	}
	policy = evaluate_dimension_access(
		dimension_map.get(key, "operational"),
		user=frappe.session.user,
		surface="module_dashboards",
		context={"module": key},
	)
	if not policy.get("effective_allowed"):
		payload = _empty_payload("No tienes permisos para este módulo.", [])
		payload["module"] = {
			"key": key,
			"label": MODULE_LABELS.get(key, key),
		}
		payload["meta"] = {
			"source": "hubgh.api.module_dashboards.get_module_dashboard",
			"generated_at": now_datetime().isoformat(),
		}
		payload["policy"] = policy
		return payload

	payload = builders[key]()
	payload["module"] = {
		"key": key,
		"label": MODULE_LABELS.get(key, key),
	}
	payload["meta"] = {
		"source": "hubgh.api.module_dashboards.get_module_dashboard",
		"generated_at": now_datetime().isoformat(),
	}
	payload["policy"] = policy
	return payload


@frappe.whitelist()
def get_initial_tray_reports():
	modules = ["seleccion", "rrll", "sst", "operacion", "nomina"]
	return {
		"modules": modules,
		"reports": {module_key: get_module_dashboard(module_key) for module_key in modules},
	}


def _build_nomina_dashboard():
	actions = [
		{"label": "Bandeja TC", "route": "app/payroll_tc_tray", "style": "primary"},
		{"label": "Bandeja TP", "route": "app/payroll_tp_tray", "style": "secondary"},
		{"label": "Bandeja Incapacidades", "route": "app/payroll_incapacity_tray", "style": "secondary"},
		{"label": "Cargador Nómina", "route": "app/payroll_import_upload", "style": "secondary"},
	]

	if not _doctype_exists("Payroll Import Line"):
		return _empty_payload("No existe Payroll Import Line en este entorno.", actions)

	tc_pending = frappe.db.count("Payroll Import Line", {"tc_status": ["in", ["Pendiente", "Revisado"]]})
	tp_pending = frappe.db.count("Payroll Import Line", {"tc_status": "Aprobado", "tp_status": ["in", ["Pendiente", "Revisado"]]})
	import_rows = frappe.db.count("Payroll Import Line")
	recobro_weighted = _compute_weighted_recobro_count()

	alerts = []
	if tc_pending > 0:
		alerts.append(
			build_dashboard_alert(
				"Novedades pendientes en TC",
				f"{tc_pending} línea(s) esperan revisión contable.",
				severity="warning",
				route="app/payroll_tc_tray",
			)
		)
	if tp_pending > 0:
		alerts.append(
			build_dashboard_alert(
				"Novedades pendientes en TP",
				f"{tp_pending} línea(s) listas para aprobación final.",
				severity="info",
				route="app/payroll_tp_tray",
			)
		)
	if recobro_weighted > 0:
		alerts.append(
			build_dashboard_alert(
				"Recobros ponderados priorizados",
				f"{recobro_weighted} línea(s) con deducción y envejecimiento activo.",
				severity="danger",
				route="app/payroll_tp_tray",
			)
		)

	empty = (tc_pending + tp_pending + import_rows + recobro_weighted) == 0
	return {
		"empty": empty,
		"empty_state": {
			"title": "Sin actividad de nómina",
			"message": "No hay líneas de importación para TC/TP en este entorno." if empty else "",
		},
		"kpis": {
			"items": [
				_kpi("nomina_tc_pendiente", "TC pendientes", tc_pending),
				_kpi("nomina_tp_pendiente", "TP pendientes", tp_pending),
				_kpi("nomina_import_rows", "Líneas importadas", import_rows),
				_kpi("nomina_recobro_weighted", "Recobros ponderados", recobro_weighted),
			],
			"empty": False,
		},
		"alerts": {
			"items": alerts,
			"empty": len(alerts) == 0,
			"message": "Sin alertas activas en Nómina." if not alerts else "",
		},
		"actions": actions,
	}


def _compute_weighted_recobro_count():
	if not _doctype_exists("Payroll Import Line"):
		return 0

	rows = frappe.get_all(
		"Payroll Import Line",
		filters={
			"status": ["in", ["Válido", "Procesado"]],
			"amount": ["<", 0],
		},
		fields=["name", "amount", "novedad_date"],
		limit=300,
	)
	if not rows:
		return 0

	weighted = 0
	today = frappe.utils.getdate()
	for row in rows:
		amount = abs(float(row.get("amount") or 0))
		aging_days = 0
		if row.get("novedad_date"):
			try:
				aging_days = max((today - frappe.utils.getdate(row.get("novedad_date"))).days, 0)
			except Exception:
				aging_days = 0
		score = min(100.0, (amount / 10000.0) + (aging_days * 2.0))
		if score >= 45:
			weighted += 1
	return weighted


def _build_seleccion_dashboard():
	actions = [
		{"label": "Bandeja Selección", "route": "app/seleccion_documentos", "style": "primary"},
		{"label": "Candidatos", "route": "app/candidato", "style": "secondary"},
		{"label": "Bandeja Contratación", "route": "app/bandeja_contratacion", "style": "secondary"},
	]

	if not _doctype_exists("Candidato"):
		return _empty_payload("No existe DocType Candidato en este entorno.", actions)

	total = frappe.db.count("Candidato")
	incompleta = frappe.db.count("Candidato", {"estado_proceso": ["in", candidate_status_filter_values(STATE_DOCUMENTACION)]})
	listos = frappe.db.count("Candidato", {"estado_proceso": ["in", candidate_status_filter_values(STATE_LISTO_CONTRATAR)]})
	en_proceso = frappe.db.count(
		"Candidato",
		{"estado_proceso": ["in", candidate_status_filter_values(STATE_DOCUMENTACION, STATE_AFILIACION)]},
	)

	rows = frappe.get_all(
		"Candidato",
		filters={"estado_proceso": ["in", candidate_status_filter_values(STATE_DOCUMENTACION, STATE_LISTO_CONTRATAR)]},
		fields=["name", "nombres", "apellidos", "estado_proceso", "pdv_destino", "modified"],
		order_by="modified desc",
		limit=6,
	)

	alerts = []
	for row in rows:
		full_name = _full_name(row.get("nombres"), row.get("apellidos"), row.get("name"))
		detail = f"Estado: {row.get('estado_proceso') or 'Sin estado'}"
		if not row.get("pdv_destino"):
			detail = f"{detail} · sin PDV destino"
		alerts.append(
			{
				"title": full_name,
				"detail": detail,
				"severity": "warning" if row.get("estado_proceso") in candidate_status_filter_values(STATE_DOCUMENTACION) else "info",
				"route": "app/seleccion_documentos",
			}
		)

	empty = total == 0
	return {
		"empty": empty,
		"empty_state": {
			"title": "Sin candidatos para gestión",
			"message": "No hay registros de Candidato para mostrar en Selección." if empty else "",
		},
		"kpis": {
			"items": [
				_kpi("total_candidatos", "Candidatos", total),
				_kpi("en_proceso", "En proceso", en_proceso),
				_kpi("documentacion_incompleta", "Docs incompletos", incompleta),
				_kpi("listos_para_contratar", "Listos para contratar", listos),
			],
			"empty": False,
		},
		"alerts": {
			"items": alerts,
			"empty": len(alerts) == 0,
			"message": "Sin alertas activas en Selección." if not alerts else "",
		},
		"actions": actions,
	}


def _build_rl_dashboard():
	actions = [
		{"label": "Bandeja Contratación", "route": "app/bandeja_contratacion", "style": "primary"},
		{"label": "Bandeja Afiliaciones", "route": "app/bandeja_afiliaciones", "style": "secondary"},
		{"label": "Vista RL", "route": "app/relaciones_laborales_contratacion", "style": "secondary"},
	]

	if not _doctype_exists("Candidato") and not _doctype_exists("Datos Contratacion"):
		return _empty_payload("No existen fuentes de candidatos/contratación para RL.", actions)

	en_afiliacion = (
		frappe.db.count("Candidato", {"estado_proceso": ["in", candidate_status_filter_values(STATE_AFILIACION)]})
		if _doctype_exists("Candidato")
		else 0
	)
	listos = (
		frappe.db.count("Candidato", {"estado_proceso": ["in", candidate_status_filter_values(STATE_LISTO_CONTRATAR)]})
		if _doctype_exists("Candidato")
		else 0
	)
	contratados = frappe.db.count("Candidato", {"estado_proceso": "Contratado"}) if _doctype_exists("Candidato") else 0

	pendientes_ficha = 0
	if _doctype_exists("Datos Contratacion"):
		pendientes_ficha = int(
			(frappe.db.sql("select count(name) from `tabDatos Contratacion` where ifnull(ficha_empleado, '') = ''") or [[0]])[0][0]
		)

	alerts = []
	if _doctype_exists("Candidato"):
		for row in frappe.get_all(
			"Candidato",
			filters={"estado_proceso": ["in", candidate_status_filter_values(STATE_AFILIACION, STATE_LISTO_CONTRATAR)]},
			fields=["name", "nombres", "apellidos", "estado_proceso", "modified"],
			order_by="modified desc",
			limit=4,
		):
			alerts.append(
				{
					"title": _full_name(row.get("nombres"), row.get("apellidos"), row.get("name")),
					"detail": f"Estado RL: {row.get('estado_proceso') or 'Sin estado'}",
					"severity": "warning" if row.get("estado_proceso") in candidate_status_filter_values(STATE_AFILIACION) else "info",
					"route": "app/bandeja_contratacion",
				}
			)

	if pendientes_ficha > 0:
		alerts.insert(
			0,
			{
				"title": "Registros de contratación incompletos",
				"detail": f"{pendientes_ficha} registro(s) en Datos Contratación sin ficha_empleado.",
				"severity": "danger",
				"route": "app/bandeja_afiliaciones",
			},
		)

	empty = (en_afiliacion + listos + contratados + pendientes_ficha) == 0
	return {
		"empty": empty,
		"empty_state": {
			"title": "Sin novedades de contratación",
			"message": "No hay candidatos ni registros de contratación en curso para RL." if empty else "",
		},
		"kpis": {
			"items": [
				_kpi("en_afiliacion", "En afiliación", en_afiliacion),
				_kpi("listos_para_contratar", "Listos para contratar", listos),
				_kpi("contratados", "Contratados", contratados),
				_kpi("datos_sin_ficha", "Datos sin ficha", pendientes_ficha),
			],
			"empty": False,
		},
		"alerts": {
			"items": alerts,
			"empty": len(alerts) == 0,
			"message": "Sin alertas activas para RL / Contratación." if not alerts else "",
		},
		"actions": actions,
	}


def _build_sst_dashboard():
	actions = [
		{"label": "Bandeja SST", "route": "app/sst_bandeja", "style": "primary"},
		{"label": "Novedad SST", "route": "app/novedad-sst", "style": "secondary"},
		{"label": "Alertas SST", "route": "app/sst-alerta", "style": "secondary"},
	]

	if not _doctype_exists("SST Alerta") and not _doctype_exists("Novedad SST"):
		return _empty_payload("No existen fuentes SST (SST Alerta / Novedad SST).", actions)

	pendientes = (
		frappe.db.count("SST Alerta", {"estado": ["in", ["Pendiente", "Reprogramada", "Enviada"]]})
		if _doctype_exists("SST Alerta")
		else 0
	)
	vencidas = 0
	if _doctype_exists("SST Alerta"):
		vencidas = int(
			(
				frappe.db.sql(
					"""
					select count(name)
					from `tabSST Alerta`
					where estado in ('Pendiente', 'Reprogramada', 'Enviada')
					  and fecha_programada is not null
					  and fecha_programada < curdate()
					"""
				)
				or [[0]]
			)[0][0]
		)

	novedades_abiertas = (
		frappe.db.count("Novedad SST", {"estado": ["in", ["Abierta", "En seguimiento", "Abierto"]]})
		if _doctype_exists("Novedad SST")
		else 0
	)
	en_radar = frappe.db.count("Novedad SST", {"en_radar": 1}) if _doctype_exists("Novedad SST") else 0

	alerts = []
	if _doctype_exists("SST Alerta"):
		for row in frappe.get_all(
			"SST Alerta",
			filters={"estado": ["in", ["Pendiente", "Reprogramada", "Enviada"]]},
			fields=["name", "fecha_programada", "tipo_alerta", "estado", "punto_venta"],
			order_by="fecha_programada asc",
			limit=5,
		):
			alerts.append(
				{
					"title": f"Alerta {row.get('name')}",
					"detail": (
						f"{row.get('tipo_alerta') or 'Seguimiento'} · "
						f"{row.get('estado') or 'Pendiente'} · "
						f"{row.get('fecha_programada') or 'sin fecha'}"
					),
					"severity": "danger" if row.get("estado") == "Pendiente" else "warning",
					"route": "app/sst_bandeja",
				}
			)

	empty = (pendientes + vencidas + novedades_abiertas + en_radar) == 0
	return {
		"empty": empty,
		"empty_state": {
			"title": "Sin datos SST para mostrar",
			"message": "No hay alertas ni novedades SST activas." if empty else "",
		},
		"kpis": {
			"items": [
				_kpi("alertas_activas", "Alertas activas", pendientes),
				_kpi("alertas_vencidas", "Alertas vencidas", vencidas),
				_kpi("novedades_abiertas", "Novedades abiertas", novedades_abiertas),
				_kpi("casos_en_radar", "Casos en radar", en_radar),
			],
			"empty": False,
		},
		"alerts": {
			"items": alerts,
			"empty": len(alerts) == 0,
			"message": "Sin alertas de seguimiento en SST." if not alerts else "",
		},
		"actions": actions,
	}


def _build_operacion_dashboard():
	actions = [
		{"label": "Operación Punto", "route": "app/operacion_punto_lite", "style": "primary"},
		{"label": "Punto 360", "route": "app/punto_360", "style": "secondary"},
		{"label": "Novedades GH", "route": "app/gh-novedad", "style": "secondary"},
	]

	try:
		from hubgh.api import ops

		data = ops.get_punto_lite()
	except frappe.PermissionError:
		return _empty_payload("El usuario no tiene Ficha Empleado/PDV asignado para Operación.", actions)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "module_dashboard_operacion_error")
		return _empty_payload("No fue posible cargar el resumen de Operación.", actions)

	kpis_data = data.get("kpis") or {}
	alerts = []

	for row in (data.get("cursos_reporte") or [])[:8]:
		if not row.get("vencido"):
			continue
		alerts.append(
			{
				"title": row.get("nombre") or row.get("persona") or "Persona",
				"detail": f"Curso {row.get('curso') or 'calidad'} · estado {row.get('estado') or 'Sin iniciar'}",
				"severity": "warning",
				"route": "app/operacion_punto_lite",
			}
		)
		if len(alerts) >= 5:
			break

	empty = not any(int(kpis_data.get(k) or 0) for k in [
		"personal_activo",
		"incapacidades_abiertas",
		"accidentes_30d",
		"cursos_calidad_vencidos",
	])

	return {
		"empty": bool(empty),
		"empty_state": {
			"title": "Sin actividad operativa",
			"message": "No hay indicadores operativos disponibles para el usuario actual." if empty else "",
		},
		"kpis": {
			"items": [
				_kpi("personal_activo", "Personal activo", kpis_data.get("personal_activo", 0)),
				_kpi("incapacidades_abiertas", "Incapacidades abiertas", kpis_data.get("incapacidades_abiertas", 0)),
				_kpi("accidentes_30d", "Accidentes 30d", kpis_data.get("accidentes_30d", 0)),
				_kpi("cursos_vencidos", "Cursos vencidos", kpis_data.get("cursos_calidad_vencidos", 0)),
			],
			"empty": False,
		},
		"alerts": {
			"items": alerts,
			"empty": len(alerts) == 0,
			"message": "Sin alertas operativas activas." if not alerts else "",
		},
		"actions": actions,
	}


def _empty_payload(message, actions):
	return {
		"empty": True,
		"empty_state": {
			"title": "Sin datos disponibles",
			"message": message,
		},
		"kpis": build_dashboard_kpis([]),
		"alerts": build_dashboard_alerts([], message),
		"actions": build_dashboard_actions(actions),
	}


def _kpi(key, label, value):
	return build_dashboard_kpi(key, label, value)


def _normalize_metric_value(value):
	if isinstance(value, bool):
		return int(value)
	if isinstance(value, int):
		return value
	if isinstance(value, float):
		return int(value) if value.is_integer() else round(value, 2)
	try:
		number = float(value)
	except Exception:
		return value
	return int(number) if number.is_integer() else round(number, 2)


def _full_name(first_name, last_name, fallback):
	name = f"{(first_name or '').strip()} {(last_name or '').strip()}".strip()
	return name or fallback or "Registro"


def _doctype_exists(doctype):
	return bool(frappe.db.exists("DocType", doctype))
