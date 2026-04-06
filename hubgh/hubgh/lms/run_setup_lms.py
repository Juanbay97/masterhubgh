import os

import frappe

from hubgh.lms.setup_curso_calidad import crear_curso_completo
from hubgh.lms.setup_demo_data import crear_data_sintetica_completud
from hubgh.setup_lms_config import setup_lms_settings


def setup_lms_completo(curso_dir=None, instructor_email="Administrator"):
	"""Setup integral LMS para HubGH."""
	if not curso_dir:
		curso_dir = _resolver_curso_dir()

	setup_lms_settings()
	curso = crear_curso_completo(curso_dir=curso_dir, instructor_email=instructor_email)
	stats = crear_data_sintetica_completud(course_name=curso["course"])
	frappe.db.commit()

	return {
		"ok": True,
		"course": curso["course"],
		"modulos": curso["modulos"],
		"enrollados": stats.get("enrollados", 0),
		"completados": stats.get("completados", 0),
		"certificados": stats.get("certificados", 0),
		"lms_url": f"/lms/courses/{curso['course']}",
	}


def _resolver_curso_dir():
	posibles_rutas = [
		"/workspace/frappe-bench/curso_calidad",
		"/frappe-bench/curso_calidad",
		"/home/frappe/frappe-bench/curso_calidad",
		os.path.join(os.getcwd(), "curso_calidad"),
	]
	for ruta in posibles_rutas:
		if os.path.exists(ruta):
			return ruta
	frappe.throw("No se encontró la carpeta curso_calidad en rutas conocidas.")

