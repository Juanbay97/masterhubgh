from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Optional

import frappe
from frappe.utils import add_days, getdate, nowdate


FOLLOWUP_SPECS = (
	("5", None, 5),
	("10", None, 10),
	("30/45", "30", 30),
	("30/45", "45", 45),
)


FOLLOWUP_QUESTION_BANK = {
	"5": {
		"escala": [
			{"dimension": "q1_bienvenida", "pregunta": "Q1. Claridad de la bienvenida recibida", "tipo_respuesta": "1-3"},
			{"dimension": "q2_rol", "pregunta": "Q2. Claridad del rol y funciones", "tipo_respuesta": "1-3"},
			{"dimension": "q3_motivacion", "pregunta": "Q3. Nivel de motivación actual", "tipo_respuesta": "1-3"},
			{"dimension": "q4_relacion_lider", "pregunta": "Q4. Relación con líder directo", "tipo_respuesta": "1-3"},
			{"dimension": "q5_integracion_equipo", "pregunta": "Q5. Integración con el equipo", "tipo_respuesta": "1-3"},
			{"dimension": "q6_herramientas", "pregunta": "Q6. Disponibilidad de herramientas", "tipo_respuesta": "Booleano"},
			{"dimension": "q7_dotacion", "pregunta": "Q7. Dotación inicial completa", "tipo_respuesta": "Booleano"},
			{"dimension": "q8_cultura", "pregunta": "Q8. Comprensión de cultura y normas", "tipo_respuesta": "1-3"},
			{"dimension": "q9_carga", "pregunta": "Q9. Percepción de carga operativa", "tipo_respuesta": "1-3"},
			{"dimension": "enps", "pregunta": "eNPS. ¿Qué tan probable es que recomiendes trabajar aquí?", "tipo_respuesta": "1-10"},
		],
		"abiertas": [
			{"categoria": "General", "pregunta": "¿Qué ha sido lo mejor de tus primeros días?"},
			{"categoria": "General", "pregunta": "¿Qué necesitas para desempeñarte mejor?"},
		],
	},
	"10": {
		"escala": [
			{"dimension": "q1_adaptacion", "pregunta": "Q1. Adaptación al puesto", "tipo_respuesta": "1-3"},
			{"dimension": "q2_claridad_objetivos", "pregunta": "Q2. Claridad de objetivos", "tipo_respuesta": "1-3"},
			{"dimension": "q3_motivacion", "pregunta": "Q3. Nivel de motivación", "tipo_respuesta": "1-3"},
			{"dimension": "q4_relacion_lider", "pregunta": "Q4. Relación con líder", "tipo_respuesta": "1-3"},
			{"dimension": "q5_apoyo_equipo", "pregunta": "Q5. Apoyo del equipo", "tipo_respuesta": "1-3"},
			{"dimension": "q6_formacion", "pregunta": "Q6. Cobertura de formación inicial", "tipo_respuesta": "Booleano"},
			{"dimension": "recomendacion", "pregunta": "Recomendación general del ingreso", "tipo_respuesta": "1-10"},
		],
		"abiertas": [
			{"categoria": "General", "pregunta": "¿Qué situaciones te han dificultado la adaptación?"},
			{"categoria": "General", "pregunta": "¿Qué acciones concretas propones para mejorar tu experiencia?"},
		],
	},
	"30/45-30": {
		"escala": [
			{"dimension": "desempeno_general", "pregunta": "Desempeño general a 30 días", "tipo_respuesta": "1-3"},
			{"dimension": "cumplimiento_normas", "pregunta": "Cumplimiento de normas", "tipo_respuesta": "Booleano"},
			{"dimension": "apoyo_lider", "pregunta": "Nivel de apoyo del líder", "tipo_respuesta": "1-3"},
			{"dimension": "retencion_riesgo", "pregunta": "¿Existe riesgo de retiro temprano?", "tipo_respuesta": "Booleano"},
			{"dimension": "comentario_hito", "pregunta": "Comentario del hito 30 días", "tipo_respuesta": "Texto"},
		],
		"abiertas": [
			{"categoria": "General", "pregunta": "¿Cuáles son tus principales logros en este primer mes?"},
			{"categoria": "General", "pregunta": "¿Qué te gustaría fortalecer durante el siguiente periodo?"},
		],
	},
	"30/45-45": {
		"escala": [
			{"dimension": "desempeno_general", "pregunta": "Desempeño general a 45 días", "tipo_respuesta": "1-3"},
			{"dimension": "autonomia", "pregunta": "Nivel de autonomía", "tipo_respuesta": "1-3"},
			{"dimension": "continuidad", "pregunta": "¿Cumple expectativas de continuidad?", "tipo_respuesta": "Booleano"},
			{"dimension": "riesgos_criticos", "pregunta": "¿Existen riesgos críticos por escalar?", "tipo_respuesta": "Booleano"},
			{"dimension": "comentario_hito", "pregunta": "Comentario del hito 45 días", "tipo_respuesta": "Texto"},
		],
		"abiertas": [
			{"categoria": "General", "pregunta": "¿Qué evidencias de mejora has observado en este periodo?"},
			{"categoria": "General", "pregunta": "¿Qué compromisos propones para el siguiente ciclo?"},
		],
	},
}


