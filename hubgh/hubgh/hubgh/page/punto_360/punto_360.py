
import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

from hubgh.api.module_dashboards import (
	build_dashboard_actions,
	build_dashboard_alert,
	build_dashboard_alerts,
	build_dashboard_kpi,
	build_dashboard_kpis,
)
from hubgh.hubgh.permissions import evaluate_dimension_permission
from hubgh.hubgh.role_matrix import user_has_any_role


NOVEDAD_TIPO_MAP = {
	"accidente": ["Accidente", "Accidente SST"],
	"incapacidad": ["Incapacidad", "Incapacidad por enfermedad general"],
}

INCAPACIDAD_TIPOS = set(NOVEDAD_TIPO_MAP["incapacidad"])


FORMACION_CATALOGO_BASE = [
	{
		"course": "calidad-e-inocuidad-alimentaria",
		"label": "Calidad e Inocuidad Alimentaria",
		"mandatory": True,
		"sources": ["base"],
	},
	{
		"course": "induccion-operativa-superpromotores",
		"label": "Inducción Operativa",
		"mandatory": False,
		"sources": ["base"],
	},
]


def _row_value(row, key, default=None):
	if isinstance(row, dict):
		return row.get(key, default)
	return getattr(row, key, default)


def _count_by_type(rows, expected_type):
	return len([row for row in (rows or []) if str(_row_value(row, "tipo", "") or "") == expected_type])


def _normalize_text(value):
	return str(value or "").strip().lower()


def _to_float(value, default=0.0):
	try:
		return float(value)
	except Exception:
		return default


def _is_sst_incapacidad(row):
	return bool(_row_value(row, "es_incapacidad", 0)) or str(_row_value(row, "tipo_novedad", "") or "") in INCAPACIDAD_TIPOS


def _handoff_label(row):
	if _row_value(row, "ref_doctype") == "GH Novedad" and _row_value(row, "ref_docname"):
		return f"Traslado RRLL: {_row_value(row, 'ref_docname')}"
	return "Sin traslado RRLL"


def _merge_course_assignment(assigned, course, label, mandatory=False, source=None):
	entry = assigned.setdefault(
		course,
		{
			"course": course,
			"label": label,
			"assignment_type": "Recomendado",
			"sources": [],
		},
	)
	if mandatory:
		entry["assignment_type"] = "Obligatorio"
	if source and source not in entry["sources"]:
		entry["sources"].append(source)


def _assignment_for_employee(emp_row, punto_doc):
	assigned = {}
	cargo = _normalize_text(_row_value(emp_row, "cargo", ""))
	email = (_row_value(emp_row, "email", "") or "").strip()
	roles = set()
	if email and frappe.db.exists("User", email):
		roles = {str(r).strip() for r in (frappe.get_roles(email) or [])}

	for base in FORMACION_CATALOGO_BASE:
		_merge_course_assignment(
			assigned,
			course=base["course"],
			label=base["label"],
			mandatory=bool(base.get("mandatory")),
			source="base",
		)

	if any(tag in cargo for tag in ["jefe", "coordinador", "gerente"]) or "Jefe_PDV" in roles:
		_merge_course_assignment(
			assigned,
			course="liderazgo-punto-de-venta",
			label="Liderazgo Punto de Venta",
			mandatory=True,
			source="cargo/rol",
		)

	if any(tag in cargo for tag in ["sst", "seguridad", "salud ocupacional"]) or "HR SST" in roles:
		_merge_course_assignment(
			assigned,
			course="seguridad-y-salud-en-el-trabajo",
			label="Seguridad y Salud en el Trabajo",
			mandatory=True,
			source="cargo/rol",
		)

	zona = _normalize_text(getattr(punto_doc, "zona", ""))
	if zona:
		_merge_course_assignment(
			assigned,
			course=f"contexto-operativo-{zona.replace(' ', '-')}",
			label=f"Contexto Operativo Zona {str(getattr(punto_doc, 'zona', '') or '').strip()}",
			mandatory=False,
			source="punto",
		)

	return sorted(assigned.values(), key=lambda x: (0 if x.get("assignment_type") == "Obligatorio" else 1, x.get("label") or ""))


def _employee_rows_for_point(punto_venta):
	return frappe.get_all(
		"Ficha Empleado",
		filters={"pdv": punto_venta},
		fields=["name", "nombres", "apellidos", "cargo", "email", "estado"],
	)


def _build_point_employee_summary(employee_rows, novedades_activas):
	novedades_by_employee = {}
	for nov in novedades_activas or []:
		emp_id = str(_row_value(nov, "empleado", "") or "")
		if not emp_id:
			continue
		novedades_by_employee.setdefault(emp_id, []).append(nov)

	rows = []
	for emp in employee_rows or []:
		emp_id = str(_row_value(emp, "name", "") or "")
		emp_novedades = novedades_by_employee.get(emp_id, [])
		has_novedad = bool(emp_novedades)
		en_radar = any(bool(_row_value(nov, "en_radar", 0)) for nov in emp_novedades)
		incapacidad_activa = any(_is_sst_incapacidad(nov) for nov in emp_novedades)
		signal = "stable"
		if incapacidad_activa:
			signal = "limited"
		elif en_radar or has_novedad:
			signal = "attention"

		rows.append(
			{
				"empleado": emp_id,
				"nombre": f"{str(_row_value(emp, 'nombres', '') or '').strip()} {str(_row_value(emp, 'apellidos', '') or '').strip()}".strip(),
				"cargo": _row_value(emp, "cargo"),
				"estado": _row_value(emp, "estado") or "Sin estado",
				"tiene_novedad": has_novedad,
				"signal": signal,
				"signal_label": (
					"Disponibilidad limitada"
					if signal == "limited"
					else ("Requiere atención" if signal == "attention" else "Estable")
				),
				"novedades_activas": len(emp_novedades),
				"en_radar": en_radar,
				"incapacidad_activa": incapacidad_activa,
			}
		)

	return sorted(rows, key=lambda row: (0 if str(row.get("estado") or "") == "Activo" else 1, str(row.get("nombre") or "")))


