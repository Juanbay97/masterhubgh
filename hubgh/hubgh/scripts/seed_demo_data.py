import random
from collections import defaultdict
from typing import Any

import frappe
from frappe.utils import add_days, nowdate


SEED_MARKER = "[SEED_DEMO_HUBGH]"
TRAY_SEED_MARKER = "[SEED_TRAY_HUBGH]"


@frappe.whitelist()
def seed_sst_bienestar_bandejas(dry_run: int = 0, per_pdv_limit: int = 12) -> dict[str, Any]:
	"""Seed deterministic synthetic records for SST and Bienestar trays across all PDV."""
	dry = int(dry_run or 0) == 1
	limit = max(int(per_pdv_limit or 12), 1)

	summary: dict[str, Any] = {
		"ok": True,
		"dry_run": dry,
		"per_pdv_limit": limit,
		"employees_considered": 0,
		"employees_seeded": 0,
		"sst": {
			"novedad": {"created": 0, "updated": 0, "skipped": 0},
			"alerta": {"created": 0, "updated": 0, "skipped": 0},
		},
		"bienestar": {
			"seguimiento": {"created": 0, "updated": 0, "skipped": 0},
			"evaluacion": {"created": 0, "updated": 0, "skipped": 0},
			"alerta": {"created": 0, "updated": 0, "skipped": 0},
			"compromiso": {"created": 0, "updated": 0, "skipped": 0},
		},
		"pdv": {},
		"warnings": [],
	}

	required_doctypes = {
		"Novedad SST",
		"SST Alerta",
		"Bienestar Seguimiento Ingreso",
		"Bienestar Evaluacion Periodo Prueba",
		"Bienestar Alerta",
		"Bienestar Compromiso",
	}
	missing = sorted(dt for dt in required_doctypes if not frappe.db.exists("DocType", dt))
	if missing:
		summary["ok"] = False
		summary["warnings"].append(f"Doctypes faltantes para sembrado de bandejas: {', '.join(missing)}")
		return summary

	employees = _load_tray_seed_employees(limit_per_pdv=limit)
	summary["employees_considered"] = len(employees)
	if not employees:
		summary["ok"] = False
		summary["warnings"].append("No se encontraron Ficha Empleado con PDV para sembrar bandejas SST/Bienestar.")
		return summary

	sst_responsable = _first_user_by_roles(["HR SST", "SST", "System Manager"]) or "Administrator"
	bienestar_responsable = _first_user_by_roles(["HR Training & Wellbeing", "Formación y Bienestar", "System Manager"]) or "Administrator"

	for idx, emp in enumerate(employees):
		seed_key = f"{TRAY_SEED_MARKER}:{emp['name']}:{idx % 4}"
		novedad_name = _upsert_seeded_sst_novedad(
			emp=emp,
			idx=idx,
			seed_key=seed_key,
			dry=dry,
			summary=summary["sst"]["novedad"],
		)
		if novedad_name:
			_upsert_seeded_sst_alerta(
				emp=emp,
				idx=idx,
				seed_key=seed_key,
				novedad_name=novedad_name,
				responsable=sst_responsable,
				dry=dry,
				summary=summary["sst"]["alerta"],
			)

		_upsert_seeded_bienestar_seguimiento(
			emp=emp,
			idx=idx,
			seed_key=seed_key,
			responsable=bienestar_responsable,
			dry=dry,
			summary=summary["bienestar"]["seguimiento"],
		)
		_upsert_seeded_bienestar_evaluacion(
			emp=emp,
			idx=idx,
			seed_key=seed_key,
			responsable=bienestar_responsable,
			dry=dry,
			summary=summary["bienestar"]["evaluacion"],
		)
		_upsert_seeded_bienestar_alerta(
			emp=emp,
			idx=idx,
			seed_key=seed_key,
			responsable=bienestar_responsable,
			dry=dry,
			summary=summary["bienestar"]["alerta"],
		)
		_upsert_seeded_bienestar_compromiso(
			emp=emp,
			idx=idx,
			seed_key=seed_key,
			responsable=bienestar_responsable,
			dry=dry,
			summary=summary["bienestar"]["compromiso"],
		)

		summary["employees_seeded"] += 1
		pdv_key = emp.get("pdv") or "SIN_PDV"
		summary["pdv"][pdv_key] = summary["pdv"].get(pdv_key, 0) + 1

	if dry:
		frappe.db.rollback()
	else:
		frappe.db.commit()

	return summary


