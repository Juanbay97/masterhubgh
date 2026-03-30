import io
import json
import re
import unicodedata
import zipfile

import frappe
from frappe import _
from frappe.utils import add_days, get_first_day, get_last_day, getdate, now_datetime, nowdate
from frappe.utils.file_manager import save_file
from frappe.utils.pdf import get_pdf

from hubgh.person_identity import resolve_employee_for_user, resolve_user_for_employee
from hubgh.lms.hardening import (
	get_lms_course_name,
	get_lms_metrics_snapshot,
	get_lms_retry_attempts,
	get_lms_retry_delay_seconds,
	increment_lms_metric,
	lms_doctypes_available,
	log_lms_event,
	run_with_lms_retry,
)


NOVEDAD_TIPO_MAP = {
	"accidente": ["Accidente", "Accidente SST"],
	"incapacidad": ["Incapacidad"],
}

DOC_CATEGORY_COMPAT = {
	"arl": ["arl", "arl eps", "certificado arl", "afiliacion arl", "afiliación arl"],
	"carnet manipulación de alimentos": [
		"carnet manipulacion de alimentos",
		"carnet de manipulacion de alimentos",
		"carne manipulacion alimentos",
		"carnet alimentos",
	],
	"examen médico": [
		"examen medico",
		"examen med ocupacional",
		"examen medico ocupacional",
		"aptitud medica",
	],
}


SST_OPEN_STATES = ["Abierta", "En seguimiento", "Abierto"]


@frappe.whitelist()
def get_punto_lite():
	"""Resumen operativo del punto asignado al usuario actual."""
	emp = _get_session_employee()
	pdv_id = emp.get("pdv")

	if not pdv_id:
		frappe.throw(_("Tu usuario no tiene punto asignado en Ficha Empleado."), frappe.PermissionError)

	pdv_name = (
		frappe.db.get_value("Punto de Venta", pdv_id, "nombre_pdv")
		or frappe.db.get_value("Punto de Venta", pdv_id, "title")
		or pdv_id
	)

	personas = frappe.get_all(
		"Ficha Empleado",
		filters={"pdv": pdv_id},
		fields=["name", "nombres", "apellidos", "estado", "email"],
		order_by="nombres asc, apellidos asc",
	)

	personas_fmt = []
	for p in personas:
		persona_name = p.get("name")
		nombre = f"{(p.get('nombres') or '').strip()} {(p.get('apellidos') or '').strip()}".strip() or persona_name
		personas_fmt.append({"name": persona_name, "nombre": nombre, "estado": p.get("estado") or ""})

	cursos_reporte, cursos_kpis = _build_pdv_lms_report(pdv_id, personas)

	kpis = {
		"personal_activo": frappe.db.count("Ficha Empleado", {"pdv": pdv_id, "estado": "Activo"}),
		"incapacidades_abiertas": frappe.db.count(
			"Novedad SST",
			{
				"punto_venta": pdv_id,
				"categoria_novedad": "SST",
				"estado": ["in", SST_OPEN_STATES],
				"es_incapacidad": 1,
			},
		),
		"accidentes_30d": frappe.db.count(
			"GH Novedad",
			{
				"punto": pdv_id,
				"tipo": ["in", _novedad_tipo_values("accidente")],
				"fecha_inicio": [">=", add_days(nowdate(), -30)],
			},
		),
		"cursos_calidad_vencidos": cursos_kpis.get("cursos_calidad_vencidos", 0),
		"cursos_calidad_completados": cursos_kpis.get("cursos_calidad_completados", 0),
		"cursos_calidad_en_progreso": cursos_kpis.get("cursos_calidad_en_progreso", 0),
		"cursos_calidad_sin_iniciar": cursos_kpis.get("cursos_calidad_sin_iniciar", 0),
	}

	return {
		"punto": {"id": pdv_id, "name": pdv_name},
		"kpis": kpis,
		"personas": personas_fmt,
		"cursos_reporte": cursos_reporte,
	}