def _feed_sort_key(item):
	severity_order = {"danger": 0, "warning": 1, "info": 2, "success": 3}
	return (
		severity_order.get(str(item.get("severity") or "info"), 9),
		str(item.get("date") or ""),
		str(item.get("title") or ""),
	)


def _build_point_contextual_actions(pdv_id, user, sensitive_policy):
	is_gh = user_has_any_role(
		user,
		"Gestión Humana",
		"System Manager",
		"HR Selection",
		"HR Labor Relations",
		"HR Training & Wellbeing",
		"HR SST",
	)
	is_jefe = user_has_any_role(user, "Jefe_PDV")
	is_sst = user_has_any_role(user, "HR SST", "GH - SST")
	is_rrll = user_has_any_role(user, "HR Labor Relations", "GH - RRLL")
	is_bienestar = user_has_any_role(user, "HR Training & Wellbeing")
	can_view_sensitive = bool(sensitive_policy.get("effective_allowed"))
	can_operate = bool(is_gh or is_jefe or is_sst or is_rrll or is_bienestar)

	return {
		"can_operate": can_operate,
		"can_view_sensitive": can_view_sensitive,
		"quick_actions": build_dashboard_actions(
			[
				{
					"key": "open_operacion",
					"label": "Abrir Operación Punto",
					"route": "app/operacion_punto_lite",
					"style": "primary",
					"visible": True,
					"context": {"pdv": pdv_id},
				},
				{
					"key": "create_gh_novedad",
					"label": "Registrar Novedad GH",
					"route": "/app/gh-novedad/new",
					"doctype": "GH Novedad",
					"style": "secondary",
					"visible": bool(is_gh or is_jefe),
					"prefill": {"punto": pdv_id},
				},
				{
					"key": "create_sst_alert",
					"label": "Programar Alerta SST",
					"route": "/app/sst-alerta/new",
					"doctype": "SST Alerta",
					"style": "secondary",
					"visible": bool(is_gh or is_sst),
					"prefill": {"punto_venta": pdv_id},
				},
				{
					"key": "create_wellbeing_alert",
					"label": "Registrar Alerta Bienestar",
					"route": "/app/bienestar-alerta/new",
					"doctype": "Bienestar Alerta",
					"style": "secondary",
					"visible": bool(is_gh or is_jefe or is_bienestar),
					"prefill": {"punto_venta": pdv_id},
				},
				{
					"key": "open_rl_view",
					"label": "Abrir Vista RL",
					"route": "app/relaciones_laborales_contratacion",
					"style": "secondary",
					"visible": bool(can_view_sensitive or is_rrll),
					"context": {"pdv": pdv_id},
				},
				{
					"key": "view_documents",
					"label": "Ver Expediente Documental",
					"route": "/app/query-report/Person%20Documents",
					"style": "secondary",
					"visible": can_operate,
					"prefill": {"punto": pdv_id},
				},
			]
		),
		"visibility_context": {
			"user": user,
			"is_gh": bool(is_gh),
			"is_jefe": bool(is_jefe),
			"is_sst": bool(is_sst),
			"is_rrll": bool(is_rrll),
			"is_bienestar": bool(is_bienestar),
		},
	}