PROBATION_QUESTION_BANK = {
	"escala": [
		{"dimension": "conocimiento_del_puesto", "pregunta": "Conocimiento del puesto", "tipo_respuesta": "1-3"},
		{"dimension": "cumplimiento_procedimientos", "pregunta": "Cumplimiento de procedimientos", "tipo_respuesta": "1-3"},
		{"dimension": "calidad_trabajo", "pregunta": "Calidad del trabajo", "tipo_respuesta": "1-3"},
		{"dimension": "velocidad_aprendizaje", "pregunta": "Velocidad de aprendizaje", "tipo_respuesta": "1-3"},
		{"dimension": "trabajo_equipo", "pregunta": "Trabajo en equipo", "tipo_respuesta": "1-3"},
		{"dimension": "actitud_servicio", "pregunta": "Actitud de servicio", "tipo_respuesta": "1-3"},
		{"dimension": "responsabilidad", "pregunta": "Responsabilidad", "tipo_respuesta": "1-3"},
		{"dimension": "adaptacion_cultura", "pregunta": "Adaptación a cultura", "tipo_respuesta": "1-3"},
	],
	"abiertas": [
		{"categoria": "Fortalezas", "pregunta": "Fortalezas observadas"},
		{"categoria": "Mejoras", "pregunta": "Aspectos por mejorar"},
		{"categoria": "Plan", "pregunta": "Plan de acción sugerido"},
	],
}


def _as_obj(value):
	if isinstance(value, dict):
		return SimpleNamespace(**value)
	return value


def _to_int(value, default=0):
	try:
		return int(value)
	except (TypeError, ValueError):
		return default


def _to_float(value, default=0.0):
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


def _resolve_followup_question_key(tipo_seguimiento: Optional[str], momento_consolidacion: Optional[str]):
	tipo = str(tipo_seguimiento or "").strip()
	momento = str(momento_consolidacion or "").strip()
	if tipo == "30/45":
		return f"30/45-{momento or '30'}"
	return tipo


def _serialize_question_bank(bank: Optional[dict]) -> dict:
	bank = bank or {}
	return {
		"escala": [deepcopy(row) for row in bank.get("escala", [])],
		"abiertas": [deepcopy(row) for row in bank.get("abiertas", [])],
	}


@frappe.whitelist()
def get_followup_questionnaire_template(tipo_seguimiento: Optional[str] = None, momento_consolidacion: Optional[str] = None) -> dict:
	"""Return follow-up questionnaire template for client-side preload in new docs."""
	key = _resolve_followup_question_key(tipo_seguimiento, momento_consolidacion)
	bank = FOLLOWUP_QUESTION_BANK.get(key)
	template = _serialize_question_bank(bank)
	template["key"] = key
	return template


@frappe.whitelist()
def get_probation_questionnaire_template() -> dict:
	"""Return fixed probation questionnaire template for client-side preload in new docs."""
	return _serialize_question_bank(PROBATION_QUESTION_BANK)