def _load_tray_seed_employees(limit_per_pdv: int) -> list[dict[str, Any]]:
	rows = frappe.get_all(
		"Ficha Empleado",
		filters={"pdv": ["!=", ""]},
		fields=["name", "pdv", "fecha_ingreso", "estado", "owner", "nombres", "apellidos"],
		order_by="pdv asc, modified desc",
	)
	if not rows:
		return []

	grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for row in rows:
		grouped[row.get("pdv")].append(row)

	selected: list[dict[str, Any]] = []
	for pdv in sorted(grouped.keys()):
		selected.extend(grouped[pdv][:limit_per_pdv])
	return selected


def _first_user_by_roles(roles: list[str]) -> str | None:
	for role in roles:
		users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent", limit=1)
		if users:
			return users[0]
	return None


def _upsert_seeded_sst_novedad(
	emp: dict[str, Any],
	idx: int,
	seed_key: str,
	dry: bool,
	summary: dict[str, int],
) -> str | None:
	variant = idx % 4
	tipo_by_variant = ["Seguimiento SST", "Accidente", "Aforado", "Seguimiento SST"]
	estado_by_variant = ["Abierta", "En seguimiento", "Abierta", "Cerrada"]
	prioridad_by_variant = ["Media", "Alta", "Media", "Baja"]

	payload: dict[str, Any] = {
		"empleado": emp["name"],
		"punto_venta": emp.get("pdv"),
		"tipo_novedad": tipo_by_variant[variant],
		"categoria_novedad": "SST",
		"estado": estado_by_variant[variant],
		"prioridad": prioridad_by_variant[variant],
		"titulo_resumen": f"Caso SST sintético {variant + 1}",
		"descripcion_resumen": f"Registro sintético para visualización de bandeja SST. {seed_key}",
		"alerta_activa": 0,
	}

	if payload["tipo_novedad"] == "Accidente":
		payload.update(
			{
				"accidente_tuvo_incapacidad": 0,
				"causa_evento": "Acto inseguro",
				"fecha_accidente": add_days(nowdate(), -(idx % 6 + 1)),
			}
		)
	elif payload["tipo_novedad"] == "Aforado":
		payload.update(
			{
				"aforado_motivo": "Condición médica",
				"aforado_desde": add_days(nowdate(), -90),
				"categoria_seguimiento": "Condición médica",
			}
		)

	existing = frappe.get_all(
		"Novedad SST",
		filters={"empleado": emp["name"], "descripcion_resumen": ["like", f"%{seed_key}%"]},
		fields=["name"],
		limit=1,
	)

	if existing:
		if dry:
			summary["updated"] += 1
			return existing[0]["name"]
		doc = frappe.get_doc("Novedad SST", existing[0]["name"])
		doc.update(payload)
		doc.save(ignore_permissions=True)
		summary["updated"] += 1
		return doc.name

	if dry:
		summary["created"] += 1
		return f"DRY-NOV-{emp['name']}"

	doc = frappe.get_doc({"doctype": "Novedad SST", **payload})
	doc.insert(ignore_permissions=True)
	summary["created"] += 1
	return doc.name