def _build_actionable_hub(
	*,
	pdv_id,
	punto,
	headcount,
	faltantes,
	cobertura_pct,
	novedades_activas,
	alertas_sst,
	disciplinarios,
	feedback,
	personas_radar,
	ingresos_formalizados_30d,
	riesgo_operativo_total,
	sensitive_policy,
	user,
):
	widgets = build_dashboard_kpis(
		[
			build_dashboard_kpi(
				"headcount_activo",
				"Headcount activo",
				headcount,
				detail=f"Cobertura {cobertura_pct}% sobre planta autorizada",
				severity="warning" if faltantes > 0 else "info",
				route="app/operacion_punto_lite",
				source="info.kpi_operativo.headcount_activo",
			),
			build_dashboard_kpi(
				"novedades_abiertas",
				"Novedades abiertas",
				len(novedades_activas),
				detail=f"{len(alertas_sst)} alerta(s) SST y {personas_radar} persona(s) en radar",
				severity="danger" if novedades_activas else "info",
				route="app/gh-novedad",
				source="info.kpi_operativo.novedades_activas",
			),
			build_dashboard_kpi(
				"brecha_dotacion",
				"Brecha de dotación",
				max(faltantes, 0),
				detail=f"{riesgo_operativo_total} señal(es) activas para liderazgo del punto",
				severity="warning" if faltantes > 0 else "success",
				route="app/punto_360",
				source="info.kpi_liderazgo.faltantes_dotacion",
			),
			build_dashboard_kpi(
				"ingresos_formalizados_30d",
				"Ingresos formalizados 30d",
				ingresos_formalizados_30d,
				detail=f"Zona {str(getattr(punto, 'zona', '') or '').strip() or 'Sin zona'}",
				severity="info",
				route="app/bandeja_contratacion",
				source="info.kpi_ingreso.ingresos_formalizados_30d",
			),
		]
	)

	feeds = []
	if faltantes > 0:
		feeds.append(
			build_dashboard_alert(
				"Cobertura por debajo de planta autorizada",
				f"Faltan {max(faltantes, 0)} colaborador(es) para llegar a {punto.planta_autorizada}.",
				severity="warning",
				route="app/operacion_punto_lite",
				key="leadership_gap",
				feed="liderazgo",
				date=nowdate(),
				source="kpi_liderazgo",
			)
		)

	for row in (alertas_sst or [])[:3]:
		feeds.append(
			build_dashboard_alert(
				f"Alerta SST {str(_row_value(row, 'name') or '').strip() or 'sin consecutivo'}",
				f"{_row_value(row, 'tipo_alerta', 'Seguimiento')} · {_row_value(row, 'estado', 'Pendiente')}",
				severity="danger" if _row_value(row, "estado") == "Pendiente" else "warning",
				route="app/sst_bandeja",
				key=f"sst_alert_{_row_value(row, 'name')}",
				feed="sst",
				date=_row_value(row, "fecha_programada"),
				source="SST Alerta",
			)
		)

	for row in (novedades_activas or [])[:3]:
		feeds.append(
			build_dashboard_alert(
				f"{_row_value(row, 'tipo_novedad', 'Novedad')} · {_row_value(row, 'empleado_nombres', '')} {_row_value(row, 'empleado_apellidos', '')}".strip(),
				f"Estado {_row_value(row, 'estado', 'Sin estado')} · inicio {_row_value(row, 'fecha_inicio', 'sin fecha')}",
				severity="warning",
				route="app/gh-novedad",
				key=f"novedad_{_row_value(row, 'name')}",
				feed="novedades",
				date=_row_value(row, "fecha_inicio"),
				source="Novedad SST",
			)
		)

	for row in (disciplinarios or [])[:2]:
		feeds.append(
			build_dashboard_alert(
				f"Caso disciplinario {str(_row_value(row, 'name') or '').strip() or 'abierto'}",
				f"{_row_value(row, 'tipo_falta', 'Sin tipo')} · {_row_value(row, 'empleado.nombres', '')} {_row_value(row, 'empleado.apellidos', '')}".strip(),
				severity="danger",
				route="app/relaciones_laborales_contratacion",
				key=f"disciplinario_{_row_value(row, 'name')}",
				feed="rrll",
				date=_row_value(row, "fecha_incidente"),
				source="Caso Disciplinario",
			)
		)

	for row in (feedback or [])[:2]:
		feeds.append(
			build_dashboard_alert(
				f"{row.get('fuente') or 'Bienestar'} · {row.get('name') or 'registro'}",
				f"Valoración {row.get('valoracion', 0)} / 5",
				severity="info",
				route="app/punto_360",
				key=f"feedback_{row.get('name')}",
				feed="bienestar",
				date=row.get("fecha"),
				source=row.get("fuente") or "Bienestar",
			)
		)

	feeds = sorted(feeds, key=_feed_sort_key)[:8]
	contextual_actions = _build_point_contextual_actions(pdv_id, user, sensitive_policy)
	tray_reports = [
		{"module": "seleccion", "label": "Reporte Selección", "route": "app/seleccion_documentos"},
		{"module": "rrll", "label": "Reporte RL / Contratación", "route": "app/bandeja_contratacion"},
		{"module": "sst", "label": "Reporte SST", "route": "app/sst_bandeja"},
		{"module": "operacion", "label": "Reporte Operación", "route": "app/operacion_punto_lite"},
	]

	return {
		"widgets": widgets,
		"feeds": build_dashboard_alerts(feeds, "Sin señales operativas relevantes para este punto."),
		"contextual_actions": contextual_actions,
		"tray_reports": tray_reports,
	}

