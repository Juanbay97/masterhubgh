import frappe

from hubgh.lms.hardening import (
	get_lms_course_name,
	get_lms_retry_attempts,
	get_lms_retry_delay_seconds,
	log_lms_event,
)


def setup_lms_settings():
	"""Configura valores base de LMS para HubGH."""
	if not frappe.db.exists("DocType", "LMS Settings"):
		frappe.throw("LMS Settings no existe. Instala la app LMS primero.")

	settings = frappe.get_single("LMS Settings")
	settings.site_name = "HubGH Capacitación"
	settings.description = "Plataforma de capacitación interna"
	settings.disable_self_learning = 0
	settings.allow_guest_access = 0
	if hasattr(settings, "enable_program"):
		settings.enable_program = 1

	resolved_course = get_lms_course_name()
	if hasattr(settings, "hubgh_lms_course_name"):
		settings.hubgh_lms_course_name = resolved_course

	if hasattr(settings, "hubgh_lms_retry_attempts"):
		settings.hubgh_lms_retry_attempts = get_lms_retry_attempts()

	if hasattr(settings, "hubgh_lms_retry_delay_ms"):
		settings.hubgh_lms_retry_delay_ms = int(get_lms_retry_delay_seconds() * 1000)

	settings.save(ignore_permissions=True)
	frappe.db.commit()

	log_lms_event(
		event="setup.settings",
		status="success",
		context={
			"course": resolved_course,
			"retry_attempts": get_lms_retry_attempts(),
			"retry_delay_seconds": get_lms_retry_delay_seconds(),
		},
	)

	return {
		"ok": True,
		"site_name": settings.site_name,
		"hubgh_lms_course_name": resolved_course,
		"hubgh_lms_retry_attempts": get_lms_retry_attempts(),
		"hubgh_lms_retry_delay_seconds": get_lms_retry_delay_seconds(),
	}
