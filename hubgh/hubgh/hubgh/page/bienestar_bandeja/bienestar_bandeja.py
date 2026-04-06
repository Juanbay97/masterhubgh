import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate

from hubgh.hubgh.bienestar_context import (
	BIENESTAR_ALERT_SOURCE_FIELDS,
	BIENESTAR_COMPROMISO_SOURCE_FIELDS,
	build_origin_context_payload,
)


ALLOWED_WELLBEING_ROLES = {
	"System Manager",
	"Gestión Humana",
	"HR Training & Wellbeing",
	"Formación y Bienestar",
	"Formacion y Bienestar",
	"GH - RRLL",
}


def _assert_operational_access() -> None:
	roles = set(frappe.get_roles() or [])
	if roles.intersection(ALLOWED_WELLBEING_ROLES):
		return
	if frappe.has_permission("Page", doc="bienestar_bandeja", ptype="read"):
		return
	frappe.throw(_("No tiene permisos para acceder a la Bandeja Central de Bienestar."), frappe.PermissionError)


def _matches_common_filters(row, punto_venta=None, responsable=None, estado=None) -> bool:
	if punto_venta and row.get("punto_venta") != punto_venta:
		return False
	if responsable and row.get("responsable_bienestar") != responsable:
		return False
	if estado and row.get("estado") != estado:
		return False
	return True


def _tipo_allows(tipo_filter, tipo_caso: str) -> bool:
	if not tipo_filter:
		return True
	return str(tipo_filter).strip().lower() == tipo_caso


def _normalize_row(row, tipo_caso: str, fecha_key: str):
	r = dict(row)
	r["tipo_caso"] = tipo_caso
	r["fecha_caso"] = r.get(fecha_key)
	r["empleado_label"] = " ".join(
		part for part in [r.get("empleado_nombres"), r.get("empleado_apellidos")] if part
	).strip() or r.get("ficha_empleado") or "Sin empleado"
	r["punto_venta_label"] = r.get("punto_venta_nombre") or r.get("punto_venta") or "Sin punto"
	r["responsable_label"] = r.get("responsable_bienestar_nombre") or r.get("responsable_bienestar") or "Sin responsable"
	r["tipo_resumen"] = _build_tipo_resumen(r, tipo_caso)
	r.update(_build_semaforo_metadata(r, tipo_caso))
	r.update(_build_context_metadata(r, tipo_caso))
	return r


def _build_semaforo_metadata(row, tipo_caso):
	score = None
	if tipo_caso == "evaluacion":
		score = row.get("porcentaje_resultado") if row.get("porcentaje_resultado") not in (None, "") else row.get("score_global")
	elif tipo_caso in {"seguimiento", "alerta", "compromiso"}:
		score = row.get("score_global")

	try:
		score_value = round(float(score), 2) if score not in (None, "") else None
	except (TypeError, ValueError):
		score_value = None

	if score_value is None:
		return {
			"semaforo_score": None,
			"semaforo_label": "Sin score",
			"semaforo_tone": "neutral",
		}

	if score_value >= 80:
		return {
			"semaforo_score": score_value,
			"semaforo_label": "Verde",
			"semaforo_tone": "success",
		}
	if score_value >= 50:
		return {
			"semaforo_score": score_value,
			"semaforo_label": "Amarillo",
			"semaforo_tone": "warning",
		}
	return {
		"semaforo_score": score_value,
		"semaforo_label": "Rojo",
		"semaforo_tone": "danger",
	}


def _build_tipo_resumen(row, tipo_caso):
	if tipo_caso == "seguimiento":
		return f"Seguimiento {row.get('tipo_seguimiento') or row.get('momento_consolidacion') or 'pendiente'}"
	if tipo_caso == "evaluacion":
		return f"Periodo prueba · {row.get('dictamen') or row.get('estado') or 'Pendiente'}"
	if tipo_caso == "alerta":
		return f"{row.get('tipo_alerta') or 'Alerta'} · {row.get('prioridad') or row.get('estado') or 'Activa'}"
	if tipo_caso == "compromiso":
		return f"Compromiso · {row.get('estado') or 'Activo'}"
	return row.get("estado") or tipo_caso


def _format_context_date(value):
	if not value:
		return ""
	try:
		return str(getdate(value))
	except Exception:
		return str(value)


