# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

import secrets

import frappe
from frappe.model.document import Document
from frappe.utils import validate_email_address
from frappe.utils.password import update_password

from hubgh.hubgh.candidate_states import STATE_AFILIACION, STATE_DOCUMENTACION, is_candidate_status, normalize_candidate_status
from hubgh.hubgh.document_service import ensure_candidate_required_documents, set_candidate_status_from_progress
from hubgh.hubgh.onboarding_security import mark_user_for_first_login_password_reset


class Candidato(Document):
	def before_insert(self):
		self.ensure_user_link()

	def after_insert(self):
		ensure_candidate_required_documents(self.name)
		if not self.estado_proceso:
			self.estado_proceso = STATE_DOCUMENTACION

	def validate(self):
		self.estado_proceso = normalize_candidate_status(self.estado_proceso, default=STATE_DOCUMENTACION)
		self.sync_apellidos_compat()
		self.validate_unique_documento()
		self.validate_unique_email()
		self.autovincular_persona()
		self.validate_disponibilidad()

	def sync_apellidos_compat(self):
		primer = (self.primer_apellido or "").strip()
		segundo = (self.segundo_apellido or "").strip()
		if primer or segundo:
			self.apellidos = " ".join([p for p in [primer, segundo] if p]).strip()

	def on_update(self):
		set_candidate_status_from_progress(self.name)
		self.notify_candidate_on_status_change()

	def validate_unique_documento(self):
		if not self.numero_documento:
			return
		if frappe.db.exists(
			"Candidato",
			{"numero_documento": self.numero_documento, "name": ["!=", self.name]},
		):
			frappe.throw("El número de documento ya existe en otro candidato.")

	def validate_unique_email(self):
		if not self.email:
			return

		normalized_email = self.email.strip().lower()
		existing = frappe.db.sql(
			"""
			SELECT name
			FROM `tabCandidato`
			WHERE LOWER(email) = %s AND name != %s
			LIMIT 1
			""",
			(normalized_email, self.name or ""),
		)
		if existing:
			frappe.throw("El correo electrónico ya existe en otro candidato.")

	def autovincular_persona(self):
		if not self.numero_documento:
			return
		persona_name = frappe.db.get_value("Ficha Empleado", {"cedula": self.numero_documento})
		if persona_name:
			self.persona = persona_name

	def ensure_user_link(self):
		logger = frappe.logger("hubgh.candidato")
		self.flags.onboarding_user_created = False
		self.flags.onboarding_login_user = None
		self.flags.onboarding_initial_password = None
		logger.info(
			"ensure_user_link:start", extra={
				"candidato": self.name,
				"numero_documento": self.numero_documento,
				"user": self.user,
			}
		)
		self.autovincular_persona()
		if self.user and frappe.db.exists("User", self.user):
			logger.info("ensure_user_link:existing_user", extra={"user": self.user})
			self.flags.onboarding_login_user = self.user
			self._ensure_persona_for_user()
			return
		if not self.numero_documento:
			logger.warning("ensure_user_link:missing_numero_documento", extra={"candidato": self.name})
			return
		user_id = self.numero_documento
		user_doc = None
		if frappe.db.exists("User", user_id):
			user_doc = frappe.get_doc("User", user_id)
		else:
			user_doc_name = frappe.db.get_value("User", {"username": user_id}, "name")
			if user_doc_name:
				user_doc = frappe.get_doc("User", user_doc_name)
		if not user_doc:
			user_email = self._get_candidate_email(user_id)
			if frappe.db.exists("User", user_email) or frappe.db.exists("User", {"email": user_email}):
				user_doc = frappe.get_doc("User", user_email)
				self.user = user_doc.name
				self.flags.onboarding_login_user = user_doc.name
				self._ensure_candidato_role(user_doc.name)
				self._ensure_persona_for_user()
				return
			logger.info(
				"ensure_user_link:create_user", extra={
					"user_id": user_id,
					"user_email": user_email,
					"first_name": self.nombres,
					"last_name": self.apellidos,
				}
			)
			user_doc = frappe.get_doc({
				"doctype": "User",
				"email": user_email,
				"username": user_id,
				"first_name": self.nombres or user_id,
				"last_name": self.apellidos or "",
				"enabled": 1,
				"user_type": "Website User",
				"roles": [{"role": "Candidato"}],
			})
			user_doc.insert(ignore_permissions=True)
			temp_password = secrets.token_urlsafe(24)
			update_password(user_doc.name, temp_password)
			logger.info(
				"ensure_user_link:initial_password_generated",
				extra={"user": user_doc.name, "derived_from_document": 0},
			)
			frappe.db.set_value("User", user_doc.name, "last_password_reset_date", None, update_modified=False)
			mark_user_for_first_login_password_reset(user_doc.name)
			self.flags.onboarding_user_created = True
			self.flags.onboarding_login_user = user_doc.name
			self.flags.onboarding_initial_password = temp_password
			logger.info("ensure_user_link:user_created", extra={"user": user_doc.name})
		self.user = user_doc.name
		if not self.flags.onboarding_login_user:
			self.flags.onboarding_login_user = user_doc.name
		self._ensure_candidato_role(user_doc.name)
		self._ensure_persona_for_user()

	def _ensure_persona_for_user(self):
		if self.persona:
			return
		if not self.numero_documento:
			return
		persona_name = frappe.db.get_value("Ficha Empleado", {"cedula": self.numero_documento})
		if not persona_name:
			persona = frappe.get_doc({
				"doctype": "Ficha Empleado",
				"nombres": self.nombres,
				"apellidos": self.apellidos,
				"cedula": self.numero_documento,
				"pdv": self.pdv_destino,
				"cargo": self.cargo_postulado,
				"fecha_ingreso": self.fecha_tentativa_ingreso,
				"email": self.email,
				"candidato_origen": self.name,
				"numero_cuenta_bancaria": self.numero_cuenta_bancaria,
				"tipo_cuenta_bancaria": self.tipo_cuenta_bancaria,
				"banco_siesa": self.banco_siesa,
				"eps_siesa": self.eps_siesa,
				"afp_siesa": self.afp_siesa,
				"cesantias_siesa": self.cesantias_siesa,
				"ccf_siesa": self.ccf_siesa,
			}).insert(ignore_permissions=True, ignore_mandatory=True)
			persona_name = persona.name
		self.persona = persona_name

	def _get_candidate_email(self, user_id):
		if self.email and validate_email_address(self.email, throw=False):
			return self.email
		return f"{user_id}@candidato.local"

	def _ensure_candidato_role(self, user_id):
		if not user_id:
			return
		user_doc = frappe.get_doc("User", user_id)
		roles = {role.role if hasattr(role, "role") else role.get("role") for role in user_doc.roles}
		if "Candidato" not in roles:
			roles.add("Candidato")
			user_doc.set("roles", [{"role": role} for role in sorted(roles)])
			user_doc.save(ignore_permissions=True)

	def sync_documentos_requeridos(self):
		# Fase 4: método legado desactivado de forma explícita.
		# La sincronización documental ahora depende únicamente de Document Type + Person Document.
		return

	def update_estado_por_documentos(self):
		# Estado documental ahora se calcula sobre Person Document.
		return

	def validate_disponibilidad(self):
		if not hasattr(self, "disponibilidad") or not self.disponibilidad:
			return
		def to_minutes(value):
			if not value:
				return None
			if hasattr(value, "hour") and hasattr(value, "minute"):
				return value.hour * 60 + value.minute
			text = str(value)
			parts = text.split(":")
			if len(parts) < 2:
				return None
			try:
				hours = int(parts[0])
				minutes = int(parts[1])
			except ValueError:
				return None
			return hours * 60 + minutes

		for row in self.disponibilidad:
			hora_inicio = row.get("hora_inicio") if isinstance(row, dict) else row.hora_inicio
			hora_fin = row.get("hora_fin") if isinstance(row, dict) else row.hora_fin
			dia = row.get("dia") if isinstance(row, dict) else row.dia
			inicio_min = to_minutes(hora_inicio)
			fin_min = to_minutes(hora_fin)
			if inicio_min is None or fin_min is None:
				continue
			if inicio_min >= fin_min:
				frappe.throw(f"La hora inicio debe ser menor que la hora fin en {dia}.")

	def notify_candidate_on_status_change(self):
		if not self.user:
			return
		old = self.get_doc_before_save() if hasattr(self, "get_doc_before_save") else None
		if not old:
			return
		self._notify_pending_docs(old)
		self._notify_ready_for_review(old)

	def _notify_pending_docs(self, old_doc):
		if is_candidate_status(self.estado_proceso, STATE_DOCUMENTACION) and not is_candidate_status(
			old_doc.estado_proceso,
			STATE_DOCUMENTACION,
		):
			self._create_notification_log(
				subject="Tienes documentos pendientes",
				content="Aún tienes documentos pendientes por cargar o completar.",
			)

	def _notify_ready_for_review(self, old_doc):
		if is_candidate_status(self.estado_proceso, STATE_AFILIACION) and not is_candidate_status(
			old_doc.estado_proceso,
			STATE_AFILIACION,
		):
			self._create_notification_log(
				subject="Paso a afiliación",
				content="Tu proceso avanzó a afiliación para validación final con RRLL.",
			)

	def _create_notification_log(self, subject, content):
		frappe.get_doc({
			"doctype": "Notification Log",
			"subject": subject,
			"email_content": content,
			"for_user": self.user,
			"type": "Alert",
			"document_type": "Candidato",
			"document_name": self.name,
			"from_user": frappe.session.user,
		}).insert(ignore_permissions=True)

	@frappe.whitelist()
	def convertir_a_usuario(self):
		# Compatibilidad con botón legado: ahora marca Contratado.
		if self.persona:
			self.estado_proceso = "Contratado"
			self.save(ignore_permissions=True)
			return self.persona

		candidato_doc = self.numero_documento
		if not candidato_doc:
			frappe.throw("Debe existir el número de documento para convertir.")

		persona_name = frappe.db.get_value("Ficha Empleado", {"cedula": candidato_doc})
		if not persona_name:
			persona = frappe.get_doc({
				"doctype": "Ficha Empleado",
				"nombres": self.nombres,
				"apellidos": self.apellidos,
				"cedula": candidato_doc,
				"pdv": self.pdv_destino,
				"cargo": self.cargo_postulado,
				"fecha_ingreso": self.fecha_tentativa_ingreso,
				"email": self.email,
				"candidato_origen": self.name,
				"numero_cuenta_bancaria": self.numero_cuenta_bancaria,
				"tipo_cuenta_bancaria": self.tipo_cuenta_bancaria,
				"banco_siesa": self.banco_siesa,
				"eps_siesa": self.eps_siesa,
				"afp_siesa": self.afp_siesa,
				"cesantias_siesa": self.cesantias_siesa,
				"ccf_siesa": self.ccf_siesa,
			}).insert(ignore_permissions=True)
			persona_name = persona.name
		else:
			frappe.db.set_value(
				"Ficha Empleado",
				persona_name,
				{
					"nombres": self.nombres,
					"apellidos": self.apellidos,
					"pdv": self.pdv_destino,
					"cargo": self.cargo_postulado,
					"fecha_ingreso": self.fecha_tentativa_ingreso,
					"email": self.email,
					"candidato_origen": self.name,
					"numero_cuenta_bancaria": self.numero_cuenta_bancaria,
					"tipo_cuenta_bancaria": self.tipo_cuenta_bancaria,
					"banco_siesa": self.banco_siesa,
					"eps_siesa": self.eps_siesa,
					"afp_siesa": self.afp_siesa,
					"cesantias_siesa": self.cesantias_siesa,
					"ccf_siesa": self.ccf_siesa,
				},
			)

		self.persona = persona_name
		self.estado_proceso = "Contratado"
		self.ensure_user_link()
		self._upgrade_user_roles()
		self._ensure_persona_document_folder()
		self.save(ignore_permissions=True)
		return persona_name

	def _ensure_persona_document_folder(self):
		if not self.persona:
			return
		if frappe.db.exists("Persona Documento", {"persona": self.persona, "tipo_documento": "Carpeta"}):
			return
		frappe.get_doc({
			"doctype": "Persona Documento",
			"persona": self.persona,
			"tipo_documento": "Carpeta",
			"estado_documento": "Pendiente",
		}).insert(ignore_permissions=True)

	def _upgrade_user_roles(self):
		if not self.user:
			return
		user_doc = frappe.get_doc("User", self.user)
		roles = {role.role for role in user_doc.roles}
		roles.update({"Gestión Humana"})
		user_doc.roles = [{"role": role} for role in sorted(roles)]
		user_doc.user_type = "System User"
		user_doc.save(ignore_permissions=True)
