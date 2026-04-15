import frappe
from frappe.model.document import Document


def _has_bank_account(doc):
	value = str((doc.get("tiene_cuenta_bancaria") if hasattr(doc, "get") else getattr(doc, "tiene_cuenta_bancaria", "")) or "").strip().lower()
	if value in {"si", "sí", "1", "true", "yes"}:
		return True
	for fieldname in ("banco_siesa", "tipo_cuenta_bancaria", "numero_cuenta_bancaria"):
		field_value = doc.get(fieldname) if hasattr(doc, "get") else getattr(doc, fieldname, None)
		if field_value not in (None, ""):
			return True
	return False


class DatosContratacion(Document):
	def validate(self):
		self._sync_from_candidate()
		self._sync_from_contract()
		self._set_estado()

	def _sync_from_candidate(self):
		if not self.candidato:
			return

		cand = frappe.get_doc("Candidato", self.candidato)

		if not self.tipo_documento:
			self.tipo_documento = cand.tipo_documento
		if not self.numero_documento:
			self.numero_documento = cand.numero_documento
		if not self.nombres:
			self.nombres = cand.nombres
		if not self.primer_apellido:
			self.primer_apellido = (cand.primer_apellido or "").strip()
		if not self.segundo_apellido:
			self.segundo_apellido = (cand.segundo_apellido or "").strip()
		if not self.primer_apellido and cand.apellidos:
			self.primer_apellido = (cand.apellidos or "").split(" ")[0] if cand.apellidos else ""
		if not self.segundo_apellido and cand.apellidos:
			parts = (cand.apellidos or "").split(" ")
			self.segundo_apellido = " ".join(parts[1:]) if len(parts) > 1 else ""

		for fieldname in (
			"fecha_nacimiento",
			"fecha_expedicion",
			"genero",
			"estado_civil",
			"nivel_educativo_siesa",
			"es_extranjero",
			"prefijo_cuenta_extranjero",
			"tiene_cuenta_bancaria",
			"direccion",
			"barrio",
			"ciudad",
			"procedencia_pais",
			"procedencia_departamento",
			"procedencia_ciudad",
			"departamento_residencia_siesa",
			"ciudad_residencia_siesa",
			"pais_residencia_siesa",
			"celular",
			"email",
			"numero_cuenta_bancaria",
			"tipo_cuenta_bancaria",
			"banco_siesa",
			"eps_siesa",
			"afp_siesa",
			"cesantias_siesa",
			"ccf_siesa",
			"pdv_destino",
			"cargo_postulado",
			"fecha_tentativa_ingreso",
		):
			if not self.get(fieldname):
				self.set(fieldname, cand.get(fieldname))

		if not self.telefono_contacto_siesa:
			self.telefono_contacto_siesa = cand.get("telefono_fijo")

		# Backfill automático para captura final SIESA usando procedencia/residencia
		pais_res = cand.get("pais_residencia_siesa") or cand.get("procedencia_pais")
		dep_res = cand.get("departamento_residencia_siesa") or cand.get("procedencia_departamento")
		ciu_res = cand.get("ciudad_residencia_siesa") or cand.get("procedencia_ciudad")

		if not self.pais_nacimiento_siesa and pais_res:
			self.pais_nacimiento_siesa = pais_res
		if not self.departamento_nacimiento_siesa and dep_res:
			self.departamento_nacimiento_siesa = dep_res
		if not self.ciudad_nacimiento_siesa and ciu_res:
			self.ciudad_nacimiento_siesa = ciu_res

		if not self.pais_expedicion_siesa and (self.pais_nacimiento_siesa or pais_res):
			self.pais_expedicion_siesa = self.pais_nacimiento_siesa or pais_res
		if not self.departamento_expedicion_siesa and (self.departamento_nacimiento_siesa or dep_res):
			self.departamento_expedicion_siesa = self.departamento_nacimiento_siesa or dep_res
		if not self.ciudad_expedicion_siesa and (self.ciudad_nacimiento_siesa or ciu_res):
			self.ciudad_expedicion_siesa = self.ciudad_nacimiento_siesa or ciu_res

	def _sync_from_contract(self):
		if not self.contrato:
			return

		if not frappe.db.exists("Contrato", self.contrato):
			return

		cont = frappe.get_doc("Contrato", self.contrato)
		for fieldname in (
			"numero_contrato",
			"tipo_contrato",
			"fecha_ingreso",
			"fecha_fin_contrato",
			"salario",
			"horas_trabajadas_mes",
			"centro_costos_siesa",
			"unidad_negocio_siesa",
			"grupo_empleados_siesa",
			"centro_trabajo_siesa",
			"tipo_cotizante_siesa",
		):
			if not self.get(fieldname):
				self.set(fieldname, cont.get(fieldname))

	def _set_estado(self):
		required = [
			"tipo_documento",
			"numero_documento",
			"nombres",
			"primer_apellido",
			"fecha_nacimiento",
			"nivel_educativo_siesa",
			"direccion",
			"celular",
			"email",
			"pdv_destino",
			"cargo_postulado",
			"fecha_ingreso",
			"salario",
			"centro_costos_siesa",
			"unidad_negocio_siesa",
			"centro_trabajo_siesa",
			"grupo_empleados_siesa",
			"tipo_cotizante_siesa",
			"pais_nacimiento_siesa",
			"departamento_nacimiento_siesa",
			"ciudad_nacimiento_siesa",
			"pais_expedicion_siesa",
			"departamento_expedicion_siesa",
			"ciudad_expedicion_siesa",
		]

		if _has_bank_account(self):
			required.extend([
				"banco_siesa",
				"numero_cuenta_bancaria",
				"tipo_cuenta_bancaria",
			])

		missing = [f for f in required if not self.get(f)]
		if missing:
			self.estado_datos = "Incompleto"
			return

		if self.estado_datos != "Enviado a SIESA":
			self.estado_datos = "Completo"
			if not self.fecha_completado:
				self.fecha_completado = frappe.utils.now_datetime()
			if not self.completado_por:
				self.completado_por = frappe.session.user