def _build_origin_display(row, fieldname, ref_name):
	if fieldname == "alerta":
		parts = [row.get("alerta_tipo_alerta") or "Alerta bienestar", row.get("alerta_prioridad") or row.get("alerta_estado")]
		return " | ".join(part for part in parts if part)
	if fieldname == "seguimiento_ingreso":
		parts = [
			"Seguimiento ingreso",
			row.get("seguimiento_ingreso_tipo_seguimiento") or row.get("seguimiento_ingreso_momento_consolidacion"),
			_format_context_date(row.get("seguimiento_ingreso_fecha_programada")),
		]
		return " | ".join(part for part in parts if part)
	if fieldname == "evaluacion_periodo_prueba":
		parts = [
			"Periodo de prueba",
			row.get("evaluacion_periodo_prueba_dictamen") or row.get("evaluacion_periodo_prueba_estado"),
			_format_context_date(row.get("evaluacion_periodo_prueba_fecha_evaluacion")),
		]
		return " | ".join(part for part in parts if part)
	if fieldname == "levantamiento_punto":
		parts = [
			"Levantamiento punto",
			row.get("levantamiento_punto_estado") or "Registrado",
			_format_context_date(row.get("levantamiento_punto_fecha_levantamiento")),
		]
		return " | ".join(part for part in parts if part)
	if fieldname == "gh_novedad":
		parts = ["GH Novedad", row.get("gh_novedad_tipo") or row.get("gh_novedad_estado")]
		return " | ".join(part for part in parts if part)
	return ref_name or ""


def _build_context_metadata(row, tipo_caso):
	if tipo_caso == "alerta":
		meta = build_origin_context_payload(row, BIENESTAR_ALERT_SOURCE_FIELDS)
		origen_legible = _build_origin_display(row, meta.get("origen_contexto_field"), meta.get("origen_contexto_ref"))
		if origen_legible:
			meta["origen_contexto_display"] = origen_legible
		meta["origen_contexto_secondary"] = meta.get("origen_contexto_ref")
		meta["rrll_handoff_name"] = row.get("gh_novedad")
		meta["rrll_handoff_label"] = (
			f"Handoff RRLL: {row.get('gh_novedad_tipo') or row.get('gh_novedad_estado') or row.get('gh_novedad')}"
			if row.get("gh_novedad")
			else "Sin handoff RRLL"
		)
		return meta
	if tipo_caso == "compromiso":
		meta = build_origin_context_payload(row, BIENESTAR_COMPROMISO_SOURCE_FIELDS)
		origen_legible = _build_origin_display(row, meta.get("origen_contexto_field"), meta.get("origen_contexto_ref"))
		if origen_legible:
			meta["origen_contexto_display"] = origen_legible
		meta["origen_contexto_secondary"] = meta.get("origen_contexto_ref")
		meta["rrll_handoff_name"] = row.get("gh_novedad")
		meta["rrll_handoff_label"] = (
			f"Handoff RRLL: {row.get('gh_novedad_tipo') or row.get('gh_novedad_estado') or row.get('gh_novedad')}"
			if row.get("gh_novedad")
			else "Sin handoff RRLL"
		)
		return meta
	if tipo_caso == "evaluacion":
		handoff = row.get("gh_novedad")
		requiere = int(row.get("requiere_escalamiento_rrll") or 0) == 1
		return {
			"origen_contexto_display": "Periodo de prueba",
			"rrll_handoff_name": handoff,
			"rrll_handoff_label": (
				f"Handoff RRLL: {row.get('gh_novedad_tipo') or handoff}"
				if handoff
				else ("Pendiente RRLL" if requiere else "Sin handoff RRLL")
			),
		}
	return {"origen_contexto_display": "Seguimiento ingreso", "rrll_handoff_label": "N/A"}