@frappe.whitelist()
def get_punto_stats(pdv_id):
    if not pdv_id:
        return {}

    # Permission Check
    if not frappe.has_permission("Punto de Venta", "read", pdv_id):
        frappe.throw(_("No tienes permiso para ver este Punto de Venta"))

    # 1. Información Básica
    punto = frappe.get_doc("Punto de Venta", pdv_id)
    user = frappe.session.user

    sensitive_policy = evaluate_dimension_permission(
        "sensitive",
        user=user,
        surface="punto_360",
        context={"pdv_id": pdv_id},
    )
    
    # 2. Headcount (solo activos)
    headcount = frappe.db.count("Ficha Empleado", {
        "pdv": pdv_id,
        "estado": "Activo"
    })

    employee_rows = _employee_rows_for_point(pdv_id)
    empleados_pdv = [str(_row_value(e, "name", "") or "") for e in employee_rows if _row_value(e, "name")]

    # 3. Novedades Activas
    novedades_activas = frappe.get_all(
        "Novedad SST",
        filters={
            "estado": ["in", ["Abierta", "En seguimiento", "Abierto"]],
            "categoria_novedad": "SST",
            "empleado": ["in", empleados_pdv],
        },
        fields=[
            "name",
            "empleado",
            "empleado.nombres as empleado_nombres",
            "empleado.apellidos as empleado_apellidos",
            "tipo_novedad",
            "estado",
            "fecha_inicio",
            "fecha_fin",
            "es_incapacidad",
            "origen_incapacidad",
            "proxima_alerta_fecha",
            "en_radar",
            "ref_doctype",
            "ref_docname",
        ],
    )

    for nov in novedades_activas:
        nov["rrll_handoff_label"] = _handoff_label(nov)
        nov["rrll_handoff_name"] = _row_value(nov, "ref_docname") if _row_value(nov, "ref_doctype") == "GH Novedad" else None
    
    # 4. Casos Disciplinarios Abiertos
    disciplinarios = []
    if sensitive_policy.get("effective_allowed"):
        disciplinarios = frappe.get_all("Caso Disciplinario",
            filters={
                "estado": ["in", ["Abierto", "En Proceso"]],
                 "empleado": ["in", empleados_pdv]
            },
            fields=["name", "empleado.nombres", "empleado.apellidos", "tipo_falta", "fecha_incidente"]
        )
    
    # 5. Casos SST Abiertos (legacy desactivado)
    sst = []

    alertas_sst = frappe.get_all(
        "SST Alerta",
        filters={
            "punto_venta": pdv_id,
            "estado": ["in", ["Pendiente", "Reprogramada", "Enviada"]],
        },
        fields=["name", "novedad", "empleado", "fecha_programada", "tipo_alerta", "estado"],
        order_by="fecha_programada asc",
    )

    no_disponibles = []
    incapacidades_activas_sst = 0
    incapacidades_rrll_handoff = 0
    accidentes_periodo_legacy = 0
    personas_radar = 0
    for nov in novedades_activas:
        if _is_sst_incapacidad(nov):
            incapacidades_activas_sst += 1
            if nov.get("rrll_handoff_name"):
                incapacidades_rrll_handoff += 1
            no_disponibles.append(
                {
                    "empleado": _row_value(nov, "empleado"),
                    "empleado_nombres": _row_value(nov, "empleado_nombres"),
                    "empleado_apellidos": _row_value(nov, "empleado_apellidos"),
                    "fecha_inicio": _row_value(nov, "fecha_inicio"),
                    "fecha_fin": _row_value(nov, "fecha_fin"),
                    "origen_incapacidad": _row_value(nov, "origen_incapacidad"),
                    "rrll_handoff_label": nov.get("rrll_handoff_label"),
                    "rrll_handoff_name": nov.get("rrll_handoff_name"),
                }
            )
        if _row_value(nov, "tipo_novedad") == "Accidente":
            accidentes_periodo_legacy += 1
        if _row_value(nov, "en_radar"):
            personas_radar += 1

    # GH Novedad queda como soporte/handoff, no como fuente canónica de incapacidad operativa.
    accidentes_periodo_gh = frappe.db.count(
        "GH Novedad",
        {
            "punto": pdv_id,
            "tipo": ["in", _novedad_tipo_values("accidente")],
            "fecha_inicio": [">=", add_days(nowdate(), -30)],
        },
    ) if frappe.db.exists("DocType", "GH Novedad") else 0

    incapacidades_activas = incapacidades_activas_sst
    accidentes_periodo = max(accidentes_periodo_legacy, accidentes_periodo_gh)

    ingresos_formalizados_30d = 0
    if frappe.db.exists("DocType", "GH Novedad"):
        ingreso_rows = frappe.get_all(
            "GH Novedad",
            filters={
                "punto": pdv_id,
                "tipo": "Otro",
                "fecha_inicio": [">=", add_days(nowdate(), -30)],
            },
            fields=["descripcion"],
        )
        ingresos_formalizados_30d = sum(
            1 for row in ingreso_rows if "ingreso formalizado" in str(row.get("descripcion") or "").lower()
        )

    # 6. Feedback Reciente (30 días) - fuente nueva de bienestar (sin dependencia Feedback Punto)
    feedback = []

    window_start = add_days(nowdate(), -30)

    def _unique_rows(rows):
        by_name = {}
        for row in rows or []:
            row_name = str(_row_value(row, "name", "") or "")
            if not row_name:
                continue
            by_name[row_name] = row
        return list(by_name.values())

    def _rows_for_punto_or_employee(doctype, date_field, fields):
        if not frappe.db.exists("DocType", doctype):
            return []

        rows = frappe.get_all(
            doctype,
            filters={"punto_venta": pdv_id, date_field: [">=", window_start]},
            fields=fields,
        )
        if empleados_pdv:
            rows += frappe.get_all(
                doctype,
                filters={"ficha_empleado": ["in", empleados_pdv], date_field: [">=", window_start]},
                fields=fields,
            )
        return _unique_rows(rows)

    bienestar_levantamientos_30d = (
        frappe.get_all(
            "Bienestar Levantamiento Punto",
            filters={"punto_venta": pdv_id, "fecha_levantamiento": [">=", window_start]},
            fields=["name", "estado", "fecha_levantamiento", "score_global", "cobertura_participacion"],
        )
        if frappe.db.exists("DocType", "Bienestar Levantamiento Punto")
        else []
    )
    bienestar_seguimientos_30d = _rows_for_punto_or_employee(
        "Bienestar Seguimiento Ingreso",
        "fecha_programada",
        ["name", "estado", "fecha_programada", "fecha_realizacion", "tipo_seguimiento", "score_global"],
    )
    bienestar_evaluaciones_30d = _rows_for_punto_or_employee(
        "Bienestar Evaluacion Periodo Prueba",
        "fecha_evaluacion",
        ["name", "estado", "fecha_evaluacion", "dictamen", "porcentaje_resultado"],
    )
    bienestar_alertas_30d = _rows_for_punto_or_employee(
        "Bienestar Alerta",
        "fecha_alerta",
        ["name", "estado", "fecha_alerta", "tipo_alerta", "prioridad"],
    )
    bienestar_compromisos_30d = _rows_for_punto_or_employee(
        "Bienestar Compromiso",
        "fecha_compromiso",
        ["name", "estado", "fecha_compromiso", "sin_mejora"],
    )

    feedback = [
        {
            "name": _row_value(row, "name"),
            "fecha": _row_value(row, "fecha_programada") or _row_value(row, "fecha_realizacion"),
            "valoracion": round(_to_float(_row_value(row, "score_global", 0), 0) / 20, 2),
            "comentarios": _row_value(row, "observaciones", "") or "",
            "fuente": "Bienestar Seguimiento Ingreso",
        }
        for row in bienestar_seguimientos_30d
    ]
    feedback += [
        {
            "name": _row_value(row, "name"),
            "fecha": _row_value(row, "fecha_levantamiento"),
            "valoracion": round(_to_float(_row_value(row, "score_global", 0), 0) / 20, 2),
            "comentarios": "",
            "fuente": "Bienestar Levantamiento Punto",
        }
        for row in bienestar_levantamientos_30d
    ]
    feedback += [
        {
            "name": _row_value(row, "name"),
            "fecha": _row_value(row, "fecha_evaluacion"),
            "valoracion": round(_to_float(_row_value(row, "porcentaje_resultado", 0), 0) / 20, 2),
            "comentarios": _row_value(row, "dictamen", "") or "",
            "fuente": "Bienestar Evaluacion Periodo Prueba",
        }
        for row in bienestar_evaluaciones_30d
    ]
    feedback = sorted(feedback, key=lambda x: str(x.get("fecha") or ""), reverse=True)[:5]

    levantamientos_realizados_30d = [
        row for row in bienestar_levantamientos_30d if _row_value(row, "estado") in {"Realizado", "Cerrado"}
    ]
    seguimientos_realizados_30d = [
        row for row in bienestar_seguimientos_30d if _row_value(row, "estado") == "Realizado"
    ]
    evaluaciones_dictamen_30d = [
        row
        for row in bienestar_evaluaciones_30d
        if str(_row_value(row, "dictamen") or "").strip().upper() in {"APRUEBA", "NO APRUEBA"}
    ]

    # S4.2 - Wellbeing aggregate (fuente operacional nueva, sin Comentario Bienestar)
    feedback_count_30d = (
        len(levantamientos_realizados_30d)
        + len(seguimientos_realizados_30d)
        + len(evaluaciones_dictamen_30d)
    )
    bienestar_scores_5 = []
    for row in levantamientos_realizados_30d:
        score = _to_float(_row_value(row, "score_global", 0), 0)
        if score > 0:
            bienestar_scores_5.append(round(score / 20, 2))
    for row in seguimientos_realizados_30d:
        score = _to_float(_row_value(row, "score_global", 0), 0)
        if score > 0:
            bienestar_scores_5.append(round(score / 20, 2))
    for row in evaluaciones_dictamen_30d:
        score = _to_float(_row_value(row, "porcentaje_resultado", 0), 0)
        if score > 0:
            bienestar_scores_5.append(round(score / 20, 2))
    feedback_avg_30d = round(sum(bienestar_scores_5) / len(bienestar_scores_5), 2) if bienestar_scores_5 else 0
    feedback_low_30d = len([score for score in bienestar_scores_5 if score <= 2])

    # S7.3 - Climate by point aggregate (fuente operacional nueva)
    clima_visitas_30d = len(levantamientos_realizados_30d)
    probation_aprobado_30d = len([
        row for row in bienestar_evaluaciones_30d if str(_row_value(row, "dictamen") or "").strip().upper() == "APRUEBA"
    ])
    probation_no_aprobado_30d = len([
        row for row in bienestar_evaluaciones_30d if str(_row_value(row, "dictamen") or "").strip().upper() == "NO APRUEBA"
    ])
    bienestar_total_30d = (
        len(bienestar_levantamientos_30d)
        + len(bienestar_seguimientos_30d)
        + len(bienestar_evaluaciones_30d)
        + len(bienestar_alertas_30d)
        + len(bienestar_compromisos_30d)
    )
    clima_cobertura_pct_30d = round((clima_visitas_30d / headcount) * 100, 1) if headcount else 0
    temas_30d = {
        "clima": clima_visitas_30d,
        "infraestructura": len([
            row for row in bienestar_alertas_30d if _row_value(row, "tipo_alerta") == "Levantamiento de punto"
        ]),
        "dotacion": len([
            row for row in bienestar_seguimientos_30d if str(_row_value(row, "tipo_seguimiento") or "") in {"5", "10", "30/45"}
        ]),
        "otro": len([
            row for row in bienestar_alertas_30d if _row_value(row, "tipo_alerta") == "Otro"
        ]) + len(bienestar_compromisos_30d),
    }

    # S4.2 - Training aggregate (additive, resilient when LMS is unavailable)
    lms_available = frappe.db.exists("DocType", "LMS Enrollment")
    formacion_total = headcount
    formacion_completados = 0
    formacion_en_progreso = 0
    formacion_sin_iniciar = formacion_total
    formacion_pct = 0
    if lms_available and formacion_total:
        user_emails = [
            (_row_value(row, "email", "") or "").strip()
            for row in frappe.get_all(
                "Ficha Empleado",
                filters={"pdv": pdv_id, "estado": "Activo"},
                fields=["email"],
            )
            if (_row_value(row, "email", "") or "").strip()
        ]
        if user_emails:
            enrollments = frappe.get_all(
                "LMS Enrollment",
                filters={"member": ["in", user_emails]},
                fields=["member", "progress"],
            )
            by_member = {
                str(_row_value(r, "member", "") or ""): float(_row_value(r, "progress", 0) or 0)
                for r in enrollments
            }
            for user_email in user_emails:
                progress = by_member.get(user_email, 0)
                if progress >= 100:
                    formacion_completados += 1
                elif progress > 0:
                    formacion_en_progreso += 1
            formacion_sin_iniciar = max(formacion_total - formacion_completados - formacion_en_progreso, 0)
            formacion_pct = round((formacion_completados / formacion_total) * 100, 1) if formacion_total else 0

    # S4.3 - Contextual navigation metadata
    navigation_context = {
        "persona_route": "persona_360",
        "persona_route_options": {"empleado": "<employee_id>", "pdv": pdv_id},
        "expediente_route": "query-report/Person Documents",
        "expediente_route_options": {"persona": "<employee_id>"},
    }

    novedades_activas_count = len(novedades_activas)
    alertas_pendientes_count = len(alertas_sst)
    disciplinarios_abiertos_count = len(disciplinarios)
    sst_abiertos_count = len(sst)
    cobertura_pct = round((headcount / punto.planta_autorizada) * 100, 2) if punto.planta_autorizada else 0
    riesgo_operativo_total = personas_radar + disciplinarios_abiertos_count + alertas_pendientes_count
    faltantes = max((punto.planta_autorizada or 0) - headcount, 0)
    point_employee_rows = _build_point_employee_summary(employee_rows, novedades_activas)
    actionable_hub = _build_actionable_hub(
        pdv_id=pdv_id,
        punto=punto,
        headcount=headcount,
        faltantes=faltantes,
        cobertura_pct=cobertura_pct,
        novedades_activas=novedades_activas,
        alertas_sst=alertas_sst,
        disciplinarios=disciplinarios,
        feedback=feedback,
        personas_radar=personas_radar,
        ingresos_formalizados_30d=ingresos_formalizados_30d,
        riesgo_operativo_total=riesgo_operativo_total,
        sensitive_policy=sensitive_policy,
        user=user,
    )

    return {
        "info": {
            "nombre": punto.nombre_pdv,
            "zona": punto.zona,
            "planta_autorizada": punto.planta_autorizada,
            "headcount": headcount,
            "faltantes": punto.planta_autorizada - headcount,
            "kpi_operativo": {
                "headcount_activo": headcount,
                "planta_autorizada": punto.planta_autorizada,
                "cobertura_dotacion_pct": cobertura_pct,
                "novedades_activas": novedades_activas_count,
                "alertas_pendientes": alertas_pendientes_count,
                "disciplinarios_abiertos": disciplinarios_abiertos_count,
                "sst_abiertos": sst_abiertos_count,
                "riesgo_operativo_total": riesgo_operativo_total,
            },
            "kpi_sst": {
                "accidentes_periodo": accidentes_periodo,
                "incapacidades_activas": incapacidades_activas,
                "incapacidades_rrll_handoff": incapacidades_rrll_handoff,
                "personas_radar": personas_radar,
                "alertas_pendientes": len(alertas_sst),
                "fuente_canonica_incapacidad": "Novedad SST",
                "_fuentes": {
                    "incapacidades_legacy": incapacidades_activas_sst,
                    "incapacidades_gh_novedad": incapacidades_rrll_handoff,
                    "accidentes_legacy": accidentes_periodo_legacy,
                    "accidentes_gh_novedad": accidentes_periodo_gh,
                },
            },
            "kpi_ingreso": {
                "ingresos_formalizados_30d": ingresos_formalizados_30d,
            },
            "kpi_liderazgo": {
                "faltantes_dotacion": faltantes,
                "cobertura_dotacion_pct": cobertura_pct,
                "ingresos_formalizados_30d": ingresos_formalizados_30d,
                "riesgo_operativo_total": riesgo_operativo_total,
                "personas_radar": personas_radar,
            },
            "kpi_bienestar": {
                "feedback_30d": feedback_count_30d,
                "valoracion_promedio_30d": feedback_avg_30d,
                "feedback_riesgo_30d": feedback_low_30d,
            },
            "kpi_clima": {
                "bienestar_registros_30d": bienestar_total_30d,
                "visitas_clima_30d": clima_visitas_30d,
                "cobertura_clima_pct_30d": clima_cobertura_pct_30d,
                "periodo_prueba_aprobado_30d": probation_aprobado_30d,
                "periodo_prueba_no_aprobado_30d": probation_no_aprobado_30d,
                "temas_30d": temas_30d,
            },
            "kpi_formacion": {
                "lms_disponible": bool(lms_available),
                "total_colaboradores": formacion_total,
                "completados": formacion_completados,
                "en_progreso": formacion_en_progreso,
                "sin_iniciar": formacion_sin_iniciar,
                "porcentaje_completud": formacion_pct,
            },
        },
        "novedades": novedades_activas,
        "disciplinarios": disciplinarios,
        "sst": sst,
        "feedback": feedback,
        "no_disponibles": no_disponibles,
        "alertas_sst": alertas_sst,
        "empleados": point_employee_rows,
        "navigation_context": navigation_context,
        "actionable_hub": actionable_hub,
    }