def ensure_ingreso_followups_for_employee(employee_doc, *, from_source=None) -> int:
	"""Ensure deterministic 5/10/30/45 follow-ups exist from employee master + fecha_ingreso."""
	if not employee_doc:
		return 0

	employee = _as_obj(employee_doc)
	employee_name = getattr(employee, "name", None)
	if not employee_name:
		return 0

	if str(getattr(employee, "estado", "") or "") != "Activo":
		return 0

	fecha_ingreso = getattr(employee, "fecha_ingreso", None)
	if not fecha_ingreso:
		return 0

	created = 0
	fecha_ingreso_dt = getdate(fecha_ingreso)
	punto_venta = getattr(employee, "pdv", None)

	for tipo, momento, day_offset in FOLLOWUP_SPECS:
		filters = {
			"ficha_empleado": employee_name,
			"tipo_seguimiento": tipo,
			"fecha_programada": add_days(fecha_ingreso_dt, day_offset),
		}
		if momento:
			filters["momento_consolidacion"] = momento

		if frappe.db.exists("Bienestar Seguimiento Ingreso", filters):
			continue

		payload = {
			"doctype": "Bienestar Seguimiento Ingreso",
			"ficha_empleado": employee_name,
			"punto_venta": punto_venta,
			"tipo_seguimiento": tipo,
			"fecha_programada": add_days(fecha_ingreso_dt, day_offset),
			"fecha_ingreso": fecha_ingreso,
			"estado": "Pendiente",
			"responsable_bienestar": getattr(employee, "owner", None),
			"observaciones": f"Generado automáticamente desde Ficha Empleado ({from_source or 'Ficha Empleado'}).",
		}
		if momento:
			payload["momento_consolidacion"] = momento

		frappe.get_doc(payload).insert(ignore_permissions=True)
		created += 1

	return created


def generate_ingreso_followups_for_active_employees() -> int:
	rows = frappe.get_all(
		"Ficha Empleado",
		filters={
			"estado": "Activo",
			"fecha_ingreso": ["is", "set"],
		},
		fields=["name", "pdv", "fecha_ingreso", "owner", "estado"],
	)

	created = 0
	for row in rows:
		created += ensure_ingreso_followups_for_employee(row, from_source="scheduler")
	return created


def calculate_probation_metrics(respuestas_escala):
	total_score = 0
	total_max = 0

	for row in respuestas_escala or []:
		raw_puntaje = getattr(row, "puntaje", None)
		if raw_puntaje in (None, ""):
			continue
		tipo = str(getattr(row, "tipo_respuesta", None) or "1-3").strip()
		raw_txt = str(raw_puntaje).strip().upper()
		if tipo == "Booleano" and raw_txt in {"SI", "SÍ", "YES", "TRUE"}:
			puntaje = 1.0
		elif tipo == "Booleano" and raw_txt in {"NO", "FALSE"}:
			puntaje = 0.0
		else:
			puntaje = _to_float(raw_puntaje, default=0)
		if tipo == "Booleano":
			max_score = 1
		elif tipo == "1-10":
			max_score = 10
		else:
			max_score = 3

		if puntaje < 0 or puntaje > max_score:
			continue
		total_score += puntaje
		total_max += max_score

	percentage = round((total_score / total_max) * 100, 2) if total_max else 0

	if not total_max:
		dictamen = "PENDIENTE"
	elif percentage >= 70:
		dictamen = "APRUEBA"
	else:
		dictamen = "NO APRUEBA"

	return {
		"total_score": total_score,
		"max_score": total_max,
		"percentage": percentage,
		"dictamen": dictamen,
	}


def calculate_followup_score(respuestas_escala) -> float:
	total_score = 0.0
	total_weight = 0.0

	for row in respuestas_escala or []:
		raw_puntaje = getattr(row, "puntaje", None)
		if raw_puntaje in (None, ""):
			continue
		tipo = str(getattr(row, "tipo_respuesta", None) or "1-10").strip()
		if tipo == "Texto":
			continue
		peso = _to_float(getattr(row, "peso", None), default=1.0)
		peso = 1.0 if peso <= 0 else peso

		if tipo == "Booleano":
			max_score = 1.0
		else:
			max_score = 10.0 if tipo == "1-10" else 3.0

		raw_txt = str(raw_puntaje).strip().upper()
		if tipo == "Booleano" and raw_txt in {"SI", "SÍ", "YES", "TRUE"}:
			puntaje = 1.0
		elif tipo == "Booleano" and raw_txt in {"NO", "FALSE"}:
			puntaje = 0.0
		else:
			puntaje = _to_float(raw_puntaje, default=0.0)
		if puntaje < 0 or puntaje > max_score:
			continue

		normalized = puntaje / max_score
		total_score += normalized * peso
		total_weight += peso

	if not total_weight:
		return 0.0
	return round((total_score / total_weight) * 100, 2)


