# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""Controller del DocType `Correccion Datos Candidato`.

Workflow lógico (Batch 5):
  - `validate`: normaliza campos, recalcula `fase` server-side (nunca confiar
	en el cliente) y captura `valor_anterior` como snapshot del estado actual.
  - `before_submit`:
	  * Fase `pre_contrato`: aplica la cascada inmediatamente.
	  * Fase `post_contrato`: exige rol aprobador (Gerente GH / System Manager)
		y aplica la cascada. NO usa Workflow formal de Frappe todavía — eso se
		introduce en el Batch 7 vía patch. Acá solo hay chequeo server-side.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from hubgh.hubgh.candidate_correction_service import (
	PERSONAL_DATA_FIELDS,
	apply_correction,
	get_correction_phase,
)


_APPROVER_ROLES = {"Gerente GH", "System Manager"}


class CorreccionDatosCandidato(Document):
	def before_insert(self):
		# El Workflow oficial sólo permite la transición Borrador → Pendiente
		# Aprobación vía la acción "Solicitar Aprobación". Por eso SIEMPRE
		# insertamos en estado "Borrador"; si la fase es post_contrato,
		# `on_insert` dispara la transición vía workflow API (es decir,
		# `apply_workflow`), que es lo único que el motor de Frappe acepta.
		self.fase = get_correction_phase(self.candidato) if self.candidato else self.fase
		self.workflow_state = "Borrador"

	# NOTE: la transición Borrador → "Pendiente Aprobación" para post_contrato
	# NO se aplica en `on_insert` porque (a) `apply_workflow` queda atrapado
	# en el flow de inserción de Frappe y no persiste el cambio, y (b)
	# `frappe.db.set_value` desde `on_insert` puede ser sobrescrito al
	# completar el flow. La transición se ejecuta en la capa API
	# (`api/correcciones.submit_candidate_correction`) después del insert.

	def validate(self):
		if not self.candidato:
			frappe.throw(_("Candidato es requerido"))
		if not self.motivo or not str(self.motivo).strip():
			frappe.throw(_("Motivo de la corrección es obligatorio"))
		if not self.solicitante:
			self.solicitante = frappe.session.user

		# Fase SIEMPRE se recalcula server-side; nunca confiar en el cliente.
		self.fase = get_correction_phase(self.candidato)

		# Snapshot del valor previo. Se recaptura en cada validate por si el
		# Candidato cambió entre save y submit.
		self._capture_valor_anterior()

	def _capture_valor_anterior(self):
		if not self.candidato or not self.campo_corregido:
			return
		if self.campo_corregido == "email":
			self.valor_anterior = (
				frappe.db.get_value("Candidato", self.candidato, "email") or ""
			)
		elif self.campo_corregido == "cedula":
			self.valor_anterior = (
				frappe.db.get_value("Candidato", self.candidato, "numero_documento")
				or ""
			)
		elif self.campo_corregido == "cuenta_bancaria":
			row = frappe.db.get_value(
				"Candidato",
				self.candidato,
				[
					"numero_cuenta_bancaria",
					"tipo_cuenta_bancaria",
					"banco_siesa",
				],
				as_dict=True,
			)
			self.valor_anterior = frappe.as_json(row or {})
		elif self.campo_corregido == "datos_personales":
			row = frappe.db.get_value(
				"Candidato",
				self.candidato,
				list(PERSONAL_DATA_FIELDS),
				as_dict=True,
			)
			self.valor_anterior = frappe.as_json(row or {})

	def before_submit(self):
		# Pre-contrato: aplica directo. Post-contrato: requiere aprobador.
		if self.fase == "pre_contrato":
			self._apply_now()
		elif self.fase == "post_contrato":
			self._enforce_approver_or_block()
			self._apply_now()
		else:
			frappe.throw(_("Fase desconocida: {0}").format(self.fase))

	def _enforce_approver_or_block(self):
		user_roles = set(frappe.get_roles(frappe.session.user))
		if not (user_roles & _APPROVER_ROLES):
			frappe.throw(
				_(
					"Una corrección post-contrato requiere aprobación de un "
					"Gerente GH o System Manager"
				),
				frappe.PermissionError,
			)
		self.aprobador = frappe.session.user

	def _apply_now(self):
		# `apply_correction` setea `afectados_resumen` y `fecha_aplicacion`.
		apply_correction(self)