@frappe.whitelist()
def get_lms_integration_health():
	"""Estado operativo lightweight de integración LMS para diagnóstico."""
	required = ["LMS Enrollment", "LMS Course", "LMS Course Progress", "LMS Certificate"]
	available = _lms_tables_available()
	course_name = get_lms_course_name()
	metrics = get_lms_metrics_snapshot()

	payload = {
		"service": "hubgh_lms_integration",
		"status": "ok" if available else "degraded",
		"available": available,
		"required_doctypes": required,
		"course": course_name,
		"retry": {
			"attempts": get_lms_retry_attempts(),
			"delay_seconds": get_lms_retry_delay_seconds(),
		},
		"metrics": metrics,
	}

	log_lms_event(event="health.read", status="success", context={"available": available, "course": course_name})
	increment_lms_metric("health.read", "success")
	return payload


@frappe.whitelist()
def get_punto_novedades(tipo=None, estado=None):
	"""Novedades GH del punto del usuario, con filtros opcionales."""
	pdv_id, _ = _get_session_point()
	filters = {"punto": pdv_id}

	if tipo:
		tipo_canonico = _canonical_novedad_tipo(tipo)
		if tipo == "Otras":
			filters["tipo"] = ["not in", _novedad_tipo_values("incapacidad") + _novedad_tipo_values("accidente")]
		elif tipo_canonico != tipo:
			filters["tipo"] = ["in", _novedad_tipo_values(tipo_canonico)]
		else:
			filters["tipo"] = tipo

	if estado:
		filters["estado"] = estado

	rows = frappe.get_all(
		"GH Novedad",
		filters=filters,
		fields=[
			"name",
			"persona",
			"punto",
			"tipo",
			"fecha_inicio",
			"fecha_fin",
			"descripcion",
			"evidencias",
			"estado",
			"cola_origen",
			"cola_sugerida",
			"cola_destino",
			"creation",
		],
		order_by="creation desc",
	)

	persona_ids = [r.get("persona") for r in rows if r.get("persona")]
	persona_names = {}
	if persona_ids:
		for p in frappe.get_all(
			"Ficha Empleado",
			filters={"name": ["in", persona_ids]},
			fields=["name", "nombres", "apellidos"],
		):
			persona_names[p.name] = f"{(p.get('nombres') or '').strip()} {(p.get('apellidos') or '').strip()}".strip() or p.name

	for row in rows:
		row["persona_nombre"] = persona_names.get(row.get("persona"), row.get("persona"))
		row["tipo_canonico"] = _canonical_novedad_tipo(row.get("tipo"))

	return rows


@frappe.whitelist()
def get_person_docs(persona):
	"""Estado documental por persona para categorías activas de operación."""
	if not persona:
		frappe.throw(_("Debes indicar persona."))

	pdv_id, _ = _get_session_point()
	persona_doc = _get_employee_doc(persona)
	if persona_doc.get("pdv") != pdv_id:
		frappe.throw(_("La persona no pertenece a tu punto."), frappe.PermissionError)

	categorias = frappe.get_all(
		"Operacion Tipo Documento",
		filters={"activo": 1},
		fields=["name", "clave", "nombre", "orden", "es_requerido"],
		order_by="orden asc, creation asc",
	)

	if not categorias:
		return {"persona": persona, "items": []}

	rows = frappe.get_all(
		"Person Document",
		filters={"employee": persona},
		fields=["name", "document_type", "status", "file", "modified"],
		order_by="modified desc",
	)

	cat_lookup = _build_doc_category_lookup(categorias)
	by_doc_type = {}
	for r in rows:
		k = _resolve_doc_category_key(r.get("document_type"), cat_lookup)
		if k and k not in by_doc_type:
			by_doc_type[k] = r

	items = []
	for c in categorias:
		cand = by_doc_type.get(_doc_category_key(c))
		items.append(
			{
				"clave": c.get("clave"),
				"nombre": c.get("nombre"),
				"requerido": int(c.get("es_requerido") or 0),
				"status": (cand or {}).get("status") or "Pendiente",
				"file": (cand or {}).get("file"),
			}
		)

	return {
		"persona": persona,
		"persona_nombre": f"{(persona_doc.get('nombres') or '').strip()} {(persona_doc.get('apellidos') or '').strip()}".strip() or persona,
		"items": items,
	}


