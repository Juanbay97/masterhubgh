import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate


def _label_from_parts(*parts):
	return " ".join(str(part).strip() for part in parts if part).strip()


def _compact_text(value, max_length=72):
	text = " ".join(str(value or "").split()).strip()
	if not text:
		return ""
	if len(text) <= max_length:
		return text
	return f"{text[: max_length - 3].rstrip()}..."


def _build_user_label_map(*user_groups):
	user_ids = sorted({user_id for group in user_groups for user_id in (group or []) if user_id})
	if not user_ids:
		return {}

	rows = frappe.get_all(
		"User",
		filters={"name": ["in", user_ids]},
		fields=["name", "full_name"],
		limit_page_length=len(user_ids),
	)
	return {row.get("name"): row.get("full_name") or row.get("name") for row in rows}


def _resolve_user_label(user_id, user_labels):
	return user_labels.get(user_id) or user_id or "Sin responsable"


def _build_handoff_label(row):
	if row.get("ref_doctype") == "GH Novedad" and row.get("ref_docname"):
		return f"Traslado RRLL: {row.get('rrll_handoff_tipo') or row.get('ref_docname')}"
	return "Sin traslado RRLL"


def _build_gh_novedad_label_map(*name_groups):
	names = sorted({name for group in name_groups for name in (group or []) if name})
	if not names:
		return {}

	rows = frappe.get_all(
		"GH Novedad",
		filters={"name": ["in", names]},
		fields=["name", "tipo", "estado"],
		limit_page_length=len(names),
	)
	return {
		row.get("name"): row.get("tipo") or row.get("estado") or row.get("name")
		for row in rows
	}


def _resolve_exam_contract_error(exc):
	message = str(exc or "").strip().lower()
	if isinstance(exc, frappe.PermissionError) or "no autorizado" in message:
		return "deny", "access_denied"
	if "doctype" in message and "no existe" in message:
		return "precondition_failed", "doctype_missing"
	if "can't connect" in message or "operationalerror" in message or "database" in message:
		return "degraded", "infrastructure_unavailable"
	return "degraded", "upstream_error"


def _decorate_sst_alert_row(row, user_labels):
	r = dict(row)
	r["empleado_label"] = _label_from_parts(r.get("empleado_nombres"), r.get("empleado_apellidos")) or r.get("empleado") or "Sin empleado"
	r["punto_venta_label"] = r.get("punto_venta_nombre") or r.get("punto_venta") or "Sin punto"
	r["responsable_label"] = r.get("asignado_a_nombre") or _resolve_user_label(r.get("asignado_a"), user_labels)
	r["tipo_resumen"] = f"{r.get('tipo_alerta') or 'Alerta'} · {r.get('estado') or 'Pendiente'}"
	r["alerta_label"] = _compact_text(r.get("mensaje")) or r.get("tipo_alerta") or "Alerta SST"
	r["novedad_label"] = (
		_compact_text(r.get("novedad_titulo_resumen")) or r.get("novedad_tipo_novedad") or r.get("novedad") or "Sin novedad vinculada"
	)
	return r


def _decorate_sst_novedad_row(row, user_labels, gh_novedad_labels):
	r = dict(row)
	r["empleado_label"] = _label_from_parts(r.get("empleado_nombres"), r.get("empleado_apellidos")) or r.get("empleado") or "Sin empleado"
	r["punto_venta_label"] = r.get("punto_venta_nombre") or r.get("punto_venta") or "Sin punto"
	r["responsable_label"] = _resolve_user_label(r.get("owner"), user_labels)
	r["tipo_resumen"] = (
		r.get("titulo_resumen")
		or r.get("descripcion_resumen")
		or f"{r.get('tipo_novedad') or 'Novedad'} · {r.get('estado') or 'Abierta'}"
	)
	r["rrll_handoff_tipo"] = gh_novedad_labels.get(r.get("ref_docname")) if r.get("ref_doctype") == "GH Novedad" else None
	r["rrll_handoff_label"] = _build_handoff_label(r)
	r["rrll_handoff_name"] = r.get("ref_docname") if r.get("ref_doctype") == "GH Novedad" else None
	return r