@frappe.whitelist()
def get_bienestar_bandeja(punto_venta=None, responsable=None, estado=None, tipo=None):
	_assert_operational_access()
	today = getdate(nowdate())

	colas = {
		"seguimientos": {"pendientes": [], "hoy": [], "vencidos": [], "proximos": []},
		"evaluaciones": {"pendientes": [], "vencidas": [], "no_aprobadas": []},
		"alertas": {"abiertas": [], "en_seguimiento": [], "escaladas": []},
		"compromisos": {"activos": [], "sin_mejora": [], "escalados_rrll": []},
	}

	if _tipo_allows(tipo, "seguimiento"):
		seguimientos = frappe.get_all(
			"Bienestar Seguimiento Ingreso",
			fields=[
				"name",
				"ficha_empleado",
				"ficha_empleado.nombres as empleado_nombres",
				"ficha_empleado.apellidos as empleado_apellidos",
				"punto_venta",
				"punto_venta.nombre_pdv as punto_venta_nombre",
				"tipo_seguimiento",
				"momento_consolidacion",
				"fecha_programada",
				"fecha_realizacion",
				"estado",
				"responsable_bienestar",
				"responsable_bienestar.full_name as responsable_bienestar_nombre",
				"score_global",
				"observaciones",
			],
			order_by="fecha_programada asc",
		)
		for row in seguimientos:
			if not _matches_common_filters(row, punto_venta, responsable, estado):
				continue
			r = _normalize_row(row, "seguimiento", "fecha_programada")
			fecha = getdate(row.get("fecha_programada")) if row.get("fecha_programada") else None
			estado_actual = row.get("estado")
			if estado_actual in {"Realizado", "Cancelado"}:
				continue
			if fecha and fecha < today:
				colas["seguimientos"]["vencidos"].append(r)
			elif fecha and fecha == today:
				colas["seguimientos"]["hoy"].append(r)
			elif fecha and fecha > today:
				colas["seguimientos"]["proximos"].append(r)
			else:
				colas["seguimientos"]["pendientes"].append(r)

	if _tipo_allows(tipo, "evaluacion"):
		evaluaciones = frappe.get_all(
			"Bienestar Evaluacion Periodo Prueba",
			fields=[
				"name",
				"ficha_empleado",
				"ficha_empleado.nombres as empleado_nombres",
				"ficha_empleado.apellidos as empleado_apellidos",
				"punto_venta",
				"punto_venta.nombre_pdv as punto_venta_nombre",
				"fecha_evaluacion",
				"estado",
				"dictamen",
				"score_global",
				"porcentaje_resultado",
				"requiere_escalamiento_rrll",
				"gh_novedad",
				"gh_novedad.tipo as gh_novedad_tipo",
				"responsable_bienestar",
				"responsable_bienestar.full_name as responsable_bienestar_nombre",
				"observaciones",
			],
			order_by="fecha_evaluacion asc",
		)
		for row in evaluaciones:
			if not _matches_common_filters(row, punto_venta, responsable, estado):
				continue
			r = _normalize_row(row, "evaluacion", "fecha_evaluacion")
			fecha = getdate(row.get("fecha_evaluacion")) if row.get("fecha_evaluacion") else None
			dictamen = str(row.get("dictamen") or "").strip().upper()
			estado_actual = row.get("estado")
			if dictamen == "NO APRUEBA" or estado_actual == "No aprobada":
				colas["evaluaciones"]["no_aprobadas"].append(r)
			elif fecha and fecha < today and estado_actual in {"Pendiente", "En gestión"}:
				colas["evaluaciones"]["vencidas"].append(r)
			elif estado_actual in {"Pendiente", "En gestión"}:
				colas["evaluaciones"]["pendientes"].append(r)

	if _tipo_allows(tipo, "alerta"):
		alertas = frappe.get_all(
			"Bienestar Alerta",
			fields=[
				"name",
				"ficha_empleado",
				"ficha_empleado.nombres as empleado_nombres",
				"ficha_empleado.apellidos as empleado_apellidos",
				"punto_venta",
				"punto_venta.nombre_pdv as punto_venta_nombre",
				"tipo_alerta",
				"prioridad",
				"fecha_alerta",
				"estado",
				"responsable_bienestar",
				"responsable_bienestar.full_name as responsable_bienestar_nombre",
				"descripcion",
				"origen_contexto",
				"seguimiento_ingreso",
				"seguimiento_ingreso.tipo_seguimiento as seguimiento_ingreso_tipo_seguimiento",
				"seguimiento_ingreso.momento_consolidacion as seguimiento_ingreso_momento_consolidacion",
				"seguimiento_ingreso.fecha_programada as seguimiento_ingreso_fecha_programada",
				"evaluacion_periodo_prueba",
				"evaluacion_periodo_prueba.dictamen as evaluacion_periodo_prueba_dictamen",
				"evaluacion_periodo_prueba.estado as evaluacion_periodo_prueba_estado",
				"evaluacion_periodo_prueba.fecha_evaluacion as evaluacion_periodo_prueba_fecha_evaluacion",
				"levantamiento_punto",
				"levantamiento_punto.fecha_levantamiento as levantamiento_punto_fecha_levantamiento",
				"levantamiento_punto.estado as levantamiento_punto_estado",
				"levantamiento_punto.punto_venta as levantamiento_punto_punto_venta",
				"gh_novedad",
				"gh_novedad.tipo as gh_novedad_tipo",
				"gh_novedad.estado as gh_novedad_estado",
				"fecha_cierre",
				"score_global",
			],
			order_by="fecha_alerta asc",
		)
		for row in alertas:
			if not _matches_common_filters(row, punto_venta, responsable, estado):
				continue
			r = _normalize_row(row, "alerta", "fecha_alerta")
			estado_actual = row.get("estado")
			if estado_actual == "Abierta":
				colas["alertas"]["abiertas"].append(r)
			elif estado_actual == "En seguimiento":
				colas["alertas"]["en_seguimiento"].append(r)
			elif estado_actual == "Escalada":
				colas["alertas"]["escaladas"].append(r)

	if _tipo_allows(tipo, "compromiso"):
		compromisos = frappe.get_all(
			"Bienestar Compromiso",
			fields=[
				"name",
				"ficha_empleado",
				"ficha_empleado.nombres as empleado_nombres",
				"ficha_empleado.apellidos as empleado_apellidos",
				"punto_venta",
				"punto_venta.nombre_pdv as punto_venta_nombre",
				"origen_contexto",
				"alerta",
				"alerta.tipo_alerta as alerta_tipo_alerta",
				"alerta.prioridad as alerta_prioridad",
				"alerta.estado as alerta_estado",
				"seguimiento_ingreso",
				"seguimiento_ingreso.tipo_seguimiento as seguimiento_ingreso_tipo_seguimiento",
				"seguimiento_ingreso.momento_consolidacion as seguimiento_ingreso_momento_consolidacion",
				"seguimiento_ingreso.fecha_programada as seguimiento_ingreso_fecha_programada",
				"evaluacion_periodo_prueba",
				"evaluacion_periodo_prueba.dictamen as evaluacion_periodo_prueba_dictamen",
				"evaluacion_periodo_prueba.estado as evaluacion_periodo_prueba_estado",
				"evaluacion_periodo_prueba.fecha_evaluacion as evaluacion_periodo_prueba_fecha_evaluacion",
				"levantamiento_punto",
				"levantamiento_punto.fecha_levantamiento as levantamiento_punto_fecha_levantamiento",
				"levantamiento_punto.estado as levantamiento_punto_estado",
				"levantamiento_punto.punto_venta as levantamiento_punto_punto_venta",
				"gh_novedad",
				"gh_novedad.tipo as gh_novedad_tipo",
				"gh_novedad.estado as gh_novedad_estado",
				"fecha_compromiso",
				"fecha_limite",
				"estado",
				"responsable_bienestar",
				"responsable_bienestar.full_name as responsable_bienestar_nombre",
				"resultado",
				"sin_mejora",
				"fecha_cierre",
				"score_global",
			],
			order_by="fecha_limite asc, fecha_compromiso asc",
		)
		for row in compromisos:
			if not _matches_common_filters(row, punto_venta, responsable, estado):
				continue
			r = _normalize_row(row, "compromiso", "fecha_limite")
			estado_actual = row.get("estado")
			if estado_actual in {"Activo", "En seguimiento"}:
				colas["compromisos"]["activos"].append(r)
			if int(row.get("sin_mejora") or 0) == 1:
				colas["compromisos"]["sin_mejora"].append(r)
			if estado_actual == "Escalado RRLL":
				colas["compromisos"]["escalados_rrll"].append(r)

	kpis = {
		"seguimientos_pendientes": len(colas["seguimientos"]["pendientes"]),
		"seguimientos_hoy": len(colas["seguimientos"]["hoy"]),
		"seguimientos_vencidos": len(colas["seguimientos"]["vencidos"]),
		"seguimientos_proximos": len(colas["seguimientos"]["proximos"]),
		"evaluaciones_pendientes": len(colas["evaluaciones"]["pendientes"]),
		"evaluaciones_vencidas": len(colas["evaluaciones"]["vencidas"]),
		"evaluaciones_no_aprobadas": len(colas["evaluaciones"]["no_aprobadas"]),
		"alertas_abiertas": len(colas["alertas"]["abiertas"]),
		"alertas_en_seguimiento": len(colas["alertas"]["en_seguimiento"]),
		"alertas_escaladas": len(colas["alertas"]["escaladas"]),
		"compromisos_activos": len(colas["compromisos"]["activos"]),
		"compromisos_sin_mejora": len(colas["compromisos"]["sin_mejora"]),
		"compromisos_escalados_rrll": len(colas["compromisos"]["escalados_rrll"]),
	}
	kpis["total_operativo"] = sum(kpis.values())
	kpis["total_vencimientos"] = kpis["seguimientos_vencidos"] + kpis["evaluaciones_vencidas"]

	return {
		"filtros": {
			"punto_venta": punto_venta,
			"responsable": responsable,
			"estado": estado,
			"tipo": tipo,
		},
		"kpis": kpis,
		"colas": colas,
		"meta": {
			"fecha_corte": str(today),
			"total_registros": sum(len(v) for grupo in colas.values() for v in grupo.values()),
		},
	}