def calculate_point_lifting_score(participantes) -> tuple[float, float]:
	scored = []
	attendees = 0

	for row in participantes or []:
		asistencia = int(getattr(row, "asistencia", 0) or 0)
		if asistencia:
			attendees += 1
		puntaje = _to_float(getattr(row, "puntaje_global", None), default=0.0)
		if 0 < puntaje <= 10:
			scored.append(puntaje)

	score_global = round((sum(scored) / len(scored)) * 10, 2) if scored else 0.0
	cobertura = round((attendees / len(participantes)) * 100, 2) if participantes else 0.0
	return score_global, cobertura


def ensure_followup_questionnaire(doc):
	if not hasattr(doc, "append"):
		return

	key = _resolve_followup_question_key(getattr(doc, "tipo_seguimiento", None), getattr(doc, "momento_consolidacion", None))
	bank = FOLLOWUP_QUESTION_BANK.get(key)
	if not bank:
		return

	if not getattr(doc, "respuestas_escala", None):
		for row in bank["escala"]:
			doc.append(
				"respuestas_escala",
				{
					"dimension": row["dimension"],
					"pregunta": row["pregunta"],
					"tipo_respuesta": row.get("tipo_respuesta", "1-10"),
					"peso": 1,
				},
			)

	if not getattr(doc, "respuestas_abiertas", None):
		for row in bank["abiertas"]:
			doc.append(
				"respuestas_abiertas",
				{
					"categoria": row["categoria"],
					"pregunta": row["pregunta"],
				},
			)


def ensure_probation_questionnaire(doc):
	if not hasattr(doc, "append"):
		return

	if not getattr(doc, "respuestas_escala", None):
		for row in PROBATION_QUESTION_BANK["escala"]:
			doc.append(
				"respuestas_escala",
				{
					"dimension": row["dimension"],
					"pregunta": row["pregunta"],
					"tipo_respuesta": row.get("tipo_respuesta", "1-3"),
					"peso": 1,
				},
			)

	if not getattr(doc, "respuestas_abiertas", None):
		for row in PROBATION_QUESTION_BANK["abiertas"]:
			doc.append(
				"respuestas_abiertas",
				{
					"categoria": row["categoria"],
					"pregunta": row["pregunta"],
				},
			)


def create_rrll_escalation_if_needed(source_doc, *, should_escalate: bool, reason: str, fecha_base=None):
	"""Create GH Novedad escalation to GH-RRLL and include source traceability."""
	if not should_escalate:
		return None
	if not getattr(source_doc, "ficha_empleado", None):
		return None
	if not frappe.db.exists("DocType", "GH Novedad"):
		return None

	existing_link = getattr(source_doc, "gh_novedad", None)
	if existing_link:
		return existing_link

	source_doctype = getattr(source_doc, "doctype", source_doc.__class__.__name__)
	source_docname = getattr(source_doc, "name", None) or "SIN-NOMBRE"
	origin = f"Fuente: {source_doctype} {source_docname}."
	existing = frappe.db.get_value(
		"GH Novedad",
		{
			"persona": source_doc.ficha_empleado,
			"descripcion": ["like", f"%{origin}%"],
		},
		"name",
	)
	if existing:
		if hasattr(source_doc, "db_set"):
			source_doc.db_set("gh_novedad", existing, update_modified=False)
		else:
			source_doc.gh_novedad = existing
		return existing

	payload = {
		"doctype": "GH Novedad",
		"persona": source_doc.ficha_empleado,
		"punto": getattr(source_doc, "punto_venta", None),
		"tipo": "Otro",
		"fecha_inicio": fecha_base or nowdate(),
		"descripcion": f"{reason}. {origin}",
		"estado": "Recibida",
		"cola_origen": "GH-Bandeja General",
		"cola_sugerida": "GH-RRLL",
		"cola_destino": "GH-RRLL",
	}

	novedad = frappe.get_doc(payload)
	novedad.insert(ignore_permissions=True)
	if hasattr(source_doc, "db_set"):
		source_doc.db_set("gh_novedad", novedad.name, update_modified=False)
	else:
		source_doc.gh_novedad = novedad.name
	return novedad.name


def ensure_bienestar_process_for_employee(employee_doc, *, from_source=None) -> Optional[str]:
	"""Compatibility wrapper: process doctype is no longer required for operational flow."""
	ensure_ingreso_followups_for_employee(employee_doc, from_source=from_source)
	return None


