import frappe

from hubgh.person_identity import resolve_user_for_employee
from hubgh.lms.hardening import (
	get_lms_course_name,
	increment_lms_metric,
	lms_doctypes_available,
	log_lms_event,
	run_with_lms_retry,
)


def enrolar_empleado_en_calidad(doc, method=None):
	"""Auto-enrola empleados activos con usuario válido en el curso de calidad."""
	if not _lms_disponible():
		log_lms_event(
			event="enrollment.auto",
			status="skip",
			context={"reason": "lms_unavailable", "empleado": getattr(doc, "name", None)},
		)
		increment_lms_metric("enrollment.auto", "skip")
		return

	if getattr(doc, "estado", None) != "Activo":
		log_lms_event(
			event="enrollment.auto",
			status="skip",
			context={"reason": "employee_inactive", "empleado": getattr(doc, "name", None)},
		)
		increment_lms_metric("enrollment.auto", "skip")
		return

	user_email = _resolver_usuario_empleado(doc)
	if not user_email:
		log_lms_event(
			event="enrollment.auto",
			status="skip",
			context={"reason": "user_not_resolved", "empleado": getattr(doc, "name", None)},
		)
		increment_lms_metric("enrollment.auto", "skip")
		return

	course_name = get_lms_course_name()
	context = {
		"empleado": getattr(doc, "name", None),
		"user": user_email,
		"course": course_name,
	}

	_asignar_rol_lms_student(user_email, context=context)
	_crear_enrollment_si_no_existe(user_email, course_name, context=context)


def verificar_enrolamiento_calidad(doc, method=None):
	"""Verifica enrolamiento cuando se actualiza ficha de empleado."""
	enrolar_empleado_en_calidad(doc, method=method)


def _resolver_usuario_empleado(doc):
	identity = resolve_user_for_employee(doc)
	return identity.user if identity and identity.user else None


def _lms_disponible():
	return lms_doctypes_available(["LMS Enrollment", "LMS Course"])


def _asignar_rol_lms_student(user_email, context=None):
	def _do_assign_role():
		user = frappe.get_doc("User", user_email)
		roles = [r.role for r in (user.roles or [])]
		if "LMS Student" in roles:
			log_lms_event(
				event="role.assign_lms_student",
				status="skip",
				context={**(context or {}), "reason": "already_assigned"},
			)
			increment_lms_metric("role.assign_lms_student", "skip")
			return

		user.append("roles", {"role": "LMS Student"})
		user.save(ignore_permissions=True)
		log_lms_event(event="role.assign_lms_student", status="success", context=context)

	run_with_lms_retry(
		"role.assign_lms_student",
		_do_assign_role,
		context=context,
		default=None,
		raise_on_failure=False,
		log_success=False,
	)


def _crear_enrollment_si_no_existe(user_email, course_name, context=None):
	ctx = {**(context or {}), "user": user_email, "course": course_name}

	course_exists = run_with_lms_retry(
		"enrollment.course_exists_check",
		lambda: bool(frappe.db.exists("LMS Course", course_name)),
		context=ctx,
		default=False,
	)
	if not course_exists:
		log_lms_event(
			event="enrollment.auto",
			status="skip",
			context={**ctx, "reason": "course_not_found"},
		)
		increment_lms_metric("enrollment.auto", "skip")
		return

	existing = run_with_lms_retry(
		"enrollment.exists_check",
		lambda: frappe.db.exists("LMS Enrollment", {"member": user_email, "course": course_name}),
		context=ctx,
		default=None,
	)
	if existing:
		log_lms_event(
			event="enrollment.auto",
			status="skip",
			context={**ctx, "reason": "already_enrolled", "enrollment": existing},
		)
		increment_lms_metric("enrollment.auto", "skip")
		return

	def _do_insert_enrollment():
		enrollment = frappe.get_doc(
			{
				"doctype": "LMS Enrollment",
				"member": user_email,
				"course": course_name,
				"member_type": "Student",
				"role": "Member",
			}
		)
		enrollment.insert(ignore_permissions=True)
		frappe.db.commit()
		return enrollment.name

	enrollment_name = run_with_lms_retry(
		"enrollment.create",
		_do_insert_enrollment,
		context=ctx,
		default=None,
	)
	if enrollment_name:
		log_lms_event(
			event="enrollment.auto",
			status="success",
			context={**ctx, "enrollment": enrollment_name},
		)