@frappe.whitelist()
def get_all_puntos_overview():
    puntos = frappe.get_all("Punto de Venta", fields=["name", "nombre_pdv", "zona", "planta_autorizada"])
    summary_list = []
    for p in puntos:
        if not frappe.has_permission("Punto de Venta", "read", p.name):
            continue

        headcount = frappe.db.count("Ficha Empleado", {"pdv": p.name, "estado": "Activo"})
        # Simplified query for speed
        novedades_legacy = frappe.db.sql("""
            SELECT count(*) FROM `tabNovedad SST` n
            INNER JOIN `tabFicha Empleado` e ON n.empleado = e.name
            WHERE n.estado = 'Abierto' AND e.pdv = %s
        """, p.name)[0][0]

        novedades_gh = 0
        if frappe.db.exists("DocType", "GH Novedad"):
            novedades_gh = frappe.db.count(
                "GH Novedad",
                {
                    "punto": p.name,
                    "estado": ["in", ["Recibida", "En gestión", "Pendiente info"]],
                },
            )

        novedades = max(novedades_legacy, novedades_gh)
        
        summary_list.append({
            "name": p.name,
            "title": p.nombre_pdv,
            "zona": p.zona,
            "headcount": f"{headcount}/{p.planta_autorizada}",
            "novedades": novedades
        })

    return summary_list