def ensure_ingreso_followups_for_process(process_doc) -> int:
	"""Compatibility wrapper for legacy process hooks.

	If a process exists for technical compatibility, derive follow-ups from its employee/date.
	"""
	process_doc = _as_obj(process_doc)
	ficha = getattr(process_doc, "ficha_empleado", None)
	fecha_ingreso = getattr(process_doc, "fecha_ingreso", None)
	if not ficha or not fecha_ingreso:
		return 0
	return ensure_ingreso_followups_for_employee(
		{
			"name": ficha,
			"pdv": getattr(process_doc, "punto_venta", None),
			"fecha_ingreso": fecha_ingreso,
			"estado": "Activo",
			"owner": getattr(process_doc, "responsable_bienestar", None),
		},
		from_source="Bienestar Proceso Colaborador",
	)


def generate_ingreso_followups_for_active_processes() -> int:
	"""Compatibility wrapper for scheduler/tests."""
	return generate_ingreso_followups_for_active_employees()


def create_wellbeing_alert_if_needed(source_doc, *, tipo_alerta: str, descripcion: str, prioridad="Alta"):
	if not source_doc or not getattr(source_doc, "ficha_empleado", None):
		return None
	if not frappe.db.exists("DocType", "Bienestar Alerta"):
		return None

	filters = {"ficha_empleado": source_doc.ficha_empleado, "tipo_alerta": tipo_alerta, "estado": ["!=" , "Cerrada"]}
	if getattr(source_doc, "name", None) and tipo_alerta == "Ingreso":
		filters["seguimiento_ingreso"] = source_doc.name
	existing = frappe.db.get_value("Bienestar Alerta", filters, "name")
	if existing:
		return existing

	payload = {
		"doctype": "Bienestar Alerta",
		"ficha_empleado": source_doc.ficha_empleado,
		"punto_venta": getattr(source_doc, "punto_venta", None),
		"tipo_alerta": tipo_alerta,
		"prioridad": prioridad,
		"descripcion": descripcion,
	}
	if tipo_alerta == "Ingreso":
		payload["seguimiento_ingreso"] = getattr(source_doc, "name", None)

	alerta = frappe.get_doc(payload)
	alerta.insert(ignore_permissions=True)
	return alerta.name


def evaluate_followup_critical_alerts(doc):
	"""Alert rules: motivación <=1, relación líder <=1, recomendación <6."""
	if not doc:
		return None

	critical_reasons = []
	for row in getattr(doc, "respuestas_escala", None) or []:
		dim = str(getattr(row, "dimension", "") or "").strip().lower()
		tipo = str(getattr(row, "tipo_respuesta", "") or "").strip()
		if tipo not in {"1-3", "1-10"}:
			continue
		puntaje = _to_float(getattr(row, "puntaje", None), 0)
		if dim in {"q3_motivacion", "q1_motivacion", "motivacion"} and puntaje <= 1:
			critical_reasons.append("motivación <= 1")
		if dim in {"q4_relacion_lider", "relacion_lider"} and puntaje <= 1:
			critical_reasons.append("relación con líder <= 1")
		if dim in {"recomendacion", "enps"} and puntaje < 6:
			critical_reasons.append("recomendación < 6")

	if not critical_reasons:
		return None

	description = f"Alerta automática por respuestas críticas en seguimiento de ingreso ({', '.join(sorted(set(critical_reasons)))})."
	return create_wellbeing_alert_if_needed(doc, tipo_alerta="Ingreso", descripcion=description, prioridad="Alta")


def mark_bienestar_followups_overdue(reference_date=None) -> int:
	today = getdate(reference_date or nowdate())
	rows = frappe.get_all(
		"Bienestar Seguimiento Ingreso",
		filters={
			"estado": ["in", ["Pendiente", "En gestión"]],
			"fecha_programada": ["<", today],
		},
		fields=["name", "estado"],
	)

	updated = 0
	for row in rows:
		current_state = getattr(row, "estado", None) if not isinstance(row, dict) else row.get("estado")
		if current_state not in {"Pendiente", "En gestión"}:
			continue
		name = getattr(row, "name", None) if not isinstance(row, dict) else row.get("name")
		if not name:
			continue
		frappe.db.set_value("Bienestar Seguimiento Ingreso", name, "estado", "Vencido")
		updated += 1

	return updated