def _upsert_seeded_sst_alerta(
	emp: dict[str, Any],
	idx: int,
	seed_key: str,
	novedad_name: str,
	responsable: str,
	dry: bool,
	summary: dict[str, int],
) -> None:
	variant = idx % 4
	estado_by_variant = ["Pendiente", "Reprogramada", "Enviada", "Atendida"]
	delta_days_by_variant = [-2, 0, 4, -1]

	payload = {
		"novedad": novedad_name,
		"empleado": emp["name"],
		"punto_venta": emp.get("pdv"),
		"fecha_programada": add_days(nowdate(), delta_days_by_variant[variant]),
		"estado": estado_by_variant[variant],
		"tipo_alerta": "Seguimiento",
		"asignado_a": responsable,
		"mensaje": f"Alerta SST sintética para tablero operativo. {seed_key}",
	}
	if payload["estado"] == "Atendida":
		payload["atendida_en"] = frappe.utils.now_datetime()

	existing = frappe.get_all(
		"SST Alerta",
		filters={"novedad": novedad_name, "mensaje": ["like", f"%{seed_key}%"]},
		fields=["name"],
		limit=1,
	)

	if existing:
		if dry:
			summary["updated"] += 1
			return
		doc = frappe.get_doc("SST Alerta", existing[0]["name"])
		doc.update(payload)
		doc.save(ignore_permissions=True)
		summary["updated"] += 1
		return

	if dry:
		summary["created"] += 1
		return

	doc = frappe.get_doc({"doctype": "SST Alerta", **payload})
	doc.insert(ignore_permissions=True)
	summary["created"] += 1


def _upsert_seeded_bienestar_seguimiento(
	emp: dict[str, Any],
	idx: int,
	seed_key: str,
	responsable: str,
	dry: bool,
	summary: dict[str, int],
) -> None:
	variant = idx % 4
	tipo_by_variant = ["5", "10", "30/45", "30/45"]
	estado_by_variant = ["Pendiente", "En gestión", "Vencido", "Realizado"]
	momento_by_variant = [None, None, "30", "45"]

	fecha_ingreso = emp.get("fecha_ingreso") or add_days(nowdate(), -120)
	fecha_programada = add_days(nowdate(), [-3, 1, -5, -10][variant])
	payload: dict[str, Any] = {
		"ficha_empleado": emp["name"],
		"fecha_ingreso": fecha_ingreso,
		"punto_venta": emp.get("pdv"),
		"tipo_seguimiento": tipo_by_variant[variant],
		"fecha_programada": fecha_programada,
		"estado": estado_by_variant[variant],
		"responsable_bienestar": responsable,
		"respuestas_abiertas": [
			{
				"categoria": "General",
				"pregunta": "Observación sintética",
				"respuesta": f"Respuesta sintética de seguimiento ({seed_key}).",
			}
		],
		"observaciones": f"Seguimiento de ingreso sintético para bandeja. {seed_key}",
	}
	if momento_by_variant[variant]:
		payload["momento_consolidacion"] = momento_by_variant[variant]
	if payload["estado"] == "Realizado":
		payload["fecha_realizacion"] = add_days(fecha_programada, 1)

	existing = frappe.get_all(
		"Bienestar Seguimiento Ingreso",
		filters={"ficha_empleado": emp["name"], "observaciones": ["like", f"%{seed_key}%"]},
		fields=["name"],
		limit=1,
	)

	if existing:
		if dry:
			summary["updated"] += 1
			return
		doc = frappe.get_doc("Bienestar Seguimiento Ingreso", existing[0]["name"])
		doc.update(payload)
		doc.save(ignore_permissions=True)
		summary["updated"] += 1
		return

	if dry:
		summary["created"] += 1
		return

	doc = frappe.get_doc({"doctype": "Bienestar Seguimiento Ingreso", **payload})
	doc.insert(ignore_permissions=True)
	summary["created"] += 1