def _novedad_tipo_values(clave):
	return list(dict.fromkeys(NOVEDAD_TIPO_MAP.get(clave, [])))


@frappe.whitelist()
def get_capacitacion_punto(punto_venta):
	"""Legacy compatibility endpoint for passive training history.

	Operational training flows were retired from Punto 360.
	Use LMS endpoints (`get_formacion_catalog_assignments`, `get_formacion_compliance`)
	for active management.
	"""
	if not punto_venta:
		return {
			"deprecated": True,
			"status": "decommissioned",
			"integration_status": "missing_point",
			"empleados": [],
			"resumen": {"total": 0, "completados": 0, "en_progreso": 0, "sin_iniciar": 0, "porcentaje_completud": 0},
		}

	compliance = get_formacion_compliance(punto_venta)
	mandatory_total = int((compliance.get("resumen") or {}).get("mandatory_total") or 0)
	mandatory_completed = int((compliance.get("resumen") or {}).get("mandatory_completed") or 0)
	mandatory_pending = int((compliance.get("resumen") or {}).get("mandatory_pending") or 0)
	progress_pct = float((compliance.get("resumen") or {}).get("cumplimiento_pct") or 0)

	return {
		"deprecated": True,
		"status": "decommissioned",
		"integration_status": compliance.get("integration_status") or ("active" if compliance.get("lms_disponible") else "degraded_no_lms"),
		"empleados": [],
		"resumen": {
			"total": mandatory_total,
			"completados": mandatory_completed,
			"en_progreso": 0,
			"sin_iniciar": mandatory_pending,
			"porcentaje_completud": progress_pct,
		},
		"message": "Entrypoint legacy de Capacitación retirado del flujo operativo. Disponible solo como fallback histórico.",
		"next_step": "Usar get_formacion_catalog_assignments y get_formacion_compliance.",
	}


