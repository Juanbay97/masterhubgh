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


# T4: _is_incapacidad with explicit Accidente guard
def _is_incapacidad(row):
	"""Return True only for genuine incapacidad rows.

	Explicit guard: tipo_novedad == "Accidente" always returns False,
	regardless of es_incapacidad flag, to prevent bleed-over into cola_incapacidades.
	"""
	if row.get("tipo_novedad") == "Accidente":
		return False
	return row.get("es_incapacidad") or row.get("tipo_novedad") in {
		"Incapacidad",
		"Incapacidad por enfermedad general",
	}


# T6: Bulk queue helpers — single frappe.get_all per helper (no N+1)

def _build_cola_recomendaciones_medicas(novedad_names):
	"""Return active seguimientos with tipo_seguimiento == 'Recomendación médica'.

	Uses a single bulk IN query keyed on parent to avoid N+1.
	"""
	if not novedad_names:
		return []

	rows = frappe.get_all(
		"SST Seguimiento",
		filters={
			"parent": ["in", novedad_names],
			"parentfield": "seguimientos",
			"tipo_seguimiento": "Recomendación médica",
			"estado_resultante": ["!=", "cerrar"],
		},
		fields=["name", "parent", "fecha_seguimiento", "tipo_seguimiento", "detalle", "estado_resultante"],
	)
	for r in rows:
		r["novedad"] = r.get("parent")
	return rows


def _build_cola_prorrogas_pendientes(novedad_names):
	"""Return non-closed prorrogas_incapacidad child rows.

	Uses a single bulk IN query keyed on parent to avoid N+1.
	"""
	if not novedad_names:
		return []

	rows = frappe.get_all(
		"SST Seguimiento",
		filters={
			"parent": ["in", novedad_names],
			"parentfield": "prorrogas_incapacidad",
			"estado_resultante": ["!=", "cerrar"],
		},
		fields=["name", "parent", "fecha_seguimiento", "tipo_seguimiento", "detalle", "estado_resultante"],
	)
	for r in rows:
		r["novedad"] = r.get("parent")
	return rows


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

	# T5: Extended fields list — adds causa_evento, origen_incapacidad,
	#     accidente_tuvo_incapacidad, prorroga
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
			# T5 new fields
			"causa_evento",
			"origen_incapacidad",
			"accidente_tuvo_incapacidad",
			"prorroga",
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

	# T7: Explicit classification — ORDER MATTERS: Accidente first, then Incapacidad
	# (first match wins; _is_incapacidad internally rejects Accidente rows so sets are mutually exclusive)
	accidentes = [n for n in novedades_abiertas if n.get("tipo_novedad") == "Accidente"]
	incapacidades = [n for n in novedades_abiertas if _is_incapacidad(n)]
	radar = [n for n in novedades_abiertas if n.get("en_radar")]
	cola_novedades_general = [
		n for n in novedades_abiertas
		if n.get("tipo_novedad") != "Accidente"
		and not _is_incapacidad(n)
		and not n.get("en_radar")
	]

	if categoria:
		radar = [r for r in radar if r.get("categoria_seguimiento") == categoria]

	# T6: Build bulk queue helpers (single query each, no N+1)
	novedad_names = [n.get("name") for n in novedades_abiertas if n.get("name")]
	cola_recomendaciones = _build_cola_recomendaciones_medicas(novedad_names)
	cola_prorrogas_pendientes = _build_cola_prorrogas_pendientes(novedad_names)

	# cola_examenes_pendientes — Citas en estado activo (Pendiente Agendamiento o Agendada)
	citas_activas = frappe.get_all(
		"Cita Examen Medico",
		filters={"estado": ["in", ["Pendiente Agendamiento", "Agendada"]]},
		fields=["name", "candidato", "ips", "fecha_cita", "hora_cita", "estado", "token"],
	)
	# Bulk-fetch candidato nombre para evitar N+1
	candidato_names = list({r.get("candidato") for r in citas_activas if r.get("candidato")})
	candidato_nombre_map = {}
	if candidato_names:
		candidato_rows = frappe.get_all(
			"Candidato",
			filters={"name": ["in", candidato_names]},
			fields=["name", "nombres", "primer_apellido"],
			limit_page_length=len(candidato_names),
		)
		for cr in candidato_rows:
			label = " ".join(filter(None, [cr.get("nombres"), cr.get("primer_apellido")])).strip()
			candidato_nombre_map[cr.get("name")] = label or cr.get("name")
	for cita in citas_activas:
		cita["candidato_nombre"] = candidato_nombre_map.get(cita.get("candidato"), cita.get("candidato") or "")

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
		# T7: cola_novedades is now the catch-all (excludes accidentes, incapacidades, radar)
		"cola_novedades": cola_novedades_general,
		"cola_accidentes": accidentes,
		"cola_incapacidades": incapacidades,
		"cola_radar": radar,
		# T6: new queue keys
		"cola_recomendaciones": cola_recomendaciones,
		"cola_prorrogas_pendientes": cola_prorrogas_pendientes,
		# Batch 5: citas de examen médico activas (Pendiente Agendamiento + Agendada)
		"cola_examenes_pendientes": citas_activas,
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
			# T6: new KPI keys
			"recomendaciones_activas": len(cola_recomendaciones),
			"prorrogas_pendientes": len(cola_prorrogas_pendientes),
			# Batch 5
			"citas_examen_activas": len(citas_activas),
		},
	}