def _upsert_seeded_bienestar_evaluacion(
	emp: dict[str, Any],
	idx: int,
	seed_key: str,
	responsable: str,
	dry: bool,
	summary: dict[str, int],
) -> None:
	variant = idx % 4
	estado_by_variant = ["Pendiente", "En gestión", "Realizada", "No aprobada"]
	dictamen_by_variant = ["PENDIENTE", "PENDIENTE", "APRUEBA", "NO APRUEBA"]

	payload = {
		"ficha_empleado": emp["name"],
		"fecha_ingreso": emp.get("fecha_ingreso") or add_days(nowdate(), -120),
		"punto_venta": emp.get("pdv"),
		"fecha_evaluacion": add_days(nowdate(), [-2, 3, -7, -4][variant]),
		"estado": estado_by_variant[variant],
		"dictamen": dictamen_by_variant[variant],
		"responsable_bienestar": responsable,
		"respuestas_abiertas": [
			{
				"categoria": "General",
				"pregunta": "Comentario de evaluación",
				"respuesta": f"Respuesta sintética de evaluación ({seed_key}).",
			}
		],
		"observaciones": f"Evaluación de periodo de prueba sintética. {seed_key}",
	}

	existing = frappe.get_all(
		"Bienestar Evaluacion Periodo Prueba",
		filters={"ficha_empleado": emp["name"], "observaciones": ["like", f"%{seed_key}%"]},
		fields=["name"],
		limit=1,
	)

	if existing:
		if dry:
			summary["updated"] += 1
			return
		doc = frappe.get_doc("Bienestar Evaluacion Periodo Prueba", existing[0]["name"])
		doc.update(payload)
		doc.save(ignore_permissions=True)
		summary["updated"] += 1
		return

	if dry:
		summary["created"] += 1
		return

	doc = frappe.get_doc({"doctype": "Bienestar Evaluacion Periodo Prueba", **payload})
	doc.insert(ignore_permissions=True)
	summary["created"] += 1


def _upsert_seeded_bienestar_alerta(
	emp: dict[str, Any],
	idx: int,
	seed_key: str,
	responsable: str,
	dry: bool,
	summary: dict[str, int],
) -> None:
	variant = idx % 4
	estado_by_variant = ["Abierta", "En seguimiento", "Escalada", "Cerrada"]
	tipo_by_variant = ["Ingreso", "Periodo de prueba", "Levantamiento de punto", "Otro"]

	payload = {
		"ficha_empleado": emp["name"],
		"punto_venta": emp.get("pdv"),
		"tipo_alerta": tipo_by_variant[variant],
		"prioridad": ["Media", "Alta", "Alta", "Baja"][variant],
		"fecha_alerta": add_days(nowdate(), [-1, 0, 2, -6][variant]),
		"estado": estado_by_variant[variant],
		"responsable_bienestar": responsable,
		"descripcion": f"Alerta bienestar sintética para bandeja. {seed_key}",
	}
	if payload["estado"] == "Cerrada":
		payload["fecha_cierre"] = nowdate()
		payload["motivo_cierre"] = "Cierre sintético controlado"

	existing = frappe.get_all(
		"Bienestar Alerta",
		filters={"ficha_empleado": emp["name"], "descripcion": ["like", f"%{seed_key}%"]},
		fields=["name"],
		limit=1,
	)

	if existing:
		if dry:
			summary["updated"] += 1
			return
		doc = frappe.get_doc("Bienestar Alerta", existing[0]["name"])
		doc.update(payload)
		doc.save(ignore_permissions=True)
		summary["updated"] += 1
		return

	if dry:
		summary["created"] += 1
		return

	doc = frappe.get_doc({"doctype": "Bienestar Alerta", **payload})
	doc.insert(ignore_permissions=True)
	summary["created"] += 1


def _upsert_seeded_bienestar_compromiso(
	emp: dict[str, Any],
	idx: int,
	seed_key: str,
	responsable: str,
	dry: bool,
	summary: dict[str, int],
) -> None:
	variant = idx % 4
	estado_by_variant = ["Activo", "En seguimiento", "Cerrado", "Escalado RRLL"]

	payload = {
		"ficha_empleado": emp["name"],
		"punto_venta": emp.get("pdv"),
		"fecha_compromiso": add_days(nowdate(), [-1, -3, -8, -12][variant]),
		"fecha_limite": add_days(nowdate(), [7, 4, -2, -5][variant]),
		"estado": estado_by_variant[variant],
		"responsable_bienestar": responsable,
		"sin_mejora": 0,
		"resultado": f"Compromiso de seguimiento sintético. {seed_key}",
	}
	if payload["estado"] in {"Cerrado", "Escalado RRLL"}:
		payload["fecha_cierre"] = nowdate()

	existing = frappe.get_all(
		"Bienestar Compromiso",
		filters={"ficha_empleado": emp["name"], "resultado": ["like", f"%{seed_key}%"]},
		fields=["name"],
		limit=1,
	)

	if existing:
		if dry:
			summary["updated"] += 1
			return
		doc = frappe.get_doc("Bienestar Compromiso", existing[0]["name"])
		doc.update(payload)
		doc.save(ignore_permissions=True)
		summary["updated"] += 1
		return

	if dry:
		summary["created"] += 1
		return

	doc = frappe.get_doc({"doctype": "Bienestar Compromiso", **payload})
	doc.insert(ignore_permissions=True)
	summary["created"] += 1


