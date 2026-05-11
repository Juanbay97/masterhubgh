# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

_EVIDENCIA_ALLOWED_EXTENSIONS = frozenset({
	".pdf", ".jpg", ".jpeg", ".png", ".gif",
	".mp4", ".mp3", ".wav", ".docx", ".xlsx",
})
_EVIDENCIA_MAX_FILE_SIZE_MB = 10


class EvidenciaDisciplinaria(Document):
	def before_save(self):
		if not self.cargado_por:
			self.cargado_por = frappe.session.user
		if not self.fecha_carga:
			self.fecha_carga = frappe.utils.now()

	def validate(self):
		self._validate_caso_or_afectado()
		self._validate_archivo()

	def _validate_caso_or_afectado(self):
		"""Al menos uno de caso o afectado debe estar lleno."""
		if not self.caso and not self.afectado:
			frappe.throw(
				_("La Evidencia Disciplinaria debe vincularse al menos a un Caso o a un Afectado."),
				frappe.ValidationError,
			)

	def _validate_archivo(self):
		"""Valida extensión y tamaño del archivo adjunto."""
		if not self.archivo:
			return

		import os
		ext = os.path.splitext(self.archivo)[-1].lower()
		if ext not in _EVIDENCIA_ALLOWED_EXTENSIONS:
			frappe.throw(
				_("Tipo de archivo no permitido: {0}. Extensiones válidas: {1}").format(
					ext or "(sin extensión)",
					", ".join(sorted(_EVIDENCIA_ALLOWED_EXTENSIONS)),
				),
				frappe.ValidationError,
			)

		# Resolve file size via File doctype when available
		if self.archivo.startswith("/files/") or self.archivo.startswith("/private/files/"):
			file_doc = frappe.db.get_value(
				"File",
				{"file_url": self.archivo},
				["file_size"],
				as_dict=True,
			)
			if file_doc:
				file_size = (
					file_doc.get("file_size")
					if isinstance(file_doc, dict)
					else getattr(file_doc, "file_size", None)
				)
				if file_size:
					max_bytes = _EVIDENCIA_MAX_FILE_SIZE_MB * 1024 * 1024
					if file_size > max_bytes:
						frappe.throw(
							_("El archivo supera el tamaño máximo permitido de {0} MB.").format(
								_EVIDENCIA_MAX_FILE_SIZE_MB
							),
							frappe.ValidationError,
						)