@frappe.whitelist()
def get_formacion_catalog_assignments(punto_venta):
	"""S8.1: additive training catalog assignment by cargo/role/point."""
	if not punto_venta:
		return {"lms_disponible": False, "empleados": [], "resumen": {"total_colaboradores": 0, "asignaciones_obligatorias": 0, "asignaciones_recomendadas": 0}}

	if not frappe.has_permission("Punto de Venta", "read", punto_venta):
		frappe.throw(_("No tienes permiso para ver este Punto de Venta"))

	punto = frappe.get_doc("Punto de Venta", punto_venta)
	lms_disponible = bool(frappe.db.exists("DocType", "LMS Enrollment"))

	empleados = _employee_rows_for_point(punto_venta)

	rows = []
	mandatory_count = 0
	recommended_count = 0
	for emp in empleados:
		assignments = _assignment_for_employee(emp, punto)
		mandatory_count += len([a for a in assignments if a.get("assignment_type") == "Obligatorio"])
		recommended_count += len([a for a in assignments if a.get("assignment_type") == "Recomendado"])
		rows.append(
			{
				"empleado": _row_value(emp, "name"),
				"nombre": f"{_row_value(emp, 'nombres', '') or ''} {_row_value(emp, 'apellidos', '') or ''}".strip(),
				"cargo": _row_value(emp, "cargo", "") or "",
				"asignaciones": assignments,
			}
		)

	return {
		"lms_disponible": lms_disponible,
		"empleados": rows,
		"resumen": {
			"total_colaboradores": len(rows),
			"asignaciones_obligatorias": mandatory_count,
			"asignaciones_recomendadas": recommended_count,
		},
	}