@frappe.whitelist()
def run(user: str | None = None, dry_run: int = 0) -> dict[str, Any]:
	"""Seed demo data for operación punto context without LMS dependency."""
	dry = int(dry_run or 0) == 1
	summary: dict[str, Any] = {
		"ok": True,
		"dry_run": dry,
		"context": {},
		"novedades": {"created": 0, "updated": 0, "skipped": 0},
		"documents": {
			"created": 0,
			"updated": 0,
			"skipped": 0,
			"status_mix": {"OK": 0, "vencido": 0, "faltante": 0},
		},
		"posts": {"created": 0, "updated": 0, "skipped": 0},
		"solicitudes": {"created": 0, "updated": 0, "skipped": 0},
		"warnings": [],
	}

	context = _resolve_context(user=user, warnings=summary["warnings"])
	summary["context"] = {
		"requested_user": user,
		"resolved_user": context.get("resolved_user"),
		"point": context.get("pdv"),
		"point_source": context.get("source"),
	}

	people = _load_people_for_point(context.get("pdv"), warnings=summary["warnings"])
	if len(people) > 6:
		rng = random.Random(f"hubgh-seed-{context.get('pdv')}")
		people = rng.sample(people, 6)

	summary["context"]["people_count"] = len(people)
	summary["context"]["people"] = [p.get("name") for p in people]

	if not people:
		summary["ok"] = False
		summary["warnings"].append("No se encontraron personas en el punto objetivo. No se generó data.")
		return summary

	_seed_gh_novedad(
		pdv=context.get("pdv"),
		people=people,
		dry=dry,
		summary=summary["novedades"],
		warnings=summary["warnings"],
	)

	_seed_person_documents(
		people=people,
		dry=dry,
		summary=summary["documents"],
		warnings=summary["warnings"],
	)

	_seed_gh_posts(
		dry=dry,
		summary=summary["posts"],
		warnings=summary["warnings"],
	)

	_seed_mock_solicitudes(
		pdv=context.get("pdv"),
		people=people,
		dry=dry,
		summary=summary["solicitudes"],
		warnings=summary["warnings"],
	)

	if dry:
		frappe.db.rollback()
	else:
		frappe.db.commit()

	return summary


def _resolve_context(user: str | None, warnings: list[str]) -> dict[str, Any]:
	if user:
		emp = _employee_by_email(user)
		if emp and emp.get("pdv"):
			return {"resolved_user": user, "pdv": emp.get("pdv"), "source": "input_user"}
		warnings.append(f"No se encontró Ficha Empleado con email={user}. Se aplicará fallback.")

	session_user = _get_session_user()
	if session_user:
		emp = _employee_by_email(session_user)
		if emp and emp.get("pdv"):
			return {
				"resolved_user": session_user,
				"pdv": emp.get("pdv"),
				"source": "session_user",
			}
		warnings.append(f"Session user {session_user} no tiene Ficha Empleado con PDV. Se aplicará fallback.")

	row = frappe.db.sql(
		"""
		select pdv, count(*) as total
		from `tabFicha Empleado`
		where ifnull(pdv, '') != ''
		group by pdv
		order by total desc, pdv asc
		limit 1
		""",
		as_dict=True,
	)
	if row:
		return {"resolved_user": session_user, "pdv": row[0].get("pdv"), "source": "fallback_first_point"}

	frappe.throw("No fue posible resolver un punto de contexto para sembrar datos demo.")


def _employee_by_email(email: str | None) -> dict[str, Any] | None:
	if not email:
		return None
	rows = frappe.get_all(
		"Ficha Empleado",
		filters={"email": (email or "").strip()},
		fields=["name", "email", "pdv", "nombres", "apellidos"],
		limit=1,
	)
	return rows[0] if rows else None


