import random

import frappe
from frappe.utils import today


COURSE_NAME = "calidad-e-inocuidad-alimentaria"


def crear_data_sintetica_completud(course_name=COURSE_NAME):
	"""Crea enrollments y progreso demo para empleados activos con usuario."""
	if not frappe.db.exists("LMS Course", course_name):
		frappe.throw(f"No existe el curso: {course_name}")

	empleados = frappe.get_all(
		"Ficha Empleado",
		filters={"estado": "Activo", "email": ["is", "set"]},
		fields=["name", "nombres", "apellidos", "email", "pdv"],
	)

	usuarios = []
	for e in empleados:
		email = (e.get("email") or "").strip()
		if email and frappe.db.exists("User", email):
			usuarios.append(email)

	usuarios = sorted(set(usuarios))
	if not usuarios:
		return {"enrollados": 0, "completados": 0, "certificados": 0}

	lecciones = obtener_lecciones_curso(course_name)
	if not lecciones:
		return {"enrollados": 0, "completados": 0, "certificados": 0}

	random.shuffle(usuarios)
	total = len(usuarios)
	segmentos = [
		("completo", int(total * 0.30), 1.0),
		("avanzado", int(total * 0.25), 0.75),
		("intermedio", int(total * 0.20), 0.50),
		("inicial", int(total * 0.15), 0.25),
		("sin_iniciar", total, 0.0),
	]

	stats = {"enrollados": 0, "completados": 0, "certificados": 0}
	idx = 0

	for _, cantidad, fraccion in segmentos:
		for _i in range(cantidad):
			if idx >= total:
				break
			usuario = usuarios[idx]
			idx += 1

			enrollment = crear_enrollment(usuario, course_name)
			if not enrollment:
				continue
			stats["enrollados"] += 1

			num = int(len(lecciones) * fraccion)
			for lesson in lecciones[:num]:
				crear_progreso_leccion(usuario, lesson)

			if fraccion >= 1.0:
				frappe.db.set_value("LMS Enrollment", enrollment, "progress", 100)
				crear_certificado(usuario, course_name)
				stats["completados"] += 1
				stats["certificados"] += 1

	# Usuarios restantes sin iniciar
	while idx < total:
		usuario = usuarios[idx]
		idx += 1
		enrollment = crear_enrollment(usuario, course_name)
		if enrollment:
			stats["enrollados"] += 1

	frappe.db.commit()
	return stats


def crear_enrollment(user_email, course_name):
	existing = frappe.db.get_value(
		"LMS Enrollment", {"member": user_email, "course": course_name}, "name"
	)
	if existing:
		return existing

	try:
		doc = frappe.get_doc(
			{
				"doctype": "LMS Enrollment",
				"member": user_email,
				"course": course_name,
				"member_type": "Student",
				"role": "Member",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception:
		return None


def crear_progreso_leccion(user_email, lesson_name):
	existing = frappe.db.get_value(
		"LMS Course Progress", {"member": user_email, "lesson": lesson_name}, "name"
	)
	if existing:
		return existing

	try:
		doc = frappe.get_doc(
			{
				"doctype": "LMS Course Progress",
				"member": user_email,
				"lesson": lesson_name,
				"status": "Complete",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception:
		return None


def crear_certificado(user_email, course_name):
	existing = frappe.db.get_value(
		"LMS Certificate", {"member": user_email, "course": course_name}, "name"
	)
	if existing:
		return existing

	template = frappe.db.get_value(
		"Print Format", {"doc_type": "LMS Certificate", "disabled": 0}, "name"
	)
	if not template:
		template = frappe.db.get_value("Print Format", {"disabled": 0}, "name")

	try:
		doc = frappe.get_doc(
			{
				"doctype": "LMS Certificate",
				"member": user_email,
				"course": course_name,
				"issue_date": today(),
				"template": template,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception:
		return None


def obtener_lecciones_curso(course_name):
	capitulos = frappe.get_all(
		"Course Chapter", filters={"course": course_name}, fields=["name"], order_by="creation asc"
	)
	lessons = []
	for cap in capitulos:
		ls = frappe.get_all(
			"Course Lesson", filters={"chapter": cap.name}, fields=["name"], order_by="creation asc"
		)
		lessons.extend([l.name for l in ls])
	return lessons