@frappe.whitelist()
def export_docs_zip(mode, month=None, persona=None):
	"""Genera ZIP descargable de soporte documental con metadata explícita de empty-state."""
	pdv_id, pdv_name = _get_session_point()
	if mode not in {"persona", "punto_mes"}:
		frappe.throw(_("mode debe ser persona o punto_mes"))

	now = now_datetime()
	buf = io.BytesIO()

	with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
		manifest = {
			"generated_at": now.isoformat(),
			"generated_by": frappe.session.user,
			"mode": mode,
			"punto": {"id": pdv_id, "name": pdv_name},
		}

		if mode == "persona":
			if not persona:
				frappe.throw(_("persona es requerida para mode=persona"))
			docs = get_person_docs(persona)
			items = docs.get("items") or []
			manifest["persona"] = persona
			manifest["empty"] = len(items) == 0
			manifest["empty_state"] = {
				"empty": len(items) == 0,
				"code": "no_document_categories" if len(items) == 0 else None,
				"message": "No hay categorías documentales activas para exportar." if len(items) == 0 else "",
			}
			zf.writestr("docs_persona.json", json.dumps(docs, ensure_ascii=False, indent=2))

		else:
			month = month or now.strftime("%Y-%m")
			start, end = _month_range(month)
			novedades = frappe.get_all(
				"GH Novedad",
				filters={"punto": pdv_id, "fecha_inicio": ["between", [start, end]]},
				fields=["name", "persona", "tipo", "estado", "fecha_inicio", "fecha_fin"],
				order_by="fecha_inicio asc",
			)
			manifest["month"] = month
			manifest["total_novedades"] = len(novedades)
			manifest["empty"] = len(novedades) == 0
			manifest["empty_state"] = {
				"empty": len(novedades) == 0,
				"code": "no_novedades_in_month" if len(novedades) == 0 else None,
				"message": "No hay novedades en el rango consultado." if len(novedades) == 0 else "",
			}
			zf.writestr("novedades_mes.json", json.dumps(novedades, ensure_ascii=False, indent=2, default=str))

		zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

	filename = f"operacion_docs_{mode}_{pdv_id}_{now.strftime('%Y%m%d_%H%M%S')}.zip"
	file_doc = save_file(filename, buf.getvalue(), "Punto de Venta", pdv_id, is_private=1)
	return {
		"file_url": file_doc.file_url,
		"file_name": filename,
		"empty": manifest.get("empty", False),
		"empty_state": manifest.get("empty_state", {"empty": False, "code": None, "message": ""}),
	}


@frappe.whitelist()
def export_cursos_pdf(filters=None):
	"""Genera PDF del estado de curso por persona usando LMS real cuando existe."""
	pdv_id, pdv_name = _get_session_point()
	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except Exception:
			filters = {}
	filters = filters or {}

	people = frappe.get_all(
		"Ficha Empleado",
		filters={"pdv": pdv_id},
		fields=["name", "nombres", "apellidos", "estado", "email"],
		order_by="nombres asc, apellidos asc",
	)

	reporte, _ = _build_pdv_lms_report(pdv_id, people)
	estado_filtro = (filters.get("estado") or "").strip() if isinstance(filters, dict) else ""
	if estado_filtro:
		reporte = [r for r in reporte if (r.get("estado") or "") == estado_filtro]

	rows_html = "".join(
		[
			"<tr>"
			f"<td>{frappe.utils.escape_html(r.get('persona') or '')}</td>"
			f"<td>{frappe.utils.escape_html(r.get('nombre') or '')}</td>"
			f"<td>{frappe.utils.escape_html(r.get('estado_persona') or '')}</td>"
			f"<td>{frappe.utils.escape_html(r.get('estado') or '')}</td>"
			f"<td>{frappe.utils.escape_html(str(r.get('avance') or 0))}%</td>"
			"</tr>"
			for r in reporte
		]
	)

	html = f"""
	<h2>Reporte cursos de calidad</h2>
	<p><strong>Punto:</strong> {frappe.utils.escape_html(pdv_name)} ({frappe.utils.escape_html(pdv_id)})</p>
	<p><strong>Fecha:</strong> {frappe.utils.escape_html(str(nowdate()))}</p>
	<p><strong>Filtros:</strong> {frappe.utils.escape_html(json.dumps(filters, ensure_ascii=False))}</p>
	<table border="1" cellspacing="0" cellpadding="6" width="100%">
		<thead>
			<tr>
				<th>ID Persona</th>
				<th>Nombre</th>
				<th>Estado</th>
				<th>Curso Calidad</th>
				<th>Avance</th>
			</tr>
		</thead>
		<tbody>
			{rows_html or '<tr><td colspan="5">Sin personas asignadas.</td></tr>'}
		</tbody>
	</table>
	"""

	pdf_content = get_pdf(html)
	filename = f"reporte_cursos_calidad_{pdv_id}_{now_datetime().strftime('%Y%m%d_%H%M%S')}.pdf"
	file_doc = save_file(filename, pdf_content, "Punto de Venta", pdv_id, is_private=1)
	return {"file_url": file_doc.file_url, "file_name": filename}