def _get_session_user() -> str | None:
	try:
		session = getattr(frappe.local, "session", None)
		if not session:
			return None
		user = getattr(session, "user", None) or getattr(frappe.session, "user", None)
		return user if user and user != "Guest" else None
	except Exception:
		return None


def _load_people_for_point(pdv: str | None, warnings: list[str]) -> list[dict[str, Any]]:
	if not pdv:
		warnings.append("No hay PDV resuelto.")
		return []

	rows = frappe.get_all(
		"Ficha Empleado",
		filters={"pdv": pdv},
		fields=["name", "nombres", "apellidos", "email", "pdv", "estado"],
		order_by="modified desc",
	)
	if not rows:
		warnings.append(f"No hay Ficha Empleado para PDV {pdv}.")
	return rows


def _seed_gh_novedad(
	pdv: str | None,
	people: list[dict[str, Any]],
	dry: bool,
	summary: dict[str, int],
	warnings: list[str],
) -> None:
	if not frappe.db.exists("DocType", "GH Novedad"):
		warnings.append("DocType GH Novedad no existe. Se omite sección.")
		summary["skipped"] += 1
		return

	persona_1 = people[0]["name"]
	persona_2 = people[1]["name"] if len(people) > 1 else people[0]["name"]
	persona_3 = people[2]["name"] if len(people) > 2 else people[0]["name"]

	plans = [
		{
			"key": "incapacidad_abierta_1",
			"persona": persona_1,
			"tipo": "Incapacidad",
			"estado": "En gestión",
			"fecha_inicio": add_days(nowdate(), -3),
			"fecha_fin": None,
			"descripcion": "Incapacidad por cuadro viral. Seguimiento con EPS.",
		},
		{
			"key": "incapacidad_abierta_2",
			"persona": persona_2,
			"tipo": "Incapacidad",
			"estado": "Pendiente info",
			"fecha_inicio": add_days(nowdate(), -9),
			"fecha_fin": None,
			"descripcion": "Incapacidad por lesión menor en miembro superior.",
		},
		{
			"key": "accidente_cerrado_1",
			"persona": persona_3,
			"tipo": "Accidente SST",
			"estado": "Cerrada",
			"fecha_inicio": add_days(nowdate(), -21),
			"fecha_fin": add_days(nowdate(), -15),
			"descripcion": "Accidente leve en zona de producción. Plan de mejora ejecutado.",
		},
		{
			"key": "ausentismo_extra_1",
			"persona": persona_1,
			"tipo": "Ausentismo",
			"estado": "Recibida",
			"fecha_inicio": add_days(nowdate(), -2),
			"fecha_fin": None,
			"descripcion": "Ausentismo reportado por calamidad doméstica.",
		},
	]

	for item in plans:
		marker = f"{SEED_MARKER}:NOVEDAD:{item['key']}"
		existing = frappe.get_all(
			"GH Novedad",
			filters={"punto": pdv, "descripcion": ["like", f"%{marker}%"]},
			fields=["name"],
			limit=1,
		)

		payload = {
			"persona": item["persona"],
			"punto": pdv,
			"tipo": item["tipo"],
			"fecha_inicio": item["fecha_inicio"],
			"fecha_fin": item["fecha_fin"],
			"estado": item["estado"],
			"descripcion": f"{item['descripcion']}\n{marker}",
		}

		if existing:
			if dry:
				summary["updated"] += 1
				continue
			doc = frappe.get_doc("GH Novedad", existing[0]["name"])
			doc.update(payload)
			doc.save(ignore_permissions=True)
			summary["updated"] += 1
		else:
			if dry:
				summary["created"] += 1
				continue
			doc = frappe.get_doc({"doctype": "GH Novedad", **payload})
			doc.insert(ignore_permissions=True)
			summary["created"] += 1


