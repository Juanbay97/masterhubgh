# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CasoSST(Document):
	def validate(self):
		frappe.throw("Caso SST quedó en desuso operativo. Registra la novedad en Novedad SST (categoría SST).")

	def on_submit(self):
		self.create_novedad_relacionada()

	def create_novedad_relacionada(self):
		if not self.empleado:
			return

		tipo_novedad = "Accidente" if self.tipo_evento in {"Accidente", "Incidente"} else "Incapacidad"
		titulo = f"{self.tipo_evento or 'Evento SST'} - {self.severidad or 'Sin severidad'}"

		frappe.get_doc({
			"doctype": "Novedad SST",
			"empleado": self.empleado,
			"punto_venta": self.pdv,
			"categoria_novedad": "SST",
			"tipo_novedad": tipo_novedad,
			"fecha_inicio": self.fecha_evento,
			"titulo_resumen": titulo,
			"descripcion_resumen": self.descripcion,
			"descripcion": self.descripcion,
			"estado": "Abierta",
			"impacta_estado": 1,
			"estado_destino": "Incapacitado",
			"es_accidente_trabajo": 1 if tipo_novedad == "Accidente" else 0,
			"crear_alerta": 1,
			"dias_para_alerta": 30,
			"tipo_alerta": "Seguimiento",
			"alerta_activa": 1,
			"ref_doctype": "Caso SST",
			"ref_docname": self.name,
		}).insert(ignore_permissions=True)
