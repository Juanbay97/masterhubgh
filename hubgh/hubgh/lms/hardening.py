import json
import time

import frappe


DEFAULT_LMS_COURSE_NAME = "calidad-e-inocuidad-alimentaria"
DEFAULT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_DELAY_MS = 150
METRICS_CACHE_KEY = "hubgh:lms:integration:metrics"


def get_lms_course_name():
	"""Resuelve el curso LMS principal de HubGH (site config -> settings -> fallback)."""
	from_site = (frappe.conf.get("hubgh_lms_course_name") or "").strip()
	if from_site:
		return from_site

	for fieldname in ["hubgh_lms_course_name", "default_course", "course"]:
		value = _get_single_setting_value("LMS Settings", fieldname)
		if value:
			return value

	log_lms_event(
		event="config.course_name",
		status="fallback",
		context={"fallback_course": DEFAULT_LMS_COURSE_NAME},
	)
	return DEFAULT_LMS_COURSE_NAME


def get_lms_retry_attempts():
	"""Resuelve el número de intentos para operaciones LMS críticas."""
	from_site = _to_positive_int(frappe.conf.get("hubgh_lms_retry_attempts"), default=None)
	if from_site is not None:
		return from_site

	value = _get_single_setting_value("LMS Settings", "hubgh_lms_retry_attempts")
	setting_attempts = _to_positive_int(value, default=None)
	if setting_attempts is not None:
		return setting_attempts

	return DEFAULT_RETRY_ATTEMPTS


def get_lms_retry_delay_seconds():
	"""Delay entre reintentos LMS en segundos."""
	from_site = _to_positive_int(frappe.conf.get("hubgh_lms_retry_delay_ms"), default=None)
	if from_site is not None:
		return from_site / 1000.0

	value = _get_single_setting_value("LMS Settings", "hubgh_lms_retry_delay_ms")
	setting_delay_ms = _to_positive_int(value, default=None)
	if setting_delay_ms is not None:
		return setting_delay_ms / 1000.0

	return DEFAULT_RETRY_DELAY_MS / 1000.0


def run_with_lms_retry(
	operation,
	func,
	*,
	context=None,
	default=None,
	raise_on_failure=False,
	log_success=False,
):
	"""Ejecuta una operación LMS con reintentos acotados y observabilidad."""
	attempts = get_lms_retry_attempts()
	delay = get_lms_retry_delay_seconds()
	ctx = dict(context or {})

	for attempt in range(1, attempts + 1):
		try:
			result = func()
			if log_success:
				log_lms_event(
					event=operation,
					status="success",
					context={**ctx, "attempt": attempt, "attempts": attempts},
				)
			increment_lms_metric(operation, "success")
			return result
		except Exception as exc:
			is_last = attempt >= attempts
			status = "error" if is_last else "retry"
			log_lms_event(
				event=operation,
				status=status,
				context={**ctx, "attempt": attempt, "attempts": attempts},
				error=exc,
			)
			increment_lms_metric(operation, status)

			if is_last:
				if raise_on_failure:
					raise
				return default

			if delay > 0:
				time.sleep(delay)

	return default


def log_lms_event(event, status, context=None, error=None):
	"""Emite logs estructurados de integración LMS."""
	payload = {
		"domain": "hubgh.lms.integration",
		"event": event,
		"status": status,
		"context": context or {},
	}
	if error:
		payload["error"] = str(error)
		payload["error_type"] = type(error).__name__

	logger = frappe.logger("hubgh.lms")
	line = json.dumps(payload, ensure_ascii=False, default=str)
	if status == "error":
		logger.error(line)
	else:
		logger.info(line)


def increment_lms_metric(endpoint, status):
	"""Incrementa contadores operativos de LMS en cache."""
	metric_key = f"{endpoint}:{status}"
	try:
		frappe.cache().hincrby(METRICS_CACHE_KEY, metric_key, 1)
	except Exception:
		# No bloquear el flujo principal por fallos de observabilidad
		pass


def get_lms_metrics_snapshot():
	"""Obtiene snapshot de métricas LMS acumuladas en cache."""
	try:
		raw = frappe.cache().hgetall(METRICS_CACHE_KEY) or {}
	except Exception:
		return {}

	parsed = {}
	for key, value in raw.items():
		k = key.decode() if isinstance(key, bytes) else str(key)
		try:
			parsed[k] = int(value)
		except Exception:
			try:
				parsed[k] = int((value.decode() if isinstance(value, bytes) else value) or 0)
			except Exception:
				parsed[k] = 0
	return parsed


def lms_doctypes_available(required_doctypes):
	"""Valida disponibilidad de doctypes LMS requeridos sin propagar excepción."""
	try:
		return all(frappe.db.exists("DocType", dt) for dt in required_doctypes)
	except Exception as exc:
		log_lms_event(
			event="lms.doctypes_check",
			status="error",
			context={"required_doctypes": required_doctypes},
			error=exc,
		)
		increment_lms_metric("lms.doctypes_check", "error")
		return False


def _get_single_setting_value(doctype, fieldname):
	if not frappe.db.exists("DocType", doctype):
		return ""

	try:
		value = frappe.db.get_single_value(doctype, fieldname)
		return (str(value).strip() if value is not None else "")
	except Exception:
		return ""


def _to_positive_int(value, default):
	try:
		parsed = int(value)
		return parsed if parsed > 0 else default
	except Exception:
		return default