def _seed_person_documents(
	people: list[dict[str, Any]],
	dry: bool,
	summary: dict[str, Any],
	warnings: list[str],
) -> None:
	if not frappe.db.exists("DocType", "Person Document"):
		warnings.append("DocType Person Document no existe. Se omite sección documental.")
		summary["skipped"] += 1
		return
	if not frappe.db.exists("DocType", "Document Type"):
		warnings.append("DocType Document Type no existe. Se omite sección documental.")
		summary["skipped"] += 1
		return

	categories = {
		"ARL": ["arl"],
		"Carnet manipulación": ["manipul", "carnet"],
		"Examen médico": ["examen", "medic", "aptitud"],
	}

	doc_types: dict[str, str] = {}
	for category, patterns in categories.items():
		doc_name = _find_document_type(patterns)
		if not doc_name:
			doc_name = _ensure_document_type(category, dry=dry)
			if not doc_name:
				warnings.append(f"No se pudo resolver Document Type para categoría {category}.")
				summary["skipped"] += 1
				continue
		doc_types[category] = doc_name

	if not doc_types:
		warnings.append("No hay categorías documentales disponibles para sembrar.")
		return

	statuses_cycle = ["OK", "vencido", "faltante"]
	for idx, person in enumerate(people[:3] or people):
		for c_idx, (category, doc_type) in enumerate(doc_types.items()):
			logical_status = statuses_cycle[(idx + c_idx) % len(statuses_cycle)]
			status_value, file_value, notes = _person_doc_payload_values(logical_status, category)

			seed_key = f"{SEED_MARKER}:DOC:{category}:{person['name']}"
			existing = frappe.get_all(
				"Person Document",
				filters={
					"employee": person["name"],
					"document_type": doc_type,
					"notes": ["like", f"%{seed_key}%"],
				},
				fields=["name"],
				limit=1,
			)

			payload = {
				"person_type": "Empleado",
				"person_doctype": "Ficha Empleado",
				"person": person["name"],
				"employee": person["name"],
				"document_type": doc_type,
				"status": status_value,
				"file": file_value,
				"notes": f"{notes}\n{seed_key}",
			}

			if existing:
				if dry:
					summary["updated"] += 1
				else:
					doc = frappe.get_doc("Person Document", existing[0]["name"])
					doc.update(payload)
					doc.save(ignore_permissions=True)
					summary["updated"] += 1
			else:
				if dry:
					summary["created"] += 1
				else:
					doc = frappe.get_doc({"doctype": "Person Document", **payload})
					doc.insert(ignore_permissions=True)
					summary["created"] += 1

			summary["status_mix"][logical_status] = summary["status_mix"].get(logical_status, 0) + 1


def _person_doc_payload_values(logical_status: str, category: str) -> tuple[str, str | None, str]:
	safe_slug = (
		category.lower().replace(" ", "_").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o")
	)
	if logical_status == "OK":
		return "Aprobado", f"/private/files/demo_{safe_slug}_ok.pdf", "Estado demo: OK"
	if logical_status == "vencido":
		return "Rechazado", f"/private/files/demo_{safe_slug}_vencido.pdf", "Estado demo: vencido"
	return "Pendiente", None, "Estado demo: faltante"


def _find_document_type(patterns: list[str]) -> str | None:
	rows = frappe.get_all("Document Type", fields=["name", "document_name"], limit=500)
	for row in rows:
		value = (row.get("document_name") or "").lower()
		if all(p.lower() in value for p in patterns):
			return row.get("name")
	for row in rows:
		value = (row.get("document_name") or "").lower()
		if any(p.lower() in value for p in patterns):
			return row.get("name")
	return None


