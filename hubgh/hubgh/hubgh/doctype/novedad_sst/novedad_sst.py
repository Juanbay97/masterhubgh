# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, cstr, getdate, nowdate

from hubgh.hubgh.document_service import move_file_to_employee_subfolder
from hubgh.hubgh.people_ops_lifecycle import apply_retirement, reverse_retirement_if_clear


RADAR_CATEGORIAS = {
	"Gestante",
	"Lactante",
	"Condición médica",
	"AT abierto",
	"Incapacidad larga",
	"Padre gestante",
}

TIPO_ACCIDENTE = "Accidente"
TIPO_RECOMENDACION = "Recomendación Médica"
TIPO_AFORADO = "Aforado"
TIPO_INCAPACIDAD_EG = "Incapacidad por enfermedad general"
TIPO_SEGUIMIENTO = "Seguimiento SST"
TIPO_PRORROGA_INCAPACIDAD = "Prórroga incapacidad"
DIAS_INCAPACIDAD_POST_EXAMEN = 30
DIAS_ANTICIPO_ALERTA_POST_INCAPACIDAD = 7


class NovedadSST(Document):
	def validate(self):
		self.sync_incapacidad_controls()
		self.normalize_prorroga_rows()
		self.sync_pdv_from_employee()
		self.relocate_incapacidad_files_to_employee_folder()
		self.normalize_estado_fields()
		self.apply_domain_defaults()
		self.validate_sst_taxonomy()
		self.validate_dates_consistency()
		self.calculate_dias_incapacidad()
		self.validate_sst_payload()
		self.ensure_tipo_accidente_flags()
		self.ensure_radar()
		self.ensure_estado_destino()
		self.ensure_retiro_consistency()
		self.ensure_alerta_base()
		self.apply_estado_empleado()

	def after_insert(self):
		self.ensure_sst_alerta_record(notify=True)

	def on_update(self):
		self.apply_estado_empleado()
		self.ensure_sst_alerta_record(notify=False)
		self.ensure_retiro_traceability_event()

	def ensure_retiro_consistency(self):
		"""S5.3: retiro final state must be closed and traceable."""
		if self.get_estado_destino() != "Retirado":
			return
		is_cerrado = (self.estado or "").lower() in {"cerrada", "cerrado"}
		if not is_cerrado:
			frappe.throw("La novedad de retiro debe estar cerrada para finalizar el estado Retirado.")

	def sync_pdv_from_employee(self):
		if self.punto_venta or not self.empleado:
			return
		self.punto_venta = (
			frappe.db.get_value("Ficha Empleado", self.empleado, "pdv")
			or frappe.defaults.get_user_default("Punto de Venta")
			or frappe.defaults.get_user_default("punto_venta")
		)

	def normalize_estado_fields(self):
		mapping = {
			"Abierto": "Abierta",
			"Cerrado": "Cerrada",
		}
		self.estado = mapping.get(self.estado, self.estado)

	def apply_domain_defaults(self):
		if self.tipo_novedad in {TIPO_ACCIDENTE, TIPO_RECOMENDACION, TIPO_AFORADO, TIPO_INCAPACIDAD_EG}:
			self.categoria_novedad = "SST"

	def validate_sst_taxonomy(self):
		rrll_tipos = {"Suspensión", "Separación del Cargo", "Retiro", "Abandono de Cargo", "Terminación"}
		if self.tipo_novedad in rrll_tipos:
			frappe.throw("Las novedades RRLL deben registrarse en GH Novedad (cola GH-RRLL), no en Novedad SST.")

	def validate_dates_consistency(self):
		if self.fecha_inicio and self.fecha_fin and getdate(self.fecha_fin) < getdate(self.fecha_inicio):
			frappe.throw("La fecha fin no puede ser menor que la fecha inicio.")

	def calculate_dias_incapacidad(self):
		if not self.is_incapacidad_case() or not self.fecha_inicio or not self.fecha_fin:
			self.dias_incapacidad = 0
			return

		start = getdate(self.fecha_inicio)
		end = getdate(self.fecha_fin)
		self.dias_incapacidad = max((end - start).days + 1, 0)

	def validate_sst_payload(self):
		if self.tipo_novedad == TIPO_ACCIDENTE:
			self.validate_accidente_payload()
		elif self.tipo_novedad == TIPO_RECOMENDACION:
			self.validate_recomendacion_payload()
		elif self.tipo_novedad == TIPO_AFORADO:
			self.validate_aforado_payload()
		elif self.is_incapacidad_case():
			self.validate_incapacidad_payload()

	def sync_incapacidad_controls(self):
		"""UI helper sync: checkbox drives tipo_novedad, but tipo_novedad remains canonical."""
		es_incapacidad = cint(getattr(self, "es_incapacidad", 0))
		if es_incapacidad and self.tipo_novedad not in {"Incapacidad", TIPO_INCAPACIDAD_EG}:
			self.tipo_novedad = TIPO_INCAPACIDAD_EG

		# Keep checkbox consistent when user selects type directly.
		self.es_incapacidad = 1 if self.is_incapacidad_case() else 0

	def validate_accidente_payload(self):
		accidente_tuvo_incapacidad = getattr(self, "accidente_tuvo_incapacidad", None)
		if accidente_tuvo_incapacidad is None:
			frappe.throw("En accidentes debes indicar si hubo incapacidad (Sí/No).")

		if not self.causa_evento:
			frappe.throw("La causa del accidente es obligatoria.")

		if cint(accidente_tuvo_incapacidad):
			self.ensure_incapacidad_fields_required()

	def validate_recomendacion_payload(self):
		if not cstr(self.recomendaciones_detalle).strip():
			frappe.throw("Debes registrar el texto de recomendaciones médicas.")
		if not self.fecha_inicio or not self.fecha_fin:
			frappe.throw("Debes registrar fecha inicio y fecha fin para la recomendación médica.")
		self.impacta_estado = 0

	def validate_aforado_payload(self):
		if not cstr(getattr(self, "aforado_motivo", "")).strip():
			frappe.throw("Debes registrar el motivo del aforamiento.")
		if not getattr(self, "aforado_desde", None):
			self.aforado_desde = self.fecha_inicio or nowdate()

	def validate_incapacidad_payload(self):
		self.ensure_incapacidad_fields_required()
		self.ensure_prorroga_consistency()

	def relocate_incapacidad_files_to_employee_folder(self):
		"""Persist incapacity files under employee subfolder for multi-record reuse."""
		if not self.empleado:
			return

		is_case = self.is_incapacidad_case() or (
			self.tipo_novedad == TIPO_ACCIDENTE and cint(getattr(self, "accidente_tuvo_incapacidad", 0))
		)
		if not is_case:
			return

		cedula = (frappe.db.get_value("Ficha Empleado", self.empleado, "cedula") or "").strip()
		base = cedula or self.empleado

		evidencia = getattr(self, "evidencia_incapacidad", None)
		if evidencia:
			self.evidencia_incapacidad = move_file_to_employee_subfolder(
				evidencia,
				self.empleado,
				"incapacidades",
				filename_prefix=f"{base}-incapacidad-principal",
			)

		for idx, row in enumerate(getattr(self, "prorrogas_incapacidad", []) or [], start=1):
			adjunto = getattr(row, "adjunto", None)
			if not adjunto:
				continue
			row.adjunto = move_file_to_employee_subfolder(
				adjunto,
				self.empleado,
				"incapacidades",
				filename_prefix=f"{base}-incapacidad-prorroga-{idx}",
			)

	def ensure_prorroga_consistency(self):
		has_prorrogas = bool(getattr(self, "prorrogas_incapacidad", None) and len(self.prorrogas_incapacidad))
		if has_prorrogas and not self.is_incapacidad_case():
			frappe.throw("Las prórrogas solo aplican a novedades con incapacidad asociada.")
		if cint(getattr(self, "prorroga", 0)) and not has_prorrogas:
			frappe.throw("Marcaste prórroga, pero no registraste filas en Prórrogas Incapacidad.")
		if has_prorrogas:
			self.prorroga = 1

	def normalize_prorroga_rows(self):
		legacy_prorrogas = []
		seguimientos_normales = []

		for row in list(getattr(self, "seguimientos", []) or []):
			payload = self._build_sst_followup_payload(row)
			if payload["tipo_seguimiento"] == TIPO_PRORROGA_INCAPACIDAD:
				legacy_prorrogas.append(payload)
				continue
			seguimientos_normales.append(payload)

		prorrogas = []
		seen = set()
		for row in list(getattr(self, "prorrogas_incapacidad", []) or []):
			payload = self._build_sst_followup_payload(row, forced_type=TIPO_PRORROGA_INCAPACIDAD)
			fingerprint = self._sst_followup_fingerprint(payload)
			if fingerprint in seen:
				continue
			seen.add(fingerprint)
			prorrogas.append(payload)

		for payload in legacy_prorrogas:
			fingerprint = self._sst_followup_fingerprint(payload)
			if fingerprint in seen:
				continue
			seen.add(fingerprint)
			prorrogas.append(payload)

		self.set("seguimientos", seguimientos_normales)
		self.set("prorrogas_incapacidad", prorrogas)

	def _build_sst_followup_payload(self, row, forced_type=None):
		return {
			"fecha_seguimiento": getattr(row, "fecha_seguimiento", None),
			"tipo_seguimiento": forced_type or cstr(getattr(row, "tipo_seguimiento", None)).strip() or TIPO_SEGUIMIENTO,
			"detalle": getattr(row, "detalle", None),
			"estado_resultante": getattr(row, "estado_resultante", None),
			"proxima_accion_fecha": getattr(row, "proxima_accion_fecha", None),
			"responsable": getattr(row, "responsable", None),
			"adjunto": getattr(row, "adjunto", None),
		}

	def _sst_followup_fingerprint(self, payload):
		return (
			cstr(payload.get("fecha_seguimiento")).strip(),
			cstr(payload.get("tipo_seguimiento")).strip(),
			cstr(payload.get("detalle")).strip(),
			cstr(payload.get("estado_resultante")).strip(),
			cstr(payload.get("proxima_accion_fecha")).strip(),
			cstr(payload.get("responsable")).strip(),
			cstr(payload.get("adjunto")).strip(),
		)

	def ensure_incapacidad_fields_required(self):
		if not cstr(getattr(self, "diagnostico_corto", "")).strip():
			frappe.throw("El diagnóstico corto es obligatorio para incapacidades.")
		if not getattr(self, "evidencia_incapacidad", None):
			frappe.throw("Debes adjuntar la evidencia de incapacidad.")
		if not self.fecha_inicio or not self.fecha_fin:
			frappe.throw("Debes registrar fecha inicio y fecha fin para la incapacidad.")
		self.impacta_estado = 1
		self.estado_destino = "Incapacitado"

	def ensure_tipo_accidente_flags(self):
		if self.tipo_novedad == TIPO_ACCIDENTE and self.es_accidente_trabajo is None:
			self.es_accidente_trabajo = 1

	def ensure_radar(self):
		if self.tipo_novedad == TIPO_AFORADO:
			self.en_radar = 1
			if not self.categoria_seguimiento:
				self.categoria_seguimiento = "Condición médica"
			return

		if self.categoria_seguimiento in RADAR_CATEGORIAS:
			self.en_radar = 1
		elif self.is_incapacidad_case() and (self.dias_incapacidad or 0) >= 30:
			self.en_radar = 1
			if not self.categoria_seguimiento:
				self.categoria_seguimiento = "Incapacidad larga"

	def ensure_alerta_base(self):
		if not cint(self.alerta_activa):
			return

		if self.tipo_novedad == TIPO_RECOMENDACION and self.fecha_fin:
			self.crear_alerta = 1
			self.tipo_alerta = "Vencimiento recomendación médica"
			self.frecuencia_alerta = "Única"
			self.proxima_alerta_fecha = add_days(self.fecha_fin, -7)
			if not self.descripcion_resumen:
				self.descripcion_resumen = "Revisar vencimiento de recomendación médica"
			return

		aforado_desde = getattr(self, "aforado_desde", None)
		if self.tipo_novedad == TIPO_AFORADO and aforado_desde:
			self.crear_alerta = 1
			self.tipo_alerta = "Seguimiento aforado semestral"
			self.frecuencia_alerta = "Recurrente"
			self.proxima_alerta_fecha = add_months(aforado_desde, 6)
			self.fecha_proxima_alerta_aforado = self.proxima_alerta_fecha
			if not self.descripcion_resumen:
				self.descripcion_resumen = "Seguimiento semestral de personal aforado"
			return

		if self.requires_post_incapacidad_alert() and self.fecha_fin:
			self.crear_alerta = 1
			self.tipo_alerta = "Examen post incapacidad"
			self.frecuencia_alerta = "Única"
			self.proxima_alerta_fecha = add_days(self.fecha_fin, -DIAS_ANTICIPO_ALERTA_POST_INCAPACIDAD)
			if not self.descripcion_resumen:
				self.descripcion_resumen = "Programar examen médico post incapacidad antes del reintegro"
			return

		if cint(self.crear_alerta):
			if not self.tipo_alerta:
				self.tipo_alerta = "Seguimiento"
			if not self.frecuencia_alerta:
				self.frecuencia_alerta = "Única"
			if not self.proxima_alerta_fecha:
				frappe.throw("Debes registrar la fecha en que debe dispararse la alerta.")

	def ensure_sst_alerta_record(self, notify=False):
		if not cint(self.alerta_activa):
			return
		if not cint(self.crear_alerta):
			return
		if not self.proxima_alerta_fecha:
			return

		alerta = frappe.db.get_value("SST Alerta", {"novedad": self.name}, "name")
		values = {
			"empleado": self.empleado,
			"punto_venta": self.punto_venta,
			"fecha_programada": self.proxima_alerta_fecha,
			"tipo_alerta": self.tipo_alerta or "Seguimiento",
			"asignado_a": self.get_alert_assignee(),
			"mensaje": self.get_alert_message(),
			"canal": "In-app",
		}

		if alerta:
			current = frappe.db.get_value(
				"SST Alerta",
				alerta,
				["estado", "referencia_todo", "atendida_en", "ultima_notificacion"],
				as_dict=True,
			) or {}
			values["estado"] = current.get("estado") or "Pendiente"
			frappe.db.set_value("SST Alerta", alerta, values)
			if current.get("referencia_todo"):
				frappe.db.set_value("SST Alerta", alerta, "referencia_todo", current.get("referencia_todo"), update_modified=False)
			if current.get("atendida_en"):
				frappe.db.set_value("SST Alerta", alerta, "atendida_en", current.get("atendida_en"), update_modified=False)
			if current.get("ultima_notificacion"):
				frappe.db.set_value("SST Alerta", alerta, "ultima_notificacion", current.get("ultima_notificacion"), update_modified=False)
			if notify:
				create_sst_todo(alerta)
			return

		doc = frappe.get_doc({"doctype": "SST Alerta", "novedad": self.name, "estado": "Pendiente", **values})
		doc.insert(ignore_permissions=True)
		if notify:
			create_sst_todo(doc.name)

	def get_alert_assignee(self):
		for role in ("HR SST", "SST", "System Manager"):
			users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent", limit=1)
			if users:
				return users[0]
		return None

	def get_alert_message(self):
		base = cstr(self.titulo_resumen or self.descripcion_resumen or self.descripcion or self.tipo_novedad)
		if self.tipo_alerta == "Examen post incapacidad":
			return "Programar examen médico post incapacidad antes del reintegro"
		if self.tipo_alerta == "Vencimiento recomendación médica":
			return "La recomendación médica vence en una semana. Validar continuidad o cierre."
		if self.tipo_alerta == "Seguimiento aforado semestral":
			return "Seguimiento semestral de personal aforado pendiente."
		return f"Seguimiento SST pendiente: {base}".strip()

	def get_estado_destino(self):
		return (getattr(self, "estado_destino", "") or "").strip() or None

	def get_impacta_estado(self):
		return bool(getattr(self, "impacta_estado", 0))

	def ensure_estado_destino(self):
		if not self.get_impacta_estado():
			return
		if self.estado_destino:
			return
		mapped = self.get_estado_destino_from_tipo()
		if mapped:
			self.estado_destino = mapped

	def get_estado_destino_from_tipo(self):
		mapping = {
			"Incapacidad": "Incapacitado",
			TIPO_INCAPACIDAD_EG: "Incapacitado",
			"Licencia": "Licencia",
			"Vacaciones": "Vacaciones",
			"Suspensión": "Suspensión",
			"Separación del Cargo": "Separación del Cargo",
			"Recomendación Médica": "Recomendación Médica",
			"Embarazo": "Embarazo",
			"Retiro": "Retirado",
		}
		return mapping.get(self.tipo_novedad)

	def apply_estado_empleado(self):
		if not self.empleado:
			return

		today = getdate(nowdate())
		fecha_fin = getdate(self.fecha_fin) if self.fecha_fin else None
		estado_actual = self.get_estado_actual()
		estado_target = self.get_estado_destino()
		is_cerrado = (self.estado or "").lower() in {"cerrada", "cerrado"}
		is_expired = bool(fecha_fin and fecha_fin < today)

		if not self.get_impacta_estado():
			if estado_actual in self.get_estados_temporales():
				self.update_empleado_estado("Activo")
			return

		if estado_target == "Retirado":
			if is_cerrado:
				apply_retirement(
					employee=self.empleado,
					source_doctype="Novedad SST",
					source_name=self.name,
					retirement_date=self.fecha_fin or self.fecha_inicio or nowdate(),
					reason=self.descripcion_resumen or self.descripcion or self.tipo_novedad,
				)
			else:
				reverse_retirement_if_clear(employee=self.empleado, source_doctype="Novedad SST", source_name=self.name)
			return

		if estado_target and not is_cerrado and not is_expired:
			self.update_empleado_estado(estado_target)
			return

		if estado_actual in self.get_estados_temporales():
			self.update_empleado_estado("Activo")

	def get_estado_actual(self):
		return frappe.db.get_value("Ficha Empleado", self.empleado, "estado")

	def update_empleado_estado(self, estado):
		frappe.db.set_value("Ficha Empleado", self.empleado, "estado", estado)

	def ensure_retiro_traceability_event(self):
		if self.get_estado_destino() != "Retirado":
			return

		if not frappe.db.exists("DocType", "GH Novedad"):
			return

		is_cerrado = (self.estado or "").lower() in {"cerrada", "cerrado"}
		if not is_cerrado:
			return

		existing = frappe.db.exists(
			"GH Novedad",
			{
				"persona": self.empleado,
				"tipo": "Otro",
				"descripcion": ["like", f"%retiro controlado desde novedad {self.name}%"],
			},
		)
		if existing:
			return

		frappe.get_doc(
			{
				"doctype": "GH Novedad",
				"persona": self.empleado,
				"punto": self.punto_venta,
				"tipo": "Otro",
				"cola_destino": "GH-RRLL",
				"estado": "Cerrada",
				"fecha_inicio": self.fecha_inicio or nowdate(),
				"fecha_fin": self.fecha_fin or self.fecha_inicio or nowdate(),
				"descripcion": f"Retiro controlado desde novedad {self.name}",
			}
		).insert(ignore_permissions=True)

	def get_estados_temporales(self):
		return {
			"Vacaciones",
			"Incapacitado",
			"Licencia",
			"Suspensión",
			"Separación del Cargo",
			"Recomendación Médica",
			"Embarazo",
		}

	def is_incapacidad_case(self):
		return self.tipo_novedad in {"Incapacidad", TIPO_INCAPACIDAD_EG} or (
			self.tipo_novedad == TIPO_ACCIDENTE and cint(getattr(self, "accidente_tuvo_incapacidad", 0))
		)

	def requires_post_incapacidad_alert(self):
		return self.is_incapacidad_case() and cint(self.dias_incapacidad) > DIAS_INCAPACIDAD_POST_EXAMEN