@frappe.whitelist()
def get_formacion_compliance(punto_venta):
	"""S8.2: compliance and expiration-style alerts for mandatory training."""
	if not punto_venta:
		return {
			"lms_disponible": False,
			"integration_status": "missing_point",
			"resumen": {"mandatory_total": 0, "mandatory_completed": 0, "mandatory_pending": 0, "cumplimiento_pct": 0},
			"alertas": [],
		}

	if not frappe.has_permission("Punto de Venta", "read", punto_venta):
		frappe.throw(_("No tienes permiso para ver este Punto de Venta"))

	assignments_data = get_formacion_catalog_assignments(punto_venta)
	lms_disponible = bool(assignments_data.get("lms_disponible"))

	if not lms_disponible:
		return {
			"lms_disponible": False,
			"integration_status": "degraded_no_lms",
			"resumen": {"mandatory_total": 0, "mandatory_completed": 0, "mandatory_pending": 0, "cumplimiento_pct": 0},
			"alertas": [],
		}

	empleados = _employee_rows_for_point(punto_venta)
	employee_by_id = {str(_row_value(e, "name", "") or ""): e for e in empleados}
	employee_by_email = {(_row_value(e, "email", "") or "").strip(): e for e in empleados if (_row_value(e, "email", "") or "").strip()}
	user_emails = list(employee_by_email.keys())

	enrollments = frappe.get_all(
		"LMS Enrollment",
		filters={"member": ["in", user_emails]} if user_emails else {"name": ["=", ""]},
		fields=["member", "course", "progress"],
	)
	progress_by_member_course = {
		(str(_row_value(row, "member", "") or ""), str(_row_value(row, "course", "") or "")): float(_row_value(row, "progress", 0) or 0)
		for row in enrollments
	}

	mandatory_total = 0
	mandatory_completed = 0
	alertas = []

	for row in assignments_data.get("empleados", []):
		emp_id = row.get("empleado")
		emp_row = employee_by_id.get(str(emp_id or ""), {})
		email = (_row_value(emp_row, "email", "") or "").strip()
		for assignment in row.get("asignaciones", []):
			if assignment.get("assignment_type") != "Obligatorio":
				continue
			mandatory_total += 1
			course = assignment.get("course")
			progress = progress_by_member_course.get((email, course), 0)
			if progress >= 100:
				mandatory_completed += 1
			else:
				alertas.append(
					{
						"empleado": emp_id,
						"curso": course,
						"curso_label": assignment.get("label"),
						"estado": "Vencida" if progress == 0 else "Pendiente",
						"detalle": "Formación obligatoria pendiente de cumplimiento",
					}
				)

	mandatory_pending = max(mandatory_total - mandatory_completed, 0)
	cumplimiento_pct = round((mandatory_completed / mandatory_total) * 100, 1) if mandatory_total else 0

	return {
		"lms_disponible": True,
		"integration_status": "active",
		"resumen": {
			"mandatory_total": mandatory_total,
			"mandatory_completed": mandatory_completed,
			"mandatory_pending": mandatory_pending,
			"cumplimiento_pct": cumplimiento_pct,
		},
		"alertas": alertas,
	}


@frappe.whitelist()
def get_lms_integration_contract():
	"""S8.3: LMS-ready technical contract without breaking current flow."""
	lms_disponible = bool(frappe.db.exists("DocType", "LMS Enrollment"))
	return {
		"status": "active" if lms_disponible else "degraded",
		"lms_disponible": lms_disponible,
		"provider": "frappe_lms",
		"version": "v1",
		"capabilities": {
			"assignments_catalog": True,
			"compliance_alerts": True,
			"persona_punto_rollups": True,
			"webhook_ingestion_ready": False,
		},
		"endpoints": {
			"catalog_assignments": "hubgh.hubgh.page.punto_360.punto_360.get_formacion_catalog_assignments",
			"compliance": "hubgh.hubgh.page.punto_360.punto_360.get_formacion_compliance",
		},
	}


def _get_total_lecciones(course_name):
	cache_key = f"hubgh_lms_total_lecciones::{course_name}"
	cached = frappe.cache().get_value(cache_key)
	if cached is not None:
		return int(cached)

	capitulos = frappe.get_all("Course Chapter", filters={"course": course_name}, pluck="name")
	if not capitulos:
		frappe.cache().set_value(cache_key, 0, expires_in_sec=3600)
		return 0

	total = frappe.db.count("Course Lesson", {"chapter": ["in", capitulos]})
	frappe.cache().set_value(cache_key, total, expires_in_sec=3600)
	return total