@frappe.whitelist()
def create_novedad(payload):
	"""Crea GH Novedad desde operación punto, respetando defaults/rutas del DocType."""
	if isinstance(payload, str):
		payload = json.loads(payload)
	payload = payload or {}

	pdv_id, _ = _get_session_point()

	persona = payload.get("persona")
	tipo = _canonical_novedad_tipo(payload.get("tipo"))
	fecha_inicio = payload.get("fecha_inicio") or payload.get("fecha_evento")
	fecha_fin = payload.get("fecha_fin")
	descripcion = payload.get("descripcion")
	evidencias = payload.get("evidencias")

	if not persona:
		frappe.throw(_("persona es requerida"))
	if not tipo:
		frappe.throw(_("tipo es requerido"))
	if not fecha_inicio:
		frappe.throw(_("fecha_inicio es requerida"))
	if not descripcion:
		frappe.throw(_("descripcion es requerida"))

	persona_doc = _get_employee_doc(persona)
	if persona_doc.get("pdv") != pdv_id:
		frappe.throw(_("La persona no pertenece a tu punto."), frappe.PermissionError)

	evidencias_txt = _normalize_evidencias(evidencias)

	doc = frappe.get_doc(
		{
			"doctype": "GH Novedad",
			"persona": persona,
			"punto": pdv_id,
			"tipo": tipo,
			"fecha_inicio": getdate(fecha_inicio),
			"fecha_fin": getdate(fecha_fin) if fecha_fin else None,
			"descripcion": descripcion,
			"evidencias": evidencias_txt,
			"estado": payload.get("estado") or None,
		}
	)
	doc.insert(ignore_permissions=True)

	return {
		"name": doc.name,
		"persona": doc.persona,
		"punto": doc.punto,
		"tipo": doc.tipo,
		"estado": doc.estado,
		"cola_origen": doc.cola_origen,
		"cola_sugerida": doc.cola_sugerida,
		"cola_destino": doc.cola_destino,
	}


def _get_session_employee():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Sesión inválida"), frappe.PermissionError)

	identity = resolve_employee_for_user(user)
	if not identity.employee:
		frappe.throw(_("No existe Ficha Empleado asociada al usuario actual."), frappe.PermissionError)
	return frappe.db.get_value(
		"Ficha Empleado",
		identity.employee,
		["name", "nombres", "apellidos", "pdv", "estado", "email"],
		as_dict=True,
	)


def _get_session_point():
	emp = _get_session_employee()
	pdv_id = emp.get("pdv")
	if not pdv_id:
		frappe.throw(_("Tu usuario no tiene punto asignado."), frappe.PermissionError)
	pdv_name = (
		frappe.db.get_value("Punto de Venta", pdv_id, "nombre_pdv")
		or frappe.db.get_value("Punto de Venta", pdv_id, "title")
		or pdv_id
	)
	return pdv_id, pdv_name


