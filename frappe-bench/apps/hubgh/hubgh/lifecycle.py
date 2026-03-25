from hubgh.access_profiles import sync_user_access_profile
from hubgh.hubgh.bienestar_automation import ensure_ingreso_followups_for_employee
from hubgh.lms.integration_hooks import enrolar_empleado_en_calidad, verificar_enrolamiento_calidad
from hubgh.setup_user_defaults import setup_user_home_page
from hubgh.user_groups import sync_user_groups_on_employee_change, sync_user_groups_on_user_change
import frappe


# Backward-compatible alias for tests/integrations importing legacy symbol.
ensure_bienestar_process_for_employee = ensure_ingreso_followups_for_employee


def on_user_create(doc, method=None):
	setup_user_home_page(doc=doc, method=method)
	sync_user_access_profile(doc.name)
	sync_user_groups_on_user_change(doc=doc, method=method)


def on_user_update(doc, method=None):
	logger = frappe.logger("hubgh.user_groups")
	setup_user_home_page(doc=doc, method=method)
	sync_user_access_profile(doc.name)
	logger.info(
		"on_user_update:before_sync_user_groups",
		extra={
			"user_doc": doc.name,
			"session_user": frappe.session.user,
			"method": method,
		},
	)
	if frappe.session.user == "Guest":
		logger.info(
			"on_user_update:skip_sync_user_groups_for_guest",
			extra={
				"user_doc": doc.name,
				"session_user": frappe.session.user,
				"method": method,
			},
		)
		return
	sync_user_groups_on_user_change(doc=doc, method=method)


def on_ficha_empleado_insert(doc, method=None):
	enrolar_empleado_en_calidad(doc, method=method)
	ensure_bienestar_process_for_employee(doc, from_source="Ficha Empleado.after_insert")
	sync_user_groups_on_employee_change(doc=doc, method=method)


def on_ficha_empleado_update(doc, method=None):
	verificar_enrolamiento_calidad(doc, method=method)
	ensure_bienestar_process_for_employee(doc, from_source="Ficha Empleado.on_update")
	sync_user_groups_on_employee_change(doc=doc, method=method)
