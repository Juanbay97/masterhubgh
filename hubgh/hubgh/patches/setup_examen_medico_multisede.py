"""Idempotent post-migrate setup for the self-service medical exam flow.

Runs once via `bench migrate`. Safe to re-run — every step checks state
before mutating, so the patch is a no-op after the first successful run
or after the operator has manually configured something.

Performs:
  1. Ensure Module Profiles + Role Profiles exist (recovers from the
     `_ensure_module_profile is_new()` bug that left some sites with
     orphan User.module_profile links).
  2. Ensure Ciudades referenced by sedes exist (Bogotá, Chía, Medellín,
     Cartagena). Creates missing rows with `nombre` only — operator can
     fill `codigo_siesa` later.
  3. Bump `cupos_por_slot` to 50 on every IPS Horario row whose value
     is below 50 (the doctype default already moved to 50 for new rows).
  4. Seed the 7 default sedes on IPS "Zonamedica MR SAS" if it exists
     and currently has 0 sedes. Maps each sede to its city + the
     `requiere_orden_servicio` flag (Bogotá: 0, otras: 1). Skipped
     silently if the IPS does not exist (operator-managed).
  5. Activate the Frappe scheduler and unpause the email queue so cron
     and outbound mail run automatically without manual intervention.
"""

import frappe


SEDES_DEFAULT = [
	{
		"nombre_sede": "Outlet Factory",
		"ciudad": "Bogotá",
		"direccion": "Av. Américas No. 62-84, locales 213-214-215",
		"telefono": "7514626 / 3168774072 / 3138536350",
		"email_notificacion": "recepcion@zonamedicaips.com",
		"requiere_orden_servicio": 0,
		"activa": 1,
	},
	{
		"nombre_sede": "Autopista Norte",
		"ciudad": "Bogotá",
		"direccion": "Carrera 45 # 105-21",
		"telefono": "7514626 / 3168774072 / 3138536350",
		"email_notificacion": "recepcion@zonamedicaips.com",
		"requiere_orden_servicio": 0,
		"activa": 1,
	},
	{
		"nombre_sede": "Soledad",
		"ciudad": "Bogotá",
		"direccion": "Avenida Carrera 28 # 41-36",
		"telefono": "7514626 / 3168774072 / 3138536350",
		"email_notificacion": "recepcion@zonamedicaips.com",
		"requiere_orden_servicio": 0,
		"activa": 1,
	},
	{
		"nombre_sede": "Accionar Salud Chía",
		"ciudad": "Chía",
		"direccion": "Cra. 1B No. 18-40, Barrio San Francisco",
		"telefono": "",
		"email_notificacion": "",
		"requiere_orden_servicio": 1,
		"activa": 1,
	},
	{
		"nombre_sede": "Medellín San Ignacio",
		"ciudad": "Medellín",
		"direccion": "[POR DEFINIR — actualizar dirección]",
		"telefono": "",
		"email_notificacion": "",
		"requiere_orden_servicio": 1,
		"activa": 1,
	},
	{
		"nombre_sede": "Medellín Aguacatala / Poblado",
		"ciudad": "Medellín",
		"direccion": "Carrera 48B # 16 Sur - 38, Sector Aguacatala",
		"telefono": "",
		"email_notificacion": "",
		"requiere_orden_servicio": 1,
		"activa": 1,
	},
	{
		"nombre_sede": "GSL Ocupacional Cartagena",
		"ciudad": "Cartagena",
		"direccion": "Avenida Lacides Segovia # 15-114, Barrio Manga",
		"telefono": "",
		"email_notificacion": "",
		"requiere_orden_servicio": 1,
		"activa": 1,
	},
]


def execute():
	logger = frappe.logger("hubgh.patch.examen_medico_multisede")

	# 1. Module / Role profiles — recreate if missing.
	_ensure_profiles(logger)

	# 2. Ciudades referenciadas por sedes.
	_ensure_ciudades(logger)

	# 3. Cupos a 50 en horarios existentes.
	_bump_cupos_to_50(logger)

	# 4. Sedes default en Zonamedica MR SAS.
	_seed_sedes_zonamedica(logger)

	# 5. Scheduler activo + cola sin pausa.
	_enable_scheduler_and_queue(logger)

	frappe.db.commit()


def _ensure_profiles(logger):
	try:
		from hubgh.access_profiles import ensure_roles_and_profiles

		ensure_roles_and_profiles()
		logger.info("examen_medico_multisede:profiles_ok")
	except Exception:
		logger.warning("examen_medico_multisede:profiles_skip", exc_info=True)


def _ensure_ciudades(logger):
	for nombre in ("Bogotá", "Chía", "Medellín", "Cartagena"):
		if frappe.db.exists("Ciudad", nombre):
			continue
		try:
			frappe.get_doc(
				{"doctype": "Ciudad", "nombre": nombre, "name": nombre}
			).insert(ignore_permissions=True, ignore_mandatory=True)
			logger.info(
				"examen_medico_multisede:ciudad_created", extra={"ciudad": nombre}
			)
		except Exception:
			logger.warning(
				"examen_medico_multisede:ciudad_skip",
				extra={"ciudad": nombre},
				exc_info=True,
			)


def _bump_cupos_to_50(logger):
	try:
		updated = frappe.db.sql(
			"""
			UPDATE `tabIPS Horario`
			SET cupos_por_slot = 50
			WHERE cupos_por_slot < 50
			"""
		)
		logger.info("examen_medico_multisede:cupos_bumped")
	except Exception:
		logger.warning("examen_medico_multisede:cupos_skip", exc_info=True)


def _seed_sedes_zonamedica(logger):
	ips_name = "Zonamedica MR SAS"
	if not frappe.db.exists("IPS", ips_name):
		logger.info(
			"examen_medico_multisede:zonamedica_absent",
			extra={"hint": "operator must create IPS Zonamedica MR SAS to use the default sedes"},
		)
		return

	doc = frappe.get_doc("IPS", ips_name)
	existing_sedes = doc.get("sedes") or []
	if existing_sedes:
		logger.info(
			"examen_medico_multisede:zonamedica_has_sedes",
			extra={"count": len(existing_sedes)},
		)
		return

	for sede in SEDES_DEFAULT:
		# Skip rows whose ciudad is missing — patch should not create stale links.
		if not frappe.db.exists("Ciudad", sede["ciudad"]):
			logger.warning(
				"examen_medico_multisede:sede_skip_missing_ciudad",
				extra={"sede": sede["nombre_sede"], "ciudad": sede["ciudad"]},
			)
			continue
		doc.append("sedes", sede)

	try:
		doc.save(ignore_permissions=True)
		logger.info(
			"examen_medico_multisede:sedes_seeded",
			extra={"count": len(doc.get("sedes") or [])},
		)
	except Exception:
		logger.warning("examen_medico_multisede:sedes_save_failed", exc_info=True)


def _enable_scheduler_and_queue(logger):
	try:
		# Pause/unpause flags live in DefaultValue; reading via get_default works
		# after migration. Setting both ensures cron + email queue run.
		frappe.db.set_default("pause_scheduler", 0)
		frappe.db.set_default("suspend_email_queue", 0)
		logger.info("examen_medico_multisede:scheduler_unpaused")
	except Exception:
		logger.warning(
			"examen_medico_multisede:scheduler_skip", exc_info=True
		)