def _get_employee_doc(persona):
	if not frappe.db.exists("Ficha Empleado", persona):
		frappe.throw(_("Persona no encontrada"))
	return frappe.db.get_value(
		"Ficha Empleado", persona, ["name", "nombres", "apellidos", "pdv", "estado"], as_dict=True
	)


def _month_range(month_yyyy_mm):
	if len(month_yyyy_mm or "") != 7:
		frappe.throw(_("month debe tener formato YYYY-MM"))
	base = getdate(f"{month_yyyy_mm}-01")
	return get_first_day(base), get_last_day(base)


def _normalize_evidencias(evidencias):
	if not evidencias:
		return None
	if isinstance(evidencias, str):
		return evidencias.strip()
	if isinstance(evidencias, list):
		items = []
		for it in evidencias:
			if isinstance(it, dict):
				items.append(it.get("file_url") or it.get("url") or it.get("name") or "")
			else:
				items.append(str(it))
		return "\n".join([x.strip() for x in items if x and x.strip()])
	return str(evidencias)


def _person_full_name(doc):
	return f"{(doc.get('nombres') or '').strip()} {(doc.get('apellidos') or '').strip()}".strip() or doc.name


def _novedad_tipo_values(clave):
	return list(dict.fromkeys(NOVEDAD_TIPO_MAP.get(clave, [])))


def _canonical_novedad_tipo(tipo):
	tipo_s = (tipo or "").strip()
	if not tipo_s:
		return tipo_s
	tipo_norm = _normalize_key(tipo_s)
	for canonico, variantes in NOVEDAD_TIPO_MAP.items():
		if tipo_norm in {_normalize_key(v) for v in variantes}:
			return variantes[-1] if canonico == "accidente" else variantes[0]
	return tipo_s


def _build_pdv_lms_report(pdv_id, personas):
	personas = personas or []
	course_name = get_lms_course_name()
	total_lecciones = _get_total_lecciones(course_name)
	enabled = _lms_tables_available()

	reporte = []
	for p in personas:
		nombre = _person_full_name(p)
		ctx = {"pdv": pdv_id, "persona": p.get("name"), "user": p.get("email"), "course": course_name}
		if not enabled:
			log_lms_event(event="report.person", status="skip", context={**ctx, "reason": "lms_unavailable"})
			increment_lms_metric("report.person", "skip")
			reporte.append(
				{
					"persona": p["name"],
					"nombre": nombre,
					"estado_persona": p.get("estado") or "",
					"estado": "Pendiente LMS",
					"avance": 0,
					"vencido": False,
					"curso": course_name,
				}
			)
			continue

		user_email = (p.get("email") or "").strip()
		identity = resolve_user_for_employee(p)
		user_id = identity.user if identity else None
		ctx["user"] = user_id or user_email
		if not user_id or not frappe.db.exists("User", user_id):
			log_lms_event(event="report.person", status="skip", context={**ctx, "reason": "user_not_found"})
			increment_lms_metric("report.person", "skip")
			reporte.append(
				{
					"persona": p["name"],
					"nombre": nombre,
					"estado_persona": p.get("estado") or "",
					"estado": "Sin usuario",
					"avance": 0,
					"vencido": True,
					"curso": course_name,
				}
			)
			continue

		enrollment = run_with_lms_retry(
			"report.enrollment_lookup",
			lambda: frappe.db.get_value(
				"LMS Enrollment",
				{"member": user_id, "course": course_name},
				["name", "progress"],
				as_dict=True,
			),
			context=ctx,
			default=None,
		)
		if not enrollment:
			log_lms_event(event="report.person", status="skip", context={**ctx, "reason": "not_enrolled_or_degraded"})
			increment_lms_metric("report.person", "skip")
			reporte.append(
				{
					"persona": p["name"],
					"nombre": nombre,
					"estado_persona": p.get("estado") or "",
					"estado": "Sin iniciar",
					"avance": 0,
					"vencido": True,
					"curso": course_name,
				}
			)
			continue

		lecciones_completadas = run_with_lms_retry(
			"report.progress_count",
			lambda: frappe.db.count(
				"LMS Course Progress",
				{"member": user_id, "course": course_name, "status": "Complete"},
			),
			context=ctx,
			default=0,
		)
		avance = int((lecciones_completadas / total_lecciones) * 100) if total_lecciones else int(enrollment.get("progress") or 0)
		certificado = run_with_lms_retry(
			"report.certificate_lookup",
			lambda: frappe.db.get_value(
				"LMS Certificate",
				{"member": user_id, "course": course_name},
				["name", "issue_date"],
				as_dict=True,
			),
			context=ctx,
			default=None,
		)
		estado = "Completado" if avance >= 100 else ("En progreso" if avance > 0 else "Sin iniciar")

		log_lms_event(event="report.person", status="success", context={**ctx, "estado": estado, "avance": avance})
		increment_lms_metric("report.person", "success")
		reporte.append(
			{
				"persona": p["name"],
				"nombre": nombre,
				"estado_persona": p.get("estado") or "",
				"estado": estado,
				"avance": avance,
				"vencido": estado != "Completado",
				"curso": course_name,
				"tiene_certificado": bool(certificado),
				"fecha_certificado": certificado.get("issue_date") if certificado else None,
			}
		)

	kpis = {
		"cursos_calidad_vencidos": len([r for r in reporte if r.get("vencido")]),
		"cursos_calidad_completados": len([r for r in reporte if r.get("estado") == "Completado"]),
		"cursos_calidad_en_progreso": len([r for r in reporte if r.get("estado") == "En progreso"]),
		"cursos_calidad_sin_iniciar": len([r for r in reporte if r.get("estado") in {"Sin iniciar", "Sin usuario", "Pendiente LMS"}]),
	}
	return reporte, kpis