def cint(value):
	try:
		return int(value or 0)
	except Exception:
		return 0


def _build_rrll_handoff_description(novedad_doc, motivo=None):
	base = cstr(motivo).strip() or cstr(getattr(novedad_doc, "titulo_resumen", None)).strip() or cstr(
		getattr(novedad_doc, "descripcion_resumen", None)
	).strip() or cstr(getattr(novedad_doc, "tipo_novedad", None)).strip() or "Caso SST"
	return f"Escalamiento RRLL desde Novedad SST {novedad_doc.name}. {base}"


def _validate_rrll_escalation_rules(novedad_doc):
	"""Throws frappe.ValidationError if novedad does not meet RRLL escalation criteria.

	Both conditions must hold simultaneously:
	  - origen_incapacidad == "Accidente laboral"
	  - causa_evento == "Acto inseguro"
	This helper runs AFTER the role check, BEFORE any GH Novedad creation.
	"""
	if getattr(novedad_doc, "origen_incapacidad", None) != "Accidente laboral":
		frappe.throw(
			_(
				"Solo se puede escalar a RRLL cuando el origen de la incapacidad es 'Accidente laboral'. "
				"El caso actual tiene origen: {0}."
			).format(novedad_doc.get("origen_incapacidad") or "no definido")
		)
	if getattr(novedad_doc, "causa_evento", None) != "Acto inseguro":
		frappe.throw(
			_(
				"Solo se puede escalar a RRLL cuando la causa del evento es 'Acto inseguro'. "
				"El caso actual tiene causa: {0}."
			).format(novedad_doc.get("causa_evento") or "no definida")
		)


