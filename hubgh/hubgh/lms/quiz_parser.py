import re

import frappe


def parsear_evaluacion_docx(filepath):
	"""Parsea preguntas y opciones desde un DOCX de evaluación."""
	try:
		import docx as python_docx
	except ImportError:
		return []

	try:
		doc = python_docx.Document(filepath)
	except Exception:
		return []

	preguntas = []
	pregunta_actual = None

	for para in doc.paragraphs:
		texto = (para.text or "").strip()
		if not texto:
			continue

		match_pregunta = re.match(r"^(\d+)[.)]\s+(.+)", texto)
		if match_pregunta:
			if pregunta_actual:
				preguntas.append(pregunta_actual)
			pregunta_actual = {
				"pregunta": match_pregunta.group(2).strip(),
				"opciones": [],
			}
			continue

		match_opcion = re.match(r"^([a-eA-E])[.)]\s+(.+)", texto)
		if match_opcion and pregunta_actual:
			texto_opcion = match_opcion.group(2).strip()
			es_correcta = any((run.bold and (run.text or "").strip()) for run in para.runs)
			if "**" in texto_opcion or "__" in texto_opcion:
				es_correcta = True
				texto_opcion = texto_opcion.replace("**", "").replace("__", "").strip()

			pregunta_actual["opciones"].append(
				{"texto": texto_opcion, "es_correcta": es_correcta}
			)

	if pregunta_actual:
		preguntas.append(pregunta_actual)

	for preg in preguntas:
		if preg["opciones"] and not any(o["es_correcta"] for o in preg["opciones"]):
			preg["opciones"][0]["es_correcta"] = True

	return preguntas


def parsear_evaluacion_pdf(_filepath):
	"""Fallback básico para PDF sin extracción robusta: retorna vacío."""
	return []


def generar_quiz_sintetico(titulo_modulo, num_preguntas=5):
	base = [
		{
			"pregunta": f"¿Cuál es el objetivo principal del módulo '{titulo_modulo}'?",
			"opciones": [
				{"texto": "Garantizar la inocuidad y calidad de los alimentos", "es_correcta": True},
				{"texto": "Reducir únicamente costos", "es_correcta": False},
				{"texto": "Acelerar producción sin controles", "es_correcta": False},
			],
		},
		{
			"pregunta": "¿Quién es responsable del cumplimiento de normas de calidad?",
			"opciones": [
				{"texto": "Solo calidad", "es_correcta": False},
				{"texto": "Todos los colaboradores", "es_correcta": True},
				{"texto": "Solo supervisión", "es_correcta": False},
			],
		},
		{
			"pregunta": "Si detectas incumplimiento, ¿qué debes hacer?",
			"opciones": [
				{"texto": "Ignorarlo", "es_correcta": False},
				{"texto": "Reportarlo de inmediato", "es_correcta": True},
				{"texto": "Esperar auditoría", "es_correcta": False},
			],
		},
		{
			"pregunta": "¿Con qué frecuencia aplican estas prácticas?",
			"opciones": [
				{"texto": "Cuando hay visita", "es_correcta": False},
				{"texto": "Diariamente", "es_correcta": True},
				{"texto": "Semanalmente", "es_correcta": False},
			],
		},
		{
			"pregunta": "No cumplir inocuidad puede causar:",
			"opciones": [
				{"texto": "Sin consecuencias", "es_correcta": False},
				{"texto": "Riesgo sanitario y sanciones", "es_correcta": True},
				{"texto": "Solo impacto estético", "es_correcta": False},
			],
		},
	]
	return base[:num_preguntas]
