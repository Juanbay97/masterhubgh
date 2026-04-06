import os
import shutil
import json

import frappe

from hubgh.lms.file_scanner import escanear_modulos
from hubgh.lms.quiz_parser import generar_quiz_sintetico, parsear_evaluacion_docx, parsear_evaluacion_pdf


COURSE_NAME = "calidad-e-inocuidad-alimentaria"
COURSE_TITLE = "Calidad e Inocuidad Alimentaria"


def _content_json_html(html):
	return json.dumps(
		{
			"time": 0,
			"blocks": [
				{
					"type": "paragraph",
					"data": {
						"text": html,
					},
				}
			],
			"version": "2.0",
		}
	)


def crear_curso_completo(curso_dir="/workspace/frappe-bench/curso_calidad", instructor_email="Administrator"):
	"""Crea/actualiza el curso de calidad en LMS a partir de carpetas locales."""
	if not frappe.db.exists("DocType", "LMS Course"):
		frappe.throw("LMS no está instalado en este sitio.")

	modulos = escanear_modulos(curso_dir)
	if not modulos:
		frappe.throw(f"No se detectaron módulos en: {curso_dir}")

	if not frappe.db.exists("User", instructor_email):
		instructor_email = "Administrator"

	_eliminar_curso_existente(COURSE_NAME)

	curso = frappe.get_doc(
		{
			"doctype": "LMS Course",
			"name": COURSE_NAME,
			"title": COURSE_TITLE,
			"short_introduction": "Programa interno de capacitación para inocuidad y aseguramiento de calidad.",
			"description": (
				"Curso de formación interna para colaboradores operativos y de soporte "
				"en temas de inocuidad alimentaria y control de calidad."
			),
			"published": 1,
			"disable_self_learning": 0,
			"enable_certification": 1,
			"tags": "calidad,inocuidad,bpm,normatividad",
			"instructors": [{"instructor": instructor_email}],
		}
	)
	curso.insert(ignore_permissions=True)

	for modulo in modulos:
		_crear_capitulo_modulo(curso.name, modulo)

	frappe.db.commit()
	return {"course": curso.name, "modulos": len(modulos)}


def _eliminar_curso_existente(course_name):
	if not frappe.db.exists("LMS Course", course_name):
		return

	capitulos = frappe.get_all("Course Chapter", filters={"course": course_name}, pluck="name")
	lecciones = []
	if capitulos:
		lecciones = frappe.get_all("Course Lesson", filters={"chapter": ["in", capitulos]}, pluck="name")

	for lesson in lecciones:
		quiz_id = frappe.db.get_value("Course Lesson", lesson, "quiz_id")
		frappe.delete_doc("Course Lesson", lesson, force=True, ignore_permissions=True)
		if quiz_id and frappe.db.exists("LMS Quiz", quiz_id):
			frappe.delete_doc("LMS Quiz", quiz_id, force=True, ignore_permissions=True)

	for chapter in capitulos:
		frappe.delete_doc("Course Chapter", chapter, force=True, ignore_permissions=True)

	frappe.delete_doc("LMS Course", course_name, force=True, ignore_permissions=True)


def _crear_capitulo_modulo(course_name, modulo):
	capitulo = frappe.get_doc(
		{
			"doctype": "Course Chapter",
			"course": course_name,
			"title": modulo["titulo_completo"],
		}
	)
	capitulo.insert(ignore_permissions=True)

	archivos = modulo["archivos"]
	if archivos.get("presentacion"):
		_crear_leccion_presentacion(capitulo.name, modulo, archivos["presentacion"])

	video_src = archivos.get("video") or archivos.get("video_link")
	if video_src:
		_crear_leccion_video(capitulo.name, modulo, video_src)

	evaluacion = archivos.get("evaluacion")
	_crear_leccion_evaluacion(capitulo.name, modulo, evaluacion)


def _crear_leccion_presentacion(chapter_name, modulo, archivo_path):
	file_url = subir_archivo_frappe(archivo_path, is_private=0)
	nombre = modulo["nombre"]

	content_html = (
		f"<h3>Presentación: {nombre}</h3>"
		f"<p>Material de estudio del módulo.</p>"
		f"<p><a href='{file_url}' target='_blank'>Abrir material</a></p>"
	)

	leccion = frappe.get_doc(
		{
			"doctype": "Course Lesson",
			"title": f"Presentación: {nombre}",
			"chapter": chapter_name,
			"content": _content_json_html(content_html),
			"include_in_preview": 1,
		}
	)
	leccion.insert(ignore_permissions=True)
	return leccion.name