def _lms_tables_available():
	return lms_doctypes_available(["LMS Enrollment", "LMS Course", "LMS Course Progress", "LMS Certificate"])


def _get_total_lecciones(course_name):
	if not lms_doctypes_available(["Course Chapter", "Course Lesson"]):
		log_lms_event(
			event="report.total_lessons",
			status="skip",
			context={"course": course_name, "reason": "course_structure_unavailable"},
		)
		increment_lms_metric("report.total_lessons", "skip")
		return 0
	capitulos = run_with_lms_retry(
		"report.chapter_lookup",
		lambda: frappe.get_all("Course Chapter", filters={"course": course_name}, pluck="name"),
		context={"course": course_name},
		default=[],
	)
	if not capitulos:
		return 0
	return run_with_lms_retry(
		"report.lesson_count",
		lambda: frappe.db.count("Course Lesson", {"chapter": ["in", capitulos]}),
		context={"course": course_name},
		default=0,
	)


def _normalize_key(value):
	value = (value or "").strip().lower()
	if not value:
		return ""
	value = unicodedata.normalize("NFKD", value)
	value = "".join(ch for ch in value if not unicodedata.combining(ch))
	value = re.sub(r"[^a-z0-9]+", " ", value)
	return re.sub(r"\s+", " ", value).strip()


def _doc_category_key(cat):
	if not cat:
		return ""
	return _normalize_key(cat.get("clave") or cat.get("nombre"))


def _build_doc_category_lookup(categorias):
	lookup = {}
	for c in categorias:
		key = _doc_category_key(c)
		if not key:
			continue
		for raw in [c.get("nombre"), c.get("clave")]:
			norm = _normalize_key(raw)
			if norm:
				lookup[norm] = key

	for canonical, aliases in DOC_CATEGORY_COMPAT.items():
		canon_norm = _normalize_key(canonical)
		if canon_norm not in lookup:
			continue
		for alias in aliases:
			lookup[_normalize_key(alias)] = lookup[canon_norm]
	return lookup


def _resolve_doc_category_key(document_type, cat_lookup):
	norm = _normalize_key(document_type)
	if not norm:
		return ""
	return cat_lookup.get(norm, "")