@frappe.whitelist()
def create_rrll_handoff(novedad_name, motivo=None):
	if not novedad_name:
		frappe.throw("Falta novedad_name")
	if not frappe.db.exists("DocType", "GH Novedad"):
		frappe.throw("GH Novedad no esta disponible en este sitio")

	novedad = frappe.get_doc("Novedad SST", novedad_name)
	if not novedad.empleado:
		frappe.throw("La Novedad SST debe tener empleado para escalar a RRLL")

	roles = set(frappe.get_roles() or [])
	allowed_roles = {"System Manager", "Gestión Humana", "HR SST", "SST", "GH - SST", "GH - RRLL"}
	if not roles.intersection(allowed_roles) and not frappe.has_permission("Novedad SST", "write", novedad):
		frappe.throw("No tienes permisos para escalar este caso SST a RRLL")

	# Business-rule gate: both origen_incapacidad and causa_evento must qualify
	_validate_rrll_escalation_rules(novedad)

	if novedad.ref_doctype == "GH Novedad" and novedad.ref_docname:
		return {"ok": True, "created": False, "gh_novedad": novedad.ref_docname}

	description = _build_rrll_handoff_description(novedad, motivo)
	existing = frappe.db.get_value(
		"GH Novedad",
		{
			"persona": novedad.empleado,
			"descripcion": ["like", f"%Novedad SST {novedad.name}%"],
		},
		"name",
	)
	if existing:
		frappe.db.set_value("Novedad SST", novedad.name, {"ref_doctype": "GH Novedad", "ref_docname": existing}, update_modified=False)
		return {"ok": True, "created": False, "gh_novedad": existing}

	gh_novedad = frappe.get_doc(
		{
			"doctype": "GH Novedad",
			"persona": novedad.empleado,
			"punto": novedad.punto_venta,
			"tipo": "Otro",
			"fecha_inicio": novedad.fecha_inicio or nowdate(),
			"fecha_fin": novedad.fecha_fin,
			"descripcion": description,
			"estado": "Recibida",
			"cola_origen": "GH-SST",
			"cola_destino": "GH-RRLL",
		}
	)
	gh_novedad.insert(ignore_permissions=True)
	frappe.db.set_value(
		"Novedad SST",
		novedad.name,
		{"ref_doctype": "GH Novedad", "ref_docname": gh_novedad.name},
		update_modified=False,
	)
	return {"ok": True, "created": True, "gh_novedad": gh_novedad.name}


def create_sst_todo(alerta_name):
	alerta = frappe.get_doc("SST Alerta", alerta_name)
	if alerta.referencia_todo and frappe.db.exists("ToDo", alerta.referencia_todo):
		return

	if not alerta.asignado_a:
		return

	todo = frappe.get_doc(
		{
			"doctype": "ToDo",
			"allocated_to": alerta.asignado_a,
			"description": alerta.mensaje or f"Alerta SST pendiente para {alerta.novedad}",
			"date": alerta.fecha_programada,
			"reference_type": "SST Alerta",
			"reference_name": alerta.name,
		}
	)
	todo.insert(ignore_permissions=True)
	frappe.db.set_value("SST Alerta", alerta.name, "referencia_todo", todo.name)
