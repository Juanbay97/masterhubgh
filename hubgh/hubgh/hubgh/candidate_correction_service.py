# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Servicio central de corrección de datos del candidato/empleado.

Batch 1: solo stubs y resolución de fase. Las cascadas reales (email, cédula,
cuenta bancaria) se implementan en batches posteriores. Cada handler stub
deja un Comment auditable y devuelve un payload marcado con `_stub`.
"""

from __future__ import annotations

import re
from typing import Optional

import frappe
from frappe import _
from frappe.utils import validate_email_address

from hubgh.hubgh.onboarding_security import send_user_activation_email


# Opciones válidas para `tipo_cuenta_bancaria` (sincronizado con candidato.json
# y contrato.json). Si cambian las opciones, actualizar acá también.
_TIPO_CUENTA_BANCARIA_OPTIONS = {"Ahorros", "Corriente", "Tarjeta Prepago"}
_CUENTA_NUMERO_RE = re.compile(r"^\d{4,30}$")

# Cédula colombiana: 6 a 12 dígitos (rango pragmático). Si se necesita un rango
# distinto, ajustar este regex y la documentación del campo en `candidato.json`.
_CEDULA_RE = re.compile(r"^\d{6,12}$")

# Estados de Afiliacion Seguridad Social que NO bloquean la corrección de cédula.
# Cualquier otro estado (`En Proceso`, `Completado`, etc.) bloquea porque ya hay
# trámites externos (EPS/AFP) asociados a la cédula vieja.
_AFILIACION_ESTADOS_NO_BLOQUEANTES = {"Pendiente"}


# ---------------------------------------------------------------------------
# Datos personales — definiciones compartidas con el controller y la UI
# ---------------------------------------------------------------------------

# Listado público de campos editables del candidato bajo el bucket
# `datos_personales`. El orden NO importa para la cascada; sirve para tomar
# snapshot de `valor_anterior` y para validar que el cliente no mande keys
# fuera del whitelist. NO incluye `tipo_documento` ni los campos bancarios/
# cédula/email (esos tienen su propio handler).
PERSONAL_DATA_FIELDS = (
	# Identidad
	"nombres",
	"apellidos",
	"primer_apellido",
	"segundo_apellido",
	# Fechas
	"fecha_nacimiento",
	"fecha_expedicion",
	# Contacto
	"celular",
	"telefono_fijo",
	"contacto_emergencia_nombre",
	"contacto_emergencia_telefono",
	# Demográficos
	"genero",
	"estado_civil",
	"nivel_educativo_siesa",
	"es_extranjero",
	# Dirección
	"ciudad",
	"localidad",
	"localidad_otras",
	"barrio",
	"direccion",
	# Procedencia / residencia (SIESA)
	"procedencia_pais",
	"procedencia_departamento",
	"procedencia_ciudad",
	"pais_residencia_siesa",
	"departamento_residencia_siesa",
	"ciudad_residencia_siesa",
)

# Subconjunto de identidad que dispara cascada a User y a snapshots de Contrato.
_PERSONAL_NAME_FIELDS = {"nombres", "apellidos", "primer_apellido", "segundo_apellido"}

# Mapeo Candidato → Ficha Empleado (campos en común). NO incluye los nombres,
# que se manejan aparte porque también cascadean al User. Si un campo NO está
# acá, NO se cascadea a Ficha (Ficha simplemente no tiene la columna).
_FICHA_COMMON_FIELDS = ("nombres", "apellidos")

# Mapeo Candidato → Contrato.snapshot. Contrato guarda un snapshot de identidad
# en `nombres` y `apellidos` (read_only). Si cambian los nombres, hay que
# refrescar el snapshot.
_CONTRATO_NAME_FIELDS = ("nombres", "apellidos")

# Opciones permitidas para Selects del Candidato — sincronizado con candidato.json.
_GENERO_OPTIONS = {"Masculino", "Femenino", "Otro"}
_ESTADO_CIVIL_OPTIONS = {"Soltero", "Casado", "Unión Libre", "Divorciado", "Viudo"}
_LOCALIDAD_OPTIONS = {
	"Antonio Nariño", "Barrios Unidos", "Bosa", "Chapinero", "Ciudad Bolivar",
	"Engativa", "Fontibon", "Kennedy", "La Candelaria", "Los Martires",
	"Puente Aranda", "Rafael Uribe Uribe", "San Cristobal", "Santa Fe", "Suba",
	"Sumapaz", "Teusaquillo", "Tunjuelito", "Usaquen", "Usme",
}


# ---------------------------------------------------------------------------
# Resolución de fase
# ---------------------------------------------------------------------------

def get_correction_phase(candidato_name: str) -> str:
	"""Determina si la corrección es pre o post contrato.

	Retorna `post_contrato` cuando:
	  - El Candidato tiene `persona` (Ficha Empleado vinculada), Y
	  - Existe un Contrato submitted (docstatus=1) para ese candidato.

	Caso contrario retorna `pre_contrato`.
	"""
	if not candidato_name:
		return "pre_contrato"

	persona = frappe.db.get_value("Candidato", candidato_name, "persona")
	if not persona:
		return "pre_contrato"

	# El FK directo en Contrato hacia el Candidato es `candidato`. También existe
	# `empleado` (Ficha Empleado), pero usar `candidato` es más simple y suficiente
	# para detectar la existencia de un contrato submitted.
	has_contract = frappe.db.exists(
		"Contrato",
		{"candidato": candidato_name, "docstatus": 1},
	)
	return "post_contrato" if has_contract else "pre_contrato"


# ---------------------------------------------------------------------------
# Punto de entrada de cascada
# ---------------------------------------------------------------------------

def apply_correction(correccion_doc):
	"""Punto de entrada único.

	Batch 1 (stub): selecciona el handler según `campo_corregido`, registra un
	Comment auditable en el Candidato y persiste el resumen en el propio doc.
	No ejecuta cascadas reales todavía.
	"""
	candidato = correccion_doc.candidato
	campo = correccion_doc.campo_corregido

	handlers = {
		"email": _apply_email_change,
		"cedula": _apply_cedula_change,
		"cuenta_bancaria": _apply_cuenta_change,
		"datos_personales": _apply_personal_data_change,
	}
	handler = handlers.get(campo)
	if not handler:
		frappe.throw(_("Campo no soportado: {0}").format(campo))

	afectados = handler(correccion_doc)
	correccion_doc.afectados_resumen = frappe.as_json(afectados)
	correccion_doc.fecha_aplicacion = frappe.utils.now()

	# Para los handlers stub seguimos registrando un Comment genérico aquí. El
	# handler real de email registra su propio Comment con detalle y devuelve el
	# `comment_id` en `afectados_resumen`, por eso lo salteamos en ese caso.
	if not afectados.get("comment_id"):
		frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Candidato",
			"reference_name": candidato,
			"content": (
				f"[CORRECCIÓN STUB] Campo: {campo} | "
				f"Motivo: {correccion_doc.motivo} | "
				f"Solicitante: {correccion_doc.solicitante}"
			),
		}).insert(ignore_permissions=True)

	return afectados


# ---------------------------------------------------------------------------
# Handlers stub (Batch 1)
# ---------------------------------------------------------------------------

def _apply_email_change(doc):
	"""Cascada real de corrección de email (Batch 2).

	Pasos:
	  1. Validar formato y unicidad del nuevo email.
	  2. Dentro de un savepoint:
	     - Actualizar `Candidato.email`.
	     - Resolver User vinculado; si existe, hacer `frappe.rename_doc("User", old, new)`
	       y re-vincular `Candidato.user`.
	     - Si el User no estaba activado (enabled=0 o last_login null), reenviar
	       el email de bienvenida via `send_user_activation_email`.
	     - Si el User estaba activo, invalidar sesiones via
	       `frappe.sessions.clear_sessions`.
	  3. Registrar Comment auditable con el detalle del cambio.

	Rollback al savepoint si cualquier paso falla.
	"""
	candidato_name = doc.candidato
	new_email_raw = (doc.valor_nuevo or "").strip()
	new_email = new_email_raw.lower()

	if not new_email:
		frappe.throw(_("Debes indicar el nuevo email."))

	# 1. Validación de formato (raises si inválido).
	validate_email_address(new_email, throw=True)

	# Datos actuales del candidato.
	candidato_row = frappe.db.get_value(
		"Candidato",
		candidato_name,
		["email", "user"],
		as_dict=True,
	)
	if not candidato_row:
		frappe.throw(_("Candidato no encontrado: {0}").format(candidato_name))

	old_email = (candidato_row.get("email") or "").strip()
	old_user = candidato_row.get("user")

	# 2. Unicidad en Candidato (excluyendo el propio).
	dup_candidato = frappe.db.sql(
		"""
		SELECT name
		FROM `tabCandidato`
		WHERE LOWER(email) = %s AND name != %s
		LIMIT 1
		""",
		(new_email, candidato_name),
	)
	if dup_candidato:
		frappe.throw(_("El correo electrónico ya existe en otro candidato."))

	# 3. Unicidad en User: no debe existir un User con ese name distinto al actual.
	if frappe.db.exists("User", new_email) and new_email != (old_user or "").lower():
		frappe.throw(_("Ya existe un usuario con ese correo electrónico."))

	# 4. Operación atómica vía savepoint.
	frappe.db.savepoint("email_correction")
	try:
		# Actualizar Candidato.email.
		frappe.db.set_value("Candidato", candidato_name, "email", new_email)

		user_renamed = False
		user_was_active = False
		sessions_invalidated = False
		welcome_email_resent = False
		user_updated = False
		reason = None
		user_new_name = None

		if old_user:
			user_info = frappe.db.get_value(
				"User",
				old_user,
				["enabled", "last_login"],
				as_dict=True,
			) or {}
			enabled = bool(user_info.get("enabled"))
			last_login = user_info.get("last_login")
			user_was_active = enabled and last_login is not None

			# Rename del User (User.name = email en Frappe).
			# NOTE: `frappe.rename_doc` (el wrapper público) en Frappe v15 NO
			# acepta `ignore_permissions`. El solicitante (HR Selection) suele
			# no tener write sobre User, así que escalamos a Administrator
			# alrededor del rename y luego restauramos. La validación de quién
			# puede solicitar la corrección ya se hizo antes en el flow.
			_original_user = frappe.session.user
			try:
				frappe.set_user("Administrator")
				frappe.rename_doc(
					"User",
					old_user,
					new_email,
					merge=False,
				)
			finally:
				frappe.set_user(_original_user)
			user_renamed = True
			user_new_name = new_email

			# Re-vincular Candidato.user.
			frappe.db.set_value("Candidato", candidato_name, "user", new_email)
			user_updated = True

			if user_was_active:
				frappe.sessions.clear_sessions(user=new_email)
				sessions_invalidated = True
			else:
				send_user_activation_email(new_email)
				welcome_email_resent = True
		else:
			reason = "no_user_linked"

		# 5. Comment auditable.
		comment_doc = frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Candidato",
			"reference_name": candidato_name,
			"content": (
				f"[CORRECCIÓN EMAIL] campo=email | "
				f"valor_anterior={old_email} | valor_nuevo={new_email} | "
				f"motivo={doc.motivo} | solicitante={doc.solicitante} | "
				f"user_renamed={user_renamed} | "
				f"sessions_invalidated={sessions_invalidated} | "
				f"email_resent={welcome_email_resent}"
			),
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.db.rollback(save_point="email_correction")
		raise

	resumen = {
		"campo": "email",
		"candidato": candidato_name,
		"user_old": old_user,
		"user_new": user_new_name,
		"user_updated": user_updated,
		"user_renamed": user_renamed,
		"user_was_active": user_was_active,
		"sessions_invalidated": sessions_invalidated,
		"welcome_email_resent": welcome_email_resent,
		"comment_id": comment_doc.name,
	}
	if reason:
		resumen["reason"] = reason
	return resumen


def _apply_cedula_change(doc):
	"""Cascada real de corrección de cédula (Batch 4).

	Contexto crítico descubierto durante implementación:
	  - `Candidato.autoname = "format:{numero_documento}"` → Candidato.name = cédula.
	  - `Ficha Empleado.autoname = "format:{cedula}"` → Ficha Empleado.name = cédula.
	  - `User.name` = email (NO cédula). `User.username` = cédula. Por eso solo
	    actualizamos `username` con `set_value`, NO renombramos el User.
	  - `Person Document.person` es Dynamic Link a `Candidato.name` (no a la
	    cédula como Data). Como Frappe propaga `rename_doc` a todos los Link FKs,
	    NO hace falta tocar Person Document manualmente.
	  - `Afiliacion Seguridad Social.candidato` es Link a Candidato → también se
	    actualiza solo via `rename_doc`.

	Pasos:
	  1. Validar formato (`^\\d{6,12}$`).
	  2. Validar unicidad: no debe existir otro Candidato/Ficha con esa cédula.
	  3. Bloquear si hay alguna Afiliacion Seguridad Social en estado distinto
	     a "Pendiente" (porque ya hubo trámite externo con la cédula vieja).
	  4. Dentro de un savepoint:
	     - `rename_doc("Candidato", old, new)` → Frappe propaga a todos los FKs.
	     - Si hay Ficha Empleado vinculada: `rename_doc("Ficha Empleado", old, new)`.
	     - Si hay User vinculado: actualizar `username` con `set_value`.
	     - Registrar Comment auditable.

	Rollback al savepoint si cualquier paso falla.
	"""
	candidato_name = doc.candidato
	nueva_cedula = (doc.valor_nuevo or "").strip()

	# 1. Validación de formato.
	if not _CEDULA_RE.match(nueva_cedula):
		frappe.throw(_("Cédula inválida: debe contener entre 6 y 12 dígitos."))

	# Estado actual del candidato.
	candidato_row = frappe.db.get_value(
		"Candidato",
		candidato_name,
		["numero_documento", "persona", "user"],
		as_dict=True,
	)
	if not candidato_row:
		frappe.throw(_("Candidato no encontrado: {0}").format(candidato_name))

	old_cedula = (candidato_row.get("numero_documento") or "").strip()
	old_persona = candidato_row.get("persona")  # Ficha Empleado.name (= cédula vieja)
	old_user = candidato_row.get("user")  # User.name (= email)

	# Si la cédula no cambia, error: el panel no debería permitir esto.
	if old_cedula == nueva_cedula:
		frappe.throw(_("La cédula nueva es igual a la actual."))

	# 2. Unicidad en Candidato (excluyendo el propio).
	if frappe.db.exists("Candidato", {"numero_documento": nueva_cedula, "name": ["!=", candidato_name]}):
		frappe.throw(_("Ya existe otro candidato con esa cédula."))

	# 3. Unicidad en Ficha Empleado (excluyendo la vinculada al candidato actual).
	# Como `Ficha Empleado.name = cedula`, basta con preguntar por `name`.
	ficha_dup_filters = {"cedula": nueva_cedula}
	if old_persona:
		ficha_dup_filters["name"] = ["!=", old_persona]
	if frappe.db.exists("Ficha Empleado", ficha_dup_filters):
		frappe.throw(_("Ya existe otra ficha de empleado con esa cédula."))

	# 4. Bloqueo por afiliaciones en estado != Pendiente.
	afiliaciones = frappe.get_all(
		"Afiliacion Seguridad Social",
		filters={"candidato": candidato_name},
		fields=["name", "estado_general"],
	)
	bloqueantes = [
		a for a in afiliaciones
		if (a.get("estado_general") or "") not in _AFILIACION_ESTADOS_NO_BLOQUEANTES
	]
	if bloqueantes:
		nombres = ", ".join(f"{a['name']} ({a.get('estado_general')})" for a in bloqueantes)
		frappe.throw(
			_(
				"No se puede corregir la cédula: existen afiliaciones de seguridad "
				"social en trámite o completadas que están atadas a la cédula "
				"actual. Hay que cancelarlas o reabrirlas manualmente antes de "
				"corregir la cédula. Afiliaciones afectadas: {0}"
			).format(nombres)
		)

	# 5. Operación atómica vía savepoint.
	frappe.db.savepoint("cedula_correction")
	ficha_renamed = False
	new_persona = None
	user_username_updated = False
	try:
		# a) Rename del Candidato. Frappe propaga a TODOS los Link FKs que
		# apunten a "Candidato" (Contrato.candidato, Person Document.candidate,
		# Afiliacion.candidato, Datos Contratacion, etc.). Esto es la razón
		# por la cual no hace falta actualizar manualmente esas tablas.
		# `frappe.rename_doc` (wrapper público) en Frappe v15 NO acepta
		# `ignore_permissions`. El aprobador (Gerente GH / System Manager)
		# en post_contrato suele tener write, pero escalamos a Administrator
		# para asegurar idempotencia con otras corridas administrativas.
		_original_user = frappe.session.user
		try:
			frappe.set_user("Administrator")
			frappe.rename_doc(
				"Candidato",
				candidato_name,
				nueva_cedula,
				merge=False,
			)
		finally:
			frappe.set_user(_original_user)
		new_candidato_name = nueva_cedula

		# Actualizar también el campo `numero_documento` (el rename cambia .name
		# pero NO los campos del documento). Mantenerlos en sync es importante
		# porque hay código que lee `numero_documento` directamente.
		frappe.db.set_value("Candidato", new_candidato_name, "numero_documento", nueva_cedula)

		# b) Rename de la Ficha Empleado (autoname = cedula).
		if old_persona:
			_original_user2 = frappe.session.user
			try:
				frappe.set_user("Administrator")
				frappe.rename_doc(
					"Ficha Empleado",
					old_persona,
					nueva_cedula,
					merge=False,
				)
			finally:
				frappe.set_user(_original_user2)
			new_persona = nueva_cedula
			ficha_renamed = True
			# Actualizar el campo `cedula` de la Ficha (idem razón que arriba).
			frappe.db.set_value("Ficha Empleado", new_persona, "cedula", nueva_cedula)
			# Re-vincular Candidato.persona al nuevo nombre. El rename del
			# Candidato YA actualiza la mayoría de FKs, pero `Candidato.persona`
			# apunta a Ficha Empleado (no a Candidato), así que el rename de
			# la Ficha es lo que dispara su actualización en otros docs. Acá
			# además dejamos explícito el valor en el propio Candidato.
			frappe.db.set_value("Candidato", new_candidato_name, "persona", new_persona)

		# c) User: NO renombramos (User.name = email). Solo actualizamos username.
		if old_user and frappe.db.exists("User", old_user):
			frappe.db.set_value("User", old_user, "username", nueva_cedula)
			user_username_updated = True

		# d) TODO: si en el futuro `person_identity` expone una función para
		# invalidar/reconstruir el snapshot operacional, llamarla acá. Hoy
		# `reconcile_person_identity` es solo un resolver de lectura, no
		# necesita invalidación explícita.

		# e) Comment auditable.
		comment_doc = frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Candidato",
			"reference_name": new_candidato_name,
			"content": (
				f"[CORRECCIÓN CÉDULA] campo=cedula | "
				f"valor_anterior={old_cedula} | valor_nuevo={nueva_cedula} | "
				f"motivo={doc.motivo} | solicitante={doc.solicitante} | "
				f"candidato_renamed=True | "
				f"ficha_empleado_renamed={ficha_renamed} | "
				f"ficha_empleado_old={old_persona} | "
				f"ficha_empleado_new={new_persona} | "
				f"user_username_actualizado={user_username_updated} | "
				f"user_name={old_user}"
			),
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.db.rollback(save_point="cedula_correction")
		raise

	# El propio doc de Corrección tiene `candidato` como Link al Candidato; como
	# Frappe rename_doc también propaga ese FK, `doc.candidato` ya quedó apuntando
	# al nuevo nombre. Retornamos el nuevo para que el caller sepa.
	return {
		"campo": "cedula",
		"candidato_old": candidato_name,
		"candidato_new": nueva_cedula,
		"valor_anterior": old_cedula,
		"valor_nuevo": nueva_cedula,
		"ficha_empleado_old": old_persona,
		"ficha_empleado_new": new_persona,
		"ficha_empleado_renamed": ficha_renamed,
		"user_username_actualizado": user_username_updated,
		"user_name": old_user,
		"afiliaciones_revisadas": [a["name"] for a in afiliaciones],
		"comment_id": comment_doc.name,
	}


def _apply_cuenta_change(doc):
	"""Cascada real de corrección de cuenta bancaria (Batch 3).

	`valor_nuevo` viene como JSON serializado con keys `numero_cuenta_bancaria`,
	`tipo_cuenta_bancaria`, `banco_siesa`. Si alguna key falta o llega vacía, se
	mantiene el valor actual del Candidato.

	Pasos:
	  1. Parsear y validar valor_nuevo (formato numérico, tipo válido, banco existe).
	  2. Dentro de un savepoint:
	     - Actualizar Candidato (3 campos).
	     - Detectar Contrato(s) submitted y actualizar `cuenta_bancaria`,
	       `tipo_cuenta_bancaria`, `banco_siesa` con `frappe.db.set_value`
	       (NO `doc.save()` porque rompería el submit).
	     - Manejo SIESA: como aún NO existe un campo `requires_resiesa` en la
	       app, dejamos un Comment explícito en Candidato y cada Contrato
	       afectado. TODO Batch posterior: agregar el campo y setearlo acá.
	     - Registrar Comment auditable en el Candidato con detalle del cambio.

	Rollback al savepoint si cualquier paso falla.
	"""
	candidato_name = doc.candidato

	# 1. Parseo de valor_nuevo.
	try:
		nuevo = frappe.parse_json(doc.valor_nuevo) if doc.valor_nuevo else None
	except Exception:
		frappe.throw(_("valor_nuevo no es JSON válido para cuenta bancaria."))
	if not isinstance(nuevo, dict):
		frappe.throw(_("valor_nuevo debe ser un objeto JSON con los campos bancarios."))

	# Datos actuales del candidato (los necesitamos como fallback y para el resumen).
	cand_row = frappe.db.get_value(
		"Candidato",
		candidato_name,
		["numero_cuenta_bancaria", "tipo_cuenta_bancaria", "banco_siesa"],
		as_dict=True,
	)
	if not cand_row:
		frappe.throw(_("Candidato no encontrado: {0}").format(candidato_name))

	valores_anteriores = {
		"numero_cuenta_bancaria": cand_row.get("numero_cuenta_bancaria"),
		"tipo_cuenta_bancaria": cand_row.get("tipo_cuenta_bancaria"),
		"banco_siesa": cand_row.get("banco_siesa"),
	}

	def _pick(key):
		# Mantenemos el valor actual si la key falta o llega vacía/None.
		val = nuevo.get(key)
		if val is None or (isinstance(val, str) and not val.strip()):
			return valores_anteriores[key]
		return val.strip() if isinstance(val, str) else val

	numero_nuevo = _pick("numero_cuenta_bancaria")
	tipo_nuevo = _pick("tipo_cuenta_bancaria")
	banco_nuevo = _pick("banco_siesa")

	# 2. Validaciones server-side.
	if not numero_nuevo or not _CUENTA_NUMERO_RE.match(str(numero_nuevo)):
		frappe.throw(_("Número de cuenta inválido: debe contener entre 4 y 30 dígitos."))
	if tipo_nuevo not in _TIPO_CUENTA_BANCARIA_OPTIONS:
		frappe.throw(
			_("Tipo de cuenta inválido: {0}. Opciones válidas: {1}").format(
				tipo_nuevo, ", ".join(sorted(_TIPO_CUENTA_BANCARIA_OPTIONS))
			)
		)
	if not banco_nuevo or not frappe.db.exists("Banco Siesa", banco_nuevo):
		frappe.throw(_("Banco Siesa no existe: {0}").format(banco_nuevo))

	valores_nuevos = {
		"numero_cuenta_bancaria": numero_nuevo,
		"tipo_cuenta_bancaria": tipo_nuevo,
		"banco_siesa": banco_nuevo,
	}

	# 3. Detectar Contrato(s) submitted. En teoría hay máximo 1, pero nos
	# defendemos contra múltiples.
	contratos = frappe.get_all(
		"Contrato",
		filters={"candidato": candidato_name, "docstatus": 1},
		pluck="name",
	)

	# 4. Operación atómica vía savepoint.
	frappe.db.savepoint("cuenta_correction")
	try:
		frappe.db.set_value("Candidato", candidato_name, valores_nuevos)

		# Mapeo Candidato → Contrato: numero_cuenta_bancaria → cuenta_bancaria.
		contrato_updates = {
			"cuenta_bancaria": numero_nuevo,
			"tipo_cuenta_bancaria": tipo_nuevo,
			"banco_siesa": banco_nuevo,
		}
		for contrato_name in contratos:
			# Contrato puede estar submitted (docstatus=1). Usar `frappe.db.set_value`
			# directo NO dispara validaciones del doc (eso es lo que queremos en una
			# corrección administrativa). Un `doc.save()` rompería el submit.
			frappe.db.set_value("Contrato", contrato_name, contrato_updates)

		# 5. Manejo SIESA. TODO: cuando exista el campo `requires_resiesa` en
		# Candidato/Contrato/Datos Contratacion, setearlo acá en vez de comment.
		siesa_flag_set = False
		siesa_comment_added = False
		siesa_msg = (
			"[CORRECCIÓN CUENTA] Cuenta bancaria modificada después de export "
			"SIESA — requiere re-exportación manual."
		)
		# Comment SIESA en Candidato.
		frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Candidato",
			"reference_name": candidato_name,
			"content": siesa_msg,
		}).insert(ignore_permissions=True)
		siesa_comment_added = True
		# Comment SIESA en cada Contrato afectado.
		for contrato_name in contratos:
			frappe.get_doc({
				"doctype": "Comment",
				"comment_type": "Info",
				"reference_doctype": "Contrato",
				"reference_name": contrato_name,
				"content": siesa_msg,
			}).insert(ignore_permissions=True)

		# 6. Comment auditable principal en el Candidato.
		comment_doc = frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Candidato",
			"reference_name": candidato_name,
			"content": (
				f"[CORRECCIÓN CUENTA] campo=cuenta_bancaria | "
				f"valor_anterior={frappe.as_json(valores_anteriores)} | "
				f"valor_nuevo={frappe.as_json(valores_nuevos)} | "
				f"motivo={doc.motivo} | solicitante={doc.solicitante} | "
				f"contratos_actualizados={contratos} | "
				f"siesa_flag_set={siesa_flag_set} | "
				f"siesa_comment_added={siesa_comment_added}"
			),
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.db.rollback(save_point="cuenta_correction")
		raise

	return {
		"campo": "cuenta_bancaria",
		"candidato": candidato_name,
		"valores_anteriores": valores_anteriores,
		"valores_nuevos": valores_nuevos,
		"contratos_actualizados": contratos,
		"siesa_flag_set": siesa_flag_set,
		"siesa_comment_added": siesa_comment_added,
		"comment_id": comment_doc.name,
	}


def _apply_personal_data_change(doc):
	"""Cascada de corrección de datos personales del candidato.

	`valor_nuevo` viene como JSON serializado con un subconjunto de
	`PERSONAL_DATA_FIELDS`. Solo se actualizan las keys presentes (cambios
	parciales). Keys fuera del whitelist se rechazan.

	Pasos:
	  1. Parseo + filtrado contra `PERSONAL_DATA_FIELDS`.
	  2. Validaciones específicas (strings no vacíos para nombres, fechas
		 razonables, Selects con opciones válidas, Links existentes).
	  3. Dentro de un savepoint:
		 - Actualizar Candidato con el dict de cambios efectivos.
		 - Si cambia algún nombre: cascada a User (first_name/last_name/full_name).
		 - Cascada a Ficha Empleado para los campos en común (nombres/apellidos).
		 - Cascada a Contrato(s) submitted: refrescar snapshot de nombres si cambió.
		 - Registrar Comment auditable con detalle de campos cambiados.

	Rollback al savepoint si cualquier paso falla.
	"""
	candidato_name = doc.candidato

	# 1. Parseo de valor_nuevo.
	try:
		nuevo = frappe.parse_json(doc.valor_nuevo) if doc.valor_nuevo else None
	except Exception:
		frappe.throw(_("valor_nuevo no es JSON válido para datos_personales."))
	if not isinstance(nuevo, dict):
		frappe.throw(_("valor_nuevo debe ser un objeto JSON con los campos a corregir."))

	# 1.b Whitelist + remoción de keys vacías (None / "" cuentan como "no enviado",
	# salvo en `segundo_apellido` y otros campos que admiten vacío explícito).
	# Para evitar ambigüedad: si la key viene como cadena vacía, INTERPRETAMOS
	# como "borrar a vacío" SOLO para campos no requeridos. Para los nombres
	# requeridos (`nombres`, `primer_apellido`), cadena vacía es error.
	allowed = set(PERSONAL_DATA_FIELDS)
	unknown_keys = [k for k in nuevo.keys() if k not in allowed]
	if unknown_keys:
		frappe.throw(
			_("Campos no permitidos en datos_personales: {0}").format(", ".join(unknown_keys))
		)

	# Filtramos None (no cambio); strings vacíos se permiten para campos opcionales,
	# pero ojo: para los requeridos validamos abajo.
	cambios = {}
	for key, val in nuevo.items():
		if val is None:
			continue
		# Normalizar strings: trim. Para Check (es_extranjero) Frappe usa 0/1.
		if isinstance(val, str):
			val = val.strip()
		cambios[key] = val

	if not cambios:
		frappe.throw(_("No se detectaron cambios para aplicar."))

	# 2. Estado actual del candidato (snapshot completo para diff y rollback lógico).
	row_actual = frappe.db.get_value(
		"Candidato",
		candidato_name,
		list(PERSONAL_DATA_FIELDS) + ["user", "persona"],
		as_dict=True,
	)
	if not row_actual:
		frappe.throw(_("Candidato no encontrado: {0}").format(candidato_name))

	old_user = row_actual.get("user")
	old_persona = row_actual.get("persona")
	valores_anteriores = {k: row_actual.get(k) for k in PERSONAL_DATA_FIELDS}

	# 3. Validaciones específicas.
	def _require_non_empty(key, label):
		if key in cambios and (cambios[key] is None or cambios[key] == ""):
			frappe.throw(_("{0} no puede quedar vacío.").format(label))

	_require_non_empty("nombres", "Nombres")
	_require_non_empty("primer_apellido", "Primer apellido")

	# Si NO se manda `nombres` pero el actual está vacío, no podemos validar
	# que quede al menos un nombre. Asumimos invariante de DB (campo reqd).

	# Fechas.
	for date_key, must_be_past in (("fecha_nacimiento", True), ("fecha_expedicion", True)):
		if date_key in cambios and cambios[date_key]:
			try:
				parsed = frappe.utils.getdate(cambios[date_key])
			except Exception:
				frappe.throw(_("{0} no es una fecha válida.").format(date_key))
			cambios[date_key] = parsed
			if must_be_past and parsed > frappe.utils.getdate(frappe.utils.nowdate()):
				frappe.throw(_("{0} no puede ser una fecha futura.").format(date_key))

	# Selects.
	if "genero" in cambios and cambios["genero"] and cambios["genero"] not in _GENERO_OPTIONS:
		frappe.throw(
			_("Género inválido: {0}. Opciones: {1}").format(
				cambios["genero"], ", ".join(sorted(_GENERO_OPTIONS))
			)
		)
	if (
		"estado_civil" in cambios
		and cambios["estado_civil"]
		and cambios["estado_civil"] not in _ESTADO_CIVIL_OPTIONS
	):
		frappe.throw(
			_("Estado civil inválido: {0}. Opciones: {1}").format(
				cambios["estado_civil"], ", ".join(sorted(_ESTADO_CIVIL_OPTIONS))
			)
		)
	if (
		"localidad" in cambios
		and cambios["localidad"]
		and cambios["localidad"] not in _LOCALIDAD_OPTIONS
	):
		frappe.throw(
			_("Localidad inválida: {0}").format(cambios["localidad"])
		)

	# Check (es_extranjero) — normalizar a 0/1.
	if "es_extranjero" in cambios:
		raw = cambios["es_extranjero"]
		if isinstance(raw, bool):
			cambios["es_extranjero"] = 1 if raw else 0
		elif isinstance(raw, (int,)):
			cambios["es_extranjero"] = 1 if raw else 0
		elif isinstance(raw, str):
			cambios["es_extranjero"] = 1 if raw in ("1", "true", "True", "Si", "si") else 0
		else:
			frappe.throw(_("es_extranjero debe ser 0/1 o booleano."))

	# Links.
	if "nivel_educativo_siesa" in cambios and cambios["nivel_educativo_siesa"]:
		if not frappe.db.exists("Nivel Educativo Siesa", cambios["nivel_educativo_siesa"]):
			frappe.throw(
				_("Nivel Educativo Siesa no existe: {0}").format(cambios["nivel_educativo_siesa"])
			)
	if "ciudad" in cambios and cambios["ciudad"]:
		if not frappe.db.exists("Ciudad", cambios["ciudad"]):
			frappe.throw(_("Ciudad no existe: {0}").format(cambios["ciudad"]))

	# 4. Detectar Contrato(s) submitted para refrescar snapshot de nombres si aplica.
	name_fields_changed = _PERSONAL_NAME_FIELDS & set(cambios.keys())
	contratos_a_actualizar = []
	if name_fields_changed:
		contratos_a_actualizar = frappe.get_all(
			"Contrato",
			filters={"candidato": candidato_name, "docstatus": 1},
			pluck="name",
		)

	# 5. Operación atómica vía savepoint.
	frappe.db.savepoint("personal_data_correction")
	ficha_campos_actualizados = []
	contratos_actualizados = []
	user_actualizado = False
	try:
		# a) Candidato — set_value con dict aplica todos los campos en una sola
		# operación. `frappe.db.set_value` acepta dict como tercer argumento.
		frappe.db.set_value("Candidato", candidato_name, cambios)

		# b) User: solo si cambian nombres/apellidos.
		if name_fields_changed and old_user and frappe.db.exists("User", old_user):
			# Valores efectivos (post-cambio) para construir first/last.
			efectivo = dict(valores_anteriores)
			efectivo.update({k: cambios[k] for k in cambios if k in PERSONAL_DATA_FIELDS})
			first_name = (efectivo.get("nombres") or "").strip()
			# Para last_name preferimos `apellidos` si existe (campo combinado),
			# sino concatenamos primer + segundo.
			last_name = (efectivo.get("apellidos") or "").strip()
			if not last_name:
				last_name = " ".join(
					p for p in [
						(efectivo.get("primer_apellido") or "").strip(),
						(efectivo.get("segundo_apellido") or "").strip(),
					] if p
				)
			full_name = " ".join(p for p in [first_name, last_name] if p)
			frappe.db.set_value(
				"User",
				old_user,
				{
					"first_name": first_name,
					"last_name": last_name,
					"full_name": full_name,
				},
			)
			user_actualizado = True

		# c) Ficha Empleado: cascada de campos en común.
		if old_persona and frappe.db.exists("Ficha Empleado", old_persona):
			ficha_update = {}
			efectivo = dict(valores_anteriores)
			efectivo.update({k: cambios[k] for k in cambios if k in PERSONAL_DATA_FIELDS})
			for field in _FICHA_COMMON_FIELDS:
				if field in cambios:
					# Para `apellidos` derivado: si no llegó pero cambió primer/segundo,
					# recomponemos. Pero como _FICHA_COMMON_FIELDS solo lista los que
					# Ficha tiene, basta con copiar el valor efectivo.
					ficha_update[field] = efectivo.get(field)
			# Caso especial: si cambió primer/segundo pero NO `apellidos`, recomponer.
			if (
				("primer_apellido" in cambios or "segundo_apellido" in cambios)
				and "apellidos" not in cambios
			):
				recompuesto = " ".join(
					p for p in [
						(efectivo.get("primer_apellido") or "").strip(),
						(efectivo.get("segundo_apellido") or "").strip(),
					] if p
				)
				if recompuesto:
					ficha_update["apellidos"] = recompuesto
			if ficha_update:
				frappe.db.set_value("Ficha Empleado", old_persona, ficha_update)
				ficha_campos_actualizados = list(ficha_update.keys())

		# d) Contrato(s) submitted: refrescar snapshot de nombres.
		if contratos_a_actualizar:
			efectivo = dict(valores_anteriores)
			efectivo.update({k: cambios[k] for k in cambios if k in PERSONAL_DATA_FIELDS})
			contrato_update = {}
			if "nombres" in cambios:
				contrato_update["nombres"] = efectivo.get("nombres")
			# Para `apellidos` en Contrato: usar el campo combinado si llegó, o
			# recomponer desde primer+segundo.
			if "apellidos" in cambios:
				contrato_update["apellidos"] = efectivo.get("apellidos")
			elif "primer_apellido" in cambios or "segundo_apellido" in cambios:
				contrato_update["apellidos"] = " ".join(
					p for p in [
						(efectivo.get("primer_apellido") or "").strip(),
						(efectivo.get("segundo_apellido") or "").strip(),
					] if p
				)
			if contrato_update:
				for contrato_name in contratos_a_actualizar:
					# set_value sobre doc submitted: NO dispara validaciones del doc.
					frappe.db.set_value("Contrato", contrato_name, contrato_update)
					contratos_actualizados.append(contrato_name)

		# e) Comment auditable.
		campos_str = ", ".join(sorted(cambios.keys()))
		comment_doc = frappe.get_doc({
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Candidato",
			"reference_name": candidato_name,
			"content": (
				f"[CORRECCIÓN DATOS PERSONALES] campos=[{campos_str}] | "
				f"valores_anteriores={frappe.as_json({k: valores_anteriores.get(k) for k in cambios})} | "
				f"valores_nuevos={frappe.as_json(cambios)} | "
				f"motivo={doc.motivo} | solicitante={doc.solicitante} | "
				f"user_actualizado={user_actualizado} | "
				f"ficha_campos={ficha_campos_actualizados} | "
				f"contratos_actualizados={contratos_actualizados}"
			),
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.db.rollback(save_point="personal_data_correction")
		raise

	return {
		"campo": "datos_personales",
		"candidato": candidato_name,
		"campos_cambiados": {k: cambios[k] for k in cambios},
		"valores_anteriores": {k: valores_anteriores.get(k) for k in cambios},
		"user_actualizado": user_actualizado,
		"ficha_empleado_actualizada": ficha_campos_actualizados,
		"contratos_actualizados": contratos_actualizados,
		"comment_id": comment_doc.name,
	}


# ---------------------------------------------------------------------------
# Utilidades para el panel UI (Batch 1: ya disponibles, se consumen en Batch 8)
# ---------------------------------------------------------------------------

def get_bank_certification_file(candidato_name: str) -> Optional[str]:
	"""Devuelve el `file_url` de la certificación bancaria adjunta al candidato.

	Busca en `Person Document` con `person_type='Candidato'` y `document_type`
	que matchee `'Certificación bancaria%'`. Devuelve `None` si no hay adjunto.

	Permission check NO se realiza acá — eso es responsabilidad del endpoint
	whitelisted (`api/correcciones.get_bank_cert_url`).
	"""
	if not candidato_name:
		return None
	rows = frappe.get_all(
		"Person Document",
		filters={
			"person_type": "Candidato",
			"person": candidato_name,
			"document_type": ["like", "Certificación bancaria%"],
		},
		fields=["file"],
		limit=1,
		order_by="modified desc",
	)
	return rows[0]["file"] if rows else None