@frappe.whitelist()
def get_sst_bandeja(punto_venta=None, categoria=None, responsable=None):
	today = getdate(nowdate())

	alertas = frappe.get_all(
		"SST Alerta",
		filters={"estado": ["in", ["Pendiente", "Reprogramada", "Enviada"]]},
		fields=[
			"name",
			"novedad",
			"novedad.titulo_resumen as novedad_titulo_resumen",
			"novedad.tipo_novedad as novedad_tipo_novedad",
			"empleado",
			"empleado.nombres as empleado_nombres",
			"empleado.apellidos as empleado_apellidos",
			"punto_venta",
			"punto_venta.nombre_pdv as punto_venta_nombre",
			"fecha_programada",
			"estado",
			"tipo_alerta",
			"asignado_a",
			"asignado_a.full_name as asignado_a_nombre",
			"mensaje",
		],
		order_by="fecha_programada asc",
	)
	user_labels = _build_user_label_map([row.get("asignado_a") for row in alertas])

	alertas_hoy, alertas_vencidas, alertas_proximas = [], [], []
	cola_alertas = []
	for row in alertas:
		if punto_venta and row.punto_venta != punto_venta:
			continue
		if responsable and row.asignado_a != responsable:
			continue

		fecha = getdate(row.fecha_programada) if row.fecha_programada else None
		urgencia = "Sin fecha"
		bucket = None
		if fecha:
			if fecha < today:
				urgencia = "Vencida"
				bucket = alertas_vencidas
			elif fecha == today:
				urgencia = "Hoy"
				bucket = alertas_hoy
			else:
				urgencia = "Proxima"
				bucket = alertas_proximas

		alerta_row = _decorate_sst_alert_row({**row, "urgencia": urgencia}, user_labels)
		if bucket is not None:
			bucket.append(alerta_row)

		cola_alertas.append(alerta_row)

	novedades_abiertas = frappe.get_all(
		"Novedad SST",
		filters={
			"estado": ["in", ["Abierta", "En seguimiento", "Abierto"]],
			"categoria_novedad": "SST",
		},
		fields=[
			"name",
			"owner",
			"empleado",
			"empleado.nombres as empleado_nombres",
			"empleado.apellidos as empleado_apellidos",
			"punto_venta",
			"punto_venta.nombre_pdv as punto_venta_nombre",
			"tipo_novedad",
			"estado",
			"prioridad",
			"titulo_resumen",
			"descripcion_resumen",
			"proxima_alerta_fecha",
			"en_radar",
			"categoria_seguimiento",
			"tiene_recomendaciones",
			"es_incapacidad",
			"ref_doctype",
			"ref_docname",
		],
		order_by="`tabNovedad SST`.modified desc",
	)

	if punto_venta:
		novedades_abiertas = [n for n in novedades_abiertas if n.punto_venta == punto_venta]
	user_labels.update(_build_user_label_map([row.get("owner") for row in novedades_abiertas]))
	gh_novedad_labels = _build_gh_novedad_label_map(
		[row.get("ref_docname") for row in novedades_abiertas if row.get("ref_doctype") == "GH Novedad"]
	)
	novedades_abiertas = [_decorate_sst_novedad_row(row, user_labels, gh_novedad_labels) for row in novedades_abiertas]

	def _is_incapacidad(row):
		return row.get("es_incapacidad") or row.get("tipo_novedad") in {
			"Incapacidad",
			"Incapacidad por enfermedad general",
		}

	accidentes = [n for n in novedades_abiertas if n.get("tipo_novedad") == "Accidente"]
	incapacidades = [n for n in novedades_abiertas if _is_incapacidad(n)]
	radar = [n for n in novedades_abiertas if n.get("en_radar")]

	if categoria:
		radar = [r for r in radar if r.get("categoria_seguimiento") == categoria]

	resumen_examenes = {
		"pendientes": 0,
		"historico": 0,
		"ruta": "/app/sst_examenes_medicos",
		"status": "ok",
		"reason": "ready",
	}
	try:
		from hubgh.hubgh.page.sst_examenes_medicos.sst_examenes_medicos import (
			list_medical_exam_candidates,
			list_medical_exam_history,
		)

		pendientes = list_medical_exam_candidates() or []
		historico = list_medical_exam_history() or []
		resumen_examenes["pendientes"] = len(pendientes)
		resumen_examenes["historico"] = len(historico)
	except Exception as exc:
		status, reason = _resolve_exam_contract_error(exc)
		resumen_examenes["status"] = status
		resumen_examenes["reason"] = reason

	return {
		"alertas_hoy": alertas_hoy,
		"alertas_vencidas": alertas_vencidas,
		"alertas_proximas": alertas_proximas,
		"novedades_abiertas": novedades_abiertas,
		"aforados": radar,
		"cola_alertas": cola_alertas,
		"cola_novedades": novedades_abiertas,
		"cola_accidentes": accidentes,
		"cola_incapacidades": incapacidades,
		"cola_radar": radar,
		"resumen_examenes": resumen_examenes,
		"kpis": {
			"total_alertas": len(cola_alertas),
			"alertas_vencidas": len(alertas_vencidas),
			"alertas_hoy": len(alertas_hoy),
			"novedades_abiertas": len(novedades_abiertas),
			"accidentes_abiertos": len(accidentes),
			"incapacidades_activas": len(incapacidades),
			"casos_radar": len(radar),
			"examenes_pendientes": resumen_examenes["pendientes"],
			"fuente_canonica_incapacidad": "Novedad SST",
		},
	}


@frappe.whitelist()
def atender_alerta(alerta_name, reprogramar_fecha=None, comentario=None, cerrar=False):
    if not alerta_name:
        frappe.throw(_("Falta alerta_name"))

    alerta = frappe.get_doc("SST Alerta", alerta_name)
    novedad = frappe.get_doc("Novedad SST", alerta.novedad)

    if comentario:
        novedad.append(
            "seguimientos",
            {
                "fecha_seguimiento": now_datetime(),
                "tipo_seguimiento": "Otro",
                "detalle": comentario,
                "estado_resultante": "requiere acción" if not cerrar else "cerrar",
                "responsable": frappe.session.user,
                "proxima_accion_fecha": reprogramar_fecha,
            },
        )

    if cerrar:
        alerta.estado = "Atendida"
        alerta.atendida_en = now_datetime()
        novedad.alerta_activa = 0
    elif reprogramar_fecha:
        alerta.estado = "Reprogramada"
        alerta.fecha_programada = reprogramar_fecha
        novedad.proxima_alerta_fecha = reprogramar_fecha
        novedad.alerta_activa = 1
    else:
        alerta.estado = "Atendida"
        alerta.atendida_en = now_datetime()

    alerta.save(ignore_permissions=True)
    novedad.save(ignore_permissions=True)
    return {"ok": True}
