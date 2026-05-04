__version__ = "0.0.1"


# ---------------------------------------------------------------------------
# Dev-only outgoing email redirect
# ---------------------------------------------------------------------------
#
# Activated when site_config (or common_site_config) has
# `hubgh_dev_email_override` set to a non-empty email address. Every call to
# `frappe.sendmail` then has its `recipients` / `cc` / `bcc` rewritten to that
# single address, and the subject is prefixed with `[DEV→<address>]` so the
# operator can tell the email did not reach its real destinations.
#
# When the flag is unset (or empty) the wrapper is a no-op and forwards every
# argument unchanged — that is the production state.
#
# Removed by clearing `hubgh_dev_email_override` in site_config.
def _install_dev_email_redirect():
	import functools
	import inspect

	import frappe

	if getattr(frappe.sendmail, "_hubgh_dev_redirect_installed", False):
		return

	_original = frappe.sendmail
	_sig = inspect.signature(_original)

	@functools.wraps(_original)
	def wrapper(*args, **kwargs):
		try:
			override = (frappe.conf.get("hubgh_dev_email_override") or "").strip()
		except Exception:
			override = ""

		if not override:
			return _original(*args, **kwargs)

		try:
			bound = _sig.bind_partial(*args, **kwargs)
			bound.arguments["recipients"] = [override]
			bound.arguments["cc"] = None
			bound.arguments["bcc"] = None
			subject = bound.arguments.get("subject") or "No Subject"
			if not str(subject).startswith("[DEV"):
				bound.arguments["subject"] = f"[DEV→{override}] {subject}"
			return _original(**bound.arguments)
		except Exception:
			# Fail open: if rebinding fails for any reason, fall back to the
			# original call so the dev redirect never breaks real flows.
			return _original(*args, **kwargs)

	wrapper._hubgh_dev_redirect_installed = True
	frappe.sendmail = wrapper


_install_dev_email_redirect()