# T8: get_caso_completo — whitelisted endpoint for caso unificado drawer
@frappe.whitelist()
def get_caso_completo(novedad_name):
	"""Return unified case view: parent fields + chronologically-sorted children.

	Raises frappe.PermissionError if caller lacks SST-related roles.
	Returns rrll_handoff as None if not escalated, or {name, cola_destino, estado}
	if escalated.

	Date sorting note: fecha_seguimiento is Datetime ("YYYY-MM-DD HH:MM:SS"),
	fecha_programada is Date ("YYYY-MM-DD"). We pad Date values to midnight
	("YYYY-MM-DD 00:00:00") before sorting so cross-type comparison is correct.
	"""
	if not novedad_name:
		frappe.throw(_("Falta novedad_name"))

	roles = set(frappe.get_roles() or [])
	allowed_roles = {"System Manager", "Gestión Humana", "HR SST", "SST", "GH - SST", "GH - RRLL"}
	if not roles.intersection(allowed_roles) and not frappe.has_permission("Novedad SST", "read", novedad_name):
		frappe.throw(_("No tienes permisos para ver este caso SST"), frappe.PermissionError)

	novedad = frappe.get_doc("Novedad SST", novedad_name)

	prorrogas = sorted(
		frappe.get_all(
			"SST Seguimiento",
			filters={"parent": novedad_name, "parentfield": "prorrogas_incapacidad"},
			fields=["name", "fecha_seguimiento", "tipo_seguimiento", "detalle", "estado_resultante"],
		),
		key=lambda x: x.get("fecha_seguimiento") or "",
	)

	seguimientos = sorted(
		frappe.get_all(
			"SST Seguimiento",
			filters={"parent": novedad_name, "parentfield": "seguimientos"},
			fields=["name", "fecha_seguimiento", "tipo_seguimiento", "detalle", "estado_resultante"],
		),
		key=lambda x: x.get("fecha_seguimiento") or "",
	)

	# Pad Date field to Datetime string for consistent cross-type sort with fecha_seguimiento
	raw_alertas = frappe.get_all(
		"SST Alerta",
		filters={"novedad": novedad_name},
		fields=["name", "fecha_programada", "tipo_alerta", "estado", "mensaje"],
	)
	for a in raw_alertas:
		fp = a.get("fecha_programada") or ""
		# Pad bare Date strings (10 chars) to midnight Datetime for sort consistency
		if fp and len(str(fp)) == 10:
			a["fecha_programada"] = f"{fp} 00:00:00"
	alertas = sorted(raw_alertas, key=lambda x: x.get("fecha_programada") or "")

	rrll_handoff = None
	if getattr(novedad, "ref_doctype", None) == "GH Novedad" and getattr(novedad, "ref_docname", None):
		handoff_data = frappe.db.get_value(
			"GH Novedad",
			novedad.ref_docname,
			["name", "cola_destino", "estado"],
			as_dict=True,
		)
		if handoff_data:
			rrll_handoff = handoff_data

	return {
		"parent": novedad_name,
		"prorrogas": prorrogas,
		"seguimientos": seguimientos,
		"alertas": alertas,
		"rrll_handoff": rrll_handoff,
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


@frappe.whitelist()
def sst_accion_cita(
	cita_name,
	accion,
	concepto=None,
	motivo=None,
	instrucciones=None,
):
	"""
	Registra el resultado de una Cita Examen Medico desde la bandeja SST.

	Acciones soportadas:
	  - realizada        → set_exam_outcome con estado="Realizada" y concepto
	  - aplazada         → set_exam_outcome con estado="Aplazada", motivo e instrucciones
	  - no_asistio_rebook → set_exam_outcome con estado="No Asistió", action="rebook"
	  - no_asistio_close → set_exam_outcome con estado="No Asistió", action="close"

	Requiere rol HR SST.

	Returns:
		{"ok": True, "cita": cita_name}

	Raises:
		frappe.PermissionError: Si el usuario no tiene rol HR SST.
		frappe.ValidationError: Si acción no es válida o cita_name no existe.
	"""
	if not cita_name:
		frappe.throw(_("Falta cita_name"), frappe.ValidationError)

	roles = set(frappe.get_roles() or [])
	allowed_roles = {"HR SST", "System Manager"}
	if not roles.intersection(allowed_roles):
		frappe.throw(
			_("Solo usuarios con rol HR SST pueden registrar resultados de exámenes médicos."),
			frappe.PermissionError,
		)

	ACCIONES_VALIDAS = {"realizada", "aplazada", "no_asistio_rebook", "no_asistio_close"}
	accion = (accion or "").strip().lower()
	if accion not in ACCIONES_VALIDAS:
		frappe.throw(
			_("Acción inválida. Valores permitidos: realizada, aplazada, no_asistio_rebook, no_asistio_close."),
			frappe.ValidationError,
		)

	from hubgh.hubgh.examen_medico.cita_service import set_exam_outcome

	if accion == "realizada":
		set_exam_outcome(
			cita_name=cita_name,
			estado="Realizada",
			concepto=concepto,
		)
	elif accion == "aplazada":
		set_exam_outcome(
			cita_name=cita_name,
			estado="Aplazada",
			motivo=motivo,
			instrucciones=instrucciones,
		)
	elif accion == "no_asistio_rebook":
		set_exam_outcome(
			cita_name=cita_name,
			estado="No Asistió",
			action="rebook",
		)
	elif accion == "no_asistio_close":
		set_exam_outcome(
			cita_name=cita_name,
			estado="No Asistió",
			action="close",
		)

	return {"ok": True, "cita": cita_name}
