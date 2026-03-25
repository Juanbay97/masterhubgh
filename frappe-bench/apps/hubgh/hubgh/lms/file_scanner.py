import os
import re

import frappe


TIPOS = {
	"presentacion": {".pptx", ".ppt", ".pdf"},
	"video": {".mp4", ".avi", ".mkv", ".mov", ".webm"},
	"video_link": {".txt"},
	"evaluacion": {".docx", ".doc", ".txt", ".pdf"},
}


def escanear_modulos(curso_dir: str):
	"""Escanea carpetas del curso y detecta archivos por módulo."""
	if not os.path.exists(curso_dir):
		frappe.throw(f"No se encuentra la carpeta del curso en: {curso_dir}")

	carpetas = [
		d for d in os.listdir(curso_dir) if os.path.isdir(os.path.join(curso_dir, d))
	]
	carpetas = sorted(
		carpetas,
		key=lambda x: int(re.match(r"^(\d+)", x).group(1)) if re.match(r"^(\d+)", x) else 999,
	)

	modulos = []
	for carpeta in carpetas:
		match = re.match(r"^(\d+)\.\s*(.+)", carpeta)
		if not match:
			continue

		num_modulo = int(match.group(1))
		nombre_modulo = re.sub(r"\s+ok\s*$", "", match.group(2).strip(), flags=re.IGNORECASE)
		carpeta_path = os.path.join(curso_dir, carpeta)

		archivos = {
			"presentacion": None,
			"video": None,
			"video_link": None,
			"evaluacion": None,
			"otros": [],
		}

		for archivo in os.listdir(carpeta_path):
			archivo_path = os.path.join(carpeta_path, archivo)
			if not os.path.isfile(archivo_path):
				continue

			ext = os.path.splitext(archivo.lower())[1]
			nombre = archivo.lower()

			if ext in TIPOS["presentacion"] and archivos["presentacion"] is None:
				archivos["presentacion"] = archivo_path
			elif ext in TIPOS["video"] and archivos["video"] is None:
				archivos["video"] = archivo_path
			elif ext in TIPOS["video_link"]:
				try:
					with open(archivo_path, "r", encoding="utf-8") as f:
						content = f.read().strip()
						if content.startswith("http"):
							archivos["video_link"] = content
				except Exception:
					archivos["otros"].append(archivo_path)
			elif ext in TIPOS["evaluacion"] and any(k in nombre for k in ["eval", "pregunt", "quiz", "test"]):
				archivos["evaluacion"] = archivo_path
			else:
				archivos["otros"].append(archivo_path)

		modulos.append(
			{
				"numero": num_modulo,
				"nombre": nombre_modulo,
				"carpeta": carpeta_path,
				"titulo_completo": f"Módulo {num_modulo}: {nombre_modulo}",
				"archivos": archivos,
			}
		)

	return modulos