def _append_operational_log(doc, gestion_breve=None, nuevo_estado=None, reprogramar_fecha=None):
	if not gestion_breve:
		return
	if hasattr(doc, "bitacora"):
		doc.append(
			"bitacora",
			{
				"fecha": now_datetime(),
				"accion": gestion_breve,
				"responsable": frappe.session.user,
				"estado_resultante": nuevo_estado or doc.get("estado"),
				"proximo_paso": gestion_breve,
				"fecha_proximo_paso": reprogramar_fecha,
			},
		)
		return

	observaciones = (doc.get("observaciones") or "").strip()
	linea = f"[{now_datetime()}] {frappe.session.user}: {gestion_breve}"
	doc.observaciones = f"{observaciones}\n{linea}".strip()


@frappe.whitelist()
def gestionar_bienestar_item(tipo, item_name, nuevo_estado=None, gestion_breve=None, reprogramar_fecha=None):
	_assert_operational_access()
	if not tipo or not item_name:
		frappe.throw(_("Debe enviar tipo e item_name"))

	tipo_key = str(tipo).strip().lower()
	doctype_by_tipo = {
		"seguimiento": "Bienestar Seguimiento Ingreso",
		"evaluacion": "Bienestar Evaluacion Periodo Prueba",
		"alerta": "Bienestar Alerta",
		"compromiso": "Bienestar Compromiso",
	}

	doctype = doctype_by_tipo.get(tipo_key)
	if not doctype:
		frappe.throw(_("Tipo no soportado para gestión operativa."))

	doc = frappe.get_doc(doctype, item_name)

	if nuevo_estado:
		doc.estado = nuevo_estado

	if reprogramar_fecha:
		if tipo_key == "seguimiento":
			doc.fecha_programada = reprogramar_fecha
		elif tipo_key == "evaluacion":
			doc.fecha_evaluacion = reprogramar_fecha
		elif tipo_key == "alerta":
			doc.fecha_alerta = reprogramar_fecha
		elif tipo_key == "compromiso":
			doc.fecha_limite = reprogramar_fecha

	if tipo_key == "evaluacion" and nuevo_estado == "No aprobada":
		doc.dictamen = "NO APRUEBA"
	if tipo_key == "alerta" and nuevo_estado == "Cerrada":
		doc.fecha_cierre = getdate(nowdate())
	if tipo_key == "compromiso" and nuevo_estado == "Cerrado":
		doc.fecha_cierre = getdate(nowdate())

	_append_operational_log(
		doc,
		gestion_breve=gestion_breve,
		nuevo_estado=nuevo_estado,
		reprogramar_fecha=reprogramar_fecha,
	)

	doc.save(ignore_permissions=True)
	return {
		"ok": True,
		"doctype": doctype,
		"name": item_name,
		"estado": doc.estado,
		"reprogramado": bool(reprogramar_fecha),
	}