def _crear_leccion_video(chapter_name, modulo, video_src):
	nombre = modulo["nombre"]
	if isinstance(video_src, str) and video_src.startswith("http"):
		content_html = (
			f"<h3>Video: {nombre}</h3>"
			f"<p><a href='{video_src}' target='_blank'>Ver video del módulo</a></p>"
		)
	else:
		file_url = subir_archivo_frappe(video_src, is_private=0)
		content_html = (
			f"<h3>Video: {nombre}</h3>"
			f"<video width='100%' controls><source src='{file_url}' type='video/mp4'></video>"
		)

	leccion = frappe.get_doc(
		{
			"doctype": "Course Lesson",
			"title": f"Video: {nombre}",
			"chapter": chapter_name,
			"content": _content_json_html(content_html),
			"include_in_preview": 0,
		}
	)
	leccion.insert(ignore_permissions=True)
	return leccion.name


def _crear_leccion_evaluacion(chapter_name, modulo, evaluacion_path=None):
	nombre = modulo["nombre"]
	preguntas = []

	if evaluacion_path and os.path.exists(evaluacion_path):
		ext = os.path.splitext(evaluacion_path)[1].lower()
		if ext == ".docx":
			preguntas = parsear_evaluacion_docx(evaluacion_path)
		elif ext == ".pdf":
			preguntas = parsear_evaluacion_pdf(evaluacion_path)

	if not preguntas:
		preguntas = generar_quiz_sintetico(nombre, num_preguntas=5)

	quiz = _crear_quiz_desde_preguntas(modulo, preguntas)

	content_html = (
		f"<h3>Evaluación: {nombre}</h3>"
		"<p>Responde la evaluación para completar el módulo.</p>"
	)
	leccion = frappe.get_doc(
		{
			"doctype": "Course Lesson",
			"title": f"Evaluación: {nombre}",
			"chapter": chapter_name,
			"content": _content_json_html(content_html),
			"quiz_id": quiz.name,
			"include_in_preview": 0,
		}
	)
	leccion.insert(ignore_permissions=True)
	return leccion.name


def _crear_quiz_desde_preguntas(modulo, preguntas):
	quiz_title = f"Evaluación Módulo {modulo['numero']}: {modulo['nombre']}"
	quiz_name = f"quiz-modulo-{modulo['numero']}-calidad"

	if frappe.db.exists("LMS Quiz", quiz_name):
		frappe.delete_doc("LMS Quiz", quiz_name, force=True, ignore_permissions=True)

	quiz = frappe.get_doc(
		{
			"doctype": "LMS Quiz",
			"name": quiz_name,
			"title": quiz_title,
			"passing_percentage": 70,
			"max_attempts": 3,
			"show_answers": 1,
			"questions": [],
		}
	)

	for idx, preg in enumerate(preguntas, start=1):
		question_doc = _crear_lms_question(modulo, idx, preg)
		quiz.append(
			"questions",
			{
				"question": question_doc.name,
				"marks": 1,
			},
		)

	quiz.insert(ignore_permissions=True)
	return quiz


def _crear_lms_question(modulo, idx, pregunta):
	qid = f"QTS-CALIDAD-{modulo['numero']:02d}-{idx:03d}"
	if frappe.db.exists("LMS Question", qid):
		frappe.delete_doc("LMS Question", qid, force=True, ignore_permissions=True)

	opciones = (pregunta.get("opciones") or [])[:4]
	while len(opciones) < 2:
		opciones.append({"texto": f"Opción {len(opciones)+1}", "es_correcta": False})

	values = {
		"doctype": "LMS Question",
		"name": qid,
		"question": pregunta.get("pregunta") or f"Pregunta {idx}",
		"type": "Choices",
	}

	for n in range(1, 5):
		opc = opciones[n - 1] if n <= len(opciones) else {"texto": "", "es_correcta": False}
		values[f"option_{n}"] = opc.get("texto") or ""
		values[f"is_correct_{n}"] = 1 if opc.get("es_correcta") else 0

	q = frappe.get_doc(values)
	q.insert(ignore_permissions=True)
	return q


def subir_archivo_frappe(filepath, is_private=0):
	"""Sube archivo local al gestor de archivos y devuelve file_url."""
	filename = os.path.basename(filepath)
	existing = frappe.db.get_value("File", {"file_name": filename}, "file_url")
	if existing:
		return existing

	max_size_mb = 24
	file_size = os.path.getsize(filepath)
	if file_size > (max_size_mb * 1024 * 1024):
		# Fallback para videos/pesados: copiar a public/files y referenciar por URL
		site_path = frappe.get_site_path("public", "files")
		os.makedirs(site_path, exist_ok=True)
		dest_path = os.path.join(site_path, filename)
		if not os.path.exists(dest_path):
			shutil.copy2(filepath, dest_path)

		file_url = f"/files/{filename}"
		return file_url

	with open(filepath, "rb") as f:
		content = f.read()

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"is_private": is_private,
			"content": content,
			"decode": False,
		}
	)
	file_doc.insert(ignore_permissions=True)
	return file_doc.file_url