def _ensure_document_type(document_name: str, dry: bool) -> str | None:
	existing = frappe.db.get_value("Document Type", {"document_name": document_name}, "name")
	if existing:
		return existing
	if dry:
		return document_name
	try:
		doc = frappe.get_doc(
			{
				"doctype": "Document Type",
				"document_name": document_name,
				"applies_to": "Ambos",
				"is_active": 1,
				"is_optional": 1,
				"is_required_for_hiring": 0,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception:
		return None


def _seed_gh_posts(dry: bool, summary: dict[str, int], warnings: list[str]) -> None:
	if not frappe.db.exists("DocType", "GH Post"):
		warnings.append("DocType GH Post no existe. Se omite sección feed.")
		summary["skipped"] += 1
		return

	plans = [
		("apertura_bienestar", "Apertura campaña de bienestar", "Bienestar"),
		("turnos_operacion", "Actualización turnos operación", "Operación"),
		("recordatorio_documental", "Recordatorio documental", "Talento"),
		("sst_jornada", "Jornada SST: pausas activas en punto", "SST"),
		("arl_recordatorio", "Recordatorio ARL y reporte oportuno", "SST"),
		("manipulacion_refuerzo", "Refuerzo carnet de manipulación de alimentos", "Operación"),
		("examen_periodico", "Agenda de exámenes médicos periódicos", "Talento"),
	]

	for idx, (key, title, area) in enumerate(plans):
		marker = f"{SEED_MARKER}:POST:{key}"
		existing = frappe.get_all(
			"GH Post",
			filters={"cuerpo_corto": ["like", f"%{marker}%"]},
			fields=["name"],
			limit=1,
		)
		payload = {
			"titulo": title,
			"area": area,
			"fecha_publicacion": add_days(nowdate(), -(idx + 1)),
			"vigencia_hasta": add_days(nowdate(), 45 - idx),
			"publicado": 1,
			"audiencia_roles": "Jefe de Punto\nGestión Humana",
			"cuerpo_corto": f"Comunicado operativo demo para {area}.\n{marker}",
		}

		if existing:
			if dry:
				summary["updated"] += 1
				continue
			doc = frappe.get_doc("GH Post", existing[0]["name"])
			doc.update(payload)
			doc.save(ignore_permissions=True)
			summary["updated"] += 1
		else:
			if dry:
				summary["created"] += 1
				continue
			doc = frappe.get_doc({"doctype": "GH Post", **payload})
			doc.insert(ignore_permissions=True)
			summary["created"] += 1


def _seed_mock_solicitudes(
	pdv: str | None,
	people: list[dict[str, Any]],
	dry: bool,
	summary: dict[str, int],
	warnings: list[str],
) -> None:
	candidates = [
		"GH Solicitud",
		"Solicitud GH",
		"Operacion Solicitud",
		"GH Request",
	]

	doctype = next((dt for dt in candidates if frappe.db.exists("DocType", dt)), None)
	if not doctype:
		warnings.append("No existe DocType de solicitudes dedicado. Se omite esta sección sin error.")
		summary["skipped"] += 1
		return

	meta = frappe.get_meta(doctype)
	if not _has_fields(meta, ["descripcion"]) and not _has_fields(meta, ["subject"]):
		warnings.append(f"DocType {doctype} no tiene campos mínimos esperados. Se omite sección.")
		summary["skipped"] += 1
		return

	seed_label = f"{SEED_MARKER}:SOLICITUD:base"
	existing = frappe.get_all(
		doctype,
		filters={"descripcion": ["like", f"%{seed_label}%"]} if _has_fields(meta, ["descripcion"]) else {},
		fields=["name"],
		limit=1,
	)

	payload: dict[str, Any] = {}
	if _has_fields(meta, ["descripcion"]):
		payload["descripcion"] = f"Solicitud demo de soporte operativo para PDV {pdv}.\n{seed_label}"
	if _has_fields(meta, ["subject"]):
		payload["subject"] = "Solicitud demo - seguimiento documental"
	if _has_fields(meta, ["persona"]) and people:
		payload["persona"] = people[0]["name"]
	if _has_fields(meta, ["punto"]):
		payload["punto"] = pdv

	if existing:
		if dry:
			summary["updated"] += 1
			return
		doc = frappe.get_doc(doctype, existing[0]["name"])
		doc.update(payload)
		doc.save(ignore_permissions=True)
		summary["updated"] += 1
		return

	if dry:
		summary["created"] += 1
		return

	try:
		doc = frappe.get_doc({"doctype": doctype, **payload})
		doc.insert(ignore_permissions=True)
		summary["created"] += 1
	except Exception:
		warnings.append(f"No fue posible crear mock de solicitudes en {doctype}. Se omite sin abortar.")
		summary["skipped"] += 1


def _has_fields(meta, fieldnames: list[str]) -> bool:
	available = set(meta.get_valid_columns() or [])
	return all(field in available for field in fieldnames)
