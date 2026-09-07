import frappe
from frappe.model.document import Document

from hubgh.hubgh.doctype.datos_contratacion.datos_contratacion import _has_bank_account
from hubgh.hubgh.people_ops_lifecycle import finalize_hiring


# Contract bank field -> field name used by Candidato and Datos Contratacion.
BANK_FIELD_SOURCES = {
	"cuenta_bancaria": "numero_cuenta_bancaria",
	"banco_siesa": "banco_siesa",
	"tipo_cuenta_bancaria": "tipo_cuenta_bancaria",
}
BANK_FIELD_LABELS = {
	"cuenta_bancaria": "Cuenta bancaria",
	"banco_siesa": "Banco",
	"tipo_cuenta_bancaria": "Tipo de cuenta",
}
BANK_SOURCE_FIELDS = [*BANK_FIELD_SOURCES.values(), "tiene_cuenta_bancaria"]


def _is_blank(value):
	return value is None or (isinstance(value, str) and not value.strip())


class Contrato(Document):
	def validate(self):
		self._set_defaults()
		self._ensure_numero_contrato()
		self._sync_candidate_snapshot()
		self._validate_dates()

	def before_submit(self):
		self._validate_bank_data_before_submit()

	def _ensure_numero_contrato(self):
		try:
			current = int(self.numero_contrato or 0)
		except Exception:
			current = 0

		if current > 1:
			return
		last_number = frappe.db.sql("select max(numero_contrato) from `tabContrato`")[0][0] or 0
		self.numero_contrato = int(last_number) + 1

	def _set_defaults(self):
		if not self.id_compania:
			self.id_compania = "4"
		if not self.id_proyecto:
			self.id_proyecto = "NM"
		if not self.sucursal_autoliquidacion:
			self.sucursal_autoliquidacion = "001"
		if not self.forma_pago:
			self.forma_pago = "2"
		if not self.estado_contrato:
			self.estado_contrato = "Pendiente"

	def _sync_candidate_snapshot(self):
		if not self.candidato:
			return
		cand = frappe.get_doc("Candidato", self.candidato)

		if not self.numero_documento:
			self.numero_documento = cand.numero_documento
		if not self.nombres:
			self.nombres = cand.nombres
		if not self.apellidos:
			self.apellidos = cand.apellidos
		if not self.email:
			self.email = cand.email
		if not self.cuenta_bancaria:
			self.cuenta_bancaria = cand.numero_cuenta_bancaria
		if not self.tipo_cuenta_bancaria:
			self.tipo_cuenta_bancaria = cand.tipo_cuenta_bancaria
		if not self.banco_siesa:
			self.banco_siesa = cand.banco_siesa
		self._fill_bank_fields_from_datos_contratacion()

		if not self.entidad_eps_siesa:
			self.entidad_eps_siesa = cand.eps_siesa
		if not self.entidad_afp_siesa:
			self.entidad_afp_siesa = cand.afp_siesa
		if not self.entidad_cesantias_siesa:
			self.entidad_cesantias_siesa = cand.cesantias_siesa
		if not self.entidad_ccf_siesa:
			self.entidad_ccf_siesa = cand.ccf_siesa

	def _fill_bank_fields_from_datos_contratacion(self):
		"""Fallback for bank data captured on Datos Contratacion but not yet on the Candidato."""
		if all(not _is_blank(getattr(self, field, None)) for field in BANK_FIELD_SOURCES):
			return
		datos = self._get_datos_contratacion_bank_data()
		if not datos:
			return
		for contract_field, source_field in BANK_FIELD_SOURCES.items():
			if _is_blank(getattr(self, contract_field, None)) and not _is_blank(datos.get(source_field)):
				setattr(self, contract_field, datos.get(source_field))

	def _get_datos_contratacion_bank_data(self):
		if not self.candidato:
			return None
		return frappe.db.get_value(
			"Datos Contratacion",
			{"candidato": self.candidato},
			BANK_SOURCE_FIELDS,
			as_dict=True,
		)

	def _validate_dates(self):
		if self.fecha_fin_contrato and self.fecha_ingreso and self.fecha_fin_contrato < self.fecha_ingreso:
			frappe.throw("La fecha fin no puede ser menor a la fecha de ingreso.")

	def _validate_bank_data_before_submit(self):
		"""Refuse to submit a contract with blank bank fields when the person is expected to have an account.

		Bank fields are not allow_on_submit, so a contract submitted without them can never be
		exported to SIESA (incident: candidate 1032391786 / CONT--10516).
		"""
		missing = [label for field, label in BANK_FIELD_LABELS.items() if _is_blank(getattr(self, field, None))]
		if not missing or not self._expects_bank_account():
			return
		frappe.throw(
			"No es posible enviar el contrato: faltan los datos bancarios ({campos}). "
			"Complete la información bancaria en el Candidato o en Datos Contratación "
			"antes de enviar el contrato.".format(campos=", ".join(missing))
		)

	def _expects_bank_account(self):
		"""True when the Contrato, Candidato or Datos Contratacion indicate the person has a bank account."""
		sources = [
			{source_field: getattr(self, contract_field, None) for contract_field, source_field in BANK_FIELD_SOURCES.items()}
		]
		if self.candidato:
			candidate = frappe.db.get_value("Candidato", self.candidato, BANK_SOURCE_FIELDS, as_dict=True)
			if candidate:
				sources.append(candidate)
			datos = self._get_datos_contratacion_bank_data()
			if datos:
				sources.append(datos)
		return any(_has_bank_account(source) for source in sources)

	def on_submit(self):
		result = finalize_hiring(self)
		employee = result.get("employee")
		if self.candidato:
			# Link contrato to Datos Contratacion
			self._sync_contrato_to_datos_contratacion()

	def _sync_contrato_to_datos_contratacion(self):
		"""Link this contrato to the Datos Contratacion record for the candidate."""
		if not self.candidato:
			return
		
		datos_name = frappe.db.get_value(
			"Datos Contratacion", 
			{"candidato": self.candidato}, 
			"name"
		)
		if datos_name:
			frappe.db.set_value(
				"Datos Contratacion",
				datos_name,
				"contrato",
				self.name,
				update_modified=False,
			)

	def _publish_ingreso_event(self, employee):
		if not employee or not frappe.db.exists("DocType", "GH Novedad"):
			return

		existing = frappe.db.exists(
			"GH Novedad",
			{
				"persona": employee,
				"tipo": "Otro",
				"fecha_inicio": self.fecha_ingreso,
				"descripcion": ["like", f"%{self.name}%"],
			},
		)
		if existing:
			return

		description = f"Ingreso formalizado desde contrato {self.name}"
		frappe.get_doc(
			{
				"doctype": "GH Novedad",
				"persona": employee,
				"punto": self.pdv_destino,
				"tipo": "Otro",
				"fecha_inicio": self.fecha_ingreso,
				"fecha_fin": self.fecha_ingreso,
				"descripcion": description,
				"estado": "Recibida",
				"cola_origen": "GH-RRLL",
				"cola_sugerida": "GH-RRLL",
				"cola_destino": "GH-RRLL",
			}
		).insert(ignore_permissions=True)

	def _ensure_employee(self):
		if self.empleado and frappe.db.exists("Ficha Empleado", self.empleado):
			return self.empleado

		if self.numero_documento:
			existing = frappe.db.get_value("Ficha Empleado", {"cedula": self.numero_documento})
			if existing:
				existing_candidate = frappe.db.get_value("Ficha Empleado", existing, "candidato_origen")
				if self.candidato and existing_candidate and existing_candidate != self.candidato:
					frappe.throw(
						"Conflicto de trazabilidad: el empleado existente ya está vinculado a otro candidato."
					)
				if self.candidato and not existing_candidate:
					frappe.db.set_value(
						"Ficha Empleado",
						existing,
						"candidato_origen",
						self.candidato,
						update_modified=False,
					)
				return existing

		employee = frappe.get_doc({
			"doctype": "Ficha Empleado",
			"nombres": self.nombres,
			"apellidos": self.apellidos,
			"cedula": self.numero_documento,
			"pdv": self.pdv_destino,
			"cargo": self.cargo,
			"tipo_jornada": self.tipo_jornada,
			"fecha_ingreso": self.fecha_ingreso,
			"email": self.email,
			"candidato_origen": self.candidato,
			"numero_cuenta_bancaria": self.cuenta_bancaria,
			"tipo_cuenta_bancaria": self.tipo_cuenta_bancaria,
			"banco_siesa": self.banco_siesa,
			"eps_siesa": self.entidad_eps_siesa,
			"afp_siesa": self.entidad_afp_siesa,
			"cesantias_siesa": self.entidad_cesantias_siesa,
			"ccf_siesa": self.entidad_ccf_siesa,
		}).insert(ignore_permissions=True, ignore_mandatory=True)
		return employee.name

	def _sync_employee_operational_data(self, employee):
		if not employee or not frappe.db.exists("Ficha Empleado", employee):
			return

		meta = frappe.get_meta("Ficha Empleado")
		fieldnames = {field.fieldname for field in meta.fields}
		updates = {}

		if "tipo_jornada" in fieldnames and self.tipo_jornada:
			updates["tipo_jornada"] = self.tipo_jornada
		if "pdv" in fieldnames and self.pdv_destino:
			updates["pdv"] = self.pdv_destino
		if "cargo" in fieldnames and self.cargo:
			updates["cargo"] = self.cargo
		if "fecha_ingreso" in fieldnames and self.fecha_ingreso:
			updates["fecha_ingreso"] = self.fecha_ingreso

		if updates:
			frappe.db.set_value("Ficha Empleado", employee, updates, update_modified=False)
